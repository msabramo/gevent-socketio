"""
Exception classes for Socket.IO
"""


class DecodeError(Exception):
    """
    Raised when received data cannot be decoded by Socket.IO protocol.
    """
