"""Faux tinySA pour les tests réseau : répond comme le firmware sur un port série virtuel (pty)."""
import os
import threading
import tty

import numpy as np


class FakeTinySA(threading.Thread):
    """Répond comme le firmware : écho de la commande, réponse, puis « ch> »."""

    def __init__(self, fd):
        super().__init__(daemon=True)
        self.fd, self.stop, self.cmds = fd, False, []
        self.mute = False                  # True : simule un câble réseau arraché (plus aucune réponse)

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
                if self.mute:
                    continue
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


def open_fake():
    """-> (FakeTinySA démarré, chemin du port série virtuel côté appli)."""
    master, slave = os.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    fake = FakeTinySA(master)
    fake.start()
    return fake, os.ttyname(slave)
