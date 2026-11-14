import unittest
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock

import mcp


class McpHttpHostTests(unittest.TestCase):
    def test_loopback_hosts_are_accepted(self):
        for host in ("127.0.0.1", "localhost", "localhost:8765", "127.0.0.1:8765"):
            with self.subTest(host=host):
                self.assertTrue(mcp.valid_local_http_host(host, 8765))

    def test_foreign_or_malformed_hosts_are_rejected(self):
        hosts = (
            None, "", "example.com", "example.com:8765", "127.0.0.1.evil.test",
            "0.0.0.0:8765", "127.0.0.1:9999", "localhost:bogus",
            "localhost:65536", "localhost@", "localhost/path", "localhost?x=1",
            "localhost#x", "localhost\r\nX-Forged: yes", "[::1]:8765",
        )
        for host in hosts:
            with self.subTest(host=host):
                self.assertFalse(mcp.valid_local_http_host(host, 8765))

    def test_nonlocal_bind_is_refused_before_opening_a_socket(self):
        server = object.__new__(mcp.EngineMcpServer)
        for host in ("0.0.0.0", "192.168.1.10", "example.com", "::"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(ValueError, "loopback"):
                    server.serve_http(host, 8765)

    def test_duplicate_or_invalid_host_headers_are_rejected(self):
        handler = object.__new__(mcp.EngineHttpRequestHandler)
        handler.server = SimpleNamespace(server_port=8765)
        handler._write_mcp_error = Mock()
        for hosts in ([], ["evil.test"], ["localhost:8765", "evil.test"]):
            with self.subTest(hosts=hosts):
                handler.headers = Message()
                for host in hosts:
                    handler.headers.add_header("Host", host)
                handler.close_connection = False
                self.assertFalse(handler._validate_host_header())
                self.assertTrue(handler.close_connection)
        self.assertEqual(handler._write_mcp_error.call_count, 3)

    def test_valid_host_header_is_accepted(self):
        handler = object.__new__(mcp.EngineHttpRequestHandler)
        handler.server = SimpleNamespace(server_port=8765)
        handler.headers = Message()
        handler.headers.add_header("Host", "localhost:8765")
        handler._write_mcp_error = Mock()
        self.assertTrue(handler._validate_host_header())
        handler._write_mcp_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
