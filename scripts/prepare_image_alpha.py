#!/usr/bin/env python3
"""Apply reviewed PNG alpha masks and optional, separately reviewed downsampling.

Pillow is an authoring/test dependency only. Runtime loading needs no new code.
The review manifest deliberately lists every image, including preserved artwork.
"""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile

from PIL import Image, ImageChops, ImageFilter, PngImagePlugin

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = REPO_ROOT / "docs" / "image-alpha-review.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def metadataDigest(image: Image.Image) -> str:
    encoded = json.dumps(
        image.info, sort_keys=True, default=lambda value: value.hex() if isinstance(value, bytes) else str(value)
    ).encode("utf-8")
    return digest(encoded)


def encodePng(image: Image.Image, original: Image.Image) -> bytes:
    """Keep authorship/XMP, color information, resolution and EXIF with the art."""
    metadata = PngImagePlugin.PngInfo()
    for key, value in getattr(original, "text", {}).items():
        if isinstance(value, PngImagePlugin.iTXt):
            metadata.add_itxt(key, value, lang=value.lang, tkey=value.tkey)
        else:
            metadata.add_text(key, value)
    if "gamma" in original.info:
        metadata.add(b"gAMA", struct.pack(">I", round(original.info["gamma"] * 100000)))
    if "srgb" in original.info:
        metadata.add(b"sRGB", bytes([original.info["srgb"]]))
    if "chromaticity" in original.info:
        metadata.add(b"cHRM", struct.pack(">8I", *(round(value * 100000) for value in original.info["chromaticity"])))
    options = {key: original.info[key] for key in ("icc_profile", "dpi", "exif") if key in original.info}
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9, pnginfo=metadata, **options)
    return output.getvalue()


def connectedBorder(candidate: Image.Image, seeds: list[list[int]] = ()) -> Image.Image:
    """Find four-connected candidate runs reached from an edge or reviewed hole."""
    width, height = candidate.size
    available = bytearray(candidate.tobytes())
    selected = bytearray(width * height)
    pending = deque()
    for y in range(height):
        for x in (0, width - 1):
            if available[y * width + x]:
                pending.append((x, y))
    for x in range(width):
        for y in (0, height - 1):
            if available[y * width + x]:
                pending.append((x, y))
    for x, y in seeds:
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError("mask seed is outside the image")
        pending.append((x, y))

    while pending:
        x, y = pending.pop()
        row = y * width
        if not available[row + x]:
            continue
        left = max(row, available.rfind(b"\x00", row, row + x) + 1)
        right = available.find(b"\x00", row + x, row + width)
        if right < 0:
            right = row + width
        available[left:right] = b"\x00" * (right - left)
        selected[left:right] = b"\xff" * (right - left)
        for neighbor_y in (y - 1, y + 1):
            if not 0 <= neighbor_y < height:
                continue
            offset = (neighbor_y - y) * width
            start, stop = left + offset, right + offset
            while start < stop:
                start = available.find(b"\xff", start, stop)
                if start < 0:
                    break
                pending.append((start % width, neighbor_y))
                end = available.find(b"\x00", start, stop)
                start = stop if end < 0 else end
    return Image.frombytes("L", candidate.size, bytes(selected))


def applyMask(source: Image.Image, policy: dict) -> Image.Image:
    image = source.convert("RGBA")
    if policy["action"] not in {"mask", "preserve"}:
        raise ValueError("unknown alpha review action")
    if policy["action"] == "preserve":
        return image
    tolerance = policy["tolerance"]
    feather = policy.get("feather", 0)
    background = policy["background"]
    if len(background) != 3 or not all(0 <= value <= 255 for value in background):
        raise ValueError("background must contain three RGB bytes")
    if not 0 <= tolerance <= 255 or not 0 <= feather <= 255:
        raise ValueError("mask tolerance and feather must be between 0 and 255")
    channels = image.convert("RGB").split()
    differences = [
        channel.point([abs(value - color) for value in range(256)]) for channel, color in zip(channels, background)
    ]
    distance = ImageChops.lighter(ImageChops.lighter(differences[0], differences[1]), differences[2])
    candidate = distance.point([255 if value <= tolerance + feather else 0 for value in range(256)])
    # Opening removes narrow routes through dark outlines/mortar into an interior.
    opening = policy.get("opening", 0)
    if opening:
        if not 1 <= opening <= 16:
            raise ValueError("opening radius must be between 1 and 16")
        size = 2 * opening + 1
        candidate = candidate.filter(ImageFilter.MinFilter(size)).filter(ImageFilter.MaxFilter(size))
    for rectangle in policy.get("protect", []):
        x0, y0, x1, y1 = rectangle
        if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
            raise ValueError("protected rectangle is outside the image")
        candidate.paste(0, rectangle)
    connected = connectedBorder(candidate, policy.get("seeds", []))
    alpha_values = [
        0 if value <= tolerance else min(255, round(255 * (value - tolerance) / max(1, feather)))
        for value in range(256)
    ]
    matte = distance.point(alpha_values)
    alpha = Image.composite(matte, Image.new("L", image.size, 255), connected)
    image.putalpha(ImageChops.darker(image.getchannel("A"), alpha))
    return image


