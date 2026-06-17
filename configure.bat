@echo off
setlocal EnableExtensions EnableDelayedExpansion

if not defined GAME_WINDOWS_FAST_BUILD set "GAME_WINDOWS_FAST_BUILD=0"
if not defined GAME_WINDOWS_REQUIRE_FAST_TOOLS set "GAME_WINDOWS_REQUIRE_FAST_TOOLS=0"
if not defined GAME_WINDOWS_INSTALL_FAST_TOOLS (
    if "!GAME_WINDOWS_FAST_BUILD!"=="1" (
        set "GAME_WINDOWS_INSTALL_FAST_TOOLS=1"
    ) else (
        set "GAME_WINDOWS_INSTALL_FAST_TOOLS=0"
    )
)

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

call :add_python_user_scripts_to_path

for /f "usebackq delims=" %%i in (`python -c "import sys; print(sys.executable)"`) do set "PYTHON_EXECUTABLE=%%i"
for /f "usebackq delims=" %%i in (`python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`) do set "PYTHON_VERSION=%%i"
for /f "usebackq delims=" %%i in (`python -m pybind11 --cmakedir`) do set "PYBIND11_DIR=%%i"
if not defined PYBIND11_DIR (
    echo pybind11 was not found for the active Python interpreter.
    echo Install it with:
    echo   python -m pip install --upgrade pybind11
    exit /b 1
)
if not "!PYTHON_VERSION!"=="3.12" (
    echo Python 3.12 is required on PATH for the Windows build.
    echo Found Python !PYTHON_VERSION! at:
    echo   !PYTHON_EXECUTABLE!
    echo CMake links against the active interpreter and development libraries, so the ABI must match CI.
    exit /b 1
)

