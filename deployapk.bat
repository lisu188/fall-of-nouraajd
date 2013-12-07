del /s "official.apk"

xcopy /s ".\android\bin\Game-debug.apk" ".\"

ren Game-debug.apk official.apk

rmdir /s /q ".\android"
