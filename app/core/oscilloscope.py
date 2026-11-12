import re
import struct

import numpy as np

from .visa_device import VisaDevice

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _to_float(token: str) -> float:
    """'7.00µs' -> 7e-6, '142.8kHz' -> 142800, '-5.20V' -> -5.2"""
    t = token.strip()
    m = _NUM_RE.match(t)
    if not m:
        return float("nan")
    v = float(m.group(0))
    mult = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6,
            "m": 1e-3, "k": 1e3, "g": 1e9}
    # Birim onekini ara (cihaz µ karakterini bozuk bayt olarak gonderebiliyor)
    for ch in t[m.end():].lower():
        if ch.isspace():
            continue
        if not ch.isalpha():
            v *= 1e-6  # bozuk mikron isareti
            break
        if ch in mult:
            v *= mult[ch]
        break
    return v

TIME_DIVS = ["1ns", "2ns", "5ns", "10ns", "20ns", "50ns",
             "100ns", "200ns", "500ns",
             "1us", "2us", "5us", "10us", "20us", "50us",
             "100us", "200us", "500us",
             "1ms", "2ms", "5ms", "10ms", "20ms", "50ms",
             "100ms", "200ms", "500ms",
             "1s", "2s", "5s", "10s", "20s", "50s", "100s"]

VOLT_DIVS = ["1mV", "2mV", "5mV", "10mV", "20mV", "50mV",
             "100mV", "200mV", "500mV",
             "1V", "2V", "5V", "10V", "20V"]

MEASURE_ITEMS = ["FREQ", "PER", "MAX", "MIN", "PKPK", "RMS", "VAVG"]


