# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reviewed route obligations and source audits, independent of the native module.

Catalog membership is a plan, not a passing gameplay witness. Only the MCP runner's
branch receipts establish that a natural route actually reached an outcome.
"""

import ast
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path

from tests.gameplay_branch_types import PLAYER_CLASSES, testName

ROOT = Path(__file__).resolve().parents[1]
ROUTE_MODULES = (
    "tests.gameplay_routes_nouraajd",
    "tests.gameplay_routes_ninemarches",
    "tests.gameplay_routes_maps",
    "tests.gameplay_routes_campaigns",
)
AUTHORED_MAPS = (
    "castleGriffinCliff",
    "castleGuardianAngels",
    "castleHomecoming",
    "gravemoor",
    "hearthfall",
    "kadath",
    "multilevel",
    "ninemarches",
    "nouraajd",
    "ritual",
    "siege",
    "sunderedmarch",
    "test",
    "usurpergate",
    "vhulmarn",
)
EVENT_CALLBACKS = frozenset(
    {"trigger", "onEnter", "onTurn", "onCreate", "onDestroy", "onOpen", "onUse", "onComplete", "isCompleted"}
)
REVIEWED_GAMEPLAY_DIGEST = "05666b98366af1ce92a684dadd38b052841a8a4cb7990500f841291394cd1863"


@dataclass(frozen=True)
class BranchFamily:
    prefix: str
    prerequisites: str
    outcomes: str


# These are deliberately authored descriptions. Source introspection cannot infer
# what a gameplay assertion needs to prove, particularly its setup boundary.
FAMILIES = (
    BranchFamily(
        "nouraajd.gate.",
        "Reach the gate in a fresh campaign and choose cooperation or a threat.",
        "The opened gate and retained campaign choice survive reload.",
    ),
    BranchFamily(
        "nouraajd.beer.",
        "Enter the tavern after the corresponding real gate choice.",
        "The actual sell_beer callback requests a stocked market with sale percent 100 or 105.",
    ),
    BranchFamily(
        "nouraajd.deed.",
        "Use the matching class at its authored landmark before consuming the deed.",
        "One deed counter, 750 earned experience and its unlock persist; Rolf and Gooby die in combat.",
    ),
    BranchFamily(
        "nouraajd.chain.",
        "Earn the relic and clear the real hunt; deliver and return items in the declared order.",
        "Each exact quest state converges on ready_to_report, then Beren completes the quest and changes map.",
    ),
    BranchFamily(
        "nouraajd.contract.",
        "Decline first, then accept before or after clearing the authored hunt.",
        "The actual completed quest grants one bounty and one blade, including a late acceptance.",
    ),
    BranchFamily(
        "nouraajd.hunt.",
        "Defeat a real hunt stage, save and reload, then retreat using an owned authored scroll.",
        "The same hunt registry and remaining real actors converge on the cleared stage.",
    ),
    BranchFamily(
        "nouraajd.amulet.",
        "Decline and accept the old woman's quest, then defeat the thief and loot the amulet.",
        "The return consumes the actual amulet, pays 50 gold once and retains completed history.",
    ),
    BranchFamily(
        "nouraajd.victor.",
        "Wait actual tavern turns, choose confrontation and enter through clue or records.",
        "Real combat rescues the child, or the unmodified 75-turn timer loses her without a reward.",
    ),
    BranchFamily(
        "nouraajd.aid.",
        "Start with the selected race; earn money and real combat/casting deficits for paid aid.",
        "Unfunded and unnecessary requests change nothing; funded aid uses exact capped deltas once.",
    ),
    BranchFamily(
        "nouraajd.campaign.",
        "Start the real campaign and complete Nouraajd, ritual and siege with earned resources.",
        "Scenario history, choices, class deed and Victor journal survive actual map transitions and reload.",
    ),
    BranchFamily(
        "nouraajd.snapshot.",
        "Leave town after the declared ordinary Victor/deed route.",
        "The campaign records the actual town outcome and class deed without progress injection.",
    ),
    BranchFamily(
        "ninemarches.companion.",
        "Recover the companion's authored cache before or after accepting the request.",
        "Recruitment grants one gift and two reputation; real banter preserves loyalty or triggers departure.",
    ),
    BranchFamily(
        "ninemarches.gate.",
        "Visit a locked threshold, collect its matching authored key and return.",
        "The wall disappears, chapter advances, key remains and repeat visits are inert.",
    ),
    BranchFamily(
        "ninemarches.gates.",
        "Open all three gates through their caches and save the actual game.",
        "All gate flags, absent walls and owned keys remain after reload.",
    ),
    BranchFamily(
        "ninemarches.site.",
        "Walk onto the authored learning stone, mine and witch hut, then revisit them.",
        "Gold, healing, crafting unlock and reputation are granted once.",
    ),
    BranchFamily(
        "ninemarches.chest.",
        "Enter each regional chest and revisit the same object.",
        "The actual looted state, gold and inventory identities do not pay twice.",
    ),
    BranchFamily(
        "ninemarches.portal.",
        "Walk onto each authored enabled monolith in both directions.",
        "The real player arrives at the configured paired destination.",
    ),
    BranchFamily(
        "ninemarches.mayor.",
        "Use normal recruitment for high standing; low standing uses an approved initial save.",
        "Only the matching low, steady or high reputation dialog branch is available.",
    ),
    BranchFamily(
        "ninemarches.obelisk.",
        "Enter and revisit all six authored obelisks.",
        "Each sigil counts once, including across the route's save checkpoint.",
    ),
    BranchFamily(
        "ninemarches.dig.",
        "Attempt digging at zero and five sigils, then recover all six.",
        "Early digging grants nothing; full digging grants one crown and wakes one actual king.",
    ),
    BranchFamily(
        "ninemarches.finale.",
        "Recover the crown with zero or all companions and defeat the spawned king.",
        "The real boss death completes the main quest; repeats do not recreate crown or boss.",
    ),
    BranchFamily(
        "ninemarches.combat.",
        "Enter each regional encounter family through ordinary map movement.",
        "The cave spawns actual opponents and real combat earns experience from those identities.",
    ),
    BranchFamily(
        "wardens.",
        "Start wardensRoad or standalone Hearthfall, defeat its occupiers and free all three captives before judging Voss.",
        "Campaign mercy/wrath preserves history; standalone callbacks reach Usurpergate without campaign metadata or mercy defender changes.",
    ),
    BranchFamily(
        "hearthfall.",
        "Defeat authored occupiers and the captain before reporting to the elder.",
        "The elder pays once and the campaign advances through its real callback.",
    ),
    BranchFamily(
        "gravemoor.",
        "Defeat the wardens, free all three real cages and judge Voss.",
        "Locked judgment becomes available; mercy or execution sets its own reward and next scenario.",
    ),
    BranchFamily(
        "usurpergate.",
        "Enter through the selected Warden route, defeat the usurper and claim the throne.",
        "Mercy changes the actual defenders; the quest, throne reward and final state are correct.",
    ),
    BranchFamily(
        "ritual.",
        "Enter the chapel, activate by threshold or anchor and use actual turn progression and combat.",
        "Anchors, waves, hazards and leader resolve to a rescued or lost captive with the matching reward.",
    ),
    BranchFamily(
        "siege.",
        "Use authored starting stock and wands earned from real spawned mages.",
        "All four breaches seal after real turns, consume wands, pay the choice-adjusted reward once.",
    ),
    BranchFamily(
        "castle.",
        "Play all three castle chapters through their actual walkable connectors and encounters.",
        "Every authored capture, defender, supply and portal has an individual receipt before campaign completion.",
    ),
    BranchFamily(
        "vhulmarn.",
        "Play the coastal map through clues or bypasses, real cave fights and the altar finale.",
        "The bell, quest item, boss, rewards and optional information routes have observable outcomes.",
    ),
    BranchFamily(
        "kadath.",
        "Play the ascent through guide or bypass, real encounter families and the throne finale.",
        "The gate, quest pickup, boss and market follow their authored conditions.",
    ),
    BranchFamily(
        "sunderedmarch.",
        "Recover the banner before or after accepting the seer's request and play the whole march.",
        "Caches, gates, obelisks, real encounters and the crowned-boss finale converge without duplicate rewards.",
    ),
    BranchFamily(
        "multilevel.",
        "Traverse the actual stairs, upper and lower goals and return over the same connectors.",
        "Native movement changes z through authored links and arrival/goal state persists.",
    ),
    BranchFamily(
        "test.",
        "Move through the test map's actual turn trigger, chest, market, hole and teleporters.",
        "Initialization, inventory, encounter and enabled/disabled connector behavior are observed in the live map.",
    ),
)


@lru_cache(maxsize=1)
def routeModules():
    from importlib import import_module

    return tuple(import_module(name) for name in ROUTE_MODULES)


def getCases():
    return tuple(case for module in routeModules() for case in module.CASES)


def selectedTestNames(class_id=None, group=None):
    if class_id is not None and class_id not in PLAYER_CLASSES:
        raise ValueError("Unknown player class: " + str(class_id))
    groups = {case.group for case in getCases()}
    if group is not None and group not in groups:
        raise ValueError("Unknown gameplay group: " + str(group))
    return tuple(
        testName(case, selected_class)
        for case in getCases()
        if group is None or case.group == group
        for selected_class in case.classes
        if class_id is None or selected_class == class_id
    )


def familyFor(branch_id):
    matches = [family for family in FAMILIES if branch_id.startswith(family.prefix)]
    if len(matches) != 1:
        raise ValueError("Branch needs exactly one reviewed prerequisite/outcome family: " + branch_id)
    return matches[0]


def ownSourceBranches():
    mapping = {}
    branches = {branch for case in getCases() for branch in case.branches}

    def link(map_name, callbacks, *prefixes):
        witnesses = tuple(sorted(branch for branch in branches if branch.startswith(prefixes)))
        for callback in callbacks.split():
            mapping[f"res/maps/{map_name}/script.py:{callback}"] = witnesses

    link(
        "nouraajd",
        "StartEvent.onEnter NouraajdDoorTrigger.trigger DoorDialog.open_door DoorDialog.threatenGate",
        "nouraajd.gate.",
    )
    link("nouraajd", "DoorDialog.can_brace_gate DoorDialog.brace_gate", "nouraajd.deed.Warrior")
    link(
        "nouraajd",
        "MainQuest.isCompleted MainQuest.onComplete RolfQuest.isCompleted RolfQuest.onComplete "
        "GoobyTrigger.trigger CaveTrigger.trigger",
        "nouraajd.deed.",
    )
    link(
        "nouraajd",
        "NouraajdTavernTrigger.trigger TavernDialog1.asked_about_girl TavernDialog2.asked_about_girl",
        "nouraajd.victor.",
    )
    link("nouraajd", "TavernDialog1.sell_beer", "nouraajd.beer.")
    link("nouraajd", "TavernDialog1.can_shadow_robed_men TavernDialog1.shadow_robed_men", "nouraajd.deed.Assasin")
    link(
        "nouraajd",
        "TavernDialog2.confrontVictorForcefully TavernDialog2.calmVictor TavernDialog2.talked_to_victor "
        "TavernDialog2.spawn_cultists TownHallTrigger.trigger TownHallDialog.can_discuss_victor_records "
        "TownHallDialog.victor_encounter_active TownHallDialog.victor_good_end TownHallDialog.victor_bad_end "
        "TownHallDialog.spawn_cultists VictorCourtyardTimerTrigger.trigger CultLeaderQuestTrigger.trigger "
        "VictorQuest.isCompleted",
        "nouraajd.victor.",
    )
    link(
        "nouraajd",
        "TownHallDialog.can_chart_wayfarer_route TownHallDialog.chart_wayfarer_route",
        "nouraajd.deed.Wayfarer",
    )
    link(
        "nouraajd",
        "TownHallDialog.give_letter TownHallDialog.has_letter_quest TownHallDialog.can_offer_letter_work "
        "BerenDialog.can_deliver_letter BerenDialog.deliver_letter BerenDialog.can_return_relic BerenDialog.return_relic "
        "BerenDialog.can_finish_cleanse BerenDialog.finish_cleanse DeliverLetterQuest.isCompleted "
        "RetrieveRelicQuest.isCompleted CleanseCaveQuest.isCompleted ChapelTrigger.trigger CatacombsTrigger.trigger "
        "OctoBogzCaveTrigger.trigger OctobogzHuntTurnTrigger.trigger",
        "nouraajd.chain.",
    )
    link(
        "nouraajd",
        "BerenDialog.can_inspect_stained_glass BerenDialog.inspect_stained_glass",
        "nouraajd.deed.Inquisitor",
    )
    link(
        "nouraajd",
        "BerenDialog.can_decode_stained_glass_ward BerenDialog.decode_stained_glass_ward",
        "nouraajd.deed.Sorcerer",
    )
    link(
        "nouraajd",
        "OctoBogzDialog.contract_not_started OctoBogzDialog.contract_active OctoBogzDialog.contract_completed "
        "OctoBogzDialog.accept_quest QuestGiverTrigger.trigger OctoBogzQuest.isCompleted OctoBogzQuest.onComplete",
        "nouraajd.contract.",
    )
    link(
        "nouraajd",
        "OldWomanTrigger.trigger QuestDialog.start_amulet_quest QuestReturnDialog.complete_amulet_quest "
        "AmuletQuest.isCompleted",
        "nouraajd.amulet.",
    )
    for suffix, race_id in (
        ("HumanRation", "humanRace"),
        ("OutlanderRations", "outlanderRace"),
        ("HighlanderAid", "highlanderRace"),
        ("WandererFocus", "wandererRace"),
    ):
        link("nouraajd", f"TownHallDialog.canOffer{suffix} TownHallDialog.claim{suffix}", "nouraajd.aid." + race_id)
    link(
        "ninemarches",
        "StartEvent.onEnter NineMarchesQuest.isCompleted NineMarchesQuest.onComplete NinefoldKingTrigger.trigger",
        "ninemarches.finale.",
    )
    for callback, prefix in (
        ("CompanionQuest.isCompleted", "ninemarches.companion."),
        ("LearningStone.onEnter", "ninemarches.site.learningStone."),
        ("WitchHut.onEnter", "ninemarches.site.witchHut."),
        ("GoldMine.onEnter", "ninemarches.site.goldMine."),
        ("KeymasterCache.onEnter GateThreshold.onEnter", "ninemarches.gate."),
        ("Obelisk.onEnter", "ninemarches.obelisk."),
        ("ItemCache.onEnter", "ninemarches.companion."),
        ("DigSite.onEnter", "ninemarches.dig."),
        (
            "MayorDialog.high_reputation MayorDialog.low_reputation MayorDialog.steady_reputation "
            "MayorTrigger.trigger TavernTrigger.trigger",
            "ninemarches.mayor.",
        ),
    ):
        link("ninemarches", callback, prefix)
    for class_name, companion, trigger_name in (
        ("KnightDialog", "halda", "KnightTrigger"),
        ("WitchDialog", "morrigane", "WitchTrigger"),
        ("SellswordDialog", "corvyn", "SellswordTrigger"),
    ):
        callbacks = " ".join(
            class_name + "." + method
            for method in (
                "not_met",
                "can_recruit",
                "is_joined",
                "has_left",
                "questInProgress",
                "start",
                "recruit",
                "banter",
            )
        )
        link("ninemarches", callbacks + " " + trigger_name + ".trigger", "ninemarches.companion." + companion + ".")
    return mapping


def sourceBranches():
    mapping = ownSourceBranches()
    for module in routeModules():
        for identity, witnesses in getattr(module, "SOURCE_BRANCHES", {}).items():
            if identity in mapping:
                raise ValueError("Duplicate source mapping: " + identity)
            mapping[identity] = tuple(witnesses)
    return mapping


def defensiveContracts():
    result = {
        "res/maps/nouraajd/script.py:ChangeMap.onEnter": "Legacy callback has no actor instance in the shipped Nouraajd map; Beren owns the real transition.",
        "nouraajd.letter.missingRecovery": "Ordinary inventory operations cannot discard the protected quest letter; recovery is a save-repair contract.",
        "nouraajd.victor.blockedSpawns": "Requires artificial blocked placement/insertion failure; authored courtyard cells are available.",
        "ninemarches.bossBeforeCrown": "The only authored king spawn is the successful crown pickup, so boss-first needs a fixture.",
        "ninemarches.nonplayerEntry": "Player-only event guards are engine contracts rather than selectable player gameplay alternatives.",
    }
    for module in routeModules():
        result.update(getattr(module, "DEFENSIVE_BRANCHES", {}))
        result.update(getattr(module, "DEFENSIVE_SOURCE_BRANCHES", {}))
    return result


def contractEvidence():
    """Explicit regression identities and their proof boundary, not gameplay credit."""
    own = "tests/test_gameplay_branch_catalog.py:GameplayBranchCatalogTest."
    native = "test.py:GameTest."
    return {
        "res/maps/nouraajd/script.py:ChangeMap.onEnter": ("structural", own + "testLegacyTransitionHasNoAuthoredActor"),
        "nouraajd.letter.missingRecovery": (
            "native-direct",
            native + "test_nouraajd_letter_reissue_and_quest_tag_regression",
        ),
        "nouraajd.victor.blockedSpawns": (
            "native-direct",
            native + "test_nouraajd_victor_fully_blocked_leader_spawn_does_not_start_timer",
        ),
        "ninemarches.bossBeforeCrown": ("native-direct", native + "test_map_finales_require_boss_defeat_and_pickup"),
        "ninemarches.nonplayerEntry": ("source-double", own + "testNineMarchesNonplayerEventsAreInertContracts"),
        "vhulmarn.bell.bypassedFinale": ("structural", own + "testVhulmarnBellIsOnEveryAuthoredRouteToTheFinale"),
        "standalone.bossBeforePickup": ("native-direct", native + "test_map_finales_require_boss_defeat_and_pickup"),
        "multilevel.blockedLanding": (
            "native-direct",
            native + "test_multilevel_map_disables_stairs_when_target_is_blocked",
        ),
        "res/maps/multilevel/script.py:LevelStairs.onDestroy": (
            "source-double",
            own + "testConnectorDestructionUnregistersOnlyItsOwnPublishedEdges",
        ),
        "wardens.elder.afterTransition": (
            "source-double",
            own + "testRetainedChapterDialogsRejectAlreadySettledActions",
        ),
        "wardens.voss.afterTransition": (
            "source-double",
            own + "testRetainedChapterDialogsRejectAlreadySettledActions",
        ),
        "castle.portal.blockedTarget": (
            "source-double",
            "tests/test_castle_campaign.py:CastlePresentationTest.testBlockedGarrisonAndLandingAreAnchoredWithoutAcknowledgment",
        ),
        "castle.town.insufficientGold": (
            "source-double",
            own + "testCastlePaidRestRejectsInsufficientGoldAndFullHealth",
        ),
        "ritual.retryFailedTransition": (
            "source-double",
            "tests/test_narrative_consequences.py:RitualResolutionTest.testBadResolutionPaysOnceSettlesQuestsAndRetriesOnlyFailedJourney",
        ),
        "res/maps/hearthfall/script.py:ElderDialog.victory_reported": (
            "source-double",
            own + "testRetainedChapterDialogsRejectAlreadySettledActions",
        ),
        "res/maps/gravemoor/script.py:VossDialog.already_judged": (
            "source-double",
            own + "testRetainedChapterDialogsRejectAlreadySettledActions",
        ),
        "res/plugins/castle_campaign.py:CastlePortal.onDestroy": (
            "source-double",
            own + "testConnectorDestructionUnregistersOnlyItsOwnPublishedEdges",
        ),
    }


def stableAstDump(value):
    """Retain authored syntax while ignoring Python 3.12's empty generic-definition fields."""
    if isinstance(value, ast.AST):
        fields = []
        for name, child in ast.iter_fields(value):
            if (
                name == "type_params"
                and isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and child == []
            ):
                continue
            if child is None and getattr(type(value), name, ...) is None:
                continue
            fields.append(name + "=" + stableAstDump(child))
        return type(value).__name__ + "(" + ", ".join(fields) + ")"
    if isinstance(value, list):
        return "[" + ", ".join(stableAstDump(child) for child in value) + "]"
    return repr(value)


