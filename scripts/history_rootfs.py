#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Materialize a verified Docker-save image and run it with an installed bwrap.

The image archive remains the source of truth. Materialization verifies the image
config and every uncompressed layer before applying it; no Docker daemon is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

METADATA = ".history-rootfs.json"
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
CONTROLLER = "/opt/recovery/controller/bin/python3.12"


class RootfsError(ValueError):
    """An image or mount does not meet the historical runner's contract."""


def relativeParts(name: str) -> tuple[str, ...]:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise RootfsError(f"Archive path escapes the image: {name!r}")
    return tuple(part for part in path.parts if part != ".")


def imagePath(root: Path, parts: tuple[str, ...], *, follow_final: bool = False) -> Path:
    """Resolve links against the image root, never the host's absolute paths."""
    pending = list(parts)
    resolved = []
    links = 0
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            if not resolved:
                raise RootfsError("Symlink escapes the image root")
            resolved.pop()
            continue
        candidate = root.joinpath(*resolved, part)
        if candidate.is_symlink() and (pending or follow_final):
            links += 1
            if links > 40:
                raise RootfsError("Too many image symlinks")
            target = PurePosixPath(os.readlink(candidate))
            if target.is_absolute():
                resolved = []
            pending = list(target.parts[1:] if target.is_absolute() else target.parts) + pending
        else:
            resolved.append(part)
    return root.joinpath(*resolved)


