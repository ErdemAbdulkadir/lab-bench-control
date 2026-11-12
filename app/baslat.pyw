# Konsol açılmadan GUI'yi başlatır (pythonw ile çalışır)
import os
import sys
import subprocess

APP_DIR = os.path.dirname(os.path.abspath(__file__))
subprocess.Popen(
    [sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(APP_DIR, "main.py")],
    cwd=APP_DIR,
    creationflags=subprocess.CREATE_NO_WINDOW,
)
