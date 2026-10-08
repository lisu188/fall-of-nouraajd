# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
"""Opt-in, per-run diagnostics shared by the game and its MCP launcher."""

from datetime import datetime, timezone
import inspect
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import traceback
import uuid

_ACTIVE_SESSION = None
_LOGGER_NAMES = ("game_diagnostics", "game", "fall-of-nouraajd-engine-mcp")
_SECRET_KEYS = {"authorization", "mcp-session-id", "sessionid", "session_id", "token", "password", "secret"}


def currentSession():
    return _ACTIVE_SESSION if _ACTIVE_SESSION is not None and not _ACTIVE_SESSION._closed else None


def debugEnabled(value=None):
    if value is not None:
        return bool(value)
    return os.environ.get("GAME_DEBUG", "").strip().lower() not in {"", "0", "false", "off", "disabled", "no"}


def _boundedValue(value, key=None, depth=0):
    if key and key.lower() in _SECRET_KEYS:
        return "<redacted>"
    if depth >= 5:
        return "<depth limit>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        return value if len(value) <= 1024 else value[:1024] + "...<truncated>"
    if isinstance(value, dict):
        result = {}
        for index, (item_key, item) in enumerate(value.items()):
            if index == 50:
                result["..."] = "<item limit>"
                break
            item_key = str(item_key)[:160]
            result[item_key] = _boundedValue(item, item_key, depth + 1)
        return result
    if isinstance(value, (tuple, list)):
        return [_boundedValue(item, depth=depth + 1) for item in value[:50]]
    return f"<{type(value).__name__}>"


def _utcNow():
    return datetime.now(timezone.utc).isoformat()


class _RuntimeHandler(RotatingFileHandler):
    def __init__(self, session):
        self.session = session
        super().__init__(session.paths["runtime"], maxBytes=4 * 1024 * 1024, backupCount=2, encoding="utf-8")
        self.setLevel(logging.DEBUG)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    def handleError(self, record):
        self.session._channelFailure("runtime", "Unable to write runtime diagnostics")


