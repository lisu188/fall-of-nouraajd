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
import tempfile
import time
import zlib

try:
    from scripts import history_source_prep as source_prep
    from scripts.history_qmake_compatibility import recipeForSource
except ModuleNotFoundError:
    import history_source_prep as source_prep
    from history_qmake_compatibility import recipeForSource

REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SOURCE = REPO_ROOT / "recovery/smoke/game_startup.cpp"
# The historical game targeted Windows; startup runs with case-insensitive file lookup.
WINDOWS_PATHS_SOURCE = REPO_ROOT / "recovery/smoke/windows_paths.cpp"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REQUIRED_CHECKS = ("map", "player", "eventLoop", "renderedFrame")
EDITOR_CHECKS = ("map", "editor", "eventLoop", "renderedFrame")
# Reviewed original editor routes with Qt metatype registration before view selection.
REVIEWED_EDITOR_MAIN_SHA256 = frozenset(
    {
        "035bc5e41119a494f0abca5007dfd2783d94f758f1e1d557d0dee718c96b2b62",  # #122
        "2d6e34b472015545231ca4c1c0dcb775ca2eb77e00eb13135244ac64bff9f129",  # #124
        "25c1c0d44c34b2f6299c730d4321040c9628e09d7af71dce1a21d8f92a9186a4",  # #134
        "c9a6650318801e75253b0c54ffb4d5b2b4d344fd794694bd37f0951b5776f936",  # #135
        "82d28c2df4fb35f1453ef25e2d8fb30c04bba2a6875710b04f9cfea9a3491d3e",  # #141
        "fa471718f3119672baf3b78564ccb3215351e4c69c637d4ca895b6513a98c5e1",  # #155
    }
)
# Catalog #204 ('stats properties') adds the developer's stdin script console on a thread-pool thread; it loops
# while the game view is visible, and the original view destructor deletes the scene that loop still queries, so
# leaving the event loop with the window shown races a use-after-free. Only for a main.cpp holding this exact
# original loop does the observer close the game window as a player would and wait for that thread before exiting.
CONSOLE_LOOP = (
    b"        QTextStream streamIn(stdin);\n"
    b"        QString script;\n"
    b"        while((!GameScene::getView())||GameScene::getView()->isVisible()){\n"
    b"            streamIn>>script;\n"
    b"            ScriptManager::getInstance().executeScript(script.toStdString());\n"
    b"        }\n"
)
# From #207 the surviving scriptmanager.h returns ScriptManager::getInstance() by pointer and executeScript takes a
# QString; reconstructed mains keep the same loop with only that call adapted. From #224 GameScene::getView() is no
# longer static, so they test the view main created instead.
CONSOLE_LOOPS = (
    CONSOLE_LOOP,
    CONSOLE_LOOP.replace(
        b"ScriptManager::getInstance().executeScript(script.toStdString());",
        b"ScriptManager::getInstance()->executeScript(script);",
    ),
)
CONSOLE_LOOPS += (
    CONSOLE_LOOPS[1].replace(
        b"        while((!GameScene::getView())||GameScene::getView()->isVisible()){\n",
        b"        while(view.isVisible()){\n",
    ),
)
CONSOLE_LOOP_SOURCE = {
    "commit": "c577f6225739c5e3e1cf90081a92e997eaed65a4",
    "path": "src/main.cpp",
    "sha256": "afcbca06c54f7e48aeb125cca228287b4b49ced0ead968b3a7c74def3311f589",
}
CONSOLE_SHUTDOWN_BOUNDARY = (
    "After the first frame and readiness report, the observer closes the game window as a player would and "
    "waits for the original stdin script console thread to stop before exiting; stdin stays open and silent, "
    "like an idle console, until that report and then reaches end of file; sources are unchanged"
)


class VerificationError(ValueError):
    """A build or startup result did not establish the required evidence."""


