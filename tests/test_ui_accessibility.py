"""Checks for the shared palette and bundled font assets; no game window is created."""

import re
import unittest
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]


def luminance(color):
    channels = [value / 255.0 for value in color]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear))


class UiAccessibilityTest(unittest.TestCase):
    def testSharedTextColorsMeetBodyContrast(self):
        source = (ROOT / "src/gui/CUiTheme.h").read_text(encoding="utf-8")
        palette = {
            name: tuple(int(channel) for channel in channels)
            for name, *channels in re.findall(r"SDL_Color (\w+)\{(\d+), (\d+), (\d+), 255\}", source)
        }
        for foreground in ("Text", "Muted", "Accent", "Danger", "Success"):
            for background in ("Background", "Panel", "Selection"):
                with self.subTest(foreground=foreground, background=background):
                    ratio = (luminance(palette[foreground]) + 0.05) / (luminance(palette[background]) + 0.05)
                    self.assertGreaterEqual(ratio, 4.5)

    def testBundledSmallestFontHasReadableGlyphHeight(self):
        # XAG 101 measures the visible ascender-to-descender body, not the nominal font size.
        source = (ROOT / "src/gui/CTextManager.cpp").read_text(encoding="utf-8")
        size = int(re.search(r'role == "small"\s*\?\s*(\d+)', source).group(1))
        for display_scale in (1, 2):
            font = ImageFont.truetype(str(ROOT / "res/fonts/SourceSans3-Regular.ttf"), size * display_scale)
            bounds = font.getbbox("Agpq")
            self.assertGreaterEqual(bounds[3] - bounds[1], 18 * display_scale)
        for license_name in ("SourceSans-LICENSE.md", "SourceSerif-LICENSE.md"):
            self.assertIn("SIL OPEN FONT LICENSE", (ROOT / "res/fonts" / license_name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