class DebugSession:
    def __init__(self, repo_root, build_dir, entrypoint, debug_dir=None):
        self.repoRoot = Path(repo_root).resolve()
        self.buildDir = Path(build_dir).resolve()
        output_dir = debug_dir if debug_dir is not None else os.environ.get("GAME_DEBUG_DIR")
        base_dir = Path(output_dir).expanduser() if output_dir else self.buildDir / "logs" / "debug"
        if not base_dir.is_absolute():
            base_dir = self.repoRoot / base_dir
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.runDir = base_dir.resolve() / run_id
        self.paths = {
            "manifest": self.runDir / "manifest.json",
            "runtime": self.runDir / "runtime.log",
            "native": self.runDir / "native.log",
            "gameplay": self.runDir / "gameplay.jsonl",
        }
        self.nativeSink = "file"
        self.nativePath = self.paths["native"]
        self._explicitTrace = any(key.startswith("GAME_PLAYTEST_TRACE") for key in os.environ)
        self._prepared = False
        self._closed = False
        self._finished = False
        self._warnings = set()
        self._handlers = []
        self._readyChannels = set()
        self._loggerLevels = {}
        self._loggerPropagation = {}
        self._savedEnv = {}
        self._nativeAttempt = 0
        self._manifestLock = threading.RLock()
        self._oldSysHook = None
        self._oldThreadHook = None
        self._sysHook = None
        self._threadHook = None
        self.manifest = {
            "schema": "game_diagnostics.v1",
            "runId": run_id,
            "entrypoint": entrypoint,
            "startedAt": _utcNow(),
            "status": "starting",
            "outcome": "running",
            "pid": os.getpid(),
            "repoRoot": str(self.repoRoot),
            "buildDir": str(self.buildDir),
            "python": {"version": platform.python_version(), "executable": sys.executable},
            "platform": platform.platform(),
            "paths": {name: str(path) for name, path in self.paths.items()},
            "channels": {
                "runtime": {"status": "pending", "maxBytes": 4 * 1024 * 1024, "backups": 2},
                "native": {"status": "pending", "retention": "append for this run"},
                "gameplay": {"status": "pending", "maxMemoryEvents": 1000, "diskChunks": 2},
            },
            "environment": {
                key: _boundedValue(os.environ[key])
                for key in ("GAME_BUILD_CONFIG", "SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "SDL_RENDER_DRIVER")
                if key in os.environ
            },
        }

    def _warnOnce(self, channel, message):
        if channel in self._warnings:
            return
        self._warnings.add(channel)
        try:
            print(f"Debug diagnostics ({channel}): {message}", file=sys.stderr)
        except Exception:
            pass

    def _channelFailure(self, channel, message):
        self.manifest["channels"].setdefault(channel, {})["status"] = "unavailable"
        if channel == "runtime":
            for target_logger, handler in self._handlers:
                if isinstance(handler, _RuntimeHandler):
                    target_logger.removeHandler(handler)
        self._warnOnce(channel, message)
        self._writeManifest()

    def _writeManifest(self):
        if not self._prepared or self._closed:
            return
        try:
            with self._manifestLock:
                temporary_path = self.runDir / "manifest.json.tmp"
                content = json.dumps(self.manifest, indent=2, ensure_ascii=True) + "\n"
                temporary_path.write_text(content, encoding="utf-8")
                try:
                    temporary_path.replace(self.paths["manifest"])
                except PermissionError:
                    # Some Windows sandbox folders allow writes but deny file replacement.
                    self.paths["manifest"].write_text(content, encoding="utf-8")
                    try:
                        temporary_path.unlink()
                    except OSError:
                        pass
        except Exception:
            self._warnOnce("manifest", "Unable to update the run manifest")

    def updateManifest(self, **fields):
        try:
            with self._manifestLock:
                self.manifest.update(_boundedValue(fields))
            self._writeManifest()
        except Exception:
            self._warnOnce("manifest", "Unable to summarize diagnostic context")

    def _setEnvironment(self, key, value):
        if key not in self._savedEnv:
            self._savedEnv[key] = os.environ.get(key)
        os.environ[key] = value

    def prepare(self):
        if self._prepared or self._closed:
            return self
        self._setEnvironment("GAME_DEBUG", "1")
        if not self._explicitTrace:
            self._setEnvironment("GAME_PLAYTEST_TRACE", "1")
            self._setEnvironment("GAME_PLAYTEST_TRACE_FILE", "")
            self._setEnvironment("GAME_PLAYTEST_TRACE_RETAIN_RECENT", "1")
        try:
            self.runDir.mkdir(parents=True, exist_ok=False)
            self._prepared = True
        except Exception:
            self._warnOnce("startup", "Unable to create the debug bundle; continuing without file diagnostics")
            return self

        for name in ("native", "gameplay"):
            try:
                self.paths[name].touch(exist_ok=False)
                self._readyChannels.add(name)
            except Exception:
                self._channelFailure(name, f"Unable to create {name} diagnostics; continuing with other channels")

        try:
            quiet_handler = logging.NullHandler()
            logging.getLogger("game_diagnostics").addHandler(quiet_handler)
            self._handlers.append((logging.getLogger("game_diagnostics"), quiet_handler))
            handler = _RuntimeHandler(self)
            for name in _LOGGER_NAMES:
                target_logger = logging.getLogger(name)
                self._loggerLevels[name] = target_logger.level
                self._loggerPropagation[name] = target_logger.propagate
                target_logger.setLevel(logging.DEBUG)
                if name == "game_diagnostics":
                    target_logger.propagate = False
                target_logger.addHandler(handler)
                self._handlers.append((target_logger, handler))
            self.manifest["channels"]["runtime"]["status"] = "active"
        except Exception:
            self._channelFailure("runtime", "Unable to initialize runtime logging")

        if not self._explicitTrace and "gameplay" in self._readyChannels:
            self._setEnvironment("GAME_PLAYTEST_TRACE_FILE", str(self.paths["gameplay"]))
        self._installHooks()
        self.manifest["status"] = "running"
        self._collectContext()
        self._writeManifest()
        try:
            print(f"Debug logs: {self.runDir}", file=sys.stderr)
        except Exception:
            pass
        self.record("session_started", entrypoint=self.manifest["entrypoint"])
        return self

    def _collectContext(self):
        try:
            disk = shutil.disk_usage(self.buildDir if self.buildDir.exists() else self.repoRoot)
            self.manifest["disk"] = {"totalBytes": disk.total, "freeBytes": disk.free}
        except OSError:
            pass
        if (self.repoRoot / ".git").exists():
            git_context = {}
            for name, arguments in (
                ("head", ["rev-parse", "HEAD"]),
                ("branch", ["branch", "--show-current"]),
                ("dirty", ["status", "--porcelain", "--untracked-files=no"]),
            ):
                try:
                    result = subprocess.run(
                        ["git", "-C", str(self.repoRoot), *arguments],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        check=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    if result.returncode == 0:
                        git_context[name] = (
                            bool(result.stdout.strip()) if name == "dirty" else result.stdout.strip()[:160]
                        )
                except (OSError, subprocess.SubprocessError):
                    pass
            self.manifest["git"] = git_context

    def _installHooks(self):
        self._oldSysHook = sys.excepthook
        self._oldThreadHook = threading.excepthook

        def exceptionHook(error_type, error, trace):
            self.recordException("uncaught_exception", error, trace=trace)
            self._oldSysHook(error_type, error, trace)

        def threadExceptionHook(args):
            self.recordException("thread_exception", args.exc_value, trace=args.exc_traceback, thread=args.thread.name)
            self._oldThreadHook(args)

        self._sysHook = exceptionHook
        self._threadHook = threadExceptionHook
        sys.excepthook = exceptionHook
        threading.excepthook = threadExceptionHook

    def record(self, event, **fields):
        if not self._prepared or self._closed:
            return
        try:
            record = {"event": str(event)[:160], "runId": self.manifest["runId"], **_boundedValue(fields)}
            logging.getLogger("game_diagnostics").info("%s", json.dumps(record, ensure_ascii=True))
        except Exception:
            self._channelFailure("runtime", "Unable to record diagnostic event")

    def recordException(self, event, error, *, trace=None, **fields):
        if not self._prepared or self._closed:
            return
        try:
            trace = error.__traceback__ if trace is None else trace
            formatted = "".join(traceback.format_exception(type(error), error, trace, limit=20))
            if len(formatted) > 16384:
                formatted = formatted[-16384:] + "\n<traceback truncated>"
            summary = {"event": str(event)[:160], "errorType": type(error).__name__, **_boundedValue(fields)}
            logging.getLogger("game_diagnostics").error("%s\n%s", json.dumps(summary, ensure_ascii=True), formatted)
        except Exception:
            self._channelFailure("runtime", "Unable to record exception diagnostics")

    def applyNative(self, native_module, sink=None, path=None):
        if self._closed:
            return False
        sink = self.nativeSink if sink is None else sink
        if path is None and sink == "file":
            path = self.nativePath
        try:
            self.manifest["nativeModule"] = str(getattr(native_module, "__file__", "<unknown>"))
            if sink == "file":
                if path is None or (Path(path) == self.paths["native"] and "native" not in self._readyChannels):
                    raise OSError("Native debug file is unavailable")
                with Path(path).open("a", encoding="utf-8"):
                    pass
            native_module.set_logger_sink(sink, str(path) if path is not None else None)
            status = "disabled" if sink == "disabled" else "active"
            if sink == "file":
                native_logger = getattr(native_module, "logger", None)
                if callable(native_logger):
                    self._nativeAttempt += 1
                    marker = f"game-debug-native:{self.manifest['runId']}:{self._nativeAttempt}"
                    native_logger(marker)
                    with Path(path).open("rb") as output:
                        output.seek(0, os.SEEK_END)
                        output.seek(max(0, output.tell() - 8192))
                        if marker.encode("ascii") not in output.read(8192):
                            raise OSError("Native file sink did not receive its verification marker")
                else:
                    status = "unverified"
            self.nativeSink = sink
            self.nativePath = Path(path) if path is not None else None
            self.manifest["channels"]["native"].update(status=status, sink=sink, path=str(path) if path else None)
            self._writeManifest()
            return True
        except Exception:
            self._channelFailure("native", "Unable to configure native logs")
            try:
                native_module.set_logger_sink("stderr", None)
                self.nativeSink = "stderr"
                self.nativePath = None
                self.manifest["channels"]["native"].update(effectiveSink="stderr", path=None)
                self._writeManifest()
            except Exception:
                pass
            return False

    def configureTrace(self, native_module):
        if self._closed:
            return False
        try:
            enabled = bool(native_module.playtest_trace_enabled())
            channel = self.manifest["channels"]["gameplay"]
            if self._explicitTrace:
                channel.update(status="active" if enabled else "disabled", source="environment")
                target = os.environ.get("GAME_PLAYTEST_TRACE_FILE")
                trace_value = os.environ.get("GAME_PLAYTEST_TRACE", "")
                if target is None:
                    if trace_value.lower() in {"1", "true", "on", "enabled"}:
                        target = "stderr"
                    else:
                        target = trace_value
                channel["target"] = target
                channel["path"] = (
                    str(Path(target).resolve()) if target and target not in {"stdout", "stderr"} and enabled else None
                )
            else:
                configure = native_module.configure_playtest_trace
                supports_tail = "retain_recent" in (getattr(configure, "__doc__", "") or "")
                if not supports_tail:
                    try:
                        supports_tail = "retain_recent" in inspect.signature(configure).parameters
                    except (TypeError, ValueError):
                        pass
                if "gameplay" not in self._readyChannels:
                    channel.update(
                        status="memory_only" if enabled and supports_tail else "limited",
                        path=None,
                        retention="tail" if supports_tail else "head",
                    )
                    self._writeManifest()
                    return enabled
                channel.update(
                    status="active" if enabled and supports_tail else "limited",
                    source="debug_defaults",
                    retention="tail" if supports_tail else "head",
                    path=str(self.paths["gameplay"]),
                )
                if not enabled or not supports_tail:
                    self._warnOnce(
                        "gameplay", "Current native module does not provide recent gameplay history; rebuild it"
                    )
            self._writeManifest()
            return enabled
        except Exception:
            self._channelFailure("gameplay", "Unable to inspect gameplay tracing")
            return False

    def finish(self, status="complete", error=None):
        if self._finished or self._closed:
            return
        self._finished = True
        if error is not None:
            self.recordException("session_failed", error)
        self.record("session_finished", status=status)
        self.updateManifest(
            status=status,
            outcome="completed" if status == "complete" else status,
            finishedAt=_utcNow(),
            errorType=type(error).__name__ if error is not None else None,
        )

    def close(self):
        global _ACTIVE_SESSION
        if self._closed:
            return
        if not self._finished:
            self.finish()
        self._closed = True
        if sys.excepthook is self._sysHook:
            sys.excepthook = self._oldSysHook
        if threading.excepthook is self._threadHook:
            threading.excepthook = self._oldThreadHook
        for target_logger, handler in self._handlers:
            target_logger.removeHandler(handler)
        for handler in {handler for _, handler in self._handlers}:
            try:
                handler.close()
            except Exception:
                pass
        for name, level in self._loggerLevels.items():
            logging.getLogger(name).setLevel(level)
            logging.getLogger(name).propagate = self._loggerPropagation[name]
        for key, old_value in self._savedEnv.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
        if _ACTIVE_SESSION is self:
            _ACTIVE_SESSION = None


def startSession(*, repo_root, build_dir, entrypoint, debug=None, debug_dir=None):
    global _ACTIVE_SESSION
    if not debugEnabled(debug):
        return None
    if _ACTIVE_SESSION is not None:
        return _ACTIVE_SESSION
    try:
        session = DebugSession(repo_root, build_dir, entrypoint, debug_dir)
        _ACTIVE_SESSION = session
        return session.prepare()
    except Exception:
        if _ACTIVE_SESSION is not None:
            _ACTIVE_SESSION.close()
        try:
            print(
                "Debug diagnostics (startup): Unable to initialize diagnostics; continuing without them",
                file=sys.stderr,
            )
        except Exception:
            pass
        return None
