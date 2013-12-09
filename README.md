# Recovered game snapshot

Original commit: `6249de1f73f78e69d83773a7645f69e7e64cc5f3`. Original tree: `15dfb18cc1d3b83d0cd777a8683692a4e79c45db`.
Startup was verified from identical recovered sources at `6249de1f73f78e69d83773a7645f69e7e64cc5f3`.

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

- `Game.pro`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:Game.pro; headerMatch=0; apiOverlap=0/10000; distance=7
- `creatures/creature.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `images/buildings/cave/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/cave/0.png; headerMatch=0; apiOverlap=0/10000; distance=154
- `images/tiles/grass/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/grass/0.png; headerMatch=0; apiOverlap=0/10000; distance=100
- `images/tiles/ground/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/ground/0.png; headerMatch=0; apiOverlap=0/10000; distance=100
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=150
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=150
- `images/tiles/water/0.png`: unverified donor reconstruction; c049ac73064442354af6224d06fe1c8b847bb8d9:images/tiles/water/0.png; headerMatch=0; apiOverlap=0/10000; distance=100
- `interactions/interaction.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/reader.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/value.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/writer.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: unverified donor reconstruction; 108bdcbeda04cefeba5e1895f91df023cea8487f:map/map.cpp; headerMatch=0; apiOverlap=9500/10000; distance=7
- `stats/stats.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `view/gamescene.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `animation/animatedobject.h`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `creatures/players/player.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `effects/damageovertime.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `effects/effect.cpp`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `effects/effect.h`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license
- `map/map.h`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.
- `map/tiles/tile.h`: ReconstructedvalueStats JSON loader against exactf4bf8a28/6249de1f declarations; preserveoriginalSorcerer/Assasin/Warrior constructors, authoredJSON values andsubclasslevelUp dispatch. Registry variant implementsrealprototypes/clones/cleanup. Build/startup pending.

Restored source fingerprint: `91b05af8a5e2a5425b01be85a318aa29447a7a990e3649662474fa2320ed8cb7`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
