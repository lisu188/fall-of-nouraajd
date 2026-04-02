#!/usr/bin/env python3

import argparse
import importlib
import inspect
import json
import logging
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

JSONRPC_VERSION = "2.0"
SERVER_NAME = "fall-of-nouraajd-engine-mcp"
SERVER_TITLE = "Fall of Nouraajd Engine MCP"
SERVER_VERSION = "0.2.0"
LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = {
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
}
DEFAULT_HTTP_FALLBACK_PROTOCOL_VERSION = "2025-03-26"
LOG_LEVELS = {
    "debug": 7,
    "info": 6,
    "notice": 5,
    "warning": 4,
    "error": 3,
    "critical": 2,
    "alert": 1,
    "emergency": 0,
}

logger = logging.getLogger(SERVER_NAME)


@dataclass
class ExportedCallable:
    name: str
    source: str
    target_name: str
    callable_obj: Any
    signature: str


@dataclass
class ClientStream:
    stream_id: str
    queue: queue.Queue[dict[str, Any] | None]
    created_at: float = field(default_factory=time.time)


@dataclass
class ConnectionState:
    transport: str
    protocol_version: str
    initialized: bool = False
    log_level: str = "info"
    client_capabilities: dict[str, Any] = field(default_factory=dict)
    client_info: dict[str, Any] = field(default_factory=dict)
    streams: dict[str, ClientStream] = field(default_factory=dict)


@dataclass
class HandleResult:
    response: dict[str, Any] | None
    session_id: str | None = None
    protocol_version: str | None = None


