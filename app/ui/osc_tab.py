import time
from pathlib import Path

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QGridLayout, QComboBox, QDoubleSpinBox, QLabel,
                             QPushButton, QLineEdit, QCheckBox, QFileDialog,
                             QMessageBox, QPlainTextEdit, QSplitter,
                             QSizePolicy, QFrame)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSettings

from core.oscilloscope import Oscilloscope, TIME_DIVS, VOLT_DIVS, MEASURE_ITEMS
from ui.device_bar import DeviceBar
from ui.cursor_monitor import CursorMonitor

SLOPES = {"Yükselen kenar": "POS", "Düşen kenar": "NEG"}
COUPLINGS = ["D1M", "A1M", "GND"]
CHANNELS = [1, 2, 3, 4]

LOG_OK = "#45B881"
LOG_WARN = "#E7B65C"
LOG_ERR = "#E56B70"
LOG_CMD = "#69A9F5"


_SCALES = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""),
           (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")]


def _fmt(v: float) -> str:
    if v != v:  # NaN
        return "—"
    a = abs(v)
    if a == 0:
        return "0"
    for scale, suf in _SCALES:
        if a >= scale:
            return f"{v / scale:.4g} {suf}".strip()
    return f"{v:.4g}"


class Worker(QThread):
    """GUI'yi kilitlememek için cihaz sorgularını arka planda çalıştırır."""
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


class ValueBox(QFrame):
    """Ölçüm değeri kutusu: etiket + birimli sayısal değer."""

    def __init__(self, title: str, unit: str):
        super().__init__()
        self.unit = unit
        self.setStyleSheet(
            "QFrame { background-color: #292F38; border: 1px solid #4A5360;"
            " border-radius: 5px; }"
            "QLabel { border: none; background: transparent; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(0)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(
            "color: #B4BECC; font-size: 9pt; letter-spacing: 0.5px; font-weight: 600;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.lbl_title)
        h = QHBoxLayout()
        h.setSpacing(3)
        self.lbl_value = QLabel("—")
        self.lbl_value.setStyleSheet(
            "font-family: 'Consolas'; font-size: 18pt; font-weight: bold; color: #E5EAF1;")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self.lbl_value, 1)
        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("color: #B4BECC; font-size: 10pt;")
        lbl_unit.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(lbl_unit)
        lay.addLayout(h)

    def set_value(self, v: float):
        self.lbl_value.setText(_fmt(v))


class OscTab(QWidget):
    def __init__(self, device=None):
        super().__init__()
        self._workers = []
        self._queue = []
        self._busy = False
        self._settings = QSettings("ECK", "ECK")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Cursor otomatik okuma timer'i
        self.cur_timer = QTimer(self)
        self.cur_timer.timeout.connect(self.read_cursors)

        # Cursor nudge birlestirme + hizlanma
        self._nudge_pending = 0
        self._nudge_cursor_name = None
        self._nudge_timer = QTimer(self)
        self._nudge_timer.setSingleShot(True)
        self._nudge_timer.setInterval(90)
        self._nudge_timer.timeout.connect(self._flush_nudge)
        self._last_press = 0.0
        self._mult_idx = 0
        self._MULT_LADDER = [1, 2, 5, 10, 20]

        self._build_ui(device)

        # Canlı ölçüm timer'ı
        self.measure_timer = QTimer(self)
        self.measure_timer.timeout.connect(self.read_measurements)

    # ------------------------------------------------ UI
    def _build_ui(self, device=None):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 6, 10, 10)
        main.setSpacing(8)

        self.bar = DeviceBar("Osiloskop", Oscilloscope, expected_vids=[0xF4EC],
                             device=device)
        self.bar.connected.connect(self._on_connected)
        btn_test = self.bar.add_button("Bağlantı Testi (IDN)")
        btn_test.clicked.connect(self._test_conn)
        main.addWidget(self.bar)

        # ---- Üst: ayar panelleri ----
        row = QHBoxLayout()
        row.setSpacing(8)

        # Timebase
        gb_h = QGroupBox("Timebase")
        gh = QGridLayout(gb_h)
        gh.setContentsMargins(10, 8, 10, 8)
        gh.setVerticalSpacing(8)
        gh.addWidget(QLabel("Zaman / div"), 0, 0)
        self.cmb_tdiv = QComboBox()
        self.cmb_tdiv.addItems(TIME_DIVS)
        self.cmb_tdiv.setCurrentText("1ms")
        gh.addWidget(self.cmb_tdiv, 0, 1)
        btn_tdiv = QPushButton("Uygula")
        btn_tdiv.clicked.connect(self._apply_tdiv)
        gh.addWidget(btn_tdiv, 0, 2)
        gh.setColumnStretch(1, 1)
        gh.setRowStretch(gh.rowCount(), 1)
        row.addWidget(gb_h, 1)

        # Dikey / kanal
        gb_v = QGroupBox("Kanal Ayarları")
        gv = QGridLayout(gb_v)
        gv.setContentsMargins(10, 8, 10, 8)
        gv.setVerticalSpacing(8)
        gv.addWidget(QLabel("Kanal"), 0, 0)
        self.cmb_ch = QComboBox()
        self.cmb_ch.addItems([str(c) for c in CHANNELS])
        gv.addWidget(self.cmb_ch, 0, 1)
        gv.addWidget(QLabel("V / div"), 1, 0)
        self.cmb_vdiv = QComboBox()
        self.cmb_vdiv.addItems(VOLT_DIVS)
        self.cmb_vdiv.setCurrentText("1V")
        gv.addWidget(self.cmb_vdiv, 1, 1)
        btn_vdiv = QPushButton("Uygula")
        btn_vdiv.clicked.connect(self._apply_vdiv)
        gv.addWidget(btn_vdiv, 1, 2)
        gv.addWidget(QLabel("Sinyal konumu (Offset)"), 2, 0)
        self.spin_offset = QDoubleSpinBox()
        self.spin_offset.setRange(-200.0, 200.0)
        self.spin_offset.setDecimals(2)
        self.spin_offset.setSingleStep(0.1)
        gv.addWidget(self.spin_offset, 2, 1)
        btn_off = QPushButton("Uygula")
        btn_off.clicked.connect(self._apply_offset)
        gv.addWidget(btn_off, 2, 2)
        gv.addWidget(QLabel("Coupling"), 3, 0)
        self.cmb_coup = QComboBox()
        self.cmb_coup.addItems(COUPLINGS)
        gv.addWidget(self.cmb_coup, 3, 1)
        btn_coup = QPushButton("Uygula")
        btn_coup.clicked.connect(self._apply_coupling)
        gv.addWidget(btn_coup, 3, 2)
        gv.addWidget(QLabel("Kanal Durumu"), 4, 0)
        hb_ch = QHBoxLayout()
        btn_ch_on = QPushButton("Aç")
        btn_ch_off = QPushButton("Kapat")
        btn_ch_on.clicked.connect(lambda: self._cmd(
            f"C{self.ch}:TRA ON", lambda: self.dev.set_channel(self.ch, True)))
        btn_ch_off.clicked.connect(lambda: self._cmd(
            f"C{self.ch}:TRA OFF", lambda: self.dev.set_channel(self.ch, False)))
        hb_ch.addWidget(btn_ch_on)
        hb_ch.addWidget(btn_ch_off)
        gv.addLayout(hb_ch, 4, 1)
        gv.setColumnStretch(1, 1)
        gv.setRowStretch(gv.rowCount(), 1)
        row.addWidget(gb_v, 2)

        # Trigger
        gb_t = QGroupBox("Trigger")
        gt = QGridLayout(gb_t)
        gt.setContentsMargins(10, 8, 10, 8)
        gt.setVerticalSpacing(8)
        gt.addWidget(QLabel("Seviye (V)"), 0, 0)
        self.spin_trlv = QDoubleSpinBox()
        self.spin_trlv.setRange(-200.0, 200.0)
        self.spin_trlv.setSingleStep(0.1)
        self.spin_trlv.setValue(1.0)
        gt.addWidget(self.spin_trlv, 0, 1)
        btn_trlv = QPushButton("Uygula")
        btn_trlv.clicked.connect(self._apply_trigger)
        gt.addWidget(btn_trlv, 0, 2)
        gt.addWidget(QLabel("Kenar"), 1, 0)
        self.cmb_slope = QComboBox()
        self.cmb_slope.addItems(SLOPES.keys())
        gt.addWidget(self.cmb_slope, 1, 1)
        btn_slope = QPushButton("Uygula")
        btn_slope.clicked.connect(self._apply_trigger)
        gt.addWidget(btn_slope, 1, 2)
        # Trigger modu butonlari (SINGLE/ARM cikis kontroluyle ayni islev)
        htr = QHBoxLayout()
        self.btn_single = QPushButton("SINGLE")
        self.btn_arm = QPushButton("ARM")
        for b in (self.btn_single, self.btn_arm):
            b.setMinimumHeight(38)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_single.setObjectName("btn_single")
        self.btn_arm.setObjectName("btn_arm")
        self.btn_single.clicked.connect(lambda: self._cmd("TRMD SINGLE", lambda: self.dev.set_trigger_mode("SINGLE")))
        self.btn_arm.clicked.connect(lambda: self._cmd("TRMD NORM", lambda: self.dev.set_trigger_mode("NORM")))
        htr.addWidget(self.btn_single)
        htr.addWidget(self.btn_arm)
        gt.addLayout(htr, 2, 0, 1, 3)
        gt.setColumnStretch(1, 1)
        gt.setRowStretch(gt.rowCount(), 1)
        row.addWidget(gb_t, 2)

        # Cursor
        gb_c = QGroupBox("Cursorlar")
        gc = QGridLayout(gb_c)
        gc.setContentsMargins(10, 8, 10, 8)
        gc.setVerticalSpacing(8)
        gc.addWidget(QLabel("Cursor"), 1, 0)
        self.cmb_cursor = QComboBox()
        self.cmb_cursor.addItems(["X1", "X2", "Y1", "Y2"])
        self.cmb_cursor.currentTextChanged.connect(self._on_cursor_changed)
        gc.addWidget(self.cmb_cursor, 1, 1)
        self.btn_cur_up = QPushButton("▲")
        self.btn_cur_down = QPushButton("▼")
        for b in (self.btn_cur_up, self.btn_cur_down):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setAutoRepeat(True)
            b.setAutoRepeatDelay(250)
            b.setAutoRepeatInterval(80)
        self.btn_cur_up.clicked.connect(lambda: self._nudge_cursor(-1))
        self.btn_cur_down.clicked.connect(lambda: self._nudge_cursor(+1))
        for b in (self.btn_cur_up, self.btn_cur_down):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        hb_cur = QHBoxLayout()
        hb_cur.setSpacing(8)
        hb_cur.addWidget(self.btn_cur_up)
        hb_cur.addWidget(self.btn_cur_down)
        gc.addLayout(hb_cur, 3, 0, 1, 2)
        self.btn_cread = QPushButton("Oku")
        self.btn_cread.clicked.connect(self.read_cursors)
        gc.addWidget(self.btn_cread, 4, 0)
        self.chk_cur_auto = QCheckBox("Otomatik (1 sn)")
        self.chk_cur_auto.toggled.connect(self._toggle_cur_auto)
        gc.addWidget(self.chk_cur_auto, 4, 1)
        self.btn_monitor = QPushButton("🔍 Canlı İzle")
        self.btn_monitor.setObjectName("btn_single")
        self.btn_monitor.clicked.connect(self._open_monitor)
        gc.addWidget(self.btn_monitor, 6, 0, 1, 2)
        self.lbl_cstep = QLabel("Adım: otomatik (0.1 div)")
        self.lbl_cstep.setStyleSheet("color: #B4BECC; font-size: 8pt;")
        gc.addWidget(self.lbl_cstep, 5, 0, 1, 2)
        gc.setColumnStretch(1, 1)
        gc.setRowStretch(6, 1)
        row.addWidget(gb_c, 2)

        main.addLayout(row, 3)

        # Cursor değerleri
        crow = QHBoxLayout()
        self.box_x1 = ValueBox("CURSOR X1", "s")
        self.box_x2 = ValueBox("CURSOR X2", "s")
        self.box_dt = ValueBox("Δt", "s")
        self.box_y1 = ValueBox("CURSOR Y1", "V")
        self.box_y2 = ValueBox("CURSOR Y2", "V")
        self.box_dv = ValueBox("ΔV", "V")
        for b in (self.box_x1, self.box_x2, self.box_dt, self.box_y1,
                  self.box_y2, self.box_dv):
            b.setMinimumWidth(150)
            crow.addWidget(b, 1)
        main.addLayout(crow, 0)

        # ---- Orta: çalıştırma + ölçüm ----
        mid = QHBoxLayout()
        mid.setSpacing(8)

        gb_r = QGroupBox("Çalıştırma")
        gr = QVBoxLayout(gb_r)
        gr.setContentsMargins(10, 8, 10, 8)
        gr.setSpacing(8)
        self.btn_run = QPushButton("RUN")
        self.btn_stop = QPushButton("STOP")
        self.btn_default = QPushButton("DEFAULT")
        for b in (self.btn_run, self.btn_stop):
            b.setMinimumHeight(38)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_run.setObjectName("btn_run")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_default.setObjectName("btn_stop")
        self.btn_default.setMinimumHeight(38)
        self.btn_default.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_run.clicked.connect(lambda: self._cmd("TRMD AUTO", lambda: self.dev.set_trigger_mode("AUTO")))
        self.btn_stop.clicked.connect(lambda: self._cmd("TRMD STOP", lambda: self.dev.set_trigger_mode("STOP")))
        self.btn_default.clicked.connect(self._apply_default)
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(self.btn_run, 0, 0)
        grid.addWidget(self.btn_stop, 0, 1)
        grid.addWidget(self.btn_default, 1, 0, 1, 2)
        grid.setRowStretch(grid.rowCount(), 1)
        gr.addLayout(grid)
        mid.addWidget(gb_r, 2)

        gb_m = QGroupBox("Ölçümler")
        gm = QVBoxLayout(gb_m)
        gm.setContentsMargins(10, 8, 10, 8)
        gm.setSpacing(8)
        self.box_freq = ValueBox("FREQUENCY", "Hz")
        self.box_per = ValueBox("PERIOD", "s")
        self.box_vpp = ValueBox("VPP", "V")
        hval = QHBoxLayout()
        hval.setSpacing(8)
        hval.addWidget(self.box_freq)
        hval.addWidget(self.box_per)
        hval.addWidget(self.box_vpp)
        gm.addLayout(hval)
        hctl = QHBoxLayout()
        self.chk_live = QCheckBox("Sürekli Ölçüm (500 ms)")
        self.chk_live.toggled.connect(self._toggle_live)
        hctl.addWidget(self.chk_live)
        hctl.addStretch(1)
        btn_meas = QPushButton("Bir Kez Oku")
        btn_meas.clicked.connect(self.read_measurements)
        hctl.addWidget(btn_meas)
        gm.addLayout(hctl)
        gm.addStretch(1)
        mid.addWidget(gb_m, 4)

        main.addLayout(mid, 2)

        # Butonlar odaak almasin: tiklandiktan sonra yon tuslari
        # widget'lar arasi gezmek yerine cursor hareketine gitsin
        for b in self.findChildren(QPushButton):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for c in self.findChildren(QComboBox):
            c.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # ---- Alt: ekran görüntüsü + log (splitter) ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        gb_s = QGroupBox("Ekran Görüntüsü")
        vs = QVBoxLayout(gb_s)
        vs.setContentsMargins(10, 8, 10, 8)
        vs.setSpacing(8)
        self.txt_folder = QLineEdit(self._settings.value(
            "screenshot/folder", str(Path.home() / "Desktop")))
        self.txt_folder.setPlaceholderText("Kayıt klasörü")
        self.txt_folder.editingFinished.connect(self._save_folder)
        vs.addWidget(self.txt_folder)
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Dosya adı (boş: otomatik osc_YYYYMMDD_HHMMSS)")
        vs.addWidget(self.txt_name)
        hb = QHBoxLayout()
        btn_browse = QPushButton("Klasör Seç")
        btn_browse.clicked.connect(self._browse)
        hb.addWidget(btn_browse)
        hb.addStretch(1)
        btn_shot = QPushButton("Görüntü Kaydet (BMP)")
        btn_shot.setObjectName("btn_single")
        btn_shot.clicked.connect(self.screenshot)
        hb.addWidget(btn_shot)
        vs.addLayout(hb)
        vs.addStretch(1)
        splitter.addWidget(gb_s)

        gb_log = QGroupBox("Komut Logu")
        vl = QVBoxLayout(gb_log)
        vl.setContentsMargins(10, 8, 10, 8)
        hlog = QHBoxLayout()
        self._btn_clear_log = QPushButton("Temizle")
        hlog.addWidget(self._btn_clear_log)
        hlog.addStretch(1)
        vl.addLayout(hlog)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self._btn_clear_log.clicked.connect(self.log.clear)
        vl.addWidget(self.log)
        splitter.addWidget(gb_log)

        splitter.setSizes([400, 760])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        main.addWidget(splitter, 3)

    # ------------------------------------------------ helpers
    @property
    def dev(self) -> Oscilloscope:
        return self.bar.device

    @property
    def ch(self) -> int:
        return int(self.cmb_ch.currentText())

    def _log_cmd(self, text: str):
        self.log.appendHtml(f'<span style="color:{LOG_CMD};">› {text}</span>')

    def _log_ok(self, text: str):
        self.log.appendHtml(f'<span style="color:{LOG_OK};">✓ {text}</span>')

    def _log_err(self, text: str):
        self.log.appendHtml(f'<span style="color:{LOG_ERR};">✗ {text}</span>')

    def _log_warn(self, text: str):
        self.log.appendHtml(f'<span style="color:{LOG_WARN};">! {text}</span>')

    def _cmd(self, cmd: str, fn):
        if not self.bar.device.is_connected:
            self._log_warn("Bağlantı yok, komut gönderilemedi")
            return
        self._log_cmd(cmd)
        self._run_bg(fn)

    def _apply_tdiv(self):
        self._cmd(f"TDIV {self.cmb_tdiv.currentText()}",
                  lambda: self.dev.set_time_div(self.cmb_tdiv.currentText()))

    def _apply_vdiv(self):
        self._cmd(f"C{self.ch}:VDIV {self.cmb_vdiv.currentText()}",
                  lambda: self.dev.set_vdiv(self.ch, self.cmb_vdiv.currentText()))

    def _apply_offset(self):
        self._cmd(f"C{self.ch}:OFFSET {self.spin_offset.value()}",
                  lambda: self.dev.set_offset(self.ch, self.spin_offset.value()))

    def _apply_coupling(self):
        self._cmd(f"C{self.ch}:COUPLING {self.cmb_coup.currentText()}",
                  lambda: self.dev.set_coupling(self.ch, self.cmb_coup.currentText()))

    def _apply_trigger(self):
        slope = SLOPES[self.cmb_slope.currentText()]
        self._cmd(f"C{self.ch}:TRLV {self.spin_trlv.value()}V, {slope}",
                  lambda: self.dev.set_trigger(self.ch, self.spin_trlv.value(), slope))

    def _run_bg(self, fn, on_done=None):
        """fn'i arka planda sıraya alır; aynı anda tek komut çalışır."""
        self._queue.append((fn, on_done))
        if not self._busy:
            self._next()

    def _next(self):
        if not self._queue:
            self._busy = False
            return
        if not self.bar.device.is_connected:
            self._log_warn("Bağlantı yok, komutlar temizlendi")
            self._queue.clear()
            self._busy = False
            return
        self._busy = True
        fn, on_done = self._queue.pop(0)
        w = Worker(fn)
        self._workers.append(w)
        w.done.connect(lambda r, cb=on_done: cb(r) if cb else None)
        w.fail.connect(lambda e: self._log_err(str(e)))
        w.finished.connect(lambda: (self._workers.remove(w) if w in self._workers else None,
                                    w.deleteLater(), self._next()))
        w.start()

    def _apply_default(self):
        self._cmd("*RST", self.dev.set_default)
        self._log_ok("Cihaz fabrika ayarlarına döndürüldü")

    def _on_connected(self):
        self._log_cmd("CRMS OFF (cursor modu: Manual)")
        self._run_bg(lambda: self.dev.set_cursor_mode("MANUAL"))
        self._log_cmd("*IDN? (otomatik bağlantı testi)")
        self._run_bg(lambda: self.dev.query("*IDN?"),
                     on_done=lambda r: (self._log_ok(f"Cihaz cevap verdi: {r}") if r
                                        else self._log_err("Cihaz SORGULARA cevap vermiyor! "
                                                           "Cihazı kapat-aç yapıp tekrar bağlanın.")))

    def _test_conn(self):
        if not self.bar.device.is_connected:
            self._log_warn("Bağlantı yok")
            return
        self._run_bg(lambda: self.dev.query("*IDN?"),
                     on_done=lambda r: (self._log_ok(f"IDN: {r}") if r
                                        else self._log_err("IDN cevabı YOK - cihaz sorguya cevap vermiyor!")))

    def _on_cursor_changed(self, cursor: str):
        # Ekranda sadece secili cursor cifti aktif gorunsun:
        # X1/X2 -> CRTY X, Y1/Y2 -> CRTY Y
        if not self.bar.device.is_connected or not cursor:
            return
        ctype = "X" if cursor.startswith("X") else "Y"
        self._log_cmd(f"CRTY {ctype}")
        self._run_bg(lambda: self.dev.set_cursor_type(ctype))

    def _apply_cursor_mode(self):
        self._cmd("CRMS OFF", lambda: self.dev.set_cursor_mode("MANUAL"))

    def _nudge_cursor(self, direction: int):
        if not self.bar.device.is_connected:
            return
        cursor = self.cmb_cursor.currentText()
        if not cursor:
            return
        now = time.monotonic()
        if now - self._last_press < 0.6:
            # Hizli/ardisik basista adim buyusun (1 -> 2 -> 5 -> 10 -> 20)
            self._mult_idx = min(self._mult_idx + 1, len(self._MULT_LADDER) - 1)
        else:
            self._mult_idx = 0
        self._last_press = now
        mult = self._MULT_LADDER[self._mult_idx]
        self.lbl_cstep.setText(
            f"Adım: otomatik (0.1 div) x{mult} "
            + ("— hızlı basış/tutma" if mult > 1 else ""))
        if self._nudge_pending and self._nudge_cursor_name != cursor:
            self._flush_nudge()
        self._nudge_cursor_name = cursor
        self._nudge_pending += direction
        self._nudge_timer.start()

    def _flush_nudge(self):
        steps = self._nudge_pending
        cursor = self._nudge_cursor_name
        self._nudge_pending = 0
        if not steps or not cursor or not self.bar.device.is_connected:
            return
        mult = self._MULT_LADDER[self._mult_idx]
        dev, ch = self.dev, self.ch
        total = abs(steps) * mult
        direction = 1 if steps > 0 else -1
        self._log_cmd(f"C{ch}: {cursor} {'+' if direction > 0 else '-'} "
                      f"{total} adım (birleşik)")
        def _after_nudge(pos):
            self._log_ok(f"Cursor {cursor} pozisyon: {_fmt(pos)}")
            # 6 deger kutusunu ve canli izlemeyi tazele; okuma sonrasi
            # ekranda aktif cursor highlight'i yine secili cursora donsun
            def _final(vals):
                self._set_cursor_values(vals)
                self._refresh_monitor()
                self._run_bg(lambda: dev.restore_active_cursor(ch, cursor))
            self._run_bg(lambda: dev.read_cursor_values(ch),
                         on_done=_final)
        self._run_bg(lambda: dev.nudge_cursor(ch, cursor, direction, total),
                     on_done=_after_nudge)

    def _refresh_monitor(self):
        """Cursor hareketi sonrasi canli izleme penceresini aninda tazele."""
        m = getattr(self, "_monitor", None)
        if m is not None:
            m.refresh_now()

    def mousePressEvent(self, ev):
        # Panel'e tiklayinca odak al -> yon tuslari calisir
        self.setFocus()
        super().mousePressEvent(ev)

    def keyPressEvent(self, ev):
        k = ev.key()
        if k in (Qt.Key.Key_Up, Qt.Key.Key_Left):
            if k == Qt.Key.Key_Left:
                # X1/X2/Y1/Y2 arasi gecis
                i = self.cmb_cursor.currentIndex()
                if i > 0:
                    self.cmb_cursor.setCurrentIndex(i - 1)
            else:
                self._nudge_cursor(-1)
        elif k in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            if k == Qt.Key.Key_Right:
                # X1/X2/Y1/Y2 arasi gecis
                i = self.cmb_cursor.currentIndex()
                if i < self.cmb_cursor.count() - 1:
                    self.cmb_cursor.setCurrentIndex(i + 1)
            else:
                self._nudge_cursor(+1)
        elif k == Qt.Key.Key_PageUp:
            self._nudge_cursor(-5)
        elif k == Qt.Key.Key_PageDown:
            self._nudge_cursor(+5)
        else:
            super().keyPressEvent(ev)

    def read_cursors(self):
        if not self.bar.device.is_connected:
            return
        ch, dev = self.ch, self.dev

        def f():
            v_raw = dev.query(f"C{ch}:CRVA? VREL")
            h_raw = dev.query(f"C{ch}:CRVA? HREL")
            return dev.read_cursor_values(ch), v_raw, h_raw

        def done(res):
            vals, v_raw, h_raw = res
            self._log_cmd(f"CRVA? C{ch} → {v_raw} | {h_raw}")
            if not h_raw.strip() and not v_raw.strip():
                self._log_warn("Cihaz cevap vermiyor - Mod=Manual uyguladığınızdan emin olun")
            elif not h_raw.strip():
                self._log_warn("X cursor değerleri yok - önce X1/X2 seçiliyken cursor seçin")
            self._set_cursor_values(vals)
            self._refresh_monitor()

        self._run_bg(f, on_done=done)

    def _set_cursor_values(self, v):
        self.box_x1.set_value(v["x1"])
        self.box_x2.set_value(v["x2"])
        self.box_dt.set_value(v["dt"])
        self.box_y1.set_value(v["y1"])
        self.box_y2.set_value(v["y2"])
        self.box_dv.set_value(v["dv"])

    def _toggle_live(self, on: bool):
        if on:
            self.measure_timer.start(500)
        else:
            self.measure_timer.stop()

    def _toggle_cur_auto(self, on: bool):
        if on:
            self.cur_timer.start(1000)
            self.read_cursors()
        else:
            self.cur_timer.stop()

    def _open_monitor(self):
        from PyQt6.QtWidgets import QMessageBox
        if not self.bar.device.is_connected:
            QMessageBox.warning(self, "Canlı İzleme", "Bağlantı yok")
            return
        # Canlı izleme yalnizca STOP modunda acilir (dalga formu sabit kalir)
        try:
            mode = self.dev.get_trigger_mode()
        except Exception as e:
            QMessageBox.warning(self, "Canlı İzleme",
                                f"Cihaz modu okunamadı, açılmadı:\n{e}")
            return
        if mode != "STOP":
            QMessageBox.warning(self, "Canlı İzleme",
                                f"Cihaz {mode} modunda.\nCanlı izleme yalnızca STOP modunda açılır.")
            return
        if getattr(self, "_monitor", None) is not None:
            try:
                if self._monitor.isVisible():
                    self._monitor.raise_()  # zaten acik: one getir
                    return
            except RuntimeError:
                pass  # C++ objesi silinmis: yeniden olustur
            self._monitor = None
        self._monitor = CursorMonitor(lambda: self.bar.device, self._monitor_channel)
        self._monitor.setWindowIcon(self.window().windowIcon())
        # Ana pencerenin sag yanina hizala
        geo = self.window().geometry()
        x = geo.x() + geo.width() + 10
        y = geo.y() + 60
        scr = self.screen().availableGeometry()
        w = self._monitor.frameGeometry().width() or 420
        if x + w > scr.right():
            x = scr.right() - w - 8
        self._monitor.move(x, y)
        self._monitor.show()

    def _monitor_channel(self) -> int:
        return self.ch

    def closeEvent(self, event):
        if getattr(self, "_monitor", None) is not None:
            try:
                self._monitor.close()
            except RuntimeError:
                pass
            self._monitor = None
        super().closeEvent(event)

    def read_measurements(self):
        if not self.bar.device.is_connected:
            if self.chk_live.isChecked():
                self.measure_timer.stop()
                self.chk_live.setChecked(False)
            return
        ch = self.ch
        dev = self.dev
        self._run_bg(lambda: [dev.query(f"C{ch}:PAVA? FREQ"),
                              dev.query(f"C{ch}:PAVA? PER"),
                              dev.query(f"C{ch}:PAVA? PKPK")],
                     on_done=lambda raws: self._set_measurements(ch, *raws))

    def _set_measurements(self, ch, *raws):
        self._log_cmd(f"PAVA? C{ch} → {' | '.join(raws)}")
        names = ["FREQ", "PER", "PKPK"]
        vals = []
        invalid = []
        import re as _re
        num = _re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
        for i, r in enumerate(raws):
            tok = r.split(",")[-1] if "," in r else ""
            m = num.search(tok)
            try:
                vals.append(float(m.group()) if m else float(tok))
            except (ValueError, IndexError):
                vals.append(float("nan"))
                invalid.append(names[i])
        if invalid:
            # "****" gibi cevaplar: cihaz bu ölçümü hesaplayamamış
            self._log_warn(f"C{ch} ölçüm geçersiz ({', '.join(invalid)}): "
                           "sinyal yok, tetik yok veya ölçüm aralığı dışı olabilir")
            return
        self.box_freq.set_value(vals[0])
        self.box_per.set_value(vals[1])
        self.box_vpp.set_value(vals[2])
        self._log_ok(f"C{ch} ölçüm okundu")

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Klasör Seç", self.txt_folder.text())
        if d:
            self.txt_folder.setText(d)
            self._save_folder()

    def _save_folder(self):
        self._settings.setValue("screenshot/folder", self.txt_folder.text())

    def screenshot(self):
        if not self.bar.device.is_connected:
            self._log_warn("Bağlantı yok, görüntü alınamadı")
            return
        folder = Path(self.txt_folder.text())
        self._save_folder()
        custom = self.txt_name.text().strip()
        if custom:
            name = custom if custom.lower().endswith(".bmp") else custom + ".bmp"
        else:
            name = time.strftime("osc_%Y%m%d_%H%M%S") + ".bmp"
        path = folder / name
        if path.exists():
            stem = path.stem
            i = 1
            while (folder / f"{stem}_{i}.bmp").exists():
                i += 1
            path = folder / f"{stem}_{i}.bmp"

        def f():
            data = self.dev.screenshot()
            folder.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return path

        self._run_bg(f, on_done=lambda p: self._log_ok(f"Ekran görüntüsü kaydedildi: {p}"))