def finalReview(entry: dict) -> dict:
    return entry.get("resize", entry)


def resizeImage(source: Image.Image, review: dict) -> Image.Image:
    size = review["size"]
    if (
        review.get("resample") != "lanczos"
        or len(size) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in size)
        or any(target > original for target, original in zip(size, source.size))
        or size[0] * source.height != size[1] * source.width
    ):
        raise ValueError("resize must use Lanczos and preserve the aspect ratio without enlarging the image")
    # Pillow resamples RGBA through premultiplied RGBa, avoiding transparent RGB fringes.
    return source.convert("RGBA").resize(tuple(size), Image.Resampling.LANCZOS)


def verifyBytes(data: bytes, entry: dict, result_review: dict) -> None:
    if digest(data) != result_review["resultSha256"]:
        raise ValueError(f"{entry['path']}: image differs from the reviewed result")
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if list(image.size) != result_review["size"] or image.format != "PNG":
            raise ValueError(f"{entry['path']}: PNG format or dimensions changed")
        if digest(image.convert("RGB").tobytes()) != result_review["rgbSha256"]:
            raise ValueError(f"{entry['path']}: RGB artwork changed")
        if "metadataSha256" in entry and metadataDigest(image) != entry["metadataSha256"]:
            raise ValueError(f"{entry['path']}: PNG metadata changed")
        if "rgbaSha256" in result_review and digest(image.convert("RGBA").tobytes()) != result_review["rgbaSha256"]:
            raise ValueError(f"{entry['path']}: reviewed alpha mask changed")
        if entry["policy"]["action"] == "mask" and image.getchannel("A").getextrema()[0] != 0:
            raise ValueError(f"{entry['path']}: cutout has no transparent background")


def verifyImage(path: Path, entry: dict) -> None:
    verifyBytes(path.read_bytes(), entry, finalReview(entry))


def processImages(root: Path, review: dict, apply: bool = False) -> int:
    images_root = (root / "res/images").resolve()
    expected = {entry["path"] for entry in review["images"]}
    actual = {path.relative_to(images_root).as_posix() for path in images_root.rglob("*.png")}
    if expected != actual or len(expected) != len(review["images"]):
        raise ValueError("every PNG must have exactly one review entry")
    changed = 0
    for entry in review["images"]:
        path = images_root / entry["path"]
        if path.is_symlink() or not path.resolve().is_relative_to(images_root):
            raise ValueError("review path escapes the images directory")
        current = path.read_bytes()
        current_hash = digest(current)
        final_review = finalReview(entry)
        if current_hash != final_review["resultSha256"]:
            if not apply or current_hash not in {entry["sourceSha256"], entry["resultSha256"]}:
                raise ValueError(f"{entry['path']}: unreviewed input; refusing to overwrite")
            encoded = current
            if current_hash != entry["resultSha256"]:
                with Image.open(io.BytesIO(current)) as image:
                    result = applyMask(image, entry["policy"])
                    encoded = encodePng(result, image)
                if digest(encoded) != entry["resultSha256"]:
                    raise ValueError(
                        f"{entry['path']}: mask output differs from the reviewed preview; "
                        "check the authoring encoder versions recorded in the review"
                    )
            verifyBytes(encoded, entry, entry)
            if "resize" in entry:
                with Image.open(io.BytesIO(encoded)) as image:
                    result = resizeImage(image, final_review)
                    encoded = encodePng(result, image)
            verifyBytes(encoded, entry, final_review)
            # Atomic replacement, one image at a time; no duplicate asset tree.
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(encoded)
                os.replace(temporary, path)
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
            changed += 1
        verifyImage(path, entry)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--apply", action="store_true", help="apply reviewed masks/resizes; otherwise check without writing"
    )
    args = parser.parse_args()
    review = json.loads(args.review.read_text(encoding="utf-8"))
    changed = processImages(args.repo_root, review, apply=args.apply)
    print(
        f"Reviewed {len(review['images'])} images; changed {changed}; all final pixels, metadata and dimensions verified."
    )


if __name__ == "__main__":
    main()
