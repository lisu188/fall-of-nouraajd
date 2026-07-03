# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2025  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import json

import game
from game import randint

LEAVE_OPTION = "Leave"

# Shown for a locked recipe when neither the recipe's unlockHint nor the
# station's per-map override provides text. Never expose the raw flag name.
DEFAULT_LOCKED_HINT = "This recipe is locked."


def _status(ok, reason=""):
    return {"ok": ok, "reason": reason}


def _coerce_count(value, default=1):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _normalize_item_entries(entries):
    # Entries listing the same item more than once are merged into a single
    # requirement: verification and removal both treat each entry
    # independently, so duplicates would otherwise pass the inventory check
    # with fewer items than the recipe actually costs.
    normalized = []
    index_by_item = {}
    for entry in entries or []:
        if isinstance(entry, str):
            item_id, count = entry, 1
        elif isinstance(entry, dict):
            item_id = entry.get("item") or entry.get("item_id") or entry.get("itemId") or entry.get("id")
            if not item_id:
                continue
            count = _coerce_count(entry.get("count", 1), 1)
        else:
            continue
        if item_id in index_by_item:
            normalized[index_by_item[item_id]]["count"] += count
        else:
            index_by_item[item_id] = len(normalized)
            normalized.append({"item_id": item_id, "count": count})
    return normalized


def count_inventory_matches(player, item_id):
    count_method = getattr(player, "countItems", None)
    if callable(count_method):
        try:
            return max(0, int(count_method(item_id)))
        except Exception:
            pass
    get_items = getattr(player, "getItems", None)
    if callable(get_items):
        try:
            return len([item for item in get_items() if item.getTypeId() == item_id])
        except Exception:
            pass
    return 1 if player.hasItem(lambda item: item.getTypeId() == item_id) else 0


def verify_inventory_requirements(player, requirements):
    for requirement in requirements:
        item_id = requirement["item_id"]
        required_count = requirement["count"]
        if count_inventory_matches(player, item_id) < required_count:
            return _status(False, f"missing:{item_id}")
    return _status(True)


def remove_required_items(player, requirements):
    for requirement in requirements:
        item_id = requirement["item_id"]
        for _ in range(requirement["count"]):
            player.removeItem(lambda item, req_id=item_id: item.getTypeId() == req_id, True)


def has_enough_gold(player, gold_cost):
    if gold_cost <= 0:
        return _status(True)
    if player.getNumericProperty("gold") < gold_cost:
        return _status(False, "missing:gold")
    return _status(True)


def deduct_gold(player, gold_cost):
    if gold_cost > 0:
        current_gold = player.getNumericProperty("gold")
        player.setNumericProperty("gold", current_gold - gold_cost)


def create_reward_objects(game_instance, player, rewards):
    object_handler = game_instance.getObjectHandler()
    for reward in rewards:
        item_id = reward["item_id"]
        for _ in range(reward["count"]):
            reward_object = object_handler.createObject(game_instance, item_id)
            player.addItem(reward_object)


def apply_recipe(game_instance, player, recipe):
    inventory_status = verify_inventory_requirements(player, recipe["inputs"])
    if not inventory_status["ok"]:
        return inventory_status

    gold_status = has_enough_gold(player, recipe["gold"])
    if not gold_status["ok"]:
        return gold_status

    # Pay the cost before rolling so a failed craft still consumes its
    # reagents (and gold); otherwise success_chance would be a free retry.
    # The preconditions above guarantee the player can afford both paths.
    remove_required_items(player, recipe["inputs"])
    deduct_gold(player, recipe["gold"])

    success_chance = max(0, min(100, recipe.get("success_chance", 100)))
    if success_chance < 100 and randint(1, 100) > success_chance:
        return _status(False, "failed")

    create_reward_objects(game_instance, player, recipe["outputs"])
    return _status(True)


