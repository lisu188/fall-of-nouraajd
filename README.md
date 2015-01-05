# Recovered game snapshot

Original commit: `71ceeb3834f44a22d5683e0eb2a5623c333dbd0f`. Original tree: `4bbb080d2497e1f9bf2bffa0ac27ce54a4744589`.
Startup was verified from identical recovered sources at `71ceeb3834f44a22d5683e0eb2a5623c333dbd0f`.

This recovered version compiled and linked on Linux, started the real game on an isolated Xvfb display,
loaded its map and a healthy player, rendered the screenshot below, and exited normally.

Startup used an explicit build-only reflection registration compatibility header. The original
registration macro passes a class name to a constructor that accepts no arguments and omits
the Qt metatype declarations needed by its original factory. The forced include restores only
the immediate parent's registration macro. Every original source file and translation unit is
preserved. Exact input/header hashes and donor provenance are attached in the preparation proof.
This establishes startup with that recorded compatibility step; gameplay parity is unverified.

![Actual startup of this recovered game](recovery/startup.png)

## Build and run

Install Qt 5 Core, Gui and Widgets development files and a C++ compiler, with CPython 3.4 development files and its matching Boost.Python library, and Python 3 for the hash-pinned build-source preparation helper. The verified tool versions were:

- g++-5 (Ubuntu 5.4.0-6ubuntu1~16.04.12) 5.4.0 20160609
- QMake version 3.0
- Using Qt version 5.5.1 in /usr/lib/x86_64-linux-gnu

Build from this snapshot's root directory:

```sh
python3 recovery/prepare_reflection_registration.py
qmake game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' 'QMAKE_CXXFLAGS+=-include $$_PRO_FILE_PWD_/recovery_reflection_registration.h' -after TARGET=RecoveryGame DESTDIR=.
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

compatibilityRepair: 2, exactOriginal: 61, reconstruction: 33.

- `CMap.cpp`: Missing #336 implementation reconstructed from prior staged native-era payload with only factory createMapObject→createObject update matching genuine same-commit CObjectHandler.h and Event/LootHandler.cpp; genuine maps/map1/script.py explicitly calls createObject. Native behavior otherwise retained; awaiting native verification. Not an exact original.
- `CPathFinder.cpp`: Reconstructed missing three pathfinders from genuine #331 CPathFinder.h methods, Cell and values storage, CMonster.cpp caller, and CMapObject.cpp relative-move contract. Cardinal passability and reverse cost propagation follow intact later ca0995d7 donor; native random and greedy variants are implemented. Original source hash unavailable; reconstruction, not exact recovery.
- `CPlayerView.cpp`: Missing #339 reconstruction, not exact original. Carries prior inventory implementation with genuine CPlayerView.h CListView/CPlayerInventoryView renames; new CTradeItemsView iterates actual genuine parent CTradePanel::getItems() set, preserving item rendering rather than inventing player-market API. No surviving originals changed; pending native build/startup.
- `GameScript.cpp`: Missing #338 module carried from prior staged candidate plus binding to genuine same-commit CGuiHandler::showPanel(QString), called by original scripts/game/object.py Market class. Pending native verification; no surviving original bytes changed.
- `Stats.h`: Missing Stats header reconstructed from intact Stats.cpp properties and existing donor b58516d9; metatypes declared by genuine same-commit ReflectTypes.cpp REFLECT(Stats/Damage), not twice.
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
- `boost/python/object/inheritance.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/object/inheritance.cpp; headerMatch=0; apiOverlap=0/10000; distance=24
- `boost/python/object/life_support.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/object_operators.cpp`: unverified donor reconstruction; 70d0d690df45877698cb094405e25be00a8139fd:boost/python/object_operators.cpp; headerMatch=0; apiOverlap=0/10000; distance=16
- `boost/python/object_protocol.cpp`: unverified upstream reconstruction; https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9
- `boost/python/str.cpp`: unverified donor reconstruction; 4b3902d44f874a1fae86054d7240a2af76901bb4:boost/python/str.cpp; headerMatch=0; apiOverlap=0/10000; distance=24
- `config/interactions.json`: Missing #337 content carried from prior reconstructed era payload (not exact original). Genuine surviving configurations show formatting-only edits while genuine CTradePanel.h/.cpp and CGuiHandler.cpp add the trade panel; project lists add only those two actual same-commit paths. Native script/factory/handler contracts retained. The map is still a later donor backport with only unsupported future Market object removed, not a recovered original map. Pending native verification.
- `config/monsters.json`: Missing #337 content carried from prior reconstructed era payload (not exact original). Genuine surviving configurations show formatting-only edits while genuine CTradePanel.h/.cpp and CGuiHandler.cpp add the trade panel; project lists add only those two actual same-commit paths. Native script/factory/handler contracts retained. The map is still a later donor backport with only unsupported future Market object removed, not a recovered original map. Pending native verification.
- `config/weapons.json`: Missing #337 content carried from prior reconstructed era payload (not exact original). Genuine surviving configurations show formatting-only edits while genuine CTradePanel.h/.cpp and CGuiHandler.cpp add the trade panel; project lists add only those two actual same-commit paths. Native script/factory/handler contracts retained. The map is still a later donor backport with only unsupported future Market object removed, not a recovered original map. Pending native verification.
- `game.pro`: Missing #339 reconstruction, not exact original. Prior reconstructed project plus only two genuine newly added CMouseHandler source/header paths. No surviving originals changed; pending native build/startup.
- `handler/CObjectHandler.cpp`: Missing #332 content reconstructed from verified #331 candidate; updated against original #332 CEventHandler.h/.cpp event-first-to-object-first transition, CGameEventCaused split, and original CTrigger.h/.cpp contract. Trigger/module registration donor55e6516 retained only where the genuine interface exists. Other bodies preserved from verified #331 reconstruction.
- `maps/map1/map.json`: Missing #338 map uses the intact later donor JSON including its original market1/Market object and all layer/object coordinates. Unlike #331–337, genuine same-commit scripts/game/object.py now declares Market(CBuilding), config/buildings.json selects game.object.Market, and market.png original pointer exists; therefore the earlier-era unsupported-object removal is not carried here. This remains a donor-backed reconstructed map, not recovered original map content. Pending native verification; no surviving original bytes changed.
- `object/CCreature.cpp`: Missing #336 implementation reconstructed from prior staged native-era payload with only factory createMapObject→createObject update matching genuine same-commit CObjectHandler.h and Event/LootHandler.cpp; genuine maps/map1/script.py explicitly calls createObject. Native behavior otherwise retained; awaiting native verification. Not an exact original.
- `object/CCreature.h`: Missing #332 content reconstructed from verified #331 candidate; updated against original #332 CEventHandler.h/.cpp event-first-to-object-first transition, CGameEventCaused split, and original CTrigger.h/.cpp contract. Trigger/module registration donor55e6516 retained only where the genuine interface exists. Other bodies preserved from verified #331 reconstruction.
- `object/CItem.cpp`: Missing #340 CItem body carried from #339 reconstructed real inventory/use/drag/click behavior because same-commit genuine CItem.h and mouse-action contracts are unchanged. This does not repair or conceal the separate surviving CReflection.h constructor/metatype mismatch; native verification must expose that issue. Not exact original; pending native verification.
- `panel/CFightPanel.cpp`: Missing fight panel reconstructed from intact donor painting/combat status bodies and genuine #331 CFightPanel.h plus CPlayerView.h view constructor; later undeclared click handlers removed, public native graphics bridge used, empty child list checked before accessing its first member.
- `scripts/game/interaction.py`: Missing interaction script reconstructed from surviving later action bodies by removing later-only game_object registry decorators. Genuine #331 scripts/game/__init__.py imports game.interaction and genuine PyTypeHandler constructs qualified Python classes directly. Action implementations preserved; Python syntax checked. Not an exact original.
- `boost/python/LICENSE_1_0.txt`: https://github.com/boostorg/python/tree/32ba64a8248d99b1852e77ff4388d9d8a991c4a9 upstream distribution license
- `scripts/PSF_LICENSE`: https://www.python.org/ftp/python/3.3.7/Python-3.3.7.tar.xz upstream Python distribution license

Restored source fingerprint: `3ee9d3fa0db319cce4318172d66fee7f1ee95733ac6a162e2243e0d4e73ce3f2`.

The restored source fingerprint identifies inputs before generation. The
[source preparation metadata](recovery/source-preparation.json) records the original inputs
and every generated or modified file's before/after hashes; the
[preparation log](recovery/source-preparation.log) retains the actual preparation steps.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
