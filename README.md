# Recovered game snapshot

Original commit: `50cecd11c3bcf6e1fa6f9450626a1795c0e41fdb`. Original tree: `c6b7e935bed34fa316636826d7e283521aa5b1df`.
Startup was verified from identical recovered sources at `50cecd11c3bcf6e1fa6f9450626a1795c0e41fdb`.

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
qmake Game.pro QMAKE_CC=gcc-5 QMAKE_CXX=g++-5 QMAKE_LINK=g++-5 'QMAKE_CXXFLAGS+=-include functional' -after TARGET=RecoveryGame DESTDIR=.
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

compatibilityRepair: 1, exactOriginal: 65, reconstruction: 44.

- `Game.pro`: Missing #196 body carried from native-verified #195 reconstruction e53cc0bde800c6d39a4e0b71b24fbb603481ebeb with byte-identical corresponding original header (or identical complete project TU/header/resource path inventory). Missing original body delta remains unknown; actual native startup checked separately. Missing #195 project reconstructed from all52 actual C++ and15 C translation units, all same-commit headers and6 surviving resource manifests under src/lib/res. Preserves every original game/library TU; declares supported CPython3.4 ABI for genuine Python3 C API, not claimed exact historical original flags. Replaces stale unverified pre-layout donor; pending native proof. JSON headers retain qualified lib/json or local includes; adding lib/json globally would shadow glibc features.h and is intentionally avoided. Defines QT_NO_KEYWORDS consistently with surviving Q_SLOT/Q_SIGNAL/Q_EMIT usage, preventing Qt slots macro from altering original Python3 PyType_Slot field.
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=21
- `lib/json/json_batchallocator.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/json_reader.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/json_value.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/json_writer.cpp`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/reader.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/value.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/json/writer.h`: unverified upstream reconstruction; https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6; adapted json include prefix to historical lib/json layout
- `lib/tinyxml/tinystr.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxml.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxml.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tinyxml/tinyxmlparser.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290
- `lib/tmx/TmxLayer.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxLayer.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxMap.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxMap.h`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/tmx/TmxObject.cpp`: unverified donor reconstruction; 181f31e1e9a7f3516c7fbd3d4400aa0822c1d387:lib/tmx/TmxObject.cpp; headerMatch=0; apiOverlap=10000/10000; distance=37
- `lib/tmx/TmxTileset.cpp`: unverified upstream reconstruction; https://github.com/tamatias/tmxparser/tree/6fa4d38742313b6365df0d224b8978be1eb81290; adapted vendored tinyxml/zlib include paths to historical directory layout
- `lib/zlib/adler32.c`: Unmodified official zlib v1.2.5 adler32.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/crc32.c`: Unmodified official zlib v1.2.5 crc32.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/deflate.c`: Unmodified official zlib v1.2.5 deflate.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/deflate.h`: Unmodified official zlib v1.2.5 deflate.h; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzlib.c`: Unmodified official zlib v1.2.5 gzlib.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzread.c`: Unmodified official zlib v1.2.5 gzread.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/gzwrite.c`: Unmodified official zlib v1.2.5 gzwrite.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/infback.c`: Unmodified official zlib v1.2.5 infback.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inffast.c`: Unmodified official zlib v1.2.5 inffast.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inflate.c`: Unmodified official zlib v1.2.5 inflate.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/inftrees.c`: Unmodified official zlib v1.2.5 inftrees.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/trees.c`: Unmodified official zlib v1.2.5 trees.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zlib.h`: Unmodified official zlib v1.2.5 zlib.h; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zutil.c`: Unmodified official zlib v1.2.5 zutil.c; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `lib/zlib/zutil.h`: Unmodified official zlib v1.2.5 zutil.h; Git blob verified against official tag tree 9712272c78b9d9c93746d9c8e156a3728c65ca72. Coherent same-version donor replaces mixed1.2.5/1.2.5 fallback; exact original only when originalHashMatches=true.
- `res/config/map.tmx`: unverified donor reconstruction; authored Tiled geometry/object coordinates from 55e6516e:maps/map1/map.json converted to XML; missing target script reference omitted
- `res/config/object.json`: unverified donor reconstruction; split object descriptors e8b7c3d0e6da989122a0587943a98504342da3cd:config/objects flattened to observed legacy class/path API; target tile/interaction entries preserved; species stats retain uncertainty of reconstructed creatures catalog
- `res/images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `src/creature.cpp`: Missing body adapted from accepted #150 reconstruction to exact #195 default/copy/factory and string-key load API, consolidated object config, src paths and genuine Qt signals. Preserves real combat/actions/inventory/equipment/level mechanics; legacy equipment setters only run when explicitly present, preserving restored slot entries. Loot delegates the surviving same-commit LootProvider. Formulas and absent original body remain inferred; not a parity claim. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/native-middle/recon/08ec144f196a9a5195e281997b5695828ccbd2ab", "sha256": "ed9e1bc1401e2c6dcb98cc025f4773e6d5277f674ce9dc808bf1c9d04c1296d1"}, {"path": "src/creature.h", "sha256": "627da3d68dec495fcdb4ec747e8c7fb09bbb0804eca3417fdfe015109eadb161"}]
- `src/gamescript.cpp`: Surviving nearby historical Python3 C API donor adapted only from former getMapObject to exact #195 declared createMapObject name; preserved actual original source cohort addObject/replaceTile/setProperty functions. No future Boost binding used; source reconstruction not parity. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/native-upper-middle/verify/snapshot-awzoo2ty/source/src/gamescript.cpp", "sha256": "1393d839a74dff59cc81afc99ca59ff473812afaf1f34573c70682cf1cb1dd03"}, {"path": "src/gamescript.h", "sha256": "85a75c2e41c9dcb45e3a473a9aa53184e83fd0c3332997a0ca3ac7584afafa79"}]
- `src/gameview.cpp`: Missing #196 body carried from native-verified #195 reconstruction fae8263548d0f71e1f752718d15c1803db5d47fd with byte-identical corresponding original header (or identical complete project TU/header/resource path inventory). Missing original body delta remains unknown; actual native startup checked separately. Missing body adapted from accepted earlier QWidget backpack/stats/list layout to exact #195 src paths, typeName and genuine PlayerEquippedView map constructor. Preserves real inventory, actions, character and combat views/signals; not exact original. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/source/recovery/payloads/reconstructions/0f/0f1d12502ec20d26023cc1d8a777880d473f1dcb-gameview.cpp", "sha256": "935518bc40dd5b43bcebb5dec1e64149f2aab9ef63db89ae9fdfb54f68dc89d7"}, {"path": "src/gameview.h", "sha256": "02fdf02391f19861c882585ec81dec73dceeedab8c81c3e2d2a229d007a822bf"}] Uses original protected/private Qt signals and slots through the supported metadata connection/invoke API and a local missing-TU QObject refresher, without changing genuine declarations.
- `src/interaction.cpp`: Missing body adapted from accepted #150 std::string native action/effect reconstruction to exact #195 default/copy/load-by-name API, typeName and consolidated config. Retains all native action/effect bodies; removes only save methods absent from surviving class declarations. Not exact source or gameplay parity. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/source/recovery/payloads/reconstructions/0b/0b0a9c19112914c23dcd4a6e2e032f335f7abf76-interaction.cpp", "sha256": "58c845dc10998af9d2593755795e2cbfce4f8fdd9e05369db918e2212cc511ec"}, {"path": "src/interaction.h", "sha256": "10c5b800cf7fa1d21c48f7b8d546fb337322e4c7bb75cb5418ace80b51b61b7b"}]
- `src/map.cpp`: content reconstruction of the BFG-removed original; carried forward unchanged from the reconstruction of 4db6a1b87f6ff850612d815ffa96ecde2bd6faac (previous version of src/map.cpp)
- `src/pathfinder.cpp`: Missing #197 merged pathfinder preserves exact older original base/dumb/random/smart algorithms from native #195/196 cohort, adapting only worker signal names and genuine new CompletionListener API. Constructor counts queued workers before main turn ends; completed movement arrives before ended/deregister; final worker emits Map completion once. Singleton static initialization zeroes genuine workers/started fields. No fabricated completion result, no omitted AI; inferred worker body, not parity. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/native-upper-middle/recon/a66abb977d8290f3e46b61e4b2a9708a87ba6630", "sha256": "ccfeaa238eeb5a20f078ae42af8642001f597c8c62d96392f1feac8361dd8a38"}, {"path": "src/pathfinder.h", "sha256": "5176d4852a684c173bea481e2027b407d7fb3d224ad65806a1227a326c5d0c10"}]
- `src/stats.cpp`: Missing merged Stats/Damage TU assembled from accepted plain #150 Stats reconstruction and surviving #150 Damage implementation for exact #195 merged declarations; no QObject/future API donor retained. Not exact original. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/source/recovery/payloads/reconstructions/4f/4ff9f45b2f23d26fc69280d6c0df542e02efa223-stats.cpp", "sha256": "bff0757ad033b37841a3a1e0ffa12abbb78dae7250c3ef4f9f26dd7c331cefbd"}, {"path": "/tmp/nouraajd-bfg-recovery/native-middle/src/70449d6d/stats/damage.cpp", "sha256": "de430be10d1a6f3f174a2efa9f0604743aff9601c0ab5fb2c9e3eeddf01ff6df"}, {"path": "src/stats.h", "sha256": "462ead5a1e2f69858c6574e13efeb3dcc157d82f48dbf6d7968335f6af0d8bef"}]
- `lib/json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `7d7a5bc10109623d10981d8e8cbed5ea42296b8d63ab2c9fd7c068ccd4bfb952`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
