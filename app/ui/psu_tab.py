from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QGridLayout, QDoubleSpinBox, QPushButton, QLabel,
                             QMessageBox, QPlainTextEdit, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from core.powersupply import PowerSupply
from ui.device_bar import DeviceBar, _Job

CHANNELS = [1, 2, 3]

LOG_OK = "#45B881"
LOG_ERR = "#E56B70"
LOG_CMD = "#69A9F5"


class MeasureBox(QFrame):
    """Canlı ölçüm kutusu: etiket + değer + birim."""

    def __init__(self, title: str, unit: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame { background-color: #2B313A; border: 1px solid #4B5665;"
            " border-radius: 6px; }"
            "QLabel { border: none; background: transparent; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(0)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(
            "color: #B4BECC; font-size: 9pt; letter-spacing: 0.5px; font-weight: 600;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.lbl_title)
        h = QHBoxLayout()
        h.setSpacing(2)
        self.lbl_value = QLabel("—")
        self.lbl_value.setStyleSheet(
            "font-family: 'Consolas'; font-size: 16pt; font-weight: bold; color: #E5EAF1;")
        self.lbl_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self.lbl_value, 1)
        lbl_unit = QLabel(unit)
        lbl_unit.setStyleSheet("color: #B4BECC; font-size: 9pt;")
        h.addWidget(lbl_unit)
        lay.addLayout(h)

    def set_value(self, v: float):
        if v != v:
            self.lbl_value.setText("—")
        else:
            self.lbl_value.setText(f"{v:.3f}")


class ChannelWidget(QGroupBox):
    def __init__(self, channel: int, device_provider):
        super().__init__(f"CH{channel}")
        self.channel = channel
        self._device_provider = device_provider
        self.setObjectName("channelCard")

        g = QGridLayout(self)
        g.setContentsMargins(12, 14, 12, 10)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(8)

        # Durum göstergesi
        self.lbl_state = QLabel("OFF")
        self.lbl_state.setStyleSheet(
            "color: #B4BECC; font-weight: 700; font-size: 9pt;")
        self.lbl_state.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.dot_state = QLabel("●")
        self.dot_state.setStyleSheet("color: #B4BECC; font-size: 12pt;")
        self.dot_state.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        g.addWidget(self.dot_state, 0, 0)
        g.addWidget(self.lbl_state, 0, 1, Qt.AlignmentFlag.AlignRight)

        # Set değerleri
        g.addWidget(QLabel("Set Voltaj (V)"), 1, 0)
        self.spin_v = QDoubleSpinBox()
        self.spin_v.setRange(0.0, 33.0)
        self.spin_v.setDecimals(3)
        self.spin_v.setSingleStep(0.1)
        self.spin_v.setSuffix(" V")
        self.spin_v.setKeyboardTracking(False)
        g.addWidget(self.spin_v, 1, 1, 1, 2)

        g.addWidget(QLabel("Set Akım (A)"), 2, 0)
        self.spin_i = QDoubleSpinBox()
        self.spin_i.setRange(0.0, 5.0)
        self.spin_i.setDecimals(3)
        self.spin_i.setSingleStep(0.01)
        self.spin_i.setSuffix(" A")
        self.spin_i.setKeyboardTracking(False)
        g.addWidget(self.spin_i, 2, 1, 1, 2)

        btn_set = QPushButton("Ayarla")
        btn_set.clicked.connect(self.apply_settings)
        g.addWidget(btn_set, 1, 3, 2, 1)

        # Enter'a basinca (veya odak kaybinda) degisen degeri gonder;
        # ok tuslari ile degisim de valueChanged ile aninda gider
        # (keyboardTracking False oldugu icin yazarken sinyal gelmez)
        self._last_v = None
        self._last_i = None
        self.spin_v.editingFinished.connect(self._on_enter_v)
        self.spin_i.editingFinished.connect(self._on_enter_i)
        self.spin_v.valueChanged.connect(self._on_enter_v)
        self.spin_i.valueChanged.connect(self._on_enter_i)

        self.btn_out = QPushButton("KAPALI")
        self.btn_out.setCheckable(True)
        self.btn_out.setMinimumHeight(34)
        self.btn_out.setStyleSheet(
            "QPushButton { border: 1px solid #4B5665; background-color: #3B434E;"
            " color: #E5EAF1; border-radius: 6px; font-weight: 700; padding: 4px 10px; }"
            "QPushButton:hover { border-color: #69A9F5; }"
            "QPushButton:checked { background-color: #45B881; border-color: #45B881;"
            " color: #0f2419; }")
        self.btn_out.toggled.connect(self._toggle_output)
        g.addWidget(self.btn_out, 3, 0, 1, 4)

        # Canlı ölçümler
        self.box_v = MeasureBox("VOLTAGE", "V")
        self.box_i = MeasureBox("CURRENT", "A")
        self.box_p = MeasureBox("POWER", "W")
        h = QHBoxLayout()
        h.setSpacing(6)
        h.addWidget(self.box_v)
        h.addWidget(self.box_i)
        h.addWidget(self.box_p)
        g.addLayout(h, 4, 0, 1, 4)

        # Cihazdaki gercek set degerleri (Ayarla basilmadan degisse bile)
        self.lbl_set = QLabel("Cihaz: — V / — A")
        self.lbl_set.setStyleSheet("color: #69A9F5; font-size: 9pt;")
        g.addWidget(self.lbl_set, 5, 0, 1, 4)

        g.setColumnStretch(1, 1)

    def dev(self) -> PowerSupply:
        return self._device_provider()

    def _log(self, html: str):
        w = self.parent()
        while w is not None and not isinstance(w, PsuTab):
            w = w.parentWidget()
        if w is not None:
            w.log.appendHtml(html)

    def _send_async(self, fn, ok_msg: str, err_prefix: str, after=None):
        d = self.dev()
        if not d.is_connected:
            return
        if getattr(self, "_send_busy", False):
            return

        def f():
            try:
                fn()
                return ("ok",)
            except Exception as e:
                return ("err", str(e))

        self._send_busy = True
        job = _Job(f, self)
        self._send_job = job

        def _done(res):
            self._send_busy = False
            if res[0] == "ok":
                self._log(f'<span style="color:{LOG_OK};">✓ CH{self.channel} {ok_msg}</span>')
                if after:
                    after()
            else:
                self._log(f'<span style="color:{LOG_ERR};">✗ CH{self.channel} '
                          f'{err_prefix}: {res[1]}</span>')

        job.done.connect(_done)
        job.start_job()

    def _on_enter_v(self, *_):
        value = self.spin_v.value()
        if value == self._last_v:
            return
        self._last_v = value
        d = self.dev()
        if not d.is_connected:
            return
        self._send_async(
            lambda: d.set_voltage(self.channel, value),
            f'voltaj girildi: {value:.3f} V',
            'voltaj hatası',
            after=lambda: self.set_settings_display(value, self.spin_i.value()))

    def _on_enter_i(self, *_):
        value = self.spin_i.value()
        if value == self._last_i:
            return
        self._last_i = value
        d = self.dev()
        if not d.is_connected:
            return
        self._send_async(
            lambda: d.set_current(self.channel, value),
            f'akım girildi: {value:.3f} A',
            'akım hatası',
            after=lambda: self.set_settings_display(self.spin_v.value(), value))

    def apply_settings(self):
        d = self.dev()
        if not d.is_connected:
            QMessageBox.warning(self, "Uyarı", "Önce cihaza bağlanın!")
            return
        sv, si = self.spin_v.value(), self.spin_i.value()

        def after():
            self.set_settings_display(sv, si)
            self._last_v = sv
            self._last_i = si

        self._send_async(
            lambda: (d.set_voltage(self.channel, sv),
                     d.set_current(self.channel, si)),
            f'ayarlandı: {sv:.3f} V / {si:.3f} A',
            'ayar hatası',
            after=after)

    def _toggle_output(self, on: bool):
        d = self.dev()
        if not d.is_connected:
            self.btn_out.blockSignals(True)
            self.btn_out.setChecked(False)
            self.btn_out.blockSignals(False)
            QMessageBox.warning(self, "Uyarı", "Önce cihaza bağlanın!")
            return
        try:
            d.set_output(self.channel, on)
            self.btn_out.setText("AÇIK" if on else "KAPALI")
            self.lbl_state.setText("ON" if on else "OFF")
            color = "#45B881" if on else "#B4BECC"
            self.lbl_state.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 9pt;")
            self.dot_state.setStyleSheet(f"color: {color}; font-size: 12pt;")
            self._log(f'<span style="color:{LOG_OK};">✓ CH{self.channel} çıkışı'
                      f' {"AÇILDI" if on else "KAPATILDI"}</span>')
            w = self.parent()
            while w is not None and not isinstance(w, PsuTab):
                w = w.parentWidget()
            if w is not None:
                w._refresh_state_soon()
        except Exception as e:
            self._log(f'<span style="color:{LOG_ERR};">✗ CH{self.channel} çıkış hatası: {e}</span>')
            QMessageBox.critical(self, "Hata", str(e))
            self.btn_out.blockSignals(True)
            self.btn_out.setChecked(not on)
            self.btn_out.blockSignals(False)

    def update_measurement(self):
        d = self.dev()
        if not d.is_connected:
            self.show_nan()
            return
        # Not: canli poller artik PsuTab._update_all ile thread'de okuyor;
        # bu metod sadece manuel tek kanal okumasi icin kaldi.
        try:
            self.box_v.set_value(d.read_voltage(self.channel))
            self.box_i.set_value(d.read_current(self.channel))
            self.box_p.set_value(d.read_power(self.channel))
        except Exception:
            pass

    def show_nan(self):
        for b in (self.box_v, self.box_i, self.box_p):
            b.set_value(float("nan"))
        self.lbl_set.setText("Cihaz: — V / — A")

    def set_settings_display(self, sv, sc):
        if sv != sv or sc != sc:
            self.lbl_set.setText("Cihaz: — V / — A")
        else:
            self.lbl_set.setText(f"Cihaz: {sv:.3f} V / {sc:.3f} A")


class PsuTab(QWidget):
    state_changed = pyqtSignal(list)  # [(ch, on, volt, amps), ...]

    def __init__(self):
        super().__init__()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)

        main = QVBoxLayout(self)
        main.setContentsMargins(10, 6, 10, 10)
        main.setSpacing(8)

        self.bar = DeviceBar("Power Supply", PowerSupply, expected_vids=[0x1AB1])
        self.bar.disconnected.connect(self._on_disconnected)
        self.bar.connected.connect(self._refresh_state_soon)  # baglanir baglanmaz state tazele
        main.addWidget(self.bar)

        # Kanal kartları
        row = QHBoxLayout()
        row.setSpacing(8)
        self.channels = []
        for ch in CHANNELS:
            w = ChannelWidget(ch, lambda: self.bar.device)
            self.channels.append(w)
            row.addWidget(w, 1)
        main.addLayout(row)

        # Tüm kanallar bölümü
        gb_all = QGroupBox("Tüm Kanallar")
        gh = QHBoxLayout(gb_all)
        gh.setContentsMargins(10, 8, 10, 8)
        btn_all_on = QPushButton("TÜMÜNÜ AÇ")
        btn_all_on.setObjectName("btn_run")
        btn_all_on.setMinimumHeight(34)
        btn_all_on.clicked.connect(lambda: self._all(True))
        btn_all_off = QPushButton("TÜMÜNÜ KAPAT")
        btn_all_off.setObjectName("btn_danger")
        btn_all_off.setMinimumHeight(34)
        btn_all_off.clicked.connect(lambda: self._all(False))
        gh.addWidget(btn_all_on)
        gh.addWidget(btn_all_off)
        gh.addStretch(1)
        main.addWidget(gb_all)

        # Geniş log alanı
        gb_log = QGroupBox("Komut Logu")
        vl = QVBoxLayout(gb_log)
        vl.setContentsMargins(10, 8, 10, 8)
        hlog = QHBoxLayout()
        btn_clear = QPushButton("Temizle")
        btn_clear.clicked.connect(self.log.clear)
        hlog.addWidget(btn_clear)
        hlog.addStretch(1)
        vl.addLayout(hlog)
        vl.addWidget(self.log)
        main.addWidget(gb_log, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_all)
        self.timer.start(1000)
        self._poll_busy = False
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self.timer.stop)

    def _log(self, html: str):
        self.log.appendHtml(html)

    def _all(self, on: bool):
        d = self.bar.device
        if not d.is_connected:
            QMessageBox.warning(self, "Uyarı", "Önce cihaza bağlanın!")
            return
        try:
            d.set_all_outputs(on)
        except Exception as e:
            self._log(f'<span style="color:{LOG_ERR};">✗ Tüm kanallar hatası: {e}</span>')
            return
        for w in self.channels:
            w.btn_out.blockSignals(True)
            w.btn_out.setChecked(on)
            w.btn_out.setText("AÇIK" if on else "KAPALI")
            w.lbl_state.setText("ON" if on else "OFF")
            color = "#45B881" if on else "#B4BECC"
            w.lbl_state.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 9pt;")
            w.dot_state.setStyleSheet(f"color: {color}; font-size: 12pt;")
            w.btn_out.blockSignals(False)
        self._log(f'<span style="color:{LOG_OK};">✓ Tüm kanallar'
                  f' {"AÇILDI" if on else "KAPATILDI"}</span>')
        self._refresh_state_soon()

    def _refresh_state_soon(self):
        """Cikis komutundan hemen sonra gercek durumu tazele (1 sn bekleme olmasin)."""
        QTimer.singleShot(150, self._update_all)

    def _on_disconnected(self):
        """Baglanti kesilince arayuzu temiz state'e getir (acik kalmis gibi kalmasin)."""
        for w in self.channels:
            w.show_nan()
            w.btn_out.blockSignals(True)
            w.btn_out.setChecked(False)
            w.btn_out.blockSignals(False)
            w.btn_out.setText("KAPALI")
            w.lbl_state.setText("OFF")
            w.lbl_state.setStyleSheet("color: #B4BECC; font-weight: 700; font-size: 9pt;")
            w.dot_state.setStyleSheet("color: #B4BECC; font-size: 12pt;")
        self._last_state = [(w.channel, False, "—", "—") for w in self.channels]
        self.state_changed.emit(self._last_state)
        self._log('<span style="color:#E7B65C;">! Bağlantı kesildi — kanal durumları temizlendi</span>')

    def _update_all(self):
        d = self.bar.device
        if not d.is_connected:
            for w in self.channels:
                w.show_nan()
            return
        # onceki poll hala calisiyorsa yeni istek biriktirme (GUI donmasin)
        if self._poll_busy:
            return
        self._poll_busy = True
        chans = [w.channel for w in self.channels]

        def f():
            rows = []
            for ch in chans:
                try:
                    v = d.read_voltage(ch)
                    i = d.read_current(ch)
                    p = d.read_power(ch)
                except Exception:
                    v = i = p = float("nan")
                try:
                    sv, sc = d.read_settings(ch)
                except Exception:
                    sv = sc = float("nan")
                try:
                    on = d.get_output_state(ch)
                except Exception:
                    on = None  # okunamadi: GUI durumuna dokunma
                rows.append((v, i, p, sv, sc, on))
            return rows

        job = _Job(f, self)
        self._poll_job = job
        job.done.connect(self._poll_done)
        job.start_job()

    def _poll_done(self, res):
        self._poll_busy = False
        if isinstance(res, Exception):
            return
        for w, (v, i, p, sv, sc, on) in zip(self.channels, res):
            w.box_v.set_value(v)
            w.box_i.set_value(i)
            w.box_p.set_value(p)
            w.set_settings_display(sv, sc)
            if on is not None:
                self._sync_output_ui(w, on)
        self._last_state = [
            (w.channel, w.btn_out.isChecked(), w.box_v.lbl_value.text(),
             w.box_i.lbl_value.text())
            for w in self.channels]
        self.state_changed.emit(self._last_state)

    @staticmethod
    def _sync_output_ui(w, on: bool):
        """Cihazdaki gercek cikis durumunu GUI butonuna yansitir."""
        if w.btn_out.isChecked() == on:
            return
        w.btn_out.blockSignals(True)
        w.btn_out.setChecked(on)
        w.btn_out.blockSignals(False)
        w.btn_out.setText("AÇIK" if on else "KAPALI")
        w.lbl_state.setText("ON" if on else "OFF")
        color = "#45B881" if on else "#B4BECC"
        w.lbl_state.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 9pt;")
        w.dot_state.setStyleSheet(f"color: {color}; font-size: 12pt;")

    def last_state(self):
        """Son poll sonucu; mini mod acilirken poll beklemeden kullanilir."""
        return getattr(self, "_last_state", [])
