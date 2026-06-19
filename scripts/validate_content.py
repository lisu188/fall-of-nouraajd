#!/usr/bin/env python3
"""Fast JSON and script consistency checks for game content.

The validator intentionally avoids importing ``game`` or ``_game`` so it can run
before the native extension is built.  It checks the content shapes that the
runtime loader currently accepts late or silently: missing refs, bad classes,
dialog links/actions, duplicate map object names, and literal script refs.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OBJECT_SCHEMA_KEYS = {"class", "ref", "properties"}
SCRIPT_REF_CALLS = {"createObject", "addObjectByName"}
SCRIPT_ITEM_CALLS = {"addItem"}
SCRIPT_QUEST_CALLS = {"addQuest", "ensure_quest", "_grant_quest", "grant_quest"}
SCRIPT_MAP_CALLS = {"changeMap"}
SCRIPT_OBJECT_NAME_CALLS = {"getObjectByName", "removeObjectByName"}
KNOWN_EVENT_NAMES = {
    "onCreate",
    "onDestroy",
    "onEnter",
    "onEquip",
    "onLeave",
    "onTurn",
    "onUnequip",
    "onUse",
}
BUILTIN_CLASSES = {
    "CArmor",
    "CBelt",
    "CBoots",
    "CBuilding",
    "CController",
    "CCreature",
    "CDialog",
    "CDialogOption",
    "CDialogState",
    "CEffect",
    "CEvent",
    "CFightController",
    "CGameObject",
    "CGloves",
    "CGroundController",
    "CHelmet",
    "CInteraction",
    "CItem",
    "CMapObject",
    "CMarket",
    "CMonsterFightController",
    "CNpcRandomController",
    "CPlayer",
    "CPlayerController",
    "CPlayerFightController",
    "CPotion",
    "CQuest",
    "CRandomController",
    "CRangeController",
    "CScroll",
    "CScript",
    "CSmallWeapon",
    "CStats",
    "CTargetController",
    "CTile",
    "CTrigger",
    "CWeapon",
}
PYTHON_REGISTRATION_DECORATORS = {"register", "trigger"}
REVIEWED_ABSTRACT_INTERNAL_CLASSES = {
    "CConfigResource",
    "CConfigResourceLoader",
    "CEventHandler",
    "CGame",
    "CGameEvent",
    "CGameEventCaused",
    "CGuiHandler",
    "CMap",
    "CNativeContentPlugin",
    "CObjectHandler",
    "CPlugin",
    "CResource",
    "CResourceLoader",
    "CRngHandler",
    "CTextResource",
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.location}: {self.message}"


@dataclass(frozen=True)
class ConfigEntry:
    key: str
    data: Any
    path: Path


@dataclass
class ScriptCall:
    name: str
    value: str
    lineno: int
    context: str

    @property
    def location(self) -> str:
        call = f'{self.name}("{self.value}")'
        return f"{self.context}:{self.lineno} {call}" if self.context else f"line {self.lineno} {call}"


@dataclass
class ScriptInfo:
    path: Path
    classes: set[str] = field(default_factory=set)
    registered_classes: set[str] = field(default_factory=set)
    methods_by_class: dict[str, set[str]] = field(default_factory=dict)
    calls: list[ScriptCall] = field(default_factory=list)
    trigger_targets: list[ScriptCall] = field(default_factory=list)
    named_objects: set[str] = field(default_factory=set)


@dataclass
class MapContext:
    name: str
    directory: Path
    map_path: Path
    map_data: Any
    config_entries: dict[str, ConfigEntry]
    config_files: dict[Path, Any]
    script_info: ScriptInfo | None
    placed_names: set[str] = field(default_factory=set)


class ScriptAnalyzer(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.info = ScriptInfo(path=path)
        self._class_stack: list[str] = []
        self._function_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.info.classes.add(node.name)
        if any(is_python_registration_decorator(decorator) for decorator in node.decorator_list):
            self.info.registered_classes.add(node.name)
        self.info.methods_by_class.setdefault(node.name, set())
        self._class_stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if self._class_stack:
            self.info.methods_by_class.setdefault(self._class_stack[-1], set()).add(node.name)
        self._function_stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call) -> Any:
        name = call_name(node.func)
        if name:
            self._record_script_call(name, node)
            self._record_named_object(name, node)
        self.generic_visit(node)

    def _record_script_call(self, name: str, node: ast.Call) -> None:
        literal = first_string_arg(node)
        if literal is None:
            return
        context = ".".join([*self._class_stack, *self._function_stack])
        if (
            name
            in SCRIPT_REF_CALLS | SCRIPT_ITEM_CALLS | SCRIPT_QUEST_CALLS | SCRIPT_MAP_CALLS | SCRIPT_OBJECT_NAME_CALLS
        ):
            self.info.calls.append(ScriptCall(name=name, value=literal, lineno=node.lineno, context=context))

    def _record_named_object(self, name: str, node: ast.Call) -> None:
        if name == "setStringProperty" and len(node.args) >= 2:
            key = string_literal(node.args[0])
            value = string_literal(node.args[1])
            if key == "name" and value:
                self.info.named_objects.add(value)


def call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def string_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def first_string_arg(node: ast.Call) -> str | None:
    for arg in node.args:
        literal = string_literal(arg)
        if literal is not None:
            return literal
    return None


def is_python_registration_decorator(decorator: ast.AST) -> bool:
    if isinstance(decorator, ast.Call):
        return call_name(decorator.func) in PYTHON_REGISTRATION_DECORATORS
    return call_name(decorator) in PYTHON_REGISTRATION_DECORATORS


class TriggerAnalyzer(ast.NodeVisitor):
    def __init__(self, info: ScriptInfo) -> None:
        self.info = info
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self._class_stack.append(node.name)
        for decorator in node.decorator_list:
            self._record_trigger(decorator, node)
        for child in node.body:
            self.visit(child)
        self._class_stack.pop()

    def _record_trigger(self, decorator: ast.AST, node: ast.ClassDef) -> None:
        if not isinstance(decorator, ast.Call) or call_name(decorator.func) != "trigger":
            return
        event_name = string_literal(decorator.args[1]) if len(decorator.args) >= 2 else None
        target_name = string_literal(decorator.args[2]) if len(decorator.args) >= 3 else None
        context = node.name
        if event_name:
            self.info.trigger_targets.append(
                ScriptCall(name="trigger event", value=event_name, lineno=node.lineno, context=context)
            )
        if target_name:
            self.info.trigger_targets.append(
                ScriptCall(name="trigger target", value=target_name, lineno=node.lineno, context=context)
            )


class ContentValidator:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.issues: list[ValidationIssue] = []
        self.global_entries: dict[str, ConfigEntry] = {}
        self.global_files: dict[Path, Any] = {}
        self.map_contexts: list[MapContext] = []
        self.plugin_info: list[ScriptInfo] = []
        self.fallback_registered_classes: set[str] = set(BUILTIN_CLASSES)
        self.metadata_declared_classes: set[str] = set()
        self.static_registered_classes: set[str] = set()
        self.native_plugin_registered_classes: set[str] = set()
        self.native_plugin_declared_class_sources: dict[str, set[str]] = {}
        self.python_registered_classes: set[str] = set()
        self.reviewed_abstract_internal_classes: set[str] = set(REVIEWED_ABSTRACT_INTERNAL_CLASSES)

    def validate(self) -> list[ValidationIssue]:
        self._collect_engine_classes()
        self._collect_plugin_classes()
        self._load_global_configs()
        self._load_maps()
        self._validate_global_configs()
        for context in self.map_contexts:
            self._validate_map_context(context)
        return sorted(self.issues, key=lambda issue: (issue.path, issue.location, issue.message))

    def _collect_engine_classes(self) -> None:
        source_roots = [self.repo_root / "src"]
        for source_root in source_roots:
            if not source_root.exists():
                continue
            for path in source_root.rglob("*"):
                if path.suffix not in {".cpp", ".h", ".hpp"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                for class_name in iter_cpp_template_type_names(text, "register_type_metadata"):
                    self.metadata_declared_classes.add(class_name)
                for class_name in iter_cpp_template_type_names(text, "register_type"):
                    if path.name == "NativePlugin.cpp":
                        continue
                    if path.name.endswith("TypeRegistration.cpp"):
                        self.static_registered_classes.add(class_name)
                for match in re.finditer(r"V_META\(\s*([A-Za-z_]\w*)", text):
                    class_name = match.group(1)
                    if is_concrete_cpp_class_name(class_name):
                        self.metadata_declared_classes.add(class_name)
        self._collect_native_plugin_classes()

    def _collect_native_plugin_classes(self) -> None:
        helper_classes = self._native_plugin_helper_classes()
        entry_helpers = self._native_plugin_entry_helpers(helper_classes)
        loaded_entries = self._manifest_native_plugin_entries()
        for library, entry in loaded_entries:
            for class_name in entry_helpers.get((library, entry), set()):
                self.native_plugin_registered_classes.add(class_name)

    def _native_plugin_helper_classes(self) -> dict[str, set[str]]:
        path = self.repo_root / "src" / "plugin" / "NativePlugin.cpp"
        if not path.exists():
            return {}
        text = read_text_lossy(path)
        helper_classes: dict[str, set[str]] = {}
        for name, body in iter_cpp_function_bodies(text):
            if not name.startswith("register_"):
                continue
            classes = iter_cpp_template_type_names(body, "register_type")
            if classes:
                helper_classes[name] = classes
                for class_name in classes:
                    self.native_plugin_declared_class_sources.setdefault(class_name, set()).add(
                        f"native_plugin::{name}"
                    )
        return helper_classes

    def _native_plugin_entry_helpers(self, helper_classes: dict[str, set[str]]) -> dict[tuple[str, str], set[str]]:
        native_dir = self.repo_root / "native_plugins"
        entry_helpers: dict[tuple[str, str], set[str]] = {}
        if not native_dir.exists():
            return entry_helpers
        for path in sorted(native_dir.glob("*.cpp")):
            text = read_text_lossy(path)
            library = path.stem
            for entry, body in iter_cpp_function_bodies(text):
                classes = iter_cpp_template_type_names(body, "register_type")
                for helper_name in re.findall(r"\bnative_plugin::(register_[A-Za-z_]\w*)\s*\(", body):
                    classes.update(helper_classes.get(helper_name, set()))
                if classes:
                    entry_helpers[(library, entry)] = classes
                    for class_name in classes:
                        self.native_plugin_declared_class_sources.setdefault(class_name, set()).add(
                            f"{library}:{entry}"
                        )
        return entry_helpers

    def _manifest_native_plugin_entries(self) -> set[tuple[str, str]]:
        manifest_path = self.repo_root / "res" / "plugins" / "manifest.json"
        if not manifest_path.exists():
            return set()
        data = self._load_json(manifest_path)
        loaded_entries: set[tuple[str, str]] = set()
        if not isinstance(data, dict):
            return loaded_entries
        for entry in iter_manifest_plugin_entries(data):
            if entry.get("kind") != "dynamic":
                continue
            library = entry.get("library")
            if not isinstance(library, str) or not library:
                continue
            function_name = entry.get("entry", "game_plugin_load_v1")
            if isinstance(function_name, str) and function_name:
                loaded_entries.add((Path(library).name, function_name))
        return loaded_entries

    def _collect_plugin_classes(self) -> None:
        plugin_dir = self.repo_root / "res" / "plugins"
        for path in sorted(plugin_dir.glob("*.py")):
            info = self._parse_script(path)
            if info:
                self.plugin_info.append(info)
                self.python_registered_classes.update(info.registered_classes)

    def _load_global_configs(self) -> None:
        config_dir = self.repo_root / "res" / "config"
        for path in sorted(config_dir.glob("*.json")):
            data = self._load_json(path)
            if data is None:
                continue
            self.global_files[path] = data
            if isinstance(data, dict):
                for key, value in data.items():
                    self.global_entries[key] = ConfigEntry(key=key, data=value, path=path)
            else:
                self._issue(path, "$", "expected top-level JSON object")

    def _load_maps(self) -> None:
        maps_dir = self.repo_root / "res" / "maps"
        for directory in sorted(path for path in maps_dir.glob("*") if path.is_dir()):
            map_path = directory / "map.json"
            map_data = self._load_json(map_path)
            if map_data is None:
                continue
            config_entries: dict[str, ConfigEntry] = {}
            config_files: dict[Path, Any] = {}
            for path in sorted(directory.glob("*.json")):
                if path.name == "map.json":
                    continue
                data = self._load_json(path)
                if data is None:
                    continue
                config_files[path] = data
                if isinstance(data, dict):
                    for key, value in data.items():
                        config_entries[key] = ConfigEntry(key=key, data=value, path=path)
                else:
                    self._issue(path, "$", "expected top-level JSON object")
            script_info = self._parse_script(directory / "script.py")
            self.map_contexts.append(
                MapContext(
                    name=directory.name,
                    directory=directory,
                    map_path=map_path,
                    map_data=map_data,
                    config_entries=config_entries,
                    config_files=config_files,
                    script_info=script_info,
                )
            )

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            self._issue(path, "$", "missing required JSON file")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._issue(path, f"line {exc.lineno} column {exc.colno}", exc.msg)
            return None

    def _parse_script(self, path: Path) -> ScriptInfo | None:
        if not path.exists():
            return None
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            self._issue(path, f"line {exc.lineno or 0}", exc.msg)
            return None
        analyzer = ScriptAnalyzer(path)
        analyzer.visit(tree)
        TriggerAnalyzer(analyzer.info).visit(tree)
        return analyzer.info

    def _validate_global_configs(self) -> None:
        visible = dict(self.global_entries)
        known_classes = self._constructible_classes()
        for entry in self.global_entries.values():
            self._validate_config_entry(entry, visible, known_classes)
        self._validate_crafting_refs()

    def _validate_map_context(self, context: MapContext) -> None:
        visible = self._visible_entries(context)
        known_classes = self._known_classes(context)
        for entry in context.config_entries.values():
            self._validate_config_entry(entry, visible, known_classes)
        self._validate_top_level_ref_cycles(context, visible)
        self._validate_map_json(context, visible, known_classes)
        self._validate_dialogs(context, visible)
        self._validate_script_refs(context, visible, known_classes)

    def _visible_entries(self, context: MapContext) -> dict[str, ConfigEntry]:
        visible = dict(self.global_entries)
        visible.update(context.config_entries)
        return visible

    def _known_classes(self, context: MapContext) -> set[str]:
        return self._constructible_classes(context.script_info.registered_classes if context.script_info else set())

    def _constructible_classes(self, extra_registered_classes: set[str] | None = None) -> set[str]:
        classes = (
            self.fallback_registered_classes
            | self.static_registered_classes
            | self.native_plugin_registered_classes
            | self.python_registered_classes
            | set(extra_registered_classes or set())
        )
        return classes - self.reviewed_abstract_internal_classes

    def _validate_config_entry(
        self, entry: ConfigEntry, visible: dict[str, ConfigEntry], known_classes: set[str]
    ) -> None:
        self._validate_object_shape(entry.path, entry.key, entry.data)
        self._validate_refs(entry.path, entry.key, entry.data, visible)
        self._validate_object_classes(entry.path, entry.key, entry.data, known_classes)

    def _validate_object_shape(self, path: Path, location: str, value: Any) -> None:
        if isinstance(value, dict):
            has_ref = "ref" in value
            has_class = "class" in value
            is_object_node = has_ref or (has_class and ("properties" in value or set(value) <= OBJECT_SCHEMA_KEYS))
            if is_object_node and has_ref and has_class:
                self._issue(path, location, 'object node must not define both "ref" and "class"')
            if is_object_node:
                unexpected = sorted(set(value) - OBJECT_SCHEMA_KEYS)
                if unexpected:
                    self._issue(path, location, f"object node has unsupported keys: {', '.join(unexpected)}")
                properties = value.get("properties")
                if "properties" in value and not isinstance(properties, dict):
                    self._issue(path, f"{location}.properties", "expected object")
            for key, child in value.items():
                self._validate_object_shape(path, append_field(location, key), child)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_object_shape(path, append_index(location, index), child)

    def _validate_object_classes(
        self, path: Path, location: str, value: Any, known_classes: set[str], in_object_node: bool = True
    ) -> None:
        if isinstance(value, dict):
            is_object_node = self._is_object_node(value)
            class_name = value.get("class")
            if is_object_node or in_object_node:
                if isinstance(class_name, str) and class_name not in known_classes:
                    self._issue(path, f"{location}.class", self._class_reference_message(class_name, "class"))
                elif class_name is not None and not isinstance(class_name, str):
                    self._issue(path, f"{location}.class", "expected string class name")
            for key, child in value.items():
                self._validate_object_classes(path, append_field(location, key), child, known_classes, is_object_node)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_object_classes(path, append_index(location, index), child, known_classes, False)

    def _validate_refs(self, path: Path, location: str, value: Any, visible: dict[str, ConfigEntry]) -> None:
        if isinstance(value, dict):
            ref = value.get("ref")
            if ref is not None:
                ref_location = append_field(location, "ref")
                if not isinstance(ref, str):
                    self._issue(path, ref_location, "expected string ref")
                elif ref not in visible:
                    self._issue(path, ref_location, f'unknown ref "{ref}"')
            for key, child in value.items():
                self._validate_refs(path, append_field(location, key), child, visible)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_refs(path, append_index(location, index), child, visible)

    def _validate_top_level_ref_cycles(self, context: MapContext, visible: dict[str, ConfigEntry]) -> None:
        for entry in list(context.config_entries.values()) + list(self.global_entries.values()):
            seen: list[str] = []
            current = entry
            while isinstance(current.data, dict) and isinstance(current.data.get("ref"), str):
                ref = current.data["ref"]
                if current.key in seen:
                    cycle = " -> ".join([*seen, current.key])
                    self._issue(entry.path, f"{entry.key}.ref", f"cyclic ref chain: {cycle}")
                    break
                seen.append(current.key)
                next_entry = visible.get(ref)
                if next_entry is None:
                    break
                current = next_entry

    def _validate_map_json(self, context: MapContext, visible: dict[str, ConfigEntry], known_classes: set[str]) -> None:
        data = context.map_data
        if not isinstance(data, dict):
            self._issue(context.map_path, "$", "expected top-level JSON object")
            return
        layers = data.get("layers")
        if not isinstance(layers, list):
            self._issue(context.map_path, "layers", "expected array")
            return
        width = data.get("width")
        height = data.get("height")
        tile_types = tile_types_by_id(data)
        for layer_index, layer in enumerate(layers):
            layer_location = f"layers[{layer_index}]"
            if not isinstance(layer, dict):
                self._issue(context.map_path, layer_location, "expected object")
                continue
            layer_type = layer.get("type")
            if layer_type == "tilelayer":
                self._validate_tile_layer(
                    context, layer, layer_location, width, height, tile_types, visible, known_classes
                )
            elif layer_type == "objectgroup":
                self._validate_object_layer(context, layer, layer_location, visible, known_classes)

    def _validate_tile_layer(
        self,
        context: MapContext,
        layer: dict[str, Any],
        location: str,
        map_width: Any,
        map_height: Any,
        tile_types: dict[int, str],
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        data = layer.get("data")
        if not isinstance(data, list):
            self._issue(context.map_path, f"{location}.data", "expected tile data array")
            return
        layer_width = layer.get("width", map_width)
        layer_height = layer.get("height", map_height)
        if isinstance(layer_width, int) and isinstance(layer_height, int):
            expected = layer_width * layer_height
            if len(data) != expected:
                self._issue(context.map_path, f"{location}.data", f"expected {expected} tile ids, got {len(data)}")
        for index, tile_id in enumerate(data):
            if not isinstance(tile_id, int):
                self._issue(context.map_path, f"{location}.data[{index}]", "expected integer tile id")
                continue
            if tile_id == 0:
                continue
            tile_type = tile_types.get(tile_id - 1)
            if not tile_type:
                self._issue(
                    context.map_path,
                    f"{location}.data[{index}]",
                    f"tile id {tile_id} has no tilesets[0].tileproperties[{tile_id - 1}].type",
                )
            elif tile_type not in visible and tile_type not in known_classes:
                self._issue(
                    context.map_path,
                    f"{location}.data[{index}]",
                    self._class_reference_message(tile_type, "tile type"),
                )

    def _validate_object_layer(
        self,
        context: MapContext,
        layer: dict[str, Any],
        location: str,
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        objects = layer.get("objects")
        if not isinstance(objects, list):
            self._issue(context.map_path, f"{location}.objects", "expected object array")
            return
        seen_names: dict[str, str] = {}
        for object_index, obj in enumerate(objects):
            object_location = f"{location}.objects[{object_index}]"
            if not isinstance(obj, dict):
                self._issue(context.map_path, object_location, "expected object")
                continue
            name = obj.get("name")
            if isinstance(name, str) and name:
                if name in context.placed_names:
                    previous = seen_names.get(name, "another layer")
                    self._issue(
                        context.map_path,
                        f"{object_location}.name",
                        f'duplicate object name "{name}", previously defined at {previous}',
                    )
                else:
                    context.placed_names.add(name)
                    seen_names[name] = object_location
            object_type = obj.get("type")
            if not isinstance(object_type, str) or not object_type:
                self._issue(context.map_path, f"{object_location}.type", "expected non-empty object type")
            elif object_type not in visible and object_type not in known_classes:
                self._issue(
                    context.map_path,
                    f"{object_location}.type",
                    self._class_reference_message(object_type, "object type"),
                )
            for numeric_key in ("width", "height"):
                numeric_value = obj.get(numeric_key)
                if numeric_value is not None and not isinstance(numeric_value, (int, float)):
                    self._issue(context.map_path, f"{object_location}.{numeric_key}", "expected number")

    def _validate_dialogs(self, context: MapContext, visible: dict[str, ConfigEntry]) -> None:
        if not context.script_info:
            return
        methods_by_class = context.script_info.methods_by_class
        for entry in context.config_entries.values():
            if not isinstance(entry.data, dict):
                continue
            properties = entry.data.get("properties")
            if not isinstance(properties, dict) or not isinstance(properties.get("states"), list):
                continue
            self._validate_dialog(entry, visible, methods_by_class, context.script_info.path)

    def _validate_dialog(
        self,
        entry: ConfigEntry,
        visible: dict[str, ConfigEntry],
        methods_by_class: dict[str, set[str]],
        script_path: Path,
    ) -> None:
        dialog_class = entry.data.get("class")
        states = entry.data.get("properties", {}).get("states", [])
        state_ids: dict[str, int] = {}
        edges: dict[str, set[str]] = {}
        option_numbers: dict[str, set[int]] = {}
        for state_index, state in enumerate(states):
            state_location = f"{entry.key}.properties.states[{state_index}]"
            if not isinstance(state, dict):
                self._issue(entry.path, state_location, "expected dialog state object")
                continue
            props = state.get("properties")
            if not isinstance(props, dict):
                self._issue(entry.path, f"{state_location}.properties", "expected object")
                continue
            state_id = props.get("stateId")
            if not isinstance(state_id, str) or not state_id:
                self._issue(entry.path, f"{state_location}.properties.stateId", "expected non-empty state id")
                continue
            if state_id in state_ids:
                previous = f"{entry.key}.properties.states[{state_ids[state_id]}]"
                self._issue(
                    entry.path,
                    f"{state_location}.properties.stateId",
                    f'duplicate dialog state "{state_id}", previously defined at {previous}',
                )
            state_ids[state_id] = state_index
            edges.setdefault(state_id, set())
            options = props.get("options", [])
            if options is None:
                options = []
            if not isinstance(options, list):
                self._issue(entry.path, f"{state_location}.properties.options", "expected array")
                continue
            for option_index, option in enumerate(options):
                option_location = f"{state_location}.properties.options[{option_index}]"
                option_props = self._merged_option_properties(option, visible)
                if option_props is None:
                    continue
                number = option_props.get("number")
                if isinstance(number, int):
                    used_numbers = option_numbers.setdefault(state_id, set())
                    if number in used_numbers:
                        self._issue(
                            entry.path, f"{option_location}.properties.number", f"duplicate option number {number}"
                        )
                    used_numbers.add(number)
                next_state = option_props.get("nextStateId")
                if isinstance(next_state, str) and next_state != "EXIT":
                    if next_state not in state_ids and not any(
                        get_state_id(candidate) == next_state for candidate in states[state_index + 1 :]
                    ):
                        self._issue(
                            entry.path, f"{option_location}.properties.nextStateId", f'unknown state "{next_state}"'
                        )
                    edges.setdefault(state_id, set()).add(next_state)
                elif next_state is not None and not isinstance(next_state, str):
                    self._issue(entry.path, f"{option_location}.properties.nextStateId", "expected string state id")
                self._validate_dialog_method(
                    entry.path,
                    f"{option_location}.properties.action",
                    option_props.get("action"),
                    dialog_class,
                    methods_by_class,
                    script_path,
                    "action",
                )
                self._validate_dialog_method(
                    entry.path,
                    f"{option_location}.properties.condition",
                    option_props.get("condition"),
                    dialog_class,
                    methods_by_class,
                    script_path,
                    "condition",
                )
        if "ENTRY" not in state_ids:
            self._issue(entry.path, f"{entry.key}.properties.states", "dialog is missing ENTRY state")
            return
        reachable = reachable_states(edges, "ENTRY")
        for state_id, state_index in state_ids.items():
            if state_id not in reachable and state_id != "EXIT":
                state = states[state_index]
                props = state.get("properties") if isinstance(state, dict) else {}
                if isinstance(props, dict) and props.get("condition"):
                    continue
                self._issue(
                    entry.path,
                    f"{entry.key}.properties.states[{state_index}].properties.stateId",
                    f'dialog state "{state_id}" is unreachable from ENTRY',
                )

    def _merged_option_properties(self, option: Any, visible: dict[str, ConfigEntry]) -> dict[str, Any] | None:
        if not isinstance(option, dict):
            return None
        merged: dict[str, Any] = {}
        ref = option.get("ref")
        if isinstance(ref, str):
            ref_entry = visible.get(ref)
            if ref_entry and isinstance(ref_entry.data, dict):
                ref_props = ref_entry.data.get("properties")
                if isinstance(ref_props, dict):
                    merged.update(ref_props)
        props = option.get("properties")
        if isinstance(props, dict):
            merged.update(props)
        return merged

    def _validate_dialog_method(
        self,
        path: Path,
        location: str,
        method: Any,
        dialog_class: Any,
        methods_by_class: dict[str, set[str]],
        script_path: Path,
        method_kind: str,
    ) -> None:
        if method is None:
            return
        if not isinstance(method, str):
            self._issue(path, location, f"expected string dialog {method_kind}")
            return
        if not isinstance(dialog_class, str):
            self._issue(path, location, f'dialog {method_kind} "{method}" has no dialog class')
            return
        available_methods = methods_by_class.get(dialog_class, set())
        if method not in available_methods:
            self._issue(
                path,
                location,
                f'dialog {method_kind} "{method}" is not defined on {dialog_class} in {self._rel(script_path)}',
            )

    def _validate_script_refs(
        self, context: MapContext, visible: dict[str, ConfigEntry], known_classes: set[str]
    ) -> None:
        if not context.script_info:
            return
        map_names = {map_context.name for map_context in self.map_contexts}
        object_names = context.placed_names | context.script_info.named_objects | {"player"}
        for call in context.script_info.calls:
            if call.name in SCRIPT_REF_CALLS:
                if call.value not in visible and call.value not in known_classes:
                    self._issue(
                        context.script_info.path,
                        call.location,
                        self._class_reference_message(call.value, "object ref or class"),
                    )
            elif call.name in SCRIPT_ITEM_CALLS:
                if call.value not in visible:
                    self._issue(context.script_info.path, call.location, f'unknown item ref "{call.value}"')
            elif call.name in SCRIPT_QUEST_CALLS:
                if call.value not in visible:
                    self._issue(context.script_info.path, call.location, f'unknown quest id "{call.value}"')
                elif not self._entry_is_quest(visible[call.value], visible):
                    self._issue(context.script_info.path, call.location, f'"{call.value}" does not resolve to a quest')
            elif call.name in SCRIPT_MAP_CALLS:
                if call.value not in map_names:
                    expected = f"res/maps/{call.value}/map.json"
                    self._issue(context.script_info.path, call.location, f"map transition target is missing {expected}")
            elif call.name in SCRIPT_OBJECT_NAME_CALLS and call.value not in object_names:
                self._issue(context.script_info.path, call.location, f'unknown map object name "{call.value}"')
        for trigger in context.script_info.trigger_targets:
            if trigger.name == "trigger event":
                if trigger.value not in KNOWN_EVENT_NAMES:
                    self._issue(context.script_info.path, trigger.location, f'unknown trigger event "{trigger.value}"')
            elif trigger.name == "trigger target" and trigger.value not in object_names:
                self._issue(context.script_info.path, trigger.location, f'unknown trigger target "{trigger.value}"')

    def _entry_is_quest(self, entry: ConfigEntry, visible: dict[str, ConfigEntry]) -> bool:
        resolved = self._resolve_entry(entry, visible)
        if not isinstance(resolved.data, dict):
            return False
        class_name = resolved.data.get("class")
        return isinstance(class_name, str) and (class_name == "CQuest" or class_name.endswith("Quest"))

    def _resolve_entry(self, entry: ConfigEntry, visible: dict[str, ConfigEntry]) -> ConfigEntry:
        current = entry
        seen: set[str] = set()
        while isinstance(current.data, dict) and isinstance(current.data.get("ref"), str):
            if current.key in seen:
                return current
            seen.add(current.key)
            next_entry = visible.get(current.data["ref"])
            if next_entry is None:
                return current
            current = next_entry
        return current

    def _validate_crafting_refs(self) -> None:
        crafting_path = self.repo_root / "res" / "config" / "crafting.json"
        data = self.global_files.get(crafting_path)
        if not isinstance(data, dict):
            return
        for recipe_name, recipe in data.items():
            if not isinstance(recipe, dict):
                self._issue(crafting_path, recipe_name, "expected recipe object")
                continue
            station = recipe.get("station")
            if isinstance(station, str) and station not in self._crafting_station_ids():
                self._issue(crafting_path, f"{recipe_name}.station", f'unknown crafting station "{station}"')
            inputs = recipe.get("inputs", [])
            if isinstance(inputs, list):
                for index, item in enumerate(inputs):
                    self._validate_recipe_item(crafting_path, f"{recipe_name}.inputs[{index}]", item)
            output = recipe.get("output")
            self._validate_recipe_item(crafting_path, f"{recipe_name}.output", output)

    def _validate_recipe_item(self, path: Path, location: str, item: Any) -> None:
        if not isinstance(item, dict):
            self._issue(path, location, "expected recipe item object")
            return
        item_name = item.get("item")
        if isinstance(item_name, str) and item_name not in self.global_entries:
            self._issue(path, f"{location}.item", f'unknown recipe item "{item_name}"')
        elif item_name is not None and not isinstance(item_name, str):
            self._issue(path, f"{location}.item", "expected string item id")

    def _crafting_station_ids(self) -> set[str]:
        station_ids: set[str] = set()
        for entry in self.global_entries.values():
            if not isinstance(entry.data, dict):
                continue
            properties = entry.data.get("properties")
            if not isinstance(properties, dict):
                continue
            station_id = properties.get("craftingStationId")
            if isinstance(station_id, str):
                station_ids.add(station_id)
        return station_ids

    def _issue(self, path: Path, location: str, message: str) -> None:
        self.issues.append(ValidationIssue(path=self._rel(path), location=location, message=message))

    def _rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return path.as_posix()

    def _is_object_node(self, value: dict[str, Any]) -> bool:
        has_ref = "ref" in value
        has_class = "class" in value
        return has_ref or (has_class and ("properties" in value or set(value) <= OBJECT_SCHEMA_KEYS))

    def _class_reference_message(self, class_name: str, label: str) -> str:
        if class_name in self.reviewed_abstract_internal_classes:
            return f'{label} "{class_name}" is reviewed as abstract/internal and cannot be used as content'
        if class_name in self.native_plugin_declared_class_sources:
            owners = ", ".join(sorted(self.native_plugin_declared_class_sources[class_name]))
            return f'{label} "{class_name}" is registered by native plugin code but no manifest entry loads {owners}'
        if class_name in self.metadata_declared_classes:
            return f'{label} "{class_name}" is declared in metadata but is not registered as constructible content'
        return f'unknown {label} "{class_name}"'


def iter_map_objects(map_data: Any) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    if not isinstance(map_data, dict):
        return objects
    layers = map_data.get("layers")
    if not isinstance(layers, list):
        return objects
    for layer in layers:
        if not isinstance(layer, dict) or layer.get("type") != "objectgroup":
            continue
        layer_objects = layer.get("objects")
        if isinstance(layer_objects, list):
            objects.extend(obj for obj in layer_objects if isinstance(obj, dict))
    return objects


def tile_types_by_id(map_data: Any) -> dict[int, str]:
    if not isinstance(map_data, dict):
        return {}
    tilesets = map_data.get("tilesets")
    if not isinstance(tilesets, list) or not tilesets or not isinstance(tilesets[0], dict):
        return {}
    tileproperties = tilesets[0].get("tileproperties")
    if not isinstance(tileproperties, dict):
        return {}
    tile_types: dict[int, str] = {}
    for raw_tile_id, tile_config in tileproperties.items():
        try:
            tile_id = int(raw_tile_id)
        except (TypeError, ValueError):
            continue
        if isinstance(tile_config, dict) and isinstance(tile_config.get("type"), str):
            tile_types[tile_id] = tile_config["type"]
    return tile_types


def normalize_cpp_type(raw: str) -> str:
    name = raw.strip()
    wrapper_match = re.match(r"CWrapper<\s*([A-Za-z_]\w*)\s*>?$", name)
    if wrapper_match:
        return wrapper_match.group(1)
    return re.sub(r"\s+", "", name)


def read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def iter_cpp_function_bodies(text: str) -> list[tuple[str, str]]:
    functions: list[tuple[str, str]] = []
    pattern = re.compile(
        r"(?:extern\s+\"C\"\s+)?(?:[A-Z_]+\s+)*bool\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*\{",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        body_start = match.end()
        depth = 1
        index = body_start
        while index < len(text) and depth:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        if depth == 0:
            functions.append((match.group(1), text[body_start : index - 1]))
    return functions


def iter_cpp_template_type_names(text: str, call_name: str) -> set[str]:
    names: set[str] = set()
    pattern = re.compile(rf"\b{re.escape(call_name)}\s*<\s*([^,;\n]+)")
    for match in pattern.finditer(text):
        name = normalize_cpp_type(match.group(1))
        if is_concrete_cpp_class_name(name):
            names.add(name)
    return names


def iter_manifest_plugin_entries(data: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    global_entries = data.get("global")
    if isinstance(global_entries, list):
        entries.extend(entry for entry in global_entries if isinstance(entry, dict))
    map_entries = data.get("maps")
    if isinstance(map_entries, dict):
        for map_plugins in map_entries.values():
            if isinstance(map_plugins, list):
                entries.extend(entry for entry in map_plugins if isinstance(entry, dict))
    return entries


def is_concrete_cpp_class_name(name: str) -> bool:
    return name != "CWrapper" and re.match(r"^C[A-Za-z_]\w*$", name) is not None


def append_field(location: str, key: Any) -> str:
    if isinstance(key, str) and re.match(r"^[A-Za-z_]\w*$", key):
        return f"{location}.{key}"
    return f"{location}[{json.dumps(key)}]"


def append_index(location: str, index: int) -> str:
    return f"{location}[{index}]"


def get_state_id(state: Any) -> str | None:
    if not isinstance(state, dict):
        return None
    props = state.get("properties")
    if not isinstance(props, dict):
        return None
    state_id = props.get("stateId")
    return state_id if isinstance(state_id, str) else None


def reachable_states(edges: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        state = pending.pop()
        if state in seen:
            continue
        seen.add(state)
        pending.extend(edges.get(state, set()) - seen)
    return seen


def validate_repo(repo_root: Path | str) -> list[ValidationIssue]:
    return ContentValidator(Path(repo_root)).validate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate game JSON resources and literal script refs.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    issues = validate_repo(args.repo_root)
    if issues:
        for issue in issues:
            print(issue)
        print(f"Content validation failed: {len(issues)} issue(s)", file=sys.stderr)
        return 1

    print("Content validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
