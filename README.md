# Recovered game snapshot

Original commit: `800026c23e9d51578496bbbc95b8e052dba1d6f8`. Original tree: `4398768e69eaad569c05f83b0b591ad65d5e9604`.
Startup was verified from identical recovered sources at `800026c23e9d51578496bbbc95b8e052dba1d6f8`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
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

compatibilityRepair: 1, exactOriginal: 44, reconstruction: 19.

- `Game.pro`: Missing qmake project regenerated from genuine same-tree object_script.Game.Debug (40 source objects, no unmatched objects), with nearest intact #116 84017c91 Game.pro settings and same-tree headers/resources. No CharView force-include compatibility is needed because the genuine GameView header now declares it.
- `compression/minizip.h`: unverified upstream reconstruction; https://github.com/richgel999/miniz/tree/v114
- `config/creatures.json`: content reconstruction of the BFG-removed original; carried nearest reconstructed config/creatures.json through API-stable #62; surviving files provide no recoverable internal implementation/data delta
- `config/map.json`: unverified donor reconstruction; bf32a4c93e396bd645769a9957eacd6a75106b62:config/map.json; headerMatch=0; apiOverlap=0/10000; distance=11
- `creatures/creature.cpp`: Adapted validated #117 Creature to genuine #118 Q_OBJECT/statsChanged signal and surviving PlayerStatsView::setPlayer connection. Actual HP/mana/derived-pool mutations emit the real moc-generated signal so the original stats widget refreshes. Set containers/combat/stat formulas/save schema retain prior provenance; exact original signal timing and internal delta remain unverified.
- `creatures/player.cpp`: Adapted validated #117 Player to genuine #118 removal of its stats widget/backpack and original QWidget PlayerStatsView::setPlayer signal contract. Player keeps its actual inventory/skill/equipment list views and base-pointer sets. Inventory/equipment parent to the actual CharView, following the surviving #117 GameView::showCharView local positions; exact original parenting/layout remains inferred. Real Player mutations emit inherited statsChanged; no stats/widget stand-ins. Prior save/combat inference remains explicit.
- `images/buildings/dungeon/0.png`: unverified donor reconstruction; 71a3432e36b5649aabdd63c7807a78e9a8a3749a:images/buildings/dungeon/0.png; headerMatch=0; apiOverlap=0/10000; distance=43
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `images/tiles/mountain/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/mountain/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `images/tiles/road/0.png`: unverified donor reconstruction; 152007b28631784d3c5e17f2686eb6ef9ff30e46:images/tiles/road/0.png; headerMatch=0; apiOverlap=0/10000; distance=155 Verified by build and startup of afdd8069 (recovery/evidence/second-original).
- `interactions/interaction.cpp`: carried forward unchanged from the reconstruction of d8eebeb95fdc4734ed2094dc13c298671c8b0529 (previous version of interactions/interaction.cpp)
- `json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6
- `map/map.cpp`: Carried validated #115 Map reconstruction unchanged; same surviving Map API at #116. Prior explicitly inferred cache radius and unknown original implementation deltas retained.
- `stats/stats.cpp`: content reconstruction of the BFG-removed original; carried validated d30a3f79 stats reconstruction; #63 surviving Stats change only renames a loadFromJson parameter
- `view/gamescene.cpp`: Carried validated #115–117 Scene reconstruction unchanged; surviving #118 Scene API is identical. Prior actual movement/map/save behavior retained; unknown original internal delta remains unverified.
- `view/gameview.cpp`: Adapted genuine surviving immediately preceding #117 eacc2b048f24ef3ac1622e2ddfb6767e75ce0649:view/gameview.cpp to original #118 QWidget BackPackObject clicked signal/paint event and GameView-owned PlayerStatsView. Uses the actual backpack image, connects clicked to the authored showCharView slot, and binds the original stats widget to the actual player after real Scene startup. Child QWidget ownership preserves value-member lifetimes. Top-center backpack placement and exact original widget layout/signal timing are inferred; original main/config/headers/widgets/resources unchanged. Startup does not prove ordinary click behavior or gameplay parity.
- `json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `e507c46e3a729f3cf6d8b64f3617eef275caf35193c20688c94d85695062927c`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
