import os
import subprocess
import sys
import traceback
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QApplication, QToolBar,
                             QToolButton, QMenuBar, QMenu, QWidget, QVBoxLayout,
                             QLabel)
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt, QSize, QEvent

from ui.osc_tab import OscTab
from ui.psu_tab import PsuTab
from ui.style import APP_QSS


def icon_path() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", "app_icon.ico")


class MiniWindow(QMainWindow):
    """Küçük, her zaman üstte duran ikon penceresi (Kronometre mini modu gibi)."""

    def __init__(self, main_win):
        super().__init__(main_win)
        self.main_win = main_win
        self.setWindowTitle("ECK Mini")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._icon_size = 56

        self._drag_pos = None
        self._moved = False

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        btn = QToolButton()
        btn.setIcon(QIcon(icon_path()))
        btn.setIconSize(QSize(44, 44))
        btn.setAutoRaise(True)
        btn.setToolTip("Büyütmek için tıkla, sürükleyerek taşı")
        btn.installEventFilter(self)
        lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self.rows_lay = QVBoxLayout()
        self.rows_lay.setContentsMargins(6, 0, 6, 4)
        self.rows_lay.setSpacing(2)
        lay.addLayout(self.rows_lay)
        self._lbl_rows = []
        self.setCentralWidget(central)
        self.resize(self._icon_size, self._icon_size)

    def update_psu(self, rows):
        """[(ch, on, volt, amps), ...] — acik kanal varsa degerleri gosterir."""
        active = [r for r in rows if r[1]]
        for lbl in self._lbl_rows:
            lbl.hide()
        if not active:
            self.setFixedSize(self._icon_size, self._icon_size)
            return
        need = len(active)
        for i in range(need):
            if i >= len(self._lbl_rows):
                lbl = QLabel()
                lbl.setStyleSheet(
                    "font-family: 'Consolas'; font-size: 9pt; font-weight: bold;"
                    " color: #45B881; background-color: #10141A;"
                    " border: 1px solid #4A5360; border-radius: 3px; padding: 1px 4px;")
                self._lbl_rows.append(lbl)
                self.rows_lay.addWidget(lbl)
            ch, _on, volt, amps = active[i]
            self._lbl_rows[i].setText(f"CH{ch} ● {volt} V  {amps} A")
            self._lbl_rows[i].show()
        w = max(self._icon_size, 190)
        self.setFixedSize(w, self._icon_size + 20 * need)

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
            return True
        if t == QEvent.Type.MouseMove and self._drag_pos is not None and \
                event.buttons() & Qt.MouseButton.LeftButton:
            gp = event.globalPosition().toPoint()
            if (gp - self._drag_pos - self.frameGeometry().topLeft()).manhattanLength() > 4:
                self._moved = True
            self.move(gp - self._drag_pos)
            return True
        if t == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            was_drag = self._moved
            self._drag_pos = None
            self._moved = False
            if not was_drag:
                self.expand()
            return True
        return super().eventFilter(obj, event)

    def expand(self):
        self.hide()
        self.main_win.showNormal()
        self.main_win.raise_()
        self.main_win.activateWindow()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elektronik Cihaz Kontrol - T3DSO2104 / DP932")
        self.setWindowIcon(QIcon(icon_path()))
        self.resize(1280, 760)

        # Tek osiloskop objesi: osiloskop ve canli ekran sekmeleri ayni
        # baglantiyi paylasir (iki ayri VISA oturumu ayni USB'yi acamaz)
        from ui.osc_tab import OscTab
        from ui.psu_tab import PsuTab
        tabs = QTabWidget()
        self.osc_tab = OscTab()
        self.psu_tab = PsuTab()
        tabs.addTab(self.osc_tab, "⚡ Osiloskop")
        tabs.addTab(self.psu_tab, "🔌 Power Supply")
        self.setCentralWidget(tabs)

        self._build_toolbar()

    def _shutdown(self):
        """Cikista tum VISA oturumlarini serbest birak (yoksa cihaz USBTMC kilitlenir)."""
        if getattr(self.osc_tab, "_monitor", None) is not None:
            self.osc_tab._monitor.close()
            self.osc_tab._monitor = None
        for tab in (self.osc_tab, self.psu_tab):
            try:
                tab._stop() if hasattr(tab, "_stop") else None
            except Exception:
                pass
            try:
                if tab.bar.device.is_connected:
                    tab.bar.device.disconnect()
            except Exception:
                pass

    def _build_toolbar(self):
        tb = QToolBar("Araçlar")
        tb.setMovable(False)
        self.addToolBar(tb)

        # Her zaman üstte toggle
        self.act_ontop = QAction("📌 Üstte Tut", self)
        self.act_ontop.setCheckable(True)
        self.act_ontop.setToolTip("Pencereyi diğer uygulamaların üstünde tut")
        self.act_ontop.toggled.connect(self._toggle_ontop)
        tb.addAction(self.act_ontop)

        # Mini mod (küçük ikon)
        self.act_mini = QAction("🖱 Mini Mod", self)
        self.act_mini.setToolTip("Küçük ikona küçült (üstte durur, tıklayınca açılır)")
        self.act_mini.triggered.connect(self.collapse)
        tb.addAction(self.act_mini)

    def _toggle_ontop(self, checked):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()

    def collapse(self):
        # Canli izleme penceresini kapat (referans silinmis olabilir)
        mon = getattr(self.osc_tab, "_monitor", None)
        if mon is not None:
            try:
                mon.close()
            except RuntimeError:
                pass
            self.osc_tab._monitor = None
        if not hasattr(self, "mini") or self.mini is None:
            self.mini = MiniWindow(self)
            self.mini.destroyed.connect(lambda: setattr(self, "mini", None))
            self.psu_tab.state_changed.connect(self.mini.update_psu)
        # Acik kanal degerlerini hemen goster (poll beklemeden)
        self.mini.update_psu(self.psu_tab.last_state())
        self.hide()
        # Önceki konumuna yakın göster
        if not self.mini.isVisible():
            geo = self.geometry()
            self.mini.move(geo.x() + geo.width() // 2 - 28,
                           geo.y() + 40)
        self.mini.show()
        self.mini.raise_()
        self.mini.activateWindow()

    def closeEvent(self, event):
        if getattr(self, "mini", None) is not None:
            self.mini.close()
            self.mini = None
        super().closeEvent(event)


