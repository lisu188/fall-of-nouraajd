#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Attach verified startup screenshots and build provenance to recovered snapshots."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

try:
    from scripts.verify_history import REQUIRED_CHECKS, VerificationError, validatePng
except ModuleNotFoundError:
    from verify_history import REQUIRED_CHECKS, VerificationError, validatePng


def requireIdentity(value, length, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value):
        raise VerificationError(f"Verified recovery needs a valid {name}")
    return value


def successfulCommand(command, name):
    if (
        not isinstance(command, dict)
        or command.get("returnCode") != 0
        or command.get("timedOut") is not False
        or not isinstance(command.get("command"), list)
        or not command["command"]
    ):
        raise VerificationError(f"Recovered README requires successful {name} evidence")


def snapshotDocumentation(report: dict, evidence_dir: Path) -> dict[str, bytes]:
    """Return portable documentation only for a fully verified, explicitly identified source tree."""
    if not isinstance(report, dict) or report.get("status") != "success":
        raise VerificationError("Cannot attach a screenshot to an unverified recovered version")
    commit = requireIdentity(report.get("sourceCommit"), 40, "source commit")
    tree = requireIdentity(report.get("sourceTree"), 40, "source tree")
    restoration = report.get("restoration", {})
    if (
        restoration.get("status") != "complete"
        or restoration.get("sourceCommit") != commit
        or restoration.get("sourceTree") != tree
        or restoration.get("unresolved") != []
    ):
        raise VerificationError("Recovered README requires complete matching restoration evidence")
    restored_fingerprint = requireIdentity(
        restoration.get("restoredFilesFingerprint"), 64, "restored-files fingerprint"
    )
    successfulCommand(report.get("configure"), "qmake configuration")
    successfulCommand(report.get("build"), "native game compilation/linking")
    smoke = report.get("smoke", {})
    successfulCommand(smoke, "isolated game startup")
    if smoke.get("status") != "success":
        raise VerificationError("Recovered README requires successful startup")
    command = smoke["command"]
    if Path(command[0]).name != "xvfb-run" or "-a" not in command:
        raise VerificationError("Recovered startup must use an isolated Xvfb display")
    if not any(argument.startswith("--server-args=") for argument in command):
        raise VerificationError("Recovered startup needs an explicit virtual-display configuration")
    startup = smoke.get("startup", {})
    if startup.get("schemaVersion") != 1 or startup.get("status") != "ready":
        raise VerificationError("Recovered README requires the game's readiness report")
    checks = startup.get("checks", {})
    if any(checks.get(name) is not True for name in REQUIRED_CHECKS):
        raise VerificationError("Recovered screenshot lacks map/player/render readiness")
    evidence_dir = Path(evidence_dir).resolve()
    frame_path = evidence_dir / "startup.png"
    width, height = validatePng(frame_path)
    frame = startup.get("frame", {})
    if (frame.get("width"), frame.get("height")) != (width, height):
        raise VerificationError("Attached screenshot differs from the verified frame dimensions")
    frame_sha256 = requireIdentity(frame.get("sha256"), 64, "captured-frame fingerprint")
    if hashlib.sha256(frame_path.read_bytes()).hexdigest() != frame_sha256:
        raise VerificationError("Attached screenshot differs from the actual verified image bytes")
    startup_path = evidence_dir / "startup.json"
    if not startup_path.is_file() or json.loads(startup_path.read_text(encoding="utf-8")) != startup:
        raise VerificationError("Copied startup report differs from the recorded native game result")

    projects = [Path(argument).name for argument in report["configure"]["command"] if argument.endswith(".pro")]
    if len(projects) != 1 or any(character in projects[0] for character in "\n\r`$\\\"' "):
        raise VerificationError("Cannot derive a portable qmake project command")
    toolchain = report.get("toolchain", {})
    compiler_version = toolchain.get("compilerCommand", {}).get("version", "").splitlines()
    qmake_version = toolchain.get("qmakeCommand", {}).get("version", "").splitlines()
    if not compiler_version or not qmake_version:
        raise VerificationError("Recovered README requires the actual compiler and qmake identities")
    provenance = []
    counts = {}
    for entry in restoration.get("restored", []):
        method = entry.get("method", "unknown")
        counts[method] = counts.get(method, 0) + 1
        if method in ("reconstruction", "compatibilityRepair"):
            path = entry.get("path", "").replace("`", "\\`")
            description = str(entry.get("provenance", "Recorded reconstructed replacement")).replace("\n", " ")
            provenance.append(f"- `{path}`: {description}")
    compiler_flags = report.get("recipe", {}).get("qmakeArguments", [])
    if any(not isinstance(flag, str) or not re.fullmatch(r"[A-Za-z0-9_+=./:-]+", flag) for flag in compiler_flags):
        raise VerificationError("Historical compiler flags need an explicitly reviewed portable command")
    qmake = " ".join(["qmake", projects[0], *compiler_flags, "-after TARGET=RecoveryGame DESTDIR=."])
    abi = str(report.get("recipe", {}).get("pythonAbi", "none"))
    prerequisites = "Qt 5 Core, Gui and Widgets development files and a C++ compiler"
    if abi != "none":
        prerequisites += f", with CPython {abi} development files and its matching Boost.Python library"
    lines = [
        "# Recovered game snapshot",
        "",
        f"Original commit: `{commit}`. Original tree: `{tree}`.",
        *(
            [f"Startup was verified from identical recovered sources at `{report['verifiedFromCommit']}`."]
            if report.get("verifiedFromCommit")
            else []
        ),
        "",
        "This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,",
        "loaded its map and a healthy player, rendered the screenshot below, and exited normally.",
        "",
        "![Actual startup of this recovered game](recovery/startup.png)",
        "",
        "## Build and run",
        "",
        f"Install {prerequisites}. The verified tool versions were:",
        "",
        f"- {compiler_version[0]}",
        *[f"- {line}" for line in qmake_version],
        "",
        "Build from this snapshot's root directory:",
        "",
        "```sh",
        qmake,
        'make -j"$(nproc)"',
        "./RecoveryGame",
        "```",
        "",
        "For an isolated launch, use:",
        "",
        "```sh",
        'LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software xvfb-run -a --server-args="-screen 0 1920x1080x24" ./RecoveryGame',
        "```",
        "",
        "The automated readiness observer used for verification is recorded in the attached evidence; ordinary",
        "launches run the game's original entry point. Startup evidence does not establish full gameplay equivalence.",
        "",
        "## Recovery provenance",
        "",
        ", ".join(f"{method}: {count}" for method, count in sorted(counts.items())) + ".",
        "",
        *provenance,
        "",
        f"Restored source fingerprint: `{restored_fingerprint}`.",
        "",
        f"The actual {width} × {height} screenshot and [verification metadata](recovery/verification.json) belong to",
        "this source version. Reconstructed code and borrowed assets are identified in that metadata; they are",
        "not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.",
        "",
    ]
    portable = copy.deepcopy(report)
    portable["artifactDir"] = "recovery"
    portable["smoke"]["startup"]["frame"]["path"] = "startup.png"
    portable["smoke"].pop("startupReport", None)
    portable["attachedScreenshot"] = {"path": "startup.png", "width": width, "height": height}
    return {
        "README.md": "\n".join(lines).encode(),
        "recovery/startup.png": frame_path.read_bytes(),
        "recovery/verification.json": (json.dumps(portable, indent=2, sort_keys=True) + "\n").encode(),
    }
