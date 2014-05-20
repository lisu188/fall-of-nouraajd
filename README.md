# Recovered game snapshot

Original commit: `fef8eedb3fd0bda998d4dd59b7cd725c6c1540ab`. Original tree: `9c3a27ac2857eb9d2b3295de5ee476ba71b0bba9`.
Startup was verified from identical recovered sources at `fef8eedb3fd0bda998d4dd59b7cd725c6c1540ab`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

Startup and shutdown used explicit teleporter serialization compatibility. The original save
method writes coordinate array entries and then a named enabled field, which its JsonCpp rejects.
A separate derived translation unit changes only the save/load bodies to inverse JSON objects
containing x, y, z and enabled. All other teleporter methods retain their original bytes; the original
source file and header remain unchanged. Legacy coordinate arrays preserve the current enabled value,
initialized to true by every reviewed original header. The attached hash-pinned helper selects only
that derived unit after reading the project, preserving teleporting and ordinary save/shutdown paths.
Exact source/header/JsonCpp hashes and the semantic compatibility boundary are attached.
This establishes startup and shutdown with that compatibility step; gameplay parity is unverified.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, and Python 3 for the hash-pinned build-source preparation helper. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Use a separate build copy for this version. Its original source contains Windows separators
in quoted includes. The attached helper changes only those recorded literals, verifies each
source file's original and prepared SHA256, and preserves the recovered snapshot's provenance.

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_teleporter_serialization.py
python3 recovery/prepare_build_sources.py
qmake Game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' -after SOURCES-=buildings/teleporter.cpp 'SOURCES+=$$_PRO_FILE_PWD_/buildings/recovery_teleporter.cpp' -after TARGET=RecoveryGame DESTDIR=.
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

compatibilityRepair: 1, exactOriginal: 90, reconstruction: 20.

- `Game.pro`: Content reconstruction of the BFG-removed original; Missing qmake project inferred from accepted #157 settings and complete same-tree source/header/resource inventory, including vendored libraries and required zlib link. Original project bytes unavailable; configuration parity not claimed. Includes all15 genuine same-tree vendored zlib C translation units; exact-readable source/header files retained unchanged.
- `config/creatures.json`: {'evidence': ['historical image directory IDs', 'config/map.json saved creature state when present'], 'inferred': ['missing initial stats', 'levelStats encoding and progression'], 'kind': 'reconstructed-config', 'note': 'Saved state is retained; absent stats are positive synthetic defaults. Build/startup unverified.', 'sourceCommit': 'fef8eedb3fd0bda998d4dd59b7cd725c6c1540ab', 'verified': False}
- `config/items.json`: content reconstruction of the BFG-removed original; Adapted genuine119 config/items.json donor blob41d081fe6c796beab79afb418358b8af12cfa877 to missing original2081: adds only class Weapon/Armor/Potion from each actual legacy type, as required by surviving150 Item::getItem/QMetaType factory. Preserves every donor item name/path/stat/power/type. All lost original later item IDs, exact balance and slot metadata remain unavailable and are not invented. This is inferred missing-config compatibility, not original2081 bytes or gameplay parity. Root owns integration and affected-proof revalidation.
- `config/map.tmx`: unverified donor reconstruction; authored Tiled geometry/object coordinates from 55e6516e:maps/map1/map.json converted to XML; missing target script reference omitted
- `creatures/creature.cpp`: Content reconstruction of the BFG-removed original; Missing #150 Creature body inferred from native-verified #97 body and exact surviving #150 declarations/callers/config: ListItem base, ordered sets, slot-index equipment map, collection signals, lower-case coordinates. Slot initialization follows original config/slots.json and ItemSlot::update at(). Saves subtract equipped bonuses before reload. Formula, equipment serialization and historical gameplay parity remain inferred; no surviving source edited. Corrected inferred equipment reload: legacy inventory.weapon/armor apply only if present; modern equipment slots survive save/load. Before/after native regression and revalidation required.
- `creatures/player.cpp`: Missing #150 player body inferred from earlier surviving donor and exact original Player.h/GameView caller: restored declared update() to refresh inventory/action maps and emit statsChanged. Remaining donor combat preserved; historical behavior not proven.
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `interactions/interaction.cpp`: Missing #150 Interaction body inferred from native-verified #97 implementation and exact #150 surviving header: public/default/copy constructors, ListItem ordering and Effect state serialization added. Removed undeclared legacy setAnimation override, retaining inherited real resource loading. Historical ordering/effect persistence parity unverified.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Content reconstruction of the BFG-removed original; Missing body inferred by carrying accepted #170 reconstruction 6b6244e51180200914bebe6d31d0fc5f372d925b; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing #166 Map body inferred from native-verified #164/#165. Genuine getObjects changes from inline to external: return actual mapObjects. Added optional movement-completion callback dispatched after real animation or immediate non-silent move; base callback policy defaults to no action because no surviving #166 caller defines base effects. Genuine derived callbacks are dispatched virtually. Default policy, removed implementation changes and gameplay parity remain inferred. Missing #164 Map body inferred from accepted #163; only genuine header change adds virtual loadFromProps, now invoked with actual TMX object properties before positioning/adding each genuine object. Unknown original body behavior remains inferred. Missing body inferred by carrying accepted #161 reconstruction e197feb3953c9c65e51587a60fc2fe66155a063e; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing body inferred by carrying accepted #159 reconstruction f59850bc2948c48c34f05161ff83bf840234b80b; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing #159 Map/MapObject body inferred from accepted #150 body and genuine same-version APIs/config. Added real TMX layer/tileset/property loading and authored entry coordinates from genuine map.tmx, with available genuine object classes/configured items/creatures. Authored TMX names without a class in this revision (StartEvent, Market) are explicitly logged, not replaced by stand-ins. Object property behavior and removed body gameplay semantics remain unverified; no original edited. Corrected missing-body ownership: removeObject detaches without deleting, as genuine Item::onEnter transfers the live item to player inventory; original AnimatedObject/Destroyer retains lifetime registration. Actual QObject destroyed-signal before/after regression required.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `tmx/TmxLayer.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `tmx/TmxMap.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `tmx/TmxObject.cpp`: unverified donor reconstruction; fb2bcb07e3b2267e7f24c5a7cd48604180b1be0f:tmx/TmxObject.cpp; headerMatch=0; apiOverlap=10000/10000; distance=2
- `tmx/TmxTileset.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `view/gamescene.cpp`: Content reconstruction of the BFG-removed original; Missing body inferred by carrying accepted #166 reconstruction f50450a42a588a0a036ebff412b6ff245a8222cc; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing body inferred by carrying accepted #159 reconstruction 2e11b4ac70d1dd42150a0e3265af39cbe00d0955; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing #159 GameScene body inferred from accepted #150 body and newly declared Map::loadMapFromTmx/getEntry APIs plus genuine config/map.tmx. Loads actual authored terrain and places real Sorcerer at authored x/y/z. Selection of TMX over legacy JSON, event behavior and historical gameplay parity are inference; no original edited.
- `view/gameview.cpp`: Missing game view body inferred from earlier donor and exact #150 intact headers/UI sources: views are owned by GameView, constructed from surviving Creature collections, refreshed through declared signals; BackPackObject renders original PNG and emits declared clicked signal. Not exact original content; layout and gameplay parity unverified.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `481db0e4ecc7c1e057d583e01753946ce49b5170430eed15f52817aaadfe911f`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
