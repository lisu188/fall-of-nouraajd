# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in screenshot-helper profile; extracts source functions without importing the game."""

import argparse
import ast
import json
from pathlib import Path
import platform
import statistics
import sys
import time

from PIL import __version__ as PILLOW_VERSION
from PIL import Image, ImageChops  # Warm imports before measuring either source version.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "test.py")
    args = parser.parse_args()
    path = args.source.resolve()
    names = {"rect_right", "rect_bottom", "rect_contains_point", "panel_pixel_summary", "pixel_diff_bounds"}
    source = ast.parse(path.read_text(encoding="utf-8"))
    tree = ast.Module(
        body=[node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names],
        type_ignores=[],
    )
    helpers = {}
    exec(compile(tree, str(path), "exec"), helpers)
    width, height = 1920, 1080
    before = bytes((17, 19, 23, 255)) * (width * height)
    after = bytes((17, 20, 23, 0)) * (width * height)
    operations = (
        (
            "panel_pixel_summary",
            (
                before,
                width,
                height,
                (20, 30, 1880, 1020),
                {"clipped": (-10, -20, 970, 560), "tail": (1900, 1070, 40, 40)},
            ),
        ),
        ("pixel_diff_bounds", (before, after, width, (0, 0, width, height))),
    )
    print(json.dumps({"platform": platform.platform(), "python": platform.python_version(), "pillow": PILLOW_VERSION}))
    for name, arguments in operations:
        operation = helpers[name]
        operation(*arguments)
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            result = operation(*arguments)
            samples.append(time.perf_counter() - started)
        lines = 0

        def trace(frame, event, arg):
            nonlocal lines
            if event == "line" and frame.f_code.co_filename == str(path):
                lines += 1
                if lines > 2000:
                    raise RuntimeError("Python-work observation stopped after 2000 helper line events")
            return trace

        previous_trace = sys.gettrace()
        try:
            sys.settrace(trace)
            operation(*arguments)
        except RuntimeError:
            if lines <= 2000:
                raise
        finally:
            sys.settrace(previous_trace)
        print(
            json.dumps(
                {
                    "helper": name,
                    "pixels": width * height,
                    "warmup": 1,
                    "samples": samples,
                    "medianSeconds": statistics.median(samples),
                    "pythonLines": lines if lines <= 2000 else ">2000",
                    "result": result,
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
