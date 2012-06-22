"""
Tests ported from original Socket.IO test suite.

In sync with parser.test.js@2a5c7b2c5b5febbf892cc2f5d2de439b5e0b56a0

Last updated: 3rd March 2012
"""

from __future__ import absolute_import, unicode_literals

from unittest import TestCase

from socketio.protocol import SocketIOProtocol
from socketio.packets import Packet, PACKET_BY_NAME
from socketio.exceptions import DecodeError


class DecodeTest(TestCase):

    def assertMsg(self, msg, **kwargs):
        self.assertEqual(msg._asdict(), kwargs)

    def test_error(self):
        msg = Packet.decode(b"7:::")
        self.assertMsg(msg, type="error", reason="", advice="")

    def test_error_with_reason(self):
        msg = Packet.decode(b"7:::0")
        self.assertMsg(msg, type="error", reason="transport not supported", advice="")

    def test_error_with_reason_and_advice(self):
        msg = Packet.decode(b"7:::2+0")
        self.assertMsg(msg, type="error", reason="unauthorized", advice="reconnect")

    def test_error_with_endpoint(self):
        msg = Packet.decode(b"7::/woot")
        self.assertMsg(msg, type="error", reason="", advice="", endpoint="/woot")

    def test_ack(self):
        msg = Packet.decode(b"6:::140")
        self.assertMsg(msg, type="ack", ackid=b'140', args=[])

    def test_ack_with_args(self):
        msg = Packet.decode(b'6:::12+["woot","wa"]')
        self.assertMsg(msg, type="ack", ackid=b'12', args=["woot", "wa"])

    def test_ack_with_bad_json(self):
        """
        NOTE: this test differs from original, as we prefer throwing an error
        then silently ignore (read the ZEN).
        """
        with self.assertRaises(DecodeError):
            Packet.decode(b'6:::1+{"++]')

    def test_json(self):
        msg = Packet.decode(b'4:::"2"')
        self.assertMsg(msg, type="json", data=b'2')

    def test_json_with_message_id_and_ack(self):
        msg = Packet.decode(b'4:1+::{"a":"b"}')
        self.assertMsg(msg, type="json", id=b'1', ack="data", data={"a": "b"})

    def test_event(self):
        msg = Packet.decode(b'5:::{"name":"woot"}')
        self.assertMsg(msg, type="event", name="woot", args=[])

    def test_event_with_data(self):
        msg = Packet.decode(b'5:::{"name":"edwald","args":[{"a": "b"},2,"3"]}')
        self.assertMsg(msg, type="event", name="edwald", args=[{"a": "b"}, 2, "3"])

    def test_message(self):
        msg = Packet.decode(b'3:::woot')
        self.assertMsg(msg, type="message", data=b"woot")

    def test_message_with_id_and_endpoint(self):
        msg = Packet.decode(b'3:5:/tobi')
        self.assertMsg(msg, type="message", id=b'5', ack=True, data=b"", endpoint="/tobi")

    def test_heartbeat(self):
        msg = Packet.decode(b'2::')
        self.assertMsg(msg, type="heartbeat")

    def test_connect(self):
        msg = Packet.decode(b'1::/tobi')
        self.assertMsg(msg, type="connect", endpoint="/tobi", qs={})

    def test_connect_with_querystring(self):
        msg = Packet.decode(b'1::/test:?test=1')
        self.assertMsg(msg, type="connect", endpoint="/test", qs={"test": ["1"]})

    def test_disconnect(self):
        msg = Packet.decode(b'0::/woot')
        self.assertMsg(msg, type="disconnect", endpoint="/woot")

    def test_decoding_newline(self):
        msg = Packet.decode(b'3:::\n')
        self.assertMsg(msg, type="message", data=b"\n")

class EncodeTest(TestCase):

    def _encode(self, msg):
        if isinstance(msg, basestring):
            return msg
        cls = PACKET_BY_NAME[msg.pop("type")]
        for f in cls._fields:
            msg.setdefault(f, None)
        return cls(**msg).encode()

    def test_error(self):
        data = self._encode({"type": "error"})
        self.assertEqual(data, b"7::")

    def test_error_with_reason(self):
        data = self._encode({"type": "error", "reason": "transport not supported"})
        self.assertEqual(data, b"7:::0")

    def test_error_with_reason_and_advice(self):
        data = self._encode({"type": "error", "reason": "unauthorized", "advice": "reconnect"})
        self.assertEqual(data, b"7:::2+0")

    def test_error_with_endpoint(self):
        data = self._encode({"type": "error", "endpoint": "/woot"})
        self.assertEqual(data, b"7::/woot")

    def test_ack(self):
        data = self._encode({"type": "ack", "ackid": b'140'})
        self.assertEqual(data, b"6:::140")

    def test_ack_with_args(self):
        data = self._encode({"type": "ack", "ackid": b'12', "args": ["woot", "wa"]})
        self.assertEqual(data, b'6:::12+["woot", "wa"]')

    def test_json(self):
        data = self._encode({"type": "json", "data": '2'})
        self.assertEqual(data, b'4:::"2"')

    def test_json_with_id_and_ack(self):
        data = self._encode({"type": "json", "data": {"a": "b"}, "id": 1, "ack": "data"})
        self.assertEqual(data, b'4:1+::{"a": "b"}')

    def test_event(self):
        data = self._encode({"type": "event", "name": "woot"})
        self.assertEqual(data, b'5:::{"name": "woot"}')

    def test_event_with_id_and_ack(self):
        data = self._encode({"type": "event", "id": b'1', "ack": "data", "name": "tobi"})
        self.assertEqual(data, b'5:1+::{"name": "tobi"}')

    def test_event_with_data(self):
        data = self._encode({"type": "event", "name": "edwald", "args": [{"a": "b"}, 2, "3"]})
        self.assertEqual(data, b'5:::{"name": "edwald", "args": [{"a": "b"}, 2, "3"]}')

    def test_message(self):
        data = self._encode({"type": "message", "data": "woot"})
        self.assertEqual(data, b'3:::woot')

    def test_message_with_id_and_endpoint(self):
        data = self._encode({"type": "message", "id": b'5', "ack": True, "endpoint": "/tobi"})
        self.assertEqual(data, b'3:5:/tobi')

    def test_heartbeat(self):
        data = self._encode({"type": "heartbeat"})
        self.assertEqual(data, b'2::')

    def test_connect(self):
        data = self._encode({"type": "connect", "endpoint": "/tobi"})
        self.assertEqual(data, b'1::/tobi')

    def test_connect_with_querystring(self):
        data = self._encode({"type": "connect", "endpoint": "/test", "qs": {"test": 1}})
        self.assertEqual(data, b'1::/test:?test=1')

    def test_disconnect(self):
        data = self._encode({"type": "disconnect", "endpoint": "/woot"})
        self.assertEqual(data, b'0::/woot')
