# Recovered game snapshot

Original commit: `1a3664c6aa7596d5b8467e0ebdb5b145d4c8238f`. Original tree: `d3db073245dbf5c252d3afc1cf173196f4c46cc2`.
Startup was verified from identical recovered sources at `1a3664c6aa7596d5b8467e0ebdb5b145d4c8238f`.

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

compatibilityRepair: 1, exactOriginal: 36, reconstruction: 16.

- `config/creatures.json`: content reconstruction of the BFG-removed original; carried the nearest #41 reconstruction through API-stable revision #43; surviving files reveal no recoverable implementation/data delta, so original internal changes remain unknown
- `creatures/creature.cpp`: content reconstruction of the BFG-removed original; carried the nearest #41 reconstruction through API-stable revision #44; surviving files reveal no recoverable implementation/data delta, so original internal changes remain unknown
- `creatures/player.cpp`: content reconstruction of the BFG-removed original; adapted #40 reconstruction to both original #41 Player(name,...) constructors
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: content reconstruction of the BFG-removed original; carried forward unchanged from the reconstruction of 9ee96a8e2bf78f077cdfbfd98442a2512e79febc (previous version of interactions/interaction.cpp)
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: content reconstruction of the BFG-removed original; adapted prepared #40 map reconstruction to original #41 implicit Map constructor; group saved objects by className because original Cave no longer serializes its name
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; from the fe3928a0 reconstruction: init renamed loadFromJson with saveToJson, main stat name and shadow resistance (same-commit stats.h)
- `view/gamescene.cpp`: content reconstruction of the BFG-removed original; adapted #40 scene reconstruction to the original #41 Player(name,map) constructor
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `ddf170ae6d0c60b8e0c85d4411f007cfba9b79f07331accfc090a72c2ec9430f`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
