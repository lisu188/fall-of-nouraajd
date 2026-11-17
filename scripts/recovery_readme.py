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
import shlex
import xml.etree.ElementTree as ET

try:
    from scripts import history_source_prep as source_prep
    from scripts.verify_history import (
        CONSOLE_LOOP_SOURCE,
        CONSOLE_LOOPS,
        CONSOLE_SHUTDOWN_BOUNDARY,
        EDITOR_CHECKS,
        REQUIRED_CHECKS,
        VerificationError,
        validatePng,
        verifiedStartupMode,
    )
except ModuleNotFoundError:
    import history_source_prep as source_prep
    from verify_history import (
        CONSOLE_LOOP_SOURCE,
        CONSOLE_LOOPS,
        CONSOLE_SHUTDOWN_BOUNDARY,
        EDITOR_CHECKS,
        REQUIRED_CHECKS,
        VerificationError,
        validatePng,
        verifiedStartupMode,
    )


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


def supplementalResourceAttachments(report: dict, preparation: dict, evidence_dir: Path) -> dict[str, bytes]:
    supplement = preparation.get("identity", {}).get("supplementalResources", {})
    expected_inputs = {**source_prep.SUPPLEMENTAL_INPUTS, **source_prep.SUPPLEMENTAL_IMAGES}
    boundary = "Game startup with supplemental Qt resource compatibility; original manifest unchanged"
    if (
        report.get("startupCompatibility") != "supplementalQtResources"
        or report.get("startupSelection", {}).get("boundary") != boundary
        or supplement.get("validationBoundary") != boundary
        or supplement.get("path") != source_prep.SUPPLEMENTAL_QRC
        or supplement.get("qmakeArgument") != source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT
        or preparation.get("qmakeArguments") != [source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT]
        or supplement.get("inputs") != expected_inputs
        or supplement.get("provenance") != source_prep.SUPPLEMENTAL_PROVENANCE
    ):
        raise VerificationError("Supplemental resource evidence differs from the reviewed original inputs and boundary")
    helper = Path(__file__).with_name("history_prepare_resources.py").read_bytes()
    if hashlib.sha256(helper).hexdigest() != supplement.get("resourceReplaySha256"):
        raise VerificationError("Portable supplemental resource helper differs from verified semantics")
    resource = evidence_dir / "supplemental_images.qrc"
    if not resource.is_file() or resource.is_symlink():
        raise VerificationError("Supplemental resource attachment is absent or symlinked")
    data = resource.read_bytes()
    if hashlib.sha256(data).hexdigest() != supplement.get("sha256"):
        raise VerificationError("Supplemental resource attachment differs from its verified output")
    try:
        document = ET.fromstring(data)
    except ET.ParseError as error:
        raise VerificationError("Supplemental resource attachment is not a valid manifest") from error
    groups = document.findall("qresource")
    if (
        document.tag != "RCC"
        or len(groups) != 1
        or groups[0].attrib != {"prefix": "/"}
        or any(node.tag != "file" or node.attrib for node in groups[0])
        or len(groups[0]) != len(source_prep.SUPPLEMENTAL_IMAGES)
        or {node.text for node in groups[0]} != set(source_prep.SUPPLEMENTAL_IMAGES)
    ):
        raise VerificationError("Supplemental resource aliases differ from the original image inputs")
    outputs = [entry for entry in preparation.get("outputs", []) if entry.get("path") == source_prep.SUPPLEMENTAL_QRC]
    if len(outputs) != 1 or outputs[0].get("after", {}).get("sha256") != supplement["sha256"]:
        raise VerificationError("Supplemental resource output lacks its exact preparation fingerprint")
    return {"recovery/supplemental_images.qrc": data, "recovery/prepare_supplemental_resources.py": helper}


