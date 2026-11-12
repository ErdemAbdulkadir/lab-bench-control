# -*- coding: utf-8 -*-
"""
Ctrl+E global kisayol izleyicisi.
Arka planda calisir (penceresi yok), Ctrl+E basinca:
  - Uygulama kapaliysa -> baslat.pyw ile acar
  - Uygulama aciksa    -> penceresini one getirir

Windows baslangicina eklemek icin: kur_hotkey.bat dosyasini calistir.
Kisayolu degistirmek icin asagidaki MOD / TUS degerlerini duzenle.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PENCERE_ADI = "Elektronik Cihaz Kontrol"   # ana pencere basliginin basi
MOD = 0x0006          # MOD_CONTROL | MOD_ALT  (0x0001=ALT, 0x0002=CTRL, 0x0004=SHIFT, 0x0008=WIN)
TUS = 0x45            # 'E'
HOTKEY_ID = 1

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


EnumWindows = ctypes.windll.user32.EnumWindows
GetWindowTextW = ctypes.windll.user32.GetWindowTextW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible


def pencere_bul():
    sonuc = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def _cb(hwnd, _lp):
        if IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith(PENCERE_ADI):
                sonuc.append(hwnd)
                return False
        return True

    EnumWindows(_cb, 0)
    return sonuc[0] if sonuc else None


def one_getir(hwnd):
    SW_RESTORE = 9
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)


def uygulama_baslat():
    subprocess.Popen(
        [sys.executable.replace("python.exe", "pythonw.exe"),
         os.path.join(APP_DIR, "baslat.pyw")],
        cwd=APP_DIR,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def log(mesaj):
    try:
        with open(os.path.join(APP_DIR, "hotkey.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%H:%M:%S} {mesaj}\n")
    except OSError:
        pass


def main():
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD, TUS):
        log(f"HOTKEY kaydi basarisiz! hata={kernel32.GetLastError()}")
        return
    log("Izleyici basladi, Ctrl+Alt+E dinleniyor")
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            hwnd = pencere_bul()
            log(f"hotkey! hwnd={hwnd}")
            if hwnd:
                one_getir(hwnd)
            else:
                uygulama_baslat()
    user32.UnregisterHotKey(None, HOTKEY_ID)


if __name__ == "__main__":
    main()
