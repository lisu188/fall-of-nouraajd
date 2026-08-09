#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DEPS_ROOT="${GAME_ANDROID_DEPS_DIR:-${SCRIPT_DIR}/.deps}"
PYTHON_VERSION="${GAME_ANDROID_PYTHON_VERSION:-3.14.7}"
PYTHON_SHA256="${GAME_ANDROID_PYTHON_SHA256:-6d50cc3aa66e414a439594089bcdfb5f1264358155c70c1f00471c24cfb477fb}"
VCPKG_REF="${GAME_ANDROID_VCPKG_REF:-2026.05.25}"
VCPKG_TRIPLET="arm64-android-dynamic"

for command in awk curl find git sed sha256sum tar; do
    if ! command -v "${command}" >/dev/null 2>&1; then
        echo "Missing required command: ${command}" >&2
        exit 2
    fi
done

if [[ -z "${ANDROID_NDK_HOME:-}" || ! -d "${ANDROID_NDK_HOME}" ]]; then
    echo "ANDROID_NDK_HOME must point to an installed Android NDK." >&2
    exit 3
fi

mkdir -p "${DEPS_ROOT}"

PYTHON_ARCHIVE="${DEPS_ROOT}/python-${PYTHON_VERSION}-aarch64-linux-android.tar.gz"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-aarch64-linux-android.tar.gz"
PYTHON_EXTRACT_ROOT="${DEPS_ROOT}/python-${PYTHON_VERSION}-aarch64-linux-android"

if [[ ! -f "${PYTHON_ARCHIVE}" ]]; then
    curl --fail --location --retry 3 --output "${PYTHON_ARCHIVE}" "${PYTHON_URL}"
fi
printf '%s  %s\n' "${PYTHON_SHA256}" "${PYTHON_ARCHIVE}" | sha256sum --check --status || {
    echo "Python Android archive checksum mismatch: ${PYTHON_ARCHIVE}" >&2
    exit 4
}

if [[ ! -d "${PYTHON_EXTRACT_ROOT}" ]]; then
    mkdir -p "${PYTHON_EXTRACT_ROOT}"
    tar -xzf "${PYTHON_ARCHIVE}" -C "${PYTHON_EXTRACT_ROOT}"
fi

mapfile -t PYTHON_LIBRARIES < <(find "${PYTHON_EXTRACT_ROOT}" -type f -name "libpython${PYTHON_VERSION%.*}.so" -print)
if [[ ${#PYTHON_LIBRARIES[@]} -ne 1 ]]; then
    echo "Expected exactly one libpython${PYTHON_VERSION%.*}.so in ${PYTHON_EXTRACT_ROOT}." >&2
    exit 5
fi
PYTHON_PREFIX="$(cd -- "$(dirname -- "${PYTHON_LIBRARIES[0]}")/.." && pwd)"
if [[ ! -f "${PYTHON_PREFIX}/include/python${PYTHON_VERSION%.*}/Python.h" || ! -d "${PYTHON_PREFIX}/lib/python${PYTHON_VERSION%.*}" ]]; then
    echo "Extracted Python prefix does not have the expected include/lib layout: ${PYTHON_PREFIX}" >&2
    exit 6
fi

VCPKG_ROOT="${DEPS_ROOT}/vcpkg"
if [[ ! -d "${VCPKG_ROOT}/.git" ]]; then
    git clone --depth 1 --branch "${VCPKG_REF}" https://github.com/microsoft/vcpkg.git "${VCPKG_ROOT}"
else
    VCPKG_HEAD="$(git -C "${VCPKG_ROOT}" describe --tags --exact-match 2>/dev/null || git -C "${VCPKG_ROOT}" rev-parse HEAD)"
    if [[ "${VCPKG_HEAD}" != "${VCPKG_REF}" ]]; then
        echo "Existing ${VCPKG_ROOT} is at ${VCPKG_HEAD}, expected ${VCPKG_REF}. Remove it or set GAME_ANDROID_DEPS_DIR." >&2
        exit 7
    fi
fi

if [[ ! -x "${VCPKG_ROOT}/vcpkg" ]]; then
    "${VCPKG_ROOT}/bootstrap-vcpkg.sh" -disableMetrics
fi

VCPKG_INSTALL_ROOT="${DEPS_ROOT}/vcpkg_installed"
"${VCPKG_ROOT}/vcpkg" install \
    --triplet="${VCPKG_TRIPLET}" \
    --overlay-triplets="${SCRIPT_DIR}/triplets" \
    --x-manifest-root="${REPO_ROOT}" \
    --x-install-root="${VCPKG_INSTALL_ROOT}" \
    --disable-metrics

DEPENDENCY_PREFIX="${VCPKG_INSTALL_ROOT}/${VCPKG_TRIPLET}"
if [[ ! -f "${DEPENDENCY_PREFIX}/lib/libSDL2.so" || ! -d "${DEPENDENCY_PREFIX}/share/sdl2" ]]; then
    echo "Dynamic vcpkg Android SDL2 installation is missing: ${DEPENDENCY_PREFIX}" >&2
    exit 8
fi
for dependency in boost-algorithm boost-filesystem boost-pool pybind11 sdl2 sdl2-image sdl2-ttf; do
    if ! grep -Fq "${dependency}" "${VCPKG_INSTALL_ROOT}/vcpkg/status"; then
        echo "vcpkg manifest dependency was not installed for Android: ${dependency}" >&2
        exit 9
    fi
done

mapfile -t SDL_JAVA_DIRS < <(find "${VCPKG_ROOT}/buildtrees/sdl2/src" -type f -path "*/android-project/app/src/main/java/org/libsdl/app/SDLActivity.java" -print | sed 's#/org/libsdl/app/SDLActivity.java$##')
if [[ ${#SDL_JAVA_DIRS[@]} -eq 0 ]]; then
    echo "Could not locate SDLActivity.java in the SDL2 source tree built by vcpkg." >&2
    exit 10
fi
SDL_JAVA_DIR="${SDL_JAVA_DIRS[0]}"
for candidate in "${SDL_JAVA_DIRS[@]}"; do
    if [[ "${candidate}" == *.clean/android-project/app/src/main/java ]]; then
        SDL_JAVA_DIR="${candidate}"
        break
    fi
done

PROPERTIES_FILE="${SCRIPT_DIR}/gradle.properties"
cat >"${PROPERTIES_FILE}" <<EOF
gameAndroidPythonPrefix=${PYTHON_PREFIX}
gameAndroidDependencyPrefix=${DEPENDENCY_PREFIX}
gameAndroidSdlJavaDir=${SDL_JAVA_DIR}
EOF

cat <<EOF
Android dependencies are ready.
Python prefix: ${PYTHON_PREFIX}
Dependency prefix: ${DEPENDENCY_PREFIX}
SDL Java sources: ${SDL_JAVA_DIR}
Gradle properties: ${PROPERTIES_FILE}

Build from ${SCRIPT_DIR} with Gradle 9.5.0 or newer in the 9.5 line:
  gradle :app:assembleDebug
EOF
