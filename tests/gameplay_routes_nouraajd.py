# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Nouraajd branch routes using authored movement, encounters and earned stock."""

from functools import partial
import json

from tests.gameplay_branch_types import RouteCase
from tests.gameplay_branch_journals import verifyJournals

SOURCES = tuple(
    "res/maps/nouraajd/" + name
    for name in (
        "script.py",
        "config.json",
        "map.json",
        "dialog.json",
        "dialog2.json",
        "dialog3.json",
        "dialog4.json",
        "dialog5.json",
    )
) + ("res/plugins/octobogz_hunt.py", "res/narrative.py")
DEEDS = {
    "Warrior": (
        "nouraajdDoor",
        "doorDialog",
        "brace_gate",
        "can_brace_gate",
        "braced_nouraajd_gate",
        "warrior_barricades",
    ),
    "Assasin": (
        "nouraajdTavern",
        "tavernDialog1",
        "shadow_robed_men",
        "can_shadow_robed_men",
        "shadowed_robed_men",
        "assasin_trails",
    ),
    "Sorcerer": (
        "nouraajdChapel",
        "berenDialog",
        "decode_stained_glass_ward",
        "can_decode_stained_glass_ward",
        "decoded_stained_glass_ward",
        "sorcerer_sigils",
    ),
    "Inquisitor": (
        "nouraajdChapel",
        "berenDialog",
        "inspect_stained_glass",
        "can_inspect_stained_glass",
        "inspected_stained_glass",
        "inquisitor_clues",
    ),
    "Wayfarer": (
        "nouraajdTownHall",
        "townHallDialog",
        "chart_wayfarer_route",
        "can_chart_wayfarer_route",
        "charted_smuggler_route",
        "wayfarer_routes",
    ),
}
CHAIN_ORDERS = ("LRHB", "LRBH", "LBRH", "RLHB", "RLBH", "RBLH", "BLRH", "BRLH")
RACES = {
    "humanRace": ("HumanRation", 20, 0, 0),
    "outlanderRace": ("OutlanderRations", -5, 5, 5),
    "highlanderRace": ("HighlanderAid", -5, 10, 0),
    "wandererRace": ("WandererFocus", -5, 0, 10),
}


def start(d, *, gate="cooperative", deed=False):
    # Gate, confrontation and town recap choices belong to the real campaign store.
    d.startCampaign("fallOfNouraajd")
    d.hunt("collectAuthoredRetreatScroll")
    d.navigateTo("nouraajdDoor")
    if gate == "threatened":
        d.choose("doorDialog", "threatenGate")
        d.select("doorDialog", "NOT_WELCOME", 0)
    if deed and d.class_id == "Warrior":
        d.choose("doorDialog", "brace_gate", condition="can_brace_gate")
    else:
        d.choose("doorDialog", "open_door")
    d.select("doorDialog", "WARRIOR_GATE" if deed and d.class_id == "Warrior" else "WELCOME", 1)
    d.test.assertTrue(d.call(d.object("nouraajdDoor"), "getBoolProperty", "opened"))
    if deed and d.class_id != "Warrior":
        performDeed(d)


def performDeed(d):
    landmark, dialog, action, condition, flag, counter = DEEDS[d.class_id]
    d.navigateTo(landmark)
    d.test.assertTrue(d.condition(dialog, condition))
    before = d.call(d.player, "getNumericProperty", "exp")
    d.choose(dialog, action, condition=condition)
    state, option = {
        "Assasin": ("ASSASIN_TRAIL", 2),
        "Sorcerer": ("SORCERER_WARD", 0),
        "Inquisitor": ("STAINED_GLASS", 0),
        "Wayfarer": ("WAYFARER_ROUTE", 0),
    }[d.class_id]
    d.select(dialog, state, option)
    d.test.assertEqual(before + 750, d.call(d.player, "getNumericProperty", "exp"))
    d.test.assertTrue(d.call(d.player, "getBoolProperty", flag))
    d.test.assertEqual(1, d.call(d.player, "getNumericProperty", counter))
    d.test.assertFalse(d.condition(dialog, condition))


def prepareRolf(d):
    # Reuse the established adjacent combat/road-recovery route, not its full test fixture.
    # This helper deliberately does not enter the catacombs or accept a Beren letter.
    d.hunt("prepareThroughRolf")
    d.test.assertIn("rolfQuest", d.questNames(completed=True))
    d.test.assertEqual(1, d.count("skullOfRolf"))
    verifyJournals(d)


