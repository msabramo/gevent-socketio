from __future__ import absolute_import, unicode_literals

import gevent
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
        self.handler().start_response(status, headers, **kwargs)


class XHRPollingTransport(BaseTransport):
    def __init__(self, *args, **kwargs):
        super(XHRPollingTransport, self).__init__(*args, **kwargs)

    def options(self):
        self.start_response("200 OK", ())
        self.write('')
        return []

    def get(self, session):
        session.touch();

        try:
            message = session._fetch_client(timeout=5.0)
        except Empty:
            message = packets.NoopPacket()

        self.start_response("200 OK", [])
        self.write_packet(message)
        return []

    def _request_body(self):
        return self.handler().wsgi_input.readline()

    def post(self, session):
        packet = packets.Packet.decode(self._request_body())
        session.packet_received(packet)

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


class WSGreenlet(gevent.Greenlet):

    def __init__(self, session, websocket):
        gevent.Greenlet.__init__(self)
        self._session = session
        self._websocket = websocket

    def __str__(self):
        return "<%s of %r>" % (type(self).__name__, self._session)


class WSInboundGreenlet(WSGreenlet):

    def _run(self):
        while True:
            message = self._websocket.receive()
            logger.debug("Received message from WS: %r", message)

            if not message:
                logger.debug("Websocket closed by client. Killing session: %r", self._session)
                self._session.kill()
                break

            try:
                packet = packets.Packet.decode(message)
            except Exception:
                logger.exception("Failed to decode packet: %r", message)
                continue

            if packet is not None:
                self._session.packet_received(packet)


class WSOutboundGreenlet(WSGreenlet):

    def _run(self):
        while True:
            message = self._session._fetch_client()

            if message is None:
                logger.debug("Closing outbound communication for session: %r", self._session)
                self._session.kill()
                break

            try:
                logger.debug("Sending outbound message: %r", message)
                self._websocket.send(message.encode())
                logger.debug("Message %r sent.", message)
            except WebSocketError:
                logger.exception("Outbound greenlet crashed.")
                break


class HeartbeatGreenlet(gevent.Greenlet):

    def __init__(self, session):
        gevent.Greenlet.__init__(self)
        self._session_ref = weakref.ref(session)

    def __str__(self):
        return "<%s for %r>" % (type(self).__name__, self._session_ref)

    def _run(self):
        while True:
            session = self._session_ref()
            if session is None or session.state != "CONNECTED":
                return
            logger.debug("Sending heartbeat for %r", session)
            session.send(packets.HeartbeatPacket(None, None, None))

            # go back to sleep
            duration = session.heartbeat
            del session
            gevent.sleep(duration // 2)

class WebsocketTransport(BaseTransport):

    def connect(self, session, request_method):
        websocket = self.handler().environ['wsgi.websocket']
        websocket.send("1::")

        in_ = WSOutboundGreenlet(session, websocket)
        in_.start()
        out_ = WSInboundGreenlet(session, websocket)
        out_.start()

        heartbeat = HeartbeatGreenlet(session)
        heartbeat.start_later(session.heartbeat // 2)

        return [in_, out_, heartbeat]
