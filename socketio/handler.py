from __future__ import absolute_import, unicode_literals

import sys
import re
import gevent
import urlparse

from socketio import transports, protocol
from geventwebsocket.handler import WebSocketHandler


from logging import getLogger
from gevent.pywsgi import WSGIHandler
logger = getLogger("socketio.handler")


class SessionGreenlet(gevent.Greenlet):
    pass


class SocketIOHandler(WebSocketHandler):
    RE_REQUEST_URL = re.compile(r"""
        ^/(?P<namespace>[^/]+)
         /(?P<protocol_version>[^/]+)
         /(?P<transport_id>[^/]+)
         /(?P<session_id>[^/]+)/?$
         """, re.X)
    RE_HANDSHAKE_URL = re.compile(r"^/(?P<namespace>[^/]+)/1/$", re.X)

    handler_types = {
        'websocket': transports.WebsocketTransport,
        #'htmlfile': transports.HTMLFileTransport,
        #'xhr-multipart': transports.XHRMultipartTransport,
        'xhr-polling': transports.XHRPollingTransport,
        #'jsonp-polling': transports.JSONPolling,
    }

    def __init__(self, socket, addr, server, *args, **kwargs):
        self.allowed_paths = None
        super(SocketIOHandler, self).__init__(socket, addr, server, *args, **kwargs)

    def _do_handshake(self, tokens):
        if tokens["namespace"] != self.server.namespace:
            self.log_error("Namespace mismatch")
        else:
            session = self.server.create_session(self.environ)
            self.write_smart(session.handshake_string())

    def write_jsonp_result(self, data, wrapper="0"):
        self.start_response("200 OK", [
            ("Content-Type", "application/javascript"),
        ])
        self.result = ['io.j[%s]("%s");' % (wrapper, data)]

    def write_plain_result(self, data):
        headers = [("Content-Type", "text/plain")]
        if self.server.cors_domain:
            headers += [
                ("Access-Control-Allow-Origin", self.server.cors_domain),
                ("Access-Control-Allow-Credentials", "true"),
            ]
        self.start_response("200 OK", headers)
        self.result = [data]

    def write_smart(self, data):
        args = urlparse.parse_qs(self.environ.get("QUERY_STRING"))

        if "jsonp" in args:
            self.write_jsonp_result(data, args["jsonp"][0])
        else:
            self.write_plain_result(data)

        self.process_result()

    def handle_one_response(self):
        self.status = None
        self.headers_sent = False
        self.result = None
        self.response_length = 0
        self.response_use_chunked = False

        path = self.environ.get('PATH_INFO')

        logger.info("REQUEST: %s @ %s", self.environ["SERVER_PORT"], path)
        request_method = self.environ.get("REQUEST_METHOD")
        request_tokens = self.RE_REQUEST_URL.match(path)

        # Kick non-socket.io requests to our superclass
        if not path.lstrip('/').startswith(self.server.namespace):
            return WSGIHandler.handle_one_response(self)

        # Parse request URL and QUERY_STRING and do handshake
        if request_tokens:
            request_tokens = request_tokens.groupdict()
        else:
            handshake_tokens = self.RE_HANDSHAKE_URL.match(path)

            if handshake_tokens:
                return self._do_handshake(handshake_tokens.groupdict())
            else:
                # This is no socket.io request. Let the WSGI app handle it.
                return WSGIHandler.handle_one_response(self)

        # Setup the transport and session
        transport = self.handler_types.get(request_tokens["transport_id"])
        session_id = request_tokens["session_id"]
        session = self.server.get_session(session_id)
        logger.debug("Handshake for session %r, transport %r", session.session_id, transport)

        # Make the session object available for WSGI apps
        self.environ['socketio'] = protocol.PySocketProtocol(session)

        if transport is transports.WebsocketTransport:
            # fake application
            try:
                _tmp, self.application = self.application, lambda *args: None
                logger.debug("Initializing websocket.")
                WebSocketHandler.handle_one_response(self)
            finally:
                self.application = _tmp

        # Create a transport and handle the request likewise
        logger.debug("Connecting transport: %r", transport)
        transport(self).connect(session, request_method)

        if session.wsgi_app_greenlet is not None:
            if not session.wsgi_app_greenlet:
                logger.debug("Joining finalized greenlet %r -> %r", self, session.wsgi_app_greenlet)
                session.wsgi_app_greenlet.join()
                session.wsgi_app_greenlet = None

        if not session.wsgi_app_greenlet:
            start_response = lambda status, headers, exc = None: None
            logger.debug("Spawning new greenlet for session: %r", session)
            session_greenlet = SessionGreenlet.spawn(self.application, self.environ, start_response)
            session_greenlet.join()
            logger.debug("Session greenlet joined: %r", session)
            del session

    def handle_bad_request(self):
        self.close_connection = True
        self.start_reponse("400 Bad Request", [
            ('Content-Type', 'text/plain'),
            ('Connection', 'close'),
            ('Content-Length', 0)
        ])
