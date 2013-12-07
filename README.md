# Recovered game snapshot

Original commit: `b9ae428bb65478f78f5e7e883ba3b2dd9e0af8ae`. Original tree: `a52f6a83298998702d2b76e5a959df9cc2ae4906`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler. The verified tool versions were:

- g++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0
- QMake version 3.1
- Using Qt version 5.15.18 in /tmp/nouraajd-recovery-qt/root/usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
qmake Game.pro -after TARGET=RecoveryGame DESTDIR=.
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

compatibilityRepair: 11, exactOriginal: 22, reconstruction: 11.

- `Game.pro`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:Game.pro
- `creatures/creature.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/creature.cpp
- `images/buildings/cave/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/cave/0.png; headerMatch=0; apiOverlap=0/10000; distance=160
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=106
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=106
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=156
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=156
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=106
- `map/map.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:map/map.cpp
- `stats/stats.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:stats/stats.cpp
- `view/gamescene.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:view/gamescene.cpp
- `animation/animatedobject.h`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:animation/animatedobject.h
- `animation/animationprovider.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:animation/animationprovider.cpp
- `creatures/monsters/pritz.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/monsters/pritz.cpp
- `creatures/monsters/pritzmage.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/monsters/pritzmage.cpp
- `creatures/players/mage.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/players/mage.cpp
- `creatures/players/player.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/players/player.cpp
- `creatures/players/rogue.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/players/rogue.cpp
- `creatures/players/warrior.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:creatures/players/warrior.cpp
- `map/map.h`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:map/map.h
- `map/tiles/tile.h`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:map/tiles/tile.h
- `view/gameview.cpp`: unverified donor reconstruction; earliest compatibility set 108bdcbeda04cefeba5e1895f91df023cea8487f:view/gameview.cpp

Restored source fingerprint: `4dd9688483ab8e3fc0b8890ed80178454b335e16a0520d0c4be8fac4141e53b5`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
