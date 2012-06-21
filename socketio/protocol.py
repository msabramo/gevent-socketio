from __future__ import absolute_import, unicode_literals

import gevent
import weakref
import json

from logging import getLogger
from socketio.packets import AckPacket, EventPacket
logger = getLogger("socketio.protocol")


from .packets import Packet, NAME_FOR_PACKET, PACKET_BY_NAME


class BaseProtocol(object):

    def _decode_packet(self, rawdata):
        return Packet.decode(rawdata)

    def _encode_packet(self, packet):
        return packet.encode()


class LegacyProtocol(BaseProtocol):
    """
    Legacy SocketIO protocol implementation, which works on dicts.
    """

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        return self._session

    def ack(self, msg_id, params):
        self.send(AckPacket(None, None, "", msg_id, params).encode())

    def emit(self, event, endpoint, *args):
        self.send(EventPacket(None, None, endpoint, event, *args).encode())

    def send(self, message):
        dst_client = self.session
        self._write(message, dst_client)

    def send_event(self, name, *args):
        self.send("5:::" + json.dumps({'name': name, 'args': args}))

    def receive(self, timeout=None):
        """Wait for incoming messages."""
        return self._session.get_server_msg(timeout=timeout)

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
        """
        Encode dictionary into bytes with message.
        """
        if isinstance(message, basestring):
            return message
        cls = PACKET_BY_NAME[message.pop("type")]
        for f in cls._fields:
            message.setdefault(f, None)
        return self._encode_packet(cls(**message))

    def decode(self, data):
        packet = self._decode_packet(data)
        d = dict((k, v) for k, v in zip(packet._fields, packet) if v is not None)
        d["type"] = NAME_FOR_PACKET[type(packet)]
        return d

SocketIOProtocol = LegacyProtocol