def clearHunt(d, *, reload_partial=False, retreat=False):
    d.hunt("prepareHealingStockAtAuthoredMarket")
    d.navigateTo("ambientOctobogzNet")
    d.hunt("recoverOnRoadPair", (118, 21, 0), (118, 20, 0), "before branch hunt")
    d.hunt("enterHunt")
    if reload_partial:
        state = d.string("octobogzHuntRegistry")
        d.saveAndReload("branch-hunt-scout-defeated")
        d.test.assertEqual(state, d.string("octobogzHuntRegistry"))
        d.hunt("trackLivingHuntActors")
    if retreat:
        d.hunt("retreatWithOwnedAuthoredScroll")
        d.hunt("prepareHealingStockAtAuthoredMarket", False)
    d.hunt("defeat", "alpha")
    d.hunt("recoverBeforeRemainingBrood", d.class_id)
    d.hunt("defeat", "brood")
    state = json.loads(d.string("octobogzHuntRegistry").removeprefix("octobogzHunt.v1:"))
    d.test.assertEqual("cleared", state["stage"])
    d.test.assertTrue(all(record["status"] == "dead" for record in state["slots"].values()))
    d.test.assertTrue(d.flag("OCTOBOGZ_SLAIN"))
    d.test.assertIsNone(d.object("cave2", required=False))


def gateRoute(d, approach):
    start(d, gate=approach)
    variable = "campaign_var_nouraajdGateApproach"
    d.check("nouraajd.gate." + approach, d.call(d.player, "getStringProperty", variable) == approach)
    d.revisit("nouraajdDoor")
    d.test.assertEqual(approach, d.call(d.player, "getStringProperty", variable))
    d.saveAndReload("gate-" + approach)
    d.check("nouraajd.gate." + approach + ".persisted", d.call(d.player, "getStringProperty", variable) == approach)
    d.navigateTo("nouraajdTavern")
    trade_before = len(d.tradeRequests())
    d.choose("tavernDialog1", "sell_beer")
    requests = d.tradeRequests()
    d.test.assertEqual(trade_before + 1, len(requests))
    expected = 105 if approach == "threatened" else 100
    d.check("nouraajd.beer." + approach, requests[-1]["sell"] == expected, tradeRequest=requests[-1])


def deedRoute(d):
    # The Warrior action must be witnessed before the ordinary gate opening consumes the visit.
    start(d, deed=d.class_id == "Warrior")
    if d.class_id != "Warrior":
        performDeed(d)
    _landmark, dialog, _action, condition, flag, counter = DEEDS[d.class_id]
    for class_id, (_place, other_dialog, _hook, other_condition, _flag, _counter) in DEEDS.items():
        if class_id != d.class_id:
            d.test.assertFalse(d.condition(other_dialog, other_condition))
    d.check("nouraajd.deed." + d.class_id, d.call(d.player, "getBoolProperty", flag))
    d.saveAndReload("class-deed-" + d.class_id)
    d.check(
        "nouraajd.deed." + d.class_id + ".persisted",
        d.call(d.player, "getNumericProperty", counter) == 1 and not d.condition(dialog, condition),
    )
    prepareRolf(d)
    d.hunt("finishOriginalMainQuest")
    d.check("nouraajd.deed." + d.class_id + ".ordinaryCombat", "mainQuest" in d.questNames(completed=True))


def letter(d):
    d.navigateTo("nouraajdTownHall")
    if not d.count("letterToBeren"):
        d.choose("townHallDialog", "give_letter")
        d.select("townHallDialog", "THANKS", 0)
    d.test.assertEqual(1, d.count("letterToBeren"))
    d.test.assertTrue(d.condition("townHallDialog", "has_letter_quest"))
    d.test.assertFalse(d.condition("townHallDialog", "can_offer_letter_work"))
    d.select("townHallDialog", "ENTRY", 4)
    d.select("townHallDialog", "ASK_HELP_REPEAT", 0)
    d.navigateTo("nouraajdChapel")
    d.choose("berenDialog", "deliver_letter", condition="can_deliver_letter")
    d.select("berenDialog", "LETTER_DELIVERED", 0)
    d.test.assertEqual(0, d.count("letterToBeren"))
    d.test.assertTrue(d.call(d.player, "getBoolProperty", "CAN_CRAFT_SCROLLS"))
    d.test.assertIn("deliverLetterQuest", d.questNames(completed=True))
    verifyJournals(d)


def relic(d):
    d.navigateTo("catacombs")
    d.test.assertIsNone(d.object("catacombs", required=False))
    d.test.assertEqual(1, d.count("holyRelic"))


