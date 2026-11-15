#!/usr/bin/env bash
set -euo pipefail

source_root=/opt/recovery/toolchain-source
source_lock="${source_root}/${RECOVERY_SOURCE_LOCK:-sources.json}"
# Optional BuildKit bind mount of pre-staged archives (see stage_sources.sh).
source_cache=/opt/recovery/source-cache
work_root=/tmp/recovery-toolchain-build
mkdir -p "${work_root}"

python3 - "${source_lock}" "${work_root}" "${source_cache}" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

lock = json.loads(Path(sys.argv[1]).read_text())
destination = Path(sys.argv[2])
cache = Path(sys.argv[3])
for source in lock["sources"]:
    name = source.get("archive") or source["url"].rsplit("/", 1)[-1]
    archive = destination / name
    staged = cache / name
    if staged.is_file():
        archive.write_bytes(staged.read_bytes())
    elif source.get("url"):
        subprocess.check_call([
            "curl", "--fail", "--location", "--silent", "--show-error", "--retry", "3",
            "--output", str(archive), source["url"],
        ])
    else:
        raise SystemExit("Source must be pre-staged with stage_sources.sh: " + source["name"])
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != source["sha256"]:
        raise SystemExit("Source checksum mismatch for " + source["name"])
    subprocess.check_call(["tar", "-xf", str(archive), "-C", str(destination)])
    archive.unlink()
PY

# BuildKit keeps only 2 MiB of output per step, so verbose builds log to files and
# report a focused failure excerpt instead of being silently clipped.
runLogged() {
    local log="$1"
    shift
    if ! "$@" > "${log}" 2>&1; then
        echo "Command failed: $*" >&2
        grep -n -B 3 -A 40 -E '^\.\.\.failed|error:|Error [0-9]' "${log}" | head -n 400 >&2 || true
        tail -n 40 "${log}" >&2
        return 1
    fi
    tail -n 3 "${log}"
}

buildPython() {
    local version="$1"
    local prefix="$2"
    local configure_options=(--prefix="${prefix}" --enable-shared)
    if [[ "${version}" != 3.3.7 ]]; then
        configure_options+=(--without-ensurepip)
    fi
    pushd "${work_root}/Python-${version}"
    runLogged "${work_root}/python-${version}-configure.log" \
        env CC=gcc-5 CXX=g++-5 LDFLAGS="-Wl,-rpath,${prefix}/lib" ./configure "${configure_options[@]}"
    runLogged "${work_root}/python-${version}-make.log" make -j"$(nproc)"
    runLogged "${work_root}/python-${version}-install.log" make altinstall
    popd
}

buildPython 2.7.18 /opt/recovery/python/2.7.18
buildPython 3.3.7 /opt/recovery/python/3.3.7
buildPython 3.4.10 /opt/recovery/python/3.4.10
buildPython 3.12.9 /opt/recovery/controller

pushd "${work_root}/boost_1_58_0"
# Boost 1.58 calls the Python >= 3.4 _Py_fopen(const char *) for every Python 3; Python 3.3
# takes a PyObject path. Apply the upstream Boost.Python fix (released in Boost 1.60).
python3 - libs/python/src/exec.cpp <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text()
original = """#if PY_VERSION_HEX >= 0x03000000
  // See http://www.codeproject.com/Articles/820116/Embedding-Python-program-in-a-C-Cplusplus-code
  FILE *fs = _Py_fopen(f, "r");
#else"""
patched = """#if PY_VERSION_HEX >= 0x03040000
  FILE *fs = _Py_fopen(f, "r");
#elif PY_VERSION_HEX >= 0x03000000
  PyObject *fo = Py_BuildValue("s", f);
  FILE *fs = _Py_fopen(fo, "r");
  Py_DECREF(fo);
#else"""
if source.count(original) != 1:
    raise SystemExit("Unexpected Boost.Python exec.cpp; refusing to patch")
path.write_text(source.replace(original, patched))
PY
runLogged "${work_root}/boost-bootstrap.log" \
    ./bootstrap.sh --with-toolset=gcc --with-libraries=python,system,filesystem,serialization,thread,date_time
for version in 2.7.18 3.3.7 3.4.10; do
    abi="${version%.*}"
    suffix="${abi//./}"
    python_prefix="/opt/recovery/python/${version}"
    include_suffix="${abi}"
    if [[ "${abi}" != 2.7 ]]; then
        include_suffix="${abi}m"
    fi
    config="${work_root}/boost-python-${suffix}.jam"
    printf 'using gcc : 5 : g++-5 ;\nusing python : %s : %s/bin/python%s : %s/include/python%s : %s/lib ;\n' \
        "${abi}" "${python_prefix}" "${abi}" "${python_prefix}" "${include_suffix}" \
        "${python_prefix}" > "${config}"
    runLogged "${work_root}/boost-py${suffix}.log" env LD_LIBRARY_PATH="${python_prefix}/lib" \
        ./b2 --user-config="${config}" --build-dir="${work_root}/boost-build-${suffix}" \
        --prefix="/opt/recovery/boost/py${suffix}" --layout=system toolset=gcc-5 \
        python="${abi}" link=shared runtime-link=shared variant=release threading=multi \
        --with-python --with-system --with-filesystem --with-serialization --with-thread --with-date_time \
        -j"$(nproc)" install
done
popd

cp "${source_lock}" /opt/recovery/source-lock.json
/opt/recovery/controller/bin/python3.12 --version
/usr/lib/x86_64-linux-gnu/qt5/bin/qmake -query QT_VERSION
g++-5 -dumpversion
rm -rf "${work_root}"
