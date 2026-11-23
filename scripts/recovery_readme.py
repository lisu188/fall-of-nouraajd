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
    from scripts import history_runtime_configs as runtime_configs
    from scripts import history_static_lto as static_lto
    from scripts.verify_history import (
        EDITOR_CHECKS,
        REQUIRED_CHECKS,
        VerificationError,
        validatePng,
        verifiedStartupMode,
    )
except ModuleNotFoundError:
    import history_source_prep as source_prep
    import history_runtime_configs as runtime_configs
    import history_static_lto as static_lto
    from verify_history import EDITOR_CHECKS, REQUIRED_CHECKS, VerificationError, validatePng, verifiedStartupMode


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


def legacyTileAttachments(report: dict, preparation: dict, evidence_dir: Path) -> dict[str, bytes]:
    helper = source_prep.legacy_tiles_prep
    compatibility = preparation.get("identity", {}).get("legacyTileConfiguration", {})
    replay = Path(helper.__file__).read_bytes()
    expected = {
        "path": helper.TARGET,
        "sha256": helper.OUTPUT_SHA256,
        "inputs": helper.INPUTS,
        "provenance": helper.PROVENANCE,
        "validationBoundary": helper.BOUNDARY,
        "replaySha256": hashlib.sha256(replay).hexdigest(),
    }
    if (
        compatibility != expected
        or preparation.get("qmakeArguments", [])
        or report.get("startupCompatibility") != "legacyTileConfiguration"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
    ):
        raise VerificationError("Legacy tile compatibility differs from its reviewed inputs, output or boundary")
    attachment = evidence_dir / helper.ATTACHMENT
    if (
        attachment.is_symlink()
        or not attachment.is_file()
        or hashlib.sha256(attachment.read_bytes()).hexdigest() != helper.OUTPUT_SHA256
    ):
        raise VerificationError("Legacy tile configuration attachment differs from its reviewed derived bytes")
    outputs = [entry for entry in preparation.get("outputs", []) if entry.get("path") == helper.TARGET]
    if (
        len(outputs) != 1
        or outputs[0].get("before") is not None
        or outputs[0].get("after") != {"kind": "file", "sha256": helper.OUTPUT_SHA256}
    ):
        raise VerificationError("Legacy tile compatibility output lacks its exact new-file preparation fingerprint")
    return {
        "recovery/" + helper.ATTACHMENT: attachment.read_bytes(),
        "recovery/prepare_legacy_tile_configuration.py": replay,
    }


def mapsManifestAttachments(report: dict, preparation: dict, evidence_dir: Path) -> dict[str, bytes]:
    helper = source_prep.maps_manifest_prep
    compatibility = preparation.get("identity", {}).get("mapsManifest", {})
    replay = Path(helper.__file__).read_bytes()
    expected = {
        "path": helper.TARGET,
        "sha256": helper.OUTPUT_SHA256,
        "inputs": helper.INPUTS,
        "absentInputs": helper.ABSENT_INPUTS,
        "qmakeArguments": helper.ARGUMENTS,
        "provenance": helper.PROVENANCE,
        "validationBoundary": helper.BOUNDARY,
        "replaySha256": hashlib.sha256(replay).hexdigest(),
    }
    if (
        compatibility != expected
        or preparation.get("qmakeArguments") != helper.ARGUMENTS
        or report.get("startupCompatibility") != "authoredMapsManifest"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
    ):
        raise VerificationError(
            "Maps manifest compatibility differs from its reviewed inputs, absence state or boundary"
        )
    attachment = evidence_dir / helper.ATTACHMENT
    if (
        attachment.is_symlink()
        or not attachment.is_file()
        or hashlib.sha256(attachment.read_bytes()).hexdigest() != helper.OUTPUT_SHA256
    ):
        raise VerificationError("Maps manifest compatibility attachment differs from its authored corrected bytes")
    outputs = [entry for entry in preparation.get("outputs", []) if entry.get("path") == helper.TARGET]
    if (
        len(outputs) != 1
        or outputs[0].get("before") is not None
        or outputs[0].get("after") != {"kind": "file", "sha256": helper.OUTPUT_SHA256}
    ):
        raise VerificationError("Maps manifest compatibility output lacks its exact new-file preparation fingerprint")
    return {
        "recovery/" + helper.ATTACHMENT: attachment.read_bytes(),
        "recovery/prepare_maps_manifest.py": replay,
    }


