# Recovered game snapshot

Original commit: `21ebd6611c521acf175ba29ab5247e6d221a5c87`. Original tree: `ab33e8cc26da48da461ff44786a1816ca1029411`.
Startup was verified from identical recovered sources at `21ebd6611c521acf175ba29ab5247e6d221a5c87`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, and Python 3 for the hash-pinned build-source preparation helper. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Use a separate build copy for this version. Its original source contains Windows separators
in quoted includes. The attached helper changes only those recorded literals, verifies each
source file's original and prepared SHA256, and preserves the recovered snapshot's provenance.

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_build_sources.py
qmake Game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' -after TARGET=RecoveryGame DESTDIR=.
make -j"$(nproc)"
mkdir -p save
./RecoveryGame
```

For an isolated launch, use:

```sh
LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software xvfb-run -a --server-args="-screen 0 1920x1080x24" ./RecoveryGame
```

The automated readiness observer used for verification is recorded in the attached evidence; ordinary
launches run the game's original entry point. Startup evidence does not establish full gameplay equivalence.

## Recovery provenance

The genuine scene writes `save/game.sav` during shutdown. Verification prepared its empty
parent directory before startup, without changing source files or replacing existing save data.
The source call, source hash and created/preserved directory are recorded in verification metadata.

compatibilityRepair: 1, exactOriginal: 57, reconstruction: 22.

- `compression/minizip.h`: unverified upstream reconstruction; https://github.com/richgel999/miniz/tree/v114
- `config/creatures.json`: content reconstruction of the BFG-removed original; carried nearest reconstructed config/creatures.json through API-stable #62; surviving files provide no recoverable internal implementation/data delta
- `config/items.json`: Adapted genuine surviving #119 5e000dca02a17e179719d99ae93d31687c9d2244 config/items.json donor to missing originalBlob2c4 shared by122–139. Genuine original122 Item::getItem migrated from legacy type strings to class + QMetaType::create, while the previous generic donor had only type and returned no real items. Adds only class Weapon/Armor/Potion corresponding to actual existing type, retaining every donor name/path/stat/power/type. This is source-derived missing-config reconstruction; unknown original added items/balance/slot declarations remain unavailable and are not invented. No surviving original file changes. Does not apply≤121 or≥140 different content groups.
- `creatures/creature.cpp`: Adapted validated #132 Creature reconstruction to genuine #137 std::map<int,Item*> equipped storage and actual hasEquipped/setItem(int)/getter declarations. Seeds keys from genuine137 slots.json; its actual RightHand=1 and Chest=4 retain weapon/armor APIs, unlike later0/3. Real item onEquip/onUnequip callbacks maintain stat bonuses; save subtracts each equipped bonus before serializing base stats. Inferred slot-value equipment JSON is inverse across save/load, and legacy inventory.weapon/armor template fields are applied only when present so they cannot erase restored equipment. Slot serialization format and exact missing policies remain inferred, not recovered original137 bodies; broader formulas and inventory/action collection-cast ABI limitation remain documented. Original surviving Player/Item/slot widgets unchanged.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=24
- `images/buildings/teleporter/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/teleporter/0.png; headerMatch=0; apiOverlap=0/10000; distance=24
- `images/items/armors/chestplateofnorth/0`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:images/items/armors/chestplateofnorth.png; headerMatch=0; apiOverlap=0/10000; distance=221
- `images/items/belts/undestructiblebelt/0.jpg`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:images/items/belts/undestructiblebelt.png; headerMatch=0; apiOverlap=0/10000; distance=221
- `images/items/helmets/0.jpg`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: Missing #150 Interaction body inferred from native-verified #97 implementation and exact #150 surviving header: public/default/copy constructors, ListItem ordering and Effect state serialization added. Removed undeclared legacy setAnimation override, retaining inherited real resource loading. Historical ordering/effect persistence parity unverified.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Adapted validated #129 missing Map implementation to genuine #130 newly introduced Teleporter class: recognizes Teleporter state, constructs the real surviving Teleporter, invokes its original 3-coordinate array loader, adds it through real map ownership, and classifies actual Teleporter objects for original saveToJson. Original genuine getObjects accessor and Teleporter entry/movement behavior remain unchanged. Carried generic Map generation/cache/formulas and unknown omitted implementation details remain inference; donor missing map configuration is not asserted identical to the lost authored map. This body does not add later enabled-flag semantics.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: Missing scene body inferred from earlier recovered donor and exact #150 intact declarations; restored declared map accessor/StepTimer mouse movement and kept player/game initialization and arrow movement. Removed undeclared later tile-size setter. Original behavior not proven; startup evidence and gameplay parity reported separately.
- `view/gameview.cpp`: Adapted validated #133 GameView reconstruction to genuine133–137 unchanged missing source blob spanning the original Creature equipped API migration from set<Item*> to map<int,Item*>. Small overloads select actual Item* values from either real return type, preserving one content-keyed body across all genuine headers. Displays only non-null items in the still-declared PlayerListView equipment panel, with actual collections/signals. Original137 PlayerEquippedView constructor is empty and GameView header still names PlayerListView. Exact missing layout/panel behavior remains inference; no surviving original changed.
- `view/mapview.cpp`: Adapted validated #124–128 MapView reconstruction and genuine original123 donor to genuine #129 Tile-derived ListItem, actual loadTiles()/tiles palette and original MapScene tile drop path. Creates real configured Tile objects, marks actual drag support, cycles items/buildings/creatures/tiles, and replaces dropped palette prototypes using actual named Tile constructor. Config key enumeration and palette order/clone policy are inferred from actual headers/callers, not recovered original bodies. Monster filtering/default editor policy remains as documented124. No original source changed; startup does not establish palette-control parity.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `98589a3fbbe48a9251a8c72cecf5128ff1b4a7e70106b4cef75fab8127abbe5c`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
