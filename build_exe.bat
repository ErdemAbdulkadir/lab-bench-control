@echo off
rem PyInstaller ile Windows uygulamasi olusturur.
rem Gerekli: pip install pyinstaller
cd /d "%~dp0"
python -m PyInstaller --noconfirm --windowed --name "ElektronikCihazKontrol" ^
  --icon "app\assets\app_icon.ico" ^
  --add-data "app\assets;assets" ^
  --paths app ^
  app\main.py
if errorlevel 1 (
  echo.
  echo HATA: derleme basarisiz. PyInstaller kurulu mu?  pip install pyinstaller
  pause
  exit /b 1
)
echo.
echo Tamamlandi: dist\ElektronikCihazKontrol\ElektronikCihazKontrol.exe
echo (dist\ElektronikCihazKontrol klasorunun tamami birlikte tasinmalidir)
pause
