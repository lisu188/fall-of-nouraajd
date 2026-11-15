#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pre-stage every pinned toolchain source archive for an offline or proxy-restricted image build.

    python3 recovery/toolchains/stage_sources.py --lock recovery/toolchains/sources-git.json CACHE_DIR
    docker build --build-context source-cache=CACHE_DIR \
        --build-arg RECOVERY_SOURCE_LOCK=sources-git.json --tag nouraajd-recovery:qt5 recovery/toolchains

Git-pinned sources are exported from the exact pinned commit with ``git archive``; downloaded
sources may use listed mirrors. Every archive must match the SHA-256 in the lock.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def gitArchive(source, target):
    pin = source["git"]
    prefix = target.name[: -len(".git.tar")] if target.name.endswith(".git.tar") else target.stem
    with tempfile.TemporaryDirectory(prefix="recovery-source-") as temporary:
        checkout = Path(temporary) / "checkout"
        subprocess.check_call(
            [
                "git",
                "-c",
                "advice.detachedHead=false",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                pin["tag"],
                pin["repository"],
                str(checkout),
            ]
        )
        commit = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        if commit != pin["commit"]:
            raise SystemExit(f"{source['name']}: tag {pin['tag']} resolves to {commit}, expected {pin['commit']}")
        with target.open("wb") as stream:
            subprocess.check_call(
                ["git", "-C", str(checkout), "archive", "--format=tar", f"--prefix={prefix}/", commit], stdout=stream
            )


def download(source, target):
    for url in [source["url"], *source.get("mirrors", [])]:
        result = subprocess.run(
            ["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "3", "--output", str(target), url]
        )
        if result.returncode == 0 and sha256(target) == source["sha256"]:
            return
        print(f"{source['name']}: {url} unavailable or mismatched", file=sys.stderr)
    raise SystemExit(f"{source['name']}: no source matched the pinned SHA-256")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("sources.json"))
    parser.add_argument("cache", type=Path)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    args.cache.mkdir(parents=True, exist_ok=True)
    for source in lock["sources"]:
        target = args.cache / (source.get("archive") or source["url"].rsplit("/", 1)[-1])
        if not (target.is_file() and sha256(target) == source["sha256"]):
            (gitArchive if "git" in source else download)(source, target)
        if sha256(target) != source["sha256"]:
            raise SystemExit(f"{source['name']}: staged archive does not match the pinned SHA-256")
        print(f"{source['name']}: {target.name} verified")


if __name__ == "__main__":
    main()
