@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE="

if defined PYTHON_EXECUTABLE (
    if exist "%PYTHON_EXECUTABLE%" set "PYTHON_EXE=%PYTHON_EXECUTABLE%"
)

if not defined PYTHON_EXE (
    for %%P in (
        "%LocalAppData%\Programs\Python\Python312\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles(x86)%\Python312-32\python.exe"
    ) do (
        if not defined PYTHON_EXE (
            if exist "%%~P" set "PYTHON_EXE=%%~P"
        )
    )
)

if not defined PYTHON_EXE (
    echo Python 3.12 was not found in a trusted install location.
    echo Set PYTHON_EXECUTABLE to the full path of python.exe and run this script again.
    exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_DIR%play.py" %*
