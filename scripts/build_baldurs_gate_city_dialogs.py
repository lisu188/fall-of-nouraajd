# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure dialog metadata and concrete callback generation for the city builder."""

import json
import re
from copy import deepcopy
from pathlib import Path


def upperFirst(value):
    return value[:1].upper() + value[1:]


def selectorMatches(properties, selector, actor_id=""):
    return (
        (not selector.get("area") or selector["area"] == properties.get("sourceArea"))
        and (not selector.get("creature") or selector["creature"] == properties.get("sourceCreature"))
        and (
            not selector.get("label")
            or selector["label"].casefold() == properties.get("label", "").casefold()
            or selector["label"] == actor_id
        )
    )


def questDialogRows(document, properties, actor_id=""):
    entries = document.get("quests", []) if isinstance(document, dict) else document
    rows = []
    for quest in entries:
        key = upperFirst(quest["id"])
        if any(selectorMatches(properties, selector, actor_id) for selector in quest["givers"]) and not (
            quest["id"] == "cythandriaDiary" and properties.get("sourceCreature") == "TAMOKO"
        ):
            rows.append(
                {
                    "text": "Accept: " + quest["title"],
                    "action": "accept" + key,
                    "condition": "canAccept" + key,
                    "questId": quest["id"],
                }
            )
        if quest["id"] == "tamokoMercy":
            if any(selectorMatches(properties, selector, actor_id) for selector in quest["givers"]):
                rows.append(
                    {
                        "text": "Discuss Tamoko's final stand.",
                        "action": "discussTamokoFinalMeeting",
                        "condition": "canDiscussTamokoFinalMeeting",
                        "questId": "tamokoMercy",
                    }
                )
            continue
        for outcome in quest["outcomes"]:
            if outcome.get("effects", {}).get("finale"):
                continue
            if any(selectorMatches(properties, selector, actor_id) for selector in outcome.get("at", quest["givers"])):
                action = "quest" + key + upperFirst(outcome["id"])
                rows.append(
                    {
                        "text": outcome["text"],
                        "action": action,
                        "condition": "can" + upperFirst(action),
                        "questId": quest["id"],
                    }
                )
    if isinstance(document, dict):
        for excursion in document.get("excursions", []):
            if any(selectorMatches(properties, selector, actor_id) for selector in excursion["at"]):
                for choice in excursion["choices"]:
                    rows.append(
                        {
                            "text": choice["label"],
                            "action": "excursion" + upperFirst(excursion["id"]) + upperFirst(choice["id"]),
                            "condition": "canExcursion" + upperFirst(excursion["id"]),
                            "questId": excursion["quest"],
                        }
                    )
    return rows


def renderCallbacks(document):
    entries = document.get("quests", []) if isinstance(document, dict) else document
    lines = []
    for quest in entries:
        key = upperFirst(quest["id"])
        lines += [
            f"        def canAccept{key}(self):",
            f"            return self.canAcceptQuest({quest['id']!r})",
            "",
            f"        def accept{key}(self):",
            f"            return self.acceptQuest({quest['id']!r})",
            "",
        ]
        for outcome in quest["outcomes"]:
            action = "quest" + key + upperFirst(outcome["id"])
            arguments = repr(quest["id"]) + ", " + repr(outcome["id"])
            lines += [
                f"        def can{upperFirst(action)}(self):",
                f"            return self.canQuestOutcome({arguments})",
                "",
                "        @resumableHook",
                f"        def {action}(self):",
                f"            return (yield from self.performQuestOutcomeFlow({arguments}))",
                "",
            ]
    if isinstance(document, dict):
        for excursion in document.get("excursions", []):
            token = upperFirst(excursion["id"])
            lines += [
                f"        def canExcursion{token}(self):",
                f"            return self.canExcursion({excursion['id']!r})",
                "",
            ]
            for choice in excursion["choices"]:
                lines += [
                    "        @resumableHook",
                    f"        def excursion{token}{upperFirst(choice['id'])}(self):",
                    f"            return (yield from self.excursionFlow({excursion['id']!r}, {choice['id']!r}))",
                    "",
                ]
    return "\n".join(lines)


SERVICE_NAMES = {
    "SPPR103": "Cure Light Wounds",
    "SPPR303": "Cure Disease",
    "SPPR307": "Remove Curse",
    "SPPR401": "Neutralize Poison",
    "SPPR212": "Slow Poison",
    "SPPR504": "Raise Dead",
}


