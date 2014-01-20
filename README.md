# Recovered game snapshot

Original commit: `1b2eb449914cdff38292b1449b4608957b349145`. Original tree: `114681828078c326b72252551abc6b4e46775d26`.
Startup was verified from identical recovered sources at `1b2eb449914cdff38292b1449b4608957b349145`.

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
- `config/map.json`: unverified donor reconstruction; bf32a4c93e396bd645769a9957eacd6a75106b62:config/map.json; headerMatch=0; apiOverlap=0/10000; distance=15
- `creatures/creature.cpp`: carried forward unchanged from the reconstruction of f6c7917cea6bf8831e4546072a676979eda5a560 (previous version of creatures/creature.cpp)
- `creatures/player.cpp`: Adapted validated #91 body to genuine #92 Player::setMap(Map*) and original ListItem::setNumber, which now dereferences getMap()->getTileSize(). A real startup trace located null Map at ListItem::setNumber via constructor updateViews. Defer panel layout until map assignment, propagate the genuine map to inventory/equipment/actions before layout, and attach existing player panels to owning GameScene instead of constructor singleton. Exact original attachment policy remains inferred; surviving source unchanged. Prior persistence provenance retained.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=47
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
- `map/map.cpp`: carried forward unchanged from the reconstruction of 00509e4451f6babbff847689d5736a04f4ac1efd (previous version of map/map.cpp)
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: carried forward unchanged from the reconstruction of 382404a3259a4094aa00d3fc4de2e0ba4d38881b (previous version of view/gamescene.cpp)
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `8df4c7103eff087a9e05dea14e5a657a0456e8e31a09a2adf6b396db00e694f2`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
