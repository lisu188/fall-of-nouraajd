#!/usr/bin/env python3
# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile factual city geometry into native resources; no original artwork or dialogue is emitted."""

import argparse
from collections import deque
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/baldurs_gate_city_source.json"
QUESTS = ROOT / "tests/fixtures/baldurs_gate_city_quests.json"
CUSTODY_SOURCE = ROOT / "tests/fixtures/baldurs_gate_city_prison_source.json"
POISON_DIALOGUE = ROOT / "tests/fixtures/baldurs_gate_city_poison_dialogue.json"
POISON_FOLLOWUP = ROOT / "tests/fixtures/baldurs_gate_city_poison_followup.json"
POISON_TEXT = ROOT / "tests/fixtures/baldurs_gate_city_poison_semantic.json"
MERCHANT_STOCK_SOURCE = ROOT / "tests/fixtures/baldurs_gate_seven_suns_stock.json"
try:
    from scripts.build_baldurs_gate_city_dialogs import prepareStores, questDialogRows, storeDialogRows
    from scripts.build_baldurs_gate_city_relocations import buildRelocations
    from scripts.build_baldurs_gate_city_regions import buildRegions
    from scripts.build_baldurs_gate_city_custody import custodyDefinitions, prepareCustodyActors
    from scripts.build_baldurs_gate_city_poison import preparePoisonSource
    from scripts.build_baldurs_gate_merchant_stock import stockDefinitions
except ModuleNotFoundError:
    from build_baldurs_gate_city_dialogs import prepareStores, questDialogRows, storeDialogRows
    from build_baldurs_gate_city_relocations import buildRelocations
    from build_baldurs_gate_city_regions import buildRegions
    from build_baldurs_gate_city_custody import custodyDefinitions, prepareCustodyActors
    from build_baldurs_gate_city_poison import preparePoisonSource
    from build_baldurs_gate_merchant_stock import stockDefinitions

