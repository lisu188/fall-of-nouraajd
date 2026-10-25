# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import http.client
from http import HTTPStatus
from http.server import HTTPServer
import io
from email.message import Message
import threading
import unittest

import mcp


class ResponseHeadersTest(unittest.TestCase):
    def handler(self):
        handler = object.__new__(mcp.EngineHttpRequestHandler)
        handler.request_version = "HTTP/1.1"
        handler.protocol_version = "HTTP/1.1"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.client_address = ("127.0.0.1", 1)
        handler.wfile = io.BytesIO()
        handler.headers = Message()
        return handler

    def testHeaderBoundaryDropsLineBreaksInsteadOfCreatingFields(self):
        for value in ["safe\r\nX-Injected: yes", "safe\nX-Injected: yes", "safe\rX-Injected: yes"]:
            with self.subTest(value=repr(value)):
                handler = self.handler()
                handler._send_safe_header("MCP-Session-Id", value)
                handler._send_safe_header("MCP-Protocol-Version", "2025-11-25")
                handler.end_headers()
                wire = handler.wfile.getvalue()
                self.assertNotIn(b"X-Injected", wire)
                self.assertNotIn(b"MCP-Session-Id", wire)
                self.assertIn(b"MCP-Protocol-Version: 2025-11-25\r\n", wire)

    def testJsonAndEmptyWritersDoNotReflectInvalidMetadata(self):
        for writer in ["json", "empty"]:
            with self.subTest(writer=writer):
                handler = self.handler()
                handler.headers["Origin"] = "https://example.test\r\n X-Folded: yes"
                arguments = dict(session_id="bad\r\nX-Session: yes", protocol_version="bad\nX-Version: yes")
                if writer == "json":
                    handler._write_json({"ok": True}, **arguments)
                else:
                    handler._write_empty(HTTPStatus.NO_CONTENT, **arguments)
                headers = handler.wfile.getvalue().split(b"\r\n\r\n", 1)[0]
                for marker in [b"X-Folded", b"X-Session", b"X-Version"]:
                    self.assertNotIn(marker, headers)
                for name in [b"Access-Control-Allow-Origin", b"MCP-Session-Id", b"MCP-Protocol-Version"]:
                    self.assertFalse(any(line.startswith(name + b":") for line in headers.split(b"\r\n")))

    def testValidMetadataAndCorsRemainUnchanged(self):
        handler = self.handler()
        handler.headers["Origin"] = "https://example.test"
        handler._write_json({"ok": True}, session_id="synthetic-session", protocol_version="2025-11-25")
        headers, body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
        self.assertIn(b"Access-Control-Allow-Origin: https://example.test\r\n", headers)
        self.assertIn(b"MCP-Session-Id: synthetic-session\r\n", headers)
        self.assertIn(b"MCP-Protocol-Version: 2025-11-25", headers)
        self.assertEqual(body, b'{"ok":true}')

    def testRealHttpParserFoldedOriginCannotReachResponseHeaders(self):
        class Writer(mcp.EngineHttpRequestHandler):
            def do_GET(self):
                self._write_json({"ok": True})
            def log_message(self, *_):
                pass

        server = HTTPServer(("127.0.0.1", 0), Writer)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
        thread.start()
        try:
            client = http.client.HTTPConnection(*server.server_address, timeout=2)
            client.putrequest("GET", "/")
            client.putheader("Origin", "https://example.test\r\n X-Folded: yes")
            client.endheaders()
            response = client.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
            self.assertIsNone(response.getheader("X-Folded"))
            self.assertEqual(response.read(), b'{"ok":true}')
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
