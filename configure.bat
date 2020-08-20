mkdir -p cmake-build-debug
mkdir -p cmake-build-release

cmake -B./cmake-build-debug -H. -DCMAKE_BUILD_TYPE=Debug
cmake -B./cmake-build-release -H. -DCMAKE_BUILD_TYPE=Release