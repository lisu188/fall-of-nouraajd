#!/usr/bin/env bash
set -euo pipefail

source_root=/opt/recovery/toolchain-source
work_root=/tmp/recovery-toolchain-build
mkdir -p "${work_root}"

python3 - "${source_root}/sources.json" "${work_root}" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

lock = json.loads(Path(sys.argv[1]).read_text())
destination = Path(sys.argv[2])
for source in lock["sources"]:
    archive = destination / source["url"].rsplit("/", 1)[-1]
    subprocess.check_call([
        "curl", "--fail", "--location", "--silent", "--show-error", "--retry", "3",
        "--output", str(archive), source["url"],
    ])
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != source["sha256"]:
        raise SystemExit("Source checksum mismatch for " + source["name"])
    subprocess.check_call(["tar", "-xf", str(archive), "-C", str(destination)])
PY

buildPython() {
    local version="$1"
    local prefix="$2"
    local configure_options=(--prefix="${prefix}" --enable-shared)
    if [[ "${version}" != 3.3.7 ]]; then
        configure_options+=(--without-ensurepip)
    fi
    pushd "${work_root}/Python-${version}"
    CC=gcc-5 CXX=g++-5 LDFLAGS="-Wl,-rpath,${prefix}/lib" \
        ./configure "${configure_options[@]}"
    make -j"$(nproc)"
    make altinstall
    popd
}

buildPython 2.7.18 /opt/recovery/python/2.7.18
buildPython 3.3.7 /opt/recovery/python/3.3.7
buildPython 3.4.10 /opt/recovery/python/3.4.10
buildPython 3.12.9 /opt/recovery/controller

pushd "${work_root}/boost_1_58_0"
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
    LD_LIBRARY_PATH="${python_prefix}/lib" \
        ./b2 --user-config="${config}" --build-dir="${work_root}/boost-build-${suffix}" \
        --prefix="/opt/recovery/boost/py${suffix}" --layout=system toolset=gcc-5 \
        python="${abi}" link=shared runtime-link=shared variant=release threading=multi \
        --with-python --with-system --with-filesystem --with-serialization --with-thread --with-date_time \
        -j"$(nproc)" install
done
popd

cp "${source_root}/sources.json" /opt/recovery/source-lock.json
/opt/recovery/controller/bin/python3.12 --version
qmake -query QT_VERSION
g++-5 -dumpversion
rm -rf "${work_root}"
