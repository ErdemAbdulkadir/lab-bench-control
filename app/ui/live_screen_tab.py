import time
from pathlib import Path

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QPushButton, QComboBox, QLineEdit,
                             QFileDialog, QSizePolicy, QStackedWidget)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from core.oscilloscope import Oscilloscope
from ui.device_bar import DeviceBar


class ShotWorker(QThread):
    done = pyqtSignal(object)
    fail = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:
            self.fail.emit(str(e))


class LiveScreenTab(QWidget):
    def __init__(self, device=None):
        super().__init__()
        self._worker = None
        self._last_frame = None
        self._live = False
        self._build_ui(device)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def _build_ui(self, device=None):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 6, 10, 10)
        main.setSpacing(8)

        self.bar = DeviceBar("Osiloskop", Oscilloscope, expected_vids=[0xF4EC],
                             device=device)
        self.bar.connected.connect(self._on_connected)
        self.bar.disconnected.connect(self._on_disconnected)
        main.addWidget(self.bar)

        # Kontroller
        gb_c = QGroupBox("Canlı İzleme")
        gh = QHBoxLayout(gb_c)
        gh.setContentsMargins(10, 8, 10, 8)
        self.btn_toggle = QPushButton("▶ Canlı Başlat")
        self.btn_toggle.setObjectName("btn_run")
        self.btn_toggle.setMinimumHeight(38)
        self.btn_toggle.clicked.connect(self._toggle)
        gh.addWidget(self.btn_toggle)

        gh.addWidget(QLabel("Mod:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["🖥 Ekran Görüntüsü (SCDP)",
                                "📈 Dalga Formu (Hızlı ~5-7 fps)"])
        self.cmb_mode.setMinimumHeight(30)
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        gh.addWidget(self.cmb_mode)

        gh.addWidget(QLabel("Yenileme:"))
        self.cmb_interval = QComboBox()
        self.cmb_interval.addItems(["En hızlı", "0.2 sn", "0.5 sn", "1 sn", "2 sn", "5 sn"])
        self.cmb_interval.setCurrentText("En hızlı")
        gh.addWidget(self.cmb_interval)

        self.btn_once = QPushButton("Bir Kez Yakala")
        self.btn_once.setMinimumHeight(38)
        self.btn_once.clicked.connect(self._tick)
        gh.addWidget(self.btn_once)

        self.btn_save = QPushButton("Görüntüyü Kaydet (BMP)")
        self.btn_save.setObjectName("btn_single")
        self.btn_save.setMinimumHeight(38)
        self.btn_save.clicked.connect(self._save)
        gh.addWidget(self.btn_save)
        gh.addStretch(1)
        main.addWidget(gb_c)

        # Görüntü paneli: sayfa 0 = SCDP etiketi, sayfa 1 = dalga formu grafigi
        gb_s = QGroupBox("Osiloskop — Canlı")
        self.stack = QStackedWidget(gb_s)
        vs = QVBoxLayout(gb_s)
        vs.setContentsMargins(10, 8, 10, 8)
        vs.addWidget(self.stack)

        self.screen = QLabel("Bağlanıp 'Canlı Başlat' ile ekranı yansıtın")
        self.screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screen.setMinimumSize(640, 400)
        self.screen.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Expanding)
        self.screen.setStyleSheet(
            "background-color: #10141A; border: 1px solid #4A5360;"
            " border-radius: 5px; color: #B4BECC; font-size: 11pt;")
        self.stack.addWidget(self.screen)

        self.fig = Figure(facecolor="#10141A")
        self.ax = self.fig.add_subplot(111)
        self._style_axes()
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet("background-color: #10141A;")
        self.stack.addWidget(self.canvas)
        self.stack.setCurrentIndex(0)
        main.addWidget(gb_s, 1)

        for b in self.findChildren(QPushButton):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _style_axes(self):
        a = self.ax
        a.set_facecolor("#10141A")
        a.tick_params(colors="#B4BECC", labelsize=8)
        for s in a.spines.values():
            s.set_color("#4A5360")
        a.grid(True, color="#262D37", linewidth=0.6)

    # ------------------------------------------------ helpers
    @property
    def dev(self) -> Oscilloscope:
        return self.bar.device

    @property
    def interval_ms(self) -> int:
        t = self.cmb_interval.currentText()
        if t == "En hızlı":
            return 0  # kare gelir gelmez yeni cekim
        return int(float(t.replace(" sn", "")) * 1000)

    def _waveform_mode(self) -> bool:
        return self.cmb_mode.currentIndex() == 1

    def _on_mode_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)
        if idx == 1:
            self.btn_save.setEnabled(False)
        else:
            self.btn_save.setEnabled(True)

    def _on_connected(self):
        self.screen.setText("Bağlandı — '▶ Canlı Başlat' ile izlemeyi başlat")

    def _on_disconnected(self):
        self._stop()
        self.screen.setText("Bağlantı kesildi")
        self._last_frame = None

    def _toggle(self):
        if self.timer.isActive():
            self._stop()
        else:
            if not self.dev.is_connected:
                self.screen.setText("Bağlantı yok — önce cihaza bağlanın")
                return
            self._live = True
            self.btn_toggle.setText("⏸ Canlı Durdur")
            self.btn_toggle.setObjectName("btn_stop")
            self.cmb_interval.setEnabled(False)
            self.cmb_mode.setEnabled(False)
            self.timer.start(self.interval_ms)
            self._tick()

    def _stop(self):
        self._live = False
        self.timer.stop()
        # Aktif çekim varsa bitmesini bekle; yarim okuma cihazi kilitlar
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
        self.btn_toggle.setText("▶ Canlı Başlat")
        self.btn_toggle.setObjectName("btn_run")
        self.cmb_interval.setEnabled(True)
        self.cmb_mode.setEnabled(True)

    def _tick(self):
        if not self.dev.is_connected:
            self._stop()
            self.screen.setText("Bağlantı yok")
            return
        if self._worker is not None and self._worker.isRunning():
            return  # önceki çekim hala sürüyor, atla
        self.timer.stop()  # kare gelince interval yeniden kurulur
        if self._worker is not None:
            self._worker.deleteLater()
        if self._waveform_mode():
            ch = 1
            fn = lambda: self.dev.get_waveform(ch)
        else:
            fn = self.dev.screenshot
        self._worker = ShotWorker(fn)
        self._worker.done.connect(self._on_frame)
        self._worker.fail.connect(self._on_fail)
        self._worker.start()

    def _schedule_next(self):
        if not (self._live and self.dev.is_connected):
            return
        if self.interval_ms == 0:
            self._tick()  # beklemeden devam
        else:
            self.timer.start(self.interval_ms)

    def _on_frame(self, data):
        if self._waveform_mode():
            self._show_waveform(data)
        else:
            self._show_image(data)
        self._schedule_next()

    def _show_image(self, data: bytes):
        if not data:
            self.screen.setText("Ekran verisi alınamadı (SCDP boş döndü)")
            return
        self._last_frame = data
        pm = QPixmap()
        if not pm.loadFromData(data):
            self.screen.setText("Görüntü çözümlenemedi (BMP formatı bekleniyor)")
            return
        self.screen.setPixmap(pm.scaled(
            self.screen.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.screen.setText("")

    def _show_waveform(self, res):
        if not res:
            self.screen.setText("Dalga formu alınamadı")
            return
        t, v, vdiv, ofst = res
        self.ax.clear()
        self._style_axes()
        self.ax.plot(t * 1e3, v, color="#45B881", linewidth=0.8)
        self.ax.set_xlabel("Zaman (ms)", color="#B4BECC", fontsize=8)
        self.ax.set_ylabel(f"Gerilim (V)  —  {vdiv:g} V/div, ofst {ofst:g} V",
                           color="#B4BECC", fontsize=8)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def _on_fail(self, err: str):
        self.screen.setText(f"Hata: {err}")
        self._schedule_next()

    def _save(self):
        data = self._last_frame
        if not data:
            self.screen.setText("Kaydedilecek görüntü yok — önce yakalayın")
            return
        folder = Path.home() / "Desktop"
        path = folder / time.strftime("live_%Y%m%d_%H%M%S.bmp")
        path, _ = QFileDialog.getSaveFileName(
            self, "Görüntüyü Kaydet", str(path), "BMP (*.bmp)")
        if not path:
            return
        if not path.lower().endswith(".bmp"):
            path += ".bmp"
        Path(path).write_bytes(data)
        self.screen.setText("Kaydedildi: " + path)