class CraftingRuntime:
    def __init__(self):
        self._item_labels = self._load_item_labels()
        self._recipes = self._load_recipes()

    def _read_json(self, filename):
        try:
            return json.loads(game.CResourcesProvider.getInstance().load("config/" + filename))
        except Exception:
            return {}

    def _load_item_labels(self):
        labels = {}
        for filename in ("items.json", "potions.json"):
            data = self._read_json(filename)
            for item_id, payload in data.items():
                props = payload.get("properties", {})
                label = props.get("label") or payload.get("label")
                if label:
                    labels[item_id] = label
        return labels

    def _load_recipes(self):
        recipes = {}
        data = self._read_json("crafting.json")
        for recipe_id, payload in data.items():
            normalized = self._normalize_recipe(recipe_id, payload)
            if normalized:
                recipes[recipe_id] = normalized
        return recipes

    def _normalize_recipe(self, recipe_id, payload):
        if not isinstance(payload, dict):
            return None
        station_id = payload.get("station")
        if not station_id:
            return None
        inputs = _normalize_item_entries(payload.get("inputs", []))
        outputs = payload.get("outputs")
        if isinstance(payload.get("output"), dict):
            outputs = [payload["output"]]
        outputs = _normalize_item_entries(outputs)
        if not outputs:
            return None
        primary_output = outputs[0]["item_id"]
        gold_cost = _coerce_count(payload.get("gold", payload.get("gold_cost", 0)), 0)
        success_chance = _coerce_count(payload.get("successChance", payload.get("success_chance", 100)), 100)
        success_chance = max(0, min(100, success_chance))
        return {
            "id": recipe_id,
            "station": station_id,
            "inputs": inputs,
            "outputs": outputs,
            "gold": gold_cost,
            "success_chance": success_chance,
            "unlock": self._normalize_unlock_requirement(recipe_id, payload),
            "unlock_hint": str(payload.get("unlockHint", "") or "").strip(),
            "display_name": self.get_item_label(primary_output),
        }

    def _normalize_unlock_requirement(self, recipe_id, payload):
        quest_key = payload.get("unlockQuest")
        if quest_key:
            raise ValueError(
                f"Recipe '{recipe_id}' references unlockQuest '{quest_key}', "
                "but crafting unlocks no longer support quest ids. "
                "Use unlockFlag with a player or map boolean."
            )
        flag_key = payload.get("unlockFlag")
        if flag_key:
            flag_key = str(flag_key).strip()
            if not flag_key:
                raise ValueError(f"Recipe '{recipe_id}' defines an empty unlockFlag.")
            return {"type": "flag", "value": flag_key}
        return {"type": "none", "value": None}

    def get_recipe(self, recipe_id):
        return self._recipes.get(recipe_id)

    def station_recipes(self, station_id):
        return sorted(
            [recipe for recipe in self._recipes.values() if recipe["station"] == station_id],
            key=lambda recipe: recipe["display_name"],
        )

    def get_item_label(self, item_id):
        return self._item_labels.get(item_id, item_id)

    def describe_entries(self, entries):
        parts = [
            f"{entry['count']}x {self.get_item_label(entry['item_id'])}" for entry in entries if entry["count"] > 0
        ]
        return ", ".join(parts) if parts else "None"

    def describe_requirements(self, recipe):
        parts = [self.describe_entries(recipe["inputs"])]
        if recipe["gold"] > 0:
            parts.append(f"{recipe['gold']}g")
        return ", ".join(part for part in parts if part and part != "None") or "No cost"

    def describe_outputs(self, recipe):
        return self.describe_entries(recipe["outputs"])

    def describe_recipe(self, recipe):
        parts_text = self.describe_requirements(recipe)
        output = recipe["outputs"][0]
        chance = recipe["success_chance"]
        return (
            f"{recipe['display_name']} [{recipe['id']}] | "
            f"Output: {self.describe_outputs(recipe)} | Requires: {parts_text} | {chance}% success"
        )

    def missing_requirements(self, player, recipe):
        missing = []
        for requirement in recipe["inputs"]:
            required_count = requirement["count"]
            if required_count <= 0:
                continue
            item_id = requirement["item_id"]
            held_count = count_inventory_matches(player, item_id)
            if held_count < required_count:
                missing.append(f"{required_count - held_count}x {self.get_item_label(item_id)}")
        gold_cost = recipe["gold"]
        if gold_cost > 0:
            held_gold = player.getNumericProperty("gold")
            if held_gold < gold_cost:
                missing.append(f"{gold_cost - held_gold}g")
        return missing

    def recipe_unlock_hint(self, recipe, station=None):
        unlock_state = recipe.get("unlock", {"type": "none", "value": None})
        if unlock_state["type"] != "flag":
            return ""
        # A map can tailor the guidance to its own quest line by setting an
        # "unlockHint_<FLAG>" string property on its station instance; the
        # recipe's unlockHint from crafting.json is the map-agnostic default.
        if station is not None:
            override = station.getStringProperty("unlockHint_" + unlock_state["value"])
            if override:
                return override
        return recipe.get("unlock_hint") or DEFAULT_LOCKED_HINT

    def recipe_state(self, player, recipe):
        if not self.is_unlocked(player, recipe):
            return "locked"
        if self.missing_requirements(player, recipe):
            return "missing"
        return "ready"

    def describe_recipe_for_player(self, player, recipe, station=None):
        description = self.describe_recipe(recipe)
        if not self.is_unlocked(player, recipe):
            return f"LOCKED - {description} | Unlock: {self.recipe_unlock_hint(recipe, station)}"
        missing = self.missing_requirements(player, recipe)
        if not missing:
            return f"READY - {description}"
        return f"MISSING - {description} | Missing: {', '.join(missing)}"

    def is_unlocked(self, player, recipe):
        unlock_state = recipe.get("unlock", {"type": "none", "value": None})
        if unlock_state["type"] == "flag":
            return self._is_flag_set(player, unlock_state["value"])
        return True

    def _is_flag_set(self, player, flag_name):
        if player.getBoolProperty(flag_name):
            return True
        game_map = player.getMap()
        if game_map and game_map.getBoolProperty(flag_name):
            return True
        return False

    def available_recipes(self, player, station_id):
        return [recipe for recipe in self.station_recipes(station_id) if self.is_unlocked(player, recipe)]

    def station_options(self, player, station_id, station=None):
        recipes = self.station_recipes(station_id)
        option_map = {self.describe_recipe_for_player(player, recipe, station): recipe for recipe in recipes}
        return recipes, option_map

    def execute_recipe(self, game_instance, player, recipe):
        if not self.is_unlocked(player, recipe):
            return _status(False, "locked")
        return apply_recipe(game_instance, player, recipe)


