#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run surviving historical property generators on isolated build-source copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

EXPECTED_PYTHON_VERSION = "Python 2.7.18"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
CPP_TOKENS = re.compile(
    r'/\*.*?\*/|//[^\n]*|(?:u8|u|U|L)?R"(?P<delimiter>[^\s()\\]{0,16})\(.*?\)(?P=delimiter)"'
    r'|"(?:\\.|[^"\\\r\n])*"|\'(?:\\.|[^\'\\\r\n])*\''
    r"|(?P<conditional>^[ \t]*#[ \t]*(?:if|ifdef|ifndef|elif|else|endif)\b[^\r\n]*)"
    r'|(?P<include>^[ \t]*#[ \t]*include[ \t]*"(?P<path>[^"\r\n]+)")'
    r'|(?P<saveWriter>\bfopen\s*\(\s*"save/game\.sav"\s*,\s*"w\+"\s*\))',
    re.MULTILINE | re.DOTALL,
)


def runtimeDirectoryPlan(source_root: Path) -> list[dict]:
    required = []
    for source in sorted(source_root.rglob("*.cpp")):
        if not source.is_file() or source.is_symlink():
            continue
        data = source.read_bytes()
        text = data.decode("utf-8", errors="surrogateescape")
        for token in CPP_TOKENS.finditer(text):
            if token.group("saveWriter"):
                required.append(
                    {
                        "source": source.relative_to(source_root).as_posix(),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "line": text.count("\n", 0, token.start()) + 1,
                        "operation": 'fopen("save/game.sav", "w+")',
                    }
                )
    return [{"path": "save", "requiredBy": required}] if required else []


def prepareRuntimeDirectories(runtime_root: Path, plan: list[dict]) -> dict:
    """Create only the empty save-directory prerequisite; preserve every existing save byte."""
    directories = []
    for entry in plan:
        if entry.get("path") != "save" or not entry.get("requiredBy"):
            raise ValueError("Historical runtime directory preparation requires an evidenced save-directory request")
        path = runtime_root / "save"
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError("Historical save directory is symlinked or is not a directory")
        existed = path.is_dir()
        if not existed:
            path.mkdir()
        directories.append({"path": "save", "created": not existed, "preservedExisting": existed})
    return {"status": "ready", "directories": directories, "identity": {"directories": plan}}


def includeOverlays(source_root: Path) -> list[dict]:
    """Plan literal quoted include repairs, excluding comments, strings and definitely inactive branches."""
    root = source_root.resolve()
    overlays = []
    for source in sorted(source_root.rglob("*")):
        if source.suffix.lower() not in SOURCE_SUFFIXES or not source.is_file():
            continue
        data = source.read_bytes()
        text = data.decode("utf-8", errors="surrogateescape")
        branches = []
        edits = []
        for token in CPP_TOKENS.finditer(text):
            if token.group("conditional"):
                directive = re.match(r"\s*#\s*(\w+)\s*(.*)", token.group())
                name, expression = directive.groups()
                expression = re.sub(r"/\*.*?\*/|//.*", "", expression).strip()
                if name in ("if", "ifdef", "ifndef"):
                    condition = {"0": False, "1": True}.get(expression) if name == "if" else None
                    branches.append({"taken": condition, "active": condition is not False})
                elif name in ("elif", "else") and branches:
                    previous = branches[-1]["taken"]
                    condition = {"0": False, "1": True}.get(expression) if name == "elif" else True
                    branches[-1]["active"] = previous is not True and condition is not False
                    branches[-1]["taken"] = True if previous is True or condition is True else None
                elif name == "endif" and branches:
                    branches.pop()
                continue
            name = token.group("path")
            if not name or "\\" not in name or any(not branch["active"] for branch in branches):
                continue
            normalized = name.replace("\\", "/")
            if normalized.startswith("/") or ":" in normalized:
                raise ValueError(f"Windows include path escapes the historical source tree: {name}")
            candidates = set()
            escaped = False
            for directory in (source.parent, source_root):
                candidate = directory / normalized
                resolved = candidate.resolve()
                if not resolved.is_relative_to(root):
                    escaped = True
                    continue
                if candidate.is_file():
                    if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != root):
                        raise ValueError(f"Windows include path crosses a symlink: {name}")
                    candidates.add(resolved)
            if not candidates:
                reason = "escapes the historical source tree" if escaped else "does not resolve to an existing header"
                raise ValueError(f"Windows include path {reason}: {name}")
            if len(candidates) != 1 or source.is_symlink():
                raise ValueError(f"Windows include path has ambiguous or symlinked source/target: {name}")
            edits.append(
                {
                    "start": token.start("path"),
                    "end": token.end("path"),
                    "line": text.count("\n", 0, token.start()) + 1,
                    "originalInclude": name,
                    "preparedInclude": normalized,
                    "resolvedHeader": next(iter(candidates)).relative_to(root).as_posix(),
                }
            )
        if edits:
            for edit in reversed(edits):
                text = text[: edit["start"]] + edit["preparedInclude"] + text[edit["end"] :]
            overlays.append(
                {
                    "path": source.relative_to(source_root).as_posix(),
                    "data": text.encode("utf-8", "surrogateescape"),
                    "includes": [
                        {key: value for key, value in edit.items() if key not in ("start", "end")} for edit in edits
                    ],
                }
            )
    return overlays


