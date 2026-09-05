import gc
import io
import json
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

import mcp


class CGameObject:
    def getName(self):
        return "probe"


class McpHandleLifetimeTest(unittest.TestCase):
    def setUp(self):
        self.server = mcp.EngineMcpServer(Path.cwd(), Path("cmake-build-release"))
        self.server._emit_log = lambda **kwargs: None
        self.server.exports["probe"] = mcp.ExportedCallable("probe", "test", "probe", CGameObject, "()")

    def initializeHttp(self):
        return self.server._handle_initialize(1, {"protocolVersion": mcp.LATEST_PROTOCOL_VERSION}, "http").session_id

    def callTool(self, name, arguments, session_id=None):
        return self.server._call_tool(
            {"name": name, "arguments": arguments},
            transport="http" if session_id else "stdio",
            session_id=session_id,
        )["structuredContent"]

    def test_repeated_inspection_reuses_object_handle(self):
        obj = CGameObject()
        handles = [self.server._serialize_result(obj)["__handle__"] for _ in range(1000)]
        self.assertEqual(len(set(handles)), 1)
        self.assertEqual(len(self.server.handles), 1)

    def test_releasing_handle_drops_last_owner_and_invalidates_calls(self):
        obj = CGameObject()
        observer = weakref.ref(obj)
        handle = self.server._serialize_result(obj)["__handle__"]
        del obj
        result = self.callTool("engine_release_handles", {"handles": [handle, handle]})
        self.assertEqual(result, {"released": 1})
        gc.collect()
        self.assertIsNone(observer())
        self.assertTrue(self.server._engine_handle_call({"handle": handle, "method": "getName"})["isError"])

    def test_http_termination_releases_only_its_own_objects(self):
        first_session = self.initializeHttp()
        second_session = self.initializeHttp()
        observers = []

        def createObject():
            obj = CGameObject()
            observers.append(weakref.ref(obj))
            return obj

        self.server.exports["probe"].callable_obj = createObject
        first = self.callTool("engine_call", {"name": "probe"}, first_session)["result"]["__handle__"]
        second = self.callTool("engine_call", {"name": "probe"}, second_session)["result"]["__handle__"]
        self.assertTrue(self.server.terminate_session(first_session))
        gc.collect()
        self.assertIsNone(observers[0]())
        self.assertIsNotNone(observers[1]())
        self.assertEqual(
            self.callTool("engine_handle_call", {"handle": second, "method": "getName"}, second_session)["result"],
            "probe",
        )
        self.assertNotEqual(first, second)

    def test_http_handles_cannot_be_used_or_released_by_other_sessions(self):
        first_session = self.initializeHttp()
        second_session = self.initializeHttp()
        handle = self.callTool("engine_call", {"name": "probe"}, first_session)["result"]["__handle__"]
        denied = self.callTool("engine_handle_call", {"handle": handle, "method": "getName"}, second_session)
        self.assertIn("Unknown handle", denied["error"])
        self.assertEqual(
            self.callTool("engine_release_handles", {"handles": [handle]}, second_session), {"released": 0}
        )
        self.assertEqual(
            self.callTool("engine_handle_call", {"handle": handle, "method": "getName"}, first_session)["result"],
            "probe",
        )

    def test_handle_limit_rejects_without_leaking_partial_results(self):
        existing = CGameObject()
        handle = self.server._serialize_result(existing)["__handle__"]
        with patch.object(mcp, "MAX_MCP_HANDLES_PER_SESSION", 2):
            with self.assertRaises(mcp.ProtocolError):
                self.server._serialize_result([CGameObject(), CGameObject()])
        self.assertEqual(self.server.handles, {handle: existing})

    def test_stdio_eof_releases_handles(self):
        obj = CGameObject()
        observer = weakref.ref(obj)
        self.server._serialize_result(obj)
        del obj
        with patch.object(mcp.sys, "stdin", io.TextIOWrapper(io.BytesIO())):
            self.server.serve_stdio()
        gc.collect()
        self.assertIsNone(observer())

    def test_invalid_utf8_returns_parse_error_and_processes_next_frame(self):
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "initialize",
            "params": {"protocolVersion": mcp.LATEST_PROTOCOL_VERSION},
        }
        stream = io.TextIOWrapper(io.BytesIO(b"\xff\n" + json.dumps(request).encode() + b"\n"))
        replies = []
        self.server._write_stdio_message = replies.append
        with patch.object(mcp.sys, "stdin", stream):
            self.server.serve_stdio()
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[1]["id"], 7)
        self.assertIn("result", replies[1])


if __name__ == "__main__":
    unittest.main()
