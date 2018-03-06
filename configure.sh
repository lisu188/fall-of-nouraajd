#!/bin/bash

sudo apt install build-essential cmake -y
sudo apt install python3-dev -y
sudo apt install libboost-dev libboost-system-dev libboost-filesystem-dev libboost-python-dev -y
sudo apt install libsdl2-dev libsdl2-ttf-dev libsdl2-image-dev -y
sudo apt install jsoncpp-dev

sudo ln -s /usr/lib/x86_64-linux-gnu/libboost_python-py36.a /usr/lib/x86_64-linux-gnu/libboost_python3.a
sudo ln -s /usr/lib/x86_64-linux-gnu/libboost_python-py36.so /usr/lib/x86_64-linux-gnu/libboost_python3.so