def writeJson(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def runCommand(
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
    log_path: Path,
    stdin_release: Path | None = None,
) -> dict:
    """Drain output directly to a file and terminate the entire child group on timeout.

    Standard input is empty. With stdin_release, it instead stays open and silent, as an idle console's would,
    until that file exists, and then reaches end of file.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL if stdin_release is None else subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name == "posix",
        )
        timed_out = False
        try:
            if stdin_release is None:
                process.wait(timeout=timeout)
            else:
                while True:
                    try:
                        process.wait(timeout=0.05)
                        break
                    except subprocess.TimeoutExpired:
                        if not process.stdin.closed and stdin_release.exists():
                            process.stdin.close()
                        if time.monotonic() - started > timeout:
                            raise
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
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
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


def verifiedStartupMode(report: dict) -> str:
    """Keep editor evidence distinct and require its original entrypoint identities."""
    mode = report.get("startupMode", "game")
    if mode not in ("game", "editor") or report.get("smoke", {}).get("startup", {}).get("mode", "game") != mode:
        raise VerificationError("Startup report mode differs from the verified historical entrypoint")
    if mode == "editor":
        selection = report.get("startupSelection", {})
        inputs = selection.get("originalInputs", [])
        if (
            selection.get("mode") != mode
            or not isinstance(inputs, list)
            or len(inputs) != 2
            or any(not isinstance(item, dict) for item in inputs)
            or {item.get("path") for item in inputs} != {"main.cpp", "config/init.json"}
            or any(
                not re.fullmatch(r"[0-9a-f]{40}", str(item.get("blob", "")))
                or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", "")))
                for item in inputs
            )
        ):
            raise VerificationError("Editor evidence requires original main.cpp and config/init.json identities")
    return mode


def validateSmokeReport(
    report_path: Path, artifact_root: Path, startup_mode: str = "game", *, portable: bool = False
) -> dict:
    if not report_path.is_file():
        raise VerificationError("Game exited without a startup-readiness report")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise VerificationError(f"Invalid startup report: {error}") from error
    if not isinstance(report, dict) or report.get("schemaVersion") != 1 or report.get("status") != "ready":
        raise VerificationError("Game did not report successful startup")
    if startup_mode not in ("game", "editor") or report.get("mode", "game") != startup_mode:
        raise VerificationError("Startup report mode differs from the verified historical entrypoint")
    checks = report.get("checks", {})
    required = EDITOR_CHECKS if startup_mode == "editor" else REQUIRED_CHECKS
    if not isinstance(checks, dict) or any(checks.get(name) is not True for name in required):
        raise VerificationError(f"Startup requires {', '.join(required)} evidence")
    if startup_mode == "editor" and "player" in checks:
        raise VerificationError("Editor startup cannot claim player evidence")
    frame = report.get("frame", {})
    if not isinstance(frame, dict) or not isinstance(frame.get("path"), str):
        raise VerificationError("Startup report has no frame path")
    frame_path = Path(frame["path"])
    if portable:
        if frame_path.name != "startup.png":
            raise VerificationError("Portable startup evidence requires its attached startup.png")
        frame_path = artifact_root / "startup.png"
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
    startup_mode: str = "game",
    console: bool = False,
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
    # Readiness must be reported before the watchdog fires; loading time is not an original property.
    ready_budget_ms = max(1000, int((timeout - 10) * 1000))
    child_environment.update(
        {
            "GAME_RECOVERY_SMOKE_REPORT": str(report_path),
            "GAME_RECOVERY_READY_BUDGET_MS": str(ready_budget_ms),
            "SDL_VIDEODRIVER": "x11",
            "SDL_AUDIODRIVER": "dummy",
            "SDL_RENDER_DRIVER": "software",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "QT_OPENGL": "software",
            "QT_X11_NO_MITSHM": "1",
        }
    )
    result = runCommand(
        command, cwd, child_environment, timeout, output_dir / "startup.log", report_path if console else None
    )
    result["stdin"] = "open and silent until the readiness report" if console else "empty"
    result["readyBudgetMs"] = ready_budget_ms
    result["status"] = "failed"
    if result["timedOut"]:
        result["reason"] = "Startup watchdog expired; a timeout is not successful readiness"
    elif result["returnCode"] != 0:
        result["reason"] = f"Game did not shut down cleanly (exit {result['returnCode']})"
    else:
        try:
            result["startup"] = validateSmokeReport(report_path, output_dir, startup_mode)
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


def findClassHeader(source_root: Path, names: tuple[str, ...], filenames: tuple[str, ...] = ()) -> tuple[str, Path]:
    declarations = re.compile(r"\bclass\s+(" + "|".join(names) + r")\s*(?::[^{;]+)?\{")
    candidates = []
    for path in sorted(source_root.rglob("*.h")):
        if filenames and path.name.lower() not in filenames:
            continue
        definition = declarations.search(path.read_text(errors="replace"))
        if definition:
            candidates.append((definition.group(1), path))
    if len(candidates) != 1:
        raise VerificationError(f"Expected one historical {'/'.join(names)} definition header; found {len(candidates)}")
    return candidates[0]


def selectStartupMode(repo_root: Path, source_commit: str, source_root: Path) -> dict:
    """Recognize the original early editor branch without trusting reconstructed flags."""
    config_path = source_root / "config/init.json"
    if not config_path.is_file():
        return {"mode": "game"}
    try:
        config = json.loads(config_path.read_text())
    except (OSError, ValueError) as error:
        raise VerificationError(f"Cannot inspect historical startup configuration: {error}") from error
    main_path = source_root / "main.cpp"
    main_data = main_path.read_bytes() if main_path.is_file() else b""
    compact = re.sub(r"\s+", "", main_data.decode())
    start = compact.find("intmain(")
    expected = (
        "intmain(intargc,char*argv[]){QApplicationa(argc,argv);QGraphicsView*view;"
        'booleditor=(*ConfigurationProvider::getConfig("config/init.json")).get("editor",false).asBool();'
        "if(editor){view=newMapView();}else{view=newGameView();}"
        "intret=a.exec();deleteview;returnret;}"
    )
    reviewed = (start >= 0 and compact[start:] == expected) or (
        hashlib.sha256(main_data).hexdigest() in REVIEWED_EDITOR_MAIN_SHA256
    )
    editor = isinstance(config, dict) and config.get("editor") is True
    if not editor and not reviewed:
        return {"mode": "game"}
    if not isinstance(config, dict) or type(config.get("editor", False)) is not bool:
        raise VerificationError("Reviewed historical editor configuration requires a boolean mode")
    try:
        from scripts.recover_history import GitObjects, RecoveryError, objectHash
    except ModuleNotFoundError:
        from recover_history import GitObjects, RecoveryError, objectHash
    verified = []
    try:
        with GitObjects(repo_root) as objects:
            tree = objects.read(source_commit, "commit").split(b"\n", 1)[0].decode().removeprefix("tree ")
            files = objects.files(tree)
            for name in ("main.cpp", "config/init.json"):
                original = files.get(name, {})
                path = source_root / name
                if original.get("mode") not in ("100644", "100755") or not path.is_file() or path.is_symlink():
                    raise VerificationError(f"Editor startup requires surviving original {name}")
                data = path.read_bytes()
                if objectHash("blob", data) != original["blob"] or objects.read(original["blob"], "blob") != data:
                    raise VerificationError(f"Editor startup differs from surviving original {name}")
                verified.append({"path": name, "blob": original["blob"], "sha256": hashlib.sha256(data).hexdigest()})
    except RecoveryError as error:
        raise VerificationError(f"Cannot verify original editor entrypoint: {error}") from error
    if not reviewed:
        raise VerificationError("Original editor main needs an explicitly reviewed startup route")
    return {
        "mode": "editor" if editor else "game",
        "originalInputs": verified,
        "boundary": (
            "Authored editor startup; gameplay and player are unverified" if editor else "Authored game startup"
        ),
    }


def consoleShutdown(source_root: Path) -> dict | None:
    """Recognize only a main.cpp that holds the developer's exact stdin console loop or its reviewed adaptation."""
    path = source_root / "src/main.cpp"
    if path.is_symlink() or not path.is_file():
        return None
    data = path.read_bytes()
    loops = [loop for loop in CONSOLE_LOOPS if loop in data]
    if len(loops) != 1 or data.count(loops[0]) != 1:
        return None
    return {
        "mode": "closeWindowAndJoinConsole",
        "main": {"path": "src/main.cpp", "sha256": hashlib.sha256(data).hexdigest()},
        "consoleLoopSha256": hashlib.sha256(loops[0]).hexdigest(),
        "consoleLoopSource": dict(CONSOLE_LOOP_SOURCE),
        "validationBoundary": CONSOLE_SHUTDOWN_BOUNDARY,
    }


def prepareSmokeAdapter(source_root: Path, build_root: Path, startup_mode: str = "game") -> dict:
    """Add a startup observer to the real target, retaining its original main function."""
    editor = startup_mode == "editor"
    if startup_mode not in ("game", "editor"):
        raise VerificationError("Unknown startup observer mode")
    scene_name, scene_header = findClassHeader(
        source_root,
        ("MapScene",) if editor else ("CGameScene", "GameScene"),
        ("mapscene.h",) if editor else ("cgamescene.h", "gamescene.h"),
    )
    view_name, view_header = findClassHeader(
        source_root,
        ("MapView",) if editor else ("CGameView", "GameView"),
        ("mapview.h",) if editor else ("cgameview.h", "gameview.h"),
    )
    map_name, map_header = findClassHeader(source_root, ("CMap", "Map"), ("cmap.h", "map.h"))
    prefixed = scene_name.startswith("C")
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
    # From #224 the scene owns the player as an instance member and the map has no player accessor yet.
    scene_player = (
        not static_player
        and re.search(r"\b\w+\s*\*\s*getPlayer\s*\(", map_text) is None
        and re.search(r"\b\w+\s*\*\s*getPlayer\s*\(", scene_text) is not None
    )
    player_getter = re.search(
        r"\b(\w+)\s*\*\s*getPlayer\s*\(", scene_text if static_player or scene_player else map_text
    )
    player_name = player_getter.group(1) if player_getter else ("CPlayer" if prefixed else "Player")
    # Several Qt trees define CPlayer alongside CCreature in the same header.
    if editor:
        if not re.search(r"class\s+Map\s*:\s*public\s+std::unordered_map", map_text) or any(
            not re.search(r"\b" + method + r"\s*\(", map_text) for method in ("getScene", "getTileSize")
        ):
            raise VerificationError("Editor needs a reviewed map-model and scene-ownership observer")
        player_header = None
    else:
        _, player_header = findClassHeader(
            source_root, (player_name,), ("cplayer.h", "player.h", "ccreature.h", "creature.h")
        )
    opengl = any(
        re.search(r'^\s*#include\s*[<"](?:QtOpenGL/)?QGLWidget[>"]', path.read_text(errors="replace"), re.MULTILINE)
        for path in source_root.rglob("*.cpp")
    )
    config = [
        "// Generated observer configuration; recorded in verification provenance.",
        f'#define GAME_RECOVERY_SCENE_HEADER "{scene_header.relative_to(source_root).as_posix()}"',
        f'#define GAME_RECOVERY_VIEW_HEADER "{view_header.relative_to(source_root).as_posix()}"',
        f'#define GAME_RECOVERY_MAP_HEADER "{map_header.relative_to(source_root).as_posix()}"',
        f"#define GAME_RECOVERY_EDITOR {int(editor)}",
        f"#define GAME_RECOVERY_SCENE_TYPE {scene_name}",
        f"#define GAME_RECOVERY_VIEW_TYPE {view_name}",
        f"#define GAME_RECOVERY_MAP_GETTER {'getMap' if has_map_getter else 'recoveryGetMap'}",
        f"#define GAME_RECOVERY_STATIC_PLAYER {int(static_player)}",
        f"#define GAME_RECOVERY_COORDS3 {int(coords3)}",
        f"#define GAME_RECOVERY_OPENGL {int(opengl)}",
    ]
    if player_header is not None:
        config.append(f'#define GAME_RECOVERY_PLAYER_HEADER "{player_header.relative_to(source_root).as_posix()}"')
    if scene_player and not editor:
        config.append("#define GAME_RECOVERY_SCENE_PLAYER 1")
    shutdown = None if editor else consoleShutdown(source_root)
    if shutdown is not None:
        config.append("#define GAME_RECOVERY_CLOSE_BEFORE_EXIT 1")
    build_root.mkdir(parents=True, exist_ok=True)
    config_path = build_root / "recovery_smoke_config.h"
    config_path.write_text("\n".join(config) + "\n", encoding="utf-8")
    return {
        "id": "classic-editor" if editor else ("prefixed" if prefixed else "classic") + ("-3d" if coords3 else "-2d"),
        "mode": startup_mode,
        "source": str(SMOKE_SOURCE),
        "config": str(config_path),
        "overlays": overlays,
        "configSha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        **({"shutdown": shutdown} if shutdown is not None else {}),
    }


# Windows import libraries that BFG removed as binaries, mapped to the platform library
# providing the same API. Only names a historical project links are resolved.
WINDOWS_LIBRARY_ALIASES = {"zdll": "libz.so"}
SYSTEM_LIBRARY_DIRS = ("/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib")


def prepareLibraryAliases(source_root: Path, build_root: Path) -> dict:
    """Provide lib<name>.so for Windows import libraries the project links but cannot ship."""
    selected = selectProjects(source_root)
    projects = " ".join(
        word
        for project in [*selected["dependencies"], selected["application"]]
        for word in qmakeVariables(project, source_root).get("LIBS", [])
    )
    aliases = {}
    directory = build_root / "library-aliases"
    for name, target in WINDOWS_LIBRARY_ALIASES.items():
        if not re.search(r"-l" + re.escape(name) + r"\b", projects):
            continue
        system = next((Path(base) / target for base in SYSTEM_LIBRARY_DIRS if (Path(base) / target).exists()), None)
        if system is None:
            raise VerificationError(f"Required historical tool is unavailable: {target} for -l{name}")
        directory.mkdir(parents=True, exist_ok=True)
        link = directory / f"lib{name}.so"
        if not link.is_symlink():
            link.symlink_to(system)
        aliases[name] = str(system)
    return {"directory": str(directory), "aliases": aliases}


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


def qmakeAssignments(project: Path, source_root: Path, included: tuple[Path, ...] = ()) -> list[tuple[str, str, str]]:
    """Read desktop Linux assignments and literal includes without visiting unrelated projects."""
    project = project.resolve()
    if not project.is_relative_to(source_root.resolve()) or project in included:
        raise VerificationError(f"Historical qmake include escapes the snapshot or is cyclic: {project}")
    text = re.sub(r"\\\r?\n", " ", project.read_text(encoding="utf-8"))
    scopes = [True]
    closed = True
    assignments = []

    def active(condition: str) -> bool:
        for term in condition.split(":"):
            alternatives = term.strip().split("|")
            values = []
            for alternative in alternatives:
                alternative = alternative.strip()
                negative = alternative.startswith("!")
                name = alternative.lstrip("!")
                value = {"unix": True, "linux": True, "win32": False, "macx": False, "android": False}.get(name)
                # Unknown qmake predicates remain candidates; conflicting ABI declarations fail closed below.
                values.append(True if value is None else value != negative)
            if not any(values):
                return False
        return True

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.count("{") > 1:
            raise VerificationError(f"Historical qmake inline scopes need an explicit adapter: {project}")
        while line.startswith("}"):
            if len(scopes) == 1:
                raise VerificationError(f"Unbalanced historical qmake scope: {project}")
            closed = scopes.pop()
            line = line[1:].strip()
        if "{" in line:
            condition, line = line.split("{", 1)
            enabled = not closed if condition.strip() == "else" else active(condition)
            scopes.append(scopes[-1] and enabled)
            line = line.strip()
        closing = line.endswith("}")
        if closing:
            line = line[:-1].strip()
        if scopes[-1] and line:
            include = re.fullmatch(r"(?:(.*?)\s*:\s*)?include\s*\(([^)]+)\)", line)
            assignment = re.fullmatch(r"(.*?)([\w.]+)\s*(\+=|-=|\*=|=)\s*(.*)", line)
            if include and active(include.group(1) or ""):
                name = include.group(2).strip().replace("$$PWD", str(project.parent))
                if "$" in name:
                    raise VerificationError(f"Historical qmake include needs an explicit adapter: {name}")
                assignments.extend(qmakeAssignments(project.parent / name, source_root, (*included, project)))
            elif assignment and active(assignment.group(1).rstrip(": ")):
                assignments.append((assignment.group(2), assignment.group(3), assignment.group(4)))
        if closing:
            if len(scopes) == 1:
                raise VerificationError(f"Unbalanced historical qmake scope: {project}")
            closed = scopes.pop()
    if len(scopes) != 1:
        raise VerificationError(f"Unbalanced historical qmake scope: {project}")
    return assignments


def qmakeVariables(project: Path, source_root: Path) -> dict[str, list[str]]:
    variables = {}
    for name, operation, value in qmakeAssignments(project, source_root):
        words = value.split()
        if operation == "=":
            variables[name] = words
        elif operation == "-=":
            variables[name] = [word for word in variables.get(name, []) if word not in words]
        else:
            variables.setdefault(name, []).extend(words)
    return variables


def selectProjects(source_root: Path) -> dict:
    """Select the application and its declared subdirs dependencies in build order."""
    roots = sorted(source_root.glob("*.pro"))
    if len(roots) > 1:
        selected = [
            project
            for project in roots
            if qmakeVariables(project, source_root).get("GAME_RECOVERY_APPLICATION") == ["true"]
        ]
        if len(selected) > 1:
            raise VerificationError("Multiple reconstructed historical application projects are selected")
        if selected:
            roots = selected
    if len(roots) > 1:
        # Windows case-only renames left both Game.pro and game.pro in several trees.
        # The obsolete project names source files removed by the same refactor.
        current = []
        for project in roots:
            sources = qmakeVariables(project, source_root).get("SOURCES", [])
            if sources and all("$" not in name and (project.parent / name).is_file() for name in sources):
                current.append(project)
        if len(current) == 1:
            roots = current
    if len(roots) != 1:
        raise VerificationError(f"Expected one historical qmake project, found {len(roots)}")
    ordered = []
    visiting = set()

    def visit(project: Path) -> None:
        project = project.resolve()
        if not project.is_relative_to(source_root.resolve()) or project in visiting:
            raise VerificationError("Historical qmake subdirs escape the snapshot or have cyclic dependencies")
        visiting.add(project)
        variables = qmakeVariables(project, source_root)
        template = variables.get("TEMPLATE", ["app"])
        if template == ["subdirs"]:
            subdirs = variables.get("SUBDIRS", [])
            visited = set()

            def subdir(name: str) -> None:
                if name in visited:
                    return
                if name not in subdirs or name in visiting:
                    raise VerificationError("Historical qmake subdir dependency is missing or cyclic")
                visiting.add(name)
                for dependency in variables.get(name + ".depends", []):
                    subdir(dependency)
                location = variables.get(name + ".file") or variables.get(name + ".subdir") or [name]
                if len(location) != 1 or "$" in location[0]:
                    raise VerificationError("Historical qmake subdir needs an explicit project adapter")
                target = project.parent / location[0]
                candidates = [target] if target.suffix == ".pro" else sorted(target.glob("*.pro"))
                if len(candidates) != 1:
                    raise VerificationError(f"Expected one historical subdir project: {target}")
                visit(candidates[0])
                visiting.remove(name)
                visited.add(name)

            for name in subdirs:
                subdir(name)
        elif template in (["app"], ["lib"]):
            ordered.append((project, template[0]))
        else:
            raise VerificationError(f"Unsupported historical qmake template: {template}")
        visiting.remove(project)

    visit(roots[0])
    applications = [project for project, template in ordered if template == "app"]
    if len(applications) != 1:
        raise VerificationError(f"Expected one historical game application, found {len(applications)}")
    return {"application": applications[0], "dependencies": [project for project, kind in ordered if kind == "lib"]}


def selectRecipe(recipes: list[dict], source_root: Path, selected: str | None) -> dict:
    if selected:
        matching = [recipe for recipe in recipes if recipe["id"] == selected]
    else:
        projects = selectProjects(source_root)
        ordered = [*projects["dependencies"], projects["application"]]
        variables = [qmakeVariables(project, source_root) for project in ordered]
        links = " ".join(word for values in variables for word in values.get("LIBS", []))
        includes = " ".join(
            word for values in variables for name in ("INCLUDEPATH", "DEPENDPATH") for word in values.get(name, [])
        )
        pattern = r"python([23])(?:\.([0-9]+)|([0-9]))"
        versions = re.findall(pattern, links, re.IGNORECASE) or re.findall(pattern, includes, re.IGNORECASE)
        declared_abis = {version[0] + "." + (version[1] or version[2]) for version in versions}
        declared_files = [
            (project.parent / name).resolve()
            for project, values in zip(ordered, variables)
            for key in ("SOURCES", "HEADERS")
            for name in values.get(key, [])
        ]
        code_files = declared_files or [path for pattern in ("*.h", "*.cpp") for path in source_root.rglob(pattern)]
        code = "\n".join(
            path.read_text(errors="replace")
            for path in code_files
            if path.is_file()
            and path.is_relative_to(source_root)
            and not any(
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
    recipe = recipeForSource(matching[0], source_root)
    arguments = source_prep.preparationArguments(source_root)
    if arguments:
        recipe = {**recipe, "qmakeArguments": [*recipe.get("qmakeArguments", []), *arguments]}
    return recipe


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
    startup = validateSmokeReport(
        Path(result["smoke"]["startupReport"]), artifact_root, result.get("startupMode", "game")
    )
    evidence_dir = output_root / "evidence" / result["fingerprint"]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    supplemental = result.get("sourcePreparation", {}).get("identity", {}).get("supplementalResources")
    if supplemental:
        if supplemental.get("path") != source_prep.SUPPLEMENTAL_QRC:
            raise VerificationError("Unexpected supplemental Qt resource output")
        resource = Path(result["restoration"]["outputDir"]) / source_prep.SUPPLEMENTAL_QRC
        if hashlib.sha256(resource.read_bytes()).hexdigest() != supplemental.get("sha256"):
            raise VerificationError("Supplemental Qt resource output differs from its preparation proof")
        shutil.copyfile(resource, evidence_dir / "supplemental_images.qrc")
    reflection = result.get("sourcePreparation", {}).get("identity", {}).get("reflectionRegistration")
    if reflection:
        helper = source_prep.reflection_prep
        header = Path(result["restoration"]["outputDir"]) / helper.TARGET
        if reflection.get("path") != helper.TARGET or header.is_symlink() or header.read_bytes() != helper.HEADER:
            raise VerificationError("Reflection compatibility header differs from its reviewed bytes")
        if hashlib.sha256(header.read_bytes()).hexdigest() != reflection.get("sha256"):
            raise VerificationError("Reflection compatibility header differs from its preparation proof")
        shutil.copyfile(header, evidence_dir / helper.ATTACHMENT)
    coordinates = result.get("sourcePreparation", {}).get("identity", {}).get("coordinatesHash")
    if coordinates:
        helper = source_prep.coordinates_prep
        header = Path(result["restoration"]["outputDir"]) / helper.TARGET
        if coordinates.get("path") != helper.TARGET or header.is_symlink() or header.read_bytes() != helper.HEADER:
            raise VerificationError("Coordinate hash compatibility header differs from its reviewed bytes")
        if hashlib.sha256(header.read_bytes()).hexdigest() != coordinates.get("sha256"):
            raise VerificationError("Coordinate hash compatibility header differs from its preparation proof")
        shutil.copyfile(header, evidence_dir / helper.ATTACHMENT)
    frame_path = Path(startup["frame"]["path"])
    if not frame_path.is_absolute():
        frame_path = artifact_root / frame_path
    shutil.copyfile(frame_path, evidence_dir / "startup.png")
    shutil.copyfile(result["smoke"]["startupReport"], evidence_dir / "startup.json")
    for key in ("configure", "build", "smoke"):
        log_path = Path(result[key]["log"])
        if log_path.is_file():
            destination = evidence_dir / ("startup.log" if key == "smoke" else key + ".log")
            with destination.open("wb") as output:
                for dependency in result.get("dependencies", []) if key != "smoke" else []:
                    output.write(("\n=== " + dependency["project"] + " ===\n").encode())
                    output.write(Path(dependency[key]["log"]).read_bytes())
                output.write(log_path.read_bytes())
    preparation = result.get("sourcePreparation", {})
    if preparation.get("steps"):
        with (evidence_dir / "source-preparation.log").open("wb") as output:
            for step in preparation["steps"]:
                output.write(("\n=== " + step["name"] + " ===\n").encode())
                output.write(Path(step["log"]).read_bytes())
        writeJson(evidence_dir / "source-preparation.json", preparation)
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
        projects = selectProjects(source_root)
        recipe = selectRecipe(recipes, source_root, selected_recipe)
        environment = dict(os.environ)
        environment.update({key: str(value) for key, value in recipe.get("environment", {}).items()})
        toolchain = toolchainFingerprint(recipe, environment)
        startup = selectStartupMode(repo_root, source_commit, source_root)
        result.update(startupMode=startup["mode"], startupSelection=startup)
        preparation = source_prep.prepareSources(
            source_root, work_root / "preparation", recipe, environment, runCommand, min(build_timeout, 120)
        )
        result["sourcePreparation"] = preparation
        if preparation["status"] == "failed":
            raise VerificationError(preparation["reason"])
        supplemental = preparation["identity"].get("supplementalResources")
        if supplemental:
            startup["boundary"] = supplemental["validationBoundary"]
            result["startupCompatibility"] = "supplementalQtResources"
        reflection = preparation["identity"].get("reflectionRegistration")
        if reflection:
            if supplemental:
                raise VerificationError("Historical compatibility states unexpectedly overlap")
            startup["boundary"] = reflection["validationBoundary"]
            result["startupCompatibility"] = "parentReflectionRegistration"
        coordinates = preparation["identity"].get("coordinatesHash")
        if coordinates:
            if supplemental or reflection:
                raise VerificationError("Historical compatibility states unexpectedly overlap")
            startup["boundary"] = coordinates["validationBoundary"]
            result["startupCompatibility"] = "originalCoordinateHash"
        resource_aliases = preparation["identity"].get("resourceAliases")
        if resource_aliases:
            if supplemental or reflection or coordinates:
                raise VerificationError("Historical compatibility states unexpectedly overlap")
            startup["boundary"] = resource_aliases["validationBoundary"]
            result["startupCompatibility"] = "renamedResourceAliases"
        conflicts = preparation["identity"].get("conflictResolution")
        if conflicts:
            if supplemental or reflection or coordinates or resource_aliases:
                raise VerificationError("Historical compatibility states unexpectedly overlap")
            startup["boundary"] = conflicts["validationBoundary"]
            result["startupCompatibility"] = "whitespaceConflictResolution"
        forwarders = preparation["identity"].get("forwardingHeaders")
        if forwarders:
            if supplemental or reflection or coordinates or resource_aliases or conflicts:
                raise VerificationError("Historical compatibility states unexpectedly overlap")
            startup["boundary"] = forwarders["validationBoundary"]
            result["startupCompatibility"] = "mergedHeaderForwarders"
        refactor = preparation["identity"].get("refactorCompletion")
        if refactor:
            if supplemental or reflection or coordinates or resource_aliases or conflicts or forwarders:
                raise VerificationError("Historical compatibility states unexpectedly overlap")
            startup["boundary"] = refactor["validationBoundary"]
            result["startupCompatibility"] = "unfinishedRefactorCompletion"
        runtime_directories = source_prep.runtimeDirectoryPlan(source_root)
        adapter = prepareSmokeAdapter(source_root, work_root / "observer", startup["mode"])
        libraries = prepareLibraryAliases(source_root, work_root / "observer")
        identity = {
            "sourceTree": tree["tree"],
            "startupSelection": startup,
            "sourcePreparation": preparation["identity"],
            "runtimePreparation": {"directories": runtime_directories},
            "recipe": recipe,
            "toolchain": toolchain,
            "toolchainImage": environment.get("GAME_RECOVERY_TOOLCHAIN_ID"),
            "adapter": hashlib.sha256(SMOKE_SOURCE.read_bytes()).hexdigest(),
            "fileLookup": hashlib.sha256(WINDOWS_PATHS_SOURCE.read_bytes()).hexdigest(),
            "libraryAliases": libraries["aliases"],
            "verifier": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "restorer": hashlib.sha256((REPO_ROOT / "scripts/recover_history.py").read_bytes()).hexdigest(),
            "adapterConfig": adapter["configSha256"],
            # The exact restored file set; unrelated override edits must not invalidate verified results.
            "restoredFiles": result["restoration"]["restoredFilesFingerprint"],
        }
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        result.update(
            {
                "project": projects["application"].relative_to(source_root).as_posix(),
                "libraryAliases": libraries,
                "fingerprint": fingerprint,
                "recipe": recipe,
                "toolchain": toolchain,
                "toolchainImage": identity["toolchainImage"],
                "adapter": adapter,
            }
        )
        cached_path = output_root / "results" / (fingerprint + ".json")
        if cached_path.is_file():
            cached = json.loads(cached_path.read_text())
            if cached.get("status") == "success":
                validateSmokeReport(
                    Path(cached["smoke"]["startupReport"]), Path(cached["artifactDir"]), startup["mode"]
                )
                cached = {**cached, "sourceCommit": source_commit, "sourceCommits": tree["commits"], "resumed": True}
                exportEvidence(cached, output_root)
                return cached
        build_base = work_root / "build"
        build_base.mkdir()
        dependencies = []
        for index, project in enumerate(projects["dependencies"]):
            dependency_root = build_base / project.relative_to(source_root).parent
            dependency_root.mkdir(parents=True, exist_ok=True)
            dependency = {"project": project.relative_to(source_root).as_posix()}
            dependencies.append(dependency)
            result["dependencies"] = dependencies
            dependency["configure"] = runCommand(
                [
                    recipe.get("qmakeCommand", "qmake"),
                    str(project),
                    "-o",
                    str(dependency_root / "Makefile"),
                    *recipe.get("qmakeArguments", []),
                ],
                dependency_root,
                environment,
                build_timeout,
                work_root / f"dependency-{index}-configure.log",
            )
            if dependency["configure"]["returnCode"] != 0:
                raise VerificationError(f"Historical dependency configuration failed: {dependency['project']}")
            dependency["build"] = runCommand(
                [recipe.get("makeCommand", "make"), f"-j{jobs}"],
                dependency_root,
                environment,
                build_timeout,
                work_root / f"dependency-{index}-build.log",
            )
            if dependency["build"]["returnCode"] != 0:
                raise VerificationError(f"Historical dependency compilation/linking failed: {dependency['project']}")
        build_root = build_base / projects["application"].relative_to(source_root).parent
        build_root.mkdir(parents=True, exist_ok=True)
        configure = [
            recipe.get("qmakeCommand", "qmake"),
            str(projects["application"]),
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
        if libraries["aliases"]:
            configure.append("LIBS+=-L" + libraries["directory"])
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
        preload = work_root / "observer" / "libwindowspaths.so"
        result["fileLookup"] = runCommand(
            [
                recipe.get("compilerCommand", "g++"),
                "-shared",
                "-fPIC",
                "-O2",
                "-std=c++11",
                "-o",
                str(preload),
                str(WINDOWS_PATHS_SOURCE),
                "-ldl",
            ],
            work_root,
            environment,
            build_timeout,
            work_root / "file-lookup.log",
        )
        if result["fileLookup"]["returnCode"] != 0:
            raise VerificationError("Could not build the case-insensitive file lookup shim; inspect file-lookup.log")
        result["fileLookup"]["semantics"] = "Windows-style case-insensitive file lookup for the game process"
        artifact_dir = work_root / "smoke"
        smoke_environment = dict(environment)
        if dependencies:
            library_dirs = [
                str(build_base / project.relative_to(source_root).parent) for project in projects["dependencies"]
            ]
            result["runtimeLibraryDirectories"] = library_dirs
            smoke_environment["LD_LIBRARY_PATH"] = ":".join(
                [*library_dirs, environment.get("LD_LIBRARY_PATH", "")]
            ).rstrip(":")
        if runtime_directories:
            result["runtimePreparation"] = source_prep.prepareRuntimeDirectories(
                projects["application"].parent, runtime_directories
            )
        result["smoke"] = runSmoke(
            ["env", "LD_PRELOAD=" + str(preload), str(executable.resolve())],
            projects["application"].parent,
            artifact_dir,
            environment=smoke_environment,
            timeout=timeout,
            startup_mode=startup["mode"],
            console="shutdown" in adapter,
        )
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
    parser.add_argument("--overrides", type=Path)
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
        override_path = args.overrides or REPO_ROOT / "recovery/overrides.json"
        if args.overrides is not None and not override_path.is_file():
            raise VerificationError(f"Requested recovery overrides do not exist: {override_path}")
        if override_path.exists():
            overrides = json.loads(override_path.read_text(encoding="utf-8"))
            overrides["_baseDir"] = str(override_path.resolve().parent)
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
