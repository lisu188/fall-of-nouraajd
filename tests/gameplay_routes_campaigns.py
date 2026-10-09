# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete Warden/Castle campaigns and the two natural ritual resolutions."""

from collections import deque
from functools import partial

from tests.castle_walkthrough import MAP_NAMES, authoredMap, shortestRoute
from tests.narrative_walkthrough import authoredRegion
from tests.gameplay_branch_types import RouteCase
from tests.gameplay_branch_journals import rememberJournalContext, verifyJournals
from tests.gameplay_routes_services import readSignpost
from tests.gameplay_routes_caves import verifyInactiveRitualCaves
from tests.gameplay_routes_maps import clearHostiles, hostiles, mapObjects, startMap

WARDEN_MAPS = ("hearthfall", "gravemoor", "usurpergate")
RITUAL_QUESTS = ("ritualQuest", "destroyAnchorsQuest", "rescueCaptiveQuest", "finalResolutionQuest")
GATES = ("spawnPoint1", "spawnPoint2", "spawnPoint3", "spawnPoint4")


def atStart(d, name):
    target = d.object(name, required=False)
    if target:
        if d.coords() == d.coords(target):
            d.revisit(name)
        else:
            d.navigateTo(name)


def fightRemaining(d, names):
    for name in names:
        if d.object(name, required=False):
            d.fight(name)
        d.test.assertIsNone(d.object(name, required=False))


def wardenCampaign(d, judgment, campaign=True):
    if campaign:
        d.startCampaign("wardensRoad")
    else:
        d.startMap("hearthfall")
        d.test.assertEqual("", d.call(d.player, "getStringProperty", "campaign_id"))
    atStart(d, "hearthfallStart")
    d.check("hearthfall.arrival", d.flag("hearthfall_intro") and "hearthfallQuest" in d.questNames())
    verifyJournals(d)
    readSignpost(d, "hearthfallSign")
    d.check("hearthfall.elder.occupied", d.condition("elderDialog", "still_occupied"))
    fightRemaining(d, ("occupierGate", "occupierWest", "occupierEast", "watchCaptain"))
    d.check("hearthfall.captain.defeated", d.flag("captain_defeated"))
    d.test.assertIn("hearthfallQuest", d.questNames())
    d.test.assertNotIn("hearthfallQuest", d.questNames(completed=True))
    d.navigateTo("elderMaren")
    d.test.assertTrue(d.condition("elderDialog", "captain_down"))
    source, gold_before = d.game_map, d.gold()
    d.choose("elderDialog", "report_victory", "captain_down")
    d.check(
        "hearthfall.elder.report",
        d.call(source, "getBoolProperty", "victory_reported")
        and d.call(source, "getBoolProperty", "victory_reward_claimed")
        and d.gold() == gold_before + 150,
    )
    d.check(
        "wardens.hearthfallToGravemoor" if campaign else "wardens.fallback.hearthfallToGravemoor",
        d.map_name == "gravemoor" and "hearthfallQuest" in d.questNames(completed=True),
    )
    atStart(d, "gravemoorStart")
    d.check("gravemoor.arrival", d.flag("gravemoor_intro") and "gravemoorQuest" in d.questNames())
    verifyJournals(d)
    readSignpost(d, "gravemoorSign")
    d.navigateTo("quartermasterVoss")
    d.select("vossDialog", "ENTRY", 0)
    d.check("gravemoor.judgment.locked", d.condition("vossDialog", "captives_missing") and not d.flag("voss_judged"))
    d.select("vossDialog", "WAITING", 0)
    for index, (warden, cage) in enumerate(
        (
            ("cryptWardenWest", "loyalistCageWest"),
            ("cryptWardenEast", "loyalistCageEast"),
            ("cryptWardenNorth", "loyalistCageNorth"),
        ),
        1,
    ):
        fightRemaining(d, (warden,))
        d.navigateTo(cage)
        d.check(
            "gravemoor.cage." + cage, d.number("loyalists_freed") == index and d.object(cage, required=False) is None
        )
    d.saveAndReload("gravemoor-cages-freed")
    d.navigateTo("quartermasterVoss")
    d.test.assertTrue(d.condition("vossDialog", "ready_to_judge"))
    source, gold_before = d.game_map, d.gold()
    spared = judgment == "spared"
    d.choose("vossDialog", "spare_voss" if spared else "execute_voss", "ready_to_judge")
    rememberJournalContext(d, source_map=source, map_name="gravemoor")
    expected_gold = gold_before + (200 if spared else 100)
    if campaign and not spared:
        expected_gold = min(expected_gold, 400)
    d.check(
        "gravemoor.judgment." + judgment,
        d.call(source, "getBoolProperty", "voss_judged")
        and d.call(source, "getBoolProperty", "voss_spared") == spared
        and d.call(source, "getBoolProperty", "judgment_reward_claimed")
        and d.gold() == expected_gold,
        goldBefore=gold_before,
        goldAfter=d.gold(),
    )
    scenario = "assault_mercy" if spared else "assault_wrath"
    d.check(
        "wardens.route." + scenario if campaign else "wardens.fallback.toUsurpergate." + judgment,
        d.map_name == "usurpergate"
        and d.call(d.player, "getStringProperty", "campaign_scenario") == (scenario if campaign else "")
        and "gravemoorQuest" in d.questNames(completed=True),
    )
    atStart(d, "usurpergateStart")
    defenders = ("curtainWallWest1", "curtainWallWest2", "housecarlWest")
    d.check(
        (
            ("usurpergate.approach.mercy" if spared else "usurpergate.approach.wrath")
            if campaign
            else "usurpergate.approach.standalone"
        ),
        d.flag("mercy_route_applied") == (spared and campaign)
        and all((d.object(name, required=False) is None) == (spared and campaign) for name in defenders),
    )
    d.check("usurpergate.arrival", d.flag("usurpergate_intro") and "usurpergateQuest" in d.questNames())
    verifyJournals(d)
    readSignpost(d, "usurpergateSign")
    d.navigateTo("banneretHild")
    d.select("banneretDialog", "ENTRY", 0)
    d.check("usurpergate.banneret.siege", d.condition("banneretDialog", "usurper_stands"))
    d.select("banneretDialog", "SIEGE", 0)
    fightRemaining(d, ("housecarlWest", "housecarlEast", "theUsurper"))
    d.check("usurpergate.usurper.defeated", d.flag("usurper_defeated"))
    d.navigateTo("banneretHild")
    d.select("banneretDialog", "ENTRY", 1)
    d.check("usurpergate.banneret.throne", d.condition("banneretDialog", "throne_waits"))
    d.select("banneretDialog", "THRONE", 0)
    gold_before = d.gold()
    d.navigateTo("obsidianThrone")
    d.check("usurpergate.throne.taken", d.flag("throne_taken") and d.gold() == gold_before + 500)
    d.revisit("obsidianThrone")
    d.check("usurpergate.throne.repeat", d.gold() == gold_before + 500)
    d.navigateTo("banneretHild")
    d.select("banneretDialog", "ENTRY", 2)
    d.check("usurpergate.banneret.retaken", d.condition("banneretDialog", "keep_retaken"))
    completed = set(("hearthfallQuest", "gravemoorQuest", "usurpergateQuest")) <= set(d.questNames(completed=True))
    if campaign:
        d.check(
            "wardens.campaign.complete",
            d.call(d.player, "getBoolProperty", "campaign_finished")
            and d.call(d.player, "getStringProperty", "campaign_history")
            == "homecoming:completed,rescue:" + judgment + "," + scenario + ":completed"
            and completed,
        )
    else:
        d.check(
            "wardens.fallback.complete",
            completed
            and not d.call(d.player, "getBoolProperty", "campaign_finished")
            and d.call(d.player, "getStringProperty", "campaign_history") == ""
            and d.call(d.player, "getStringProperty", "campaign_id") == "",
        )
    d.saveAndReload("wardens-completed")
    d.check(
        "wardens.campaign.persisted" if campaign else "wardens.fallback.persisted",
        d.call(d.player, "getBoolProperty", "campaign_finished") == campaign
        and (campaign or d.call(d.player, "getStringProperty", "campaign_history") == ""),
    )


