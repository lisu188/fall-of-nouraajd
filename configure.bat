@echo off
setlocal EnableExtensions EnableDelayedExpansion

where cmake >nul 2>nul
if errorlevel 1 (
    echo CMake was not found on PATH.
    echo Install Visual Studio 2022 with the C++ CMake tools component, or add CMake to PATH.
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install Python 3 and make sure it is available on PATH.
    exit /b 1
)

for /f "usebackq delims=" %%i in (`python -c "import sys; print(sys.executable)"`) do set "PYTHON_EXECUTABLE=%%i"
for /f "usebackq delims=" %%i in (`python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`) do set "PYTHON_VERSION=%%i"
if not "!PYTHON_VERSION!"=="3.12" (
    echo Python 3.12 is required on PATH for the Windows build.
    echo Found Python !PYTHON_VERSION! at:
    echo   !PYTHON_EXECUTABLE!
    echo vcpkg provides Python 3.12 development libraries, so the interpreter must match that ABI.
    exit /b 1
)

if not defined VCPKG_ROOT (
    if defined VCPKG_INSTALLATION_ROOT set "VCPKG_ROOT=!VCPKG_INSTALLATION_ROOT!"
)
if not defined VCPKG_ROOT (
    if exist "C:\vcpkg" set "VCPKG_ROOT=C:\vcpkg"
)
if not defined VCPKG_ROOT (
    set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
    if exist "!VSWHERE!" (
        for /f "usebackq delims=" %%i in (`"!VSWHERE!" -latest -products * -find "VC\vcpkg\vcpkg.exe" 2^>nul`) do (
            if not defined VCPKG_ROOT (
                for %%d in ("%%~dpi.") do set "VCPKG_ROOT=%%~fd"
            )
        )
    )
)
if not defined VCPKG_ROOT (
    echo VCPKG_ROOT was not set, C:\vcpkg was not found, and Visual Studio vcpkg was not found.
    echo Install vcpkg, then set VCPKG_ROOT to its install directory.
    exit /b 1
)

set "VCPKG_TOOLCHAIN_FILE=!VCPKG_ROOT!\scripts\buildsystems\vcpkg.cmake"
if not exist "!VCPKG_TOOLCHAIN_FILE!" (
    echo vcpkg CMake toolchain file was not found:
    echo   !VCPKG_TOOLCHAIN_FILE!
    exit /b 1
)

if not defined CMAKE_GENERATOR set "CMAKE_GENERATOR=Visual Studio 17 2022"
if not defined CMAKE_GENERATOR_PLATFORM set "CMAKE_GENERATOR_PLATFORM=x64"
if not defined VCPKG_TARGET_TRIPLET set "VCPKG_TARGET_TRIPLET=x64-windows"
if not defined VCPKG_INSTALLED_DIR set "VCPKG_INSTALLED_DIR=%CD%\vcpkg_installed"
set "VCPKG_INSTALLED_DIR_CMAKE=!VCPKG_INSTALLED_DIR:\=/!"

call :configure cmake-build-debug
if errorlevel 1 exit /b 1

call :configure cmake-build-release
if errorlevel 1 exit /b 1

exit /b 0

:configure
set "BUILD_DIR=%~1"

if exist "!BUILD_DIR!\CMakeCache.txt" (
    findstr /C:"CMAKE_GENERATOR:INTERNAL=!CMAKE_GENERATOR!" "!BUILD_DIR!\CMakeCache.txt" >nul 2>nul
    if errorlevel 1 (
        echo Recreating !BUILD_DIR! because it was configured with a different CMake generator.
        del /q "!BUILD_DIR!\CMakeCache.txt" 2>nul
        rmdir /s /q "!BUILD_DIR!\CMakeFiles" 2>nul
    ) else (
        findstr /C:"CMAKE_GENERATOR_PLATFORM:INTERNAL=!CMAKE_GENERATOR_PLATFORM!" "!BUILD_DIR!\CMakeCache.txt" >nul 2>nul
        if errorlevel 1 (
            echo Recreating !BUILD_DIR! because it was configured for a different platform.
            del /q "!BUILD_DIR!\CMakeCache.txt" 2>nul
            rmdir /s /q "!BUILD_DIR!\CMakeFiles" 2>nul
        )
    )
    if exist "!BUILD_DIR!\CMakeCache.txt" (
        findstr /C:"VCPKG_INSTALLED_DIR:PATH=!VCPKG_INSTALLED_DIR_CMAKE!" "!BUILD_DIR!\CMakeCache.txt" >nul 2>nul
        if errorlevel 1 (
            echo Recreating !BUILD_DIR! because it was configured with a different vcpkg installed directory.
            del /q "!BUILD_DIR!\CMakeCache.txt" 2>nul
            rmdir /s /q "!BUILD_DIR!\CMakeFiles" 2>nul
        )
    )
)

cmake -B ./!BUILD_DIR! -S . ^
    -U "Python3_*" ^
    -U "_Python3_*" ^
    -U "PYBIND11_PYTHON_*" ^
    -G "!CMAKE_GENERATOR!" ^
    -A "!CMAKE_GENERATOR_PLATFORM!" ^
    -DCMAKE_TOOLCHAIN_FILE="!VCPKG_TOOLCHAIN_FILE!" ^
    -DVCPKG_INSTALLED_DIR="!VCPKG_INSTALLED_DIR!" ^
    -DVCPKG_TARGET_TRIPLET="!VCPKG_TARGET_TRIPLET!" ^
    -DPython3_EXECUTABLE="!PYTHON_EXECUTABLE!"
exit /b %ERRORLEVEL%
