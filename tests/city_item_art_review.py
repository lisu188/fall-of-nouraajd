# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent inverse of the reviewed item and container animation substitutions."""

import hashlib

PREFIX = "maps/baldursGate/images/"
CHEST_IDS_SHA256 = "93d181cc1719210ac7f916447307ea2e4a61bd695b024a03ddcdd28f64d9364e"


def reviewedItemPaths():
    ordinary = set(range(10, 69)) - {52, 61, 65}
    return {
        **{f"BOOK{number:02}": ("items/ordinaryBook", "images/items/scroll") for number in ordinary},
        "BOOK08": ("items/understandingTomeV2", "images/items/scroll"),
        "MISC54": ("items/wrappedChildRemainsV2", "images/items/scroll"),
        "MISC55": ("items/carriedDuke", "images/items/scroll"),
        "MAGE04": ("items/questRing", "images/items/quest/preciousAmulet"),
        "POTN20": ("items/antidoteBottle", "images/items/potions/life"),
        "POTN47": ("items/antidoteBottle", "images/items/potions/life"),
    }


def normalizeItemAnimations(config):
    expected = reviewedItemPaths()
    seen_items = []
    chests = []
    for row in config.values():
        props = row.get("properties", {})
        code = props.get("plugin_citySourceItem")
        animation = props.get("animation", "")
        if code in expected:
            relative, original = expected[code]
            if animation != PREFIX + relative:
                raise ValueError("Unexpected city item animation for " + code)
            props["animation"] = original
            seen_items.append(code)
        elif animation == PREFIX + "interactions/woodenChest":
            if row["class"] != "BaldursGateContainer" or not props.get("sourceContainer"):
                raise ValueError("City chest artwork attached to a non-container")
            chests.append(props["sourceContainer"])
            props["animation"] = "images/misc/chest"
        elif animation.startswith((PREFIX + "items/", PREFIX + "interactions/")):
            raise ValueError("Unreviewed city interaction animation: " + animation)
    if sorted(seen_items) != sorted(expected):
        raise ValueError("City item consumer identities changed")
    if hashlib.sha256("\n".join(sorted(chests)).encode()).hexdigest() != CHEST_IDS_SHA256:
        raise ValueError("City chest identities differ from the fingerprinted ARE type-2 records")
