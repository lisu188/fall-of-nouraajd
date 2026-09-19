# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import json
import unittest
from unittest.mock import patch

import mcp


class McpStdioEncodingTest(unittest.TestCase):
    def testUnicodeRepliesRemainUtf8CompatibleWithAWindowsCodePage(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 9,
            "result": {"text": "Matulog\u2019s lot. Hmph\u2026 \u0141\u00f3d\u017a \U0001f5fa"},
        }
        output = io.BytesIO()
        stream = io.TextIOWrapper(output, encoding="cp1252", errors="strict")
        with patch.object(mcp.sys, "stdout", stream):
            mcp.EngineMcpServer._write_stdio_message(payload)
        encoded = output.getvalue()
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(payload, json.loads(encoded.decode("utf-8")))


if __name__ == "__main__":
    unittest.main()
