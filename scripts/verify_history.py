#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build recovered Qt snapshots and require observable, isolated game startup."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SOURCE = REPO_ROOT / "recovery/smoke/game_startup.cpp"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REQUIRED_CHECKS = ("map", "player", "eventLoop", "renderedFrame")


class VerificationError(ValueError):
    """A build or startup result did not establish the required evidence."""


def writeJson(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def runCommand(command: list[str], cwd: Path, environment: dict[str, str], timeout: float, log_path: Path) -> dict:
    """Drain output directly to a file and terminate the entire child group on timeout."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name == "posix",
        )
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait()
    return {
        "command": command,
        "returnCode": process.returncode,
        "timedOut": timed_out,
        "seconds": round(time.monotonic() - started, 3),
        "log": str(log_path.resolve()),
    }


def validatePng(path: Path) -> tuple[int, int]:
    """Check PNG structure, checksums and decompression without optional image packages."""
    if path.suffix.lower() != ".png" or not path.is_file():
        raise VerificationError("A nonempty PNG frame is required")
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise VerificationError("Frame is not a PNG image")
    offset = len(PNG_SIGNATURE)
    dimensions = None
    compressed = bytearray()
    ended = False
    while offset < len(data):
        if len(data) - offset < 12:
            raise VerificationError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        if length > len(data) - offset - 12:
            raise VerificationError("Truncated PNG payload")
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        checksum = struct.unpack_from(">I", data, offset + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != checksum:
            raise VerificationError("PNG checksum mismatch")
        if dimensions is None:
            if kind != b"IHDR" or length != 13:
                raise VerificationError("PNG must begin with IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if not (0 < width <= 8192 and 0 < height <= 8192):
                raise VerificationError("PNG dimensions are outside the smoke-frame limit")
            if depth != 8 or color not in (0, 2, 4, 6) or compression or filtering or interlace:
                raise VerificationError("Smoke frame must be an ordinary noninterlaced 8-bit PNG")
            dimensions = (width, height, {0: 1, 2: 3, 4: 2, 6: 4}[color])
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if length or offset + 12 != len(data):
                raise VerificationError("Invalid PNG end chunk")
            ended = True
            break
        offset += length + 12
    if not ended or dimensions is None or not compressed:
        raise VerificationError("Incomplete PNG frame")
    width, height, channels = dimensions
    expected_length = height * (1 + width * channels)
    decoder = zlib.decompressobj()
    try:
        pixels = decoder.decompress(bytes(compressed), expected_length + 1)
    except zlib.error as error:
        raise VerificationError(f"Invalid PNG image data: {error}") from error
    if not decoder.eof or decoder.unused_data or len(pixels) != expected_length:
        raise VerificationError("PNG pixel data has an unexpected size")
    stride = 1 + width * channels
    if any(pixels[row * stride] > 4 for row in range(height)):
        raise VerificationError("PNG has an invalid row filter")
    return width, height


def validateSmokeReport(report_path: Path, artifact_root: Path) -> dict:
    if not report_path.is_file():
        raise VerificationError("Game exited without a startup-readiness report")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise VerificationError(f"Invalid startup report: {error}") from error
    if not isinstance(report, dict) or report.get("schemaVersion") != 1 or report.get("status") != "ready":
        raise VerificationError("Game did not report successful startup")
    checks = report.get("checks", {})
    if not isinstance(checks, dict) or any(checks.get(name) is not True for name in REQUIRED_CHECKS):
        raise VerificationError("Startup requires map, player, event-loop and rendered-frame evidence")
    frame = report.get("frame", {})
    if not isinstance(frame, dict) or not isinstance(frame.get("path"), str):
        raise VerificationError("Startup report has no frame path")
    frame_path = Path(frame["path"])
    if not frame_path.is_absolute():
        frame_path = artifact_root / frame_path
    frame_path = frame_path.resolve()
    if not frame_path.is_relative_to(artifact_root.resolve()):
        raise VerificationError("Frame path escapes the verification artifacts")
    width, height = validatePng(frame_path)
    if (width, height) != (frame.get("width"), frame.get("height")):
        raise VerificationError("Frame dimensions differ from the startup report")
    if "sha256" in frame and hashlib.sha256(frame_path.read_bytes()).hexdigest() != frame["sha256"]:
        raise VerificationError("Frame content differs from the recorded screenshot")
    return report


def runSmoke(
    executable: Path | list[str],
    cwd: Path,
    output_dir: Path,
    *,
    environment: dict[str, str] | None = None,
    timeout: float = 30,
    isolate: bool = True,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir.resolve() / "startup.json"
    if report_path.exists():
        raise VerificationError("Refusing to reuse a possibly stale startup report")
    command = [str(executable.resolve())] if isinstance(executable, Path) else list(executable)
    if isolate:
        missing = [name for name in ("xvfb-run", "xauth") if shutil.which(name) is None]
        if os.name != "posix" or missing:
            return {"status": "blocked", "reason": "Isolated Linux startup requires xvfb-run and xauth"}
        command = ["xvfb-run", "-a", "--server-args=-screen 0 1920x1080x24", *command]
    child_environment = dict(os.environ if environment is None else environment)
    child_environment.update(
        {
            "GAME_RECOVERY_SMOKE_REPORT": str(report_path),
            "SDL_VIDEODRIVER": "x11",
            "SDL_AUDIODRIVER": "dummy",
            "SDL_RENDER_DRIVER": "software",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "QT_OPENGL": "software",
            "QT_X11_NO_MITSHM": "1",
        }
    )
    result = runCommand(command, cwd, child_environment, timeout, output_dir / "startup.log")
    result["status"] = "failed"
    if result["timedOut"]:
        result["reason"] = "Startup watchdog expired; a timeout is not successful readiness"
    elif result["returnCode"] != 0:
        result["reason"] = f"Game did not shut down cleanly (exit {result['returnCode']})"
    else:
        try:
            result["startup"] = validateSmokeReport(report_path, output_dir)
            frame_path = Path(result["startup"]["frame"]["path"])
            if not frame_path.is_absolute():
                frame_path = output_dir / frame_path
            result["startup"]["frame"]["sha256"] = hashlib.sha256(frame_path.read_bytes()).hexdigest()
            writeJson(report_path, result["startup"])
            result["status"] = "success"
        except VerificationError as error:
            result["reason"] = str(error)
    return result


def findHeader(source_root: Path, name: str) -> Path:
    candidates = sorted(source_root.rglob(name))
    if len(candidates) != 1:
        raise VerificationError(f"Expected one historical {name}; found {len(candidates)}")
    return candidates[0]


def prepareSmokeAdapter(source_root: Path, build_root: Path) -> dict:
    """Add a startup observer to the real target, retaining its original main function."""
    prefixed = any(source_root.rglob("CGameScene.h"))
    scene_name, view_name, map_name = (
        ("CGameScene", "CGameView", "CMap") if prefixed else ("GameScene", "GameView", "Map")
    )
    scene_header = findHeader(source_root, scene_name + ".h" if prefixed else "gamescene.h")
    view_header = findHeader(source_root, view_name + ".h" if prefixed else "gameview.h")
    map_header = findHeader(source_root, map_name + ".h" if prefixed else "map.h")
    scene_text = scene_header.read_text(encoding="utf-8")
    map_text = map_header.read_text(encoding="utf-8")
    has_map_getter = re.search(r"\bgetMap\s*\(", scene_text) is not None
    overlays = []
    if not has_map_getter:
        declaration = re.search(r"\bclass\s+" + scene_name + r"\s*:[^{]+\{", scene_text)
        if not declaration or not re.search(r"\b" + map_name + r"\s*\*\s*map\b", scene_text):
            raise VerificationError("Scene needs a reviewed map-access adapter")
        insertion = f"\npublic:\n    {map_name} *recoveryGetMap() const {{ return map; }}\nprivate:\n"
        original = scene_header.read_bytes()
        scene_header.write_text(scene_text[: declaration.end()] + insertion + scene_text[declaration.end() :])
        overlays.append(
            {
                "path": str(scene_header.relative_to(source_root)),
                "purpose": "smoke-only map accessor",
                "beforeSha256": hashlib.sha256(original).hexdigest(),
                "afterSha256": hashlib.sha256(scene_header.read_bytes()).hexdigest(),
            }
        )
    contains = re.search(r"\bcontains\s*\(([^)]*)\)", map_text)
    if contains is None:
        raise VerificationError("Map needs a reviewed tile-readiness adapter")
    coords3 = contains.group(1).count(",") >= 2
    static_player = re.search(r"\bstatic\s+\w+\s*\*\s*getPlayer\s*\(", scene_text) is not None
    player_header = findHeader(source_root, "CPlayer.h" if prefixed else "player.h")
    opengl = any(
        re.search(r'^\s*#include\s*[<"](?:QtOpenGL/)?QGLWidget[>"]', path.read_text(errors="replace"), re.MULTILINE)
        for path in source_root.rglob("*.cpp")
    )
    config = [
        "// Generated observer configuration; recorded in verification provenance.",
        f'#define GAME_RECOVERY_SCENE_HEADER "{scene_header.relative_to(source_root).as_posix()}"',
        f'#define GAME_RECOVERY_VIEW_HEADER "{view_header.relative_to(source_root).as_posix()}"',
        f'#define GAME_RECOVERY_MAP_HEADER "{map_header.relative_to(source_root).as_posix()}"',
        f'#define GAME_RECOVERY_PLAYER_HEADER "{player_header.relative_to(source_root).as_posix()}"',
        f"#define GAME_RECOVERY_SCENE_TYPE {scene_name}",
        f"#define GAME_RECOVERY_VIEW_TYPE {view_name}",
        f"#define GAME_RECOVERY_MAP_GETTER {'getMap' if has_map_getter else 'recoveryGetMap'}",
        f"#define GAME_RECOVERY_STATIC_PLAYER {int(static_player)}",
        f"#define GAME_RECOVERY_COORDS3 {int(coords3)}",
        f"#define GAME_RECOVERY_OPENGL {int(opengl)}",
    ]
    build_root.mkdir(parents=True, exist_ok=True)
    config_path = build_root / "recovery_smoke_config.h"
    config_path.write_text("\n".join(config) + "\n", encoding="utf-8")
    return {
        "id": ("prefixed" if prefixed else "classic") + ("-3d" if coords3 else "-2d"),
        "source": str(SMOKE_SOURCE),
        "config": str(config_path),
        "overlays": overlays,
        "configSha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }


def loadRecipes(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    recipes = value.get("recipes", [])
    if isinstance(recipes, dict):
        recipes = [{"id": key, **recipe} for key, recipe in recipes.items()]
    if not recipes:
        raise VerificationError(f"No build recipes in {path}")
    lock = {key: item for key, item in value.items() if key != "recipes"}
    if lock.get("sourceLock"):
        source_lock = REPO_ROOT / lock["sourceLock"]
        if not source_lock.is_file():
            raise VerificationError(f"Pinned historical dependency lock is missing: {source_lock}")
        lock["sourceLockSha256"] = hashlib.sha256(source_lock.read_bytes()).hexdigest()
    return [{"toolchainLock": lock, **recipe} for recipe in recipes]


def selectRecipe(recipes: list[dict], source_root: Path, selected: str | None) -> dict:
    if selected:
        matching = [recipe for recipe in recipes if recipe["id"] == selected]
    else:
        projects = sorted(path for pattern in ("*.pro", "*.pri") for path in source_root.rglob(pattern))
        text = "\n".join(path.read_text(encoding="utf-8") for path in projects)
        versions = re.findall(r"python([23])(?:\.([0-9]+)|([0-9]))", text, re.IGNORECASE)
        declared_abis = {version[0] + "." + (version[1] or version[2]) for version in versions}
        code = "\n".join(
            path.read_text(errors="replace")
            for pattern in ("*.h", "*.cpp")
            for path in source_root.rglob(pattern)
            if not any(
                part.lower() in ("boost", "libraries", "json") for part in path.relative_to(source_root).parts[:-1]
            )
        )
        python_used = re.search(r"(?:Python\.h|boost/python|PyModuleDef|Py_InitModule|PyInit_)", code) is not None
        source_majors = set()
        if re.search(r"\bPy_InitModule\w*\s*\(", code):
            source_majors.add("2")
        if re.search(r"\b(?:PyModuleDef|PyModule_Create\w*|PyInit_\w+)\b", code):
            source_majors.add("3")
        if len(declared_abis) > 1:
            raise VerificationError("Multiple historical Python ABIs are declared; supply --recipe")
        abi = next(iter(declared_abis), "none")
        if declared_abis and len(source_majors) == 1 and abi[0] not in source_majors:
            raise VerificationError("Python initialization API conflicts with the declared ABI; supply --recipe")
        if abi == "none" and len(source_majors) == 1:
            compatible_abis = {
                str(recipe.get("pythonAbi"))
                for recipe in recipes
                if str(recipe.get("pythonAbi", "")).startswith(next(iter(source_majors)) + ".")
            }
            if len(compatible_abis) == 1:
                abi = next(iter(compatible_abis))
        if abi == "none" and python_used:
            raise VerificationError("Python is used but the historical ABI cannot be inferred; supply --recipe")
        matching = [recipe for recipe in recipes if str(recipe.get("pythonAbi", "none")) == abi]
    if len(matching) != 1:
        raise VerificationError(f"Expected one build recipe; found {len(matching)}")
    return matching[0]


def toolchainFingerprint(recipe: dict, environment: dict[str, str]) -> dict:
    versions = {}
    for field in ("qmakeCommand", "makeCommand", "compilerCommand"):
        command = recipe.get(field)
        if command:
            executable = shutil.which(command, path=environment.get("PATH"))
            if executable is None:
                raise VerificationError(f"Required historical tool is unavailable: {command}")
            version_flag = "-v" if field == "qmakeCommand" else "--version"
            result = subprocess.run(
                [executable, version_flag], capture_output=True, text=True, env=environment, timeout=10, check=False
            )
            if result.returncode != 0:
                raise VerificationError(f"Cannot identify historical tool: {command}")
            versions[field] = {"path": executable, "version": result.stdout + result.stderr}
    return versions


def exportEvidence(result: dict, output_root: Path) -> None:
    """Keep successful evidence together so replay does not depend on temporary artifact paths."""
    if result.get("status") != "success":
        return
    artifact_root = Path(result["artifactDir"])
    startup = validateSmokeReport(Path(result["smoke"]["startupReport"]), artifact_root)
    evidence_dir = output_root / "evidence" / result["fingerprint"]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    frame_path = Path(startup["frame"]["path"])
    if not frame_path.is_absolute():
        frame_path = artifact_root / frame_path
    shutil.copyfile(frame_path, evidence_dir / "startup.png")
    shutil.copyfile(result["smoke"]["startupReport"], evidence_dir / "startup.json")
    for key in ("configure", "build", "smoke"):
        log_path = Path(result[key]["log"])
        if log_path.is_file():
            shutil.copyfile(log_path, evidence_dir / ("startup.log" if key == "smoke" else key + ".log"))
    result["evidenceDir"] = str(evidence_dir.resolve())
    writeJson(evidence_dir / "verification.json", result)


def verifySnapshot(
    repo_root: Path,
    catalog: dict,
    tree: dict,
    output_root: Path,
    recipes: list[dict],
    *,
    overrides: dict | None = None,
    selected_recipe: str | None = None,
    timeout: float = 30,
    build_timeout: float = 1200,
    jobs: int = 1,
) -> dict:
    try:
        from scripts.recover_history import RecoveryError, restoreSnapshot
    except ModuleNotFoundError:
        from recover_history import RecoveryError, restoreSnapshot

    source_commit = tree["commits"][0]
    result = {"sourceCommit": source_commit, "sourceCommits": tree["commits"], "sourceTree": tree["tree"]}
    output_root.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="snapshot-", dir=output_root)).resolve()
    source_root = work_root / "source"
    try:
        result["restoration"] = restoreSnapshot(repo_root, catalog, source_commit, source_root, overrides=overrides)
    except (RecoveryError, ValueError, OSError) as error:
        return {**result, "status": "blocked", "reason": f"Snapshot restoration is incomplete: {error}"}
    try:
        recipe = selectRecipe(recipes, source_root, selected_recipe)
        environment = dict(os.environ)
        environment.update({key: str(value) for key, value in recipe.get("environment", {}).items()})
        toolchain = toolchainFingerprint(recipe, environment)
        adapter = prepareSmokeAdapter(source_root, work_root / "observer")
        identity = {
            "sourceTree": tree["tree"],
            "recipe": recipe,
            "toolchain": toolchain,
            "toolchainImage": environment.get("GAME_RECOVERY_TOOLCHAIN_ID"),
            "adapter": hashlib.sha256(SMOKE_SOURCE.read_bytes()).hexdigest(),
            "verifier": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "restorer": hashlib.sha256((REPO_ROOT / "scripts/recover_history.py").read_bytes()).hexdigest(),
            "adapterConfig": adapter["configSha256"],
            "overrides": overrides,
            "overrideContext": [
                entry
                for entry in (overrides or {}).get("entries", [])
                if entry.get("commit", source_commit) == source_commit
                and entry.get("tree", tree["tree"]) == tree["tree"]
            ],
        }
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        result.update({"fingerprint": fingerprint, "recipe": recipe, "toolchain": toolchain, "adapter": adapter})
        cached_path = output_root / "results" / (fingerprint + ".json")
        if cached_path.is_file():
            cached = json.loads(cached_path.read_text())
            if cached.get("status") == "success":
                validateSmokeReport(Path(cached["smoke"]["startupReport"]), Path(cached["artifactDir"]))
                cached = {**cached, "sourceCommit": source_commit, "sourceCommits": tree["commits"], "resumed": True}
                exportEvidence(cached, output_root)
                return cached
        projects = sorted(source_root.glob("*.pro"))
        if len(projects) != 1:
            raise VerificationError(f"Expected one historical qmake project, found {len(projects)}")
        build_root = work_root / "build"
        build_root.mkdir()
        configure = [
            recipe.get("qmakeCommand", "qmake"),
            str(projects[0]),
            "-o",
            str(build_root / "Makefile"),
            *recipe.get("qmakeArguments", []),
            "-after",
            "TARGET=RecoveryGame",
            "DESTDIR=.",
            "CONFIG-=app_bundle",
            "SOURCES+=" + str(SMOKE_SOURCE),
            "INCLUDEPATH+=" + str(source_root),
            "INCLUDEPATH+=" + str(work_root / "observer"),
        ]
        result["configure"] = runCommand(configure, build_root, environment, build_timeout, work_root / "configure.log")
        if result["configure"]["returnCode"] != 0:
            reason = "timed out" if result["configure"]["timedOut"] else "failed"
            raise VerificationError(f"Historical qmake configuration {reason}; inspect configure.log")
        result["build"] = runCommand(
            [recipe.get("makeCommand", "make"), f"-j{jobs}"],
            build_root,
            environment,
            build_timeout,
            work_root / "build.log",
        )
        if result["build"]["returnCode"] != 0:
            reason = "timed out" if result["build"]["timedOut"] else "failed"
            raise VerificationError(f"Historical game compilation/linking {reason}; inspect build.log")
        executable = build_root / "RecoveryGame"
        if not executable.is_file():
            raise VerificationError("Build did not produce the actual game executable")
        artifact_dir = work_root / "smoke"
        result["smoke"] = runSmoke(executable, source_root, artifact_dir, environment=environment, timeout=timeout)
        result["smoke"]["startupReport"] = str(artifact_dir / "startup.json")
        result["artifactDir"] = str(artifact_dir)
        result["status"] = result["smoke"]["status"]
        if "reason" in result["smoke"]:
            result["reason"] = result["smoke"]["reason"]
        exportEvidence(result, output_root)
        writeJson(cached_path, result)
        return result
    except (VerificationError, OSError, ValueError, subprocess.TimeoutExpired) as error:
        result.update({"status": "blocked" if "unavailable" in str(error) else "failed", "reason": str(error)})
        return result


def selectTrees(catalog: dict, overrides: dict | None, commit_prefix: str | None = None) -> list[dict]:
    """Reuse identical trees only when commit-scoped repairs also have identical applicability."""
    trees = sorted(catalog["trees"], key=lambda tree: tree["tree"])
    if commit_prefix:
        matching = [(tree, commit) for tree in trees for commit in tree["commits"] if commit.startswith(commit_prefix)]
        if len(matching) != 1:
            raise VerificationError("--commit must identify one cataloged damaged commit")
        tree, commit = matching[0]
        return [{**tree, "commits": [commit]}]
    selected = []
    for tree in trees:
        contexts = {}
        for commit in tree["commits"]:
            context = [
                entry
                for entry in (overrides or {}).get("entries", [])
                if entry.get("commit", commit) == commit and entry.get("tree", tree["tree"]) == tree["tree"]
            ]
            key = json.dumps(context, sort_keys=True)
            contexts.setdefault(key, []).append(commit)
        selected.extend({**tree, "commits": commits} for commits in contexts.values())
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--commit")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--catalog", type=Path, default=REPO_ROOT / "recovery/catalog.json")
    parser.add_argument("--overrides", type=Path, default=REPO_ROOT / "recovery/overrides.json")
    parser.add_argument("--recipes", type=Path, default=REPO_ROOT / "recovery/toolchains/qt5.json")
    parser.add_argument("--recipe")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / ".cache/history-recovery/verification")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--build-timeout", type=float, default=1200)
    parser.add_argument(
        "--jobs", type=int, default=len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else 1
    )
    args = parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count or args.jobs < 1:
        parser.error("Shard index/count and job count must be positive and consistent")
    if args.timeout <= 0 or args.build_timeout <= 0:
        parser.error("Timeouts must be positive")
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        recipes = loadRecipes(args.recipes)
        overrides = None
        if args.overrides.exists():
            overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
            overrides["_baseDir"] = str(args.overrides.resolve().parent)
        trees = selectTrees(catalog, overrides, args.commit)
        trees = [tree for index, tree in enumerate(trees) if index % args.shard_count == args.shard_index]
        results = []
        for tree in trees:
            result = verifySnapshot(
                args.repo_root.resolve(),
                catalog,
                tree,
                args.output_dir.resolve(),
                recipes,
                overrides=overrides,
                selected_recipe=args.recipe,
                timeout=args.timeout,
                build_timeout=args.build_timeout,
                jobs=args.jobs,
            )
            results.append(result)
            print(json.dumps({key: result[key] for key in ("sourceCommit", "sourceTree", "status")}), flush=True)
            writeJson(args.output_dir / f"summary-{args.shard_index}.json", {"schemaVersion": 1, "results": results})
        return 0 if results and all(result["status"] == "success" for result in results) else 1
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
