# -*- coding: utf-8 -*-
"""
T3DSO2104 cursor tipi A/B testi (PyVISA, ekranda gozleme dayali).

Kilavuz: T3DSO1000/2000 Programming Guide
  CRMS OFF = manual (T3DSO2000 Format 1)
  CRTY X|Y|X-Y = cursor tipi (manual modda)
  C1:CRST TREF,-1us,TDIF,2us = X1/X2 konumlandir
  C1:CRST VREF,1V,VDIF,-1V = Y1/Y2 konumlandir

Calistir: python cursor_ab_test.py [VISA_KAYNAK]
Cihaz EKRANINI izle; her adimda ne gordugunu not et.
"""
import sys
import time

import pyvisa


def wait_opc(instr):
    """Cihazin islemi bitirmesini bekle (kilavuzda belgeli *OPC?)."""
    return instr.query("*OPC?").strip()


def main():
    rm = pyvisa.ResourceManager()
    res = sys.argv[1] if len(sys.argv) > 1 else None
    if res is None:
        usb = [r for r in rm.list_resources() if "INSTR" in r]
        if not usb:
            print("USB INSTR bulunamadi")
            return
        res = usb[0]
    instr = rm.open_resource(res)
    instr.timeout = 5000
    print("IDN:", instr.query("*IDN?").strip())

    # 0) Temiz baslangic: manual mod + cursorlari ekrana ser
    instr.write("CRMS OFF")
    wait_opc(instr)
    print("CRMS? =", instr.query("CRMS?").strip())

    # 1) X tipi dene: CRST ile X1/X2'yi belirgin sekilde ayir
    instr.write("CRTY X")
    wait_opc(instr)
    instr.write("C1:CRST TREF,-2us,TDIF,2us")
    wait_opc(instr)
    print("CRTY X sonrasi CRTY? =", repr(instr.query("CRTY?").strip()))
    print("  -> EKRAN: sadece 2 dikey cursor (X1/X2) var mi?")
    time.sleep(3)
    print("CRST? TREF =", instr.query("C1:CRST? TREF").strip())
    print("CRST? TDIF =", instr.query("C1:CRST? TDIF").strip())

    # 2) Y tipi dene: Y1/Y2'yi belirgin ayir
    instr.write("CRTY Y")
    wait_opc(instr)
    instr.write("C1:CRST VREF,1.0V,VDIF,-1.0V")
    wait_opc(instr)
    print("CRTY Y sonrasi CRTY? =", repr(instr.query("CRTY?").strip()))
    print("  -> EKRAN: sadece 2 yatay cursor (Y1/Y2) var mi?")
    time.sleep(3)

    # 3) X-Y: hepsi
    instr.write("CRTY X-Y")
    wait_opc(instr)
    print("CRTY X-Y sonrasi CRTY? =", repr(instr.query("CRTY?").strip()))
    print("  -> EKRAN: 4 cursor var mi?")
    time.sleep(3)

    # 4) Sonuc yorumlama
    print("""
YORUM:
- Ekranda cursorlar adimlar arasinda degisiyorsa -> CRTY calisiyor,
  Qt kodundaki tek eksik *OPC? senkronizasyonu olabilir.
- Hicbir adimda ekran degismediyse ve CRTY? hep bossa ->
  firmware CRTY'yi desteklemiyor; SCPI ile tip secilemez.
- CRST? okumalari yazilanla uyusuyorsa konumlandirma calisiyor demektir.
""")
    instr.close()


if __name__ == "__main__":
    main()
