"""Adjacent movement, ordinary combat, and natural timers through the campaign's final chapters."""

import json
from pathlib import Path

from tests.castle_walkthrough import TransitRoutes, shortestRoute

ROOT = Path(__file__).resolve().parents[1]


def authoredRegion(map_name):
    directory = ROOT / "res/maps" / map_name
    document = json.loads((directory / "map.json").read_text())
    configs = {}
    for path in sorted((ROOT / "res/config").glob("*.json")):
        configs.update(json.loads(path.read_text()))
    configs.update(json.loads((directory / "config.json").read_text()))

    def definition(type_id):
        value = configs[type_id]
        base = definition(value["ref"]) if "ref" in value else {}
        return {**base, **value, "properties": {**base.get("properties", {}), **value.get("properties", {})}}

    objects = {}
    walkable = set()
    tile_types = document["tilesets"][0]["tileproperties"]
    for layer in document["layers"]:
        z = int(layer["properties"]["level"])
        if layer["type"] == "objectgroup":
            for item in layer["objects"]:
                objects[item["name"]] = (int(item["x"] // 32), int(item["y"] // 32), z)
        elif layer["type"] == "tilelayer":
            for index, tile in enumerate(layer["data"]):
                type_id = tile_types.get(str(tile - 1), {}).get("type", layer["properties"]["default"])
                if definition(type_id)["properties"].get("canStep", False):
                    walkable.add((index % document["width"], index // document["width"], z))
    if map_name == "siege":
        # Activating a breach replaces its border tile with authored SwampTile.
        walkable.update(objects[name] for name in objects if name.startswith("spawnPoint"))
    return objects, walkable


class NarrativeWalkthrough:
    def __init__(self, engine_call, handle_call, game_handle, map_handle, player_handle):
        self.engineCall = engine_call
        self.handleCall = handle_call
        self.game = game_handle
        self.gameMap = map_handle
        self.player = player_handle
        self.loop = self.engineCall("event_loop.instance", [])
        self.log = {"movementSteps": 0, "mapTurns": 0, "sealedGates": [], "fixturePotions": 6}
        self.walkTarget = None
        self.assertSurvival("fresh fixture")

    def call(self, handle, method, args=None):
        return self.handleCall(handle, method, args or [])

    def pump(self):
        self.call(self.loop, "run")
        self.assertSurvival("after event_loop.run")

    def properties(self, handle):
        return json.loads(self.engineCall("jsonify", [handle]))["properties"]

    def coords(self, handle=None):
        data = self.properties(handle or self.player)
        return tuple(data["pos" + axis] for axis in "xyz")

    def object(self, name):
        return self.call(self.gameMap, "getObjectByName", [name])

    def flag(self, name):
        return self.call(self.gameMap, "getBoolProperty", [name])

    def questNames(self, key):
        return [
            quest["properties"].get("typeId") or quest["properties"].get("name")
            for quest in self.properties(self.player).get(key) or []
        ]

    def failureState(self, reason, stage):
        map_name = self.call(self.gameMap, "getStringProperty", ["mapName"])
        target_names = {
            name for name, coords in getattr(self, "objects", {}).items() if tuple(coords) == self.walkTarget
        }
        if map_name == "ritual":
            target_names.add("ritualLeader")
        target_objects = {}
        for name in sorted(target_names):
            handle = self.object(name)
            target_objects[name] = self.properties(handle) if handle else None
        return {
            **self.log,
            "reason": reason,
            "stage": stage,
            "map": map_name,
            "nativeTurn": self.call(self.gameMap, "getTurn"),
            "uiDefeatReceipt": self.call(self.player, "getStringProperty", ["uiDefeatReceipt"]),
            "playerCoords": self.coords(),
            "player": self.properties(self.player),
            "resources": {
                **{
                    key: self.call(self.player, method)
                    for key, method in (
                        ("hp", "getHp"),
                        ("hpMax", "getHpMax"),
                        ("mana", "getMana"),
                        ("manaMax", "getManaMax"),
                    )
                },
                **{item: self.call(self.player, "countItems", [item]) for item in ("LifePotion", "ManaPotion")},
            },
            "target": {"coords": self.walkTarget, "objects": target_objects},
        }

    def assertSurvival(self, stage):
        alive = self.call(self.player, "isAlive")
        receipt = self.call(self.player, "getStringProperty", ["uiDefeatReceipt"])
        if not alive or receipt:
            raise AssertionError(self.failureState("Walkthrough player was defeated", stage))

    def recoverBeforeAction(self, stage):
        hp_max = self.call(self.player, "getHpMax")
        if self.call(self.player, "getHp") * 4 >= hp_max * 3:
            return
        candidates = []
        for item in self.call(self.player, "getItems"):
            if not self.call(item, "hasTag", ["heal"]):
                continue
            power = self.call(item, "getPower")
            if power > 0:
                candidates.append((power, self.call(item, "getTypeId"), self.call(item, "getName"), item))
        # Match the combat controller's 75% recovery threshold and weakest-first supplies.
        # Each carried candidate is used at most once; inventory use does not advance a map turn.
        for _, type_id, _, item in sorted(candidates, key=lambda entry: entry[:3]):
            hp_before = self.call(self.player, "getHp")
            if hp_before * 4 >= hp_max * 3:
                break
            self.call(self.player, "useItem", [item])
            self.assertSurvival("after inventory recovery")
            hp_after = self.call(self.player, "getHp")
            if hp_after <= hp_before:
                raise AssertionError(self.failureState("Carried healing item did not restore health", stage))
            self.log.setdefault("recoveryItems", []).append(
                {"typeId": type_id, "hpBefore": hp_before, "hpAfter": hp_after, "stage": stage}
            )

    def tick(self):
        self.assertSurvival("before map.move")
        self.recoverBeforeAction("before map.move")
        self.call(self.gameMap, "move")
        self.log["mapTurns"] += 1
        self.pump()

    def walkTo(self, target, *, stop=None):
        target = tuple(target)
        self.walkTarget = target
        for _ in range(256):
            self.assertSurvival("before movement")
            if (stop and stop()) or self.coords() == target:
                return
            try:
                route = shortestRoute(self.walkable, TransitRoutes(), self.coords(), target)
            except AssertionError as error:
                raise AssertionError(self.failureState("No adjacent authored route", "before movement")) from error
            step, _ = route[0]
            self.recoverBeforeAction("before movement")
            self.call(self.player, "moveTo", list(step))
            self.log["movementSteps"] += 1
            self.pump()
            self.tick()
        raise AssertionError(self.failureState("Movement did not reach the authored target", "movement budget"))

    def automaticCombat(self):
        template = self.call(self.game, "createObject", [self.call(self.player, "getTypeId")])
        self.call(self.player, "setFightController", [self.call(template, "getFightController")])

    def ritual(self, outcome, *, save_name=None):
        self.log["outcome"] = outcome
        self.log["class"] = self.call(self.player, "getTypeId")
        self.objects, self.walkable = authoredRegion("ritual")
        self.automaticCombat()
        # Ordinary carried supplies model inventory from the previous chapter; equipment/stats stay as authored.
        for _ in range(self.log["fixturePotions"]):
            self.call(self.player, "addItem", ["LifePotion"])
            self.call(self.player, "addItem", ["ManaPotion"])
        self.initialExperience = self.call(self.player, "getNumericProperty", ["exp"])
        assert self.flag("ritual_initialized")
        assert set(self.questNames("quests")) >= {
            "ritualQuest",
            "destroyAnchorsQuest",
            "rescueCaptiveQuest",
            "finalResolutionQuest",
        }
        dialog = self.call(self.game, "createObject", ["capturedSoulDialog"])
        self.call(dialog, "invokeAction", ["continueAfterLoss"])
        assert not self.flag("ritual_resolution_chosen")
        self.walkTo(self.objects["anchorNorth"])
        assert self.object("anchorNorth") is None
        assert self.flag("ritual_started")
        if outcome == "bad":
            # Let the authored five-turn countdown cadence run; the remaining anchors are still intact.
            for _ in range(80):
                if self.flag("captive_lost"):
                    break
                self.tick()
            assert self.flag("captive_lost") and self.flag("bad_ending")
            assert not self.flag("anchors_destroyed")
            assert not self.flag("ritual_resolution_chosen")
            assert "finalResolutionQuest" in self.questNames("quests")
            self.call(dialog, "invokeAction", ["continueAfterLoss"])
            assert not self.flag("ritual_resolution_chosen")
        self.walkTo(self.objects["anchorCrypt"])
        assert self.object("anchorCrypt") is None
        if save_name:
            self.saveAndReload(save_name)
        self.walkTo(self.objects["anchorSanctum"])
        assert self.object("anchorSanctum") is None
        assert self.flag("anchors_destroyed")
        for _ in range(80):
            leader = self.object("ritualLeader")
            if not leader:
                break
            self.walkTo(self.coords(leader), stop=lambda: self.flag("leader_defeated"))
        assert self.flag("leader_defeated"), self.log
        assert self.call(self.player, "getNumericProperty", ["exp"]) > self.initialExperience
        assert self.flag("captive_lost") == (outcome == "bad"), self.log
        self.walkTo(self.objects["ritualCaptive"])
        dialog = self.call(self.game, "createObject", ["capturedSoulDialog"])
        gold_before = self.call(self.player, "getGold")
        potions_before = self.call(self.player, "countItems", ["LifePotion"])
        source_map = self.gameMap
        progression_before = self.progression()
        self.call(dialog, "invokeAction", ["free_captive" if outcome == "good" else "continueAfterLoss"])
        self.pump()
        self.gameMap = self.call(self.game, "getMap")
        assert self.call(self.gameMap, "getStringProperty", ["mapName"]) == "siege"
        assert self.call(self.gameMap, "getPlayer") == self.player
        assert self.progression() == progression_before
        assert self.call(source_map, "getBoolProperty", ["ritual_resolution_chosen"])
        assert self.call(self.player, "getGold") - gold_before == (300 if outcome == "good" else 100)
        assert self.call(self.player, "countItems", ["LifePotion"]) - potions_before == (1 if outcome == "good" else 0)
        assert set(self.questNames("completedQuests")) >= {
            "ritualQuest",
            "destroyAnchorsQuest",
            "rescueCaptiveQuest",
            "finalResolutionQuest",
        }
        assert not set(self.questNames("quests")) & {"ritualQuest", "finalResolutionQuest"}
        self.log["ritualGold"] = 300 if outcome == "good" else 100
        self.automaticCombat()

    def saveAndReload(self, name):
        self.assertSurvival("before save")
        before = {
            "gold": self.call(self.player, "getGold"),
            "class": self.call(self.player, "getTypeId"),
            "turn": self.call(self.gameMap, "getTurn"),
            "lost": self.flag("captive_lost"),
            "completedQuests": self.questNames("completedQuests"),
            "progression": self.progression(),
            "potions": [self.call(self.player, "countItems", [item]) for item in ("LifePotion", "ManaPotion")],
        }
        assert self.engineCall("CMapLoader.saveWithResult", [self.gameMap, name]), "Partial-objective save failed"
        self.game = self.engineCall("CGameLoader.loadGame", [])
        self.engineCall("CGameLoader.loadSavedGame", [self.game, name])
        self.gameMap = self.call(self.game, "getMap")
        self.player = self.call(self.gameMap, "getPlayer")
        self.pump()
        assert self.call(self.player, "getGold") == before["gold"]
        assert self.call(self.player, "getTypeId") == before["class"]
        assert self.call(self.gameMap, "getTurn") == before["turn"]
        assert self.flag("captive_lost") == before["lost"]
        assert self.questNames("completedQuests") == before["completedQuests"]
        assert self.progression() == before["progression"]
        assert [self.call(self.player, "countItems", [item]) for item in ("LifePotion", "ManaPotion")] == before[
            "potions"
        ]
        assert self.flag("anchor_north_destroyed") and self.flag("anchor_crypt_destroyed")
        assert not self.flag("anchor_sanctum_destroyed")
        self.automaticCombat()
        self.log["partialObjectivesSaveReload"] = True

    def progression(self):
        return {
            "class": self.call(self.player, "getTypeId"),
            "level": self.call(self.player, "getLevel"),
            "experience": self.call(self.player, "getNumericProperty", ["exp"]),
            "equipped": self.properties(self.player).get("equipped"),
        }

    def siege(self, expected_bounty=500):
        self.objects, self.walkable = authoredRegion("siege")
        gates = ["spawnPoint1", "spawnPoint2", "spawnPoint3", "spawnPoint4"]
        for _ in range(1200):
            remaining = [name for name in gates if not self.call(self.object(name), "getBoolProperty", ["destroyed"])]
            if not remaining:
                break
            enabled = [name for name in remaining if self.call(self.object(name), "getBoolProperty", ["enabled"])]
            if not enabled or not self.call(self.player, "countItems", ["magicWand"]):
                # Leave a sealed border breach so attackers can reach the ordinary interior target.
                self.walkTo(self.objects["siegeStart"])
                self.tick()
                continue
            name = min(enabled, key=lambda name: sum(abs(a - b) for a, b in zip(self.coords(), self.objects[name])))
            self.walkTo(self.objects[name])
            before_wands = self.call(self.player, "countItems", ["magicWand"])
            before_gold = self.call(self.player, "getGold")
            assert self.call(self.object(name), "sealBreach"), (name, self.coords(), self.log)
            self.pump()
            assert self.call(self.player, "countItems", ["magicWand"]) == before_wands - 1
            assert not self.call(self.object(name), "sealBreach")
            self.log["sealedGates"].append(name)
            self.walkable.discard(self.objects[name])
            if len(remaining) == 1:
                assert self.call(self.player, "getGold") == before_gold + expected_bounty
        self.log["siegeFinalState"] = {
            "playerCoords": self.coords(),
            "wandCount": self.call(self.player, "countItems", ["magicWand"]),
            "turn": self.call(self.gameMap, "getTurn"),
            "gates": {
                name: {
                    key: self.call(self.object(name), "getBoolProperty", [key])
                    for key in ("enabled", "destroyed", "pendingSeal")
                }
                for name in gates
            },
        }
        assert len(self.log["sealedGates"]) == 4, self.log
        assert self.flag("campaign_completed")
        assert "defendSiegeQuest" in self.questNames("completedQuests")
        assert "defendSiegeQuest" not in self.questNames("quests")
        self.log["siegeGold"] = expected_bounty
        self.log["finalLevel"] = self.call(self.player, "getLevel")
        return self.log