def reflectionRegistrationAttachments(report: dict, preparation: dict, evidence_dir: Path) -> dict[str, bytes]:
    helper = source_prep.reflection_prep
    compatibility = preparation.get("identity", {}).get("reflectionRegistration", {})
    replay = Path(helper.__file__).read_bytes()
    expected = {
        "path": helper.TARGET,
        "sha256": hashlib.sha256(helper.HEADER).hexdigest(),
        "inputs": helper.INPUTS,
        "qmakeArgument": helper.ARGUMENT,
        "provenance": helper.PROVENANCE,
        "validationBoundary": helper.BOUNDARY,
        "replaySha256": hashlib.sha256(replay).hexdigest(),
    }
    if (
        compatibility != expected
        or preparation.get("qmakeArguments") != [helper.ARGUMENT]
        or report.get("startupCompatibility") != "parentReflectionRegistration"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
    ):
        raise VerificationError("Reflection compatibility differs from its reviewed inputs, macro or boundary")
    header = evidence_dir / helper.ATTACHMENT
    if header.is_symlink() or not header.is_file() or header.read_bytes() != helper.HEADER:
        raise VerificationError("Reflection compatibility attachment differs from the reviewed header bytes")
    outputs = [entry for entry in preparation.get("outputs", []) if entry.get("path") == helper.TARGET]
    if len(outputs) != 1 or outputs[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}:
        raise VerificationError("Reflection compatibility output lacks its exact preparation fingerprint")
    return {
        "recovery/" + helper.ATTACHMENT: helper.HEADER,
        "recovery/prepare_reflection_registration.py": replay,
    }


def coordinateHashAttachments(report: dict, preparation: dict, evidence_dir: Path) -> dict[str, bytes]:
    helper = source_prep.coordinates_prep
    compatibility = preparation.get("identity", {}).get("coordinatesHash", {})
    replay = Path(helper.__file__).read_bytes()
    expected = {
        "path": helper.TARGET,
        "sha256": hashlib.sha256(helper.HEADER).hexdigest(),
        "inputs": helper.INPUTS,
        "qmakeArgument": helper.ARGUMENT,
        "provenance": helper.PROVENANCE,
        "validationBoundary": helper.BOUNDARY,
        "replaySha256": hashlib.sha256(replay).hexdigest(),
    }
    if (
        compatibility != expected
        or preparation.get("qmakeArguments") != [helper.ARGUMENT]
        or report.get("startupCompatibility") != "originalCoordinateHash"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
    ):
        raise VerificationError("Coordinate hash compatibility differs from its reviewed inputs, macro or boundary")
    header = evidence_dir / helper.ATTACHMENT
    if header.is_symlink() or not header.is_file() or header.read_bytes() != helper.HEADER:
        raise VerificationError("Coordinate hash compatibility attachment differs from the reviewed header bytes")
    outputs = [entry for entry in preparation.get("outputs", []) if entry.get("path") == helper.TARGET]
    if len(outputs) != 1 or outputs[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}:
        raise VerificationError("Coordinate hash compatibility output lacks its exact preparation fingerprint")
    return {
        "recovery/" + helper.ATTACHMENT: helper.HEADER,
        "recovery/prepare_coordinates_hash.py": replay,
    }


def resourceAliasAttachments(report: dict, preparation: dict) -> dict[str, bytes]:
    helper = source_prep.aliases_prep
    compatibility = preparation.get("identity", {}).get("resourceAliases", {})
    replay = Path(helper.__file__).read_bytes()
    aliases = compatibility.get("aliases", {})
    if (
        {key: value for key, value in compatibility.items() if key != "aliases"}
        != {
            "inputs": helper.INPUTS,
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(replay).hexdigest(),
        }
        or preparation.get("qmakeArguments")
        or report.get("startupCompatibility") != "renamedResourceAliases"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
        or set(aliases) != set(helper.ALIASES)
        or any(
            aliases[target] != {"source": source, "sha256": helper.INPUTS[source]}
            for target, source in helper.ALIASES.items()
        )
    ):
        raise VerificationError("Resource alias compatibility differs from its reviewed original inputs or boundary")
    outputs = {
        entry.get("path"): entry.get("after")
        for entry in preparation.get("outputs", [])
        if entry.get("path") in helper.ALIASES
    }
    if outputs != {target: {"kind": "file", "sha256": aliases[target]["sha256"]} for target in helper.ALIASES}:
        raise VerificationError("Resource alias compatibility outputs lack their exact preparation fingerprints")
    return {"recovery/prepare_resource_aliases.py": replay}


