#!/bin/bash

sudo apt update
sudo apt install -y build-essential cmake ninja-build ccache \
    python3 python3-dev \
    libboost-dev libboost-filesystem-dev libboost-python-dev \
    libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev

git submodule update --init --recursive
mkdir -p cmake-build-debug
mkdir -p cmake-build-release

cmake -G Ninja -B ./cmake-build-debug -S . \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake -G Ninja -B ./cmake-build-release -S . \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache

#export SDL_VIDEO_X11_VISUALID=0x022 //TODO: check this, this was used to run in WSL ubuntu with xming
