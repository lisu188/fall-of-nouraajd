#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise native binding exception translation with flushed progress markers."""

import importlib
import os
from pathlib import Path
import sys


def runChecks(game, repetitions=32, output=None):
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    output = sys.stdout if output is None else output

    def report(message):
        print(f"binding exception preflight: {message}", file=output, flush=True)

    def expectError(label, error_type, operation):
        for attempt in range(1, repetitions + 1):
            report(f"{label} {attempt}/{repetitions}: calling")
            try:
                operation()
            except error_type as error:
                report(f"{label} {attempt}/{repetitions}: caught {type(error).__name__}: {error}")
            else:
                raise AssertionError(f"{label} did not raise {error_type.__name__}")

    game_instance = None
    try:
        expectError("jsonify({})", TypeError, lambda: game.jsonify({}))
        expectError("invalid logger sink", ValueError, lambda: game.set_logger_sink("unit-test-invalid-sink", None))
        expectError("file logger without path", ValueError, lambda: game.set_logger_sink("file", None))
        report("loadGame: calling")
        game_instance = game.CGameLoader.loadGame()
        report("createObject(CGameObject): calling")
        obj = game_instance.createObject("CGameObject")
        expectError("unsupported list property", TypeError, lambda: setattr(obj, "unsupported_dynamic_value", []))
    finally:
        try:
            if game_instance is not None:
                report("context shutdown: calling")
                game_instance.getContext().shutdown()
                report("context shutdown: complete")
        finally:
            report("disable logger: calling")
            game.set_logger_sink("disabled", None)
    report("complete")


def main():
    root = Path(__file__).resolve().parents[1]
    default_build = "cmake-build-clangcl20-release" if os.name == "nt" else "cmake-build-gcc15-release"
    build_dir = (root / os.environ.get("GAME_BUILD_DIR", default_build)).resolve()
    build_config = os.environ.get("GAME_BUILD_CONFIG", "Release")
    for path in reversed((build_dir / build_config, build_dir, root / "res", root)):
        sys.path.insert(0, str(path))
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    os.environ.setdefault("SDL_RENDER_DRIVER", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    os.chdir(build_dir)
    print("binding exception preflight: import game: calling", flush=True)
    runChecks(importlib.import_module("game"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
