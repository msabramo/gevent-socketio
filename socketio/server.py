from __future__ import absolute_import, unicode_literals


from gevent.pywsgi import WSGIServer

from socketio.handler import SocketIOHandler
from socketio.session import Session

import urlparse

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

    def create_session(self, environ):
        """
        Create a new session on the server.
        """
        handshake_data = {
            "query": dict(urlparse.parse_qsl(environ["QUERY_STRING"]))
        }
        session = Session(self, handshake_data)
        self._sessions[session.session_id] = session
        return session