def conflictResolutionAttachments(report: dict, preparation: dict) -> dict[str, bytes]:
    helper = source_prep.conflicts_prep
    recorded = preparation.get("identity", {}).get("conflictResolution", {})
    replay = Path(helper.__file__).read_bytes()
    files = recorded.get("files", {})
    if (
        {key: value for key, value in recorded.items() if key not in ("files", "supplied")}
        != {
            "side": helper.SIDE,
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(replay).hexdigest(),
        }
        or preparation.get("qmakeArguments")
        or report.get("startupCompatibility") != "whitespaceConflictResolution"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
        or set(files) != set(helper.INPUTS)
        or any(files[name].get("beforeSha256") != digest for name, digest in helper.INPUTS.items())
        or recorded.get("supplied")
        not in ({}, {helper.SUPPLIED_PATH: {"sha256": helper.SUPPLIED_SHA256, "sourceCommit": helper.SUPPLIED_COMMIT}})
    ):
        raise VerificationError("Conflict resolution differs from its reviewed original inputs or boundary")
    outputs = {
        entry.get("path"): (entry.get("before"), entry.get("after"))
        for entry in preparation.get("outputs", [])
        if entry.get("path") in helper.INPUTS or entry.get("path") == helper.SUPPLIED_PATH
    }
    expected = {
        name: (
            {"kind": "file", "sha256": files[name]["beforeSha256"]},
            {"kind": "file", "sha256": files[name]["afterSha256"]},
        )
        for name in helper.INPUTS
    }
    if recorded["supplied"]:
        expected[helper.SUPPLIED_PATH] = (None, {"kind": "file", "sha256": helper.SUPPLIED_SHA256})
    if outputs != expected:
        raise VerificationError("Conflict resolution outputs lack their exact preparation fingerprints")
    return {"recovery/prepare_conflict_resolution.py": replay}


def forwarderAttachments(report: dict, preparation: dict) -> dict[str, bytes]:
    helper = source_prep.forwarders_prep
    recorded = preparation.get("identity", {}).get("forwardingHeaders", {})
    replay = Path(helper.__file__).read_bytes()
    state = helper.STATES.get(recorded.get("state"), {})
    forwarders = recorded.get("forwarders", {})
    if (
        not state
        or {key: value for key, value in recorded.items() if key not in ("state", "forwarders")}
        != {
            "inputs": {**helper.INCLUDERS, **state["targets"]},
            "provenance": helper.PROVENANCE,
            "validationBoundary": helper.BOUNDARY,
            "replaySha256": hashlib.sha256(replay).hexdigest(),
        }
        or preparation.get("qmakeArguments")
        or report.get("startupCompatibility") != "mergedHeaderForwarders"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
        or sorted(forwarders) != state["forwarders"]
        or any(
            forwarders[name]
            != {
                "includes": list(helper.FORWARDERS[name]),
                "sha256": hashlib.sha256(helper.forwarderBytes(name)).hexdigest(),
            }
            for name in forwarders
        )
    ):
        raise VerificationError("Forwarding headers differ from their reviewed original inputs or boundary")
    outputs = {
        entry.get("path"): entry.get("after")
        for entry in preparation.get("outputs", [])
        if entry.get("path") in helper.FORWARDERS
    }
    if outputs != {name: {"kind": "file", "sha256": forwarders[name]["sha256"]} for name in forwarders}:
        raise VerificationError("Forwarding headers lack their exact preparation fingerprints")
    return {"recovery/prepare_forwarding_headers.py": replay}


