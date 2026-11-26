"""Relais autonome du Raspberry Pi (relais/tinysa_relais.py) : faux tinySA (pty) → relais → TCP → classe TinySA de
l'appli. Linux / macOS seulement (pty) ; sous Windows le test est sauté.
    python tests/test_relais_pi.py        -> ÉCHECS: 0"""
import os
import sys
import threading
import time

if not hasattr(os, "openpty"):
    print("pty indisponible (Windows) : test sauté\n\nÉCHECS: 0")
    sys.exit(0)

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "relais"))
import tinysa_relais as R  # noqa: E402
from faketinysa import open_fake  # noqa: E402

fails = 0


def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra, flush=True)


SRC = __import__("_src").source()


def chunk(start, end):
    a = SRC.index(start)
    return SRC[a:SRC.index(end, a)]


ns = dict(__name__="tsm_pi")
exec("import bisect, csv, io, itertools, math, os, re, select, socket, threading, time, unicodedata\n"
     "from collections import deque\nimport numpy as np\nimport serial\n", ns)
ns.update(MIN_PTS=51, HYST=3.0, RBW_LIST=[1, 3, 10, 30, 100], APP_NAME="t")
exec(chunk("# ===== PURE-BEGIN", "# ===== PURE-END"), ns)
exec(chunk("class TinySA:", "# ----"), ns)
TinySA = ns["TinySA"]

fake, slave = open_fake()
stop = threading.Event()
port = []
th = threading.Thread(target=R.serve, kwargs=dict(serial_port=slave, tcp_port=0, host="127.0.0.1",
                                                   stop=stop.is_set, on_ready=port.append), daemon=True)
th.start()
t0 = time.time()
while not port and time.time() - t0 < 5:
    time.sleep(0.05)
check("relais du Pi démarré", bool(port))
kind, url = ns["parse_device_addr"](f"127.0.0.1:{port[0]}")
dev = TinySA(url)
check("version via le relais du Pi", dev.version() == "tinySA4_v1.4-fake")
fr, lv = dev.scan(470e6, 530e6, 301)
check("scan via le relais du Pi : 301 points, porteuse à 500 MHz", len(lv) == 301
      and abs(fr[int(np.argmax(lv))] - 500e6) < 300e3)
dev.ser.close()
dev2 = TinySA(url)
check("reconnexion (coupure Wi-Fi) : un nouveau client remplace l'ancien", dev2.version() == "tinySA4_v1.4-fake")
dev2.close()
check("adresse « raspberrypi.local » acceptée par l'appli",
      ns["parse_device_addr"]("raspberrypi.local") == ("net", "socket://raspberrypi.local:5025"))


class _P:
    def __init__(self, dev, vid=None, pid=None):
        self.device, self.vid, self.pid = dev, vid, pid


_orig = R.list_ports.comports
R.list_ports.comports = lambda: [_P("/dev/ttyAMA0"), _P("/dev/ttyACM3", 0x0483, 0x5740)]
check("détection : le tinySA par son identifiant USB", R.find_tinysa() == "/dev/ttyACM3")
R.list_ports.comports = lambda: [_P("/dev/ttyAMA0"), _P("/dev/ttyACM0")]
check("détection : sinon le 1er ttyACM", R.find_tinysa() == "/dev/ttyACM0")
R.list_ports.comports = lambda: []
check("détection : rien de branché", R.find_tinysa() is None)
R.list_ports.comports = _orig
# --- diagnostic « le Pi ne voit pas le tinySA » (faux /sys)
import tempfile  # noqa: E402


def _fake_sys(devs):
    root = tempfile.mkdtemp()
    for i, (v, p_, name) in enumerate(devs):
        d = os.path.join(root, f"1-{i}")
        os.makedirs(d)
        for k, val in (("idVendor", v), ("idProduct", p_), ("product", name)):
            open(os.path.join(d, k), "w").write(val + "\n")
    return root


_none = os.path.join(tempfile.mkdtemp(), "ttyACM*")
_dg = R.diagnose(_fake_sys([("1d6b", "0002", "hub"), ("046d", "c52b", "Receiver")]), _none)
check("diag : rien vu -> allumé / câble data / bon port", any("ALLUMÉ" in x and "câble" in x for x in _dg), str(_dg))
check("diag : liste les appareils vus (sans les hubs)", "046d:c52b" in _dg[0] and "1d6b" not in _dg[0], _dg[0])
_dg = R.diagnose(_fake_sys([("0483", "df11", "DFU")]), _none)
check("diag : tinySA en mode DFU", any("DFU" in x for x in _dg[2:]), str(_dg))
_dg = R.diagnose(_fake_sys([("0483", "5720", "Mass Storage")]), _none)
check("diag : STM32 sans port série = disque USB ?", any("disque USB" in x for x in _dg), str(_dg))
_dg = R.diagnose(_fake_sys([("0483", "5740", "tinySA4")]), _none)
check("diag : tinySA vu sans ttyACM -> redémarrer", any("redémarre le Pi" in x for x in _dg), str(_dg))
# --- --multi : plusieurs tinySA sur le même Pi, un port réseau chacun, retenu par numéro de série
class _Q(_P):
    def __init__(self, dev, sn, loc):
        super().__init__(dev, 0x0483, 0x5740)
        self.serial_number, self.location = sn, loc


