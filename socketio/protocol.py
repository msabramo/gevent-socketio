import gevent
import anyjson as json
from socketio.exceptions import DecodeError
import weakref

from logging import getLogger
logger = getLogger("socketio.protocol")


class SocketIOProtocol(object):
    """SocketIO protocol specific functions."""

    def __init__(self, handler):
        self.handler = weakref.ref(handler)
        self.session = None

    def ack(self, msg_id, params):
        self.send("6:::%s+%s" % (msg_id, json.dumps(params)))

    def emit(self, event, endpoint, *args):
        self.send("5::%s:%s" % (endpoint, json.dumps({'name': event,
                                                      'args': args})))

    def send(self, message):
        dst_client = self.session
        self._write(message, dst_client)

    def send_event(self, name, *args):
        self.send("5:::" + json.dumps({'name': name, 'args': args}))

    def receive(self, timeout=None):
        """Wait for incoming messages."""
        return self.session.get_server_msg(timeout=timeout)

    def broadcast(self, message, exceptions=None, include_self=False):
        """
        Send messages to all connected clients, except itself and some
        others.
        """

        if exceptions is None:
            exceptions = []

        if not include_self:
            exceptions.append(self.session.session_id)

        for session_id, session in self.handler.server.sessions.iteritems():
            if session_id not in exceptions:
                self._write(message, session)

    def broadcast_event(self, name, *args, **kwargs):
        self.broadcast("5:::" + json.dumps({'name': name, 'args': args}), **kwargs)

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
        if isinstance(message, basestring):
            encoded_msg = message
        elif isinstance(message, (object, dict)):
            return self.encode(json.dumps(message))
        else:
            raise ValueError("Can't encode message")

        return encoded_msg

    def decode(self, data):
        data.encode('utf-8', 'ignore')
        msg_type, msg_id, tail = data.split(":", 2)

        logger.debug("RECEIVED MSG TYPE %r %r", msg_type, data)

        if msg_type == "0": # disconnect
            self.session.kill()
            return {'endpoint': tail, 'type': 'disconnect'}

        elif msg_type == "1": # connect
            self.send("1::%s" % tail)
            return {'endpoint': tail, 'type': 'connect'}

        elif msg_type == "2": # heartbeat
            self.session.heartbeat()
            return {'type': 'heartbeat'}

        msg_endpoint, data = tail.split(":", 1)
        message = {'endpoint': msg_endpoint}

        if msg_type == "3": # message
            message['type'] = 'message'
            message['data'] = data
        elif msg_type == "4": # json msg
            message['type'] = 'json'
            message['data'] = json.loads(data)
        elif msg_type == "5": # event
            logger.debug("EVENT with data: %r", data)
            message.update(json.loads(data))

            if "+" in msg_id:
                message['id'] = msg_id
            else:
                pass # TODO send auto ack
            message['type'] = 'event'
        elif msg_type == "6": # ack
            message['type'] = 'ack?'
        elif msg_type == "7": # error
            message['type'] = 'error'
            els = data.split('+', 1)
            message['reason'] = els[0]
            if len(els) == 2:
                message['advice'] = els[1]
        elif msg_type == "8": # noop
            message['type'] = 'noop'
        else:
            raise Exception("Unknown message type: %s" % msg_type)

        return message
