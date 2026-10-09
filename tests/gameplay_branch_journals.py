# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only journal witnesses taken from the actual active and completed quests."""

from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def questSpecs():
    result = {}
    for path in sorted((ROOT / "res/maps").glob("*/config.json")):
        for quest_id, value in json.loads(path.read_text(encoding="utf-8")).items():
            if not isinstance(value, dict) or not value.get("class", "").endswith("Quest"):
                continue
            properties = value.get("properties", {})
            if "description" in properties:
                result[quest_id] = {
                    "origin": path.parent.name,
                    "description": properties["description"],
                    "source": path.relative_to(ROOT).as_posix(),
                }
    return result


def rememberJournalContext(d, *, source_map=None, map_name=None):
    """Remember observed source state before its real map transition loses the map handle."""
    context = getattr(d, "_journal_source_context", {})
    observed_map = d.map_name if map_name is None else map_name

    def read(kind, name):
        if source_map is not None:
            return d.call(source_map, "get" + kind + "Property", name)
        return {"Bool": d.flag, "Numeric": d.number, "String": d.string}[kind](name)

    if observed_map == "ritual":
        context["ritual"] = {
            "lost": read("Bool", "captive_lost"),
            "anchors": read("Numeric", "anchors_destroyed_count"),
        }
    elif observed_map == "gravemoor":
        context["gravemoor"] = {"judged": read("Bool", "voss_judged"), "spared": read("Bool", "voss_spared")}
    elif observed_map == "nouraajd":
        context["nouraajd"] = {"victor": read("String", "quest_state_victor")}
    d._journal_source_context = context
    return context


COMPLETED_OBJECTIVES = {
    "mainQuest": ("slay Gooby",),
    "rolfQuest": ("Sergeant Rolf's skull",),
    "deliverLetterQuest": ("sealed letter", "Beren"),
    "retrieveRelicQuest": ("holy relic", "Beren"),
    "cleanseCaveQuest": ("holy relic", "OctoBogz"),
    "amuletQuest": ("stolen amulet", "goblin thief"),
    "octoBogzQuest": ("3/3 threats slain",),
    "haldaQuest": ("Halda", "has joined"),
    "morriganeQuest": ("Morrigane", "has joined"),
    "corvynQuest": ("Corvyn", "has joined"),
    "ninemarchesQuest": ("Crowned God is down", "quiet at last"),
    "hearthfallQuest": ("Hearthfall is free", "Gravemoor"),
    "usurpergateQuest": ("Wardenskeep is yours", "Warden again"),
    "ritualQuest": ("Reach the captive", "chapel's fate"),
    "destroyAnchorsQuest": ("3/3 destroyed",),
    "finalResolutionQuest": ("rescue or a warning",),
    "defendSiegeQuest": ("4/4 sealed",),
    "drownedTitheQuest": ("carry the Tiara", "deep knows your name"),
    "kadathAscentQuest": ("wear the Onyx Signet", "not release you unmarked"),
    "sunderedMarchQuest": ("Crown of the Barrow-Warlord is yours", "king is down"),
    "seerHuntQuest": ("has her banner", "have her boon"),
}


def containsAll(test, text, fragments, quest_id, field):
    for fragment in fragments:
        test.assertIn(fragment.casefold(), text.casefold(), (quest_id, field, fragment, text))


