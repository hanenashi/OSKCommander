@echo off
echo ========================================================
echo  BUILDING OBERSTURMKLIPPCOMMANDER v6.3
echo ========================================================

:: 1. Cleanup previous builds
rmdir /s /q build
rmdir /s /q dist
del *.spec

:: 2. Run PyInstaller
:: --noconsole: Hide the black CMD window
:: --onefile: Bundle everything into one .exe
:: --add-data: Include the PNG and ADB files inside the exe
:: --name: The output filename

pyinstaller ^
 --noconsole ^
 --onefile ^
 --name "OberSturmKlippCommander_v6.3" ^
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
echo Copy 'dist\OberSturmKlippCommander_v6.3.exe' to your friend.
echo He does NOT need Python, ADB, or anything else.
pause