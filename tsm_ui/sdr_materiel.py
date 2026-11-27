# SDR : WiNRADiO, sources d'IQ, réglages, écoute, moniteur multicanal, récepteurs.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


SDRSweep.family = "sdr"
SDRSweep.caps = dict(listen=True, realtime=True, sweep_all=True, calibrated=False)
register_spectrum_driver("sdr", lambda a: parse_sdr_addr(a) is not None,
                         lambda a, w: SDRSweep(a, w.sdr_dir, w._tr, w.sdr_tool))


# --------------------------------------------------------------------------
# V8 étape 7 : WiNRADiO G39DDC par sa DLL (G39DDCAPI.dll, appels __stdcall, structures #pragma pack(1)) — d'après la
# doc et l'en-tête officiels (winradio.com, lus le 24/11/2026). JAMAIS essayé avec un vrai G39DDC : testé avec une
# fausse DLL (tests/fake_winradio.py). Règle de la DLL : un récepteur se pilote depuis UN SEUL fil (celui qui l'a
# ouvert), et on n'appelle pas la DLL depuis ses fonctions de rappel -> les rappels ne font que copier les données.
# --------------------------------------------------------------------------
import ctypes  # noqa: E402

_WR_FN = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)        # __stdcall sous Windows
_WR_U32, _WR_U64, _WR_PTR = ctypes.c_uint32, ctypes.c_uint64, ctypes.c_size_t      # DWORD_PTR = taille d'un pointeur
WR_OPEN_FIRST = ctypes.c_void_p(-1)      # G39DDC_OPEN_FIRST = ((CHAR*)-1)
WR_OPEN_DEMO = ctypes.c_void_p(0)        # G39DDC_OPEN_DEMO  = ((CHAR*)0)
WR_ATT = {0: 0, 6: 1, 12: 2, 18: 3}      # G39DDC_ATTENUATOR_0dB … _18dB
WR_DDC1_MODE_DEFAULT, WR_DDC1_MODE_WIDEBAND = 0, 1      # valeurs supposées dans l'ordre de la doc (pas dans l'en-tête lu)


class WR_DEVICE_INFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("DevicePath", ctypes.c_char * 260), ("InterfaceType", ctypes.c_ubyte), ("SerialNumber", ctypes.c_char * 9),
                ("HWVersion", ctypes.c_uint16), ("FWVersion", ctypes.c_uint16), ("EEPROMVersion", ctypes.c_ubyte),
                ("ChannelCount", _WR_U32), ("FrontEndMinFrequency", _WR_U64), ("FrontEndMaxFrequency", _WR_U64),
                ("FrontEndMaxHFFrequency", _WR_U64), ("FrontEndFrequencyStep", _WR_U32),
                ("FrontEndWindowWidth", _WR_U32), ("HardwareOptions", _WR_U32)]


class WR_DDC_INFO(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("SampleRate", _WR_U32), ("Bandwidth", _WR_U32), ("BitsPerSample", _WR_U32)]


WR_IF_CB = _WR_FN(None, ctypes.POINTER(ctypes.c_short), _WR_U32, _WR_U32, ctypes.c_uint16, _WR_U32, _WR_PTR)
WR_DDC1_CB = _WR_FN(None, _WR_U32, ctypes.c_void_p, _WR_U32, _WR_U32, _WR_PTR)
WR_DDC1_PLAY_CB = _WR_FN(ctypes.c_int, _WR_U32, ctypes.c_void_p, _WR_U32, _WR_U32, _WR_PTR)
WR_DDC2_CB = _WR_FN(None, _WR_U32, ctypes.POINTER(ctypes.c_float), _WR_U32, _WR_PTR)
WR_DDC2_PRE_CB = _WR_FN(None, _WR_U32, ctypes.POINTER(ctypes.c_float), _WR_U32, ctypes.c_float, ctypes.c_float, _WR_PTR)
WR_AUDIO_CB = _WR_FN(None, _WR_U32, _WR_U32, ctypes.POINTER(ctypes.c_float), _WR_U32, _WR_PTR)
WR_AUDIO_PLAY_CB = _WR_FN(ctypes.c_int, _WR_U32, ctypes.POINTER(ctypes.c_float), _WR_U32, _WR_PTR)
WR_SWEEP_CB = _WR_FN(ctypes.c_int, ctypes.POINTER(ctypes.c_short), _WR_U32, _WR_U32, _WR_U64, _WR_PTR)


class WR_CALLBACKS(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("IFCallback", WR_IF_CB), ("DDC1StreamCallback", WR_DDC1_CB),
                ("DDC1PlaybackStreamCallback", WR_DDC1_PLAY_CB), ("DDC2StreamCallback", WR_DDC2_CB),
                ("DDC2PreprocessedStreamCallback", WR_DDC2_PRE_CB), ("AudioStreamCallback", WR_AUDIO_CB),
                ("AudioPlaybackStreamCallback", WR_AUDIO_PLAY_CB), ("SweepingCallback", WR_SWEEP_CB)]


WR_SIGS = {   # nom -> (type de retour, arguments)  (fonctions utilisées seulement)
    "OpenDevice": (ctypes.c_int32, [ctypes.c_void_p]), "CloseDevice": (ctypes.c_int, [ctypes.c_int32]),
    "GetDeviceInfo": (ctypes.c_int, [ctypes.c_int32, ctypes.POINTER(WR_DEVICE_INFO), _WR_U32]),
    "SetPower": (ctypes.c_int, [ctypes.c_int32, ctypes.c_int]),
    "SetAttenuator": (ctypes.c_int, [ctypes.c_int32, _WR_U32]),
    "SetPreamplifier": (ctypes.c_int, [ctypes.c_int32, ctypes.c_int]),
    "SetFrontEndFrequency": (ctypes.c_int, [ctypes.c_int32, _WR_U64]),
    "SetDDC1Mode": (ctypes.c_int, [ctypes.c_int32, _WR_U32]),
    "GetDDC1Count": (ctypes.c_int, [ctypes.c_int32, _WR_U32, ctypes.POINTER(_WR_U32)]),
    "GetDDCInfo": (ctypes.c_int, [_WR_U32, ctypes.POINTER(WR_DDC_INFO)]),
    "SetDDC1": (ctypes.c_int, [ctypes.c_int32, _WR_U32, _WR_U32]),
    "SetDDC1Frequency": (ctypes.c_int, [ctypes.c_int32, _WR_U32, ctypes.c_int32]),
    "StartDDC1": (ctypes.c_int, [ctypes.c_int32, _WR_U32, _WR_U32]),
    "StopDDC1": (ctypes.c_int, [ctypes.c_int32, _WR_U32]),
    "StartSweeping": (ctypes.c_int, [ctypes.c_int32, _WR_U64, _WR_U64, _WR_U64, ctypes.c_uint16, ctypes.c_int]),
    "StopSweeping": (ctypes.c_int, [ctypes.c_int32]),
    "GetIFSpectrumCompensation": (ctypes.c_int, [ctypes.c_int32, _WR_U64, ctypes.POINTER(ctypes.c_float), _WR_U32]),
    "SetCallbacks": (ctypes.c_int, [ctypes.c_int32, ctypes.POINTER(WR_CALLBACKS), _WR_PTR]),
}


class WinradioG39:
    """Un G39DDC ouvert (dans le fil qui l'utilise). lib = DLL chargée (ctypes.WinDLL) ou fausse DLL (tests)."""

    def __init__(self, serial="", lib=None, dll_dir="", trace=None):
        self.trace = trace
        if lib is None:
            path = find_winradio_dll(dll_dir)
            if path is None or not hasattr(ctypes, "WinDLL"):
                raise RuntimeError("G39DDCAPI.dll introuvable : installe le logiciel WiNRADiO G39DDC (il installe la "
                                   "DLL) ou indique son dossier dans 📡 Réglages SDR." if path is None else
                                   "WiNRADiO : pilote Windows seulement.")
            lib = ctypes.WinDLL(path)
        self.lib = lib
        self.f = {}
        for name, (res, args) in WR_SIGS.items():
            fn = getattr(lib, name)
            if hasattr(fn, "argtypes"):
                fn.restype, fn.argtypes = res, args
            self.f[name] = fn
        self._sn = ctypes.c_char_p(serial.encode("ascii", "ignore")) if serial else None
        arg = ctypes.cast(self._sn, ctypes.c_void_p) if serial else WR_OPEN_FIRST
        self.h = self.f["OpenDevice"](arg)
        if self.h is None or int(self.h) < 0:
            raise RuntimeError("WiNRADiO G39DDC introuvable ou déjà utilisé (OpenDevice a échoué).")
        self.info = WR_DEVICE_INFO()
        self.call("GetDeviceInfo", ctypes.byref(self.info), ctypes.sizeof(self.info))
        self.call("SetPower", 1)
        self.cbs = WR_CALLBACKS()           # gardés tant que le récepteur est ouvert (sinon ramassés : plantage)
        self._t(f"G39DDC ouvert : n° {self.serial()}, {self.info.FrontEndMinFrequency / 1e6:g}–"
                f"{self.info.FrontEndMaxFrequency / 1e6:g} MHz, pas {self.info.FrontEndFrequencyStep} Hz, "
                f"fenêtre {self.info.FrontEndWindowWidth / 1e6:g} MHz")

    def _t(self, txt):
        if self.trace is not None:
            self.trace(txt)

    def serial(self):
        return bytes(self.info.SerialNumber).split(b"\0")[0].decode("ascii", "ignore")

    def call(self, name, *a):
        ok = self.f[name](self.h, *a)
        if not ok:
            raise RuntimeError(f"G39DDC : {name} a échoué")
        return ok

    def set_gains(self, g):
        att = min(WR_ATT, key=lambda k: abs(k - int(g.get("att", 0) or 0)))
        self.call("SetAttenuator", WR_ATT[att])
        self.call("SetPreamplifier", 1 if g.get("amp") else 0)

    def fe_round(self, hz):
        """Fréquence front-end valide (multiple du pas, bornée) la plus proche."""
        st = max(1, int(self.info.FrontEndFrequencyStep))
        lo, hi = int(self.info.FrontEndMinFrequency), int(self.info.FrontEndMaxFrequency)
        v = int(round(hz / st)) * st
        return min(hi - (hi % st), max(lo if lo % st == 0 else lo + st - lo % st, v))

    def set_callbacks(self, **kw):
        self.cbs = WR_CALLBACKS()
        for k, v in kw.items():
            setattr(self.cbs, k, v)
        self.call("SetCallbacks", ctypes.byref(self.cbs), 0)

    def close(self):
        h, self.h = self.h, None
        if h is not None:
            try:
                self.f["CloseDevice"](h)
            except Exception:  # noqa: BLE001
                pass


