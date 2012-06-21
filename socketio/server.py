from __future__ import absolute_import, unicode_literals

import uuid
import weakref
import gevent
import time


from gevent.pywsgi import WSGIServer
from gevent.queue import Queue
from gevent.event import Event
from socketio.handler import SocketIOHandler
from socketio import packets


from logging import getLogger
logger = getLogger("socketio.server")


__all__ = ['SocketIOServer']


class SocketIOServer(WSGIServer):
    """A WSGI Server with a resource that acts like an SocketIO."""

    def __init__(self, *args, **kwargs):
        self._sessions = {}
        self.namespace = kwargs.pop('namespace', 'socket.io')
        self.cors_domain = kwargs.pop('cors', '')

        kwargs.pop('policy_server')

        kwargs.setdefault('handler_class', SocketIOHandler)
        super(SocketIOServer, self).__init__(*args, **kwargs)


    def get_session(self, sid):
        """Return an existing or new client Session."""
        session = self._sessions.get(sid, None)
        if session is not None:
            session.touch()  # Touch the session as used
        return session

    def create_session(self):
        session = Session(self)
        self._sessions[session.session_id] = session
        return session


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

    def __init__(self, server, expire=10):
        self._server = weakref.ref(server)

        self.session_id = uuid.uuid1().hex
        self.state = "NEW"
        self.connection_confirmed = False

        self.client_queue = Queue() # queue for messages to client
        self.server_queue = Queue() # queue for messages to server

        self.timestamp = time.clock()

        self.wsgi_app_greenlet = None

        self.expire_greenlet = SessionExpireGreenlet(expire, self)
        self.expire_greenlet.start_later(expire)

    def __str__(self):
        result = ['session_id=%r' % self.session_id]
        if self.state == self.STATE_CONNECTED:
            result.append('connected')
        if self.client_queue.qsize():
            result.append('client_queue[%s]' % self.client_queue.qsize())
        if self.server_queue.qsize():
            result.append('server_queue[%s]' % self.server_queue.qsize())

        return ' '.join(result)

    @property
    def connected(self):
        return self.state == self.STATE_CONNECTED

    def touch(self):
        self.timestamp = max(time.clock(), self.timestamp)
        if self.state == "NEW":
            self.state = self.STATE_CONNECTED

    def clear_disconnect_timeout(self):
        self.touch()

    def heartbeat(self):
        self.touch()

    def kill(self):
        if self.connected:
            self.state = self.STATE_DISCONNECTING
            self.server_queue.put_nowait(packets.DisconnectPacket(None, None, None))
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

    def put_server_msg(self, msg):
        self.clear_disconnect_timeout()
        self.server_queue.put_nowait(msg)

    def put_client_msg(self, msg):
        self.clear_disconnect_timeout()
        self.client_queue.put_nowait(msg)

    def get_client_msg(self, **kwargs):
        return self.client_queue.get(**kwargs)

    def get_server_msg(self, **kwargs):
        return self.server_queue.get(**kwargs)
