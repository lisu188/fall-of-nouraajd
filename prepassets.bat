rmdir /s /q ".\android\assets"

mkdir ".\android\assets\images"
mkdir ".\android\assets\config"

xcopy /s ".\images" ".\android\assets\images"
xcopy /s ".\config" ".\android\assets\config"
