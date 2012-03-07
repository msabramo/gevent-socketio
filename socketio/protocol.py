from __future__ import absolute_import, unicode_literals

from itertools import chain

import urlparse
import re
import gevent
import anyjson as json

from collections import namedtuple
from socketio.exceptions import DecodeError

from logging import getLogger
logger = getLogger("socketio.protocol")


class NamedInt(int):
    __slots__ = ("description")

    def __new__(self, value, description):
        x = int.__new__(self, value)
        x.description = description
        return x

    def __repr__(self):
        return "<{0} = 0>".format(self.description)

    def __eq__(self, other):
        if isinstance(other, basestring):
            return self.description == other
        return int.__eq__(self, other)


# Error reasons
REASONS = (
    NamedInt(0, "transport not supported"),
    NamedInt(1, "client not handshaken"),
    NamedInt(2, "unauthorized")
)

ADVICES = (
    NamedInt(0, "reconnect"),
)


Packet = namedtuple("Packet", "type, id, ack, endpoint, data")
AckPacket = namedtuple("AckPacket", Packet._fields + ("ackId", "args"))
ConnectPacket = namedtuple("ConnectPacket", Packet._fields + ("qs",))
ErrorPacket = namedtuple("ErrorPacket", Packet._fields + ("reason", "advice"))
EventPacket = namedtuple("AckPacket", Packet._fields + ("name", "args"))

class BaseProtocol(object):
    _PACKET_RE = re.compile(br"^(?P<type>[^:]+):(?P<id>[0-9]+)?(?P<ack>[+])?:(?P<endpoint>[^:]+)?:?(?P<data>.+)?$", re.DOTALL)

    PACKET_TYPES = {
        b"0": "disconnect",
        b"1": "connect",
        b"2": "heartbeat",
        b"3": "message",
        b"4": "json",
        b"5": "event",
        b"6": "ack",
        b"7": "error",
        b"8": "noop",
    }

    def decode_packet(self, rawdata):
        """
        The packet format is as follow:
        
            {type} ':' {id}? {ack}? ':' {endpoint} ':'? {data}
        
        where:
        
            * ``type`` is the packet type,
            * ``id`` is an optional integer specifing the packet's ID,
            * ``ack`` can be either omited or a ``'+'` character,
            * ``endpoint`` is a path specifying custom namespace,
            * ``data`` is any non-whitespace set of characters 
        """
        m = self._PACKET_RE.match(rawdata)
        if m is None:
            raise DecodeError("Malformed packet {0!r}".format(rawdata))
        packet = Packet(*m.groups())
        packet = packet._replace(
            type=self.PACKET_TYPES[packet.type],
            endpoint=packet.endpoint.decode('utf-8') if packet.endpoint else None,
            ack=("data" if packet.ack else True) if packet.id else None
        )
        postprocess = getattr(self, "_post_" + packet.type, None)
        if postprocess is not None:
            packet = postprocess(packet)
        return packet

    def _plus_split(self, data):
        i = data.find(b"+")
        if i < 0:
            return data, ''
        return data[:i], data[i + 1:]

    def _post_error(self, packet):
        if packet.data:
            reason, advice = self._plus_split(packet.data)
            reason = REASONS[int(reason)] if reason else ''
            advice = ADVICES[int(advice)] if advice else ''
        else:
            reason, advice = '', ''
        return ErrorPacket(packet.type, packet.id, packet.ack, packet.endpoint, None, reason, advice)

    def _post_json(self, packet):
        try:
            return packet._replace(data=self._parse_json(packet.data))
        except ValueError:
            raise DecodeError("Malformed JSON in data: %r" % packet.data)

    def _post_connect(self, packet):
        qs = urlparse.parse_qs(packet.data.decode('utf-8')[1:]) if packet.data else {}
        return ConnectPacket(packet.type, packet.id, packet.ack, packet.endpoint, None, qs)

    def _post_ack(self, packet):
        ackid, args = self._plus_split(packet.data)
        if args:
            try:
                args = self._parse_json(args)
            except ValueError:
                raise DecodeError("Malformed JSON in args: %r" % args)
        else:
            args = []
        return AckPacket(packet.type, packet.id, packet.ack, packet.endpoint, None, ackid, args)

    def _post_message(self, packet):
        return packet._replace(data=packet.data or b'')

    def _post_event(self, packet):
        try:
            data = self._parse_json(packet.data)
        except ValueError:
            raise DecodeError("Malformed JSON in event data: %r" % packet.data)
        return EventPacket(packet.type, packet.id, packet.ack, packet.endpoint, None, data["name"], data.get("args", []))

    def _parse_json(self, rawdata):
        return json.loads(rawdata)


class LegacyProtocol(BaseProtocol):
    """
    Legacy SocketIO protocol implementation, which works on dicts.
    """

    def __init__(self, handler):
        self.handler = handler
        self.session = None

    def ack(self, msg_id, params):
        self.send("6:::%s+%s" % (msg_id, json.dumps(params)))

    def emit(self, event, endpoint, *args):
        self.send("5::%s:%s" % (endpoint, json.dumps({'name': event,
                                                      'args': args})))

    def send(self, message, destination=None):
        if destination is None:
            dst_client = self.session
        else:
            dst_client = self.handler.server.sessions.get(destination)

        self._write(message, dst_client)

    def send_event(self, name, *args):
        self.send("5:::" + json.dumps({'name': name, 'args': args}))

    def receive(self):
        """Wait for incoming messages."""

        return self.session.get_server_msg()

    def broadcast(self, message, exceptions=None, include_self=False):
        """
        Send messages to all connected clients, except itself and some
        others.
        """

        if exceptions is None:
            exceptions = []

        if not include_self:
            exceptions.append(self.session.session_id)

        for session_id, session in self.handler.server.sessions.iteritems():
            if session_id not in exceptions:
                self._write(message, session)

    def broadcast_event(self, name, *args, **kwargs):
        self.broadcast("5:::" + json.dumps({'name': name, 'args': args}), **kwargs)

    def start_heartbeat(self):
        """Start the heartbeat Greenlet to check connection health."""
        def ping():
            self.session.state = self.session.STATE_CONNECTED

            while self.session.connected:
                gevent.sleep(5.0) # FIXME: make this a setting
                self.send("2::")

        return gevent.spawn(ping)

    def _write(self, message, session=None):
        if session is None:
            raise Exception("No client with that session exists")
        else:
            session.put_client_msg(message)

    def encode(self, message):
        if isinstance(message, basestring):
            encoded_msg = message
        elif isinstance(message, (object, dict)):
            return self.encode(json.dumps(message))
        else:
            raise ValueError("Can't encode message")

        return encoded_msg

    def decode(self, data):
        packet = self.decode_packet(data)
        return dict((k, v) for k, v in zip(packet._fields, packet) if v is not None)

SocketIOProtocol = LegacyProtocol