if defined VCPKG_INSTALLATION_ROOT (
    if exist "!VCPKG_INSTALLATION_ROOT!\vcpkg.exe" (
        if not defined VCPKG_ROOT (
            set "VCPKG_ROOT=!VCPKG_INSTALLATION_ROOT!"
        ) else (
            echo !VCPKG_ROOT! | findstr /I /C:"\VC\vcpkg" >nul 2>nul
            if not errorlevel 1 set "VCPKG_ROOT=!VCPKG_INSTALLATION_ROOT!"
        )
    )
)
if defined VCPKG_ROOT (
    echo !VCPKG_ROOT! | findstr /I /C:"\VC\vcpkg" >nul 2>nul
    if not errorlevel 1 (
        if exist "C:\vcpkg\vcpkg.exe" set "VCPKG_ROOT=C:\vcpkg"
    )
)
if not defined VCPKG_ROOT (
    if exist "C:\vcpkg\vcpkg.exe" set "VCPKG_ROOT=C:\vcpkg"
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

if "!GAME_WINDOWS_FAST_BUILD!"=="1" (
    if not defined CONFIGURE_BUILD_DIRS set "CONFIGURE_BUILD_DIRS=cmake-build-release"
    if not defined VCPKG_TARGET_TRIPLET set "VCPKG_TARGET_TRIPLET=x64-windows-release"
    if not defined VCPKG_INSTALLED_DIR set "VCPKG_INSTALLED_DIR=%CD%\vcpkg_installed\fast"

    call :ensure_fast_tool ninja ninja Ninja-build.Ninja
    if errorlevel 1 (
        if "!GAME_WINDOWS_REQUIRE_FAST_TOOLS!"=="1" exit /b 1
    )

    call :ensure_fast_tool sccache sccache Mozilla.sccache
    if errorlevel 1 (
        if "!GAME_WINDOWS_REQUIRE_FAST_TOOLS!"=="1" exit /b 1
    )
)

if not defined CMAKE_GENERATOR (
    if "!GAME_WINDOWS_FAST_BUILD!"=="1" (
        where ninja >nul 2>nul
        if not errorlevel 1 set "CMAKE_GENERATOR=Ninja"
    )
)
if not defined CMAKE_GENERATOR set "CMAKE_GENERATOR=Visual Studio 17 2022"

if /I "!CMAKE_GENERATOR!"=="Ninja" (
    set "CMAKE_GENERATOR_PLATFORM="
    call :ensure_msvc_env
    if errorlevel 1 exit /b 1
) else (
    if not defined CMAKE_GENERATOR_PLATFORM set "CMAKE_GENERATOR_PLATFORM=x64"
)

if "!GAME_WINDOWS_FAST_BUILD!"=="1" (
    if not defined SCCACHE_EXECUTABLE (
        for /f "usebackq delims=" %%i in (`where sccache 2^>nul`) do (
            if not defined SCCACHE_EXECUTABLE set "SCCACHE_EXECUTABLE=%%i"
        )
    )
    if defined SCCACHE_EXECUTABLE (
        set "CMAKE_C_COMPILER_LAUNCHER=!SCCACHE_EXECUTABLE!"
        set "CMAKE_CXX_COMPILER_LAUNCHER=!SCCACHE_EXECUTABLE!"
    )
)

if not defined VCPKG_TARGET_TRIPLET set "VCPKG_TARGET_TRIPLET=x64-windows"
if not defined VCPKG_INSTALLED_DIR set "VCPKG_INSTALLED_DIR=%CD%\vcpkg_installed"
if not defined VCPKG_OVERLAY_TRIPLETS set "VCPKG_OVERLAY_TRIPLETS="
if not defined VCPKG_MANIFEST_MODE set "VCPKG_MANIFEST_MODE=ON"
if not defined CONFIGURE_BUILD_DIRS set "CONFIGURE_BUILD_DIRS=cmake-build-debug cmake-build-release"
set "VCPKG_INSTALLED_DIR_CMAKE=!VCPKG_INSTALLED_DIR:\=/!"

for %%d in (!CONFIGURE_BUILD_DIRS!) do (
    call :configure %%d
    if errorlevel 1 exit /b 1
)

exit /b 0

:add_python_user_scripts_to_path
for /f "usebackq delims=" %%i in (`python -c "import site; from pathlib import Path; print(Path(site.getuserbase()) / 'Scripts')" 2^>nul`) do set "PYTHON_USER_SCRIPTS=%%i"
if defined PYTHON_USER_SCRIPTS (
    if exist "!PYTHON_USER_SCRIPTS!" set "PATH=!PYTHON_USER_SCRIPTS!;!PATH!"
)
exit /b 0

:ensure_fast_tool
set "TOOL_NAME=%~1"
set "CHOCO_PACKAGE=%~2"
set "WINGET_ID=%~3"
where !TOOL_NAME! >nul 2>nul
if not errorlevel 1 exit /b 0

if not "!GAME_WINDOWS_INSTALL_FAST_TOOLS!"=="1" (
    echo !TOOL_NAME! was not found; continuing without installing it.
    exit /b 1
)

echo !TOOL_NAME! was not found; attempting to install it for the Windows fast build.
where choco >nul 2>nul
if not errorlevel 1 (
    choco install -y !CHOCO_PACKAGE! --no-progress
    call :add_python_user_scripts_to_path
    where !TOOL_NAME! >nul 2>nul
    if not errorlevel 1 exit /b 0
)

where winget >nul 2>nul
if not errorlevel 1 (
    winget install --id !WINGET_ID! --exact --silent --accept-package-agreements --accept-source-agreements
    call :add_python_user_scripts_to_path
    where !TOOL_NAME! >nul 2>nul
    if not errorlevel 1 exit /b 0
)

if /I "!TOOL_NAME!"=="ninja" (
    python -m pip install --user ninja
    call :add_python_user_scripts_to_path
    where ninja >nul 2>nul
    if not errorlevel 1 exit /b 0
)

echo Could not install !TOOL_NAME!. Install it manually, or set GAME_WINDOWS_INSTALL_FAST_TOOLS=0 to fall back when possible.
exit /b 1

:ensure_msvc_env
where cl >nul 2>nul
if not errorlevel 1 exit /b 0

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "!VSWHERE!" (
    for /f "usebackq delims=" %%i in (`"!VSWHERE!" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul`) do (
        if not defined VS_INSTALL_DIR set "VS_INSTALL_DIR=%%i"
    )
)
if defined VS_INSTALL_DIR (
    if exist "!VS_INSTALL_DIR!\Common7\Tools\VsDevCmd.bat" (
        call "!VS_INSTALL_DIR!\Common7\Tools\VsDevCmd.bat" -arch=amd64 -host_arch=amd64 >nul
    )
)

where cl >nul 2>nul
if errorlevel 1 (
    echo MSVC cl.exe was not found. Run configure.bat from a Visual Studio Developer Command Prompt or install VS C++ tools.
    exit /b 1
)
exit /b 0

:configure
set "BUILD_DIR=%~1"
set "CMAKE_GENERATOR_PLATFORM_ARG="
set "CMAKE_BUILD_TYPE_ARG="
set "CMAKE_COMPILER_LAUNCHER_ARGS="
set "GAME_FAST_CMAKE_ARGS="

if defined CMAKE_GENERATOR_PLATFORM set "CMAKE_GENERATOR_PLATFORM_ARG=-A !CMAKE_GENERATOR_PLATFORM!"
if /I "!CMAKE_GENERATOR!"=="Ninja" set "CMAKE_BUILD_TYPE_ARG=-DCMAKE_BUILD_TYPE=Release"
if defined CMAKE_C_COMPILER_LAUNCHER set "CMAKE_COMPILER_LAUNCHER_ARGS=-DCMAKE_C_COMPILER_LAUNCHER=!CMAKE_C_COMPILER_LAUNCHER! -DCMAKE_CXX_COMPILER_LAUNCHER=!CMAKE_CXX_COMPILER_LAUNCHER!"
if "!GAME_WINDOWS_FAST_BUILD!"=="1" set "GAME_FAST_CMAKE_ARGS=-DGAME_ENABLE_UNITY_BUILD=ON -DGAME_ENABLE_PCH=ON -DGAME_UNITY_BATCH_SIZE=16"

if exist "!BUILD_DIR!\CMakeCache.txt" (
    findstr /C:"CMAKE_GENERATOR:INTERNAL=!CMAKE_GENERATOR!" "!BUILD_DIR!\CMakeCache.txt" >nul 2>nul
    if errorlevel 1 (
        echo Recreating !BUILD_DIR! because it was configured with a different CMake generator.
        del /q "!BUILD_DIR!\CMakeCache.txt" 2>nul
        rmdir /s /q "!BUILD_DIR!\CMakeFiles" 2>nul
    ) else (
        if defined CMAKE_GENERATOR_PLATFORM (
            findstr /C:"CMAKE_GENERATOR_PLATFORM:INTERNAL=!CMAKE_GENERATOR_PLATFORM!" "!BUILD_DIR!\CMakeCache.txt" >nul 2>nul
            if errorlevel 1 (
                echo Recreating !BUILD_DIR! because it was configured for a different platform.
                del /q "!BUILD_DIR!\CMakeCache.txt" 2>nul
                rmdir /s /q "!BUILD_DIR!\CMakeFiles" 2>nul
            )
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
    if exist "!BUILD_DIR!\CMakeCache.txt" (
        findstr /C:"VCPKG_TARGET_TRIPLET:STRING=!VCPKG_TARGET_TRIPLET!" "!BUILD_DIR!\CMakeCache.txt" >nul 2>nul
        if errorlevel 1 (
            echo Recreating !BUILD_DIR! because it was configured with a different vcpkg target triplet.
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
    !CMAKE_GENERATOR_PLATFORM_ARG! ^
    !CMAKE_BUILD_TYPE_ARG! ^
    !CMAKE_COMPILER_LAUNCHER_ARGS! ^
    !GAME_FAST_CMAKE_ARGS! ^
    -DCMAKE_TOOLCHAIN_FILE="!VCPKG_TOOLCHAIN_FILE!" ^
    -DVCPKG_INSTALLED_DIR="!VCPKG_INSTALLED_DIR!" ^
    -DVCPKG_TARGET_TRIPLET="!VCPKG_TARGET_TRIPLET!" ^
    -DVCPKG_OVERLAY_TRIPLETS="!VCPKG_OVERLAY_TRIPLETS!" ^
    -DVCPKG_MANIFEST_MODE="!VCPKG_MANIFEST_MODE!" ^
    -Dpybind11_DIR="!PYBIND11_DIR!" ^
    -DPython3_EXECUTABLE="!PYTHON_EXECUTABLE!"
exit /b %ERRORLEVEL%