class WinradioSweep(SpectrumDevice):
    """G39DDC en balayage (pour le ScanWorker) : StartSweeping de la DLL entre la plus basse et la plus haute bande ;
    chaque instantané IF (rappel) est copié, puis dans le fil du worker : FFT + compensation de la DLL -> dBm, posé
    dans un SweepAccum ; scan() rend le dernier passage complet comme SDRSweep. Niveaux calibrés en dBm (doc)."""
    PROMPT = None
    family = "sdr"
    caps = dict(listen=True, realtime=True, sweep_all=True, calibrated=True)

    def __init__(self, addr, dll_dir="", trace=None, lib=None):
        self.kind, serial = parse_sdr_addr(addr) or ("winradio", "")
        self.spec = SDR_KINDS["winradio"]
        self.trace, self.abort, self.idle = trace, None, 30.0
        self.dev = WinradioG39(serial, lib=lib, dll_dir=dll_dir, trace=trace)
        self.q = deque(maxlen=400)
        self.acc, self.lock = SweepAccum(), threading.Lock()
        self.served, self.key, self.nfft, self.comp, self.running = {}, None, 8192, {}, False
        self.inverted = False

    def version(self):
        return f"WiNRADiO G39DDC · n° {self.dev.serial()}"

    def set_rbw(self, khz):
        self.rbw = khz
        return True, ""

    def expect_scan(self, points, rbw_khz, step_khz=None):
        self.idle = 30.0

    def _on_snap(self, buf, n, center_if, fe, _ud):
        try:
            self.q.append((np.ctypeslib.as_array(buf, shape=(int(n),)).copy(), int(center_if), int(fe)))
        except Exception:  # noqa: BLE001 — jamais d'exception vers la DLL
            pass
        return 1

    def configure(self, bands, rbw_khz, gains):
        lo = min(b["start_hz"] for b in bands)
        hi = max(b["stop_hz"] for b in bands)
        d = self.dev
        w = float(d.info.FrontEndWindowWidth or 2e6)
        a, z = d.fe_round(lo + w / 2.0), d.fe_round(max(lo + w / 2.0, hi - w / 2.0))
        if z <= a:
            z = d.fe_round(a + max(1, d.info.FrontEndFrequencyStep))
        nfft = 8192
        if rbw_khz:                                    # finesse demandée -> taille de FFT (≤ instantané de 65 536)
            nfft = int(min(65536, max(1024, 2 ** math.ceil(math.log2(WR_ADC_RATE / (float(rbw_khz) * 1000.0))))))
        key = (a, z, nfft, int(gains.get("att", 0) or 0), bool(gains.get("amp")))
        if key == self.key and self.running:
            return
        self.stop_sweep()
        self.key, self.nfft = key, nfft
        d.set_gains(gains or {})
        self.cb = WR_SWEEP_CB(self._on_snap)
        d.set_callbacks(SweepingCallback=self.cb)
        with self.lock:
            self.acc = SweepAccum()
        self.served, self.comp = {}, {}
        d.call("StartSweeping", a, z, a, 20, 1)
        self.running = True
        d._t(f"balayage {a / 1e6:g}–{z / 1e6:g} MHz (front-end), FFT {nfft}")

    def _drain(self):
        d = self.dev
        while self.q:
            samples, cif, fe = self.q.popleft()
            comp = self.comp.get(fe)
            if comp is None and len(self.comp) < 4000:
                buf = (ctypes.c_float * (self.nfft // 2))()
                try:
                    d.call("GetIFSpectrumCompensation", fe, buf, self.nfft // 2)
                    comp = np.ctypeslib.as_array(buf).astype(float).copy()
                except RuntimeError:
                    comp = None
                self.comp[fe] = comp
            F, L = wr_snapshot_spectrum(samples, cif, fe, float(d.info.FrontEndWindowWidth), comp, nfft=self.nfft,
                                        inverted=self.inverted)
            if F is None or len(F) < 2:
                continue
            bw = (F[1] - F[0]) * 1e6
            with self.lock:
                self.acc.feed((F[0] * 1e6 - bw / 2.0, F[-1] * 1e6 + bw / 2.0, bw, L))

    def scan(self, start_hz, stop_hz, points):
        if not self.running:
            raise RuntimeError("G39DDC : balayage pas lancé")
        key = (round(start_hz), round(stop_hz), int(points))
        need = self.served.get(key, 0)
        t0 = time.time()
        while True:
            self._drain()
            with self.lock:
                passes, snap = self.acc.passes, self.acc.snapshot()
            if snap is not None and passes > need:
                break
            if self.abort is not None and self.abort():
                raise Aborted()
            if time.time() - t0 > self.idle:
                raise TimeoutError(f"WiNRADiO G39DDC muet depuis {self.idle:.0f} s")
            time.sleep(0.02)
        self.served[key] = passes
        F, L = snap
        x = np.linspace(start_hz, stop_hz, int(points))
        return x, resample_max(F, L, start_hz, stop_hz, int(points))

    def stop_sweep(self):
        if self.running:
            try:
                self.dev.f["StopSweeping"](self.dev.h)
            except Exception:  # noqa: BLE001
                pass
            self.running = False

    def close(self):
        self.stop_sweep()
        self.dev.close()


class ProcIQ:
    """Source d'IQ = un outil (hackrf_transfer, rtl_sdr, rx_sdr…) qui écrit l'IQ brut sur sa sortie standard."""

    def __init__(self, kind, exe, center, rate, gains, serial=""):
        self.kind, self.rate, self.center = kind, int(rate), float(center)
        self.dtype = SDR_DTYPE.get(kind, "ci8")
        self.err = deque(maxlen=20)
        argv = listen_cmd(kind, exe, center, rate, gains.get("lna", 24), gains.get("vga", 20), gains.get("amp", False),
                          serial)
        self.proc = sdr_proc_track(subprocess.Popen([str(x) for x in argv], stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, bufsize=0,
                                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read_err(self):
        try:
            for line in self.proc.stderr:
                t = line.decode(errors="ignore").strip()
                if t:
                    self.err.append(t)
        except Exception:  # noqa: BLE001
            pass

    def read(self, n):
        return self.proc.stdout.read(n) if self.proc is not None else b""

    def close(self):
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=3)
            except Exception:  # noqa: BLE001
                pass


SDR_DEMO_STATE = dict(v=0, plan=[], tx=[], fault=None)   # étape 21 : signaux du SDR démo (micros + émission simulée)
# 8.2 : fault = dict(kind (clé de DEMO_FAULTS), until (time.time())) : panne simulée injectée dans le flux du SDR démo


def sdr_demo_fault(kind=None, secs=30.0):
    """8.2 (labo) : injecte une panne simulée dans le SDR démo pendant `secs` s (None = arrêter)."""
    st = SDR_DEMO_STATE
    st["fault"] = None if not kind else dict(kind=kind, until=time.time() + float(secs), t0=time.time())
    st["v"] += 1


def sdr_demo_fault_now():
    f = SDR_DEMO_STATE.get("fault")
    if f and time.time() >= f["until"]:
        SDR_DEMO_STATE["fault"] = None
        SDR_DEMO_STATE["v"] += 1
        return None
    return f


def sdr_demo_set(plan=None, tx=None):
    """Change ce que « reçoit » le SDR démo (sans rien faire si c'est pareil)."""
    st = SDR_DEMO_STATE
    ch = False
    for k, v in (("plan", plan), ("tx", tx)):
        if v is not None and v != st[k]:
            st[k] = list(v)
            ch = True
    if ch:
        st["v"] += 1


class DemoIQ:
    """Source d'IQ du SDR démo (étape 21) : SigGen au rythme réel, signaux = SDR_DEMO_STATE (tes micros + ce qu'émet
    l'émission simulée). Même interface que ProcIQ : read(n octets), close(), rate, dtype, err."""
    dtype = "cf32_le"

    def __init__(self, center, rate=None):
        self.center, self.rate = float(center), int(rate or DEMO_RATE)
        self.err = deque(maxlen=20)
        self.gen = SigGen(self.rate, self.center)
        self._v, self.n, self.closed = None, 0, False
        self.t0 = time.monotonic()

    def read(self, nbytes):
        if self.closed:
            return b""
        st = SDR_DEMO_STATE
        flt = sdr_demo_fault_now()
        fk = flt["kind"] if flt else None
        if st["v"] != self._v:
            self._v = st["v"]
            sigs = list(st["plan"]) + list(st["tx"])
            if fk == "pilot":                            # 8.2 : pannes simulées qui changent les signaux
                sigs = [dict(s_, pilot=0.0) for s_ in sigs]
            elif fk == "nosrc":                          # son introuvable : porteuses là, plus rien à entendre
                sigs = [dict(s_, audio=dict(src="wav", path="<introuvable>")) if s_.get("kind") in ("fm", "nfm") else s_
                        for s_ in sigs]
            elif fk == "jam":
                mic = next((s_ for s_ in sigs if s_.get("kind") == "fm"), None)
                if mic is not None:
                    sigs.append(dict(key="faultjam", kind="nfm", f=float(mic["f"]) + 0.02, lvl=-2.0, dev=4000.0,
                                     audio="beep", k=5))
            self.gen.set_sigs(sigs)
            self.gen.noise = 0.1 if fk == "noise" else 0.01
        if fk == "unplug":
            self.err.append("SDR démo : débranché (panne simulée)")
            return b""
        if fk == "stall" and time.time() - flt["t0"] < 3.0:
            return self._stall(nbytes)                   # flux figé : rien pendant 3 s (puis il repart)
        n = max(1, int(nbytes) // IQ_BYTES[self.dtype])
        nn = int(math.ceil(n / 0.8)) if fk == "drop" else n   # panne « blocs perdus » : le SDR produit nn, on en reçoit n
        due = self.t0 + (self.n + nn) / self.rate
        dt = due - time.monotonic()
        if dt > 0:
            time.sleep(min(dt, 0.5))
        elif dt < -1.0:                              # PC très occupé : on repart de maintenant (pas de rattrapage)
            self.t0, self.n = time.monotonic(), 0
        x = self.gen.block(nn)
        self.n += nn
        if nn > n:
            x = x[nn - n:]                           # 20 % des échantillons perdus (comme un USB qui sature)
        self._nread = getattr(self, "_nread", 0) + 1
        self.ts_off = -2.0 if (fk == "badts" and self._nread % 40 == 0) else 0.0   # 8.2 : l'heure recule (simulé)
        if fk == "sat":
            g = 8.0
            x = (np.clip(x.real * g, -1, 1) + 1j * np.clip(x.imag * g, -1, 1)).astype(np.complex64)
        return x.tobytes()

    def _stall(self, nbytes):
        """Flux figé (panne simulée) : on attend que les 3 s passent, sans rien livrer."""
        while not self.closed:
            f = sdr_demo_fault_now()
            if not f or f["kind"] != "stall" or time.time() - f["t0"] >= 3.0:
                break
            time.sleep(0.1)
        self.t0, self.n = time.monotonic(), 0
        return self.read(nbytes)

    def close(self):
        self.closed = True


class TxRunner:
    """Émission (étape 21) : un fil Python qui fabrique l'IQ (SigGen) et le donne à « hackrf_transfer -t - » ; ou, en
    démo, pose les signaux dans le SDR démo (rien n'est émis). Arrêt : stop(), fin de durée, outil qui s'arrête."""

    def __init__(self, fc, rate, sigs, until, exe=None, gain=0, amp=False, serial="", demo=False):
        self.fc, self.rate, self.sigs, self.until = float(fc), int(rate), list(sigs), float(until)
        self.exe, self.gain, self.amp, self.serial, self.demo = exe, int(gain), bool(amp), serial, bool(demo)
        self.err, self.sent, self.done, self.why = deque(maxlen=20), 0, False, ""
        self._stop = threading.Event()
        self.proc = None
        if demo:
            sdr_demo_set(tx=self.sigs)
            return
        argv = tx_cmd(exe, self.fc, self.rate, self.gain, self.amp, serial)
        self.proc = sdr_proc_track(subprocess.Popen([str(x) for x in argv], stdin=subprocess.PIPE,
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, bufsize=0,
                                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        threading.Thread(target=self._err, daemon=True).start()
        threading.Thread(target=self._run, daemon=True).start()

    def _err(self):
        try:
            for line in self.proc.stderr:
                t = line.decode(errors="ignore").strip()
                if t:
                    self.err.append(t)
        except Exception:  # noqa: BLE001
            pass

    def _run(self):
        g = SigGen(self.rate, self.fc, self.sigs, noise=0.0)
        n = int(self.rate * 0.02)
        tot = sum(0.3 * 10.0 ** (float(s_.get("lvl", 0.0)) / 20.0) for s_ in self.sigs) or 0.3
        scale = 0.9 / tot                            # somme des signaux juste sous la pleine échelle (pas d'écrêtage)
        try:
            while not self._stop.is_set() and time.time() < self.until:
                self.proc.stdin.write(iq_ci8(g.block(n), scale=scale))
                self.sent += n
        except (BrokenPipeError, OSError, ValueError) as e:
            self.why = self.err[-1] if self.err else str(e)
        finally:
            self._close()

    def running(self):
        if self.demo:
            return not self.done and time.time() < self.until
        return self.proc is not None and not self.done

    def _close(self):
        self.done = True
        p, self.proc = self.proc, None
        if p is None:
            return
        try:
            p.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            p.wait(timeout=2)
        except Exception:  # noqa: BLE001
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass

    def stop(self):
        self._stop.set()
        if self.demo:
            self.done = True
            sdr_demo_set(tx=[])
        elif self.proc is not None and threading.current_thread() is threading.main_thread():
            t0 = time.time()
            while self.proc is not None and time.time() - t0 < 2.0:
                time.sleep(0.05)
            self._close()


class WinradioIQ:
    """Source d'IQ = le DDC1 du G39DDC : type de DDC choisi d'après la largeur voulue (wr_pick_ddc), front-end +
    décalage DDC1 sur le centre demandé, rappel qui copie les échantillons (16 ou 32 bits). rate / dtype = ceux du
    type retenu (pas forcément le débit demandé : le démodulateur s'adapte). À ouvrir dans le fil qui lit."""

    def __init__(self, center, rate, gains, serial="", dll_dir="", lib=None, span=None):
        self.center = float(center)
        self.err = deque(maxlen=20)
        self.dev = d = WinradioG39(serial, lib=lib, dll_dir=dll_dir)
        want = float(span or rate * 0.8)
        if want > 4e6:
            try:
                d.call("SetDDC1Mode", WR_DDC1_MODE_WIDEBAND)
            except RuntimeError:
                pass
        cnt = _WR_U32(0)
        d.call("GetDDC1Count", 0, ctypes.byref(cnt))
        infos = []
        for i in range(int(cnt.value)):
            di = WR_DDC_INFO()
            if d.f["GetDDCInfo"](i, ctypes.byref(di)):
                infos.append((i, int(di.SampleRate), int(di.Bandwidth), int(di.BitsPerSample)))
        idx = wr_pick_ddc(infos, want)
        if idx is None:
            d.close()
            raise RuntimeError("G39DDC : aucun type de DDC1 disponible")
        _i, self.rate, self.bw, bits = next(x for x in infos if x[0] == idx)
        self.dtype = "ci16_le" if bits == 16 else "ci32_le"
        d.set_gains(gains or {})
        d.call("SetDDC1", 0, idx)
        fe = d.fe_round(self.center)
        d.call("SetFrontEndFrequency", fe)
        d.call("SetDDC1Frequency", 0, int(round(self.center - fe)))
        self.q, self.nb = deque(), IQ_BYTES[self.dtype]
        self.cb = WR_DDC1_CB(self._on_iq)
        d.set_callbacks(DDC1StreamCallback=self.cb)
        spb = max(64, int(self.rate * 0.02) // 64 * 64)
        d.call("StartDDC1", 0, spb)
        self.buf = b""

    def _on_iq(self, _ch, buf, n, bits, _ud):
        try:
            self.q.append(ctypes.string_at(buf, int(n) * 2 * int(bits) // 8))
        except Exception:  # noqa: BLE001
            pass

    def read(self, n):
        t0 = time.time()
        while len(self.buf) < n and time.time() - t0 < 2.0:
            if self.q:
                self.buf += self.q.popleft()
            else:
                time.sleep(0.005)
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def close(self):
        d, self.dev = self.dev, None
        if d is not None:
            try:
                d.f["StopDDC1"](d.h, 0)
            except Exception:  # noqa: BLE001
                pass
            d.close()


SDR_PROBE_RUNNER = None          # tests : fausse détection (argv -> (code, sortie)) à la place de l'outil réel


def sdr_probe(kind, model=None, gains=None, tool_dir="", iq_tool=None, secs=2.0, wr_lib=None):
    """Étape 14 (4.) : « Tester mon SDR » pour de vrai (sans Qt, dans un fil) : outil trouvé, SDR détecté par son
    outil, IQ reçu pendant `secs` secondes, débit tenu. -> {étape: (ok, détail)} (s'arrête à la 1re étape ratée)."""
    res = {}
    sp = SDR_KINDS.get(kind) or {}
    if kind == "winradio":
        dll = find_winradio_dll(tool_dir)
        res["tool"] = (bool(dll) or wr_lib is not None, dll or ("" if wr_lib is not None else
                                                                  TR("G39DDCAPI.dll introuvable : installe le logiciel WiNRADiO")))
        if not res["tool"][0]:
            return res
        res["seen"] = (None, TR("vérifié à l'ouverture du flux"))
    else:
        name, args, _pat = SDR_PROBE.get(kind) or SDR_PROBE["soapy"]
        exe = name if SDR_PROBE_RUNNER is not None else find_sdr_tool(name, tool_dir)
        if exe is None:
            res["tool"] = (False, TR("{} introuvable : dézippe le kit SDR à côté de l'appli (ou installe les outils)").format(name))
            return res
        res["tool"] = (True, str(exe))
        try:
            if SDR_PROBE_RUNNER is not None:
                code, out = SDR_PROBE_RUNNER([exe] + args)
            else:
                pr = subprocess.run([str(exe)] + args, capture_output=True, text=True, timeout=10,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                code, out = pr.returncode, (pr.stdout or "") + "\n" + (pr.stderr or "")
        except (OSError, subprocess.SubprocessError) as e:
            res["seen"] = (False, str(e)[:160])
            return res
        seen, det = probe_seen(kind, out)
        res["seen"] = (seen, det or TR("code de sortie {}").format(code))
        if not seen:
            return res
    m = model or {}
    rate = sdr_rate(m, kind) if m else sdr_iq_rate(kind)
    fmin, fmax = m.get("fmin", sp.get("fmin", 1.0)), m.get("fmax", sp.get("fmax", 2000.0))
    center = (600.0 if fmin <= 600.0 <= fmax else (fmin + fmax) / 2.0) * 1e6
    try:
        src = open_iq_source(kind, center, rate, gains or {}, tool=iq_tool, tool_dir=tool_dir, wr_lib=wr_lib)
    except RuntimeError as e:
        res["iq"] = (False, str(e)[:160])
        return res
    n, t0, first = 0, time.time(), None
    dog = threading.Timer(secs + 6.0, src.close)       # audit V8 : outil figé -> lecture débloquée, test terminé
    dog.daemon = True
    dog.start()
    try:
        nb = IQ_BYTES[src.dtype]
        while time.time() - t0 < secs + 3.0:
            d = src.read(65536)
            if not d:
                break
            if first is None:
                first, n = time.time(), 0              # débit compté après la mise en route
            n += len(d)
            if first is not None and time.time() - first >= secs:
                break
        dt = time.time() - first if first else 0.0
        err = list(src.err or ())
        rate = src.rate
    finally:
        dog.cancel()
        src.close()
    if not n:
        res["iq"] = (False, (err[-1] if err else TR("aucune donnée : SDR occupé par un autre logiciel ?"))[:160])
        return res
    res["iq"] = (True, TR("{} Mo en {} s").format(f"{n / 1e6:.1f}", f"{dt:.1f}"))
    ms, share = probe_rate(n, dt, rate, nb)
    res["rate"] = (share >= 0.9, TR("{} MS/s reçus sur {} demandés").format(f"{ms:g}", f"{rate / 1e6:g}")
                   + ("" if share >= 0.9 else " — " + TR("le PC ou l'USB ne suit pas (câble, port USB 3, autre logiciel)")))
    return res


def open_iq_source(kind, center, rate, gains, serial="", tool=None, tool_dir="", wr_lib=None, span=None):
    """Source d'IQ pour l'écoute / le temps réel : .read(n), .close(), .rate, .dtype, .err. Lève RuntimeError."""
    if kind == "demo":                               # étape 21 : SDR démo (signaux fabriqués par l'appli)
        return DemoIQ(center, rate)
    if kind == "winradio":
        return WinradioIQ(center, rate, gains, serial, tool_dir, lib=wr_lib, span=span)
    sp = SDR_KINDS[kind]
    exe = tool if tool is not None else find_sdr_tool(sp["iq_tool"], tool_dir)
    if exe is None:
        raise RuntimeError(f"{sp['iq_tool']} introuvable (outils {sp['name']} : PothosSDR / SoapySDR, ou 📡 Réglages SDR).")
    try:
        return ProcIQ(kind, exe, center, rate, gains, serial)
    except OSError as e:
        raise RuntimeError(f"Impossible de lancer {sp['iq_tool']} : {e}")


WINRADIO_LIB = None          # tests : fausse DLL (tests/fake_winradio.py) à la place de G39DDCAPI.dll
register_spectrum_driver("winradio", lambda a: (parse_sdr_addr(a) or ("",))[0] == "winradio",
                         lambda a, w: WinradioSweep(a, w.sdr_dir, w._tr, lib=WINRADIO_LIB))


SDR_INSTALL = {   # étape 7 : comment installer, par genre (fenêtre « Comment l'installer ? »)
    "hackrf": "Installe PothosSDR (il contient hackrf_sweep, hackrf_transfer et les pilotes). Si Windows ne voit pas le "
              "HackRF : pilote WinUSB avec Zadig.",
    "rtlsdr": "Installe PothosSDR (rtl_power, rtl_sdr). Pilote WinUSB avec Zadig (choisir « Bulk-In, Interface 0 »).",
    "sdrplay": "1. Installe l'API SDRplay (site sdrplay.com). 2. Installe PothosSDR (SoapySDR). 3. Ajoute le module "
               "SoapySDRPlay3 et les rx_tools (rx_power, rx_sdr).",
    "soapy": "1. Installe PothosSDR (SoapySDR + modules Airspy, Lime, Pluto, UHD, bladeRF). 2. Ajoute les rx_tools "
             "(rx_power, rx_sdr). 3. Branche le SDR : il doit apparaître dans « SoapySDRUtil --find ».",
    "winradio": "Installe le logiciel WiNRADiO G39DDC (il installe G39DDCAPI.dll et le pilote). Le récepteur doit être "
                "reconnu par son propre logiciel ; ferme ce logiciel avant de lancer la surveillance.",
}
SDR_SENS = [("low", "Basse (près des scènes, émetteurs forts)"), ("mid", "Normale"),
            ("high", "Haute (loin, micros faibles)")]


def sdr_sens_gains(model, sens):
    """Sensibilité simple (basse / normale / haute) -> valeur de chaque étage de gain du modèle (au pas près)."""
    out = {}
    for gk, _n, lo, hi, st, dflt in (model or {}).get("gains", []):
        if lo == 0 and hi == 1:                       # interrupteur (ampli, préampli) : seulement en « haute »
            v = 1 if sens == "high" else 0
        elif gk == "att":                             # atténuateur : à l'envers
            v = {"low": hi, "mid": lo, "high": lo}.get(sens, dflt)
        else:
            v = {"low": lo + 0.25 * (hi - lo), "mid": dflt, "high": lo + 0.85 * (hi - lo)}.get(sens, dflt)
        out[gk] = int(round((v - lo) / st) * st + lo)
    return out


class SdrDialog(QtWidgets.QDialog):
    """V8 : réglages SDR, version simple (étape 7, Clément : « usine à gaz ») : choisir SON SDR, voir s'il est prêt,
    une sensibilité en 3 crans ; la fiche technique et les réglages fins sont repliés."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Réglages SDR")
        c = owner.sdr_cfg
        self.models = dict(c.get("models") or {})
        self.gains = {k: dict(v) for k, v in (c.get("gains") or {}).items()}
        self._offs = dict(c.get("offsets") or {})
        lay = QtWidgets.QVBoxLayout(self)
        f = QtWidgets.QFormLayout()
        self.model_combo = QtWidgets.QComboBox()
        for m in SDR_MODELS:
            if m["kind"]:
                self.model_combo.addItem(m["name"], m["key"])
        self.model_combo.setToolTip("Ton SDR : l'appli adapte les débits, la largeur de la fenêtre, les gains et l'échelle\n"
                                    "des niveaux à ses caractéristiques (bits, plage, entrée max).")
        cur = c.get("model") or next(iter(self.models.values()), "hackrf_one")
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(cur)))
        f.addRow("Mon SDR :", self.model_combo)
        self.summary = QtWidgets.QLabel("")
        self.summary.setWordWrap(True)
        f.addRow("", self.summary)
        self.state = QtWidgets.QLabel("")
        self.state.setWordWrap(True)
        self.help_btn = QtWidgets.QPushButton("Comment l'installer ?")
        self.help_btn.setToolTip("Les étapes d'installation pour ce SDR (logiciels à installer sous Windows).")
        self.help_btn.clicked.connect(lambda *_: self._install_help())
        self.test_btn = QtWidgets.QPushButton("🔌 Tester mon SDR")      # étape 14 (4.) : un vrai essai
        self.test_btn.setToolTip("Essaie VRAIMENT le SDR branché (quelques secondes) : outil trouvé, SDR vu par son pilote,\n"
                                 "signal reçu, débit tenu. Ferme d'abord les autres logiciels qui l'utilisent.")
        self.test_btn.clicked.connect(lambda *_: self.run_probe())
        st_row = QtWidgets.QHBoxLayout()
        st_row.addWidget(self.state, 1)
        st_row.addWidget(self.test_btn)
        st_row.addWidget(self.help_btn)
        self.compat_btn = QtWidgets.QPushButton("📋 Tous les SDR")       # 8.2 : tableau de compatibilité
        self.compat_btn.setToolTip("Ce que l'appli sait faire avec chaque SDR (balayage, écoute, émission, dBm calibrés),\n"
                                   "et ce qui a été essayé avec le vrai matériel.")
        self.compat_btn.clicked.connect(lambda *_: owner.open_sdr_compat())
        st_row.addWidget(self.compat_btn)
        f.addRow("État :", st_row)
        self.probe_lbl = QtWidgets.QLabel("")
        self.probe_lbl.setWordWrap(True)
        self.probe_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        f.addRow("", self.probe_lbl)
        self.sens = QtWidgets.QComboBox()
        for k, t in SDR_SENS:
            self.sens.addItem(t, k)
        self.sens.setToolTip("Règle tous les gains du SDR d'un coup. Basse : près des scènes, quand des émetteurs forts\n"
                             "sont tout près (évite la saturation). Haute : antenne loin, micros faibles.")
        self.sens.activated.connect(lambda *_: self._apply_sens())
        f.addRow("Sensibilité :", self.sens)
        lay.addLayout(f)
        self.more = QtWidgets.QToolButton()
        self.more.setText("Réglages avancés")
        self.more.setCheckable(True)
        self.more.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.more.setArrowType(Qt.ArrowType.RightArrow)
        self.more.setToolTip("Fiche technique, gains étage par étage, dossier des outils, correction de niveau.")
        self.more.toggled.connect(lambda on: self._more(on))
        lay.addWidget(self.more)
        self.adv = QtWidgets.QWidget()
        av = QtWidgets.QVBoxLayout(self.adv)
        av.setContentsMargins(12, 0, 0, 0)
        self.sheet = QtWidgets.QLabel("")
        self.sheet.setWordWrap(True)
        self.sheet.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.sheet.setStyleSheet("padding:6px; border:1px solid rgba(128,128,128,.35); border-radius:8px")
        av.addWidget(self.sheet)
        self.gain_box = QtWidgets.QGroupBox("Gains de ce modèle")
        self.gain_box.setToolTip("Trop de gain = le SDR sature et invente des signaux (intermod interne) ; trop peu = les\n"
                                 "micros faibles disparaissent dans le bruit. Commence au milieu.")
        self.gain_form = QtWidgets.QFormLayout(self.gain_box)
        self.gain_w = {}
        av.addWidget(self.gain_box)
        af = QtWidgets.QFormLayout()
        self.dir_edit = QtWidgets.QLineEdit(c.get("dir", ""))
        self.dir_edit.setPlaceholderText("automatique (PATH, PothosSDR, dossier « outils », dossier WiNRADiO)")
        self.dir_edit.setToolTip("Dossier qui contient les outils (hackrf_sweep, rtl_power, rx_power…) ou la DLL WiNRADiO.\n"
                                 "Vide = recherche automatique.")
        browse = QtWidgets.QPushButton("Parcourir…")
        browse.setToolTip("Choisir le dossier des outils SDR.")
        browse.clicked.connect(lambda *_: self._browse())
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.dir_edit, 1)
        row.addWidget(browse)
        af.addRow("Dossier des outils :", row)
        self.off_spin = QtWidgets.QDoubleSpinBox()
        self.off_spin.setRange(-60.0, 60.0)
        self.off_spin.setDecimals(1)
        self.off_spin.setSuffix(" dB")
        self.off_spin.setToolTip("Ajouté aux niveaux de ce SDR pendant l'écoute (dBFS -> dBm à peu près), pour que la\n"
                                 "surveillance pendant l'écoute ait la même échelle que le tinySA. 0 pour un WiNRADiO\n"
                                 "(déjà en dBm). Le plus juste : la calibration automatique avec un tinySA.")
        af.addRow("Correction de niveau (écoute) :", self.off_spin)
        self.rec_spin = QtWidgets.QSpinBox()
        self.rec_spin.setRange(1, 2000)
        self.rec_spin.setValue(int(c.get("rec_max_gb", 20)))
        self.rec_spin.setSuffix(" Go")
        self.rec_spin.setToolTip("Taille maximale d'un enregistrement IQ (⏱ Temps réel) : il s'arrête tout seul au-delà\n"
                                 "(et quand il reste moins de 2 Go sur le disque).")
        af.addRow("Enregistrement IQ max :", self.rec_spin)
        self.keep_combo = QtWidgets.QComboBox()           # étape 12 : durée de conservation (son, IQ, incidents)
        for k_ in KEEP_DAYS:
            self.keep_combo.addItem(keep_text(k_, TR), k_)
        self.keep_combo.setCurrentIndex(max(0, self.keep_combo.findData(owner.privacy()["keep_days"])))
        self.keep_combo.setToolTip("Le son, l'IQ et les dossiers d'incident plus vieux que ça sont effacés tout seuls\n"
                                   "(ils contiennent des voix : ne les garde pas plus que nécessaire).")
        self.priv_btn = QtWidgets.QPushButton("Pourquoi ?")
        self.priv_btn.setToolTip("Ce qu'il faut savoir avant d'enregistrer du son.")
        self.priv_btn.clicked.connect(lambda *_: QtWidgets.QMessageBox.information(self, TR("Son enregistré et vie privée"),
                                                                                    TR(PRIVACY_TEXT)))
        f.addRow("Enregistrements gardés :", owner._row(self.keep_combo, self.priv_btn, None))
        av.addLayout(af)
        lay.addWidget(self.adv)
        self.adv.hide()
        lay.addStretch(1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._key = None
        self.dir_edit.textChanged.connect(lambda *_: self._found())
        self.model_combo.currentIndexChanged.connect(lambda *_: self._model())
        self._model()
        fit_dialog(self, 560, 300)

    def _more(self, on):
        self.adv.setVisible(on)
        self.more.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.adjustSize()

    def _keep(self):
        """Mémorise les gains du modèle affiché avant d'en changer."""
        if self._key:
            self.gains[self._key] = {k: (int(w.isChecked()) if isinstance(w, QtWidgets.QCheckBox) else int(w.value()))
                                     for k, w in self.gain_w.items()}
            self._offs[self._key] = float(self.off_spin.value())

    def _model(self):
        self._keep()
        key = self.model_combo.currentData()
        m = sdr_model(key)
        self._key = key
        self.sheet.setText(sdr_model_text(m, TR))
        bits = (m or {}).get("bits")
        span = sdr_span_mhz(m, max(m["rates"])) if m and m.get("rates") else None
        self.summary.setText(" · ".join(x for x in (
            f"{m['fmin']:g} – {m['fmax']:g} MHz" if m else "",
            TR("{} bits").format(bits) if bits else "",
            TR("fenêtre jusqu'à {} MHz").format(f"{span:.1f}") if span else "",
            TR("niveaux en dBm") if (m or {}).get("cal") else TR("niveaux à caler"),
            TR("balaye, écoute et démodule") if m and device_caps(m["kind"], m)["iq"] else "") if x))
        while self.gain_form.rowCount():
            self.gain_form.removeRow(0)
        self.gain_w = {}
        g0 = self.gains.get(key, {})
        for gk, name, lo, hi, st, dflt in (m or {}).get("gains", []):
            if lo == 0 and hi == 1:
                w = QtWidgets.QCheckBox(name)
                w.setChecked(bool(g0.get(gk, dflt)))
                w.setToolTip(name)
                self.gain_form.addRow(w)
            else:
                w = QtWidgets.QSpinBox()
                w.setRange(int(lo), int(hi))
                w.setSingleStep(int(st))
                w.setValue(int(g0.get(gk, dflt)))
                w.setSuffix(" dB" if "linéarité" not in name else "")
                w.setToolTip(f"{name} : {lo} à {hi}, par pas de {st}.")
                self.gain_form.addRow(name + " :", w)
            self.gain_w[gk] = w
        self.gain_box.setVisible(bool(self.gain_w))
        self.off_spin.setValue(float(self._offs.get(key, 0.0)))
        self.off_spin.setEnabled(not (m or {}).get("cal"))
        cur = {k: (int(w.isChecked()) if isinstance(w, QtWidgets.QCheckBox) else int(w.value()))
               for k, w in self.gain_w.items()}
        k_ = next((s for s, _t in SDR_SENS if sdr_sens_gains(m, s) == cur), "")
        self.sens.setCurrentIndex(self.sens.findData(k_) if k_ else 1)
        self._found()

    def _apply_sens(self):
        m = sdr_model(self.model_combo.currentData())
        for gk, v in sdr_sens_gains(m, self.sens.currentData()).items():
            w = self.gain_w.get(gk)
            if isinstance(w, QtWidgets.QCheckBox):
                w.setChecked(bool(v))
            elif w is not None:
                w.setValue(int(v))

    def _missing(self):
        """Outils / DLL qui manquent pour le modèle choisi."""
        m = sdr_model(self.model_combo.currentData())
        sp = SDR_KINDS.get((m or {}).get("kind"), {})
        d = self.dir_edit.text().strip()
        miss = [t for t in (sp.get("tool"), sp.get("iq_tool")) if t and not find_sdr_tool(t, d)]
        if sp.get("dll") and not find_winradio_dll(d, sp["dll"]):
            miss.append(sp["dll"])
        return miss

    def _found(self):
        miss = self._missing()
        ok = not miss
        self.state.setText(TR("✔ Prêt") if ok else TR("✗ Il manque : {}").format(", ".join(miss)))
        self.state.setStyleSheet("" if ok else f"color: {self.owner.theme.get('st_weak', '#d29922')};")

    def run_probe(self):
        """🔌 Tester mon SDR (dans un fil : la fenêtre reste utilisable)."""
        o = self.owner
        m = sdr_model(self.model_combo.currentData())
        if not m or not m.get("kind"):
            self.probe_lbl.setText(TR("Ce modèle n'est pas pris en charge."))
            return None
        busy = [d for d in (getattr(o, "_multimon", None), getattr(o, "_listen", None), getattr(o, "_rt", None))
                if d is not None and getattr(d, "worker", None) is not None]
        if busy:
            self.probe_lbl.setText(TR("⚠ Le SDR est utilisé (moniteur, écoute ou temps réel) : arrête-les d'abord."))
            return None
        kind, d_ = m["kind"], self.dir_edit.text().strip()
        self.test_btn.setEnabled(False)
        self.probe_lbl.setText(TR("… essai en cours (quelques secondes)"))

        def done(res, err):
            self.test_btn.setEnabled(True)
            if err is not None:
                self.probe_lbl.setText(TR("✗ Essai impossible : {}").format(err))
                return
            lines, ok = probe_report(res, TR)
            self.last_probe = (res, ok)
            head = TR("✔ Ton SDR marche : il peut surveiller et écouter.") if ok else \
                TR("✗ Il y a un souci : regarde la 1re ligne en rouge, puis « Comment l'installer ? ».")
            self.probe_lbl.setText(head + "\n" + "\n".join(lines))
            self.probe_lbl.setStyleSheet(f"color: {o.tone_color('ok' if ok else 'bad')};")
        return o.run_heavy(lambda: sdr_probe(kind, m, o.sdr_gains(kind), d_, getattr(o, "_listen_tool", None),
                                             wr_lib=WINRADIO_LIB), done, None, TR("Essai du SDR"))

    def _install_help(self):
        m = sdr_model(self.model_combo.currentData())
        k = (m or {}).get("kind", "")
        txt = SDR_INSTALL.get(k) or SDR_INSTALL["soapy"]
        if k != "winradio":
            txt = TR(SDR_KIT_HINT) + "\n\n" + TR(txt)
        QtWidgets.QMessageBox.information(self, TR("Installer {}").format(m["name"] if m else "SDR"), TR(txt))

    def _browse(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier des outils SDR", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def values(self):
        self._keep()
        key = self.model_combo.currentData()
        m = sdr_model(key)
        models = dict(self.models)
        if m and m["kind"]:
            models[m["kind"]] = key
        out = dict(dir=self.dir_edit.text().strip(), rec_max_gb=self.rec_spin.value(), model=key, models=models,
                   gains=self.gains, offsets=dict(self._offs),
                   privacy=dict(self.owner.privacy(), keep_days=self.keep_combo.currentData()))
        g = self.gains.get(key, {})              # compatibilité : anciens réglages globaux = ceux du modèle choisi
        for k_ in ("lna", "vga", "amp"):
            if k_ in g:
                out[k_] = bool(g[k_]) if k_ == "amp" else int(g[k_])
        return out


class DemodPick:
    """Préréglage + mode + compander + désaccentuation (listes liées) : choisir un préréglage remplit le reste,
    toucher le reste passe en « ✏ Réglages à la main ». params() -> réglages pour ChannelDemod."""

    def __init__(self, on_change=None):
        self.pre = QtWidgets.QComboBox()
        for k, n, _d, why in DEMOD_PRESETS:
            self.pre.addItem(n, k)
            self.pre.setItemData(self.pre.count() - 1, why, Qt.ItemDataRole.ToolTipRole)
        self.pre.addItem(DEMOD_CUSTOM, "")
        self.pre.setToolTip("Préréglage par type d'appareil : déviation, largeur du canal, bande audio, "
                            "désaccentuation, compander.\nValeurs de départ (fiches techniques), à ajuster à "
                            "l'oreille : non vérifiées sur les vrais appareils.")
        self.mode = QtWidgets.QComboBox()
        for k, md in LISTEN_MODES.items():
            self.mode.addItem(md["name"], k)
        self.mode.setToolTip("FM large = micros HF / ears analogiques ; FM étroite = talkies ; AM = aviation.")
        self.comp = QtWidgets.QComboBox()
        for k, t in LISTEN_COMPANDERS.items():
            self.comp.addItem(t, k)
        self.comp.setToolTip("Expanseur 2:1 générique : approximation des companders des marques (non publiés).")
        self.de = QtWidgets.QComboBox()
        for t, v in (("50 µs (Europe)", 50.0), ("75 µs", 75.0), ("aucune", 0.0)):
            self.de.addItem(t, v)
        self.de.setToolTip("Désaccentuation (atténue le souffle aigu) : 50 µs en général.")
        self.on_change = on_change
        self._busy = False
        self.pre.currentIndexChanged.connect(lambda *_: self._preset())
        for c in (self.mode, self.comp, self.de):
            c.currentIndexChanged.connect(lambda *_: self._manual())
        self._preset()

    def _preset(self):
        d = demod_preset(self.pre.currentData())
        if d is not None:
            self._busy = True
            self.mode.setCurrentIndex(max(0, self.mode.findData(d["mode"])))
            self.comp.setCurrentIndex(max(0, self.comp.findData(d["comp"])))
            self.de.setCurrentIndex(max(0, self.de.findData(float(d["deemph"]))))
            self._busy = False
        if self.on_change:
            self.on_change()

    def _manual(self):
        if self._busy:
            return
        self.pre.blockSignals(True)
        self.pre.setCurrentIndex(self.pre.count() - 1)
        self.pre.blockSignals(False)
        if self.on_change:
            self.on_change()

    def widgets(self):
        return (self.pre, self.mode, self.comp, self.de)

    def params(self):
        d = demod_preset(self.pre.currentData()) or {}
        return dict(mode=self.mode.currentData(), compander=self.comp.currentData(), deemph=self.de.currentData(),
                    dev=d.get("dev"), cut=d.get("cut"), audio=d.get("audio"))


class ListenWorker(QtCore.QThread):
    """V8 : écoute d'un SDR. Lance hackrf_transfer / rtl_sdr (IQ brut sur stdout), démodule jusqu'à 4 canaux
    (ChannelDemod), met l'audio du canal choisi (ou le mélange) dans une file lue par AudioOut dans le fil de
    l'interface, et donne les niveaux (RF dBFS, audio) environ 10 fois par seconde."""
    levels = Signal(object)          # [(niveau RF dBFS, crête audio 0..1)] par canal
    status = Signal(str)
    stopped = Signal(str)            # raison de l'arrêt ("" = demandé)
    spectrum = Signal(object, object)   # étape 7 : (F MHz, niveaux dBFS) de la fenêtre, 2 fois par seconde
    MAX_CH = 4
    SPEC_FFT = 2048

    def __init__(self, kind, center_hz, channels, mode="wfm", deemph_us=50.0, squelch=None, compander="none",
                 gains=None, serial="", tool=None, tool_dir="", dev=None, cut=None, audio=None):
        super().__init__()
        self.kind, self.center, self.serial = kind, float(center_hz), serial
        self.rate = sdr_iq_rate(kind)
        self.channels = list(channels)[:self.MAX_CH]        # MHz
        self.opts = dict(mode=mode, deemph_us=deemph_us, squelch=squelch, compander=compander, dev=dev, cut=cut,
                         audio=audio)
        self.gains = dict(lna=24, vga=20, amp=False)
        self.gains.update(gains or {})
        self.tool, self.tool_dir = tool, tool_dir
        self.sel = 0                 # canal entendu ; -1 = mélange de tous
        self.volume = 1.0
        self.audio = deque(maxlen=200)
        self.tap = deque(maxlen=400)  # étape 6 : copie du son (enregistrement WAV, téléphone), lue par ListenDialog
        self.proc = self.src = None
        self.err = deque(maxlen=20)
        self.span = None              # étape 7 : largeur voulue (WiNRADiO : choix du type de DDC)
        self.want_spec = False        # étape 7 : envoyer le spectre de la fenêtre (surveillance pendant l'écoute)

    def run(self):
        sp = SDR_KINDS[self.kind]
        try:                                    # étape 7 : outil (HackRF, RTL, SoapySDR) ou DLL WiNRADiO
            src = self.src = open_iq_source(self.kind, self.center, self.rate, self.gains, self.serial, self.tool,
                                            self.tool_dir, wr_lib=WINRADIO_LIB, span=self.span)
        except RuntimeError as e:
            self.stopped.emit(str(e))
            return
        self.rate, self.err = src.rate, src.err
        demods = [ChannelDemod(self.rate, f * 1e6 - self.center, **self.opts) for f in self.channels]
        self.status.emit(f"🎧 {sp['name']} : écoute autour de {self.center / 1e6:.3f} MHz")
        chunk = int(self.rate * 0.02) * IQ_BYTES[src.dtype]   # 20 ms d'IQ
        buf, why, t_lv, spec, t_sp = b"", "", 0.0, [], time.time()
        try:
            while not self.isInterruptionRequested():
                data = src.read(chunk - len(buf))
                if not data:
                    time.sleep(0.1)
                    why = (self.err[-1] if self.err else "flux coupé") + f" — {sp['name']} débranché ou occupé ?"
                    break
                buf += data
                if len(buf) < chunk:
                    continue
                iq, buf = iq_decode(src.dtype, buf), b""
                outs = [d.process(iq) for d in demods]
                sel = self.sel
                if sel < 0 or sel >= len(outs):
                    nn_ = min((len(o[0]) for o in outs), default=0)
                    a = (np.sum([to_stereo(o[0])[:nn_] for o in outs], axis=0) / max(1, len(outs))
                         if outs else np.zeros(0))
                else:
                    a = outs[sel][0]
                if len(a):
                    pcm = audio_int16(a, self.volume)
                    self.audio.append(pcm)
                    self.tap.append(pcm)
                now = time.time()
                if now - t_lv > 0.1:
                    t_lv = now
                    self.levels.emit([(lv, float(np.max(np.abs(o))) if len(o) else 0.0, d_.pilot, d_.health)
                                      for (o, lv), d_ in zip(outs, demods)])
                if self.want_spec:                   # étape 7 : spectre de la fenêtre -> surveillance pendant l'écoute
                    avg, _mx = rt_frames(iq, self.SPEC_FFT)
                    if avg is not None:
                        spec.append(avg)
                    if now - t_sp >= 0.5 and spec:
                        t_sp = now
                        L = np.max(np.array(spec), axis=0)
                        spec = []
                        self.spectrum.emit(rt_freqs(self.center, self.rate, self.SPEC_FFT), L)
        finally:
            self._kill()
        self.stopped.emit(why)

    def _read_err(self):
        try:
            for line in self.proc.stderr:
                t = line.decode(errors="ignore").strip()
                if t:
                    self.err.append(t)
        except Exception:  # noqa: BLE001
            pass

    def _kill(self):
        s, self.src = getattr(self, "src", None), None
        if s is not None:
            s.close()


class AudioOut:
    """Sortie son 48 kHz stéréo 16 bits (QtMultimedia), nourrie depuis une file d'octets par un minuteur."""

    def __init__(self, parent=None, device=""):
        self.sink = self.io = None
        self.error = ""
        try:
            from PySide6 import QtMultimedia
            fmt = QtMultimedia.QAudioFormat()
            fmt.setSampleRate(LISTEN_RATE)
            fmt.setChannelCount(2)                                 # stéréo (FM stéréo, ears) ; mono = 2 voies égales
            fmt.setSampleFormat(QtMultimedia.QAudioFormat.SampleFormat.Int16)
            dev = QtMultimedia.QMediaDevices.defaultAudioOutput()
            for d in (QtMultimedia.QMediaDevices.audioOutputs() if device else ()):   # 8.1 : sortie choisie
                if bytes(d.id()).hex() == device or d.description() == device:
                    dev = d
                    break
            if dev.isNull():
                self.error = "aucune sortie son trouvée"
                return
            self.sink = QtMultimedia.QAudioSink(dev, fmt, parent)
            self.sink.setBufferSize(LISTEN_RATE * 4 // 2)        # 500 ms demandés (Windows peut en donner moins)
            self.io = self.sink.start()
        except Exception as e:  # noqa: BLE001
            self.error = f"sortie son indisponible ({e})"
            self.sink = self.io = None

    MAX_LAG = LISTEN_RATE * 4 * 6 // 10                          # 0,6 s d'avance au plus (octets, stéréo 16 bits)

    def feed(self, q):
        """Remplit TOUT l'espace libre de la carte son, quitte à couper un morceau (8.1, Clément : « toujours saccadé ») :
        avant, un morceau n'était écrit que s'il tenait en entier -> sous Windows (tampon à peine plus grand qu'un
        morceau) la carte tombait à sec à chaque fois. Le retard au-delà de 0,6 s est jeté (pas d'écho qui grandit)."""
        if self.io is None:
            q.clear()
            return
        queued = sum(map(len, list(q)))                           # instantané : l'interface ajoute en même temps
        while q and queued > self.MAX_LAG:
            queued -= len(q.popleft())
        free = self.sink.bytesFree()
        free -= free % 4                                          # trames entières (2 voies × 16 bits)
        while q and free > 0:
            b = q[0]
            n = min(len(b), free)
            self.io.write(bytes(b[:n]))
            free -= n
            if n < len(b):
                q[0] = b[n:]
            else:
                q.popleft()

    def close(self):
        if self.sink is not None:
            try:
                self.sink.stop()
            except Exception:  # noqa: BLE001
                pass
        self.sink = self.io = None


def sdr_audio_device(owner):
    """8.1 (Clément : « l'audio du SDR sort sur la sortie de Windows, pas celle choisie dans Réglages ») : sortie de
    l'écoute SDR. sdr_cfg « audio_dev » : "" = la même que les sons de l'appli (⚙ › Son), « __win__ » = celle de
    Windows, sinon une sortie précise (casque pour l'écoute, enceintes pour les alarmes…)."""
    k = str((getattr(owner, "sdr_cfg", None) or {}).get("audio_dev") or "")
    if k == "__win__":
        return ""
    if not k:
        snd = getattr(owner, "sound", None)
        return str(((getattr(snd, "cfg", None) or {}).get("device")) or "")
    return k


def pump_move(src, dst):
    """Passe le son produit (file du fil SDR) dans la file de la carte son (AudioPump)."""
    while src:
        dst.append(src.popleft())


class AudioPump(QtCore.QThread):
    """8.1 (Clément : « l'audio saccade sur un micro du SDR, pas en Écouter ici ») : la carte son est nourrie par SON
    fil, indépendant de l'interface. Avant, un spectre / waterfall un peu lent à redessiner retardait l'envoi et la
    carte tombait à sec. La file `q` (deque) est remplie par l'interface, vidée ici (opérations de deque atomiques)."""

    def __init__(self, q, device=""):
        super().__init__()
        self.q, self.out, self.error, self.device = q, None, "", device
        self.src, self.side = None, None    # 8.1 (vidéo de Clément, son haché 0,8 s / 1,4 s) : le fil va chercher le son
        #                                     LUI-MÊME à la source (src = file du fil de calcul) ; une copie part dans
        #                                     `side` pour l'interface (WAV, ⏪, spectre du son), sans la retarder

    def _move(self):
        src, side = self.src, self.side
        if src is not None:
            while src:
                b = src.popleft()
                self.q.append(b)
                if side is not None:
                    side.append(b)
        self.out.feed(self.q)

    def run(self):
        self.out = AudioOut(None, self.device)
        self.error = self.out.error
        tm = QtCore.QTimer()
        tm.timeout.connect(lambda: self._move())       # lambda : exécuté dans CE fil (une méthode de l'objet QThread,
        #                                                qui vit dans le fil de l'interface, y serait renvoyée)
        tm.start(5)
        self.exec()
        tm.stop()
        self.out.close()

    def feed(self, q):
        pass                                             # c'est le fil qui nourrit la carte

    def close(self):
        self.quit()
        self.wait(2000)


class ListenDialog(QtWidgets.QDialog):
    """V8 : 🎧 Écouter une ou plusieurs fréquences avec un SDR (FM / AM), niveau RF et audio de chaque canal,
    choix de celui qu'on entend, squelch, expanseur 2:1 (approximation des companders)."""

    def __init__(self, owner, rows=None, freqs=None):
        super().__init__(owner)
        self._aq = deque(maxlen=200)                      # 8.1 : file de la carte son (AudioPump)
        self.owner = owner
        self.setWindowTitle("🎧 Écouter avec le SDR")
        self.wav = self.wav_path = None                 # étape 6 : ⏺ son enregistré
        self._wins, self._wi, self.hop, self._hop_floor = [], 0, HopState(), None
        self._t_hop = 0.0
        self.resize(760, 600)
        self.worker, self.audio, self.paused = None, None, []
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Coche jusqu'à 4 fréquences <b>proches</b> (elles doivent tenir dans la fenêtre du SDR : ±1,9 MHz pour un "
            "HackRF, ±0,9 MHz pour un RTL-SDR), puis ▶ Écouter. Les micros <b>analogiques</b> s'écoutent (FM large) ; "
            "les <b>numériques</b> (ULX-D, Axient D, EW-D / DX, 6000, Spectera…) non : codecs propriétaires, souvent "
            "chiffrés. Pendant l'écoute, le balayage de ce SDR est en pause (un tinySA continue de surveiller).")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 4)
        lay.addWidget(info)
        R = owner._row
        self.dev_combo = QtWidgets.QComboBox()
        for k, sp in SDR_KINDS.items():
            self.dev_combo.addItem(f"📡 {sp['name']} ({sp.get('iq_tool') or sp.get('dll')})", k)
        pk = parse_sdr_addr(owner.port_combo.currentData() or "") or parse_sdr_addr(owner.dev2.get("addr", ""))
        if pk:
            self.dev_combo.setCurrentIndex(max(0, self.dev_combo.findData(pk[0])))
        self.dev_combo.setToolTip("Le SDR qui écoute (il faut ses outils : hackrf_transfer / rtl_sdr).")
        self.dp = DemodPick()
        self.pre_combo, self.mode_combo, self.comp_combo, self.de_combo = self.dp.widgets()
        self.sq_spin = QtWidgets.QSpinBox()
        self.sq_spin.setRange(-121, 0)
        self.sq_spin.setValue(-121)
        self.sq_spin.setSpecialValueText("ouvert")
        self.sq_spin.setSuffix(" dBFS")
        self.sq_spin.setToolTip("Squelch : coupe le son d'un canal quand son niveau RF est sous ce seuil.")
        self.vol = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 200)
        self.vol.setValue(100)
        self.vol.setToolTip("Volume.")
        self.vol.valueChanged.connect(lambda v: self.worker is not None and setattr(self.worker, "volume", v / 100.0))
        lay.addLayout(R("SDR :", self.dev_combo, "Préréglage :", self.pre_combo, None))
        lay.addLayout(R("Mode :", self.mode_combo, "Compander :", self.comp_combo, "Désaccentuation :", self.de_combo,
                        None))
        lay.addLayout(R("Squelch :", self.sq_spin, "Volume :", self.vol, None))
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Écouter", "Nom", "MHz", "Niveau RF", "Audio", "Type · santé du micro"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        for c, w_ in enumerate((70, 170, 90, 210, 110)):
            self.table.setColumnWidth(c, w_)
        self.table.setWordWrap(False)
        self.table.horizontalHeaderItem(5).setToolTip(
            "Tonalité au-dessus de l'audio dans le signal FM : pilote de squelch (Sennheiser, Shure…), données\n"
            "(batterie, télécommande) ou pilote stéréo 19 kHz. Sa présence dit que l'émetteur est bien là ;\n"
            "le CONTENU (niveau de batterie) n'est pas décodé : protocoles des marques non publiés.")
        self.table.setToolTip("Coche les fréquences à démoduler ; pendant l'écoute, clique une ligne pour l'entendre.")
        self.table.cellClicked.connect(lambda r, c: self._pick(r))
        lay.addWidget(self.table, 1)
        self.win_lbl = QtWidgets.QLabel("")
        self.win_lbl.setWordWrap(True)
        lay.addWidget(self.win_lbl)
        self.mix_chk = QtWidgets.QCheckBox("Mélanger tous les canaux")
        self.mix_chk.setToolTip("Entendre tous les canaux démodulés en même temps (sinon : la ligne choisie).")
        self.mix_chk.toggled.connect(lambda *_: self._pick(None))
        self.go_btn = QtWidgets.QPushButton("▶ Écouter")
        self.go_btn.setToolTip("Lance / arrête l'écoute.")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Arrête l'écoute et ferme.")
        close.clicked.connect(self.close)
        lay.addLayout(R(self.go_btn, self.mix_chk, None, close))
        # étape 6 : enregistrer le son, son seulement sur le téléphone, balayage d'écoute
        self.rec_btn = QtWidgets.QPushButton("⏺ Enregistrer le son")
        self.rec_btn.setCheckable(True)
        self.rec_btn.setToolTip("Enregistre ce que tu entends (fichier WAV 48 kHz stéréo) dans le dossier des journaux,\n"
                                "« enregistrements_audio » : pour garder la preuve d'un brouilleur, d'un larsen, d'une coupure.")
        self.rec_btn.toggled.connect(lambda on: self.toggle_rec(on))
        self.pc_mute = QtWidgets.QCheckBox("🔇 Son seulement sur le téléphone")
        self.pc_mute.setToolTip("Coupe le son de ce PC (la page web 🎧 Écoute continue d'en recevoir).")
        self.hop_chk = QtWidgets.QCheckBox("🔁 Balayage d'écoute")
        self.hop_chk.setToolTip("Les fréquences cochées ne tiennent pas dans une seule fenêtre du SDR : il passe de l'une à\n"
                                "l'autre et s'arrête là où ça parle (niveau au-dessus du squelch ; squelch ouvert : 12 dB\n"
                                "au-dessus du canal le plus calme vu),\n"
                                "le temps de la phrase. Comme un scanner. Quelques dixièmes de seconde de blanc à chaque saut.")
        self.hop_chk.toggled.connect(lambda *_: self._window())
        self.dwell = QtWidgets.QComboBox()
        for s_ in LISTEN_HOP_DWELL:
            self.dwell.addItem(f"{s_} s par fenêtre", s_)
        self.dwell.setCurrentIndex(1)
        self.dwell.setToolTip("Temps passé sur une fenêtre où rien ne parle.")
        lay.addLayout(R(self.rec_btn, self.pc_mute, None, self.hop_chk, self.dwell))
        self.auto_chk = QtWidgets.QCheckBox("⏺ Sur alarme : garder le son (10 s avant, 10 s après)")
        self.auto_chk.setChecked(owner.privacy()["alarm_audio"] and owner.privacy()["ack"])   # étape 12 : accord
        self.auto_chk.toggled.connect(lambda on: self._auto_toggled(on))
        self.auto_chk.setToolTip("Quand une alarme (conflit, absent) part sur une fréquence de la fenêtre écoutée, le son des\n"
                                 "10 secondes d'avant et des 10 suivantes est enregistré en WAV (preuve du brouillage),\n"
                                 "dans « enregistrements_audio », et noté au journal.")
        self.rec_badge = QtWidgets.QLabel("")           # étape 12 : on voit toujours si du son est enregistré
        self.rec_badge.setToolTip("Rouge = du son est enregistré en ce moment ; orange = il le sera si une alarme part.\n"
                                  "Les enregistrements sont effacés tout seuls après la durée choisie (📡 Réglages SDR).")
        lay.addLayout(R(self.auto_chk, None, self.rec_badge))
        self.pre = PreRing(10.0, LISTEN_RATE * 4)
        self._auto, self._seen, self._t_al, self._types = None, set(), 0.0, {}
        self.mon_lbl = QtWidgets.QLabel("")            # étape 7 : surveillance pendant l'écoute
        self.mon_lbl.setWordWrap(True)
        self.mon_lbl.setToolTip("Pendant l'écoute, le spectre de la fenêtre du SDR sert aussi à surveiller tes fréquences\n"
                                "qui y tombent (si le SDR est ton appareil de surveillance). Un tinySA branché garde\n"
                                "la surveillance de tout.")
        lay.addWidget(self.mon_lbl)
        self.st_lbl = QtWidgets.QLabel("Pas encore testé avec un vrai SDR : dis-moi ce que ça donne !")
        self.st_lbl.setWordWrap(True)
        lay.addWidget(self.st_lbl)
        self.ws = list(owner.watch)
        pre = {id(owner.watch[r]) for r in (rows or []) if 0 <= r < len(owner.watch)}
        for f_ in freqs or ():                       # étape 6 : une fréquence hors de la liste (alarme, chasse…)
            w_ = next((w for w in self.ws if abs(w["freq"] - f_) < 0.0005), None)
            if w_ is None:
                w_ = dict(name=f"📍 {f_:.3f}", freq=float(f_))
                self.ws.insert(0, w_)
            pre.add(id(w_))
        self.table.setRowCount(len(self.ws))
        for r, w in enumerate(self.ws):
            it = QtWidgets.QTableWidgetItem("")
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked if id(w) in pre else Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, it)
            for c, v in ((1, w["name"] or "—"), (2, f"{w['freq']:.3f}"), (3, ""), (4, ""), (5, "")):
                self.table.setItem(r, c, QtWidgets.QTableWidgetItem(v))
        self.table.itemChanged.connect(lambda *_: self._window())
        self.dev_combo.currentIndexChanged.connect(lambda *_: self._window())
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._feed)
        self._sel_row = None
        self._window()

    def _checked(self):
        return [r for r in range(self.table.rowCount())
                if self.table.item(r, 0) is not None and self.table.item(r, 0).checkState() == Qt.CheckState.Checked]

    def _window(self):
        if self.worker is not None:      # écoute en cours : la fenêtre ne bouge pas (setText du tableau = itemChanged)
            return
        rows = self._checked()
        kind = self.dev_combo.currentData()
        c, use = listen_center([self.ws[r]["freq"] for r in rows], kind)
        self._plan = (c, [r for r in rows if self.ws[r]["freq"] in use][:ListenWorker.MAX_CH])
        wins = listen_windows([self.ws[r]["freq"] for r in rows], kind, ListenWorker.MAX_CH) if rows else []
        self._wins = [(c_, [r for r in rows if self.ws[r]["freq"] in u_]) for c_, u_ in wins]
        if self.worker is None:
            self.hop_chk.setEnabled(len(self._wins) > 1)
        m_ = self.owner.sdr_model_for(kind)
        if m_ is not None:                             # étape 7 : la fenêtre dépend du modèle (débit, bits)
            self.win_lbl.setToolTip(sdr_model_text(m_, TR))
        if not rows:
            self.win_lbl.setText("Coche au moins une fréquence.")
        elif self.hop_chk.isChecked() and len(self._wins) > 1:
            self.win_lbl.setText(f"🔁 Balayage d'écoute : {len(self._wins)} fenêtres du SDR, {len(rows)} fréquence(s).")
        else:
            out = [r for r in rows if r not in self._plan[1]]
            self.win_lbl.setText(f"Fenêtre du SDR centrée sur {c / 1e6:.3f} MHz : {len(self._plan[1])} canal(aux) "
                                 "démodulé(s)" + (f" · ⚠ {len(out)} trop loin (ou au-delà de 4) : pas écoutée(s)"
                                                  if out else "") + ".")

    def _pick(self, r):
        if r is not None and self.worker is not None and r in self._plan[1]:
            self._sel_row = r
        if self.worker is not None:
            idx = self._plan[1].index(self._sel_row) if self._sel_row in self._plan[1] else 0
            self.worker.sel = -1 if self.mix_chk.isChecked() else idx
            for rr in self._plan[1]:
                it = self.table.item(rr, 1)
                on = self.mix_chk.isChecked() or rr == self._plan[1][idx]
                it.setText(("🔊 " if on else "") + (self.ws[rr]["name"] or "—"))

    def toggle(self):
        if self.worker is not None:
            self.stop()
            return
        c, rows = self._plan
        if not rows:
            self.st_lbl.setText("Coche au moins une fréquence (proches les unes des autres).")
            return
        if self.hop_chk.isChecked() and len(self._wins) > 1:
            self._wi = 0
            c, rows = self._wins[0]
            self._plan = (c, rows)
            self.hop.dwell = float(self.dwell.currentData() or 3)
            self.hop.reset(time.time())
            self._hop_floor = None
        self._start(c, rows)

    def _start(self, c, rows, hopping=False):
        """Lance (ou relance, balayage d'écoute) le ListenWorker sur une fenêtre du SDR."""
        kind = self.dev_combo.currentData()
        o = self.owner
        m_ = o.sdr_model_for(kind)
        out_ = [self.ws[r]["freq"] for r in rows if m_ is not None and not sdr_in_range(m_, self.ws[r]["freq"])]
        if out_:                                       # étape 7 : hors de la plage du modèle
            self.st_lbl.setText(TR("⚠ {} : hors de la plage du {} ({} – {} MHz).").format(
                ", ".join(f"{f:.3f}" for f in out_), m_["name"], f"{m_['fmin']:g}", f"{m_['fmax']:g}"))
            return
        rt = getattr(o, "_rt", None)
        if rt is not None and rt.worker is not None:
            self.st_lbl.setText("⚠ Le temps réel ⏱ utilise déjà le SDR : clique sur son spectre pour écouter.")
            return
        self.paused = [w for w in o.workers if w.isRunning() and w.sdr and parse_sdr_addr(w.port)[0] == kind]
        for w in self.paused:
            w.paused = True                       # le SDR ne peut pas balayer et écouter en même temps
        sq = None if self.sq_spin.value() <= -121 else float(self.sq_spin.value())
        pp = self.dp.params()
        self.worker = ListenWorker(kind, c, [self.ws[r]["freq"] for r in rows], pp["mode"], pp["deemph"], sq,
                                   pp["compander"], o.sdr_gains(kind), tool=getattr(o, "_listen_tool", None),
                                   tool_dir=o.sdr_cfg.get("dir", ""), dev=pp["dev"], cut=pp["cut"], audio=pp["audio"])
        self.worker.volume = self.vol.value() / 100.0
        fr_ = [self.ws[r]["freq"] for r in rows]
        self.worker.span = max(200e3, (max(fr_) - min(fr_)) * 1e6 + 400e3)     # WiNRADiO : plus petit DDC qui suffit
        self.worker.want_spec = True
        self.worker.spectrum.connect(lambda F, L, w_=self.worker: self._spec(F, L) if w_ is self.worker else None)
        self.worker.levels.connect(lambda lv, w_=self.worker: self._levels(lv) if w_ is self.worker else None)
        self.worker.status.connect(lambda t, w_=self.worker: self.st_lbl.setText(t) if w_ is self.worker else None)
        self.worker.stopped.connect(lambda why, w_=self.worker: self._stopped(why) if w_ is self.worker else None)
        self._sel_row = rows[0]
        self._pick(None)
        self.last_levels = None
        if not hopping:                                # étape 8 : seules les alarmes NOUVELLES déclenchent un WAV
            self._seen = set(self.owner.alarms.active)
            self._types = {}
        self._publish()
        if hopping and self.audio is not None:      # balayage : on garde la sortie son
            QtCore.QTimer.singleShot(0, self.worker.start)
            return
        self.audio = AudioPump(self._aq, sdr_audio_device(self.owner))                # 8.1 : son nourri par son propre fil
        self.audio.start()
        QtCore.QTimer.singleShot(300 if self.paused else 0, self.worker.start)   # le temps de libérer le SDR
        self.timer.start(10)                             # 8.1 : son nourri plus souvent (moins de trous)
        self.go_btn.setText("■ Arrêter")
        for wd in (self.dev_combo, self.pre_combo, self.mode_combo, self.comp_combo, self.de_combo, self.sq_spin,
                   self.table):
            wd.setEnabled(wd is self.table)

    def _feed(self):
        w = self.worker
        if w is None:
            return
        while w.tap:                                   # copie : WAV, téléphone
            b = w.tap.popleft()
            self.pre.push(b)
            if self._auto is not None:                 # étape 8 : enregistrement sur alarme en cours
                try:
                    self._auto["wv"].writeframes(b)
                except Exception:  # noqa: BLE001
                    self._auto_end()
            if self.wav is not None:
                try:
                    self.wav.writeframes(b)
                except Exception as e:  # noqa: BLE001
                    self.st_lbl.setText(TR("⚠ Enregistrement arrêté : {}").format(e))
                    self.rec_btn.setChecked(False)
            self.owner.listen_web_push(b)
        if self.audio is not None:
            if self.pc_mute.isChecked():
                w.audio.clear()
            else:
                pump_move(w.audio, self._aq)
        now = time.time()
        if self._auto is not None and now >= self._auto["until"]:
            self._auto_end()
        if now - self._t_al >= 0.5:
            self._badge()
        if self.auto_chk.isChecked() and now - self._t_al >= 0.5:
            self._t_al = now
            self._alarm_check()
        if self.hop_chk.isChecked() and len(self._wins) > 1 and now - self._t_hop >= 0.25:
            self._t_hop = now
            sq = None if self.sq_spin.value() <= -121 else float(self.sq_spin.value())
            lv_ = [lv[0] for lv in (getattr(self, "last_levels", None) or ())]
            if lv_:                                    # bruit = le plus bas vu sur toutes les fenêtres
                self._hop_floor = min(lv_ + ([self._hop_floor] if self._hop_floor is not None else []))
            lim = sq if sq is not None else ((self._hop_floor + HOP_OPEN_DB) if self._hop_floor is not None else 0.0)
            act = any(v > lim for v in lv_)
            if self.hop.feed(now, act):
                self._hop_next()

    def _alarm_check(self):
        """Étape 8 : nouvelle alarme dans la fenêtre écoutée -> WAV des 10 s d'avant + 10 s d'après."""
        w = self.worker
        if w is None or self._auto is not None:
            return
        c = self._plan[0] or 0.0
        half = 0.4 * float(getattr(w, "rate", 2.4e6)) / 1e6
        new = alarms_in_window(list(self.owner.alarms.active.values()), c / 1e6 - half, c / 1e6 + half, self._seen)
        for a in new:
            self._seen.add(a.get("key"))
        if not new:
            return
        import wave
        a = new[0]
        d = Path(self.owner.log_dir) / "enregistrements_audio" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"alarme_{datetime.now():%H%M%S}_{float(a['freq']):.3f}MHz.wav"
            wv = wave.open(str(p), "wb")
            wv.setnchannels(2)
            wv.setsampwidth(2)
            wv.setframerate(LISTEN_RATE)
            wv.writeframes(self.pre.dump())
        except Exception as e:  # noqa: BLE001
            self.st_lbl.setText(TR("⚠ Enregistrement impossible : {}").format(e))
            return
        self._auto = dict(wv=wv, path=p, until=time.time() + 10.0, a=a)
        self.st_lbl.setText(TR("⏺ Alarme {} sur {} : son enregistré (10 s avant, 10 s après)…").format(
            a.get("kind", ""), a.get("name", "")))

    def _auto_end(self):
        au, self._auto = self._auto, None
        if au is None:
            return
        try:
            au["wv"].close()
        except Exception:  # noqa: BLE001
            pass
        a = au["a"]
        self.owner.log_event(dict(name=a.get("name", ""), freq=float(a.get("freq") or 0.0),
                                  note=TR("son de l'alarme : {}").format(au["path"])), 0.0, "ENREGISTRÉ (alarme)")
        self.st_lbl.setText(TR("⏺ Son de l'alarme enregistré : {}").format(au["path"]))

    def _hop_next(self):
        """Balayage d'écoute : fenêtre suivante (le son et l'enregistrement continuent)."""
        w, self.worker = self.worker, None
        if w is not None:
            w.requestInterruption()
            w.wait(5000)
        self._wi = (self._wi + 1) % len(self._wins)
        c, rows = self._wins[self._wi]
        self._plan = (c, rows)
        self.hop.reset(time.time())
        self.table.blockSignals(True)            # sinon itemChanged -> _window() remettrait la 1re fenêtre
        for r in range(self.table.rowCount()):
            for c_ in (3, 4, 5):
                if self.table.item(r, c_) is not None:
                    self.table.item(r, c_).setText("")
            if self.table.item(r, 1) is not None:
                self.table.item(r, 1).setText(self.ws[r]["name"] or "—")
        self.table.blockSignals(False)
        self._start(c, rows, hopping=True)

    def _auto_toggled(self, on):
        """Étape 12 : cocher « garder le son sur alarme » = accord vie privée la 1re fois, retenu dans les réglages."""
        if on and not self.owner.privacy_ok(self):
            self.auto_chk.blockSignals(True)
            self.auto_chk.setChecked(False)
            self.auto_chk.blockSignals(False)
            on = False
        self.owner.privacy()["alarm_audio"] = bool(on)
        self._badge()

    def _badge(self):
        if self.wav is not None or self._auto is not None:
            t, c = TR("⏺ SON ENREGISTRÉ"), self.owner.theme.get("st_occ", "#ff453a")
        elif self.auto_chk.isChecked() and self.worker is not None:
            t, c = TR("⏺ prêt à enregistrer sur alarme"), self.owner.theme.get("st_weak", "#ff9f0a")
        else:
            t, c = "", ""
        if self.rec_badge.text() != t:
            self.rec_badge.setText(t)
            self.rec_badge.setStyleSheet(f"color: {c}; font-weight: bold;" if c else "")

    def toggle_rec(self, on):
        """⏺ Son enregistré en WAV (48 kHz stéréo 16 bits) dans <journaux>/enregistrements_audio/<date>/."""
        import wave
        if on and not self.owner.privacy_ok(self):        # étape 12 : accord vie privée la 1re fois
            self.rec_btn.blockSignals(True)
            self.rec_btn.setChecked(False)
            self.rec_btn.blockSignals(False)
            return
        if not on:
            if self.wav is not None:
                try:
                    self.wav.close()
                except Exception:  # noqa: BLE001
                    pass
                self.st_lbl.setText(TR("⏺ Son enregistré : {}").format(self.wav_path))
                self.owner.set_status(TR("⏺ Son enregistré : {}").format(self.wav_path))
            self.wav = None
            self.rec_btn.setText("⏺ Enregistrer le son")
            self._publish()
            return
        c, rows = self._plan
        f = self.ws[rows[0]]["freq"] if rows else (c or 0) / 1e6
        d = Path(self.owner.log_dir) / "enregistrements_audio" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"ecoute_{datetime.now():%H%M%S}_{f:.3f}MHz.wav"
            wv = wave.open(str(p), "wb")
            wv.setnchannels(2)
            wv.setsampwidth(2)
            wv.setframerate(LISTEN_RATE)
        except Exception as e:  # noqa: BLE001
            self.st_lbl.setText(TR("⚠ Enregistrement impossible : {}").format(e))
            self.rec_btn.blockSignals(True)
            self.rec_btn.setChecked(False)
            self.rec_btn.blockSignals(False)
            return
        self.wav, self.wav_path = wv, p
        self.rec_btn.setText("⏹ Arrêter l'enregistrement")
        self._publish()

    def _publish(self):
        """État de l'écoute pour la page web (vue 🎧 Écoute)."""
        w = self.worker
        c, rows = self._plan if w is not None else (None, [])
        sel = self._sel_row if self._sel_row in rows else (rows[0] if rows else None)
        lv = getattr(self, "last_levels", None) or []
        k = rows.index(sel) if sel in rows else 0
        self.owner._v8_listen = dict(
            on=w is not None, f=self.ws[sel]["freq"] if sel is not None else None,
            name=self.ws[sel]["name"] if sel is not None else "",
            freqs=[self.ws[r]["freq"] for r in rows], rf=round(float(lv[k][0]), 1) if k < len(lv) else None,
            rec=self.wav is not None, hop=bool(self.hop_chk.isChecked() and len(self._wins) > 1),
            mode=self.mode_combo.currentText(), pc_mute=self.pc_mute.isChecked())

    def _spec(self, F, L):
        """Étape 7 : spectre de la fenêtre écoutée -> surveillance (si le SDR est l'appareil qui surveille)."""
        o = self.owner
        kind = self.dev_combo.currentData()
        used = o.sdr_listen_feed(kind, F, L)
        lv_ = getattr(self, "last_levels", None) or []
        for k_, r in enumerate(self._plan[1]):         # étape 8 : type de chaque signal écouté
            pil = lv_[k_][2] if k_ < len(lv_) else None
            self._types[r] = classify_signal(F, L, self.ws[r]["freq"], pil, span=0.6)
        a, b = float(np.min(F)), float(np.max(F))
        n = sum(1 for w in o.watch if a <= w["freq"] <= b)
        self.mon_lbl.setText(TR("📡 Surveillance pendant l'écoute : {} – {} MHz ({} de tes fréquences).").format(
            f"{a:.3f}", f"{b:.3f}", n) if used else
            TR("📡 Le tinySA continue de surveiller toute ta liste pendant l'écoute."))

    def _levels(self, lv):
        m_ = self.owner.sdr_model_for(self.dev_combo.currentData())
        fl_ = sdr_floor_dbfs(m_, getattr(self.worker, "rate", None)) if m_ is not None else -90.0
        nom = (self.dp.params().get("dev") or LISTEN_MODES.get(self.mode_combo.currentData(), {}).get("dev") or 0) / 1000.0
        for t_, r in zip(lv, self._plan[1]):
            rf, au, pil = t_[:3]
            hl = t_[3] if len(t_) > 3 else None
            c_ = self._types.get(r)
            txt, tone = mic_health(hl["dev"] if hl and rf > fl_ + 10 else None, nom,
                                   hl["drift"] if hl and rf > fl_ + 10 else None, pil, au)
            if c_ is not None and c_.get("kind") not in ("fm_ana", "fm_st", "nfm"):
                txt, tone = TR(c_["name"]), ("warn" if c_["kind"] != "none" else "none")
            elif c_ is not None and txt == "—":
                txt = TR(c_["name"])
            elif c_ is not None:
                txt = TR(c_["name"]) + " · " + TR(txt)
            it5 = self.table.item(r, 5)
            it5.setText(TR(txt))
            it5.setForeground(QtGui.QColor(self.owner.tone_color(tone)) if tone in ("warn", "bad") else QtGui.QBrush())
            if c_ is not None:
                it5.setToolTip(TR(c_["why"]) + "\n" + signal_report(c_, TR))
            n = int(max(0, min(10, (rf - fl_) / max(1.0, -fl_) * 10.0)))   # étape 7 : échelle d'après les bits
            self.table.item(r, 3).setText(f"{'█' * n}{'·' * (10 - n)}  {rf:.0f} dBFS")
            m = int(max(0, min(10, au * 10)))
            self.table.item(r, 4).setText("▮" * m)
        self.last_levels = lv
        self._publish()

    def _stopped(self, why):
        if why:
            self.st_lbl.setText(f"⚠ Écoute arrêtée : {why}")
        self._end()

    def stop(self):
        self._end()

    def _end(self):
        self.timer.stop()
        self._auto_end()
        if self.rec_btn.isChecked():
            self.rec_btn.setChecked(False)              # ferme le WAV proprement
        w, self.worker = self.worker, None
        if w is not None:
            w.requestInterruption()
            w.wait(5000)
        if self.audio is not None:
            self.audio.close()
            self.audio = None
        for w in self.paused:
            w.paused = False
        self.paused = []
        self.go_btn.setText("▶ Écouter")
        for wd in (self.dev_combo, self.pre_combo, self.mode_combo, self.comp_combo, self.de_combo, self.sq_spin,
                   self.table):
            wd.setEnabled(True)
        self.owner.listen_web_clear()
        self.owner.sdr_listen_clear()
        self.mon_lbl.setText("")
        self._publish()

    def closeEvent(self, ev):
        self.stop()
        super().closeEvent(ev)


class MultiMonitorWorker(QtCore.QThread):
    """V8 étape 9 : 📡 moniteur multicanal. UNE fenêtre IQ du SDR ; chaque bloc de 50 ms : FFT (niveaux, bruit, voisins,
    largeur de TOUS les canaux), et démodulation complète des « récepteurs virtuels » (plan_vrx : celui qu'on écoute,
    les alarmes, la priorité ; les autres tournent toutes les 5 s) : audio (AudioMeter), santé (déviation, dérive).
    Émet `stats` (liste par canal) et `spec` (F MHz, dBFS) 2 fois par seconde, `perf` (pertes, charge, retard)."""
    stats = Signal(object)
    spec = Signal(object, object)
    perf = Signal(object)
    stopped = Signal(str)
    status = Signal(str)
    incident = Signal(object)        # V8 étape 10 : dossier d'incident écrit (ou raté) : dict(req, iq)
    bursts = Signal(object)          # V8 étape 10 : signaux brefs disparus [événement BurstDetector]
    NFFT = 4096

    def __init__(self, kind, center_hz, rate, chans, gains=None, serial="", tool=None, tool_dir=""):
        super().__init__()
        self.kind, self.center, self.rate, self.serial = kind, float(center_hz), int(rate), serial
        self.chans = list(chans)           # [dict(key, name, freq MHz, bw kHz, prio, keep_on, mode, dev, …)]
        self.gains, self.tool, self.tool_dir = dict(gains or {}), tool, tool_dir
        self.n_vrx, self.sel_key, self.alarm_keys = 4, None, set()
        self.volume = 1.0
        self.audio = deque(maxlen=200)
        self.src, self.err = None, deque(maxlen=20)
        self.demod_opts = dict(mode="wfm", deemph_us=50.0, compander=None)
        self.inc_req, self.ring_s, self.keep_iq = deque(), 0.0, True    # V8 étape 10 : incidents
        self.frozen = False                                             # étape 14 : coupé par le chien de garde

    def force_close(self):
        """Étape 14 : flux figé (l'outil ne rend plus rien sans erreur) -> on ferme la source (tue l'outil), la lecture
        bloquée se termine, le moniteur relance le SDR."""
        self.frozen = True
        s_ = self.src
        if s_ is not None:
            try:
                s_.close()
            except Exception:  # noqa: BLE001
                pass

    def _inc_write(self, pend, dtype, center, hw):
        """Écrit l'IQ d'un incident (avant + après) en SigMF, dans un fil à part (ne pas perdre d'échantillons)."""
        def go():
            req = pend["req"]
            base = os.path.join(req["dir"], "iq")
            iq = dict(file="", why="")
            try:
                os.makedirs(req["dir"], exist_ok=True)
                parts = list(pend["pre"]) + list(pend["post"])       # audit V8 : écrit morceau par morceau, sans
                size = sum(len(x) for x in parts)                    # recoller des centaines de Mo en mémoire
                if shutil.disk_usage(req["dir"]).free < max(2e9, 3 * size):   # étape 12 : disque presque plein
                    raise OSError(TR("disque presque plein : IQ non gardé"))
                with open(base + ".sigmf-data.part", "wb") as f:         # étape 14 : « .part » tant que pas fini
                    for x in parts:
                        f.write(x)
                    f.flush()
                    os.fsync(f.fileno())
                pend["pre"], pend["post"], parts = [], [], None      # mémoire rendue tout de suite
                os.replace(base + ".sigmf-data.part", base + ".sigmf-data")
                ann = [{"core:sample_start": max(0, int(round((req["t"] - pend["t0"]) * self.rate))),
                        "core:sample_count": 1, "core:label": f"incident {req.get('name', '')}"}]
                write_atomic(base + ".sigmf-meta", json.dumps(sigmf_meta(dtype, self.rate, center, pend["t0"], hw, ann),
                                                             indent=1))   # le .meta en DERNIER = IQ complet
                iq = dict(file="iq.sigmf-data", path=base + ".sigmf-data", dur=size / IQ_BYTES[dtype] / self.rate,
                          rate=self.rate, center=center, t0=pend["t0"])
            except OSError as e:
                iq["why"] = str(e)
            self.incident.emit(dict(req=req, iq=iq, also=pend.get("also", [])))
            for r_ in pend.get("merged", []):        # demandes arrivées pendant l'enregistrement : même dossier
                self.incident.emit(dict(req=r_, iq=dict(iq, same=req["dir"]), also=[]))
        threading.Thread(target=go, daemon=True).start()

    def run(self):
        sp = SDR_KINDS[self.kind]
        try:
            src = self.src = open_iq_source(self.kind, self.center, self.rate, self.gains, self.serial, self.tool,
                                            self.tool_dir, wr_lib=WINRADIO_LIB)
        except RuntimeError as e:
            self.stopped.emit(str(e))
            return
        self.rate, self.err = src.rate, src.err
        self.status.emit(f"📡 {sp['name']} : {len(self.chans)} canaux autour de {self.center / 1e6:.3f} MHz")
        nb = IQ_BYTES[src.dtype]
        chunk = int(self.rate * 0.05) * nb
        Fb = rt_freqs(self.center, self.rate, self.NFFT)
        dem, meters = {}, {c["key"]: AudioMeter() for c in self.chans}
        prev_ok = {c["key"]: None for c in self.chans}
        drops = {c["key"]: deque(maxlen=20) for c in self.chans}
        buf, why, t0, got, busy = b"", "", time.time(), 0, 0.0
        acc, t_emit, turn, t_turn, active = [], time.time(), 0, 0.0, []
        last = {}
        clk, b_fft, b_vrx, n_vb, ovr = AcqClock(self.rate), 0.0, 0.0, 0, 0     # étape 12 : horloge, coûts
        self.n_auto, self.clock = 4, clk
        bps = self.rate * nb                         # V8 étape 10 : tampon IQ circulaire (les secondes AVANT)
        self.ring_s = iq_ring_seconds(bps)
        ring, pend, bd = PreRing(self.ring_s, bps), None, BurstDetector(gap=3)
        try:
            while not self.isInterruptionRequested():
                data = src.read(chunk - len(buf))
                if not data:
                    time.sleep(0.1)
                    why = (TR("flux figé : plus de données depuis {} s").format(f"{FROZEN_S:.0f}") if self.frozen
                           else (self.err[-1] if self.err else "flux coupé")) + f" — {sp['name']} débranché ou occupé ?"
                    break
                if got == 0 and not buf:
                    t0 = time.time()                 # pertes comptées depuis les premières données, pas le lancement
                buf += data
                if len(buf) < chunk:
                    continue
                tw = time.time()
                if self.keep_iq:
                    raw = bytes(buf)
                    if pend is not None:
                        pend["post"].append(raw)
                        while self.inc_req:                   # demandes pendant l'enregistrement : même dossier
                            r_ = self.inc_req.popleft()
                            pend["also"].append(r_.get("trigger"))
                            pend["merged"].append(r_)
                        if tw - pend["req"]["t"] >= INC_POST_S:
                            self._inc_write(pend, src.dtype, self.center, sp["name"])
                            pend = None
                    else:
                        ring.push(raw)
                        if self.inc_req:                      # audit V8 : on PREND les morceaux du tampon (pas de copie)
                            pre = list(ring.q)
                            pend = dict(req=self.inc_req.popleft(), pre=pre, post=[], also=[], merged=[],
                                        t0=tw - ring.n / float(bps))
                            ring = PreRing(self.ring_s, bps)
                elif self.inc_req:
                    r_ = self.inc_req.popleft()
                    self.incident.emit(dict(req=r_, iq=dict(file="", why=TR("IQ non gardé (case décochée)")), also=[]))
                iq, buf = iq_decode(src.dtype, buf), b""
                got += len(iq)
                t_cap = clk.feed(len(iq), tw)           # étape 12 : heure de CAPTURE (compte d'échantillons)
                avg, _mx = rt_frames(iq, self.NFFT)
                if avg is not None:
                    acc.append(avg)
                now = time.time()
                b_fft += now - tw
                if now - t_turn >= 5.0 or not active:      # 16. récepteurs virtuels : qui est démodulé
                    t_turn, turn = now, turn + 1
                    items = [dict(key=c["key"], prio=c.get("prio", 1), keep_on=c.get("keep_on"),
                                  alarm=c["key"] in self.alarm_keys, selected=c["key"] == self.sel_key)
                             for c in self.chans]
                    el_ = max(1e-3, now - t0)
                    if n_vb:                                # étape 12 : combien le PC peut en démoduler
                        na = vrx_auto(b_fft / el_, b_vrx / n_vb / 0.05)
                        self.n_auto = max(1, min(VRX_MAX, int(round(0.5 * self.n_auto + 0.5 * na))))
                    n_eff = self.n_auto if self.n_vrx <= 0 else self.n_vrx
                    active = plan_vrx(items, min(VRX_MAX, n_eff), turn)
                    for k in list(dem):
                        if k not in active:
                            dem.pop(k)
                    for c in self.chans:
                        if c["key"] in active and c["key"] not in dem:
                            o = dict(self.demod_opts)
                            o.update({k_: c[k_] for k_ in ("mode", "dev") if c.get(k_)})
                            dem[c["key"]] = ChannelDemod(self.rate, c["freq"] * 1e6 - self.center, **o)
                tv0 = time.time()
                n_vb += len(dem)
                for c in self.chans:
                    d_ = dem.get(c["key"])
                    if d_ is None:
                        continue
                    a, lv = d_.process(iq)
                    rf_ok = prev_ok.get(c["key"]) is not False
                    meters[c["key"]].feed(a, 0.05, rf_ok, now)
                    if c["key"] == self.sel_key and len(a):
                        self.audio.append(audio_int16(a, self.volume))
                    last[c["key"]] = (lv, d_.health, d_.pilot)
                b_vrx += time.time() - tv0
                busy += time.time() - tw
                if now - t_emit >= 0.5 and acc:
                    L = np.max(np.array(acc), axis=0)
                    acc = []
                    t_emit_prev, t_emit = t_emit, now
                    rows = []
                    for c in self.chans:
                        f = c["freq"]
                        bwm = max(0.1, float(c.get("bw") or 0.0) / 2000.0 + 0.05)
                        sel = np.abs(Fb - f) <= bwm
                        rf = float(np.max(L[sel])) if sel.any() else None
                        far = (np.abs(Fb - f) <= 1.0) & (np.abs(Fb - f) > 0.15)
                        noise = float(np.percentile(L[far], 20)) if far.sum() >= 5 else None
                        inb, alo, ahi = adjacent_db(Fb, L, f)
                        adj = [x for x in (alo, ahi) if x is not None]
                        ok_ = rf is not None and noise is not None and rf - noise >= 10
                        if prev_ok.get(c["key"]) and not ok_:
                            drops[c["key"]].append(now)        # décrochage : la porteuse disparaît
                        prev_ok[c["key"]] = ok_
                        lv, hl, pil = last.get(c["key"], (None, None, None))
                        ob = obw_khz(Fb, L, f, 0.3)[0] if ok_ else None
                        rows.append(dict(key=c["key"], name=c["name"], freq=f, rf=rf, noise=noise, t=t_cap,
                                         adj_lvl=max(adj) if adj else None,
                                         snr=(rf - noise) if (rf is not None and noise is not None) else None,
                                         adj_margin=(inb - max(adj)) if (inb is not None and adj) else None,
                                         obw=ob, vrx=c["key"] in dem, pilot=pil,
                                         dev=hl["dev"] if hl and ok_ else None, drift=hl["drift"] if hl and ok_ else None,
                                         rf_drops=sum(1 for t_ in drops[c["key"]] if now - t_ < 120),
                                         **(meters[c["key"]].state() if c["key"] in dem else {})))
                    self.stats.emit(rows)
                    self.spec.emit(Fb, L)
                    ev_ = bd.feed(now, Fb, L, float(np.median(L)) + 15.0)
                    ev_ = unknown_bursts(ev_, [c["freq"] for c in self.chans])
                    if ev_:
                        self.bursts.emit(ev_)
                    el = max(1e-3, now - t0)
                    ovr = max(ovr, count_overruns(list(self.err or ())))
                    crit = [c["key"] for c in self.chans if int(c.get("prio") or 1) >= 2 and c["key"] not in dem]
                    self.perf.emit(dict(expected=self.rate * el, got=got, load=busy / max(1e-3, now - t_emit_prev),
                                        lag=max(0.0, clk.lag), vrx=len(dem), vrx_want=len(self.chans) if self.n_vrx <= 0
                                        else min(self.n_vrx, len(self.chans)), n_auto=self.n_auto, resyncs=clk.resyncs,
                                        overruns=ovr, queue=len(self.audio), ring_s=self.ring_s,
                                        ring_mb=ring.n / 1e6 if self.keep_iq else 0.0, crit=len(crit), t=t_cap))
                    busy = 0.0
        finally:
            s_, self.src = self.src, None
            if s_ is not None:
                s_.close()
            if pend is not None:                        # arrêt pendant un incident : on garde ce qu'on a
                self._inc_write(pend, src.dtype, self.center, sp["name"])
            for r_ in self.inc_req:
                self.incident.emit(dict(req=r_, iq=dict(file="", why=TR("moniteur arrêté")), also=[]))
            self.inc_req.clear()
        self.stopped.emit(why)


class MultiMonitorDialog(QtWidgets.QDialog):
    """V8 étape 9 : 📡 moniteur multicanal SDR. Tous tes micros de la fenêtre du SDR : niveau, écart au bruit, son
    (RMS / crête / silence / coupures / saturation), santé (déviation, dérive), largeur occupée, canaux voisins,
    diagnostic RF + audio ; clic sur une ligne = l'écouter + son waterfall et son historique."""
    COLS = ["Nom", "Suivi", "MHz", "RF", "Son", "Santé", "Largeur", "Voisins", "Diagnostic"]
    C_COV, C_DIAG = 1, 8

    def __init__(self, owner):
        super().__init__(owner)
        self._aq = deque(maxlen=200)                      # 8.1 : file de la carte son (AudioPump)
        self.owner = o = owner
        self.setWindowTitle("Moniteur multicanal SDR")
        self.setModal(False)
        self.worker, self.audio, self.paused = None, None, []
        self.hist, self.rows, self.sel, self.wf = {}, [], None, {}
        self.trk, self.chron, self._seen_al, self._last_auto, self.incs = {}, [], set(), -1e18, {}   # étape 10
        self.ext = {}                     # étape 12 : mesures des autres appareils {clé: {tsa, rx: [(heure, dB)]}}
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Tous tes micros qui tiennent dans la fenêtre du SDR, surveillés en même temps (RF, son, "
                                "santé). Clique une ligne pour l'écouter.")
        info.setWordWrap(True)
        info.setToolTip("Toutes tes fréquences de la fenêtre sont mesurées en même temps (niveau, voisins, largeur). Les plus\n"
                        "importantes ont en plus un « récepteur virtuel » qui les démodule : son, déviation, dérive, coupures.")
        info.setMinimumHeight(info.fontMetrics().height() * 2)
        lay.addWidget(info)
        R = o._row
        self.dev_combo = QtWidgets.QComboBox()
        for k, sp in SDR_KINDS.items():
            self.dev_combo.addItem(f"📡 {sp['name']}", k)
        pk = parse_sdr_addr(o.port_combo.currentData() or "") or parse_sdr_addr(o.dev2.get("addr", ""))
        if pk:
            self.dev_combo.setCurrentIndex(max(0, self.dev_combo.findData(pk[0])))
        self.dev_combo.setToolTip("Le SDR qui écoute (il faut ses outils, ou la DLL WiNRADiO).")
        self.vrx_spin = QtWidgets.QSpinBox()
        self.vrx_spin.setRange(0, VRX_MAX)
        self.vrx_spin.setSpecialValueText("Auto")            # étape 12 : d'après ce que le PC peut calculer
        self.vrx_spin.setValue(0)
        self.vrx_spin.valueChanged.connect(lambda v: self.worker is not None and setattr(self.worker, "n_vrx", v))
        self.vrx_spin.setToolTip("Combien de micros sont démodulés en même temps (son, déviation, dérive). Plus = plus de "
                                 "calcul.\nLes autres sont mesurés par la FFT et passent à tour de rôle toutes les 5 s.")
        self.go_btn = QtWidgets.QPushButton("▶ Surveiller")
        self.go_btn.setToolTip("Lance / arrête le moniteur multicanal.")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        lay.addLayout(R("SDR :", self.dev_combo, None, self.go_btn))      # récepteurs virtuels : onglet Système
        self.mode_combo = QtWidgets.QComboBox()             # V8 étape 11 : répétition / spectacle
        for k, t in SDR_MODES:
            self.mode_combo.addItem(t, k)
        self.mode_combo.setToolTip("Surveillance : comme d'habitude.\n🎭 Répétition : le moniteur APPREND ce qui est normal "
                                   "pour chaque micro (niveau, bruit, son).\n🎤 Spectacle : il prévient quand un micro "
                                   "s'écarte de sa répétition.")
        self.reh = RehearsalProfile()
        self.reh_btn = QtWidgets.QPushButton("💾 Garder la répétition")
        self.reh_btn.setToolTip("Retient ce qui a été appris pendant la répétition (gardé dans les réglages) : il sert en "
                                "mode 🎤 Spectacle.")
        self.reh_btn.clicked.connect(lambda *_: self.save_rehearsal())
        self.reh_lbl = QtWidgets.QLabel("")
        self.reh_lbl.setWordWrap(True)
        self.phase_combo = QtWidgets.QComboBox()             # 20. quelle phase du show
        self.phase_combo.setEditable(True)
        for p_ in dict.fromkeys(list(PHASES) + list(self._phases())):
            self.phase_combo.addItem(p_)
        self.phase_combo.setCurrentIndex(1)
        self.phase_combo.setToolTip("La phase du show : balance, répétition, début, exploitation… (tu peux en taper une autre).\n"
                                    "Chaque phase apprise est gardée à part ; on compare le show à celle qu'on choisit.")
        self._phase_name = self.phase_combo.currentText()      # audit V8 : changement seulement une fois le nom fini
        self.phase_combo.activated.connect(lambda *_: self._phase_changed())
        self.phase_combo.lineEdit().editingFinished.connect(lambda: self._phase_changed())
        self.mode_combo.currentIndexChanged.connect(lambda *_: self._mode_changed())
        lay.addLayout(R("Mode :", self.mode_combo, self.phase_combo, self.reh_btn, self.reh_lbl, None))
        self.win_lbl = QtWidgets.QLabel("")
        self.win_lbl.setWordWrap(True)
        lay.addWidget(self.win_lbl)
        self.cap_lbl = QtWidgets.QLabel("")                    # étape 12 : ce qui est VRAIMENT surveillé
        self.cap_lbl.setWordWrap(True)
        self.cap_lbl.setToolTip("Ce que le SDR couvre vraiment et ce que le PC arrive à démoduler en ce moment.")
        lay.addWidget(self.cap_lbl)
        self._want, self._fails, self.disc, self.disc_why = False, 0, 0, ""
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        hh = self.table.horizontalHeader()
        for c in range(len(self.COLS) - 1):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(len(self.COLS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("RF = niveau (dBFS) et écart au bruit · Son = RMS / crête (🎧 = récepteur virtuel) ·\n"
                              "Santé = déviation et dérive · Largeur = 99 % de la puissance · Voisins = marge sur les canaux\n"
                              "adjacents · Diagnostic = croisement RF + son.")
        self.table.itemSelectionChanged.connect(lambda: self._pick())
        lay.addWidget(self.table, 2)
        low = QtWidgets.QHBoxLayout()
        self.wf_plot = pg.PlotWidget()
        self.wf_plot.setMinimumHeight(150)
        self.wf_plot.setToolTip("Waterfall du micro choisi (± 150 kHz) : le temps descend.")
        self.wf_img = pg.ImageItem()
        self.wf_img.setLookupTable(make_lut(o.theme.get("wf", "Inferno")))
        self.wf_plot.addItem(self.wf_img)
        self.wf_plot.hideAxis("left")
        self.wf_plot.setLabel("bottom", "kHz autour du micro")
        self.h_plot = pg.PlotWidget()
        self.h_plot.setMinimumHeight(150)
        self.h_plot.setToolTip("Historique du micro choisi (10 dernières minutes) : RF, bruit, son.")
        self.h_plot.addLegend(offset=(5, 5))
        self.c_rf = self.h_plot.plot(pen=pg.mkPen(o.theme.get("curve", "#0a84ff"), width=1.4), name="RF")
        self.c_nz = self.h_plot.plot(pen=pg.mkPen("#8e8e93", width=1), name="bruit")
        self.c_au = self.h_plot.plot(pen=pg.mkPen(o.theme.get("st_free", "#30d158"), width=1.2), name="son")
        low.addWidget(self.wf_plot, 1)
        low.addWidget(self.h_plot, 1)
        self.tabs = QtWidgets.QTabWidget()              # V8 étape 10 : micro choisi | chronologie des incidents
        tw_ = QtWidgets.QWidget()
        tw_.setLayout(low)
        self.tabs.addTab(tw_, "Micro choisi")
        cw = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(cw)
        cl.setContentsMargins(0, 4, 0, 0)
        self.inc_chk = QtWidgets.QCheckBox("📦 Dossier d'incident automatique")
        self.inc_chk.setChecked(True)
        self.inc_chk.setToolTip("Quand un micro a un souci (alarme, décrochage, bruit qui monte, voisin trop fort…), garde\n"
                                "tout seul ses mesures, un rapport et l'IQ des secondes AVANT et APRÈS (à rejouer).\n"
                                "Un dossier toutes les 2 min au plus ; les plus anciens sont effacés au-delà de 2 Go.")
        self.iq_chk = QtWidgets.QCheckBox("avec l'IQ")
        self.iq_chk.setChecked(True)
        self.iq_chk.setToolTip("Garde le signal brut (IQ) pour pouvoir REJOUER l'incident et l'écouter.\n"
                               "Gros fichiers : environ 10 à 20 Mo par seconde selon le SDR.")
        self.iq_chk.toggled.connect(lambda on: self.worker is not None and setattr(self.worker, "keep_iq", bool(on)))
        self.mark_btn = QtWidgets.QPushButton("📦 Noter un incident")
        self.mark_btn.setToolTip("Crée tout de suite un dossier d'incident pour le micro choisi (ou le 1er de la liste).")
        self.mark_btn.clicked.connect(lambda *_: self.manual_incident())
        self.play_btn = QtWidgets.QPushButton("▶ Rejouer")
        self.play_btn.setToolTip("Ouvre le rapport de l'incident choisi et rejoue son IQ dans le temps réel (son, spectre).")
        self.play_btn.clicked.connect(lambda *_: self.replay())
        self.dir_btn = QtWidgets.QPushButton("📂 Dossiers")
        self.dir_btn.setToolTip("Ouvre le dossier des incidents.")
        self.dir_btn.clicked.connect(lambda *_: QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(self._inc_root()))))
        cl.addLayout(o._row(self.inc_chk, self.iq_chk, None, self.mark_btn, self.play_btn, self.dir_btn))
        self.chron_tbl = QtWidgets.QTableWidget(0, 4)
        self.chron_tbl.setHorizontalHeaderLabels(["Heure", "Micro", "Quoi", "Dossier"])
        self.chron_tbl.verticalHeader().setVisible(False)
        self.chron_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.chron_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.chron_tbl.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        ch = self.chron_tbl.horizontalHeader()
        for c in range(3):
            ch.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        ch.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.chron_tbl.setToolTip("Tout ce qui est arrivé à tes micros pendant la surveillance (le plus récent en haut).\n"
                                  "Double-clic sur une ligne avec un dossier = rejouer l'incident.")
        self.chron_tbl.cellDoubleClicked.connect(lambda r, c: self.replay(r))
        cl.addWidget(self.chron_tbl)
        self.tabs.addTab(cw, "Chronologie")
        self.sys_tbl = QtWidgets.QTableWidget(0, 2)            # étape 12 : santé du système
        self.sys_tbl.setHorizontalHeaderLabels(["Quoi", "État"])
        self.sys_tbl.verticalHeader().setVisible(False)
        self.sys_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sys_tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.sys_tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.sys_tbl.setToolTip("La santé du SDR et du PC : échantillons perdus, retard, charge, mémoire, disque,\n"
                                "déconnexions. Orange / rouge = la surveillance n'est plus complète.")
        self.ph_tbl = QtWidgets.QTableWidget(0, 1)              # 20. phases côte à côte
        self.ph_tbl.verticalHeader().setVisible(False)
        self.ph_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ph_tbl.setToolTip("Chaque micro dans chaque phase apprise : écart au bruit, bruit de fond, niveau du son.\n"
                               "Un micro bien plus faible au show qu'à la balance = antenne masquée, pack mal placé…")
        self.tabs.addTab(self.ph_tbl, "Phases")
        sw_ = QtWidgets.QWidget()
        sl_ = QtWidgets.QVBoxLayout(sw_)
        sl_.setContentsMargins(0, 4, 0, 0)
        sl_.addLayout(R("Récepteurs virtuels :", self.vrx_spin, None))
        sl_.addWidget(self.sys_tbl)
        self.tabs.addTab(sw_, "Système")
        lay.addWidget(self.tabs, 1)
        self.sel_lbl = QtWidgets.QLabel("")
        self.sel_lbl.setWordWrap(True)
        lay.addWidget(self.sel_lbl)
        self.perf_lbl = QtWidgets.QLabel("")
        self.perf_lbl.setToolTip("Performances : échantillons perdus (le PC ou l'USB ne suit pas), charge du calcul, retard.")
        lay.addWidget(self.perf_lbl)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._feed)
        self.dev_combo.currentIndexChanged.connect(lambda *_: self._plan())
        self._plan()
        self._mode_changed()
        self._fill_phases()
        fit_dialog(self, 1000, 720)

    def _tsa_level(self, f):
        """Étape 12 : niveau du tinySA sur f et l'HEURE de son balayage (pas l'heure où on le lit). -> (t, dBm) ou None."""
        o = self.owner
        for bid, (F, L) in list(o.latest.items()):
            if bid in (o.SDR_LISTEN_ID, ZOOM_ID) or bid < 0 or not len(F) or not F[0] <= f <= F[-1]:
                continue
            lv = level_at(F, L, f, 0.1)
            if lv is not None:
                return float(o.latest_t.get(bid, 0.0)), float(lv)
        return None

    # ---------------------------------------------------------------- V8 étape 11 : répétition / spectacle
    def _phases(self):
        o = self.owner
        ph = o.sdr_cfg.get("phases")
        if not isinstance(ph, dict):
            ph = o.sdr_cfg["phases"] = phases_norm(None, o.sdr_cfg.get("rehearsal"))
        return ph

    def _phase(self):
        return self.phase_combo.currentText().strip() or PHASES[1]

    def _ref(self):
        return (self._phases().get(self._phase()) or {}).get("mics") or {}

    def _mode_changed(self):
        md = self.mode_combo.currentData()
        self.reh_btn.setVisible(md == "learn")
        self.phase_combo.setVisible(md != "watch")
        ph = self._phases().get(self._phase())
        if md == "learn":
            n = len(self.reh.summary())
            self.reh_lbl.setText(TR("🎭 J'apprends « {} » : {} micro(s) appris (30 s de mesures chacun au moins).").format(
                TR(self._phase()), n))
        elif md == "show":
            self.reh_lbl.setText(TR("🎤 Comparé à « {} » ({} micros, {}).").format(
                TR(self._phase()), len(ph.get("mics", {})), ph.get("name", "")) if ph else
                TR("⚠ « {} » pas encore apprise : choisis « 🎭 Apprendre » pendant cette phase.").format(TR(self._phase())))
        else:
            self.reh_lbl.setText("")

    def _phase_changed(self):
        name = self._phase()
        if name == getattr(self, "_phase_name", None):
            return                                         # même phase (ou nom en cours de frappe) : rien n'est effacé
        self._phase_name = name
        if self.mode_combo.currentData() == "learn":
            self.reh = RehearsalProfile()                # nouvelle phase : on repart de zéro
        self._mode_changed()

    def save_rehearsal(self):
        sm = self.reh.summary()
        if not sm:
            self.reh_lbl.setText(TR("Rien d'appris pour l'instant : laisse tourner la répétition (30 s par micro au moins)."))
            return False
        o = self.owner
        self._phases()[self._phase()] = dict(t=time.time(), name=datetime.now().strftime("%d/%m %H:%M"), mics=sm)
        try:
            o._save_config()
        except Exception:  # noqa: BLE001
            pass
        self.reh_lbl.setText(TR("💾 « {} » gardée : {} micros. Choisis « 🎤 Comparer » pendant le show.").format(
            TR(self._phase()), len(sm)))
        self._fill_phases()
        return True

    def _fill_phases(self):
        """20. Onglet Phases : chaque micro, phase par phase (écart au bruit · bruit · son)."""
        ph = self._phases()
        names = list(ph)
        t = self.ph_tbl
        t.setColumnCount(1 + len(names))
        t.setHorizontalHeaderLabels([TR("Micro")] + [TR(n) for n in names])
        t.setRowCount(len(self.chans))
        for r, c in enumerate(self.chans):
            t.setItem(r, 0, QtWidgets.QTableWidgetItem(c["name"]))
            for j, n in enumerate(names):
                v = (ph[n].get("mics") or {}).get(c["key"])
                txt = "—" if not v else " · ".join(x for x in (
                    f"+{v['snr_med']:.0f} dB" if v.get("snr_med") is not None else "",
                    TR("bruit {}").format(f"{v['noise_med']:.0f}") if v.get("noise_med") is not None else "",
                    TR("son {}").format(f"{v['audio_p50']:.0f}") if v.get("audio_p50") is not None else "") if x)
                t.setItem(r, 1 + j, QtWidgets.QTableWidgetItem(txt))

    def _plan(self):
        """Fenêtre du SDR : la plus grande grappe de tes fréquences (au plus 4 MHz utiles sur un HackRF à 4,8 MS/s…)."""
        o = self.owner
        kind = self.dev_combo.currentData()
        m = o.sdr_model_for(kind)
        rate = sdr_rate(m, kind)
        ws = [w for w in o.watch if not w.get("off") and (m is None or sdr_in_range(m, w["freq"]))]
        use = sdr_span_mhz(m, rate) / 2.0                 # étape 12 : largeur UTILE du modèle (pas le débit brut)
        self.n_asked = len(ws)
        F = sorted(w["freq"] for w in ws)
        best = []
        for f0 in F:
            g = [f for f in F if f0 <= f <= f0 + 2 * use - 0.3]
            if len(g) > len(best):
                best = g
        self.rate = rate
        self.center = ((best[0] + best[-1]) / 2.0 - 0.2) * 1e6 if best else None
        keep = set(best)
        self.chans = [dict(key=int(round(w["freq"] * 1000)), name=w["name"] or f"{w['freq']:.3f}", freq=w["freq"],
                           bw=float(w.get("bw") or 0.0) * 1000.0, prio=o.freq_prio(w), keep_on=o.is_keep_on(w["status"]),
                           keep_free=o.is_keep_free(w["status"]))
                      for w in ws if w["freq"] in keep]
        self.win_lbl.setText(TR("Fenêtre : {} – {} MHz").format(f"{best[0] - 0.1:.3f}", f"{best[-1] + 0.1:.3f}")
                             if best else TR("Aucune de tes fréquences n'est dans la plage de ce SDR."))
        if best and getattr(self, "cap_lbl", None) is not None and self.worker is None:   # avant ▶ : ce qui tient
            ct, ctone = capacity_view(len(ws), len(self.chans), len(self.chans), 0, TR, planned=True)
            self.cap_lbl.setText(ct)
            self.cap_lbl.setStyleSheet("" if ctone == "ok" else f"color: {o.tone_color(ctone)};")
        self.out_ws = [w for w in ws if w["freq"] not in keep]        # étape 14 : on montre aussi ce qui N'EST PAS suivi
        self.table.setRowCount(len(self.chans) + len(self.out_ws))
        for r, c in enumerate(self.chans):
            for col, v in enumerate((c["name"], coverage_text("stop", None, TR), f"{c['freq']:.3f}", "", "", "", "", "", "")):
                self.table.setItem(r, col, QtWidgets.QTableWidgetItem(v))
            self.hist.setdefault(c["key"], MicHistory())
        for i, w in enumerate(self.out_ws):
            r = len(self.chans) + i
            for col, v in enumerate((w["name"] or f"{w['freq']:.3f}", coverage_text("out", None, TR), f"{w['freq']:.3f}",
                                     "—", "—", "—", "—", "—", TR("le tinySA ou le balayage s'en occupe"))):
                it = QtWidgets.QTableWidgetItem(v)
                it.setForeground(QtGui.QColor(o.theme.get("dim", "#8e8e93")))
                self.table.setItem(r, col, it)
            self.table.item(r, 1).setForeground(QtGui.QColor(o.tone_color("bad")))
        if getattr(self, "ph_tbl", None) is not None:
            self._fill_phases()

    def toggle(self):
        if self.worker is not None:
            self.stop()
            return
        if not self.chans or self.center is None:
            self.sel_lbl.setText(TR("Rien à surveiller avec ce SDR."))
            return
        o = self.owner
        kind = self.dev_combo.currentData()
        for d in (getattr(o, "_listen", None), getattr(o, "_rt", None)):
            if d is not None and getattr(d, "worker", None) is not None:
                self.sel_lbl.setText(TR("⚠ Le SDR est déjà pris (écoute ou temps réel) : ferme-les d'abord."))
                return
        self.paused = [w for w in o.workers if w.isRunning() and w.sdr and (parse_sdr_addr(w.port) or ("",))[0] == kind]
        for w in self.paused:
            w.paused = True
        self.worker = MultiMonitorWorker(kind, self.center, self.rate, self.chans, o.sdr_gains(kind),
                                         tool=getattr(o, "_listen_tool", None), tool_dir=o.sdr_cfg.get("dir", ""))
        self.worker.n_vrx = self.vrx_spin.value()
        self._want = True
        self._t_stats, self._t_start, self._fr_shown = None, time.time(), None     # étape 14 : âge des mesures
        self.worker.stats.connect(lambda rows, w_=self.worker: self._stats(rows) if w_ is self.worker else None)
        self.worker.spec.connect(lambda F, L, w_=self.worker: self._spec(F, L) if w_ is self.worker else None)
        self.worker.perf.connect(lambda p, w_=self.worker: self._perf(p) if w_ is self.worker else None)
        self.worker.status.connect(self.sel_lbl.setText)
        self.worker.stopped.connect(lambda why, w_=self.worker: self._stopped(why) if w_ is self.worker else None)
        self.worker.incident.connect(self._inc_done)           # même un ancien moniteur : son dossier est fini
        self.worker.bursts.connect(lambda evs, w_=self.worker: self._bursts(evs) if w_ is self.worker else None)
        if self.iq_chk.isChecked() and not o.privacy_ok(self):     # étape 12 : l'IQ contient le son
            self.iq_chk.setChecked(False)
        self.worker.keep_iq = self.iq_chk.isChecked()
        self.trk = {c["key"]: AnomalyTracker(not c.get("keep_free")) for c in self.chans}   # libre : signal = anomalie
        self._seen_al = {a.get("key") for a in o.alarms.active.values()}
        self.audio = AudioPump(self._aq, sdr_audio_device(self.owner))                       # 8.1 : son nourri par son propre fil
        self.audio.start()
        if o.sdr_cfg.get("shure") and not getattr(o, "_shure", None):       # étape 11 : récepteurs pour comparer
            o.receivers_start(o.sdr_cfg["shure"])
        QtCore.QTimer.singleShot(300 if self.paused else 0, self.worker.start)
        self.timer.start(10)                             # 8.1 : son nourri plus souvent (moins de trous)
        self.go_btn.setText("■ Arrêter")
        self.dev_combo.setEnabled(False)

    def _feed(self):
        w = self.worker
        if w is None:
            return
        o = self.owner
        if time.time() - getattr(self, "_t_fresh", 0.0) >= 0.5:          # étape 14 : âge des mesures
            self._t_fresh = time.time()
            self._freshen()
        w.alarm_keys = {a["key"][1] for a in o.alarms.active.values() if a.get("key") and a["key"][0] in ("CONFLIT", "BREF", "ABSENT")}
        if self.audio is not None:
            pump_move(w.audio, self._aq)
        if self.mode_combo.currentData() == "learn" and int(time.time()) % 5 == 0:
            self._mode_changed()
        if self.chans:                                            # étape 10 : nouvelles alarmes sur un de mes micros
            lo, hi = min(c["freq"] for c in self.chans) - 0.1, max(c["freq"] for c in self.chans) + 0.1
            for a in alarms_in_window(o.alarms.active.values(), lo, hi, self._seen_al):
                self._seen_al.add(a.get("key"))
                c = min(self.chans, key=lambda c_: abs(c_["freq"] - float(a["freq"])))
                if abs(c["freq"] - float(a["freq"])) <= 0.1:
                    self._event(c, dict(kind="alarm", t=time.time(), value=a.get("kind", "")))

    def _pick(self):
        r = self.table.currentRow()
        self.sel = self.chans[r]["key"] if 0 <= r < len(self.chans) else None
        if self.worker is not None:
            self.worker.sel_key = self.sel
        self._draw_sel()

    def _stats(self, rows):
        self.rows = rows
        o = self.owner
        now = time.time()
        for r, s in enumerate(rows):
            h = self.hist.setdefault(s["key"], MicHistory())
            now = float(s.get("t") or time.time())           # étape 12 : heure de capture
            h.add(now, adj=s.get("adj_lvl"), rf=s.get("rf"), noise=s.get("noise"), audio=s.get("rms"), dev=s.get("dev"), drift=s.get("drift"),
                  obw=s.get("obw"), snr=s.get("snr"))
            nom = next((c.get("dev") for c in self.chans if c["key"] == s["key"] and c.get("dev")), 75000) / 1000.0
            rx0 = o.receiver_for(s["freq"])
            obw_exp = expected_obw_khz(self.worker.demod_opts.get("mode", "wfm") if self.worker else "wfm")
            dg = rf_audio_diag(dict(s, nominal=nom, obw_exp=obw_exp, rx_alerts=(rx0 or {}).get("alerts")), TR)
            md = self.mode_combo.currentData()
            if md == "learn" and self.worker is not None:
                self.reh.learn(s)
            elif md == "show":
                dd = rehearsal_check(self._ref().get(s["key"]), s, TR)
                if dd:
                    dg = sorted([x for x in dg if x[0] != "ok"] + dd, key=lambda x: {"bad": 0, "warn": 1}.get(x[1], 2))
            ex = self.ext.setdefault(s["key"], dict(tsa=deque(maxlen=3600), rx=deque(maxlen=3600)))
            tl = self._tsa_level(s["freq"]) if o.tsa_live() else None      # 10. ce que voit le tinySA, à SON heure
            if tl and (not ex["tsa"] or ex["tsa"][-1][0] != tl[0]):
                ex["tsa"].append(tl)
            rx_ = o.receiver_for(s["freq"])                                # … et le récepteur Shure
            if rx_ and rx_.get("live") and rx_.get("hist"):
                ex["rx"] = deque(rx_["hist"], maxlen=3600)
            ht, _tone = mic_health(s.get("dev"), nom, s.get("drift"), s.get("pilot"), None)
            vals = [s["name"], f"{s['freq']:.3f}",
                    "—" if s.get("rf") is None else f"{s['rf']:.0f} dBFS · " + (f"+{s['snr']:.0f} dB" if s.get("snr")
                                                                               is not None else "—"),
                    ("🎧 " + (f"{s['rms']:.0f} / {s['peak']:.0f} dB" + (" ⚠ sature" if s.get("clip", 0) > 0.005 else "")
                              + (f" · silence {s['silent']:.0f} s" if s.get("silent", 0) >= 2 else ""))
                     if s.get("vrx") and s.get("rms") is not None else "—"),
                    TR(ht), "—" if s.get("obw") is None else f"{s['obw']:.0f} kHz",
                    "—" if s.get("adj_margin") is None else f"{round(s['adj_margin']):.0f} dB", diag_short(dg[0][2])]
            vals.insert(1, coverage_text(coverage_state(True, True, s.get("vrx"), "live", getattr(self, "_perf_tone", "ok")),
                                         None, TR))
            for c, v in enumerate(vals):
                it = self.table.item(r, c)
                if it is None:
                    it = QtWidgets.QTableWidgetItem("")
                    self.table.setItem(r, c, it)
                if it.text() != str(v):
                    it.setText(str(v))
            c_ = next((c for c in self.chans if c["key"] == s["key"]), None)
            tk = self.trk.get(s["key"])
            if tk is not None and c_ is not None and self.worker is not None:      # 8. perturbations
                bad = dg[0][0] if dg[0][1] == "bad" and (s.get("vrx") or dg[0][0].startswith("reh")) else None
                for ev in tk.feed(now, s.get("rf"), s.get("noise"), s.get("adj_margin"), bad, s.get("obw"), obw_exp,
                                  s.get("adj_lvl")):
                    if ev["kind"] == "diag":
                        ev["value"] = dg[0][2]
                    self._event(c_, ev)
            tone = dg[0][1]
            self.table.item(r, self.C_DIAG).setForeground(QtGui.QColor(self.owner.tone_color(tone)) if tone != "ok"
                                                          else QtGui.QBrush())
            self.table.item(r, self.C_DIAG).setToolTip("\n".join(x[2] for x in dg))
            cs = coverage_state(True, True, s.get("vrx"), "live", getattr(self, "_perf_tone", "ok"))
            for c in range(len(self.COLS)):                   # valeurs fraîches : couleur normale
                it = self.table.item(r, c)
                if it is not None and c != self.C_DIAG:
                    it.setForeground(QtGui.QBrush())
            self.table.item(r, self.C_COV).setForeground(QtGui.QColor(self.owner.tone_color(COVERAGE[cs][1]))
                                                         if COVERAGE[cs][1] != "ok" else QtGui.QBrush())
        self._t_stats = time.time()
        self._stale_shown = False
        self._draw_sel()

    def _freshen(self):
        """Étape 14 (1.) : des valeurs qui ne bougent plus ne doivent JAMAIS passer pour actuelles. Toutes les 0,5 s :
        âge des dernières mesures -> lignes grisées « ⏸ mesure ancienne (il y a N s) » ; au-delà de FROZEN_S, flux figé :
        l'outil du SDR est coupé et le moniteur relance (reconnexion automatique)."""
        w = self.worker
        t0 = getattr(self, "_t_stats", None)
        if w is None:
            fr, age = "none", None
        else:
            age = time.time() - (t0 if t0 is not None else getattr(self, "_t_start", time.time()))
            fr = freshness(age, FRESH_S, FROZEN_S if t0 is not None else FROZEN_S * 2)
        if fr == "lost" and w is not None and not w.frozen:
            self.sel_lbl.setText(TR("⚠ Flux du SDR figé (plus de données depuis {}) : je relance le SDR…").format(
                age_text(age, TR)))
            w.force_close()
        if fr == "live" or (fr == getattr(self, "_fr_shown", None) and fr != "stale"):
            self._fr_shown = fr
            return
        self._fr_shown = fr
        dim = QtGui.QColor(self.owner.theme.get("dim", "#8e8e93"))
        cs = "stop" if w is None else ("wait" if t0 is None else "stale")
        txt = coverage_text(cs, age if t0 is not None else None, TR)
        for r in range(len(self.chans)):
            for c in range(len(self.COLS)):
                it = self.table.item(r, c)
                if it is not None:
                    it.setForeground(dim)
            it = self.table.item(r, self.C_COV)
            if it is not None:
                it.setText(txt)
                if cs == "stale":
                    it.setForeground(QtGui.QColor(self.owner.tone_color("warn")))

    def _spec(self, F, L):
        o = self.owner
        self._lastFL = (F, L)
        o.sdr_listen_feed(self.dev_combo.currentData(), F, L)
        for c in self.chans:                       # 2. waterfall de chaque micro (± 150 kHz), 300 lignes max
            m = np.abs(F - c["freq"]) <= 0.15
            if not m.any():
                continue
            row = L[m]
            q = self.wf.get(c["key"])
            if q is None or q.shape[1] != len(row):
                q = np.full((300, len(row)), np.nan, dtype=np.float32)
            q = np.roll(q, 1, axis=0)
            q[0] = row
            self.wf[c["key"]] = q

    def _draw_sel(self):
        k = self.sel
        if k is None:
            return
        q = self.wf.get(k)
        if q is not None:
            v = np.nan_to_num(q, nan=float(np.nanmin(q)) if np.isfinite(q).any() else -120.0)
            lo, hi = float(np.percentile(v, 5)), float(np.max(v))
            self.wf_img.setImage(v[::-1].T, autoLevels=False, levels=(lo, max(lo + 10.0, hi)))   # récent en haut
            self.wf_img.setRect(QtCore.QRectF(-150.0, 0.0, 300.0, float(v.shape[0])))           # x = kHz autour du micro
        h = self.hist.get(k)
        if h is not None and h.pts:
            t_end = h.pts[-1][0]
            for curve, key in ((self.c_rf, "rf"), (self.c_nz, "noise"), (self.c_au, "audio")):
                t, v = h.series(key, t_end - 600)
                curve.setData((t - t_end) / 60.0, v)
            ds = h.drift_stats()
            s = next((x for x in self.rows if x["key"] == k), None)
            if s is not None:
                dg = rf_audio_diag(dict(s, nominal=75.0), TR)
                if self.mode_combo.currentData() == "show":
                    dg = [x for x in dg if x[0] != "ok"] + rehearsal_check(self._ref().get(k), s, TR) or dg
                cmp_ = []                                    # 10. comparaison des récepteurs (10 dernières minutes)
                ex = self.ext.get(k) or {}
                t1, v1 = h.series("rf", t_end - 600)
                for key2, nm in (("tsa", "tinySA"), ("rx", TR("récepteur"))):
                    b2 = [(t_, v_) for t_, v_ in ex.get(key2, ()) if t_ >= t_end - 600]
                    if b2:
                        cmp_.append(compare_text(compare_receivers(list(zip(t1, v1)), b2), "SDR", nm, TR))
                self.sel_lbl.setText(f"🎧 {s['name']} ({s['freq']:.3f} MHz) : " + " · ".join(x[2] for x in dg)
                                     + (TR(" · dérive sur 10 min : moyenne {} kHz, ± {} kHz").format(
                                         f"{ds['mean']:+.1f}", f"{ds['std']:.1f}") if ds else "")
                                     + "".join("\n" + x for x in cmp_))

    # ---------------------------------------------------------------- V8 étape 10 : incidents
    def _inc_root(self):
        d = Path(self.owner.log_dir) / "incidents"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return d

    def _chron_add(self, t, name, what, folder="", kind=None):
        """Nouvelle ligne de la chronologie ; étape 14 (6.) : le même problème répété sur le même micro (moins de 10 min)
        ne fait PAS de nouvelle ligne : « ×N », de la 1re à la dernière fois. -> True si regroupé."""
        i = chron_group(self.chron, name, kind, t) if kind and not folder else None
        if i is not None:
            x = self.chron[i]
            x["n"], x["t_last"], x["what"] = x.get("n", 1) + 1, t, what
            for c, v in ((0, f"{datetime.fromtimestamp(x['t']):%H:%M:%S} → {datetime.fromtimestamp(t):%H:%M:%S}"),
                         (2, f"{what} ×{x['n']}")):
                it = self.chron_tbl.item(i, c)
                if it is not None:
                    it.setText(v)
            return True
        self.chron.insert(0, dict(t=t, name=name, what=what, dir=folder, kind=kind, n=1, t_last=t))
        del self.chron[500:]
        tb = self.chron_tbl
        tb.insertRow(0)
        for c, v in enumerate((datetime.fromtimestamp(t).strftime("%H:%M:%S"), name, what,
                               TR("⏳ en cours…") if folder else "")):
            tb.setItem(0, c, QtWidgets.QTableWidgetItem(v))
        while tb.rowCount() > 500:
            tb.removeRow(tb.rowCount() - 1)
        return False

    def _event(self, c, ev, force=False):
        """Une perturbation (ou une alarme) sur un micro : dans la chronologie, et dossier d'incident si coché."""
        ev = dict(ev, when=datetime.fromtimestamp(ev["t"]).strftime("%H:%M:%S"))
        c.setdefault("events", deque(maxlen=200)).append(ev)
        auto = self.inc_chk.isChecked() and ev["kind"] in INC_AUTO_KINDS and ev["t"] - self._last_auto >= INC_GAP_S
        folder = ""
        if (force or auto) and self.worker is not None:
            self._last_auto = ev["t"]                      # un dossier toutes les 2 min au plus (place disque)
            folder = str(self._inc_root() / datetime.fromtimestamp(ev["t"]).strftime("%Y-%m-%d") /
                         f"incident_{datetime.fromtimestamp(ev['t']):%H%M%S}_{incident_slug(c['name'])}")
            fl = getattr(self, "_lastFL", None)
            self.incs[folder] = dict(chan=c, ev=ev, spec=(np.asarray(fl[0]).tolist(), np.asarray(fl[1]).tolist())
                                     if fl is not None else None)
            self.worker.inc_req.append(dict(key=c["key"], name=c["name"], freq=c["freq"], trigger=ev, t=ev["t"],
                                            dir=folder))
        grouped = self._chron_add(ev["t"], c["name"], anomaly_text(ev, TR), folder, ev["kind"])
        if ev["kind"] != "burst" and not grouped:            # répétition : une seule fois au journal
            self.owner.log_event(dict(name=c["name"], freq=c["freq"], note=anomaly_text(ev, TR) +
                                      (TR(" · dossier : {}").format(folder) if folder else "")), 0.0, "INCIDENT SDR")

    def _bursts(self, evs):
        for e_ in evs[:5]:
            c = dict(key=None, name=TR("inconnu"), freq=float(e_["f"]))
            self._chron_add(e_["t1"], c["name"], anomaly_text(dict(kind="burst", value=TR("{} MHz, {} s, {} dBFS").format(
                f"{e_['f']:.3f}", f"{max(0.05, e_['t1'] - e_['t0']):.1f}", f"{e_['peak']:.0f}")), TR),
                            "", f"burst{round(float(e_['f']), 1)}")

    def manual_incident(self):
        if self.worker is None or not self.chans:
            self.sel_lbl.setText(TR("Lance d'abord le moniteur (▶ Surveiller)."))
            return
        c = next((c for c in self.chans if c["key"] == self.sel), self.chans[0])
        self._event(c, dict(kind="manual", t=time.time()), force=True)
        self.tabs.setCurrentIndex(1)

    def _inc_done(self, res):
        """IQ écrit (ou pas) : mesures.json + rapport.html, chronologie mise à jour, vieux dossiers effacés."""
        req = res["req"]
        folder = req["dir"]
        info = self.incs.pop(folder, None) or {}
        same = (res.get("iq") or {}).get("same")
        if same:                                   # rangé dans le dossier de l'incident en cours à ce moment-là
            for r, x in enumerate(self.chron):
                if x.get("dir") == folder:
                    x["dir"] = same
                    it = self.chron_tbl.item(r, 3)
                    if it is not None:
                        it.setText(TR("📦 avec {}").format(os.path.basename(same)))
                        it.setToolTip(same)
            return
        c = info.get("chan") or dict(name=req.get("name", ""), freq=req.get("freq", 0.0))
        t = float(req["t"])
        h = self.hist.get(req.get("key"))
        series = {}
        if h is not None:
            for k in ("rf", "noise", "audio", "drift", "snr", "dev"):
                tt, vv = h.series(k, t - 300.0)
                series[k] = [[round(float(a), 2), round(float(b), 2)] for a, b in zip(tt, vv)]
        s = next((x for x in self.rows if x.get("key") == req.get("key")), None)
        evs = [dict(e_) for e_ in c.get("events", []) if abs(e_["t"] - t) <= 600]
        doc = dict(version=APP_VER, name=c.get("name", ""), freq=c.get("freq", 0.0), t=t,
                   when=datetime.fromtimestamp(t).strftime("%d/%m/%Y %H:%M:%S"), trigger=req.get("trigger") or {},
                   also=[a for a in res.get("also") or [] if a], series=series, events=evs,
                   diag=rf_audio_diag(dict(s, nominal=75.0), TR) if s else [],
                   last=s or {}, iq=res.get("iq") or {}, sdr=self.dev_combo.currentText(),
                   duration=incident_duration(series.get("rf", []), t))
        sp = info.get("spec")
        if not sp and getattr(self, "_lastFL", None) is not None:     # incident parti avant le 1er spectre
            sp = (np.asarray(self._lastFL[0]).tolist(), np.asarray(self._lastFL[1]).tolist())
        if sp:                                       # 18. capture du spectre, au plus 3000 points
            k_ = max(1, len(sp[0]) // 3000)
            doc["spectrum"] = dict(F=[round(x, 5) for x in sp[0][::k_]], L=[round(x, 1) for x in sp[1][::k_]])
        q = self.wf.get(req.get("key"))
        if q is not None and np.isfinite(q).any():  # 18. waterfall du micro en image
            try:
                os.makedirs(folder, exist_ok=True)
                v = np.nan_to_num(q, nan=float(np.nanmin(q)))
                lo, hi = float(np.percentile(v, 5)), float(np.max(v))
                idx = np.clip((v - lo) / max(10.0, hi - lo) * 255, 0, 255).astype(np.uint8)
                lut = make_lut(self.owner.theme.get("wf", "Inferno"))
                rgb = np.ascontiguousarray(lut[idx][:, :, :3].astype(np.uint8))
                img = QtGui.QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1] * 3, QtGui.QImage.Format.Format_RGB888)
                if img.scaled(min(900, rgb.shape[1] * 3), rgb.shape[0]).save(os.path.join(folder, "waterfall.png")):
                    doc["wf_png"] = "waterfall.png"
            except Exception:  # noqa: BLE001
                pass
        try:
            os.makedirs(folder, exist_ok=True)
            write_atomic(os.path.join(folder, "mesures.json"),
                         json.dumps(doc, ensure_ascii=False, indent=1, default=str))       # étape 14 : jamais à moitié
            write_atomic(os.path.join(folder, "rapport.html"), incident_report_html(doc, TR))
            state = TR("📦 {}").format(os.path.basename(folder)) + ("" if doc["iq"].get("file") else TR(" (sans IQ)"))
        except OSError as e:
            state = TR("⚠ {}").format(e)
        for r, x in enumerate(self.chron):
            if x.get("dir") == folder:
                it = self.chron_tbl.item(r, 3)
                if it is not None:
                    it.setText(state)
                    it.setToolTip(folder)
        self._prune()

    def _prune(self):
        root = self._inc_root()
        ent = []
        try:
            for d in root.glob("*/incident_*"):
                n = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
                ent.append((str(d), d.stat().st_mtime, n))
        except OSError:
            return
        for p in incident_prune(ent, INC_MAX_MB * 2 ** 20):
            shutil.rmtree(p, ignore_errors=True)

    def replay(self, row=None):
        """9. Rejouer un incident : le rapport dans le navigateur + l'IQ dans le temps réel (son, spectre, waterfall)."""
        r = self.chron_tbl.currentRow() if row is None else row
        x = self.chron[r] if 0 <= r < len(self.chron) else next((y for y in self.chron if y.get("dir")), None)
        if not x or not x.get("dir"):
            self.sel_lbl.setText(TR("Choisis dans la chronologie une ligne qui a un dossier."))
            return
        open_incident(self.owner, x["dir"], self)

    def _perf(self, p):
        txt, tone = perf_view(p["expected"], p["got"], p["load"], p.get("lag", 0.0))
        self.perf_lbl.setText(TR("⚙ SDR : {} · {} récepteur(s) virtuel(s)").format(TR(txt), p.get("vrx", 0)))
        self.perf_lbl.setStyleSheet("" if tone == "ok" else f"color: {self.owner.tone_color(tone)};")
        self.perf_lbl.setVisible(tone != "ok")          # tout va bien : le détail reste dans l'onglet Système
        self._perf_tone = tone
        self._fails = 0                                   # des données arrivent : le SDR va bien
        ct, ctone = capacity_view(getattr(self, "n_asked", len(self.chans)), len(self.chans), p.get("vrx", 0),
                                  p.get("crit", 0), TR)
        self.cap_lbl.setText(ct)
        self.cap_lbl.setStyleSheet("" if ctone == "ok" else f"color: {self.owner.tone_color(ctone)};")
        if p.get("crit") and time.time() - getattr(self, "_t_crit", 0) > 300:      # 16. ressources insuffisantes
            self._t_crit = time.time()
            self.owner.log_event(dict(name=TR("SDR"), freq=0.0, note=ct), 0.0, "INCIDENT SDR")
        self._sys(p)

    def _sys(self, p):
        """Onglet Système : santé du SDR et du PC."""
        root = Path(self.owner.log_dir)

        def size_mb(sub):
            try:
                return sum(f.stat().st_size for f in (root / sub).rglob("*") if f.is_file()) / 1e6
            except OSError:
                return 0.0
        now = time.time()
        if now - getattr(self, "_t_sizes", 0) > 30:
            try:
                dg = shutil.disk_usage(root).free / 1e9
            except OSError:
                dg = None
            self._sizes = dict(disk_gb=dg, inc_mb=size_mb("incidents"), audio_mb=size_mb("enregistrements_audio"),
                               iq_mb=size_mb("enregistrements_iq"))
            self._t_sizes = now
        lost = None if p["expected"] <= 0 else max(0.0, 1.0 - p["got"] / p["expected"]) * 100.0
        rows = resource_view(dict(p, lost=lost, disc=self.disc, disc_why=self.disc_why, **getattr(self, "_sizes", {})), TR)
        t = self.sys_tbl
        t.setRowCount(len(rows))
        for r, (k, v, tone) in enumerate(rows):
            for c, x in enumerate((k, v)):
                it = t.item(r, c)
                if it is None:
                    it = QtWidgets.QTableWidgetItem(x)
                    t.setItem(r, c, it)
                elif it.text() != x:
                    it.setText(x)
            t.item(r, 1).setForeground(QtGui.QColor(self.owner.tone_color(tone)) if tone in ("warn", "bad")
                                       else QtGui.QBrush())

    def _stopped(self, why):
        want = self._want
        if why:
            self.sel_lbl.setText(TR("⚠ Moniteur arrêté : {}").format(why))
        self.stop(keep_paused=bool(why and want))         # audit V8 : le balayage SDR reste en pause jusqu'au retour
        if why and want:                                  # étape 12 : SDR décroché -> on relance tout seul
            self.disc += 1
            self.disc_why = why[:80]
            self._fails += 1
            d = reconnect_delay(self._fails)
            self._want = True
            self.owner.log_event(dict(name=TR("SDR"), freq=0.0, note=why), 0.0, "APPAREIL PERDU")
            self.sel_lbl.setText(TR("⚠ SDR décroché ({}) : nouvel essai dans {} s…").format(why, f"{d:.0f}"))
            QtCore.QTimer.singleShot(int(d * 1000), self._retry)

    def _retry(self):
        if self._want and self.worker is None and self.isVisible():
            self.toggle()
        elif self.worker is None:                         # plus de relance : on rend le SDR au balayage
            for w in self.paused:
                w.paused = False
            self.paused = []

    def stop(self, keep_paused=False):
        self._want = False
        self.timer.stop()
        w, self.worker = self.worker, None
        if w is not None:
            w.requestInterruption()
            w.wait(5000)
        if self.audio is not None:
            self.audio.close()
            self.audio = None
        if not keep_paused:
            for w in self.paused:
                w.paused = False
            self.paused = []
        self.owner.sdr_listen_clear()
        self.go_btn.setText("▶ Surveiller")
        self.dev_combo.setEnabled(True)
        self.trk = {}
        self._fr_shown = None
        self._freshen()                                # arrêté : plus aucune valeur ne passe pour actuelle

    def closeEvent(self, ev):
        self.stop()
        super().closeEvent(ev)


class ReceiverClient(threading.Thread):
    """V8 étapes 11 / 13 (14. / 15.) : télémétrie d'un récepteur en réseau, toutes marques gérées (RX_BRANDS) : Shure en
    TCP, Sennheiser G3 / G4 et SSC en UDP ; reconnexion toutes les 5 s, muet 15 s = coupé. Sans Qt (fil Python)."""

    def __init__(self, host, port=None, brand="shure"):
        super().__init__(daemon=True)
        self.brand = brand if brand in RX_BRANDS else "shure"
        self.host, self.port = host, int(port or RX_BRANDS[self.brand]["port"] or 0)
        self.state, self.div, self.hist = {}, {}, {}
        self.ok, self.err, self.t_last = False, "", 0.0
        self.lock = threading.Lock()
        self._halt = threading.Event()

    def _got(self, ch, t, key_div=True):
        """Après une mise à jour d'un canal : diversity et historique du niveau."""
        st = self.state.get(ch, {})
        st["t"] = t                                   # étape 14 : heure de la dernière nouvelle de CE canal
        if key_div and st.get("ant"):
            self.div.setdefault(ch, DiversityAB()).feed(st.get("ant"), t)
        if st.get("rf") is not None:
            self.hist.setdefault(ch, deque(maxlen=3600)).append((t, float(st["rf"])))
        self.t_last = t

    def run(self):
        if not RX_BRANDS[self.brand]["proto"]:
            self.err = TR(RX_BRANDS[self.brand].get("why", ""))
            return
        while not self._halt.is_set():
            try:
                (self._run_tcp if RX_BRANDS[self.brand]["proto"] == "tcp" else self._run_udp)()
            except OSError as e:
                self.ok, self.err = False, str(e)
            self._halt.wait(5)

    def _run_tcp(self):
        s = socket.create_connection((self.host, self.port), timeout=3)
        try:
            s.settimeout(1.0)
            for c in shure_init():
                s.sendall(c.encode("ascii"))
            self.ok, self.err, buf, t_rx = True, "", "", time.time()
            while not self._halt.is_set():
                try:
                    d = s.recv(4096)
                except socket.timeout:
                    if time.time() - t_rx > 15:
                        raise OSError("plus de réponse depuis 15 s")
                    continue
                if not d:
                    raise OSError("connexion fermée par le récepteur")
                t_rx = time.time()
                msgs, buf = shure_split(buf + d.decode("ascii", "replace"))
                buf = buf[-4000:]
                with self.lock:
                    for m in msgs:
                        p = shure_parse(m)
                        if p and shure_apply(self.state, p):
                            self._got(p["ch"], t_rx, p["key"] in ("ALL", "RF_ANTENNA"))
        finally:
            s.close()

    def _run_udp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(1.0)
            ssc = self.brand == "ssc"
            t_rx, t_req, first = time.time(), 0.0, True
            while not self._halt.is_set():
                if time.time() - t_req >= (5.0 if ssc else 50.0):      # G4 : abonnement de 60 s à renouveler
                    t_req = time.time()
                    for c in (ssc_init() if ssc else g4_init()):
                        s.sendto(c.encode("utf-8"), (self.host, self.port))
                try:
                    d, _a = s.recvfrom(65535)
                except socket.timeout:
                    if time.time() - t_rx > 15:
                        self.ok = False
                        raise OSError("plus de réponse depuis 15 s" if not first else "pas de réponse")
                    continue
                t_rx, first = time.time(), False
                self.ok, self.err = True, ""
                txt = d.decode("utf-8", "replace")
                with self.lock:
                    if ssc:
                        try:
                            obj = json.loads(txt)
                        except ValueError:
                            continue
                        if ssc_apply(self.state, obj):
                            for ch in list(self.state):
                                self._got(ch, t_rx)
                    else:
                        if any([g4_apply(self.state, ln) for ln in re.split(r"[\r\n]+", txt) if ln.strip()]):
                            self._got(1, t_rx)
        finally:
            s.close()

    def stop(self):
        self._halt.set()

    def snapshot(self):
        with self.lock:
            return {c: dict(v, div=self.div[c].text(TR) if c in self.div else "—", hist=list(self.hist.get(c, ())),
                            alerts=receiver_alerts(v, self.div.get(c), TR))
                    for c, v in self.state.items()}


class ShureClient(ReceiverClient):
    """Récepteur Shure (TCP 2202) — nom gardé de l'étape 11."""

    def __init__(self, host, port=SHURE_PORT):
        super().__init__(host, port, "shure")


class ReceiversDialog(QtWidgets.QDialog):
    """V8 étape 11 : 📶 récepteurs Shure en réseau : ce que VOIT chaque récepteur (niveau RF, antenne A / B, diversity,
    son, pile), relié à ta liste par la fréquence ; sert aussi à comparer avec le SDR / le tinySA (moniteur multicanal)."""
    COLS = ["Récepteur", "Canal", "Nom", "MHz", "RF", "Antenne", "Diversity A / B", "Son", "Pile", "Dans ma liste",
            "Alertes"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Récepteurs en réseau (télémétrie)")
        self.setModal(False)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Tes récepteurs en réseau disent eux-mêmes ce qu'ils reçoivent : niveau RF, antenne, son, "
                                "pile, alertes. Choisis la marque, tape l'adresse IP, puis <b>＋ Ajouter</b>.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 2)
        lay.addWidget(info)
        self.brand = QtWidgets.QComboBox()                  # étape 13 : toutes marques
        for k, b in RX_BRANDS.items():
            self.brand.addItem(b["name"], k)
        self.brand.setToolTip("La marque / famille du récepteur (le protocole réseau en dépend).")
        self.addr = QtWidgets.QLineEdit("")
        self.addr.setPlaceholderText("192.168.1.50")
        self.addr.setToolTip("Adresse IP du récepteur (le port habituel de la marque est mis tout seul ; sinon « adresse:port »).")
        self.add_btn = QtWidgets.QPushButton("＋ Ajouter")
        self.add_btn.setToolTip("Ajoute ce récepteur et s'y connecte (retenu dans les réglages).")
        self.add_btn.clicked.connect(lambda *_: self.add())
        self.addr.returnPressed.connect(self.add)
        lay.addLayout(o._row("Marque :", self.brand, "Adresse :", self.addr, self.add_btn))
        self.why = QtWidgets.QLabel("")
        self.why.setWordWrap(True)
        lay.addWidget(self.why)
        self.brand.currentIndexChanged.connect(lambda *_: self._brand_changed())
        self.mine = QtWidgets.QListWidget()
        self.mine.setMaximumHeight(90)
        self.mine.setToolTip("Tes récepteurs. Choisis-en un puis « Retirer » (ou touche Suppr).")
        self.del_btn = QtWidgets.QPushButton("Retirer")
        self.del_btn.setToolTip("Retire le récepteur choisi de la liste.")
        self.del_btn.clicked.connect(lambda *_: self.remove())
        lay.addLayout(o._row(self.mine, self.del_btn))
        del_key(self.mine, self.remove)
        self._fill_mine()
        self._brand_changed()
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self.table.horizontalHeader()
        for c in range(len(self.COLS) - 1):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(len(self.COLS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("RF = niveau reçu par le récepteur (dBm) · Antenne = A, B ou aucune · Diversity = part du\n"
                              "temps sur chaque antenne et bascules (beaucoup de bascules / « aucune » = antennes à revoir).")
        lay.addWidget(self.table, 1)
        self.st = QtWidgets.QLabel("")
        self.st.setWordWrap(True)
        lay.addWidget(self.st)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()
        fit_dialog(self, 900, 460)

    def _brand_changed(self):
        b = RX_BRANDS.get(self.brand.currentData()) or {}
        ok = bool(b.get("proto"))
        self.add_btn.setEnabled(ok)
        self.addr.setEnabled(ok)
        self.why.setText("" if ok else "⚠ " + TR(b.get("why", "")))
        self.why.setStyleSheet("" if ok else f"color: {self.owner.tone_color('warn')};")

    def _fill_mine(self):
        self.mine.clear()
        for b, h, p in receiver_addrs(self.owner.sdr_cfg.get("shure", "")):
            it = QtWidgets.QListWidgetItem(f"{TR(RX_BRANDS[b]['name'])} · {h}" + (f":{p}" if p != RX_BRANDS[b]["port"] else ""))
            it.setData(Qt.ItemDataRole.UserRole, (b, h, p))
            self.mine.addItem(it)

    def add(self):
        b = self.brand.currentData()
        a = self.addr.text().strip()
        if not a or not RX_BRANDS[b]["proto"]:
            return False
        cur = receiver_addrs(self.owner.sdr_cfg.get("shure", ""))
        new = receiver_addrs(f"{b}:{a}")
        if not new:
            self.why.setText(TR("Adresse illisible : tape une adresse IP (ex. 192.168.1.50)."))
            return False
        self.owner.receivers_start(receiver_addrs_text(cur + [x for x in new if x not in cur]))
        self.addr.clear()
        self._fill_mine()
        self.refresh()
        return True

    def remove(self):
        it = self.mine.currentItem()
        if it is None:
            return
        x = tuple(it.data(Qt.ItemDataRole.UserRole))
        cur = [y for y in receiver_addrs(self.owner.sdr_cfg.get("shure", "")) if y != x]
        self.owner.receivers_start(receiver_addrs_text(cur))
        self._fill_mine()
        self.refresh()

    def connect_all(self):
        self.owner.receivers_start(self.owner.sdr_cfg.get("shure", ""))
        self.refresh()

    def refresh(self):
        o = self.owner
        rows = o.receivers()
        self.table.setRowCount(len(rows))
        for r, x in enumerate(rows):
            w = o.watch_near(x.get("freq"))
            un = x.get("rf_unit") or "dBm"
            vals = [("✔ " if x.get("live") else "⏸ ") + x["host"]
                    + ("" if x.get("live") else " · " + TR("il y a {}").format(age_text(x.get("age"), TR))),
                    str(x["ch"]), x.get("name") or "—",
                    "—" if x.get("freq") is None else f"{x['freq']:.3f}",
                    "—" if x.get("rf") is None else f"{x['rf']:g} {un}", x.get("ant") or "—", x.get("div") or "—",
                    "—" if x.get("audio") is None else (f"{x['audio']:g} dBFS" if un == "dBm" else f"{x['audio']:g} %"),
                    "—" if x.get("batt") is None else "▮" * int(x["batt"]) + "▯" * max(0, 5 - int(x["batt"])),
                    (w["name"] or f"{w['freq']:.3f}") if w else "—",
                    " · ".join(x.get("alerts") or []) or "—"]
            for c, v in enumerate(vals):
                it = self.table.item(r, c)
                if it is None:
                    self.table.setItem(r, c, QtWidgets.QTableWidgetItem(v))
                elif it.text() != v:
                    it.setText(v)
        dim = QtGui.QColor(o.theme.get("dim", "#8e8e93"))
        for r, x in enumerate(rows):                       # étape 14 : canal sans nouvelles = grisé, valeurs anciennes
            for c in range(self.table.columnCount()):
                it = self.table.item(r, c)
                if it is not None:
                    it.setForeground(QtGui.QBrush() if x.get("live") else dim)
                    it.setToolTip("" if x.get("live") else TR("Valeurs d'il y a {} : le récepteur ne répond plus (réseau, "
                                                                "alimentation ?).").format(age_text(x.get("age"), TR)))
        for r, x in enumerate(rows):                       # 14. alertes : en rouge, notées une fois au journal
            it = self.table.item(r, 10)
            if it is not None:
                it.setForeground(QtGui.QColor(o.tone_color("bad")) if x.get("alerts") else QtGui.QBrush())
                it.setToolTip("\n".join(x.get("alerts") or []))
            seen = o.__dict__.setdefault("_rx_alerts_seen", set())
            for a_ in x.get("alerts") or []:
                k_ = (x["host"], x["ch"], a_)
                if k_ not in seen:
                    seen.add(k_)
                    o.log_event(dict(name=x.get("name") or f"{x['host']} #{x['ch']}", freq=x.get("freq") or 0.0,
                                     note=a_), 0.0, "RÉCEPTEUR")
        cl = list(getattr(o, "_shure", {}).values())
        if not cl:
            self.st.setText(TR("Aucun récepteur : choisis la marque, tape une adresse puis ＋ Ajouter."))
        else:
            self.st.setText(" · ".join((f"✔ {c.host}" if c.ok else f"✗ {c.host} : {c.err or TR('connexion…')}") for c in cl))

    def closeEvent(self, ev):
        self.timer.stop()
        super().closeEvent(ev)