def creatureTypes(d):
    return {d.call(d.object(name), "getTypeId") for name in hostiles(d)}


def ritualCountdownAfterTurn(before_turn, countdown, last_tick):
    return countdown - int(before_turn - last_tick >= 5)


def finishSiege(d):
    d.test.assertEqual("siege", d.map_name)
    atStart(d, "siegeStart")
    d.check("siege.arrival", d.flag("siege_initialized") and "defendSiegeQuest" in d.questNames())
    initial_wands = d.count("magicWand")
    d.test.assertGreaterEqual(initial_wands, 1)
    seen_types = set()
    sealed = []
    missing_wand_seen = False
    for _ in range(1600):
        seen_types.update(creatureTypes(d))
        remaining = [name for name in GATES if not d.call(d.object(name), "getBoolProperty", "destroyed")]
        if not remaining:
            break
        enabled = [name for name in remaining if d.call(d.object(name), "getBoolProperty", "enabled")]
        if not enabled:
            d.navigateTo("siegeStart")
            d.tick()
            continue
        name = min(enabled, key=lambda value: sum(abs(a - b) for a, b in zip(d.coords(), d.coords(d.object(value)))))
        if d.count("magicWand") == 0:
            d.navigateTo(name)
            if d.count("magicWand") == 0:
                gold_before = d.gold()
                d.test.assertFalse(d.call(d.object(name), "sealBreach"))
                d.test.assertEqual(gold_before, d.gold())
                missing_wand_seen = True
            d.navigateTo("siegeStart")
            d.tick()
            continue
        d.navigateTo(name)
        gate = d.object(name)
        # Headless confirmation leaves the breach open. Declining exploration consumes nothing.
        d.test.assertFalse(d.call(gate, "getBoolProperty", "destroyed"))
        wand_before, gold_before = d.count("magicWand"), d.gold()
        d.test.assertTrue(d.call(gate, "sealBreach"))
        d.pump()
        d.test.assertEqual(wand_before - 1, d.count("magicWand"))
        d.test.assertTrue(d.call(gate, "getBoolProperty", "pendingSeal"))
        d.test.assertFalse(d.call(gate, "sealBreach"))
        if len(sealed) == 3:
            approach = d.call(d.player, "getStringProperty", "campaign_var_nouraajdGateApproach")
            bounty = 475 if approach == "threatened" else 500
            d.test.assertEqual(gold_before + bounty, d.gold())
        d.navigateTo("siegeStart")
        d.waitTurns(32, lambda: not d.call(gate, "getBoolProperty", "pendingSeal"))
        d.check(
            "siege.gate." + name,
            d.call(gate, "getBoolProperty", "destroyed")
            and not d.call(gate, "getBoolProperty", "enabled")
            and not d.call(gate, "getBoolProperty", "canStep"),
        )
        sealed.append(name)
    d.check("siege.wand.missing", missing_wand_seen)
    d.check("siege.spawn.grunt", "siegePritz" in seen_types)
    # Only naturally defeated mages can replace the one authored starting wand.
    acquired_wands = d.count("magicWand") + len(sealed) - initial_wands
    d.check(
        "siege.spawn.mageAndLoot",
        "siegePritzMage" in seen_types and acquired_wands >= max(0, 4 - initial_wands),
        acquiredWands=acquired_wands,
        observedTypes=sorted(seen_types),
    )
    d.check("siege.quest.complete", d.flag("campaign_completed") and "defendSiegeQuest" in d.questNames(completed=True))
    verifyJournals(d)
    gold_before = d.gold()
    d.call(d.player, "checkQuests")
    d.check("siege.reward.once", d.gold() == gold_before)
    d.saveAndReload("siege-completed")
    d.check("siege.completion.persisted", d.flag("campaign_completed") and d.flag("siege_reward_claimed"))


