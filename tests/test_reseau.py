"""Chemin réseau de bout en bout : faux tinySA (port série virtuel) → SerialRelay → TCP → classe TinySA.
Linux / macOS seulement (pty) ; sous Windows le test est sauté. Nécessite pyserial (vrai) et numpy.

    python tests/test_reseau.py
"""
import os
import sys
import threading
import time
import types

if not hasattr(os, "openpty"):
    print("pty indisponible (Windows) : test sauté\n\nÉCHECS: 0")
    sys.exit(0)

import numpy as np
import serial
import tty

fails = 0


def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra, flush=True)


# --- on charge seulement ce qu'il faut du gros fichier (pas de Qt) : section PURE + TinySA + SerialRelay
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tinysa_monitor.py"), encoding="utf-8").read()


def chunk(start, end):
    a = SRC.index(start)
    return SRC[a:SRC.index(end, a)]


ns = dict(__name__="tsm_net")
exec("import bisect, csv, io, itertools, math, re, select, socket, threading, time, unicodedata\n"
     "from collections import deque\nimport numpy as np\nimport serial\n", ns)
ns.update(MIN_PTS=51, HYST=3.0, RBW_LIST=[1, 3, 10, 30, 100], APP_NAME="t", TINYSA_VID=0, TINYSA_PID=0)
exec(chunk("# ===== PURE-BEGIN", "# ===== PURE-END"), ns)
exec(chunk("class TinySA:", "# ----"), ns)
exec(chunk("def local_ips():", "class RelayWindow"), ns)
TinySA, SerialRelay = ns["TinySA"], ns["SerialRelay"]


class FakeTinySA(threading.Thread):
    """Répond comme le firmware : écho de la commande, réponse, puis « ch> »."""

    def __init__(self, fd):
        super().__init__(daemon=True)
        self.fd, self.stop, self.cmds = fd, False, []

    def out(self, txt):
        os.write(self.fd, txt.encode())

    def run(self):
        buf = b""
        while not self.stop:
            try:
                d = os.read(self.fd, 1024)
            except OSError:
                return
            buf += d
            while b"\r" in buf:
                line, buf = buf.split(b"\r", 1)
                c = line.decode().strip()
                self.cmds.append(c)
                rep = ""
                if c == "version":
                    rep = "tinySA4_v1.4-fake\r\n"
                elif c.startswith("scan "):
                    _, a, b, n, _o = c.split()
                    for f in np.linspace(float(a), float(b), int(n)):
                        lv = -40.0 if abs(f - 500e6) < 60e3 else -100.0
                        rep += f"{f:.0f} {lv:.2f} \r\n"
                self.out(c + "\r\n" + rep + "ch> ")


master, slave = os.openpty()
tty.setraw(master)
tty.setraw(slave)
fake = FakeTinySA(master)
fake.start()
slave_path = os.ttyname(slave)

relay = SerialRelay(slave_path, tcp_port=0, host="127.0.0.1")
relay.start()
relay.ready.wait(3)
check("relais démarré", relay.is_alive() and relay.serial_ok and relay.tcp_port > 0, relay.error)

kind, url = ns["parse_device_addr"](f"127.0.0.1:{relay.tcp_port}")
check("adresse réseau → url socket://", kind == "net" and url == f"socket://127.0.0.1:{relay.tcp_port}", url)

t0 = time.time()
dev = TinySA(url)
check("connexion au tinySA via le réseau", True)
ver = dev.version()
check("version via le relais", ver == "tinySA4_v1.4-fake", repr(ver))
time.sleep(0.2)
check("le relais voit le client", relay.client == "127.0.0.1", str(relay.client))
fr, lv = dev.scan(470e6, 530e6, 301)
check("scan via le relais : 301 points", len(lv) == 301 and fr is not None and len(fr) == 301, str(len(lv)))
check("scan : porteuse à 500 MHz retrouvée", abs(fr[int(np.argmax(lv))] - 500e6) < 300e3 and lv.max() > -50)
ok, msg = dev.try_cmd("rbw 100")
check("commande de réglage via le relais", ok, msg)
dt = time.time() - t0
check(f"rapide en local ({dt:.2f} s)", dt < 5)

# --- coupure réseau côté appli : un nouveau client remplace l'ancien
dev.ser.close()
dev2 = TinySA(url)
check("reconnexion après coupure", dev2.version() == "tinySA4_v1.4-fake")
time.sleep(0.2)
check("toujours un seul client", relay.client == "127.0.0.1")
# --- l'ancien client encore ouvert est remplacé par le nouveau
dev3 = TinySA(url)
check("un 2e client prend la main", dev3.version() == "tinySA4_v1.4-fake")
dev2.close()
dev3.close()
check("compteurs de trafic", relay.rx > 1000 and relay.tx > 10, f"rx={relay.rx} tx={relay.tx}")

# --- port série introuvable : le relais reste vivant et réessaie
r2 = SerialRelay("/dev/inexistant_tinysa", tcp_port=0, host="127.0.0.1")
r2.start()
r2.ready.wait(3)
check("port USB absent : relais vivant, erreur affichée", r2.is_alive() and not r2.serial_ok and "inexistant" in r2.error,
      r2.error)
r2.stop()
r2.join(4)
check("arrêt du relais", not r2.is_alive())

# --- pas de relais : erreur claire et rapide
t0 = time.time()
try:
    TinySA("socket://127.0.0.1:1")
    check("adresse sans relais : erreur", False)
except Exception as e:  # noqa: BLE001
    check("adresse sans relais : erreur", True)
    check(f"… rapide ({time.time() - t0:.1f} s)", time.time() - t0 < 8)

relay.stop()
relay.join(4)
fake.stop = True
check("relais arrêté proprement", not relay.is_alive())
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
