# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exact authored-station recipe witnesses; outcome expectations never authorize retries."""

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path

from tests.gameplay_routes_services import visitService

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def recipeDefinitions():
    return json.loads((ROOT / "res/config/crafting.json").read_text(encoding="utf-8"))


def inventoryTypes(d):
    return {item["__handle__"]: d.call(item, "getTypeId") for item in d.call(d.player, "getItems")}


def craftContext(d):
    return {
        "world": d.game_map["__handle__"],
        "player": d.player["__handle__"],
        "coords": d.coords(),
        "turn": d.call(d.game_map, "getTurn"),
        "hp": d.call(d.player, "getHp"),
        "mana": d.call(d.player, "getMana"),
        "exp": d.call(d.player, "getNumericProperty", "exp"),
        "quests": tuple(sorted(d.questNames())),
        "completedQuests": tuple(sorted(d.questNames(completed=True))),
        "equipped": {
            slot: item["__handle__"] if item else None for slot, item in d.call(d.player, "getEquipped").items()
        },
    }


def openStation(d, name, branch=None, *, navigate=None):
    requests = visitService(d, name, "choice_requested", navigate=navigate)
    station = d.object(name)
    d.test.assertEqual("CraftingStation", d.call(station, "getType"))
    d.test.assertTrue(d.call(station, "getBoolProperty", "enabled"))
    station_id = d.call(station, "getStringProperty", "craftingStationId")
    label = d.call(station, "getStringProperty", "label") or station_id
    matching = [request for request in requests if request.get("title") == label]
    d.test.assertEqual(1, len(matching), ("Authored station must request its actual chooser", name))
    request = matching[0]
    payload = request.get("choicesJson", "")
    d.test.assertEqual(len(payload.encode("utf-8")), request.get("choicesJsonLength"), "Choice payload was truncated")
    choices = tuple(json.loads(payload))
    expected = {identity for identity, recipe in recipeDefinitions().items() if recipe["station"] == station_id}
    d.test.assertEqual(expected, {choice["id"] for choice in choices})
    d.test.assertEqual(len(expected), len(choices), "A recipe must appear exactly once")
    d.test.assertTrue(request.get("headless") is True)
    d.test.assertEqual("Craft", request.get("actionLabel"))
    d.test.assertEqual("Leave station", request.get("backLabel"))
    d.test.assertEqual(dict(zip("xyz", d.coords())), request.get("playerCoords"))
    d.test.assertEqual(d.call(d.player, "getName"), request.get("player", {}).get("name"))
    if branch:
        d.check(branch, True, station=name, callbackSeq=request["seq"], recipes=sorted(expected))
    return choices


def recipeAttempt(d, station, recipe_id, branch, *, outcome, navigate=None):
    d.test.assertIn(outcome, {"locked", "missingIngredients", "insufficientGold", "success", "failure"})
    recipe = recipeDefinitions()[recipe_id]
    choices = openStation(d, station, navigate=navigate)
    choice = next(value for value in choices if value["id"] == recipe_id)
    before, gold_before, context = inventoryTypes(d), d.gold(), craftContext(d)
    inputs = Counter()
    for entry in recipe.get("inputs", ()):
        inputs[entry["item"]] += entry.get("count", 1)
    counts = Counter(before.values())
    missing = next((identity for identity, count in inputs.items() if counts[identity] < count), None)
    flag = recipe.get("unlockFlag")
    unlocked = not flag or d.call(d.player, "getBoolProperty", flag) or d.call(d.game_map, "getBoolProperty", flag)
    cost = recipe.get("gold", 0)
    if outcome == "locked":
        d.test.assertFalse(unlocked, "The locked branch needs its actual unmet authored prerequisite")
        reason = "locked"
    else:
        d.test.assertTrue(unlocked, "A prerequisite cannot be injected or skipped")
        if outcome == "missingIngredients":
            d.test.assertIsNotNone(missing)
            reason = "missing:" + missing
        else:
            d.test.assertIsNone(missing, "The gold/roll branch requires every actual ingredient")
            if outcome == "insufficientGold":
                d.test.assertLess(gold_before, cost)
                reason = "missing:gold"
            else:
                d.test.assertGreaterEqual(gold_before, cost)
                if outcome == "failure":
                    d.test.assertLess(recipe.get("successChance", 100), 100, "A guaranteed recipe cannot roll failure")
                reason = "" if outcome == "success" else "failed"
    d.test.assertIs(choice["enabled"], outcome in {"success", "failure"})
    result = d.engine("craftRecipe", d.game, d.object(station), recipe_id)
    d.pump()
    d.test.assertEqual({"ok": outcome == "success", "reason": reason}, result, "The declared outcome was not observed")
    after = inventoryTypes(d)
    d.test.assertEqual(context, craftContext(d), "Crafting changed unrelated native state or advanced the map")
    removed, added = set(before) - set(after), set(after) - set(before)
    if outcome in {"success", "failure"}:
        d.test.assertEqual(gold_before - cost, d.gold())
        d.test.assertEqual(inputs, Counter(before[identity] for identity in removed))
        output = recipe["output"]
        expected_output = Counter({output["item"]: output.get("count", 1)}) if outcome == "success" else Counter()
        d.test.assertEqual(expected_output, Counter(after[identity] for identity in added))
        d.test.assertEqual(
            {identity: before[identity] for identity in set(before) & set(after)},
            {identity: after[identity] for identity in set(before) & set(after)},
        )
    else:
        d.test.assertEqual(gold_before, d.gold())
        d.test.assertEqual(before, after)
    d.check(
        branch,
        True,
        station=station,
        recipe=recipe_id,
        result=result,
        goldBefore=gold_before,
        goldAfter=d.gold(),
        consumed=sorted(removed),
        created=sorted(added),
    )
    return result
