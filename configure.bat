git clone https://github.com/lisu188/fall-of-nouraajd-windows-tools.git windows-tools

set PATH=windows-tools\Python36\;windows-tools\boost64\;windows-tools\SDL2_image-2.0.5\x86_64-w64-mingw32\;windows-tools\SDL2_ttf-2.0.15\x86_64-w64-mingw32\;windows-tools\SDL2-2.0.12\x86_64-w64-mingw32\;windows-tools\mingw\mingw64\bin\;windows-tools\boost_1_74_0\boost64\lib\;windows-tools\SDL2_image-2.0.5\x86_64-w64-mingw32\bin\;windows-tools\SDL2_ttf-2.0.15\x86_64-w64-mingw32\bin\;windows-tools\SDL2-2.0.12\x86_64-w64-mingw32\bin;%PATH%;

mkdir cmake-build-debug
mkdir cmake-build-release

cmake -B./cmake-build-debug -H. -DCMAKE_BUILD_TYPE=Debug
cmake -B./cmake-build-release -H. -DCMAKE_BUILD_TYPE=Release