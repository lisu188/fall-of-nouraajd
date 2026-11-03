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

    def testTextContentOptionIsExplicitOnlyOnEngineCallsAndDefaultsToTrue(self):
        tools = {row["name"]: row for row in self.server._list_tools()}
        for name, tool in tools.items():
            with self.subTest(tool=name):
                option = tool["inputSchema"].get("properties", {}).get("include_text_content")
                if name in {"engine_call", "engine_handle_call"}:
                    self.assertIsNotNone(option)
                    self.assertEqual("boolean", option["type"])
                    self.assertIs(True, option["default"])
                    self.assertIn("structuredContent-aware", option["description"])
                    self.assertNotIn("include_text_content", tool["inputSchema"]["required"])
                    self.assertEqual("object", tool["outputSchema"]["type"])
                else:
                    self.assertIsNone(option)

    def testTextContentDefaultAndExplicitTrueKeepSuccessAndExceptionBytes(self):
        obj = CGameObject()
        self.server.handles["owner"] = obj
        self.server.exports["probe"].callable_obj = lambda: {"nested": [obj, None, 17, "Łódź"]}
        for tool, arguments in (
            ("engine_call", {"name": "probe"}),
            ("engine_handle_call", {"handle": "owner", "method": "getName"}),
        ):
            with self.subTest(tool=tool, error=False):
                invoke = getattr(self.server, "_" + tool)
                implicit = invoke(arguments)
                explicit = invoke({**arguments, "include_text_content": True})
                self.assertEqual(implicit, explicit)
                self.assertEqual(
                    json.dumps(implicit, ensure_ascii=True, separators=(",", ":")),
                    json.dumps(explicit, ensure_ascii=True, separators=(",", ":")),
                )
                self.assertEqual(json.loads(implicit["content"][0]["text"]), implicit["structuredContent"])
        self.server.exports["probe"].callable_obj = Mock(side_effect=ValueError("controlled export error"))
        obj.getName = Mock(side_effect=ValueError("controlled method error"))
        with patch.object(mcp.traceback, "format_exc", return_value="controlled traceback\n") as trace:
            for tool, arguments in (
                ("engine_call", {"name": "probe"}),
                ("engine_handle_call", {"handle": "owner", "method": "getName"}),
            ):
                with self.subTest(tool=tool, error=True):
                    invoke = getattr(self.server, "_" + tool)
                    implicit = invoke(arguments)
                    explicit = invoke({**arguments, "include_text_content": True})
                    self.assertTrue(implicit["isError"])
                    self.assertEqual(
                        json.dumps(implicit, ensure_ascii=True, separators=(",", ":")),
                        json.dumps(explicit, ensure_ascii=True, separators=(",", ":")),
                    )
                    self.assertEqual("controlled traceback\n", implicit["structuredContent"]["traceback"])
            self.assertEqual(4, trace.call_count)
            self.assertTrue(all(call.kwargs == {"limit": 10} for call in trace.call_args_list))

    def testTextOmissionKeepsNestedResultsMetadataAndActualHandleIdentity(self):
        obj = CGameObject()
        nested = {"objects": [obj, {"again": obj}], "empty": [], "none": None, "value": "Łódź"}
        self.server.handles["owner"] = obj
        obj.getObjectProperty = lambda key: nested
        self.server.exports["probe"].callable_obj = lambda: nested
        for metadata in (True, False):
            for tool, arguments in (
                ("engine_call", {"name": "probe"}),
                ("engine_handle_call", {"handle": "owner", "method": "getObjectProperty", "args": ["nested"]}),
            ):
                with self.subTest(metadata=metadata, tool=tool):
                    invoke = getattr(self.server, "_" + tool)
                    full = invoke({**arguments, "include_handle_methods": metadata})
                    textless = invoke({**arguments, "include_handle_methods": metadata, "include_text_content": False})
                    self.assertEqual([], textless["content"])
                    self.assertEqual(full["structuredContent"], textless["structuredContent"])
                    self.assertEqual(full["isError"], textless["isError"])
                    handle = textless["structuredContent"]["result"]["objects"][0]
                    self.assertEqual(metadata, "pythonMethods" in handle)
                    self.assertEqual(handle, textless["structuredContent"]["result"]["objects"][1]["again"])
                    self.assertIs(obj, self.server.handles[handle["__handle__"]])

    def testInvalidTextFlagsRefuseBeforeRegistryExportOrTargetLookup(self):
        called = Mock(return_value="called")
        self.server.exports["probe"].callable_obj = called

        class CGameObject:
            @property
            def getName(self):
                called()
                return lambda: "descriptor value"

        self.server.handles["owner"] = CGameObject()
        lookups = Mock()

        class TrackingDict(dict):
            def get(self, key, default=None):
                lookups(key)
                return super().get(key, default)

        self.server.exports = TrackingDict(self.server.exports)
        self.server._stdio_handles.handles = TrackingDict(self.server.handles)
        with patch.object(self.server, "_handleRegistry", wraps=self.server._handleRegistry) as registry, patch.object(
            self.server, "_resolve_handle_references", wraps=self.server._resolve_handle_references
        ) as resolved, patch.object(
            self.server, "_allowed_handle_methods_for", wraps=self.server._allowed_handle_methods_for
        ) as allowed:
            for flag in (None, 0, 1, 0.0, "false", [], {}):
                for tool, arguments in (
                    ("engine_call", {"name": "probe"}),
                    ("engine_handle_call", {"handle": "owner", "method": "getName"}),
                ):
                    for dispatched in (False, True):
                        with self.subTest(flag=flag, tool=tool, dispatched=dispatched):
                            arguments = {**arguments, "include_text_content": flag}
                            with self.assertRaises(mcp.ProtocolError) as caught:
                                if dispatched:
                                    self.server._dispatch_tool({"name": tool, "arguments": arguments}, "stdio", None)
                                else:
                                    getattr(self.server, "_" + tool)(arguments)
                            self.assertEqual(-32602, caught.exception.code)
                            self.assertEqual("include_text_content must be a boolean", caught.exception.message)
            lookups.assert_not_called()
            called.assert_not_called()
            registry.assert_not_called()
            resolved.assert_not_called()
            allowed.assert_not_called()

    def testTextOmissionKeepsEveryEarlyHandleFailureAndGuard(self):
        obj = CGameObject()
        self.server.handles["owner"] = obj

        def compare(arguments):
            full = self.server._engine_handle_call(arguments)
            textless = self.server._engine_handle_call({**arguments, "include_text_content": False})
            self.assertEqual([], textless["content"])
            self.assertTrue(full["isError"])
            self.assertEqual(full["isError"], textless["isError"])
            self.assertEqual(full["structuredContent"], textless["structuredContent"])
            self.assertIsInstance(textless["structuredContent"], dict)

        for arguments in (
            {"handle": "owner", "method": "__dict__"},
            {"handle": "missing", "method": "getName"},
            {"handle": "owner", "method": "notExported"},
            {"handle": "owner", "method": "getLabel"},
        ):
            with self.subTest(arguments=arguments):
                compare(arguments)
        obj.getName = 17
        compare({"handle": "owner", "method": "getName"})
        obj.getName = lambda: "probe"
        with patch.object(self.server, "_resolve_handle_references", side_effect=ValueError("controlled resolution")):
            compare({"handle": "owner", "method": "getName"})
        for hook in ("_validate_pathfinding_call", "_validateEquipmentCall"):
            with self.subTest(guard=hook), patch.object(self.server, hook, return_value={"error": "controlled guard"}):
                compare({"handle": "owner", "method": "getName"})

    def testTextOmissionKeepsExceptionPayloadAndSkipsCompatibilityJsonEncoding(self):
        obj = CGameObject()
        self.server.handles["owner"] = obj
        self.server.exports["probe"].callable_obj = Mock(side_effect=ValueError("export failed"))
        obj.getName = Mock(side_effect=ValueError("method failed"))
        with patch.object(mcp.traceback, "format_exc", return_value="controlled traceback\n"):
            for tool, arguments in (
                ("engine_call", {"name": "probe"}),
                ("engine_handle_call", {"handle": "owner", "method": "getName"}),
            ):
                with self.subTest(tool=tool):
                    invoke = getattr(self.server, "_" + tool)
                    full = invoke(arguments)
                    with patch.object(mcp.json, "dumps", wraps=mcp.json.dumps) as encoded:
                        textless = invoke({**arguments, "include_text_content": False})
                    self.assertEqual([], textless["content"])
                    self.assertTrue(textless["isError"])
                    self.assertEqual(full["structuredContent"], textless["structuredContent"])
                    self.assertEqual(0, encoded.call_count)

    def testTextChoiceIsLocalAcrossReentrantAndFollowingDefaultCalls(self):
        seen = []
        self.server.exports["inner"] = mcp.ExportedCallable("inner", "test", "inner", lambda: 17, "()")

        def outer():
            seen.append(self.server._engine_call({"name": "inner"}))
            return "outer"

        self.server.exports["probe"].callable_obj = outer
        textless = self.server._engine_call({"name": "probe", "include_text_content": False})
        full = self.server._engine_call({"name": "probe"})
        self.assertEqual([], textless["content"])
        self.assertTrue(full["content"])
        self.assertTrue(all(response["content"] for response in seen))
        self.assertEqual({"name": "probe", "source": "test", "result": "outer"}, textless["structuredContent"])

    def testTextlessHandleKeepsHttpSessionAuthorizationAndRelease(self):
        obj = CGameObject()
        self.server.exports["probe"].callable_obj = lambda: obj
        first, second = self.initializeHttp(), self.initializeHttp()
        response = self.server._call_tool(
            {"name": "engine_call", "arguments": {"name": "probe", "include_text_content": False}}, "http", first
        )
        self.assertEqual([], response["content"])
        handle = response["structuredContent"]["result"]["__handle__"]
        denied = self.server._call_tool(
            {
                "name": "engine_handle_call",
                "arguments": {"handle": handle, "method": "getName", "include_text_content": False},
            },
            "http",
            second,
        )
        self.assertEqual([], denied["content"])
        self.assertTrue(denied["isError"])
        self.assertIn("Unknown handle", denied["structuredContent"]["error"])
        self.assertEqual(
            "probe",
            self.callTool(
                "engine_handle_call", {"handle": handle, "method": "getName", "include_text_content": False}, first
            )["result"],
        )
        self.assertEqual({"released": 0}, self.callTool("engine_release_handles", {"handles": [handle]}, second))
        self.assertEqual({"released": 1}, self.callTool("engine_release_handles", {"handles": [handle]}, first))

    def testFixedTextlessWireWorkKeepsActionsAndReflectionExactlyEqual(self):
        class CGameObject:
            def getName(self):
                return "fixed-handle"

            def __repr__(self):
                return "<fixed-text-content-probe>"

            getBoolProperty = getDescription = getLabel = getNumericProperty = getName
            getObjectProperty = getStringProperty = getType = getTypeId = hasTag = getName

        objects = [CGameObject() for _ in range(5)]
        action = Mock(return_value={"nested": [objects, None], "value": 17})
        self.server.exports["probe"].callable_obj = action
        results = {}
        for metadata in (True, False):
            for text in (True, False):
                with patch.object(
                    self.server, "_python_methods_for", wraps=self.server._python_methods_for
                ) as inspected, patch.object(mcp.json, "dumps", wraps=mcp.json.dumps) as encoded:
                    responses = [
                        self.server._engine_call(
                            {"name": "probe", "include_handle_methods": metadata, "include_text_content": text}
                        )
                        for _ in range(64)
                    ]
                self.assertEqual(320 if metadata else 0, inspected.call_count)
                self.assertEqual(64 if text else 0, encoded.call_count)
                self.assertTrue(all(not response["isError"] for response in responses))
                self.assertTrue(all(bool(response["content"]) == text for response in responses))
                results[metadata, text] = (
                    responses[0]["structuredContent"],
                    sum(
                        len(json.dumps(response, ensure_ascii=True, separators=(",", ":")).encode("ascii"))
                        for response in responses
                    ),
                )
            self.assertEqual(results[metadata, True][0], results[metadata, False][0])
            self.assertLess(results[metadata, False][1] * 5, results[metadata, True][1] * 3, results)
            print(
                f"[MCP text content] metadata={metadata} calls=64 fullBytes={results[metadata, True][1]} "
                f"textlessBytes={results[metadata, False][1]} fullEncodes=64 textlessEncodes=0 "
                f"inspectionEach={320 if metadata else 0} budget=textless<60%"
            )
        self.assertEqual(256, action.call_count)


if __name__ == "__main__":
    unittest.main()
