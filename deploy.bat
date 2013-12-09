rmdir /s /q ".\official"

mkdir ".\official"
mkdir ".\official\images"
mkdir ".\official\config"

xcopy /s ".\libraries" ".\official"
xcopy /s ".\images" ".\official\images"
xcopy /s ".\config" ".\official\config"
xcopy /s ".\release\Game.exe" ".\official"

del official.zip

7za a -tzip official.zip ".\official\*"

rmdir /s /q ".\official"

astyle.exe -n --recursive *.cpp *.h

.\git\git.exe add -A
.\git\git.exe commit -m auto
.\git\git.exe clean -fd -x -e *.zip *.apk

mkdir ".\release"
mkdir ".\debug"

