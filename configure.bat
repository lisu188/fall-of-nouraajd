git clone https://github.com/lisu188/fall-of-nouraajd-windows-tools.git windows-tools

set PATH=windows-tools/Python36/;windows-tools/boost64/;windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/;windows-tools/SDL2_ttf-2.0.15/x86_64-w64-mingw32/;windows-tools/SDL2-2.0.12/x86_64-w64-mingw32/;windows-tools/mingw/mingw64/bin/;windows-tools/boost_1_74_0/boost64/lib/;windows-tools/SDL2_image-2.0.5/x86_64-w64-mingw32/bin/;windows-tools/SDL2_ttf-2.0.15/x86_64-w64-mingw32/bin/;windows-tools/SDL2-2.0.12/x86_64-w64-mingw32/bin;C:\Program Files\CMake\bin;

mkdir cmake-build-debug
mkdir cmake-build-release

set CC=D:\a\fall-of-nouraajd\fall-of-nouraajd\windows-tools\mingw\mingw64\bin\gcc.exe
set CXX=D:\a\fall-of-nouraajd\fall-of-nouraajd\windows-tools\mingw\mingw64\bin\g++.exe

rd /s /q "C:/Program Files (x86)/Microsoft Visual Studio"

cmake -B./cmake-build-debug -H. -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_COMPILER=%CXX% -DCMAKE_C_COMPILER=%CC%
cmake -B./cmake-build-release -H. -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=%CXX% -DCMAKE_C_COMPILER=%CC%