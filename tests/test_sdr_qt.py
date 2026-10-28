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

_path = os.environ.get("PATH", "")
os.environ["PATH"] = ""                          # aucun hackrf_sweep dans le PATH
w, ev = run_worker({}, lambda e: bool(e["errors"]), 10, tool=None, addr="hackrf:inexistant")
os.environ["PATH"] = _path
check("outil introuvable : erreur claire", ev["errors"] and ("introuvable" in ev["errors"][0]
                                                             or "arrêté" in ev["errors"][0]), str(ev["errors"]))

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
