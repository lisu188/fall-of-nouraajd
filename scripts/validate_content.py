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
# Recognised kinds for an optional map.json top-level "assets" declaration. Each declared asset
# is a safe relative path under its own map directory; the kind documents how the entry resolves.
MAP_ASSET_KINDS = {"file", "directory", "animationRoot", "logicalId"}
# Player class/race profile config files and their allowed top-level profile keys. Profiles are
# data-only config entries (no "class"/"ref"), so the engine's config loader skips them; this
# validator gives them an explicit schema so malformed profiles are still caught.
PLAYER_CLASS_PROFILE_FILE = "classes.json"
PLAYER_RACE_PROFILE_FILE = "races.json"
PLAYER_CLASS_PROFILE_KEYS = {
    "profileKind",
    "label",
    "actions",
    "levelling",
    "statContribution",
    "startingEquipment",
}
PLAYER_RACE_PROFILE_KEYS = {"profileKind", "label", "baseStatContribution", "traits", "resistances", "visual"}
STARTING_EQUIPMENT_POLICIES = {"fixed", "none"}
SCRIPT_REF_CALLS = {"createObject", "addObjectByName"}
SCRIPT_ITEM_CALLS = {"addItem"}
SCRIPT_QUEST_CALLS = {"addQuest", "ensure_quest", "_grant_quest", "grant_quest"}
SCRIPT_MAP_CALLS = {"changeMap"}
SCRIPT_OBJECT_NAME_CALLS = {"getObjectByName", "removeObjectByName"}
SCRIPT_PROPERTY_READ_CALLS = {"getBoolProperty", "getNumericProperty", "getStringProperty"}
SCRIPT_PROPERTY_WRITE_CALLS = {"setBoolProperty", "setNumericProperty", "setStringProperty", "incProperty"}
SCRIPT_BOOL_PROPERTY_METHODS = {"getBoolProperty", "setBoolProperty"}
SCRIPT_PROPERTY_DEFAULT_WRITE_CALLS = {
    "_set_bool_property_default": "setBoolProperty",
    "_set_numeric_property_default": "setNumericProperty",
    "set_bool_property_default": "setBoolProperty",
    "set_numeric_property_default": "setNumericProperty",
}
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
REVIEWED_DYNAMIC_PROPERTIES = {
    # "race" is the CCreatureRace archetype reference reviewed by
    # _validate_creature_race_reference (EPIC_06/STORY_01/SUBSTORY_01); it is accepted
    # as a known dynamic property so its resolution is checked rather than rejected as
    # an unknown property.
    "CCreature": {"class", "race"},
    "CDialogState": {"condition"},
    "CScroll": {"singleUse"},
}
REVIEWED_DYNAMIC_PROPERTY_PREFIXES = {
    "CGameObject": ("campaign_", "plugin_", "quest_state_"),
}
PYTHON_REGISTRATION_DECORATORS = {"register", "trigger"}
TYPE_REGISTRATION_EXCLUSIONS_PATH = Path("scripts/type_registration_exclusions.json")

# Reflective dialog action/condition dispatch fails closed at runtime
# (res/game.py CDialog._get_public_callback): a config-driven callback name is
# rejected unless it is a public identifier that is not the dispatch entry point
# itself. Names rejected here would silently no-op (actions) or evaluate to false
# (conditions, hiding a guarded option) at runtime, so flag them at validation
# time instead of letting authors ship a callback that can never fire.
DIALOG_CALLBACK_DISPATCH_METHODS = {"invokeAction", "invokeCondition"}

# Creature archetype naming and compatibility policy (EPIC_01/STORY_03/SUBSTORY_04).
# Race template ids end with "Race", class template ids end with "Class", and the
# class reference is carried by the JSON property "creatureClass" -- never the bare
# "class" key, which is reserved as the object-constructor key.
CREATURE_RACES_CONFIG = "creature_races.json"
CREATURE_CLASSES_CONFIG = "creature_classes.json"
CREATURE_RACE_ID_SUFFIX = "Race"
CREATURE_CLASS_ID_SUFFIX = "Class"
CREATURE_CLASS_REFERENCE_PROPERTY = "creatureClass"
CREATURE_ARCHETYPE_ID_SUFFIXES = {
    CREATURE_RACES_CONFIG: CREATURE_RACE_ID_SUFFIX,
    CREATURE_CLASSES_CONFIG: CREATURE_CLASS_ID_SUFFIX,
}

# CCreatureClass.mainStat validation (EPIC_06/STORY_02/SUBSTORY_01).
# A creature class archetype names the stat it scales from via the "mainStat"
# property, which the engine resolves at runtime through CStats::getMainValue ->
# CStats::getNumericProperty(mainStat).  That lookup only succeeds when the value
# names one of CStats' numeric (int) metadata properties; a typo such as
# "strenght" would silently resolve to 0 main value at runtime.  The allowed names
# are derived from the live CStats metadata schema (the int-typed properties), never
# hard-coded, so the check stays in lockstep with src/core/CStats.h.  CCreatureClass
# configs do not exist on the current content, so this validator is forward-guarding
# and vacuously satisfied until such archetypes are authored.
CREATURE_CLASS_OBJECT_CLASS = "CCreatureClass"
CREATURE_CLASS_MAIN_STAT_PROPERTY = "mainStat"
MAIN_STAT_SCHEMA_CLASS = "CStats"
MAIN_STAT_NUMERIC_TYPE_TOKEN = "int"

# CCreatureClass action/levelling resolution policy (EPIC_06/STORY_02/SUBSTORY_02).
# A CCreatureClass definition grants interactions through two property blocks that
# the runtime loader resolves late: "actions" is a list of object nodes (each a
# ref or inline class) that must each resolve to a CInteraction, and "levelling" is
# a map keyed by the level at which an interaction is unlocked -- the keys must be
# positive-integer strings and the values must each resolve to a CInteraction. The
# same effective action id must not be granted twice within one class definition
# (whether through "actions" or "levelling"), since a duplicate silently shadows the
# earlier grant at load time instead of being reported.
CREATURE_CLASS_CONSTRUCTOR_CLASS = "CCreatureClass"
CREATURE_CLASS_ACTIONS_PROPERTY = "actions"
CREATURE_CLASS_LEVELLING_PROPERTY = "levelling"
INTERACTION_BASE_CLASS = "CInteraction"
# Explicit effect target routing (EPIC_06/STORY_01/SUBSTORY_03).  CInteraction routes
# its effect to the caster when "selfTarget" is true; a legacy compatibility fallback
# also routes a Buff-tagged effect to the caster even without selfTarget.  A caster-target
# ability must therefore declare selfTarget explicitly rather than lean on the tag, so the
# tag can go back to meaning only classification/stacking/UI/dispel.  This rule flags any
# interaction whose resolved effect carries the Buff tag but does not set selfTarget true.
INTERACTION_EFFECT_PROPERTY = "effect"
INTERACTION_SELF_TARGET_PROPERTY = "selfTarget"
EFFECT_TAGS_PROPERTY = "tags"
BUFF_EFFECT_TAG = "buff"

# CCreatureRace stat/action/type validation (EPIC_06/STORY_03/SUBSTORY_01).
# A CCreatureRace definition carries the per-race template fields the engine merges
# into a creature: "baseStats" is a CStats payload whose keys must each name a CStats
# metadata property (a typo such as "strenght" would be silently dropped at load
# time), "actions" is a list of object nodes that must each resolve to a CInteraction
# (the same resolution the class actions validator enforces), and "creatureType" /
# "subtypes" tag the race for type-driven lookups.  For now the type fields are
# DATA-ONLY -- the only rule is that "creatureType" is a non-empty string and every
# "subtypes" entry is a non-empty string; no mechanical type semantics are invented.
# The allowed baseStats keys are derived from the live CStats metadata schema so they
# stay in lockstep with src/core/CStats.h, and CInteraction resolution reuses the
# class-action helper.  CCreatureRace configs do not exist on current content, so this
# check is vacuously satisfied (forward-guarding) until such archetypes are authored.
CREATURE_RACE_CONSTRUCTOR_CLASS = "CCreatureRace"
CREATURE_RACE_BASE_STATS_PROPERTY = "baseStats"
CREATURE_RACE_ACTIONS_PROPERTY = "actions"
CREATURE_RACE_TYPE_PROPERTY = "creatureType"
CREATURE_RACE_SUBTYPES_PROPERTY = "subtypes"
CREATURE_RACE_STATS_SCHEMA_CLASS = "CStats"

# Archetype-definition base classes (EPIC_06/STORY_04/SUBSTORY_02).
# CCreatureRace and CCreatureClass configs are *referenced definitions* (a race or
# class template carried by a creature via the "creatureClass"/race reference
# property), never actors that can be instantiated onto a map or spawned at
# runtime.  Any config whose effective engine class is one of these -- or which is
# declared in the dedicated archetype config files -- must therefore be rejected
# when used as a concrete spawn target: map object types, map tile types, and
# createObject/addObjectByName script calls.
CREATURE_RACE_BASE_CLASS = "CCreatureRace"
CREATURE_CLASS_BASE_CLASS = "CCreatureClass"
CREATURE_ARCHETYPE_BASE_CLASSES = (CREATURE_RACE_BASE_CLASS, CREATURE_CLASS_BASE_CLASS)
CREATURE_ARCHETYPE_DEFINITION_CONFIGS = (CREATURE_RACES_CONFIG, CREATURE_CLASSES_CONFIG)

# CCreature.creatureClass reference resolution policy (EPIC_06/STORY_01/SUBSTORY_02).
# A CCreature config carries its class template through the JSON *property*
# "creatureClass" (CREATURE_CLASS_REFERENCE_PROPERTY) -- never the top-level object
# constructor key "class".  That property value is itself an object node (a ref or
# inline class) that the runtime loader resolves late; it must resolve, through any
# ref/config chain, to a definition whose effective engine class is or inherits
# CCreatureClass.  A value that is not an object node (a wrong-typed scalar/array), a
# ref that does not resolve to a known config (missing), and an object that resolves
# to a non-CCreatureClass class (wrong type) are each reported distinctly with the
# exact "...properties.creatureClass" path.  No creature on current content sets this
# property, so the check is forward-guarding and vacuously satisfied until authored.

# CCreature.race resolution policy (EPIC_06/STORY_01/SUBSTORY_01).
# A creature names its race archetype via the "race" property, which the runtime
# loader resolves late through the same ref/config machinery as any object node: the
# value is an object node ({"ref": "<raceId>"} or an inline {"class": ...}) whose
# effective engine class must be -- or inherit from -- CCreatureRace.  A reference to
# an unknown id, to a config whose class is not a CCreatureRace, or a wrong-typed
# (non-object) "race" value would silently resolve to no/wrong race at load time, so
# each is reported here against the exact path (e.g. configId.properties.race.ref).
# CCreature configs do not declare a "race" property on current content, so this
# check is forward-guarding and vacuously satisfied until such configs are authored.
CREATURE_RACE_PROPERTY = "race"

# Player-selectable race label uniqueness (EPIC_06/STORY_03/SUBSTORY_02).
# At character creation res/game.py turns the player-selectable race templates into a
# label->id selection map exactly the way player_class_options builds the class map:
#   label = race.getStringProperty("label") or race_id
#   options[label] = race_id
# The map is keyed by the display label (falling back to the template id when the race
# carries no "label"), so two player-selectable races that resolve to the same label
# would silently collapse to a single entry -- the second id overwrites the first and a
# player picking that label can never reach the shadowed race.  This check enforces that
# every player-selectable CCreatureRace's resolved label-or-id key is unique.  Only races
# whose "playerSelectable" property resolves true participate; non-selectable races never
# enter the selection map, so their labels are free to collide.  No CCreatureRace configs
# exist on current content, so this is forward-guarding and vacuously satisfied today.
CREATURE_RACE_PLAYER_SELECTABLE_PROPERTY = "playerSelectable"
CREATURE_RACE_LABEL_PROPERTY = "label"

# Gooby quest runtime-name preservation (EPIC_05/STORY_03/SUBSTORY_02).
# The Gooby hunt depends on a fixed spawn/rename chain in the nouraajd map script:
# CaveTrigger spawns the template named GOOBY_TEMPLATE_NAME ("gooby") and immediately
# renames the runtime object to GOOBY_RUNTIME_NAME ("gooby1") via
# setStringProperty("name", "gooby1"); GoobyTrigger then fires onDestroy against the
# runtime name "gooby1" and marks the main quest "gooby_slain".  Both names are
# load-bearing constants that a template migration must NOT rename: if the template id
# changed, createObject would spawn nothing; if the runtime name changed, the onDestroy
# trigger and quest-completion flow could never recognize the slain creature.  This
# guard fires only on a map that participates in the chain -- one that spawns the
# "gooby" template or wires a trigger against the "gooby1" runtime name -- so unrelated
# maps and synthetic fixtures stay unaffected, but the real chain is asserted whole.
GOOBY_TEMPLATE_NAME = "gooby"
GOOBY_RUNTIME_NAME = "gooby1"

# Map-local creature override inventory (EPIC_01/STORY_01/SUBSTORY_02).
# Map config files reference creature templates via "ref" plus a "properties" block
# that overrides template behavior.  Any override touching one of these properties
# carries map-local behavior (Pritz controllers, quest-item carriers, npc dressing)
# that a later template migration must preserve rather than flatten.  The native
# CCreature template spells "stats" as the baseStats/levelStats pair and "labels"
# as the singular "label" key, so both spellings are watched here.
CREATURE_BASE_CLASS = "CCreature"
# Player vs monster classification (EPIC_01/STORY_01/SUBSTORY_04).
# CPlayer derives from CCreature in engine metadata (src/object/CPlayer.h:
# V_META(CPlayer, CCreature, ...)), so getAllSubTypes("CCreature") -- used by
# CRngHandler to build the random-encounter creature table -- enumerates player
# templates alongside true monsters.  Classification below is derived purely from
# that metadata inheritance lineage (never from template-id name strings): a
# template is a player when its resolved class inherits CPlayer, and a monster
# when it inherits CCreature but not CPlayer.  The player templates that leak into
# the CCreature enumeration are flagged so random-encounter code can explicitly
# exclude them.
PLAYER_BASE_CLASS = "CPlayer"
# Class-identity checks (EPIC_06/STORY_03/SUBSTORY_05).  Map scripts gate
# class-specific content on the player's class identity.  The migrated form
# reads the explicit CPlayer "playerClassId" property (getPlayerClassId());
# the legacy form compares the raw type id (getTypeId()).  getPlayerClassId()
# falls back to getTypeId() when playerClassId is unset, so a player's valid
# class ids are its explicit playerClassId (when present) and its config id.
PLAYER_CLASS_ID_PROPERTY = "playerClassId"
PLAYER_CLASS_ID_METHOD = "getPlayerClassId"
LEGACY_CLASS_ID_METHOD = "getTypeId"
CREATURE_OVERRIDE_PROPERTIES = (
    "baseStats",
    "levelStats",
    "stats",
    "actions",
    "controller",
    "fightController",
    "affiliation",
    "items",
    "equipped",
    "sw",
    "animation",
    "npc",
    "label",
    "labels",
)

