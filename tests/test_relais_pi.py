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


SRC = open(os.path.join(HERE, "..", "tinysa_monitor.py"), encoding="utf-8").read()


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
stop.set()
th.join(3)
check("relais arrêté proprement", not th.is_alive())
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
