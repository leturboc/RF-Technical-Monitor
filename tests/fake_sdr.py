"""Faux hackrf_sweep / rtl_power pour les tests : lit -f lo:hi (MHz, plusieurs fois possible) et -w (case Hz),
écrit en boucle des lignes au format hackrf_sweep (blocs de 5 MHz, dans le désordre comme le vrai), avec des
porteuses à -40 dB sur FAKE_SDR_CARRIERS (MHz séparés par des virgules). FAKE_SDR_DIE=n : s'arrête (code 1)
après n passages, comme un HackRF débranché."""
import os, sys, time, random
from datetime import datetime

args = sys.argv[1:]
ranges, w = [], 100000.0
for i, a in enumerate(args):
    if a == "-f":
        lo, hi = args[i + 1].replace("M", "").split(":")[:2]
        ranges.append((float(lo), float(hi)))
    if a == "-w":
        w = float(args[i + 1])
car = [float(x) for x in os.environ.get("FAKE_SDR_CARRIERS", "").split(",") if x.strip()]
die = int(os.environ.get("FAKE_SDR_DIE", "0") or 0)
if not ranges:
    print("hackrf_sweep: pas de plage", file=sys.stderr)
    sys.exit(2)
blocks = []
for lo, hi in ranges:
    f = lo * 1e6
    while f < hi * 1e6:
        blocks.append(f)
        f += 5e6
n = 0
rnd = random.Random(1)
while True:
    order = blocks[1::2] + blocks[0::2]          # le vrai hackrf_sweep n'écrit pas dans l'ordre
    for lo in order:
        nb = max(1, int(5e6 / w))
        lv = []
        for k in range(nb):
            fc = (lo + (k + 0.5) * w) / 1e6
            v = -95 + rnd.gauss(0, 1)
            for c in car:
                if abs(fc - c) <= max(w / 1e6, 0.02):
                    v = -40.0
            lv.append(f"{v:.2f}")
        now = datetime.now()
        sys.stdout.write(f"{now:%Y-%m-%d}, {now:%H:%M:%S.%f}, {int(lo)}, {int(lo + 5e6)}, {w:.2f}, 20, "
                         + ", ".join(lv) + "\n")
    sys.stdout.flush()
    n += 1
    if die and n >= die:
        print("hackrf_sweep: USB transfer error (débranché)", file=sys.stderr)
        sys.exit(1)
    time.sleep(0.05)