def _install_crash_hook():
    """Slot icinde yakalanmayan hata uygulamayi kapatsin yerine loglansin."""
    def hook(t, v, tb):
        line = "".join(traceback.format_exception(t, v, tb))
        try:
            with open(os.path.join(os.path.expanduser("~"), "Desktop",
                                   "eck_hata.log"), "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now()} ---\n{line}\n")
        except Exception:
            pass
        traceback.print_exception(t, v, tb)
    sys.excepthook = hook


def mevcut_pencereye_gec():
    """Uygulama zaten aciksa penceresini one getirir, True dondurur."""
    import ctypes
    u32 = ctypes.windll.user32
    sonuc = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _cb(hwnd, _lp):
        if u32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith("Elektronik Cihaz Kontrol"):
                sonuc.append(hwnd)
                return False
        return True

    u32.EnumWindows(_cb, 0)
    if sonuc:
        h = sonuc[0]
        if u32.IsIconic(h):
            u32.ShowWindow(h, 9)
        u32.SetForegroundWindow(h)
        return True
    return False


def kisayolu_kur():
    """Ctrl+Alt+E kisayolunu Baslat Menusune kurar (yoksa). Uygulama ile birlikte gelir."""
    lnk = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows",
                       "Start Menu", "Programs", "Elektronik Cihaz Kontrol.lnk")
    if os.path.exists(lnk):
        return
    hedef = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "app_icon.ico")
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
          f"$s.TargetPath='{sys.executable}';"
          f"$s.Arguments='\"{hedef}\"';"
          f"$s.WorkingDirectory='{os.path.dirname(hedef)}';"
          f"$s.IconLocation='{icon}';"
          "$s.HotKey='Ctrl+Alt+E';$s.Save()")
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                     creationflags=subprocess.CREATE_NO_WINDOW)


def run():
    if mevcut_pencereye_gec():
        sys.exit(0)
    app = QApplication(sys.argv)
    _install_crash_hook()
    app.setQuitOnLastWindowClosed(True)
    app.setStyleSheet(APP_QSS)
    win = MainWindow()
    app.aboutToQuit.connect(win._shutdown)
    win.show()
    kisayolu_kur()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
