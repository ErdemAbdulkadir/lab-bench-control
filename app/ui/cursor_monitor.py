from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor

# Cihaz cursor degerleri div cinsindendir:
# X (TDIF/TREF): 0..14 (yatay 14 div), Y (VDIF/VREF): 0..8 (dikey 8 div)
X_DIVS = 14.0
Y_DIVS = 8.0
# T3DSO BMP'sinde (800x480) dalga grid alaninin piksel dikdortgeni
GRID_X, GRID_Y, GRID_W, GRID_H = 12.0, 20.0, 700.0, 400.0
BMP_W, BMP_H = 800.0, 480.0
LINE_NAMES = ("X1", "X2", "Y1", "Y2")


def _divs_max(name):
    return X_DIVS if name.startswith("X") else Y_DIVS


def _div_to_frac(name, div):
    return max(0.0, min(1.0, div / _divs_max(name)))


class _PollWorker(QThread):
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


class _ScreenOverlay(QWidget):
    """Cihaz ekran goruntusu uzerinde cursor cizgisi onizlemesi."""
    released = pyqtSignal(str, float)  # (X1/X2/Y1/Y2, div)

    def __init__(self):
        super().__init__()
        self._pm = None
        self._drag = None
        self._show = set()
        self.selected = "X1"
        self.frac = {"X1": 0.3, "X2": 0.7, "Y1": 0.35, "Y2": 0.65}
        self.setMinimumSize(480, 320)

    def set_pixmap(self, pm):
        self._pm = pm
        self._show.clear()  # yeni ekranda cihazin kendi cursorlari var
        self.update()

    def show_line(self, name):
        """Cursor konumunu kullaniciya gostermeye devam et."""
        self._show.add(name)
        self.update()

    def set_frac(self, name, f):
        self.frac[name] = max(0.0, min(1.0, f))
        self.update()

    def set_selected(self, name):
        self.selected = name
        self.update()

    def _img_rect(self):
        """Tum BMP'nin widget'a sigmis hali."""
        r = self.rect()
        if self._pm is None or self._pm.isNull():
            return QRectF(r)
        s = min(r.width() / BMP_W, r.height() / BMP_H)
        w, h = BMP_W * s, BMP_H * s
        return QRectF((r.width() - w) / 2, (r.height() - h) / 2, w, h)

    def _rect(self):
        """Grid dikdortgeni (widget koordinatlarinda)."""
        ir = self._img_rect()
        if self._pm is None or self._pm.isNull():
            return ir
        return QRectF(ir.x() + GRID_X / BMP_W * ir.width(),
                      ir.y() + GRID_Y / BMP_H * ir.height(),
                      GRID_W / BMP_W * ir.width(),
                      GRID_H / BMP_H * ir.height())

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#10141A"))
        if self._pm is not None and not self._pm.isNull():
            p.drawPixmap(self._img_rect(), self._pm, QRectF(self._pm.rect()))
        else:
            p.setPen(QColor("#B4BECC"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Ekran bekleniyor…")
            return
        g = self._rect()
        # Cizgiler: suruklenen + son ayarlananlar; yeni ekran gelince silinir
        names = set(self._show)
        if self._drag:
            names.add(self._drag)
        if not names:
            return
        for name in names:
            f = self.frac[name]
            dragging = self._drag == name
            pen = QPen(QColor("#45B881"))
            pen.setWidth(2 if dragging else 1)
            pen.setStyle(Qt.PenStyle.SolidLine if dragging else Qt.PenStyle.DashLine)
            p.setPen(pen)
            if name.startswith("X"):
                x = g.x() + f * g.width()
                p.drawLine(QPointF(x, g.y()), QPointF(x, g.y() + g.height()))
                p.setPen(QColor("#E5EAF1"))
                p.drawText(int(x) + 4, int(g.y()) + 14, name)
            else:
                y = g.y() + f * g.height()
                p.drawLine(QPointF(g.x(), y), QPointF(g.x() + g.width(), y))
                p.setPen(QColor("#E5EAF1"))
                p.drawText(int(g.x()) + 4, int(y) - 4, name)

    def _pick(self, pos):
        g = self._rect()
        best, bd = None, 18.0
        for name, f in self.frac.items():
            if name.startswith("X"):
                d = abs(pos.x() - (g.x() + f * g.width()))
            else:
                d = abs(pos.y() - (g.y() + f * g.height()))
            if d < bd:
                best, bd = name, d
        return best

    def mousePressEvent(self, ev):
        n = self._pick(ev.position())
        if not n:
            # Cizgiden tutulmadiysa secili cursoru basilan yere zipla
            n = self.selected
            g = self._rect()
            if n.startswith("X"):
                f = (ev.position().x() - g.x()) / max(1.0, g.width())
            else:
                f = (ev.position().y() - g.y()) / max(1.0, g.height())
            self.set_frac(n, f)
        self._drag = n
        self.update()

    def mouseMoveEvent(self, ev):
        if not self._drag:
            return
        g = self._rect()
        if self._drag.startswith("X"):
            f = (ev.position().x() - g.x()) / max(1.0, g.width())
        else:
            f = (ev.position().y() - g.y()) / max(1.0, g.height())
        self.set_frac(self._drag, f)

    def mouseReleaseEvent(self, ev):
        if not self._drag:
            return
        name, f = self._drag, self.frac[self._drag]
        self._drag = None
        self.update()
        self.released.emit(name, f)  # frac 0..1; cevirmeyi izleyici yapar


def _lbl(txt, color="#E5EAF1", size=13, bold=True):
    l = QLabel(txt)
    l.setStyleSheet(
        f"font-family: 'Consolas'; font-size: {size}pt; font-weight: {'bold' if bold else 'normal'};"
        f" color: {color}; background: transparent; border: none;")
    return l


class CursorMonitor(QWidget):
    """Canli izleme: cihaz RUN modundayken acilir; ekran bir kez cekilir.
    Cursorlar suruklenerek veya ok tuslariyla ayarlanir, her adim cihaza
    yazilir. Run/stop moduna dokunmaz."""

    KEYS = {"X1": "TDIF", "X2": "TREF", "Y1": "VDIF", "Y2": "VREF"}
    def __init__(self, device_provider, channel_provider):
        super().__init__()
        self._dev_provider = device_provider
        self._ch_provider = channel_provider
        self._worker = None      # veri cekme isçisi
        self._cmd_worker = None  # cursor yazma isçisi
        self._pending = {}
        self._trash = []
        self._divs = {}  # yerel cursor durumu (div): okumadan yazmak icin
        self.setWindowTitle("Cursor Canlı İzleme")
        self.resize(600, 580)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        main = QVBoxLayout(self)
        main.setContentsMargins(10, 8, 10, 8)
        main.setSpacing(6)

        self.lbl_head = _lbl("Cihaz ekranı alındı — ok tuşları / sürükleme ile cursor ayarla",
                             "#69A9F5", 10)
        main.addWidget(self.lbl_head)

        self.screen = _ScreenOverlay()
        self.screen.released.connect(self._on_line_released)
        main.addWidget(self.screen, 1)

        gb = QGroupBox("Cursor Değerleri")
        g = QGridLayout(gb)
        g.setContentsMargins(8, 6, 8, 6)
        self._rows = {}
        items = (("x1", "X1", "s"), ("x2", "X2", "s"),
                 ("y1", "Y1", "V"), ("y2", "Y2", "V"))
        for i, (key, name, unit) in enumerate(items):
            c, r = i % 2, i // 2
            h = QHBoxLayout()
            h.setSpacing(4)
            h.addWidget(_lbl(f"{name}", "#B4BECC", 10, bold=False))
            l = _lbl("—")
            h.addWidget(l, 1)
            h.addWidget(_lbl(unit, "#B4BECC", 9, bold=False))
            g.addLayout(h, r, c)
            self._rows[key] = l
        main.addWidget(gb)

        hb = QHBoxLayout()
        hb.addWidget(_lbl("Cursor:", "#B4BECC", 10, bold=False))
        self.cmb_cursor = QComboBox()
        self.cmb_cursor.addItems(list(LINE_NAMES))
        self.cmb_cursor.setMinimumHeight(30)
        self.cmb_cursor.currentTextChanged.connect(self._on_cursor_changed)
        hb.addWidget(self.cmb_cursor)
        self.btn_up = QPushButton("▲")
        self.btn_down = QPushButton("▼")
        for b in (self.btn_up, self.btn_down):
            b.setMinimumHeight(30)
            b.setMaximumWidth(40)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_up.clicked.connect(lambda: self._nudge(+1))
        self.btn_down.clicked.connect(lambda: self._nudge(-1))
        hb.addWidget(self.btn_up)
        hb.addWidget(self.btn_down)
        self.btn_refresh = QPushButton("🔄 Ekranı Yenile")
        self.btn_refresh.setMinimumHeight(30)
        self.btn_refresh.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_refresh.clicked.connect(self._refresh_all)
        hb.addWidget(self.btn_refresh)
        hb.addStretch(1)
        main.addLayout(hb)

        self._msg = _lbl("Ok tuşları: ←/→ X, ↑/↓ Y  |  PgUp/PgDn: hızlı adım  |  Tab: cursor seç",
                         "#8A93A0", 9, bold=False)
        main.addWidget(self._msg)

        self._tick()  # acilista bir kez veri + ekran cek

    # ------------------------------------------------ helpers
    def _fmt(self, v, unit):
        if v != v:
            return "—"
        a = abs(v)
        if a >= 1:
            return f"{v:.4g} {unit}"
        if a >= 1e-3:
            return f"{v * 1e3:.4g} m{unit}"
        if a >= 1e-6:
            return f"{v * 1e6:.4g} µ{unit}"
        if a >= 1e-9:
            return f"{v * 1e9:.4g} n{unit}"
        return f"{v * 1e12:.4g} p{unit}"

    def _on_cursor_changed(self, name):
        self.screen.set_selected(name)

    def _nudge(self, direction):
        self._move_cursor(direction)

    def _retire(self, w):
        """Bitmis isçiyi hemen destroy etme: referansi kutuda kalsin."""
        if w is None:
            return
        self._trash.append(w)
        if len(self._trash) > 32:
            self._trash = [t for t in self._trash if t.isRunning()]

    def _move_cursor(self, direction, mult=1):
        cursor = self.cmb_cursor.currentText()
        name = cursor
        div = max(0.0, min(_divs_max(name),
                           self._divs.get(name, _divs_max(name) / 2)
                           + direction * 0.1 * mult))
        self._divs[name] = div
        self.screen.set_frac(name, _div_to_frac(name, div))
        self.screen.show_line(name)
        self._send_group(name[0], name)  # X cifti veya Y cifti tek yazmada

    def _on_line_released(self, name, frac):
        self.cmb_cursor.setCurrentText(name)
        self._divs[name] = frac * _divs_max(name)
        self.screen.show_line(name)
        self._send_group(name[0], name)

    def _send_group(self, prefix, active=None):
        """Cift halinde yazar; AYARLANAN cursor sona yazilir ki cihazda
        o aktif olsun: X -> TREF+TDIF, Y -> VREF+VDIF."""
        dev = self._dev_provider()
        if not dev.is_connected:
            self._msg.setText("Osiloskopa bağlanın")
            return
        self._msg.setText("")
        if prefix == "X":
            a, b = "X1", "X2"
        else:
            a, b = "Y1", "Y2"
        da = self._divs.get(a, _divs_max(a) / 2)
        db = self._divs.get(b, _divs_max(b) / 2)
        w = self._cmd_worker
        if w is not None and w.isRunning():
            self._pending[prefix] = (da, db, active)
            return
        self._do_send_group(prefix, da, db, active)

    def _do_send_group(self, prefix, da, db, active=None):
        dev, ch = self._dev_provider(), self._ch_provider()
        if prefix == "X":
            k1, k2 = self.KEYS["X1"], self.KEYS["X2"]  # X1=TDIF, X2=TREF
            v1, v2 = da, db
        else:
            k1, k2 = self.KEYS["Y1"], self.KEYS["Y2"]  # Y1=VDIF, Y2=VREF
            v1, v2 = da, db
        # aktif (ayarlanan) cursor SONA yazilir
        if active is not None and self.KEYS[active] == k1:
            k1, k2, v1, v2 = k2, k1, v2, v1
        self._retire(self._cmd_worker)
        self._cmd_worker = _PollWorker(
            lambda: dev.set_cursor_pair(ch, k1, v1, k2, v2))
        self._cmd_worker.done.connect(self._after_cmd)
        self._cmd_worker.fail.connect(self._on_fail)
        self._cmd_worker.start()

    def _after_cmd(self, _r=None):
        if self._pending:
            prefix, (da, db, active) = self._pending.popitem()
            self._do_send_group(prefix, da, db, active)
            return
        # Yazmalar bitti.
        if getattr(self, "_refresh_after", False):
            self._refresh_after = False
            self._tick(False)  # ekran resmi + degerler (sadece buton istegi)

    def _refresh_all(self):
        """Buton: 4 cursor degerini gonder + ekran resmini ve degerleri yenile."""
        if not self._dev_provider().is_connected:
            self._msg.setText("Osiloskopa bağlanın")
            return
        self._refresh_after = True
        self._send_group("X")
        self._send_group("Y")

    def _tick(self, light=False):
        """light=False: tam cekim (acilis/yenile butonu: deger+div+ekran).
        light=True: sadece deger + ekran resmi (cursor yazmasindan sonra)."""
        dev, ch = self._dev_provider(), self._ch_provider()
        if not dev.is_connected:
            self._msg.setText("Osiloskopa bağlanın")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        def _poll():
            vals = dev.read_cursor_values(ch)
            if light:
                divs = {}
            else:
                divs = {c: dev.get_cursor_pos(ch, k) for c, k in self.KEYS.items()}
                # Bazi anahtarlar div yerine zaman/gerilim donebilir;
                # olcekle cevir (X: 7+val/tdiv, Y: 4-val/vdiv+|ofst|/vdiv)
                try:
                    if any(not (d == d and 0 <= d <= _divs_max(c))
                           for c, d in divs.items()):
                        tdiv = dev.get_tdiv()
                        vdiv = dev.get_vdiv(ch)
                        ofst = dev.get_ofst(ch)
                        for c, d in list(divs.items()):
                            if not (d == d and 0 <= d <= _divs_max(c)):
                                if c.startswith("X") and tdiv:
                                    divs[c] = 7.0 + d / tdiv
                                elif not c.startswith("X") and vdiv:
                                    divs[c] = 4.0 - d / vdiv + abs(ofst) / vdiv
                except Exception:
                    pass
            shot = dev.screenshot()
            return vals, divs, shot

        self._retire(self._worker)
        self._worker = _PollWorker(_poll)
        self._worker.done.connect(self._on_data)
        self._worker.fail.connect(self._on_fail)
        self._worker.start()

    def _on_data(self, res):
        vals, divs, shot = res
        for k in ("x1", "x2"):
            self._rows[k].setText(self._fmt(vals[k], "s"))
        for k in ("y1", "y2"):
            self._rows[k].setText(self._fmt(vals[k], "V"))
        if divs:
            # Sadece eksenin div araligindaki degerleri benimse
            for name, d in divs.items():
                if d == d and 0.0 <= d <= _divs_max(name):
                    self._divs[name] = d
            for name, d in self._divs.items():
                self.screen.set_frac(name, _div_to_frac(name, d))
        if shot:
            pm = QPixmap()
            if pm.loadFromData(shot):
                self.screen.set_pixmap(pm)

    def _on_fail(self, err):
        self._msg.setText(f"Hata: {err}")

    def keyPressEvent(self, ev):
        k = ev.key()
        cursor = self.cmb_cursor.currentText()
        is_x = cursor.startswith("X")
        if k == Qt.Key.Key_Left and is_x:
            self._move_cursor(-1)
        elif k == Qt.Key.Key_Right and is_x:
            self._move_cursor(+1)
        elif k == Qt.Key.Key_Up and not is_x:
            self._move_cursor(+1)
        elif k == Qt.Key.Key_Down and not is_x:
            self._move_cursor(-1)
        elif k == Qt.Key.Key_PageUp:
            self._move_cursor(+5)
        elif k == Qt.Key.Key_PageDown:
            self._move_cursor(-5)
        elif k == Qt.Key.Key_Tab:
            i = (self.cmb_cursor.currentIndex() + 1) % self.cmb_cursor.count()
            self.cmb_cursor.setCurrentIndex(i)
        else:
            super().keyPressEvent(ev)

    def refresh_now(self):
        self._tick()

    def closeEvent(self, event):
        for w in [self._worker, self._cmd_worker] + self._trash:
            if w is not None and w.isRunning():
                w.wait(5000)
        super().closeEvent(event)