def finishRitualAndSiege(d, outcome, activation="anchor"):
    d.test.assertEqual("ritual", d.map_name)
    atStart(d, "ritualStart")
    d.check("ritual.arrival", d.flag("ritual_initialized") and set(RITUAL_QUESTS) <= set(d.questNames()))
    verifyJournals(d)
    verifyInactiveRitualCaves(d)
    d.navigateTo("ritualWitness")
    d.select("chapelWarningDialog", "ENTRY", 0)
    d.navigateTo("chapelRecords")
    d.check("ritual.records", d.object("chapelRecords") is not None)
    d.test.assertFalse(d.condition("capturedSoulDialog", "can_free_captive"))
    d.check("ritual.captive.locked", d.condition("capturedSoulDialog", "need_more_work"))
    if activation == "threshold":
        positions, walkable = authoredRegion("ritual")
        for name in ("anchorNorth", "anchorCrypt", "anchorSanctum"):
            walkable.discard(positions[name])
        from tests.castle_walkthrough import TransitRoutes

        for _step, arrival in shortestRoute(walkable, TransitRoutes(), d.coords(), positions["sanctumThreshold"]):
            d.navigateCoords(arrival)
        d.check("ritual.activation.threshold", d.flag("ritual_started") and d.number("anchors_destroyed_count") == 0)
    else:
        d.navigateTo("anchorNorth")
        d.check("ritual.activation.anchor", d.flag("ritual_started") and d.flag("anchor_north_destroyed"))
    d.test.assertTrue(d.flag("ritual_active"))
    if outcome == "bad":
        observed_tiers = {"early": set(), "middle": set(), "late": set()}
        for target, branch in ((8, "ritual.timer.eight"), (4, "ritual.timer.four"), (0, "ritual.timer.expired")):
            for _ in range(100):
                countdown = d.number("ritual_countdown")
                observed_tiers["late" if countdown <= 4 else "middle" if countdown <= 8 else "early"].update(
                    creatureTypes(d)
                )
                if countdown <= target:
                    break
                before_turn = d.call(d.game_map, "getTurn")
                before_countdown = countdown
                last_tick = d.number("ritual_last_tick_turn")
                d.tick()
                d.test.assertEqual(
                    ritualCountdownAfterTurn(before_turn, before_countdown, last_tick), d.number("ritual_countdown")
                )
            d.check(branch, d.number("ritual_countdown") <= target)
        d.check("ritual.waves.early", "ritualCultist" in observed_tiers["early"])
        d.check("ritual.waves.middle", {"ritualPritz", "ritualCultist"} <= observed_tiers["middle"])
        d.check("ritual.waves.late", {"ritualMage", "ritualPritz", "ritualCultist"} <= observed_tiers["late"])
        d.check(
            "ritual.captive.lost",
            d.flag("captive_lost") and d.flag("bad_ending") and not d.flag("ritual_resolution_chosen"),
        )
        d.test.assertIn("finalResolutionQuest", d.questNames())
        for name in ("hazardNorth", "hazardCenter", "hazardSouth"):
            d.navigateTo(name)
        d.check("ritual.hazards.inactive", not d.flag("ritual_active"))
    elif activation == "threshold":
        for name in ("hazardNorth", "hazardCenter", "hazardSouth"):
            d.navigateTo(name)
        d.check("ritual.hazards.active", d.flag("ritual_active") and not d.flag("captive_lost"))
    for name, flag in (
        ("anchorNorth", "anchor_north_destroyed"),
        ("anchorCrypt", "anchor_crypt_destroyed"),
        ("anchorSanctum", "anchor_sanctum_destroyed"),
    ):
        if d.object(name, required=False):
            d.navigateTo(name)
        d.check("ritual.anchor." + name, d.flag(flag) and d.object(name, required=False) is None)
        if name == "anchorCrypt":
            d.saveAndReload("ritual-two-anchors")
    d.check("ritual.anchors.complete", d.flag("anchors_destroyed") and d.number("anchors_destroyed_count") == 3)
    d.test.assertTrue(d.flag("leader_spawned"))
    if d.object("ritualLeader", required=False):
        d.fight("ritualLeader")
    d.check("ritual.leader.defeated", d.flag("leader_defeated") and not d.flag("ritual_active"))
    area_flags = (
        ("entryCourtyard", "seen_entry_courtyard"),
        ("outerChapel", "seen_outer_chapel"),
        ("sideCrypt", "seen_side_crypt"),
        ("ritualSanctum", "seen_ritual_sanctum"),
    )
    for name, flag in area_flags:
        d.navigateTo(name)
        d.test.assertTrue(d.flag(flag), name)
        d.revisit(name)
        d.test.assertTrue(d.flag(flag), name)
    d.check("ritual.areas", all(d.flag(flag) for _name, flag in area_flags))
    d.test.assertEqual(outcome == "bad", d.flag("captive_lost"))
    d.navigateTo("ritualCaptive")
    source, gold_before, potions_before = d.game_map, d.gold(), d.count("LifePotion")
    rememberJournalContext(d)
    verifyJournals(d)
    if outcome == "good":
        d.choose("capturedSoulDialog", "free_captive", "can_free_captive")
        resolution_flag = "captive_freed"
    else:
        d.select("capturedSoulDialog", "ENTRY", 1)
        d.choose("capturedSoulDialog", "continueAfterLoss", "canContinueAfterLoss")
        resolution_flag = "captive_lost"
    d.check(
        "ritual.resolution." + outcome,
        d.call(source, "getBoolProperty", resolution_flag)
        and d.call(source, "getBoolProperty", "ritual_resolution_chosen")
        and d.call(source, "getBoolProperty", "reward_claimed")
        and d.gold() == gold_before + (300 if outcome == "good" else 100)
        and d.count("LifePotion") == potions_before + int(outcome == "good"),
    )
    d.check("ritual.toSiege", d.map_name == "siege" and set(RITUAL_QUESTS) <= set(d.questNames(completed=True)))
    finishSiege(d)


def ritualRoute(d, outcome, activation):
    d.startMap("ritual")
    finishRitualAndSiege(d, outcome, activation)


def castleNavigate(d, coords, walkable, portals, reserved):
    available = walkable - {reserved}
    route = shortestRoute(available, portals, d.coords(), tuple(coords))
    for _step, arrival in route:
        d.navigateCoords(arrival)
        d.test.assertEqual(tuple(arrival), d.coords())


