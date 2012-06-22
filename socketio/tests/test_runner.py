"""
Socket.IO integration tests.

This tests the server implementation using latest Socket.IO JavaScript client.

Just run this server instead of the one runned by ``make test-acceptance``
and open a browser at the right page.

TODO: use selenium to auto-open the browsers.

"""

from socketio.server import SocketIOServer
import gevent.pywsgi
import gevent.pool
import os.path
import json
import functools


PROJECT_BASE = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def serve_statics(env, start_response):
    path = env["PATH_INFO"]
    if path == "/":
        start_response("200 OK", [("Content-Type", "text/html")])
        return [INDEX_PAGE]
    elif path == "/socket.io/socket.io.js":
        start_response("200 OK", [("Content-Type", "text/javascript")])
        DIST = os.path.join(PROJECT_BASE, "lib", "socket.io-client", "dist")
        return open(os.path.join(DIST, "socket.io.js"))
    elif path == "/favicon.ico":
        start_response("404 Not Found", [("Content-Type", "text/plain")])
    else:
        mimetype = "text/css" if path.endswith("css") else "text/javascript"

        if path.startswith("/test/"):
            ROOT = os.path.join(PROJECT_BASE, "lib", "socket.io-client")
        else:
            ROOT = os.path.join(PROJECT_BASE, "lib", "socket.io-client",
                    "support", "test-runner", "public")
        fpath = os.path.join(ROOT, *path.split("/"))
        try:
            f = open(fpath)
            start_response("200 OK", [("Content-Type", mimetype)])
            return f
        except IOError:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
    return ["Not found: ", path]


INDEX_PAGE = ur"""
<!DOCTYPE html>
<html>
  <head>
    <link href='/stylesheets/main.css' rel='stylesheet'></link>
    <script src='/socket.io/socket.io.js' type="text/javascript"></script>
    <script src='/javascript/jquery.js' type="text/javascript"></script>
    <script src='/javascript/should.js' type="text/javascript"></script>
    <script src='/javascript/script.js' type="text/javascript"></script>
    <script src='/javascript/runner.js' type="text/javascript"></script>

    <script type="text/javascript"><!--
        var testsPorts = %(ports_mapping)s;
    //--></script>
    <script type="text/javascript"><!--
        $(function () {
            run('io.test.js', 
                'parser.test.js', 
                'util.test.js',
                'events.test.js',
                'socket.test.js'
            );
        });
    //--></script>

    <title>Socket.IO tests runner</title>
</head>

<body>
    <h2>Socket.IO test runner</h2>
</body>

</html>
"""


def sio_server(func):
    @functools.wraps(func)
    def _server(env, start_response):
        if "socketio" not in env:
            return
        if env["socketio"]._session is None:
            return
        return func(env, env["socketio"])
    return _server

if __name__ == "__main__":
    port = 3001
    greenlet_pool = gevent.pool.Pool()

    import logging
    logging.basicConfig(level=logging.DEBUG)

    def spawn_server(func, port):
        print "Serving port", port, func.__name__
        server = SocketIOServer(("localhost", port), func,
                        spawn=greenlet_pool,
                        cors="http://localhost:3000",
                        policy_server=False)
        server.serve_forever()

    port_mapping = {}

    # Start the test servers... many servers...
    from . import test_servers

    for func in test_servers.__dict__.itervalues():
        if not callable(func) or func.__name__.startswith("_"):
            continue
#        if func.__name__ != "event_to_server_and_ack":
#            continue
        func = sio_server(func)
        greenlet_pool.spawn(spawn_server, func, port)
        port_mapping[func.__doc__] = port
        port += 1

    print port_mapping

    INDEX_PAGE = INDEX_PAGE % {
        "ports_mapping": json.dumps({"socket.test.js": port_mapping})
    }

    # Spawn the base HTTP server
    static_server = gevent.pywsgi.WSGIServer(("localhost", 3000), serve_statics)
    static_server.serve_forever()
