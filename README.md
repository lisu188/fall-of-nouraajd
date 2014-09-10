# Recovered game snapshot

Original commit: `e8b7c3d0e6da989122a0587943a98504342da3cd`. Original tree: `08b67cf8633e706371bbfd9f6fdfc735c63f5757`.
Startup was verified from identical recovered sources at `e8b7c3d0e6da989122a0587943a98504342da3cd`.

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

compatibilityRepair: 1, exactOriginal: 62, reconstruction: 47.

- `config/objects/interactions.json`: unverified donor reconstruction; 9fc9416b1025044633a6b789212f67c56ecaafba:config/objects/interactions.json; headerMatch=0; apiOverlap=0/10000; distance=5
- `config/objects/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=103
- `config/objects/weapons.json`: working reconstruction
- `format.py`: unverified donor reconstruction; 51c2e9b0b64c86a8e593a5231c3ef9e44efc5af1:format.py; headerMatch=0; apiOverlap=0/10000; distance=20
- `game.pro`: working reconstruction
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=78
- `lib/tinyxml/tinystr.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxml.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxml.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxmlparser.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tmx/TmxLayer.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxLayer.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxMap.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxMap.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxTileset.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/zlib/adler32.c`: working reconstruction
- `lib/zlib/crc32.c`: working reconstruction
- `lib/zlib/deflate.c`: working reconstruction
- `lib/zlib/deflate.h`: working reconstruction
- `lib/zlib/gzguts.h`: working reconstruction
- `lib/zlib/gzlib.c`: working reconstruction
- `lib/zlib/gzread.c`: working reconstruction
- `lib/zlib/gzwrite.c`: working reconstruction
- `lib/zlib/infback.c`: working reconstruction
- `lib/zlib/inffast.c`: working reconstruction
- `lib/zlib/inflate.c`: working reconstruction
- `lib/zlib/inftrees.c`: working reconstruction
- `lib/zlib/trees.c`: working reconstruction
- `lib/zlib/zlib.h`: working reconstruction
- `lib/zlib/zutil.c`: working reconstruction
- `lib/zlib/zutil.h`: working reconstruction
- `maps/map.tmx`: working reconstruction
- `scripts/game/interaction.py`: unverified donor reconstruction; 21c04c61c564bb91953b90218c6cf4bed54417a9:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=19
- `src/CCreature.cpp`: working reconstruction
- `src/CCreature.h`: Reconstructed combined CCreature/player/monster declarations from intact #247 separate headers, same-commit surviving APIs/callers, and the #331 split CPlayer/CMonster declarations; original bytes and unspecified internal deltas unavailable. No compilation/runtime validation.
- `src/CGamePanel.cpp`: working reconstruction
- `src/CGameView.cpp`: working reconstruction
- `src/CInteraction.cpp`: working reconstruction
- `src/CItem.cpp`: working reconstruction
- `src/CMap.cpp`: working reconstruction
- `src/CMapObject.cpp`: working reconstruction
- `src/CObjectHandler.cpp`: working reconstruction
- `src/CPathFinder.cpp`: working reconstruction
- `src/CPlayerView.cpp`: working reconstruction
- `src/GameScript.cpp`: working reconstruction
- `src/Stats.h`: working reconstruction
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `ec6803fb065fdedb4b9b2de4b431da040a62ba38a5b147cc4cdcf9e76618242e`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