class ProtocolError(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class EngineMcpServer:
    def __init__(
        self,
        repo_root: Path,
        build_dir: Path,
        allow_origins: list[str] | None = None,
        trace_messages: bool = False,
        native_log_sink: str = "stdout",
        native_log_path: Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.build_dir = build_dir
        self.allow_origins = allow_origins or []
        self.trace_messages = trace_messages
        self.native_log_sink = native_log_sink
        self.native_log_path = native_log_path
        self.handles: dict[str, Any] = {}
        self.next_handle = 1
        self.exports: dict[str, ExportedCallable] = {}
        self.game_module: Any | None = None
        self._game_module: Any | None = None
        self.http_sessions: dict[str, ConnectionState] = {}
        self.stdio_state: ConnectionState | None = None
        self._lock = threading.RLock()
        self._next_stream_seq = 1

    def build_extension(self) -> None:
        logger.info("building extension target _game in %s", self.build_dir)
        subprocess.run(
            ["cmake", "--build", str(self.build_dir), "--target", "_game", f"-j{os.cpu_count() or 1}"],
            cwd=self.repo_root,
            check=True,
        )

    def import_modules(self) -> None:
        os.chdir(self.build_dir)
        sys.path.insert(0, str(self.repo_root / "res"))
        sys.path.insert(0, str(self.build_dir))
        try:
            self._game_module = importlib.import_module("_game")
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Unable to import compiled `_game` module. Build it with `cmake --build "
                f"{self.build_dir} --target _game -j$(nproc)` or run mcp.py with `--build`."
            ) from exc
        self._configure_native_logging()
        self.game_module = importlib.import_module("game")
        logger.info("modules imported successfully")

    def inspect_and_export(self) -> None:
        if self._game_module is None or self.game_module is None:
            raise RuntimeError("Modules are not imported")
        self._export_module_callables(self._game_module, source="_game")
        self._export_module_callables(self.game_module, source="game")
        logger.info("exported %d callables", len(self.exports))

    def _configure_native_logging(self) -> None:
        if self._game_module is None:
            return
        setter = getattr(self._game_module, "set_logger_sink", None)
        if setter is None:
            logger.warning("native module does not expose set_logger_sink; cannot redirect native logs")
            return
        sink = self.native_log_sink or "stdout"
        call_args: list[Any] = [sink]
        call_args.append(str(self.native_log_path) if self.native_log_path is not None else None)
        try:
            setter(*call_args)
        except Exception:
            logger.exception("failed to configure native logger sink")
            return
        target_desc = sink
        if self.native_log_path:
            target_desc = f"{sink}:{self.native_log_path}"
        logger.info("configured native logger sink to %s", target_desc)

    def _export_module_callables(self, module: Any, source: str) -> None:
        for name, value in inspect.getmembers(module):
            if name.startswith("_"):
                continue
            if inspect.isclass(value):
                self._export_class_python_methods(value, source=source)
            if not callable(value):
                continue
            if name in {"load", "register", "trigger"}:
                continue
            if name not in self.exports:
                self.exports[name] = ExportedCallable(
                    name=name,
                    source=source,
                    target_name=name,
                    callable_obj=value,
                    signature=self._safe_signature(value),
                )

    def _export_class_python_methods(self, cls: Any, source: str) -> None:
        class_name = getattr(cls, "__name__", None)
        if not isinstance(class_name, str) or not class_name or class_name.startswith("_"):
            return
        for name, value in inspect.getmembers(cls):
            if name.startswith("_"):
                continue
            if self._python_callable(value) is None:
                continue
            export_name = f"{class_name}.{name}"
            if export_name in self.exports:
                continue
            self.exports[export_name] = ExportedCallable(
                name=export_name,
                source=f"{source}.{class_name}",
                target_name=name,
                callable_obj=value,
                signature=self._safe_signature(value),
            )

    @staticmethod
    def _safe_signature(fn: Any) -> str:
        try:
            return str(inspect.signature(fn))
        except (TypeError, ValueError):
            return "(signature unavailable)"

    @staticmethod
    def _python_callable(value: Any) -> Any | None:
        if inspect.isfunction(value):
            return value
        function = getattr(value, "__func__", None)
        if function is not None and inspect.isfunction(function):
            return function
        if (
            callable(value)
            and inspect.ismethoddescriptor(value)
            and type(value).__name__ == "instancemethod"
            and getattr(value, "__self__", None) is not None
        ):
            return value
        return None

    def serve_stdio(self) -> None:
        logger.info("starting stdio MCP server")
        while True:
            request = self._read_stdio_message()
            if request is None:
                logger.info("stdio closed")
                return
            self._trace_message(
                transport="stdio",
                direction="recv",
                payload=request,
                extra={"jsonrpcResponse": self._is_jsonrpc_response(request)},
            )
            response = self._handle_stdio_payload(request)
            if response is None:
                continue
            self._trace_message(
                transport="stdio",
                direction="send",
                payload=response,
                session_id=None,
            )
            self._write_stdio_message(response)

    def _handle_stdio_payload(self, payload: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
        if isinstance(payload, list):
            if not payload:
                return self._error_response(None, -32600, "Invalid Request")

            responses: list[dict[str, Any]] = []
            for item in payload:
                if not isinstance(item, dict):
                    responses.append(self._error_response(None, -32600, "Invalid Request"))
                    continue
                if self._is_jsonrpc_response(item):
                    logger.debug("ignoring stdio client response payload in batch")
                    continue
                try:
                    result = self.handle_message(item, transport="stdio", session_id=None)
                except ProtocolError as exc:
                    responses.append(self._error_response(item.get("id"), exc.code, exc.message, exc.data))
                    continue
                except Exception:
                    logger.exception("unhandled stdio batch item failure")
                    responses.append(self._error_response(item.get("id"), -32603, "Internal error"))
                    continue

                if result.response is not None and not self._is_notification(item):
                    responses.append(result.response)

            return responses or None

        if isinstance(payload, dict) and self._is_jsonrpc_response(payload):
            logger.debug("ignoring stdio client response payload")
            return None

        try:
            result = self.handle_message(payload, transport="stdio", session_id=None)
            if result.response is not None:
                return result.response
            return None
        except ProtocolError as exc:
            req_id = payload.get("id") if isinstance(payload, dict) else None
            return self._error_response(req_id, exc.code, exc.message, exc.data)
        except Exception:
            logger.exception("unhandled stdio request failure")
            req_id = payload.get("id") if isinstance(payload, dict) else None
            return self._error_response(req_id, -32603, "Internal error")

    def handle_http_post(
        self,
        payload: Any,
        session_id: str | None,
        protocol_version_header: str | None,
    ) -> tuple[HTTPStatus, dict[str, Any] | list[dict[str, Any]] | None, str | None, str | None]:
        if isinstance(payload, list):
            return self._handle_http_batch(
                payload, session_id=session_id, protocol_version_header=protocol_version_header
            )

        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, self._error_response(None, -32600, "Invalid Request"), None, None

        if self._is_jsonrpc_response(payload):
            logger.debug("accepted client JSON-RPC response over HTTP")
            return HTTPStatus.ACCEPTED, None, None, None

        try:
            result = self.handle_message(
                payload, transport="http", session_id=session_id, protocol_version_header=protocol_version_header
            )
        except ProtocolError as exc:
            req_id = payload.get("id") if isinstance(payload, dict) else None
            return (
                HTTPStatus.BAD_REQUEST if exc.code in {-32600, -32602} else HTTPStatus.OK,
                self._error_response(req_id, exc.code, exc.message, exc.data),
                None,
                None,
            )
        except Exception:
            logger.exception("unhandled HTTP request failure")
            req_id = payload.get("id") if isinstance(payload, dict) else None
            return HTTPStatus.OK, self._error_response(req_id, -32603, "Internal error"), None, None

        if self._is_notification(payload):
            return HTTPStatus.ACCEPTED, None, result.session_id, result.protocol_version

        return HTTPStatus.OK, result.response, result.session_id, result.protocol_version

    def _handle_http_batch(
        self,
        payload: list[Any],
        session_id: str | None,
        protocol_version_header: str | None,
    ) -> tuple[HTTPStatus, dict[str, Any] | list[dict[str, Any]] | None, str | None, str | None]:
        if not payload:
            return HTTPStatus.BAD_REQUEST, self._error_response(None, -32600, "Invalid Request"), None, None

        responses: list[dict[str, Any]] = []
        new_session_id: str | None = None
        negotiated_protocol_version: str | None = None

        for item in payload:
            if not isinstance(item, dict):
                responses.append(self._error_response(None, -32600, "Invalid Request"))
                continue
            if self._is_jsonrpc_response(item):
                continue
            try:
                result = self.handle_message(
                    item,
                    transport="http",
                    session_id=session_id,
                    protocol_version_header=protocol_version_header,
                )
                if result.session_id and new_session_id is None:
                    new_session_id = result.session_id
                if result.protocol_version and negotiated_protocol_version is None:
                    negotiated_protocol_version = result.protocol_version
                if result.response is not None and not self._is_notification(item):
                    responses.append(result.response)
            except ProtocolError as exc:
                responses.append(self._error_response(item.get("id"), exc.code, exc.message, exc.data))
            except Exception:
                logger.exception("unhandled HTTP batch item failure")
                responses.append(self._error_response(item.get("id"), -32603, "Internal error"))

        if not responses:
            return HTTPStatus.ACCEPTED, None, new_session_id, negotiated_protocol_version

        return HTTPStatus.OK, responses, new_session_id, negotiated_protocol_version

    def handle_message(
        self,
        request: dict[str, Any],
        transport: str,
        session_id: str | None,
        protocol_version_header: str | None = None,
    ) -> HandleResult:
        if not isinstance(request, dict):
            raise ProtocolError(-32600, "Invalid Request")
        if request.get("jsonrpc") != JSONRPC_VERSION:
            raise ProtocolError(-32600, "Invalid Request")

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method is None:
            raise ProtocolError(-32600, "Invalid Request")

        if not isinstance(method, str) or not method:
            raise ProtocolError(-32600, "Invalid Request")

        if "id" in request and req_id is None:
            raise ProtocolError(-32600, "Invalid Request")

        if self._is_notification(request):
            if method == "initialize":
                raise ProtocolError(-32600, "Invalid Request")
            if transport == "http" and session_id is None and method != "notifications/initialized":
                raise ProtocolError(-32600, "Invalid Request")

        if method == "initialize":
            if not isinstance(params, dict):
                raise ProtocolError(-32602, "Invalid params")
            if transport == "http" and session_id is not None:
                raise ProtocolError(-32600, "Initialize must not include an MCP-Session-Id header")
            return self._handle_initialize(req_id=req_id, params=params, transport=transport)

        state = self._require_connection_state(transport=transport, session_id=session_id)

        if transport == "http":
            effective_protocol_version = self._resolve_http_protocol_version(
                state=state,
                header_value=protocol_version_header,
            )
            if state.protocol_version != effective_protocol_version:
                logger.debug(
                    "session %s protocol header override from %s to %s",
                    session_id,
                    state.protocol_version,
                    effective_protocol_version,
                )
                state.protocol_version = effective_protocol_version
        else:
            effective_protocol_version = state.protocol_version

        if method == "notifications/initialized":
            state.initialized = True
            self._emit_log(
                transport=transport,
                session_id=session_id,
                level="info",
                logger_name="lifecycle",
                data={"message": "client initialized", "protocolVersion": effective_protocol_version},
            )
            return HandleResult(response=None, session_id=session_id, protocol_version=effective_protocol_version)

        if method == "notifications/cancelled":
            self._emit_log(
                transport=transport,
                session_id=session_id,
                level="notice",
                logger_name="lifecycle",
                data={"message": "request cancellation received", "params": self._jsonable(params)},
            )
            return HandleResult(response=None, session_id=session_id, protocol_version=effective_protocol_version)

        if method == "ping":
            return HandleResult(
                response=self._result_response(req_id, {}),
                session_id=session_id,
                protocol_version=effective_protocol_version,
            )

        if not state.initialized:
            raise ProtocolError(-32002, "Server not initialized")

        if method == "logging/setLevel":
            if not isinstance(params, dict):
                raise ProtocolError(-32602, "Invalid params")
            level = params.get("level")
            if not isinstance(level, str) or level not in LOG_LEVELS:
                raise ProtocolError(-32602, "Invalid log level")
            previous = state.log_level
            state.log_level = level
            self._emit_log(
                transport=transport,
                session_id=session_id,
                level="notice",
                logger_name="logging",
                data={"message": "log level updated", "previous": previous, "current": level},
            )
            return HandleResult(
                response=self._result_response(req_id, {}),
                session_id=session_id,
                protocol_version=effective_protocol_version,
            )

        if method == "tools/list":
            if params is not None and not isinstance(params, dict):
                raise ProtocolError(-32602, "Invalid params")
            cursor = params.get("cursor") if isinstance(params, dict) else None
            if cursor not in {None, ""}:
                raise ProtocolError(-32602, "Unsupported cursor")
            return HandleResult(
                response=self._result_response(req_id, {"tools": self._list_tools()}),
                session_id=session_id,
                protocol_version=effective_protocol_version,
            )

        if method == "tools/call":
            if not isinstance(params, dict):
                raise ProtocolError(-32602, "Invalid params")
            result = self._call_tool(params, transport=transport, session_id=session_id)
            return HandleResult(
                response=self._result_response(req_id, result),
                session_id=session_id,
                protocol_version=effective_protocol_version,
            )

        raise ProtocolError(-32601, f"Method not found: {method}")

    def _handle_initialize(self, req_id: Any, params: dict[str, Any], transport: str) -> HandleResult:
        requested_protocol_version = params.get("protocolVersion")
        client_capabilities = params.get("capabilities", {})
        client_info = params.get("clientInfo", {})

        if not isinstance(requested_protocol_version, str):
            raise ProtocolError(-32602, "Invalid params")
        if requested_protocol_version in SUPPORTED_PROTOCOL_VERSIONS:
            negotiated_protocol_version = requested_protocol_version
        else:
            negotiated_protocol_version = LATEST_PROTOCOL_VERSION

        if not isinstance(client_capabilities, dict):
            raise ProtocolError(-32602, "Invalid params")
        if not isinstance(client_info, dict):
            raise ProtocolError(-32602, "Invalid params")

        state = ConnectionState(
            transport=transport,
            protocol_version=negotiated_protocol_version,
            initialized=False,
            client_capabilities=client_capabilities,
            client_info=client_info,
        )

        new_session_id: str | None = None
        if transport == "stdio":
            self.stdio_state = state
        else:
            new_session_id = self._create_session_id()
            with self._lock:
                self.http_sessions[new_session_id] = state

        self._emit_log(
            transport=transport,
            session_id=new_session_id,
            level="info",
            logger_name="lifecycle",
            data={
                "message": "session initialized",
                "transport": transport,
                "protocolVersion": negotiated_protocol_version,
                "clientInfo": self._jsonable(client_info),
            },
        )

        return HandleResult(
            response=self._result_response(
                req_id,
                {
                    "protocolVersion": negotiated_protocol_version,
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "title": SERVER_TITLE,
                        "version": SERVER_VERSION,
                    },
                    "capabilities": {
                        "logging": {},
                        "tools": {
                            "listChanged": False,
                        },
                    },
                },
            ),
            session_id=new_session_id,
            protocol_version=negotiated_protocol_version,
        )

    def _require_connection_state(self, transport: str, session_id: str | None) -> ConnectionState:
        if transport == "stdio":
            if self.stdio_state is None:
                raise ProtocolError(-32002, "Server not initialized")
            return self.stdio_state
        if session_id is None:
            raise ProtocolError(-32600, "Missing MCP-Session-Id")
        with self._lock:
            state = self.http_sessions.get(session_id)
        if state is None:
            raise ProtocolError(-32001, "Unknown session")
        return state

    def _resolve_http_protocol_version(self, state: ConnectionState, header_value: str | None) -> str:
        if header_value is None or header_value == "":
            return state.protocol_version or DEFAULT_HTTP_FALLBACK_PROTOCOL_VERSION
        if header_value not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ProtocolError(-32600, "Unsupported MCP-Protocol-Version")
        return header_value

    def _create_session_id(self) -> str:
        while True:
            session_id = secrets.token_urlsafe(24)
            if all(0x21 <= ord(ch) <= 0x7E for ch in session_id):
                with self._lock:
                    if session_id not in self.http_sessions:
                        return session_id

    def _create_stream(self, session_id: str) -> ClientStream:
        with self._lock:
            state = self.http_sessions.get(session_id)
            if state is None:
                raise KeyError(session_id)
            stream_id = f"s_{self._next_stream_seq}"
            self._next_stream_seq += 1
            stream = ClientStream(stream_id=stream_id, queue=queue.Queue())
            state.streams[stream_id] = stream
            return stream

    def _remove_stream(self, session_id: str, stream_id: str) -> None:
        with self._lock:
            state = self.http_sessions.get(session_id)
            if state is None:
                return
            state.streams.pop(stream_id, None)

    def terminate_session(self, session_id: str) -> bool:
        with self._lock:
            state = self.http_sessions.pop(session_id, None)
        if state is None:
            return False
        for stream in list(state.streams.values()):
            try:
                stream.queue.put_nowait(None)
            except Exception:
                pass
        logger.info("terminated session %s", session_id)
        return True

    def serve_http(self, host: str, port: int) -> None:
        httpd = EngineHttpServer((host, port), EngineHttpRequestHandler, self)
        try:
            logger.info("HTTP MCP server listening on http://%s:%d/mcp", host, port)
            httpd.serve_forever()
        finally:
            httpd.server_close()

    def validate_origin(self, origin: str | None) -> bool:
        if not origin:
            return True
        if origin in self.allow_origins:
            return True
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"}:
            return False
        hostname = parsed.hostname
        return hostname in {"127.0.0.1", "localhost"}

    def _list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "engine_list",
                "title": "List engine exports",
                "description": "List unified exported callables from _game and game modules.",
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "exports": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "signature": {"type": "string"},
                                    "source": {"type": "string"},
                                },
                                "required": ["name", "signature", "source"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["exports"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "engine_call",
                "title": "Call engine function",
                "description": "Call an exported engine callable by name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "args": {"type": "array", "default": []},
                        "kwargs": {"type": "object", "default": {}},
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "source": {"type": "string"},
                        "result": {},
                    },
                    "required": ["name", "source", "result"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "engine_handle_call",
                "title": "Call method on engine handle",
                "description": "Call a method on a previously returned engine handle.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "handle": {"type": "string"},
                        "method": {"type": "string"},
                        "args": {"type": "array", "default": []},
                        "kwargs": {"type": "object", "default": {}},
                    },
                    "required": ["handle", "method"],
                    "additionalProperties": False,
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "result": {},
                    },
                    "required": ["result"],
                    "additionalProperties": False,
                },
            },
        ]

    def _call_tool(self, params: dict[str, Any], transport: str, session_id: str | None) -> dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not isinstance(tool_name, str) or not tool_name:
            raise ProtocolError(-32602, "Invalid params")
        if not isinstance(arguments, dict):
            raise ProtocolError(-32602, "Invalid params")

        self._emit_log(
            transport=transport,
            session_id=session_id,
            level="info",
            logger_name="tools",
            data={"message": "tool call started", "tool": tool_name},
        )

        if tool_name == "engine_list":
            exports = [
                {
                    "name": exported.name,
                    "signature": exported.signature,
                    "source": exported.source,
                }
                for exported in sorted(self.exports.values(), key=lambda item: item.name)
            ]
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({"exports": exports}, ensure_ascii=False),
                    }
                ],
                "structuredContent": {
                    "exports": exports,
                },
                "isError": False,
            }
            self._emit_log(
                transport=transport,
                session_id=session_id,
                level="info",
                logger_name="tools",
                data={"message": "tool call completed", "tool": tool_name, "count": len(exports)},
            )
            return result

        if tool_name == "engine_call":
            result = self._engine_call(arguments)
            self._emit_log(
                transport=transport,
                session_id=session_id,
                level="info",
                logger_name="tools",
                data={"message": "tool call completed", "tool": tool_name},
            )
            return result

        if tool_name == "engine_handle_call":
            result = self._engine_handle_call(arguments)
            self._emit_log(
                transport=transport,
                session_id=session_id,
                level="info",
                logger_name="tools",
                data={"message": "tool call completed", "tool": tool_name},
            )
            return result

        raise ProtocolError(-32602, f"Unknown tool: {tool_name}")

    def _engine_call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        name = arguments.get("name")
        call_args = arguments.get("args", [])
        call_kwargs = arguments.get("kwargs", {})

        if not isinstance(name, str) or not name:
            raise ProtocolError(-32602, "engine_call requires non-empty string `name`")
        if not isinstance(call_args, list):
            raise ProtocolError(-32602, "engine_call `args` must be an array")
        if not isinstance(call_kwargs, dict):
            raise ProtocolError(-32602, "engine_call `kwargs` must be an object")

        exported = self.exports.get(name)
        if exported is None:
            raise ProtocolError(-32602, f"Callable not exported: {name}")

        try:
            resolved_args = self._resolve_handle_references(call_args)
            resolved_kwargs = self._resolve_handle_references(call_kwargs)
            result = exported.callable_obj(*resolved_args, **resolved_kwargs)
            serialized = self._serialize_result(result)
            structured = {
                "name": name,
                "source": exported.source,
                "result": serialized,
            }
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(structured, ensure_ascii=False),
                    }
                ],
                "structuredContent": structured,
                "isError": False,
            }
        except ProtocolError:
            raise
        except Exception as exc:
            error_payload = {
                "error": str(exc),
                "traceback": traceback.format_exc(limit=10),
            }
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(error_payload, ensure_ascii=False),
                    }
                ],
                "structuredContent": error_payload,
                "isError": True,
            }

    def _engine_handle_call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        handle = arguments.get("handle")
        method = arguments.get("method")
        call_args = arguments.get("args", [])
        call_kwargs = arguments.get("kwargs", {})

        if not isinstance(handle, str) or not handle:
            raise ProtocolError(-32602, "engine_handle_call requires non-empty string `handle`")
        if not isinstance(method, str) or not method:
            raise ProtocolError(-32602, "engine_handle_call requires non-empty string `method`")
        if not isinstance(call_args, list):
            raise ProtocolError(-32602, "engine_handle_call `args` must be an array")
        if not isinstance(call_kwargs, dict):
            raise ProtocolError(-32602, "engine_handle_call `kwargs` must be an object")
        if handle not in self.handles:
            result = {"error": f"Unknown handle: {handle}"}
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": True,
            }

        target = self.handles[handle]
        try:
            method_callable = getattr(target, method)
        except AttributeError:
            result = {"error": f"Unknown method `{method}` for handle `{handle}`"}
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": True,
            }

        if not callable(method_callable):
            result = {"error": f"Attribute `{method}` on handle `{handle}` is not callable"}
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": True,
            }

        try:
            resolved_args = self._resolve_handle_references(call_args)
            resolved_kwargs = self._resolve_handle_references(call_kwargs)
            result = method_callable(*resolved_args, **resolved_kwargs)
            serialized = self._serialize_result(result)
            structured = {"result": serialized}
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(structured, ensure_ascii=False),
                    }
                ],
                "structuredContent": structured,
                "isError": False,
            }
        except Exception as exc:
            error_payload = {
                "error": str(exc),
                "traceback": traceback.format_exc(limit=10),
            }
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(error_payload, ensure_ascii=False),
                    }
                ],
                "structuredContent": error_payload,
                "isError": True,
            }

    def _resolve_handle_references(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._resolve_handle_references(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._resolve_handle_references(item) for item in value)
        if isinstance(value, dict):
            handle = value.get("__handle__")
            if isinstance(handle, str):
                if handle not in self.handles:
                    raise ProtocolError(-32602, f"Unknown handle: {handle}")
                return self.handles[handle]
            return {str(key): self._resolve_handle_references(item) for key, item in value.items()}
        return value

    def _python_methods_for(self, value: Any) -> list[dict[str, str]]:
        methods: list[dict[str, str]] = []
        for name, member in inspect.getmembers(type(value)):
            if name.startswith("_"):
                continue
            if self._python_callable(member) is None:
                continue
            methods.append({"name": name, "signature": self._safe_signature(member)})
        methods.sort(key=lambda item: item["name"])
        return methods

    def _serialize_result(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [self._serialize_result(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._serialize_result(item) for key, item in value.items()}
        handle = f"h_{self.next_handle}"
        self.next_handle += 1
        self.handles[handle] = value
        result = {"__handle__": handle, "__type__": value.__class__.__name__, "repr": repr(value)}
        python_methods = self._python_methods_for(value)
        if python_methods:
            result["pythonMethods"] = python_methods
        return result

    def _trace_message(
        self,
        *,
        transport: str,
        direction: str,
        payload: Any,
        session_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self.trace_messages:
            return
        record: dict[str, Any] = {
            "transport": transport,
            "direction": direction,
            "sessionId": session_id,
            "payload": self._jsonable(payload),
        }
        if extra:
            record["meta"] = self._jsonable(extra)
        logger.debug("trace %s", json.dumps(record, ensure_ascii=False))

    def _emit_log(
        self,
        transport: str,
        session_id: str | None,
        level: str,
        logger_name: str,
        data: Any,
    ) -> None:
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "notifications/message",
            "params": {
                "level": level,
                "logger": logger_name,
                "data": self._jsonable(data),
            },
        }

        message = f"[{logger_name}] {json.dumps(self._jsonable(data), ensure_ascii=False)}"
        python_level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "notice": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
            "alert": logging.CRITICAL,
            "emergency": logging.CRITICAL,
        }.get(level, logging.INFO)
        logger.log(python_level, message)

        if transport == "stdio":
            state = self.stdio_state
            if state and state.initialized and self._should_emit_client_log(state.log_level, level):
                self._trace_message(
                    transport="stdio",
                    direction="send",
                    payload=payload,
                    session_id=None,
                    extra={"logger": logger_name},
                )
                self._write_stdio_message(payload)
            return

        if session_id is None:
            return
        with self._lock:
            state = self.http_sessions.get(session_id)
            if state is None or not state.initialized or not self._should_emit_client_log(state.log_level, level):
                return
            streams = list(state.streams.values())
        if not streams:
            return
        for stream in streams:
            try:
                stream.queue.put_nowait(payload)
            except Exception:
                pass

    @staticmethod
    def _should_emit_client_log(min_level: str, candidate_level: str) -> bool:
        return LOG_LEVELS[candidate_level] <= LOG_LEVELS[min_level]

    @staticmethod
    def _result_response(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        response: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "error": error}
        if req_id is not None:
            response["id"] = req_id
        return response

    @staticmethod
    def _is_notification(payload: dict[str, Any]) -> bool:
        return isinstance(payload, dict) and "method" in payload and "id" not in payload

    @staticmethod
    def _is_jsonrpc_response(payload: Any) -> bool:
        return isinstance(payload, dict) and "method" not in payload and ("result" in payload or "error" in payload)

    @staticmethod
    def _read_stdio_message() -> Any | None:
        while True:
            raw = sys.stdin.buffer.readline()
            if not raw:
                return None
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            return json.loads(line)

    @staticmethod
    def _write_stdio_message(payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write(body)
        sys.stdout.write("\n")
        sys.stdout.flush()

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [EngineMcpServer._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): EngineMcpServer._jsonable(item) for key, item in value.items()}
        return repr(value)


class EngineHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, request_handler_class, mcp_server: EngineMcpServer) -> None:
        super().__init__(server_address, request_handler_class)
        self.mcp_server = mcp_server


class EngineHttpRequestHandler(BaseHTTPRequestHandler):
    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/mcp" and not self.server.mcp_server.validate_origin(self.headers.get("Origin")):
            self._write_mcp_error(HTTPStatus.FORBIDDEN, None, -32600, "Forbidden origin")
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._add_default_headers()
        self.send_header("Allow", "GET, POST, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]

        if path in {"/healthz", "/status"}:
            payload = {
                "name": SERVER_NAME,
                "title": SERVER_TITLE,
                "version": SERVER_VERSION,
                "status": "ok",
                "tools": len(self.server.mcp_server.exports),
            }
            self._write_json(payload)
            return

        if path == "/manifest.json":
            payload = {
                "name": SERVER_NAME,
                "title": SERVER_TITLE,
                "version": SERVER_VERSION,
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {
                    "logging": {},
                    "tools": {"listChanged": False},
                },
                "mcpEndpoint": "/mcp",
            }
            self._write_json(payload)
            return

        if path == "/":
            payload = {
                "name": SERVER_NAME,
                "title": SERVER_TITLE,
                "version": SERVER_VERSION,
                "status": "ok",
                "mcpEndpoint": "/mcp",
            }
            self._write_json(payload)
            return

        if path != "/mcp":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        if not self.server.mcp_server.validate_origin(self.headers.get("Origin")):
            self._write_mcp_error(HTTPStatus.FORBIDDEN, None, -32600, "Forbidden origin")
            return

        accept = self.headers.get("Accept", "")
        if "text/event-stream" not in accept:
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self._add_default_headers()
            self.send_header("Allow", "POST, DELETE, OPTIONS, GET")
            self.end_headers()
            return

        session_id = self.headers.get("MCP-Session-Id")
        if not session_id:
            self._write_mcp_error(HTTPStatus.BAD_REQUEST, None, -32600, "Missing MCP-Session-Id")
            return

        state = self.server.mcp_server.http_sessions.get(session_id)
        if state is None:
            self._write_mcp_error(HTTPStatus.NOT_FOUND, None, -32001, "Unknown session")
            return

        protocol_version_header = self.headers.get("MCP-Protocol-Version")
        try:
            protocol_version = self.server.mcp_server._resolve_http_protocol_version(state, protocol_version_header)
        except ProtocolError as exc:
            self._write_mcp_error(HTTPStatus.BAD_REQUEST, None, exc.code, exc.message, exc.data)
            return

        try:
            stream = self.server.mcp_server._create_stream(session_id)
        except KeyError:
            self._write_mcp_error(HTTPStatus.NOT_FOUND, None, -32001, "Unknown session")
            return

        self.send_response(HTTPStatus.OK)
        self._add_default_headers()
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("MCP-Session-Id", session_id)
        self.send_header("MCP-Protocol-Version", protocol_version)
        self.end_headers()

        try:
            self._write_sse_event(stream.stream_id, "")
            while True:
                try:
                    item = stream.queue.get(timeout=30.0)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    break
                self.server.mcp_server._trace_message(
                    transport="http",
                    direction="send",
                    session_id=session_id,
                    payload=item,
                    extra={"stream": stream.stream_id},
                )
                self._write_sse_event(stream.stream_id, json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        finally:
            self.server.mcp_server._remove_stream(session_id, stream.stream_id)

    def do_DELETE(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/mcp":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        if not self.server.mcp_server.validate_origin(self.headers.get("Origin")):
            self._write_mcp_error(HTTPStatus.FORBIDDEN, None, -32600, "Forbidden origin")
            return

        session_id = self.headers.get("MCP-Session-Id")
        if not session_id:
            self._write_mcp_error(HTTPStatus.BAD_REQUEST, None, -32600, "Missing MCP-Session-Id")
            return

        if not self.server.mcp_server.terminate_session(session_id):
            self._write_mcp_error(HTTPStatus.NOT_FOUND, None, -32001, "Unknown session")
            return

        self.send_response(HTTPStatus.NO_CONTENT)
        self._add_default_headers()
        self.end_headers()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/mcp":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        if not self.server.mcp_server.validate_origin(self.headers.get("Origin")):
            self._write_mcp_error(HTTPStatus.FORBIDDEN, None, -32600, "Forbidden origin")
            return

        accept = self.headers.get("Accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            self._write_mcp_error(
                HTTPStatus.BAD_REQUEST,
                None,
                -32600,
                "Accept header must include application/json and text/event-stream",
            )
            return

        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self._write_mcp_error(HTTPStatus.LENGTH_REQUIRED, None, -32600, "Missing Content-Length header")
            return

        try:
            length = int(length_header)
        except ValueError:
            self._write_mcp_error(HTTPStatus.BAD_REQUEST, None, -32600, "Invalid Content-Length header")
            return

        try:
            raw_body = self.rfile.read(length)
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._write_mcp_error(HTTPStatus.BAD_REQUEST, None, -32700, "Parse error")
            return

        session_id = self.headers.get("MCP-Session-Id")
        protocol_version_header = self.headers.get("MCP-Protocol-Version")

        self.server.mcp_server._trace_message(
            transport="http",
            direction="recv",
            session_id=session_id,
            payload=payload,
            extra={"path": path, "protocolVersion": protocol_version_header},
        )

        if isinstance(payload, dict) and payload.get("method") != "initialize":
            if not session_id:
                self._write_mcp_error(HTTPStatus.BAD_REQUEST, payload.get("id"), -32600, "Missing MCP-Session-Id")
                return
            if session_id not in self.server.mcp_server.http_sessions:
                self._write_mcp_error(HTTPStatus.NOT_FOUND, payload.get("id"), -32001, "Unknown session")
                return

        status, response, new_session_id, negotiated_protocol_version = self.server.mcp_server.handle_http_post(
            payload=payload,
            session_id=session_id,
            protocol_version_header=protocol_version_header,
        )

        response_session_id = new_session_id or session_id
        response_protocol_version = negotiated_protocol_version
        if response_protocol_version is None and response_session_id:
            state = self.server.mcp_server.http_sessions.get(response_session_id)
            if state is not None:
                response_protocol_version = state.protocol_version

        if response is None:
            self.send_response(status)
            self._add_default_headers()
            if response_session_id:
                self.send_header("MCP-Session-Id", response_session_id)
            if response_protocol_version:
                self.send_header("MCP-Protocol-Version", response_protocol_version)
            self.end_headers()
            self.server.mcp_server._trace_message(
                transport="http",
                direction="send",
                session_id=response_session_id,
                payload={"status": int(status), "body": None},
                extra={"path": path, "protocolVersion": response_protocol_version, "status": int(status)},
            )
            return

        self.server.mcp_server._trace_message(
            transport="http",
            direction="send",
            session_id=response_session_id,
            payload=response,
            extra={"path": path, "protocolVersion": response_protocol_version, "status": int(status)},
        )
        self._write_json(
            response,
            status=status,
            session_id=response_session_id,
            protocol_version=response_protocol_version,
        )

    def log_message(self, format: str, *args: Any) -> None:
        logger.info('%s - "%s"', self.address_string(), format % args)

    def _write_json(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
        status: HTTPStatus = HTTPStatus.OK,
        session_id: str | None = None,
        protocol_version: str | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._add_default_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if session_id:
            self.send_header("MCP-Session-Id", session_id)
        if protocol_version:
            self.send_header("MCP-Protocol-Version", protocol_version)
        self.end_headers()
        self.wfile.write(body)

    def _write_mcp_error(
        self,
        status: HTTPStatus,
        req_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> None:
        payload = {"jsonrpc": JSONRPC_VERSION, "error": {"code": code, "message": message}}
        if req_id is not None:
            payload["id"] = req_id
        if data is not None:
            payload["error"]["data"] = data
        self.server.mcp_server._trace_message(
            transport="http",
            direction="send",
            session_id=self.headers.get("MCP-Session-Id"),
            payload=payload,
            extra={
                "path": self.path.split("?", 1)[0],
                "status": int(status),
                "error": True,
            },
        )
        self._write_json(payload, status=status)

    def _write_sse_event(self, event_id: str, data: str) -> None:
        lines = []
        lines.append(f"id: {event_id}")
        if data:
            for line in data.splitlines() or [""]:
                lines.append(f"data: {line}")
        else:
            lines.append("data:")
        lines.append("")
        lines.append("")
        self.wfile.write("\n".join(lines).encode("utf-8"))
        self.wfile.flush()

    def _add_default_headers(self) -> None:
        self.send_header(
            "Access-Control-Allow-Origin", self.headers.get("Origin", "*") if self.headers.get("Origin") else "*"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "content-type, accept, origin, mcp-session-id, mcp-protocol-version, last-event-id",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Vary", "Accept, Origin, MCP-Protocol-Version, MCP-Session-Id")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP server exposing unified game/_game functions")
    parser.add_argument("--repo-root", default=None, help="Repository root path")
    parser.add_argument("--build-dir", default="cmake-build-release", help="Build directory containing _game")
    parser.add_argument("--build", action="store_true", help="Build the extension before starting the server")
    parser.add_argument("--stdio", action="store_true", help="Run as a stdio MCP server instead of HTTP")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host to bind when running in HTTP mode")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port to bind when running in HTTP mode")
    parser.add_argument("--log-level", default="INFO", help="Python log level")
    parser.add_argument(
        "--trace-messages",
        action="store_true",
        help="Log full MCP request/response payloads for debugging",
    )
    parser.add_argument("--allow-origin", action="append", default=[], help="Additional allowed Origin value")
    parser.add_argument(
        "--native-log-sink",
        choices=["stdout", "stderr", "file", "disabled"],
        default=None,
        help="Configure native engine logging target (default stdout, file when --stdio).",
    )
    parser.add_argument(
        "--native-log-file",
        default=None,
        help="File path for native logs when using --native-log-sink file (relative to repo root by default).",
    )
    return parser.parse_args()


def configure_logging(level_name: str, log_sink: str = "stderr", trace_messages: bool = False) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    if trace_messages and level > logging.DEBUG:
        level = logging.DEBUG
    stream = sys.stdout if log_sink == "stdout" else sys.stderr
    logging.basicConfig(
        level=level,
        stream=stream,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main() -> int:
    args = parse_args()
    python_log_sink = "stderr" if args.stdio else "stdout"
    configure_logging(args.log_level, log_sink=python_log_sink, trace_messages=args.trace_messages)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent
    build_dir_arg = Path(args.build_dir)
    build_dir = build_dir_arg.resolve() if build_dir_arg.is_absolute() else (repo_root / build_dir_arg).resolve()
    native_log_sink = args.native_log_sink or ("file" if args.stdio else "stdout")
    native_log_path: Path | None = None
    if native_log_sink == "file":
        log_path = Path(args.native_log_file) if args.native_log_file else build_dir / "logs" / "mcp-stdio.log"
        if not log_path.is_absolute():
            log_path = repo_root / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        native_log_path = log_path
    elif args.native_log_file:
        logger.warning(
            "Ignoring --native-log-file because native log sink %s does not use a file",
            native_log_sink,
        )

    server = EngineMcpServer(
        repo_root=repo_root,
        build_dir=build_dir,
        allow_origins=args.allow_origin,
        trace_messages=args.trace_messages,
        native_log_sink=native_log_sink,
        native_log_path=native_log_path,
    )
    if args.build:
        server.build_extension()
    server.import_modules()
    server.inspect_and_export()
    if args.stdio:
        server.serve_stdio()
    else:
        server.serve_http(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
