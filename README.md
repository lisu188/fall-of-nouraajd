# Recovered game snapshot

Original commit: `874190dae431b570131b0b08561c0900057a6538`. Original tree: `0c32f6b216c608b34fe2b33e294c516dfec7bf36`.
Startup was verified from identical recovered sources at `874190dae431b570131b0b08561c0900057a6538`.

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
./RecoveryGame
```

For an isolated launch, use:

```sh
LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software xvfb-run -a --server-args="-screen 0 1920x1080x24" ./RecoveryGame
```

The automated readiness observer used for verification is recorded in the attached evidence; ordinary
launches run the game's original entry point. Startup evidence does not establish full gameplay equivalence.

## Recovery provenance

compatibilityRepair: 1, exactOriginal: 45, reconstruction: 17.

- `config/creatures.json`: content reconstruction of the BFG-removed original; carried nearest reconstructed config/creatures.json through API-stable #62; surviving files provide no recoverable internal implementation/data delta
- `creatures/creature.cpp`: content reconstruction of the BFG-removed original; adapted #52 reconstruction to original #63 map-independent constructors and addEffect(type,caster); Effect is now declared by interaction.h
- `creatures/player.cpp`: content reconstruction of the BFG-removed original; adapted #53 reconstruction to both original #63 map-independent Player constructors; Map::addObject assigns the actual owning map
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=98
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: content reconstruction of the BFG-removed original; adapted #52 interaction reconstruction to original #63 effect string field and Creature::addEffect API; moved exact surviving #62 effect implementations into interaction.cpp and use surviving #63 effects.json durations/buff targets
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: content reconstruction of the BFG-removed original; adapted #61 reconstruction to original #63 map-independent MapObject constructor and Map::hide; hide clears rendered cache while preserving logical map/object state
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: content reconstruction of the BFG-removed original; adapted #59 reconstruction to surviving #63 map-independent Player/Cave/Dungeon constructors; owning maps assigned through Map::addObject
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `10dacf08ce9bb25fc3abde7cc091543a2f629f14647395964e7e823575982b95`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
