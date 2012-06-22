# -*- encoding: utf-8
import gevent

def noop(env, io):
    """test connecting the socket and disconnecting"""

def receiving(env, io):
    """test receiving messages"""
    for i in range(1, 4):
        io.send_data(i)
    gevent.sleep(0.5)
    io.disconnect()

def sending(env, io):
    """test sending messages"""
    while True:
        msg = io.receive()
        if msg is None:
            return
        io.send(msg)


def acks_from_client(env, io):
    """test acks sent from client"""
    io.send_data("tobi")
    io.send_data("tobi 2")


def acks_from_server(env, io):
    "test acks sent from server"
    pass


#  server('test connecting to namespaces', function (io) {
#    io.of('/woot').on('connection', function (socket) {
#      socket.send('connected to woot');
#    });
#
#    io.of('/chat').on('connection', function (socket) {
#      socket.send('connected to chat');
#    });
#  });
#
#  server('test disconnecting from namespaces', function (io) {
#    io.of('/a').on('connection', function (socket) {});
#    io.of('/b').on('connection', function (socket) {});
#  });
#
#  server('test authorizing for namespaces', function (io) {
#    io.of('/a')
#      .authorization(function (data, fn) {
#        fn(null, false);
#      })
#      .on('connection', function (socket) {});
#  });

def json_from_server(env, io):
    "test sending json from server"
    io.send_json(3141592)

def json_from_client(env, io):
    "test sending json from client"
    msg = io.receive()
    if isinstance(msg.data, list) and len(msg.data) == 3:
        io.send_data("echo")

def event_from_server(env, io):
    "test emitting an event from server"
    io.emit("woot")

def multiple_events_from_client(env, io):
    "test emitting multiple events at once to the server"
    messages = []
    while len(messages) < 2:
        pkt = io.receive()
        if pkt.name == "print":
            msg, = pkt.args
            if pkt.args in messages:
                raise Exception("Duplicate message")
            messages.append(msg)
    io.emit("done")


def event_from_client(env, io):
    "test emitting an event to server"
    while True:
        pkt = io.receive()
        if pkt is None:
            return
        if pkt.name == "woot":
            io.emit("echo")


def event_from_server_client_ack(env, io):
    "test emitting an event from server and sending back data"
    data, = io.emit("woot", 1, ack=True)
    assert data == "test"
    io.emit("done")


def event_to_server_and_ack(env, io):
    "test emitting an event to server and sending back data"
    pkt = io.receive()
    assert pkt.name == "tobi"
    assert pkt.args == [1, 2]
    io.ack(pkt, {"hello": "world"})


#def encoding_payload(env, io):
#    "test encoding a payload"
#    #    io.of('/woot').on('connection', function (socket) {
#    pkt = io.receive()
#    assert pkt.endpoint == "/woot"
#    count = 0
#    while count < 4:
#        pkt = io.receive()
#        if pkt.data == u'ñ':
#            count += 1
#    io.emit("done")

def sending_query_strings_to_server(env, io):
    "test sending query strings to the server"
    io.send_json(io.session.handshake_info)

def sending_newline(env, io):
    "test sending newline"
    pkt = io.receive()
    assert pkt.data == u'\n'
    io.emit("done")


def sending_unicode(env, io):
    "test sending unicode"
    pkt = io.receive()
    assert pkt.data["test"] == u"☃"
    io.emit("done")


def webworker_test(env, io):
    "test webworker connection"
    pkt = io.receive()
    assert pkt.data == "woot"
    io.emit("done")
