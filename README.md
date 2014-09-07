# Recovered game snapshot

Original commit: `2565fadfd42ef79564159dbea40ec7c47c1a57f0`. Original tree: `eae1fe5dfbfd25187a96bf7c957d358d5db121ee`.
Startup was verified from identical recovered sources at `2565fadfd42ef79564159dbea40ec7c47c1a57f0`.

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

compatibilityRepair: 1, exactOriginal: 61, reconstruction: 49.

- `Game.pro`: content reconstruction of the BFG-removed original; carried forward unchanged from the previous reconstruction of Game.pro
- `config/objects/interactions.json`: unverified donor reconstruction; 9fc9416b1025044633a6b789212f67c56ecaafba:config/objects/interactions.json; headerMatch=0; apiOverlap=0/10000; distance=1
- `config/objects/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=107
- `config/objects/weapons.json`: Replace unrelated tile-config donor for missing weapons.json with intact55e6516e:config/weapons.json blob0a32d5f0cc003ae07cfd43d092921d76ec82f3e5. Original weapon image identities, CWeapon API and authored ChaosSword/Staff/Dagger references support the donor; add original CTypeHandler schema. Numeric donor stats are inferred, not exact recovered target balance.
- `format.py`: unverified donor reconstruction; 51c2e9b0b64c86a8e593a5231c3ef9e44efc5af1:format.py; headerMatch=0; apiOverlap=0/10000; distance=16
- `game.pro`: Refine missing application .pro reconstruction with all33 supplied Tmx/base64/tinyxml/zlib C/C++ translation units and lib include path. Actual reconstructed map now invokes the parser, exposing fail-before unresolved Tmx link symbols. Preserve Python2.7 ABI, unique reconstructed application marker, and existing path guards; no surviving project edits or new production dependency.
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=74
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
- `scripts/game/interaction.py`: unverified donor reconstruction; 21c04c61c564bb91953b90218c6cf4bed54417a9:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=15
- `src/CCreature.cpp`: Infer missing #258–259 source from native-verified adjacent #260 reconstruction after checking same-commit original headers/callers; preserve every surviving input. Reconstructed combined header differs only by genuine CPlayer(CMap*,QString) constructor; implement delegation/map/load behavior. Use original int Stats::getMain rather than future getMainValue and apply actual main-stat selector explicitly. Keep declared null equipment slots.
- `src/CCreature.h`: Reconstructed combined CCreature/player/monster declarations from intact #247 separate headers, same-commit surviving APIs/callers, and the #331 split CPlayer/CMonster declarations; original bytes and unspecified internal deltas unavailable. No compilation/runtime validation.
- `src/CGamePanel.cpp`: Infer missing #258–259 source from native-verified adjacent #260 reconstruction after checking same-commit original headers/callers; preserve every surviving input. Original CGamePanel.h is byte-identical; actual panel interfaces retained.
- `src/CGameView.cpp`: Inferred reconstruction adapted from intact CGameView.cpp donors and same-commit CGameView.h/CGameScene.cpp. The genuine #257 menu makes the view a QWidget child and hides itself; #258 changes to QObject parenting. Reconstructed show() promotes only a non-window child to Qt::Window before showNormal(), preserving the menu and all surviving source bytes. Actual #257 before/after frame plus new #258/#259 ordinary native proofs are attached. Both fresh adjacent proofs pass full compile/link and map/player/frame/clean exit; gameplay and exact source remain unverified.
- `src/CInteraction.cpp`: Generated missing-body reconstruction for genuine #260 CInteraction.h Effect (non-QObject constructor/callback map) ABI. Use intact #290 CInteraction.cpp blob98248e766f1e2921c117dbc064325ddb8824e70a mouse/action/effect lifecycle as adapted donor; invoke actual #260 scripts/game/interaction.py functions, not later class instances. Native Effect callbacks transcribe intact #331beef9d87 scripts/game/effect.py blob2ba257597feba52e3ba108b1056e3a5443b8ba1c arithmetic/return semantics using original Effect/Stats-pointer APIs. Barrier false and ArmorOfEndlessWinter missing restriction are genuine donor behavior/limitation. Maps original StunEffect spelling to genuine Stun config entry. saveToJson field shape is reconstructed and unverified; no whole-game or gameplay parity claim.
- `src/CItem.cpp`: Generated adaptation of intact #2475fe60e7c:src/item.cpp blob6776325d5546af8c14a14c3433c5021eeac82566 and potion.cpp blob465840edb9a59f0e82e7b72fd12cd109f0da9e13. Combine genuine #260 item classes, apply C-prefix/QString/default constructor changes, retain real pickup/equip/unequip/mouse-use/health-mana potion behavior, load JSON properties from actual config/objects layout and use original getStats()->addBonus/removeBonus API. No future GUI handler or event API, no surviving source edits. Accept both genuine target flat item/armor configuration and nested property descriptors while preserving their actual stats/equip/potion behavior.
- `src/CMap.cpp`: Infer missing #258 monolithic CMap.cpp from native-verified adjacent #259 generated reconstruction. All original CMap/CMapObject/PlayerView/GameView/PathFinder/ObjectHandler headers are byte-identical between these trees; original commit message is tiles then tile visible. Preserve actual Tmx/scene/set-of-objects interface, missing-property guards and unchanged geometry data. Procedural/pathfinding behavior and exact missing original map implementation remain unverified.
- `src/CMapObject.cpp`: Infer missing #258–259 source from native-verified adjacent #260 reconstruction after checking same-commit original headers/callers; preserve every surviving input. Original #259 CMapObject.h lacks the #260 explicit destructor declaration; omit that definition. Preserve genuine four-argument moveTo/no-argument callbacks/Tmx property APIs.
- `src/CObjectHandler.cpp`: Infer missing #258–259 source from native-verified adjacent #260 reconstruction after checking same-commit original headers/callers; preserve every surviving input. Original CObjectHandler/CTypeHandler APIs are byte-identical; support actual flat and nested object descriptors, no stand-in types. Native #259 clean-exit regression and diagnostic backtrace exposed QWidget destruction through an invalid non-widget QObject parent. Actual CAnimatedObject inherits QWidget, so give it the genuine owning CGameView QWidget; graphics ownership remains in original scene/item hierarchy.
- `src/CPathFinder.cpp`: Infer missing #258–259 source from native-verified adjacent #260 reconstruction after checking same-commit original headers/callers; preserve every surviving input. Original CPathFinder.h is byte-identical; cardinal/random/cost-field behavior and performance remain unverified.
- `src/CPlayerView.cpp`: Infer missing #258–259 source from native-verified adjacent #260 reconstruction after checking same-commit original headers/callers; preserve every surviving input. Original CPlayerView.h is byte-identical; actual PNG paths and initialized stats-view pointer retained. The actual #259 arrow assets are directory/0.png, unlike #260 flat PNGs; retain directory-slash paths after the native startup failure exposed this boundary.
- `src/GameScript.cpp`: Retain reconstructed missing #258–259 Boost.Python module and exact init_game/Python2.7 ABI. Actual target script imports Interaction and calls Stats.getDamage; expose real CInteraction alias and genuine generated Stats getter, as native-proven #260 does. No stand-in or no-op binding.
- `src/Stats.cpp`: unverified donor reconstruction; 9fc9416b1025044633a6b789212f67c56ecaafba:src/Stats.cpp; headerMatch=0; apiOverlap=0/10000; distance=1
- `src/Stats.h`: Infer missing #258–259 Stats.h from nearest pre-deletion Stats header plus all22 exact fields emitted by genuine #257 generator/descriptors (retained generated-prop.h). Inline actual PROP rows using same-commit original Util.h macro; gen/ was genuinely deleted in #258, so no missing generated include remains. Preserve older int getMain/pointer-main Stats API, unlike #260 QString getMain/getMainValue. Not exact original source.
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `529ddaf7de073e418446b125613c46d7d6a252b2480f8a354f218cccfd904d24`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
