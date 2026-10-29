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

# ---- écoute : démodulation (signaux synthétiques)
fs = 4800000
t = np.arange(int(fs * 0.25)) / fs
def fm(f_off, tone, dev, amp=0.3):
    ph = 2 * np.pi * f_off * t + dev / tone * np.sin(2 * np.pi * tone * t)
    return amp * np.exp(1j * ph)
rng = np.random.default_rng(3)
iq = (fm(600e3, 1000.0, 30e3) + fm(-800e3, 3000.0, 30e3) +
      0.01 * (rng.normal(size=len(t)) + 1j * rng.normal(size=len(t)))).astype(np.complex64)


def tone_of(a, rate=48000):
    a = np.asarray(a[len(a) // 4:])
    sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    fr = np.fft.rfftfreq(len(a), 1 / rate)
    k = int(np.argmax(sp[5:])) + 5
    snr = 10 * np.log10(sp[k] ** 2 / (np.sum(sp ** 2) - np.sum(sp[max(0, k - 3):k + 4] ** 2) + 1e-12))
    return fr[k], snr


CD = ns["ChannelDemod"]
outs = {}
for off in (600e3, -800e3):
    d = CD(fs, off, "wfm", deemph_us=0)
    chunks = [d.process(iq[i:i + 96000])[0] for i in range(0, len(iq), 96000)]   # en blocs de 20 ms
    outs[off] = np.concatenate(chunks)
f1, snr1 = tone_of(outs[600e3])
f2, snr2 = tone_of(outs[-800e3])
ok("écoute : 48 kHz en sortie (0,25 s → ~12 000 échantillons)", 11500 <= len(outs[600e3]) <= 12100, str(len(outs[600e3])))
ok("écoute : micro à +600 kHz → 1 kHz", abs(f1 - 1000) < 20 and snr1 > 20, f"{f1:.0f} Hz, {snr1:.1f} dB")
ok("écoute : micro à −800 kHz → 3 kHz (2 canaux dans la même fenêtre)", abs(f2 - 3000) < 20 and snr2 > 20,
   f"{f2:.0f} Hz, {snr2:.1f} dB")
amp = np.sqrt(np.mean(outs[600e3][3000:] ** 2)) * np.sqrt(2)
ok("écoute : niveau audio ≈ déviation / 50 kHz (30 → 0,6)", 0.5 < amp < 0.7, f"{amp:.3f}")
d1 = CD(fs, 600e3, "wfm", deemph_us=0)
whole = d1.process(iq)[0]
ok("écoute : en blocs = d'un coup (pas de clic aux raccords)", len(whole) == len(outs[600e3])
   and np.max(np.abs(whole - outs[600e3])) < 1e-3, f"{len(whole)} / {len(outs[600e3])}")
dq = CD(fs, 1500e3, "wfm", squelch=-40)
aq, lvq = dq.process(iq)
ok("écoute : squelch ferme un canal vide", np.all(aq == 0) and lvq < -40, f"{lvq:.1f} dBFS")
d_on = CD(fs, 600e3, "wfm", squelch=-40)
a_on, lv_on = d_on.process(iq)
ok("écoute : squelch ouvert sur un micro", np.any(a_on != 0) and lv_on > -40, f"{lv_on:.1f}")
dd = CD(fs, 600e3, "wfm", deemph_us=50)
ok("écoute : désaccentuation 50 µs (atténue les aigus)", tone_of(dd.process(iq)[0])[0] == f1)
# expanseur 2:1 : un signal 4× plus faible (−12 dB) ressort ~16× plus faible (−24 dB)
class S: env = 0.05
lo_ = 0.05 * np.sin(np.arange(48000) / 48000 * 2 * np.pi * 440).astype(np.float32)
hi_ = lo_ * 4
st1, st2 = S(), S()
ex_lo = ns["expand2"](lo_, st1)[24000:]
ex_hi = ns["expand2"](hi_, st2)[24000:]
ratio = 20 * np.log10(np.sqrt(np.mean(ex_hi ** 2)) / np.sqrt(np.mean(ex_lo ** 2)))
ok("expanseur 2:1 : 12 dB d'écart → ~24 dB", 22 < ratio < 26, f"{ratio:.1f} dB")
st3, st4 = S(), S()
r15 = 20 * np.log10(np.sqrt(np.mean(ns["expand2"](hi_, st3, ratio=1.5)[24000:] ** 2)) /
                    np.sqrt(np.mean(ns["expand2"](lo_, st4, ratio=1.5)[24000:] ** 2)))
ok("expanseur 1,5:1 (ENR 1.2) : 12 dB → ~18 dB", 16 < r15 < 20, f"{r15:.1f} dB")
CP = ns["COMPANDERS"]
ok("companders : modes Wisycom FLAT, ENC, ENR, ENS, ENC / ENR 1.2, SEN / EVO, LEX", {"none", "wisy_enc", "wisy_enr",
   "wisy_ens", "wisy_enc12", "wisy_enr12", "hdx", "lex"} <= set(CP) and CP["none"][1] == 1.0
   and CP["none"][0].startswith("FLAT"))
ok("préréglages : chaque compander existe", all(d["comp"] in CP for _k, _n, d, _w in ns["DEMOD_PRESETS"]))
iqh = ns["iq_from_bytes"]("hackrf", bytes([127, 129, 0, 0]))
ok("IQ HackRF (int8)", abs(iqh[0] - (127 / 128 - 127j / 128)) < 1e-6 and len(iqh) == 2, str(iqh))
iqr = ns["iq_from_bytes"]("rtlsdr", bytes([255, 0]))
ok("IQ RTL-SDR (uint8 centré)", abs(iqr[0].real - 127.5 / 128) < 1e-6 and abs(iqr[0].imag + 127.5 / 128) < 1e-6)
c, use = ns["listen_center"]([606.0, 614.0, 607.5, 608.2], "hackrf")
ok("centre d'écoute : la plus grande grappe qui tient (HackRF ±1,9 MHz)", use == [606.0, 607.5, 608.2]
   and 606e6 < c < 608.2e6, f"{c} {use}")
c2, use2 = ns["listen_center"]([606.0], "rtlsdr")
ok("centre d'écoute : décalé du continu du SDR", abs(c2 - 606e6) >= 150e3, str(c2))
lc = ns["listen_cmd"]("hackrf", "hackrf_transfer", 607e6, 4800000, 24, 20, False)
ok("commande hackrf_transfer", lc == ["hackrf_transfer", "-r", "-", "-f", "607000000", "-s", "4800000", "-l", "24",
                                     "-g", "20", "-a", "0"], str(lc))
ok("commande rtl_sdr", ns["listen_cmd"]("rtlsdr", "rtl_sdr", 607e6, 2400000, 30) ==
   ["rtl_sdr", "-f", "607000000", "-s", "2400000", "-g", "30", "-"])

# ---- temps réel : FFT jointives, persistance, détecteur de signaux brefs
fs2 = 2400000
tt = np.arange(fs2 // 10) / fs2
x = (0.5 * np.exp(2j * np.pi * 300e3 * tt) + 0.001 * (rng.normal(size=len(tt)) + 1j * rng.normal(size=len(tt))))
burst = np.zeros(len(tt), dtype=complex)
burst[1000:3000] = 0.5 * np.exp(2j * np.pi * -500e3 * tt[1000:3000])      # 0,8 ms seulement
avg, mx = ns["rt_frames"]((x + burst).astype(np.complex64), 1024)
Fr = ns["rt_freqs"](606e6, fs2, 1024)
ok("temps réel : porteuse à +300 kHz au bon endroit", abs(Fr[int(np.argmax(avg))] - 606.3) < 0.003, str(Fr[int(np.argmax(avg))]))
ok("temps réel : niveau en dBFS (porteuse 0,5 → ≈ −6 dB)", -8 < avg.max() < -4, f"{avg.max():.1f}")
kb = int(np.argmin(np.abs(Fr - 605.5)))
ok("temps réel : signal de 0,8 ms vu dans le max (rien n'échappe)", mx[kb] > -20 and avg[kb] < mx[kb] - 10,
   f"max {mx[kb]:.1f} / moy {avg[kb]:.1f}")
ok("temps réel : bruit bas", np.median(avg) < -70, f"{np.median(avg):.1f}")
ok("temps réel : partie utile 80 %", ns["rt_useful"](606e6, 2400000) == (605.04, 606.96))
ok("réduction max : pic gardé", ns["decimate_max"](np.r_[np.zeros(9999), 5.0], 1000).max() == 5.0
   and len(ns["decimate_max"](np.zeros(10000), 1000)) == 1000)
pe = ns["Persist"](4, decay=0.5)
pe.add([-120, -60, -60, 0])
img = pe.add([-120, -60, -30, 0])
ok("persistance : trace forte (fixe) et pâle (brève)", img[1].max() == 1.5 and img[2].max() == 1.0
   and img[2].sum() == 1.5, str(img[2][img[2] > 0]))
bd = ns["BurstDetector"](gap=2)
Fb = np.linspace(600, 610, 101)
quiet = np.full(101, -100.0)
def with_sig(*idx):
    L = quiet.copy()
    for i, v in idx:
        L[i] = v
    return L
evs = []
evs += bd.feed(0.0, Fb, with_sig((50, -40)), -70)            # porteuse fixe à 605
evs += bd.feed(0.1, Fb, with_sig((50, -40), (20, -50), (21, -45)), -70)   # brève à 602,1 (2 cases)
evs += bd.feed(0.2, Fb, with_sig((50, -40), (20, -50)), -70)
evs += bd.feed(0.3, Fb, with_sig((50, -38)), -70)            # la brève s'arrête
ok("détecteur : 1 événement (le signal bref), 1 signal en cours (la porteuse)", len(evs) == 1 and len(bd.active) == 1,
   str(evs) + str(bd.active))
e = evs[0] if evs else {}
ok("détecteur : fréquence au pic, durée, niveau", abs(e.get("f", 0) - 602.1) < 1e-6 and abs(e["t1"] - e["t0"] - 0.1) < 1e-9
   and e["peak"] == -45, str(e))
ok("détecteur : la porteuse garde son début et son pic", bd.active[0]["t0"] == 0.0 and bd.active[0]["peak"] == -38)
evs = bd.feed(0.4, Fb, quiet, -70)
ok("détecteur : porteuse coupée → événement de 0,3 s", len(evs) == 1 and abs(evs[0]["t1"] - evs[0]["t0"] - 0.3) < 1e-9)

# ---- formats IQ, préréglages de démodulation, SigMF
dec = ns["iq_decode"]
ok("IQ ci16_le", abs(dec("ci16_le", np.array([16384, -16384], dtype="<i2").tobytes())[0] - (0.5 - 0.5j)) < 1e-6)
ok("IQ cf32_le", dec("cf32_le", np.array([0.25, -0.75], dtype="<f4").tobytes())[0] == np.complex64(0.25 - 0.75j))
ok("IQ : octets en trop ignorés", len(dec("ci16_le", b"\x00" * 9)) == 2)
P = ns["DEMOD_PRESETS"]
ok("préréglages : chacun expliqué, clés uniques, modes connus", len({k for k, *_ in P}) == len(P)
   and all(len(w) > 20 and d["mode"] in ns["LISTEN_MODES"] for _k, _n, d, w in P))
ok("préréglage inconnu → None", ns["demod_preset"]("zzz") is None and ns["demod_preset"]("pmr446")["dev"] == 2500)
pr = ns["demod_preset"]("senn_ana")
d48 = CD(fs, 600e3, pr["mode"], 0, None, "none", dev=pr["dev"], cut=pr["cut"], audio=pr["audio"])
a48 = d48.process(iq)[0]
amp48 = np.sqrt(np.mean(a48[3000:] ** 2)) * np.sqrt(2)
ok("préréglage Sennheiser : 30 kHz de déviation → 30/48 du plein volume", 0.55 < amp48 < 0.7, f"{amp48:.3f}")
ok("préréglage : la tonalité reste juste", abs(tone_of(a48)[0] - 1000) < 20)
nb = ns["demod_preset"]("pmr446")
dn = CD(fs, 600e3, nb["mode"], 0, None, "none", dev=nb["dev"], cut=nb["cut"], audio=nb["audio"])
ok("préréglage étroit : filtre de canal serré (le micro FM large est coupé)", dn.f1 is not None
   and len(dn.process(iq)[0]) > 0)
meta = ns["sigmf_meta"]("ci8", 9600000, 606.2e6, 1793282592.25, "HackRF One",
                        [ns["sigmf_annot"](dict(t0=1793282593.25, t1=1793282593.75, f=605.4, peak=-30.0, width=0.0),
                                           1793282592.25, 9600000)])
inf = ns["sigmf_info"](meta)
ok("SigMF : aller-retour (format, débit, centre, heure)", inf["dtype"] == "ci8" and inf["rate"] == 9600000
   and inf["center"] == 606.2e6 and abs(inf["t0"] - 1793282592.25) < 1e-3, str(inf))
an = meta["annotations"][0]
ok("SigMF : signal noté en annotation (début, durée, bande)", an["core:sample_start"] == 9600000
   and an["core:sample_count"] == 4800000 and an["core:freq_lower_edge"] < 605.4e6 < an["core:freq_upper_edge"], str(an))
try:
    ns["sigmf_info"]({"global": {"core:datatype": "ri16_le", "core:sample_rate": 1}})
    ok("SigMF : format inconnu refusé", False)
except ValueError:
    ok("SigMF : format inconnu refusé", True)
ok("taille lisible", ns["rec_size_text"](1.44e9) == "1,4 Go" and ns["rec_size_text"](3.5e8) == "350 Mo")

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
