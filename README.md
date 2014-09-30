# Recovered game snapshot

Original commit: `a2567aac4099cd68008bbd8390d6cf8a02b6bc81`. Original tree: `4850b282c8c4c775aa2294c92010bd14b2531024`.
Startup was verified from identical recovered sources at `a2567aac4099cd68008bbd8390d6cf8a02b6bc81`.

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

compatibilityRepair: 6, exactOriginal: 58, reconstruction: 32.

- `CCreature.cpp`: content reconstruction of the BFG-removed original; Use the surviving object accessors and route bonus application and removal through Stats and attribute refresh.
- `CCreature.h`: content reconstruction of the BFG-removed original; Declare stat bonus methods used by the surviving effect callback and follow nonvirtual map ownership.
- `CGamePanel.cpp`: content reconstruction of the BFG-removed original; Carry the working panel refresh implementation against the unchanged declarations.
- `CItem.cpp`: content reconstruction of the BFG-removed original; Use the surviving object and map accessors in the carried item code.
- `CMap.cpp`: content reconstruction of the BFG-removed original; Use the renamed map directory and import its companion event module through the native loader.
- `CObjectHandler.cpp`: content reconstruction of the BFG-removed original; Enumerate configuration via the authored resource handler, deduplicate disk and archive paths, and resolve the script factory against the surviving API.
- `CPathFinder.cpp`: content reconstruction of the BFG-removed original; Use typed connections to the completion methods that are no longer Qt slots.
- `CPlayerView.cpp`: content reconstruction of the BFG-removed original; Carry the player view against the revised slot path and QWidget refresh interface.
- `GameScript.cpp`: content reconstruction of the BFG-removed original; Expose the global and map-specific native resource loaders through Python 3.4.
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
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=69
- `boost/python/object/life_support.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=61
- `boost/python/object_protocol.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=69
- `config/interactions.json`: Missing interaction configuration reconstructed from donor properties plus actual matching Python class names, genuine #331 config/tiles.json handler/class schema and CTypeHandler.cpp PyTypeHandler qualified-name construction. Restores game.interaction class qualification and PyTypeHandler selection; preserves donor action properties. Not an exact original.
- `config/monsters.json`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:config/monsters.json; headerMatch=0; apiOverlap=0/10000; distance=70
- `config/weapons.json`: Inferred missing #263 implementation from native-verified #260–262 reconstructions and actual same-commit original headers/callers; surviving original bytes remain unchanged. Replace demonstrably wrong future donor containing duplicate tile definitions with the nearest native-verified262 weapon configuration, retaining actual weapon ids, bonuses, interactions and original263 declared Qt property schema. Inferred data, not recovered original balancing/layout.
- `images.qrc`: Carry the verified split-project image reconstruction along the surviving resource directory rename.
- `scripts/game/interaction.py`: content reconstruction of the BFG-removed original; Carry the preceding interaction definitions across the Python effect transition. The exact removed script is unknown.
- `CScriptLoader.cpp`: Adapt the surviving #296 loader to #295 event.py and Python-managed loader ownership.
- `CScriptLoader.h`: Use the earliest surviving loader declarations from #296 to satisfy the #295 project references.
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `maps/map1/event.py`: Carry the preceding authored event class into the renamed event module and explicitly import game.
- `maps/map1/map.json`: Carry the preceding reconstructed sparse map through the renamed map directory. Exact original coordinates remain unknown.
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `2cacddacede767fdf77c02cf02fabe40fab814970796dcb46e1a5dc41b9ad47e`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
