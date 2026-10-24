"""Vrai ScanWorker (PySide6) sur un faux tinySA en réseau : balayage, coupure du relais (link False),
reconnexion automatique (link True), 2e appareil qui attend son relais. Linux / macOS (pty) ; sauté sinon.

    python tests/test_reseau_qt.py
"""
import importlib.util
import os
import sys
import tempfile
import time

if not hasattr(os, "openpty"):
    print("pty indisponible (Windows) : test sauté\n\nÉCHECS: 0")
    sys.exit(0)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="tsm_net_")
os.environ["APPDATA"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from faketinysa import open_fake  # noqa: E402

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
fake, path = open_fake()
relay = m.SerialRelay(path, tcp_port=0, host="127.0.0.1")
relay.start()
relay.ready.wait(3)
port = relay.tcp_port
url = m.parse_device_addr(f"127.0.0.1:{port}")[1]

cfg = dict(bands=[dict(id=7, name="UHF", start_hz=470e6, stop_hz=530e6, n=301, enabled=True)], rbw=100,
           input="auto", lna=None, att="auto", offset=0.0, seg=None, demo_freqs=[], ver=1)
ev = dict(sweeps=[], links=[], errors=[], status=[], info=[])
w = m.ScanWorker(url, False, lambda: cfg, lambda: 1, "tinySA 2")
w.sweep.connect(lambda bid, f, l: ev["sweeps"].append((bid, len(l), float(f[l.argmax()]))))
w.link.connect(lambda ok: ev["links"].append(ok))
w.error.connect(lambda e: ev["errors"].append(e))
w.status.connect(lambda s: ev["status"].append(s))
w.info.connect(lambda s: ev["info"].append(s))
w.start()
check("balayage via le réseau", wait_until(lambda: len(ev["sweeps"]) >= 2, 15), str(ev))
if ev["sweeps"]:
    bid, n, fmax = ev["sweeps"][0]
    check("bande 7, 301 points, porteuse à 500 MHz", bid == 7 and n == 301 and abs(fmax - 500.0) < 0.3, str(ev["sweeps"][0]))
check("version lue", ev["info"] and ev["info"][0] == "tinySA4_v1.4-fake", str(ev["info"]))
check("statut préfixé « tinySA 2 »", any(s.startswith("tinySA 2 : Connecté") for s in ev["status"]), str(ev["status"][:3]))
check("réglages envoyés (rbw)", any(c.startswith("rbw") for c in fake.cmds), str(fake.cmds[:6]))

# --- coupure : on arrête le relais
relay.stop()
relay.join(4)
check("coupure détectée : link(False)", wait_until(lambda: ev["links"][:1] == [False], 30), str(ev["links"]))
check("pas d'erreur bloquante", not ev["errors"], str(ev["errors"]))
check("le worker tourne toujours (réessaie)", w.isRunning())
n_before = len(ev["sweeps"])
# --- retour du relais sur le même port
relay = m.SerialRelay(path, tcp_port=port, host="127.0.0.1")
relay.start()
relay.ready.wait(3)
check("relais relancé", relay.is_alive(), relay.error)
check("reconnexion automatique : link(True)", wait_until(lambda: ev["links"] == [False, True], 20), str(ev["links"]))
check("les balayages reprennent", wait_until(lambda: len(ev["sweeps"]) > n_before + 1, 15))
# --- liaison muette (câble arraché : la connexion ne se ferme pas, plus rien ne passe)
m.TinySA.NET_IDLE_MIN = 2.0
time.sleep(1.5)                        # le worker se reconnecte avec le nouveau délai au besoin
t0 = time.time()
fake.mute = True
check("liaison muette détectée : link(False)", wait_until(lambda: ev["links"][-1:] == [False], 40), str(ev["links"]))
dt = time.time() - t0
check(f"… en {dt:.0f} s (délai réseau + scan en cours)", dt < 40)
fake.mute = False
n_before = len(ev["sweeps"])
check("retour de la liaison : link(True)", wait_until(lambda: ev["links"][-1:] == [True], 30), str(ev["links"]))
check("les balayages reprennent encore", wait_until(lambda: len(ev["sweeps"]) > n_before + 1, 20))
w.requestInterruption()
check("arrêt propre", w.wait(10000))

# --- 2e appareil dont le relais n'est pas encore lancé : il attend (pas de message d'erreur)
ev2 = dict(links=[], errors=[])
w2 = m.ScanWorker("socket://127.0.0.1:1", False, lambda: cfg, lambda: 1, "tinySA 2")
w2.retry_first = True
w2.link.connect(lambda ok: ev2["links"].append(ok))
w2.error.connect(lambda e: ev2["errors"].append(e))
w2.start()
check("relais absent au démarrage : alarme (link False), pas d'erreur",
      wait_until(lambda: ev2["links"] == [False], 10) and not ev2["errors"], str(ev2))
w2.requestInterruption()
check("arrêt pendant l'attente", w2.wait(5000))
# --- 1er appareil injoignable au démarrage : erreur immédiate (comme avant)
ev3 = []
w3 = m.ScanWorker("socket://127.0.0.1:1", False, lambda: cfg, lambda: 1)
w3.error.connect(lambda e: ev3.append(e))
w3.start()
check("1er appareil injoignable : erreur", wait_until(lambda: ev3, 10) and not w3.isRunning() or ev3, str(ev3))
w3.wait(3000)
relay.stop()
relay.join(4)
fake.stop = True
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
