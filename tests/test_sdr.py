"""V8 : SDR (HackRF / RTL-SDR) — partie pure + vrai processus (faux hackrf_sweep)."""
import itertools, re, csv, io, math, os, sys, unicodedata, subprocess, time
from collections import deque
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = __import__("_src").source()
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
   "wisy_ens", "wisy_enc12", "wisy_enr12", "sen", "evo", "lex"} <= set(CP) and CP["none"]["ratio"] == 1.0
   and CP["none"]["name"].startswith("FLAT"))
ok("FLAT : ni compander ni désaccentuation ; NONE-d75 : 75 µs", CD(fs, 600e3, "wfm", 50.0, None, "none").de is None
   and CD(fs, 600e3, "wfm", 50.0, None, "none_d75").de[0] < CD(fs, 600e3, "wfm", 50.0, None, "none_d50").de[0])
ok("ENC : désaccentuation réduite (pré-accentuation réduite)", CD(fs, 600e3, "wfm", 50.0, None, "wisy_enc").de[0]
   > CD(fs, 600e3, "wfm", 50.0, None, "wisy_enr").de[0])
class S5: env = 0.05
class S6: env = 0.05
q_ = lo_ * 0.05                                     # signal très faible (−26 dB de plus) : sous le genou
r_enr = np.sqrt(np.mean(ns["expand2"](q_, S5(), knee=-30.0, low=1.0)[24000:] ** 2))
r_std = np.sqrt(np.mean(ns["expand2"](q_, S6())[24000:] ** 2))
ok("ENR : sous le genou, le souffle est fermé plus fort", r_enr < r_std / 3, f"{r_enr:.2e} / {r_std:.2e}")
ok("préréglages : chaque compander existe", all(d["comp"] in CP for _k, _n, d, _w in ns["DEMOD_PRESETS"]))
d_enr = CD(fs, 600e3, "wfm", 50.0, None, "wisy_enr")
ok("ENR : marche en blocs (détecteur sans aigus)", len(np.concatenate([d_enr.process(iq[i:i + 96000])[0]
                                                                        for i in range(0, len(iq), 96000)])) > 11000)
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

