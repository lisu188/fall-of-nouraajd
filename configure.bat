git clone https://github.com/lisu188/fall-of-nouraajd-windows-tools.git windows-tools

set PATH=%pythonLocation%\;%pythonLocation%\Scripts\;%cd%\windows-tools\Python36\;%cd%\windows-tools\boost64;%cd%\windows-tools\SDL2_image-2.0.5\x86_64-w64-mingw32\;%cd%\windows-tools\SDL2_ttf-2.0.15\x86_64-w64-mingw32\;%cd%\windows-tools\SDL2-2.0.12\x86_64-w64-mingw32\;%cd%\windows-tools\mingw\mingw64\bin\;%cd%\windows-tools\boost_1_74_0\boost64\lib\;%cd%\windows-tools\SDL2_image-2.0.5\x86_64-w64-mingw32\bin\;%cd%\windows-tools\SDL2_ttf-2.0.15\x86_64-w64-mingw32\bin\;%cd%\windows-tools\SDL2-2.0.12\x86_64-w64-mingw32\bin\;C:\Program Files\CMake\bin;%PATH%
set PYTHON_EXECUTABLE=%pythonLocation%\python.exe
for /f "usebackq delims=" %%i in (`"%PYTHON_EXECUTABLE%" -m pybind11 --cmakedir`) do set PYBIND11_DIR=%%i

mkdir cmake-build-debug
mkdir cmake-build-release

cmake -B./cmake-build-debug -H. -DCMAKE_BUILD_TYPE=Debug -G "MinGW Makefiles" -DPython3_ROOT_DIR="%pythonLocation%" -DPython3_EXECUTABLE="%PYTHON_EXECUTABLE%" -Dpybind11_DIR="%PYBIND11_DIR%"
cmake -B./cmake-build-release -H. -DCMAKE_BUILD_TYPE=Release -G "MinGW Makefiles" -DPython3_ROOT_DIR="%pythonLocation%" -DPython3_EXECUTABLE="%PYTHON_EXECUTABLE%" -Dpybind11_DIR="%PYBIND11_DIR%"
