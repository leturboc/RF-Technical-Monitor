"""Faux hackrf_transfer / rtl_sdr pour les tests : IQ brut sur stdout (int8 si « -r » = HackRF, sinon uint8),
au rythme réel, avec des micros FM (FAKE_IQ_CARRIERS = « 606.0:1000,607.5:3000:32768 » : MHz:tonalité Hz[:pilote Hz],
déviation 30 kHz) et des signaux intermittents (FAKE_IQ_BURSTS). FAKE_IQ_SECONDS = s'arrête après n secondes (débranché)."""
import os, sys, time
import numpy as np

args = sys.argv[1:]
if "-t" in args:                             # émission (« hackrf_transfer -t - ») : lit l'IQ int8 et note ce qu'il a reçu
    import json
    fs_t = float(args[args.index("-s") + 1])
    raw = bytearray()
    while True:
        b = sys.stdin.buffer.read(65536)
        if not b:
            break
        if len(raw) < int(fs_t * 0.4) * 2:
            raw += b
        rep = dict(args=args, bytes=len(raw))
    x = np.frombuffer(bytes(raw), dtype=np.int8).astype(np.float32)
    iq = x[0::2] + 1j * x[1::2]
    n = 1 << int(np.log2(max(1024, len(iq) // 2)))
    sp = np.abs(np.fft.fftshift(np.fft.fft(iq[-n:] * np.hanning(n))))
    fr = np.fft.fftshift(np.fft.fftfreq(n, 1.0 / fs_t))
    out = os.environ.get("FAKE_TX_OUT")
    if out:
        with open(out, "w") as fh:
            json.dump(dict(args=args, samples=len(iq), peak_hz=float(fr[int(np.argmax(sp))]),
                           maxabs=float(np.max(np.abs(x))) if len(x) else 0.0), fh)
    sys.exit(0)
hackrf = "-r" in args
fc = float(args[args.index("-f") + 1])
fs = float(args[args.index("-s") + 1])
car = []
for x in os.environ.get("FAKE_IQ_CARRIERS", "").split(","):   # « MHz:tonalité[:pilote Hz] »
    if ":" in x:
        f, t, *pl = x.split(":")
        car.append((float(f) * 1e6 - fc, float(t), float(pl[0]) if pl and pl[0] else 0.0))
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
    for off, tone, pil in car:
        ph = 2 * np.pi * off * t + 30e3 / tone * np.sin(2 * np.pi * tone * t)
        if pil:                                   # pilote (tonalité inaudible) : ±4 kHz de déviation
            ph = ph + 4e3 / pil * np.sin(2 * np.pi * pil * t)
        x = x + 0.4 * np.exp(1j * ph)
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
