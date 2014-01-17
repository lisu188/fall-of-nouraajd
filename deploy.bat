rmdir /s /q ".\official"

mkdir ".\official"
mkdir ".\official\config"
mkdir ".\official\save"

xcopy /s ".\libraries" ".\official"
xcopy /s ".\config" ".\official\config"
xcopy /s ".\release\Game.exe" ".\official"

del official.zip

7za a -tzip official.zip ".\official\*"

rmdir /s /q ".\official"

astyle.exe -n -xe -j --recursive *.cpp *.h *.json --exclude=release/ --exclude=debug/ -Q

.\git\git.exe add -A
.\git\git.exe commit -m auto
.\git\git.exe clean -fd -x -e *.zip *.apk

mkdir ".\release"
mkdir ".\debug"
mkdir ".\save"

