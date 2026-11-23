# Historical Linux toolchains

The recovery image keeps the Qt5 game builds separate from the current game's
dependencies. Its immutable Ubuntu 16.04 amd64 base supplies GCC 5.4 and Qt 5.5.1.
The compiler and Qt package versions are pinned in `Dockerfile`. The archived
Ubuntu repository still supplies Xenial at `archive.ubuntu.com`; switching this
recipe to `old-releases.ubuntu.com` currently returns 404.

`sources.json` locks every downloaded source archive by SHA256. The four Python
hashes were computed from archives downloaded directly from python.org. The
Boost hash also has an official release-metadata link in the lock. Archives are
checked before extraction. The resulting image retains its source lock and full
installed-package list; CI also records the image ID used for each validation run.

The embedded interpreter variants are CPython 2.7.18, 3.3.7 and 3.4.10. Each has
its own Boost 1.58 installation and recipe environment. These variants are needed
because the historical sources switch between Python 3 and Python 2 initialization
APIs, then return to Python 3. Historical library/include paths use the recipe's
`CPATH`, `LIBRARY_PATH` and `LD_LIBRARY_PATH` fallbacks. `PYTHONHOME` is set only for
the historical child process, never globally in the image.

The separate CPython 3.12.9 controller runs the modern recovery scripts. Its SSL
module is optional in this old build environment: downloading sources uses curl
during image construction, and validation runs without network access.

Build the image from the repository root on a Docker host:

```sh
docker build --platform linux/amd64 --tag nouraajd-recovery:qt5 recovery/toolchains
```

### Hosts without python.org or Boost archive access

`sources-git.json` is an alternative lock: each CPython source is the official
release tag's commit exported with `git archive --format=tar --prefix=Python-<version>/`
(the commits are pinned and the exported tarballs hashed), and Boost is the identical
release archive with a SourceForge mirror. Stage every archive, then pass the cache as
a named build context (the default `source-cache` stage is empty, so normal builds still
download from `sources.json`):

```sh
python3 recovery/toolchains/stage_sources.py --lock recovery/toolchains/sources-git.json /tmp/recovery-sources
docker build --platform linux/amd64 --build-context source-cache=/tmp/recovery-sources \
    --build-arg RECOVERY_SOURCE_LOCK=sources-git.json --tag nouraajd-recovery:qt5 recovery/toolchains
```

Xenial apt only speaks plain HTTP to the archive. On a host that allows only HTTPS
through a proxy, run the transport adapter and build with host networking; apt still
verifies every archive signature and package hash:

```sh
python3 recovery/toolchains/http_archive_proxy.py 3142 &
docker build --network host --build-arg http_proxy=http://127.0.0.1:3142 ...
```

Boost 1.58's `exec.cpp` assumes the Python >= 3.4 `_Py_fopen(const char *)`; `build.sh`
applies the upstream Boost.Python fix so the Python 3.3 variant builds. Python and Boost
build output goes to log files and only failure excerpts are printed, because BuildKit
keeps at most 2 MiB of output per step.

Validate a restored version with the real game build and an isolated startup
session. Use an absolute writable results directory outside the read-only source
mount:

```sh
mkdir -p /tmp/nouraajd-history-results
docker run --rm --network none --user "$(id -u):$(id -g)" \
    --volume "$PWD:$PWD:ro" --workdir "$PWD" \
    --volume /tmp/nouraajd-history-results:/results \
    nouraajd-recovery:qt5 scripts/verify_history.py \
    --commit b9ae428b --recipes recovery/toolchains/qt5.json --output-dir /results
```

The `Historical recovery` workflow uses 16 snapshots per shard and at most four
concurrent shards. Image construction runs independently of restoration checks,
so unresolved files do not prevent establishing the build environment. Every
assigned snapshot must restore, compile, link and pass startup; missing files,
missing tools, timeouts and failed readiness checks fail the shard. Logs and partial
results remain available as artifacts.

Startup evidence records the authored mode. Game snapshots still require a live
player, a loaded map, an event loop, a rendered frame, and clean process exit.
The early editor route is selected only when the restored `main.cpp` and
`config/init.json` exactly match surviving Git blobs and the reviewed original
branch selects `MapView`. Its proof records those blob/SHA-256 identities and
requires the real `MapView`/`MapScene`, an owned nonempty map, a rendered frame,
an event loop, and clean exit. Editor reports carry `mode: editor` and make no
player or gameplay claim; they cannot satisfy a game-mode verification. The
original editor configuration and entrypoint are preserved. Unknown entrypoint
shapes or reconstructed editor flags fail rather than selecting a weaker check.

The exact original #98 resource omission is handled by a separate generated qrc,
using the 21 original image files and the immediately following original commit's
manifest delta. The original manifest, animation provider and configuration stay
unchanged. Preparation pins all 24 inputs, the generated output and its portable
replay helper; the qmake argument and startup compatibility boundary are recorded.
This proof is explicitly labeled startup with supplemental resource compatibility.
Earlier and already repaired manifests keep their ordinary recipes.

The image digest and critical compiler/Qt packages are fixed. Transitive Ubuntu
packages come from the archived repository and their resolved versions are recorded
in `/opt/recovery-installed-packages.txt`; the workflow shares the identical built
image between shards rather than independently resolving packages per snapshot.
