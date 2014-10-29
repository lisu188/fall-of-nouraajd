# Recovered game snapshot

Original commit: `d732bf46e0b8a059330fdcbf4619ee7caf1c8381`. Original tree: `b3a8b6c9d560b800f34b7c0b4961e10344a42e8e`.
Startup was verified from identical recovered sources at `d732bf46e0b8a059330fdcbf4619ee7caf1c8381`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, with CPython 3.4 development files and its matching Boost.Python library. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_historical_handlers.py
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

compatibilityRepair: 4, exactOriginal: 59, reconstruction: 37.

- `CCreature.h`: content reconstruction of the BFG-removed original; Follow the surviving onTurn event callback.
- `CGamePanel.cpp`: content reconstruction of the BFG-removed original; Retain common panel behavior and the combat panel across the file split.
- `CGamePanel.h`: content reconstruction of the BFG-removed original; Keep named panel declarations and defer character panel children until a player exists.
- `CItem.cpp`: content reconstruction of the BFG-removed original; Resolve the creature from the equip and unequip event cause.
- `CMap.cpp`: content reconstruction of the BFG-removed original; Dispatch turn events and attach tiles through their surviving scene and graphics interfaces.
- `CMapObject.h`: content reconstruction of the BFG-removed original; Fit the named event, game-object and moveable interfaces to surviving bodies.
- `CPathFinder.cpp`: content reconstruction of the BFG-removed original; Fit the preceding pathfinders to the surviving synchronous movement interface.
- `CPlayerView.cpp`: content reconstruction of the BFG-removed original; Route item drops through the historical item-use dispatcher.
- `GameScript.cpp`: content reconstruction of the BFG-removed original; Connect surviving Python scripts to native item, turn, and tile events.
- `Stats.h`: content reconstruction of the BFG-removed original; Carry the verified historical Stats declarations through the refactor.
- `android/posix.c`: unverified upstream reconstruction; https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz; renamed posixmodule header to existing android/posix.h; Android compatibility unverified; Linux excludes this source
- `boost/python/converter/builtin_converters.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/from_python.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/registry.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/converter/type_id.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/dict.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/exec.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/list.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/numeric.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/class.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object/enum.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object/function.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object/function_doc_signature.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=36
- `boost/python/object/life_support.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=28
- `boost/python/object_protocol.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=36
- `config/interactions.json`: Missing interaction configuration reconstructed from donor properties plus actual matching Python class names, genuine #331 config/tiles.json handler/class schema and CTypeHandler.cpp PyTypeHandler qualified-name construction. Restores game.interaction class qualification and PyTypeHandler selection; preserves donor action properties. Not an exact original.
- `config/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=37
- `config/weapons.json`: Missing weapon config reconstructed from intact 55e6516eb91b739e899df1ef8d72116da44fec49:config/weapons.json Git blob0a32d5f0cc003ae07cfd43d092921d76ec82f3e5; its genuine ChaosSword/other authored item IDs and flat Stats bonus shape match #331 CItem.h, native loader/property contracts and original weapon image path identities (ChaosSword also occurs in the existing reconstructed map), and CObjectHandler deserialization. Original CTypeHandler field restored consistently with genuine config/tiles.json. Replaces unrelated tile-config donor; not an exact original.
- `handlers/CObjectHandler.cpp`: content reconstruction of the BFG-removed original; Create the common game-object type and configure its historical properties.
- `images.qrc`: Carry the verified split-project image reconstruction along the surviving resource directory rename.
- `mapObjects/CCreature.cpp`: content reconstruction of the BFG-removed original; Route equipment and tile-step events through the surviving dispatcher.
- `mapObjects/CMapObject.cpp`: content reconstruction of the BFG-removed original; Place object type and map access on the common game-object base.
- `maps/map1/map.json`: Carry #306’s sparse map reconstruction through the formatting and visitor revisions. Preserve the separate Tiled donor used by later revisions.
- `scripts/game/interaction.py`: Missing interaction script reconstructed from surviving later action bodies by removing later-only game_object registry decorators. Genuine #331 scripts/game/__init__.py imports game.interaction and genuine PyTypeHandler constructs qualified Python classes directly. Action implementations preserved; Python syntax checked. Not an exact original.
- `android/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `handlers/CEventHandler.cpp`: Carry the preceding dispatcher to the path named by the surviving qmake project.
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `745ef32221c729e6bb0e6c4a870b0ebb1c7295607ab955e9ac3f79e0e95c913e`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
