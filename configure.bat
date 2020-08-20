git clone https://github.com/lisu188/fall-of-nouraajd-windows-tools.git windows-tools

set PATH=%cd%\windows-tools\Python36\;%cd%\windows-tools\boost64;%cd%\windows-tools\SDL2_image-2.0.5\x86_64-w64-mingw32\;%cd%\windows-tools\SDL2_ttf-2.0.15\x86_64-w64-mingw32\;%cd%\windows-tools\SDL2-2.0.12\x86_64-w64-mingw32\;%cd%\windows-tools\mingw\mingw64\bin\;%cd%\windows-tools\boost_1_74_0\boost64\lib\;%cd%\windows-tools\SDL2_image-2.0.5\x86_64-w64-mingw32\bin\;%cd%\windows-tools\SDL2_ttf-2.0.15\x86_64-w64-mingw32\bin\;%cd%\windows-tools\SDL2-2.0.12\x86_64-w64-mingw32\bin\;C:\Program Files\CMake\bin;

mkdir cmake-build-debug
mkdir cmake-build-release

dir windows-tools
%cd%\windows-tools\mingw\mingw64\bin\gcc

cmake -B./cmake-build-debug -H. -DCMAKE_BUILD_TYPE=Debug -DCMAKE_MAKE_PROGRAM=mingw32-make.exe -G "MinGW Makefiles"
cmake -B./cmake-build-release -H. -DCMAKE_BUILD_TYPE=Release -DCMAKE_MAKE_PROGRAM=mingw32-make.exe -G "MinGW Makefiles"