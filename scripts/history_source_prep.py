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

try:
    from scripts import history_prepare_reflection as reflection_prep
    from scripts import history_prepare_coordinates as coordinates_prep
    from scripts import history_prepare_resource_aliases as aliases_prep
except ModuleNotFoundError:
    import history_prepare_reflection as reflection_prep
    import history_prepare_coordinates as coordinates_prep
    import history_prepare_resource_aliases as aliases_prep

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


SUPPLEMENTAL_QRC = "recovery_supplemental_images.qrc"
SUPPLEMENTAL_QMAKE_ARGUMENT = "RESOURCES+=$$_PRO_FILE_PWD_/" + SUPPLEMENTAL_QRC
SUPPLEMENTAL_INPUTS = {
    "animation/animationprovider.cpp": "9bb143c1a9f29e7b07da200d23b003db36ccc8a12b4a9559e1ff86e3a672ba46",
    "config/interactions.json": "9dc5e72dc28ede2c1ed627d09b83bca9587cd3dedd99c6c9a8e950a1ec364b34",
    "images.qrc": "41b1e493f0cbb29996abaff166808e22d77476eefd48a42957e37cfe6e09153a",
}
SUPPLEMENTAL_IMAGES = {
    "images/interactions/abyssalshadows/0.png": "07cb42c9b283fd4c04a1486e3dc207bf631fef02dd774ae6e29bb8950bd02398",
    "images/interactions/armorofendlesswinter/0.png": "a3ef4298d68e1a3f3e02010362fba3c1a1fc34808930c816ccead4eb2378df8d",
    "images/interactions/attack/0.png": "43ab0a5cd12951a3be7ecf547b9d154acf6da949763a24018dbbe7f156579b91",
    "images/interactions/backstab/0.png": "c89a43bb6def8d290e2147abbb40374c5133d52c9f46f3843e2b4ca913ab3663",
    "images/interactions/barrier/0.png": "790132a8aef56777672ea70d2cde861d92a9c6bdca3ddd6b20e38df45945535e",
    "images/interactions/bloodlash/0.png": "853187c73a72f7250c1374c2817d5dbcadae099b9cbf0a5df327285ad6a66d1b",
    "images/interactions/bloodthirst/0.png": "dffa9919ce78ea9c630049f9f5aae6db025814c7a6f5fec8d28b20d66b7ea52c",
    "images/interactions/chaosblast/0.png": "255c6409d532ed1ca2539d6d8340680b3a223c7199a0a1ff0cdfd5ff20d4ed8a",
    "images/interactions/chloroform/0.png": "4246708ff5abd3f1e71af3157b331e42785fdde83ec757ec3411faf7eb6b5735",
    "images/interactions/deathstrike/0.png": "c0b87a24c16574cd27b5239d0b443c050440085d3978ba748e4809c4f48fcaf0",
    "images/interactions/devour/0.png": "8c85a01931f710885837616bae6891f3f98eea25707f595178752605f791ad00",
    "images/interactions/doubleattack/0.png": "c62e498185044edc2f35b9e4025800bc8f99b9af8fe5c899947955008e28500b",
    "images/interactions/endlesspain/0.png": "f893283c0a7253076f8becd9b3ca496959bed2d7a8c113407e1112ea6b5500da",
    "images/interactions/frostbolt/0.png": "320b12e60d00ec6c19d0b2283656a7867cb8709357426198c39ea200aa7d2a94",
    "images/interactions/lethalpoison/0.png": "bbed760353474361861bac85752f03822e4a347b83e8e94bebb5d84b9abfaf73",
    "images/interactions/magicmissile/0.png": "3d330005b87da024d4a9efd312fc29b67501296cf5013625c7a696c7b623b69b",
    "images/interactions/mutilation/0.png": "aa4f24b9800f68b0fd2055efb1ffeb4b58338bf90c349e8ae22d4dfd8cd7964a",
    "images/interactions/shadowbolt/0.png": "13cfabf00bef6f2780dea5906e83a4462a2a096a0b3bbd425256fcbf93e2b941",
    "images/interactions/sneakattack/0.png": "5531765521c55e08750bbd5b829fd5e49990d0149b991afc1ca8c33a54e5775f",
    "images/interactions/strike/0.png": "21edb56961749e8f4ebbf8bde378492d8b4ae64ddb20ab519fcbe5cc7ba57c06",
    "images/interactions/stun/0.png": "a7dd3bc29c13fe238c2bbd3c3fe2832f4eba1c4f231f2bf880dfae22a63f76ed",
}
SUPPLEMENTAL_PROVENANCE = {
    "donorCommit": "95b01c98de4f4b1e49ec72e367e295720898efeb",
    "donorManifestSha256": "eb38ec7532942928d923a4fd1be6654bcb2cd2056ae009795cdfa9213fb9f013",
    "sourceCommit": "83f5addfdbc6f59cc91ac0a9fee63e7131b6b7d8",
}


