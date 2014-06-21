rmdir /s /q ".\official"

mkdir ".\official"
mkdir ".\official\scripts"
mkdir ".\official\config"

xcopy /s ".\libraries" ".\official"
xcopy /s ".\scripts" ".\official\scripts"
xcopy /s ".\config" ".\official\config"
xcopy /s ".\release\Game.exe" ".\official"

del ..\build.zip
7za a -tzip ..\build.zip ".\official\*"



