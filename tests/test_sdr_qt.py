"""V8 : vrai ScanWorker (PySide6) branché sur un SDR simulé (faux hackrf_sweep) : balayage, porteuse vue,
outil qui s'arrête (SDR débranché) → link False puis reconnexion ; outil introuvable → erreur claire.

    python tests/test_sdr_qt.py
"""
import importlib.util
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="tsm_sdr_")
os.environ["APPDATA"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tsm", os.path.join(HERE, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
from PySide6 import QtCore  # noqa: E402

app = QtCore.QCoreApplication([])
fails = 0


def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra, flush=True)


def wait_until(cond, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


m.ScanWorker.RETRY_S = 1
FAKE = [sys.executable, os.path.join(HERE, "fake_sdr.py")]
cfg = dict(bands=[dict(id=7, name="UHF", start_hz=470e6, stop_hz=480e6, n=401, enabled=True),
                  dict(id=8, name="Haut", start_hz=600e6, stop_hz=610e6, n=201, enabled=True)],
           rbw=None, input="auto", lna=None, att="auto", offset=0.0, seg=290, demo_freqs=[], ver=1)


def run_worker(env, until, timeout, addr="hackrf", tool=FAKE):
    os.environ.update(env)
    ev = dict(sweeps=[], links=[], errors=[], info=[])
    w = m.ScanWorker(addr, False, lambda: cfg, lambda: 1)
    w.sdr_tool = tool
    w.get_sdr = lambda: dict(lna=16, vga=30, amp=False)
    w.sweep.connect(lambda bid, f, l: ev["sweeps"].append((bid, len(l), float(f[l.argmax()]), float(l.max()))))
    w.link.connect(lambda ok: ev["links"].append(ok))
    w.error.connect(lambda msg: ev["errors"].append(msg))
    w.info.connect(lambda t: ev["info"].append(t))
    w.start()
    wait_until(lambda: until(ev), timeout)
    w.requestInterruption()
    w.wait(8000)
    return w, ev


w, ev = run_worker({"FAKE_SDR_CARRIERS": "473.0,605.5", "FAKE_SDR_DIE": "0"},
                   lambda e: len({s[0] for s in e["sweeps"]}) == 2 and len(e["sweeps"]) >= 4, 30)
check("SDR : les deux bandes balayées", {s[0] for s in ev["sweeps"]} == {7, 8}, str(ev))
s7 = [s for s in ev["sweeps"] if s[0] == 7]
s8 = [s for s in ev["sweeps"] if s[0] == 8]
check("SDR : nombre de points demandé (une bande d'un coup)", s7 and s7[0][1] == 401 and s8 and s8[0][1] == 201)
check("SDR : porteuse 473 MHz au bon endroit", s7 and abs(s7[-1][2] - 473.0) <= 0.03 and s7[-1][3] > -50, str(s7[-1:]))
check("SDR : porteuse 605,5 MHz au bon endroit", s8 and abs(s8[-1][2] - 605.5) <= 0.06, str(s8[-1:]))
check("SDR : nom de l'appareil", ev["info"] and "HackRF" in ev["info"][0], str(ev["info"]))
check("SDR : commande avec les gains", any("-l 16" in t and "-g 30" in t for t in w.trace), str(list(w.trace)[:3]))
check("SDR : outil arrêté proprement", w.dev is None)

w, ev = run_worker({"FAKE_SDR_CARRIERS": "473.0", "FAKE_SDR_DIE": "3"},
                   lambda e: False in e["links"] and True in e["links"][e["links"].index(False):]
                   and len(e["sweeps"]) >= 6, 40)
check("SDR débranché : liaison perdue signalée", False in ev["links"], str(ev["links"]))
check("SDR débranché : reconnexion automatique", True in ev["links"], str(ev["links"]))
check("SDR débranché : la raison est notée (diagnostic)", any("débranché" in t for t in w.trace))
check("SDR débranché : pas d'erreur bloquante", not ev["errors"], str(ev["errors"]))

# outil mort ENTRE deux cycles : configure() doit le signaler (avant : relancé en silence, panne invisible)
os.environ.update(FAKE_SDR_DIE="1")
sd = m.SDRSweep("hackrf", tool=FAKE)
sd.configure(cfg["bands"], None, {})
wait_until(lambda: sd.proc.poll() is not None, 20)
try:
    sd.configure(cfg["bands"], None, {})
    _raised = ""
except RuntimeError as e:
    _raised = str(e)
sd.close()
check("outil mort entre deux cycles → panne signalée", "débranché" in _raised, _raised)
os.environ["FAKE_SDR_DIE"] = "0"

_path = os.environ.get("PATH", "")
os.environ["PATH"] = ""                          # aucun hackrf_sweep dans le PATH
w, ev = run_worker({}, lambda e: bool(e["errors"]), 10, tool=None, addr="hackrf:inexistant")
os.environ["PATH"] = _path
check("outil introuvable : erreur claire", ev["errors"] and ("introuvable" in ev["errors"][0]
                                                             or "arrêté" in ev["errors"][0]), str(ev["errors"]))

# ---- écoute : faux hackrf_transfer → ListenWorker → audio 48 kHz
FIQ = [sys.executable, os.path.join(HERE, "fake_iq.py")]


def tone_of(a, rate=48000):
    sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
    return float(np.fft.rfftfreq(len(a), 1 / rate)[int(np.argmax(sp[5:])) + 5])


import numpy as np  # noqa: E402
os.environ.update(FAKE_IQ_CARRIERS="606.0:1000,607.5:3000", FAKE_IQ_SECONDS="0")
c, use = m.listen_center([606.0, 607.5], "hackrf")
lw = m.ListenWorker("hackrf", c, use, "wfm", 50.0, None, "x2", dict(lna=16, vga=20), tool=FIQ)
lev, stop = [], []
lw.levels.connect(lambda v: lev.append(v))
lw.stopped.connect(lambda why: stop.append(why))
lw.start()
wait_until(lambda: len(lw.audio) >= 40, 20)
pcm = b"".join(list(lw.audio))
lw.sel = 1
lw.audio.clear()
wait_until(lambda: len(lw.audio) >= 40, 20)
pcm2 = b"".join(list(lw.audio))
lw.requestInterruption()
lw.wait(8000)
app.processEvents()
a1 = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32000
a2 = np.frombuffer(pcm2, dtype="<i2").astype(np.float32) / 32000
check("écoute : audio reçu (48 kHz, 16 bits)", len(a1) > 30000, str(len(a1)))
check("écoute : canal 1 = micro 606,000 (1 kHz)", abs(tone_of(a1[4800:]) - 1000) < 30, str(tone_of(a1[4800:])))
check("écoute : on bascule sur le canal 2 = 607,500 (3 kHz)", abs(tone_of(a2[4800:]) - 3000) < 30,
      str(tone_of(a2[4800:])))
check("écoute : niveaux des 2 canaux", lev and len(lev[-1]) == 2 and all(x[0] > -30 for x in lev[-1]), str(lev[-1:]))
check("écoute : arrêt demandé = pas d'erreur", stop == [""], str(stop))
check("écoute : outil arrêté", lw.proc is None)
os.environ["FAKE_IQ_SECONDS"] = "1"
lw = m.ListenWorker("rtlsdr", c, use, tool=FIQ)
stop = []
lw.stopped.connect(lambda why: stop.append(why))
lw.start()
wait_until(lambda: bool(stop), 15)
lw.wait(3000)
check("écoute : SDR débranché → arrêt expliqué", stop and "débranché" in stop[0], str(stop))

# pause du balayage pendant l'écoute (le SDR ne fait pas les deux)
os.environ.update(FAKE_SDR_CARRIERS="473.0", FAKE_SDR_DIE="0")
ev = dict(sweeps=[], links=[], errors=[], st=[])
w = m.ScanWorker("hackrf", False, lambda: cfg, lambda: 1)
w.sdr_tool = FAKE
w.sweep.connect(lambda bid, f, l: ev["sweeps"].append(time.time()))
w.link.connect(lambda ok: ev["links"].append(ok))
w.status.connect(lambda t: ev["st"].append(t))
w.start()
wait_until(lambda: len(ev["sweeps"]) >= 2, 20)
w.paused = True
wait_until(lambda: w.dev is None, 10)
time.sleep(0.5)
app.processEvents()
n_p = len(ev["sweeps"])
wait_until(lambda: False, 1.5)
check("pause : l'outil de balayage est arrêté (SDR libre)", w.dev is None)
check("pause : plus de balayage", len(ev["sweeps"]) == n_p, f"{n_p} → {len(ev['sweeps'])}")
check("pause : message clair, pas de « liaison perdue »", any("pause" in t for t in ev["st"]) and not ev["links"],
      str(ev["st"][-2:]) + str(ev["links"]))
w.paused = False
check("reprise après l'écoute", wait_until(lambda: len(ev["sweeps"]) > n_p + 1, 20))
w.requestInterruption()
w.wait(8000)

# ---- temps réel : faux hackrf_transfer avec un micro fixe et un signal intermittent (0,3 s toutes les 1,2 s)
os.environ.update(FAKE_IQ_CARRIERS="606.0:1000", FAKE_IQ_BURSTS="605.4:0.3:1.2", FAKE_IQ_SECONDS="0")
rw = m.RealtimeWorker("hackrf", 606.2e6, 2400000, 2048, tool=FIQ)
rw.thr = -40.0
frames, evs, rstop = [], [], []
rw.frame.connect(lambda fr: frames.append(fr))
rw.events.connect(lambda e: evs.extend(e))
rw.stopped.connect(lambda why: rstop.append(why))
rw.start()
wait_until(lambda: len(evs) >= 2 and len(frames) > 20, 25)
rw.listen = dict(f=606.0, mode="wfm", compander="x2", deemph=50.0, volume=1.0)
wait_until(lambda: len(rw.audio) >= 30, 15)
pcm = b"".join(list(rw.audio))
rw.requestInterruption()
rw.wait(8000)
app.processEvents()
fr = frames[-1] if frames else {}
Fm = np.asarray(fr.get("F", [0]))
check("temps réel : spectre reçu, 20 images / s", len(frames) > 20 and len(Fm) == 2048, str(len(frames)))
check("temps réel : micro fixe à 606,000 vu (FM ±30 kHz)", frames and abs(Fm[int(np.argmax(fr["avg"]))] - 606.0) < 0.05,
      str(Fm[int(np.argmax(fr["avg"]))] if frames else None))
b = [e for e in evs if abs(e["f"] - 605.4) < 0.01]
check("temps réel : signal intermittent noté au journal (fréquence, durée ≈ 0,3 s)", len(b) >= 2
      and all(0.15 <= e["t1"] - e["t0"] <= 0.5 for e in b), str(evs[:3]))
check("temps réel : le micro fixe n'est pas un « événement »", not [e for e in evs if abs(e["f"] - 606.0) < 0.05])
a3 = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32000
check("temps réel : clic = écoute (1 kHz du micro)", len(a3) > 20000 and abs(tone_of(a3[4800:]) - 1000) < 30,
      str(len(a3)))
check("temps réel : charge mesurée", frames and 0 < fr["load"] < 5, str(fr.get("load")))
check("temps réel : arrêt propre", rstop == [""] and rw.proc is None, str(rstop))
os.environ["FAKE_IQ_BURSTS"] = ""

# ---- enregistrement IQ (SigMF) puis relecture
import json  # noqa: E402
os.environ.update(FAKE_IQ_CARRIERS="606.0:1000", FAKE_IQ_BURSTS="605.4:0.3:1.0", FAKE_IQ_SECONDS="0")
rw = m.RealtimeWorker("hackrf", 606.2e6, 2400000, 2048, tool=FIQ)
rw.thr = -40.0
st_r, fr_r = [], []
rw.status.connect(lambda t: st_r.append(t))
rw.frame.connect(lambda fr: fr_r.append(fr))
rw.start()
wait_until(lambda: len(fr_r) > 5, 15)
base = os.path.join(tmp, "iq_test")
rw.start_rec(base)
t_rec = time.time()
wait_until(lambda: time.time() - t_rec > 3.5, 10)
rw.stop_rec()
wait_until(lambda: any("arrêté" in t for t in st_r), 5)
rw.requestInterruption()
rw.wait(8000)
app.processEvents()
data_sz = os.path.getsize(base + ".sigmf-data") if os.path.exists(base + ".sigmf-data") else 0
check("enregistrement : fichier IQ écrit (~3,5 s à 2,4 MS/s ci8 ≈ 17 Mo)", 12e6 < data_sz < 22e6, str(data_sz))
meta = json.load(open(base + ".sigmf-meta", encoding="utf-8"))
info = m.sigmf_info(meta)
check("enregistrement : métadonnées SigMF (ci8, 2,4 MS/s, 606,2 MHz)", info["dtype"] == "ci8" and info["rate"] == 2400000
      and info["center"] == 606.2e6 and info["t0"] is not None, str(info))
check("enregistrement : signaux brefs notés en annotations", any("605.4" in a["core:label"] for a in meta["annotations"]),
      str(meta["annotations"][:2]))
check("enregistrement : indicateur de taille pendant l'enregistrement", any(f.get("rec") for f in fr_r))
info["path"] = base + ".sigmf-data"
pw = m.RealtimeWorker("hackrf", 0, 0, 2048, src=info)
pw.thr = -40.0
pf, pe, ps = [], [], []
pw.frame.connect(lambda fr: pf.append(fr))
pw.events.connect(lambda e: pe.extend(e))
pw.stopped.connect(lambda why: ps.append(why))
pw.listen = dict(f=606.0, volume=1.0, **{k: v for k, v in dict(mode="wfm", compander="x2", deemph=50.0, dev=48000,
                                                                     cut=90000, audio=18000).items()})
pw.start()
t_pl = time.time()
wait_until(lambda: bool(ps), 20)
dt_pl = time.time() - t_pl
app.processEvents()
pcm = b"".join(list(pw.audio))
a4 = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32000
check("relecture : au rythme réel (≈ durée de l'enregistrement)", 2.5 < dt_pl < 8, f"{dt_pl:.1f} s")
check("relecture : position et durée", pf and pf[-1]["dur"] > 3 and pf[-1]["pos"] > 3, str(pf[-1:] and (pf[-1]['pos'], pf[-1]['dur'])))
check("relecture : heure d'origine (pas l'heure actuelle)", pf and abs(pf[0]["t"] - info["t0"]) < 1.0)
check("relecture : signal intermittent retrouvé", any(abs(e["f"] - 605.4) < 0.01 for e in pe), str(pe[:2]))
check("relecture : on réécoute le micro (1 kHz)", len(a4) > 48000 and abs(tone_of(a4[4800:]) - 1000) < 30, str(len(a4)))
check("relecture : fin propre", ps == [""], str(ps))
pw = m.RealtimeWorker("hackrf", 0, 0, 2048, src=info)
pw.speed, pw.seek_to = 4, 2.0
pf, ps = [], []
pw.frame.connect(lambda fr: pf.append(fr))
pw.stopped.connect(lambda why: ps.append(why))
t_pl = time.time()
pw.start()
wait_until(lambda: bool(ps), 20)
dt4 = time.time() - t_pl
app.processEvents()
check("relecture : déplacement (commence à 2 s)", pf and 1.9 <= pf[0]["pos"] <= 2.3, str(pf[0]["pos"] if pf else None))
check("relecture : ×4 plus rapide", dt4 < 1.5, f"{dt4:.2f} s")
os.environ["FAKE_IQ_BURSTS"] = ""

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
