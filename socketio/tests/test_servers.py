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
    """
    Echo back all messages.
    """
    for msg in io:
        io.send(msg)
