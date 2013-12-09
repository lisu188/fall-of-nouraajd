rmdir /s /q ".\android\assets"

mkdir ".\android\assets\images"

xcopy /s ".\images" ".\android\assets\images"