def storeToken(store_id):
    return upperFirst(re.sub(r"[^a-zA-Z0-9]", "", store_id).lower())


def prepareStores(stores, items):
    result = deepcopy(stores)
    for store in result.values():
        for row in store.get("stock", []):
            metadata = items.get(row["item"], {})
            row["quantity"] = max(1, (row.get("charges") or [1])[0]) if metadata.get("stack_size", 1) > 1 else 1
            base_value = max(0, int(metadata.get("price", 0))) * row["quantity"]
            row["price"] = max(1, base_value * int(store.get("sell_markup", 100)) // 100)
            row["label"] = metadata.get("displayName") or row["item"]
    return result


def storeDialogRows(store_id, store):
    token = storeToken(store_id)
    rows = []
    flags = store.get("flags", 0)
    for index, row in enumerate(store.get("stock", []) if flags & 1 else []):
        label = row.get("label", row["item"])
        count = row.get("quantity", 1)
        rows.append(
            {
                "group": "stock",
                "text": f"{label} x{count} - {row.get('price', 0)} gold",
                "action": f"buyStore{token}{index}",
                "condition": f"canUseStore{token}",
            }
        )
    for index, row in enumerate(store.get("drinks", []) if flags & 64 else []):
        rows.append(
            {
                "group": "drinks",
                "text": f"{row.get('displayName', 'Drink')} - {row['price']} gold",
                "action": f"drinkStore{token}{index}",
                "condition": f"canUseStore{token}",
            }
        )
    for index, row in enumerate(store.get("cures", []) if flags & 32 else []):
        rows.append(
            {
                "group": "services",
                "text": f"{SERVICE_NAMES.get(row['spell'], row['spell'])} - {row['price']} gold",
                "action": f"serviceStore{token}{index}",
                "condition": f"canUseStore{token}",
            }
        )
    for index, label in enumerate(("Peasant", "Merchant", "Noble", "Royal")):
        if store.get("room_flags", 0) & (1 << index):
            rows.append(
                {
                    "group": "rooms",
                    "text": f"{label} room - {store['room_prices'][index]} gold",
                    "action": f"restStore{token}{index}",
                    "condition": f"canUseStore{token}",
                }
            )
    if flags & 4:
        rows.append(
            {
                "group": "services",
                "text": f"Identify first unknown possession - {store['identify_price']} gold",
                "action": f"identifyStore{token}",
                "condition": f"canUseStore{token}",
            }
        )
    return rows


def renderStoreCallbacks(stores):
    lines = []
    for store_id, store in stores.items():
        token = storeToken(store_id)
        lines += [f"        def canUseStore{token}(self):", f"            return self.canUseStore({store_id!r})", ""]
        for action, key, method, capability in (
            ("buy", "stock", "buyStock", 1),
            ("drink", "drinks", "buyDrink", 64),
            ("service", "cures", "buyService", 32),
        ):
            if not store.get("flags", 0) & capability:
                continue
            for index, _row in enumerate(store.get(key, [])):
                lines += [
                    f"        def {action}Store{token}{index}(self):",
                    f"            return self.{method}({store_id!r}, {index})",
                    "",
                ]
        for index in range(4):
            if store.get("room_flags", 0) & (1 << index):
                lines += [
                    f"        def restStore{token}{index}(self):",
                    f"            return self.rest({store_id!r}, {index})",
                    "",
                ]
        if store.get("flags", 0) & 4:
            lines += [f"        def identifyStore{token}(self):", f"            return self.identify({store_id!r})", ""]
    return "\n".join(lines)


def updateCallbacks(root):
    document = json.loads((root / "tests/fixtures/baldurs_gate_city_quests.json").read_text(encoding="utf-8"))
    source = json.loads((root / "tests/fixtures/baldurs_gate_city_source.json").read_text(encoding="utf-8"))
    path = root / "res/maps/baldursGate/script.py"
    text = path.read_text(encoding="utf-8")
    start, end = "        # QUEST_CALLBACKS_BEGIN\n", "        # QUEST_CALLBACKS_END"
    before, remainder = text.split(start, 1)
    _old, after = remainder.split(end, 1)
    callbacks = renderCallbacks(document) + "\n" + renderStoreCallbacks(source.get("stores", {}))
    path.write_text(before + start + callbacks + "\n" + end + after, encoding="utf-8")


if __name__ == "__main__":
    updateCallbacks(Path(__file__).resolve().parents[1])
