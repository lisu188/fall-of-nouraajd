#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile the finite Seven Suns materialization contract; source ability parity stays separate."""

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = "tests/fixtures/baldurs_gate_seven_suns_stock.json"
HEADER_PATH = "src/handler/CSevenSunsMerchantStockData.h"
ACTOR_ID = "citySevenSunsRevealedDoppss"
WEAPON_ID = "citySevenSunsDoppssWeapon"
FAMILIES = ("RNDTRE05", "RNDMAG01", "RNDMAG02", "RNDSCR01", "RNDSCR02", "RNDSCR03")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return "city-json:" + json.dumps(value, separators=(",", ":"))


def itemId(code):
    require(re.fullmatch(r"[A-Z0-9]{1,8}", code), "Invalid fixed stock resource")
    return "citySevenSunsTreasure" + code[0] + code[1:].lower()


def validateStock(document):
    require(document.get("schema") == "baldurs-gate-seven-suns-stock.v1", "Unsupported stock schema")
    require(
        document.get("originalParity") is False and document.get("itemAbilitiesEstablished") is False,
        "Materialization facts cannot grant original/ability acceptance",
    )
    require(document.get("nativeDiceRule") == "oneNativeD20PerSelectedRow", "Unreviewed native dice conversion")
    require(set(document["rows"]) == set(FAMILIES), "Changed finite stock families")
    tokens = set()
    for family, row in document["rows"].items():
        table, ordinal = {
            "RNDTRE05": ("RNDTREAS", 5),
            "RNDMAG01": ("RNDMAGIC", 1),
            "RNDMAG02": ("RNDMAGIC", 2),
            "RNDSCR01": ("RNDSCROL", 1),
            "RNDSCR02": ("RNDSCROL", 2),
            "RNDSCR03": ("RNDSCROL", 3),
        }[family]
        require(
            row["table"] == table and type(row["ordinal"]) is int and row["ordinal"] == ordinal,
            "Changed source stock row header",
        )
        expected_start = 1 if family.startswith("RNDSCR") else 2
        require(
            type(row["columns"]) is list
            and all(type(column) is int for column in row["columns"])
            and row["columns"] == list(range(expected_start, 21)),
            "Unreviewed stock columns",
        )
        require(len(row["cells"]) == len(row["columns"]), "Stock row dimension mismatch")
        for token in row["cells"]:
            require(isinstance(token, str) and len(token) <= 16, "Invalid stock token")
            if token in FAMILIES:
                require(
                    (family == "RNDTRE05" and token != "RNDTRE05")
                    or (family.startswith("RNDMAG") and token.startswith("RNDSCR")),
                    "Unreviewed cyclic stock reference",
                )
            elif token.isascii() and token.isdecimal():
                require(0 <= int(token) <= 256, "Unreviewed stock gold amount")
            else:
                require(re.fullmatch(r"[A-Z0-9]{1,8}(?:\*[1-9][0-9]{0,2})?", token), "Unknown stock token")
                tokens.add(token.split("*")[0])
    require(len(tokens) == 97 and set(document["items"]) == tokens, "Concrete stock closure changed")
    for code, item in document["items"].items():
        require(item["resourceId"] == itemId(code), "Stock resource identifier mismatch")
        require(re.fullmatch(r"[a-f0-9]{64}", item["baseSha256"]), "Missing item fingerprint")
        require(
            len(item["charges"]) == 3 and all(type(v) is int and 0 <= v <= 65535 for v in item["charges"]),
            "Unreviewed item charges",
        )
        for key, maximum in (
            ("stackSize", 65535),
            ("flags", 65535),
            ("itemType", 255),
            ("price", 1000000),
            ("lore", 65535),
            ("enchantment", 255),
        ):
            require(type(item[key]) is int and 0 <= item[key] <= maximum, "Invalid item field: " + key)
        require(type(item["abilityCount"]) is int and 0 <= item["abilityCount"] <= 3, "Unreviewed finite ability count")
        require(
            len(item["abilityEffectCounts"]) == item["abilityCount"]
            and all(type(value) is int and 0 <= value <= 4096 for value in item["abilityEffectCounts"]),
            "Unreviewed ability effect metadata",
        )
        require(
            type(item["equippedEffectCount"]) is int and 0 <= item["equippedEffectCount"] <= 4096,
            "Unreviewed equipped effect metadata",
        )
        require(
            all(value == 0 for value in item["charges"][item["abilityCount"] :]),
            "Charges extend beyond parsed base ability headers",
        )
        header = item["headerEvidence"]
        require(
            header["format"] == "ITM V1"
            and header["fingerprint"]["sha256"] == item["baseSha256"]
            and type(header["fingerprint"]["bytes"]) is int
            and 114 <= header["fingerprint"]["bytes"] <= 131072,
            "Changed parsed item header identity",
        )
        require(item["abilitiesPending"] is True, "Closed stock does not prove spell/item effects")
    weapon = document["weapon"]
    require(
        weapon["baseSha256"] == "44c02f993700e11ec0994567ad9edb9ad4c1737eab6761dbe6767887f6cc343a"
        and weapon["resourceId"] == WEAPON_ID
        and weapon["bonus"] == {"dmgMin": 1, "dmgMax": 12, "hit": 0}
        and type(weapon["enchantment"]) is int
        and weapon["enchantment"] == 1,
        "Unreviewed source weapon conversion",
    )
    return document