# Supporting EE BASE facts: each CRE SHA256 equals the existing source fixture.
# These are visual adaptations; original-game parity remains unestablished.
CITY_APPEARANCE_SOURCE_SHA256 = "a20a7e9bfc63fe83654bdb8f1ec057a03498192a7b62a6be0ab9c7f2b495b2da"
CITY_APPEARANCE_SOURCE_GROUPS = {
    ("BASILISK_GREATER", "MALE"): "BASILNAD".split(),
    ("BAT_INSIDE", "MALE"): "BAT_DOOR".split(),
    ("BAT_OUTSIDE", "MALE"): "BAT_OUT".split(),
    ("BEGGAR_MAN", "MALE"): "BEGGBA".split(),
    ("BOY", "MALE"): "BOYBA1 BOYBA1_A BOYBA1_C BOYBA2 BOYBA3_A BOYBA3_B VARCI".split(),
    ("CARRION_CRAWLER", "MALE"): "CARRIO".split(),
    ("CAT", "MALE"): "CATP".split(),
    ("CHICKEN", "MALE"): "CHICKER".split(),
    ("CLERIC_FEMALE_ELF", "FEMALE"): "AGNASI TENYA2 VOLTIN".split(),
    ("CLERIC_FEMALE_HUMAN", "FEMALE"): "PUMBER2 PUMBERL SHAELL TAMOKO WUDEI".split(),
    ("CLERIC_MALE_DWARF", "MALE"): "SAILAL".split(),
    ("CLERIC_MALE_ELF", "MALE"): "GAXIR ORDULI".split(),
    ("CLERIC_MALE_GNOME", "MALE"): "QUAYLE TIAX".split(),
    ("CLERIC_MALE_HUMAN", "MALE"): (
        "BELAND BENJY BRATHL CHANTH CHIMP5 DEAD2 FERGUS FFHUNT FLAM10 FLAM11 FLAM12 FLAM13 FLAM6 FLAM7 FLAM9 "
        "FLAME1 FLAME2 FLAME3 FLAME4 FLAMGATE KENT PGOND PRIHEL RASHAD SAILNED TREMAI WATCHM"
    ).split(),
    ("DOOM_GUARD", "MALE"): "HELMHO".split(),
    ("DOOM_GUARD", "SUMMONED"): "STALKE".split(),
    ("DOPPLEGANGER", "MALE"): "DOPPSS".split(),
    ("ELMINSTER", "MALE"): "ELMIN5".split(),
    ("FAT_MAN", "MALE"): (
        "BARSLIM BART0133 BART0720 BART10 BART11 BART12 BART15 BART16 BART6 BART7 BART8 BART9 DOPMER DOPPSM "
        "DUN INNKE3 IRONM2 IRONM3 IRONM4 IRONME MALTZ MERC0706 MERLEA SAILDAN TRIADO"
    ).split(),
    ("FAT_WOMAN", "FEMALE"): "EMITAR EMITAR2 EMITAR3 GLANMA".split(),
    ("FIGHTER_FEMALE_DWARF", "FEMALE"): "PHEIRK".split(),
    ("FIGHTER_FEMALE_ELF", "FEMALE"): "NORALE".split(),
    ("FIGHTER_FEMALE_HALFLING", "FEMALE"): "SEWERF5".split(),
    ("FIGHTER_MALE_DWARF", "MALE"): "FENTEN".split(),
    ("FIGHTER_MALE_ELF", "MALE"): "ATTSLIM FARLUC VAIL".split(),
    ("FIGHTER_MALE_HALFLING", "MALE"): "SAILFIN".split(),
    ("FIGHTER_MALE_HUMAN", "MALE"): (
        "AASIM ACHEN ALAI ALDETH ANGELO BANDITCY BELT BORK BRANDI CAILAN CARSTO CYDERM DELTAN DOOMGU DRATAN "
        "ELKART ENTAR GALDOR GARDUS GORPEL HASEO HOUSG3 HOUSG4 HOUSG5 HOUSG6 IRLENT IRON12 IRON13 IRON14 "
        "JACIL JARDAK JHASSO LOBAR LUSSEL MERCHG NANTRI PHANDA RAHVIN RANCE SAILJOS SCAR TURPIN ZHALIM"
    ).split(),
    ("GHAST", "MALE"): "GHAST SEWERF3".split(),
    ("GIRL", "FEMALE"): "GIRBA1 GIRBA2 GIRBA3 GIRBA3_A GIRBA3_C LAERTA LOUISE".split(),
    ("GRAY_OOZE", "MALE"): "JELLGR".split(),
    ("HALF_OGRE", "MALE"): "TAZOK2".split(),
    ("HARLOT_FIGHTER", "FEMALE"): "ITHTYL".split(),
    ("HARLOT_WOMAN", "FEMALE"): "PROST2 PROST3 PROST4 PROST5 PROST6 PROST7 PROST8 QUENAS".split(),
    ("HOBGOBLIN", "MALE"): "HOBELITE".split(),
    ("KOBOLD", "MALE"): "KOBCOMM RATCHI".split(),
    ("KOBOLD_XVART", "MALE"): "DESTUS".split(),
    ("MAGE_FEMALE_ELF", "FEMALE"): "CYTHAN SHALDR".split(),
    ("MAGE_FEMALE_HUMAN", "FEMALE"): "BRIELB DELORN HELSHA ITHMEE LIIA NEMPHR VAYYA".split(),
    ("MAGE_MALE_ELF", "MALE"): "ENTILL GERVIS".split(),
    ("MAGE_MALE_HUMAN", "MALE"): (
        "ARKION DEGROD DIVINE FAIZAH HALBAZ NIEMAI OBERAN OULAM RAGEFA RAMAZI RESAR SEMAJ SUNIN WHEBER "
        "WILLIAM YAGO ZORL"
    ).split(),
    ("NOBLE_MAN", "MALE"): (
        "FELONI NOBL11 NOBL12 NOBL14 NOBLBA_A NOBLBA_B NOBLBA_C NOBLBA_D NOBLBA_E NOBLPA NOBLPA1 NOBLPA2 "
        "NOBLPA3 NOBLPA4 NOBLPA5 REGINA TARTUS"
    ).split(),
    ("NOBLE_WOMAN", "FEMALE"): (
        "BRILLA HANNAH NOBW5 NOBW7 NOBW8 NOBW9 NOBWBA NOBWBA_A NOBWBA_D NOBWBA_E NOWBAX_A NOWBAX_B NOWBAX_C "
        "NOWBAX_D NOWBAX_E"
    ).split(),
    ("OGRE", "MALE"): "GORF LARZE SEWERF4".split(),
    ("OGRE_MAGE", "MALE"): "OGREMA OGREMA_A OGREMA_B OGREMA_C OGREMA_D OGRMBA".split(),
    ("OGRILLON", "MALE"): "SEWERF1".split(),
    ("PEASANT_MAN", "MALE"): (
        "BORIN CAUTER CONNOL DEAD DEAD1 DILLAR GARDEN KERRAC KESHEE MCOOK2 MCOOK3 MCOOK4 MCOOK5 MICK MTOB2 "
        "MTOB3 MTOB6 MTOB7 MTOB8 MTOB9 MTOWBA MTOWBA_A MTOWBA_B MTOWBA_C MTOWBA_D MTOWBA_E MTOWWON1 MTOWWON2 "
        "MTWSLIM MTWSLIM2 MTWSLIM3 NIKOLA NIVEK OCELLI RODNIM SAILNEW SERVA2 SERVAN SEWERC SHEP TICK WAITER"
    ).split(),
    ("PEASANT_WOMAN", "FEMALE"): (
        "FCOOK3 FECOOK FRIWEN FTOWB5 FTOWB6 FTOWB7 FTOWBA FTOWBA_A FTOWBA_B FTOWBA_C FTOWBA_D FTOWBA_E LANTAN "
        "MAPLE MTOWWON3 SANADAL VIVIEN"
    ).split(),
    ("RAT", "MALE"): "RAT".split(),
    ("SAREVOK", "MALE"): "SAREVO SAREVO2".split(),
    ("SEAGULL", "MALE"): "SEAGUL".split(),
    ("SIRINE", "FEMALE"): "ABELA LARRIA".split(),
    ("SKELETON", "MALE"): "SKELWA SKELWA02 SKELWA03".split(),
    ("SLAVE", "MALE"): "SHVERT".split(),
    ("SLEEPING_DWARF", "MALE"): "SLEEPDW".split(),
    ("SLEEPING_FAT_MAN_HUMAN", "MALE"): "SLEEPFAT".split(),
    ("SLEEPING_MAN_ELF", "MALE"): "SLEEPEL".split(),
    ("SLEEPING_MAN_HALFLING", "MALE"): "SLEEPHAL".split(),
    ("SLEEPING_MAN_HUMAN", "MALE"): "DELTAN2 GANTOL1 SLEEPMH WINSKI2".split(),
    ("SLEEPING_WOMAN_HUMAN", "FEMALE"): "PROSLAY SLEEPFH VOLETA".split(),
    ("SLIME_MUSTARD", "MALE"): "JELLMUL JELLYMU".split(),
    ("SLIME_OCHRE", "MALE"): "JELLOC".split(),
    ("SLIME_OLIVE", "MALE"): "JELLYGR JELLYGR2 SCHLUM".split(),
    ("SPIDER_GIANT", "MALE"): "SPIDGI".split(),
    ("SPIDER_HUGE", "MALE"): "SPIDHU".split(),
    ("SPIDER_PHASE", "MALE"): "SPIDPH".split(),
    ("STATIC_BEGGAR_MAN", "MALE"): "BEGBAX_A BEGBAX_B BEGBAX_C BEGBAX_D BEGGBAX".split(),
    ("STATIC_BOY", "MALE"): "BOYBAX BOYBAX_A BOYBAX_B BOYBAX_C EURIC".split(),
    ("STATIC_FAT_MAN", "MALE"): "FATMAN LUCKY SHOP01 SHOP03 SHOP04 SHOP05 SHOP06 SHOP07 SHOP08".split(),
    ("STATIC_FAT_WOMAN", "FEMALE"): "FATWOM".split(),
    ("STATIC_GIRL", "FEMALE"): "GIRBAX_A GIRBAX_B GIRBAX_C GIRBAX_D GIRBAX_E PETRIN".split(),
    ("STATIC_HARLOT_WOMAN", "FEMALE"): "PRSBAX_A PRSBAX_B PRSBAX_C".split(),
    ("STATIC_NOBLE_MAN", "MALE"): "NOBBAX_A NOBBAX_B NOBBAX_C NOBBAX_D NOBBAX_E".split(),
    ("STATIC_PEASANT_MAN", "MALE"): "MTOWBAX MTWBAX_A MTWBAX_B MTWBAX_C MTWBAX_D MTWBAX_E".split(),
    ("STATIC_PEASANT_MAN_CHAIR", "MALE"): "MTOWBASC".split(),
    ("STATIC_PEASANT_MAN_MATTE", "MALE"): "MTOWBASN MTOWBESN".split(),
    ("STATIC_PEASANT_MAN_STOOL", "MALE"): "MTOWBAST".split(),
    ("STATIC_PEASANT_WOMAN", "FEMALE"): "FTOWBAX FTWBAX_A FTWBAX_B FTWBAX_C FTWBAX_D FTWBAX_E".split(),
    ("STATIC_PEASANT_WOMAN_CHAIR", "FEMALE"): "FTOWBASC".split(),
    ("STATIC_PEASANT_WOMAN_MATTE", "FEMALE"): "FTOWBASN".split(),
    ("STATIC_SLAVE", "MALE"): "PRISON".split(),
    ("THIEF_FEMALE_ELF", "FEMALE"): "ALYTH RINNIE THIEFF WIVEN".split(),
    ("THIEF_FEMALE_HALFLING", "FEMALE"): "ALORA".split(),
    ("THIEF_FEMALE_HALFLING_LOW", "FEMALE"): "NADINE".split(),
    ("THIEF_FEMALE_HUMAN", "FEMALE"): "BLACKL DESRET JALANT KRYSTI NILA SILENC SKIE".split(),
    ("THIEF_MALE_DWARF", "MALE"): "BREVLI NADARI QUINN".split(),
    ("THIEF_MALE_ELF", "MALE"): "BHEREN CORDYR DRELIK".split(),
    ("THIEF_MALE_GNOME", "MALE"): "NEB".split(),
    ("THIEF_MALE_HALFLING", "MALE"): "BELLAM HARBOR NELIK".split(),
    ("THIEF_MALE_HUMAN", "MALE"): (
        "ALATOS DENKOD DIYAB ELDOTH FORTHE GAMES2 GAMES3 GAMES4 GAMES5 HUSAM LOTHAN MAREK MAREK1 MICHAE "
        "MRSHADE NAAMAN NARLEN NIKLOS NORTUA REDEDG SLYTHE TAXEK THALDO THIEF THIEFG"
    ).split(),
    ("THIEF_MALE_HUMAN_LOW", "MALE"): "THIEFM".split(),
    ("ZOMBIE", "MALE"): "GHORAK SEWERF2".split(),
}
CITY_BODY_APPEARANCES = {
    "BAT_INSIDE": "bat",
    "BAT_OUTSIDE": "bat",
    "CAT": "cat",
    "CHICKEN": "chicken",
    "RAT": "rat",
    "SEAGULL": "seagull",
    "SKELETON": "skeleton",
    "GHAST": "images/monsters/fenGhoul",
    "ZOMBIE": "images/monsters/fenGhoul",
    "CARRION_CRAWLER": "carrionCrawler",
    "GRAY_OOZE": "slime",
    "SLIME_MUSTARD": "slime",
    "SLIME_OLIVE": "slime",
    "SLIME_OCHRE": "slime",
    "SPIDER_GIANT": "images/monsters/lengSpider",
    "SPIDER_HUGE": "images/monsters/lengSpider",
    "SPIDER_PHASE": "images/monsters/lengSpider",
    "OGRE": "ogre",
    "HALF_OGRE": "ogre",
    "OGRE_MAGE": "ogreMage",
    "OGRILLON": "ogre",
    "HOBGOBLIN": "hobgoblin",
    "KOBOLD": "kobold",
    "KOBOLD_XVART": "xvart",
    "DOPPLEGANGER": "doppelganger",
    "DOOM_GUARD": "images/monsters/barrowKnight",
    "SAREVOK": "images/monsters/barrowKnight",
    "BASILISK_GREATER": "basilisk",
    "SIRINE": "sirine",
}
CITY_APPEARANCE_PREFIX = "maps/baldursGate/images/npc/"
CITY_BUILDING_APPEARANCES = {
    "timberHouse": (
        "cityAr0100Portal4",
        "cityAr0100Portal5",
        "cityAr0100Portal9",
        "cityAr0600Portal1",
        "cityAr0600Portal9",
        "cityAr0700Portal11",
        "cityAr0800Portal9",
        "cityAr1200Portal8",
        "cityAr1200Portal11",
        "cityAr1200Portal12",
        "cityAr1300Portal2",
        "cityAr1300Portal18",
    ),
    "stoneTownhouse": (
        "cityAr0100Portal1",
        "cityAr0100Portal8",
        "cityAr0700Portal20",
        "cityAr0700Portal5",
        "cityAr0700Portal6",
    ),
    "merchantShop": (
        "cityAr0800Portal8",
        "cityAr0800Portal11",
        "cityAr0800Portal12",
        "cityAr1100Portal3",
        "cityAr1100Portal6",
        "cityAr1100Portal13",
        "cityAr1100Portal14",
        "cityAr1300Portal6",
        "cityAr1300Portal8",
        "cityAr1300Portal9",
    ),
    "innTavern": (
        "cityAr0100Portal7",
        "cityAr0200Portal9",
        "cityAr0300Portal3",
        "cityAr0300Portal4",
        "cityAr0700Portal3",
        "cityAr0700Portal4",
        "cityAr0800Portal5",
        "cityAr0800Portal10",
        "cityAr1100Portal2",
        "cityAr1100Portal8",
        "cityAr1200Portal7",
        "cityAr1300Portal1",
    ),
    "magicShop": ("cityAr0800Portal6",),
    "temple": ("cityAr0200Portal1", "cityAr0600Portal7", "cityAr1200Portal5"),
    "cityGate": ("cityAr0800Boundary18",),
    "guardBarracks": ("cityAr1100Portal1",),
    "ducalPalace": ("cityAr0200Portal13",),
    "guildhall": ("cityAr1100Portal5", "cityAr1100Portal4", "cityAr0300Portal6"),
    "dockWarehouse": ("cityAr1200Portal9", "cityAr1200Portal10", "cityAr1300Portal11", "cityAr0700Portal2"),
}
CITY_BUILDING_ASSETS = (*CITY_BUILDING_APPEARANCES, "ruinedTemple")
CITY_TILE_ASSETS = (
    "streetCobble",
    "flagstonePaving",
    "packedEarth",
    "grassCourtyard",
    "woodenFloor",
    "marbleFloor",
    "dungeonFlagstone",
    "sewerWalkway",
    "sewerWater",
    "riverWater",
    "stoneWall",
    "rockWall",
)
CITY_TILE_APPEARANCES = {"cityStreetTile": "streetCobble", "cityWallTile": "stoneWall"}


