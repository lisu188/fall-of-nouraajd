# Recovered game snapshot

Original commit: `eb8276b2fc795f3af5f36370c209db85c1fb818d`. Original tree: `e66dd5c26c055f78ad0f29d2254b2bf6b5202612`.
Startup was verified from identical recovered sources at `eb8276b2fc795f3af5f36370c209db85c1fb818d`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, with CPython 2.7 development files and its matching Boost.Python library. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

This version uses its original `preprocessor.py` and `classes.json` with CPython 2.7.18 to
generate `gen/prop.h` and refresh marked property blocks in headers before qmake. Run this
on a separate build copy: the original generator can modify existing source headers.

Build from this snapshot's root directory:

```sh
python2.7 -B preprocessor.py
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

compatibilityRepair: 2, exactOriginal: 65, reconstruction: 52.

- `Game.pro`: content reconstruction of the BFG-removed original; carried forward unchanged from the previous reconstruction of Game.pro
- `config/object.json`: unverified donor reconstruction; split object descriptors e8b7c3d0e6da989122a0587943a98504342da3cd:config/objects flattened to observed legacy class/path API; target tile/interaction entries preserved; species stats retain uncertainty of reconstructed creatures catalog
- `format.py`: unverified donor reconstruction; 51c2e9b0b64c86a8e593a5231c3ef9e44efc5af1:format.py; headerMatch=0; apiOverlap=0/10000; distance=8
- `game.pro`: content reconstruction of the BFG-removed original; Ported verified #248 project rules through the #249 source and header renames, removed the merged scrollobject unit and selected the prefixed scene header in the shared Python module.
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=66
- `lib/json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/reader.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/value.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/writer.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/tinyxml/tinystr.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxml.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxml.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxmlparser.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tmx/TmxLayer.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxLayer.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxMap.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxMap.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxTileset.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/zlib/adler32.c`: Unmodified official zlib v1.2.5 adler32.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/crc32.c`: Unmodified official zlib v1.2.5 crc32.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/deflate.c`: Unmodified official zlib v1.2.5 deflate.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/deflate.h`: Missing vendored zlib source reconstructed from official zlib1.2.5 fossil archive. The exact surviving zconf.h, inflate.h, inftrees.h and other vendor files match1.2.5 ignoring whitespace; prior1.2.7 donor fails real TMX compilation on missing z_const/Z_ARG/z_crc_t. Official source bytes preserved; original historical file bytes unavailable and not claimed exact. Raw official Git blob differs from original BFG ID; classification remains inferred, not exactOriginal. All16 replacements linked in native #260.
- `lib/zlib/gzguts.h`: Missing vendored zlib source reconstructed from official zlib1.2.5 fossil archive. The exact surviving zconf.h, inflate.h, inftrees.h and other vendor files match1.2.5 ignoring whitespace; prior1.2.7 donor fails real TMX compilation on missing z_const/Z_ARG/z_crc_t. Official source bytes preserved; original historical file bytes unavailable and not claimed exact. Raw official Git blob differs from original BFG ID; classification remains inferred, not exactOriginal. All16 replacements linked in native #260.
- `lib/zlib/gzlib.c`: Unmodified official zlib v1.2.5 gzlib.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzread.c`: Unmodified official zlib v1.2.5 gzread.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzwrite.c`: Unmodified official zlib v1.2.5 gzwrite.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/infback.c`: Unmodified official zlib v1.2.5 infback.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inffast.c`: Unmodified official zlib v1.2.5 inffast.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inflate.c`: Unmodified official zlib v1.2.5 inflate.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inftrees.c`: Unmodified official zlib v1.2.5 inftrees.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/trees.c`: Unmodified official zlib v1.2.5 trees.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zlib.h`: Missing vendored zlib source reconstructed from official zlib1.2.5 fossil archive. The exact surviving zconf.h, inflate.h, inftrees.h and other vendor files match1.2.5 ignoring whitespace; prior1.2.7 donor fails real TMX compilation on missing z_const/Z_ARG/z_crc_t. Official source bytes preserved; original historical file bytes unavailable and not claimed exact. Raw official Git blob differs from original BFG ID; classification remains inferred, not exactOriginal. All16 replacements linked in native #260.
- `lib/zlib/zutil.c`: Unmodified official zlib v1.2.5 zutil.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zutil.h`: Missing vendored zlib source reconstructed from official zlib1.2.5 fossil archive. The exact surviving zconf.h, inflate.h, inftrees.h and other vendor files match1.2.5 ignoring whitespace; prior1.2.7 donor fails real TMX compilation on missing z_const/Z_ARG/z_crc_t. Official source bytes preserved; original historical file bytes unavailable and not claimed exact. Raw official Git blob differs from original BFG ID; classification remains inferred, not exactOriginal. All16 replacements linked in native #260.
- `maps/map.tmx`: Missing TMX map reconstructed from the prior converted later-map donor, removing only Market and StartEvent objects unsupported by the genuine 2014-09-09 target APIs/configuration/scripts. The original target misc.json defines Event only, buildings.json defines Cave/Teleporter, CBuilding.h has no Market, and the original scripts/game/object.py defines Cave/Teleporter only. No fake classes/events or empty script substitutes. All tile geometry, tilesets, layer metadata, entry coordinates and six supported Cave/Teleporter/ChaosSword objects are preserved. Exact original map bytes and its lost event content remain unavailable; this is an inferred donor adaptation.
- `scripts/game/interaction.py`: unverified donor reconstruction; 21c04c61c564bb91953b90218c6cf4bed54417a9:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=7
- `src/CCreature.cpp`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/CCreature.h`: Reconstructed combined CCreature/player/monster declarations from intact #247 separate headers, same-commit surviving APIs/callers, and the #331 split CPlayer/CMonster declarations; original bytes and unspecified internal deltas unavailable. No compilation/runtime validation.
- `src/CGamePanel.cpp`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/CGameView.cpp`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/CInteraction.cpp`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/CMap.cpp`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/CMap.h`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/CMapObject.cpp`: content reconstruction of the BFG-removed original; Split the #247 map and event sources at the #248 class rename. The unchanged #249–253 blob follows the scene player through getPlayer(), and selects the renamed tile header using project path evidence.
- `src/CPathFinder.cpp`: content reconstruction of the BFG-removed original; Ported the verified #248 sources through the #249 scene, view, slot, script engine and loot provider renames; retained the surviving parent scene implementation. Shared CMapObject includes the renamed tile header when present at #252.
- `src/GameScript.cpp`: content reconstruction of the BFG-removed original; Adapted the Boost.Python module donor to the surviving #248 Python 2 scriptmanager, game/object.py and interaction.py imports, string-keyed numeric Stats and Damage accessors and explicit Interaction alias; callback bodies are inferred.
- `src/playerlistview.cpp`: content reconstruction of the BFG-removed original; Reassembled #248 player-list and scroll implementations in their merged #249 unit. Stats retains typed accessors and copies declared members into a fresh QObject; the Damage macro in the surviving header supplies its accessors.
- `src/stats.cpp`: content reconstruction of the BFG-removed original; Reassembled #248 player-list and scroll implementations in their merged #249 unit. Stats retains typed accessors and copies declared members into a fresh QObject; the Damage macro in the surviving header supplies its accessors.
- `lib/json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `47984c1403919a0f2ce356d667cb4c0024039129abc976806456c013f215bcae`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
