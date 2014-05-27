# Recovered game snapshot

Original commit: `e2e604b09cda43317530a1543d5ef8ae1cf3c3b0`. Original tree: `33e0d5ad348cef78e90cf06d0da4c49fec2cb825`.
Startup was verified from identical recovered sources at `e2e604b09cda43317530a1543d5ef8ae1cf3c3b0`.

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

- `Game.pro`: working reconstruction
- `config/map.tmx`: unverified donor reconstruction; authored Tiled geometry/object coordinates from 55e6516e:maps/map1/map.json converted to XML; missing target script reference omitted
- `config/object.json`: unverified donor reconstruction; split object descriptors e8b7c3d0e6da989122a0587943a98504342da3cd:config/objects flattened to observed legacy class/path API; target tile/interaction entries preserved; species stats retain uncertainty of reconstructed creatures catalog
- `images/loading.png`: synthesized visible 32px placeholder; original artwork unavailable; unverified
- `lib/base64/base64.cpp`: unverified donor reconstruction; 779fb803ff021de5e74ed3b24d7c31a9adcaa236:base64/base64.cpp; headerMatch=0; apiOverlap=10000/10000; distance=14
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
- `lib/tmx/TmxObject.cpp`: unverified donor reconstruction; 181f31e1e9a7f3516c7fbd3d4400aa0822c1d387:lib/tmx/TmxObject.cpp; headerMatch=0; apiOverlap=10000/10000; distance=44
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
- `src/creature.cpp`: working reconstruction
- `src/gamescene.cpp`: working reconstruction
- `src/gameview.cpp`: working reconstruction
- `src/interaction.cpp`: Missing body adapted from accepted #150 std::string native action/effect reconstruction to exact #195 default/copy/load-by-name API, typeName and consolidated config. Retains all native action/effect bodies; removes only save methods absent from surviving class declarations. Not exact source or gameplay parity. Inputs: [{"path": "/tmp/nouraajd-bfg-recovery/source/recovery/payloads/reconstructions/0b/0b0a9c19112914c23dcd4a6e2e032f335f7abf76-interaction.cpp", "sha256": "58c845dc10998af9d2593755795e2cbfce4f8fdd9e05369db918e2212cc511ec"}, {"path": "src/interaction.h", "sha256": "10c5b800cf7fa1d21c48f7b8d546fb337322e4c7bb75cb5418ace80b51b61b7b"}]
- `src/map.cpp`: working reconstruction
- `src/pathfinder.cpp`: content reconstruction of the BFG-removed original; flattened by the #182 refactor; carried from the #180 reconstruction with includes rewritten to the flat src/ layout, MapObject::className renamed typeName to match the same-commit map.h (Effect keeps className)
- `src/stats.cpp`: content reconstruction of the BFG-removed original; flattened by the #182 refactor; carried from the #180 reconstruction with includes rewritten to the flat src/ layout, MapObject::className renamed typeName to match the same-commit map.h (Effect keeps className)
- `lib/json/LICENSE`: https://github.com/open-source-parsers/jsoncpp/tree/4fce396c9d3e27a8ab8fb88e94c1676e021ae3a6 upstream distribution license

Restored source fingerprint: `e664eebd311862fb1c0a92d7d211b659f87bc7af3b3bcb2c086c02e61647c24f`.

The actual 1278 × 718 screenshot and [verification metadata](recovery/verification.json) belong to
this source version. Reconstructed code and borrowed assets are identified in that metadata; they are
not claimed to be the original deleted bytes. BFG removal-marker files are absent from this snapshot.