# Amulet quest item/runtime actor preservation (EPIC_05/STORY_02/SUBSTORY_02).
# The amulet quest's thief carrier ("goblinThief") owns the quest item as
# *quest-instance inventory*: the map config attaches "preciousAmulet" through the
# carrier's "items" override, and the map script spawns that carrier at runtime
# (createObject("goblinThief")) under the fixed object name "amuletGoblin", which the
# completion path resolves via getObjectByName("amuletGoblin") to despawn the thief.
# A later archetype migration must keep "preciousAmulet" as instance inventory on the
# thief carrier rather than relocate it onto a shared GoblinRace/thief class template,
# and must keep the runtime actor name resolvable.  This guard therefore asserts, on
# any map that declares the AMULET_CARRIER_CONFIG, that the carrier's effective items
# still include AMULET_QUEST_ITEM (following ref inheritance) and that the script
# spawns the carrier under AMULET_RUNTIME_ACTOR_NAME as a name that getObjectByName can
# resolve.  Maps that do not declare the carrier are vacuously satisfied.  Identifiers
# are matched structurally against config/script content, never inferred from prose.
AMULET_CARRIER_CONFIG = "goblinThief"
AMULET_QUEST_ITEM = "preciousAmulet"
AMULET_RUNTIME_ACTOR_NAME = "amuletGoblin"
CREATURE_ITEMS_PROPERTY = "items"

# Required production archetype enforcement (EPIC_06/STORY_04/SUBSTORY_01).
# Once the archetype migration is declared complete, every production
# CCreature/CPlayer config must declare BOTH its race (CREATURE_RACE_PROPERTY) and
# its class (CREATURE_CLASS_REFERENCE_PROPERTY) reference properties so that no
# production creature can silently remain on the legacy path -- with the only
# permitted gaps being entries listed in an explicit reviewed exception manifest
# (intended for low-level test fixtures, each exempted by exact config path + key
# with a reason).  The migration is NOT complete on current content -- the archetype
# config files do not exist and essentially no production creature declares
# race/creatureClass yet -- so enforcement is gated behind ARCHETYPE_MIGRATION_COMPLETE
# and is fully inert (emits nothing) while that switch is False.  The standalone
# read-only report_unmigrated_creatures() inventory is unaffected and keeps working
# regardless of this switch.
ARCHETYPE_MIGRATION_COMPLETE = False
CREATURE_REQUIRED_ARCHETYPE_PROPERTIES = (
    CREATURE_RACE_PROPERTY,
    CREATURE_CLASS_REFERENCE_PROPERTY,
)


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


@dataclass(frozen=True)
class CreatureOverride:
    path: str
    key: str
    location: str
    template: str
    properties: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "key": self.key,
            "location": self.location,
            "template": self.template,
            "properties": list(self.properties),
        }

    def __str__(self) -> str:
        return f"{self.path}: {self.location}: ref \"{self.template}\" overrides {', '.join(self.properties)}"


@dataclass(frozen=True)
class CreatureClassification:
    """Metadata-inheritance partition of CCreature templates into players vs monsters.

    Derived solely from engine class lineage (CPlayer derives from CCreature), not
    from template-id naming heuristics.  ``players_in_creature_enumeration`` lists the
    player templates that getAllSubTypes("CCreature") returns, so random-encounter
    code can explicitly exclude them.
    """

    player_templates: tuple[str, ...]
    monster_templates: tuple[str, ...]
    players_in_creature_enumeration: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "playerTemplates": list(self.player_templates),
            "monsterTemplates": list(self.monster_templates),
            "playersInCreatureEnumeration": list(self.players_in_creature_enumeration),
        }


@dataclass(frozen=True)
class UnmigratedCreature:
    """A production CCreature/CPlayer config still missing race/creatureClass migration.

    ``config_id`` is the global config key and ``path`` the file that declares it.
    ``missing`` is the sorted tuple of archetype reference properties absent from the
    config's ``properties`` block -- a subset of {"race", "creatureClass"}.  This is a
    purely informational report (it never emits validation issues or affects exit
    status); it drives one migration ticket per remaining creature family so a partial
    archetype migration cannot ship silently.
    """

    config_id: str
    path: str
    missing: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "configId": self.config_id,
            "path": self.path,
            "missing": list(self.missing),
        }

    def __str__(self) -> str:
        return f"{self.path}: {self.config_id}: missing {', '.join(self.missing)}"


@dataclass(frozen=True)
class LegacyClassCheck:
    """A legacy getTypeId()-based player class check pending migration.

    ``path`` is the script file, ``context`` the class/method location, ``lineno``
    the source line, and ``class_id`` the player class id compared against.  This
    is a purely informational migration report: it never emits validation issues
    or affects exit status, so existing ``getTypeId()`` class checks keep working
    during the compatibility phase while still being surfaced for migration to
    ``getPlayerClassId()``.
    """

    path: str
    context: str
    lineno: int
    class_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "context": self.context,
            "lineno": self.lineno,
            "classId": self.class_id,
        }

    def __str__(self) -> str:
        location = f"{self.context}:{self.lineno}" if self.context else f"line {self.lineno}"
        return f'{self.path}: {location}: getTypeId() == "{self.class_id}"'


@dataclass(frozen=True)
class RegistrationExclusionUse:
    path: str
    location: str
    reason: str


@dataclass(frozen=True)
class RegistrationExclusion:
    class_name: str
    reason: str
    owner_module: str
    allowed_uses: tuple[RegistrationExclusionUse, ...] = ()


@dataclass(frozen=True)
class CppMetadataProperty:
    owner_class: str
    name: str
    type_token: str


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


@dataclass(frozen=True)
class ScriptClassCheck:
    """A literal player class-identity comparison found in a map script.

    ``method`` is the class-id accessor being compared -- either the migrated
    ``getPlayerClassId`` or the legacy ``getTypeId`` -- and ``class_id`` is the
    string literal it is compared against.  ``receiver`` records the resolved
    receiver kind ("player" for player receivers) so legacy ``getTypeId`` checks
    can be scoped to player receivers, since ``getTypeId`` is a generic accessor
    that legitimately compares non-player objects.  Only literal comparisons in
    the script source are captured; nothing is inferred.
    """

    class_id: str
    method: str
    receiver: str
    lineno: int
    context: str

    @property
    def location(self) -> str:
        call = f'{self.method}() == "{self.class_id}"'
        return f"{self.context}:{self.lineno} {call}" if self.context else f"line {self.lineno} {call}"


@dataclass
class SpawnedCreature:
    """A creature template spawned at runtime via createObject/addObjectByName.

    ``template`` is the literal template id passed to the spawn call. ``runtime_name``
    is the post-spawn object name assigned through ``setStringProperty("name", ...)``
    when that name is a string literal, or ``None`` when the spawn stays anonymous or
    the name is computed (e.g. an f-string). These are recorded separately so the
    migration preserves both template ids and runtime names, which trigger validators
    special-case for runtime-spawned quest actors. Nothing here is inferred from design
    docs -- only literal values present in the script source are captured.
    """

    template: str
    spawn_call: str
    lineno: int
    context: str
    runtime_name: str | None = None

    @property
    def location(self) -> str:
        call = f'{self.spawn_call}("{self.template}")'
        return f"{self.context}:{self.lineno} {call}" if self.context else f"line {self.lineno} {call}"


@dataclass
class ScriptQuestStateUsage:
    storage_key: str | None = None
    default_state: str | None = None
    read_states: set[str] = field(default_factory=set)
    written_states: set[str] = field(default_factory=set)
    terminal_check_states: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ScriptLegacyBoolFlag:
    name: str
    quest: str
    states: tuple[str, ...]
    excluded_states: tuple[str, ...]
    lineno: int
    context: str

    @property
    def location(self) -> str:
        call = f'LegacyBoolFlag("{self.name}")'
        return f"{self.context}:{self.lineno} {call}" if self.context else f"line {self.lineno} {call}"


@dataclass(frozen=True)
class ScriptPropertyAccess:
    owner: str
    access: str
    name: str
    method: str
    lineno: int
    context: str

    @property
    def location(self) -> str:
        call = f'{self.method}("{self.name}")'
        return f"{self.context}:{self.lineno} {call}" if self.context else f"line {self.lineno} {call}"


@dataclass(frozen=True)
class ArchetypeMigrationException:
    """A reviewed exemption from the required-production-archetype rule.

    ``path`` is the repo-relative config file (e.g. "res/config/test_fixtures.json")
    and ``key`` the exact top-level config id within it that is allowed to remain on
    the legacy path without declaring race/creatureClass.  ``reason`` documents why the
    exemption is acceptable -- intended for low-level test fixtures, never production
    creatures.  An entry only suppresses diagnostics for the creature whose path AND
    key match exactly, so a manifest entry can never blanket-exempt real content.
    """

    path: str
    key: str
    reason: str


# Reviewed exemptions from the required-production-archetype rule.  Empty by default:
# no production creature is exempt, and low-level test fixtures are added here only
# with an exact path/key and a reason.  Honored only while ARCHETYPE_MIGRATION_COMPLETE
# is True (and even then, only for the exact path+key listed).
ARCHETYPE_MIGRATION_EXCEPTIONS: tuple[ArchetypeMigrationException, ...] = ()


@dataclass(frozen=True)
class ScriptPropertyHygieneAllowance:
    path: str
    owner: str
    name: str
    reason: str


SCRIPT_PROPERTY_HYGIENE_ALLOWLIST = (
    ScriptPropertyHygieneAllowance(
        path="res/maps/nouraajd/script.py",
        owner="player",
        name="CAN_CRAFT_SCROLLS",
        reason="Crafting recipes read this player compatibility flag through unlockFlag configuration.",
    ),
    ScriptPropertyHygieneAllowance(
        path="res/maps/nouraajd/script.py",
        owner="player",
        name="CAN_BREW_GREATER_POTIONS",
        reason="Crafting recipes read this player compatibility flag through unlockFlag configuration.",
    ),
    ScriptPropertyHygieneAllowance(
        path="res/maps/multilevel/script.py",
        owner="map",
        name="used_stairs_up",
        reason="Walkthrough and MCP validation read this map telemetry flag outside map script source.",
    ),
    ScriptPropertyHygieneAllowance(
        path="res/maps/multilevel/script.py",
        owner="map",
        name="used_stairs_down",
        reason="Walkthrough and MCP validation read this map telemetry flag outside map script source.",
    ),
    ScriptPropertyHygieneAllowance(
        path="res/maps/multilevel/script.py",
        owner="map",
        name="visited_multilevel_start",
        reason="Map entry marker is intentionally externally observable instead of read by map script source.",
    ),
    ScriptPropertyHygieneAllowance(
        path="res/maps/ritual/script.py",
        owner="map",
        name="ritual_started",
        reason="Walkthrough and MCP validation read this progression flag outside map script source.",
    ),
    ScriptPropertyHygieneAllowance(
        path="res/maps/siege/script.py",
        owner="map",
        name="campaign_completed",
        reason="Campaign completion marker is intentionally externally observable after quest completion.",
    ),
)


