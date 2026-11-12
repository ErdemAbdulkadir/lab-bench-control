@echo off
rem Ctrl+Alt+E kisa yollu uygulama kisayolu olusturur (arka plan sureci YOK).
rem Windows bu kisayolu kendi dinler; basildiginda uygulamayi acar.
rem Uygulama zaten aciksa tek-ornek kilidi sayesinde pencere one gelir.
chcp 65001 >nul
set PYTHONW=%LocalAppData%\Programs\Python\Python313\pythonw.exe
if not exist "%PYTHONW%" set PYTHONW=pythonw.exe

rem Masaustune koy
set LNK=%USERPROFILE%\Desktop\Elektronik Cihaz Kontrol.lnk

powershell -NoProfile -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');" ^
  "$s.TargetPath = '%PYTHONW%';" ^
  "$s.Arguments = '\"%~dp0app\main.py\"';" ^
  "$s.WorkingDirectory = '%~dp0app';" ^
  "$s.IconLocation = '%~dp0app\assets\app_icon.ico';" ^
  "$s.HotKey = 'Ctrl+Alt+E';" ^
  "$s.Save()"
echo Kisayol olusturuldu: %LNK%
pause
