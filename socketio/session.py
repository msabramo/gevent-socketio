from __future__ import absolute_import, unicode_literals

import uuid
import weakref
import gevent
import time

from gevent.queue import Queue
from socketio import packets


from logging import getLogger
logger = getLogger("socketio.server.session")


__all__ = ['SocketIOServer']


class SessionExpireGreenlet(gevent.Greenlet):
    """
    Monitoring greenlet that expires a session after some period
    of time.
    """

    def __init__(self, expire, session):
        gevent.Greenlet.__init__(self)
        self._session = weakref.ref(session)
        self.expire = expire

    def _run(self):
        while True:
            session = self._session()

            if session is None: # session was deleted
                return

            delta = time.clock() - session.timestamp
            if delta > self.expire:
                logger.info("Session %r expired. Delta is %r, expected less then %r", session, delta, self.expire)
                session.kill()
                return

            # session is alive, go to sleep
            gevent.sleep(session.timestamp + self.expire - max(0, delta))


class Session(object):
    """
    Client session which checks the connection health and the queues for
    message passing.
    """

    STATE_NEW = "NEW"
    STATE_CONNECTED = "CONNECTED"
    STATE_DISCONNECTING = "DISCONNECTING"
    STATE_DISCONNECTED = "DISCONNECTED"

    def __init__(self, server, handshake_info, expire=10, heartbeat=15):
        self.handshake_info = handshake_info  # Info sent in handshake data

        self._server = weakref.ref(server)
        self.__packetid = 1
        self._acks = weakref.WeakValueDictionary()

        self.session_id = uuid.uuid1().hex

        self.state = "NEW"
        self.connection_confirmed = False
        self.timestamp = time.clock()
        self.wsgi_app_greenlet = None

        self.expire = expire
        self.heartbeat = heartbeat

        self.client_queue = Queue()  # queue for messages to client
        self.server_queue = Queue()  # queue for messages to server

        self.expire_greenlet = SessionExpireGreenlet(expire, self)
        self.expire_greenlet.start_later(expire)



    def __repr__(self):
        return "<Session {s.session_id}, timestamp={s.timestamp}, state={s.state}>".format(s=self)

    @property
    def connected(self):
        return self.state == self.STATE_CONNECTED

    def touch(self):
        self.timestamp = max(time.clock(), self.timestamp)
        if self.state == "NEW":
            self.state = self.STATE_CONNECTED

    def clear_disconnect_timeout(self):
        self.touch()

    def kill(self):
        if self.connected:
            self.state = self.STATE_DISCONNECTING
            self.server_queue.put_nowait(None)
            self.client_queue.put_nowait(None)
            self.expire_greenlet.kill()

            del self.expire_greenlet
            del self.wsgi_app_greenlet
            del self.client_queue
            del self.server_queue

            # unregister from server
            server = self._server()
            if server is not None:
                del server._sessions[self.session_id]
        else:
            pass # Fail silently

    def receive(self, **kwargs):
        msg = self.server_queue.get(**kwargs)
        assert msg is None or isinstance(msg, packets.Packet), "Got SERVER message which is not a packet %r" % msg
        return msg

    def ack(self, packet, *args):
        self.send(packets.AckPacket(None, None, None, packet.id, args))

    def packet_id(self):
        """
        Generate a unique packet id.
        """
        id_, self.__packetid = self.__packetid, self.__packetid + 1
        return id_

    def send(self, packet, timeout=None):
        assert isinstance(packet, packets.Packet), "Trying to enqueue CLIENT message that is not a packet %r" % packet
        self.touch()

        # No ack
        if packet.ack is None:
            self.client_queue.put_nowait(packet)
            return None

        # Needs an ack
        acked = gevent.event.AsyncResult()
        self._acks[unicode(packet.id)] = acked
        self.client_queue.put_nowait(packet)
        return acked.get(timeout=timeout)

    def _fetch_client(self, **kwargs):
        msg = self.client_queue.get(**kwargs)
        assert msg is None or isinstance(msg, packets.Packet), "Got CLIENT message which is not a packet %r" % msg
        return msg

    def handshake_string(self):
        return "{0.session_id}:{0.heartbeat}:{0.expire}:websocket,xhr-polling".format(self)

    def packet_received(self, packet):
        assert isinstance(packet, packets.Packet), "Trying to enqueue SERVER message that is not a packet %r" % packet

        if packet.kind == "disconnect":
            logger.info("Client is disconnecting from session %r", self)
            self.kill()
            return

        # clear the timeout
        self.touch()

        if packet.kind == "heartbeat":
            return

        if packet.kind == "ack":
            # user is waiting for an ack
            ack_event = self._acks.get(packet.ackid)
            if ack_event is not None:
                ack_event.set(packet.args)
            return

        if packet.id is not None:
            if packet.ack is True: # != None, "+"
                self.ack(packet)

        return self.server_queue.put_nowait(packet)