def applyCityEnvironmentAppearances(source, config):
    assignments = {}
    for appearance, names in CITY_BUILDING_APPEARANCES.items():
        for name in names:
            row = config.get(name, {})
            properties = row.get("properties", {})
            area = source["areas"].get(properties.get("sourceArea"), {})
            destination = source["areas"].get(properties.get("destinationArea"), {})
            gate = appearance == "cityGate"
            if (
                name in assignments
                or row.get("class") != "BaldursGatePortal"
                or area.get("classification") != "exterior"
                or (not gate and destination.get("classification") != "interior")
                or (
                    gate
                    and (properties.get("destinationArea") != "AR0900" or properties.get("sourceDirection") != "east")
                )
            ):
                raise ValueError("Unreviewed City building appearance target: " + name)
            assignments[name] = "maps/baldursGate/images/buildings/" + appearance
    for name, appearance in CITY_TILE_APPEARANCES.items():
        if config.get(name, {}).get("class") != "CTile":
            raise ValueError("Unreviewed City tile appearance target: " + name)
        assignments[name] = "maps/baldursGate/images/tiles/" + appearance
    for name, animation in assignments.items():
        config[name]["properties"]["animation"] = animation
    return [
        {"path": "images/" + directory + "/" + appearance + ".png", "kind": "file"}
        for directory, appearances in (
            ("buildings", CITY_BUILDING_ASSETS),
            ("tiles", CITY_TILE_ASSETS),
            ("interactions", ("closedDoor", "openDoor")),
        )
        for appearance in appearances
    ]


def cityActorAppearance(properties, source, appearances):
    code = properties["sourceCreature"]
    creature = source["creatures"][code]
    if code not in appearances:
        raise ValueError("Unaudited City appearance for " + code)
    animation, sex = appearances[code]
    if animation in CITY_BODY_APPEARANCES:
        asset = CITY_BODY_APPEARANCES[animation]
        return asset if asset.startswith("images/") else CITY_APPEARANCE_PREFIX + asset
    if animation in {"BOY", "STATIC_BOY", "GIRL", "STATIC_GIRL"}:
        return CITY_APPEARANCE_PREFIX + ("girl" if "GIRL" in animation else "boy")
    if sex not in {"MALE", "FEMALE"}:
        raise ValueError("Unsupported source appearance sex for " + code)
    suffix = "Woman" if sex == "FEMALE" else "Man"
    class_id, race_id = creature["class"], creature["race"]
    if class_id in {156, 211, 213} or properties.get("custodyRole") in {"patrol", "escort", "angelo"}:
        role = "guard"
    elif race_id in {2, 4, 5, 6}:
        role = {2: "elf", 4: "dwarf", 5: "halfling", 6: "gnome"}[race_id]
    elif "NOBLE" in animation:
        role = "noble"
    elif class_id in {3, 8, 11, 14, 15}:
        role = "priest"
    elif class_id in {1, 7, 13, 19}:
        role = "mage"
    elif class_id in {4, 9}:
        role = "rogue"
    elif properties.get("sourceStore", "").startswith("TEM"):
        role = "priest"
    elif properties.get("sourceStore") or properties.get("sourceStores"):
        role = "merchant"
    elif class_id in {2, 6, 12, 129} or animation.startswith("FIGHTER_"):
        role = "fighter"
    elif animation.startswith("THIEF_"):
        role = "rogue"
    elif animation.startswith("CLERIC_"):
        role = "priest"
    elif animation.startswith("MAGE_") or animation == "ELMINSTER":
        role = "mage"
    else:
        role = "commoner"
    return CITY_APPEARANCE_PREFIX + role + suffix


