rmdir /s /q ".\official"

mkdir ".\official"
mkdir ".\official\scripts"

xcopy /s ".\libraries" ".\official"
xcopy /s ".\scripts" ".\official\scripts"
xcopy /s ".\release\Game.exe" ".\official"

del ..\build.zip
7za a -tzip ..\build.zip ".\official\*"



