# Recovered game snapshot

Original commit: `ddb05027fb3e831cbef7f16f1dea58f519c1756c`. Original tree: `ae2e73fdd7400feff1b9c9c90c5b8205c5356378`.
Startup was verified from identical recovered sources at `ddb05027fb3e831cbef7f16f1dea58f519c1756c`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

Startup used a separate build-only maps resource manifest. The original manifest still references
a trigger configuration that the original commit deleted. The attached helper removes only that
entry, reproducing the later authored correction exactly, and selects the derived manifest only
after the project is read. The original manifest, source files and translation units remain unchanged.
Exact input/output hashes, the required absence state and the compatibility boundary are attached.
This establishes startup with that recorded compatibility step; gameplay parity is unverified.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, with CPython 3.4 development files and its matching Boost.Python library, and Python 3 for the hash-pinned build-source preparation helper. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_maps_manifest.py
python3 recovery/prepare_historical_handlers.py
qmake game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' -after RESOURCES-=maps.qrc 'RESOURCES+=$$_PRO_FILE_PWD_/recovery_maps.qrc' -after TARGET=RecoveryGame DESTDIR=.
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

compatibilityRepair: 2, exactOriginal: 68, reconstruction: 24.

- `CMap.cpp`: Missing #351 reconstruction, not exact original. Actual #351 CMap.h moves player ownership from scene to map; getPlayer/setPlayer bodies are unchanged intact55e6516 donor methods matching the genuine CGameScene::startGame call. Other verified loader/map bodies preserved. Pending native verification; surviving original bytes retained.
- `GameScript.cpp`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:GameScript.cpp; headerMatch=0; apiOverlap=0/10000; distance=10
- `boost/python/converter/builtin_converters.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/from_python.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/registry.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/converter/type_id.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/dict.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/exec.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/list.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/numeric.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/class.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object/enum.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object/function.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object/function_doc_signature.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=9
- `boost/python/object/life_support.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=1
- `boost/python/object_protocol.cpp`: content reconstruction of the BFG-removed original; Carry the working bundled Boost.Python translation unit through the formatting or platform transition.
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=9
- `game.pro`: content reconstruction of the BFG-removed original; reconstruct from the surviving translation units and retain the Python 3.4/Boost link ABI from the nearest historical project
- `handler/CObjectHandler.cpp`: Missing #341 reconstruction, not exact original. Preserves prior real config/property loading and CTypeHandler/PyTypeHandler instances; genuine CTypeHandler.cpp now owns its explicit native constructor registry instead of old Qt reflection. Pending native verification; original bytes preserved.
- `object/CCreature.cpp`: Missing #351 reconstruction, not exact original. Prior actual creature combat/inventory bodies already obtain player through map, consistent with genuine removal of CGameScene::getPlayer; missing exact implementation unknown. Pending native verification; surviving original bytes retained.
- `object/CCreature.h`: Missing #348 reconstruction, not exact original. Preserves prior creature implementation/header donor and actual existing callbacks; same-commit genuine Monster changes only smart-finder selection. Exact missing changes unknown; native compilation/startup provides bounded validation. Pending native verification; no gameplay/path parity claim.
- `scripts/game/interaction.py`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:scripts/game/interaction.py; headerMatch=0; apiOverlap=0/10000; distance=9
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `7bb9f1c0261ea8f0521983e87c8b76ae783f340297f9d96c449680716b278285`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