def resourceInput(source_root: Path, name: str) -> bytes | None:
    path = source_root / name
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != source_root):
        raise ValueError(f"Supplemental Qt resource input crosses a symlink: {name}")
    if not path.is_file():
        return None
    if not path.resolve().is_relative_to(source_root.resolve()):
        raise ValueError(f"Supplemental Qt resource input escapes the source tree: {name}")
    return path.read_bytes()


def supplementalResourcePlan(source_root: Path) -> dict | None:
    """Recognize only the exact original #98 resource omission and pin its existing image bytes."""
    for name, expected in SUPPLEMENTAL_INPUTS.items():
        data = resourceInput(source_root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            return None
    for name, expected in SUPPLEMENTAL_IMAGES.items():
        data = resourceInput(source_root, name)
        if data is None or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Supplemental Qt resource image differs from its original bytes: {name}")
    data = (
        '<RCC>\n    <qresource prefix="/">\n'
        + "".join(f"        <file>{name}</file>\n" for name in sorted(SUPPLEMENTAL_IMAGES))
        + "    </qresource>\n</RCC>\n"
    ).encode()
    return {
        "path": SUPPLEMENTAL_QRC,
        "sha256": hashlib.sha256(data).hexdigest(),
        "inputs": {**SUPPLEMENTAL_INPUTS, **SUPPLEMENTAL_IMAGES},
        "qmakeArgument": SUPPLEMENTAL_QMAKE_ARGUMENT,
        "provenance": SUPPLEMENTAL_PROVENANCE,
        "validationBoundary": "Game startup with supplemental Qt resource compatibility; original manifest unchanged",
        "resourceReplaySha256": hashlib.sha256(
            Path(__file__).with_name("history_prepare_resources.py").read_bytes()
        ).hexdigest(),
        "data": data,
    }


def preparationArguments(source_root: Path) -> list[str]:
    """Use the same explicit resource argument in workbench and observer builds."""
    arguments = [SUPPLEMENTAL_QMAKE_ARGUMENT] if supplementalResourcePlan(source_root) else []
    if reflection_prep.reflectionPlan(source_root):
        arguments.append(reflection_prep.ARGUMENT)
    if coordinates_prep.coordinateHashPlan(source_root):
        arguments.append(coordinates_prep.ARGUMENT)
    return arguments


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
    return (
        (source_root / "preprocessor.py").is_file()
        or bool(includeOverlays(source_root))
        or supplementalResourcePlan(source_root) is not None
        or reflection_prep.reflectionPlan(source_root) is not None
        or coordinates_prep.coordinateHashPlan(source_root) is not None
        or aliases_prep.resourceAliasPlan(source_root) is not None
    )


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
    supplement = supplementalResourcePlan(source_root)
    reflection = reflection_prep.reflectionPlan(source_root)
    coordinates = coordinates_prep.coordinateHashPlan(source_root)
    resource_aliases = aliases_prep.resourceAliasPlan(source_root)
    if coordinates:
        target = source_root / coordinates["path"]
        if target.is_symlink() or (
            target.exists() and (not target.is_file() or target.read_bytes() != coordinates["data"])
        ):
            raise ValueError("Coordinate hash compatibility output is symlinked or already differs")
    if reflection:
        target = source_root / reflection["path"]
        if target.is_symlink() or (
            target.exists() and (not target.is_file() or target.read_bytes() != reflection["data"])
        ):
            raise ValueError("Reflection compatibility output is symlinked or already differs")
    if supplement:
        target = source_root / supplement["path"]
        if target.is_symlink():
            raise ValueError("Supplemental Qt resource output is symlinked")
        if target.exists() and (not target.is_file() or target.read_bytes() != supplement["data"]):
            raise ValueError("Supplemental Qt resource output already exists with different bytes")
    if (
        not generator.is_file()
        and not include_overlays
        and not supplement
        and not reflection
        and not coordinates
        and not resource_aliases
    ):
        return result
    output_root.mkdir(parents=True, exist_ok=True)
    before = sourceManifest(source_root)
    if supplement:
        target = source_root / supplement["path"]
        if target.is_symlink():
            raise ValueError("Supplemental Qt resource output is symlinked")
        target.write_bytes(supplement["data"])
        identity = {key: value for key, value in supplement.items() if key != "data"}
        result["identity"]["supplementalResources"] = identity
        result["qmakeArguments"] = [supplement["qmakeArgument"]]
        log = output_root / "supplemental-resources.log"
        log.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["steps"].append(
            {
                "name": "supplementalResources",
                "command": ["history_source_prep.py", "generate-supplemental-qrc"],
                "returnCode": 0,
                "timedOut": False,
                "log": str(log),
            }
        )
    if reflection:
        reflection_prep.writeHeader(source_root, reflection["data"])
        identity = {key: value for key, value in reflection.items() if key != "data"}
        result["identity"]["reflectionRegistration"] = identity
        result.setdefault("qmakeArguments", []).append(reflection["qmakeArgument"])
        log = output_root / "reflection-registration.log"
        log.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["steps"].append(
            {
                "name": "reflectionRegistration",
                "command": ["history_source_prep.py", "prepare-reflection-registration"],
                "returnCode": 0,
                "timedOut": False,
                "log": str(log),
            }
        )
    if coordinates:
        coordinates_prep.writeHeader(source_root, coordinates["data"])
        identity = {key: value for key, value in coordinates.items() if key != "data"}
        result["identity"]["coordinatesHash"] = identity
        result.setdefault("qmakeArguments", []).append(coordinates["qmakeArgument"])
        log = output_root / "coordinates-hash.log"
        log.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["steps"].append(
            {
                "name": "coordinatesHash",
                "command": ["history_source_prep.py", "prepare-coordinates-hash"],
                "returnCode": 0,
                "timedOut": False,
                "log": str(log),
            }
        )
    if resource_aliases:
        aliases_prep.writeAliases(source_root, resource_aliases["data"])
        identity = {key: value for key, value in resource_aliases.items() if key != "data"}
        result["identity"]["resourceAliases"] = identity
        log = output_root / "resource-aliases.log"
        log.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["steps"].append(
            {
                "name": "resourceAliases",
                "command": ["history_source_prep.py", "prepare-resource-aliases"],
                "returnCode": 0,
                "timedOut": False,
                "log": str(log),
            }
        )
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
                "before": before.get(name),
                "after": after.get(name),
                "purpose": (
                    "supplemental Qt resources"
                    if name == SUPPLEMENTAL_QRC
                    else (
                        "immediate-parent reflection registration compatibility"
                        if name == reflection_prep.TARGET
                        else (
                            "coordinate hashing delegated to original CoordsHasher"
                            if name == coordinates_prep.TARGET
                            else (
                                "manifest-named alias of an original renamed resource"
                                if resource_aliases and name in aliases_prep.ALIASES
                                else "Windows include separators on an isolated build-source copy"
                            )
                        )
                    )
                ),
            }
            for name in sorted(set(before) | set(after))
            if (
                before.get(name) != after.get(name)
                or (supplement and name == SUPPLEMENTAL_QRC)
                or (reflection and name == reflection_prep.TARGET)
                or (coordinates and name == coordinates_prep.TARGET)
            )
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
                or (supplement and entry["path"] == SUPPLEMENTAL_QRC)
                or (reflection and entry["path"] == reflection_prep.TARGET)
                or (coordinates and entry["path"] == coordinates_prep.TARGET)
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
