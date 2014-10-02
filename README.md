# Recovered game snapshot

Original commit: `e899bef6df6f290bc79088296a169152ece3f10a`. Original tree: `385e782f57ebb5eab482c5b9947491648d102563`.
Startup was verified from identical recovered sources at `e899bef6df6f290bc79088296a169152ece3f10a`.

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
python3 recovery/prepare_map_packages.py
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

compatibilityRepair: 2, exactOriginal: 58, reconstruction: 33.

- `CCreature.cpp`: content reconstruction of the BFG-removed original; Carry the preceding creature implementation through the formatting revision against the unchanged native interface.
- `CCreature.h`: content reconstruction of the BFG-removed original; Declare stat bonus methods used by the surviving effect callback and follow nonvirtual map ownership.
- `CGamePanel.cpp`: content reconstruction of the BFG-removed original; Carry the working panel refresh implementation against the unchanged declarations.
- `CItem.cpp`: content reconstruction of the BFG-removed original; Carry native life and mana potion behavior without the removed effect field or onMove override.
- `CMap.cpp`: content reconstruction of the BFG-removed original; Dispatch the tile step to the authored creature callback and let the Python holder own its map importer.
- `CObjectHandler.cpp`: content reconstruction of the BFG-removed original; Load the authored map-local configuration along with global resource definitions.
- `CPathFinder.cpp`: content reconstruction of the BFG-removed original; Use typed connections to the completion methods that are no longer Qt slots.
- `CPlayerView.cpp`: content reconstruction of the BFG-removed original; Carry the player view against the revised slot path and QWidget refresh interface.
- `GameScript.cpp`: content reconstruction of the BFG-removed original; Expose the authored scripted tile callback with a heap-backed wrapper and bind the map removal API used by the authored start event.
- `Stats.h`: Content reconstruction matching exact original #260 Stats.cpp e9d15a08d8073b9ec1462a7e542db131edd1314f: const numeric getter declarations, out-of-line setters, QString main/getMainValue. Use intact55e6516e:Stats.h property/declaration layout and zero initialized fields, retain era-correct QObject base and original257 PROPERTY_ACCESSOR semantics. Include QVariant/cmath explicitly for complete genuine APIs and Util::Coords::getDist. Metatype declarations remain owned by exact same-commit ReflectTypes.cpp; no surviving source modified.
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
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=67
- `boost/python/object/life_support.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=59
- `boost/python/object_protocol.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=67
- `config/interactions.json`: Missing interaction configuration reconstructed from donor properties plus actual matching Python class names, genuine #331 config/tiles.json handler/class schema and CTypeHandler.cpp PyTypeHandler qualified-name construction. Restores game.interaction class qualification and PyTypeHandler selection; preserves donor action properties. Not an exact original.
- `config/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=68
- `config/weapons.json`: Inferred missing #263 implementation from native-verified #260–262 reconstructions and actual same-commit original headers/callers; surviving original bytes remain unchanged. Replace demonstrably wrong future donor containing duplicate tile definitions with the nearest native-verified262 weapon configuration, retaining actual weapon ids, bonuses, interactions and original263 declared Qt property schema. Inferred data, not recovered original balancing/layout.
- `images.qrc`: Carry the verified split-project image reconstruction along the surviving resource directory rename.
- `maps/map1/map.json`: content reconstruction of the BFG-removed original; Carry the preceding reconstructed sparse map across the map directory transition. Original placements, including the new StartEvent, are unavailable.
- `scripts/game/interaction.py`: content reconstruction of the BFG-removed original; Carry the preceding interaction definitions across the Python effect transition. The exact removed script is unknown.
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `bf58a1fad70212bfd6dd7230c7e3759e6c5fdef07045d2cbd3c0d96260883fe3`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
