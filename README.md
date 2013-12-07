# Recovered game snapshot

Original commit: `b9ae428bb65478f78f5e7e883ba3b2dd9e0af8ae`. Original tree: `a52f6a83298998702d2b76e5a959df9cc2ae4906`.
Startup was verified from identical recovered sources at `b9ae428bb65478f78f5e7e883ba3b2dd9e0af8ae`.

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

exactOriginal: 23, reconstruction: 10.

- `Game.pro`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:Game.pro; headerMatch=0; apiOverlap=0/10000; distance=2 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `creatures/creature.cpp`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/creature.cpp; headerMatch=1; apiOverlap=10000/10000; distance=2 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=105 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `map/map.cpp`: content reconstruction of the BFG-removed original; reconstructed against the original map.h/tile.h API (private AnimatedObject bases, Tile::addToGame, Destroyer-owned objects); replaces the 2026 donor that required modified headers
- `stats/stats.cpp`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:stats/stats.cpp; headerMatch=1; apiOverlap=10000/10000; distance=2 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `view/gamescene.cpp`: content reconstruction of the BFG-removed original; adapted from the 2026 donor (108bdcbe view/gamescene.cpp) to the original headers: tiles are created through Map::getTile and player views are positioned by GameView::resize

Restored source fingerprint: `cea519bf0b15967eb8e57df55f07da76b489d36052e4c131446cb759d4b776e7`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
