from __future__ import absolute_import, unicode_literals

from socketio import packets


from logging import getLogger
logger = getLogger("socketio.protocol")


class PySocketProtocol(object):

    def __init__(self, session, endpoint=None):
        self._session = session
        self._endpoint = endpoint

    def _nextid(self):
        return None

    @property
    def session(self):
        return self._session

    def send(self, packet):
        """
        Send a prepared packet.
        """
        self._session.send(packet)

    def receive(self, timeout=None):
        """Wait for incoming messages."""
        return self._session.receive(timeout=timeout)

    def _base_args(self, need_ack):
        if not need_ack:
            return None, None, self._endpoint
        else:
            return self._nextid(), True, self._endpoint

    def emit(self, event, args, ack=False):
        """Emit an event."""
        return self.send_packet(packets.EventPacket(*self._base_args(ack) + (event, args)))

    def send_data(self, data, ack=False):
        """Sends data to the client."""
        return self.send_packet(packets.DataPacket(*self._base_args(ack) + (data,)))

    def send_json(self, json, ack=False):
        """Send raw JSON to the client."""
        return self.send_packet(packets.DataPacket(*self._base_args(ack) + (json,)))

SocketIOProtocol = PySocketProtocol
