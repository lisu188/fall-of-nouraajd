rmdir /s /q ".\official"

mkdir ".\official"
mkdir ".\official\save"

xcopy /s ".\libraries" ".\official"
xcopy /s ".\release\Game.exe" ".\official"

del ..\build.zip
7za a -tzip ..\build.zip ".\official\*"

rmdir /s /q ".\official"
rmdir /s /q ".\release"
rmdir /s /q ".\debug"
rmdir /s /q ".\save"

astyle.exe -n -xe -j --recursive *.cpp *.h *.json

.\git\git.exe add -A
.\git\git.exe commit -m auto
.\git\git.exe clean -fd -x -e *.zip *.apk

mkdir ".\release"
mkdir ".\debug"
mkdir ".\save"

del ..\code.zip
7za a -tzip ..\code.zip ".\*"