def applyCityAppearances(source, config):
    fingerprint = hashlib.sha256(
        json.dumps(
            {code: row["sha256"] for code, row in source["creatures"].items()},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if fingerprint != CITY_APPEARANCE_SOURCE_SHA256:
        raise ValueError("City appearance evidence no longer matches the source CRE fingerprints")
    appearances = {}
    for appearance, codes in CITY_APPEARANCE_SOURCE_GROUPS.items():
        for code in codes:
            if code in appearances:
                raise ValueError("Duplicate source appearance " + code)
            appearances[code] = appearance
    assets = set()
    for row in config.values():
        properties = row.get("properties", {})
        if row.get("class") not in {"CCreature", "BaldursGateContainer"} or not properties.get("sourceCreature"):
            continue
        animation = (
            CITY_APPEARANCE_PREFIX + "corpse"
            if row["class"] == "BaldursGateContainer"
            else cityActorAppearance(properties, source, appearances)
        )
        properties["animation"] = animation
        if animation.startswith(CITY_APPEARANCE_PREFIX):
            assets.add(animation.removeprefix("maps/baldursGate/") + ".png")
    return [{"path": path, "kind": "file"} for path in sorted(assets)]


LANDMARKS = {
    "AR0002": "Temple of Helm",
    "AR0101": "Silvershield estate: ground floor",
    "AR0102": "Silvershield estate: upper floor",
    "AR0103": "Splurging Sturgeon: ground floor",
    "AR0104": "Splurging Sturgeon: upper floor",
    "AR0105": "Blade and Stars: ground floor",
    "AR0106": "Blade and Stars: second floor",
    "AR0107": "Blade and Stars: third floor",
    "AR0108": "Ducal Palace: ground floor",
    "AR0109": "Ducal Palace: second floor",
    "AR0110": "Ducal Palace: third floor",
    "AR0111": "Ducal Palace: basement",
    "AR0114": "Blushing Mermaid: ground floor",
    "AR0115": "Blushing Mermaid: upper floor",
    "AR0116": "Helm and Cloak: ground floor",
    "AR0117": "Helm and Cloak: upper front",
    "AR0118": "Helm and Cloak: upper rear",
    "AR0119": "Three Old Kegs: ground floor",
    "AR0120": "Three Old Kegs: second floor",
    "AR0121": "Three Old Kegs: third floor",
    "AR0126": "Ragefast's house",
    "AR0127": "Merchant League: ground floor",
    "AR0128": "Merchant League: second floor",
    "AR0129": "Merchant League: third floor",
    "AR0130": "Hall of Wonders",
    "AR0131": "Temple of Gond",
    "AR0132": "Lady's House",
    "AR0133": "Low Lantern: main deck",
    "AR0134": "Low Lantern: first lower deck",
    "AR0135": "Low Lantern: second lower deck",
    "AR0136": "Low Lantern: third lower deck",
    "AR0137": "Ramazith's tower: ground floor",
    "AR0138": "Ramazith's tower: top floor",
    "AR0139": "Ramazith's tower: second floor",
    "AR0140": "Ramazith's tower: third floor",
    "AR0141": "Ramazith's tower: fourth floor",
    "AR0142": "Ramazith's tower: fifth floor",
    "AR0143": "Oberan's estate: ground floor",
    "AR0144": "Oberan's estate: second floor",
    "AR0145": "Oberan's estate: third floor",
    "AR0148": "Guild front house: east",
    "AR0149": "Shrine of Ilmater",
    "AR0150": "Guild front house: west",
    "AR0151": "Guild front house: west center",
    "AR0152": "Guild front house: east center",
    "AR0153": "Thieves' Guild",
    "AR0154": "Keexie's tavern: ground floor",
    "AR0157": "Quinn's house: ground floor",
    "AR0158": "Quinn's house: upper floor",
    "AR0161": "Degrodel's house",
    "AR0162": "Laerta and Louise's house",
    "AR0167": "Pheirkas's house: ground floor",
    "AR0168": "Pheirkas's house: upper floor",
    "AR0171": "Keexie's tavern: upper floor",
    "AR0307": "Counting House: ground floor",
    "AR0308": "Counting House: upper floor",
    "AR0601": "Seven Suns: ground floor",
    "AR0602": "Seven Suns: upper floor",
    "AR0603": "Seven Suns: cellar",
    "AR0606": "Flaming Fist: cells",
    "AR0607": "Flaming Fist: ground floor",
    "AR0608": "Flaming Fist: upper floor",
    "AR0609": "Temple of Umberlee",
    "AR0611": "Iron Throne: cellar",
    "AR0612": "Iron Throne: second floor",
    "AR0613": "Iron Throne: third floor",
    "AR0614": "Iron Throne: fourth floor",
    "AR0615": "Iron Throne: fifth floor",
    "AR0616": "Iron Throne: ground floor",
    "AR0617": "Tremain's house: ground floor",
    "AR0618": "Tremain's house: upper floor",
    "AR0619": "Fenten's house: ground floor",
    "AR0620": "Fenten's house: upper floor",
    "AR0621": "Iron Throne: roof",
    "AR0702": "Harbormaster",
    "AR0703": "Sorcerous Sundries: ground floor",
    "AR0704": "Sorcerous Sundries: upper floor",
    "AR0705": "Elfsong Tavern: ground floor",
    "AR0706": "Elfsong Tavern: upper floor",
    "AR0715": "Nadine's house: ground floor",
    "AR0716": "Nadine's house: upper floor",
    "AR0719": "Felonius Gist's house",
    "AR0720": "Drakon Tavern",
    "AR0721": "Chicken warehouse",
    "AR0724": "Market tent: dice",
    "AR0725": "Market tent: games",
    "AR0726": "Diviner's tent",
    "AR0803": "Maltz's shop: ground floor",
    "AR0804": "Maltz's shop: upper floor",
    "AR0805": "Arkion's house: ground floor",
    "AR0806": "Arkion's house: upper floor",
    "AR0809": "Silence's shop",
    "AR0810": "Lucky Aello's shop",
    "AR0813": "Nemphre's house: ground floor",
    "AR0814": "Nemphre's house: upper floor",
    "AR1109": "Phandalyn's tavern: ground floor",
    "AR1111": "Sunin's house",
    "AR1112": "Weapons shop: southwest",
    "AR1113": "Ye Olde Inn: ground floor",
    "AR1114": "Ye Olde Inn: upper floor",
    "AR1115": "Potion shop: west",
    "AR1116": "Weapons shop: south",
    "AR1117": "Potion shop: south",
    "AR1207": "Basilisk warehouse",
    "AR1208": "Noralee's warehouse",
    "AR1209": "Larriaz's house",
    "AR1211": "Ghorak's house: ground floor",
    "AR1212": "Ghorak's house: upper floor",
    "AR1213": "Cordyr's house: ground floor",
    "AR1214": "Cordyr's house: upper floor",
    "AR1215": "Jopalin's tavern",
    "AR1302": "Well-Adjusted Al's shop",
    "AR1303": "Nadarin's warehouse",
    "AR1312": "Gantolandan's house: ground floor",
    "AR1313": "Gantolandan's house: upper floor",
    "AR1320": "Southeastern shop",
}
DESTINATION = ROOT / "res/maps/baldursGate"
SOURCE_PIXELS_PER_CELL = 64
BLOCKED_TERRAINS = {0, 8, 10, 12, 13, 14}
WARD_ROWS = (("AR0100", "AR0200", "AR0300"), ("AR0600", "AR0700", "AR0800"), ("AR1100", "AR1200", "AR1300"))


def identity(source_id):
    return "city" + "".join(word[:1].upper() + word[1:].lower() for word in source_id.replace("#", " ").split())


CITY_JSON_PREFIX = "city-json:"


def decodeCityData(encoded):
    return json.loads(encoded.removeprefix(CITY_JSON_PREFIX))


def protectCityData(value):
    if not isinstance(value, str):
        return value
    try:
        decoded = json.loads(value)
    except ValueError:
        return value
    return CITY_JSON_PREFIX + value if isinstance(decoded, (list, dict)) else value


def protectCityDefinitions(document):
    pending = [document]
    while pending:
        row = pending.pop()
        if isinstance(row, dict):
            properties = row.get("properties")
            if isinstance(properties, dict):
                for key, value in tuple(properties.items()):
                    properties[key] = protectCityData(value)
            pending.extend(row.values())
        elif isinstance(row, list):
            pending.extend(row)
    return document


def sevenSunsMerchantProperties(name, creature, source_creature):
    lineages = ("cityAr0601Actor1", "cityAr0601Actor3", "cityAr0602Actor1", "cityAr0602Actor2")
    if name not in lineages:
        return {}
    if creature != "DOPMER" or source_creature.get("allegiance") != 128:
        raise ValueError("Reviewed Seven Suns merchant allegiance changed")
    return {"sourceAllegiance": source_creature["allegiance"]}


def definition(class_id, **properties):
    return {"class": class_id, "properties": {key: protectCityData(value) for key, value in properties.items()}}


def nativeItem(source_id, item):
    """Native gear conversion; source-specific abilities remain explicit, unaudited obligations."""
    item_type = item.get("item_type", 0)
    item_flags = item.get("flags")
    item_flags_known = type(item_flags) is int and 0 <= item_flags <= 0xFFFFFFFF
    immovable = item_flags_known and not bool(item_flags & 4)
    enchantment = min(5, max(0, item.get("enchantment", 0)))
    equipped_effect_count = item.get("equipped_effect_count")
    equipped_effects_known = type(equipped_effect_count) is int and 0 <= equipped_effect_count <= 65535
    class_id, animation, bonus = "CItem", "images/items/scroll", {}
    if item_type in range(15, 31):
        class_id = "CSmallWeapon" if item_type in {16, 19} else "CWeapon"
        animation = "images/items/weapons/dagger" if item_type in {16, 19, 24} else "images/items/weapons/sword"
        if item_type in {18, 26, 35}:
            animation = "images/items/weapons/staff"
        bonus = {"dmgMin": 4 + enchantment * 2, "dmgMax": 8 + enchantment * 3, "hit": enchantment * 3}
    elif item_type in {2, 32}:
        class_id, animation = "CArmor", (
            "images/items/armors/robe" if item_type == 32 else "images/items/armors/platearmor"
        )
        bonus = {"armor": 10 + enchantment * 10}
    elif item_type in {3, 4, 6, 7, 12}:
        class_id, animation = {
            3: ("CBelt", "images/items/belts/undestructiblebelt"),
            4: ("CBoots", "images/items/boots/eradicatorsboots"),
            6: ("CGloves", "images/items/gloves/glovesoftheassasin"),
            7: ("CHelmet", "images/items/helmets/crownofnightmares"),
            12: ("CShield", "images/items/armors/platearmor"),
        }[item_type]
        bonus = {"armor": 5 + enchantment * 10}
    elif item_type in {1, 10, 34}:
        animation = "images/items/quest/preciousAmulet"
    elif item_type == 8:
        animation = "images/items/quest/ironKey"
    elif item_type == 9:
        animation = "images/items/potions/life"
    props = {
        "label": item.get("displayName") or source_id,
        "animation": animation,
        "description": "A city possession converted to native item rules. Its source identity and ownership persist.",
        "plugin_citySourceItem": source_id,
        "plugin_cityItemType": item_type,
        "plugin_cityTradeable": not bool(item.get("flags", 0) & 2048) and not immovable,
        "plugin_cityValue": max(0, item.get("price", item.get("base_value", 1))),
        "plugin_citySourceFlags": item.get("flags", 0),
        "plugin_cityLore": item.get("lore", 0),
        "plugin_cityStackSize": item.get("stack_size", 1),
        "plugin_cityEquippedEffectsStatus": (
            ("positive" if equipped_effect_count else "zero") if equipped_effects_known else "unknown"
        ),
        "plugin_cityAbilitiesPending": bool(
            item.get("ability_count", 0)
            or not equipped_effects_known
            or equipped_effect_count
            or item.get("flags", 0) & 64
        ),
        "tags": ["cursed"] if item.get("flags", 0) & 16 else [],
    }
    if item_flags_known:
        props.update(
            plugin_cityItemFlags=item_flags,
            plugin_cityItemImmovable=immovable,
            plugin_cityUndroppable=immovable,
        )
    if source_id == "BOOK08":
        class_id = "BaldursGateUnderstandingTome"
    if bonus:
        props["bonus"] = definition("CStats", **bonus)
    if item.get("flags", 0) & 2 and class_id in {"CWeapon", "CSmallWeapon"}:
        props["coveredSlots"] = ["LeftHand"]
    return definition(class_id, **props)


def doorProperties(area_id, index, door):
    difficulty = door["lock_difficulty"]
    return {
        "sourceDoor": f"{area_id}#door{index}",
        "sourceDoorName": door["name"],
        "sourceDoorFlags": door["flags"],
        "sourceKey": door["key"],
        "sourceScript": door["script"],
        "sourceLockDifficulty": difficulty,
        "locked": bool(door["flags"] & 2),
        "open": bool(door["flags"] & 1),
        "forbidClosing": bool(door["flags"] & 32),
        "lockAgility": 18 if difficulty >= 80 else 16 if difficulty >= 40 else 12,
        "forceStrength": 14 if difficulty >= 60 else 12,
        "forbidPicking": difficulty >= 100,
        "forbidForcing": difficulty >= 100,
        "trapped": bool(door["trapped"]),
        "sourceTrapDetection": door["trap_detection"],
        "sourceTrapRemoval": door["trap_removal"],
        "sourceDoorGeometry": json.dumps(
            {key: door[key] for key in ("open_polygon", "closed_polygon", "open_impeded", "closed_impeded")},
            separators=(",", ":"),
        ),
    }


def rowsFromRuns(search):
    result = []
    for row in search["terrainRowsRle"]:
        values = []
        for count, terrain in zip(row[::2], row[1::2]):
            values.extend([terrain] * count)
        if len(values) != search["width"]:
            raise ValueError("Malformed factual search row")
        result.append(values)
    return result


def layoutAreas(areas):
    result, width, height = {}, 224, 192
    x_offsets = [4, 78, 154]
    y_offsets = [4, 64, 126]
    for row, names in enumerate(WARD_ROWS):
        for column, area_id in enumerate(names):
            size = areas[area_id]["dimensions"]
            result[area_id] = [x_offsets[column], y_offsets[row], 0, math.ceil(size[0] / 64), math.ceil(size[1] / 64)]
    x, y, shelf_height, level = 4, 4, 0, 1
    for area_id, area in sorted(areas.items()):
        if area_id in result:
            continue
        w, h = (math.ceil(value / 64) for value in area["dimensions"])
        if w + 8 > width or h + 8 > height:
            raise ValueError("Source area exceeds bounded native atlas: " + area_id)
        if x + w + 4 > width:
            x, y, shelf_height = 4, y + shelf_height + 5, 0
        if y + h + 4 > height:
            x, y, shelf_height, level = 4, 4, 0, level + 1
        result[area_id] = [x, y, level, w, h]
        x += w + 5
        shelf_height = max(shelf_height, h)
    return width, height, result


def compileCity(source, quests=None):
    quests = quests or json.loads(QUESTS.read_text(encoding="utf-8"))
    source = copy.deepcopy(source)
    custody_source = json.loads(CUSTODY_SOURCE.read_text(encoding="utf-8"))
    prepareCustodyActors(source, custody_source)
    departure_rule = source.get("scriptSourceRules", {}).get("LEAVECH7.BCS", {})
    if (
        departure_rule.get("condition") != {"global": "Chapter", "scope": "GLOBAL", "equals": 7}
        or departure_rule.get("actions") != ["DestroySelf"]
        or departure_rule.get("sha256") != source["references"]["LEAVECH7.BCS"]["sha256"]
    ):
        raise ValueError("The source chapter-seven departure rule requires a new behavior audit")
    excluded_items = source.get("editionExcludedItems", {})
    conversions = source.get("editionItemConversions", {})

    def convertedInventory(records):
        result = []
        for source_index, record in enumerate(records):
            code = record["item"]
            if not code or code in excluded_items:
                continue
            record = copy.deepcopy(record)
            record["item"] = conversions.get(code, {}).get("original", code)
            record["sourceIndex"] = source_index
            result.append(record)
        return result

    for creature in source["creatures"].values():
        creature["items"] = convertedInventory(creature.get("items", []))
    for area in source["areas"].values():
        area["actors"] = [a for a in area["actors"] if a["creature"] not in source.get("editionExcludedCreatures", {})]
        for container in area["containers"]:
            container["items"] = convertedInventory(container["items"])
    for store in source.get("stores", {}).values():
        store["stock"] = convertedInventory(store["stock"])
    source["stores"] = prepareStores(source.get("stores", {}), source["items"])
    areas = source["areas"]
    for area_id, area in areas.items():
        area["label"] = LANDMARKS.get(area_id, area["label"])
    spawn_policies = {
        "AR0615.BCS#spawn0": {"phase": 7},
        "AR0300.BCS#spawn7": {"phase": 5, "phaseMax": 7, "requiresFlag": "narlenOfficerDue"},
        "AR0607.BCS#spawn3": {"phase": 5},
        "AR0608.BCS#spawn3": {"phase": 5},
        "AR0608.BCS#spawn0": {"phase": 7},
        "AR0608.BCS#spawn1": {"phase": 7},
        "AR0608.BCS#spawn2": {"phase": 7},
        "AR0607.BCS#spawn0": {"phase": 7},
        "AR0112.BCS#spawn0": {"phase": 7},
        "AR0112.BCS#spawn1": {"phase": 7},
        "AR0108.BCS#spawn0": {"phase": 7, "requiresQuest": {"ducalPalace": "active"}},
        "AR0108.BCS#spawn1": {"phase": 7},
        "AR0108.BCS#spawn2": {"phase": 7},
        "AR0125.BCS#spawn0": {"phase": 7, "requiresFlag": "palaceCleared"},
        "AR1100.BCS#spawn9": {"phase": 5, "requiresFlag": "aldethSaved"},
        "AR0153.BCS#spawn5": {"phase": 7, "requiresFlag": "palaceCleared"},
        "AR0617.BCS#spawn1": {"phase": 5},
        "AR0800.BCS#spawn7": {"phase": 7},
        "LAERTA.DLG#spawn0": {"phase": 5, "requiresQuest": {"bogeyman": "active"}},
        "GERVIS.DLG#spawn0": {"phase": 5, "requiresQuest": {"bogeyman": "active"}},
        "PUMBERL.DLG#spawn0": {"phase": 5, "phaseMax": 7, "requiresFlag": "jalanthaSummoned"},
        **{
            f"AR0108.BCS#spawn{index}": {"phase": 7, "requiresQuest": {"ducalPalace": "active"}}
            for index in range(3, 9)
        },
    }
    selected_spawns = {}
    for spawn in source.get("scriptedActors", []):
        if spawn["sourceId"] not in spawn_policies:
            continue
        if len(spawn["areas"]) != 1 or not spawn.get("position") or min(spawn["position"]) < 0:
            raise ValueError("Ambiguous authored actor source placement: " + spawn["sourceId"])
        area_id = spawn["areas"][0]
        actor_id = identity(area_id + " Script Actor " + spawn["creature"])
        if actor_id in selected_spawns:
            raise ValueError("Duplicate authored actor source placement: " + actor_id)
        selected_spawns[actor_id] = {**spawn, **spawn_policies[spawn["sourceId"]]}
        areas[area_id]["actors"].append(
            {
                "sourceId": actor_id,
                "name": spawn["displayName"],
                "displayName": spawn["displayName"],
                "creature": spawn["creature"],
                "creatureMetadata": spawn["creature"],
                "position": spawn["position"],
                "dialogue": "",
                "schedule": 0xFFFFFF,
                "scriptedPolicy": selected_spawns[actor_id],
            }
        )
    for npc in source.get("campaignNpcs", []):
        number = npc["sourceId"].rsplit("npc", 1)[1]
        native_id = "cityCampaignNpc" + number
        inside = npc["area"] in areas
        if not inside and npc["creature"] not in {"ELDOTH", "QUAYLE"}:
            continue
        area_id = npc["area"] if inside else "AR0800"
        policy = (
            None
            if inside
            else {
                "phase": 5,
                "phaseMax": 7,
                "sourceId": npc["sourceId"],
                "requiresFlag": "eldothJoined" if npc["creature"] == "ELDOTH" else "quayleAtGate",
            }
        )
        areas[area_id]["actors"].append(
            {
                "sourceId": npc["sourceId"],
                "nativeId": native_id,
                "name": npc["displayName"],
                "displayName": npc["displayName"],
                "creature": npc["creature"],
                "creatureMetadata": npc["creatureMetadata"],
                "position": npc["position"] if inside else [3500, 1380],
                "dialogue": "",
                "schedule": 0xFFFFFF,
                "scriptedPolicy": policy,
                "sourceGameNpc": npc["sourceId"],
                "sourceOriginalArea": npc["area"],
                "sourceOriginalPosition": npc["position"],
            }
        )
    width, height, atlas = layoutAreas(areas)
    levels = {region[2] for region in atlas.values()}
    tiles = {z: [12] * (width * height) for z in levels}
    objects = {z: [] for z in levels}
    occupied, adaptations, actor_definitions = set(), [], []
    config = {
        "cityStreetTile": definition(
            "CTile", animation="images/tiles/road", canStep=True, label="City paving", tileType="cityStreet"
        ),
        "cityWallTile": definition(
            "CTile", animation="images/tiles/wasteland", canStep=False, label="City masonry", tileType="cityWall"
        ),
    }
    areas_metadata = {}
    for area_id, region in atlas.items():
        x, y, z, w, h = region
        area = areas[area_id]
        search = area.get("searchMap")
        raster = rowsFromRuns(search) if search and "terrainRowsRle" in search else []
        for row in range(h):
            for col in range(w):
                samples = []
                if raster:
                    left, right = col * 4, min((col + 1) * 4, search["width"])
                    top = row * 64 // 12
                    bottom = min(math.ceil((row + 1) * 64 / 12), search["height"])
                    samples = [raster[ry][rx] for ry in range(top, bottom) for rx in range(left, right)]
                walkable = any(value not in BLOCKED_TERRAINS for value in samples) if samples else not raster
                tiles[z][(y + row) * width + x + col] = (
                    (6 if area_id in source["exteriors"] else 10) if walkable else 12
                )
        areas_metadata[area_id] = {"bounds": region, "label": area["label"], "classification": area["classification"]}

    def rawPosition(area_id, source_position):
        x, y, z, w, h = atlas[area_id]
        return (
            x + min(w - 1, max(0, int(source_position[0]) // 64)),
            y + min(h - 1, max(0, int(source_position[1]) // 64)),
            z,
        )

    def usablePosition(area_id, point, *, reserve=False):
        initial = rawPosition(area_id, point)
        x, y, z, w, h = atlas[area_id]
        queue, visited = deque([initial]), {initial}
        while queue:
            current = queue.popleft()
            cx, cy, cz = current
            if tiles[cz][cy * width + cx] != 12 and (not reserve or current not in occupied):
                if reserve:
                    occupied.add(current)
                if current != initial:
                    adaptations.append(
                        {
                            "area": area_id,
                            "source": list(point),
                            "initial": initial,
                            "placed": current,
                            "reason": "nearest unoccupied native walkable cell",
                        }
                    )
                return current
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cx + dx, cy + dy, cz)
                if x <= nxt[0] < x + w and y <= nxt[1] < y + h and nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        raise ValueError("Source region has no native walkable cell: " + area_id)

    def place(name, point):
        x, y, z = point
        objects[z].append(
            {
                "id": sum(map(len, objects.values())) + 1,
                "name": name,
                "type": name,
                "x": x * 32,
                "y": y * 32,
                "width": 32,
                "height": 32,
                "rotation": 0,
                "visible": True,
            }
        )

    for source_item, item in source.get("items", {}).items():
        if item.get("editionClassification") != "excludedKnownEeAddition":
            config[identity("Item " + source_item)] = nativeItem(source_item, item)

    relocations = buildRelocations(source, usablePosition=lambda area, point: usablePosition(area, point, reserve=True))
    relocation_by_actor = {row["canonicalActorId"]: row for row in relocations}
    links, represented_doors, geometry_doors = [], set(), []
    for area_id, area in sorted(areas.items()):
        for index, region in enumerate(area["regions"], 1):
            destination = region.get("destination")
            if not destination:
                continue
            box = region["bounding_box"]
            origin = usablePosition(area_id, [(box[0] + box[2]) // 2, (box[1] + box[3]) // 2], reserve=True)
            name = identity(area_id + " Portal " + str(index))
            props = {
                "label": "Passage to " + areas[destination]["label"] if destination in areas else "City boundary",
                "animation": (
                    "images/buildings/stairs_down"
                    if area["classification"] == "underground"
                    else "images/buildings/town_hall"
                ),
                "canStep": True,
                "sourceArea": area_id,
                "sourceRegion": region.get("sourceId", ""),
                "simulationRegion": area_id,
                "destinationArea": destination,
                "sourceFlags": region["flags"],
                "sourceEntrance": region["entrance"],
            }
            matching_doors = [
                (number, door)
                for number, door in enumerate(area["doors"], 1)
                if door["travel_trigger"].casefold() == region["name"].casefold()
            ]
            if len(matching_doors) > 1:
                raise ValueError("Ambiguous source door/portal association: " + name)
            if matching_doors:
                number, door = matching_doors[0]
                props.update(doorProperties(area_id, number, door))
                represented_doors.add((area_id, number))
            if destination in {"AR0146", "AR0123", "AR0125"}:
                props.update(phaseMin=7, requiredFlag="palaceCleared")
            if area_id == "AR0200" and destination == "AR0108":
                props.update(
                    locked=True,
                    lockAgility=12,
                    lockKey="MISC78",
                    forbidForcing=True,
                    sourceClassicLockAdaptation="Classic courtyard switches and pickable palace lock; EE lock removed",
                )
            if destination in areas:
                entries = areas[destination]["entrances"]
                entry = next((e for e in entries if e["name"].casefold() == region["entrance"].casefold()), None)
                if not entry:
                    raise ValueError(
                        "Unresolved source entrance: " + area_id + " -> " + destination + ":" + region["entrance"]
                    )
                target = usablePosition(destination, entry["position"])
                props.update(targetX=target[0], targetY=target[1], targetZ=target[2])
                links.append({"object": name, "from": area_id, "to": destination, "origin": origin, "target": target})
            config[name] = definition("BaldursGatePortal", **props)
            place(name, origin)

    for index, link in enumerate(source.get("worldMapLinks", []), 1):
        area_id, destination = link["source"], link["destination"]
        name = identity(area_id + " Boundary " + str(index))
        origin = usablePosition(area_id, link["sourcePosition"], reserve=True)
        props = {
            "label": "City gate" if destination not in areas else "Street to " + areas[destination]["label"],
            "animation": "images/misc/signpost",
            "canStep": True,
            "simulationRegion": area_id,
            "sourceArea": area_id,
            "destinationArea": destination,
            "sourceEntrance": link["entrance"],
            "sourceDirection": link["direction"],
            "sourceTravelTimeQuarters": link["travel_time_quarters"],
        }
        if destination in areas:
            target = usablePosition(destination, link["destinationPosition"])
            props.update(targetX=target[0], targetY=target[1], targetZ=target[2])
            links.append({"object": name, "from": area_id, "to": destination, "origin": origin, "target": target})
        config[name] = definition("BaldursGatePortal", **props)
        place(name, origin)

    for area_id, area in sorted(areas.items()):
        for index, actor in enumerate(area["actors"], 1):
            name = actor.get("nativeId") or (
                actor["sourceId"]
                if actor.get("scriptedPolicy")
                else identity(actor.get("sourceId", area_id + " Actor " + str(index)))
            )
            cre = source["creatures"].get(actor.get("creatureMetadata", actor["creature"]), {})
            hostile = cre.get("allegiance", 128) >= 200
            stats = {
                "strength": 6,
                "agility": 6,
                "stamina": max(1, math.ceil(cre.get("max_hit_points", 35) / 7)),
                "intelligence": 6,
                "dmgMin": 4,
                "dmgMax": 8,
                "hit": 75,
                "mainStat": "strength",
            }
            props = {
                "label": actor.get("displayName") or actor["name"] or actor["creature"],
                "npc": not hostile,
                "canStep": True,
                "affiliation": "cityHostile" if hostile else "cityResidents",
                "simulationRegion": area_id,
                "sourceArea": area_id,
                "sourceCreature": actor["creature"],
                "sourceActor": actor.get("sourceId", ""),
                "sourceDialogue": actor.get("dialogue") or cre.get("dialogue", ""),
                "sourceSchedule": actor["schedule"],
                "sourceKillXp": cre.get("kill_xp", 0),
                "sw": -20,
                "baseStats": definition("CStats", **stats),
                "fightController": definition("CMonsterFightController"),
                "actions": [{"ref": "Attack"}],
                "sourceInventory": json.dumps(cre.get("items", []), separators=(",", ":")),
                "sourceItemSlots": json.dumps(cre.get("itemSlots", []), separators=(",", ":")),
                "controller": (
                    definition("CTargetController", target="player") if hostile else definition("CController")
                ),
                "gold": cre.get("gold", 0),
            }
            props.update(sevenSunsMerchantProperties(name, actor["creature"], cre))
            if "LEAVECH7" in cre.get("scripts", []):
                props.update(phaseMax=5, sourceDepartureScript="LEAVECH7")
            if actor.get("sourceGameNpc"):
                props.update(
                    sourceGameNpc=actor["sourceGameNpc"],
                    sourceOriginalArea=actor["sourceOriginalArea"],
                    sourceOriginalPosition=json.dumps(actor["sourceOriginalPosition"]),
                )
                if actor["sourceOriginalArea"] != area_id:
                    props["sourceAdaptation"] = "Explicit outside-history companion arrives at the eastern city gate"
            for key in ("custodyRole", "patrolArea"):
                if actor.get(key):
                    props[key] = actor[key]
            position = usablePosition(area_id, actor["position"], reserve=True)
            policy = actor.get("scriptedPolicy")
            if policy:
                props.update(
                    sourceSpawnFact=policy["sourceId"],
                    phaseMin=policy["phase"],
                    phaseMax=policy.get("phaseMax", policy["phase"]),
                )
                actor_definitions.append(
                    {
                        "id": name,
                        "sourceCreature": actor["creature"],
                        "sourceArea": area_id,
                        **({"custodyRole": actor["custodyRole"]} if actor.get("custodyRole") else {}),
                        "x": position[0],
                        "y": position[1],
                        "z": position[2],
                        **{
                            key: policy[key]
                            for key in ("phase", "phaseMax", "requiresQuest", "requiresFlag")
                            if key in policy
                        },
                    }
                )
            else:
                place(name, position)
            corpse = cre.get("hit_points", 1) <= 0
            if corpse:
                for key in (
                    "npc",
                    "controller",
                    "fightController",
                    "baseStats",
                    "actions",
                    "affiliation",
                    "gold",
                    "sourceKillXp",
                ):
                    props.pop(key, None)
                props.update(
                    sourceCorpse=True,
                    sourceHitPoints=cre["hit_points"],
                    contents=json.dumps(cre.get("items", []), separators=(",", ":")),
                    locked=False,
                    trapped=False,
                )
            config[name] = definition("BaldursGateContainer" if corpse else "CCreature", **props)
            if corpse:
                continue
            options = [
                definition("CDialogOption", number=0, text="Speak.", action="talk", nextStateId="ENTRY"),
                definition(
                    "CDialogOption", number=1, text="Inspect possessions.", action="showInventory", nextStateId="ENTRY"
                ),
                definition("CDialogOption", number=2, text="Attempt theft.", action="pickPocket", nextStateId="ENTRY"),
                definition("CDialogOption", number=3, text="Attack.", action="attack", nextStateId="EXIT"),
                definition("CDialogOption", number=4, text="Leave.", nextStateId="EXIT"),
            ]
            store_refs = (
                source.get("references", {}).get(props["sourceDialogue"] + ".DLG", {}).get("storeReferences", [])
            )
            if len(store_refs) == 1:
                props["sourceStore"] = store_refs[0]
            elif store_refs:
                props["sourceStores"] = json.dumps(store_refs, separators=(",", ":"))
            config[name]["properties"].update(
                {key: props[key] for key in ("sourceStore", "sourceStores") if key in props}
            )
            scene_areas = {scene["sourceArea"] for scene in relocation_by_actor.get(name, {}).get("scenes", [])}
            rows_by_action = {}
            for scene_area in sorted(scene_areas | {area_id}):
                for row in questDialogRows(quests, dict(props, sourceArea=scene_area), name):
                    rows_by_action[row["action"]] = row
            rows = list(rows_by_action.values())
            authored = [
                definition(
                    "CDialogOption",
                    text=row["text"],
                    action=row["action"],
                    condition=row["condition"],
                    nextStateId="ENTRY",
                )
                for row in rows
            ]
            utilities = []
            if actor["creature"].startswith(("ALORA", "TIAX", "SKIE", "ELDOTH", "QUAYLE")):
                utilities.extend(
                    definition("CDialogOption", text=text, action=action, nextStateId="ENTRY")
                    for text, action in (
                        ("Ask about recruitment.", "recruit"),
                        ("Discuss this companion.", "inspectCompanion"),
                        ("Dismiss this companion.", "dismiss"),
                        ("Transfer a companion possession.", "takeCompanionItem"),
                    )
                )
            if actor["creature"].startswith("ALORA"):
                utilities.append(
                    definition(
                        "CDialogOption",
                        text="Keep watch while Alora searches the museum.",
                        action="helpAloraLookout",
                        condition="canHelpAlora",
                        nextStateId="ENTRY",
                    )
                )
            if actor["creature"] in {"VAIL", "RANCE", "CAILAN", "FAIZAH", "ACHEN"}:
                utilities.append(
                    definition(
                        "CDialogOption",
                        text="Use a Stone to Flesh scroll.",
                        action="restoreStatue",
                        condition="canRestoreStatue",
                        nextStateId="ENTRY",
                    )
                )
            if actor["creature"] == "PUMBERL" and area_id == "AR0609":
                utilities.append(
                    definition(
                        "CDialogOption",
                        text="Request an audience with Jalantha: 50 gold.",
                        action="requestJalanthaAudience",
                        nextStateId="ENTRY",
                    )
                )
            if actor["creature"] == "TAMOKO":
                for text, action, condition in (
                    ("Hear Tamoko's warning.", "hearTamokoWarning", "canTamokoFirstMeeting"),
                    ("Decline Tamoko's first approach.", "declineTamokoFirstMeeting", "canTamokoFirstMeeting"),
                    ("Discuss Tamoko's request.", "discussTamokoRequest", "canTamokoSecondMeeting"),
                    ("Agree to Tamoko's request.", "acceptTamokoRequest", "canFinishTamokoSecondMeeting"),
                    ("Refuse Tamoko's request.", "refuseTamokoRequest", "canFinishTamokoSecondMeeting"),
                ):
                    utilities.append(
                        definition("CDialogOption", text=text, action=action, condition=condition, nextStateId="ENTRY")
                    )
            if actor["creature"] == "NARLEN":
                utilities.append(
                    definition(
                        "CDialogOption",
                        text="Begin the nighttime lookout.",
                        action="beginNarlenLookout",
                        condition="canBeginNarlenLookout",
                        nextStateId="ENTRY",
                    )
                )
                utilities.append(
                    definition(
                        "CDialogOption", text="Warn Narlen about the guard.", action="warnNarlen", nextStateId="ENTRY"
                    )
                )
            shop_states = []
            if props.get("sourceStore"):
                store_id = props["sourceStore"]
                shop_rows = storeDialogRows(store_id, source["stores"][store_id])
                for group in ("stock", "rooms", "drinks", "services"):
                    group_rows = [row for row in shop_rows if row["group"] == group]
                    if not group_rows:
                        continue
                    utilities.append(definition("CDialogOption", text="Browse " + group + ".", nextStateId=group + "0"))
                    for offset in range(0, len(group_rows), 8):
                        page = offset // 8
                        page_options = [
                            definition(
                                "CDialogOption",
                                text=row["text"],
                                action=row["action"],
                                condition=row["condition"],
                                nextStateId=group + str(page),
                            )
                            for row in group_rows[offset : offset + 8]
                        ]
                        if page:
                            page_options.append(
                                definition("CDialogOption", text="Previous page.", nextStateId=group + str(page - 1))
                            )
                        if offset + 8 < len(group_rows):
                            page_options.append(
                                definition("CDialogOption", text="Next page.", nextStateId=group + str(page + 1))
                            )
                        page_options.append(
                            definition("CDialogOption", text="Return to the conversation.", nextStateId="ENTRY")
                        )
                        for number, option in enumerate(page_options):
                            option["properties"]["number"] = number
                        shop_states.append(
                            definition(
                                "CDialogState",
                                stateId=group + str(page),
                                text=source["stores"][store_id].get("displayName", props["label"]) + ": " + group,
                                options=page_options,
                            )
                        )
                source_store = source["stores"][store_id]
                if source_store.get("flags", 0) & 2 and source_store.get("purchased_types"):
                    utilities.append(
                        definition("CDialogOption", text="Sell a possession.", action="sell", nextStateId="ENTRY")
                    )
                    if source_store.get("flags", 0) & 1:
                        utilities.append(
                            definition(
                                "CDialogOption",
                                text="Buy back a sold possession.",
                                action="buyBack",
                                nextStateId="ENTRY",
                            )
                        )
                if source_store.get("flags", 0) & 16:
                    utilities.append(
                        definition(
                            "CDialogOption",
                            text="Donate to improve your standing.",
                            action="donate",
                            nextStateId="ENTRY",
                        )
                    )
            options = options[:1] + authored + utilities + options[1:]
            for number, option in enumerate(options):
                option["properties"]["number"] = number
            config[name + "Dialog"] = definition(
                "BaldursGateDialog",
                actorId=name,
                speaker=props["label"],
                sourceStore=props.get("sourceStore", ""),
                questIds=",".join(
                    "city" + key[:1].upper() + key[1:] + "Quest"
                    for key in dict.fromkeys(row["questId"] for row in rows)
                ),
                states=[definition("CDialogState", stateId="ENTRY", text=props["label"], options=options)]
                + shop_states,
            )
            if not config[name + "Dialog"]["properties"]["questIds"]:
                del config[name + "Dialog"]["properties"]["questIds"]
        for index, container in enumerate(area["containers"], 1):
            name = identity(area_id + " Container " + str(index))
            difficulty = container["lock_difficulty"]
            props = {
                "label": container["name"] or "Container",
                "animation": "images/misc/chest",
                "canStep": True,
                "sourceArea": area_id,
                "sourceContainer": container.get("sourceId", ""),
                "simulationRegion": area_id,
                "sourceFlags": container["flags"],
                "sourceLockDifficulty": difficulty,
                "locked": bool(container["flags"] & 1),
                "lockAgility": 18 if difficulty >= 80 else 16 if difficulty >= 40 else 12,
                "forceStrength": 14 if difficulty >= 60 else 12,
                "trapped": bool(container["trapped"]),
                "sourceTrapDetection": container["trap_detection"],
                "sourceTrapRemoval": container["trap_removal"],
                "contents": json.dumps(container["items"], separators=(",", ":")),
                "sourceKey": container["key"],
                "sourceOwner": container["owner"],
                "sourceScript": container["script"],
                "sourceBreakDifficulty": container["break_difficulty"],
                "magicallyLocked": bool(container["flags"] & 4),
                "disabled": bool(container["flags"] & 32),
                "forbidPicking": difficulty >= 100 or bool(container["flags"] & 4),
                "forbidForcing": container["break_difficulty"] >= 100 or bool(container["flags"] & 4),
            }
            config[name] = definition("BaldursGateContainer", **props)
            place(name, usablePosition(area_id, container["position"], reserve=True))

    for area_id, area in sorted(areas.items()):
        for index, door in enumerate(area["doors"], 1):
            if (area_id, index) in represented_doors:
                continue
            if not (door["open_polygon"] or door["closed_polygon"]):
                geometry_doors.append(
                    {
                        "sourceDoor": f"{area_id}#door{index}",
                        "sourceArea": area_id,
                        "classification": "geometryOnlyNoClickPolygon",
                        **door,
                    }
                )
                represented_doors.add((area_id, index))
                continue
            name = identity(area_id + " Door " + str(index))
            config[name] = definition(
                "BaldursGateDoor",
                label="Door",
                animation="maps/baldursGate/images/interactions/" + ("openDoor" if door["flags"] & 1 else "closedDoor"),
                canStep=True,
                sourceArea=area_id,
                simulationRegion=area_id,
                **doorProperties(area_id, index, door),
            )
            place(name, usablePosition(area_id, door["use_points"][:2], reserve=True))
            represented_doors.add((area_id, index))

    for source_item in {
        item["item"] for area in areas.values() for obj in area["containers"] for item in obj["items"]
    } | {item["item"] for cre in source["creatures"].values() for item in cre.get("items", [])}:
        config.setdefault(
            identity("Item " + source_item),
            definition(
                "CItem",
                label=source_item,
                animation="images/items/scroll",
                plugin_citySourceItem=source_item,
                plugin_cityTradeable=True,
                plugin_cityValue=1,
            ),
        )

    for quest in quests["quests"]:
        config["city" + quest["id"][:1].upper() + quest["id"][1:] + "Quest"] = definition(
            "BaldursGateQuest",
            questKey=quest["id"],
            description=quest["title"],
            objective=quest.get("objective", quest["title"]),
            rewardText=quest.get("rewardText", "See the recorded city agreement."),
        )

    non_travel_regions = buildRegions(source, atlas, config, objects, usablePosition=usablePosition)

    for index, point in enumerate(([2143, 1618], [2220, 1627]), 1):
        name = "cityPalaceSwitch" + str(index)
        config[name] = definition(
            "BaldursGateContainer",
            label="Palace courtyard switch " + str(index),
            animation="images/misc/signpost",
            canStep=True,
            sourceArea="AR0200",
            simulationRegion="AR0200",
            palaceSwitch=index,
            sourceEvidence="https://www.gamebanshee.com/baldursgate/walkthrough/baldursgatenorthern.php",
        )
        place(name, usablePosition("AR0200", point, reserve=True))

    custody_data = custodyDefinitions(custody_source, usablePosition)
    config["cityCustody"] = definition(
        "BaldursGateCustody",
        canStep=True,
        animation="images/ambient/street_lantern",
        custodyDefinitions=json.dumps(custody_data, separators=(",", ":")),
    )
    place("cityCustody", usablePosition("AR0800", [3560, 1380], reserve=True))
    config["cityCustodyQuest"] = definition("BaldursGateCustodyQuest", description="The Flaming Fist pursuit")
    config["citySevenSunsWarningLead"] = definition(
        "BaldursGateSevenSunsWarningLeadQuest", description="Seven Suns: a merchant's warning"
    )
    entry = usablePosition("AR0800", [3500, 1350], reserve=True)
    config["cityStart"] = definition(
        "BaldursGateStart", canStep=True, animation="images/misc/signpost", alwaysSimulate=True
    )
    place("cityStart", entry)
    config["cityClock"] = definition(
        "BaldursGateClock",
        canStep=True,
        animation="images/ambient/street_lantern",
        alwaysSimulate=True,
        sevenSunsMerchantDefinition=json.dumps(
            {
                "version": 1,
                "dialogue": "DOPMER",
                "fingerprint": "e0410b2b978573d0e921a63bf3a55fd53d49c291f556b6e0a045db63762030a7",
                "stockContract": "doppss-native-v1",
            },
            separators=(",", ":"),
        ),
        sevenSunsWarningDefinition=json.dumps(
            {
                "version": 1,
                "dialogue": "DOPPSM",
                "fingerprint": "263ba285fac3cc7d486ce0c4223ce4af574b257b7ce224d8755b988906df6aac",
                "journalQuest": "citySevenSunsWarningLead",
            },
            separators=(",", ":"),
        ),
        areaAtlas=json.dumps(areas_metadata, separators=(",", ":")),
        activeSimulationRegion="AR0800",
        questDefinitions=json.dumps(quests, separators=(",", ":")),
        storeDefinitions=json.dumps(source.get("stores", {}), separators=(",", ":")),
        geometryDoors=json.dumps(geometry_doors, separators=(",", ":")),
        actorDefinitions=json.dumps(actor_definitions, separators=(",", ":")),
        relocationDefinitions=json.dumps(relocations, separators=(",", ":")),
        regionDefinitions=json.dumps(non_travel_regions, separators=(",", ":")),
    )
    place("cityClock", usablePosition("AR0800", [3540, 1380], reserve=True))
    # Incoming landings are allocated after objects so they cannot re-enter a portal or overlap an actor.
    # Search only the entrance's walkable component; never cut a new passage through source masonry.
    for link in links:
        initial = tuple(link["target"])
        x, y, z, w, h = atlas[link["to"]]
        queue, visited = deque([initial]), {initial}
        target = None
        while queue:
            current = queue.popleft()
            if current not in occupied:
                target = current
                break
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (current[0] + dx, current[1] + dy, z)
                if (
                    x <= nxt[0] < x + w
                    and y <= nxt[1] < y + h
                    and nxt not in visited
                    and tiles[z][nxt[1] * width + nxt[0]] != 12
                ):
                    visited.add(nxt)
                    queue.append(nxt)
        if target is None:
            raise ValueError("No safe landing in source entrance component: " + link["object"])
        link["target"] = target
        props = config[link["object"]]["properties"]
        props.update(targetX=target[0], targetY=target[1], targetZ=target[2])
        if target != initial:
            adaptations.append(
                {
                    "area": link["to"],
                    "initial": initial,
                    "placed": target,
                    "object": link["object"],
                    "reason": "safe arrival beside occupied source entrance",
                }
            )

    tile_set = copy.deepcopy(
        json.loads((ROOT / "res/maps/candlekeep/map.json").read_text(encoding="utf-8"))["tilesets"]
    )
    tile_set[0]["tileproperties"]["5"]["type"] = "cityStreetTile"
    tile_set[0]["tileproperties"]["11"]["type"] = "cityWallTile"
    layers = []
    for level in sorted(levels):
        common = {
            "x": 0,
            "y": 0,
            "opacity": 1,
            "visible": True,
            "properties": {"level": str(level)},
            "propertytypes": {"level": "string"},
        }
        layers.append(
            {
                **common,
                "type": "tilelayer",
                "properties": {
                    "level": str(level),
                    "default": "cityWallTile",
                    "outOfBounds": "cityWallTile",
                    "xBound": str(width - 1),
                    "yBound": str(height - 1),
                },
                "propertytypes": {key: "string" for key in ("level", "default", "outOfBounds", "xBound", "yBound")},
                "name": "City terrain " + str(level),
                "width": width,
                "height": height,
                "data": tiles[level],
            }
        )
        layers.append(
            {**common, "type": "objectgroup", "name": "City objects " + str(level), "objects": objects[level]}
        )
    document = {
        "width": width,
        "height": height,
        "tilewidth": 32,
        "tileheight": 32,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.2.0",
        "type": "map",
        "version": 1.2,
        "nextobjectid": sum(map(len, objects.values())) + 1,
        "properties": {
            "x": str(entry[0]),
            "y": str(entry[1]),
            "z": "0",
            "label": "Baldur's Gate",
            "guardNativeEncounterSaves": True,
        },
        "propertytypes": {
            **{key: "string" for key in ("x", "y", "z", "label")},
            "guardNativeEncounterSaves": "bool",
        },
        "layers": layers,
        "tilesets": tile_set,
    }
    geometry = {
        "sourcePixelsPerNativeCell": 64,
        "atlas": areas_metadata,
        "connections": links,
        "placementAdaptations": adaptations,
        "scriptedActorPlacements": actor_definitions,
        "relocationDefinitions": relocations,
        "nonTravelRegions": non_travel_regions,
        "geometryDoors": [
            {"sourceDoor": row["sourceDoor"], "classification": row["classification"]} for row in geometry_doors
        ],
        "sourceParityEstablished": False,
    }
    stock_config = stockDefinitions(json.loads(MERCHANT_STOCK_SOURCE.read_text(encoding="utf-8")))
    if set(config) & set(stock_config):
        raise ValueError("Reviewed merchant stock IDs collide with existing city resources")
    config.update(stock_config)
    geometry["poisonSourcePortConfigured"] = preparePoisonSource(
        document,
        config,
        source,
        json.loads(POISON_DIALOGUE.read_text(encoding="utf-8")),
        json.loads(POISON_FOLLOWUP.read_text(encoding="utf-8")),
        json.loads(POISON_TEXT.read_text(encoding="utf-8")),
        usablePosition,
    )
    document["assets"] = sorted(
        applyCityAppearances(source, config) + applyCityEnvironmentAppearances(source, config),
        key=lambda row: row["path"],
    )
    protectCityDefinitions(config)
    return document, config, geometry


def compileDialogs(config, quests):
    dialogs = {}
    for name, row in config.items():
        props, class_id = row["properties"], row["class"]
        if class_id not in {"BaldursGateContainer", "BaldursGateDoor", "BaldursGatePortal", "BaldursGateStart"}:
            continue
        if class_id == "BaldursGatePortal" and not props.get("sourceDoor"):
            continue
        if props.get("palaceSwitch"):
            choices = [
                (
                    "Press the courtyard switch.",
                    "pressPalaceSwitchOne" if props["palaceSwitch"] == 1 else "pressPalaceSwitchTwo",
                    "ENTRY",
                )
            ]
        elif class_id == "BaldursGateStart":
            choices = [
                ("Earlier history: I helped Aldeth in Cloakwood.", "historyAldethHelped", "ENTRY"),
                ("Earlier history: Aldeth died in Cloakwood.", "historyAldethKilled", "ENTRY"),
                ("Earlier history: I helped Tenya.", "historyTenyaHelped", "ENTRY"),
                ("Earlier history: Tenya died.", "historyTenyaKilled", "ENTRY"),
                ("Begin the outside Candlekeep interlude.", "cityInterlude", "ENTRY"),
                ("Return to the city after the interlude.", "returnFromInterlude", "ENTRY"),
                ("Earlier history: Eldoth traveled with me.", "historyEldothJoined", "ENTRY"),
                ("Earlier history: Eldoth was not in my company.", "historyEldothAbsent", "ENTRY"),
                ("Outside encounter: meet Quayle at the bridge.", "encounterQuayle", "ENTRY"),
                ("Finish earlier-history choices.", "finishHistoryChoices", "ENTRY"),
                ("Wait one city hour.", "waitHour", "ENTRY"),
            ]
        else:
            choices = [
                ("Use the matching key.", "useKey", "ENTRY"),
                ("Attempt to pick the lock.", "unlock", "ENTRY"),
                ("Attempt to force the lock.", "force", "ENTRY"),
                ("Attempt to disarm the trap.", "disarm", "ENTRY"),
                ("Open and examine.", "open", "ENTRY"),
            ]
            if class_id in {"BaldursGateDoor", "BaldursGatePortal"}:
                choices.append(("Close the door.", "close", "ENTRY"))
        options = [
            definition("CDialogOption", text=text, action=action, nextStateId=state) for text, action, state in choices
        ]
        for option in options:
            if option["properties"].get("action") == "finishHistoryChoices":
                option["properties"]["condition"] = "canFinishHistoryChoices"
            elif option["properties"].get("action") == "cityInterlude":
                option["properties"]["condition"] = "canCityInterlude"
            elif option["properties"].get("action") == "returnFromInterlude":
                option["properties"]["condition"] = "canReturnFromInterlude"
        for quest_row in questDialogRows(quests, props, name):
            options.append(
                definition(
                    "CDialogOption",
                    text=quest_row["text"],
                    action=quest_row["action"],
                    condition=quest_row["condition"],
                    nextStateId="ENTRY",
                )
            )
        options.append(definition("CDialogOption", text="Return to exploration.", nextStateId="EXIT"))
        for number, option in enumerate(options):
            option["properties"]["number"] = number
        dialogs[name + "Dialog"] = definition(
            "BaldursGateDialog",
            actorId=name,
            speaker=props.get("label", "Baldur's Gate"),
            states=[
                definition(
                    "CDialogState",
                    stateId="ENTRY",
                    text=props.get("label", "City history and journeys"),
                    options=options,
                )
            ],
        )
    return dialogs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    document, config, geometry = compileCity(source)
    output = {
        DESTINATION / "map.json": document,
        DESTINATION / "config.json": config,
        DESTINATION / "dialog.json": compileDialogs(config, json.loads(QUESTS.read_text(encoding="utf-8"))),
        ROOT / "tests/fixtures/baldurs_gate_city_geometry.json": geometry,
    }
    for path, value in output.items():
        data = json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != data:
                raise SystemExit("Stale generated city resource: " + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
    print(
        json.dumps(
            {
                "areas": len(source["areas"]),
                "levels": len({a["bounds"][2] for a in geometry["atlas"].values()}),
                "objects": document["nextobjectid"] - 1,
                "connections": len(geometry["connections"]),
                "placementAdaptations": len(geometry["placementAdaptations"]),
            }
        )
    )


if __name__ == "__main__":
    main()
