# Recovered game snapshot

Original commit: `a43f8e4b3bb03491b0b64b5fc0bb3e33fe127073`. Original tree: `cfa5daf3063627fe1245d248937884f6833320f2`.
Startup was verified from identical recovered sources at `a43f8e4b3bb03491b0b64b5fc0bb3e33fe127073`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, with CPython 2.7 development files and its matching Boost.Python library. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
qmake game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' -after TARGET=RecoveryGame DESTDIR=.
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

compatibilityRepair: 1, exactOriginal: 58, reconstruction: 17.

- `config/objects/interactions.json`: Missing interaction configuration reconstructed from donor properties plus actual matching Python class names, genuine #331 config/tiles.json handler/class schema and CTypeHandler.cpp PyTypeHandler qualified-name construction. Restores game.interaction class qualification and PyTypeHandler selection; preserves donor action properties. Not an exact original.
- `config/objects/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=97
- `config/objects/weapons.json`: working reconstruction
- `format.py`: unverified donor reconstruction; 18f71340e6334db61d3abc88ac99ac118270d7d1:format.py; headerMatch=0; apiOverlap=0/10000; distance=20
- `maps/map.json`: working reconstruction
- `scripts/game/interaction.py`: unverified donor reconstruction; 21c04c61c564bb91953b90218c6cf4bed54417a9:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=25
- `src/CCreature.cpp`: working reconstruction
- `src/CCreature.h`: Reconstructed combined CCreature/player/monster declarations from intact #247 separate headers, same-commit surviving APIs/callers, and the #331 split CPlayer/CMonster declarations; original bytes and unspecified internal deltas unavailable. No compilation/runtime validation.
- `src/CGamePanel.cpp`: working reconstruction
- `src/CInteraction.cpp`: working reconstruction
- `src/CItem.cpp`: working reconstruction
- `src/CMap.cpp`: working reconstruction
- `src/CObjectHandler.cpp`: working reconstruction
- `src/CPathFinder.cpp`: working reconstruction
- `src/CPlayerView.cpp`: working reconstruction
- `src/GameScript.cpp`: working reconstruction
- `src/Stats.h`: working reconstruction
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `7f9e531f1b1e30aeccc09ae277d5058307b98b5c23f84cb6627979f7901cbe2e`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