def handInRelic(d):
    d.navigateTo("nouraajdChapel")
    d.choose("berenDialog", "return_relic", condition="can_return_relic")
    d.select("berenDialog", "RELIC_RETURNED", 0)
    d.test.assertEqual(0, d.count("holyRelic"))
    d.test.assertTrue(d.call(d.player, "getBoolProperty", "CAN_BREW_GREATER_POTIONS"))
    d.test.assertIn("retrieveRelicQuest", d.questNames(completed=True))
    verifyJournals(d)


def chainRoute(d, order, start_new=True, before_report=None):
    if start_new:
        start(d, deed=True)
        prepareRolf(d)
    d.navigateTo("nouraajdChapel")
    d.test.assertFalse(d.condition("berenDialog", "can_deliver_letter"))
    d.test.assertFalse(d.condition("berenDialog", "can_return_relic"))
    d.test.assertFalse(d.condition("berenDialog", "can_finish_cleanse"))
    completed = set()
    state = "letter_pending"
    for step in order:
        {"L": letter, "R": relic, "H": handInRelic, "B": clearHunt}[step](d)
        completed.add(step)
        if step == "L":
            state = (
                "octobogz_slain_no_relic"
                if "B" in completed
                else ("relic_obtained" if "R" in completed else "letter_delivered")
            )
        elif step == "R" and state == "letter_delivered":
            state = "relic_obtained"
        elif step == "H":
            state = "ready_to_report" if "B" in completed else "relic_returned_waiting_kill"
        elif step == "B":
            state = (
                "ready_to_report"
                if "H" in completed
                else ("octobogz_slain_no_relic" if "L" in completed else "octobogz_slain_pending_letter")
            )
        d.check(
            f"nouraajd.chain.{order}.{step}",
            d.string("quest_state_beren_chain") == state,
            state=d.string("quest_state_beren_chain"),
            relics=d.count("holyRelic"),
        )
    d.navigateTo("nouraajdChapel")
    d.test.assertEqual("ready_to_report", d.string("quest_state_beren_chain"))
    d.test.assertTrue(d.condition("berenDialog", "can_finish_cleanse"))
    if before_report:
        before_report(d)
        d.navigateTo("nouraajdChapel")
    d.saveAndReload("beren-ready-" + order)
    verifyJournals(d)
    d.choose("berenDialog", "finish_cleanse", condition="can_finish_cleanse")
    d.check(
        f"nouraajd.chain.{order}.ritual", d.map_name == "ritual" and "cleanseCaveQuest" in d.questNames(completed=True)
    )
    verifyJournals(d)


def contractRoute(d, early):
    start(d, deed=True)
    prepareRolf(d)
    d.navigateTo("questGiver")
    d.test.assertTrue(d.condition("dialog", "contract_not_started"))
    d.select("dialog", "ENTRY", 0)
    d.select("dialog", "ASK_WHY", 1)
    d.select("dialog", "OFFER_HELP", 1)
    d.select("dialog", "DECLINE_QUEST", 0)
    d.test.assertNotIn("octoBogzQuest", d.questNames())
    if early:
        d.choose("dialog", "accept_quest", condition="contract_not_started")
        d.select("dialog", "ACCEPT_QUEST", 0)
        d.test.assertTrue(d.condition("dialog", "contract_active"))
        d.select("dialog", "ENTRY", 2)
        d.select("dialog", "ACTIVE_REMINDER", 0)
    before_blades = d.count("ShadowBlade")
    clearHunt(d, reload_partial=True, retreat=True)
    d.navigateTo("questGiver")
    before_claim = d.gold()
    d.choose("dialog", "accept_quest", condition="contract_completed")
    d.select("dialog", "COMPLETED_THANKS", 0)
    d.check(
        "nouraajd.contract." + ("early" if early else "late"),
        d.gold() == before_claim + (0 if early else 1000)
        and d.count("ShadowBlade") == before_blades + 1
        and "octoBogzQuest" in d.questNames(completed=True),
    )
    paid = d.gold()
    d.choose("dialog", "accept_quest", condition="contract_completed")
    d.select("dialog", "COMPLETED_THANKS", 0)
    d.check("nouraajd.contract.rewardOnce", d.gold() == paid and d.count("ShadowBlade") == before_blades + 1)
    d.check("nouraajd.hunt.partialReloadAndRetreat", d.flag("octobogzHuntCleared"))
    blade = next(item for item in d.call(d.player, "getItems") if d.call(item, "getTypeId") == "ShadowBlade")
    old_weapon = d.call(d.player, "getItemAtSlot", "0")
    old_type = d.call(old_weapon, "getTypeId") if old_weapon else None
    d.call(d.player, "equipItem", "0", blade)
    d.test.assertEqual(blade["__handle__"], d.call(d.player, "getItemAtSlot", "0")["__handle__"])
    d.test.assertEqual(blade["__handle__"], d.call(d.player, "getEquipped")["0"]["__handle__"])
    if old_weapon:
        d.test.assertIn(old_weapon["__handle__"], {item["__handle__"] for item in d.call(d.player, "getItems")})
    d.saveAndReload("earned-shadow-blade-equipped")
    equipped = d.call(d.player, "getItemAtSlot", "0")
    d.check("nouraajd.contract.equipment", d.call(equipped, "getTypeId") == "ShadowBlade" and d.gold() == paid)
    if old_type:
        d.test.assertGreaterEqual(d.count(old_type), 1)


