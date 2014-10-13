# Recovered game snapshot

Original commit: `471be57fbbd86d75c56133e610a1f28bb68446bb`. Original tree: `4f1b7cea4d6d9f2d318ac3633ec6c9e3e1ce259d`.
Startup was verified from identical recovered sources at `471be57fbbd86d75c56133e610a1f28bb68446bb`.

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
python3 recovery/prepare_creature_events.py
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

compatibilityRepair: 3, exactOriginal: 59, reconstruction: 34.

- `CCreature.cpp`: content reconstruction of the BFG-removed original; Carry the compatible #304 implementation across the #305 formatting and platform changes.
- `CCreature.h`: content reconstruction of the BFG-removed original; Carry the compatible #304 implementation across the #305 formatting and platform changes.
- `CGamePanel.cpp`: content reconstruction of the BFG-removed original; Carry the compatible #304 implementation across the #305 formatting and platform changes.
- `CGamePanel.h`: content reconstruction of the BFG-removed original; Carry the compatible #304 implementation across the #305 formatting and platform changes.
- `CMap.cpp`: content reconstruction of the BFG-removed original; Carry the compatible #304 implementation across the #305 formatting and platform changes.
- `CObjectHandler.cpp`: content reconstruction of the BFG-removed original; Load the authored map-local configuration along with global resource definitions.
- `CPathFinder.cpp`: content reconstruction of the BFG-removed original; Carry the pathfinder and emit three-dimensional movement where required by the surviving completion signal.
- `CPlayerView.cpp`: content reconstruction of the BFG-removed original; Carry the player views against the unchanged slot accessor and view interface.
- `GameScript.cpp`: content reconstruction of the BFG-removed original; Carry the compatible #304 implementation across the #305 formatting and platform changes.
- `Stats.h`: Content reconstruction matching exact original #260 Stats.cpp e9d15a08d8073b9ec1462a7e542db131edd1314f: const numeric getter declarations, out-of-line setters, QString main/getMainValue. Use intact55e6516e:Stats.h property/declaration layout and zero initialized fields, retain era-correct QObject base and original257 PROPERTY_ACCESSOR semantics. Include QVariant/cmath explicitly for complete genuine APIs and Util::Coords::getDist. Metatype declarations remain owned by exact same-commit ReflectTypes.cpp; no surviving source modified.
- `android/posix.c`: unverified upstream reconstruction; https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz; renamed posixmodule header to existing android/posix.h; Android compatibility unverified; Linux excludes this source
- `boost/python/converter/builtin_converters.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/from_python.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/registry.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/type_id.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/dict.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/exec.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/list.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/numeric.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/class.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/enum.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/function.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/function_doc_signature.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=59
- `boost/python/object/life_support.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=51
- `boost/python/object_protocol.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=59
- `config/interactions.json`: Missing interaction configuration reconstructed from donor properties plus actual matching Python class names, genuine #331 config/tiles.json handler/class schema and CTypeHandler.cpp PyTypeHandler qualified-name construction. Restores game.interaction class qualification and PyTypeHandler selection; preserves donor action properties. Not an exact original.
- `config/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=60
- `config/weapons.json`: Missing weapon config reconstructed from intact 55e6516eb91b739e899df1ef8d72116da44fec49:config/weapons.json Git blob0a32d5f0cc003ae07cfd43d092921d76ec82f3e5; its genuine ChaosSword/other authored item IDs and flat Stats bonus shape match #331 CItem.h, native loader/property contracts and original weapon image path identities (ChaosSword also occurs in the existing reconstructed map), and CObjectHandler deserialization. Original CTypeHandler field restored consistently with genuine config/tiles.json. Replaces unrelated tile-config donor; not an exact original.
- `images.qrc`: Carry the verified split-project image reconstruction along the surviving resource directory rename.
- `maps/map1/map.json`: content reconstruction of the BFG-removed original; Carry the preceding reconstructed sparse map across the map directory transition. Original placements, including the new StartEvent, are unavailable.
- `scripts/game/interaction.py`: Missing interaction script reconstructed from surviving later action bodies by removing later-only game_object registry decorators. Genuine #331 scripts/game/__init__.py imports game.interaction and genuine PyTypeHandler constructs qualified Python classes directly. Action implementations preserved; Python syntax checked. Not an exact original.
- `android/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `3e8320a4049901444a818b3e0d2470078aa4b2905ceefc1cb73f4b7b0c1e71bc`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
