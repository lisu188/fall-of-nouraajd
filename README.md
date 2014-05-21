# Recovered game snapshot

Original commit: `7022f82ba68e4b740e85915b1710dd0502837efe`. Original tree: `3a3959894ad4327a3cf53ae6a7cf3fbc23427748`.
Startup was verified from identical recovered sources at `7022f82ba68e4b740e85915b1710dd0502837efe`.

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

The isolated build copy resolves exact-pinned original merge conflicts only where the two
alternatives differ in whitespace. Five compiled files retain the reviewed HEAD alternative;
the derived teleporter unit also resolves its whitespace-only conflict. Original Git inputs
remain unchanged. Exact before/after hashes and portable replay helpers document this build
compatibility separately from teleporter serialization semantics; gameplay parity is unverified.

The reconstructed qmake project also requires pathfinder/pathfindercache.cpp. The original
revision omitted that file. The isolated build uses the exact file added by immediate child
779fb803, the sole change in that child. The attached helper verifies the donor and its inputs.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, and Python 3 for the hash-pinned build-source preparation helper. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_teleporter_serialization.py
python3 recovery/prepare_trivial_conflicts.py
python3 recovery/prepare_pathfinder_cache.py
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

compatibilityRepair: 1, exactOriginal: 60, reconstruction: 49.

