rmdir /s /q ".\official"

mkdir ".\official"
mkdir ".\official\save"

xcopy /s ".\libraries" ".\official"
xcopy /s ".\release\Game.exe" ".\official"

del official.zip

7za a -tzip official.zip ".\official\*"

rmdir /s /q ".\official"

.\git\git.exe add -A
.\git\git.exe commit -m auto
.\git\git.exe clean -fd -x -e *.zip *.apk

astyle.exe -n -xe -j --recursive *.cpp *.h *.json

mkdir ".\release"
mkdir ".\debug"
mkdir ".\save"

