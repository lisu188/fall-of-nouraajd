# Recovered game snapshot

Original commit: `99979aa8abd08c9fcccb17277873beb1b204d8e1`. Original tree: `ad9a1d245766b1f0c7ab688deb0d8896353af3c9`.
Startup was verified from identical recovered sources at `99979aa8abd08c9fcccb17277873beb1b204d8e1`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

Startup used a derived legacy tile configuration on an isolated build copy. The unchanged original
CTile loader reads `config/tiles.json`, while the unchanged original tile data moved to
`config/objects/tiles.json`. The attached hash-pinned helper flattens each exact original properties
object, renames `animation` to `path`, and preserves `canStep`. It creates only the missing legacy
configuration and refuses to replace existing data. Original source and configuration bytes remain
unchanged. This is explicitly inferred compatibility, not recovery of a deleted original file;
the input/output hashes and preparation proof are attached. Gameplay parity remains unverified.

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
python3 recovery/prepare_legacy_tile_configuration.py
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

compatibilityRepair: 1, exactOriginal: 61, reconstruction: 47.

- `Game.pro`: content reconstruction of the BFG-removed original; carried forward unchanged from the previous reconstruction of Game.pro
- `config/objects/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=109
- `config/objects/weapons.json`: Inferred missing #256 implementation from native-verified #257 bodies and same-commit surviving declarations/callers; surviving source bytes are unchanged. Use the explicit #257 reconstruction with the same surviving weapon class declarations and genuine item/interaction configuration schema; item balance values remain inferred donor data, not exact recovery.
- `format.py`: unverified donor reconstruction; 51c2e9b0b64c86a8e593a5231c3ef9e44efc5af1:format.py; headerMatch=0; apiOverlap=0/10000; distance=14
- `game.pro`: Inferred missing #256 implementation from native-verified #257 bodies and same-commit surviving declarations/callers; surviving source bytes are unchanged. Project selects actual same-commit application, engine sources, headers and all33 vendored TMX/non-jsoncpp C/C++ implementation units; no surviving project modified.
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=72
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
- `scripts/game/interaction.py`: unverified donor reconstruction; 21c04c61c564bb91953b90218c6cf4bed54417a9:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=13
- `src/CCreature.cpp`: Inferred missing #256 implementation from native-verified #257 bodies and same-commit surviving declarations/callers; surviving source bytes are unchanged. Use genuine #256 Stats::loadFromJson and copy construction rather than the future assignment operator. Preserve actual combined CCreature/CPlayer/CMonster API, slot-map invariant, item/action mechanics and authored configuration; no fake class or callback.
- `src/CCreature.h`: Reconstructed combined CCreature/player/monster declarations from intact #247 separate headers, same-commit surviving APIs/callers, and the #331 split CPlayer/CMonster declarations; original bytes and unspecified internal deltas unavailable. No compilation/runtime validation.
- `src/CGamePanel.cpp`: Infer missing #257 body from native-verified #259 reconstruction, adapted only to same-commit original declarations/callers; preserve every surviving input. Original CGamePanel.h is unchanged; use public typeName rather than the future getter.
- `src/CGameView.cpp`: Inferred reconstruction adapted from intact CGameView.cpp donors and same-commit CGameView.h/CGameScene.cpp. The genuine #257 menu makes the view a QWidget child and hides itself; #258 changes to QObject parenting. Reconstructed show() promotes only a non-window child to Qt::Window before showNormal(), preserving the menu and all surviving source bytes. Actual #257 before/after frame plus new #258/#259 ordinary native proofs are attached. Both fresh adjacent proofs pass full compile/link and map/player/frame/clean exit; gameplay and exact source remain unverified.
- `src/CInteraction.cpp`: Infer missing #257 body from native-verified #259 reconstruction, adapted only to same-commit original declarations/callers; preserve every surviving input. Original interaction header still declares loadFromJson/non-const getManaCost and has no later effect/mana setters; load its intact flat configuration. Preserve genuine earlier effect functions and Python function namespace, not later event types.
- `src/CItem.cpp`: Inferred missing #256 implementation from native-verified #257 bodies and same-commit surviving declarations/callers; surviving source bytes are unchanged. Same-commit CItem.h lacks future bonus getters/setters and still requires CWeapon::getStats()->Stats*. Restore only this genuine API and real static item/potion factory mechanics; all action/equipment configuration remains actual.
- `src/CMap.cpp`: Infer missing #257 monolithic TMX map from native-verified #259 reconstruction, adapted to genuine original CMap.h: base dictionary holds tile-name QString values and separate tiles cache owns rendered CTile instances. Restore getTileSize/hide/showAll and lazy visible-tile construction using original CTile API. Keep exact Tmx property guards, direct set of world objects, no-argument callbacks and real map entry/geometry. Flat weapon map object uses actual static CItem factory. Procedural/pathfinding and exact historical source behavior remain inferred; native unverified.
- `src/CMapObject.cpp`: Infer missing #257 body from native-verified #259 reconstruction, adapted only to same-commit original declarations/callers; preserve every surviving input. Original CMapObject lacks future typeName/tooltip getters; preserve public field and pure loadFromJson base definition. Initialize genuine position fields; movement queries original string-valued map plus actual nested tile config. Real QWidget owner uses game view in this older inheritance era. Actual signal trace places the factory-era fault in QWidget::setParent: original factory first assigns a non-widget QObject parent. Clear that QObject relationship explicitly before assigning the valid game-view QWidget, within this missing body; original factory bytes and behavior remain exercised.
- `src/CPathFinder.cpp`: Infer missing #257 body from native-verified #259 reconstruction, adapted only to same-commit original declarations/callers; preserve every surviving input. Adapt verified cost-field/cardinal/random implementation to original string-valued tile map and its declared CSmartPathFinder::canStep method using real nested passability metadata. No pathfinding gameplay/performance acceptance yet.
- `src/CPlayerView.cpp`: Infer missing #257 body from native-verified #259 reconstruction, adapted only to same-commit original declarations/callers; preserve every surviving input. Original CPlayerView.h is unchanged; preserve real arrow directory assets and initialized stats widget.
- `src/GameScript.cpp`: Retain reconstructed missing #257 Boost module and exact init_game/Python2.7 ABI, exposing genuine CInteraction alias and generated Stats::getDamage required by actual script. No fake class/binding.
- `src/Stats.cpp`: Inferred missing #256 implementation from native-verified #257 bodies and same-commit surviving declarations/callers; surviving source bytes are unchanged. Actual original Stats.h predates copy assignment and still declares JSON load/save. Keep real generated numeric properties, add/remove bonuses and main-stat pointer, implementing those genuine JSON methods; copy constructor rebinds the main pointer to this object. Normalize the lower-case main names present in intact configuration. Preserve returned stat text lifetime within its const-char API rather than import the donor temporary-string lifetime error. Balance/gameplay parity remains unverified.
- `src/Util.h`: Inferred missing #256 implementation from native-verified #257 bodies and same-commit surviving declarations/callers; surviving source bytes are unchanged. Restore PROPERTY_ACCESSOR as a real Qt property macro from the immediately following intact macro.conf; #257 removes this macro from Util and expands exactly these real methods into original headers. Same Coords, task, comparer and PROP helpers from intact #257 Util. This is a donor adaptation, not exact original bytes.
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `ea8662c8a7704e00df25aa94474e12bd88337bb767fd9a052c0695dd212d6894`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
