@echo off
cd /d "%~dp0"
pyinstaller --noconfirm --windowed --name "ElektronikCihazKontrol" ^
  --icon "app\assets\app_icon.ico" ^
  --add-data "app\assets;assets" ^
  app\main.py
echo.
echo Tamamlandi: dist\ElektronikCihazKontrol.exe
pause