def sourceReviewDigest(root=ROOT):
    """Formatting-independent guard against silently adding branches inside known callbacks.

    Updating this digest requires reviewing the authored source and the obligation
    mappings. Its match confirms only that review scope has not changed.
    """
    paths = set((root / "res/maps").glob("*/*.json")) | set((root / "res/maps").glob("*/script.py"))
    paths.update((root / "res/campaigns").glob("*/campaign.json"))
    paths.update(
        root / source
        for source in ("res/narrative.py", "res/plugins/castle_campaign.py", "res/plugins/octobogz_hunt.py")
    )
    digest = hashlib.sha256()
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        normalized = (
            stableAstDump(ast.parse(text))
            if path.suffix == ".py"
            else (json.dumps(json.loads(text), sort_keys=True, separators=(",", ":")))
        )
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(normalized.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


CAMPAIGN_EDGE_BRANCHES = {
    ("fallOfNouraajd", "recovery", "completed", "cleansing"): ("nouraajd.campaign.toRitual",),
    ("fallOfNouraajd", "cleansing", "good_ending", "siege"): ("nouraajd.campaign.good",),
    ("fallOfNouraajd", "cleansing", "bad_ending", "siege"): ("nouraajd.campaign.bad",),
    ("wardensRoad", "homecoming", "completed", "rescue"): ("wardens.hearthfallToGravemoor",),
    ("wardensRoad", "rescue", "spared", "assault_mercy"): ("wardens.route.assault_mercy",),
    ("wardensRoad", "rescue", "executed", "assault_wrath"): ("wardens.route.assault_wrath",),
    ("longLiveTheQueen", "homecoming", "completed", "guardianAngels"): ("castle.castleHomecoming.complete",),
    ("longLiveTheQueen", "guardianAngels", "completed", "griffinCliff"): ("castle.castleGuardianAngels.complete",),
}


def campaignEdges(root=ROOT):
    result = set()
    for path in sorted((root / "res/campaigns").glob("*/campaign.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        scenarios = document["scenarios"]
        for scenario_id, scenario in scenarios.items():
            for outcome, target in scenario.get("next", {}).items():
                if target not in scenarios:
                    raise ValueError(f"Missing campaign scenario: {path}:{scenario_id}:{target}")
                result.add((document["campaignId"], scenario_id, outcome, target))
    return frozenset(result)


def campaignOutcomes(root=ROOT):
    result = set()
    for path in sorted((root / "res/campaigns").glob("*/campaign.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for scenario_id, scenario in document["scenarios"].items():
            tree = ast.parse((root / "res/maps" / scenario["map"] / "script.py").read_text(encoding="utf-8"))
            declarations = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "CAMPAIGN_OUTCOMES" for target in node.targets)
            ]
            if len(declarations) != 1:
                raise ValueError("Campaign scenario needs one authored outcome declaration: " + scenario["map"])
            for outcome in ast.literal_eval(declarations[0].value):
                result.add(document["campaignId"] + ":" + scenario_id + ":" + outcome)
    return frozenset(result)


def classDefinitions(root=ROOT):
    classes = {}
    callbacks = set()
    for path in sorted((root / "res/maps").glob("*/script.py")):
        source = path.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {method.name: method for method in node.body if isinstance(method, ast.FunctionDef)}
            classes[(path.parent.name, node.name)] = (source, methods, tuple(ast.unparse(base) for base in node.bases))
            for name, method in methods.items():
                if name in EVENT_CALLBACKS and not all(isinstance(item, ast.Pass) for item in method.body):
                    callbacks.add(source + ":" + node.name + "." + name)
    return classes, callbacks


def resolveResource(value, resources, ancestors=()):
    if not isinstance(value, dict):
        raise ValueError("A resource reference must be an object")
    ref = value.get("ref")
    base = {}
    if ref:
        if ref in ancestors:
            raise ValueError("Cyclic resource reference: " + " -> ".join((*ancestors, ref)))
        if ref not in resources:
            raise ValueError("Missing resource reference: " + ref)
        base = resolveResource(resources[ref], resources, (*ancestors, ref))
    result = {**base, **value}
    result["properties"] = {**base.get("properties", {}), **value.get("properties", {})}
    return result


def dialogCallbacks(dialog, resources, *, identity="dialog"):
    """Return callbacks and validate resolved graph links, including post-action branches."""
    resolved = resolveResource(dialog, resources)
    states = [
        resolveResource(value, resources)["properties"] for value in resolved.get("properties", {}).get("states", ())
    ]
    state_ids = [state["stateId"] for state in states]
    if len(state_ids) != len(set(state_ids)):
        raise ValueError("Duplicate dialog state: " + identity)
    callbacks = set()
    for state in states:
        if state.get("condition"):
            callbacks.add(state["condition"])
        numbers = set()
        for option in state.get("options", ()):
            properties = resolveResource(option, resources)["properties"]
            number = properties.get("number", 0)
            if number in numbers:
                raise ValueError(f"Duplicate dialog option: {identity}:{state['stateId']}:{number}")
            numbers.add(number)
            for key in ("action", "condition", "afterCondition"):
                if properties.get(key):
                    callbacks.add(properties[key])
            for key in ("nextStateId", "afterStateId", "elseStateId"):
                target = properties.get(key)
                if target and target != "EXIT" and target not in state_ids:
                    raise ValueError(f"Missing dialog state: {identity}:{target}")
    return resolved.get("class", "CDialog"), frozenset(callbacks)


def sourceCallbacks(root=ROOT):
    classes, callbacks = classDefinitions(root)
    globals_ = {}
    for path in sorted((root / "res/config").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            globals_.update(value)
    for directory in sorted((root / "res/maps").iterdir()):
        if not directory.is_dir():
            continue
        resources = dict(globals_)
        local_ids = set()
        for path in sorted(directory.glob("*.json")):
            if path.name == "map.json":
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                resources.update(value)
                local_ids.update(value)
        for resource_id in sorted(local_ids):
            value = resources[resource_id]
            if not isinstance(value, dict):
                continue
            resolved = resolveResource(value, resources)
            if "states" not in resolved.get("properties", {}):
                continue
            class_id, hooks = dialogCallbacks(value, resources, identity=directory.name + ":" + resource_id)
            for hook in hooks:
                definition = classes.get((directory.name, class_id))
                if definition is None or hook not in definition[1]:
                    raise ValueError(f"Missing exact registered dialog callback: {directory.name}:{class_id}.{hook}")
                callbacks.add(definition[0] + ":" + class_id + "." + hook)
    return frozenset(callbacks)


def auditMappings(callbacks, mappings, contracts, declared_branches):
    issues = []
    for identity in sorted(callbacks):
        if identity not in mappings and identity not in contracts:
            issues.append("Unmapped authored callback: " + identity)
    for identity, witnesses in sorted(mappings.items()):
        if not witnesses:
            issues.append("Callback has no declared route witnesses: " + identity)
        for branch in witnesses:
            if branch not in declared_branches:
                issues.append("Unknown branch witness: " + identity + " -> " + branch)
    return tuple(issues)


def pendingGameplayObligations():
    """Content/runtime blockers stay visible, never classified as defensive or credited."""
    result = {}
    for module in routeModules():
        for actor, evidence in getattr(module, "AUTHORED_UNREACHABLE", {}).items():
            result["castle." + evidence["map"] + ".defender." + actor] = {
                "reason": "Authored actor lies in a component disconnected from all published movement/portal routes.",
                **evidence,
            }
        result.update(getattr(module, "PENDING_GAMEPLAY_OBLIGATIONS", {}))
    return result


def branchCatalog():
    mappings = sourceBranches()
    result = {}
    for case in getCases():
        for branch in case.branches:
            family = familyFor(branch)
            entry = result.setdefault(
                branch,
                {
                    "prerequisites": family.prerequisites,
                    "outcomes": family.outcomes,
                    "sources": set(),
                    "callbacks": set(),
                    "cases": [],
                    "classes": set(),
                },
            )
            entry["sources"].update(case.sources)
            entry["callbacks"].update(identity for identity, witnesses in mappings.items() if branch in witnesses)
            entry["cases"].append(case.id)
            entry["classes"].update(case.classes)
    return {
        branch: {
            **entry,
            "sources": tuple(sorted(entry["sources"])),
            "callbacks": tuple(sorted(entry["callbacks"])),
            "cases": tuple(entry["cases"]),
            "classes": tuple(class_id for class_id in PLAYER_CLASSES if class_id in entry["classes"]),
        }
        for branch, entry in sorted(result.items())
    }


def auditCatalog(root=ROOT):
    cases = getCases()
    branches = {branch for case in cases for branch in case.branches}
    issues = list(auditMappings(sourceCallbacks(root), sourceBranches(), defensiveContracts(), branches))
    actual_maps = {path.name for path in (root / "res/maps").iterdir() if path.is_dir()}
    if actual_maps != set(AUTHORED_MAPS):
        issues.append("Authored map roster changed; review its gameplay obligations")
    for map_name in AUTHORED_MAPS:
        classes = {class_id for case in cases if map_name in case.maps for class_id in case.classes}
        if classes != set(PLAYER_CLASSES):
            issues.append("Incomplete class roster for map: " + map_name)
    edges = campaignEdges(root)
    if edges != set(CAMPAIGN_EDGE_BRANCHES):
        issues.append("Campaign edge obligations differ from the authored manifests")
    issues.extend(
        auditMappings((), {str(edge): values for edge, values in CAMPAIGN_EDGE_BRANCHES.items()}, {}, branches)
    )
    outcomes = {"fallOfNouraajd:recovery:completed": ("nouraajd.campaign.toRitual",)}
    for module in routeModules():
        outcomes.update(getattr(module, "CAMPAIGN_BRANCHES", {}))
    if campaignOutcomes(root) != set(outcomes):
        issues.append("Campaign outcomes, including terminal completions, need reviewed route mappings")
    issues.extend(auditMappings((), outcomes, {}, branches))
    source_definitions = {}
    for identity in sourceBranches():
        source, callback = identity.split(":", 1)
        if source not in source_definitions:
            tree = ast.parse((root / source).read_text(encoding="utf-8"))
            source_definitions[source] = {
                node.name + "." + method.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
                for method in node.body
                if isinstance(method, ast.FunctionDef)
            }
        if callback not in source_definitions[source]:
            issues.append("Mapped source callback no longer exists: " + identity)
    if set(contractEvidence()) != set(defensiveContracts()):
        issues.append("Defensive contracts need explicit automated regression identities")
    for branch in sorted(branches):
        try:
            familyFor(branch)
        except ValueError as exc:
            issues.append(str(exc))
    return {
        "issues": tuple(issues),
        "pendingGameplay": pendingGameplayObligations(),
        "defensiveContracts": defensiveContracts(),
        "contractEvidence": contractEvidence(),
        "caseCount": len(cases),
        "executionCount": len(selectedTestNames()),
        "branchCount": len(branches),
        "proof": "structural-only; actual MCP receipts are required for gameplay acceptance",
    }