# ---- tous les modes courants : BLU (USB / LSB), CW, AM, FM stéréo
fs3 = 2400000
t3 = np.arange(int(fs3 * 0.3)) / fs3
noise3 = 0.003 * (rng.normal(size=len(t3)) + 1j * rng.normal(size=len(t3)))
def rms_(a):
    return float(np.sqrt(np.mean(np.asarray(a)[len(a) // 3:] ** 2)))
usb_sig = (0.3 * np.exp(2j * np.pi * (300e3 + 1000) * t3) + noise3).astype(np.complex64)   # USB : tonalité 1 kHz
au = CD(fs3, 300e3, "usb").process(usb_sig)[0]
al = CD(fs3, 300e3, "lsb").process(usb_sig)[0]
ok("BLU haute : tonalité 1 kHz retrouvée", abs(tone_of(au)[0] - 1000) < 20 and tone_of(au)[1] > 15, str(tone_of(au)))
ok("BLU basse sur un signal USB : rejeté (≥ 20 dB plus bas)", rms_(al) < rms_(au) / 10, f"{rms_(al):.4f} / {rms_(au):.4f}")
lsb_sig = (0.3 * np.exp(2j * np.pi * (300e3 - 1500) * t3) + noise3).astype(np.complex64)
al2 = CD(fs3, 300e3, "lsb").process(lsb_sig)[0]
ok("BLU basse : tonalité 1,5 kHz retrouvée", abs(tone_of(al2)[0] - 1500) < 20, str(tone_of(al2)))
cw_sig = (0.3 * np.exp(2j * np.pi * 300e3 * t3) + noise3).astype(np.complex64)
ac = CD(fs3, 300e3, "cw").process(cw_sig)[0]
ok("CW : porteuse → bip à 700 Hz", abs(tone_of(ac)[0] - 700) < 20, str(tone_of(ac)))
am_sig = (0.3 * (1 + 0.6 * np.sin(2 * np.pi * 800 * t3)) * np.exp(2j * np.pi * 300e3 * t3) + noise3).astype(np.complex64)
aa = CD(fs3, 300e3, "am").process(am_sig)[0]
ok("AM : tonalité 800 Hz, niveau réglé par l'AGC", abs(tone_of(aa)[0] - 800) < 20 and 0.05 < rms_(aa) < 0.5,
   f"{tone_of(aa)} {rms_(aa):.3f}")
# FM stéréo : G = 1 kHz, D = 3 kHz, pilote 19 kHz, multiplex standard
Lc, Rc = np.sin(2 * np.pi * 1000 * t3), np.sin(2 * np.pi * 3000 * t3)
mpx = 0.45 * (Lc + Rc) / 2 + 0.1 * np.sin(2 * np.pi * 19000 * t3) + 0.45 * (Lc - Rc) / 2 * np.sin(2 * np.pi * 38000 * t3)
phs = 2 * np.pi * 75000 * np.cumsum(mpx) / fs3
st_sig = (0.3 * np.exp(1j * (2 * np.pi * 300e3 * t3 + phs)) + noise3).astype(np.complex64)
ast = CD(fs3, 300e3, "wfm_st", deemph_us=0).process(st_sig)[0]
ok("FM stéréo : sortie 2 voies", ast.ndim == 2 and ast.shape[1] == 2, str(ast.shape))
def at(a, f, rate=48000):
    a = a[len(a) // 3:]
    sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    fr = np.fft.rfftfreq(len(a), 1 / rate)
    return sp[int(np.argmin(np.abs(fr - f)))]
sepL = 20 * np.log10(at(ast[:, 0], 1000) / at(ast[:, 0], 3000))
sepR = 20 * np.log10(at(ast[:, 1], 3000) / at(ast[:, 1], 1000))
ok("FM stéréo : gauche = 1 kHz, droite = 3 kHz (séparation ≥ 20 dB)", sepL > 20 and sepR > 20, f"{sepL:.1f} / {sepR:.1f} dB")
mono_sig = (0.3 * np.exp(1j * (2 * np.pi * 300e3 * t3 + 2 * np.pi * 75000 * np.cumsum(0.45 * Lc) / fs3)) + noise3)
amo = CD(fs3, 300e3, "wfm_st", deemph_us=0).process(mono_sig.astype(np.complex64))[0]
ok("FM stéréo sans pilote : mono sur les 2 voies", np.allclose(amo[:, 0], amo[:, 1]))
ok("audio : mono → stéréo entrelacé", len(ns["audio_int16"](np.zeros(10))) == 40
   and len(ns["audio_int16"](np.zeros((10, 2)))) == 40)
class S2: env = 0.05
ea = ns["expand2"](hi_, S2(), detector="avg")[24000:]
class S3: env = 0.05
eb = ns["expand2"](lo_, S3(), detector="avg")[24000:]
ok("détecteur moyen (SA572) : aussi 2:1", 22 < 20 * np.log10(np.sqrt(np.mean(ea ** 2)) / np.sqrt(np.mean(eb ** 2))) < 26)
ok("tous les modes ont un nom", all(len(v["name"]) > 5 for v in ns["LISTEN_MODES"].values())
   and {"wfm", "wfm_st", "nfm", "am", "usb", "lsb", "cw"} <= set(ns["LISTEN_MODES"]))

# ---- couleur des modes Wisycom (oreille de Clément) et pilote ultrasonore
def fm_tones(tones, dev=40e3, extra=()):
    m_ = sum(a * np.sin(2 * np.pi * f * t3) for f, a in tones) + sum(a * np.sin(2 * np.pi * f * t3) for f, a in extra)
    return (0.3 * np.exp(1j * (2 * np.pi * 300e3 * t3 + 2 * np.pi * dev * np.cumsum(m_) / fs3)) + noise3).astype(np.complex64)
two = fm_tones([(1000, 0.3), (12000, 0.3)])
def hi_lo(comp):
    a = CD(fs3, 300e3, "wfm", 0, None, comp, dev=40e3, audio=18000).process(two)[0]
    return 20 * np.log10(at(a, 12000) / at(a, 1000))
enc_, ens_, enr_ = hi_lo("wisy_enc"), hi_lo("wisy_ens"), hi_lo("wisy_enr")
ok("ENS : plus d'air que ENC (aigus +3 dB ou plus)", ens_ > enc_ + 3, f"ENS {ens_:.1f} / ENC {enc_:.1f}")
ok("ENR : coupe le haut (12 kHz −6 dB ou plus vs ENC)", enr_ < enc_ - 6, f"ENR {enr_:.1f} / ENC {enc_:.1f}")
dp_ = CD(fs3, 300e3, "wfm")
for i in range(0, len(t3), 48000):
    dp_.process(fm_tones([(1000, 0.3)], extra=[(32768, 0.08)])[i:i + 48000])
ok("pilote 32,768 kHz détecté dans le FM", dp_.pilot is not None and abs(dp_.pilot[0] - 32768) < 100,
   str(dp_.pilot))
dq_ = CD(fs3, 300e3, "wfm")
for i in range(0, len(t3), 48000):
    dq_.process(fm_tones([(1000, 0.3)])[i:i + 48000])
ok("pas de pilote → rien d'annoncé", dq_.pilot is None, str(dq_.pilot))

# SDRplay RSP1B (rx_tools au-dessus de SoapySDR) : commandes construites, format IQ 16 bits
ok("adresse « sdrplay » / « rsp1b:ABC123 »", psa("sdrplay") == ("sdrplay", "") and psa("RSP1B:ABC123") == ("sdrplay", "ABC123"))
ok("rx_power : comme rtl_power + appareil SoapySDR",
   ns["sdr_cmd"]("sdrplay", "rx_power", [(470, 694)], 25000, 40, serial="ABC")
   == ["rx_power", "-f", "470M:694M:25000", "-i", "1", "-g", "40", "-d", "driver=sdrplay,serial=ABC", "-"])
ok("rx_sdr : IQ 16 bits sur la sortie standard",
   ns["listen_cmd"]("sdrplay", "rx_sdr", 607e6, 4800000, 40)
   == ["rx_sdr", "-d", "driver=sdrplay", "-f", "607000000", "-s", "4800000", "-g", "40", "-F", "CS16", "-"])
ok("RSP1B : format ci16_le, 4,8 MS/s en écoute, jusqu'à 9,6 MS/s en temps réel",
   ns["SDR_DTYPE"]["sdrplay"] == "ci16_le" and ns["sdr_iq_rate"]("sdrplay") == 4800000
   and ns["RT_RATES"]["sdrplay"][0] == 9600000)
_x = ns["iq_decode"]("ci16_le", np.array([16384, -16384], dtype="<i2").tobytes())
ok("IQ 16 bits décodé (pleine échelle ≈ 1)", abs(_x[0] - (0.5 - 0.5j)) < 1e-6, str(_x))

# ---- étape 6 : écouter de partout (fenêtres, balayage d'écoute, son pour le téléphone)
lw = ns["listen_windows"]([606.0, 607.5, 620.0, 620.5, 621.0, 606.2], "hackrf")
ok("fenêtres : 2 fenêtres, la plus grosse grappe d'abord", [sorted(u) for _c, u in lw] == [[606.0, 606.2, 607.5], [620.0, 620.5, 621.0]], str(lw))
ok("fenêtres : au plus 4 canaux par fenêtre", all(len(u) <= 4 for _c, u in ns["listen_windows"]([600 + 0.2 * k for k in range(9)], "hackrf")))
ok("fenêtres : toutes les fréquences servies", sorted(f for _c, u in ns["listen_windows"]([600 + 0.2 * k for k in range(9)], "hackrf")
                                                for f in u) == [round(600 + 0.2 * k, 6) for k in range(9)])
ok("fenêtres : rien -> rien", ns["listen_windows"]([], "rtlsdr") == [])
hp = ns["HopState"](dwell=3.0, hang=2.0)
hp.reset(0.0)
ok("balayage : reste tant que rien ne parle avant 3 s", not hp.feed(2.9, False) and hp.feed(3.0, False))
hp.reset(10.0)
ok("balayage : ça parle -> on reste", not hp.feed(11.0, True) and not hp.feed(20.0, True))
ok("balayage : fin de phrase + 2 s -> on passe", not hp.feed(21.5, False) and hp.feed(22.0, False))
st = (np.arange(480) % 2 * 2 - 1).astype("<i2")              # G = -1, D = +1 alternés
ok("son téléphone : 48 kHz stéréo -> 16 kHz mono (1/6 des octets)", len(ns["pcm_mono16k"](st.tobytes())) == len(st.tobytes()) // 6)
tone = (np.stack([np.full(600, 1000), np.full(600, 3000)], axis=1)).astype("<i2").tobytes()
ok("son téléphone : moyenne des deux voies", set(np.frombuffer(ns["pcm_mono16k"](tone), "<i2").tolist()) == {2000})
rg = ns["PcmRing"](rate=16000, keep=1.0)
for k in range(10):
    rg.push(bytes([k]) * 3200)                               # 0,1 s chacun
seq, d = rg.since(0)
ok("anneau : 1re demande = la dernière ½ s seulement", seq == 10 and len(d) == 16000, (seq, len(d)))
ok("anneau : la suite seulement", rg.since(8) == (10, bytes([8]) * 3200 + bytes([9]) * 3200))
ok("anneau : à jour -> rien", rg.since(10) == (10, b""))
ok("anneau : garde ~1 s", sum(len(x) for _s, x in rg.chunks) <= 32000)
pk = ns["pcm_packet"](7, 16000, b"\x01\x00")
ok("paquet : TSMA + n° + fréquence + PCM", pk[:4] == b"TSMA" and np.frombuffer(pk[4:12], "<u4").tolist() == [7, 16000]
   and pk[12:] == b"\x01\x00")
lr = ns["listen_request"]
ok("commande téléphone : écouter", lr(dict(action="start", f="606.1234567")) == dict(action="start", f=606.123457, mode=""))
ok("commande téléphone : arrêter", lr(dict(action="stop")) == dict(action="stop"))
for bad in (dict(action="x"), dict(action="start", f=-3), dict(action="start", f="abc"), dict(action="start", f=float("nan")), [1]):
    try:
        lr(bad)
        ok(f"commande téléphone refusée : {bad}", False)
    except (ValueError, TypeError):
        ok(f"commande téléphone refusée : {bad}", True)

# ---- étape 7 : fiches des SDR, gains par modèle, SoapySDR, WiNRADiO (calculs)
ok("modèles : tous les genres pris en charge ont un modèle par défaut",
   all(ns["sdr_model"](ns["SDR_MODEL_DEFAULT"][k]) for k in ns["SDR_KINDS"]))
ok("modèles : chaque gain a un défaut dans sa plage", all(lo <= d <= hi for m in ns["SDR_MODELS"]
                                                          for _k, _n, lo, hi, _s, d in m["gains"]))
ok("modèles : HackRF 8 bits, RSP1B 14 bits, Airspy 12 bits, G39DDC 16 bits",
   [ns["sdr_model"](k)["bits"] for k in ("hackrf_one", "rsp1b", "airspy_r2", "g39ddc")] == [8, 14, 12, 16])
ok("dynamique : 8 bits ≈ 50 dB, 14 bits ≈ 86 dB", (ns["bits_dynamic"](8), ns["bits_dynamic"](14)) == (49.9, 86.0))
ok("plancher : plus de bits = plus bas", ns["sdr_floor_dbfs"](ns["sdr_model"]("rsp1b"), 4800000)
   < ns["sdr_floor_dbfs"](ns["sdr_model"]("hackrf_one"), 4800000))
ok("modèle choisi par genre (et mauvais choix ignoré)",
   ns["sdr_model_of"]("hackrf", {"hackrf": "hackrf_pro"})["key"] == "hackrf_pro"
   and ns["sdr_model_of"]("hackrf", {"hackrf": "rsp1b"})["key"] == "hackrf_one")
ok("débit : Airspy 10 MS/s (pas multiple de 240 kHz)", ns["sdr_rate"](ns["sdr_model"]("airspy_r2")) == 10000000)
ok("plage : HF+ ne fait pas l'UHF", not ns["sdr_in_range"](ns["sdr_model"]("airspy_hf"), 606.0))
g = ns["sdr_gains_for"](ns["sdr_model"]("hackrf_one"), {"hackrf_one": {"lna": 32}}, {"vga": 30})
ok("gains : valeur du modèle, sinon ancien réglage, sinon défaut", (g["lna"], g["vga"], g["amp"]) == (32, 30, False), str(g))
ok("gains : bornés à la plage du modèle", ns["sdr_gains_for"](ns["sdr_model"]("hackrf_one"), {"hackrf_one": {"lna": 99}})["lna"] == 40)
ce = ns["sdr_cfg_extra"](dict(model="rsp1b", models={"sdrplay": "rspdx", "hackrf": "rsp1b"},
                              gains={"rsp1b": {"lna": "70", "x": 3}, "zz": {}}, offsets={"rsp1b": "12.5", "bad": 1}))
ok("config : relue prudemment", ce == dict(model="rsp1b", models={"sdrplay": "rspdx"}, gains={"rsp1b": {"lna": 60}},
                                           offsets={"rsp1b": 12.5}), str(ce))
ok("fiche lisible", "14 bits" in ns["sdr_model_text"](ns["sdr_model"]("rsp1b")) and "dBm" in
   ns["sdr_model_text"](ns["sdr_model"]("g39ddc")))
for a_, k_ in (("airspy", "airspy"), ("AirspyHF", "airspyhf"), ("lime", "lime"), ("pluto", "pluto"), ("usrp", "uhd"),
               ("bladerf:12", "bladerf"), ("winradio", "winradio"), ("g39ddc:AB12", "winradio"), ("rsp1b", "sdrplay"),
               ("rtl:1", "rtlsdr")):
    ok(f"adresse « {a_} » -> {k_}", psa(a_)[0] == k_, str(psa(a_)))
ok("adresse inconnue -> None", psa("monsdr") is None)
cm = ns["listen_cmd"]("airspy", "rx_sdr", 606e6, 10000000, 14)
ok("Airspy : rx_sdr, driver=airspy, IQ 16 bits", "driver=airspy" in cm and "CS16" in cm, str(cm))
ok("Soapy : balayage par rx_power avec le bon pilote", "driver=uhd" in ns["sdr_cmd"]("uhd", "rx_power", [(470, 480)], 1e5))
ok("IQ 32 bits (WiNRADiO)", abs(ns["iq_decode"]("ci32_le", np.array([2**30, -2**30], dtype="<i4").tobytes())[0]
                                - (0.5 - 0.5j)) < 1e-6)
ok("WiNRADiO : plus petit DDC qui suffit, 16 bits de préférence",
   ns["wr_pick_ddc"]([(0, 250000, 200000, 16), (1, 5000000, 4000000, 32), (2, 5000000, 4000000, 16)], 3e6) == 2)
ok("WiNRADiO : trop large -> le plus large", ns["wr_pick_ddc"]([(0, 250000, 200000, 16), (1, 2500000, 2000000, 16)], 9e6) == 1)
tt = np.arange(65536) / 100e6
x = (8000 * np.cos(2 * np.pi * (25e6 + 300e3) * tt) + np.random.default_rng(3).normal(size=65536)).astype("<i2")
Fw, Lw = ns["wr_snapshot_spectrum"](x, 25e6, 600e6, 2e6, None)
ok("WiNRADiO : instantané -> fréquence RF (front-end + écart à la FI)", abs(Fw[int(np.argmax(Lw))] - 600.3) < 0.02
   and Fw[0] >= 598.99 and Fw[-1] <= 601.01, str(Fw[int(np.argmax(Lw))]))
Fi, Li = ns["wr_snapshot_spectrum"](x, 25e6, 600e6, 2e6, None, inverted=True)
ok("WiNRADiO : spectre inversé (option)", abs(Fi[int(np.argmax(Li))] - 599.7) < 0.02)
R = ns["Resampler"](250000 / 5, 48000)
y = np.concatenate([R(np.sin(np.arange(i, i + 777) * 0.01).astype(np.float32)) for i in range(0, 50000, 777)])
ok("rééchantillonnage : 50 kS/s -> 48 kS/s en flux (longueur)", abs(len(y) - 65 * 777 * 0.96) <= 2, str(len(y)))

# ---- étape 8 : type de signal, mesures, santé d'un micro, enregistrement sur alarme
rg8 = np.random.default_rng(0)
fs8 = 4.8e6
n8 = int(fs8 * 0.5)
t8 = np.arange(n8) / fs8
nz8 = 0.003 * (rg8.normal(size=n8) + 1j * rg8.normal(size=n8))


def sp8(x, nfft=2048):
    avg, _mx = ns["rt_frames"]((x + nz8).astype(np.complex64), nfft)
    return ns["rt_freqs"](600e6, fs8, nfft), avg


def band8(off, bw):
    X = np.fft.fft(rg8.normal(size=n8) + 1j * rg8.normal(size=n8))
    X[np.abs(np.fft.fftfreq(n8, 1 / fs8) - off) > bw / 2] = 0
    y = np.fft.ifft(X)
    return 0.3 * y / np.std(y)


cs = ns["classify_signal"]
F8, L8 = sp8(0.3 * np.exp(1j * (2 * np.pi * 400e3 * t8 + 30e3 / 1000 * np.sin(2 * np.pi * 1000 * t8))))
c8 = cs(F8, L8, 600.4)
ok("type : micro FM analogique (±30 kHz)", c8["kind"] == "fm_ana" and 40 < c8["obw_khz"] < 120, str(c8))
ok("mesure : tient dans un canal de 200 kHz", "✔" in ns["signal_report"](c8))
ok("type : FM étroite (talkie)", cs(*sp8(0.3 * np.exp(1j * (2 * np.pi * -500e3 * t8 + 2.5 * np.sin(2 * np.pi * 1000 * t8))))
                                   , 599.5)["kind"] == "nfm")
ok("type : porteuse pure", cs(*sp8(0.3 * np.exp(2j * np.pi * -1e6 * t8)), 599.0)["kind"] == "cw")
ok("type : plateau numérique 300 kHz", cs(*sp8(band8(800e3, 300e3)), 600.8)["kind"] == "num")
ok("type : pilote 19 kHz = FM stéréo", c8 and cs(F8, L8, 600.4, pilot=(19000.0, 30.0))["kind"] == "fm_st")
ok("type : rien de net (bruit)", cs(*sp8(np.zeros(n8)), 600.0)["kind"] == "none")
wide = cs(*sp8(band8(0, 1.6e6)), 600.0)
ok("mesure : signal large déborde du canal (pas de verdict « tient »)", wide["kind"] in ("wide", "num")
   and "✔" not in ns["signal_report"](wide), str(wide))
mh = ns["mic_health"]
ok("santé : bonne déviation", mh(38.0, 48.0, 0.5)[1] == "ok")
ok("santé : trop chaud", mh(70.0, 48.0, 0.0)[1] in ("warn", "bad") and "chaud" in mh(70.0, 48.0, 0.0)[0])
ok("santé : dérive de 20 kHz = hors fréquence", mh(30.0, 48.0, 20.0)[1] == "bad")
ok("santé : pilote affiché", "pilote 32.0 kHz" in mh(30.0, 48.0, 0.0, (32000.0, 30.0))[0])
ok("santé : pas de mesure", mh(None, 48.0) == ("—", "none"))
pr = ns["PreRing"](1.0, 1000)
for _ in range(30):
    pr.push(b"x" * 100)
ok("tampon d'avant l'alarme : garde ~1 s", 900 <= len(pr.dump()) <= 1100, str(len(pr.dump())))
al = [dict(key=("CONFLIT", 606000), kind="CONFLIT", freq=606.0), dict(key=("ABSENT", 700000), kind="ABSENT", freq=700.0),
      dict(key=("APPAREIL", -1), kind="APPAREIL", freq=0.0), dict(key=("BREF", 605500), kind="CONFLIT", freq=605.5)]
ok("alarmes dans la fenêtre (nouvelles seulement)", [a["key"] for a in ns["alarms_in_window"](al, 605, 607,
                                                                                          {("BREF", 605500)})]
   == [("CONFLIT", 606000)])

# ---- étape 9 : moniteur multicanal (audio, voisins, diagnostic, récepteurs virtuels, historique, performances)
am = ns["AudioMeter"]()
st_ = am.feed(0.5 * np.sin(np.arange(2400) * 0.2), 0.05, True, 0.0)
ok("audio : RMS et crête (sinus 0,5 ≈ −9 / −6 dB)", abs(st_["rms"] + 9.0) < 0.6 and abs(st_["peak"] + 6.0) < 0.3, str(st_))
for k_ in range(30):
    st_ = am.feed(np.zeros(2400), 0.05, True, 1.0 + k_ * 0.05)
ok("audio : silence compté et coupure notée (RF présente)", st_["silent"] >= 1.4 and st_["cuts"] == 1, str(st_))
ok("audio : saturation", ns["AudioMeter"]().feed(np.ones(100), 0.05)["clip"] == 1.0)
Fa = np.linspace(605.0, 607.0, 801)
La = np.full(801, -90.0)
La[np.abs(Fa - 606.0) < 0.03] = -20.0
La[np.abs(Fa - 606.2) < 0.03] = -30.0
inb, lo_, hi_ = ns["adjacent_db"](Fa, La, 606.0)
ok("voisins : canal −20, voisin haut −30 (10 dB de marge)", (inb, lo_, hi_) == (-20.0, -90.0, -30.0), str((inb, lo_, hi_)))
dg = ns["rf_audio_diag"]
ok("diagnostic : RF faible en premier", dg(dict(snr=4, silent=10, rms=-80))[0][0] == "rf_low")
ok("diagnostic : porteuse sans son = mute", dg(dict(snr=30, silent=8, rms=-70))[0][0] == "mute")
ok("diagnostic : saturation", dg(dict(snr=30, clip=0.02, rms=-3))[0][0] == "hot")
ok("diagnostic : voisin fort", dg(dict(snr=30, rms=-20, adj_margin=8))[0][0] == "adj")
ok("diagnostic : RAS", dg(dict(snr=30, rms=-20, silent=0, adj_margin=40, drift=0.5))[0][0] == "ok")
items = [dict(key=k, prio=1) for k in range(10)] + [dict(key=99, prio=2), dict(key=50, alarm=True), dict(key=7, selected=True)]
pl = ns["plan_vrx"](items, 4, 0)
ok("récepteurs virtuels : écouté, alarme, critique d'abord", pl[:3] == [7, 50, 99] and len(pl) == 4, str(pl))
ok("récepteurs virtuels : les autres tournent", ns["plan_vrx"](items, 4, 1)[3] != ns["plan_vrx"](items, 4, 2)[3])
hh = ns["MicHistory"]()
for k_ in range(20):
    hh.add(1000.0 + k_, rf=-40.0, drift=1.0 + 0.1 * (k_ % 3))
ok("historique : un point par seconde", not hh.add(1019.5, rf=0) and len(hh.pts) == 20)
ok("historique : dérive moyenne / écart-type", ns["MicHistory"].drift_stats(hh)["mean"] == 1.1, str(hh.drift_stats()))
ok("performances : pertes et ton", ns["perf_view"](1000, 900, 0.3)[1] == "bad" and ns["perf_view"](1000, 1000, 0.2)[1] == "ok")

# ---------------------------------------------------------------- V8 étape 10 : incidents
ok("tampon IQ : borné par la mémoire", ns["iq_ring_seconds"](19.2e6) < 20 and ns["iq_ring_seconds"](1e6) == 20.0)
AT = ns["AnomalyTracker"]
tk, evs = AT(keep_on=True), []
for i in range(120):                       # 60 s de porteuse stable, puis effondrement
    t = i * 0.5
    evs += tk.feed(t, -40.0, -95.0, 40.0)
for i in range(120, 126):
    evs += tk.feed(i * 0.5, -75.0, -95.0, 40.0)
ok("perturbation : décrochage RF repéré une fois", [e["kind"] for e in evs] == ["drop"] and evs[0]["value"] >= 30, str(evs))
evs = []
for k in range(3):                         # trois décrochages en quelques minutes
    for i in range(40):
        evs += tk.feed(100 + k * 70 + i * 0.5, -40.0, -95.0, 40.0)
    for i in range(6):
        evs += tk.feed(120 + k * 70 + i * 0.5, -75.0, -95.0, 40.0)
ok("perturbation : décrochages répétés", "flaps" in [e["kind"] for e in evs], str(evs))
tk2, ev2 = AT(keep_on=True), []
for i in range(200):
    ev2 += tk2.feed(i * 0.5, -40.0, -95.0 + (12.0 if i >= 180 else 0.0), 40.0)
ok("perturbation : bruit qui monte", [e["kind"] for e in ev2] == ["noise"], str(ev2))
tk3, ev3 = AT(keep_on=False), []
for i in range(30):
    ev3 += tk3.feed(i * 0.5, -95.0 + (30 if i >= 20 else 0), -95.0, None)
ok("perturbation : signal sur une fréquence libre", [e["kind"] for e in ev3] == ["appear"], str(ev3))
tk4, ev4 = AT(), []
for i, m in enumerate([40, 40, 12, 12, 40, 11]):
    ev4 += tk4.feed(i * 0.5, -40.0, -95.0, m, "rf_low" if i == 3 else None)
ok("perturbation : voisin trop fort (1 fois / min) + diagnostic rouge", [e["kind"] for e in ev4] == ["adj", "diag"], str(ev4))
ok("perturbation : texte", ns["anomaly_text"](dict(kind="drop", value=18.2)) == "Décrochage RF : -18 dB"
   and "3 en 10 min" in ns["anomaly_text"](dict(kind="flaps", value=3)))
ok("signaux brefs : seulement les inconnus", [e["f"] for e in ns["unknown_bursts"](
    [dict(f=600.05), dict(f=601.0)], [600.0])] == [601.0])
ok("dossier : nom propre", ns["incident_slug"]("Chant Lead / Élodie") == "Chant-Lead-Elodie")
ok("dossiers : les plus anciens effacés", ns["incident_prune"]([("a", 1, 50), ("b", 2, 50), ("c", 3, 50)], 100) == ["a"])
doc = dict(name="HF 1 <chant>", freq=600.125, t=1000.0, when="24/11/2026 21:00:00", trigger=dict(kind="drop", value=20),
           series=dict(rf=[[990 + i, -40 if i < 10 else -70] for i in range(20)], noise=[[990 + i, -95] for i in range(20)],
                       audio=[[990 + i, -20] for i in range(20)]),
           diag=[("rf_low", "bad", "RF trop faible")], events=[dict(kind="drop", value=20, when="21:00:00")],
           iq=dict(file="iq.sigmf-data", dur=30, rate=4.8e6, center=600e6))
h = ns["incident_report_html"](doc)
ok("rapport d'incident : complet et échappé", "&lt;chant&gt;" in h and h.count("<svg") == 2 and "iq.sigmf-data" in h
   and "stroke='#ff3b30'" in h and "RF trop faible" in h)

# ---------------------------------------------------------------- V8 étape 11 : répétition, comparaison, Shure
rp = ns["RehearsalProfile"]()
for i in range(80):
    rp.learn(dict(key=600125, name="HF1", freq=600.125, snr=30 + (i % 5), noise=-95.0, rf=-60.0,
                  rms=-20.0 if i % 2 else -70.0))
rp.learn(dict(key=601000, name="HF2", freq=601.0, snr=20, noise=-95, rf=-70))
sm = rp.summary()
ok("répétition : seulement les micros assez mesurés", list(sm) == [600125] and sm[600125]["audio_p95"] == -20.0
   and sm[600125]["snr_p10"] == 30.0, str(sm))
ref = sm[600125]
chk = ns["rehearsal_check"]
ok("spectacle : comme en répétition = rien", chk(ref, dict(snr=29, noise=-94, rms=-22)) == [])
ok("spectacle : RF faible, bruit, son trop fort", [x[0] for x in chk(ref, dict(snr=12, noise=-85, rms=-8))]
   == ["reh_rf", "reh_noise", "reh_audio"])
rn = ns["rehearsal_norm"]({"t": 5, "name": "Balances", "mics": {"600125": ref, "x": {}}})
ok("répétition : relue de la config (clés en texte)", list(rn["mics"]) == [600125] and rn["mics"][600125]["snr_p10"] == 30.0)
ok("répétition : config abîmée ignorée", ns["rehearsal_norm"]({"mics": 3}) is None and ns["rehearsal_norm"](None) is None)
ok("réglages SDR : répétition + récepteurs gardés", ns["sdr_cfg_extra"]({"rehearsal": {"mics": {"1": ref}},
   "shure": "10.0.0.5, 10.0.0.6:2300, 10.0.0.5"}).get("shure") == "10.0.0.5, 10.0.0.6:2300")
A = [(t, -60.0 if t not in (20, 21) else -90.0) for t in range(60)]
B = [(t + 0.2, -50.0) for t in range(60)]
cr = ns["compare_receivers"](A, B)
ok("comparaison : décalage et décrochages vus par un seul", cr["offset"] == 10.0 and cr["only_a"] == 2 and cr["only_b"] == 0,
   str(cr))
ok("comparaison : trop peu de mesures", ns["compare_receivers"](A[:5], B) is None)
ok("comparaison : texte", "+10.0 dB" in ns["compare_text"](cr, "SDR", "tinySA") and "SDR : 2" in ns["compare_text"](cr, "SDR", "tinySA"))
ms, rest = ns["shure_split"]("< REP 1 CHAN_NAME {Chant 1   } >< REP 1 FREQUENCY 0578125 >< SAMPLE 1 ALL XB 095 040 >< REP 2")
ok("Shure : messages découpés", len(ms) == 3 and rest == "< REP 2", str((ms, rest)))
stt = {}
for x in ms + ["REP 1 TX_BATT_BARS 004", "REP 2 TX_BATT_BARS 255", "REP 0 MODEL {ULXD4Q}"]:
    ns["shure_apply"](stt, x)
ok("Shure : nom, fréquence, RF, antenne, son, pile", stt[1] == dict(name="Chant 1", freq=578.125, ant="XB", rf=-33,
   audio=-10, batt=4) and stt[2] == dict(batt=None) and 0 not in stt, str(stt))
ok("Shure : commandes d'init", ns["shure_init"](2)[0] == "< GET 0 ALL >" and ns["shure_init"](2)[2] == "< SET 2 METER_RATE 01000 >")
dv = ns["DiversityAB"]()
for a_ in ["AX", "AX", "XB", "AX", "XX"]:
    dv.feed(a_)
ok("diversity A / B : part et bascules", dv.switches == 2 and "A 60 %" in dv.text() and "aucune : 20 %" in dv.text(), dv.text())
ok("Shure : adresses", ns["shure_addrs"]("a.b, 1.2.3.4:99; bad!x") == [("a.b", 2202), ("1.2.3.4", 99)])

# ---------------------------------------------------------------- V8 étape 12 : son et vie privée
pn = ns["privacy_norm"]
ok("vie privée : par défaut rien n'est enregistré, 7 jours", pn(None) == dict(alarm_audio=False, keep_days=7, ack=False))
ok("vie privée : durée inconnue -> 7 jours", pn({"keep_days": 5, "ack": 1})["keep_days"] == 7 and pn({"ack": 1})["ack"] is True)
ok("vie privée : effacement des vieux", ns["retention_pick"]([("a", 0), ("b", 9 * 86400)], 10 * 86400, 7) == ["a"]
   and ns["retention_pick"]([("a", 0)], 1e9, 0) == [])
ok("vie privée : texte de durée", ns["keep_text"](0) == "tout garder" and ns["keep_text"](14) == "14 jours")

# ---------------------------------------------------------------- V8 étape 12 : fondations
ck = ns["AcqClock"](1000.0)
t1 = ck.feed(500, 100.0)
t2 = ck.feed(500, 100.6)
ok("horloge : heure d'après les échantillons, retard mesuré", t1 == 100.0 and abs(t2 - 100.5) < 1e-9 and abs(ck.lag - 0.1) < 1e-9)
t3 = ck.feed(500, 110.0)
ok("horloge : trou de 9 s -> recalage compté", ck.resyncs == 1 and t3 == 110.0 and ck.lag == 0.0)
ok("pertes signalées par l'outil", ns["count_overruns"](["OOOO", "Found 1 device", "overflow!", "U"]) == 2)
ok("récepteurs virtuels auto : d'après la charge", ns["vrx_auto"](0.1, 0.1) == 5 and ns["vrx_auto"](0.7, 0.1) == 1
   and ns["vrx_auto"](0.0, 0.01) == ns["VRX_MAX"] and ns["vrx_auto"](0.2, None) == 4)
cv = ns["capacity_view"](12, 8, 4, 0)
ok("capacité : honnête (rotation, hors fenêtre)", "8 fréquences" in cv[0] and "4 à tour de rôle" in cv[0]
   and "4 HORS" in cv[0] and cv[1] == "warn", cv[0])
ok("capacité : critiques sans récepteur = rouge", ns["capacity_view"](3, 3, 1, 2)[1] == "bad")
dc = ns["device_caps"]("hackrf", ns["sdr_model"]("hackrf_one"))
ok("fiche commune : SDR démodule, tinySA non", dc["iq"] and dc["span"] > 1 and not ns["device_caps"]("")["iq"]
   and "démodule" in ns["caps_text"](dc), str(dc))
rv = ns["resource_view"](dict(lost=6.0, load=0.5, lag=0.1, disk_gb=1.0, vrx=2, vrx_want=4))
ok("santé du système : pertes et disque en rouge", dict((a, c) for a, _b, c in rv)["Échantillons perdus"] == "bad"
   and dict((a, c) for a, _b, c in rv)["Disque libre"] == "bad" and dict((a, c) for a, _b, c in rv)["Récepteurs virtuels"] == "warn")
ok("reconnexion : 3 s puis 10 s puis 30 s", [ns["reconnect_delay"](n) for n in (1, 2, 4)] == [3.0, 10.0, 30.0])

# ---------------------------------------------------------------- V8 étape 12 : compléments de la feuille de route
am2, am3 = ns["AudioMeter"](), ns["AudioMeter"]()
for i in range(100):
    am2.feed(np.full(480, 0.001 if i % 2 else 0.2, dtype=np.float32), 0.05, True, i * 0.05)
    am3.feed(np.full(480, 0.008, dtype=np.float32), 0.05, True, i * 0.05)
st2, st3_ = am2.state(), am3.state()
ok("17. son haché repéré, souffle repéré", st2["chops"] >= 8 and st2["afloor"] < -50 and st3_["afloor"] > -45
   and st3_["chops"] == 0, str((st2, st3_)))
dg2 = ns["rf_audio_diag"](dict(snr=30, afloor=-40, adyn=20, chops=10, obw=260, obw_exp=130, rx_alerts=["Pile"]))
ok("17. / 11. diagnostic : souffle, haché, trop large, alerte récepteur", {"noisy", "chop", "wide", "rx"} <= {x[0] for x in dg2})
ok("17. son continu (musique, tonalité) : pas de faux « souffle »", "noisy" not in {x[0] for x in ns["rf_audio_diag"](
   dict(snr=30, afloor=-8, adyn=st3_["adyn"]))}, str(st3_))
ok("11. largeur attendue d'un micro FM", ns["expected_obw_khz"]("wfm") == 130.0 and ns["expected_obw_khz"]("am") == 200.0)
tk5, ev5 = ns["AnomalyTracker"](), []
for i in range(60):
    ev5 += tk5.feed(i * 0.5, -40.0, -95.0, 40.0, None, 120.0 if i < 50 else 260.0, 130.0, -90.0 if i < 55 else -70.0)
ok("11. / 12. débordement de largeur et voisin qui monte", [e["kind"] for e in ev5] == ["wide", "adj_rise"], str(ev5))
dv2 = ns["DiversityAB"]()
for k in range(400):
    dv2.feed("AX" if k % 50 else "XX", float(k))
ok("15. antenne B jamais utilisée + pertes comptées", dv2.dead() == "B" and len(dv2.losses) >= 7)
al = ns["receiver_alerts"](dict(batt=1, alarms={"RF_INT_DET": "CRITICAL"}), dv2)
ok("14. / 15. alertes du récepteur", len(al) == 4 and "Antenne B" in al[2] and "8 pertes" in al[3], str(al))
st3 = {}
ns["shure_apply"](st3, "REP 1 RF_INT_DET CRITICAL")
ns["shure_apply"](st3, "REP 1 ENCRYPTION_WARNING ON")
ns["shure_apply"](st3, "REP 1 RF_INT_DET NONE")
ok("14. alertes Shure : levées et retombées", st3[1]["alarms"] == {"ENCRYPTION_WARNING": "ON"}, str(st3))
ph = ns["phases_norm"]({"Balance": {"mics": {"1": ref}}, "bad": 3}, {"mics": {"2": ref}})
ok("20. phases : relues, ancienne répétition reprise", sorted(ph) == ["Balance", "Répétition"])
ok("20. phases : tableau micros × phases", ns["phases_table"](ph, [1, 2])[1] == {"Balance": ref["snr_med"], "Répétition": None},
   str(ns["phases_table"](ph, [1, 2])))
ser = [(t_, -40.0 if (t_ < 100 or t_ >= 112) else -80.0) for t_ in range(60, 130)]
ok("18. durée de l'incident", ns["incident_duration"](ser, 100.0) == 12.0 and ns["incident_duration"](ser[:45], 100.0) is None)
Fx = np.linspace(599, 601, 400)
ok("18. capture du spectre en SVG", "<svg" in ns["_svg_iq_spectrum"](Fx, -90 + 30 * (np.abs(Fx - 600) < 0.05), 600.0)
   and "MHz" in ns["_svg_iq_spectrum"](Fx, Fx * 0 - 90, 600.0))
cr2 = ns["compare_receivers"](A, B)
ok("10. comparaison : stabilité de chacun", cr2["std_b"] == 0.0 and cr2["std_a"] > 0
   and "stabilité" in ns["compare_text"](cr2, "SDR", "tinySA"))

ok("diagnostic court pour la colonne", ns["diag_short"]("RF trop faible : risque de décrochage (antenne).") == "RF trop faible"
   and ns["diag_short"]("Fréquence qui dérive (+6 kHz) : pack froid") == "Fréquence qui dérive"
   and ns["anomaly_text"](dict(kind="adj", value=-0.4)) == "Voisin trop fort : 0 dB")

# ---------------------------------------------------------------- V8 étape 13 : récepteurs d'autres marques
ra = ns["receiver_addrs"]("10.0.0.5, g4:10.0.0.6, sennheiser:10.0.0.7:1234; ssc:10.0.0.8, wisycom:10.0.0.9, 10.0.0.5")
ok("récepteurs : marques et ports", ra == [("shure", "10.0.0.5", 2202), ("g4", "10.0.0.6", 53212), ("g4", "10.0.0.7", 1234),
   ("ssc", "10.0.0.8", 45), ("wisycom", "10.0.0.9", 0)], str(ra))
ok("récepteurs : relus de la config à l'identique", ns["receiver_addrs"](ns["receiver_addrs_text"](ra)) == ra
   and ns["receiver_addrs_text"](ra).startswith("10.0.0.5, g4:10.0.0.6"))
g4 = {}
for ln in ["RF1 60", "RF2 75", "AF 40", "Bat 3", "Frequency 556100", "Name HF 1", "Msg RF_Mute", "Bidule 3"]:
    ns["g4_apply"](g4, ln)
ok("Sennheiser G4 : RF A / B, antenne, son, pile, fréquence, nom, alerte", g4[1] == dict(rf_unit="%", rf_a=60.0, rf_b=75.0,
   rf=75.0, ant="XB", audio=40.0, batt=5, freq=556.1, name="HF 1", alarms={"MSG": "RF_Mute"}), str(g4))
ns["g4_apply"](g4, "Msg OK")
ok("Sennheiser G4 : alerte retombée", g4[1]["alarms"] == {})
ssc = {}
ns["ssc_apply"](ssc, {"rx1": {"name": "Chant", "frequency": 606000, "rf1": {"level": -60}, "rf2": {"level": -72},
                              "af": {"level": -20}, "warnings": ["RF low"]}, "mates": {"tx1": {"battery": {"gauge": 70}}}})
ok("Sennheiser SSC : canal lu (JSON)", ssc[1] == dict(name="Chant", freq=606.0, rf_a=-60.0, rf_unit="dBm", rf=-60.0,
   rf_b=-72.0, ant="AX", audio=-20.0, alarms={"W1": "RF low"}, batt=4), str(ssc))
import json as _js
ok("SSC : requêtes JSON valides", all(isinstance(_js.loads(x), dict) for x in ns["ssc_init"]())
   and _js.loads(ns["json_dumps_compact"]({"a": 'x"y\\z', "b": [1, None, True]})) == {"a": 'x"y\\z', "b": [1, None, True]})

# ---------------------------------------------------------------- V8 étape 14 : fiabilité (2ᵉ audit)
fr = ns["freshness"]
ok("1. fraîcheur : en direct / ancienne / perdue / jamais", [fr(1.0), fr(3.0), fr(9.0), fr(None)] == ["live", "stale", "lost", "none"])
ok("1. âge lisible", [ns["age_text"](4.2), ns["age_text"](190), ns["age_text"](7300), ns["age_text"](None)]
   == ["4 s", "3 min", "2 h", "jamais"])
cs = ns["coverage_state"]
ok("2. couverture par micro", [cs(True, True, True, "live"), cs(True, True, False, "live"), cs(True, True, True, "stale"),
   cs(True, True, True, "live", "bad"), cs(True, False, True, "live"), cs(False, True, True, "live")]
   == ["full", "turn", "stale", "degr", "out", "stop"])
ok("2. texte : mesure ancienne avec son âge", ns["coverage_text"]("stale", 12) == "⏸ mesure ancienne (il y a 12 s)")
rows_ = [dict(name="HF1", kind="drop", t=100.0, t_last=100.0), dict(name="HF1", kind="drop", t=50.0, dir="x")]
ok("6. même problème, même micro, < 10 min : regroupé", ns["chron_group"](rows_, "HF1", "drop", 400.0) == 0
   and ns["chron_group"](rows_, "HF1", "drop", 800.0) is None and ns["chron_group"](rows_, "HF2", "drop", 120.0) is None)
ok("4. détection : HackRF vu", ns["probe_seen"]("hackrf", "hackrf_info version: x\nFound HackRF\nIndex: 0")
   == (True, "Found HackRF"))
ok("4. détection : rien de branché", ns["probe_seen"]("rtlsdr", "No supported devices found.")[0] is False
   and "No supported" in ns["probe_seen"]("rtlsdr", "No supported devices found.")[1])
ok("4. débit tenu / pas tenu", ns["probe_rate"](9.6e6 * 2, 2.0, 4.8e6, 2) == (4.8, 1.0)
   and ns["probe_rate"](4.8e6, 2.0, 4.8e6, 2)[1] == 0.25)
lines_, okp = ns["probe_report"]({"tool": (True, "x"), "seen": (True, "Found"), "iq": (True, "1 Mo"), "rate": (False, "lent")})
ok("4. rapport du test", not okp and lines_[0].startswith("✔") and lines_[3].startswith("✗"), str(lines_))
ok("5. consentement précis : mémoire / disque / déclencheurs / où / durée / copies",
   all(x in ns["PRIVACY_TEXT"] for x in ("En mémoire seulement", "Sur le disque", "alarme", "incidents", "copies")))

ok("audit V8 : capacité avant ▶ = sans promesse chiffrée", "le plus possible" in ns["capacity_view"](8, 8, 8, 0, planned=True)[0]
   and "en continu" not in ns["capacity_view"](8, 8, 8, 0, planned=True)[0])

# ---------------------------------------------------------------- V8 étape 16 : le SDR au cœur
ok("S-mètre : S9 = −93 dBm, 6 dB par unité", ns["s_meter"](-93)[0] == "S9" and ns["s_meter"](-105)[0] == "S7"
   and ns["s_meter"](-73)[0] == "S9+20" and ns["s_meter"](None)[0] == "—")
ok("niveaux SDR = ceux de l'appli", [ns["sdr_level"](x) for x in ("ultra", "simple", "expert")] == ["simple", "plus", "expert"])
ok("modes", ns["rf_mode_norm"]("both") == "both" and ns["rf_mode_norm"]("x") == "tiny")
ok("fenêtre : A dedans / dehors ; centre au quart", ns["vfo_inside"](600e6, 4.0, 601.5) and not ns["vfo_inside"](600e6, 4.0, 602.5)
   and ns["vfo_center"](600.0, 4.0) == 599e6)
st_ = ns["station_norm"]({"a": 600.1, "step": 12.5, "nfft": 999, "b_on": 1, "vol": 9})
ok("poste SDR relu de la config", st_["a"] == 600.1 and st_["step"] == 12.5 and st_["nfft"] == 4096 and st_["b_on"] is True
   and st_["vol"] == 0.8)

# ---------------------------------------------------------------- V8 étapes 16 bis / 17 : affichage poste, plusieurs SDR
ok("grande fréquence : texte et crans", ns["freq_digits"](598300000)[0] == "598.300 000"
   and ns["freq_digits"](598300000)[1][:3] == [100000000, 10000000, 1000000] and ns["freq_digits"](598300000)[1][3] == 0
   and ns["freq_digits"](598300000)[1][-1] == 1)
ok("vu-mètre en mots", [ns["level_words"](x)[0] for x in (-100, -85, -70, -40, -10)]
   == ["très faible", "faible", "bon", "fort", "trop fort"] and ns["level_words"](None)[0] == "—")
ok("zones TNT à éviter (marquées à la main ou par le plan)", ns["sdr_zones"]("FR", {"36": "tv", "37": "free"}, [37, 38], 594, 610)
   == [(590.0, 598.0, "TNT 36"), (606.0, 614.0, "TNT 38")])
ok("barre d'état du spectre", "RBW 2.03 kHz" in ns["spectrum_status"](4.8e6, 4096) and "non calé" in ns["spectrum_status"](4.8e6, 4096)
   and "SATURATION" in ns["spectrum_status"](4.8e6, 4096, ovf=0.05, calibrated=True))
ok("micro suivant / précédent", ns["next_mic"]([600.1, 598.3, 602.0], 600.1, 1) == 602.0
   and ns["next_mic"]([600.1, 598.3], 600.1, -1) == 598.3 and ns["next_mic"]([600.1], 600.1, 1) is None)
pp = ns["sdr_posts_norm"]([{"id": 2, "name": "  SDR   B ", "model": "rsp1b", "serial": "x y!", "scenes": ["B", ""]},
                           {"id": 2}, {"id": 9}, "z"])
ok("postes SDR : le 1er toujours là, doublons / hors bornes écartés", [p_["id"] for p_ in pp] == [1, 2]
   and pp[1]["name"] == "SDR B" and pp[1]["serial"] == "xy" and pp[1]["scenes"] == ["B"] and pp[1]["model"] == "rsp1b")
ok("micros d'un poste = ceux de ses scènes", [w["name"] for w in ns["post_watch"]([dict(name="a", scene="A"),
   dict(name="b", scene="B")], ["B"])] == ["b"] and len(ns["post_watch"]([dict(name="a", scene="A")], [])) == 1)
ok("deux postes sur le même SDR repérés", ns["sdr_post_clash"]([(1, "hackrf", ""), (2, "hackrf", "AB")]) == [(1, 2)]
   and ns["sdr_post_clash"]([(1, "hackrf", "A"), (2, "hackrf", "B"), (3, "rtlsdr", "")]) == [])

# ---------------------------------------------------------------- V8 étape 18 : double-clic, pavé numérique
ok("favoris : relus (1…9 seulement)", ns["favs_norm"]({"1": 600100, "2": "x", "10": 5, 3: 598300}) == {1: 600100, 3: 598300})
ok("favoris : une fréquence sur une seule touche", ns["fav_assign"]({1: 600100, 2: 598300}, 3, 600100) == {2: 598300, 3: 600100}
   and ns["fav_assign"]({1: 600100}, 1, None) == {})

# ---------------------------------------------------------------- V8 étape 19 : réglage d'écoute déduit du micro
dg_ = ns["demod_guess"]
ok("écoute déduite : analogiques", [dg_(x) for x in ("EW 300 G4", "Sennheiser évolution", "SK 5212", "Shure UR4D", "SLX",
   "Wisycom MTP40", "Lectrosonics SSM", "PSM 900", "talkie Motorola")] == ["senn_ana", "senn_ana", "senn_pro", "shure_ana",
   "shure_ana", "wisy_ana", "lectro", "iem", "pmr446"])
ok("écoute déduite : numériques repérés (ne s'écoutent pas)", all(dg_(x) == "digital" for x in (
   "ULXD4Q", "Axient AD4D", "QLX-D", "SLX-D", "EW-DX", "EW-D", "EM 6000", "Spectera")))
ok("écoute déduite : rien d'utile = inconnu", dg_("HF 1", "Scène A") is None and dg_() is None)
ok("écoute déduite : tous les préréglages existent", all(ns["demod_preset"](k) is not None for _p, k in ns["DEMOD_RULES"]
   if k != "digital"))

# ---------------------------------------------------------------- V8 étape 20 : patrouille, alarme, pilote, c'est quoi
san_ = ns["sdr_auto_norm"]
ok("réglages auto : défauts", san_(None) == ns["SDR_AUTO_DEFAULT"] and san_({"dwell": 9, "src": "zz"})["dwell"] == 8
   and san_({"dwell": 9})["src"] == "favs" and san_({"tune": 0})["tune"] is False)
pi_ = ns["patrol_items"]
mics_ = [(606000, False), (610000, True), (614000, False), (620000, False)]
ok("patrouille : favoris par fréquence (moins de recentrages), éteint sauté", pi_({3: 606000, 1: 620000, 2: 610000},
   mics_) == [606000, 620000])
ok("patrouille : aucun favori -> tous les micros", pi_({}, mics_) == [606000, 614000, 620000])
ok("patrouille : favori d'un autre SDR ignoré", pi_({1: 999000}, mics_) == [606000, 614000, 620000])
ok("patrouille : « tous » même avec des favoris", pi_({1: 620000}, mics_, "all") == [606000, 614000, 620000])
pn_ = ns["patrol_next"]
ok("patrouille : suivant en boucle", pn_([1, 2, 3], 3) == 1 and pn_([1, 2, 3], 1) == 2 and pn_([1, 2], 9) == 1
   and pn_([], 1) is None)
ap_ = ns["alarm_pick"]
als_ = [dict(id=1, key=("CONFLIT", 606000), kind="CONFLIT", freq=606.0, prio=1, t0=10),
        dict(id=2, key=("ABSENT", 614000), kind="ABSENT", freq=614.0, prio=2, t0=5),
        dict(id=3, key=("APPAREIL", -1), kind="APPAREIL", freq=0, prio=2, t0=20),
        dict(id=4, key=("CONFLIT", 900000), kind="CONFLIT", freq=900.0, prio=2, t0=30)]
ok("alarme à suivre : la plus grave dans la plage", ap_(als_, set(), lambda f: f < 800)["id"] == 2)
ok("alarme à suivre : déjà vue = ignorée", ap_(als_, {2}, lambda f: f < 800)["id"] == 1
   and ap_(als_, {1, 2}, lambda f: f < 800) is None)
pv_ = ns["pilot_verdict"]
ok("pilote : même = c'est ton émetteur", pv_(32768, (32800, 30), True)[0] == "same" and pv_(32768, (32800, 30), True)[2] == "ok")
ok("pilote : autre pilote = autre émetteur ?", pv_(32768, (40000, 30), True)[0] == "other")
ok("pilote : manquant depuis 5 s = alerte, avant = attente", pv_(32768, None, True, 6)[0] == "missing"
   and pv_(32768, None, True, 2)[0] == "wait")
ok("pilote : pas de porteuse = pas jugé ; jamais vu = rien à dire", pv_(32768, None, False)[0] == "off"
   and pv_(None, None, True)[0] == "none" and pv_(None, (32768, 25), True)[0] == "seen")
pl_ = ns["pilot_learn"]
h_, hz_ = pl_(None, (32768, 30), 0.0)
h_, hz_ = pl_(h_, (32790, 30), 2.0)
ok("pilote : pas encore appris avant 3 s", hz_ is None)
h_, hz_ = pl_(h_, (32780, 30), 3.2)
ok("pilote : appris après 3 s stables", hz_ == 32768)
ok("pilote : autre tonalité = on recommence", pl_(dict(hz=32768, t0=0), (40000, 30), 5)[1] is None
   and pl_(dict(hz=32768, t0=0), None, 5) == (None, None))
F20 = np.linspace(600, 610, 4001)
L20 = np.full_like(F20, -100.0)
L20 = np.maximum(L20, -50.0 - 40.0 * ((F20 - 605.0) / 0.05) ** 2)
c20 = ns["classify_signal"](F20, L20, 605.0)
ok("c'est quoi : micro FM sur A", c20["kind"] == "fm_ana" and ns["what_is_text"](c20).startswith("🏷"),
   str(c20["kind"]))
ok("porteuse vue sur le spectre du SDR", ns["sdr_carrier"](F20, L20, 605.0) and not ns["sdr_carrier"](F20, L20, 607.0))
ok("c'est quoi : rien", "Rien" in ns["what_is_text"](dict(kind="none")))

# ---------------------------------------------------------------- V8 étape 21 : générateur (SDR démo + émission)
da_ = ns["demo_audio"]
_t21 = np.arange(48000 * 3) / 48000.0
ok("sons de démo : dans −1…1 et pas muets", all(float(np.max(np.abs(da_(k_, _t21, 2)))) <= 1.0 and
   float(np.sqrt(np.mean(da_(k_, _t21, 2) ** 2))) > 0.02 for k_, _n in ns["DEMO_SOUNDS"]))
ok("programme : allumé / éteint", ns["sched_on"](None, 5) and ns["sched_on"]((10, 3, 0), 2) and not ns["sched_on"]((10, 3, 0), 5))
_g21 = ns["SigGen"](2400000, 606e6, [dict(key="a", kind="cw", f=606.3, lvl=0.0)], noise=0.0)
_b1, _b2 = _g21.block(1000), _g21.block(1000)
_ph = np.unwrap(np.angle(np.concatenate([_b1, _b2])))
ok("générateur : pas de saut de phase entre deux blocs", float(np.max(np.abs(np.diff(np.diff(_ph))))) < 1e-3)
_g21 = ns["SigGen"](2400000, 605.24e6, ns["demo_sdr_plan"]([]))
_x21 = np.concatenate([_g21.block(120000) for _i in range(20)])
_d21 = ns["ChannelDemod"](2400000, 606.2e6 - 605.24e6, "wfm", 50.0, None, None)
_a21, _l21 = _d21.process(_x21)
ok("SDR démo : un micro FM s'écoute (son) et a son pilote", float(np.sqrt(np.mean(np.asarray(_a21) ** 2))) > 0.01
   and _d21.pilot is not None and abs(_d21.pilot[0] - ns["DEMO_PILOT"]) < 300, str(_d21.pilot))
_p21 = ns["demo_sdr_plan"]([dict(f=606.0, name="A", bw=0, free=False, digital=False),
                             dict(f=607.0, name="B", bw=0, free=False, digital=True),
                             dict(f=605.0, name="R", bw=0, free=True, digital=False),
                             dict(f=610.0, name="S", bw=8.0, free=False, digital=False)])
_kinds = {s_["key"][:3]: s_ for s_ in _p21}
ok("plan démo : micro FM, numérique = bloc, réserve = brouilleur intermittent, bloc large, TNT",
   _kinds["mic"]["kind"] == "fm" and _kinds["num"]["kind"] == "noise" and _kinds["jam"].get("on")
   and _kinds["blk"]["bw"] == 8.0 and "tnt" in _kinds)
tp_ = ns["tx_plan"]
_r21 = tp_([dict(f=606.0, kind="fm"), dict(f=607.0, kind="cw")])
ok("émission : centre hors des signaux, débit qui contient tout", not isinstance(_r21, str) and
   all(abs(s_["f"] * 1e6 - _r21[0]) > 1e5 for s_ in _r21[2]) and _r21[1] == 4000000, str(_r21[:2]))
ok("émission : refus clairs", isinstance(tp_([]), str) and isinstance(tp_([dict(f=470.0), dict(f=500.0)]), str)
   and isinstance(tp_([dict(f=7000.0)]), str) and isinstance(tp_([dict(f=606.0 + i) for i in range(9)]), str))
ok("émission : commande hackrf_transfer", ns["tx_cmd"]("hackrf_transfer", 606.95e6, 4000000, 60, True, "ab") ==
   ["hackrf_transfer", "-t", "-", "-f", "606950000", "-s", "4000000", "-x", "47", "-a", "1", "-d", "ab"])
_c8 = np.frombuffer(ns["iq_ci8"](np.array([2.0 + 0j, -2.0j], dtype=np.complex64)), dtype=np.int8)
ok("IQ int8 : ramené sous la pleine échelle", int(np.max(np.abs(_c8.astype(int)))) <= 127 and _c8[0] > 100)

# ---------------------------------------------------------------- étape 21 : sources sonores (générateur, WAV…)
asn_ = ns["audio_spec_norm"]
ok("source sonore : bornes 20 Hz – 20 kHz, ancien nom accepté", asn_(dict(src="tone", f=5))["f"] == 20.0
   and asn_(dict(src="tone", f=99999))["f"] == 20000.0 and asn_("melody")["src"] == "melody" and asn_(None)["src"] == "voice")
_ta = np.arange(48000) / 48000.0
_s1 = ns["demo_audio"](dict(src="tone", f=440), _ta)
_fk = np.fft.rfftfreq(len(_s1), 1 / 48000.0)[int(np.argmax(np.abs(np.fft.rfft(_s1))))]
ok("générateur : la bonne fréquence", abs(_fk - 440) < 2, str(_fk))
_sw = ns["demo_audio"](dict(src="sweep", f1=100, f2=10000, dur=2, log=True), np.arange(96000) / 48000.0)
_seg = _sw[47000:49000]
_fm = np.fft.rfftfreq(len(_seg), 1 / 48000.0)[int(np.argmax(np.abs(np.fft.rfft(_seg * np.hanning(len(_seg))))))]
ok("balayage log : au milieu ≈ moyenne géométrique (1 kHz)", 800 < _fm < 1250, str(_fm))
_pk = ns["demo_audio"](dict(src="pink"), np.arange(2 ** 15) / 48000.0)
_P = np.abs(np.fft.rfft(_pk)) ** 2
_fr = np.fft.rfftfreq(len(_pk), 1 / 48000.0)
ok("bruit rose : plus de graves que d'aigus", _P[(_fr > 100) & (_fr < 200)].mean() > 5 * _P[(_fr > 10000) & (_fr < 20000)].mean())
ok("son de l'appli (alarme) et WAV inconnu = silence", float(np.max(np.abs(ns["demo_audio"](dict(src="app", app="alarm2"),
   _ta)))) > 0.5 and float(np.max(np.abs(ns["demo_audio"](dict(src="wav", path="nope"), _ta)))) == 0.0)
ns["WAV_PCM"]["essai"] = np.linspace(-0.5, 0.5, 4800).astype(np.float32)
ok("WAV : joué en boucle", abs(float(ns["demo_audio"](dict(src="wav", path="essai"), np.array([0.0, 0.1, 0.2]))[1]) -
   float(ns["WAV_PCM"]["essai"][0])) < 1e-6)
asn2_ = ns["alarm_sounds_norm"]
ok("sons des alarmes : clés connues seulement", set(asn2_(dict(alarm2=dict(src="tone", f=800), zzz="x", ok="beep"))) ==
   {"alarm2", "ok"} and asn2_(None) == {})
_ap = ns["alarm_pcm"](dict(src="sweep", f1=200, f2=2000, dur=30))
ok("son d'alarme coupé à 4 s, fondu (pas de clic)", len(_ap) == int(48000 * ns["ALARM_SND_MAX_S"]) and abs(float(_ap[0])) < 1e-3
   and abs(float(_ap[-1])) < 1e-3)
ok("son d'alarme d'origine ré-utilisable", 0.2 < len(ns["alarm_pcm"](dict(src="app", app="alarm2"))) / 48000.0 < 1.0)
ok("texte d'une source", ns["audio_text"](dict(src="sweep", f1=20, f2=20000, dur=10)).startswith("Balayage 20 → 20000"))

# ---------------------------------------------------------------- V8 étape 22 : gain auto, calibration, remonter le temps
gs_ = ns["gain_steps"]
_hk = ns["sdr_model"]("hackrf_one")
ok("gain : étapes du LNA du modèle", gs_(_hk) == [0, 8, 16, 24, 32, 40] and gs_(None) == [])
agp_ = ns["auto_gain_pick"]
_rows = [dict(gain=0, ovf=0, peak=-40), dict(gain=16, ovf=0, peak=-20), dict(gain=24, ovf=0, peak=-8),
         dict(gain=32, ovf=0.01, peak=-0.5)]
ok("gain auto : le plus haut sans saturer avec 6 dB de marge", agp_(_rows)[0] == 24)
ok("gain auto : fort sans écrêter -> le plus bas, « peu de marge »", agp_([dict(gain=0, ovf=0, peak=-2), dict(gain=8, ovf=0,
   peak=-1)])[0] == 0 and "marge" in agp_([dict(gain=0, ovf=0, peak=-2)])[1])
ok("gain auto : tout sature -> le plus bas + conseil", agp_([dict(gain=8, ovf=0.2, peak=0), dict(gain=0, ovf=0.05, peak=0)])
   == (0, "sature même au plus bas : éloigne l'antenne ou ajoute un atténuateur"))
_F = np.linspace(600, 604, 4001)
_Lt = np.full_like(_F, -100.0)
_Ls = np.full_like(_F, -140.0)
for _fc, _p in ((601.0, -50.0), (602.5, -60.0), (603.2, -45.0)):
    _m = np.abs(_F - _fc) < 0.01
    _Lt[_m] = _p
    _Ls[_m] = _p - 40.0 + 0.3                       # SDR : même signal, 40 dB plus bas (dBFS), à 0,3 dB près
_c = ns["calib_candidates"](_F, _Lt, _F, _Ls, rbw_khz=1.0, enbw=1.0)
_o = ns["sdr_tsa_offset"](_c)
ok("calibration : 3 signaux communs, correction ≈ +39,7 dB", len(_c) == 3 and _o and abs(_o["offset"] - 39.7) < 0.2
   and _o["spread"] < 0.2, str((_c, _o)))
ok("calibration : pas assez de signaux = None", ns["sdr_tsa_offset"](_c[:1]) is None)
_rb = ns["RewindBuffer"](1, bytes_per_s=1000)
for _i in range(200):
    _rb.push_frame(_i * 0.5, np.linspace(600, 602, 4096), np.full(4096, -90.0 + (_i % 3)))
    _rb.push_audio(_i * 0.5, b"x" * 500)
    _rb.push_tune(_i * 0.5, 606.2 if _i < 150 else 607.0, "A")
ok("remonter le temps : 1 min gardée, spectres réduits à 1024 cases", 60 <= _rb.span()[1] - _rb.span()[0] <= 61
   and len(_rb.frames[-1][2]) == 1024)
ok("remonter le temps : fréquence de A à un instant", _rb.tune_at(60.0)[0] == 606.2 and _rb.tune_at(99.0)[0] == 607.0)
ok("remonter le temps : son à partir d'un instant", len(_rb.audio_from(90.0, 5.0)) == 5000)
_rb0 = ns["RewindBuffer"](0, bytes_per_s=1000)
_rb0.push_audio(1.0, b"x" * 500)
_rb0.push_frame(1.0, np.linspace(600, 602, 100), np.zeros(100))
ok("remonter le temps : 0 = désactivé, rien gardé", not _rb0.audio and not _rb0.frames and _rb0.span() is None)

# 8.0.2 : plusieurs écrans
_sp = ns["screen_preset"]("tiny_sdr", 0, 1)
ok("écrans : tinySA ici, SDR sur l'autre", _sp["dock_sdr_rx"] == 1 and _sp["dock_spectre"] == 0 and _sp["dock_freq"] == 0)
_sp2 = ns["screen_preset"]("list_out", 1, 0, sdr=False)
ok("écrans : liste sur l'autre, SDR non utilisé = caché", _sp2["dock_freq"] == 0 and _sp2["dock_spectre"] == 1
   and _sp2["dock_sdr_spec"] == -1)
ok("écrans : mode d'après les panneaux", ns["screen_rf_mode"](_sp) == "both"
   and ns["screen_rf_mode"](ns["screen_preset"]("all_here", sdr=False)) == "tiny"
   and ns["screen_rf_mode"]({"dock_sdr_spec": 0, "dock_alarmes": 0}) == "sdr")
ok("écrans utilisés", ns["screens_used"](_sp, 0) == [1] and ns["screens_used"](ns["screen_preset"]("all_here"), 0) == [])
ok("écran débranché : ses panneaux reviennent", ns["screen_plan_fit"]({"a": 2, "b": -1, "c": 1}, 2, 0)
   == {"a": 0, "b": -1, "c": 1})
_sn = ns["screens_norm"]({"on": True, "plan": {"dock_freq": 1, "x": 3, "dock_wf": True, "dock_spectre": -2},
                          "hosts": {"1": {"geo": "abc", "state": 5}, "z": {}}})
ok("écrans : config nettoyée", _sn["on"] and _sn["plan"] == {"dock_freq": 1} and _sn["hosts"] == {"1": {"geo": "abc"}}
   and not ns["screens_norm"]({"on": True})["on"], str(_sn))

# 8.0.2 : micros choisis pour un poste SDR
ok("micros choisis : nettoyés", ns["post_mics_norm"]([600100, "640000", 600100, None, 5, {1}]) == [600100, 640000])
ok("micros choisis : ajouter / retirer", ns["post_mics_set"]([600100], [640000, 600100], True) == [600100, 640000]
   and ns["post_mics_set"]([600100, 640000], [600100], False) == [640000])
_ww = [dict(name="A", freq=600.1, scene="S1"), dict(name="B", freq=640.0, scene="S2"), dict(name="C", freq=470.3, scene="S1")]
ok("micros choisis : remplacent les scènes", [w["name"] for w in ns["post_watch"](_ww, ["S1"], [640000])] == ["B"]
   and [w["name"] for w in ns["post_watch"](_ww, ["S1"], [])] == ["A", "C"])
ok("postes : micros gardés", ns["sdr_posts_norm"]([{"id": 2, "mics": [470300]}])[1]["mics"] == [470300]
   and ns["sdr_posts_norm"]([])[0]["mics"] == [])

# 8.0.3 : démo du tinySA = plan du SDR démo, type de signal par micro
_pl = ns["demo_sdr_plan"]([dict(f=600.0, name="A"), dict(f=610.0, name="B", kind="off"),
                           dict(f=620.0, name="C", free=True, kind="fm"), dict(f=630.0, name="D", kind="digital"),
                           dict(f=640.0, name="E", kind="jam")])
_keys = {s_["key"][:3]: s_ for s_ in _pl}
ok("démo : « rien » = pas de signal, « micro FM » même sur une réserve",
   not any(abs(s_["f"] - 610.0) < 1e-6 for s_ in _pl) and any(abs(s_["f"] - 620.0) < 1e-6 and s_["kind"] == "fm" for s_ in _pl))
ok("démo : numérique = bloc, brouilleur = toujours là",
   any(abs(s_["f"] - 630.0) < 1e-6 and s_["kind"] == "noise" for s_ in _pl)
   and any(abs(s_["f"] - 640.0) < 1e-6 and s_["key"].startswith("jam") and not s_.get("on") for s_ in _pl))
_fr = np.linspace(599.0, 641.0, 4201)
_lv = ns["demo_plan_levels"](_fr, [s_ for s_ in _pl if s_["key"] != "mic600.0000" or True], 30.0)
_at = lambda f: float(np.nanmax(_lv[np.abs(_fr - f) < 0.02])) if np.any(~np.isnan(_lv[np.abs(_fr - f) < 0.02])) else None
ok("démo tinySA : niveaux sur les micros, rien sur l'éteint", _at(620.0) is not None and _at(620.0) > -70
   and _at(610.0) is None and _at(630.0) is not None, f"{_at(620.0)} {_at(610.0)} {_at(630.0)}")

# 8.1 : bruit continu d'un morceau à l'autre (plus de « burst » au rythme de l'affichage)
for _k in ("pink", "white"):
    _sp = ns["audio_spec_norm"](dict(src=_k))
    _full = ns["demo_audio"](_sp, np.arange(48000) / 48000.0, 0)
    _parts = np.concatenate([ns["demo_audio"](_sp, (np.arange(2400) + i * 2400) / 48000.0, 0) for i in range(20)])
    ok(f"bruit {_k} : en morceaux = d'un seul tenant", np.allclose(_full, _parts) and 0.1 < float(np.std(_full)) < 0.4)

ok("8.1 : sortie de l'écoute SDR gardée", ns["sdr_cfg_extra"](dict(audio_dev="__win__")).get("audio_dev") == "__win__")

# 8.1 : échelles de niveau
_ref = ns["audio_ref_norm"]({})
ok("échelles : EBU −18 dBFS = 0 dBu = 0,775 V ; +4 dBu = 0 VU", abs(ns["dbfs_to_unit"](-18, _ref, "dbu")) < 1e-9
   and abs(ns["dbfs_to_unit"](-18, _ref, "vrms") - 0.7746) < 1e-3 and abs(ns["dbfs_to_unit"](-14, _ref, "vu")) < 1e-9)
ok("échelles : SMPTE −20 dBFS = +4 dBu ; dBV = dBu − 2,21", abs(ns["dbfs_to_unit"](-20, dict(align="smpte"), "dbu") - 4) < 1e-9
   and abs(ns["dbfs_to_unit"](-18, _ref, "dbv") + 2.2185) < 1e-6)
ok("échelles : aller-retour", all(abs(ns["unit_to_dbfs"](ns["dbfs_to_unit"](-12.5, _ref, u), _ref, u) + 12.5) < 1e-6
                                  for u, _t in ns["AUDIO_UNITS"]))
_t = np.arange(48000) / 48000.0
_m = ns["audio_meter"](0.5 * np.sin(2 * np.pi * 1000 * _t))
ok("vu-mètre : sinus 0,5 = −6,02 dBFS (RMS AES17 et crête)", abs(_m["rms"] + 6.02) < 0.01 and abs(_m["peak"] + 6.02) < 0.01)
ok("gain vers la cible, limité par la crête", ns["gain_to_target"](-24, -18, -10) == (6.0, False)
   and ns["gain_to_target"](-24, -18, -2)[1])
ok("déviation : −18 dBFS sur 48 kHz max ≈ 6 kHz ; écart à la nominale", abs(ns["fm_deviation"](-18, 48) - 6.04) < 0.01
   and abs(ns["deviation_db"](24, 48) + 6.02) < 0.01)
for _k in ("tone", "sweep", "pink"):
    _x = ns["demo_audio"](ns["audio_spec_norm"](dict(src=_k, lvl=-18)), np.arange(96000) / 48000.0, 0)
    ok(f"niveau visé −18 dBFS : {_k}", abs(ns["audio_meter"](_x)["rms"] + 18) < 0.6, str(ns["audio_meter"](_x)["rms"]))
ok("unités RF : dBW / dBµW", ns["to_unit"](17, "dbw") == -13 and ns["to_unit"](-70, "dbuw") == -40
   and ns["from_unit"](-13, "dbw") == 17)
ok("RF en µV / pW", "µV" in ns["rf_linear_text"](-90) and "pW" in ns["rf_linear_text"](-90))
ok("fiche des échelles : essentiel et options", "dBFS" in ns["scales_help_html"]() and "option" in ns["scales_help_html"]())

_mi, _md, _lb = ns["meter_ticks"](-60, 0, 300)
ok("vu-mètre gradué : 1 dB, valeurs tous les 10 dB sur 300 px", _mi[:2] == [-59, -58] and _lb == list(range(-60, 1, 10))
   and not set(_mi) & set(_md) and not set(_md) & set(_lb))
ok("vu-mètre étroit : graduations moins serrées", ns["meter_ticks"](-120, -20, 120)[2] == [-120, -80, -40])
ok("style du vu-mètre RF gardé (aiguille / barre), valeur bancale ignorée",
   ns["sdr_cfg_extra"](dict(meter_style="bar")).get("meter_style") == "bar"
   and "meter_style" not in ns["sdr_cfg_extra"](dict(meter_style="x")))

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