def amuletRoute(d):
    start(d, deed=True)
    prepareRolf(d)
    d.navigateTo("oldWoman")
    d.select("questDialog", "ENTRY", 0)
    d.select("questDialog", "OLD_WOMAN_HELLO", 1)
    d.select("questDialog", "DECLINE_QUEST", 0)
    d.check("nouraajd.amulet.declined", d.string("quest_state_amulet") == "not_started")
    d.choose("questDialog", "start_amulet_quest")
    d.select("questDialog", "ACCEPT_QUEST", 0)
    d.check("nouraajd.amulet.accepted", d.string("quest_state_amulet") == "active")
    d.revisit("oldWoman")
    d.test.assertEqual(0, d.count("preciousAmulet"))
    d.check("nouraajd.amulet.reminder", "amuletQuest" in d.questNames())
    d.saveAndReload("amulet-active")
    d.fight("amuletGoblin")
    d.check("nouraajd.amulet.realLoot", d.count("preciousAmulet") == 1)
    d.navigateTo("oldWoman")
    gold = d.gold()
    d.choose("questReturnDialog", "complete_amulet_quest")
    d.check(
        "nouraajd.amulet.returned",
        d.gold() == gold + 50 and d.count("preciousAmulet") == 0 and "amuletQuest" in d.questNames(completed=True),
    )
    d.test.assertIsNone(d.object("oldWoman", required=False))
    d.saveAndReload("amulet-returned")
    d.check("nouraajd.amulet.persisted", d.gold() == gold + 50 and d.string("quest_state_amulet") == "returned")


def meetVictor(d, approach, direct, *, ask_girl=True, start_encounter=True):
    d.navigateTo("nouraajdTavern")
    if ask_girl:
        d.choose("tavernDialog1", "asked_about_girl")
        d.select("tavernDialog1", "INKEEPER_ABOUT_GIRL", 2)
    d.revisit("nouraajdTavern")
    tavern = d.object("nouraajdTavern")
    opened = d.call(tavern, "getNumericProperty", "time_visited")
    while d.call(d.game_map, "getTurn") - opened <= 50:
        d.tick()
    d.revisit("nouraajdTavern")
    d.choose("tavernDialog2", "confrontVictorForcefully" if approach == "forceful" else "calmVictor")
    state = "PUNCHED_VICTOR" if approach == "forceful" else "YELLED_AT_VICTOR"
    d.choose("tavernDialog2", "talked_to_victor", state_id=state)
    d.test.assertTrue(d.flag("TALKED_TO_VICTOR"))
    d.test.assertEqual(ask_girl, d.condition("tavernDialog2", "asked_about_girl"))
    if not start_encounter:
        d.select("tavernDialog2", "VICTOR_SPEECH", 1 if ask_girl else 0)
        if not ask_girl:
            d.select("tavernDialog2", "VICTOR_CLUE", 1)
        d.select("tavernDialog2", "SUGGEST_TOWN_HALL", 0)
        return
    if direct:
        d.select("tavernDialog2", "VICTOR_SPEECH", 0)
        d.select("tavernDialog2", "VICTOR_CLUE", 0)
        d.choose("tavernDialog2", "spawn_cultists", state_id="COURTYARD_PATH")
    else:
        d.select("tavernDialog2", "VICTOR_SPEECH", 1 if ask_girl else 0)
        if not ask_girl:
            d.select("tavernDialog2", "VICTOR_CLUE", 1)
        d.select("tavernDialog2", "SUGGEST_TOWN_HALL", 0)
        d.navigateTo("nouraajdTownHall")
        d.test.assertTrue(d.condition("townHallDialog", "can_discuss_victor_records"))
        d.choose("townHallDialog", "spawn_cultists")
    d.test.assertEqual("encounter_active", d.string("quest_state_victor"))