def compileResolver(document):
    """Validate once and snapshot the finite pure oracle, without retaining mutable input data."""
    validateStock(document)
    rows = {
        family: (row["ordinal"], dict(zip(row["columns"], row["cells"]))) for family, row in document["rows"].items()
    }
    items = {code: (item["stackSize"], tuple(item["charges"])) for code, item in document["items"].items()}

    def resolve(draws):
        iterator, trace, family = iter(draws), [], "RNDTRE05"
        for _depth in range(3):
            try:
                column = next(iterator)
            except StopIteration as error:
                raise ValueError("Missing native stock roll") from error
            require(type(column) is int and 1 <= column <= 20, "Native stock roll must be1..20")
            ordinal, cells = rows[family]
            token = cells.get(column, "")
            trace.append({"family": family, "row": ordinal, "column": column, "token": token})
            if not token:
                return {
                    "rolls": trace,
                    "outcome": {"kind": "none", "code": "", "quantity": 0, "gold": 0, "charges": [0, 0, 0]},
                }
            if token in FAMILIES:
                family = token
                continue
            if token.isascii() and token.isdecimal():
                return {
                    "rolls": trace,
                    "outcome": {"kind": "gold", "code": "", "quantity": 0, "gold": int(token), "charges": [0, 0, 0]},
                }
            code, separator, suffix = token.partition("*")
            stack_size, charges = items[code]
            quantity = int(suffix) if separator and stack_size > 1 else 1
            require(quantity <= max(1, stack_size), "Stock stack exceeds reviewed item capacity")
            return {
                "rolls": trace,
                "outcome": {"kind": "item", "code": code, "quantity": quantity, "gold": 0, "charges": list(charges)},
            }
        raise ValueError("Stock reference depth exceeded")

    return resolve


def resolveStock(document, draws):
    """Compatibility entry point; repeated workloads should use compileResolver once."""
    return compileResolver(document)(draws)


