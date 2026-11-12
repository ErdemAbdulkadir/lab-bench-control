@echo off
rem Ctrl+Alt+E kisayol izleyicisini (app\hotkey_watch.pyw) Windows baslangicina ekler.
rem Gerek yoksa kullanmayin: uygulama ilk acilista Baslat Menusune Ctrl+Alt+E
rem kisayolunu zaten kurar. Bu izleyici, o kisayol calismadiginda yedek yoldur.
rem Kaldirmak icin: Baslangic klasorundeki "ECK Hotkey.lnk" dosyasini silin
rem (Win+R -> shell:startup).
setlocal
set "SCRIPT=%~dp0app\hotkey_watch.pyw"
set "APP=%~dp0app"

set "PYTHONW="
for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do if not defined PYTHONW set "PYTHONW=%%P"
if not defined PYTHONW (
  echo HATA: pythonw.exe bulunamadi. Python'u kurup PATH'e ekleyin.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'ECK Hotkey.lnk';" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath = $env:PYTHONW;" ^
  "$s.Arguments = '\"' + $env:SCRIPT + '\"';" ^
  "$s.WorkingDirectory = $env:APP;" ^
  "$s.Save();" ^
  "Write-Host ('Kurulum tamam: ' + $lnk)"
pause
