# -*- coding: utf-8 -*-
"""CRST birim testi: tek/çift yazma ve okuma geri dönüşlerini ölçer.
GUI KAPALI olmalı. Ciktiyi tamamen kopyalayip gonder."""
import sys
import pyvisa


def main():
    rm = pyvisa.ResourceManager()
    usb = [r for r in rm.list_resources() if "INSTR" in r]
    if not usb:
        print("USB INSTR bulunamadi")
        return
    instr = rm.open_resource(usb[0])
    instr.timeout = 5000
    print("IDN:", instr.query("*IDN?").strip())

    def q(c):
        try:
            print(f"  {c!r:44} -> {instr.query(c).strip()!r}")
        except Exception as e:
            print(f"  {c!r:44} -> HATA {e}")

    def w(c):
        print(f"  YAZ {c!r}")
        instr.write(c)

    print("\n--- mevcut durum ---")
    q("C1:VDIV?")
    q("C1:OFST?")
    q("TDIV?")
    q("C1:CRST? VREF")
    q("C1:CRST? VDIF")
    q("C1:CRST? TREF")
    q("C1:CRST? TDIF")
    q("C1:CRVA? VREL")
    q("C1:CRVA? HREL")

    print("\n--- TEST 1: TEK yazma VDIF,2.00 (2 div mi 2V mi?) ---")
    w("C1:CRST VDIF,2.00")
    q("C1:CRST? VDIF")
    q("C1:CRVA? VREL")

    print("\n--- TEST 2: CIFT yazma VREF,4.00,VDIF,6.00 ---")
    w("C1:CRST VREF,4.00,VDIF,6.00")
    q("C1:CRST? VREF")
    q("C1:CRST? VDIF")
    q("C1:CRVA? VREL")

    print("\n--- TEST 3: CIFT yazma ters sirayla VDIF,1.00,VREF,3.00 ---")
    w("C1:CRST VDIF,1.00,VREF,3.00")
    q("C1:CRST? VREF")
    q("C1:CRST? VDIF")
    q("C1:CRVA? VREL")

    print("\n--- TEST 4: TEK yazma TDIF,5.00 ---")
    w("C1:CRST TDIF,5.00")
    q("C1:CRST? TDIF")
    q("C1:CRVA? HREL")

    print("\n--- TEST 5: CIFT yazma TREF,2.00,TDIF,8.00 ---")
    w("C1:CRST TREF,2.00,TDIF,8.00")
    q("C1:CRST? TREF")
    q("C1:CRST? TDIF")
    q("C1:CRVA? HREL")

    print("\nOKURKEN EKRAN: Y cursorlari nereye gitti? VREL/VREL degerleri ne?")
    input("Bitirmek icin Enter...")
    instr.close()


if __name__ == "__main__":
    main()