_RUNTIME = None


def get_runtime():
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = CraftingRuntime()
    return _RUNTIME


def _format_result_message(runtime, recipe, result, player=None, station=None):
    if result["ok"]:
        output = recipe["outputs"][0]
        label = runtime.get_item_label(output["item_id"])
        quantity = output["count"]
        if quantity > 1:
            return f"You crafted {quantity}x {label}."
        return f"You crafted {label}."
    reason = result.get("reason", "")
    if reason == "locked":
        return f"That recipe is locked. {runtime.recipe_unlock_hint(recipe, station)}"
    if reason == "failed":
        return "The reagents fizzled and nothing was created."
    if reason == "missing:gold":
        return "You need more gold to craft this."
    if reason.startswith("missing:"):
        missing = runtime.missing_requirements(player, recipe) if player else []
        if missing:
            return f"You are missing {', '.join(missing)}."
        missing_item = reason.split("missing:", 1)[1]
        return f"You need more {runtime.get_item_label(missing_item)}."
    return reason or "Crafting failed."


def _get_station_identifier(station):
    station_id = station.getStringProperty("craftingStationId")
    if not station_id:
        station_id = station.getStringProperty("station") or station.getTypeId()
    return station_id


def open_crafting_station(station, player):
    if not player or not player.isPlayer():
        return
    runtime = get_runtime()
    station_id = _get_station_identifier(station)
    if not station_id:
        return
    game_instance = station.getGame()
    handler = game_instance.getGuiHandler()
    station_label = station.getStringProperty("label") or station_id
    while True:
        recipes, option_map = runtime.station_options(player, station_id, station)
        if not recipes:
            handler.showInfo(f"No known recipes for {station_label}.", True)
            return
        options = list(option_map.keys())
        options.append(LEAVE_OPTION)
        selection = handler.showSelection(game.list_string(game_instance, options))
        if selection == LEAVE_OPTION or selection not in option_map:
            break
        recipe = option_map[selection]
        if not runtime.is_unlocked(player, recipe):
            handler.showInfo(_format_result_message(runtime, recipe, _status(False, "locked"), player, station), True)
            continue
        result = runtime.execute_recipe(game_instance, player, recipe)
        handler.showInfo(_format_result_message(runtime, recipe, result, player, station), True)


def craft_recipe(game_instance, player, recipe_id):
    runtime = get_runtime()
    recipe = runtime.get_recipe(recipe_id)
    if not recipe:
        return _status(False, "missing:recipe")
    return runtime.execute_recipe(game_instance, player, recipe)


def load(self, context):
    from game import CBuilding
    from game import register

    @register(context)
    class CraftingStation(CBuilding):
        def onEnter(self, event):
            if event.getCause().isPlayer():
                open_crafting_station(self, event.getCause())
