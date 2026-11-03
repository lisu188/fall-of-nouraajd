import ast
import gc
import io
import json
import unittest
import weakref
from pathlib import Path
from unittest.mock import Mock, patch

import mcp


class CGameObject:
    def getName(self):
        return "probe"


class McpHandleLifetimeTest(unittest.TestCase):
    def setUp(self):
        self.server = mcp.EngineMcpServer(Path.cwd(), Path("cmake-build-release"))
        self.server._emit_log = lambda **kwargs: None
        self.addCleanup(self.server.close)
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

    def runnerSourcePath(self):
        return Path(__file__).resolve().parents[1] / "test.py"

    def testCanonicalRunnerRegistersEveryHandleLifetimeCaseInSourceSuites(self):
        tree = ast.parse(self.runnerSourcePath().read_text(encoding="utf-8"))
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "tests.test_mcp_handle_lifetime"
        ]
        self.assertEqual(1, len(imports), "Canonical runner must import this source-only test class")
        self.assertEqual(
            [("McpHandleLifetimeTest", "_McpHandleLifetimeTest")],
            [(alias.name, alias.asname) for alias in imports[0].names],
        )
        wrappers = [
            node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "McpHandleLifetimeTest"
        ]
        self.assertEqual(1, len(wrappers))
        self.assertEqual(["_McpHandleLifetimeTest"], [node.id for node in wrappers[0].bases])
        self.assertTrue(
            any(
                isinstance(node, ast.Name) and node.id == "_McpHandleLifetimeTest"
                for child in ast.walk(tree)
                if isinstance(child, ast.Delete)
                for node in child.targets
            )
        )
        wanted = {
            "FAST_TEST_PREFIXES",
            "FAST_TEST_NAMES",
            "COVERAGE_SAFE_EXCLUDED_TEST_NAMES",
            "MCP_BRANCH_TEST_PREFIX",
        }
        namespace = {"_McpHandleLifetimeTest": type(self)}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in wanted
            ):
                namespace[node.targets[0].id] = ast.literal_eval(node.value)
        self.assertTrue(wanted.issubset(namespace))
        selector = next(
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "test_name_matches_suite"
        )
        module = ast.fix_missing_locations(ast.Module(body=[wrappers[0], selector], type_ignores=[]))
        exec(compile(module, str(self.runnerSourcePath()), "exec"), namespace)
        names = unittest.defaultTestLoader.getTestCaseNames(namespace["McpHandleLifetimeTest"])
        self.assertEqual(unittest.defaultTestLoader.getTestCaseNames(type(self)), names)
        for name in names:
            qualified = "McpHandleLifetimeTest." + name
            for suite in ("fast", "full", "coverage-safe"):
                self.assertTrue(namespace["test_name_matches_suite"](qualified, suite), (qualified, suite))

    def testHandleMethodMetadataOptionIsExplicitAndDefaultsToTrue(self):
        schemas = {row["name"]: row["inputSchema"] for row in self.server._list_tools()}
        for name in ("engine_call", "engine_handle_call"):
            with self.subTest(tool=name):
                self.assertEqual(
                    {"type": "boolean", "default": True}, schemas[name]["properties"].get("include_handle_methods")
                )
                self.assertNotIn("include_handle_methods", schemas[name]["required"])

    def testDefaultAndExplicitTrueKeepTheExactFullToolResponse(self):
        obj = CGameObject()
        self.server.exports["probe"].callable_obj = lambda: obj
        implicit = self.server._engine_call({"name": "probe"})
        explicit = self.server._engine_call({"name": "probe", "include_handle_methods": True})
        self.assertEqual(implicit, explicit)
        self.assertIn("getName", {row["name"] for row in implicit["structuredContent"]["result"]["pythonMethods"]})
        self.assertEqual(
            json.dumps(implicit, ensure_ascii=True, separators=(",", ":")),
            json.dumps(explicit, ensure_ascii=True, separators=(",", ":")),
        )
        self.assertEqual(json.loads(implicit["content"][0]["text"]), implicit["structuredContent"])

    def testMetadataOmissionSkipsInspectionBeforeRecursiveSerialization(self):
        obj = CGameObject()
        nested = {"objects": [obj, {"same": obj}], "value": 17, "none": None}
        self.server.exports["probe"].callable_obj = lambda: nested
        self.server.handles["owner"] = obj
        obj.getObjectProperty = lambda name: nested
        for tool, arguments in (
            ("engine_call", {"name": "probe"}),
            ("engine_handle_call", {"handle": "owner", "method": "getObjectProperty", "args": ["nested"]}),
        ):
            with self.subTest(tool=tool):
                with patch.object(
                    self.server, "_python_methods_for", side_effect=AssertionError("unexpected inspection")
                ):
                    response = getattr(self.server, "_" + tool)({**arguments, "include_handle_methods": False})
                self.assertFalse(response["isError"], response)
                result = response["structuredContent"]["result"]
                first, second = result["objects"][0], result["objects"][1]["same"]
                self.assertEqual(first, second)
                self.assertNotIn("pythonMethods", first)
                self.assertEqual({"__handle__", "__type__", "repr"}, set(first))
                self.assertEqual(17, result["value"])
                self.assertIsNone(result["none"])
                self.assertIs(obj, self.server.handles[first["__handle__"]])
                self.assertEqual(json.loads(response["content"][0]["text"]), response["structuredContent"])

    def testInvalidMetadataFlagsRefuseBeforeCallingOrDereferencingTargets(self):
        invoked = Mock(return_value="called")
        self.server.exports["probe"].callable_obj = invoked

        class CGameObject:
            @property
            def getName(self):
                invoked()
                return lambda: "read descriptor"

        self.server.handles["unread"] = CGameObject()
        for flag in (0, "false", None):
            for tool, arguments in (
                ("engine_call", {"name": "probe"}),
                ("engine_handle_call", {"handle": "unread", "method": "getName"}),
            ):
                with self.subTest(tool=tool, flag=flag):
                    with self.assertRaises(mcp.ProtocolError) as caught:
                        getattr(self.server, "_" + tool)({**arguments, "include_handle_methods": flag})
                    self.assertEqual(-32602, caught.exception.code)
        invoked.assert_not_called()

    def testMetadataChoiceStaysLocalAcrossReentrantDefaultCalls(self):
        outer, inner = CGameObject(), CGameObject()
        observations = []

        def probe():
            observations.append(self.server._serialize_result(inner))
            return outer

        self.server.exports["probe"].callable_obj = probe
        compact = self.server._engine_call({"name": "probe", "include_handle_methods": False})
        full = self.server._engine_call({"name": "probe"})
        self.assertIn("pythonMethods", observations[0])
        self.assertNotIn("pythonMethods", compact["structuredContent"]["result"])
        self.assertIn("pythonMethods", full["structuredContent"]["result"])
        self.assertEqual(
            compact["structuredContent"]["result"]["__handle__"], full["structuredContent"]["result"]["__handle__"]
        )

    def testCompactRecursiveFailureRollsBackOnlyNewHandleReservations(self):
        existing = CGameObject()
        handle = self.server._serialize_result(existing)["__handle__"]
        self.server.exports["probe"].callable_obj = lambda: [existing, CGameObject(), CGameObject()]
        with patch.object(mcp, "MAX_MCP_HANDLES_PER_SESSION", 2):
            with self.assertRaises(mcp.ProtocolError):
                self.server._engine_call({"name": "probe", "include_handle_methods": False})
        self.assertEqual({handle: existing}, self.server.handles)
        self.assertEqual({id(existing): handle}, self.server._stdio_handles.object_handles)

    def testCompactHandleKeepsAuthorizationOwnershipAndRelease(self):
        obj = CGameObject()
        observer = weakref.ref(obj)
        self.server.exports["probe"].callable_obj = lambda: obj
        first, second = self.initializeHttp(), self.initializeHttp()
        compact = self.callTool("engine_call", {"name": "probe", "include_handle_methods": False}, first)["result"]
        handle = compact["__handle__"]
        self.assertEqual(
            "probe", self.callTool("engine_handle_call", {"handle": handle, "method": "getName"}, first)["result"]
        )
        denied = self.callTool(
            "engine_handle_call", {"handle": handle, "method": "getName", "include_handle_methods": False}, second
        )
        self.assertIn("Unknown handle", denied["error"])
        denied = self.callTool(
            "engine_handle_call", {"handle": handle, "method": "__dict__", "include_handle_methods": False}, first
        )
        self.assertIn("not exported", denied["error"])
        self.server.exports["probe"].callable_obj = CGameObject
        del obj
        self.assertEqual({"released": 1}, self.callTool("engine_release_handles", {"handles": [handle]}, first))
        gc.collect()
        self.assertIsNone(observer())
        self.assertTrue(self.server._engine_handle_call({"handle": handle, "method": "getName"})["isError"])

    def testFixedRepeatedHandleWorkReducesWireWithoutMetadataInspection(self):
        class CGameObject:
            def getName(self):
                return "fixed-handle"

            def __repr__(self):
                return "<metadata-probe>"

            getBoolProperty = getDescription = getLabel = getNumericProperty = getName
            getObjectProperty = getStringProperty = getType = getTypeId = hasTag = getName

        objects = [CGameObject() for _ in range(5)]
        self.server.exports["probe"].callable_obj = lambda: objects
        original = self.server._python_methods_for
        sizes = {}
        for compact in (False, True):
            with patch.object(self.server, "_python_methods_for", wraps=original) as inspected:
                total = 0
                for _ in range(64):
                    response = self.server._engine_call({"name": "probe", "include_handle_methods": not compact})
                    self.assertFalse(response["isError"], response)
                    total += len(json.dumps(response, ensure_ascii=True, separators=(",", ":")).encode("ascii"))
                self.assertEqual(0 if compact else 320, inspected.call_count)
                sizes[compact] = total
        self.assertLess(sizes[True] * 4, sizes[False], sizes)


if __name__ == "__main__":
    unittest.main()
