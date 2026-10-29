"""Faux hackrf_transfer / rtl_sdr pour les tests : IQ brut sur stdout (int8 si « -r » = HackRF, sinon uint8),
au rythme réel, avec des micros FM (FAKE_IQ_CARRIERS = « 606.0:1000,607.5:3000 » : MHz:tonalité Hz, déviation
30 kHz) et des signaux intermittents (FAKE_IQ_BURSTS). FAKE_IQ_SECONDS = s'arrête après n secondes (débranché)."""
import os, sys, time
import numpy as np

args = sys.argv[1:]
hackrf = "-r" in args
fc = float(args[args.index("-f") + 1])
fs = float(args[args.index("-s") + 1])
car = []
for x in os.environ.get("FAKE_IQ_CARRIERS", "").split(","):
    if ":" in x:
        f, t = x.split(":")
        car.append((float(f) * 1e6 - fc, float(t)))
stop = float(os.environ.get("FAKE_IQ_SECONDS", "0") or 0)
bursts = []                                  # FAKE_IQ_BURSTS = « 605.2:0.3:1.0 » : MHz, durée allumé (s), période (s)
for x in os.environ.get("FAKE_IQ_BURSTS", "").split(","):
    if x.count(":") == 2:
        f, on, per = x.split(":")
        bursts.append((float(f) * 1e6 - fc, float(on), float(per)))
n = int(fs * 0.02)
rng = np.random.default_rng(2)
t0, k = time.time(), 0
out = sys.stdout.buffer
while True:
    t = (np.arange(n) + k * n) / fs
    x = 0.02 * (rng.normal(size=n) + 1j * rng.normal(size=n))
    for off, tone in car:
        x = x + 0.4 * np.exp(1j * (2 * np.pi * off * t + 30e3 / tone * np.sin(2 * np.pi * tone * t)))
    for off, on, per in bursts:
        m = (t % per) < on
        if m.any():
            x = x + 0.3 * m * np.exp(2j * np.pi * off * t)
    iq = np.empty(2 * n, dtype=np.float32)
    iq[0::2], iq[1::2] = x.real, x.imag
    if hackrf:
        b = np.clip(np.round(iq * 127), -128, 127).astype(np.int8).tobytes()
    else:
        b = np.clip(np.round(iq * 127 + 127.5), 0, 255).astype(np.uint8).tobytes()
    try:
        out.write(b)
        out.flush()
    except (BrokenPipeError, OSError):
        break
    k += 1
    if stop and time.time() - t0 > stop:
        print("hackrf_transfer: USB error (débranché)", file=sys.stderr, flush=True)
        sys.exit(1)
    dt = t0 + k * 0.02 - time.time()
    if dt > 0:
        time.sleep(dt)
