# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Correlate Gooby's actual quest completion, native payment and observed reward receipt."""

from collections import OrderedDict

QUEST_ID = "mainQuest"
REWARD_TITLE = "Nouraajd's thanks"
GOLD_REWARD = 200


def observeMainQuestReward(validator, records):
    receipts = getattr(validator, "_main_quest_rewards", None)
    if receipts is None:
        validator._main_quest_rewards = receipts = OrderedDict()
    pending = getattr(validator, "_pending_main_quest_reward", None)
    for record in records:
        event = record.get("event")
        if event == "quest_completed":
            if pending is not None:
                raise AssertionError(("Main quest reward ended without its receipt", pending))
            if record.get("quest") != QUEST_ID:
                continue
            player = record.get("player")
            if not isinstance(player, dict) or player.get("isPlayer") is not True:
                raise AssertionError(("Main quest completion has no actual player", record))
            if (
                record.get("map") != "nouraajd"
                or any(not isinstance(player.get(key), str) for key in ("id", "name", "typeId", "type"))
                or not all(player[key] for key in ("id", "name", "type"))
            ):
                raise AssertionError(("Main quest completion has no authored identity", record))
            key = (record["map"], player["name"])
            if key in receipts:
                raise AssertionError(("Main quest completed twice for the same player", record))
            pending = {"completion": record, "gold": None}
        elif pending is not None and event == "gold_changed":
            completion = pending["completion"]
            if record.get("actor") != completion["player"]:
                raise AssertionError(("Main quest payment has a different recipient", record))
            values = [record.get(key) for key in ("before", "after", "delta")]
            if (
                record.get("map") != completion["map"]
                or any(type(value) is not int for value in values)
                or values[1] - values[0] != GOLD_REWARD
                or values[2] != GOLD_REWARD
                or pending["gold"] is not None
            ):
                raise AssertionError(("Main quest must pay exactly 200 gold once", record))
            pending["gold"] = record
        elif event == "reader_requested" and record.get("title") == REWARD_TITLE:
            if pending is None or pending["gold"] is None:
                raise AssertionError(("Main quest receipt has no witnessed native payment", record))
            completion = pending["completion"]
            body = record.get("body")
            if (
                record.get("map") != completion["map"]
                or record.get("player") != completion["player"]
                or record.get("headless") is not True
                or record.get("titleLength") != len(REWARD_TITLE.encode("utf-8"))
                or not isinstance(body, str)
                or record.get("bodyLength") != len(body.encode("utf-8"))
                or body.splitlines().count("Gold: +200") != 1
                or any(line.startswith("Gold: ") and line != "Gold: +200" for line in body.splitlines())
            ):
                raise AssertionError(("Main quest reward receipt differs from its actual payment", record))
            key = (completion["map"], completion["player"]["name"])
            receipts[key] = {
                "completion": completion,
                "payment": pending["gold"],
                "receipt": record,
            }
            if len(receipts) > 16:
                raise AssertionError("Main quest reward evidence exceeds the bounded player budget")
            pending = None
    validator._pending_main_quest_reward = pending


def requireMainQuestReward(validator, player_name):
    if getattr(validator, "_pending_main_quest_reward", None) is not None:
        raise AssertionError("Main quest reward did not finish its native payment and presentation")
    receipt = getattr(validator, "_main_quest_rewards", {}).get(("nouraajd", player_name))
    if receipt is None:
        raise AssertionError("Completed MainQuest requires its actual 200-gold native reward receipt")
    return receipt
