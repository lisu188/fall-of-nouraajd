#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Link a focused state regression to objects from an accepted historical native build."""

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compileArguments(template, source, output):
    command = list(template)
    assert command[-1].endswith(".cpp") and "-c" in command
    command[-1:] = ["-x", "c++", str(source)]
    command[command.index("-o") + 1] = str(output)
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--toolchain-rootfs", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--template", default="Sorcerer")
    parser.add_argument("--replacement-creature", type=Path)
    parser.add_argument("--replacement-map", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo_root.resolve()))
    from scripts import history_rootfs

    report = json.loads(args.verification.read_text())
    if report.get("status") != "success":
        parser.error(
            "The harness requires a successful historical build/startup report"
        )
    source = Path(report["restoration"]["outputDir"]).resolve(strict=True)
    build_log = Path(report["build"]["log"]).resolve(strict=True)
    build = build_log.parent / "build"
    if not build.is_dir() or not (build / "main.o").is_file():
        parser.error(
            "Retained build objects are required; compact exported evidence alone is insufficient"
        )
    image_id = history_rootfs.loadMetadata(args.toolchain_rootfs)["imageId"]
    if image_id != report.get("toolchainImage"):
        parser.error(
            "Regression rootfs image must match the accepted native build image"
        )
    output = args.output_dir.absolute()
    if output.exists() or output.is_symlink():
        parser.error("Output directory must be new")
    if output.is_relative_to(source) or output.is_relative_to(build):
        parser.error(
            "Regression output must be separate from accepted source/build inputs"
        )
    output.mkdir(parents=True)
    fixture = (
        args.repo_root.resolve()
        / "tests/fixtures/history-state/history_state_roundtrip.cpp"
    ).resolve(strict=True)
    commands = [
        shlex.split(line)
        for line in build_log.read_text().splitlines()
        if line.startswith("g++")
    ]
    template = next(
        command
        for command in commands
        if "-c" in command and command[-1].endswith("/main.cpp")
    )
    link = list(
        next(
            command
            for command in reversed(commands)
            if "-o" in command and "-c" not in command
        )
    )
    read_only = [source.parent, fixture.parent]
    replacements = {}
    for option, name in [
        (args.replacement_creature, "creature.o"),
        (args.replacement_map, "map.o"),
    ]:
        if option:
            path = option.resolve(strict=True)
            if not path.is_file():
                parser.error(
                    "Replacement must be an explicit regular missing-source reconstruction"
                )
            read_only.append(path.parent)
            replacements[name] = path
    proof = {
        "schemaVersion": 1,
        "sourceCommit": report["sourceCommit"],
        "restoredFilesFingerprint": report["restoration"]["restoredFilesFingerprint"],
        "toolchainImage": history_rootfs.loadMetadata(args.toolchain_rootfs)["imageId"],
        "fixtureSha256": sha(fixture),
        "runnerSha256": sha(Path(__file__)),
        "verificationSha256": sha(args.verification),
        "replacements": {
            name: {"path": str(path), "sha256": sha(path)}
            for name, path in replacements.items()
        },
        "steps": [],
        "boundary": "Real historical classes/factories/state callbacks; this does not establish gameplay or UI parity",
    }
    environment = {"PATH": "/usr/lib/x86_64-linux-gnu/qt5/bin:/usr/bin:/bin"}

    def run(command, cwd, name):
        result = history_rootfs.runRootfs(
            args.toolchain_rootfs,
            command,
            cwd,
            read_only,
            [output],
            environment=environment,
            timeout=120,
        )
        (output / (name + ".log")).write_text(result.stdout + result.stderr)
        proof["steps"].append(
            {"name": name, "command": command, "returnCode": result.returncode}
        )
        if result.returncode:
            raise RuntimeError(name + " failed; see " + str(output / (name + ".log")))
        return result

    try:
        harness_object = output / "state_roundtrip.o"
        run(
            compileArguments(template, fixture, harness_object),
            build,
            "compile-harness",
        )
        historical_main = output / "historical_main.o"
        command = compileArguments(template, source / "main.cpp", historical_main)
        command.insert(-1, "-Dmain=recoveryHistoricalMain")
        run(command, build, "compile-original-registration")
        link[link.index("-o") + 1] = str(output / "state-roundtrip")
        if link.count("main.o") != 1 or link.count("game_startup.o") != 1:
            raise RuntimeError(
                "Expected exactly one original main and one startup observer object"
            )
        link[link.index("main.o")] = str(historical_main)
        link.remove("game_startup.o")
        link.insert(1, str(harness_object))
        for name, path in replacements.items():
            if link.count(name) != 1:
                raise RuntimeError("Replacement object is not unique: " + name)
            target = output / ("replacement-" + name)
            command = compileArguments(template, path, target)
            original_directory = source / (
                "creatures" if name == "creature.o" else "map"
            )
            command[-1:-1] = ["-iquote", str(original_directory)]
            run(command, build, "compile-replacement-" + name)
            link[link.index(name)] = str(target)
        run(link, build, "link-harness")
        runtime = output / "runtime"
        runtime.mkdir()
        config = source / "config"
        if config.is_dir():
            if config.is_symlink() or any(
                path.is_symlink() for path in config.rglob("*")
            ):
                raise RuntimeError("Refusing symlinked runtime configuration")
            shutil.copytree(config, runtime / "config")
        result = run(
            [
                "env",
                "LIBGL_ALWAYS_SOFTWARE=1",
                "QT_OPENGL=software",
                "xvfb-run",
                "-a",
                "--server-args=-screen 0 1920x1080x24",
                str(output / "state-roundtrip"),
                args.template,
            ],
            runtime,
            "native-state-roundtrip",
        )
        native = next(
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.startswith('{"status"')
        )
        if native.get("status") != "success" or not all(
            native.get("checks", {}).values()
        ):
            raise RuntimeError("Native regression did not report all real state checks")
        proof.update(status="success", checks=native["checks"])
    except Exception as error:
        proof.update(status="failed", reason=str(error))
    finally:
        (output / "regression.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))
    return 0 if proof.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