R.list_ports.comports = lambda: [_Q("/dev/ttyACM1", "B222", "1-1.3"), _P("/dev/ttyAMA0"), _Q("/dev/ttyACM0", "A111", "1-1.2")]
check("multi : tous les tinySA, reconnus par numéro de série", R.find_all_tinysa()
      == [("A111", "/dev/ttyACM0"), ("B222", "/dev/ttyACM1")], str(R.find_all_tinysa()))
R.list_ports.comports = _orig
check("multi : prochain port libre", (R.next_port({}, 5025), R.next_port({"a": 5025, "b": 5026}, 5025),
                                      R.next_port({"a": 5026}, 5025)) == (5025, 5027, 5025))
_pf = os.path.join(tempfile.mkdtemp(), "ports.json")
R.save_ports(_pf, {"A111": 5025, "B222": 5026})
check("multi : ports retenus d'un démarrage à l'autre", R.load_ports(_pf) == {"A111": 5025, "B222": 5026})
fake2, slave2 = open_fake()
fake3, slave3 = open_fake()
stop2 = threading.Event()
ready = {}
_lst = [("SN-A", slave2), ("SN-B", slave3)]
thm = threading.Thread(target=R.serve_multi, kwargs=dict(base_port=0, host="127.0.0.1", stop=stop2.is_set,
                                                         lister=lambda: list(_lst), ports_file=None, scan_s=0.2,
                                                         on_ready=lambda k, p: ready.__setitem__(k, p)), daemon=True)
thm.start()
t0 = time.time()
while len(ready) < 2 and time.time() - t0 < 6:
    time.sleep(0.05)
check("multi : un relais par tinySA", set(ready) == {"SN-A", "SN-B"} and ready["SN-A"] != ready["SN-B"], str(ready))
if len(ready) == 2:
    for k in ("SN-A", "SN-B"):
        d_ = TinySA(ns["parse_device_addr"](f"127.0.0.1:{ready[k]}")[1])
        check(f"multi : {k} répond sur son port", d_.version() == "tinySA4_v1.4-fake")
        d_.close()
stop2.set()
thm.join(4)
check("multi : arrêt propre", not thm.is_alive())
# ---- client qui ne lit plus (revue de code 7.41) : le relais doit le lâcher au lieu de rester bloqué
import socket as _so
fake4, slave4 = open_fake()
stop4 = threading.Event()
p4 = []
th4 = threading.Thread(target=R.serve, kwargs=dict(serial_port=slave4, tcp_port=0, host="127.0.0.1", stop=stop4.is_set,
                                                    on_ready=p4.append, allow=["127.0.0.1"]), daemon=True)
th4.start()
t0 = time.time()
while not p4 and time.time() - t0 < 5:
    time.sleep(0.05)
lazy = _so.create_connection(("127.0.0.1", p4[0]))
lazy.setsockopt(_so.SOL_SOCKET, _so.SO_RCVBUF, 4096)
for _ in range(4):                                  # gros scans demandés, jamais lus
    try:
        lazy.sendall(b"scan 470000000 700000000 20000 3\r")
    except OSError:
        break
time.sleep(8)
_v4 = ""
for _ in range(5):                                  # le faux tinySA peut finir d'envoyer un scan en cours
    try:
        d4 = TinySA(ns["parse_device_addr"](f"127.0.0.1:{p4[0]}")[1])
        _v4 = d4.version()
        d4.close()
    except Exception:  # noqa: BLE001
        pass
    if _v4 == "tinySA4_v1.4-fake":
        break
    time.sleep(2)
check("client qui ne lit plus : lâché, un nouveau client est servi", _v4 == "tinySA4_v1.4-fake", repr(_v4))
lazy.close()
stop4.set()
th4.join(3)
check("relais (client lent) arrêté proprement", not th4.is_alive())
# ---- --allow : une adresse non autorisée est refusée
stop5 = threading.Event()
p5 = []
fake5, slave5 = open_fake()
th5 = threading.Thread(target=R.serve, kwargs=dict(serial_port=slave5, tcp_port=0, host="127.0.0.1", stop=stop5.is_set,
                                                    on_ready=p5.append, allow=["10.9.9.9"]), daemon=True)
th5.start()
t0 = time.time()
while not p5 and time.time() - t0 < 5:
    time.sleep(0.05)
_refused = False
try:
    d5 = TinySA(ns["parse_device_addr"](f"127.0.0.1:{p5[0]}")[1])
    d5.close()
except Exception:  # noqa: BLE001
    _refused = True
check("--allow : client non autorisé refusé", _refused)
stop5.set()
th5.join(3)
stop.set()
th.join(3)
check("relais arrêté proprement", not th.is_alive())
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