class Oscilloscope(VisaDevice):
    """Teledyne LeCroy T3DSO2104 (T3DSO1000/2000 serisi) kontrol katmanı."""

    # ---- Dikey / yatay ----
    def set_time_div(self, tdiv: str):
        self.write(f"TDIV {tdiv}")

    def set_vdiv(self, channel: int, vdiv: str):
        self.write(f"C{channel}:VDIV {vdiv}")

    def set_offset(self, channel: int, offset: float):
        self.write(f"C{channel}:OFFSET {offset}")

    def set_coupling(self, channel: int, coupling: str):
        # coupling: D1M, A1M, GND
        self.write(f"C{channel}:COUPLING {coupling}")

    def set_channel(self, channel: int, on: bool):
        self.write(f"C{channel}:TRA {'ON' if on else 'OFF'}")

    # ---- Trigger ----
    def set_trigger(self, channel: int, level: float, slope: str, edge_source="SR"):
        # slope: "POS" (yükselen) veya "NEG" (düşen)
        self.write(f"TRSE EDGE,{edge_source},C{channel}")
        self.write(f"C{channel}:TRSL {slope}")
        self.write(f"C{channel}:TRLV {level}V")

    def set_trigger_mode(self, mode: str):
        # mode: RUN, STOP, SINGLE
        self.write(f"TRMD {mode}")

    def get_trigger_mode(self) -> str:
        # cevap: "TRMD AUTO" / "TRMD STOP" / "TRMD SINGLE" (format farkli olabilir)
        resp = self.query("TRMD?").upper()
        if not resp:
            raise ValueError("TRMD? cevabi bos")
        if "SINGLE" in resp:
            return "SINGLE"
        if "STOP" in resp:
            return "STOP"
        if "AUTO" in resp or "RUN" in resp or "TRMD" in resp:
            return "RUN"
        # taninmayan cevap: icerigi loglayip acma
        raise ValueError(f"TRMD? anlasilamadi: {resp!r}")

    def arm(self):
        self.write("ARM")

    def set_default(self):
        self.write("*RST")

    # ---- Measure ----
    def measure(self, channel: int, item: str) -> float:
        resp = self.query(f"C{channel}:PAVA? {item}")
        # cevap formati: "FREQ, 1.000000e+03"
        try:
            return float(resp.split(",")[-1])
        except (ValueError, IndexError):
            return float("nan")

    # ---- Cursor (T3DSO: CRMS / CRST / CRVA?) ----
    # X1/X2 yatay (zaman), Y1/Y2 dikey (gerilim) cursorlari
    # T3DSO2000'te ekrandaki X1 cursori TDIF, X2 TREF ile kontrol ediliyor
    # (CRVA? HREL alan sirasiyla dogrulandi: h[2]=X1=TDIF, h[3]=X2=TREF)
    CURSOR_KEYS = {"X1": "TDIF", "X2": "TREF", "Y1": "VDIF", "Y2": "VREF"}

    def set_cursor_mode(self, mode: str):
        # mode: "MANUAL", "TRACK", "OFF"
        # T3DSO2000 serisi (Format 1): CRMS OFF=manual, CRMS ON=track
        # T3DSO1000 serisi (Format 2): CRMS MANUAL/TRACK/OFF
        fmt1 = {"MANUAL": "OFF", "TRACK": "ON", "OFF": "OFF"}
        self.write(f"CRMS {fmt1.get(mode, mode)}")

    def set_cursor_type(self, ctype: str):
        # ctype: "X", "Y", "X-Y"
        self.write(f"CRTY {ctype}")

    def _parse_unit(self, resp: str) -> float:
        # "C1:VDIV 1.00E+00V" / "-5.20V" / "7.00µs" gibi cevaplari float'a cevirir
        try:
            tok = resp.replace(",", " ").split()[-1]
            return _to_float(tok)
        except (ValueError, IndexError):
            return float("nan")

    def get_vdiv(self, channel: int) -> float:
        resp = self.query(f"C{channel}:VDIV?")
        v = self._parse_unit(resp)
        if v != v:
            raise ValueError(f"V/div okunamadı, cihaz cevabı: '{resp}'")
        return v

    def get_tdiv(self) -> float:
        resp = self.query("TDIV?")
        t = self._parse_unit(resp)
        if t != t:
            raise ValueError(f"Zaman/div okunamadı, cihaz cevabı: '{resp}'")
        return t

    def get_ofst(self, channel: int) -> float:
        resp = self.query(f"C{channel}:OFST?")
        v = self._parse_unit(resp)
        if v != v:
            raise ValueError(f"OFST okunamadı, cihaz cevabı: '{resp}'")
        return v

    def get_cursor_pos(self, channel: int, key: str) -> float:
        # key: TREF/TDIF/VREF/VDIF ; cevap: "C1:CRST VREF,-3.00E+00V"
        resp = self.query(f"C{channel}:CRST? {key}")
        try:
            return self._parse_unit(resp.split(",")[-1])
        except (ValueError, IndexError):
            return float("nan")

    def set_cursor_pos(self, channel: int, key: str, pos: float):
        # TUM cursor anahtarlari div cinsindendir (0..14, ekran ustunden)
        s = f"{max(0.0, min(14.0, pos)):.2f}"
        self.write(f"C{channel}:CRST {key},{s}")

    def set_cursor_pair(self, channel: int, key_a: str, pos_a: float,
                        key_b: str, pos_b: float):
        # Cihaz cursor konumunu cift halinde kabul ediyor:
        # "C1:CRST TREF,x,TDIF,y" / "C1:CRST VREF,x,VDIF,y"
        def s(v):
            return f"{max(0.0, min(14.0, v)):.2f}"
        self.write(f"C{channel}:CRST {key_a},{s(pos_a)},{key_b},{s(pos_b)}")

    def restore_active_cursor(self, channel: int, cursor: str):
        # Ekranda aktif cursor highlight'ini secili cursora geri cevirir:
        # degeri aynen tekrar yazmak cihazda o cursori "aktif" isaretler
        key = self.CURSOR_KEYS[cursor]
        pos = self.get_cursor_pos(channel, key)
        self.set_cursor_pos(channel, key, pos)

    def _query_cursor_raw(self, channel: int, key: str) -> str:
        return self.query(f"C{channel}:CRST? {key}")

    def nudge_cursor(self, channel: int, cursor: str, direction: int, steps: int = 1):
        # cursor: "X1", "X2", "Y1", "Y2"; adim: 0.1 div * steps
        # NOT: CRST T/X anahtarlarinin hepsi div birimindedir; Y icin vdiv ile
        # carpma YOK (cihaz testiyle dogrulandi)
        key = self.CURSOR_KEYS[cursor]
        n = max(1, abs(int(steps)))
        step = 0.1 * n  # div
        resp = self._query_cursor_raw(channel, key)
        pos = self._parse_unit(resp.split(",")[-1])
        if pos != pos:
            raise ValueError(f"Cursor pozisyonu okunamadı ({cursor}), cevap: '{resp}'")
        new = pos + direction * step
        self.set_cursor_pos(channel, key, new)
        return new

    def read_cursor_values(self, channel: int):
        # CRVA? HREL -> "HREL,dT,1/dT,X1,X2" ; VREL -> "VREL,dV,Y1,Y2"
        def parse(resp: str, n: int):
            parts = resp.split(",")[1:]
            vals = [_to_float(p) for p in parts]
            if not vals:
                return [float("nan")] * n
            return vals[-n:]
        h = parse(self.query(f"C{channel}:CRVA? HREL"), 4)  # dT, 1/dT, X1, X2
        v = parse(self.query(f"C{channel}:CRVA? VREL"), 3)  # dV, Y1, Y2
        return {"x1": h[2], "x2": h[3], "dt": h[0],
                "y1": v[1], "y2": v[2], "dv": v[0]}

    # ---- Ekran görüntüsü ----
    def screenshot(self) -> bytes:
        with self._lock:
            try:
                self.instr.chunk_size = 10 * 1024 * 1024
                self.instr.timeout = 10000
                self.instr.write("SCDP\n")
                return self.instr.read_raw()  # USBTMC'de read cihaz hazirlanana kadar bloklar
            except Exception:
                pass
            if self._reopen():
                try:
                    self.instr.chunk_size = 10 * 1024 * 1024
                    self.instr.timeout = 10000
                    self.instr.write("SCDP\n")
                    return self.instr.read_raw()
                except Exception:
                    return b""
        return b""

    # ---- Dalga formu (hizli canli gosterim) ----
    def get_waveform(self, channel: int):
        """(t[s], v[V], vdiv, ofst) dondurur; ~150-200ms surer."""
        with self._lock:
            try:
                instr = self.instr
                instr.chunk_size = 10 * 1024 * 1024
                instr.timeout = 10000

                instr.write(f"C{channel}:WF? DESC")
                hd = instr.read_raw()
                i = hd.find(b"#9")
                if i < 0:
                    raise ValueError(f"WF DESC basligi yok: {hd[:60]!r}")
                hdr = hd[i + 11:i + 11 + 346]
                dt = struct.unpack_from("<f", hdr, 176)[0]  # horiz_interval

                instr.write(f"C{channel}:WF? DAT2")
                d = instr.read_raw()
                i = d.find(b"#9")
                if i < 0:
                    raise ValueError(f"WF DAT2 basligi yok: {d[:60]!r}")
                n = int(d[i + 2:i + 11])
                raw = np.frombuffer(d[i + 12:i + 12 + n], dtype=np.uint8)
                if n == 0 or len(raw) == 0:
                    raise ValueError("WF DAT2 bos dondu (veri alinamadi)")

                def _q(cmd):
                    # lock zaten tutuluyor: instr'a dogrudan yaz
                    try:
                        return instr.query(cmd).strip()
                    except Exception:
                        return ""

                vdiv = float(_q(f"C{channel}:VDIV?").split()[-1].rstrip("V"))
                ofst = float(_q(f"C{channel}:OFST?").split()[-1].rstrip("V"))
            except Exception:
                raise
        volts = (raw.astype(np.float64) - 127.0) / 25.6 * vdiv + ofst
        t = (np.arange(len(raw)) - len(raw) / 2.0) * dt
        return t, volts, vdiv, ofst
