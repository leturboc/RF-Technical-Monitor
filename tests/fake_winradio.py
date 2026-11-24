"""Fausse G39DDCAPI.dll pour les tests (V8 étape 7) : mêmes noms de fonctions, mêmes structures ctypes, rappels
appelés depuis un fil comme la vraie DLL. Instantanés IF (16 bits réels à 100 MS/s) pour le balayage, IQ du DDC1
(16 bits) pour l'écoute, avec des porteuses (FAKE_IQ_CARRIERS = « 606.0:1000 » : MHz:tonalité FM).
Ce n'est PAS la vraie DLL : seule la manière de l'appeler est vérifiée, pas le comportement du vrai récepteur."""
import ctypes
import os
import threading
import time

import numpy as np

ADC = 100e6
CENTER_IF = 25e6           # centre de la bande utile dans l'instantané (choix du faux)
WINDOW = 2e6               # FrontEndWindowWidth
STEP = 2000000             # FrontEndFrequencyStep
DDC_TYPES = [(250000, 200000, 16), (500000, 400000, 16), (1250000, 1000000, 16), (2500000, 2000000, 16),
             (5000000, 4000000, 16), (5000000, 4000000, 32)]
COMP_DB = -40.0            # compensation renvoyée (dB) : une porteuse pleine échelle ≈ +40 − 40…


def _carriers():
    out = []
    for x in os.environ.get("FAKE_IQ_CARRIERS", "").split(","):
        if ":" in x:
            f, t = x.split(":")
            out.append((float(f) * 1e6, float(t)))
    return out


class FakeG39:
    def __init__(self):
        self.calls = []
        self.cbs = None
        self.fe = 0
        self.ddc_rel = 0
        self.ddc = 4
        self.power = False
        self.att = self.amp = None
        self._run = None
        self.opened = 0

    def _log(self, name, *a):
        self.calls.append((name,) + a)

    # --- appareil
    def OpenDevice(self, sn):
        self._log("OpenDevice")
        self.opened += 1
        return 0

    def CloseDevice(self, h):
        self._stop()
        self._log("CloseDevice")
        self.opened -= 1
        return 1

    def GetDeviceInfo(self, h, info, size):
        i = info._obj
        i.SerialNumber = b"FAKE0001"
        i.ChannelCount = 2
        i.FrontEndMinFrequency = 9000
        i.FrontEndMaxFrequency = 3500000000
        i.FrontEndFrequencyStep = STEP
        i.FrontEndWindowWidth = int(WINDOW)
        return 1

    def SetPower(self, h, on):
        self.power = bool(on)
        return 1

    def SetAttenuator(self, h, a):
        self.att = int(a)
        return 1

    def SetPreamplifier(self, h, on):
        self.amp = bool(on)
        return 1

    def SetFrontEndFrequency(self, h, f):
        self.fe = int(f)
        self._log("SetFrontEndFrequency", int(f))
        return 1

    def SetCallbacks(self, h, cbs, ud):
        self.cbs = cbs._obj
        return 1

    # --- DDC1 (IQ)
    def SetDDC1Mode(self, h, mode):
        return 1

    def GetDDC1Count(self, h, ch, cnt):
        cnt._obj.value = len(DDC_TYPES)
        return 1

    def GetDDCInfo(self, i, di):
        if not 0 <= int(i) < len(DDC_TYPES):
            return 0
        r, b, bits = DDC_TYPES[int(i)]
        d = di._obj
        d.SampleRate, d.Bandwidth, d.BitsPerSample = r, b, bits
        return 1

    def SetDDC1(self, h, ch, i):
        self.ddc = int(i)
        self._log("SetDDC1", int(i))
        return 1

    def SetDDC1Frequency(self, h, ch, rel):
        self.ddc_rel = int(rel)
        return 1

    def StartDDC1(self, h, ch, spb):
        if not self.power:
            return 0
        self._stop()
        stop = threading.Event()
        self._run = stop
        rate, _bw, bits = DDC_TYPES[self.ddc]
        center = self.fe + self.ddc_rel
        car = [(f - center, t) for f, t in _carriers() if abs(f - center) < rate / 2]
        rng = np.random.default_rng(1)
        n = int(spb)

        def loop():
            k, t0 = 0, time.time()
            while not stop.is_set():
                t = (np.arange(n) + k * n) / rate
                x = 0.01 * (rng.normal(size=n) + 1j * rng.normal(size=n))
                for off, tone in car:
                    x = x + 0.3 * np.exp(1j * (2 * np.pi * off * t + 30e3 / tone * np.sin(2 * np.pi * tone * t)))
                iq = np.empty(2 * n, dtype=np.float64)
                iq[0::2], iq[1::2] = x.real, x.imag
                if bits == 16:
                    a = np.clip(np.round(iq * 32767), -32768, 32767).astype("<i2")
                else:
                    a = np.clip(np.round(iq * 2147483647), -2147483648, 2147483647).astype("<i4")
                self.cbs.DDC1StreamCallback(0, a.ctypes.data, n, bits, 0)
                k += 1
                dt = t0 + k * n / rate - time.time()
                if dt > 0:
                    time.sleep(dt)
        threading.Thread(target=loop, daemon=True).start()
        self._log("StartDDC1", n)
        return 1

    def StopDDC1(self, h, ch):
        self._stop()
        return 1

    # --- balayage (instantanés IF)
    def StartSweeping(self, h, a, z, start, settle, fwd):
        if not self.power:
            return 0
        self._stop()
        stop = threading.Event()
        self._run = stop
        rng = np.random.default_rng(2)
        tt = np.arange(65536) / ADC
        self._log("StartSweeping", int(a), int(z))

        def loop():
            while not stop.is_set():
                fe = int(a)
                while fe <= int(z) and not stop.is_set():
                    x = 2.0 * rng.normal(size=65536)
                    for f, _tone in _carriers():
                        off = f - fe
                        if abs(off) <= WINDOW / 2:
                            x = x + 8000.0 * np.cos(2 * np.pi * (CENTER_IF + off) * tt)
                    s = np.clip(np.round(x), -32768, 32767).astype("<i2")
                    self.cbs.SweepingCallback(s.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), 65536,
                                              int(CENTER_IF), fe, 0)
                    fe += STEP
                    time.sleep(0.003)
        threading.Thread(target=loop, daemon=True).start()
        return 1

    def StopSweeping(self, h):
        self._stop()
        return 1

    def GetIFSpectrumCompensation(self, h, fe, buf, count):
        for i in range(int(count)):
            buf[i] = COMP_DB
        return 1

    def _stop(self):
        if self._run is not None:
            self._run.set()
            self._run = None
            time.sleep(0.05)