def victorCountdownCheckpoint(d, label, credit=False):
    names = ("cultLeaderQuest", *("victorCultist" + str(index) for index in range(1, 5)))

    def snapshot():
        actors = {}
        for name in names:
            actor = d.object(name, required=False)
            if actor:
                actors[name] = (d.call(actor, "getTypeId"), d.coords(actor), d.call(actor, "getHp"))
        return (
            d.string("quest_state_victor"),
            d.number("VICTOR_COURTYARD_TURN"),
            d.call(d.game_map, "getTurn"),
            actors,
        )

    before = snapshot()
    d.test.assertEqual("encounter_active", before[0])
    d.test.assertIn("cultLeaderQuest", before[3])
    d.saveAndReload(label)
    after = snapshot()
    d.test.assertEqual(before, after, "Reload must retain actual actors and the original native deadline")
    if credit:
        d.check(
            "nouraajd.victor.countdownPersisted",
            before == after,
            spawnTurn=after[1],
            mapTurn=after[2],
            actorNames=tuple(after[3]),
        )


def fleeCourtyardUntil(d, elapsed, allow_timeout=False):
    # Keep moving through actual walkable edges so pursuing cultists cannot turn
    # an intended timeout into an automatic combat rescue while the hero waits.
    spawn_turn = d.number("VICTOR_COURTYARD_TURN")
    previous = None
    while d.call(d.game_map, "getTurn") - spawn_turn < elapsed:
        origin = d.coords()
        actors = [
            d.object(name, required=False)
            for name in ("cultLeaderQuest", *("victorCultist" + str(index) for index in range(1, 5)))
        ]
        opponents = [d.coords(actor) for actor in actors if actor]
        d.test.assertTrue(opponents, "The real timed encounter must remain present while fleeing")
        candidates = []
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            target = (origin[0] + dx, origin[1] + dy, origin[2])
            if not d.canStep(target):
                continue
            distance = min(sum(abs(a - b) for a, b in zip(target, enemy)) for enemy in opponents)
            if distance > 1:
                candidates.append((distance, target != previous, abs(target[0] - 45) + abs(target[1] - 100), target))
        d.test.assertTrue(candidates, ("No natural escape step remains", origin, opponents))
        target = max(candidates)[-1]
        d.step(target)
        previous = origin
        expected = (
            "bad_end" if allow_timeout and d.call(d.game_map, "getTurn") - spawn_turn >= 75 else "encounter_active"
        )
        d.test.assertEqual(expected, d.string("quest_state_victor"))


def victorRoute(d, approach, direct, saved, start_new=True, ask_girl=True):
    if start_new:
        start(d, deed=ask_girl)
        prepareRolf(d)
    meetVictor(d, approach, direct, ask_girl=ask_girl)
    victorCountdownCheckpoint(d, "victor-active-countdown", credit=True)
    d.check(
        "nouraajd.victor.approach." + approach,
        d.call(d.player, "getStringProperty", "campaign_var_nouraajdVictorConfrontation") == approach,
    )
    d.check(
        "nouraajd.victor.entry." + ("courtyard" if direct else "records"),
        d.object("cultLeaderQuest", required=False) is not None,
    )
    if saved:
        d.fight("cultLeaderQuest")
        d.check(
            "nouraajd.victor.rescued", d.string("quest_state_victor") == "good_end" and d.flag("VICTOR_REWARD_GRANTED")
        )
        d.test.assertIn("victorQuest", d.questNames(completed=True))
    else:
        fleeCourtyardUntil(d, 74)
        victorCountdownCheckpoint(d, "victor-one-turn-before-deadline")
        d.check("nouraajd.victor.activeBeforeDeadline", d.string("quest_state_victor") == "encounter_active")
        gold = d.gold()
        fleeCourtyardUntil(d, 75, allow_timeout=True)
        d.check(
            "nouraajd.victor.lostAtDeadline",
            d.string("quest_state_victor") == "bad_end" and not d.flag("VICTOR_REWARD_GRANTED") and d.gold() == gold,
        )
        d.test.assertIsNone(d.object("cultLeaderQuest", required=False))
    gold = d.gold()
    d.navigateTo("nouraajdTownHall")
    condition = "victor_good_end" if saved else "victor_bad_end"
    d.test.assertTrue(d.condition("townHallDialog", condition))
    d.test.assertFalse(d.condition("townHallDialog", "can_discuss_victor_records"))
    d.saveAndReload("victor-" + ("rescued" if saved else "lost"))
    d.check("nouraajd.victor.endingPersisted", d.gold() == gold and d.condition("townHallDialog", condition))
    verifyJournals(d)


