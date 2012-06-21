from __future__ import absolute_import, unicode_literals

import gevent
import socket
import urlparse
import weakref
from logging import getLogger

from gevent.queue import Empty
from socketio import packets
from geventwebsocket.exceptions import WebSocketError


logger = getLogger("socketio.transports")


class BaseTransport(object):
    """Base class for all transports. Mostly wraps handler class functions."""

    def __init__(self, handler):
        self.content_type = ("Content-Type", "text/plain; charset=UTF-8")
        self.headers = [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Credentials", "true"),
            ("Access-Control-Allow-Methods", "POST, GET, OPTIONS"),
            ("Access-Control-Max-Age", 3600),
        ]
        self.headers_list = []
        self.handler = weakref.ref(handler)

    def write_packet(self, packet):
        self.write(packet.encode())

    def write(self, data):
        if 'Content-Length' not in self.handler().response_headers_list:
            self.handler().response_headers.append(('Content-Length', len(data)))
            self.handler().response_headers_list.append('Content-Length')

        self.handler().write(data)

    def start_response(self, status, headers, **kwargs):
        if "Content-Type" not in [x[0] for x in headers]:
            headers.append(self.content_type)

        headers.extend(self.headers)
        logger.debug("[[%r:%r]] Sending reply %r\n    with headers: %r", self.handler(), self.handler().application, status, headers)
        self.handler().start_response(status, headers, **kwargs)


class XHRPollingTransport(BaseTransport):
    def __init__(self, *args, **kwargs):
        super(XHRPollingTransport, self).__init__(*args, **kwargs)

    def options(self):
        self.start_response("200 OK", ())
        self.write('')
        return []

    def get(self, session):
        session.clear_disconnect_timeout();

        try:
            message = session.get_client_msg(timeout=5.0)
        except Empty:
            message = packets.NoopPacket()

        self.start_response("200 OK", [])
        self.write_packet(message)

        return []

    def _request_body(self):
        return self.handler().wsgi_input.readline()

    def post(self, session):
        session.put_server_msg(packets.Packet.decode(self._request_body()))

        self.start_response("200 OK", [
            ("Connection", "close"),
            ("Content-Type", "text/plain")
        ])
        self.write("1")

        return []

    def connect(self, session, request_method):
        if not session.connection_confirmed:
            session.connection_confirmed = True
            self.start_response("200 OK", [
                ("Connection", "close"),
            ])
            self.write_packet(packets.ConnectPacket(None, None, None, None))

            return []
        elif request_method in ("GET", "POST", "OPTIONS"):
            return getattr(self, request_method.lower())(session)
        else:
            raise Exception("No support for the method: " + request_method)


class JSONPolling(XHRPollingTransport):
    def __init__(self, handler):
        super(JSONPolling, self).__init__(handler)
        self.content_type = ("Content-Type", "text/javascript; charset=UTF-8")

    def _request_body(self):
        data = super(JSONPolling, self)._request_body()
        # resolve %20%3F's, take out wrapping d="...", etc..
        return urlparse.unquote(data)[3:-1].replace(r'\"', '"')

    def write(self, data):
        super(JSONPolling, self).write("io.j[0]('%s');" % data)


class XHRMultipartTransport(XHRPollingTransport):
    def __init__(self, handler):
        super(JSONPolling, self).__init__(handler)
        self.content_type = (
            "Content-Type",
            "multipart/x-mixed-replace;boundary=\"socketio\""
        )

    def connect(self, session, request_method):
        if request_method == "GET":
            heartbeat = self.handler.environ['socketio'].start_heartbeat()
            return [heartbeat] + self.get(session)
        elif request_method == "POST":
            return self.post(session)
        else:
            raise Exception("No support for such method: " + request_method)

    def get(self, session):
        header = "Content-Type: text/plain; charset=UTF-8\r\n\r\n"

        self.start_response("200 OK", [("Connection", "keep-alive")])
        self.write_multipart("--socketio\r\n")
        self.write_multipart(header)
        self.write_multipart(self.encode(session.session_id) + "\r\n")
        self.write_multipart("--socketio\r\n")

        def chunk():
            while True:
                message = session.get_client_msg()

                if message is None:
                    session.kill()
                    break
                else:
                    message = self.encode(message)

                    try:
                        self.write_multipart(header)
                        self.write_multipart(message)
                        self.write_multipart("--socketio\r\n")
                    except socket.error:
                        session.kill()
                        break

        return [gevent.spawn(chunk)]


class WSGreenlet(gevent.Greenlet):

    def __init__(self, session, websocket):
        gevent.Greenlet.__init__(self)
        self._session = session
        self._websocket = websocket

    def __str__(self):
        return "<%s of session %r>" % (type(self).__name__, self._session.session_id)


class WSInboundGreenlet(WSGreenlet):

    def _run(self):
        while True:
            message = self._websocket.receive()

            if not message:
                self._session.kill()
                break
            else:
                decoded_message = packets.Packet.decode(message)
                if decoded_message is not None:
                    self._session.put_server_msg(decoded_message)


class WSOutboundGreenlet(WSGreenlet):

    def _run(self):
        while True:
            message = self._session.get_client_msg()

            if message is None:
                self._session.kill()
                break

            try:
                logger.debug("Sending message %r", message)
                self._websocket.send(message.encode())
                logger.debug("Message %r sent.", message)
            except WebSocketError:
                logger.exception("Outbound greenlet crashed.")
                break


class WebsocketTransport(BaseTransport):

    def connect(self, session, request_method):
        websocket = self.handler().environ['wsgi.websocket']
        websocket.send("1::")

        in_ = WSOutboundGreenlet(session, websocket)
        in_.start()
        out_ = WSInboundGreenlet(session, websocket)
        out_.start()

        # heartbeat = self.handler().environ['socketio'].start_heartbeat()

        return [in_, out_]


class HTMLFileTransport(XHRPollingTransport):
    """Not tested at all!"""

    def __init__(self, handler):
        super(HTMLFileTransport, self).__init__(handler)
        self.content_type = ("Content-Type", "text/html")

    def write_packed(self, data):
        self.write("<script>parent.s._('%s', document);</script>" % data)

    def handle_get_response(self, session):
        self.start_response("200 OK", [
            ("Connection", "keep-alive"),
            ("Content-Type", "text/html"),
            ("Transfer-Encoding", "chunked"),
        ])
        self.write("<html><body>" + " " * 244)

        try:
            message = session.get_client_msg(timeout=5.0)
            message = self.encode(message)
        except Empty:
            message = ""

        self.write_packed(message)