def teleporterSerializationAttachments(report: dict, preparation: dict, evidence_dir: Path) -> dict[str, bytes]:
    compatibility = preparation.get("identity", {}).get("teleporterSerialization", {})
    helper = source_prep.teleporterHelper(compatibility.get("inputs"))
    expected = helper.reviewedIdentity(compatibility.get("inputs"))
    if (
        expected is None
        or compatibility != expected
        or preparation.get("qmakeArguments") != helper.ARGUMENTS
        or report.get("startupCompatibility") != "teleporterSerialization"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
    ):
        raise VerificationError(
            "Teleporter serialization differs from its reviewed source, header, JsonCpp or boundary"
        )
    attachment = evidence_dir / helper.ATTACHMENT
    if (
        attachment.is_symlink()
        or not attachment.is_file()
        or hashlib.sha256(attachment.read_bytes()).hexdigest() != expected["sha256"]
    ):
        raise VerificationError("Teleporter serialization attachment differs from its reviewed derived source")
    outputs = [entry for entry in preparation.get("outputs", []) if entry.get("path") == helper.TARGET]
    if (
        len(outputs) != 1
        or outputs[0].get("before") is not None
        or outputs[0].get("after") != {"kind": "file", "sha256": expected["sha256"]}
    ):
        raise VerificationError("Teleporter serialization output lacks its exact new-file preparation fingerprint")
    attachments = {
        "recovery/" + helper.ATTACHMENT: attachment.read_bytes(),
        "recovery/prepare_teleporter_serialization.py": Path(helper.__file__).read_bytes(),
    }
    if helper is source_prep.teleporter_conflicts_prep:
        attachments["recovery/history_prepare_teleporter.py"] = Path(source_prep.teleporter_prep.__file__).read_bytes()
        attachments["recovery/history_prepare_conflicts.py"] = Path(source_prep.conflicts_prep.__file__).read_bytes()
    return attachments


def legacyTimingAttachments(report: dict, preparation: dict) -> dict[str, bytes]:
    helper = source_prep.timing_prep
    outputs_sha = {name.removesuffix(".json") + ".txt": sha for name, sha in helper.RENAMED_INPUTS.items()}
    replay = Path(helper.__file__).read_bytes()
    expected = {
        "paths": sorted(outputs_sha),
        "sha256": outputs_sha,
        "inputs": {**helper.INPUTS, **helper.RENAMED_INPUTS},
        "absentInputs": sorted(outputs_sha),
        "provenance": helper.PROVENANCE,
        "validationBoundary": helper.BOUNDARY,
        "replaySha256": hashlib.sha256(replay).hexdigest(),
    }
    if (
        preparation.get("identity", {}).get("legacyTimingResources") != expected
        or preparation.get("qmakeArguments", [])
        or report.get("startupCompatibility") != "legacyTimingResources"
        or report.get("startupSelection", {}).get("boundary") != helper.BOUNDARY
    ):
        raise VerificationError("Legacy timing resources differ from their reviewed original inputs or boundary")
    outputs = preparation.get("outputs", [])
    if len(outputs) != len(outputs_sha) or {entry.get("path") for entry in outputs} != set(outputs_sha):
        raise VerificationError("Legacy timing resource output paths differ from the three reviewed aliases")
    for entry in outputs:
        if entry.get("before") is not None or entry.get("after") != {
            "kind": "file",
            "sha256": outputs_sha[entry["path"]],
        }:
            raise VerificationError("Legacy timing resources lack exact new-file preparation fingerprints")
    return {"recovery/prepare_legacy_timing.py": replay}


