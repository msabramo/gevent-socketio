"""
Exception classes for Socket.IO
"""

from __future__ import absolute_import, unicode_literals

class DecodeError(Exception):
    """
    Raised when received data cannot be decoded by Socket.IO protocol.
    """