def assertOutcomeText(d, record, context):
    quest_id, completed = record["id"], record["completed"]
    objective, reward = record["objective"], record["reward"]
    history = d.call(d.player, "getStringProperty", "campaign_history")
    on_source = d.map_name == record["origin"]
    if completed and quest_id in COMPLETED_OBJECTIVES:
        containsAll(d.test, objective, COMPLETED_OBJECTIVES[quest_id], quest_id, "objective")
    if completed and quest_id.startswith("castle"):
        containsAll(d.test, objective, (record["description"], "Completed."), quest_id, "objective")
    if quest_id == "victorQuest":
        state = (
            d.string("quest_state_victor")
            if on_source
            else (d.call(d.player, "getStringProperty", "nouraajdVictorState"))
        )
        if completed:
            d.test.assertIn(state, ("good_end", "bad_end"), "Completed Victor journal lost its observed outcome")
        if state == "good_end":
            containsAll(d.test, objective, ("daughter survived",), quest_id, "objective")
            containsAll(d.test, reward, ("500 gold",), quest_id, "reward")
        elif state == "bad_end":
            containsAll(d.test, objective, ("daughter was taken",), quest_id, "objective")
            containsAll(d.test, reward, ("No reward",), quest_id, "reward")
        elif state == "encounter_active":
            containsAll(d.test, objective, ("cult leader", "before", "daughter is taken"), quest_id, "objective")
        elif state in ("met_victor", "records_reviewed", "courtyard_known"):
            containsAll(d.test, objective, ("Victor's clue", "courtyard"), quest_id, "objective")
    elif quest_id == "gravemoorQuest" and completed:
        if "rescue:spared" in history:
            spared = True
        elif "rescue:executed" in history:
            spared = False
        else:
            observed = context.get("gravemoor", {})
            d.test.assertTrue(observed.get("judged"), "Voss journal needs observed judgment before departure")
            spared = observed["spared"]
        containsAll(d.test, objective, ("Voss lives" if spared else "moor keeps the traitor",), quest_id, "objective")
    elif quest_id == "rescueCaptiveQuest":
        if "cleansing:bad_ending" in history:
            lost = True
        elif "cleansing:good_ending" in history:
            lost = False
        elif on_source:
            lost = d.flag("captive_lost")
        else:
            d.test.assertIn("ritual", context, "Off-map captive journal needs a real source-state observation")
            lost = context["ritual"]["lost"]
        containsAll(d.test, objective, ("captive was lost" if lost else "Free the captive",), quest_id, "objective")
        containsAll(d.test, reward, ("100 gold" if lost else "300 gold",), quest_id, "reward")
    elif quest_id == "defendSiegeQuest":
        gate = d.call(d.player, "getStringProperty", "campaign_var_nouraajdGateApproach")
        containsAll(d.test, reward, ("475 gold" if gate == "threatened" else "500 gold",), quest_id, "reward")
    elif quest_id == "ninemarchesQuest" and on_source and not completed:
        if d.flag("crown_taken"):
            fragments = ("Ninefold Crown", "put down the Ninefold King")
        elif d.number("obelisks_read") >= 6:
            fragments = ("All six obelisks", "Dig the grave-crown")
        elif d.number("chapter") >= 2:
            fragments = (f"{int(d.number('obelisks_read'))}/6 read",)
        else:
            fragments = ("Chapter I", "iron march-key")
        containsAll(d.test, objective, fragments, quest_id, "objective")
    elif quest_id == "destroyAnchorsQuest" and on_source and not completed:
        containsAll(
            d.test, objective, (f"{int(d.number('anchors_destroyed_count'))}/3 destroyed",), quest_id, "objective"
        )


def verifyJournals(d):
    """Assert text from live quest handles and return stable metadata for the receipt."""
    context = rememberJournalContext(d)
    specs = questSpecs()
    records = {}
    completed_snapshots = getattr(d, "_journal_completed_snapshots", {})
    for completed, getter in ((False, "getQuests"), (True, "getCompletedQuests")):
        for quest in d.call(d.player, getter):
            name, type_id = d.call(quest, "getName"), d.call(quest, "getTypeId")
            d.test.assertTrue(isinstance(name, str) and name.strip(), "Journal quest name must be nonempty")
            d.test.assertTrue(isinstance(type_id, str) and type_id.strip(), "Journal quest type must be nonempty")
            quest_id = type_id if type_id in specs else name
            d.test.assertIn(quest_id, specs, "Authored quest needs a reviewed journal expectation")
            d.test.assertNotIn(quest_id, records, "Quest must occur exactly once across active and completed journals")
            record = {"id": quest_id, "name": name, "type": type_id, "completed": completed, **specs[quest_id]}
            for field in ("description", "objective", "reward", "hint"):
                value = d.call(quest, "get" + field.capitalize())
                d.test.assertTrue(isinstance(value, str) and value.strip(), (quest_id, "empty journal " + field))
                d.test.assertNotIn("unavailable", value.casefold(), (quest_id, "unexpected legacy neutral text", value))
                if field == "description":
                    d.test.assertEqual(specs[quest_id]["description"], value)
                record[field] = value
            version = d.call(quest, "getNumericProperty", "questJournalVersion")
            origin = d.call(quest, "getStringProperty", "questJournalOrigin")
            if completed or d.map_name != record["origin"]:
                d.test.assertEqual(1, version, (quest_id, "missing captured journal"))
                d.test.assertEqual(record["origin"], origin)
                d.test.assertEqual(completed, d.call(quest, "getBoolProperty", "questJournalCompleted"))
                for field in ("objective", "reward", "hint"):
                    captured = d.call(quest, "getStringProperty", "questJournal" + field.capitalize())
                    d.test.assertEqual(record[field], captured, (quest_id, "off-map journal changed", field))
            assertOutcomeText(d, record, context)
            if completed:
                if quest_id in completed_snapshots:
                    d.test.assertEqual(
                        completed_snapshots[quest_id], record, "Completed history changed after progression/reload"
                    )
                completed_snapshots[quest_id] = dict(record)
            records[quest_id] = record
    d._journal_completed_snapshots = completed_snapshots
    observations = getattr(d, "_journal_observations", [])
    observations.append({"map": d.map_name, "quests": records})
    d._journal_observations = observations
    return records