def stockDefinitions(document):
    validateStock(document)
    body = {
        "strength": 6,
        "agility": 6,
        "stamina": 4,
        "intelligence": 6,
        "dmgMin": 0,
        "dmgMax": 0,
        "hit": 75,
        "damage": 0,
        "crit": 0,
        "mainStat": "strength",
    }
    result = {
        ACTOR_ID: {
            "class": "CCreature",
            "properties": {
                "label": "Revealed doppelganger",
                "animation": "images/monsters/cultist",
                "npc": False,
                "affiliation": "cityHostile",
                "canStep": True,
                "sourceCreature": "DOPPSS",
                "sourceAllegiance": 255,
                "sourceKillXp": 420,
                "sourceSchedule": -1,
                "sourceScheduleRaw": "0xffffffff",
                "phaseMin": 5,
                "phaseMax": 7,
                "sw": -20,
                "baseStats": {"class": "CStats", "properties": body},
                "fightController": {"class": "CMonsterFightController"},
                "controller": {"class": "CTargetController", "properties": {"target": "player"}},
                "actions": [{"ref": "Attack"}],
                "gold": 0,
                "sourceInventory": encoded(
                    [
                        {"item": "S1-12", "flags": 0, "charges": [0, 0, 0]},
                        {"item": "RNDTRE05", "flags": 0, "charges": [0, 0, 0]},
                    ]
                ),
                "plugin_cityInventoryInitialized": False,
            },
        },
        WEAPON_ID: {
            "class": "CWeapon",
            "properties": {
                "label": "Doppelganger natural attack",
                "animation": "images/items/weapons/sword",
                "plugin_citySourceItem": "S1-12",
                "plugin_cityQuantity": 1,
                "plugin_cityCharges": encoded([0, 0, 0]),
                "plugin_cityUndroppable": True,
                "plugin_cityUnstealable": True,
                "plugin_cityTradeable": False,
                "plugin_citySourceItemFlags": 96,
                "plugin_citySourceFlags": 0,
                "plugin_citySourceItemFingerprint": document["weapon"]["baseSha256"],
                "plugin_citySourceEnchantment": document["weapon"]["enchantment"],
                "bonus": {"class": "CStats", "properties": document["weapon"]["bonus"]},
            },
        },
    }
    for code, item in sorted(document["items"].items()):
        result[item["resourceId"]] = {
            "class": "CItem",
            "properties": {
                "label": item["label"],
                "animation": item["animation"],
                "plugin_citySourceItem": code,
                "plugin_cityItemType": item["itemType"],
                "plugin_cityValue": item["price"],
                "plugin_cityLore": item["lore"],
                "plugin_cityStackSize": item["stackSize"],
                "plugin_citySourceItemFlags": item["flags"],
                "plugin_citySourceFlags": 0,
                "plugin_citySourceItemFingerprint": item["baseSha256"],
                "plugin_citySourceEnchantment": item["enchantment"],
                "plugin_cityQuantity": 1,
                "plugin_cityCharges": encoded(item["charges"]),
                "plugin_cityUndroppable": not bool(item["flags"] & 4),
                "plugin_cityUnstealable": False,
                "plugin_cityUnidentified": True,
                "plugin_cityTradeable": bool(item["flags"] & 4),
                "plugin_cityAbilitiesPending": True,
            },
        }
    return result


def stockHeader(document):
    validateStock(document)
    quoted = lambda value: json.dumps(value, ensure_ascii=True)
    lines = [
        "// Copyright (C) 2026 Andrzej Lis",
        "// SPDX-License-Identifier: GPL-3.0-or-later",
        "// Generated by scripts/build_baldurs_gate_merchant_stock.py; do not edit.",
        "#pragma once",
        "#include <array>",
        "#include <string_view>",
        "namespace seven_suns_stock {",
        "struct Item {",
        "    std::string_view code, resourceId, label, animation, fingerprint;",
        "    int flags, itemType, stackSize, price, lore, enchantment;",
        "    std::array<int, 3> charges;",
        "};",
        "struct Row {",
        "    std::string_view family;",
        "    int ordinal, firstColumn;",
        "    std::array<std::string_view, 20> cells;",
        "};",
        "// clang-format off",
        "inline constexpr std::array<Item, 97> Items{{",
    ]
    for code, item in sorted(document["items"].items()):
        strings = [code, item["resourceId"], item["label"], item["animation"], item["baseSha256"]]
        numbers = [item[k] for k in ("flags", "itemType", "stackSize", "price", "lore", "enchantment")]
        lines.append(
            "    {"
            + ", ".join(
                [
                    *(quoted(v) for v in strings),
                    *(str(v) for v in numbers),
                    "{" + ", ".join(map(str, item["charges"])) + "}",
                ]
            )
            + "},"
        )
    lines += ["}};", "inline constexpr std::array<Row, 6> Rows{{"]
    for family in FAMILIES:
        row = document["rows"][family]
        cells = [""] * (row["columns"][0] - 1) + row["cells"]
        lines.append(
            "    {"
            + quoted(family)
            + ", "
            + str(row["ordinal"])
            + ", "
            + str(row["columns"][0])
            + ", {"
            + ", ".join(map(quoted, cells))
            + "}},"
        )
    lines += ["}};", "// clang-format on", "} // namespace seven_suns_stock", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = json.loads((ROOT / FIXTURE_PATH).read_text(encoding="utf-8"))
    header = stockHeader(document)
    path = ROOT / HEADER_PATH
    if args.check:
        require(path.is_file() and path.read_text(encoding="utf-8") == header, "Stale finite stock header")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "items": 97,
                "rows": 6,
                "sourceAbilitiesEstablished": False,
                "originalParity": False,
                "headerSha256": hashlib.sha256(header.encode()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
