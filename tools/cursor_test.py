# -*- coding: utf-8 -*-
"""
T3DSO2104 cursor diagnostigi (PyVISA).

Kilavuz: T3DSO1000/2000 Programming Guide (tds031000-2000_programming_manual.pdf)
  - CRMS  : CURSOR_MEASURE. T3DSO2000 (Format 1): OFF=manual, ON=track
  - CRTY  : CURSOR_TYPE. X | Y | X-Y (manual modda gosterilecek tip)
  - CRST  : CURSOR_SET. <trace>:CRST <cursor>,<pozisyon>[,...]
  - CRVA? : CURSOR_VALUE?. <trace>:CRVA? HREL|VREL

Kullanim:
  python cursor_test.py [VISA_KAYNAK]
Kaynak verilmezse ilk USB INSTR cihazi kullanilir.
"""
import sys

import pyvisa

# Cihazin kabul ettigi komutlari echo'ladigini gozlemledik
# (CRMS? -> 'CRMS OFF CRMS OFF' = echo + cevap). Echo yoksa komut taninmiyor.
ECHO_CHECK = True


def probe(instr, cmd, timeout_s=1.5):
    """Yaz, sonra CRMS? okuyarak echo'yu kontrol et. Donen: (echo_var_mi, cevap)"""
    old = instr.timeout
    instr.timeout = int(timeout_s * 1000)
    try:
        instr.write(cmd)
        resp = instr.query("CRMS?").strip()
        echoed = cmd.upper() in resp.upper()
        return echoed, resp
    finally:
        instr.timeout = old


def main():
    rm = pyvisa.ResourceManager()
    res = sys.argv[1] if len(sys.argv) > 1 else None
    if res is None:
        usb = [r for r in rm.list_resources() if "INSTR" in r]
        if not usb:
            print("USB INSTR cihazi bulunamadi")
            return
        res = usb[0]
    print(f"Cihaz: {res}")
    instr = rm.open_resource(res)
    instr.timeout = 5000
    instr.write_termination = "\n"
    instr.read_termination = None

    # 0) Kimlik
    print("IDN :", instr.query("*IDN?").strip())

    # 1) Adim 1: manuel cursor modu (T3DSO2000: CRMS OFF = manual)
    instr.write("CRMS OFF")
    print("CRMS? =", instr.query("CRMS?").strip())

    # 2) Adim 2-3: CRTY dene ve echo ile kabul edilip edilmedigini test et
    for t in ("X", "Y", "X-Y"):
        echoed, resp = probe(instr, f"CRTY {t}")
        print(f"CRTY {t:4} -> echo={'VAR' if echoed else 'YOK'} | CRMS? = '{resp}'")

    # CRTY? sorgusu ayri kontrol
    print("CRTY? =", repr(instr.query("CRTY?").strip()))

    # 3) Adim 4: cursor gorunmuyorsa CRST ile konumlandir (kilavuz ornegi):
    #    C1:CRST TREF,-1us,TDIF,2us  -> X1 ve X2'yi -1us ve +2us'a koyar
    instr.write("C1:CRST TREF,-1us,TDIF,2us")
    print("CRST? TREF =", instr.query("C1:CRST? TREF").strip())
    print("CRST? TDIF =", instr.query("C1:CRST? TDIF").strip())
    # Y cursorlari (volt):
    instr.write("C1:CRST VREF,1.0V,VDIF,-1.0V")
    print("CRST? VREF =", instr.query("C1:CRST? VREF").strip())
    print("CRST? VDIF =", instr.query("C1:CRST? VDIF").strip())

    # 4) Adim 6: hata ayirt etme sirasi
    #    a) CRMS?        -> mod kabul edildi mi (echo + 'CRMS OFF/ON')
    #    b) CRTY?        -> tip sorgusu cevap veriyor mu (bos = desteklenmiyor)
    #    c) C1:CRST? ... -> konum kabul edildi mi (okunan = yazilan mi)
    #    d) C1:CRVA? HREL/VREL -> cursor degerleri donuyor mu
    print("CRVA? HREL =", instr.query("C1:CRVA? HREL").strip())
    print("CRVA? VREL =", instr.query("C1:CRVA? VREL").strip())

    instr.close()


if __name__ == "__main__":
    main()
