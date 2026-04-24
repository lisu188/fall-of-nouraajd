#!/bin/bash

sudo apt-get update
sudo apt-get install -y build-essential cmake ninja-build ccache \
    python3 python3-dev \
    libboost-dev \
    libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev \
    nlohmann-json3-dev \
    xvfb xauth

git submodule update --init --recursive
mkdir -p cmake-build-debug
mkdir -p cmake-build-release

python3 -m pip install --upgrade pybind11 pillow
PYBIND11_DIR="$(python3 -m pybind11 --cmakedir)"

cmake -G Ninja -B ./cmake-build-debug -S . \
    -DCMAKE_BUILD_TYPE=Debug \
    -Dpybind11_DIR="${PYBIND11_DIR}" \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake -G Ninja -B ./cmake-build-release -S . \
    -DCMAKE_BUILD_TYPE=Release \
    -Dpybind11_DIR="${PYBIND11_DIR}" \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

#export SDL_VIDEO_X11_VISUALID=0x022 //TODO: check this, this was used to run in WSL ubuntu with xming
