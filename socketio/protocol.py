from __future__ import absolute_import, unicode_literals

from socketio import packets


from logging import getLogger
logger = getLogger("socketio.protocol")


class PySocketProtocol(object):

    def __init__(self, session, endpoint=None):
        self._session = session
        self._endpoint = endpoint

    @property
    def session(self):
        return self._session

    def send(self, packet):
        """
        Send a prepared packet.
        """
        return self._session.send(packet)

    def ack(self, packet, *args):
        """
        Acknowledge that packet was received.
        """
        return self._session.ack(packet, *args)

    def receive(self, timeout=None):
        """Wait for incoming messages."""
        return self._session.receive(timeout=timeout)

    def _base_args(self, need_ack):
        if not need_ack:
            return None, None, self._endpoint
        else:
            return self.session.packet_id(), "data", self._endpoint

    def emit(self, event, args=None, ack=False):
        """Emit an event."""
        return self.send(packets.EventPacket(*self._base_args(ack) + (event, args)))

    def send_data(self, data, ack=False):
        """Sends data to the client."""
        return self.send(packets.MessagePacket(*self._base_args(ack) + (data,)))

    def send_json(self, json, ack=False):
        """Send raw JSON to the client."""
        return self.send(packets.JSONPacket(*self._base_args(ack) + (json,)))

    def disconnect(self, reason="booted"):
        return self.send(packets.DisconnectPacket(None, None, self._endpoint))


SocketIOProtocol = PySocketProtocol
