# Recovered game snapshot

Original commit: `80920f276d6aff53a2aa0dd237f4a26cb47cb60d`. Original tree: `f258b5917713c6e1eeebb2d39e5595d166d2d819`.
Startup was verified from identical recovered sources at `80920f276d6aff53a2aa0dd237f4a26cb47cb60d`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

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
python3 recovery/prepare_build_sources.py
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

compatibilityRepair: 1, exactOriginal: 62, reconstruction: 20.

- `compression/minizip.h`: unverified upstream reconstruction; https://github.com/richgel999/miniz/tree/v114
- `config/creatures.json`: {'evidence': ['historical image directory IDs', 'config/map.json saved creature state when present'], 'inferred': ['missing initial stats', 'levelStats encoding and progression'], 'kind': 'reconstructed-config', 'note': 'Saved state is retained; absent stats are positive synthetic defaults. Build/startup unverified.', 'sourceCommit': '80920f276d6aff53a2aa0dd237f4a26cb47cb60d', 'verified': False}
- `config/items.json`: content reconstruction of the BFG-removed original; Adapted genuine119 config/items.json donor blob41d081fe6c796beab79afb418358b8af12cfa877 to missing original2081: adds only class Weapon/Armor/Potion from each actual legacy type, as required by surviving150 Item::getItem/QMetaType factory. Preserves every donor item name/path/stat/power/type. All lost original later item IDs, exact balance and slot metadata remain unavailable and are not invented. This is inferred missing-config compatibility, not original2081 bytes or gameplay parity. Root owns integration and affected-proof revalidation.
- `creatures/creature.cpp`: Content reconstruction of the BFG-removed original; Missing #150 Creature body inferred from native-verified #97 body and exact surviving #150 declarations/callers/config: ListItem base, ordered sets, slot-index equipment map, collection signals, lower-case coordinates. Slot initialization follows original config/slots.json and ItemSlot::update at(). Saves subtract equipped bonuses before reload. Formula, equipment serialization and historical gameplay parity remain inferred; no surviving source edited. Corrected inferred equipment reload: legacy inventory.weapon/armor apply only if present; modern equipment slots survive save/load. Before/after native regression and revalidation required.
- `creatures/player.cpp`: Missing #150 player body inferred from earlier surviving donor and exact original Player.h/GameView caller: restored declared update() to refresh inventory/action maps and emit statsChanged. Remaining donor combat preserved; historical behavior not proven.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=8
- `images/buildings/teleporter/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/teleporter/0.png; headerMatch=0; apiOverlap=0/10000; distance=8
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: Missing #150 Interaction body inferred from native-verified #97 implementation and exact #150 surviving header: public/default/copy constructors, ListItem ordering and Effect state serialization added. Removed undeclared legacy setAnimation override, retaining inherited real resource loading. Historical ordering/effect persistence parity unverified.
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Content reconstruction of the BFG-removed original; Missing map body inferred from earlier recovered donor; adapted to exact #150 intact Map/MapObject declarations: no later TMX/entry-coordinate API, original JSON map/state and declared ownership preserved. Not exact original content; gameplay parity unverified. Missing ensureSize background generation is inferred as GrassTile (declared in original tiles.json) when the original default string is empty; preserves every explicitly authored road/mountain and player coordinate. Before this missing-body repair native observer reported real healthy player but no terrain at authored spawn (0,0,0). Historical terrain parity is unverified. Corrected missing-body ownership: removeObject detaches without deleting, as genuine Item::onEnter transfers the live item to player inventory; original AnimatedObject/Destroyer retains lifetime registration. Actual QObject destroyed-signal before/after regression required.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: Missing scene body inferred from earlier recovered donor and exact #150 intact declarations; restored declared map accessor/StepTimer mouse movement and kept player/game initialization and arrow movement. Removed undeclared later tile-size setter. Original behavior not proven; startup evidence and gameplay parity reported separately.
- `view/gameview.cpp`: Missing game view body inferred from earlier donor and exact #150 intact headers/UI sources: views are owned by GameView, constructed from surviving Creature collections, refreshed through declared signals; BackPackObject renders original PNG and emits declared clicked signal. Not exact original content; layout and gameplay parity unverified.
- `view/mapview.cpp`: content reconstruction of the BFG-removed original; carried forward unchanged from the reconstruction of 7476f6bac498deb69ac2f9eb80963e8cab3c5705 (previous version of view/mapview.cpp)
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `143cbe83924dd33a00ed9062aa8f3ef1e089444a26967ca675d927270e3fee37`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
