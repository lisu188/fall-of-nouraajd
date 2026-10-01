#!/bin/bash
set -euo pipefail

if [[ "${GAME_CONFIGURE_SKIP_APT:-0}" != "1" ]]; then
    sudo apt-get update
    sudo apt-get install -y build-essential cmake ninja-build ccache clang-format black \
        python3 python3-dev python3-pip python3-venv pybind11-dev python3-pil \
        libboost-dev \
        libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev \
        xvfb xauth
fi

if [[ "${GAME_CONFIGURE_SKIP_SUBMODULES:-0}" != "1" ]]; then
    git submodule update --init --recursive
fi
build_types_raw="${GAME_CONFIGURE_BUILD_TYPES:-Debug Release}"
read -r -a build_types <<< "${build_types_raw//,/ }"
if [[ "${#build_types[@]}" -eq 0 ]]; then
    echo "GAME_CONFIGURE_BUILD_TYPES did not contain any build types" >&2
    exit 2
fi

PYBIND11_CONFIG="$(dpkg-query -L pybind11-dev | awk '/\/pybind11Config.cmake$/ { print; exit }')"
if [[ -z "${PYBIND11_CONFIG}" ]]; then
    echo "pybind11Config.cmake was not found in the pybind11-dev package" >&2
    exit 1
fi
PYBIND11_DIR="$(dirname "${PYBIND11_CONFIG}")"

for build_type in "${build_types[@]}"; do
    build_type_lower="$(tr '[:upper:]' '[:lower:]' <<< "${build_type}")"
    build_dir="cmake-build-${build_type_lower}"
    mkdir -p "${build_dir}"
    cmake -G Ninja -B "./${build_dir}" -S . \
        -DCMAKE_BUILD_TYPE="${build_type}" \
        -Dpybind11_DIR="${PYBIND11_DIR}" \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
done

#export SDL_VIDEO_X11_VISUALID=0x022 //TODO: check this, this was used to run in WSL ubuntu with xming
