@echo off
rem Masaustune "Elektronik Cihaz Kontrol" kisayolu olusturur (Ctrl+Alt+E ile acilir).
rem Arka planda surec calismaz; kisayol tusunu Windows dinler.
rem Uygulama zaten aciksa yeni kopya acilmaz, mevcut pencere one gelir.
setlocal
set "APP=%~dp0app"

rem pythonw.exe'yi PATH'ten bul (konsol penceresi acmadan calistirir)
set "PYTHONW="
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do if not defined PYTHONW set "PYTHONW=%%P"
if not defined PYTHONW (
  echo HATA: pythonw.exe bulunamadi. Python'u kurup PATH'e ekleyin.
  pause
  exit /b 1
)

rem Gerekli paketler kurulu mu? (pythonw hata gostermez, eksikse kisayol sessizce kapanir)
for %%D in ("%PYTHONW%") do set "PYEXE=%%~dpDpython.exe"
"%PYEXE%" -c "import PyQt6, pyvisa, numpy, matplotlib" 2>nul
if errorlevel 1 (
  echo Gerekli Python paketleri eksik, kuruluyor...
  "%PYEXE%" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 (
    echo HATA: paketler kurulamadi.
    pause
    exit /b 1
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Elektronik Cihaz Kontrol.lnk';" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath = $env:PYTHONW;" ^
  "$s.Arguments = '\"' + (Join-Path $env:APP 'main.py') + '\"';" ^
  "$s.WorkingDirectory = $env:APP;" ^
  "$s.IconLocation = (Join-Path $env:APP 'assets\app_icon.ico');" ^
  "$s.HotKey = 'Ctrl+Alt+E';" ^
  "$s.Save();" ^
  "Write-Host ('Kisayol olusturuldu: ' + $lnk)"
pause
