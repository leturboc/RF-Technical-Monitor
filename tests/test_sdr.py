"""V8 : SDR (HackRF / RTL-SDR) — partie pure + vrai processus (faux hackrf_sweep)."""
import itertools, re, csv, io, math, os, sys, unicodedata, subprocess, time
from collections import deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "..", "tinysa_monitor.py"), encoding="utf-8").read()
a = src.index("# ===== PURE-BEGIN")
b = src.index("# ===== PURE-END")
ns = dict(itertools=itertools, re=re, csv=csv, io=io, math=math, np=np, unicodedata=unicodedata, deque=deque,
          MIN_PTS=51, HYST=3.0, RBW_LIST=[0.3, 1, 3, 10, 30, 100, 300, 600, 850])
exec(src[a:b], ns)
fails = 0


def ok(label, cond, extra=""):
    global fails
    fails += not cond
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra)


psa = ns["parse_sdr_addr"]
ok("adresse : hackrf", psa("hackrf") == ("hackrf", "") and psa(" HackRF:0000abcd ") == ("hackrf", "0000abcd"))
ok("adresse : rtlsdr", psa("rtlsdr:1") == ("rtlsdr", "1") and psa("rtl-sdr") == ("rtlsdr", ""))
ok("adresse : pas un SDR", psa("COM4") is None and psa("192.168.1.20:5025") is None and psa("") is None)
ok("adresse réseau / USB inchangées", ns["parse_device_addr"]("COM4")[0] == "serial")
ok("adresse : SDR reconnu par parse_device_addr", ns["parse_device_addr"]("hackrf") == ("sdr", "hackrf"))

L = "2026-10-28, 20:00:00.123456, 470000000, 475000000, 1000000.00, 20, -80.5, -81.0, -40.25, -79.0, -82.0"
sl = ns["sweep_line"](L)
ok("ligne hackrf_sweep lue", sl is not None and sl[0] == 470e6 and sl[2] == 1e6 and len(sl[3]) == 5
   and sl[3][2] == -40.25, str(sl))
ok("ligne illisible → None", ns["sweep_line"]("hackrf_sweep version 2024") is None
   and ns["sweep_line"]("a, b, c, d, e, f, g") is None)

acc = ns["SweepAccum"]()
def line(lo, vals):
    return f"d, t, {int(lo)}, {int(lo + 1e6 * len(vals))}, 1000000.00, 20, " + ", ".join(str(v) for v in vals)
for lo in (475e6, 470e6):                       # dans le désordre
    acc.feed(ns["sweep_line"](line(lo, [-90] * 5)))
ok("passage en cours : rien de complet", acc.snapshot() is None and acc.passes == 0)
acc.feed(ns["sweep_line"](line(475e6, [-50] * 5)))
F, Lv = acc.snapshot()
ok("passage complet quand un bloc revient", acc.passes == 1 and len(F) == 10 and np.all(np.diff(F) > 0)
   and F[0] == 470.5e6, str(F))

rm = ns["resample_max"]
Fh = np.arange(470e6, 480e6, 10e3) + 5e3
Lh = np.full(len(Fh), -95.0)
Lh[np.argmin(np.abs(Fh - 473.003e6))] = -40.0  # porteuse étroite
r = rm(Fh, Lh, 470e6, 480e6, 101)               # cellules de 100 kHz : la porteuse ne doit pas disparaître
ok("rééchantillonnage : max par cellule (porteuse gardée)", r.max() == -40.0 and np.sum(r == -40.0) == 1, str(r.max()))
ok("rééchantillonnage : la cellule de la porteuse est la bonne", abs(np.linspace(470e6, 480e6, 101)[np.argmax(r)]
                                                                   - 473e6) <= 50e3)
r2 = rm([470e6, 480e6], [-90.0, -70.0], 470e6, 480e6, 11)
ok("rééchantillonnage : interpolation si cases plus larges", abs(r2[5] + 80.0) < 1e-9 and len(r2) == 11, str(r2))
Fd = np.arange(470e6, 471e6, 1e3)
Ld = np.where(np.abs(Fd - 470.9995e6) < 1, -30.0, -100.0)
r3 = rm(Fd, Ld, 470e6, 470.5e6, 51)
ok("rééchantillonnage : rien pris hors de la plage demandée", r3.max() == -100.0, str(r3.max()))

sr = ns["sdr_ranges"]
ok("plages : fusion et MHz entiers", sr([(470.2e6, 520e6), (510e6, 560.5e6), (600e6, 610e6)])
   == [(470, 561), (600, 610)], str(sr([(470.2e6, 520e6), (510e6, 560.5e6), (600e6, 610e6)])))
many = [(f * 1e6, f * 1e6 + 1e6) for f in range(470, 700, 10)]
ok("plages : au plus 10 (les plus proches réunies)", len(sr(many)) == 10)
bands = [dict(start_hz=470e6, stop_hz=520e6, n=2001), dict(start_hz=600e6, stop_hz=610e6, n=101)]
ok("case : pas le plus fin des bandes", ns["sdr_bin_hz"]("hackrf", bands) == 25000.0)
ok("case : RBW fixée", ns["sdr_bin_hz"]("hackrf", bands, 100) == 100000.0)
ok("case : bornée par l'outil", ns["sdr_bin_hz"]("hackrf", bands, 0.3) == 2445.0)
cmd = ns["sdr_cmd"]("hackrf", "hackrf_sweep", [(470, 561), (600, 610)], 25000, 30, 21, True, "abcd")
ok("commande hackrf_sweep", cmd == ["hackrf_sweep", "-f", "470:561", "-f", "600:610", "-w", "25000", "-l", "24",
                                    "-g", "20", "-a", "1", "-d", "abcd"], str(cmd))
cmd = ns["sdr_cmd"]("rtlsdr", "rtl_power", [(470, 561), (600, 610)], 25000, 30)
ok("commande rtl_power", cmd == ["rtl_power", "-f", "470M:610M:25000", "-i", "1", "-g", "30", "-"], str(cmd))

# vrai processus : faux hackrf_sweep → lignes → passages → porteuse retrouvée
env = dict(os.environ, FAKE_SDR_CARRIERS="473.0,605.5")
p = subprocess.Popen(ns["sdr_cmd"]("hackrf", [sys.executable, os.path.join(HERE, "fake_sdr.py")],
                                   [(470, 480), (600, 610)], 25000), stdout=subprocess.PIPE, text=True, env=env)
acc = ns["SweepAccum"]()
t0 = time.time()
while acc.passes < 2 and time.time() - t0 < 20:
    acc.feed(ns["sweep_line"](p.stdout.readline()))
p.kill()
p.wait()
F, Lv = acc.snapshot()
r = rm(F, Lv, 470e6, 480e6, 401)
ok("faux hackrf_sweep : 2 passages lus", acc.passes >= 2)
ok("faux hackrf_sweep : porteuse 473 MHz vue", abs(np.linspace(470e6, 480e6, 401)[np.argmax(r)] - 473e6) <= 30e3
   and r.max() > -50, str(r.max()))

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