def campaignRoute(d, outcome):
    from tests.gameplay_routes_campaigns import finishRitualAndSiege

    saved = outcome == "good"
    approach = "deescalated" if saved else "forceful"
    gate = "cooperative" if saved else "threatened"
    start(d, gate=gate, deed=True)
    prepareRolf(d)
    d.hunt("finishOriginalMainQuest")
    victorRoute(d, approach, direct=not saved, saved=saved, start_new=False)
    chainRoute(d, "LRHB", start_new=False)
    d.check(
        "nouraajd.campaign.toRitual",
        d.map_name == "ritual" and d.call(d.player, "getStringProperty", "campaign_history") == "recovery:completed",
    )
    finishRitualAndSiege(d, outcome, activation="anchor" if saved else "threshold")
    expected = "recovery:completed,cleansing:" + ("good_ending" if saved else "bad_ending") + ",siege:completed"
    d.check(
        "nouraajd.campaign." + outcome,
        d.call(d.player, "getBoolProperty", "campaign_finished")
        and d.call(d.player, "getStringProperty", "campaign_history") == expected
        and d.call(d.player, "getStringProperty", "campaign_var_nouraajdGateApproach") == gate
        and d.call(d.player, "getStringProperty", "campaign_var_nouraajdVictorConfrontation") == approach
        and d.call(d.player, "getStringProperty", "campaign_var_nouraajdVictorOutcome")
        == ("rescued" if saved else "lost")
        and d.call(d.player, "getStringProperty", "nouraajdVictorState") == ("good_end" if saved else "bad_end"),
    )
    d.saveAndReload("nouraajd-campaign-" + outcome)
    d.check("nouraajd.campaign.persisted", d.call(d.player, "getStringProperty", "campaign_history") == expected)


def townSnapshotRoute(d, unresolved):
    start(d)
    prepareRolf(d)
    hook = partial(meetVictor, approach="deescalated", direct=False, ask_girl=False, start_encounter=False)
    chainRoute(d, "LRHB", start_new=False, before_report=hook if unresolved else None)
    outcome = "unresolved" if unresolved else "notAttempted"
    d.check(
        "nouraajd.snapshot." + outcome,
        d.call(d.player, "getStringProperty", "campaign_var_nouraajdVictorOutcome") == outcome,
    )
    d.check(
        "nouraajd.snapshot.noDeed", d.call(d.player, "getStringProperty", "campaign_var_nouraajdClassDeed") == "none"
    )


def tavernTimingRoute(d):
    start(d)
    d.navigateTo("nouraajdTavern")
    tavern = d.object("nouraajdTavern")
    opened = d.call(tavern, "getNumericProperty", "time_visited")
    d.test.assertEqual(1, d.call(tavern, "getNumericProperty", "visited"))
    while d.call(d.game_map, "getTurn") - opened < 48:
        d.tick()
    d.revisit("nouraajdTavern")
    d.check(
        "nouraajd.victor.tavern.atFifty",
        d.call(d.game_map, "getTurn") - opened == 50 and d.call(tavern, "getNumericProperty", "visited") == 1,
    )
    d.revisit("nouraajdTavern")
    d.check("nouraajd.victor.tavern.afterFifty", d.call(tavern, "getNumericProperty", "visited") == 2)


def aidSnapshot(d):
    return tuple(d.call(d.player, name) for name in ("getGold", "getHp", "getMana"))


