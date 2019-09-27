#!/bin/bash

sudo apt update
sudo apt install build-essential cmake -y
sudo apt install python3-dev -y
sudo apt install libboost-dev libboost-filesystem-dev libboost-python-dev -y
sudo apt install libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev -y

sudo ln -fs /usr/lib/x86_64-linux-gnu/libboost_python-py36.a /usr/lib/x86_64-linux-gnu/libboost_python3.a
sudo ln -fs /usr/lib/x86_64-linux-gnu/libboost_python-py36.so /usr/lib/x86_64-linux-gnu/libboost_python3.so

mkdir -p cmake-build-debug
mkdir -p cmake-build-release

cmake -B./cmake-build-debug -H. -DCMAKE_BUILD_TYPE=Debug
cmake -B./cmake-build-release -H. -DCMAKE_BUILD_TYPE=Release

#export SDL_VIDEO_X11_VISUALID=0x022 //TODO: check this, this was used to run in WSL ubuntu with xming