@dataclass
class ScriptInfo:
    path: Path
    classes: set[str] = field(default_factory=set)
    registered_classes: set[str] = field(default_factory=set)
    class_bases: dict[str, set[str]] = field(default_factory=dict)
    methods_by_class: dict[str, set[str]] = field(default_factory=dict)
    calls: list[ScriptCall] = field(default_factory=list)
    quest_grants: list[ScriptCall] = field(default_factory=list)
    quest_states: dict[str, ScriptQuestStateUsage] = field(default_factory=dict)
    legacy_bool_flags: list[ScriptLegacyBoolFlag] = field(default_factory=list)
    property_reads: list[ScriptPropertyAccess] = field(default_factory=list)
    property_writes: list[ScriptPropertyAccess] = field(default_factory=list)
    trigger_targets: list[ScriptCall] = field(default_factory=list)
    named_objects: set[str] = field(default_factory=set)
    spawned_creatures: list[SpawnedCreature] = field(default_factory=list)
    class_checks: list[ScriptClassCheck] = field(default_factory=list)


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
        self._state_alias_stack: list[dict[str, str]] = []
        self._string_values_stack: list[dict[str, set[str]]] = []
        # Maps a local variable name to the SpawnedCreature it was assigned from
        # (via createObject) so a later setStringProperty("name", ...) on that
        # variable can attach the runtime name. Scoped per function body.
        self._spawn_vars_stack: list[dict[str, SpawnedCreature]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.info.classes.add(node.name)
        base_names = {base_name for base in node.bases if (base_name := python_base_class_name(base))}
        if base_names:
            self.info.class_bases.setdefault(node.name, set()).update(base_names)
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
        self._state_alias_stack.append({})
        self._string_values_stack.append({})
        self._spawn_vars_stack.append({})
        for child in node.body:
            self.visit(child)
        self._spawn_vars_stack.pop()
        self._string_values_stack.pop()
        self._state_alias_stack.pop()
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        self._record_class_constant_assignment(node)
        self._record_local_assignment(node.targets, node.value)
        self._record_spawn_assignment(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if node.value is not None:
            self._record_class_constant_assignment(node)
            self._record_local_assignment([node.target], node.value)
            self._record_spawn_assignment([node.target], node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        name = call_name(node.func)
        if name:
            self._record_script_call(name, node)
            self._record_named_object(name, node)
            self._record_anonymous_spawn(name, node)
            self._record_runtime_spawn_name(name, node)
            self._record_quest_state_call(name, node)
            self._record_property_access(name, node)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> Any:
        self._record_quest_state_comparison(node, terminal=False)
        self._record_class_check_comparison(node)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> Any:
        if node.value is not None and self._is_terminal_state_context():
            self._record_terminal_state_checks(node.value)
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
            call = ScriptCall(name=name, value=literal, lineno=node.lineno, context=context)
            self.info.calls.append(call)
            if name in SCRIPT_QUEST_CALLS:
                self.info.quest_grants.append(call)

    def _record_named_object(self, name: str, node: ast.Call) -> None:
        if name == "setStringProperty" and len(node.args) >= 2:
            key = string_literal(node.args[0])
            value = string_literal(node.args[1])
            if key == "name" and value:
                self.info.named_objects.add(value)

    def _record_anonymous_spawn(self, name: str, node: ast.Call) -> None:
        """Record addObjectByName("template", ...) spawns, which are anonymous.

        addObjectByName instantiates a template directly on the map without binding
        a Python variable, so there is never a runtime name to attach.
        """
        if name != "addObjectByName":
            return
        template = first_string_arg(node)
        if template is None:
            return
        self.info.spawned_creatures.append(
            SpawnedCreature(
                template=template,
                spawn_call=name,
                lineno=node.lineno,
                context=self._context,
                runtime_name=None,
            )
        )

    def _record_spawn_assignment(self, targets: list[ast.expr], value: ast.AST) -> None:
        """Track ``var = ...createObject("template")`` so a later name write can attach.

        Records the SpawnedCreature immediately (template id) and remembers the local
        variable; the runtime name is filled in when a subsequent
        ``var.setStringProperty("name", literal)`` is seen in the same function scope.
        """
        if not self._spawn_vars_stack:
            return
        spawn_vars = self._spawn_vars_stack[-1]
        template = self._created_object_template(value)
        for target in targets:
            target_name = assigned_name(target)
            if target_name is None:
                continue
            if template is None:
                spawn_vars.pop(target_name, None)
                continue
            creature = SpawnedCreature(
                template=template,
                spawn_call="createObject",
                lineno=getattr(value, "lineno", 0),
                context=self._context,
                runtime_name=None,
            )
            self.info.spawned_creatures.append(creature)
            spawn_vars[target_name] = creature

    def _record_runtime_spawn_name(self, name: str, node: ast.Call) -> None:
        """Attach a literal runtime name to a tracked createObject spawn variable."""
        if name != "setStringProperty" or len(node.args) < 2:
            return
        if string_literal(node.args[0]) != "name":
            return
        runtime_name = string_literal(node.args[1])
        if runtime_name is None:
            return
        receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
        receiver_name = assigned_name(receiver) if receiver is not None else None
        if receiver_name is None or not self._spawn_vars_stack:
            return
        for spawn_vars in reversed(self._spawn_vars_stack):
            creature = spawn_vars.get(receiver_name)
            if creature is not None and creature.runtime_name is None:
                creature.runtime_name = runtime_name
                return

    def _created_object_template(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Call) and call_name(node.func) == "createObject":
            return first_string_arg(node)
        return None

    def _record_class_constant_assignment(self, node: ast.Assign | ast.AnnAssign) -> None:
        if not self._class_stack:
            return
        value = node.value
        if value is None:
            return
        for target in assignment_targets(node):
            name = assigned_name(target)
            if name == "QUEST_KEYS":
                self._record_quest_keys(value)
            elif name == "QUEST_DEFAULTS":
                self._record_quest_defaults(value)
            elif name == "LEGACY_BOOL_FLAGS":
                self._record_legacy_bool_flags(value, getattr(node, "lineno", 0))

    def _record_local_assignment(self, targets: list[ast.expr], value: ast.AST) -> None:
        if not self._state_alias_stack or not self._string_values_stack:
            return
        state_aliases = self._state_alias_stack[-1]
        string_values = self._string_values_stack[-1]
        quest_key = get_state_key(value)
        literal_values = self._literal_string_values(value)
        for target in targets:
            target_name = assigned_name(target)
            if target_name is None:
                continue
            if quest_key:
                state_aliases[target_name] = quest_key
            else:
                state_aliases.pop(target_name, None)
            if literal_values:
                string_values[target_name] = set(literal_values)
            else:
                string_values.pop(target_name, None)

    def _record_quest_keys(self, value: ast.AST) -> None:
        for quest_key, storage_key in literal_string_dict(value).items():
            self._quest_state_usage(quest_key).storage_key = storage_key

    def _record_quest_defaults(self, value: ast.AST) -> None:
        for quest_key, state in literal_string_dict(value).items():
            self._quest_state_usage(quest_key).default_state = state

    def _record_legacy_bool_flags(self, value: ast.AST, lineno: int) -> None:
        for call in iter_calls(value):
            if call_name(call.func) != "LegacyBoolFlag" or len(call.args) < 2:
                continue
            flag_name = string_literal(call.args[0])
            quest_key = string_literal(call.args[1])
            if not flag_name or not quest_key:
                continue
            self.info.legacy_bool_flags.append(
                ScriptLegacyBoolFlag(
                    name=flag_name,
                    quest=quest_key,
                    states=tuple(sorted(self._keyword_string_values(call, "states"))),
                    excluded_states=tuple(sorted(self._keyword_string_values(call, "excluded_states"))),
                    lineno=getattr(call, "lineno", lineno),
                    context=self._context,
                )
            )

    def _record_quest_state_call(self, name: str, node: ast.Call) -> None:
        if name in {"_set_state", "set_state"} and len(node.args) >= 2:
            quest_key = string_literal(node.args[0])
            if quest_key:
                for state in self._literal_string_values(node.args[1]):
                    self._quest_state_usage(quest_key).written_states.add(state)
        elif name == "state_in" and len(node.args) >= 2:
            quest_key = string_literal(node.args[0])
            if quest_key:
                for state in self._literal_string_values(node.args[1]):
                    self._quest_state_usage(quest_key).read_states.add(state)

    def _record_quest_state_comparison(self, node: ast.Compare, terminal: bool) -> None:
        operands = [node.left, *node.comparators]
        for index, operator in enumerate(node.ops):
            left = operands[index]
            right = operands[index + 1]
            if isinstance(operator, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                self._record_comparison_pair(left, right, terminal)
                self._record_comparison_pair(right, left, terminal)

    def _record_comparison_pair(self, state_expr: ast.AST, value_expr: ast.AST, terminal: bool) -> None:
        quest_key = self._state_key_from_expr(state_expr)
        if not quest_key:
            return
        states = self._literal_string_values(value_expr)
        if not states:
            return
        usage = self._quest_state_usage(quest_key)
        usage.read_states.update(states)
        if terminal:
            usage.terminal_check_states.update(states)

    def _record_class_check_comparison(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        for index, operator in enumerate(node.ops):
            if not isinstance(operator, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                continue
            left = operands[index]
            right = operands[index + 1]
            self._record_class_check_pair(left, right)
            self._record_class_check_pair(right, left)

    def _record_class_check_pair(self, call_expr: ast.AST, value_expr: ast.AST) -> None:
        detected = self._class_id_method_call(call_expr)
        if detected is None:
            return
        method, receiver = detected
        # getPlayerClassId is player-specific, so any comparison is a class check.
        # getTypeId is a generic accessor, so only treat it as a legacy class check
        # when it is called on a player receiver -- otherwise it is a normal object
        # type comparison (monsters, items, ...) that must not be flagged.
        if method == LEGACY_CLASS_ID_METHOD and receiver != "player":
            return
        for value in self._literal_string_values(value_expr):
            self.info.class_checks.append(
                ScriptClassCheck(
                    class_id=value,
                    method=method,
                    receiver=receiver,
                    lineno=getattr(call_expr, "lineno", 0),
                    context=self._context,
                )
            )

    def _class_id_method_call(self, node: ast.AST) -> tuple[str, str] | None:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and not node.args
            and not node.keywords
            and node.func.attr in (PLAYER_CLASS_ID_METHOD, LEGACY_CLASS_ID_METHOD)
        ):
            return node.func.attr, self._receiver_kind(node.func.value)
        return None

    def _record_terminal_state_checks(self, node: ast.AST) -> None:
        if isinstance(node, ast.Compare):
            self._record_quest_state_comparison(node, terminal=True)
            return
        if isinstance(node, ast.BoolOp):
            for value in node.values:
                self._record_terminal_state_checks(value)
            return
        if isinstance(node, ast.UnaryOp):
            self._record_terminal_state_checks(node.operand)
            return
        if isinstance(node, ast.Call) and call_name(node.func) == "state_in" and len(node.args) >= 2:
            quest_key = string_literal(node.args[0])
            if not quest_key:
                return
            states = self._literal_string_values(node.args[1])
            usage = self._quest_state_usage(quest_key)
            usage.read_states.update(states)
            usage.terminal_check_states.update(states)

    def _record_property_access(self, name: str, node: ast.Call) -> None:
        if name in SCRIPT_PROPERTY_READ_CALLS and node.args:
            self._record_property_accesses("read", name, self._property_receiver(node), node.args[0], node)
        elif name in SCRIPT_PROPERTY_WRITE_CALLS and node.args:
            self._record_property_accesses("write", name, self._property_receiver(node), node.args[0], node)
        elif name in SCRIPT_PROPERTY_DEFAULT_WRITE_CALLS and len(node.args) >= 2:
            self._record_property_accesses(
                "write",
                SCRIPT_PROPERTY_DEFAULT_WRITE_CALLS[name],
                self._receiver_kind(node.args[0]),
                node.args[1],
                node,
            )

    def _record_property_accesses(
        self, access: str, method: str, owner: str, property_expr: ast.AST, node: ast.Call
    ) -> None:
        target = self.info.property_reads if access == "read" else self.info.property_writes
        for property_name in self._literal_string_values(property_expr):
            target.append(
                ScriptPropertyAccess(
                    owner=owner,
                    access=access,
                    name=property_name,
                    method=method,
                    lineno=node.lineno,
                    context=self._context,
                )
            )

    def _property_receiver(self, node: ast.Call) -> str:
        if isinstance(node.func, ast.Attribute):
            return self._receiver_kind(node.func.value)
        return "unknown"

    def _receiver_kind(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            if node.id == "player" or node.id.endswith("_player"):
                return "player"
            if node.id in {"game_map", "map"} or node.id.endswith("_map"):
                return "map"
            return "unknown"
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr == "map":
                return "map"
            return self._receiver_kind(node.value)
        if isinstance(node, ast.Call):
            name = call_name(node.func)
            if name == "getPlayer":
                return "player"
            if name == "getMap":
                return "map"
            if name in {"getObjectByName", "createObject", "getCause"}:
                return "object"
            if isinstance(node.func, ast.Attribute):
                return self._receiver_kind(node.func.value)
        return "unknown"

    def _literal_string_values(self, node: ast.AST) -> set[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values: set[str] = set()
            for element in node.elts:
                values.update(self._literal_string_values(element))
            return values
        if isinstance(node, ast.IfExp):
            return self._literal_string_values(node.body) | self._literal_string_values(node.orelse)
        if isinstance(node, ast.Name) and self._string_values_stack:
            for string_values in reversed(self._string_values_stack):
                if node.id in string_values:
                    return set(string_values[node.id])
        return set()

    def _keyword_string_values(self, node: ast.Call, keyword_name: str) -> set[str]:
        for keyword in node.keywords:
            if keyword.arg == keyword_name:
                return self._literal_string_values(keyword.value)
        return set()

    def _state_key_from_expr(self, node: ast.AST) -> str | None:
        quest_key = get_state_key(node)
        if quest_key:
            return quest_key
        if isinstance(node, ast.Name) and self._state_alias_stack:
            for state_aliases in reversed(self._state_alias_stack):
                if node.id in state_aliases:
                    return state_aliases[node.id]
        return None

    def _quest_state_usage(self, quest_key: str) -> ScriptQuestStateUsage:
        return self.info.quest_states.setdefault(quest_key, ScriptQuestStateUsage())

    def _is_terminal_state_context(self) -> bool:
        if not self._function_stack:
            return False
        function_name = self._function_stack[-1]
        return (
            function_name == "isCompleted"
            or function_name == "victor_has_ended"
            or function_name.startswith("is_")
            or function_name.endswith(
                ("_completed", "_delivered", "_returned", "_ended", "_done", "_purged", "_good_end", "_bad_end")
            )
        )

    @property
    def _context(self) -> str:
        function_stack = self._function_stack
        if self._class_stack and function_stack and function_stack[0] == "load":
            function_stack = function_stack[1:]
        return ".".join([*self._class_stack, *function_stack])


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


def assignment_targets(node: ast.Assign | ast.AnnAssign) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        return node.targets
    return [node.target]


def assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def get_state_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and call_name(node.func) == "get_state" and node.args:
        return string_literal(node.args[0])
    return None


def literal_string_dict(node: ast.AST) -> dict[str, str]:
    if not isinstance(node, ast.Dict):
        return {}
    values: dict[str, str] = {}
    for key_node, value_node in zip(node.keys, node.values):
        key = string_literal(key_node) if key_node is not None else None
        value = string_literal(value_node)
        if key is not None and value is not None:
            values[key] = value
    return values


def iter_calls(node: ast.AST) -> list[ast.Call]:
    return [child for child in ast.walk(node) if isinstance(child, ast.Call)]


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


def is_safe_map_relative_path(path: str) -> bool:
    """Return True when ``path`` is a safe POSIX-style relative path under a map directory.

    Rejects absolute paths, Windows-style separators or drive letters, leading slashes, and any
    ``.``/``..``/empty path segment so a declared asset can never escape its own map directory.
    """
    if not isinstance(path, str) or not path or path != path.strip():
        return False
    if "\\" in path or ":" in path or path.startswith("/"):
        return False
    return all(segment not in ("", ".", "..") for segment in path.split("/"))


class ContentValidator:
    def __init__(
        self,
        repo_root: Path,
        property_hygiene_allowlist: tuple[ScriptPropertyHygieneAllowance, ...] | None = None,
        archetype_migration_complete: bool | None = None,
        archetype_migration_exceptions: tuple[ArchetypeMigrationException, ...] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.issues: list[ValidationIssue] = []
        self.global_entries: dict[str, ConfigEntry] = {}
        self.global_files: dict[Path, Any] = {}
        self.map_contexts: list[MapContext] = []
        self.plugin_info: list[ScriptInfo] = []
        self.fallback_registered_classes: set[str] = set(BUILTIN_CLASSES)
        self.metadata_declared_classes: set[str] = set()
        self.metadata_class_bases: dict[str, str | None] = {}
        self.metadata_properties: dict[str, dict[str, CppMetadataProperty]] = {}
        self._metadata_property_schema_cache: dict[str, dict[str, CppMetadataProperty] | None] = {}
        self.static_registered_classes: set[str] = set()
        self.native_plugin_registered_classes: set[str] = set()
        self.native_plugin_declared_class_sources: dict[str, set[str]] = {}
        self.python_registered_classes: set[str] = set()
        self.python_class_bases: dict[str, set[str]] = {}
        self.registration_exclusions: dict[str, RegistrationExclusion] = {}
        self.property_hygiene_allowlist = (
            SCRIPT_PROPERTY_HYGIENE_ALLOWLIST if property_hygiene_allowlist is None else property_hygiene_allowlist
        )
        # Required-production-archetype enforcement is gated behind this switch so the
        # rule stays fully inert on pre-migration content; defaults to the module-level
        # ARCHETYPE_MIGRATION_COMPLETE (False today) and is overridable for fixture tests.
        self.archetype_migration_complete = (
            ARCHETYPE_MIGRATION_COMPLETE if archetype_migration_complete is None else archetype_migration_complete
        )
        self.archetype_migration_exceptions = (
            ARCHETYPE_MIGRATION_EXCEPTIONS if archetype_migration_exceptions is None else archetype_migration_exceptions
        )

    def validate(self) -> list[ValidationIssue]:
        self._collect_engine_classes()
        self._collect_plugin_classes()
        self._load_type_registration_exclusions()
        self._load_global_configs()
        self._load_maps()
        self._validate_global_configs()
        for context in self.map_contexts:
            self._validate_map_context(context)
        return sorted(self.issues, key=lambda issue: (issue.path, issue.location, issue.message))

    def inventory_creature_overrides(self) -> list[CreatureOverride]:
        """Enumerate every map-local creature reference that overrides template behavior.

        This shares the class-resolution machinery used by validation but does not
        emit validation issues or affect exit status; it is a read-only report used
        to guard a later creature-template migration against losing map-local
        behavior (controllers, quest-item carriers, npc dressing).
        """
        self._collect_engine_classes()
        self._collect_plugin_classes()
        self._load_global_configs()
        self._load_maps()
        overrides: list[CreatureOverride] = []
        for context in self.map_contexts:
            visible = self._visible_entries(context)
            for entry in context.config_entries.values():
                self._collect_creature_overrides(entry.path, entry.key, entry.key, entry.data, visible, overrides)
        return sorted(overrides, key=lambda override: (override.path, override.location))

    def classify_creature_templates(self) -> CreatureClassification:
        """Partition global CCreature templates into players vs monsters by metadata.

        A template is classified by resolving its effective engine class (following
        ``ref`` chains) and walking the C++ metadata inheritance lineage: it is a
        player when the class inherits ``CPlayer`` and a (non-player) monster when it
        inherits ``CCreature`` but not ``CPlayer``.  No template-id name strings are
        consulted.  Player templates that fall inside the broader CCreature lineage --
        i.e. those that getAllSubTypes("CCreature") would enumerate for random
        encounters -- are also reported separately so encounter code can exclude them.
        """
        self._collect_engine_classes()
        self._collect_plugin_classes()
        self._load_global_configs()
        visible = dict(self.global_entries)
        players: list[str] = []
        monsters: list[str] = []
        for key, entry in self.global_entries.items():
            if not isinstance(entry.data, dict):
                continue
            class_name = self._effective_object_class(entry.data, visible)
            if not isinstance(class_name, str):
                continue
            if not (class_name == CREATURE_BASE_CLASS or self._class_inherits_from(class_name, CREATURE_BASE_CLASS)):
                continue
            if self._class_inherits_from(class_name, PLAYER_BASE_CLASS):
                players.append(key)
            else:
                monsters.append(key)
        players.sort()
        monsters.sort()
        return CreatureClassification(
            player_templates=tuple(players),
            monster_templates=tuple(monsters),
            # CPlayer inherits CCreature, so every player template is also returned by
            # the CCreature subtype enumeration that random-encounter code relies on.
            players_in_creature_enumeration=tuple(players),
        )

    def report_unmigrated_creatures(self) -> list[UnmigratedCreature]:
        """List production CCreature/CPlayer configs missing race and/or creatureClass.

        Resolves each global config's effective engine class (following ``ref`` chains)
        and selects those whose class is, or inherits from, ``CCreature`` -- which also
        covers ``CPlayer`` templates since CPlayer derives from CCreature.  For each such
        config it inspects the ``properties`` block for the archetype reference
        properties ``race`` (CREATURE_RACE_PROPERTY) and ``creatureClass``
        (CREATURE_CLASS_REFERENCE_PROPERTY) and records whichever are absent.  This is a
        read-only report: it shares the validation class-resolution machinery but never
        emits validation issues or changes exit status, so the normal validation run --
        which today would flag every still-unmigrated creature -- stays green.  Results
        are sorted by config id for deterministic output, and each missing-property list
        is itself sorted ("creatureClass" before "race").
        """
        self._collect_engine_classes()
        self._collect_plugin_classes()
        self._load_global_configs()
        visible = dict(self.global_entries)
        unmigrated: list[UnmigratedCreature] = []
        for key, entry in self.global_entries.items():
            if not isinstance(entry.data, dict):
                continue
            class_name = self._effective_object_class(entry.data, visible)
            if not isinstance(class_name, str):
                continue
            if not (class_name == CREATURE_BASE_CLASS or self._class_inherits_from(class_name, CREATURE_BASE_CLASS)):
                continue
            properties = entry.data.get("properties")
            properties = properties if isinstance(properties, dict) else {}
            missing = tuple(
                sorted(
                    name
                    for name in (CREATURE_CLASS_REFERENCE_PROPERTY, CREATURE_RACE_PROPERTY)
                    if name not in properties
                )
            )
            if missing:
                unmigrated.append(UnmigratedCreature(config_id=key, path=self._rel(entry.path), missing=missing))
        return sorted(unmigrated, key=lambda creature: (creature.config_id, creature.path))

    def report_legacy_class_checks(self) -> list[LegacyClassCheck]:
        """List legacy getTypeId()-based player class checks still awaiting migration.

        Loads maps and analyzes each map script for player class-identity comparisons,
        selecting the legacy ``getTypeId()`` form whose literal names a real player
        class id (i.e. one that should be rewritten as ``getPlayerClassId()``).  This
        is a read-only migration report: it shares the validation machinery but never
        emits validation issues or changes exit status, so existing getTypeId() class
        checks keep validating green during the compatibility phase.  Results are
        sorted for deterministic output.
        """
        self._collect_engine_classes()
        self._collect_plugin_classes()
        self._load_global_configs()
        self._load_maps()
        legacy: list[LegacyClassCheck] = []
        for context in self.map_contexts:
            script_info = context.script_info
            if script_info is None or not script_info.class_checks:
                continue
            known_ids = self._known_player_class_ids(self._visible_entries(context))
            for check in script_info.class_checks:
                if check.method != LEGACY_CLASS_ID_METHOD:
                    continue
                if check.class_id not in known_ids:
                    continue
                legacy.append(
                    LegacyClassCheck(
                        path=self._rel(script_info.path),
                        context=check.context,
                        lineno=check.lineno,
                        class_id=check.class_id,
                    )
                )
        return sorted(legacy, key=lambda entry: (entry.path, entry.lineno, entry.class_id))

    def _collect_creature_overrides(
        self,
        path: Path,
        key: str,
        location: str,
        value: Any,
        visible: dict[str, ConfigEntry],
        overrides: list[CreatureOverride],
    ) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if (
                isinstance(value.get("ref"), str)
                and isinstance(properties, dict)
                and self._is_creature_node(value, visible)
            ):
                overridden = tuple(name for name in CREATURE_OVERRIDE_PROPERTIES if name in properties)
                if overridden:
                    overrides.append(
                        CreatureOverride(
                            path=self._rel(path),
                            key=key,
                            location=location,
                            template=value["ref"],
                            properties=overridden,
                        )
                    )
            for child_key, child in value.items():
                self._collect_creature_overrides(
                    path, key, append_field(location, child_key), child, visible, overrides
                )
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._collect_creature_overrides(path, key, append_index(location, index), child, visible, overrides)

    def _is_creature_node(self, value: dict[str, Any], visible: dict[str, ConfigEntry]) -> bool:
        class_name = self._effective_object_class(value, visible)
        if not isinstance(class_name, str):
            return False
        if class_name == CREATURE_BASE_CLASS:
            return True
        return self._class_inherits_from(class_name, CREATURE_BASE_CLASS)

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
                for class_name, base_class, properties in iter_cpp_metadata_declarations(text):
                    self.metadata_declared_classes.add(class_name)
                    self.metadata_class_bases.setdefault(class_name, base_class)
                    if base_class is not None:
                        self.metadata_class_bases[class_name] = base_class
                    class_properties = self.metadata_properties.setdefault(class_name, {})
                    for cpp_property in properties:
                        class_properties[cpp_property.name] = cpp_property
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
                self._merge_python_class_bases(info)

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
            if script_info:
                self._merge_python_class_bases(script_info)
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

    def _merge_python_class_bases(self, info: ScriptInfo) -> None:
        for class_name, base_names in info.class_bases.items():
            self.python_class_bases.setdefault(class_name, set()).update(base_names)

    def _load_json(self, path: Path) -> Any:
        if not path.exists():
            self._issue(path, "$", "missing required JSON file")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._issue(path, f"line {exc.lineno} column {exc.colno}", exc.msg)
            return None

    def _load_type_registration_exclusions(self) -> None:
        path = self.repo_root / TYPE_REGISTRATION_EXCLUSIONS_PATH
        if not path.exists():
            return
        data = self._load_json(path)
        if data is None:
            return
        if not isinstance(data, dict):
            self._issue(path, "$", "expected top-level JSON object")
            return
        exclusions = data.get("exclusions")
        if not isinstance(exclusions, list):
            self._issue(path, "exclusions", "expected array")
            return
        for index, raw_entry in enumerate(exclusions):
            location = f"exclusions[{index}]"
            exclusion = self._parse_registration_exclusion(path, location, raw_entry)
            if not exclusion:
                continue
            if exclusion.class_name in self.registration_exclusions:
                self._issue(path, f"{location}.className", f'duplicate exclusion for "{exclusion.class_name}"')
                continue
            if exclusion.class_name not in self._known_registration_exclusion_classes():
                self._issue(
                    path,
                    f"{location}.className",
                    f'excluded class "{exclusion.class_name}" is not metadata-declared or registered',
                )
                continue
            self.registration_exclusions[exclusion.class_name] = exclusion

    def _parse_registration_exclusion(self, path: Path, location: str, raw_entry: Any) -> RegistrationExclusion | None:
        if not isinstance(raw_entry, dict):
            self._issue(path, location, "expected exclusion object")
            return None
        class_name = raw_entry.get("className")
        reason = raw_entry.get("reason")
        owner_module = raw_entry.get("ownerModule")
        valid = True
        if not isinstance(class_name, str) or not class_name:
            self._issue(path, f"{location}.className", "expected non-empty class name")
            valid = False
        if not isinstance(reason, str) or not reason:
            self._issue(path, f"{location}.reason", "expected non-empty reason")
            valid = False
        if not isinstance(owner_module, str) or not owner_module:
            self._issue(path, f"{location}.ownerModule", "expected non-empty owner/module")
            valid = False
        allowed_uses = self._parse_registration_exclusion_allowed_uses(
            path, f"{location}.allowedUses", raw_entry.get("allowedUses", [])
        )
        if not valid or allowed_uses is None:
            return None
        return RegistrationExclusion(
            class_name=class_name,
            reason=reason,
            owner_module=owner_module,
            allowed_uses=tuple(allowed_uses),
        )

    def _parse_registration_exclusion_allowed_uses(
        self, path: Path, location: str, raw_uses: Any
    ) -> list[RegistrationExclusionUse] | None:
        if not isinstance(raw_uses, list):
            self._issue(path, location, "expected array")
            return None
        allowed_uses: list[RegistrationExclusionUse] = []
        for index, raw_use in enumerate(raw_uses):
            use_location = f"{location}[{index}]"
            if not isinstance(raw_use, dict):
                self._issue(path, use_location, "expected allowed use object")
                return None
            use_path = raw_use.get("path")
            use_config_location = raw_use.get("location")
            reason = raw_use.get("reason")
            valid = True
            if not isinstance(use_path, str) or not use_path:
                self._issue(path, f"{use_location}.path", "expected non-empty path")
                valid = False
            if not isinstance(use_config_location, str) or not use_config_location:
                self._issue(path, f"{use_location}.location", "expected non-empty location")
                valid = False
            if not isinstance(reason, str) or not reason:
                self._issue(path, f"{use_location}.reason", "expected non-empty reason")
                valid = False
            if not valid:
                return None
            allowed_uses.append(RegistrationExclusionUse(path=use_path, location=use_config_location, reason=reason))
        return allowed_uses

    def _known_registration_exclusion_classes(self) -> set[str]:
        return (
            self.fallback_registered_classes
            | self.metadata_declared_classes
            | self.static_registered_classes
            | self.native_plugin_registered_classes
            | self.python_registered_classes
        )

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
        self._validate_creature_archetype_naming()
        self._validate_duplicate_player_selectable_race_labels(visible)
        self._validate_required_production_archetypes(visible)
        self._validate_profile_configs()

    def _validate_map_context(self, context: MapContext) -> None:
        visible = self._visible_entries(context)
        known_classes = self._known_classes(context)
        archetype_ids = self._archetype_definition_ids(visible)
        for entry in context.config_entries.values():
            self._validate_config_entry(entry, visible, known_classes)
        self._validate_top_level_ref_cycles(context, visible)
        self._validate_map_json(context, visible, known_classes, archetype_ids)
        self._validate_map_assets(context)
        self._validate_dialogs(context, visible)
        self._validate_script_refs(context, visible, known_classes, archetype_ids)
        self._validate_gooby_runtime_names(context)
        self._validate_class_id_references(context, visible)
        self._validate_script_property_hygiene(context)
        self._validate_quest_state_transitions(context)
        self._validate_amulet_quest_actor(context, visible)

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
        return classes - set(self.registration_exclusions)

    def _validate_config_entry(
        self, entry: ConfigEntry, visible: dict[str, ConfigEntry], known_classes: set[str]
    ) -> None:
        self._validate_object_shape(entry.path, entry.key, entry.data)
        self._validate_refs(entry.path, entry.key, entry.data, visible)
        self._validate_object_classes(entry.path, entry.key, entry.data, known_classes)
        self._validate_object_properties(entry.path, entry.key, entry.data, visible, known_classes)
        self._validate_creature_class_actions_levelling(entry.path, entry.key, entry.data, visible)
        self._validate_creature_class_property(entry.path, entry.key, entry.data, visible)
        self._validate_creature_race_definition(entry.path, entry.key, entry.data, visible)
        self._validate_interaction_self_target(entry.path, entry.key, entry.data, visible)

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
                class_location = f"{location}.class"
                if (
                    isinstance(class_name, str)
                    and class_name not in known_classes
                    and not self._excluded_use_is_allowed(path, class_location, class_name)
                ):
                    self._issue(path, class_location, self._class_reference_message(class_name, "class"))
                elif class_name is not None and not isinstance(class_name, str):
                    self._issue(path, class_location, "expected string class name")
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

    def _validate_object_properties(
        self, path: Path, location: str, value: Any, visible: dict[str, ConfigEntry], known_classes: set[str]
    ) -> None:
        if isinstance(value, dict):
            if self._is_object_node(value):
                self._validate_object_node_properties(path, location, value, visible, known_classes)
            for key, child in value.items():
                self._validate_object_properties(path, append_field(location, key), child, visible, known_classes)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_object_properties(path, append_index(location, index), child, visible, known_classes)

    def _validate_object_node_properties(
        self,
        path: Path,
        location: str,
        value: dict[str, Any],
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        properties = value.get("properties")
        if not isinstance(properties, dict):
            return
        class_name = self._effective_object_class(value, visible)
        if not class_name or class_name in self.python_registered_classes:
            return
        property_schema = self._metadata_property_schema(class_name)
        if property_schema is None:
            return
        dynamic_properties = REVIEWED_DYNAMIC_PROPERTIES.get(class_name, set())
        properties_location = append_field(location, "properties")
        for property_name, property_value in properties.items():
            if property_name in property_schema:
                self._validate_property_value_type(
                    path,
                    append_field(properties_location, property_name),
                    class_name,
                    property_schema[property_name],
                    property_value,
                    visible,
                    known_classes,
                )
                continue
            if property_name not in dynamic_properties and not self._is_reviewed_dynamic_property(
                class_name, property_name
            ):
                self._issue(
                    path,
                    append_field(properties_location, property_name),
                    f'unknown property "{property_name}" for class "{class_name}"',
                )
        self._validate_creature_class_main_stat(path, properties_location, class_name, properties)
        self._validate_creature_race_reference(
            path, properties_location, class_name, properties, visible, known_classes
        )

    def _validate_creature_race_reference(
        self,
        path: Path,
        properties_location: str,
        class_name: str,
        properties: dict[str, Any],
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        """Verify a CCreature.race resolves to a CCreatureRace definition.

        A creature names its race archetype through the "race" property, which the
        engine resolves through the same ref/config machinery as any object node.  The
        value must be an object node ({"ref": "<raceId>"} or an inline {"class": ...})
        whose effective engine class is -- or inherits from -- CCreatureRace.  An
        unknown reference, a reference to a config whose class is not a CCreatureRace,
        or a wrong-typed (non-object / class-less) "race" value would silently resolve
        to no/wrong race at load time, so each is reported against the exact path
        (e.g. configId.properties.race.ref).  CCreature configs do not declare a "race"
        property on current content, so this check is vacuously satisfied (forward
        guarding) until such configs are authored.
        """
        if class_name != CREATURE_BASE_CLASS and not self._class_inherits_from(class_name, CREATURE_BASE_CLASS):
            return
        if CREATURE_RACE_PROPERTY not in properties:
            return
        race_value = properties[CREATURE_RACE_PROPERTY]
        race_location = append_field(properties_location, CREATURE_RACE_PROPERTY)
        if not isinstance(race_value, dict):
            self._issue(
                path,
                race_location,
                f'property "{CREATURE_RACE_PROPERTY}" for class "{class_name}" expected object inheriting from '
                f'"{CREATURE_RACE_BASE_CLASS}"; got {json_value_kind(race_value)}',
            )
            return
        ref = race_value.get("ref")
        declared_class = race_value.get("class")
        if isinstance(ref, str):
            reference_location = append_field(race_location, "ref")
        elif isinstance(declared_class, str):
            reference_location = append_field(race_location, "class")
        else:
            reference_location = race_location
        if isinstance(ref, str) and ref not in visible:
            self._issue(
                path,
                reference_location,
                f'property "{CREATURE_RACE_PROPERTY}" for class "{class_name}" references unknown id "{ref}"; '
                f'expected a "{CREATURE_RACE_BASE_CLASS}" definition',
            )
            return
        actual_class = self._effective_object_class(race_value, visible)
        if actual_class is None:
            self._issue(
                path,
                reference_location,
                f'property "{CREATURE_RACE_PROPERTY}" for class "{class_name}" expected object inheriting from '
                f'"{CREATURE_RACE_BASE_CLASS}"; got object without class/ref',
            )
            return
        if actual_class not in known_classes:
            return
        if actual_class != CREATURE_RACE_BASE_CLASS and not self._class_inherits_from(
            actual_class, CREATURE_RACE_BASE_CLASS
        ):
            self._issue(
                path,
                reference_location,
                f'property "{CREATURE_RACE_PROPERTY}" for class "{class_name}" expected object inheriting from '
                f'"{CREATURE_RACE_BASE_CLASS}"; got "{actual_class}"',
            )

    def _validate_creature_class_main_stat(
        self,
        path: Path,
        properties_location: str,
        class_name: str,
        properties: dict[str, Any],
    ) -> None:
        """Verify a CCreatureClass.mainStat names a numeric CStats property.

        The engine resolves a creature class's main stat through
        ``CStats::getNumericProperty(mainStat)`` (CStats::getMainValue), so a
        non-empty ``mainStat`` must name one of CStats' numeric (int) metadata
        properties.  Empty, non-string, or typo values (e.g. "strenght") would
        resolve to a zero main value at runtime, so they are rejected here with the
        exact class config location.  The allowed names are derived from the live
        CStats metadata schema, so this stays in lockstep with src/core/CStats.h.
        ``CCreatureClass`` archetypes do not exist on current content, so this check
        is vacuously satisfied (forward-guarding) until they are authored.
        """
        if class_name != CREATURE_CLASS_OBJECT_CLASS and not self._class_inherits_from(
            class_name, CREATURE_CLASS_OBJECT_CLASS
        ):
            return
        if CREATURE_CLASS_MAIN_STAT_PROPERTY not in properties:
            return
        main_stat = properties[CREATURE_CLASS_MAIN_STAT_PROPERTY]
        main_stat_location = append_field(properties_location, CREATURE_CLASS_MAIN_STAT_PROPERTY)
        if not isinstance(main_stat, str) or not main_stat:
            self._issue(
                path,
                main_stat_location,
                f'property "{CREATURE_CLASS_MAIN_STAT_PROPERTY}" for class "{class_name}" '
                f"expected a non-empty numeric {MAIN_STAT_SCHEMA_CLASS} property name; "
                f"got {json_value_kind(main_stat)}",
            )
            return
        allowed_stats = self._numeric_main_stat_names()
        if allowed_stats is None:
            return
        if main_stat not in allowed_stats:
            self._issue(
                path,
                main_stat_location,
                f'property "{CREATURE_CLASS_MAIN_STAT_PROPERTY}" for class "{class_name}" '
                f'value "{main_stat}" is not a numeric {MAIN_STAT_SCHEMA_CLASS} property; '
                f"expected one of {', '.join(sorted(allowed_stats))}",
            )

    def _numeric_main_stat_names(self) -> set[str] | None:
        """Return CStats' numeric (int) metadata property names, or None if absent.

        Derived from the live CStats metadata schema so the allowed set never drifts
        from src/core/CStats.h.  Returns None when CStats metadata is unavailable
        (e.g. before the native sources exist), leaving the check inert rather than
        guessing a stat set.
        """
        property_schema = self._metadata_property_schema(MAIN_STAT_SCHEMA_CLASS)
        if not property_schema:
            return None
        return {
            cpp_property.name
            for cpp_property in property_schema.values()
            if cpp_property.type_token == MAIN_STAT_NUMERIC_TYPE_TOKEN
        }

    def _effective_object_class(
        self, value: dict[str, Any], visible: dict[str, ConfigEntry], seen_refs: set[str] | None = None
    ) -> str | None:
        class_name = value.get("class")
        if isinstance(class_name, str):
            return class_name
        ref = value.get("ref")
        if not isinstance(ref, str):
            return None
        seen = set(seen_refs or set())
        if ref in seen:
            return None
        seen.add(ref)
        ref_entry = visible.get(ref)
        if ref_entry is None or not isinstance(ref_entry.data, dict):
            return None
        return self._effective_object_class(ref_entry.data, visible, seen)

    def _metadata_property_schema(
        self, class_name: str, seen_classes: set[str] | None = None
    ) -> dict[str, CppMetadataProperty] | None:
        if seen_classes is None and class_name in self._metadata_property_schema_cache:
            return self._metadata_property_schema_cache[class_name]
        if class_name not in self.metadata_class_bases and class_name not in self.metadata_properties:
            if seen_classes is None:
                self._metadata_property_schema_cache[class_name] = None
            return None
        seen = set(seen_classes or set())
        if class_name in seen:
            return {}
        seen.add(class_name)
        properties: dict[str, CppMetadataProperty] = {}
        base_class = self.metadata_class_bases.get(class_name)
        if base_class:
            base_properties = self._metadata_property_schema(base_class, seen)
            if base_properties:
                properties.update(base_properties)
        properties.update(self.metadata_properties.get(class_name, {}))
        if seen_classes is None:
            self._metadata_property_schema_cache[class_name] = properties
        return properties

    def _validate_property_value_type(
        self,
        path: Path,
        location: str,
        class_name: str,
        cpp_property: CppMetadataProperty,
        value: Any,
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        expected_kind = expected_json_property_kind(cpp_property.type_token)
        if expected_kind is None:
            return
        actual_kind = json_value_kind(value)
        if actual_kind != expected_kind:
            self._issue(
                path,
                location,
                f'property "{cpp_property.name}" for class "{class_name}" expected {expected_kind}; got {actual_kind}',
            )
            return
        expected_base_class = expected_cpp_object_base_class(cpp_property.type_token)
        if expected_base_class is not None:
            self._validate_property_object_compatibility(
                path,
                location,
                class_name,
                cpp_property,
                value,
                expected_base_class,
                visible,
                known_classes,
            )

    def _validate_property_object_compatibility(
        self,
        path: Path,
        location: str,
        class_name: str,
        cpp_property: CppMetadataProperty,
        value: Any,
        expected_base_class: str,
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._validate_property_object_value_compatibility(
                    path,
                    append_index(location, index),
                    class_name,
                    cpp_property,
                    item,
                    expected_base_class,
                    visible,
                    known_classes,
                )
            return
        self._validate_property_object_value_compatibility(
            path,
            location,
            class_name,
            cpp_property,
            value,
            expected_base_class,
            visible,
            known_classes,
        )

    def _validate_property_object_value_compatibility(
        self,
        path: Path,
        location: str,
        class_name: str,
        cpp_property: CppMetadataProperty,
        value: Any,
        expected_base_class: str,
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
    ) -> None:
        if not isinstance(value, dict):
            self._issue(
                path,
                location,
                (
                    f'property "{cpp_property.name}" for class "{class_name}" expected object inheriting from '
                    f'"{expected_base_class}"; got {json_value_kind(value)}'
                ),
            )
            return
        actual_class = self._effective_object_class(value, visible)
        if actual_class is None:
            self._issue(
                path,
                location,
                (
                    f'property "{cpp_property.name}" for class "{class_name}" expected object inheriting from '
                    f'"{expected_base_class}"; got object without class/ref'
                ),
            )
            return
        if actual_class not in known_classes:
            return
        if not self._class_inherits_from(actual_class, expected_base_class):
            self._issue(
                path,
                location,
                (
                    f'property "{cpp_property.name}" for class "{class_name}" expected object inheriting from '
                    f'"{expected_base_class}"; got "{actual_class}"'
                ),
            )

    def _class_inherits_from(self, class_name: str, expected_base_class: str) -> bool:
        seen: set[str] = set()
        stack = [class_name]
        while stack:
            current = stack.pop()
            if current == expected_base_class:
                return True
            if current in seen:
                continue
            seen.add(current)
            base_class = self.metadata_class_bases.get(current)
            if base_class:
                stack.append(base_class)
            stack.extend(self.python_class_bases.get(current, set()))
        return False

    def _is_reviewed_dynamic_property(self, class_name: str, property_name: str) -> bool:
        for lineage_class in self._metadata_class_lineage(class_name):
            prefixes = REVIEWED_DYNAMIC_PROPERTY_PREFIXES.get(lineage_class, ())
            if any(property_name.startswith(prefix) for prefix in prefixes):
                return True
        return False

    def _metadata_class_lineage(self, class_name: str) -> tuple[str, ...]:
        lineage: list[str] = []
        seen: set[str] = set()
        current: str | None = class_name
        while current and current not in seen:
            lineage.append(current)
            seen.add(current)
            current = self.metadata_class_bases.get(current)
        return tuple(lineage)

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

    def _validate_map_json(
        self,
        context: MapContext,
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
        archetype_ids: set[str],
    ) -> None:
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
                    context, layer, layer_location, width, height, tile_types, visible, known_classes, archetype_ids
                )
            elif layer_type == "objectgroup":
                self._validate_object_layer(context, layer, layer_location, visible, known_classes, archetype_ids)

    def _validate_map_assets(self, context: MapContext) -> None:
        data = context.map_data
        if not isinstance(data, dict) or "assets" not in data:
            return
        assets = data.get("assets")
        if not isinstance(assets, list):
            self._issue(context.map_path, "assets", "expected array")
            return
        seen_paths: set[str] = set()
        for index, entry in enumerate(assets):
            location = f"assets[{index}]"
            if not isinstance(entry, dict):
                self._issue(context.map_path, location, "expected object with 'path' and 'kind'")
                continue
            path_value = entry.get("path")
            if not isinstance(path_value, str) or not path_value:
                self._issue(context.map_path, f"{location}.path", "expected non-empty string")
                continue
            if not is_safe_map_relative_path(path_value):
                self._issue(
                    context.map_path,
                    f"{location}.path",
                    "must be a safe relative path under the map directory (no absolute paths, '..' traversal, "
                    "backslashes, drive letters, or empty segments)",
                )
                continue
            if path_value in seen_paths:
                self._issue(context.map_path, f"{location}.path", f"duplicate asset declaration: {path_value}")
            seen_paths.add(path_value)
            kind = entry.get("kind")
            if not isinstance(kind, str) or kind not in MAP_ASSET_KINDS:
                self._issue(
                    context.map_path,
                    f"{location}.kind",
                    f"expected one of {sorted(MAP_ASSET_KINDS)}",
                )
                continue
            self._validate_map_asset_target(context, location, path_value, kind)

    def _validate_profile_configs(self) -> None:
        for path, data in self.global_files.items():
            if path.name == PLAYER_CLASS_PROFILE_FILE:
                self._validate_profile_file(path, data, "playerClass", PLAYER_CLASS_PROFILE_KEYS)
            elif path.name == PLAYER_RACE_PROFILE_FILE:
                self._validate_profile_file(path, data, "playerRace", PLAYER_RACE_PROFILE_KEYS)

    def _validate_profile_file(self, path: Path, data: Any, kind: str, allowed_keys: set[str]) -> None:
        if not isinstance(data, dict):
            self._issue(path, "$", "expected top-level JSON object")
            return
        for profile_id, profile in data.items():
            self._validate_profile_entry(path, profile_id, profile, kind, allowed_keys)

    def _validate_profile_entry(self, path: Path, profile_id: str, profile: Any, kind: str, allowed: set[str]) -> None:
        if not isinstance(profile, dict):
            self._issue(path, profile_id, "expected object")
            return
        if profile.get("profileKind") != kind:
            self._issue(path, f"{profile_id}.profileKind", f'expected "{kind}"')
        unexpected = sorted(set(profile) - allowed)
        if unexpected:
            self._issue(path, profile_id, f"unsupported profile keys: {', '.join(unexpected)}")
        label = profile.get("label")
        if not isinstance(label, str) or not label:
            self._issue(path, f"{profile_id}.label", "expected non-empty string")
        if kind == "playerClass":
            self._validate_string_list(path, f"{profile_id}.actions", profile.get("actions"), required=True)
            self._validate_string_valued_map(path, f"{profile_id}.levelling", profile.get("levelling"), required=True)
            self._validate_int_valued_map(
                path, f"{profile_id}.statContribution", profile.get("statContribution"), required=True
            )
            self._validate_starting_equipment(path, f"{profile_id}.startingEquipment", profile.get("startingEquipment"))
        else:
            self._validate_int_valued_map(
                path, f"{profile_id}.baseStatContribution", profile.get("baseStatContribution"), required=True
            )
            self._validate_string_list(path, f"{profile_id}.traits", profile.get("traits"), required=False)
            self._validate_int_valued_map(
                path, f"{profile_id}.resistances", profile.get("resistances"), required=False
            )

    def _validate_string_list(self, path: Path, location: str, value: Any, *, required: bool) -> None:
        if value is None:
            if required:
                self._issue(path, location, "expected array of non-empty strings")
            return
        if not isinstance(value, list):
            self._issue(path, location, "expected array")
            return
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item:
                self._issue(path, f"{location}[{index}]", "expected non-empty string")

    def _validate_string_valued_map(self, path: Path, location: str, value: Any, *, required: bool) -> None:
        if value is None:
            if required:
                self._issue(path, location, "expected object of non-empty string values")
            return
        if not isinstance(value, dict):
            self._issue(path, location, "expected object")
            return
        for key, item in value.items():
            if not isinstance(item, str) or not item:
                self._issue(path, f"{location}.{key}", "expected non-empty string")

    def _validate_int_valued_map(self, path: Path, location: str, value: Any, *, required: bool) -> None:
        if value is None:
            if required:
                self._issue(path, location, "expected object of integer values")
            return
        if not isinstance(value, dict):
            self._issue(path, location, "expected object")
            return
        for key, item in value.items():
            if isinstance(item, bool) or not isinstance(item, int):
                self._issue(path, f"{location}.{key}", "expected integer")

    def _validate_starting_equipment(self, path: Path, location: str, value: Any) -> None:
        if value is None:
            self._issue(path, location, "expected object with a 'policy'")
            return
        if not isinstance(value, dict):
            self._issue(path, location, "expected object")
            return
        policy = value.get("policy")
        if policy not in STARTING_EQUIPMENT_POLICIES:
            self._issue(path, f"{location}.policy", f"expected one of {sorted(STARTING_EQUIPMENT_POLICIES)}")
        if "slots" in value:
            self._validate_string_valued_map(path, f"{location}.slots", value.get("slots"), required=False)

    def _validate_map_asset_target(self, context: MapContext, location: str, path_value: str, kind: str) -> None:
        if kind == "logicalId":
            return
        target = context.directory / path_value
        if kind == "file":
            if not target.is_file():
                self._issue(context.map_path, f"{location}.path", f"declared file asset not found: {path_value}")
        elif kind == "directory":
            if not target.is_dir():
                self._issue(context.map_path, f"{location}.path", f"declared directory asset not found: {path_value}")
        elif kind == "animationRoot":
            if not target.is_dir() and not (context.directory / f"{path_value}.png").is_file():
                self._issue(
                    context.map_path,
                    f"{location}.path",
                    f"declared animation root resolves to neither a directory nor a '<path>.png' file: {path_value}",
                )

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
        archetype_ids: set[str],
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
            elif self._reject_archetype_spawn_target(
                context.map_path, f"{location}.data[{index}]", tile_type, "tile type", archetype_ids
            ):
                continue
            elif (
                tile_type not in visible
                and tile_type not in known_classes
                and not self._excluded_use_is_allowed(context.map_path, f"{location}.data[{index}]", tile_type)
            ):
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
        archetype_ids: set[str],
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
            elif self._reject_archetype_spawn_target(
                context.map_path, f"{object_location}.type", object_type, "object type", archetype_ids
            ):
                pass
            elif (
                object_type not in visible
                and object_type not in known_classes
                and not self._excluded_use_is_allowed(context.map_path, f"{object_location}.type", object_type)
            ):
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
        # Mirror the runtime fail-closed contract (res/game.py
        # CDialog._get_public_callback): empty / non-identifier / private
        # (leading underscore, dunder) / dispatch-entry-point names are rejected
        # reflectively, so such a config callback can never run.
        if not method:
            self._issue(path, location, f"empty dialog {method_kind} name")
            return
        if not method.isidentifier():
            self._issue(path, location, f'dialog {method_kind} "{method}" is not a valid method name')
            return
        if method.startswith("_"):
            self._issue(
                path,
                location,
                f'dialog {method_kind} "{method}" is private and is rejected by the reflective dispatch',
            )
            return
        if method in DIALOG_CALLBACK_DISPATCH_METHODS:
            self._issue(
                path,
                location,
                f'dialog {method_kind} "{method}" is the reflective dispatch entry point and cannot be a callback',
            )
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
        self,
        context: MapContext,
        visible: dict[str, ConfigEntry],
        known_classes: set[str],
        archetype_ids: set[str],
    ) -> None:
        if not context.script_info:
            return
        map_names = {map_context.name for map_context in self.map_contexts}
        object_names = context.placed_names | context.script_info.named_objects | {"player"}
        for call in context.script_info.calls:
            if call.name in SCRIPT_REF_CALLS:
                if self._reject_archetype_spawn_target(
                    context.script_info.path, call.location, call.value, "object ref or class", archetype_ids
                ):
                    continue
                if (
                    call.value not in visible
                    and call.value not in known_classes
                    and not self._excluded_use_is_allowed(context.script_info.path, call.location, call.value)
                ):
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

    def _known_player_class_ids(self, visible: dict[str, ConfigEntry]) -> set[str]:
        """Resolve the set of valid player class ids from CPlayer config templates.

        getPlayerClassId() returns a player's explicit "playerClassId" property when
        set, otherwise its config/type id.  A class check literal is therefore valid
        when it matches either the config id of a CPlayer template (resolving ``ref``
        chains, like every other class resolution here) or that template's explicit
        playerClassId override.  Derived purely from engine class lineage, never from
        template-id name strings.
        """
        ids: set[str] = set()
        for key, entry in visible.items():
            if not isinstance(entry.data, dict):
                continue
            class_name = self._effective_object_class(entry.data, visible)
            if not isinstance(class_name, str):
                continue
            if class_name != PLAYER_BASE_CLASS and not self._class_inherits_from(class_name, PLAYER_BASE_CLASS):
                continue
            ids.add(key)
            explicit = self._effective_property_value(entry.data, PLAYER_CLASS_ID_PROPERTY, visible)
            if isinstance(explicit, str) and explicit:
                ids.add(explicit)
        return ids

    def _validate_class_id_references(self, context: MapContext, visible: dict[str, ConfigEntry]) -> None:
        """Reject class-specific script content that references an unknown class id.

        A migrated ``getPlayerClassId() == "<id>"`` check must name a real player
        class id (a CPlayer template's config id or explicit playerClassId), so new
        class-specific content cannot silently gate on a class that does not exist.
        Legacy ``getTypeId()``-based class checks are still allowed during the
        compatibility phase (they are surfaced non-fatally by
        report_legacy_class_checks); they are only flagged here when they compare a
        player receiver against a real class id whose migrated accessor would be
        getPlayerClassId -- and even then only as the informational report, never as a
        blocking issue.
        """
        script_info = context.script_info
        if script_info is None or not script_info.class_checks:
            return
        known_ids = self._known_player_class_ids(visible)
        for check in script_info.class_checks:
            if check.method != PLAYER_CLASS_ID_METHOD:
                continue
            if check.class_id not in known_ids:
                self._issue(
                    script_info.path,
                    check.location,
                    f'player class check references unknown class id "{check.class_id}"; '
                    f"no CPlayer template declares it (known: {self._format_id_set(known_ids)})",
                )

    def _format_id_set(self, ids: set[str]) -> str:
        return ", ".join(sorted(ids)) if ids else "<none>"

    def _validate_amulet_quest_actor(self, context: MapContext, visible: dict[str, ConfigEntry]) -> None:
        """Guard that the amulet quest keeps its item carrier and runtime actor name.

        Vacuous unless this map declares the amulet thief carrier
        (AMULET_CARRIER_CONFIG).  When it does, two invariants are enforced so an
        archetype migration cannot quietly drop them:

        * The carrier still carries AMULET_QUEST_ITEM as quest-instance inventory --
            i.e. its effective "items" (resolving ``ref`` inheritance) reference the
            quest item by ref or by a node whose resolved "name" is the quest item.
            Reported against ``<carrier>.properties.items`` so the migration can see the
            item must stay on the instance rather than move to a race/class template.
        * The map script spawns the carrier under AMULET_RUNTIME_ACTOR_NAME and that
            name is recognized as a resolvable map object (the completion path resolves
            it via getObjectByName).  Reported against the spawning script.
        """
        carrier_entry = context.config_entries.get(AMULET_CARRIER_CONFIG)
        if carrier_entry is None:
            return
        if isinstance(carrier_entry.data, dict):
            items = self._effective_property_value(carrier_entry.data, CREATURE_ITEMS_PROPERTY, visible)
            if not self._items_reference(items, AMULET_QUEST_ITEM, visible):
                self._issue(
                    carrier_entry.path,
                    f"{append_field(AMULET_CARRIER_CONFIG, 'properties')}.{CREATURE_ITEMS_PROPERTY}",
                    f'amulet quest carrier "{AMULET_CARRIER_CONFIG}" must carry quest item '
                    f'"{AMULET_QUEST_ITEM}" as instance inventory; it must not be moved to a '
                    f"shared race/class template during the archetype migration",
                )

        info = context.script_info
        if info is None:
            return
        spawns_runtime_actor = any(
            spawn.template == AMULET_CARRIER_CONFIG and spawn.runtime_name == AMULET_RUNTIME_ACTOR_NAME
            for spawn in info.spawned_creatures
        )
        if not spawns_runtime_actor:
            self._issue(
                info.path,
                f'createObject("{AMULET_CARRIER_CONFIG}")',
                f'amulet quest runtime actor name "{AMULET_RUNTIME_ACTOR_NAME}" must be assigned to a '
                f'spawned "{AMULET_CARRIER_CONFIG}"; the completion path resolves it via '
                f"getObjectByName and would otherwise break",
            )
            return
        recognized_names = context.placed_names | info.named_objects | {"player"}
        if AMULET_RUNTIME_ACTOR_NAME not in recognized_names:
            self._issue(
                info.path,
                f'getObjectByName("{AMULET_RUNTIME_ACTOR_NAME}")',
                f'amulet quest runtime actor name "{AMULET_RUNTIME_ACTOR_NAME}" is not resolvable as a '
                f"map object name",
            )

    def _items_reference(self, items: Any, item_id: str, visible: dict[str, ConfigEntry]) -> bool:
        """Whether an "items" value references ``item_id`` by ref or resolved name."""
        if not isinstance(items, list):
            return False
        for entry in items:
            if not isinstance(entry, dict):
                continue
            if entry.get("ref") == item_id:
                return True
            name = self._effective_property_value(entry, "name", visible)
            if name == item_id:
                return True
        return False

    def _validate_gooby_runtime_names(self, context: MapContext) -> None:
        """Assert the Gooby quest spawn/rename chain keeps its load-bearing names.

        EPIC_05/STORY_03/SUBSTORY_02. The chain is: CaveTrigger
        ``createObject("gooby")`` -> ``setStringProperty("name", "gooby1")``, and a
        ``@trigger(..., "onDestroy", "gooby1")`` plus quest-completion flow that
        recognizes the runtime name "gooby1".  A migration must preserve both the
        template id "gooby" and the runtime name "gooby1"; renaming either silently
        breaks the spawn, the onDestroy trigger, or quest completion.

        The guard engages only on a map that already participates in the chain -- one
        that spawns the "gooby" template, or that renames a spawn to "gooby1", or that
        wires a trigger against the "gooby1" runtime name -- so unrelated maps and
        synthetic fixtures stay unaffected.  Once engaged it requires the full chain:
        a "gooby" template spawn that is renamed to "gooby1", and a trigger target
        recognizing "gooby1".  Every diagnostic reports the script path so an author
        sees exactly where the chain broke.
        """
        info = context.script_info
        if not info:
            return

        gooby_template_spawns = [c for c in info.spawned_creatures if c.template == GOOBY_TEMPLATE_NAME]
        renamed_to_runtime = [c for c in info.spawned_creatures if c.runtime_name == GOOBY_RUNTIME_NAME]
        runtime_trigger_targets = [
            t for t in info.trigger_targets if t.name == "trigger target" and t.value == GOOBY_RUNTIME_NAME
        ]

        # Engage only when this map participates in the Gooby chain in some form.
        if not (gooby_template_spawns or renamed_to_runtime or runtime_trigger_targets):
            return

        chain_spawns = [c for c in gooby_template_spawns if c.runtime_name == GOOBY_RUNTIME_NAME]

        if not gooby_template_spawns:
            location = renamed_to_runtime[0].location if renamed_to_runtime else runtime_trigger_targets[0].location
            self._issue(
                info.path,
                location,
                f'Gooby quest chain references runtime name "{GOOBY_RUNTIME_NAME}" but no spawn of '
                f'template "{GOOBY_TEMPLATE_NAME}" remains; the template name must not be renamed',
            )
            return

        if not chain_spawns:
            self._issue(
                info.path,
                gooby_template_spawns[0].location,
                f'CaveTrigger spawns template "{GOOBY_TEMPLATE_NAME}" but does not rename the runtime '
                f'object to "{GOOBY_RUNTIME_NAME}"; the runtime name must be preserved',
            )
            return

        if not runtime_trigger_targets:
            self._issue(
                info.path,
                chain_spawns[0].location,
                f'runtime object "{GOOBY_RUNTIME_NAME}" is spawned from template "{GOOBY_TEMPLATE_NAME}" but no '
                f'trigger recognizes "{GOOBY_RUNTIME_NAME}"; quest-completion flow must keep recognizing it',
            )

    def _validate_script_property_hygiene(self, context: MapContext) -> None:
        info = context.script_info
        if not info:
            return

        valid_legacy_flags = self._validate_legacy_bool_flags(info)
        accesses_by_key: dict[tuple[str, str], dict[str, list[ScriptPropertyAccess]]] = {}
        owners_by_property: dict[str, set[str]] = {}
        unknown_accesses: list[ScriptPropertyAccess] = []

        for legacy_flag in valid_legacy_flags:
            owners_by_property.setdefault(legacy_flag, set()).add("map")

        for access in info.property_reads + info.property_writes:
            if access.method not in SCRIPT_BOOL_PROPERTY_METHODS:
                continue
            if access.owner in {"map", "player"}:
                owners_by_property.setdefault(access.name, set()).add(access.owner)
                by_access = accesses_by_key.setdefault((access.owner, access.name), {"read": [], "write": []})
                by_access[access.access].append(access)
            elif access.owner == "unknown":
                unknown_accesses.append(access)

        for property_name, owners in sorted(owners_by_property.items()):
            if len(owners) <= 1:
                continue
            first_access = self._first_property_access(info, property_name)
            location = first_access.location if first_access else f'property "{property_name}"'
            owner_list = ", ".join(sorted(owners))
            self._issue(
                info.path, location, f'bool property "{property_name}" is used on multiple owners: {owner_list}'
            )

        for (owner, property_name), accesses in sorted(accesses_by_key.items()):
            if owner == "map" and property_name in valid_legacy_flags:
                continue
            if self._property_hygiene_allowance_reason(info.path, owner, property_name):
                continue

            reads = accesses["read"]
            writes = accesses["write"]
            if reads and not writes:
                self._issue(
                    info.path,
                    reads[0].location,
                    f'{owner} bool property "{property_name}" is read without a write/default, legacy sync, '
                    "or allowlist",
                )
            elif writes and not reads:
                self._issue(
                    info.path,
                    writes[0].location,
                    f'write-only {owner} bool property "{property_name}" has no read, legacy sync, or allowlist',
                )

        reviewed_names = set(owners_by_property)
        for allowance in self.property_hygiene_allowlist:
            if allowance.path == self._rel(info.path):
                reviewed_names.add(allowance.name)
        for access in unknown_accesses:
            if access.name not in reviewed_names:
                continue
            if self._property_hygiene_allowance_reason(info.path, "unknown", access.name):
                continue
            self._issue(
                info.path,
                access.location,
                f'bool property "{access.name}" has unknown receiver; manual review required to classify ownership',
            )

    def _validate_legacy_bool_flags(self, info: ScriptInfo) -> set[str]:
        valid_flags: set[str] = set()
        for flag in info.legacy_bool_flags:
            usage = info.quest_states.get(flag.quest)
            if usage is None or not usage.storage_key:
                self._issue(
                    info.path,
                    flag.location,
                    f'legacy bool flag "{flag.name}" references unknown quest key "{flag.quest}"',
                )
                continue
            valid_flags.add(flag.name)
        return valid_flags

    def _validate_quest_state_transitions(self, context: MapContext) -> None:
        """Validate the state machine declared by a map script's quest-state usage.

        Builds on the quest-state collection produced by ScriptAnalyzer (QUEST_KEYS,
        QUEST_DEFAULTS, _set_state/state_in writes and reads, and terminal completion
        checks). A quest key is "declared" when QUEST_KEYS maps it to a storage key.
        The rules enforced are:

        * every QUEST_DEFAULTS default references a declared quest key;
        * every transition target (a _set_state write) belongs to a declared quest key;
        * every state read (a get_state comparison or state_in) belongs to a declared
            quest key;
        * every terminal completion state is reachable from a default -- i.e. it is the
            default state itself or a state assigned by some transition write. A terminal
            state that is never the default and never written can never be entered, so the
            completion check it guards can never fire.

        Undeclared keys are detected because any get_state/_set_state/state_in reference
        records a ScriptQuestStateUsage entry whose storage_key stays None when the key
        is absent from QUEST_KEYS.
        """
        info = context.script_info
        if not info:
            return
        for quest_key in sorted(info.quest_states):
            usage = info.quest_states[quest_key]
            declared = bool(usage.storage_key)
            location = f'quest "{quest_key}"'
            if usage.default_state is not None and not declared:
                self._issue(
                    info.path,
                    location,
                    f'quest default "{usage.default_state}" references undeclared quest key "{quest_key}" '
                    "(missing from QUEST_KEYS)",
                )
            if not declared:
                for state in sorted(usage.written_states):
                    self._issue(
                        info.path,
                        location,
                        f'transition target "{state}" writes undeclared quest key "{quest_key}" '
                        "(missing from QUEST_KEYS)",
                    )
                for state in sorted(usage.read_states):
                    self._issue(
                        info.path,
                        location,
                        f'state read "{state}" references undeclared quest key "{quest_key}" '
                        "(missing from QUEST_KEYS)",
                    )
                continue
            reachable = set(usage.written_states)
            if usage.default_state is not None:
                reachable.add(usage.default_state)
            for state in sorted(usage.terminal_check_states - reachable):
                self._issue(
                    info.path,
                    location,
                    f'terminal state "{state}" is unreachable: it is neither the default nor a transition target',
                )

    def _first_property_access(self, info: ScriptInfo, property_name: str) -> ScriptPropertyAccess | None:
        accesses = [
            access
            for access in info.property_reads + info.property_writes
            if access.name == property_name and access.owner in {"map", "player"}
        ]
        if not accesses:
            return None
        return min(accesses, key=lambda access: access.lineno)

    def _property_hygiene_allowance_reason(self, path: Path, owner: str, property_name: str) -> str | None:
        relative_path = self._rel(path)
        for allowance in self.property_hygiene_allowlist:
            if allowance.path == relative_path and allowance.owner == owner and allowance.name == property_name:
                return allowance.reason
        return None

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

    def _validate_creature_archetype_naming(self) -> None:
        config_dir = self.repo_root / "res" / "config"
        for filename, suffix in CREATURE_ARCHETYPE_ID_SUFFIXES.items():
            path = config_dir / filename
            data = self.global_files.get(path)
            if not isinstance(data, dict):
                continue
            for template_id, entry in data.items():
                if isinstance(template_id, str) and not template_id.endswith(suffix):
                    self._issue(
                        path,
                        template_id,
                        f'{filename} template id "{template_id}" must end with "{suffix}"',
                    )
                self._validate_creature_class_reference(path, template_id, entry)

    def _validate_creature_class_reference(self, path: Path, location: str, value: Any) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict) and "class" in properties:
                self._issue(
                    path,
                    f"{append_field(location, 'properties')}.class",
                    f'class reference must use property "{CREATURE_CLASS_REFERENCE_PROPERTY}", '
                    f'never the reserved object-constructor key "class"',
                )
            for key, child in value.items():
                self._validate_creature_class_reference(path, append_field(location, key), child)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_creature_class_reference(path, append_index(location, index), child)

    def _validate_duplicate_player_selectable_race_labels(self, visible: dict[str, ConfigEntry]) -> None:
        """Reject duplicate selection labels among player-selectable CCreatureRace configs.

        res/game.py builds the race-selection menu as a label->id map (mirroring
        player_class_options): the key is the race's resolved "label" property, falling
        back to its template id when no label is set, and the value is the template id.
        Two player-selectable races sharing that key collapse to one menu entry, so the
        second silently overwrites the first.  This enumerates every global config whose
        effective class is (or inherits) CCreatureRace and whose resolved
        "playerSelectable" property is true, keys each by label-or-id, and reports any key
        claimed by more than one race -- naming the conflicting ids and their paths.
        Non-player-selectable races are ignored because they never enter the menu.
        """
        labels: dict[str, list[ConfigEntry]] = {}
        for key, entry in self.global_entries.items():
            if not isinstance(entry.data, dict):
                continue
            class_name = self._effective_object_class(entry.data, visible)
            if not isinstance(class_name, str):
                continue
            if not (
                class_name == CREATURE_RACE_BASE_CLASS
                or self._class_inherits_from(class_name, CREATURE_RACE_BASE_CLASS)
            ):
                continue
            selectable = self._effective_property_value(entry.data, CREATURE_RACE_PLAYER_SELECTABLE_PROPERTY, visible)
            if selectable is not True:
                continue
            label = self._effective_property_value(entry.data, CREATURE_RACE_LABEL_PROPERTY, visible)
            selection_key = label if isinstance(label, str) and label else key
            labels.setdefault(selection_key, []).append(entry)
        for selection_key, entries in labels.items():
            if len(entries) < 2:
                continue
            conflicting = sorted(entry.key for entry in entries)
            for entry in sorted(entries, key=lambda candidate: candidate.key):
                others = ", ".join(other for other in conflicting if other != entry.key)
                self._issue(
                    entry.path,
                    entry.key,
                    f'player-selectable race selection label "{selection_key}" is not unique; '
                    f"it collides with {others} -- res/game.py maps a selected label back to a "
                    f"single race id, so duplicate labels make the selection ambiguous",
                )

    def _validate_required_production_archetypes(self, visible: dict[str, ConfigEntry]) -> None:
        """Require every production creature to declare race AND creatureClass post-migration.

        Once the archetype migration is declared complete, no production CCreature/CPlayer
        config may silently remain on the legacy path: each must declare both its race
        (CREATURE_RACE_PROPERTY) and its class (CREATURE_CLASS_REFERENCE_PROPERTY) reference
        property in its ``properties`` block.  Production creatures are the global
        res/config entries whose effective engine class is, or inherits from, CCreature
        (which also covers CPlayer, since CPlayer derives from CCreature) -- the exact same
        resolution the read-only report_unmigrated_creatures() inventory uses.  Every
        missing archetype across all production creatures is reported in a single run, with
        one issue per absent property naming the precise ``configId.properties.<prop>`` path.

        Enforcement is gated behind ``self.archetype_migration_complete`` so the rule is
        fully inert on pre-migration content: while the switch is False (the default today)
        nothing is emitted, keeping the standard validation green.  When the switch is on, a
        creature exempted in the reviewed exception manifest (by exact path AND key) is not
        flagged -- the manifest is intended for low-level test fixtures only.
        """
        if not self.archetype_migration_complete:
            return
        exempt_keys = {(exception.path, exception.key) for exception in self.archetype_migration_exceptions}
        for key, entry in self.global_entries.items():
            if not isinstance(entry.data, dict):
                continue
            class_name = self._effective_object_class(entry.data, visible)
            if not isinstance(class_name, str):
                continue
            if not (class_name == CREATURE_BASE_CLASS or self._class_inherits_from(class_name, CREATURE_BASE_CLASS)):
                continue
            if (self._rel(entry.path), key) in exempt_keys:
                continue
            properties = entry.data.get("properties")
            properties = properties if isinstance(properties, dict) else {}
            properties_location = append_field(key, "properties")
            for property_name in CREATURE_REQUIRED_ARCHETYPE_PROPERTIES:
                if property_name not in properties:
                    self._issue(
                        entry.path,
                        append_field(properties_location, property_name),
                        f'production creature "{key}" (class "{class_name}") must declare archetype '
                        f'property "{property_name}" after archetype migration; legacy creatures without '
                        f"race/creatureClass are no longer allowed unless listed in the reviewed archetype "
                        f"exception manifest",
                    )

    def _effective_property_value(
        self,
        value: dict[str, Any],
        property_name: str,
        visible: dict[str, ConfigEntry],
        seen_refs: set[str] | None = None,
    ) -> Any:
        """Resolve a property's effective value, honoring ``ref`` inheritance.

        A config node may define properties inline or inherit them from a referenced
        template via ``ref``; an inline ``properties`` value overrides the referenced
        one.  Returns ``None`` when the property is absent (or the ref chain cycles or
        dangles), mirroring how the runtime loader resolves overrides on top of a base
        template.
        """
        properties = value.get("properties")
        if isinstance(properties, dict) and property_name in properties:
            return properties[property_name]
        ref = value.get("ref")
        if not isinstance(ref, str):
            return None
        seen = set(seen_refs or set())
        if ref in seen:
            return None
        seen.add(ref)
        ref_entry = visible.get(ref)
        if ref_entry is None or not isinstance(ref_entry.data, dict):
            return None
        return self._effective_property_value(ref_entry.data, property_name, visible, seen)

    def _validate_creature_class_actions_levelling(
        self, path: Path, location: str, value: Any, visible: dict[str, ConfigEntry]
    ) -> None:
        """Validate CCreatureClass.actions / levelling resolve to CInteraction.

        Recurses through the config tree so a CCreatureClass node nested under a ref
        chain or another object is still checked.  For every node whose effective
        class is ``CCreatureClass`` it verifies that each ``actions`` entry resolves
        to a ``CInteraction``, that each ``levelling`` key is a positive-integer
        string whose value resolves to a ``CInteraction``, and that no effective
        action id (the ref target id) is granted more than once across both blocks.
        """
        if isinstance(value, dict):
            if self._effective_object_class(value, visible) == CREATURE_CLASS_CONSTRUCTOR_CLASS:
                self._validate_creature_class_grants(path, location, value, visible)
            for key, child in value.items():
                self._validate_creature_class_actions_levelling(path, append_field(location, key), child, visible)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_creature_class_actions_levelling(path, append_index(location, index), child, visible)

    def _validate_creature_class_grants(
        self, path: Path, location: str, value: dict[str, Any], visible: dict[str, ConfigEntry]
    ) -> None:
        properties = value.get("properties")
        if not isinstance(properties, dict):
            return
        properties_location = append_field(location, "properties")
        seen_action_ids: dict[str, str] = {}
        self._validate_creature_class_actions(
            path,
            append_field(properties_location, CREATURE_CLASS_ACTIONS_PROPERTY),
            properties.get(CREATURE_CLASS_ACTIONS_PROPERTY),
            visible,
            seen_action_ids,
        )
        self._validate_creature_class_levelling(
            path,
            append_field(properties_location, CREATURE_CLASS_LEVELLING_PROPERTY),
            properties.get(CREATURE_CLASS_LEVELLING_PROPERTY),
            visible,
            seen_action_ids,
        )

    def _validate_creature_class_actions(
        self,
        path: Path,
        location: str,
        actions: Any,
        visible: dict[str, ConfigEntry],
        seen_action_ids: dict[str, str],
    ) -> None:
        if actions is None:
            return
        if not isinstance(actions, list):
            self._issue(path, location, "expected array of CInteraction action entries")
            return
        for index, action in enumerate(actions):
            entry_location = append_index(location, index)
            self._validate_creature_class_interaction_entry(path, entry_location, action, visible)
            self._record_effective_action_id(path, entry_location, action, seen_action_ids)

    def _validate_creature_class_levelling(
        self,
        path: Path,
        location: str,
        levelling: Any,
        visible: dict[str, ConfigEntry],
        seen_action_ids: dict[str, str],
    ) -> None:
        if levelling is None:
            return
        if not isinstance(levelling, dict):
            self._issue(path, location, "expected object keyed by positive-integer level")
            return
        for level_key, action in levelling.items():
            entry_location = append_field(location, level_key)
            if not is_positive_integer_string(level_key):
                self._issue(
                    path,
                    entry_location,
                    f'levelling key "{level_key}" must be a positive-integer string',
                )
            self._validate_creature_class_interaction_entry(path, entry_location, action, visible)
            self._record_effective_action_id(path, entry_location, action, seen_action_ids)

    def _validate_creature_class_interaction_entry(
        self, path: Path, location: str, action: Any, visible: dict[str, ConfigEntry]
    ) -> None:
        if not isinstance(action, dict):
            self._issue(path, location, f'expected object resolving to "{INTERACTION_BASE_CLASS}"')
            return
        class_name = self._effective_object_class(action, visible)
        if class_name is None:
            self._issue(
                path,
                location,
                f'expected object resolving to "{INTERACTION_BASE_CLASS}"; got object without class/ref',
            )
            return
        if not self._class_resolves_to_interaction(class_name):
            self._issue(
                path,
                location,
                f'expected object resolving to "{INTERACTION_BASE_CLASS}"; got "{class_name}"',
            )

    def _class_resolves_to_interaction(self, class_name: str) -> bool:
        return class_name == INTERACTION_BASE_CLASS or self._class_inherits_from(class_name, INTERACTION_BASE_CLASS)

    def _validate_interaction_self_target(
        self, path: Path, location: str, value: Any, visible: dict[str, ConfigEntry]
    ) -> None:
        """Require caster-target interactions to declare selfTarget explicitly.

        Recurses the config tree so an interaction nested under a ref chain or another
        object is still checked.  For every node whose effective class resolves to
        CInteraction, it resolves the interaction's ``effect`` (following ref chains) and
        its effect tags: when the effect carries the Buff tag -- which historically routed
        the effect back to the caster through the legacy tag-based fallback -- the
        interaction must set ``selfTarget`` true so the routing is explicit rather than
        inferred from the tag.  Interactions without an effect, or with a non-Buff effect,
        are unaffected, and the Buff tag itself is preserved for classification.
        """
        if isinstance(value, dict):
            if self._is_interaction_node(value, visible):
                self._check_interaction_self_target(path, location, value, visible)
            for key, child in value.items():
                self._validate_interaction_self_target(path, append_field(location, key), child, visible)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_interaction_self_target(path, append_index(location, index), child, visible)

    def _is_interaction_node(self, value: dict[str, Any], visible: dict[str, ConfigEntry]) -> bool:
        class_name = self._effective_object_class(value, visible)
        return isinstance(class_name, str) and self._class_resolves_to_interaction(class_name)

    def _check_interaction_self_target(
        self, path: Path, location: str, value: dict[str, Any], visible: dict[str, ConfigEntry]
    ) -> None:
        effect_value = self._effective_property_value(value, INTERACTION_EFFECT_PROPERTY, visible)
        if not isinstance(effect_value, dict):
            return
        tags = self._effective_property_value(effect_value, EFFECT_TAGS_PROPERTY, visible)
        if not (isinstance(tags, list) and BUFF_EFFECT_TAG in tags):
            return
        self_target = self._effective_property_value(value, INTERACTION_SELF_TARGET_PROPERTY, visible)
        if self_target is not True:
            self._issue(
                path,
                append_field(append_field(location, "properties"), INTERACTION_SELF_TARGET_PROPERTY),
                f'interaction with a Buff-tagged effect must declare "selfTarget": true so caster '
                f"targeting is explicit; it currently relies on the deprecated Buff-tag routing fallback",
            )

    def _validate_creature_class_property(
        self, path: Path, location: str, value: Any, visible: dict[str, ConfigEntry]
    ) -> None:
        """Validate a CCreature's "creatureClass" property resolves to a CCreatureClass.

        Recurses through the config tree so a creature node nested under a ref chain
        or another object is still checked.  For every node whose effective class is or
        inherits ``CCreature`` it inspects the *property* ``properties.creatureClass``
        (never the top-level object-constructor key ``class``) and verifies that its
        value is an object node resolving, through any ref/config chain, to a definition
        whose effective class is or inherits ``CCreatureClass``.  Wrong-typed values,
        unresolvable/missing references, and resolved-but-wrong-class targets are each
        reported distinctly at the exact ``properties.creatureClass`` path.
        """
        if isinstance(value, dict):
            if self._is_creature_node(value, visible):
                self._validate_creature_class_reference_target(path, location, value, visible)
            for key, child in value.items():
                self._validate_creature_class_property(path, append_field(location, key), child, visible)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_creature_class_property(path, append_index(location, index), child, visible)

    def _validate_creature_class_reference_target(
        self, path: Path, location: str, value: dict[str, Any], visible: dict[str, ConfigEntry]
    ) -> None:
        properties = value.get("properties")
        if not isinstance(properties, dict) or CREATURE_CLASS_REFERENCE_PROPERTY not in properties:
            return
        reference = properties[CREATURE_CLASS_REFERENCE_PROPERTY]
        reference_location = append_field(append_field(location, "properties"), CREATURE_CLASS_REFERENCE_PROPERTY)
        if not isinstance(reference, dict):
            self._issue(
                path,
                reference_location,
                f'property "{CREATURE_CLASS_REFERENCE_PROPERTY}" expected an object resolving to '
                f'"{CREATURE_CLASS_BASE_CLASS}"; got {json_value_kind(reference)}',
            )
            return
        resolved_class = self._effective_object_class(reference, visible)
        if resolved_class is None:
            self._issue(
                path,
                reference_location,
                f'property "{CREATURE_CLASS_REFERENCE_PROPERTY}" expected an object resolving to '
                f'"{CREATURE_CLASS_BASE_CLASS}"; reference does not resolve to a known config',
            )
            return
        if not self._class_resolves_to_creature_class(resolved_class):
            self._issue(
                path,
                reference_location,
                f'property "{CREATURE_CLASS_REFERENCE_PROPERTY}" expected an object resolving to '
                f'"{CREATURE_CLASS_BASE_CLASS}"; got "{resolved_class}"',
            )

    def _class_resolves_to_creature_class(self, class_name: str) -> bool:
        return class_name == CREATURE_CLASS_BASE_CLASS or self._class_inherits_from(
            class_name, CREATURE_CLASS_BASE_CLASS
        )

    def _record_effective_action_id(
        self, path: Path, location: str, action: Any, seen_action_ids: dict[str, str]
    ) -> None:
        if not isinstance(action, dict):
            return
        action_id = action.get("ref")
        if not isinstance(action_id, str) or not action_id:
            return
        previous = seen_action_ids.get(action_id)
        if previous is not None:
            self._issue(
                path,
                location,
                f'duplicate action id "{action_id}", previously granted at {previous}',
            )
            return
        seen_action_ids[action_id] = location

    def _validate_creature_race_definition(
        self, path: Path, location: str, value: Any, visible: dict[str, ConfigEntry]
    ) -> None:
        """Validate CCreatureRace baseStats keys, actions, and type fields.

        Recurses through the config tree so a CCreatureRace node nested under a ref
        chain or another object is still checked.  For every node whose effective class
        is ``CCreatureRace`` it verifies that each ``baseStats`` key names a ``CStats``
        metadata property, that each ``actions`` entry resolves to a ``CInteraction``,
        and that ``creatureType`` / every ``subtypes`` entry is a non-empty string. The
        type fields stay DATA-ONLY (non-empty-string checks only); no mechanical type
        semantics are inferred.
        """
        if isinstance(value, dict):
            if self._effective_object_class(value, visible) == CREATURE_RACE_CONSTRUCTOR_CLASS:
                self._validate_creature_race_fields(path, location, value, visible)
            for key, child in value.items():
                self._validate_creature_race_definition(path, append_field(location, key), child, visible)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_creature_race_definition(path, append_index(location, index), child, visible)

    def _validate_creature_race_fields(
        self, path: Path, location: str, value: dict[str, Any], visible: dict[str, ConfigEntry]
    ) -> None:
        properties = value.get("properties")
        if not isinstance(properties, dict):
            return
        properties_location = append_field(location, "properties")
        if CREATURE_RACE_BASE_STATS_PROPERTY in properties:
            self._validate_creature_race_base_stats(
                path,
                append_field(properties_location, CREATURE_RACE_BASE_STATS_PROPERTY),
                properties[CREATURE_RACE_BASE_STATS_PROPERTY],
            )
        if CREATURE_RACE_ACTIONS_PROPERTY in properties:
            self._validate_creature_race_actions(
                path,
                append_field(properties_location, CREATURE_RACE_ACTIONS_PROPERTY),
                properties[CREATURE_RACE_ACTIONS_PROPERTY],
                visible,
            )
        if CREATURE_RACE_TYPE_PROPERTY in properties:
            self._validate_creature_race_type(
                path,
                append_field(properties_location, CREATURE_RACE_TYPE_PROPERTY),
                properties[CREATURE_RACE_TYPE_PROPERTY],
            )
        if CREATURE_RACE_SUBTYPES_PROPERTY in properties:
            self._validate_creature_race_subtypes(
                path,
                append_field(properties_location, CREATURE_RACE_SUBTYPES_PROPERTY),
                properties[CREATURE_RACE_SUBTYPES_PROPERTY],
            )

    def _validate_creature_race_base_stats(self, path: Path, location: str, base_stats: Any) -> None:
        allowed_keys = self._creature_race_stats_property_names()
        if allowed_keys is None:
            return
        if not isinstance(base_stats, dict):
            self._issue(
                path,
                location,
                f"expected {CREATURE_RACE_STATS_SCHEMA_CLASS}-compatible object; got {json_value_kind(base_stats)}",
            )
            return
        # baseStats is deserialized through the standard object envelope
        # ({"class": "CStats", "properties": {<stat>: <int>}}) -- the same nested form every
        # other CStats payload in content uses -- and content loads under a strict deserialize
        # scope, so a bare/flat stat map (stat keys at the top level, no "class") fails to
        # construct at load time. Require the envelope and validate the inner stat keys.
        if "class" not in base_stats and "ref" not in base_stats:
            self._issue(
                path,
                location,
                f'expected a {CREATURE_RACE_STATS_SCHEMA_CLASS} object node '
                f'(e.g. {{"class": "{CREATURE_RACE_STATS_SCHEMA_CLASS}", "properties": {{...}}}})',
            )
            return
        stat_properties = base_stats.get("properties")
        if stat_properties is None:
            return
        if not isinstance(stat_properties, dict):
            self._issue(
                path,
                append_field(location, "properties"),
                f"expected object; got {json_value_kind(stat_properties)}",
            )
            return
        properties_location = append_field(location, "properties")
        for stat_key in stat_properties:
            if stat_key not in allowed_keys:
                self._issue(
                    path,
                    append_field(properties_location, stat_key),
                    f'"{stat_key}" is not a {CREATURE_RACE_STATS_SCHEMA_CLASS} property; '
                    f"expected one of {', '.join(sorted(allowed_keys))}",
                )

    def _creature_race_stats_property_names(self) -> set[str] | None:
        """Return all CStats metadata property names, or None when CStats is absent.

        Derived from the live CStats metadata schema so the allowed baseStats keys
        never drift from src/core/CStats.h.  Returns None when CStats metadata is
        unavailable (e.g. before the native sources exist), leaving the check inert
        rather than guessing a stat set.
        """
        property_schema = self._metadata_property_schema(CREATURE_RACE_STATS_SCHEMA_CLASS)
        if not property_schema:
            return None
        return set(property_schema)

    def _validate_creature_race_actions(
        self, path: Path, location: str, actions: Any, visible: dict[str, ConfigEntry]
    ) -> None:
        if not isinstance(actions, list):
            self._issue(path, location, f"expected array of {INTERACTION_BASE_CLASS} action entries")
            return
        for index, action in enumerate(actions):
            self._validate_creature_class_interaction_entry(path, append_index(location, index), action, visible)

    def _validate_creature_race_type(self, path: Path, location: str, creature_type: Any) -> None:
        if not isinstance(creature_type, str) or not creature_type:
            self._issue(
                path,
                location,
                f'"{CREATURE_RACE_TYPE_PROPERTY}" expected a non-empty string; got {json_value_kind(creature_type)}',
            )

    def _validate_creature_race_subtypes(self, path: Path, location: str, subtypes: Any) -> None:
        if not isinstance(subtypes, list):
            self._issue(
                path,
                location,
                f'"{CREATURE_RACE_SUBTYPES_PROPERTY}" expected an array of non-empty strings; '
                f"got {json_value_kind(subtypes)}",
            )
            return
        for index, subtype in enumerate(subtypes):
            if not isinstance(subtype, str) or not subtype:
                self._issue(
                    path,
                    append_index(location, index),
                    f"expected a non-empty string; got {json_value_kind(subtype)}",
                )

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

    def _archetype_definition_ids(self, visible: dict[str, ConfigEntry]) -> set[str]:
        """Resolve config ids that name a CCreatureRace/CCreatureClass *definition*.

        An id is an archetype definition when its effective engine class (following
        ``ref`` chains) is one of CREATURE_ARCHETYPE_BASE_CLASSES or inherits from
        one, or when it is a top-level entry declared in the dedicated archetype
        config files (creature_races.json / creature_classes.json).  Such ids are
        referenced definitions, not actors, so using them as a concrete spawn target
        is rejected.  Resolution is purely structural -- never from id name strings.
        """
        archetype_ids: set[str] = set()
        for key, entry in visible.items():
            if not isinstance(entry.data, dict):
                continue
            if self._is_archetype_definition_node(entry.data, visible) or self._is_archetype_definition_config(
                entry.path
            ):
                archetype_ids.add(key)
        return archetype_ids

    def _is_archetype_definition_node(self, value: dict[str, Any], visible: dict[str, ConfigEntry]) -> bool:
        class_name = self._effective_object_class(value, visible)
        if not isinstance(class_name, str):
            return False
        return class_name in CREATURE_ARCHETYPE_BASE_CLASSES or any(
            self._class_inherits_from(class_name, base) for base in CREATURE_ARCHETYPE_BASE_CLASSES
        )

    def _is_archetype_definition_config(self, path: Path) -> bool:
        return self._rel(path) in {
            (Path("res") / "config" / name).as_posix() for name in CREATURE_ARCHETYPE_DEFINITION_CONFIGS
        }

    def _reject_archetype_spawn_target(
        self, path: Path, location: str, name: str, label: str, archetype_ids: set[str]
    ) -> bool:
        """Emit an issue when ``name`` is an archetype definition used as a spawn target.

        Returns True when the name was rejected so callers can skip the regular
        unknown-reference diagnostic.
        """
        if name not in archetype_ids:
            return False
        self._issue(
            path,
            location,
            f'{label} "{name}" is a creature archetype definition '
            f"(CCreatureRace/CCreatureClass) and cannot be used as a concrete spawn target",
        )
        return True

    def _class_reference_message(self, class_name: str, label: str) -> str:
        exclusion = self.registration_exclusions.get(class_name)
        if exclusion:
            return (
                f'{label} "{class_name}" is excluded from content instantiation: '
                f"{exclusion.reason} (owner/module: {exclusion.owner_module})"
            )
        if class_name in self.native_plugin_declared_class_sources:
            owners = ", ".join(sorted(self.native_plugin_declared_class_sources[class_name]))
            return f'{label} "{class_name}" is registered by native plugin code but no manifest entry loads {owners}'
        if class_name in self.metadata_declared_classes:
            return f'{label} "{class_name}" is declared in metadata but is not registered as constructible content'
        return f'unknown {label} "{class_name}"'

    def _excluded_use_is_allowed(self, path: Path, location: str, class_name: str) -> bool:
        exclusion = self.registration_exclusions.get(class_name)
        if not exclusion:
            return False
        relative_path = self._rel(path)
        return any(
            allowed_use.path == relative_path and allowed_use.location == location
            for allowed_use in exclusion.allowed_uses
        )


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


def expected_json_property_kind(type_token: str) -> str | None:
    if type_token == "bool":
        return "bool"
    if type_token == "int":
        return "int"
    if type_token == "std::string":
        return "string"
    if type_token == "CTags" or re.match(r"^std::(?:set|list|vector)<", type_token):
        return "array"
    if type_token.startswith("std::shared_ptr<") or type_token in {
        "CInteractionMap",
        "CItemMap",
        "CSlotMap",
        "int_int_map",
        "int_string_map",
        "string_int_map",
        "string_string_map",
    }:
        return "object"
    return None


def expected_cpp_object_base_class(type_token: str) -> str | None:
    match = re.search(r"\bstd::shared_ptr<([A-Za-z_]\w*)>", type_token)
    if match:
        return match.group(1)
    return None


def json_value_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def is_positive_integer_string(value: Any) -> bool:
    """Return True when ``value`` is a canonical positive-integer string (1, 2, ...).

    Rejects non-strings, non-digit strings, "0", and any leading-zero / signed /
    whitespace-padded form so a levelling key always denotes a single unambiguous
    positive level.
    """
    if not isinstance(value, str) or not value.isdigit():
        return False
    return value == str(int(value)) and int(value) > 0


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


def iter_cpp_metadata_declarations(text: str) -> list[tuple[str, str | None, list[CppMetadataProperty]]]:
    declarations: list[tuple[str, str | None, list[CppMetadataProperty]]] = []
    text = strip_cpp_comments(text)
    for body in iter_cpp_macro_bodies(text, "V_META"):
        args = split_cpp_args(body)
        if len(args) < 2:
            continue
        class_name = normalize_cpp_class_token(args[0])
        if not is_concrete_cpp_class_name(class_name):
            continue
        base_class = normalize_cpp_class_token(args[1])
        if not is_concrete_cpp_class_name(base_class):
            base_class = None
        properties: list[CppMetadataProperty] = []
        for property_body in iter_cpp_macro_bodies(body, "V_PROPERTY"):
            property_args = split_cpp_args(property_body)
            if len(property_args) < 3:
                continue
            owner_class = normalize_cpp_class_token(property_args[0])
            property_name = property_args[2].strip()
            if not is_concrete_cpp_class_name(owner_class) or not re.match(r"^[A-Za-z_]\w*$", property_name):
                continue
            properties.append(
                CppMetadataProperty(
                    owner_class=owner_class,
                    name=property_name,
                    type_token=normalize_cpp_type_token(property_args[1]),
                )
            )
        declarations.append((class_name, base_class, properties))
    return declarations


def strip_cpp_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n\r]*", "", text, flags=re.DOTALL)


def iter_cpp_macro_bodies(text: str, macro_name: str) -> list[str]:
    bodies: list[str] = []
    pattern = re.compile(rf"\b{re.escape(macro_name)}\s*\(")
    for match in pattern.finditer(text):
        open_index = text.find("(", match.start(), match.end())
        close_index = find_matching_parenthesis(text, open_index)
        if close_index is not None:
            bodies.append(text[open_index + 1 : close_index])
    return bodies


def find_matching_parenthesis(text: str, open_index: int) -> int | None:
    if open_index < 0 or open_index >= len(text) or text[open_index] != "(":
        return None
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(open_index, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def split_cpp_args(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    paren_depth = 0
    angle_depth = 0
    square_depth = 0
    brace_depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(0, paren_depth - 1)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(0, angle_depth - 1)
        elif char == "[":
            square_depth += 1
        elif char == "]":
            square_depth = max(0, square_depth - 1)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(0, brace_depth - 1)
        elif char == "," and paren_depth == 0 and angle_depth == 0 and square_depth == 0 and brace_depth == 0:
            args.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        args.append(tail)
    return args


def normalize_cpp_class_token(raw: str) -> str:
    return re.sub(r"\s+", "", raw.strip())


def normalize_cpp_type_token(raw: str) -> str:
    token = re.sub(r"\s+", " ", raw.strip())
    return re.sub(r"\s*([<>,:&*])\s*", r"\1", token)


def python_base_class_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


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


def inventory_creature_overrides(repo_root: Path | str) -> list[CreatureOverride]:
    return ContentValidator(Path(repo_root)).inventory_creature_overrides()


def classify_creature_templates(repo_root: Path | str) -> CreatureClassification:
    return ContentValidator(Path(repo_root)).classify_creature_templates()


def report_unmigrated_creatures(repo_root: Path | str) -> list[UnmigratedCreature]:
    return ContentValidator(Path(repo_root)).report_unmigrated_creatures()


def report_legacy_class_checks(repo_root: Path | str) -> list[LegacyClassCheck]:
    return ContentValidator(Path(repo_root)).report_legacy_class_checks()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate game JSON resources and literal script refs.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--report-creature-overrides",
        action="store_true",
        help="Print the map-local creature override inventory as JSON and exit without validating.",
    )
    parser.add_argument(
        "--report-creature-classification",
        action="store_true",
        help="Print the metadata-derived player/monster classification as JSON and exit without validating.",
    )
    parser.add_argument(
        "--report-unmigrated",
        action="store_true",
        help=(
            "Print the production CCreature/CPlayer configs still missing race and/or "
            "creatureClass as JSON and exit without validating."
        ),
    )
    parser.add_argument(
        "--report-legacy-class-checks",
        action="store_true",
        help=(
            "Print the legacy getTypeId()-based player class checks still awaiting "
            "migration to getPlayerClassId() as JSON and exit without validating."
        ),
    )
    args = parser.parse_args(argv)

    if args.report_creature_overrides:
        overrides = inventory_creature_overrides(args.repo_root)
        json.dump([override.as_dict() for override in overrides], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.report_creature_classification:
        classification = classify_creature_templates(args.repo_root)
        json.dump(classification.as_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.report_unmigrated:
        unmigrated = report_unmigrated_creatures(args.repo_root)
        json.dump([creature.as_dict() for creature in unmigrated], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.report_legacy_class_checks:
        legacy = report_legacy_class_checks(args.repo_root)
        json.dump([check.as_dict() for check in legacy], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

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
