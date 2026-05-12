#!/bin/bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build ccache clang-format \
    python3 python3-dev pybind11-dev python3-pil \
    libboost-dev \
    libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev \
    nlohmann-json3-dev \
    xvfb xauth

git submodule update --init --recursive
mkdir -p cmake-build-debug
mkdir -p cmake-build-release

PYBIND11_CONFIG="$(dpkg-query -L pybind11-dev | awk '/\/pybind11Config.cmake$/ { print; exit }')"
if [[ -z "${PYBIND11_CONFIG}" ]]; then
    echo "pybind11Config.cmake was not found in the pybind11-dev package" >&2
    exit 1
fi
PYBIND11_DIR="$(dirname "${PYBIND11_CONFIG}")"

cmake -G Ninja -B ./cmake-build-debug -S . \
    -DCMAKE_BUILD_TYPE=Debug \
    -Dpybind11_DIR="${PYBIND11_DIR}" \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake -G Ninja -B ./cmake-build-release -S . \
    -DCMAKE_BUILD_TYPE=Release \
    -Dpybind11_DIR="${PYBIND11_DIR}" \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

#export SDL_VIDEO_X11_VISUALID=0x022 //TODO: check this, this was used to run in WSL ubuntu with xming
