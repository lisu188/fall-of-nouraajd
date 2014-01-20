# Recovered game snapshot

Original commit: `84017c9110a182dc9c25eca52576ff97f9a4b76c`. Original tree: `be0c1f9744ef0cb5c276e0ee32cfe8790ae3e504`.
Startup was verified from identical recovered sources at `84017c9110a182dc9c25eca52576ff97f9a4b76c`.

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

compatibilityRepair: 1, exactOriginal: 44, reconstruction: 18.

- `compression/minizip.h`: unverified upstream reconstruction; https://github.com/richgel999/miniz/tree/v114
- `config/creatures.json`: content reconstruction of the BFG-removed original; carried nearest reconstructed config/creatures.json through API-stable #62; surviving files provide no recoverable internal implementation/data delta
- `config/map.json`: unverified donor reconstruction; bf32a4c93e396bd645769a9957eacd6a75106b62:config/map.json; headerMatch=0; apiOverlap=0/10000; distance=13
- `creatures/creature.cpp`: Adapted the validated #114 Creature reconstruction to genuine #115 set-based inventory/equipment/actions/effects and loot declarations, matching original Monster::getLoot, PlayerListView and item callers. Set insertion/erase replace list mutation; adding a loot container transfers its elements as the previous merge did. Implements actual declared getEquipped/getExp accessors. Earlier inferred combat/stat formulas and save schema retained; original internal delta unavailable.
- `creatures/player.cpp`: Adapted validated #115 set-based Player to genuine #116 Player::BackPackObject declaration, original images.qrc backpack.png and original GameView::showCharView public slot. The actual icon child belongs to the real Player, and left-click calls the existing character panel toggle, consuming that UI event. Ownership uses a QGraphicsItem child to preserve value-member lifetime. View anchoring at top center and exact original connection/layout policy are inferred because the body is missing; no neighboring surviving backpack implementation exists through149. getStep/containers/save/combat retain prior provenance; startup does not prove click behavior or gameplay equivalence.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=45
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: carried forward unchanged from the reconstruction of d8eebeb95fdc4734ed2094dc13c298671c8b0529 (previous version of interactions/interaction.cpp)
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Carried validated #115 Map reconstruction unchanged; same surviving Map API at #116. Prior explicitly inferred cache radius and unknown original implementation deltas retained.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: Adapted validated #114 Scene reconstruction to genuine #115 getStep/getMap declarations moved out of line. Returns the immediately preceding original inline step100 and actual owned map; real inherited mouse movement/save/startup behavior unchanged. Original internal delta unavailable.
- `view/gameview.cpp`: Copied genuine surviving immediately preceding #115 6d8b6688d0808565029e6b96e9a52549e80c19aa:view/gameview.cpp; #116 original GameView header only moves the already existing showCharView method into Qt public slots, requiring no implementation change. Missing-source copy formatted to repository style only. Unknown original #116 implementation delta remains unverified; this avoids the generic future donor currently selected for the missing source.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `1dd5ab73f604cf0ddab9ee6b448eb471a95ca0a9b8a35178b442c9d8751235af`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
