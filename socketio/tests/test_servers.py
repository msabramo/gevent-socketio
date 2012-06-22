# -*- encoding: utf-8
import gevent

def noop(env, io):
    """test connecting the socket and disconnecting"""

def receiving(env, io):
    """test receiving messages"""
    for i in range(1, 4):
        io.send("3:::" + str(i))
    gevent.sleep(0.5)
    io.send("0::")

def sending(env, io):
    """test sending messages"""
    while True:
        msg = io.receive()
        if msg is None:
            return
        io.send(msg)


def acks_from_client(env, io):
    """test acks sent from client"""
    io.send("tobi")
    io.send("tobi 2")


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

#      io.sockets.json.send(3141592);
#    });
#  });
#
#  server('test sending json from client', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.on('message', function (arr) {
#        if (Array.isArray(arr) && arr.length == 3) {
#          socket.send('echo');
#        }
#      });
#    });
#  });
#
#  server('test emitting an event from server', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.emit('woot');
#    });
#  });
#
#  server('test emitting multiple events at once to the server', function (io) {
#    io.sockets.on('connection', function (socket) {
#      var messages = [];
#
#      socket.on('print', function (msg) {
#        if (messages.indexOf(msg) >= 0) {
#          console.error('duplicate message');
#        }
#
#        messages.push(msg);
#        if (messages.length == 2) {
#          socket.emit('done');
#        }
#      });
#    });
#  });
#
#  server('test emitting an event to server', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.on('woot', function () {
#        socket.emit('echo');
#      });
#    });
#  });
#
#  server('test emitting an event from server and sending back data', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.emit('woot', 1, function (a) {
#        if (a === 'test') {
#          socket.emit('done');
#        }
#      });
#    });
#  });
#
#  server('test emitting an event to server and sending back data', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.on('tobi', function (a, b, fn) {
#        if (a === 1 && b === 2) {
#          fn({ hello: 'world' });
#        }
#      });
#    });
#  });
#
#  server('test encoding a payload', function (io) {
#    io.of('/woot').on('connection', function (socket) {
#      var count = 0;
#
#      socket.on('message', function (a) {
#        if (a == 'ñ') {
#          if (++count == 4) {
#            socket.emit('done');
#          }
#        }
#      });
#    });
#  });
#
#  server('test sending query strings to the server', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.json.send(socket.handshake);
#    })
#  });
#
#  server('test sending newline', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.on('message', function (msg) {
#        if (msg == '\n') {
#          socket.emit('done');
#        }
#      });
#    });
#  });
#
#  server('test sending unicode', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.on('message', function (msg) {
#        if (msg.test == "☃") {
#          socket.emit('done');
#        }
#      });
#    });
#  });
#
#  server('test webworker connection', function (io) {
#    io.sockets.on('connection', function (socket) {
#      socket.on('message', function (msg) {
#        if (msg == 'woot') {
#          socket.emit('done');
#        }
#      });
#    });
#  });
