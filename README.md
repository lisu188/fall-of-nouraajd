# Recovered game snapshot

Original commit: `4a6a0310a4c84dbb67673f9c9ec1724da2fbf4f6`. Original tree: `492bd374cb3b456711d03adc525b4db6531399b4`.
Startup was verified from identical recovered sources at `4a6a0310a4c84dbb67673f9c9ec1724da2fbf4f6`.

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

compatibilityRepair: 8, exactOriginal: 25, reconstruction: 19.

- `Game.pro`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:Game.pro; headerMatch=0; apiOverlap=0/10000; distance=8
- `creatures/creature.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `images/buildings/cave/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/cave/0.png; headerMatch=0; apiOverlap=0/10000; distance=153
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=99
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=99
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=149
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=149
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=99
- `interactions/interaction.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/reader.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/value.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/writer.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:map/map.cpp; headerMatch=0; apiOverlap=9500/10000; distance=8
- `stats/stats.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `view/gamescene.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `animation/animatedobject.h`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `creatures/players/player.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `effects/damageovertime.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `effects/effect.cpp`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `effects/effect.h`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license
- `map/map.h`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.
- `map/tiles/tile.h`: Reconstructed first JSON-era implementation from original4a6a0310 declarations, authored config and surviving callers, with root108 body as a structural donor; synthetic formulas and effects lifecycle are explicit recovery choices. Build/startup pending.

Restored source fingerprint: `2c19c1a5aca15bdffbb3687e57a338860a1db6d6af5a86fcf73696d408bc3b92`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
