#!/bin/bash

apt update
apt install build-essential cmake -y
apt install python3-dev -y
apt install libboost-dev libboost-system-dev libboost-filesystem-dev libboost-python-dev -y
apt install libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev -y
apt install libjsoncpp-dev

ln -s /usr/lib/x86_64-linux-gnu/libboost_python-py36.a /usr/lib/x86_64-linux-gnu/libboost_python3.a
ln -s /usr/lib/x86_64-linux-gnu/libboost_python-py36.so /usr/lib/x86_64-linux-gnu/libboost_python3.so
