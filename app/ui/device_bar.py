from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QComboBox, QPushButton,
                             QLabel, QApplication)
from PyQt6.QtCore import pyqtSignal, QThread, Qt

from core.visa_device import VisaDevice

# Bilinen cihazlar: VID -> (emoji, tur, marka/model)
_KNOWN = [
    (0x1AB1, "🔌", "Power Supply", "Rigol DP932"),
    (0xF4EC, "⚡", "Osiloskop", "T3DSO2104"),
]


def _vid_of(resource: str):
    """USB0::0xVID::0xPID::...::INSTR biciminden VID'i cikarir."""
    try:
        parts = resource.split("::")
        if len(parts) > 1 and parts[1].upper().startswith("0X"):
            return int(parts[1], 16)
    except (ValueError, IndexError):
        pass
    return None


def _classify(resource: str) -> str:
    vid = _vid_of(resource)
    for known_vid, emoji, tur, model in _KNOWN:
        if vid == known_vid:
            return f"{emoji} {tur} — {model}"
    up = resource.upper()
    if "T3DSO" in up or "SDS" in up:
        return "⚡ Osiloskop (bilinmeyen model)"
    if "DP9" in up or "DP8" in up:
        return "🔌 Power Supply (bilinmeyen model)"
    if up.startswith("ASRL"):
        return "🔌 Seri Port (bilinmiyor)"
    return resource  # bilinmeyen: ham isim


class _Job(QThread):
    """Tek seferlik arka plan isleci; sonucu sinyalle dondurur."""
    done = pyqtSignal(object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def start_job(self):
        self.finished.connect(self.deleteLater)
        self.start()

    def run(self):
        try:
            res = self._fn()
        except Exception as e:
            res = e
        self.done.emit(res)


class DeviceBar(QWidget):
    """Cihaz tarama / seçim / bağlanma barı."""
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, title: str, device_cls=VisaDevice, expected_vids=None,
                 device=None):
        super().__init__()
        # Ayni fiziksel cihaz sekmeler arasinda paylasilabilir:
        # iki ayri VisaData objesi ayni USB kaynagi acamaz
        self.device = device if device is not None else device_cls()
        self.expected_vids = expected_vids  # bu sekmenin kabul ettigi VID'ler
        self.setObjectName("deviceBar")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(
            "color: #B4BECC; font-weight: 600; letter-spacing: 0.5px;")
        lay.addWidget(self.lbl_title)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(280)
        lay.addWidget(self.combo, 1)

        self.btn_scan = QPushButton("Tara")
        self.btn_scan.setToolTip("VISA cihazlarını yeniden tara")
        self.btn_scan.clicked.connect(self.scan)
        lay.addWidget(self.btn_scan)

        self.btn_connect = QPushButton("Bağlan")
        self.btn_connect.setMinimumWidth(110)
        self.btn_connect.clicked.connect(self.toggle_connect)
        lay.addWidget(self.btn_connect)

        self.lbl_status = QLabel("Disconnected")
        self.lbl_status.setStyleSheet(
            "color: #E56B70; font-weight: 600;")
        lay.addWidget(self.lbl_status)

        self._dot = QLabel("●")
        self._dot.setStyleSheet("color: #E56B70; font-size: 13pt;")
        lay.addWidget(self._dot)

        QApplication.instance().aboutToQuit.connect(self._wait_jobs)
        self.scan()

    def _wait_jobs(self):
        """Cikista arka plan islerini kisa surede bekle (abort onleme)."""
        for attr in ("_scan_job", "_conn_job"):
            job = getattr(self, attr, None)
            if job is not None and job.isRunning():
                job.wait(2000)

    def add_button(self, text: str) -> QPushButton:
        """Tara butonunun yanina ek buton ekler (IDN testi vb.)."""
        btn = QPushButton(text)
        lay = self.layout()
        lay.insertWidget(lay.indexOf(self.btn_scan) + 1, btn)
        return btn

    def scan(self):
        """Cihazlari arka planda tara; GUI donmasin."""
        if getattr(self, "_scanning", False):
            return
        self._scanning = True
        job = _Job(lambda: VisaDevice.list_devices(), self)
        self._scan_job = job  # referans kalsin
        job.done.connect(self._scan_done)
        job.start_job()

    def _scan_done(self, res):
        self._scanning = False
        self.combo.clear()
        if isinstance(res, Exception):
            return
        for r in res:
            self.combo.addItem(_classify(r), userData=r)
            # tooltip: ham kaynak ismi
            self.combo.setItemData(self.combo.count() - 1, r,
                                   Qt.ItemDataRole.ToolTipRole)

    def toggle_connect(self):
        if self.device.is_connected:
            self.btn_connect.setEnabled(False)
            self.btn_connect.setText("...")
            job = _Job(self.device.disconnect, self)
            self._conn_job = job
            job.done.connect(lambda _r: (self._set_status(False),
                                         self.btn_connect.setEnabled(True),
                                         self.disconnected.emit()))
            job.start_job()
            return
        resource = (self.combo.currentData() or self.combo.currentText() or "").strip()
        if not resource:
            self._set_status(False, "Cihaz seçilmedi")
            return
        # Bu sekmenin cihazi mi? (VID kontrolu) — yanlis baglantiyi engelle
        if self.expected_vids:
            vid = _vid_of(resource)
            if vid is not None and vid not in self.expected_vids:
                name = self.combo.currentText()
                self._set_status(False, f"Bu cihaz buraya ait değil: {name}")
                return
        if getattr(self, "_connecting", False):
            return
        self._connecting = True
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("...")
        job = _Job(lambda: self.device.connect(resource), self)
        self._conn_job = job
        job.done.connect(self._connect_done)
        job.start_job()

    def _connect_done(self, ok):
        self._connecting = False
        self.btn_connect.setEnabled(True)
        if ok is True:
            self._set_status(True)
            self.connected.emit()
        else:
            err = getattr(self.device, "last_error", "") or "Bağlanamadı"
            self._set_status(False, err)

    def _set_status(self, ok: bool, msg: str = ""):
        if ok:
            text, color = "Connected", "#45B881"
        else:
            text, color = (msg or "Disconnected"), "#E56B70"
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: 600;")
        self._dot.setStyleSheet(f"color: {color}; font-size: 13pt;")
        self.btn_connect.setText("Kes" if ok else "Bağlan")
