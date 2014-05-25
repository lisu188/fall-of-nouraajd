# Recovered game snapshot

Original commit: `6cc78c34d64fdee43adca1b829ccf687daa62ced`. Original tree: `87ea8580651c311e0a64397425faa080539fb701`.
Startup was verified from identical recovered sources at `6cc78c34d64fdee43adca1b829ccf687daa62ced`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

The isolated build supplies the missing jsoncpp companions restored at #183.
Where needed, forwarding headers expose declarations from the merged headers.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_merged_headers.py
qmake Game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' -after TARGET=RecoveryGame DESTDIR=.
make -j"$(nproc)"
mkdir -p save
./RecoveryGame
```

For an isolated launch, use:

```sh
LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software xvfb-run -a --server-args="-screen 0 1920x1080x24" ./RecoveryGame
```

The automated readiness observer used for verification is recorded in the attached evidence; ordinary
launches run the game's original entry point. Startup evidence does not establish full gameplay equivalence.

## Recovery provenance

The genuine scene writes `save/game.sav` during shutdown. Verification prepared its empty
parent directory before startup, without changing source files or replacing existing save data.
The source call, source hash and created/preserved directory are recorded in verification metadata.

compatibilityRepair: 1, exactOriginal: 62, reconstruction: 48.

- `Game.pro`: content reconstruction of the BFG-removed original; qmake source and header lists follow the surviving relocated tree
- `config/creatures.json`: {'evidence': ['historical image directory IDs', 'config/map.json saved creature state when present'], 'inferred': ['missing initial stats', 'levelStats encoding and progression'], 'kind': 'reconstructed-config', 'note': 'Saved state is retained; absent stats are positive synthetic defaults. Build/startup unverified.', 'sourceCommit': '6cc78c34d64fdee43adca1b829ccf687daa62ced', 'verified': False}
- `config/items.json`: content reconstruction of the BFG-removed original; Adapted genuine119 config/items.json donor blob41d081fe6c796beab79afb418358b8af12cfa877 to missing original2081: adds only class Weapon/Armor/Potion from each actual legacy type, as required by surviving150 Item::getItem/QMetaType factory. Preserves every donor item name/path/stat/power/type. All lost original later item IDs, exact balance and slot metadata remain unavailable and are not invented. This is inferred missing-config compatibility, not original2081 bytes or gameplay parity. Root owns integration and affected-proof revalidation.
- `config/map.tmx`: unverified donor reconstruction; authored Tiled geometry/object coordinates from 55e6516e:maps/map1/map.json converted to XML; missing target script reference omitted
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=3
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
- `lib/tmx/TmxObject.cpp`: unverified donor reconstruction; 181f31e1e9a7f3516c7fbd3d4400aa0822c1d387:lib/tmx/TmxObject.cpp; headerMatch=0; apiOverlap=10000/10000; distance=55
- `lib/tmx/TmxTileset.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/zlib/adler32.c`: Unmodified official zlib v1.2.5 adler32.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/crc32.c`: Unmodified official zlib v1.2.5 crc32.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/deflate.c`: Unmodified official zlib v1.2.5 deflate.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/deflate.h`: Unmodified official zlib v1.2.5 deflate.h; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzlib.c`: Unmodified official zlib v1.2.5 gzlib.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzread.c`: Unmodified official zlib v1.2.5 gzread.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzwrite.c`: Unmodified official zlib v1.2.5 gzwrite.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/infback.c`: Unmodified official zlib v1.2.5 infback.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inffast.c`: Unmodified official zlib v1.2.5 inffast.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inflate.c`: Unmodified official zlib v1.2.5 inflate.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inftrees.c`: Unmodified official zlib v1.2.5 inftrees.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/trees.c`: Unmodified official zlib v1.2.5 trees.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zlib.h`: Unmodified official zlib v1.2.5 zlib.h; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zutil.c`: Unmodified official zlib v1.2.5 zutil.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zutil.h`: Unmodified official zlib v1.2.5 zutil.h; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `src/buildings/building.cpp`: content reconstruction of the BFG-removed original; #180 refactor merged the per-class sources into this unit, matching the same-commit merged header; bodies concatenated verbatim from the #179 restored building.cpp, cave.cpp, dungeon.cpp and teleporter.cpp (accepted #179 tree), includes rewritten to the #180 src/ layout; merge order and include set inferred; missing virtual methods inferred from the #182 reconstruction; matching #182 teleporter coordinates and enabled-state object avoids mixing JSON arrays and objects on shutdown
- `src/creatures/creature.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers. The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `src/creatures/player.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers; interaction.h included directly because the merged item.h no longer provides it. The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `src/interactions/interaction.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers. The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `src/items/item.cpp`: content reconstruction of the BFG-removed original; #180 refactor merged the per-class sources into this unit, matching the same-commit merged header; bodies concatenated verbatim from the #179 restored item.cpp, armor.cpp, belt.cpp, helmet.cpp, boots.cpp, gloves.cpp, weapon.cpp and smallweapon.cpp (accepted #179 tree), includes rewritten to the #180 src/ layout; merge order and include set inferred; missing virtual methods inferred from the #182 reconstruction
- `src/map/map.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers; MapObject animation member renamed dynamicAnimation and onMoveEnd removed to match the same-commit map.h. The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `src/pathfinder/pathfinder.cpp`: content reconstruction of the BFG-removed original; #180 refactor merged the per-class sources into this unit, matching the same-commit merged header; bodies concatenated verbatim from the #179 restored pathfinder.cpp, dumbpathfinder.cpp, randompathfinder.cpp and smartpathfinder.cpp (accepted #179 tree), includes rewritten to the #180 src/ layout; merge order and include set inferred
- `src/stats/stats.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers. The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `src/view/gamescene.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers; removed compression/compression.h include (directory deleted in #180, unused). The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `src/view/gameview.cpp`: content reconstruction of the BFG-removed original; moved by the #180 refactor; carried from the accepted #179 reconstruction of the same file with includes rewritten to the #180 src/ layout and merged headers. The #180 tree itself does not build: its surviving main.cpp includes deleted headers and registers Interaction without its declaration
- `lib/json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `f4b7e0dc6c1f960e86b64460704001cdbc96cb583223cd1318550d6808dbdc43`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
