"""V8 étape 14 : tests de RÉSISTANCE du moteur SDR (vrai MultiMonitorWorker, PySide6 sans fenêtre) sur des sources IQ
qui se comportent mal : flux qui se fige sans erreur, flux haché avec des trous, SDR qui meurt, disque plein, rafale
d'incidents, coupure pendant l'écriture, endurance (mémoire bornée), outils SDR tués à la fermeture.

    python tests/test_sdr_stress.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="tsm_stress_")
os.environ["APPDATA"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tsm", os.path.join(HERE, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
import numpy as np  # noqa: E402
from collections import deque  # noqa: E402
from PySide6 import QtCore  # noqa: E402

app = QtCore.QCoreApplication([])
fails = 0
RATE = 960000


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


class FakeSrc:
    """Source IQ ci8 au rythme réel : une porteuse FM ; `plan` = liste de (secondes, comportement) :
    « ok », « freeze » (read bloque sans erreur jusqu'à close), « gap » (rien pendant n s puis reprise, le temps
    perdu n'est pas rattrapé), « die » (fin du flux avec une erreur)."""

    def __init__(self, plan, rate=RATE):
        self.rate, self.dtype, self.err = rate, "ci8", deque(maxlen=20)
        self.plan, self.t0, self.closed = list(plan), time.time(), threading.Event()
        self.ph, self.sent = 0.0, 0

    def _mode(self):
        el = time.time() - self.t0
        for dur, mode in self.plan:
            if el < dur:
                return mode, el
            el -= dur
        return "ok", 0.0

    def read(self, n):
        if self.closed.is_set():
            return b""
        mode, _el = self._mode()
        if mode == "freeze":
            self.closed.wait()                      # l'outil ne rend plus rien, sans erreur
            return b""
        if mode == "die":
            self.err.append("usb_bulk_transfer: LIBUSB_ERROR_NO_DEVICE")
            return b""
        if mode == "gap":
            time.sleep(0.05)
            return self.read_after_gap(n)
        k = max(2, min(n, int(self.rate * 2 * 0.05)) // 2)
        time.sleep(k / self.rate)
        t = (np.arange(k) + self.sent) / self.rate
        self.sent += k
        ph = 2 * np.pi * (100e3 * t + 30e3 / 1e3 * np.sin(2 * np.pi * 1e3 * t))
        iq = (np.exp(1j * ph) * 0.5 + (np.random.randn(k) + 1j * np.random.randn(k)) * 0.01)
        out = np.empty(2 * k, dtype=np.int8)
        out[0::2] = np.clip(iq.real * 127, -127, 127)
        out[1::2] = np.clip(iq.imag * 127, -127, 127)
        return out.tobytes()

    def read_after_gap(self, n):
        while self._mode()[0] == "gap" and not self.closed.is_set():
            time.sleep(0.05)
        return self.read(n)

    def close(self):
        self.closed.set()


def run_worker(src, chans=None, secs=None, until=None):
    m.open_iq_source = lambda *a, **k: src
    w = m.MultiMonitorWorker("hackrf", 600e6, RATE, chans or [dict(key=600100, name="HF1", freq=600.1, prio=2,
                                                                    keep_on=True)])
    got = dict(stats=0, perf=None, stopped=None, inc=[])
    w.stats.connect(lambda r: got.__setitem__("stats", got["stats"] + 1))
    w.perf.connect(lambda p: got.__setitem__("perf", p))
    w.stopped.connect(lambda why: got.__setitem__("stopped", why))
    w.incident.connect(lambda r: got["inc"].append(r))
    w.start()
    if until is not None:
        wait_until(lambda: until(w, got), secs or 15)
    elif secs:
        wait_until(lambda: False, secs)
    return w, got


def stop(w, got):
    w.requestInterruption()
    w.force_close()
    wait_until(lambda: not w.isRunning(), 6)
    wait_until(lambda: False, 0.3)


# 1. flux figé : des données, puis plus rien SANS erreur -> le chien de garde coupe, la boucle se termine
src = FakeSrc([(1.5, "ok"), (999, "freeze")])
w, got = run_worker(src, until=lambda w, g: g["stats"] >= 2, secs=8)
n0 = got["stats"]
wait_until(lambda: False, 2.0)
check("flux figé : plus aucune mesure n'arrive (le moniteur le voit)", got["stats"] - n0 <= 1, str((n0, got["stats"])))
w.force_close()
check("flux figé : couper la source libère la lecture bloquée", wait_until(lambda: not w.isRunning(), 5))
check("flux figé : raison claire donnée", got["stopped"] and "figé" in got["stopped"], str(got["stopped"]))

# 2. SDR qui meurt : fin du flux avec erreur -> arrêt rapide, erreur de l'outil dans la raison
src = FakeSrc([(1.0, "ok"), (999, "die")])
w, got = run_worker(src, until=lambda w, g: g["stopped"] is not None, secs=8)
check("SDR débranché : arrêt avec l'erreur de l'outil", got["stopped"] and "LIBUSB" in got["stopped"], str(got["stopped"]))

# 3. flux haché : un trou de 3 s -> horloge recalée (comptée), les mesures reprennent, pas d'exception
src = FakeSrc([(2.0, "ok"), (3.0, "gap"), (999, "ok")])
w, got = run_worker(src, secs=7.5)
check("flux haché : les mesures reprennent après le trou", got["stats"] >= 8 and w.isRunning(), str(got["stats"]))
check("flux haché : trou vu par l'horloge (recalage compté)", w.clock.resyncs >= 1, str(w.clock.resyncs))
stop(w, got)

# 4. rafale d'incidents + disque plein + écriture sûre
inc_dir = os.path.join(tmp, "incidents")
src = FakeSrc([(999, "ok")])
w, got = run_worker(src, until=lambda w, g: g["stats"] >= 4, secs=8)
for k in range(5):
    w.inc_req.append(dict(key=600100, name="HF1", freq=600.1, trigger=dict(kind="manual", t=time.time()), t=time.time(),
                          dir=os.path.join(inc_dir, f"inc{k}")))
wait_until(lambda: len(got["inc"]) >= 5, 20)
main = [r for r in got["inc"] if not r["iq"].get("same")]
same = [r for r in got["inc"] if r["iq"].get("same")]
check("rafale de 5 incidents : un seul IQ écrit, 4 rangés avec lui", len(main) == 1 and len(same) == 4
      and all(r["iq"]["same"] == main[0]["req"]["dir"] for r in same), str([r["iq"] for r in got["inc"]]))
d0 = main[0]["req"]["dir"] if main else ""
check("incident : IQ complet (data puis meta), aucun .part restant",
      os.path.isfile(os.path.join(d0, "iq.sigmf-data")) and os.path.isfile(os.path.join(d0, "iq.sigmf-meta"))
      and not [f for f in os.listdir(d0) if f.endswith(".part")], str(os.listdir(d0) if d0 else []))
real_du = m.shutil.disk_usage
m.shutil.disk_usage = lambda p: real_du(p)._replace(free=10 ** 6)          # il ne reste qu'1 Mo
got["inc"].clear()
w.inc_req.append(dict(key=600100, name="HF1", freq=600.1, trigger=dict(kind="manual", t=time.time()), t=time.time(),
                      dir=os.path.join(inc_dir, "plein")))
wait_until(lambda: got["inc"], 20)
m.shutil.disk_usage = real_du
check("disque presque plein : incident gardé SANS IQ, raison dite", got["inc"] and not got["inc"][0]["iq"].get("file")
      and "disque" in got["inc"][0]["iq"].get("why", ""), str(got["inc"][:1]))
stop(w, got)

# 4 bis. audit V8 : l'incident n'est plus recollé en mémoire (morceaux écrits un par un, mémoire rendue)
pend_ = dict(req=dict(dir=os.path.join(inc_dir, "morceaux"), t=time.time(), name="HF1"), pre=[b"\1\2" * 50000] * 4,
             post=[b"\3\4" * 50000] * 2, also=[], merged=[], t0=time.time() - 1)
res_ = []
w2 = m.MultiMonitorWorker("hackrf", 600e6, RATE, [])
w2.incident.connect(lambda r: res_.append(r))
w2._inc_write(pend_, "ci8", 600e6, "test")
wait_until(lambda: res_, 10)
f_ = os.path.join(inc_dir, "morceaux", "iq.sigmf-data")
check("incident écrit morceau par morceau (taille exacte, mémoire rendue)", res_ and os.path.getsize(f_) == 6 * 100000
      and pend_["pre"] == [] and pend_["post"] == [] and open(f_, "rb").read(2) == b"\1\2", str(res_[:1]))

# 4 ter. audit V8 : « Tester mon SDR » ne reste jamais bloqué sur un outil figé
m.SDR_PROBE_RUNNER = lambda argv: (0, "Found HackRF")
m.open_iq_source = lambda *a, **k: FakeSrc([(0.3, "ok"), (999, "freeze")])
t_ = time.time()
r_ = m.sdr_probe("hackrf", m.sdr_model("hackrf_one"), {}, "", secs=1.0)
m.SDR_PROBE_RUNNER = None
check("test du SDR : outil figé -> le test se termine quand même (< 10 s)", time.time() - t_ < 10 and "rate" in r_,
      f"{time.time() - t_:.1f} s {r_}")

# 5. coupure pendant l'écriture : write_atomic ne laisse jamais un fichier à moitié sous le vrai nom
p = os.path.join(tmp, "rapport.html")
m.write_atomic(p, "version 1")
real_rep = m.os.replace
m.os.replace = lambda a, b: (_ for _ in ()).throw(OSError("coupure"))
try:
    m.write_atomic(p, "version 2 " * 1000)
except OSError:
    pass
m.os.replace = real_rep
check("coupure pendant l'écriture : l'ancien fichier reste entier", open(p, encoding="utf-8").read() == "version 1")

# 6. endurance : 12 micros, 25 s ; mémoire du tampon bornée, files bornées, pas de fuite visible
chans = [dict(key=600000 + 25 * i, name=f"HF{i}", freq=600.0 + 0.025 * i, prio=1 + (i % 2), keep_on=True)
         for i in range(12)]
src = FakeSrc([(999, "ok")])
try:
    import resource  # noqa: E402  (Linux / macOS ; sous Windows : mesure mémoire sautée)
except ImportError:
    resource = None
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else 0
w, got = run_worker(src, chans=chans, secs=25)
rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else 0
p = got["perf"] or {}
check("endurance : tampon IQ borné (≤ budget)", p.get("ring_mb", 0) * 1e6 <= m.IQ_RING_BUDGET + RATE * 2,
      str(p.get("ring_mb")))
check("endurance : file du son bornée", len(w.audio) <= 200, str(len(w.audio)))
check("endurance : récepteurs virtuels limités, rotation active", 1 <= p.get("vrx", 0) <= m.VRX_MAX, str(p))
check("endurance : mémoire du processus raisonnable (< 400 Mo de plus)", (rss1 - rss0) / 1024 < 400,
      f"{(rss1 - rss0) / 1024:.0f} Mo")
stop(w, got)

# 7. outils SDR : retenus et tués à la fermeture
pr = m.sdr_proc_track(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]))
check("outil SDR resté vivant : tué à la fermeture", m.sdr_kill_all() >= 1 and pr.poll() is not None)

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
