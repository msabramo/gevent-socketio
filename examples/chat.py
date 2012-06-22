from gevent import monkey; monkey.patch_all()
from socketio import SocketIOServer


class Application(object):
    def __init__(self):
        self.buffer = []
        self.cache = {
            'nicknames': set()
        }

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO'].strip('/')

        if not path:
            start_response('200 OK', [('Content-Type', 'text/html')])
            return ['<h1>Welcome. Try the <a href="/chat.html">chat</a> example.</h1>']

        if path in ['socket.io.js', 'chat.html', 'stylesheets/style.css']:
            try:
                data = open(path).read()
            except Exception:
                return not_found(start_response)

            if path.endswith(".js"):
                content_type = "text/javascript"
            elif path.endswith(".css"):
                content_type = "text/css"
            else:
                content_type = "text/html"

            start_response('200 OK', [('Content-Type', content_type)])
            return [data]

        if path.startswith("socket.io"):
            socketio = environ['socketio']

            while True:
                message = socketio.receive()

                if message and message.kind == "event":
                    self.handle_event(message, socketio)
        else:
            return not_found(start_response)

    def handle_event(self, message, io):
        if message.name == "nickname":
            nickname = message.args[0]
            nickdict = {}
            nickdict[nickname] = nickname
            io.session.nickname = nickname

            self.cache['nicknames'].add(nickname)

            # io.ack(message.id, [0])
            # io.broadcast_event("announcement", "%s connected" % nickname)
            # io.broadcast_event("nicknames", list(self.cache['nicknames']), include_self=True)

        elif message.name == "user_message":
            # io.broadcast_event("user message", io.session.nickname, message['args'][0])
            pass


def not_found(start_response):
    start_response('404 Not Found', [])
    return ['<h1>Not Found</h1>']


if __name__ == '__main__':
    print "Listening on port 8080"
    import logging
    logging.basicConfig(level=logging.DEBUG)
    SocketIOServer(('127.0.0.1', 8080), Application(), namespace="socket.io", policy_server=False).serve_forever()