def castleNearestDefender(remaining, objects, walkable, portals, origin, reserved):
    distances = {tuple(origin): 0}
    queue = deque([tuple(origin)])
    available = walkable - {reserved}
    while queue:
        point = queue.popleft()
        steps = [(point[0] + dx, point[1] + dy, point[2]) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
        steps.extend(sorted(portals.passages.get(point, ())))
        for step in steps:
            if step not in available:
                continue
            arrival = portals.get(step, step)
            if arrival not in available or arrival in distances:
                continue
            distances[arrival] = distances[point] + 1
            queue.append(arrival)
    reachable = [name for name in remaining if objects[name]["coords"] in distances]
    return min(reachable, key=lambda name: (distances[objects[name]["coords"]], name), default=None)


def castleTownRest(d, objects, walkable, portals, reserved, mission):
    towns = [
        name
        for name, value in objects.items()
        if value["properties"].get("campaign_loyalTown") and value["properties"].get("campaign_isTown")
    ]
    d.test.assertTrue(towns, "The paid-rest route needs an authored loyal town")
    town = min(
        towns,
        key=lambda name: (
            len(shortestRoute(walkable - {reserved}, portals, d.coords(), objects[name]["coords"])),
            name,
        ),
    )
    castleNavigate(d, objects[town]["coords"], walkable, portals, reserved)
    d.test.assertTrue(d.flag("campaign_castleSupply_" + town))
    income = {
        name: value
        for name, value in objects.items()
        if value.get("class") in ("CastleSupply", "CastleObjective")
        and not d.flag(
            ("campaign_castleSupply_" if value["class"] == "CastleSupply" else "campaign_castleCaptured_") + name
        )
    }
    blocked = {reserved, *(value["coords"] for value in income.values())}
    # Claim only supplies needed to leave the town. Other income stays reserved
    # while actual paid rests reduce the player's observed gold below ten.
    for _ in range(len(income) + 1):
        rest_walkable = walkable - blocked
        defenders = []
        for name in mission["defenderIds"]:
            try:
                route = shortestRoute(rest_walkable, portals, d.coords(), objects[name]["coords"])
                defenders.append((len(route), name))
            except AssertionError:
                # Every defender retains its separate mandatory obligation below.
                continue
        if defenders:
            break
        exits = []
        for name, value in income.items():
            if value["class"] != "CastleSupply":
                continue
            try:
                route = shortestRoute(walkable - (blocked - {value["coords"]}), portals, d.coords(), value["coords"])
                exits.append((len(route), name))
            except AssertionError:
                continue
        d.test.assertTrue(exits, "No authored supply permits leaving the loyal town without capturing a new position")
        name = min(exits)[1]
        value = income.pop(name)
        blocked.discard(value["coords"])
        castleNavigate(d, value["coords"], walkable - blocked, portals, reserved)
        d.test.assertTrue(d.flag("campaign_castleSupply_" + name))
    paid_rest_seen = False
    for _distance, name in sorted(defenders):
        if d.object(name, required=False) is None:
            continue
        castleNavigate(d, objects[name]["coords"], rest_walkable, portals, reserved)
        if d.call(d.player, "getHp") == d.call(d.player, "getHpMax"):
            continue
        recovery = d.recoveryEnabled
        d.recoveryEnabled = False
        try:
            castleNavigate(d, objects[town]["coords"], rest_walkable, portals, reserved)
            if d.call(d.player, "getHp") == d.call(d.player, "getHpMax"):
                continue
            if d.gold() < 10:
                d.test.assertTrue(paid_rest_seen, "The route must spend gold through ordinary town rests")
                d.check(
                    "castle.town.insufficientGold", not d.restAtTown(town), gold=d.gold(), hp=d.call(d.player, "getHp")
                )
                return
            d.check("castle.town.rest", d.restAtTown(town))
            d.check("castle.town.fullHealth", not d.restAtTown(town))
            paid_rest_seen = True
        finally:
            d.recoveryEnabled = recovery
    d.test.fail(("Authored encounters did not produce enough natural injuries to exhaust paid town rest", d.gold()))


def castleSupply(d, name, objects, walkable, portals, reserved):
    source = objects[name]["coords"]
    castleNavigate(d, source, walkable, portals, reserved)
    d.test.assertTrue(d.flag("campaign_castleSupply_" + name))
    candidates = []
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        neighbor = (source[0] + dx, source[1] + dy, source[2])
        if neighbor in walkable and neighbor != reserved:
            try:
                route = shortestRoute(walkable - {reserved}, portals, d.coords(), neighbor)
            except AssertionError:
                continue
            candidates.append((len(route), neighbor))
    d.test.assertTrue(candidates, ("No actual adjacent supply reentry route", name, source))
    neighbor = min(candidates)[1]
    castleNavigate(d, neighbor, walkable, portals, reserved)
    d.test.assertEqual(neighbor, d.coords())
    # The adjacent approach may itself claim another authored garrison's supplies.
    # Snapshot only the final one-cell reentry into this already claimed source.
    gold_before = d.gold()
    d.step(source)
    d.test.assertEqual(source, d.coords())
    d.check(
        "castle." + d.map_name + ".supply." + name,
        d.gold() == gold_before and d.flag("campaign_castleSupply_" + name),
        approach=neighbor,
        goldBeforeReentry=gold_before,
        goldAfterReentry=d.gold(),
    )


def castleChapter(d, map_name, rest=False):
    d.test.assertEqual(map_name, d.map_name)
    _document, objects, walkable, portals, mission = authoredMap(map_name)
    prefix = "castle." + map_name
    final_name = mission["objectiveIds"][-1]
    reserved = objects[final_name]["coords"]
    d.tick()
    d.check(prefix + ".arrival", mission["questId"] in d.questNames())
    guarded_approaches = []
    for name in mission["captureIds"]:
        if name == final_name:
            continue
        marker_position = objects[name]["coords"]
        guards = tuple(filter(None, objects[name]["properties"].get("campaign_guards", "").split(",")))
        if not guards:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (marker_position[0] + dx, marker_position[1] + dy, marker_position[2])
            try:
                route = shortestRoute(walkable - {reserved, marker_position}, portals, d.coords(), neighbor)
            except AssertionError:
                continue
            guarded_approaches.append((len(route), name, neighbor, route))
    d.test.assertTrue(guarded_approaches, (map_name, "No guarded objective interaction route"))
    _length, guarded_name, _neighbor, guarded_route = min(guarded_approaches)
    for _step, arrival in guarded_route:
        d.navigateCoords(arrival)
        d.test.assertEqual(tuple(arrival), d.coords())
    guarded_marker = d.object(guarded_name)
    d.test.assertFalse(d.flag("campaign_castleCaptured_" + guarded_name))
    gold_before = d.gold()
    d.check(
        prefix + ".guardedCapture",
        not d.call(guarded_marker, "capture", d.player)
        and not d.flag("campaign_castleCaptured_" + guarded_name)
        and d.gold() == gold_before,
    )
    if rest:
        d.test.assertTrue(objects[guarded_name]["properties"].get("campaign_isTown"))
        gold_before, hp_before = d.gold(), d.call(d.player, "getHp")
        rest_dialog = d.call(d.game, "createObject", "CastleTownRestDialog")
        d.check(
            "castle.town.locked",
            not d.call(rest_dialog, "configureTown", guarded_marker)
            and d.gold() == gold_before
            and d.call(d.player, "getHp") == hp_before,
        )
        castleTownRest(d, objects, walkable, portals, reserved, mission)
    for name in ("castleCatherine", "castleChristian"):
        castleNavigate(d, objects[name]["coords"], walkable, portals, reserved)
        d.choose(objects[name]["properties"]["campaign_dialog"], "reportProgress")
    d.check(prefix + ".officers", mission["questId"] in d.questNames())
    supplies = sorted(name for name, value in objects.items() if value.get("class") == "CastleSupply")
    for name in supplies:
        castleSupply(d, name, objects, walkable, portals, reserved)
    # Visit every connector before the last required capture can end this chapter.
    for name, value in sorted(objects.items()):
        if value.get("class") != "CastlePortal":
            continue
        source = value["coords"]
        target = tuple(int(value["properties"]["campaign_target" + axis]) for axis in "XYZ")
        if value["properties"].get("campaign_portalKind") == "diagonalPassage":
            castleNavigate(d, source, walkable, portals, reserved)
            d.navigateCoords(target)
            d.check(prefix + ".portal." + name, d.coords() == target)
            continue
        candidates = [(source[0] + dx, source[1] + dy, source[2]) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        approaches = []
        for candidate in candidates:
            if candidate not in walkable or candidate == reserved:
                continue
            try:
                route = shortestRoute(walkable - {reserved}, portals, d.coords(), candidate)
            except AssertionError:
                continue
            approaches.append((len(route), candidate))
        d.test.assertTrue(approaches, (map_name, "No natural connector approach", name))
        castleNavigate(d, min(approaches)[1], walkable, portals, reserved)
        d.step(source)
        d.check(prefix + ".portal." + name, d.coords() == target)
    for name in mission["captureIds"]:
        if name == final_name:
            continue
        marker = d.object(name)
        position = objects[name]["coords"]
        neighbors = [(position[0] + dx, position[1] + dy, position[2]) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        routes = []
        for neighbor in neighbors:
            if neighbor not in walkable or neighbor == reserved:
                continue
            try:
                route = shortestRoute(walkable - {reserved}, portals, d.coords(), neighbor)
            except AssertionError:
                continue
            routes.append((len(route), neighbor))
        d.test.assertTrue(routes, (map_name, name, "No guarded capture approach"))
        castleNavigate(d, min(routes)[1], walkable, portals, reserved)
        guards = tuple(filter(None, objects[name]["properties"].get("campaign_guards", "").split(",")))
        if any(d.object(guard, required=False) for guard in guards):
            d.test.assertFalse(d.call(marker, "capture", d.player))
        castleNavigate(d, position, walkable, portals, reserved)
        d.check(prefix + ".capture." + name, d.flag("campaign_castleCaptured_" + name))
        gold_before = d.gold()
        d.test.assertFalse(d.call(marker, "capture", d.player))
        d.test.assertEqual(gold_before, d.gold())
    d.check(
        prefix + ".captureRepeat",
        all(d.flag("campaign_castleCaptured_" + name) for name in mission["captureIds"] if name != final_name),
    )
    final_guards = set(filter(None, objects[final_name]["properties"].get("campaign_guards", "").split(",")))
    remaining = set(mission["defenderIds"]) - final_guards
    while remaining:
        name = castleNearestDefender(remaining, objects, walkable, portals, d.coords(), reserved)
        if name is None:
            for absent in sorted(remaining):
                if d.object(absent, required=False) is None:
                    d.check(prefix + ".defender." + absent, d.flag("campaign_castleDefeated_" + absent))
                    remaining.remove(absent)
            d.test.assertFalse(remaining, (map_name, "No authored route to remaining defenders", sorted(remaining)))
            break
        actor = d.object(name, required=False)
        if actor:
            castleNavigate(d, objects[name]["coords"], walkable, portals, reserved)
        d.check(prefix + ".defender." + name, d.flag("campaign_castleDefeated_" + name))
        remaining.remove(name)
    d.saveAndReload(map_name + "-before-final-capture")
    for name in final_guards:
        if d.object(name, required=False):
            d.fight(name)
        d.check(prefix + ".defender." + name, d.flag("campaign_castleDefeated_" + name))
    source = d.game_map
    gold_before = d.gold()
    final_capture_gold = d.call(d.object(final_name), "getNumericProperty", "campaign_rewardGold")
    d.navigateTo(final_name)
    d.check(
        prefix + ".capture." + final_name, d.call(source, "getBoolProperty", "campaign_castleCaptured_" + final_name)
    )
    d.check(
        prefix + ".complete",
        d.call(source, "getBoolProperty", "campaign_castleFinished_" + mission["scenarioId"])
        and mission["questId"] in d.questNames(completed=True)
        and d.gold() == gold_before + final_capture_gold + mission["victoryGold"],
        goldBefore=gold_before,
        captureGold=final_capture_gold,
        victoryGold=mission["victoryGold"],
        goldAfter=d.gold(),
    )


def castleCampaign(d):
    d.startCampaign("longLiveTheQueen")
    for index, map_name in enumerate(MAP_NAMES):
        castleChapter(d, map_name, rest=index == 0)
    d.check(
        "castle.campaign.complete",
        d.call(d.player, "getBoolProperty", "campaign_finished")
        and d.call(d.player, "getStringProperty", "campaign_history")
        == "homecoming:completed,guardianAngels:completed,griffinCliff:completed",
    )
    d.saveAndReload("castle-campaign-completed")
    d.check("castle.campaign.persisted", d.call(d.player, "getBoolProperty", "campaign_finished"))


WARDEN_COMMON = (
    "hearthfall.signpost.read",
    "hearthfall.signpost.repeat",
    "gravemoor.signpost.read",
    "gravemoor.signpost.repeat",
    "usurpergate.signpost.read",
    "usurpergate.signpost.repeat",
    "hearthfall.arrival",
    "hearthfall.elder.occupied",
    "hearthfall.captain.defeated",
    "hearthfall.elder.report",
    "wardens.hearthfallToGravemoor",
    "gravemoor.arrival",
    "gravemoor.judgment.locked",
    "gravemoor.cage.loyalistCageWest",
    "gravemoor.cage.loyalistCageEast",
    "gravemoor.cage.loyalistCageNorth",
    "usurpergate.arrival",
    "usurpergate.throne.premature",
    "usurpergate.banneret.siege",
    "usurpergate.usurper.defeated",
    "usurpergate.banneret.throne",
    "usurpergate.throne.taken",
    "usurpergate.throne.repeat",
    "usurpergate.banneret.retaken",
    "wardens.campaign.complete",
    "wardens.campaign.persisted",
)
WARDEN_FALLBACK_COMMON = tuple(branch for branch in WARDEN_COMMON if not branch.startswith("wardens.")) + (
    "wardens.fallback.hearthfallToGravemoor",
    "usurpergate.approach.standalone",
    "wardens.fallback.complete",
    "wardens.fallback.persisted",
)
SIEGE_BRANCHES = (
    "siege.arrival",
    *("siege.gate." + name for name in GATES),
    "siege.wand.missing",
    "siege.spawn.grunt",
    "siege.spawn.mageAndLoot",
    "siege.quest.complete",
    "siege.reward.once",
    "siege.completion.persisted",
)
RITUAL_COMMON = (
    "ritual.arrival",
    "ritual.cave.inactive",
    "ritual.records",
    "ritual.captive.locked",
    "ritual.anchor.anchorNorth",
    "ritual.anchor.anchorCrypt",
    "ritual.anchor.anchorSanctum",
    "ritual.anchors.complete",
    "ritual.leader.defeated",
    "ritual.areas",
    "ritual.toSiege",
    *SIEGE_BRANCHES,
)
RITUAL_GOOD_BRANCHES = RITUAL_COMMON + ("ritual.activation.anchor", "ritual.resolution.good")
RITUAL_BAD_BRANCHES = RITUAL_COMMON + (
    "ritual.activation.threshold",
    "ritual.timer.eight",
    "ritual.timer.four",
    "ritual.timer.expired",
    "ritual.waves.early",
    "ritual.waves.middle",
    "ritual.waves.late",
    "ritual.captive.lost",
    "ritual.hazards.inactive",
    "ritual.resolution.bad",
)


def castleBranches():
    result = [
        "castle.town.rest",
        "castle.town.fullHealth",
        "castle.town.insufficientGold",
        "castle.town.locked",
        "castle.campaign.complete",
        "castle.campaign.persisted",
    ]
    for map_name in MAP_NAMES:
        _document, objects, _walkable, _portals, mission = authoredMap(map_name)
        prefix = "castle." + map_name
        result.extend(
            (
                prefix + ".arrival",
                prefix + ".officers",
                prefix + ".complete",
                prefix + ".guardedCapture",
                prefix + ".captureRepeat",
            )
        )
        result.extend(prefix + ".capture." + name for name in mission["captureIds"])
        result.extend(prefix + ".defender." + name for name in mission["defenderIds"])
        result.extend(
            prefix + ".supply." + name for name, value in objects.items() if value.get("class") == "CastleSupply"
        )
        result.extend(
            prefix + ".portal." + name for name, value in objects.items() if value.get("class") == "CastlePortal"
        )
    return tuple(result)


def sources(maps):
    return tuple(
        "res/maps/" + map_name + "/" + filename
        for map_name in maps
        for filename in ("script.py", "config.json", "map.json")
    )


CASES = (
    RouteCase(
        id="wardens-mercy",
        group="campaigns",
        maps=WARDEN_MAPS,
        campaign="wardensRoad",
        branches=WARDEN_COMMON
        + ("gravemoor.judgment.spared", "wardens.route.assault_mercy", "usurpergate.approach.mercy"),
        run=partial(wardenCampaign, judgment="spared"),
        sources=sources(WARDEN_MAPS) + ("res/plugins/object.py",),
        duration_seconds=600,
    ),
    RouteCase(
        id="wardens-wrath",
        group="campaigns",
        maps=WARDEN_MAPS,
        campaign="wardensRoad",
        branches=WARDEN_COMMON
        + ("gravemoor.judgment.executed", "wardens.route.assault_wrath", "usurpergate.approach.wrath"),
        run=partial(wardenCampaign, judgment="executed"),
        sources=sources(WARDEN_MAPS) + ("res/plugins/object.py",),
        duration_seconds=600,
    ),
    RouteCase(
        id="wardens-standalone-spared",
        group="standalone",
        maps=WARDEN_MAPS,
        branches=WARDEN_FALLBACK_COMMON + ("gravemoor.judgment.spared", "wardens.fallback.toUsurpergate.spared"),
        run=partial(wardenCampaign, judgment="spared", campaign=False),
        sources=sources(WARDEN_MAPS) + ("res/plugins/object.py",),
        duration_seconds=600,
    ),
    RouteCase(
        id="wardens-standalone-executed",
        group="standalone",
        maps=WARDEN_MAPS,
        branches=WARDEN_FALLBACK_COMMON + ("gravemoor.judgment.executed", "wardens.fallback.toUsurpergate.executed"),
        run=partial(wardenCampaign, judgment="executed", campaign=False),
        sources=sources(WARDEN_MAPS) + ("res/plugins/object.py",),
        duration_seconds=600,
    ),
    RouteCase(
        id="ritual-anchor-rescue",
        group="campaigns",
        maps=("ritual", "siege"),
        branches=RITUAL_GOOD_BRANCHES,
        run=partial(ritualRoute, outcome="good", activation="anchor"),
        sources=sources(("ritual", "siege")),
        duration_seconds=600,
    ),
    RouteCase(
        id="ritual-threshold-timeout",
        group="campaigns",
        maps=("ritual", "siege"),
        branches=RITUAL_BAD_BRANCHES,
        run=partial(ritualRoute, outcome="bad", activation="threshold"),
        sources=sources(("ritual", "siege")),
        duration_seconds=900,
    ),
    RouteCase(
        id="ritual-threshold-rescue",
        group="campaigns",
        maps=("ritual", "siege"),
        branches=RITUAL_COMMON + ("ritual.activation.threshold", "ritual.hazards.active", "ritual.resolution.good"),
        run=partial(ritualRoute, outcome="good", activation="threshold"),
        sources=sources(("ritual", "siege")),
        duration_seconds=600,
    ),
    RouteCase(
        id="castle-all-authored-content",
        group="campaigns",
        maps=MAP_NAMES,
        campaign="longLiveTheQueen",
        branches=castleBranches(),
        run=castleCampaign,
        sources=sources(MAP_NAMES) + ("res/plugins/castle_campaign.py",),
        duration_seconds=1800,
    ),
)


DEFENSIVE_BRANCHES = {
    "wardens.elder.afterTransition": "Reporting immediately leaves Hearthfall; old-map dialog reentry is a retained-handle contract.",
    "wardens.voss.afterTransition": "Judgment immediately leaves Gravemoor; repeated old-map actions are contract tests.",
    "castle.portal.blockedTarget": "Shipped connector targets are walkable; exercising a blocked target needs a changed fixture.",
    "ritual.retryFailedTransition": "Requires a map-load failure fixture; successful authored content cannot induce it naturally.",
}


PENDING_GAMEPLAY_OBLIGATIONS = {
    "usurpergate.throne.premature": {
        "map": "usurpergate",
        "coords": (12, 3, 0),
        "actor": "theUsurper",
        "actorCoords": (12, 6, 0),
        "reason": (
            "No real early-throne gameplay witness has been established. The pursuing Usurper and unordered native "
            "actor commit order make a geometrical detour insufficient: the reviewed finite movement model permits "
            "a route for player-first commits but finds none for boss-first commits after the existing arrival. "
            "A pure callback regression proves only the no-reward guard; it gives no gameplay credit."
        ),
        "sources": (
            "res/maps/usurpergate/script.py:ObsidianThrone.onEnter",
            "res/maps/usurpergate/config.json:theUsurper.controller",
            "res/maps/usurpergate/map.json",
            "src/core/CMap.cpp:CMap::move",
            "src/core/CMap.h:mapObjects",
            "src/core/CController.cpp:find_shared_target_next_step",
        ),
        "supplementalTest": (
            "tests.test_gameplay_routes_campaigns.GameplayCampaignRouteTest."
            "testPrematureThroneEntryPreservesRewardsQuestsAndCampaign"
        ),
    },
}


# These remain declared route obligations. Static discovery is a content blocker,
# never a reason to credit or silently drop a natural-combat branch.
AUTHORED_UNREACHABLE = {
    "castleHomecomingEncounter958": {"map": "castleHomecoming", "coords": (69, 30, 0), "componentCells": 5},
    "castleHomecomingEncounter1007": {"map": "castleHomecoming", "coords": (53, 45, 0), "componentCells": 21},
    "castleHomecomingEncounter1025": {"map": "castleHomecoming", "coords": (3, 50, 0), "componentCells": 4},
    "castleHomecomingEncounter1445": {"map": "castleHomecoming", "coords": (52, 48, 0), "componentCells": 21},
    "castleGriffinCliffEncounter524": {"map": "castleGriffinCliff", "coords": (65, 69, 0), "componentCells": 9},
    "castleGriffinCliffEncounter1150": {"map": "castleGriffinCliff", "coords": (6, 64, 0), "componentCells": 39},
    "castleGriffinCliffEncounter1151": {"map": "castleGriffinCliff", "coords": (3, 69, 0), "componentCells": 39},
    "castleGriffinCliffEncounter2028": {"map": "castleGriffinCliff", "coords": (34, 17, 1), "componentCells": 33},
    "castleGriffinCliffEncounter2064": {"map": "castleGriffinCliff", "coords": (34, 4, 1), "componentCells": 7},
    "castleGriffinCliffEncounter2066": {"map": "castleGriffinCliff", "coords": (51, 52, 1), "componentCells": 11},
    "castleGriffinCliffEncounter2125": {"map": "castleGriffinCliff", "coords": (44, 9, 1), "componentCells": 4},
    "castleGriffinCliffEncounter2154": {"map": "castleGriffinCliff", "coords": (17, 53, 1), "componentCells": 18},
    "castleGriffinCliffEncounter2200": {"map": "castleGriffinCliff", "coords": (40, 4, 1), "componentCells": 20},
}


SOURCE_BRANCHES = {
    "res/maps/hearthfall/script.py:HearthfallStart.onEnter": ("hearthfall.arrival",),
    "res/maps/hearthfall/script.py:HearthfallQuest.isCompleted": ("hearthfall.elder.report",),
    "res/maps/hearthfall/script.py:ElderDialog.still_occupied": ("hearthfall.elder.occupied",),
    "res/maps/hearthfall/script.py:ElderDialog.captain_down": (
        "hearthfall.captain.defeated",
        "hearthfall.elder.report",
    ),
    "res/maps/hearthfall/script.py:ElderDialog.report_victory": ("hearthfall.elder.report",),
    "res/maps/hearthfall/script.py:ElderTrigger.trigger": ("hearthfall.elder.report",),
    "res/maps/hearthfall/script.py:CaptainTrigger.trigger": ("hearthfall.captain.defeated",),
    "res/maps/hearthfall/script.py:GateSentryTrigger.trigger": ("hearthfall.captain.defeated",),
    "res/maps/gravemoor/script.py:GravemoorStart.onEnter": ("gravemoor.arrival",),
    "res/maps/gravemoor/script.py:LoyalistCage.onEnter": tuple(
        "gravemoor.cage." + name for name in ("loyalistCageWest", "loyalistCageEast", "loyalistCageNorth")
    ),
    "res/maps/gravemoor/script.py:GravemoorQuest.isCompleted": (
        "gravemoor.judgment.spared",
        "gravemoor.judgment.executed",
    ),
    "res/maps/gravemoor/script.py:VossDialog.captives_missing": ("gravemoor.judgment.locked",),
    "res/maps/gravemoor/script.py:VossDialog.ready_to_judge": (
        "gravemoor.judgment.spared",
        "gravemoor.judgment.executed",
    ),
    "res/maps/gravemoor/script.py:VossDialog._pass_judgment": (
        "gravemoor.judgment.spared",
        "gravemoor.judgment.executed",
    ),
    "res/maps/gravemoor/script.py:VossDialog.spare_voss": ("gravemoor.judgment.spared",),
    "res/maps/gravemoor/script.py:VossDialog.execute_voss": ("gravemoor.judgment.executed",),
    "res/maps/gravemoor/script.py:VossTrigger.trigger": (
        "gravemoor.judgment.locked",
        "gravemoor.judgment.spared",
        "gravemoor.judgment.executed",
    ),
    "res/maps/usurpergate/script.py:UsurpergateStart.onEnter": (
        "usurpergate.approach.mercy",
        "usurpergate.approach.wrath",
    ),
    "res/maps/usurpergate/script.py:ObsidianThrone.onEnter": (
        "usurpergate.throne.premature",
        "usurpergate.throne.taken",
        "usurpergate.throne.repeat",
    ),
    "res/maps/usurpergate/script.py:UsurpergateQuest.isCompleted": ("usurpergate.throne.taken",),
    "res/maps/usurpergate/script.py:BanneretDialog.usurper_stands": ("usurpergate.banneret.siege",),
    "res/maps/usurpergate/script.py:BanneretDialog.throne_waits": ("usurpergate.banneret.throne",),
    "res/maps/usurpergate/script.py:BanneretDialog.keep_retaken": ("usurpergate.banneret.retaken",),
    "res/maps/usurpergate/script.py:BanneretTrigger.trigger": (
        "usurpergate.banneret.throne",
        "usurpergate.banneret.retaken",
    ),
    "res/maps/usurpergate/script.py:UsurperTrigger.trigger": ("usurpergate.usurper.defeated",),
    "res/maps/usurpergate/script.py:BreachGuardTrigger.trigger": ("usurpergate.usurper.defeated",),
    "res/maps/ritual/script.py:StartEvent.onEnter": ("ritual.arrival",),
    "res/maps/ritual/script.py:RitualQuest.isCompleted": ("ritual.leader.defeated",),
    "res/maps/ritual/script.py:DestroyAnchorsQuest.isCompleted": ("ritual.anchors.complete",),
    "res/maps/ritual/script.py:RescueCaptiveQuest.isCompleted": ("ritual.resolution.good", "ritual.resolution.bad"),
    "res/maps/ritual/script.py:FinalResolutionQuest.isCompleted": ("ritual.resolution.good", "ritual.resolution.bad"),
    "res/maps/ritual/script.py:CapturedSoulDialog.canContinueAfterLoss": ("ritual.resolution.bad",),
    "res/maps/ritual/script.py:CapturedSoulDialog.continueAfterLoss": ("ritual.resolution.bad",),
    "res/maps/ritual/script.py:CapturedSoulDialog.can_free_captive": (
        "ritual.captive.locked",
        "ritual.resolution.good",
    ),
    "res/maps/ritual/script.py:CapturedSoulDialog.is_captive_lost": ("ritual.captive.lost", "ritual.resolution.bad"),
    "res/maps/ritual/script.py:CapturedSoulDialog.is_captive_freed": ("ritual.resolution.good",),
    "res/maps/ritual/script.py:CapturedSoulDialog.need_more_work": ("ritual.captive.locked",),
    "res/maps/ritual/script.py:CapturedSoulDialog.free_captive": ("ritual.resolution.good",),
    "res/maps/ritual/script.py:RitualTurnTrigger.trigger": (
        "ritual.timer.eight",
        "ritual.timer.four",
        "ritual.timer.expired",
        "ritual.waves.early",
        "ritual.waves.middle",
        "ritual.waves.late",
    ),
    "res/maps/ritual/script.py:WitnessTrigger.trigger": ("ritual.records",),
    "res/maps/ritual/script.py:RecordsTrigger.trigger": ("ritual.records",),
    "res/maps/ritual/script.py:SanctumTrigger.trigger": ("ritual.activation.threshold",),
    "res/maps/ritual/script.py:AnchorNorthTrigger.trigger": ("ritual.anchor.anchorNorth",),
    "res/maps/ritual/script.py:AnchorCryptTrigger.trigger": ("ritual.anchor.anchorCrypt",),
    "res/maps/ritual/script.py:AnchorSanctumTrigger.trigger": ("ritual.anchor.anchorSanctum",),
    "res/maps/ritual/script.py:RitualLeaderTrigger.trigger": ("ritual.leader.defeated",),
    "res/maps/ritual/script.py:CaptiveTrigger.trigger": ("ritual.resolution.good", "ritual.resolution.bad"),
    **{
        "res/maps/ritual/script.py:" + name + ".trigger": ("ritual.hazards.active", "ritual.hazards.inactive")
        for name in ("HazardNorthTrigger", "HazardCenterTrigger", "HazardSouthTrigger")
    },
    **{
        "res/maps/ritual/script.py:" + name + ".trigger": ("ritual.areas",)
        for name in ("EntryCourtyardTrigger", "OuterChapelTrigger", "SideCryptTrigger", "SanctumAreaTrigger")
    },
    "res/maps/siege/script.py:SiegeStartEvent.onEnter": ("siege.arrival",),
    "res/maps/siege/script.py:DefendSiegeQuest.isCompleted": ("siege.quest.complete",),
    "res/maps/siege/script.py:DefendSiegeQuest.onComplete": ("siege.quest.complete", "siege.reward.once"),
    "res/maps/siege/script.py:SpawnPoint.onCreate": ("siege.arrival",),
    "res/maps/siege/script.py:SpawnPoint.onTurn": ("siege.spawn.grunt", "siege.spawn.mageAndLoot"),
    "res/maps/siege/script.py:SpawnPoint.onEnter": ("siege.wand.missing",)
    + tuple("siege.gate." + name for name in GATES),
    "res/maps/siege/script.py:TurnTrigger.trigger": tuple("siege.gate." + name for name in GATES),
    "res/plugins/castle_campaign.py:CastleMissionStart.onCreate": tuple(
        "castle." + name + ".arrival" for name in MAP_NAMES
    ),
    "res/plugins/castle_campaign.py:CastleMissionStart.onTurn": tuple(
        "castle." + name + ".arrival" for name in MAP_NAMES
    ),
    "res/plugins/castle_campaign.py:CastleMissionStart.onEnter": tuple(
        "castle." + name + ".arrival" for name in MAP_NAMES
    ),
    "res/plugins/castle_campaign.py:CastleObjective.onEnter": tuple(
        branch for branch in castleBranches() if ".capture." in branch
    ),
    "res/plugins/castle_campaign.py:CastleTownRestDialog.configureTown": (
        "castle.town.rest",
        "castle.town.fullHealth",
        "castle.town.insufficientGold",
        "castle.town.locked",
    ),
    "res/plugins/castle_campaign.py:CastleTownRestDialog.canRest": (
        "castle.town.rest",
        "castle.town.fullHealth",
        "castle.town.insufficientGold",
    ),
    "res/plugins/castle_campaign.py:CastleTownRestDialog.rest": (
        "castle.town.rest",
        "castle.town.fullHealth",
        "castle.town.insufficientGold",
    ),
    "res/plugins/castle_campaign.py:CastleDefeatTrigger.trigger": tuple(
        branch for branch in castleBranches() if ".defender." in branch
    ),
    "res/plugins/castle_campaign.py:CastleOfficerTrigger.trigger": tuple(
        "castle." + name + ".officers" for name in MAP_NAMES
    ),
    "res/plugins/castle_campaign.py:CastlePortal.onCreate": tuple("castle." + name + ".arrival" for name in MAP_NAMES),
    "res/plugins/castle_campaign.py:CastlePortal.onTurn": tuple(
        branch for branch in castleBranches() if ".portal." in branch
    ),
    "res/plugins/castle_campaign.py:CastlePortal.onEnter": tuple(
        branch for branch in castleBranches() if ".portal." in branch
    ),
    "res/plugins/castle_campaign.py:CastleSupply.onEnter": tuple(
        branch for branch in castleBranches() if ".supply." in branch
    ),
}
for map_name, dialog in (
    ("castleHomecoming", "CastleHomecomingOfficerDialog"),
    ("castleGuardianAngels", "CastleGuardianAngelsOfficerDialog"),
    ("castleGriffinCliff", "CastleGriffinCliffOfficerDialog"),
):
    SOURCE_BRANCHES["res/maps/" + map_name + "/script.py:" + dialog + ".reportProgress"] = (
        "castle." + map_name + ".officers",
    )

DEFENSIVE_SOURCE_BRANCHES = {
    "res/maps/hearthfall/script.py:ElderDialog.victory_reported": "The victory action leaves this map immediately; retained-dialog contract only.",
    "res/maps/gravemoor/script.py:VossDialog.already_judged": "The judgment action leaves this map immediately; retained-dialog contract only.",
    "res/plugins/castle_campaign.py:CastlePortal.onDestroy": "Ordinary authored traversal retains connectors; destruction is a teardown contract.",
}

CAMPAIGN_BRANCHES = {
    "wardensRoad:homecoming:completed": ("wardens.hearthfallToGravemoor",),
    "wardensRoad:rescue:spared": ("wardens.route.assault_mercy",),
    "wardensRoad:rescue:executed": ("wardens.route.assault_wrath",),
    "wardensRoad:assault_mercy:completed": ("wardens.campaign.complete",),
    "wardensRoad:assault_wrath:completed": ("wardens.campaign.complete",),
    "longLiveTheQueen:homecoming:completed": ("castle.castleHomecoming.complete",),
    "longLiveTheQueen:guardianAngels:completed": ("castle.castleGuardianAngels.complete",),
    "longLiveTheQueen:griffinCliff:completed": ("castle.campaign.complete",),
    "fallOfNouraajd:cleansing:good_ending": ("ritual.resolution.good", "ritual.toSiege"),
    "fallOfNouraajd:cleansing:bad_ending": ("ritual.resolution.bad", "ritual.toSiege"),
    "fallOfNouraajd:siege:completed": ("siege.quest.complete",),
}