def raceAid(d):
    start(d)
    suffix, gold_delta, hp_gain, mana_gain = RACES[d.race_id]
    d.navigateTo("nouraajdTownHall")
    for race_id, (other_suffix, *_rest) in RACES.items():
        d.test.assertEqual(race_id == d.race_id, d.condition("townHallDialog", "canOffer" + other_suffix))
    if d.race_id != "humanRace":
        d.test.assertLess(d.gold(), 5, "The fresh authored player must reach the unfunded aid branch")
        before = aidSnapshot(d)
        d.choose("townHallDialog", "claim" + suffix, condition="canOffer" + suffix)
        d.check(
            "nouraajd.aid." + d.race_id + ".unfunded",
            aidSnapshot(d) == before and not d.call(d.player, "getBoolProperty", "nouraajdRaceServiceClaimed"),
        )
        prepareRolf(d)
        d.hunt("recoverOnRoadPair", (44, 106, 0), (44, 107, 0), "race aid full resources")
        d.navigateTo("nouraajdTownHall")
        d.test.assertGreaterEqual(d.gold(), 5)
        d.test.assertEqual(d.call(d.player, "getHpMax"), d.call(d.player, "getHp"))
        d.test.assertEqual(d.call(d.player, "getManaMax"), d.call(d.player, "getMana"))
        before = aidSnapshot(d)
        d.choose("townHallDialog", "claim" + suffix, condition="canOffer" + suffix)
        d.check(
            "nouraajd.aid." + d.race_id + ".unneeded",
            aidSnapshot(d) == before and not d.call(d.player, "getBoolProperty", "nouraajdRaceServiceClaimed"),
        )
        # Actual courtyard opponents supply damage; an owned paid action supplies mana expenditure.
        d.recoveryEnabled = False
        try:
            meetVictor(d, "deescalated", False)
            actions = [
                action
                for action in d.call(d.player, "getEffectiveInteractions")
                if 0 < d.call(action, "getNumericProperty", "manaCost") <= d.call(d.player, "getMana")
            ]
            d.test.assertTrue(actions, "Paid aid route needs an actual affordable owned class ability")
            enemy = d.object("victorCultist1")
            action = actions[0]
            target = d.player if d.call(action, "getBoolProperty", "selfTarget") else enemy
            d.call(d.player, "useAction", action, target)
            d.pump()
            for name in ("victorCultist1", "victorCultist2", "victorCultist3", "victorCultist4"):
                if hp_gain and d.call(d.player, "getHp") == d.call(d.player, "getHpMax"):
                    if d.object(name, required=False):
                        d.fight(name)
            d.navigateTo("nouraajdTownHall")
            before = aidSnapshot(d)
            hp_max = d.call(d.player, "getHpMax")
            mana_max = d.call(d.player, "getManaMax")
            expected = (before[0] + gold_delta, min(hp_max, before[1] + hp_gain), min(mana_max, before[2] + mana_gain))
            d.test.assertNotEqual(before[1:], expected[1:], "Real combat/casting must leave a recoverable deficit")
            d.choose("townHallDialog", "claim" + suffix, condition="canOffer" + suffix)
            d.test.assertEqual(expected, aidSnapshot(d))
        finally:
            d.recoveryEnabled = True
    else:
        before = aidSnapshot(d)
        d.choose("townHallDialog", "claimHumanRation", condition="canOfferHumanRation")
        d.test.assertEqual((before[0] + 20, before[1], before[2]), aidSnapshot(d))
    d.check("nouraajd.aid." + d.race_id + ".claimed", d.call(d.player, "getBoolProperty", "nouraajdRaceServiceClaimed"))
    after = aidSnapshot(d)
    d.revisit("nouraajdTownHall")
    d.test.assertFalse(d.condition("townHallDialog", "canOffer" + suffix))
    d.test.assertEqual(after[0], d.gold())
    d.saveAndReload("racial-aid-" + d.race_id)
    d.check(
        "nouraajd.aid." + d.race_id + ".persisted",
        not d.condition("townHallDialog", "canOffer" + suffix)
        and d.call(d.player, "getStringProperty", "nouraajdRaceServiceKind") == d.race_id,
    )


def case(case_id, branches, run, **kwargs):
    return RouteCase(
        case_id, "nouraajd", ("nouraajd",), tuple(branches), run, campaign="fallOfNouraajd", sources=SOURCES, **kwargs
    )


def campaignBranches(outcome):
    from tests.gameplay_routes_campaigns import RITUAL_BAD_BRANCHES, RITUAL_GOOD_BRANCHES

    saved = outcome == "good"
    return (
        "nouraajd.victor.countdownPersisted",
        "nouraajd.victor.approach." + ("deescalated" if saved else "forceful"),
        "nouraajd.victor.entry." + ("records" if saved else "courtyard"),
        *(
            ("nouraajd.victor.rescued",)
            if saved
            else ("nouraajd.victor.activeBeforeDeadline", "nouraajd.victor.lostAtDeadline")
        ),
        "nouraajd.victor.endingPersisted",
        *(f"nouraajd.chain.LRHB.{step}" for step in "LRHB"),
        "nouraajd.chain.LRHB.ritual",
        "nouraajd.campaign.toRitual",
        "nouraajd.campaign." + outcome,
        "nouraajd.campaign.persisted",
        *(RITUAL_GOOD_BRANCHES if saved else RITUAL_BAD_BRANCHES),
    )


