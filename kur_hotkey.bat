@echo off
rem Ctrl+E kisayol izleyicisini Windows baslangicina ekler / kaldirir.
set SCRIPT=%~dp0app\hotkey_watch.pyw
set LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ECK Hotkey.lnk
set PYTHONW=%LocalAppData%\Programs\Python\Python313\pythonw.exe
if not exist "%PYTHONW%" set PYTHONW=pythonw.exe

powershell -NoProfile -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');" ^
  "$s.TargetPath = '%PYTHONW%';" ^
  "$s.Arguments = '\"%SCRIPT%\"';" ^
  "$s.WorkingDirectory = '%~dp0app';" ^
  "$s.Save()"
echo Kurulum tamam: %LNK%
pause
