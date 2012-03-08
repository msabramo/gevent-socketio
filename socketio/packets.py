from __future__ import absolute_import, unicode_literals

import re
import urlparse
import anyjson as json

from collections import namedtuple
from socketio.exceptions import DecodeError


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

BASE_FIELDS = ("id", "ack", "endpoint")


class Packet(object):
    __slots__ = ()
    _PACKET_RE = re.compile(br"^(?P<type>\d{1,3}):(?P<id>[0-9]+)?(?P<ack>[+])?:(?P<endpoint>[^:]+)?:?(?P<data>.+)?$", re.DOTALL)

    @classmethod
    def decode(cls, rawdata):
        """
        The packet format is as follow:
        
            {type} ':' {id}? {ack}? ':' {endpoint} ':'? {data}
        
        where:
        
            * ``type`` is the packet type,
            * ``id`` is an optional integer specifying the packet's ID,
            * ``ack`` can be either ommited or a ``'+'` character,
            * ``endpoint`` is a path specifying custom namespace,
            * ``data`` is any non-whitespace set of characters 
        """
        m = cls._PACKET_RE.match(rawdata)
        if m is None:
            raise DecodeError("Malformed packet {0!r}".format(rawdata))
        data = m.groupdict()
        type_ = int(data.pop("type"))
        try:
            packet_cls = PACKET_TYPES[type_]
        except IndexError:
            raise DecodeError("Unknown packet type: %d" % type_)
        return packet_cls.from_data(**data)

    @classmethod
    def from_data(cls, id, ack, endpoint, *args, **kwargs):
        return cls(id, ("data" if ack else True) if id else None,
                   endpoint.decode('utf-8') if endpoint else None, *args)

    @staticmethod
    def _plus_split(data):
        i = data.find(b"+")
        if i < 0:
            return data, ''
        return data[:i], data[i + 1:]

    @staticmethod
    def _parse_json(data):
        try:
            return json.loads(data)
        except ValueError:
            raise DecodeError("Malformed JSON data: %r" % data)


class ErrorPacket(Packet, namedtuple("_ErrorPacket", BASE_FIELDS + ("reason", "advice"))):
    __slots__ = ()

    # Error reasons
    REASONS = (
        NamedInt(0, "transport not supported"),
        NamedInt(1, "client not handshaken"),
        NamedInt(2, "unauthorized")
    )

    ADVICES = (
        NamedInt(0, "reconnect"),
    )

    @classmethod
    def from_data(cls, id, ack, endpoint, data):
        if data:
            reason, advice = cls._plus_split(data)
            reason = cls.REASONS[int(reason)] if reason else ''
            advice = cls.ADVICES[int(advice)] if advice else ''
        else:
            reason, advice = '', ''
        return super(ErrorPacket, cls).from_data(id, ack, endpoint, reason, advice)


class DataPacket(Packet, namedtuple("_DataPacket", BASE_FIELDS + ("data",))):
    __slots__ = ()

    @classmethod
    def from_data(cls, id, ack, endpoint, data):
        return super(DataPacket, cls).from_data(id, ack, endpoint, cls._parse_data(data))


class JSONPacket(DataPacket):
    __slots__ = ()

    @classmethod
    def _parse_data(cls, data):
        return cls._parse_json(data)


class MessagePacket(DataPacket):
    __slots__ = ()

    @classmethod
    def _parse_data(cls, data):
        return data or b''


class ConnectPacket(Packet, namedtuple("_ConnectPacket", BASE_FIELDS + ("qs",))):
    __slots__ = ()

    @classmethod
    def from_data(cls, id, ack, endpoint, data):
        qs = urlparse.parse_qs(data.decode('utf-8')[1:]) if data else {}
        return super(ConnectPacket, cls).from_data(id, ack, endpoint, qs)


class AckPacket(Packet, namedtuple("_AckPacket", BASE_FIELDS + ("ackid", "args"))):
    __slots__ = ()

    @classmethod
    def from_data(cls, id, ack, endpoint, data):
        ackid, args = cls._plus_split(data)
        if args:
            args = cls._parse_json(args)
        else:
            args = []
        return super(AckPacket, cls).from_data(id, ack, endpoint, ackid, args)

class EventPacket(Packet, namedtuple("_EventPacket", BASE_FIELDS + ("name", "args"))):
    __slots__ = ()

    @classmethod
    def from_data(cls, id, ack, endpoint, data):
        event_data = cls._parse_json(data)
        return cls(id, ack, endpoint, event_data["name"], event_data.get("args", []))


_SimplePacket = namedtuple("_SimplePacket", BASE_FIELDS)


class DisconnectPacket(Packet, _SimplePacket):
    __slots__ = ()


class HeartbeatPacket(Packet, _SimplePacket):
    __slots__ = ()


class NoopPacket(Packet, _SimplePacket):
    __slots__ = ()


PACKET_TYPES = (
    DisconnectPacket,
    ConnectPacket,
    HeartbeatPacket,
    MessagePacket,
    JSONPacket,
    EventPacket,
    AckPacket,
    ErrorPacket,
    NoopPacket,
)
