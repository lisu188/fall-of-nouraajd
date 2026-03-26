#!/usr/bin/env python3
"""Copyright 2025.

Minimal MCP server that exposes a unified `engine` module composed of
`game` and `_game` callables.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

JSONRPC_VERSION = "2.0"
SERVER_NAME = "fall-of-nouraajd-engine-mcp"
SERVER_VERSION = "0.1.0"


@dataclass
class ExportedCallable:
    name: str
    source: str
    target_name: str
    callable_obj: Any
    signature: str


class EngineMcpServer:
    def __init__(self, repo_root: Path, build_dir: Path) -> None:
        self.repo_root = repo_root
        self.build_dir = build_dir
        self.handles: dict[str, Any] = {}
        self.next_handle = 1
        self.exports: dict[str, ExportedCallable] = {}
        self.game_module: Any | None = None
        self._game_module: Any | None = None

    def build_extension(self) -> None:
        subprocess.run(
            ["cmake", "--build", str(self.build_dir), "--target", "_game", f"-j{os.cpu_count() or 1}"],
            cwd=self.repo_root,
            check=True,
        )

    def import_modules(self) -> None:
        sys.path.insert(0, str(self.repo_root / "res"))
        sys.path.insert(0, str(self.build_dir))
        try:
            self._game_module = importlib.import_module("_game")
        except ModuleNotFoundError as exc:  # pragma: no cover - defensive path
            raise ModuleNotFoundError(
                "Unable to import compiled `_game` module. Build it with `cmake --build "
                f"{self.build_dir} --target _game -j$(nproc)` or run mcp.py with `--build`."
            ) from exc
        self.game_module = importlib.import_module("game")

    def inspect_and_export(self) -> None:
        if self._game_module is None or self.game_module is None:
            raise RuntimeError("Modules are not imported")

        self._export_module_callables(self._game_module, source="_game")
        self._export_module_callables(self.game_module, source="game")

    def _export_module_callables(self, module: Any, source: str) -> None:
        for name, value in inspect.getmembers(module):
            if name.startswith("_"):
                continue
            if not callable(value):
                continue
            if inspect.isclass(value):
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

    @staticmethod
    def _safe_signature(fn: Any) -> str:
        try:
            return str(inspect.signature(fn))
        except (TypeError, ValueError):
            return "(signature unavailable)"

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        return self._handle_request(request)

    def serve_stdio(self) -> None:
        while True:
            request = self._read_message()
            if request is None:
                return

            response = self.handle_request(request)
            if response is not None:
                self._write_message(response)

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return {
                "jsonrpc": JSONRPC_VERSION,
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "capabilities": {"tools": {"listChanged": False}},
                },
            }
        if method == "tools/list":
            return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": {"tools": self._list_tools()}}
        if method == "tools/call":
            return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": self._call_tool(params)}

        return {
            "jsonrpc": JSONRPC_VERSION,
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def _list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "engine_list",
                "description": "List unified exported callables from _game and game modules.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "engine_call",
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
            },
            {
                "name": "engine_handle_call",
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
            },
        ]

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "engine_list":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                [
                                    {
                                        "name": exported.name,
                                        "signature": exported.signature,
                                        "source": exported.source,
                                    }
                                    for exported in sorted(self.exports.values(), key=lambda item: item.name)
                                ],
                                indent=2,
                            ),
                        }
                    ]
                }
            if tool_name == "engine_call":
                return self._engine_call(args)
            if tool_name == "engine_handle_call":
                return self._engine_handle_call(args)
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]}
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "error": str(exc),
                                "traceback": traceback.format_exc(limit=6),
                            },
                            indent=2,
                        ),
                    }
                ],
            }

    def _engine_call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        name = arguments.get("name")
        call_args = arguments.get("args", [])
        call_kwargs = arguments.get("kwargs", {})

        if not isinstance(name, str) or not name:
            raise ValueError("engine_call requires non-empty string `name`")
        exported = self.exports.get(name)
        if exported is None:
            raise KeyError(f"Callable not exported: {name}")

        result = exported.callable_obj(*call_args, **call_kwargs)
        serialized = self._serialize_result(result)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "name": name,
                            "source": exported.source,
                            "result": serialized,
                        },
                        indent=2,
                    ),
                }
            ]
        }

    def _engine_handle_call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        handle = arguments.get("handle")
        method = arguments.get("method")
        call_args = arguments.get("args", [])
        call_kwargs = arguments.get("kwargs", {})
        if handle not in self.handles:
            raise KeyError(f"Unknown handle: {handle}")
        if not isinstance(method, str) or not method:
            raise ValueError("engine_handle_call requires non-empty string `method`")

        target = self.handles[handle]
        method_callable = getattr(target, method)
        if not callable(method_callable):
            raise TypeError(f"Attribute `{method}` on handle `{handle}` is not callable")

        result = method_callable(*call_args, **call_kwargs)
        serialized = self._serialize_result(result)
        return {"content": [{"type": "text", "text": json.dumps({"result": serialized}, indent=2)}]}

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
        return {"__handle__": handle, "__type__": value.__class__.__name__, "repr": repr(value)}

    @staticmethod
    def _read_message() -> dict[str, Any] | None:
        content_length: int | None = None

        while True:
            header = sys.stdin.buffer.readline()
            if not header:
                return None
            if header in (b"\r\n", b"\n"):
                break
            normalized = header.decode("utf-8").strip()
            if normalized.lower().startswith("content-length:"):
                content_length = int(normalized.split(":", 1)[1].strip())

        if content_length is None:
            raise RuntimeError("Missing Content-Length header")

        body = sys.stdin.buffer.read(content_length)
        return json.loads(body.decode("utf-8"))

    @staticmethod
    def _write_message(payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        sys.stdout.buffer.write(header)
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()

    def serve_http(self, host: str, port: int) -> None:
        httpd = EngineHttpServer((host, port), EngineHttpRequestHandler, self)
        try:
            print(f"HTTP MCP server listening on http://{host}:{port}", file=sys.stderr)
            httpd.serve_forever()
        finally:
            httpd.server_close()


class EngineHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, mcp_server: EngineMcpServer) -> None:  # noqa: N803
        super().__init__(server_address, RequestHandlerClass)
        self.mcp_server = mcp_server


class EngineHttpRequestHandler(BaseHTTPRequestHandler):
    server_version = f"{SERVER_NAME}/{SERVER_VERSION}"
    protocol_version = "HTTP/1.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._add_default_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in {"/", "/healthz", "/status"}:
            payload = {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "status": "ok",
                "tools": len(self.server.mcp_server.exports),  # type: ignore[attr-defined]
            }
            self._write_json(payload)
            return
        if self.path == "/manifest.json":
            payload = {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
            }
            self._write_json(payload)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

    def do_POST(self) -> None:
        if self.path not in {"/", "/rpc", "/mcp"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            self.send_error(HTTPStatus.LENGTH_REQUIRED, "Missing Content-Length header")
            return
        try:
            length = int(length_header)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid Content-Length header")
            return
        raw_body = self.rfile.read(length)
        try:
            request = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            return

        response = self.server.mcp_server.handle_request(request)  # type: ignore[attr-defined]
        if response is None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._add_default_headers()
            self.end_headers()
            return
        self._write_json(response)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write(
            "[HTTP MCP] %s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args)
        )

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._add_default_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _add_default_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP server exposing unified game/_game functions")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--build-dir", default="cmake-build-release", help="Build directory containing _game")
    parser.add_argument("--build", action="store_true", help="Build the extension before starting the server")
    parser.add_argument("--stdio", action="store_true", help="Run as a stdio MCP server instead of HTTP")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host to bind when running in HTTP mode")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port to bind when running in HTTP mode")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    build_dir = (repo_root / args.build_dir).resolve()

    server = EngineMcpServer(repo_root=repo_root, build_dir=build_dir)
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