def preparationRequired(source_root: Path) -> bool:
    return (source_root / "preprocessor.py").is_file() or bool(includeOverlays(source_root))


def sourceManifest(source_root: Path) -> dict:
    files = {}
    for path in sorted(source_root.rglob("*")):
        if path.is_symlink():
            data = os.readlink(path).encode()
            kind = "symlink"
        elif path.is_file():
            data = path.read_bytes()
            kind = "file"
        else:
            continue
        files[path.relative_to(source_root).as_posix()] = {"sha256": hashlib.sha256(data).hexdigest(), "kind": kind}
    return files


def prepareSources(
    source_root: Path, output_root: Path, recipe: dict, environment: dict, run_command, timeout: float = 120
) -> dict:
    """Record derived build outputs without changing the restored-input identity."""
    implementation = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {
        "status": "not-required",
        "steps": [],
        "outputs": [],
        "identity": {"implementationSha256": implementation},
    }
    generator = source_root / "preprocessor.py"
    include_overlays = includeOverlays(source_root)
    if not generator.is_file() and not include_overlays:
        return result
    output_root.mkdir(parents=True, exist_ok=True)
    before = sourceManifest(source_root)
    if include_overlays:
        recorded = []
        for overlay in include_overlays:
            (source_root / overlay["path"]).write_bytes(overlay["data"])
            recorded.append(
                {
                    "path": overlay["path"],
                    "includes": overlay["includes"],
                    "beforeSha256": before[overlay["path"]]["sha256"],
                    "afterSha256": hashlib.sha256(overlay["data"]).hexdigest(),
                }
            )
        log = output_root / "include-separators.log"
        log.write_text(json.dumps(recorded, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["steps"].append(
            {
                "name": "windowsIncludeSeparators",
                "command": ["history_source_prep.py", "normalize-quoted-includes"],
                "returnCode": 0,
                "timedOut": False,
                "log": str(log),
            }
        )
        result["identity"]["includeSeparators"] = recorded
        result["identity"]["includeReplaySha256"] = hashlib.sha256(
            Path(__file__).with_name("history_prepare_includes.py").read_bytes()
        ).hexdigest()
        result["outputs"] = [
            {
                "path": overlay["path"],
                "before": before[overlay["path"]],
                "after": {"kind": "file", "sha256": hashlib.sha256(overlay["data"]).hexdigest()},
                "purpose": "Windows include separators on an isolated build-source copy",
            }
            for overlay in include_overlays
        ]
        result["identity"]["outputs"] = result["outputs"]
    if not generator.is_file():
        after = sourceManifest(source_root)
        outputs = [
            {
                "path": name,
                "before": before[name],
                "after": after[name],
                "purpose": "Windows include separators on an isolated build-source copy",
            }
            for name in before
            if before[name] != after[name]
        ]
        result.update({"status": "success", "outputs": outputs})
        result["identity"]["outputs"] = outputs
        return result
    if generator.is_symlink():
        raise ValueError("Historical property generator must be a regular snapshot file")
    if recipe.get("pythonAbi") != "2.7":
        raise ValueError("Historical property generator requires the locked Python 2.7 recipe")
    python_home = Path(recipe.get("environment", {}).get("PYTHONHOME", ""))
    if not python_home.is_absolute():
        raise ValueError("Historical property generator requires a pinned absolute PYTHONHOME")
    interpreter = python_home / "bin/python2.7"
    inputs = ["preprocessor.py", "classes.json"]
    if "macro.conf" in generator.read_text(encoding="utf-8"):
        inputs.append("macro.conf")
    for name in inputs:
        path = source_root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Historical source preparation input is absent or not regular: {name}")
    prepared_environment = {**environment, "PYTHONDONTWRITEBYTECODE": "1"}
    version_log = output_root / "interpreter.log"
    version = run_command([str(interpreter), "--version"], source_root, prepared_environment, timeout, version_log)
    result["steps"].append({"name": "interpreter", **version})
    version_text = version_log.read_text(encoding="utf-8", errors="replace").strip()
    if version["returnCode"] != 0 or version.get("timedOut") or version_text != EXPECTED_PYTHON_VERSION:
        return {
            **result,
            "status": "failed",
            "reason": "Historical source preparation interpreter differs from Python 2.7.18",
        }
    execution = run_command(
        [str(interpreter), "-B", str(generator)],
        source_root,
        prepared_environment,
        timeout,
        output_root / "generator.log",
    )
    result["steps"].append({"name": "generator", **execution})
    after = sourceManifest(source_root)
    outputs = []
    for name in sorted(set(before) | set(after)):
        if before.get(name) != after.get(name):
            outputs.append(
                {
                    "path": name,
                    "before": before.get(name),
                    "after": after.get(name),
                    "purpose": "historical property generation",
                }
            )
    result["outputs"] = outputs
    result["identity"].update(
        {
            "interpreter": version_text,
            "inputs": {name: before[name] for name in inputs},
            "outputs": outputs,
        }
    )
    unexpected = [
        entry["path"]
        for entry in outputs
        if not (
            entry["after"]
            and entry["after"]["kind"] == "file"
            and (
                entry["path"] == "gen/prop.h"
                or (entry["path"].startswith("src/") and entry["path"].endswith(".h"))
                or entry["path"] in {overlay["path"] for overlay in include_overlays}
            )
        )
    ]
    if execution["returnCode"] != 0 or execution.get("timedOut"):
        return {**result, "status": "failed", "reason": "Historical property generator failed; inspect generator.log"}
    if unexpected:
        return {
            **result,
            "status": "failed",
            "reason": "Historical property generator changed unexpected paths: " + ", ".join(unexpected),
        }
    if not (source_root / "gen/prop.h").is_file():
        return {**result, "status": "failed", "reason": "Historical property generator did not produce gen/prop.h"}
    result["status"] = "success"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--recipes", required=True, type=Path)
    parser.add_argument("--recipe", required=True)
    args = parser.parse_args()
    try:
        from scripts import verify_history as verify
    except ModuleNotFoundError:
        import verify_history as verify
    recipes = verify.loadRecipes(args.recipes)
    recipe = verify.selectRecipe(recipes, args.source_root, args.recipe)
    environment = {**os.environ, **recipe.get("environment", {})}
    result = prepareSources(args.source_root, args.output_dir, recipe, environment, verify.runCommand)
    verify.writeJson(args.output_dir / "preparation.json", result)
    print(json.dumps({key: result[key] for key in ("status", "outputs")}))
    return 0 if result["status"] in ("success", "not-required") else 1


if __name__ == "__main__":
    raise SystemExit(main())
