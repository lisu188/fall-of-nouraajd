# Recovered game snapshot

Original commit: `c85e4a79bde5380e2df8505aab816b3823be4ca9`. Original tree: `9117e1015d0eac6e39c61f9ded1e57d16669d0b1`.
Startup was verified from identical recovered sources at `c85e4a79bde5380e2df8505aab816b3823be4ca9`.

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

compatibilityRepair: 1, exactOriginal: 34, reconstruction: 15.

- `creatures/creature.cpp`: content reconstruction of the BFG-removed original; from the cf8025b1 reconstruction: Creature(path, map) loads configurations and saved games through loadFromJson (actions, items, equipped weapon/armor, coordinates, saved level/exp/hp/mana) with the matching saveToJson, and keeps the equipped list (same-commit creature.h, player.json, configs)
- `creatures/player.cpp`: content reconstruction of the BFG-removed original; from the 3ffa66f1 reconstruction: Player(path, map) and an equipped-items view (same-commit player.h)
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: content reconstruction of the BFG-removed original; from the a1107283 reconstruction: effects are data-driven Effect(type, caster, duration) objects (same-commit effect.h, surviving effect.cpp)
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: content reconstruction of the BFG-removed original; from the 27745415 reconstruction: MapObject::moveTo gains the silent flag declared in the same-commit map.h (silent moves only place the object)
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; from the fe3928a0 reconstruction: init renamed loadFromJson with saveToJson, main stat name and shadow resistance (same-commit stats.h)
- `view/gamescene.cpp`: content reconstruction of the BFG-removed original; from the b1f98e58 reconstruction: the player is restored from the saved player.json introduced in this commit
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `5f3e1511abd08b990494cbab59ac8e8566748a51cb290de8428e9a854532cd8c`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
