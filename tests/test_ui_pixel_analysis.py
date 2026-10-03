# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
"""Pixel-analysis parity and bounded Python work without starting the game."""

import ast
from pathlib import Path
import random
import sys
import unittest


def loadPixelHelpers():
    path = Path(__file__).resolve().parents[1] / "test.py"
    names = {"rect_right", "rect_bottom", "rect_contains_point", "panel_pixel_summary", "pixel_diff_bounds"}
    source = ast.parse(path.read_text(encoding="utf-8"))
    tree = ast.Module(
        body=[node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names],
        type_ignores=[],
    )
    namespace = {}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace


def referenceSummary(data, width, height, panel, regions):
    points = {
        (x, y) for y in range(height) for x in range(width) if any(data[(y * width + x) * 4 : (y * width + x) * 4 + 3])
    }

    def count(rect):
        return sum(rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3] for x, y in points)

    bounds = None
    if points:
        left, top = min(x for x, y in points), min(y for x, y in points)
        bounds = [left, top, max(x for x, y in points) - left + 1, max(y for x, y in points) - top + 1]
    inside = count(panel)
    return {
        "inside": inside,
        "outside": len(points) - inside,
        "tightBounds": bounds,
        "regions": {name: count(rect) for name, rect in regions.items()},
    }


def referenceDiff(before, after, width, rect):
    points = []
    for y in range(rect[1], rect[1] + rect[3]):
        for x in range(rect[0], rect[0] + rect[2]):
            offset = (y * width + x) * 4
            if before[offset : offset + 3] != after[offset : offset + 3]:
                points.append((x, y))
    if not points:
        return None, 0
    left, top = min(x for x, y in points), min(y for x, y in points)
    return (left, top, max(x for x, y in points) - left + 1, max(y for x, y in points) - top + 1), len(points)


class UiPixelAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import PIL.Image
            import PIL.ImageChops
        except ImportError as exc:
            raise unittest.SkipTest(f"Pillow is required for screenshot pixel analysis: {exc}")
        cls.helpers = loadPixelHelpers()

    def testSummaryMatchesOracleForClippedOverlappingAndEmptyRegions(self):
        rng = random.Random(871)
        width, height = 9, 7
        data = bytes(channel for _ in range(width * height) for channel in [rng.randrange(3) for _ in range(4)])
        regions = {
            "clipped": (-4, -3, 7, 6),
            "overlap": (1, 1, 5, 4),
            "right": (7, 5, 20, 20),
            "outside": (-5, -5, 2, 2),
            "empty": (3, 2, 0, 4),
            "negative": (4, 3, -2, 1),
        }
        for panel in ((0, 0, width, height), (-2, -1, 5, 4), (4, 5, 12, 9), (1, 1, 0, 0)):
            with self.subTest(panel=panel):
                self.assertEqual(
                    referenceSummary(data, width, height, panel, regions),
                    self.helpers["panel_pixel_summary"](data, width, height, panel, regions),
                )

    def testSummaryCountsRgbEvenWhenTransparentAndIgnoresAlphaOnlyPixels(self):
        width, height = 4, 3
        data = bytearray(bytes((0, 0, 0, 255)) * (width * height))
        for index, rgb in ((5, (1, 0, 0)), (6, (0, 1, 0)), (9, (0, 0, 1))):
            data[index * 4 : index * 4 + 4] = bytes((*rgb, 0))
        summary = self.helpers["panel_pixel_summary"](bytes(data), width, height, (1, 1, 1, 1))
        self.assertEqual({"inside": 1, "outside": 2, "tightBounds": [1, 1, 2, 2], "regions": {}}, summary)
        self.assertEqual(
            {"inside": 0, "outside": 0, "tightBounds": None, "regions": {}},
            self.helpers["panel_pixel_summary"](bytes((0, 0, 0, 255)) * 12, width, height, (0, 0, 4, 3)),
        )
        for width, height in ((0, 3), (4, 0), (0, 0)):
            self.assertEqual(
                {"inside": 0, "outside": 0, "tightBounds": None, "regions": {"empty": 0}},
                self.helpers["panel_pixel_summary"](b"", width, height, (0, 0, 4, 3), {"empty": (0, 0, 4, 3)}),
            )

    def testDiffMatchesOracleForRgbChangesAlphaOnlyChangesAndEmptyRegions(self):
        width, height = 8, 6
        rng = random.Random(173)
        before = bytes(rng.randrange(256) for _ in range(width * height * 4))
        after = bytearray(before)
        for index in range(width * height):
            after[index * 4 + 3] ^= 255
        for index, channel in ((0, 0), (10, 1), (19, 2), (37, 0), (47, 2)):
            after[index * 4 + channel] ^= 255
        after = bytes(after)
        for rect in ((0, 0, 8, 6), (1, 1, 5, 4), (3, 3, 2, 1), (0, 0, 0, 6), (2, 3, -1, 2)):
            with self.subTest(rect=rect):
                self.assertEqual(
                    referenceDiff(before, after, width, rect),
                    self.helpers["pixel_diff_bounds"](before, after, width, rect),
                )
        self.assertEqual((None, 0), self.helpers["pixel_diff_bounds"](before, before, width, (0, 0, 8, 6)))
        transparent = bytes((0, 0, 1, 0)) * 48
        opaque = bytes((0, 0, 1, 255)) * 48
        self.assertEqual((None, 0), self.helpers["pixel_diff_bounds"](transparent, opaque, width, (0, 0, 8, 6)))
        self.assertEqual(
            ((0, 0, 8, 6), 48),
            self.helpers["pixel_diff_bounds"](bytes(8 * 6 * 4), transparent, width, (0, 0, 8, 6)),
        )

    def testFullHdAnalysisHasBoundedPythonWorkAndExactCounts(self):
        width, height = 1920, 1080
        before = bytes((17, 19, 23, 255)) * (width * height)
        after = bytes((17, 20, 23, 0)) * (width * height)
        panel = (20, 30, 1880, 1020)
        regions = {"clipped": (-10, -20, 970, 560), "tail": (1900, 1070, 40, 40)}
        operations = (
            (
                "panel_pixel_summary",
                (before, width, height, panel, regions),
                {
                    "inside": 1880 * 1020,
                    "outside": width * height - 1880 * 1020,
                    "tightBounds": [0, 0, width, height],
                    "regions": {"clipped": 960 * 540, "tail": 20 * 10},
                },
            ),
            (
                "pixel_diff_bounds",
                (before, after, width, (0, 0, width, height)),
                ((0, 0, width, height), width * height),
            ),
        )
        for name, args, expected in operations:
            with self.subTest(helper=name):
                lines = 0
                helper_source = str(Path(__file__).resolve().parents[1] / "test.py")

                def trace(frame, event, arg):
                    nonlocal lines
                    if event == "line" and frame.f_code.co_filename == helper_source:
                        lines += 1
                        if lines > 2000:
                            raise AssertionError(f"{name} exceeded 2000 Python lines for one fixed Full HD frame")
                    return trace

                previous_trace = sys.gettrace()
                try:
                    sys.settrace(trace)
                    actual = self.helpers[name](*args)
                finally:
                    sys.settrace(previous_trace)
                self.assertEqual(expected, actual)
                self.assertLessEqual(lines, 2000)


if __name__ == "__main__":
    unittest.main()
