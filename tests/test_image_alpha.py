# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
"""Reviewed alpha-mask behavior and PNG provenance without starting the game."""

from collections import deque
import copy
import io
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImageAlphaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PIL import Image, PngImagePlugin
        except ImportError as exc:
            raise unittest.SkipTest(f"Pillow is required for image alpha-mask checks: {exc}")
        from scripts import prepare_image_alpha

        cls.Image = Image
        cls.PngImagePlugin = PngImagePlugin
        cls.tool = prepare_image_alpha

    def maskPolicy(self, **changes):
        policy = {"action": "mask", "background": [0, 0, 0], "tolerance": 0, "feather": 0}
        policy.update(changes)
        return policy

    def assertAlpha(self, image, expected):
        self.assertEqual(expected, list(image.getchannel("A").tobytes()))

    def referenceConnected(self, values, width, height, seeds=()):
        pending = deque(
            (x, y) for y in range(height) for x in range(width) if x in (0, width - 1) or y in (0, height - 1)
        )
        pending.extend(seeds)
        selected = set()
        while pending:
            x, y = pending.popleft()
            if not (0 <= x < width and 0 <= y < height) or not values[y * width + x] or (x, y) in selected:
                continue
            selected.add((x, y))
            pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
        return [255 if (x, y) in selected else 0 for y in range(height) for x in range(width)]

    def testFloodMatchesFourConnectedReferenceIncludingNarrowRows(self):
        rng = random.Random(1907)
        for width, height in ((1, 1), (1, 7), (7, 1), (2, 5), (5, 7), (9, 6)):
            for sample in range(25):
                with self.subTest(size=(width, height), sample=sample):
                    values = [255 if rng.randrange(3) else 0 for _ in range(width * height)]
                    candidate = self.Image.new("L", (width, height))
                    candidate.putdata(values)
                    before = candidate.tobytes()
                    actual = self.tool.connectedBorder(candidate)
                    self.assertEqual(self.referenceConnected(values, width, height), list(actual.tobytes()))
                    self.assertEqual(before, candidate.tobytes())

    def testFloodSeedsAllEdgesWithoutDiagonalConnections(self):
        candidate = self.Image.new("L", (7, 7))
        for point in ((3, 0), (6, 3), (3, 6), (0, 3), (1, 1), (2, 2), (3, 3)):
            candidate.putpixel(point, 255)
        actual = self.tool.connectedBorder(candidate)
        self.assertEqual(4, actual.tobytes().count(255))
        for point in ((3, 0), (6, 3), (3, 6), (0, 3)):
            self.assertEqual(255, actual.getpixel(point))
        self.assertEqual(0, actual.getpixel((3, 3)))

    def testFloodDoesNotCrossRowBoundariesOrFillNonCandidates(self):
        rows = ((0, 0, 0, 0, 255), (255, 0, 255, 255, 0), (0, 0, 0, 0, 255), (255, 0, 0, 0, 0))
        candidate = self.Image.new("L", (5, 4))
        candidate.putdata([value for row in rows for value in row])
        self.assertEqual(
            [0, 0, 0, 0, 255, 255, 0, 0, 0, 0, 0, 0, 0, 0, 255, 255, 0, 0, 0, 0],
            list(self.tool.connectedBorder(candidate).tobytes()),
        )

    def testMatchingForegroundEnclosedByOutlineStaysOpaque(self):
        source = self.Image.new("RGBA", (7, 7), (0, 0, 0, 255))
        for y in range(1, 6):
            for x in range(1, 6):
                if x in (1, 5) or y in (1, 5):
                    source.putpixel((x, y), (180, 70, 20, 255))
        result = self.tool.applyMask(source, self.maskPolicy())
        self.assertEqual(0, result.getpixel((0, 0))[3])
        self.assertEqual(255, result.getpixel((3, 3))[3])
        self.assertEqual(255, result.getpixel((1, 3))[3])
        self.assertEqual(source.convert("RGB").tobytes(), result.convert("RGB").tobytes())

    def testReviewedHoleSeedRemovesOnlyItsEnclosedBackground(self):
        source = self.Image.new("RGBA", (7, 5), (200, 40, 20, 255))
        for point in ((2, 2), (3, 2), (5, 2), (0, 0)):
            source.putpixel(point, (0, 0, 0, 255))
        result = self.tool.applyMask(source, self.maskPolicy(seeds=[[2, 2]]))
        self.assertEqual(0, result.getpixel((2, 2))[3])
        self.assertEqual(0, result.getpixel((3, 2))[3])
        self.assertEqual(0, result.getpixel((0, 0))[3])
        self.assertEqual(255, result.getpixel((5, 2))[3])
        self.assertEqual(255, result.getpixel((4, 2))[3])

    def testNoisyBackgroundAndDifferentCornersUseReviewedColorTolerance(self):
        source = self.Image.new("RGBA", (5, 5))
        source.putdata([(20 + index % 4, 18 + index % 5, 19 + index % 3, 255) for index in range(25)])
        source.putpixel((2, 2), (190, 50, 30, 255))
        result = self.tool.applyMask(source, self.maskPolicy(background=[20, 20, 20], tolerance=4))
        self.assertAlpha(result, [255 if index == 12 else 0 for index in range(25)])

    def testColorDistancePreservesDarkOutlineAndLightForeground(self):
        source = self.Image.new("RGBA", (5, 1))
        source.putdata(
            [(150, 150, 150, 255), (10, 10, 10, 255), (220, 220, 220, 255), (150, 150, 180, 255), (165, 165, 165, 255)]
        )
        result = self.tool.applyMask(source, self.maskPolicy(background=[150, 150, 150], tolerance=10, feather=15))
        self.assertAlpha(result, [0, 255, 255, 255, 85])

    def testExistingPartialAlphaNeverIncreasesAndRgbNeverChanges(self):
        source = self.Image.new("RGBA", (4, 2))
        source.putdata(
            [
                (0, 0, 0, 0),
                (0, 0, 0, 120),
                (5, 5, 5, 230),
                (10, 10, 10, 50),
                (200, 20, 30, 90),
                (255, 255, 255, 0),
                (15, 15, 15, 180),
                (20, 20, 20, 200),
            ]
        )
        before = source.tobytes()
        result = self.tool.applyMask(source, self.maskPolicy(feather=20))
        self.assertEqual(source.size, result.size)
        self.assertEqual(source.convert("RGB").tobytes(), result.convert("RGB").tobytes())
        self.assertAlpha(result, [0, 0, 64, 50, 90, 0, 180, 200])
        self.assertTrue(
            all(
                after <= before
                for before, after in zip(source.getchannel("A").tobytes(), result.getchannel("A").tobytes())
            )
        )
        self.assertEqual(before, source.tobytes())

    def testProtectedRectangleRetainsForegroundMatchingBackground(self):
        source = self.Image.new("RGBA", (6, 5), (0, 0, 0, 255))
        result = self.tool.applyMask(source, self.maskPolicy(protect=[[1, 1, 3, 4]]))
        self.assertAlpha(result, [255 if 1 <= x < 3 and 1 <= y < 4 else 0 for y in range(5) for x in range(6)])

    def testOpeningBlocksNarrowBackgroundRouteIntoForegroundInterior(self):
        source = self.Image.new("RGBA", (11, 11), (0, 0, 0, 255))
        for y in range(3, 8):
            for x in range(3, 8):
                if x in (3, 7) or y in (3, 7):
                    source.putpixel((x, y), (180, 70, 20, 255))
        source.putpixel((5, 3), (0, 0, 0, 255))
        unprotected = self.tool.applyMask(source, self.maskPolicy())
        protected = self.tool.applyMask(source, self.maskPolicy(opening=1))
        self.assertEqual(0, unprotected.getpixel((5, 5))[3])
        self.assertEqual(255, protected.getpixel((5, 5))[3])
        self.assertEqual(0, protected.getpixel((0, 0))[3])
        self.assertEqual(source.convert("RGB").tobytes(), protected.convert("RGB").tobytes())

    def testPreservedArtworkKeepsAllChannels(self):
        source = self.Image.new("RGBA", (2, 1))
        source.putdata([(0, 0, 0, 255), (50, 120, 200, 60)])
        result = self.tool.applyMask(source, {"action": "preserve"})
        self.assertEqual(source.tobytes(), result.tobytes())

    def testInvalidPoliciesRefuseOutOfRangeValuesAndCoordinates(self):
        source = self.Image.new("RGBA", (5, 4))
        cases = (
            {"action": "unrecognized"},
            {"background": [0, 0]},
            {"background": [-1, 0, 0]},
            {"background": [0, 256, 0]},
            {"tolerance": -1},
            {"tolerance": 256},
            {"feather": -1},
            {"feather": 256},
            {"opening": -1},
            {"opening": 17},
            {"seeds": [[5, 0]]},
            {"seeds": [[0, -1]]},
            {"protect": [[0, 0, 6, 4]]},
            {"protect": [[2, 1, 2, 3]]},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.tool.applyMask(source, self.maskPolicy(**changes))

    def pngBytes(self, image):
        output = io.BytesIO()
        image.save(output, format="PNG", compress_level=9)
        return output.getvalue()

    def makeFixture(self, root):
        image = self.Image.new("RGBA", (5, 4), (0, 0, 0, 255))
        image.putpixel((2, 2), (180, 60, 20, 255))
        policy = self.maskPolicy()
        original = self.pngBytes(image)
        result = self.pngBytes(self.tool.applyMask(image, policy))
        path = root / "res/images/sample.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(original)
        review = {
            "images": [
                {
                    "path": "sample.png",
                    "policy": policy,
                    "size": [5, 4],
                    "sourceSha256": self.tool.digest(original),
                    "resultSha256": self.tool.digest(result),
                    "rgbSha256": self.tool.digest(image.convert("RGB").tobytes()),
                }
            ]
        }
        return path, original, result, review

    def testApplyChecksReviewedOutputAndIsIdempotent(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            path, original, result, review = self.makeFixture(root)
            self.assertNotEqual(original, result)
            self.assertEqual(1, self.tool.processImages(root, review, apply=True))
            self.assertEqual(result, path.read_bytes())
            self.assertEqual(0, self.tool.processImages(root, review, apply=True))
            self.assertEqual(0, self.tool.processImages(root, review))

    def testMaskApplicationPreservesAuthorshipTextAndInternationalXmp(self):
        metadata = self.PngImagePlugin.PngInfo()
        text_values = {
            "Author": "Andrzej Lis",
            "Description": "Reviewed game artwork with an alpha mask",
            "Creation Time": "2026-10-20T12:34:56+02:00",
        }
        for key, value in text_values.items():
            metadata.add_text(key, value)
        xmp_key = "XML:com.adobe.xmp"
        xmp_value = '<x:xmpmeta xmlns:x="adobe:ns:meta/">Zażółć gęślą jaźń</x:xmpmeta>'
        metadata.add_itxt(xmp_key, xmp_value, lang="pl-PL", tkey="Metadane XMP", zip=True)
        source = self.Image.new("RGBA", (5, 4), (0, 0, 0, 255))
        source.putpixel((2, 2), (180, 60, 20, 192))
        output = io.BytesIO()
        source.save(output, format="PNG", pnginfo=metadata)
        original = output.getvalue()
        with self.Image.open(io.BytesIO(original)) as source:
            source.load()
            masked = self.tool.applyMask(source, self.maskPolicy())
            encoded = self.tool.encodePng(masked, source)
            rgb_hash = self.tool.digest(source.convert("RGB").tobytes())
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            path = root / "res/images/metadata.png"
            path.parent.mkdir(parents=True)
            path.write_bytes(original)
            review = {
                "images": [
                    {
                        "path": "metadata.png",
                        "policy": self.maskPolicy(),
                        "size": [5, 4],
                        "sourceSha256": self.tool.digest(original),
                        "resultSha256": self.tool.digest(encoded),
                        "rgbSha256": rgb_hash,
                    }
                ]
            }
            self.assertEqual(1, self.tool.processImages(root, review, apply=True))
            with self.Image.open(path) as result:
                result.load()
                self.assertEqual(masked.tobytes(), result.tobytes())
                for key, value in text_values.items():
                    self.assertEqual(value, result.text[key])
                self.assertEqual(xmp_value, result.text[xmp_key])
                self.assertIsInstance(result.text[xmp_key], self.PngImagePlugin.iTXt)
                self.assertEqual("pl-PL", result.text[xmp_key].lang)
                self.assertEqual("Metadane XMP", result.text[xmp_key].tkey)

    def testPngEncodingPreservesColorResolutionAndExifMetadata(self):
        metadata = self.PngImagePlugin.PngInfo()
        metadata.add(b"gAMA", struct.pack(">I", 45455))
        metadata.add(b"sRGB", b"\x00")
        metadata.add(b"cHRM", struct.pack(">8I", 31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000))
        exif = self.Image.Exif()
        exif[0x010E] = "Alpha-mask metadata regression fixture"
        exif[0x013B] = "Andrzej Lis"
        image = self.Image.new("RGBA", (3, 2), (0, 0, 0, 255))
        image.putpixel((1, 1), (100, 50, 20, 90))
        output = io.BytesIO()
        image.save(output, format="PNG", pnginfo=metadata, dpi=(96, 144), exif=exif)
        with self.Image.open(io.BytesIO(output.getvalue())) as original:
            original.load()
            masked = self.tool.applyMask(original, self.maskPolicy())
            encoded = self.tool.encodePng(masked, original)
            with self.Image.open(io.BytesIO(encoded)) as result:
                result.load()
                self.assertEqual(masked.tobytes(), result.tobytes())
                self.assertEqual(original.convert("RGB").tobytes(), result.convert("RGB").tobytes())
                self.assertEqual(0, result.getpixel((0, 0))[3])
                self.assertEqual(90, result.getpixel((1, 1))[3])
                for name in ("gamma", "srgb", "chromaticity", "dpi", "exif"):
                    self.assertEqual(original.info[name], result.info[name], name)
                self.assertEqual(dict(original.getexif()), dict(result.getexif()))

    def testReadOnlyCheckRefusesUnappliedSourceWithoutWriting(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            path, original, _, review = self.makeFixture(root)
            with self.assertRaisesRegex(ValueError, "unreviewed input"):
                self.tool.processImages(root, review)
            self.assertEqual(original, path.read_bytes())

    def testApplyRefusesSourceHashMismatchWithoutWriting(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            path, _, _, review = self.makeFixture(root)
            changed = self.pngBytes(self.Image.new("RGBA", (5, 4), (20, 40, 60, 255)))
            path.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "unreviewed input"):
                self.tool.processImages(root, review, apply=True)
            self.assertEqual(changed, path.read_bytes())

    def testApplyRefusesUnreviewedMaskOutputWithoutWriting(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            path, original, _, review = self.makeFixture(root)
            review["images"][0]["resultSha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "differs from the reviewed preview"):
                self.tool.processImages(root, review, apply=True)
            self.assertEqual(original, path.read_bytes())

    def testReviewMustListEveryImageExactlyOnce(self):
        for mode in ("missing", "duplicate", "extra"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                path, original, _, review = self.makeFixture(root)
                if mode == "missing":
                    review["images"] = []
                else:
                    review["images"].append(copy.deepcopy(review["images"][0]))
                    if mode == "extra":
                        review["images"][-1]["path"] = "missing.png"
                with self.assertRaisesRegex(ValueError, "every PNG must have exactly one review entry"):
                    self.tool.processImages(root, review, apply=True)
                self.assertEqual(original, path.read_bytes())

    def testEveryRealAssetMatchesItsReviewedDimensionsRgbAndResultHash(self):
        review = json.loads((ROOT / "docs/image-alpha-review.json").read_text(encoding="utf-8"))
        assets = {path.relative_to(ROOT / "res/images").as_posix() for path in (ROOT / "res/images").rglob("*.png")}
        self.assertEqual(192, len(assets))
        self.assertEqual(192, len(review["images"]))
        self.assertEqual(assets, {entry["path"] for entry in review["images"]})
        self.assertEqual(0, self.tool.processImages(ROOT, review))
        for entry in review["images"]:
            with self.subTest(path=entry["path"]):
                self.assertIn(entry["policy"]["action"], ("mask", "preserve"))
                self.assertTrue(entry["policy"]["reason"].strip())
                for name in ("sourceSha256", "resultSha256", "rgbSha256"):
                    self.assertRegex(entry[name], r"^[0-9a-f]{64}$")
                path = ROOT / "res/images" / entry["path"]
                if entry["policy"]["action"] == "preserve":
                    self.assertEqual(entry["sourceSha256"], entry["resultSha256"])
                else:
                    self.assertNotEqual(entry["sourceSha256"], entry["resultSha256"])
                    with self.Image.open(path) as image:
                        histogram = image.getchannel("A").histogram()
                        self.assertGreater(histogram[0], 0, "masked image must contain transparent background")
                        self.assertGreater(histogram[255], 0, "masked image must retain opaque foreground")
                        self.assertEqual(entry["transparentPixels"], histogram[0])
                        self.assertEqual(entry["partialPixels"], sum(histogram[1:255]))


if __name__ == "__main__":
    unittest.main()
