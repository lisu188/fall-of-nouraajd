# Recovered game snapshot

Original commit: `251c727c2a6957bcaca2335e2632bf2a60a772d3`. Original tree: `be145d0bc5df25b8abc3418577089d2591788b61`.
Startup was verified from identical recovered sources at `251c727c2a6957bcaca2335e2632bf2a60a772d3`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
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

compatibilityRepair: 1, exactOriginal: 56, reconstruction: 18.

- `compression/minizip.h`: unverified upstream reconstruction; https://github.com/richgel999/miniz/tree/v114
- `config/creatures.json`: content reconstruction of the BFG-removed original; carried nearest reconstructed config/creatures.json through API-stable #62; surviving files provide no recoverable internal implementation/data delta
- `config/items.json`: Adapted genuine surviving #119 5e000dca02a17e179719d99ae93d31687c9d2244 config/items.json donor to missing originalBlob2c4 shared by122–139. Genuine original122 Item::getItem migrated from legacy type strings to class + QMetaType::create, while the previous generic donor had only type and returned no real items. Adds only class Weapon/Armor/Potion corresponding to actual existing type, retaining every donor name/path/stat/power/type. This is source-derived missing-config reconstruction; unknown original added items/balance/slot declarations remain unavailable and are not invented. No surviving original file changes. Does not apply≤121 or≥140 different content groups.
- `config/map.json`: unverified donor reconstruction; bf32a4c93e396bd645769a9957eacd6a75106b62:config/map.json; headerMatch=0; apiOverlap=0/10000; distance=6
- `creatures/creature.cpp`: Adapted validated #119 Creature to genuine #120 private Comparer sets while its public getter types remain std::set<T*>*. Matches the explicit same-commit surviving Player::getLoot cast pattern to return the actual owned containers through their legacy types, preserving pointer identity and mutation semantics rather than inventing snapshots. This is a documented original-style container ABI/aliasing compatibility inference under pinned GCC5, not a portable C++ guarantee or gameplay parity claim. Real contents/signals/formulas/save behavior retain prior provenance.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=38
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: Carried validated #119 Interaction and removed only its obsolete setAnimation definition because genuine #120 header now inherits MapObject::setAnimation. Real configured animations and combat/effects remain enabled; previous behavior/inference provenance retained.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Adapted validated #122 Map to genuine #123 Cave/Dungeon default constructors, original loadFromJson implementations and save schemas. Cave loading delegates the real three-coordinate array; Dungeon loading delegates the original six-coordinate entry/exit array. Generated paired dungeon entrances use that same genuine loader/schema, preserving actual teleport destinations. Building now inherits original ListItem; no obsolete constructors or fake objects used. Prior inferred geometry/cache/default policies and unknown original delta remain explicit; original building code untouched.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: Adapted validated #119 Scene to genuine #120 static Map tile-size API by removing the two obsolete per-map setter calls. Real original configuration now determines static size; real map/player/save/movement remains unchanged. Exact missing original implementation delta remains unverified.
- `view/gameview.cpp`: Adapted validated #119 GameView-owned real collections to genuine #120 PlayerListView constructor std::set<ListItem*,Comparer>* using the actual surviving Comparer. Actual player inventory/actions/equipment remain the source, with real signals/views/widgets. Prior explicit layout/timing inference and original-style Creature container ABI limitation remain; original headers/main/config/player/assets unchanged.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `f79f7719f661506ebecc6df2a3d6c89e02506141d4e8e5aa2da50b3bbac0eec9`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