def removePath(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def inspectImage(archive: Path, expected_image_id: str | None = None) -> dict:
    if expected_image_id is not None and not IMAGE_ID.fullmatch(expected_image_id):
        raise RootfsError("Expected image ID must be a SHA-256 Docker image ID")
    with tarfile.open(archive, "r:*") as outer:
        members = {}
        for member in outer:
            if member.name in members:
                raise RootfsError(f"Duplicate Docker-save member: {member.name}")
            members[member.name] = member

        def readJson(name: str) -> tuple[dict | list, bytes]:
            relativeParts(name)
            member = members.get(name)
            if member is None or not member.isfile() or member.size > 8 * 1024 * 1024:
                raise RootfsError(f"Missing or oversized Docker-save metadata: {name}")
            raw = outer.extractfile(member).read()
            return json.loads(raw), raw

        manifest, _ = readJson("manifest.json")
        if not isinstance(manifest, list) or len(manifest) != 1:
            raise RootfsError("Save exactly one historical toolchain image")
        image = manifest[0]
        config_name = image["Config"]
        config, raw = readJson(config_name)
        image_id = "sha256:" + hashlib.sha256(raw).hexdigest()
        config_digest = image_id.removeprefix("sha256:")
        if config_name not in (config_digest + ".json", "blobs/sha256/" + config_digest):
            raise RootfsError("Image config SHA-256 differs from its Docker-save name")
        if expected_image_id is not None and image_id != expected_image_id:
            raise RootfsError("Image ID differs from the recorded toolchain image")
        if config.get("os") != "linux" or config.get("architecture") != "amd64":
            raise RootfsError("The historical toolchain requires a Linux amd64 image")
        layers = image["Layers"]
        diff_ids = config.get("rootfs", {}).get("diff_ids", [])
        if not layers or len(layers) != len(diff_ids) or len(set(layers)) != len(layers):
            raise RootfsError("Image layer inventory differs from its config")
        sizes = []
        for name, digest in zip(layers, diff_ids):
            relativeParts(name)
            member = members.get(name)
            if member is None or not member.isfile() or not IMAGE_ID.fullmatch(digest):
                raise RootfsError(f"Invalid image layer: {name}")
            sizes.append(member.size)
        return {
            "schemaVersion": 1,
            "imageId": image_id,
            "layers": [{"path": name, "diffId": digest} for name, digest in zip(layers, diff_ids)],
            "environment": config.get("config", {}).get("Env") or [],
            "entrypoint": config.get("config", {}).get("Entrypoint") or [],
            "estimatedPeakBytes": sum(sizes) + max(sizes),
        }


def applyLayer(stream, root: Path, directory_modes: dict[tuple[str, ...], int]) -> None:
    with tarfile.open(fileobj=stream, mode="r:") as layer:
        members = layer.getmembers()
        # Whiteouts affect only lower layers, regardless of entry order in this tar.
        for member in members:
            parts = relativeParts(member.name)
            if not parts or not parts[-1].startswith(".wh."):
                continue
            if member.size:
                raise RootfsError("Image whiteout must be empty")
            parent = imagePath(root, parts[:-1], follow_final=True)
            if parts[-1] == ".wh..wh..opq":
                if parent.exists():
                    for child in parent.iterdir():
                        removePath(child)
            else:
                name = parts[-1][len(".wh.") :]
                if not name or name in (".", ".."):
                    raise RootfsError("Invalid image whiteout")
                removePath(parent / name)

        hardlinks = []
        for member in members:
            parts = relativeParts(member.name)
            if not parts or parts[-1].startswith(".wh."):
                continue
            if parts == (METADATA,):
                raise RootfsError("Image contains reserved runner provenance metadata")
            # Runtime creates an isolated /dev; old Ubuntu image layers also
            # contain device nodes that an unprivileged extractor cannot create.
            if member.isdev() and parts[0] == "dev":
                continue
            target = imagePath(root, parts)
            if target == root / METADATA:
                raise RootfsError("Image alias targets reserved runner provenance metadata")
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                if target.is_symlink() or (target.exists() and not target.is_dir()):
                    removePath(target)
                target.mkdir(exist_ok=True)
                directory_modes[parts] = member.mode & 0o777
            elif member.isfile() and not member.issparse():
                removePath(target)
                with layer.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                target.chmod(member.mode & 0o777)
            elif member.issym():
                link = PurePosixPath(member.linkname)
                # Validate relative traversal before storing the container-relative link.
                depth = 0 if link.is_absolute() else len(parts) - 1
                for part in link.parts[1:] if link.is_absolute() else link.parts:
                    depth += -1 if part == ".." else int(part not in ("", "."))
                    if depth < 0:
                        raise RootfsError("Symlink escapes the image root")
                removePath(target)
                target.symlink_to(member.linkname)
            elif member.islnk():
                hardlinks.append((parts, relativeParts(member.linkname)))
            else:
                raise RootfsError(f"Unsupported image member: {member.name}")
        for target_parts, source_parts in hardlinks:
            target = imagePath(root, target_parts)
            if target == root / METADATA:
                raise RootfsError("Image hardlink targets reserved runner provenance metadata")
            source = imagePath(root, source_parts, follow_final=True)
            if not source.is_file():
                raise RootfsError("Image hardlink target is not a regular file")
            target.parent.mkdir(parents=True, exist_ok=True)
            removePath(target)
            os.link(source, target)


def materializeImage(archive: Path, destination: Path, expected_image_id: str | None = None) -> dict:
    metadata = inspectImage(archive, expected_image_id)
    if destination.exists() or destination.is_symlink():
        raise RootfsError("Rootfs destination must not already exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(destination.parent)
    needed = metadata["estimatedPeakBytes"] + 256 * 1024 * 1024
    if needed > usage.free or usage.used + needed >= usage.total * 0.9:
        raise RootfsError(f"Insufficient disk headroom for the estimated {needed} bytes")
    destination.mkdir()
    root = destination.resolve()
    directory_modes = {}
    try:
        with tarfile.open(archive, "r:*") as outer:
            for item in metadata["layers"]:
                digest = hashlib.sha256()
                with tempfile.TemporaryFile(dir=destination.parent) as spool:
                    with outer.extractfile(item["path"]) as source:
                        while chunk := source.read(1024 * 1024):
                            digest.update(chunk)
                            spool.write(chunk)
                    if "sha256:" + digest.hexdigest() != item["diffId"]:
                        raise RootfsError(f"Image layer SHA-256 mismatch: {item['path']}")
                    spool.seek(0)
                    applyLayer(spool, root, directory_modes)
        (root / METADATA).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for parts, mode in sorted(directory_modes.items(), key=lambda item: len(item[0]), reverse=True):
            directory = imagePath(root, parts)
            if directory.is_dir() and not directory.is_symlink():
                directory.chmod(mode)
    except BaseException:
        # Only remove the new task-owned, reproducible output, never the input archive.
        for directory in root.rglob("*"):
            if directory.is_dir() and not directory.is_symlink():
                directory.chmod(0o700)
        shutil.rmtree(root)
        raise
    return metadata


def loadMetadata(root: Path) -> dict:
    path = root / METADATA
    if root.is_symlink() or path.is_symlink() or not path.is_file():
        raise RootfsError("A completely materialized toolchain rootfs is required")
    metadata = json.loads(path.read_text(encoding="utf-8"))
    if metadata.get("schemaVersion") != 1 or not IMAGE_ID.fullmatch(metadata.get("imageId", "")):
        raise RootfsError("Invalid rootfs image provenance")
    return metadata


def gitReadMounts(repo: Path) -> list[Path]:
    """Include shared Git metadata/object stores without granting host write access."""
    common = Path(
        subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True
        ).strip()
    ).resolve()
    mounts = [repo.resolve(), common]
    pending = [common / "objects"]
    seen = set()
    while pending:
        objects = pending.pop().resolve()
        if objects in seen:
            continue
        seen.add(objects)
        mounts.append(objects)
        alternates = objects / "info/alternates"
        if alternates.is_file():
            for line in alternates.read_text(encoding="utf-8").splitlines():
                if line:
                    path = Path(line)
                    pending.append(path if path.is_absolute() else objects / path)
    return sorted(set(mounts), key=lambda path: len(path.parts))


def bwrapCommand(
    root: Path,
    command: list[str],
    cwd: Path,
    read_only: list[Path],
    writable: list[Path],
    environment: dict[str, str] | None = None,
) -> list[str]:
    metadata = loadMetadata(root)
    executable = shutil.which("bwrap")
    if executable is None or os.name != "posix":
        raise RootfsError("The local historical rootfs runner requires Linux bwrap")
    root = root.resolve()
    mounts = [(path.resolve(strict=True), False) for path in read_only]
    mounts += [(path.resolve(strict=True), True) for path in writable]
    for path, write in mounts:
        if path == Path("/") or (write and root.is_relative_to(path)):
            raise RootfsError("Refusing a writable toolchain or host-root mount")
        if write and any(source.is_relative_to(path) for source, rw in mounts if not rw):
            raise RootfsError("Writable mounts must not expose the source checkout")
    if not any(cwd.resolve().is_relative_to(path) for path, _ in mounts if path.is_dir()):
        raise RootfsError("Working directory must be inside an explicit mount")
    arguments = [
        executable,
        "--die-with-parent",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--uid",
        "0",
        "--gid",
        "0",
        "--ro-bind",
        str(root),
        "/",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/home",
        "--tmpfs",
        "/mnt",
        "--tmpfs",
        "/run",
        "--clearenv",
    ]
    variables = dict(item.split("=", 1) for item in metadata["environment"] if "=" in item)
    variables.update(HOME="/tmp")
    variables.update(environment or {})
    variables["GAME_RECOVERY_TOOLCHAIN_ID"] = metadata["imageId"]
    for name, value in sorted(variables.items()):
        arguments += ["--setenv", name, value]
    for path, write in sorted(set(mounts), key=lambda item: (len(item[0].parts), item[1])):
        arguments += ["--bind" if write else "--ro-bind", str(path), str(path)]
    return arguments + ["--chdir", str(cwd.resolve()), "--", *command]


def runRootfs(
    root: Path,
    command: list[str],
    cwd: Path,
    read_only: list[Path],
    writable: list[Path],
    *,
    environment: dict[str, str] | None = None,
    timeout: float = 3600,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        bwrapCommand(root, command, cwd, read_only, writable, environment),
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    materialize = commands.add_parser("materialize")
    materialize.add_argument("archive", type=Path)
    materialize.add_argument("destination", type=Path)
    materialize.add_argument("--image-id", required=True, help="Id from the CI artifact's image.json")
    run = commands.add_parser("run")
    run.add_argument("--rootfs", type=Path, required=True)
    run.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    run.add_argument("--writable", type=Path, action="append", required=True)
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "materialize":
        print(json.dumps(materializeImage(args.archive, args.destination, args.image_id), indent=2))
    else:
        arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        result = runRootfs(args.rootfs, [CONTROLLER, *arguments], args.repo, gitReadMounts(args.repo), args.writable)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