def sourcePreparationAttachments(report: dict, evidence_dir: Path) -> dict[str, bytes]:
    preparation = report.get("sourcePreparation", {})
    if not preparation or preparation.get("status") == "not-required":
        if report.get("sourceCommit") in source_prep.scene_prep.PINS:
            raise VerificationError("Missing scene transition preparation")
        if report.get("sourceCommit") in source_prep.shutdown_prep.TARGETS:
            raise VerificationError("Missing Python shutdown preparation")
        if report.get("sourceCommit") == source_prep.panel_prep.COMMIT:
            raise VerificationError("Missing panel transition preparation")
        if report.get("sourceCommit") == source_prep.text_shutdown_prep.COMMIT:
            raise VerificationError("Missing text-panel shutdown preparation")
        if report.get("sourceCommit") == source_prep.sparse_prep.COMMIT:
            raise VerificationError("Missing sparse map transition preparation")
        if report.get("sourceCommit") == source_prep.named_event_prep.COMMIT:
            raise VerificationError("Missing named event transition preparation")
        if report.get("sourceCommit") in source_prep.effect_prep.COMMITS:
            raise VerificationError("Missing effect transition preparation")
        if report.get("sourceCommit") in source_prep.resources_prep.COMMITS:
            raise VerificationError("Missing resources transition preparation")
        if report.get("sourceCommit") in source_prep.import_hook_prep.COMMITS:
            raise VerificationError("Missing import hook preparation")
        if report.get("sourceCommit") in source_prep.map_events_prep.COMMITS:
            raise VerificationError("Missing map event preparation")
        if report.get("sourceCommit") in source_prep.python_effects_prep.COMMITS:
            raise VerificationError("Missing Python effect preparation")
        if report.get("sourceCommit") in source_prep.class_loaders_prep.COMMITS:
            raise VerificationError("Missing Class loader preparation")
        if report.get("sourceCommit") in source_prep.map_packages_prep.COMMITS:
            raise VerificationError("Missing Map package preparation")
        if report.get("sourceCommit") in source_prep.potion_movement_prep.COMMITS:
            raise VerificationError("Missing Potion movement preparation")
        if report.get("sourceCommit") in source_prep.loader_prep.COMMITS:
            raise VerificationError("Missing script loader preparation")
        if report.get("sourceCommit") in source_prep.panel_refresh_prep.PROFILES:
            raise VerificationError("Missing panel refresh transition preparation")
        if report.get("sourceCommit") == source_prep.position_prep.COMMIT:
            raise VerificationError("Missing map position preparation")
        if report.get("sourceCommit") == source_prep.trigger_prep.COMMIT:
            raise VerificationError("Missing trigger decorator preparation")
        if report.get("sourceCommit") == source_prep.console_prep.COMMIT:
            raise VerificationError("Missing console reader preparation")
        if report.get("sourceCommit") in source_prep.merged_prep.COMMITS:
            raise VerificationError("Missing merged-header preparation")
        if report.get("sourceCommit") == source_prep.cache_prep.COMMIT:
            raise VerificationError("Missing pathfinder cache preparation for catalog #176")
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
    has_legacy_tiles = "legacyTileConfiguration" in names
    has_maps_manifest = "mapsManifest" in names
    has_teleporter = "teleporterSerialization" in names
    has_timing = "legacyTimingResources" in names
    has_conflicts = "trivialConflicts" in names
    has_scene = "sceneTransition" in names
    if has_scene != (report.get("sourceCommit") in source_prep.scene_prep.PINS):
        raise VerificationError("Scene transition preparation differs from the catalog commit")
    has_shutdown = "pythonShutdown" in names
    if has_shutdown != (report.get("sourceCommit") in source_prep.shutdown_prep.TARGETS):
        raise VerificationError("Python shutdown preparation differs from the catalog commit")
    has_panel = "panelTransition" in names
    if has_panel != (report.get("sourceCommit") == source_prep.panel_prep.COMMIT):
        raise VerificationError("Panel transition preparation differs from the catalog commit")
    has_text_shutdown = "textPanelShutdown" in names
    if has_text_shutdown != (report.get("sourceCommit") == source_prep.text_shutdown_prep.COMMIT):
        raise VerificationError("Text-panel shutdown preparation differs from the catalog commit")
    has_sparse = "sparseMapTransition" in names
    if has_sparse != (report.get("sourceCommit") == source_prep.sparse_prep.COMMIT):
        raise VerificationError("Sparse map transition preparation differs from the catalog commit")
    has_named_event = "namedEventTransition" in names
    if has_named_event != (report.get("sourceCommit") == source_prep.named_event_prep.COMMIT):
        raise VerificationError("Named event transition preparation differs from the catalog commit")
    has_resources_transition = "resourcesTransition" in names
    if has_resources_transition != (report.get("sourceCommit") in source_prep.resources_prep.COMMITS):
        raise VerificationError("Resources transition preparation differs from the catalog commit")
    has_import_hook = "importHook" in names
    if has_import_hook != (report.get("sourceCommit") in source_prep.import_hook_prep.COMMITS):
        raise VerificationError("Import hook preparation differs from the catalog commit")
    has_map_events = "mapEvents" in names
    if has_map_events != (report.get("sourceCommit") in source_prep.map_events_prep.COMMITS):
        raise VerificationError("Map event preparation differs from the catalog commit")
    has_python_effects = "pythonEffects" in names
    if has_python_effects != (report.get("sourceCommit") in source_prep.python_effects_prep.COMMITS):
        raise VerificationError("Python effect preparation differs from the catalog commit")
    has_class_loaders = "classLoaders" in names
    if has_class_loaders != (report.get("sourceCommit") in source_prep.class_loaders_prep.COMMITS):
        raise VerificationError("Class loader preparation differs from the catalog commit")
    has_map_packages = "mapPackages" in names
    if has_map_packages != (report.get("sourceCommit") in source_prep.map_packages_prep.COMMITS):
        raise VerificationError("Map package preparation differs from the catalog commit")
    has_potion_movement = "potionMovement" in names
    if has_potion_movement != (report.get("sourceCommit") in source_prep.potion_movement_prep.COMMITS):
        raise VerificationError("Potion movement preparation differs from the catalog commit")
    has_script_loader = "scriptLoader" in names
    if has_script_loader != (report.get("sourceCommit") in source_prep.loader_prep.COMMITS):
        raise VerificationError("Script loader preparation differs from the catalog commit")
    has_effect = "effectTransition" in names
    if has_effect != (report.get("sourceCommit") in source_prep.effect_prep.COMMITS):
        raise VerificationError("Effect transition preparation differs from the catalog commit")
    has_panel_refresh = "panelRefreshTransition" in names
    if has_panel_refresh != (report.get("sourceCommit") in source_prep.panel_refresh_prep.PROFILES):
        raise VerificationError("Panel refresh transition preparation differs from the catalog commit")
    has_position = "mapPosition" in names
    if has_position != (report.get("sourceCommit") == source_prep.position_prep.COMMIT):
        raise VerificationError("Map position preparation differs from the catalog commit")
    has_trigger = "triggerDecorator" in names
    if has_trigger != (report.get("sourceCommit") == source_prep.trigger_prep.COMMIT):
        raise VerificationError("Trigger decorator preparation differs from the catalog commit")
    has_console = "consoleReader" in names
    if has_console != (report.get("sourceCommit") == source_prep.console_prep.COMMIT):
        raise VerificationError("Console reader preparation differs from the catalog commit")
    has_merged_headers = "mergedHeaders" in names
    if has_merged_headers != (report.get("sourceCommit") in source_prep.merged_prep.COMMITS):
        raise VerificationError("Merged-header preparation differs from the catalog commit")
    has_cache = "childPathfinderCache" in names
    if has_cache != (report.get("sourceCommit") == source_prep.cache_prep.COMMIT):
        raise VerificationError("Pathfinder cache preparation differs from the catalog commit")
    expected_names = (
        (["supplementalResources"] if has_resources else [])
        + (["reflectionRegistration"] if has_reflection else [])
        + (["coordinatesHash"] if has_coordinates else [])
        + (["legacyTileConfiguration"] if has_legacy_tiles else [])
        + (["mapsManifest"] if has_maps_manifest else [])
        + (["teleporterSerialization"] if has_teleporter else [])
        + (["legacyTimingResources"] if has_timing else [])
        + (["trivialConflicts"] if has_conflicts else [])
        + (["childPathfinderCache"] if has_cache else [])
        + (["mergedHeaders"] if has_merged_headers else [])
        + (["consoleReader"] if has_console else [])
        + (["sceneTransition"] if has_scene else [])
        + (["pythonShutdown"] if has_shutdown else [])
        + (["triggerDecorator"] if has_trigger else [])
        + (["mapPosition"] if has_position else [])
        + (["panelTransition"] if has_panel else [])
        + (["textPanelShutdown"] if has_text_shutdown else [])
        + (["sparseMapTransition"] if has_sparse else [])
        + (["namedEventTransition"] if has_named_event else [])
        + (["resourcesTransition"] if has_resources_transition else [])
        + (["importHook"] if has_import_hook else [])
        + (["mapEvents"] if has_map_events else [])
        + (["pythonEffects"] if has_python_effects else [])
        + (["classLoaders"] if has_class_loaders else [])
        + (["mapPackages"] if has_map_packages else [])
        + (["potionMovement"] if has_potion_movement else [])
        + (["scriptLoader"] if has_script_loader else [])
        + (["effectTransition"] if has_effect else [])
        + (["panelRefreshTransition"] if has_panel_refresh else [])
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
    if has_legacy_tiles:
        attachments.update(legacyTileAttachments(report, preparation, evidence_dir))
    if has_maps_manifest:
        attachments.update(mapsManifestAttachments(report, preparation, evidence_dir))
    if has_teleporter:
        attachments.update(teleporterSerializationAttachments(report, preparation, evidence_dir))
    if has_timing:
        attachments.update(legacyTimingAttachments(report, preparation))
    if has_conflicts:
        helper = source_prep.conflicts_prep
        try:
            helper.validatePreparation(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        if report.get("buildCompatibility") != "trivialConflicts":
            raise VerificationError("Whitespace-only conflict preparation lacks its build boundary")
        attachments["recovery/prepare_trivial_conflicts.py"] = Path(helper.__file__).read_bytes()
    elif report.get("buildCompatibility"):
        raise VerificationError("Recovered build compatibility lacks preparation evidence")
    if has_cache:
        helper = source_prep.cache_prep
        try:
            helper.validate(preparation)
            data = helper.containedPath(evidence_dir, helper.ATTACHMENT).read_bytes()
        except (ValueError, OSError) as error:
            raise VerificationError(str(error)) from error
        if hashlib.sha256(data).hexdigest() != helper.SHA256 or not (has_conflicts and has_teleporter):
            raise VerificationError("Pathfinder cache differs from the reviewed #176 compatibility inputs")
        attachments["recovery/" + helper.ATTACHMENT] = data
        attachments["recovery/prepare_pathfinder_cache.py"] = Path(helper.__file__).read_bytes()
    if has_console:
        helper = source_prep.console_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_console_reader.py"] = Path(helper.__file__).read_bytes()
    scene_outputs = {}
    if has_scene:
        helper = source_prep.scene_prep
        commit = report["sourceCommit"]
        try:
            helper.validate(commit, preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        scene_outputs = helper.PINS[commit]
        attachments["recovery/prepare_scene_transition.py"] = Path(helper.__file__).read_bytes()
    if has_shutdown:
        helper = source_prep.shutdown_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_python_shutdown.py"] = Path(helper.__file__).read_bytes()
    if has_trigger:
        helper = source_prep.trigger_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_trigger_decorator.py"] = Path(helper.__file__).read_bytes()
    if has_position:
        helper = source_prep.position_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_map_position.py"] = Path(helper.__file__).read_bytes()
    if has_panel:
        helper = source_prep.panel_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_panel_transition.py"] = Path(helper.__file__).read_bytes()
    if has_text_shutdown:
        helper = source_prep.text_shutdown_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_text_panel_shutdown.py"] = Path(helper.__file__).read_bytes()
    if has_sparse:
        helper = source_prep.sparse_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_sparse_map_transition.py"] = Path(helper.__file__).read_bytes()
    if has_named_event:
        helper = source_prep.named_event_prep
        try:
            helper.validate(preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_named_event_transition.py"] = Path(helper.__file__).read_bytes()
    if has_resources_transition:
        helper = source_prep.resources_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_resources_transition.py"] = Path(helper.__file__).read_bytes()
    if has_import_hook:
        helper = source_prep.import_hook_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_import_hook.py"] = Path(helper.__file__).read_bytes()
    if has_map_events:
        helper = source_prep.map_events_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_map_events.py"] = Path(helper.__file__).read_bytes()
    if has_python_effects:
        helper = source_prep.python_effects_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_python_effects.py"] = Path(helper.__file__).read_bytes()
    if has_class_loaders:
        helper = source_prep.class_loaders_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_class_loaders.py"] = Path(helper.__file__).read_bytes()
    if has_map_packages:
        helper = source_prep.map_packages_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_map_packages.py"] = Path(helper.__file__).read_bytes()
    if has_potion_movement:
        helper = source_prep.potion_movement_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_potion_movement.py"] = Path(helper.__file__).read_bytes()
    if has_script_loader:
        helper = source_prep.loader_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_script_loader.py"] = Path(helper.__file__).read_bytes()
    if has_effect:
        helper = source_prep.effect_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_effect_transition.py"] = Path(helper.__file__).read_bytes()
    if has_panel_refresh:
        helper = source_prep.panel_refresh_prep
        try:
            helper.validate(report["sourceCommit"], preparation)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        attachments["recovery/prepare_panel_refresh_transition.py"] = Path(helper.__file__).read_bytes()
    merged_outputs = {}
    if has_merged_headers:
        helper = source_prep.merged_prep
        try:
            companions = helper.donorFiles(Path(__file__).resolve().parents[1])
            merged_outputs = helper.validate(report["sourceCommit"], preparation, companions)
        except (ValueError, OSError, KeyError) as error:
            raise VerificationError(str(error)) from error
        attachments.update({f"recovery/{name}": data for name, data in companions.items()})
        attachments["recovery/prepare_merged_headers.py"] = Path(helper.__file__).read_bytes()
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
                or name in merged_outputs
                or (has_panel and name in source_prep.panel_prep.PINS)
                or (has_text_shutdown and name in source_prep.text_shutdown_prep.PINS)
                or (has_sparse and name in source_prep.sparse_prep.PINS)
                or (has_named_event and name in source_prep.named_event_prep.PINS)
                or (has_effect and name in source_prep.effect_prep.PINS)
                or (has_script_loader and name in source_prep.loader_prep.PINS)
                or (has_import_hook and name in source_prep.import_hook_prep.PROFILES[report["sourceCommit"]])
                or (has_map_events and name in source_prep.map_events_prep.PROFILES[report["sourceCommit"]])
                or (has_python_effects and name in source_prep.python_effects_prep.PROFILES[report["sourceCommit"]])
                or (has_class_loaders and name in source_prep.class_loaders_prep.PROFILES[report["sourceCommit"]])
                or (has_map_packages and name in source_prep.map_packages_prep.PROFILES[report["sourceCommit"]])
                or (has_potion_movement and name in source_prep.potion_movement_prep.PROFILES[report["sourceCommit"]])
                or (has_resources_transition and name in source_prep.resources_prep.PINS)
                or (has_panel_refresh and name in source_prep.panel_refresh_prep.PROFILES[report["sourceCommit"]])
                or name in scene_outputs
                or (has_shutdown and name == source_prep.shutdown_prep.TARGETS[report["sourceCommit"]])
                or (has_position and name == source_prep.position_prep.TARGET)
                or (has_trigger and name == source_prep.trigger_prep.TARGET)
                or (has_console and name == source_prep.console_prep.TARGET)
                or (has_conflicts and name in source_prep.conflicts_prep.FILES)
                or (has_cache and name == source_prep.cache_prep.TARGET)
                or (has_resources and name == source_prep.SUPPLEMENTAL_QRC)
                or (has_reflection and name == source_prep.reflection_prep.TARGET)
                or (has_coordinates and name == source_prep.coordinates_prep.TARGET)
                or (has_legacy_tiles and name == source_prep.legacy_tiles_prep.TARGET)
                or (has_maps_manifest and name == source_prep.maps_manifest_prep.TARGET)
                or (has_teleporter and name == source_prep.teleporter_prep.TARGET)
                or (has_timing and name in identity["legacyTimingResources"]["paths"])
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
    legacy_tile_preparation = "recovery/prepare_legacy_tile_configuration.py" in preparation_files
    maps_manifest_preparation = "recovery/prepare_maps_manifest.py" in preparation_files
    teleporter_preparation = "recovery/prepare_teleporter_serialization.py" in preparation_files
    timing_preparation = "recovery/prepare_legacy_timing.py" in preparation_files
    conflicts_preparation = "recovery/prepare_trivial_conflicts.py" in preparation_files
    cache_preparation = "recovery/prepare_pathfinder_cache.py" in preparation_files
    runtime_config = report.get("runtimeConfiguration")
    if (commit in runtime_configs.INPUT_PINS) != bool(runtime_config):
        raise VerificationError("Runtime configuration evidence is required for this transition")
    if runtime_config:
        helper = Path(runtime_configs.__file__).read_bytes()
        try:
            runtime_configs.validateIdentity(commit, runtime_config)
        except ValueError as error:
            raise VerificationError(str(error)) from error
        if report["startupSelection"].get("boundary") != runtime_configs.BOUNDARY:
            raise VerificationError("Missing runtime configuration startup boundary")
        preparation_files["recovery/prepare_runtime_configs.py"] = helper
    compatibility_modes = [
        name
        for enabled, name in (
            (resource_preparation, "supplementalQtResources"),
            (runtime_config, "transitionalRuntimeConfiguration"),
            (reflection_preparation, "parentReflectionRegistration"),
            (coordinates_preparation, "originalCoordinateHash"),
            (legacy_tile_preparation, "legacyTileConfiguration"),
            (maps_manifest_preparation, "authoredMapsManifest"),
            (teleporter_preparation, "teleporterSerialization"),
            (timing_preparation, "legacyTimingResources"),
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
        static_lto.ARGUMENT,
        "QMAKE_CXXFLAGS+=-include functional",
        "INCLUDEPATH+=$$_PRO_FILE_PWD_/provider",
        source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT,
        source_prep.reflection_prep.ARGUMENT,
        source_prep.coordinates_prep.ARGUMENT,
        *source_prep.maps_manifest_prep.ARGUMENTS,
        *source_prep.teleporter_prep.ARGUMENTS,
    }
    if resource_preparation != (source_prep.SUPPLEMENTAL_QMAKE_ARGUMENT in compiler_flags):
        raise VerificationError("Supplemental resource qmake argument and attached preparation differ")
    if reflection_preparation != (source_prep.reflection_prep.ARGUMENT in compiler_flags):
        raise VerificationError("Reflection compatibility qmake argument and attached preparation differ")
    if coordinates_preparation != (source_prep.coordinates_prep.ARGUMENT in compiler_flags):
        raise VerificationError("Coordinate hash compatibility qmake argument and attached preparation differ")
    manifest_flags = source_prep.maps_manifest_prep.ARGUMENTS
    if maps_manifest_preparation:
        if compiler_flags[-len(manifest_flags) :] != manifest_flags or any(
            compiler_flags.count(flag) != 1 for flag in manifest_flags
        ):
            raise VerificationError("Maps manifest qmake arguments differ from the exact reviewed replacement order")
    elif any(flag in compiler_flags for flag in manifest_flags[1:]):
        raise VerificationError("Maps manifest qmake arguments lack attached preparation evidence")
    teleporter_flags = source_prep.teleporter_prep.ARGUMENTS
    if teleporter_preparation:
        if compiler_flags[-len(teleporter_flags) :] != teleporter_flags or any(
            compiler_flags.count(flag) != 1 for flag in teleporter_flags
        ):
            raise VerificationError(
                "Teleporter qmake arguments differ from the exact reviewed source replacement order"
            )
    elif any(flag in compiler_flags for flag in teleporter_flags[1:]):
        raise VerificationError("Teleporter qmake arguments lack attached preparation evidence")
    if any(
        not isinstance(flag, str) or (flag not in reviewed_flags and not re.fullmatch(r"[A-Za-z0-9_+=./:-]+", flag))
        for flag in compiler_flags
    ):
        raise VerificationError("Historical compiler flags need an explicitly reviewed portable command")
    qmake = shlex.join(["qmake", projects[0], *compiler_flags, "-after", "TARGET=RecoveryGame", "DESTDIR=."])
    build_commands = [qmake, 'make -j"$(nproc)"']
    executable = "./RecoveryGame"
    split_runtime = report.get("runtimeWorkingDirectory")
    if split_runtime is not None:
        project = report.get("project")
        expected_runtime = {"core/core.pro": ".", "game/game.pro": "files"}.get(project)
        if project == "game/game.pro" and split_runtime in ("resources", "game"):
            expected_runtime = split_runtime
        if split_runtime != expected_runtime:
            raise VerificationError("Unexpected split-project runtime directory")
        dependencies = report.get("dependencies", [])
        expected_dependencies = ["python/python.pro"]
        if split_runtime == "resources":
            expected_dependencies.append("resources/resources.pro")
        if [entry.get("project") for entry in dependencies] != expected_dependencies:
            raise VerificationError("Missing reviewed split-project dependencies")
        for entry in dependencies:
            successfulCommand(entry.get("configure"), "split-project dependency qmake")
            successfulCommand(entry.get("build"), "split-project dependency build")
        project_dir = Path(project).parent.as_posix()
        dependency_qmake = shlex.join(["qmake", "python.pro", *compiler_flags])
        build_commands = [
            '(cd python && ' + dependency_qmake + ' && make -j"$(nproc)")',
            f'(cd {project_dir} && ' + qmake + ' && make -j"$(nproc)")',
            'export LD_LIBRARY_PATH="$PWD/python${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"',
        ]
        if split_runtime == "resources":
            resource_qmake = shlex.join(["qmake", "resources.pro", *compiler_flags])
            build_commands.insert(1, '(cd resources && ' + resource_qmake + ' && make -j"$(nproc)")')
        executable = f"./{project_dir}/RecoveryGame"
        if split_runtime in ("files", "resources", "game"):
            build_commands.append(f"cd {split_runtime}")
            executable = "./RecoveryGame" if split_runtime == project_dir else f"../{project_dir}/RecoveryGame"
    abi = str(report.get("recipe", {}).get("pythonAbi", "none"))
    prerequisites = "Qt 5 Core, Gui and Widgets development files and a C++ compiler"
    if abi != "none":
        prerequisites += f", with CPython {abi} development files and its matching Boost.Python library"
    if (
        include_preparation
        or resource_preparation
        or reflection_preparation
        or coordinates_preparation
        or maps_manifest_preparation
        or teleporter_preparation
        or timing_preparation
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
                "Startup used a derived legacy tile configuration on an isolated build copy. The unchanged original",
                "CTile loader reads `config/tiles.json`, while the unchanged original tile data moved to",
                "`config/objects/tiles.json`. The attached hash-pinned helper flattens each exact original properties",
                "object, renames `animation` to `path`, and preserves `canStep`. It creates only the missing legacy",
                "configuration and refuses to replace existing data. Original source and configuration bytes remain",
                "unchanged. This is explicitly inferred compatibility, not recovery of a deleted original file;",
                "the input/output hashes and preparation proof are attached. Gameplay parity remains unverified.",
                "",
            ]
            if legacy_tile_preparation
            else []
        ),
        *(
            [
                "Startup used a separate build-only maps resource manifest. The original manifest still references",
                "a trigger configuration that the original commit deleted. The attached helper removes only that",
                "entry, reproducing the later authored correction exactly, and selects the derived manifest only",
                "after the project is read. The original manifest, source files and translation units remain unchanged.",
                "Exact input/output hashes, the required absence state and the compatibility boundary are attached.",
                "This establishes startup with that recorded compatibility step; gameplay parity is unverified.",
                "",
            ]
            if maps_manifest_preparation
            else []
        ),
        *(
            [
                "Startup and shutdown used explicit teleporter serialization compatibility. The original save",
                "method writes coordinate array entries and then a named enabled field, which its JsonCpp rejects.",
                "A separate derived translation unit changes only the save/load bodies to inverse JSON objects",
                "containing x, y, z and enabled. All other teleporter methods retain their original bytes; the original",
                "source file and header remain unchanged. Legacy coordinate arrays preserve the current enabled value,",
                "initialized to true by every reviewed original header. The attached hash-pinned helper selects only",
                "that derived unit after reading the project, preserving teleporting and ordinary save/shutdown paths.",
                "Exact source/header/JsonCpp hashes and the semantic compatibility boundary are attached.",
                "This establishes startup and shutdown with that compatibility step; gameplay parity is unverified.",
                "",
            ]
            if teleporter_preparation
            else []
        ),
        *(
            [
                "Startup used three legacy timing resource aliases on an isolated build copy. This original",
                "commit renamed the timing files to `time.json` without changing their bytes, while its unchanged",
                "resource manifest and animation provider still name `time.txt`. The attached hash-pinned helper",
                "copies only those 21 surviving bytes under the three absent legacy filenames. Original manifest,",
                "provider and renamed files remain unchanged. The later authored revision changes both manifest",
                "and provider to JSON; this compatibility step preserves the earlier provider and its original",
                "timing limitations. This proves startup with recorded resource compatibility; animation timing",
                "and gameplay parity remain unverified. Exact input/output hashes and absence proof are attached.",
                "",
            ]
            if timing_preparation
            else []
        ),
        *(
            [
                "The isolated build copy resolves exact-pinned original merge conflicts only where the two",
                "alternatives differ in whitespace. Five compiled files retain the reviewed HEAD alternative;",
                "the derived teleporter unit also resolves its whitespace-only conflict. Original Git inputs",
                "remain unchanged. Exact before/after hashes and portable replay helpers document this build",
                "compatibility separately from teleporter serialization semantics; gameplay parity is unverified.",
                "",
            ]
            if conflicts_preparation else []
        ),
        *(
            [
                "The runtime copy combines the split object tables, copies the flat tile table to its legacy path,",
                "and supplies empty arrays for missing timing files so the original animation loader selects 250 ms.",
                "",
            ]
            if runtime_config else []
        ),
        *(
            [
                "The reconstructed qmake project also requires pathfinder/pathfindercache.cpp. The original",
                "revision omitted that file. The isolated build uses the exact file added by immediate child",
                "779fb803, the sole change in that child. The attached helper verifies the donor and its inputs.",
                "",
            ]
            if cache_preparation else []
        ),
        *(
            [
                "The isolated build supplies the missing jsoncpp companions restored at #183.",
                "Where needed, forwarding headers expose declarations from the merged headers.",
                "",
            ]
            if "recovery/prepare_merged_headers.py" in preparation_files else []
        ),
        *(
            ["The Linux build copy reads console commands through Qt’s stdin notifier so the game can exit.", ""]
            if "recovery/prepare_console_reader.py" in preparation_files else []
        ),
        *(
            ["The isolated Linux build updates the surviving scene or tile call sites for this revision.", ""]
            if "recovery/prepare_scene_transition.py" in preparation_files else []
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
        *(["python3 recovery/prepare_legacy_tile_configuration.py"] if legacy_tile_preparation else []),
        *(["python3 recovery/prepare_maps_manifest.py"] if maps_manifest_preparation else []),
        *(["python3 recovery/prepare_teleporter_serialization.py"] if teleporter_preparation else []),
        *(["python3 recovery/prepare_legacy_timing.py"] if timing_preparation else []),
        *(["python3 recovery/prepare_trivial_conflicts.py"] if conflicts_preparation else []),
        *(["python3 recovery/prepare_pathfinder_cache.py"] if cache_preparation else []),
        *(["python3 recovery/prepare_merged_headers.py"] if "recovery/prepare_merged_headers.py" in preparation_files else []),
        *(["python3 recovery/prepare_console_reader.py"] if "recovery/prepare_console_reader.py" in preparation_files else []),
        *(["python3 recovery/prepare_scene_transition.py"] if "recovery/prepare_scene_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_python_shutdown.py"] if "recovery/prepare_python_shutdown.py" in preparation_files else []),
        *(["python3 recovery/prepare_trigger_decorator.py"] if "recovery/prepare_trigger_decorator.py" in preparation_files else []),
        *(["python3 recovery/prepare_map_position.py"] if "recovery/prepare_map_position.py" in preparation_files else []),
        *(["python3 recovery/prepare_panel_transition.py"] if "recovery/prepare_panel_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_text_panel_shutdown.py"] if "recovery/prepare_text_panel_shutdown.py" in preparation_files else []),
        *(["python3 recovery/prepare_sparse_map_transition.py"] if "recovery/prepare_sparse_map_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_named_event_transition.py"] if "recovery/prepare_named_event_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_effect_transition.py"] if "recovery/prepare_effect_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_script_loader.py"] if "recovery/prepare_script_loader.py" in preparation_files else []),
        *(["python3 recovery/prepare_import_hook.py"] if "recovery/prepare_import_hook.py" in preparation_files else []),
        *(["python3 recovery/prepare_map_events.py"] if "recovery/prepare_map_events.py" in preparation_files else []),
        *(["python3 recovery/prepare_python_effects.py"] if "recovery/prepare_python_effects.py" in preparation_files else []),
        *(["python3 recovery/prepare_class_loaders.py"] if "recovery/prepare_class_loaders.py" in preparation_files else []),
        *(["python3 recovery/prepare_map_packages.py"] if "recovery/prepare_map_packages.py" in preparation_files else []),
        *(["python3 recovery/prepare_potion_movement.py"] if "recovery/prepare_potion_movement.py" in preparation_files else []),
        *(["python3 recovery/prepare_resources_transition.py"] if "recovery/prepare_resources_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_panel_refresh_transition.py"] if "recovery/prepare_panel_refresh_transition.py" in preparation_files else []),
        *(["python3 recovery/prepare_build_sources.py"] if include_preparation else []),
        *(["python2.7 -B preprocessor.py"] if generator_preparation else []),
        *build_commands,
        *(["python3 recovery/prepare_runtime_configs.py"] if runtime_config else []),
        *(["mkdir -p save"] if save_directory else []),
        executable,
        "```",
        "",
        "For an isolated launch, use:",
        "",
        "```sh",
        'LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software xvfb-run -a --server-args="-screen 0 1920x1080x24" ' + executable,
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