CASES = (
    *(
        case(
            "nouraajd_gate_" + approach,
            ("nouraajd.gate." + approach, "nouraajd.gate." + approach + ".persisted", "nouraajd.beer." + approach),
            partial(gateRoute, approach=approach),
        )
        for approach in ("cooperative", "threatened")
    ),
    *(
        case(
            "nouraajd_deed_" + class_id,
            (
                "nouraajd.deed." + class_id,
                "nouraajd.deed." + class_id + ".persisted",
                "nouraajd.deed." + class_id + ".ordinaryCombat",
            ),
            deedRoute,
            classes=(class_id,),
        )
        for class_id in DEEDS
    ),
    *(
        RouteCase(
            "nouraajd_chain_" + order,
            "nouraajd",
            ("nouraajd", "ritual"),
            tuple(f"nouraajd.chain.{order}.{step}" for step in order) + (f"nouraajd.chain.{order}.ritual",),
            partial(chainRoute, order=order),
            campaign="fallOfNouraajd",
            sources=SOURCES,
            duration_seconds=1200.0,
        )
        for order in CHAIN_ORDERS
    ),
    *(
        case(
            "nouraajd_contract_" + ("early" if early else "late"),
            (
                "nouraajd.contract." + ("early" if early else "late"),
                "nouraajd.contract.rewardOnce",
                "nouraajd.contract.equipment",
                "nouraajd.hunt.partialReloadAndRetreat",
            ),
            partial(contractRoute, early=early),
            duration_seconds=1200.0,
        )
        for early in (True, False)
    ),
    case(
        "nouraajd_amulet",
        tuple(
            "nouraajd.amulet." + state
            for state in ("declined", "accepted", "reminder", "realLoot", "returned", "persisted")
        ),
        amuletRoute,
        duration_seconds=600.0,
    ),
    *(
        case(
            f"nouraajd_victor_{approach}_{'courtyard' if direct else 'records'}_{'saved' if saved else 'lost'}",
            (
                "nouraajd.victor.approach." + approach,
                "nouraajd.victor.entry." + ("courtyard" if direct else "records"),
                "nouraajd.victor.countdownPersisted",
                *(
                    ("nouraajd.victor.rescued",)
                    if saved
                    else ("nouraajd.victor.activeBeforeDeadline", "nouraajd.victor.lostAtDeadline")
                ),
                "nouraajd.victor.endingPersisted",
            ),
            partial(victorRoute, approach=approach, direct=direct, saved=saved),
            duration_seconds=600.0,
        )
        for approach in ("forceful", "deescalated")
        for direct in (False, True)
        for saved in (False, True)
    ),
    *(
        case(
            "nouraajd_aid_" + race_id,
            (
                ("nouraajd.aid." + race_id + ".unfunded", "nouraajd.aid." + race_id + ".unneeded")
                if race_id != "humanRace"
                else ()
            )
            + ("nouraajd.aid." + race_id + ".claimed", "nouraajd.aid." + race_id + ".persisted"),
            raceAid,
            race=race_id,
            duration_seconds=600.0,
        )
        for race_id in RACES
    ),
    *(
        RouteCase(
            "nouraajd_campaign_" + outcome,
            "campaigns",
            ("nouraajd", "ritual", "siege"),
            campaignBranches(outcome),
            partial(campaignRoute, outcome=outcome),
            campaign="fallOfNouraajd",
            sources=SOURCES + ("res/campaigns/fallOfNouraajd/campaign.json",),
            duration_seconds=2400.0,
        )
        for outcome in ("good", "bad")
    ),
    *(
        RouteCase(
            "nouraajd_snapshot_" + outcome,
            "nouraajd",
            ("nouraajd", "ritual"),
            tuple(f"nouraajd.chain.LRHB.{step}" for step in "LRHB")
            + ("nouraajd.chain.LRHB.ritual", "nouraajd.snapshot." + outcome, "nouraajd.snapshot.noDeed"),
            partial(townSnapshotRoute, unresolved=outcome == "unresolved"),
            campaign="fallOfNouraajd",
            sources=SOURCES,
            duration_seconds=1200.0,
        )
        for outcome in ("notAttempted", "unresolved")
    ),
    case(
        "nouraajd_tavern_timing",
        ("nouraajd.victor.tavern.atFifty", "nouraajd.victor.tavern.afterFifty"),
        tavernTimingRoute,
    ),
    *(
        case(
            "nouraajd_victor_without_girl_clue_" + approach,
            (
                "nouraajd.victor.approach." + approach,
                "nouraajd.victor.entry.records",
                "nouraajd.victor.countdownPersisted",
                "nouraajd.victor.rescued",
                "nouraajd.victor.endingPersisted",
            ),
            partial(victorRoute, approach=approach, direct=False, saved=True, ask_girl=False),
            duration_seconds=600.0,
        )
        for approach in ("forceful", "deescalated")
    ),
)
