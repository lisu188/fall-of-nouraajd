# Recovered game snapshot

Original commit: `c4d43a9f8ddd1980f4b39a659d63c68c6a2de31c`. Original tree: `e0d8a77808b5620bac1be16bea71d51b2f4475d1`.
Startup was verified from identical recovered sources at `c4d43a9f8ddd1980f4b39a659d63c68c6a2de31c`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, with CPython 3.3 development files and its matching Boost.Python library. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_python_shutdown.py
(cd python && qmake python.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' 'QMAKE_AR=gcc-ar-5 cqs' && make -j"$(nproc)")
(cd core && qmake core.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' 'QMAKE_AR=gcc-ar-5 cqs' -after TARGET=RecoveryGame DESTDIR=. && make -j"$(nproc)")
export LD_LIBRARY_PATH="$PWD/python${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
./core/RecoveryGame
```

For an isolated launch, use:

```sh
LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software xvfb-run -a --server-args="-screen 0 1920x1080x24" ./core/RecoveryGame
```

The automated readiness observer used for verification is recorded in the attached evidence; ordinary
launches run the game's original entry point. Startup evidence does not establish full gameplay equivalence.

## Recovery provenance

compatibilityRepair: 2, exactOriginal: 58, reconstruction: 34.

- `config/objects/interactions.json`: Missing interaction configuration reconstructed from donor properties plus actual matching Python class names, genuine #331 config/tiles.json handler/class schema and CTypeHandler.cpp PyTypeHandler qualified-name construction. Restores game.interaction class qualification and PyTypeHandler selection; preserves donor action properties. Not an exact original.
- `config/objects/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=94
- `config/objects/weapons.json`: Inferred missing #263 implementation from native-verified #260–262 reconstructions and actual same-commit original headers/callers; surviving original bytes remain unchanged. Replace demonstrably wrong future donor containing duplicate tile definitions with the nearest native-verified262 weapon configuration, retaining actual weapon ids, bonuses, interactions and original263 declared Qt property schema. Inferred data, not recovered original balancing/layout.
- `core/src/CCreature.cpp`: Inferred #266 missing implementation grounded in native-verified263–265 bodies and actual original266 JSON/property/three-argument moveTo/bool item-use migration. Preserve all surviving original bytes. Original inferred combined266 header deliberately omits obsolete loadFromJson; remove that member rather than invent a declaration. Public getStats/addItem/addAction/setItem APIs let missing factory initialize actual configured state; original QObject property path stores configured sw read by getScale, with direct static factory still populating genuine protected sw/stats. Keep real combat, bonuses, level/effects, slot invariants and signals.
- `core/src/CCreature.h`: Reconstructed combined CCreature/player/monster declarations from intact #247 separate headers, same-commit surviving APIs/callers, and the #331 split CPlayer/CMonster declarations; original bytes and unspecified internal deltas unavailable. No compilation/runtime validation.
- `core/src/CGamePanel.cpp`: Inferred missing268 input, preserving every surviving original byte. Actual header declarations and all surviving callers are unchanged from verified266/267; retain the genuine panel/inventory/action/text/backpack implementations. Unavailable original268 body changes cannot be inferred exactly.
- `core/src/CInteraction.cpp`: Inferred #266 missing implementation grounded in native-verified263–265 bodies and actual original266 JSON/property/three-argument moveTo/bool item-use migration. Preserve all surviving original bytes. Retain all genuine function-based Python interaction dispatch and native authored effects, adapting only removal of the no-longer-declared Effect::saveToJson. Effect bodies remain grounded in surviving scripts/game/effect.py and earlier genuine APIs, not placeholders.
- `core/src/CItem.cpp`: Inferred #266 missing implementation grounded in native-verified263–265 bodies and actual original266 JSON/property/three-argument moveTo/bool item-use migration. Preserve all surviving original bytes. Match real bool onUse migration: equip returns non-consumption; actual Life/Mana effects and displayed scroll text return consumption, and single-use mouse path removes only after successful use. Remove obsolete loader member; preserve declared armor named constructor with actual config and proper base copy state. Keep actual interactions/equipment/bonus/potion behavior, not no-op callbacks.
- `core/src/CMap.cpp`: Inferred #266 missing implementation grounded in native-verified263–265 bodies and actual original266 JSON/property/three-argument moveTo/bool item-use migration. Preserve all surviving original bytes. Restore real original loadMap(QJsonObject)/handleTileLayer/handleObjectLayer API using Tiled JSON tileproperties/layer-data/object-property semantics from intact55e6516:CMapLoader.cpp, with firstgid normalization from the validated TMX donor and explicit rectangular dimensions, retaining validated tile/object ownership, movement, levels and entry APIs. Honor rectangular dimensions and declared three-argument moves. Source map data is explicitly inferred separately; unsupported schemas/classes fail, no fake objects.
- `core/src/CObjectHandler.cpp`: content reconstruction of the BFG-removed original; carry the verified factory for the unchanged interface and include the script engine directly after its transitive include was removed
- `core/src/CPathFinder.cpp`: Inferred missing #261 body from native-verified #260 reconstruction and exact same-commit original header/callers, preserving all surviving bytes. Retain real cardinal/random/cost-field path implementations and add only the declared CSmartPathFinder::canStep wrapper to the genuine CMap::canStep API. No pathfinding behavior/performance parity claim.
- `core/src/CPlayerView.cpp`: Inferred missing #263 implementation from native-verified #260–262 reconstructions and actual same-commit original headers/callers; surviving original bytes remain unchanged. Carry every actual261 slot method through the262 combined declaration. Original CAnimatedObject is now QObject+QGraphicsPixmapItem and places CObjectData(this) in MIME data, so read the genuine MIME source with checked dynamic casts instead of stale QWidget event->source(). Match original CItemSlot::checkType(CItem*) and one-argument setAnimation. Inventory/equipment and drag/drop actions remain real.
- `core/src/GameScript.cpp`: content reconstruction of the BFG-removed original; reuse the accepted neighboring Python 3.3 bindings against the surviving Windows-build refactor interfaces
- `core/src/Stats.h`: Content reconstruction matching exact original #260 Stats.cpp e9d15a08d8073b9ec1462a7e542db131edd1314f: const numeric getter declarations, out-of-line setters, QString main/getMainValue. Use intact55e6516e:Stats.h property/declaration layout and zero initialized fields, retain era-correct QObject base and original257 PROPERTY_ACCESSOR semantics. Include QVariant/cmath explicitly for complete genuine APIs and Util::Coords::getDist. Metatype declarations remain owned by exact same-commit ReflectTypes.cpp; no surviving source modified.
- `format.py`: unverified donor reconstruction; 18f71340e6334db61d3abc88ac99ac118270d7d1:format.py; headerMatch=0; apiOverlap=0/10000; distance=17
- `maps/map.json`: Inferred missing268 input, preserving every surviving original byte. Actual Tiled JSON loader API is unchanged; retain audited266 deterministic conversion of supported265 TMX donor geometry, all40000 tile IDs and six supported actors. Original268 map changes and omitted future event/shop mechanics remain unavailable; no exact layout/gameplay parity claim.
- `python/converter/builtin_converters.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/converter/from_python.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/converter/registry.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/converter/type_id.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/dict.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/exec.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/list.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/numeric.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/object/class.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/object/enum.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/object/function.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/object/function_doc_signature.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=93
- `python/object/life_support.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=85
- `python/object_protocol.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=93
- `scripts/game/interaction.py`: unverified donor reconstruction; 21c04c61c564bb91953b90218c6cf4bed54417a9:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=28
- `python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `f74e404fccda93214126b391b15e2d80524df5862a46807f0d32873895bef01a`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