def consoleShutdown(report: dict) -> bool:
    """True when the observer closed the window for a main.cpp holding the exact original stdin console loop."""
    adapter = report.get("adapter", {})
    shutdown = adapter.get("shutdown")
    if shutdown is None:
        return False
    expected = {
        "mode": "closeWindowAndJoinConsole",
        "consoleLoopSource": CONSOLE_LOOP_SOURCE,
        "validationBoundary": CONSOLE_SHUTDOWN_BOUNDARY,
    }
    main = shutdown.get("main", {})
    if (
        {key: value for key, value in shutdown.items() if key not in ("main", "consoleLoopSha256")} != expected
        or shutdown.get("consoleLoopSha256") not in [hashlib.sha256(loop).hexdigest() for loop in CONSOLE_LOOPS]
        or set(main) != {"path", "sha256"}
        or main.get("path") != "src/main.cpp"
        or adapter.get("mode") != "game"
        or report.get("smoke", {}).get("stdin") != "open and silent until the readiness report"
    ):
        raise VerificationError("Console shutdown differs from its reviewed original console loop or boundary")
    requireIdentity(main.get("sha256"), 64, "console main fingerprint")
    return True


def sourcePreparationAttachments(report: dict, evidence_dir: Path) -> dict[str, bytes]:
    preparation = report.get("sourcePreparation", {})
    if not preparation or preparation.get("status") == "not-required":
        return {}
    if preparation.get("status") != "success":
        raise VerificationError("Recovered README requires successful source preparation")
    steps = preparation.get("steps", [])
    names = [step.get("name") for step in steps]
    has_includes = "windowsIncludeSeparators" in names
    has_generator = "generator" in names
    has_resources = "supplementalResources" in names
    has_reflection = "reflectionRegistration" in names
    has_coordinates = "coordinatesHash" in names
    has_aliases = "resourceAliases" in names
    has_conflicts = "conflictResolution" in names
    has_forwarders = "forwardingHeaders" in names
    expected_names = (
        (["supplementalResources"] if has_resources else [])
        + (["reflectionRegistration"] if has_reflection else [])
        + (["coordinatesHash"] if has_coordinates else [])
        + (["resourceAliases"] if has_aliases else [])
        + (["forwardingHeaders"] if has_forwarders else [])
        + (["conflictResolution"] if has_conflicts else [])
        + (["windowsIncludeSeparators"] if has_includes else [])
        + (["interpreter", "generator"] if has_generator else [])
    )
    if not expected_names or names != expected_names:
        raise VerificationError("Recovered README requires recorded source preparation execution evidence")
    for step in steps:
        successfulCommand(step, "source preparation " + step["name"])
    identity = preparation.get("identity", {})
    if has_generator and identity.get("interpreter") != "Python 2.7.18":
        raise VerificationError("Recovered source preparation requires the locked Python 2.7.18 interpreter")
    requireIdentity(identity.get("implementationSha256"), 64, "source preparation implementation")
    inputs = identity.get("inputs", {})
    if has_generator and not {"preprocessor.py", "classes.json"}.issubset(inputs):
        raise VerificationError("Recovered source preparation lacks original generator input fingerprints")
    if not has_generator and (inputs or "interpreter" in identity):
        raise VerificationError("Include-only preparation cannot claim a historical Python generator")
    include_files = {}
    attachments = supplementalResourceAttachments(report, preparation, evidence_dir) if has_resources else {}
    if has_reflection:
        attachments.update(reflectionRegistrationAttachments(report, preparation, evidence_dir))
    if has_coordinates:
        attachments.update(coordinateHashAttachments(report, preparation, evidence_dir))
    if has_aliases:
        attachments.update(resourceAliasAttachments(report, preparation))
    if has_conflicts:
        attachments.update(conflictResolutionAttachments(report, preparation))
    if has_forwarders:
        attachments.update(forwarderAttachments(report, preparation))
    if has_includes:
        include_entries = identity.get("includeSeparators", [])
        if not include_entries:
            raise VerificationError("Recovered include preparation lacks literal source edits")
        for entry in include_entries:
            name = entry.get("path", "")
            if Path(name).is_absolute() or ".." in Path(name).parts or "\\" in name or ":" in name:
                raise VerificationError("Recovered include preparation path escapes the build copy")
            if not entry.get("includes"):
                raise VerificationError("Recovered include preparation lacks literal include changes")
            for stage in ("beforeSha256", "afterSha256"):
                requireIdentity(entry.get(stage), 64, "include preparation " + stage)
            include_files[name] = entry
        helper = Path(__file__).with_name("history_prepare_includes.py").read_bytes()
        if hashlib.sha256(helper).hexdigest() != identity.get("includeReplaySha256"):
            raise VerificationError("Portable include preparation helper differs from verified semantics")
        attachments["recovery/prepare_build_sources.py"] = helper
    outputs = preparation.get("outputs", [])
    if outputs != identity.get("outputs"):
        raise VerificationError("Recovered source preparation output fingerprints differ")
    for name, metadata in inputs.items():
        if name not in ("preprocessor.py", "classes.json", "macro.conf") or metadata.get("kind") != "file":
            raise VerificationError("Recovered source preparation has unexpected generator inputs")
        requireIdentity(metadata.get("sha256"), 64, "source preparation input fingerprint")
    for output in outputs:
        name = output.get("path", "")
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not (
                name == "gen/prop.h"
                or (name.startswith("src/") and name.endswith(".h"))
                or name in include_files
                or (has_resources and name == source_prep.SUPPLEMENTAL_QRC)
                or (has_reflection and name == source_prep.reflection_prep.TARGET)
                or (has_coordinates and name == source_prep.coordinates_prep.TARGET)
                or (has_aliases and name in source_prep.aliases_prep.ALIASES)
                or (has_conflicts and name in source_prep.conflicts_prep.INPUTS)
                or (
                    has_conflicts
                    and name in preparation["identity"]["conflictResolution"].get("supplied", {})
                )
                or (has_forwarders and name in preparation["identity"]["forwardingHeaders"].get("forwarders", {}))
            )
        ):
            raise VerificationError("Recovered source preparation has unexpected derived output paths")
        for stage in ("before", "after"):
            metadata = output.get(stage)
            if metadata is None and stage == "before":
                continue
            if not isinstance(metadata, dict) or metadata.get("kind") != "file":
                raise VerificationError("Recovered source preparation lacks derived output fingerprints")
            requireIdentity(metadata.get("sha256"), 64, "source preparation output fingerprint")
    metadata_path = evidence_dir / "source-preparation.json"
    log_path = evidence_dir / "source-preparation.log"
    if not metadata_path.is_file() or json.loads(metadata_path.read_text(encoding="utf-8")) != preparation:
        raise VerificationError("Copied source preparation report differs from recorded build preparation")
    if not log_path.is_file() or not log_path.stat().st_size:
        raise VerificationError("Recovered source preparation log is absent or empty")
    return {
        "recovery/source-preparation.json": metadata_path.read_bytes(),
        "recovery/source-preparation.log": log_path.read_bytes(),
        **attachments,
    }


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
    mode = verifiedStartupMode(report)
    editor = mode == "editor"
    checks = startup.get("checks", {})
    required = EDITOR_CHECKS if editor else REQUIRED_CHECKS
    if (
        not isinstance(checks, dict)
        or any(checks.get(name) is not True for name in required)
        or (editor and "player" in checks)
    ):
        raise VerificationError("Recovered screenshot lacks mode-specific map/render readiness")
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
    preparation_files = sourcePreparationAttachments(report, evidence_dir)
    resource_preparation = "recovery/supplemental_images.qrc" in preparation_files
    reflection_preparation = "recovery/prepare_reflection_registration.py" in preparation_files
    coordinates_preparation = "recovery/prepare_coordinates_hash.py" in preparation_files
    alias_preparation = "recovery/prepare_resource_aliases.py" in preparation_files
    conflict_preparation = "recovery/prepare_conflict_resolution.py" in preparation_files
    forwarder_preparation = "recovery/prepare_forwarding_headers.py" in preparation_files
    console_shutdown = consoleShutdown(report)
    conflict_supplied = bool(
        report.get("sourcePreparation", {}).get("identity", {}).get("conflictResolution", {}).get("supplied")
    )
    compatibility_modes = [
        name
        for enabled, name in (
            (resource_preparation, "supplementalQtResources"),
            (reflection_preparation, "parentReflectionRegistration"),
            (coordinates_preparation, "originalCoordinateHash"),
            (alias_preparation, "renamedResourceAliases"),
            (conflict_preparation, "whitespaceConflictResolution"),
            (forwarder_preparation, "mergedHeaderForwarders"),
        )
        if enabled
    ]
    expected_compatibility = compatibility_modes[0] if compatibility_modes else None
    if len(compatibility_modes) > 1 or report.get("startupCompatibility") != expected_compatibility:
        raise VerificationError("Recovered startup compatibility lacks its explicit preparation evidence")
    generator_preparation = "generator" in [
        step.get("name") for step in report.get("sourcePreparation", {}).get("steps", [])
    ]
    include_preparation = "recovery/prepare_build_sources.py" in preparation_files
    runtime_preparation = report.get("runtimePreparation", {})
    save_directory = bool(runtime_preparation)
    if save_directory:
        planned = runtime_preparation.get("identity", {}).get("directories", [])
        actual = runtime_preparation.get("directories", [])
        if (
            runtime_preparation.get("status") != "ready"
            or len(planned) != 1
            or len(actual) != 1
            or planned[0].get("path") != "save"
            or actual[0].get("path") != "save"
            or not planned[0].get("requiredBy")
        ):
            raise VerificationError("Recovered README requires recorded, contained runtime save-directory preparation")
        for evidence in planned[0]["requiredBy"]:
            requireIdentity(evidence.get("sha256"), 64, "runtime source prerequisite fingerprint")
            if evidence.get("operation") != 'fopen("save/game.sav", "w+")':
                raise VerificationError("Recovered runtime prerequisite lacks the genuine save-file writer")

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
    reviewed_flags = {
        "QMAKE_CXXFLAGS+=-include functional",
        "INCLUDEPATH+=$$_PRO_FILE_PWD_/provider",
        source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT,
        source_prep.reflection_prep.ARGUMENT,
        source_prep.coordinates_prep.ARGUMENT,
    }
    if resource_preparation != (source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT in compiler_flags):
        raise VerificationError("Supplemental resource qmake argument and attached preparation differ")
    if reflection_preparation != (source_prep.reflection_prep.ARGUMENT in compiler_flags):
        raise VerificationError("Reflection compatibility qmake argument and attached preparation differ")
    if coordinates_preparation != (source_prep.coordinates_prep.ARGUMENT in compiler_flags):
        raise VerificationError("Coordinate hash compatibility qmake argument and attached preparation differ")
    if any(
        not isinstance(flag, str) or (flag not in reviewed_flags and not re.fullmatch(r"[A-Za-z0-9_+=./:-]+", flag))
        for flag in compiler_flags
    ):
        raise VerificationError("Historical compiler flags need an explicitly reviewed portable command")
    qmake = shlex.join(["qmake", projects[0], *compiler_flags, "-after", "TARGET=RecoveryGame", "DESTDIR=."])
    abi = str(report.get("recipe", {}).get("pythonAbi", "none"))
    prerequisites = "Qt 5 Core, Gui and Widgets development files and a C++ compiler"
    if abi != "none":
        prerequisites += f", with CPython {abi} development files and its matching Boost.Python library"
    if (
        include_preparation
        or resource_preparation
        or reflection_preparation
        or coordinates_preparation
        or alias_preparation
        or conflict_preparation
        or forwarder_preparation
    ):
        prerequisites += ", and Python 3 for the hash-pinned build-source preparation helper"
    lines = [
        f"# Recovered {mode} snapshot",
        "",
        f"Original commit: `{commit}`. Original tree: `{tree}`.",
        *(
            [f"Startup was verified from identical recovered sources at `{report['verifiedFromCommit']}`."]
            if report.get("verifiedFromCommit")
            else []
        ),
        "",
        f"This recovered version compiled and linked on Linux, started the real {mode} on an isolated Xvfb display,",
        (
            "loaded its editor map, rendered the screenshot below, and exited normally."
            if editor
            else "loaded its map and a healthy player, rendered the screenshot below, and exited normally."
        ),
        *(
            [
                "Gameplay and player behavior were not verified. The surviving original `main.cpp` and",
                "`config/init.json` selected the editor; their Git blob and SHA256 identities are recorded in",
                "the attached verification metadata. The original entrypoint and configuration are preserved.",
            ]
            if editor
            else []
        ),
        "",
        *(
            [
                "Startup used supplemental Qt resource compatibility. The original manifest omitted 21 interaction",
                "images required by the original animation loader. Verification generated a separate manifest from",
                "the existing original images using the immediately following original commit's resource entries.",
                "The original manifest, provider and configuration remain unchanged. Their exact hashes, the image",
                "hashes, generated manifest and compatibility boundary are recorded in the attached preparation proof.",
                "This result establishes startup with that recorded compatibility step.",
                "",
            ]
            if resource_preparation
            else []
        ),
        *(
            [
                "Startup used an explicit build-only reflection registration compatibility header. The original",
                "registration macro passes a class name to a constructor that accepts no arguments and omits",
                "the Qt metatype declarations needed by its original factory. The forced include restores only",
                "the immediate parent's registration macro. Every original source file and translation unit is",
                "preserved. Exact input/header hashes and donor provenance are attached in the preparation proof.",
                "This establishes startup with that recorded compatibility step; gameplay parity is unverified.",
                "",
            ]
            if reflection_preparation
            else []
        ),
        *(
            [
                "Startup used an explicit build-only coordinate hashing compatibility header. The original",
                "pathfinder instantiates std::unordered_map<Coords, int> without a std::hash<Coords> specialization.",
                "The forced include delegates that standard interface to the existing original CoordsHasher;",
                "the original hash algorithm and all original source files remain unchanged. Exact input/header",
                "hashes and the compatibility boundary are attached in the preparation proof. This establishes",
                "startup with that recorded compatibility step; gameplay parity is unverified.",
                "",
            ]
            if coordinates_preparation
            else []
        ),
        *(
            [
                "Startup used explicit build-only resource aliases. This commit renamed three monster `time.txt`",
                "files to `time.json` without changing their bytes, but its unchanged original `creatures.qrc`",
                "still names `time.txt`, so the original manifest cannot compile; the next commit updates it.",
                "The attached helper supplies each manifest-named file with the exact bytes of its rename target,",
                "as the parent commit held them. The original manifest, sources and images remain unchanged.",
                "This establishes startup with that recorded compatibility step; gameplay parity is unverified.",
                "",
            ]
            if alias_preparation
            else []
        ),
        *(
            [
                "Startup used an explicit build-only resolution of original merge-conflict hunks. This commit",
                "was recorded with unresolved conflict markers in seven files, so it cannot compile as committed;",
                "in every hunk both sides differ only in whitespace. The attached helper keeps the origin/master",
                "side, which equals the parent commit's file, after verifying each original and resolved hash.",
                *(
                    [
                        "This commit also omitted `pathfinder/pathfindercache.cpp`, which its headers declare; the",
                        "helper supplies the hash-pinned file the immediately following commit adds unchanged.",
                    ]
                    if conflict_supplied
                    else []
                ),
                "This establishes startup with that recorded compatibility step; gameplay parity is unverified.",
                "",
            ]
            if conflict_preparation
            else []
        ),
        *(
            [
                "Startup used explicit build-only forwarding headers. This commit merged several class headers",
                "into one header per family while its unchanged original sources still include the old names,",
                "so it cannot compile as committed; a later commit rewrites those includes. Each forwarder only",
                "includes the header that now declares the same classes. Original sources remain unchanged.",
                "This establishes startup with that recorded compatibility step; gameplay parity is unverified.",
                "",
            ]
            if forwarder_preparation
            else []
        ),
        *(
            [
                "Shutdown used an explicit observer step. This version's `main.cpp` holds the developer's stdin",
                "script console loop (original at catalog #204; reconstructions from #207 adapt only its",
                "ScriptManager call). It runs on a thread-pool thread while the game window is visible, and the",
                "original view destructor deletes the scene that loop still queries, so leaving the event loop",
                "with the window shown crashes. Standard input stayed open and silent, like an idle console,",
                "until the frame and readiness report; then the observer closed the game window as a player",
                "would, stdin reached end of file, and the observer waited for that thread to stop. Sources are",
                "unchanged; the `main.cpp` and loop hashes are in the verification metadata.",
                "",
            ]
            if console_shutdown
            else []
        ),
        f"![Actual startup of this recovered {mode}](recovery/startup.png)",
        "",
        "## Build and run",
        "",
        f"Install {prerequisites}. The verified tool versions were:",
        "",
        f"- {compiler_version[0]}",
        *[f"- {line}" for line in qmake_version],
        "",
        *(
            [
                "This version uses its original `preprocessor.py` and `classes.json` with CPython 2.7.18 to",
                "generate `gen/prop.h` and refresh marked property blocks in headers before qmake. Run this",
                "on a separate build copy: the original generator can modify existing source headers.",
                "",
            ]
            if generator_preparation
            else []
        ),
        *(
            [
                "Use a separate build copy for this version. Its original source contains Windows separators",
                "in quoted includes. The attached helper changes only those recorded literals, verifies each",
                "source file's original and prepared SHA256, and preserves the recovered snapshot's provenance.",
                "",
            ]
            if include_preparation
            else []
        ),
        "Build from this snapshot's root directory:",
        "",
        "```sh",
        *(["python3 recovery/prepare_supplemental_resources.py"] if resource_preparation else []),
        *(["python3 recovery/prepare_reflection_registration.py"] if reflection_preparation else []),
        *(["python3 recovery/prepare_coordinates_hash.py"] if coordinates_preparation else []),
        *(["python3 recovery/prepare_resource_aliases.py"] if alias_preparation else []),
        *(["python3 recovery/prepare_conflict_resolution.py"] if conflict_preparation else []),
        *(["python3 recovery/prepare_forwarding_headers.py"] if forwarder_preparation else []),
        *(["python3 recovery/prepare_build_sources.py"] if include_preparation else []),
        *(["python2.7 -B preprocessor.py"] if generator_preparation else []),
        qmake,
        'make -j"$(nproc)"',
        *(["mkdir -p save"] if save_directory else []),
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
        *(
            [
                "The genuine scene writes `save/game.sav` during shutdown. Verification prepared its empty",
                "parent directory before startup, without changing source files or replacing existing save data.",
                "The source call, source hash and created/preserved directory are recorded in verification metadata.",
                "",
            ]
            if save_directory
            else []
        ),
        ", ".join(f"{method}: {count}" for method, count in sorted(counts.items())) + ".",
        "",
        *provenance,
        "",
        f"Restored source fingerprint: `{restored_fingerprint}`.",
        "",
        *(
            [
                "The restored source fingerprint identifies inputs before generation. The",
                "[source preparation metadata](recovery/source-preparation.json) records the original inputs",
                "and every generated or modified file's before/after hashes; the",
                "[preparation log](recovery/source-preparation.log) retains the actual preparation steps.",
                "",
            ]
            if preparation_files
            else []
        ),
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
    if preparation_files:
        portable["attachedSourcePreparation"] = {
            Path(name).name: {"path": Path(name).name, "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in preparation_files.items()
        }
    return {
        "README.md": "\n".join(lines).encode(),
        "recovery/startup.png": frame_path.read_bytes(),
        "recovery/verification.json": (json.dumps(portable, indent=2, sort_keys=True) + "\n").encode(),
        **preparation_files,
    }
