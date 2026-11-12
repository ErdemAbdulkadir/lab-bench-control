"""SCDP teshsi: cesitli komut/okuma yontemlerini dener, ilk baytlari yazar."""
import time
import pyvisa

rm = pyvisa.ResourceManager()
res = [r for r in rm.list_resources() if "INSTR" in r]
print("Kaynaklar:", res)
if not res:
    raise SystemExit("Cihaz yok")
instr = rm.open_resource(res[0])
instr.timeout = 10000
instr.chunk_size = 10 * 1024 * 1024
print("IDN:", instr.query("*IDN?").strip())


def try_read_raw(cmd, sleep_ms):
    print(f"\n--- write({cmd!r}), sleep {sleep_ms}ms, read_raw ---")
    try:
        instr.write(cmd)
        time.sleep(sleep_ms / 1000)
        data = instr.read_raw()
        print(f"uzunluk={len(data)}, ilk 16 bayt={data[:16]!r}")
        return data
    except Exception as e:
        print("HATA:", repr(e))
        return b""


def try_read_loop(cmd, sleep_ms):
    # ornek C++ kodu gibi: donguyle oku, timeout'ta veya 0 baytta dur
    print(f"\n--- write({cmd!r}), sleep {sleep_ms}ms, dongulu viRead benzeri okuma ---")
    try:
        instr.write(cmd)
        time.sleep(sleep_ms / 1000)
        buf = b""
        instr.timeout = 500
        while True:
            try:
                part = instr.read_raw()
                if not part:
                    break
                buf += part
                print(f"  +{len(part)} bayt (toplam {len(buf)})")
            except Exception:
                break
        instr.timeout = 10000
        print(f"TOPLAM uzunluk={len(buf)}, ilk 16 bayt={buf[:16]!r}")
        return buf
    except Exception as e:
        print("HATA:", repr(e))
        return b""


b1 = try_read_raw("SCDP\n", 500)
if not b1:
    b1 = try_read_raw("SCDP", 500)
if not b1:
    b1 = try_read_loop("SCDP\n", 500)
if not b1:
    b2 = try_read_raw("SCDP?", 500)
    if not b2:
        b2 = try_read_loop("SCDP?", 500)
        b1 = b2
    else:
        b1 = b2

if b1:
    with open("scdp_debug.bin", "wb") as f:
        f.write(b1)
    print("\nscdp_debug.bin olarak kaydedildi.")
print("\nSTB?", instr.query("*STB?").strip())
