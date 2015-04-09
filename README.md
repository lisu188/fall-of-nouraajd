# Recovered game snapshot

Original commit: `4c0be0149008787ff79b4479307f1945b28c9507`. Original tree: `ad96fe398c11d2e0fb656210dab39bddd50e4f3c`.
Startup was verified from identical recovered sources at `4c0be0149008787ff79b4479307f1945b28c9507`.

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
python3 recovery/prepare_trigger_decorator.py
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

compatibilityRepair: 2, exactOriginal: 65, reconstruction: 27.

- `CMap.cpp`: Missing #351 reconstruction, not exact original. Actual #351 CMap.h moves player ownership from scene to map; getPlayer/setPlayer bodies are unchanged intact55e6516 donor methods matching the genuine CGameScene::startGame call. Other verified loader/map bodies preserved. Pending native verification; surviving original bytes retained.
- `GameScript.cpp`: unverified donor reconstruction; 55e6516eb91b739e899df1ef8d72116da44fec49:GameScript.cpp; headerMatch=0; apiOverlap=0/10000; distance=14
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
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=13
- `boost/python/object/life_support.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=5
- `boost/python/object_protocol.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=13
- `config/interactions.json`: Missing #337 content carried from prior reconstructed era payload (not exact original). Genuine surviving configurations show formatting-only edits while genuine CTradePanel.h/.cpp and CGuiHandler.cpp add the trade panel; project lists add only those two actual same-commit paths. Native script/factory/handler contracts retained. The map is still a later donor backport with only unsupported future Market object removed, not a recovered original map. Pending native verification.
- `config/monsters.json`: Missing #337 content carried from prior reconstructed era payload (not exact original). Genuine surviving configurations show formatting-only edits while genuine CTradePanel.h/.cpp and CGuiHandler.cpp add the trade panel; project lists add only those two actual same-commit paths. Native script/factory/handler contracts retained. The map is still a later donor backport with only unsupported future Market object removed, not a recovered original map. Pending native verification.
- `config/weapons.json`: Missing #337 content carried from prior reconstructed era payload (not exact original). Genuine surviving configurations show formatting-only edits while genuine CTradePanel.h/.cpp and CGuiHandler.cpp add the trade panel; project lists add only those two actual same-commit paths. Native script/factory/handler contracts retained. The map is still a later donor backport with only unsupported future Market object removed, not a recovered original map. Pending native verification.
- `game.pro`: content reconstruction of the BFG-removed original; reconstruct from the surviving translation units and retain the Python 3.4/Boost link ABI from the nearest historical project
- `handler/CObjectHandler.cpp`: Missing #341 reconstruction, not exact original. Preserves prior real config/property loading and CTypeHandler/PyTypeHandler instances; genuine CTypeHandler.cpp now owns its explicit native constructor registry instead of old Qt reflection. Pending native verification; original bytes preserved.
- `object/CCreature.cpp`: Missing #351 reconstruction, not exact original. Prior actual creature combat/inventory bodies already obtain player through map, consistent with genuine removal of CGameScene::getPlayer; missing exact implementation unknown. Pending native verification; surviving original bytes retained.
- `object/CCreature.h`: Missing #348 reconstruction, not exact original. Preserves prior creature implementation/header donor and actual existing callbacks; same-commit genuine Monster changes only smart-finder selection. Exact missing changes unknown; native compilation/startup provides bounded validation. Pending native verification; no gameplay/path parity claim.
- `scripts/game/interaction.py`: Missing interaction script reconstructed from surviving later action bodies by removing later-only game_object registry decorators. Genuine #331 scripts/game/__init__.py imports game.interaction and genuine PyTypeHandler constructs qualified Python classes directly. Action implementations preserved; Python syntax checked. Not an exact original.
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `f59ca60fbc687f600d6d6353dfc4b51ffc0f10dfc2c4d716aace7070e3d4f5a0`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
