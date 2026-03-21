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


def _status(ok, reason=""):
    return {"ok": ok, "reason": reason}


def _coerce_count(value, default=1):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _normalize_item_entries(entries):
    normalized = []
    for entry in entries or []:
        if isinstance(entry, str):
            normalized.append({"item_id": entry, "count": 1})
            continue
        if isinstance(entry, dict):
            item_id = entry.get("item_id") or entry.get("itemId") or entry.get("id")
            if not item_id:
                continue
            normalized.append({"item_id": item_id, "count": _coerce_count(entry.get("count", 1), 1)})
    return normalized


def _normalize_recipe(recipe_id, recipe):
    return {
        "id": recipe_id,
        "requirements": _normalize_item_entries(recipe.get("requirements", [])),
        "rewards": _normalize_item_entries(recipe.get("rewards", [])),
        "gold_cost": _coerce_count(recipe.get("gold_cost", recipe.get("goldCost", 0)), 0),
    }


def load_recipe_definitions(source_object, property_name="recipes"):
    recipes_value = None
    if source_object is not None:
        try:
            recipes_value = source_object.getObjectProperty(property_name)
        except Exception:
            recipes_value = None
        if recipes_value is None:
            try:
                recipes_value = json.loads(source_object.getStringProperty(property_name))
            except Exception:
                recipes_value = None
    if recipes_value is None and source_object is not None and source_object.getMap() is not None:
        game_map = source_object.getMap()
        try:
            recipes_value = game_map.getObjectProperty(property_name)
        except Exception:
            recipes_value = None
        if recipes_value is None:
            try:
                recipes_value = json.loads(game_map.getStringProperty(property_name))
            except Exception:
                recipes_value = None

    if not isinstance(recipes_value, dict):
        return {}

    recipes = {}
    for recipe_id, recipe_value in recipes_value.items():
        if isinstance(recipe_value, dict):
            recipes[recipe_id] = _normalize_recipe(recipe_id, recipe_value)
    return recipes


def count_inventory_matches(player, item_id):
    get_items = getattr(player, "getItems", None)
    if callable(get_items):
        return len([item for item in get_items() if item.getName() == item_id])
    return 1 if player.hasItem(lambda item: item.getName() == item_id) else 0


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
            player.removeItem(lambda item, req_id=item_id: item.getName() == req_id, True)


def check_and_deduct_gold(player, gold_cost):
    if gold_cost <= 0:
        return _status(True)
    if player.getGold() < gold_cost:
        return _status(False, "missing:gold")
    player.takeGold(gold_cost)
    return _status(True)


def create_reward_objects(game, player, rewards):
    object_handler = game.getObjectHandler()
    for reward in rewards:
        item_id = reward["item_id"]
        for _ in range(reward["count"]):
            reward_object = object_handler.createObject(game, item_id)
            player.addItem(reward_object)


def apply_recipe(game, player, recipe):
    inventory_status = verify_inventory_requirements(player, recipe["requirements"])
    if not inventory_status["ok"]:
        return inventory_status

    gold_status = check_and_deduct_gold(player, recipe["gold_cost"])
    if not gold_status["ok"]:
        return gold_status

    remove_required_items(player, recipe["requirements"])
    create_reward_objects(game, player, recipe["rewards"])
    return _status(True)


def load(self, context):
    return None
