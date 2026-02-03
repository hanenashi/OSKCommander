@echo off
echo ========================================================
echo  BUILDING OBERSTURMKLIPPCOMMANDER v6.5
echo ========================================================

:: 1. Cleanup previous builds (Quietly)
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

:: 2. Run PyInstaller
pyinstaller ^
 --noconsole ^
 --onefile ^
 --name "OberSturmKlippCommander_v6.5" ^
 --add-data "obersturmkiippfuhrer.png;." ^
 --add-data "adb.exe;." ^
 --add-data "AdbWinApi.dll;." ^
 --add-data "AdbWinUsbApi.dll;." ^
 --icon "obersturmkiippfuhrer.png" ^
 main.py

echo.
echo ========================================================
echo  BUILD COMPLETE!
echo ========================================================
echo.
echo You can find the executable in the 'dist' folder.
echo Copy 'dist\OberSturmKlippCommander_v6.5.exe' to your friend.
pause