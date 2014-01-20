# Recovered game snapshot

Original commit: `6d8b6688d0808565029e6b96e9a52549e80c19aa`. Original tree: `5d1456cfdabfad51681138ea1c663cea35dee0e0`.
Startup was verified from identical recovered sources at `6d8b6688d0808565029e6b96e9a52549e80c19aa`.

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

compatibilityRepair: 1, exactOriginal: 44, reconstruction: 20.

- `Game.pro`: Missing Game.pro reconstructed from the same-tree object_script.Game.Debug compiled object list and the nearest intact 84017c91 Game.pro settings. Native GCC first failed in unchanged view/gameview.h:26 because its CharView pointer has no declaration. Inferred project-only build compatibility force-includes the same-commit surviving view/charview.h (SHA-256 3a46107f0f2fa4248ee3ae3bd84044c797fde799859d617eccff8a0eb2628d18) with QMAKE_CXXFLAGS += -include $$PWD/view/charview.h. No surviving header, implementation, configuration or resource bytes are changed. Acceptance is compilation and genuine game startup with this reconstructed-project include repair; unchanged authored build/startup and historical gameplay equivalence remain unverified. First failure and original input hashes retained in native-early/failures/114-first-build/diagnostic.json. The same missing project blob also covers #115; includes genuine view/charview.cpp, which its original GameView now constructs even though the retained older object_script omits that source. At #114 the extra real empty constructor is unused; no original implementation is synthesized. This repaired project is build compatibility in both trees.
- `compression/minizip.h`: unverified upstream reconstruction; https://github.com/richgel999/miniz/tree/v114
- `config/creatures.json`: content reconstruction of the BFG-removed original; carried nearest reconstructed config/creatures.json through API-stable #62; surviving files provide no recoverable internal implementation/data delta
- `config/map.json`: unverified donor reconstruction; bf32a4c93e396bd645769a9957eacd6a75106b62:config/map.json; headerMatch=0; apiOverlap=0/10000; distance=14
- `creatures/creature.cpp`: Adapted the validated #114 Creature reconstruction to genuine #115 set-based inventory/equipment/actions/effects and loot declarations, matching original Monster::getLoot, PlayerListView and item callers. Set insertion/erase replace list mutation; adding a loot container transfers its elements as the previous merge did. Implements actual declared getEquipped/getExp accessors. Earlier inferred combat/stat formulas and save schema retained; original internal delta unavailable.
- `creatures/player.cpp`: Adapted the validated #114 Player reconstruction to genuine #115 std::set loot/inventory/actions/equipment and original PlayerListView(std::set<ListItem*>*). Uses per-player sets of actual base-class pointers for view collections, avoiding reinterpretation of incompatible standard container types. Populates view sets from real owned items/actions before original panels update. The exact original layout/refresh policy remains inferred; no fake items or player objects.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=46
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `include/zconf.h`: unverified upstream reconstruction; https://zlib.net/fossils/zlib-1.2.7.tar.gz
- `include/zlib.h`: unverified upstream reconstruction; https://zlib.net/fossils/zlib-1.2.7.tar.gz
- `interactions/interaction.cpp`: carried forward unchanged from the reconstruction of d8eebeb95fdc4734ed2094dc13c298671c8b0529 (previous version of interactions/interaction.cpp)
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Adapted validated #114 Map reconstruction to genuine #115 header removal of Map::show and cacheSize member. Removed obsolete show body; retains the immediately preceding original cache radius25 as a local ensureSize policy because the missing body gives no evidence for a new viewport/radius rule. Rendering, map state and object traversal remain real. Radius policy and prior unknown implementation deltas are explicitly inferred.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: Adapted validated #114 Scene reconstruction to genuine #115 getStep/getMap declarations moved out of line. Returns the immediately preceding original inline step100 and actual owned map; real inherited mouse movement/save/startup behavior unchanged. Original internal delta unavailable.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `c76624f6344d16af9996340aac076ded8f9c0f3c86f0aebc352c894318bd1321`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