- `Game.pro`: content reconstruction of the BFG-removed original; qmake project regenerated with 85 sources inferred without a surviving object_script listing: intact 5258bb04:Game.pro SOURCES reconciled with this tree's files; settings from intact 5258bb04:Game.pro
- `config/creatures.json`: {'evidence': ['historical image directory IDs', 'config/map.json saved creature state when present'], 'inferred': ['missing initial stats', 'levelStats encoding and progression'], 'kind': 'reconstructed-config', 'note': 'Saved state is retained; absent stats are positive synthetic defaults. Build/startup unverified.', 'sourceCommit': '7022f82ba68e4b740e85915b1710dd0502837efe', 'verified': False}
- `config/items.json`: content reconstruction of the BFG-removed original; Adapted genuine119 config/items.json donor blob41d081fe6c796beab79afb418358b8af12cfa877 to missing original2081: adds only class Weapon/Armor/Potion from each actual legacy type, as required by surviving150 Item::getItem/QMetaType factory. Preserves every donor item name/path/stat/power/type. All lost original later item IDs, exact balance and slot metadata remain unavailable and are not invented. This is inferred missing-config compatibility, not original2081 bytes or gameplay parity. Root owns integration and affected-proof revalidation.
- `config/map.tmx`: unverified donor reconstruction; authored Tiled geometry/object coordinates from 55e6516e:maps/map1/map.json converted to XML; missing target script reference omitted
- `creatures/creature.cpp`: Content reconstruction of the BFG-removed original; Missing #175 body candidate inferred from earlier native API-checked donor 08ec144f196a9a5195e281997b5695828ccbd2ab; surviving headers have formatting-only changes or inline isAsync addition. Native acceptance pending; teleporter authored save defect remains separate. Missing #150 Creature body inferred from native-verified #97 body and exact surviving #150 declarations/callers/config: ListItem base, ordered sets, slot-index equipment map, collection signals, lower-case coordinates. Slot initialization follows original config/slots.json and ItemSlot::update at(). Saves subtract equipped bonuses before reload. Formula, equipment serialization and historical gameplay parity remain inferred; no surviving source edited. Corrected inferred equipment reload: legacy inventory.weapon/armor apply only if present; modern equipment slots survive save/load. Before/after native regression and revalidation required.
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `interactions/interaction.cpp`: Content reconstruction of the BFG-removed original; Missing #175 body candidate inferred from earlier native API-checked donor 0b0a9c19112914c23dcd4a6e2e032f335f7abf76; surviving headers have formatting-only changes or inline isAsync addition. Native acceptance pending; teleporter authored save defect remains separate. Missing #150 Interaction body inferred from native-verified #97 implementation and exact #150 surviving header: public/default/copy constructors, ListItem ordering and Effect state serialization added. Removed undeclared legacy setAnimation override, retaining inherited real resource loading. Historical ordering/effect persistence parity unverified.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/reader.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/value.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/writer.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Content reconstruction of the BFG-removed original; Missing #175 Map body inferred from native-verified #166; genuine header tokens identical apart from formatting. Missing #166 Map body inferred from native-verified #164/#165. Genuine getObjects changes from inline to external: return actual mapObjects. Added optional movement-completion callback dispatched after real animation or immediate non-silent move; base callback policy defaults to no action because no surviving #166 caller defines base effects. Genuine derived callbacks are dispatched virtually. Default policy, removed implementation changes and gameplay parity remain inferred. Missing #164 Map body inferred from accepted #163; only genuine header change adds virtual loadFromProps, now invoked with actual TMX object properties before positioning/adding each genuine object. Unknown original body behavior remains inferred. Missing body inferred by carrying accepted #161 reconstruction e197feb3953c9c65e51587a60fc2fe66155a063e; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing body inferred by carrying accepted #159 reconstruction f59850bc2948c48c34f05161ff83bf840234b80b; exact surviving same-path header bytes are unchanged. Unknown removed implementation changes and historical gameplay parity are unverified. Missing #159 Map/MapObject body inferred from accepted #150 body and genuine same-version APIs/config. Added real TMX layer/tileset/property loading and authored entry coordinates from genuine map.tmx, with available genuine object classes/configured items/creatures. Authored TMX names without a class in this revision (StartEvent, Market) are explicitly logged, not replaced by stand-ins. Object property behavior and removed body gameplay semantics remain unverified; no original edited. Corrected missing-body ownership: removeObject detaches without deleting, as genuine Item::onEnter transfers the live item to player inventory; original AnimatedObject/Destroyer retains lifetime registration. Actual QObject destroyed-signal before/after regression required.
- `pathfinder/smartpathfinder.cpp`: unverified donor reconstruction; fb2bcb07e3b2267e7f24c5a7cd48604180b1be0f:pathfinder/smartpathfinder.cpp; headerMatch=0; apiOverlap=10000/10000; distance=1
- `stats/stats.cpp`: Content reconstruction of the BFG-removed original; Missing #175 Stats body inferred from native-verified #150/#163 Stats body4ff9f45b2f23d26fc69280d6c0df542e02efa223; surviving #150/#175 header tokens are identical apart from formatting, including value-argument bonuses. Unknown removed-body changes and historical parity unverified.
- `tinyxml/tinystr.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `tinyxml/tinyxml.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `tinyxml/tinyxml.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `tinyxml/tinyxmlparser.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `tmx/TmxLayer.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `tmx/TmxLayer.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `tmx/TmxMap.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `tmx/TmxMap.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `tmx/TmxMapTile.h`: unverified donor reconstruction; fb2bcb07e3b2267e7f24c5a7cd48604180b1be0f:tmx/TmxMapTile.h; headerMatch=0; apiOverlap=0/10000; distance=1
- `tmx/TmxTileset.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `view/gamescene.cpp`: content reconstruction of the BFG-removed original; carried forward unchanged from the reconstruction of 4ac65b4fa8932bcd62d9ea368cb9db5557508def (previous version of view/gamescene.cpp)
- `view/gameview.cpp`: content reconstruction of the BFG-removed original; carried forward unchanged from the reconstruction of 9b0dfbaa8fa749b21bf55bb5b19242f32fdd1d2f (previous version of view/gameview.cpp)
- `zlib/adler32.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 adler32.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 65ad6a5adc44c00428b35eb15ff26d16f9ef209b, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/crc32.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 crc32.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 91be372d224da6833c03bd24d7158ff622ece35f, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/crc32.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 crc32.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 8053b6117c023f64554ea783b23fa06985acff7b, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/deflate.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 deflate.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 5c4022f3d4774b98bb22104890b04a7d3f7f4aec, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/deflate.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 deflate.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob cbf0d1ea5d966e572c4d3ae24d334c1ff1789169, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/gzguts.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 gzguts.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 0f8fb79f87d4f65e7f5667129c763e3a361199f2, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/gzlib.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 gzlib.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 603e60ed5444e0e7a2ed9590a9d9a73ce7cc97bf, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/gzread.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 gzread.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 548201ab0099b51556da32c4873d1dbb2d211b5a, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/gzwrite.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 gzwrite.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob e8defc6887a186055f17597968c4fc5791332811, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/infback.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 infback.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob af3a8c965d50cc6ac05c6c844a8f79e2cdc9f3c1, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/inffast.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 inffast.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 2f1d60b43b8a9deacf22bb5526a979dcc219a68f, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/inffixed.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 inffixed.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 75ed4b5978de4be3c44ad48a060b75500f17a0a2, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/inflate.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 inflate.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob a8431abeacffd97e5028a9e54135a5f173528960, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/inflate.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 inflate.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 95f4986d400223bad542e5b34a7e6284a039425e, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/inftrees.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 inftrees.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 11e9c52accbe8e2cf4e502f88ce89ccfa4f992e5, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/trees.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 trees.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 56e9bb1c115e81082f58a89b003b766760e12a12, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/trees.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 trees.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob d35639d82a27807e49ea35c334f8bbcf64720f82, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/zlib.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 zlib.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob bfbba83e8ee0902abe8bcbfab8bdebbbc07dca69, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/zutil.c`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 zutil.c, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 898ed345b0e3ef23ce5aaba1eb6307b5b113d6b1, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `zlib/zutil.h`: Content reconstruction of the BFG-removed original; Unmodified official zlib1.2.5 zutil.h, upstream https://github.com/madler/zlib/tree/v1.2.5, Git blob 258fa88799ad1d97e44fe1ac9df77948e82ea5c0, coherent with exact surviving zconf.h1.2.5. Missing historical vendor bytes remain unavailable; upstream donor is inferred rather than exact original.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `1a0fd13c03202220fdd0f7b8d19bbfae6fd454995f016e399e14de0bfd2b592f`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
