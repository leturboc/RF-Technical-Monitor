# Appareils de mesure : tinySA (série / réseau), SDR en balayage, fil de balayage, relais réseau.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


# --------------------------------------------------------------------------
# Communication avec le tinySA
# --------------------------------------------------------------------------
class Aborted(Exception):
    """Commande interrompue (bouton Arrêter)."""


class TinySA:
    PROMPT = b"ch>"
    NET_IDLE_MIN = 20.0          # réseau : liaison déclarée muette après ce silence (s), allongé selon le RBW

    def __init__(self, port, baud=115200, trace=None):
        # port : « COM3 » (USB) ou « socket://192.168.1.20:5025 » (réseau, via le relais ou ser2net)
        # baud : ignoré en USB (port COM virtuel) ; ne compte que sur un vrai port série (adaptateur, connecteur)
        self.net = "://" in str(port)
        self.idle = self.NET_IDLE_MIN          # tinySA muet (réseau coupé, appareil figé) : erreur → reconnexion
        self.abort = None                      # fonction : True = abandonner la commande en cours (Arrêter)
        self.trace = trace                     # fonction(texte) : journal des échanges (diagnostic)
        self.rx_bytes = self.tx_bytes = 0      # 🌐 compteur réseau : octets échangés
        self.rtt = None                        # délai jusqu'au 1er octet de la dernière réponse (s)
        self.ser = serial.serial_for_url(port, int(baud), timeout=0.2)
        self.ser.reset_input_buffer()
        self.cmd("", timeout=5)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def cmd(self, text, timeout=15.0):
        if self.trace is None:
            return self._cmd(text, timeout)
        t0 = time.monotonic()
        self.trace(f">> {text or '(entrée)'}")
        try:
            lines = self._cmd(text, timeout)
        except Exception as e:
            self.trace(f"!! {type(e).__name__} : {e} (après {time.monotonic() - t0:.1f} s)")
            raise
        first = lines[0][:70] if lines else ""
        self.trace(f"<< {len(lines)} ligne(s) en {time.monotonic() - t0:.2f} s" + (f" : {first}" if first else ""))
        return lines

    def _cmd(self, text, timeout=15.0):
        self.ser.reset_input_buffer()
        out_ = (text + "\r").encode()
        self.ser.write(out_)
        self.tx_bytes += len(out_)
        buf, t0 = bytearray(), time.monotonic()      # monotonic : une heure système corrigée (NTP) ne fausse rien
        t_rx, first = t0, True
        while True:
            now = time.monotonic()
            if now - t0 > timeout:
                raise TimeoutError(f"Pas de réponse du tinySA à « {text} »")
            if self.abort is not None and self.abort():
                raise Aborted()
            if self.idle is not None and now - t_rx > self.idle:
                # câble réseau arraché, Wi-Fi coupé, tinySA figé : la liaison ne se ferme pas, elle se tait
                raise TimeoutError(f"tinySA muet depuis {self.idle:.0f} s")
            n = self.ser.in_waiting
            chunk = self.ser.read(n if n else 1)
            if chunk:
                t_rx = time.monotonic()
                if first:
                    self.rtt, first = t_rx - t0, False
                self.rx_bytes += len(chunk)
                buf.extend(chunk)
                if buf[-16:].rstrip().endswith(self.PROMPT):
                    break
        lines = [l.strip() for l in buf.decode(errors="ignore").replace("\r", "\n").split("\n")]
        lines = [l for l in lines if l and not l.startswith("ch>")]
        if lines and text and lines[0].startswith(text[:12]):
            lines = lines[1:]
        return lines

    def try_cmd(self, text):
        """Commande de réglage ; renvoie (ok, message d'erreur)."""
        try:
            lines = self.cmd(text, timeout=6)
        except TimeoutError:
            return False, f"{text} : pas de réponse"
        refus = tinysa_refusal(lines)              # disque USB, mise à jour… : le réglage n'est PAS appliqué
        if refus:
            return False, f"{text} : {refus}"
        bad = [l for l in lines if "usage" in l.lower() or l.endswith("?")]
        return (not bad), (f"{text} : {bad[0]}" if bad else "")

    def version(self):
        try:
            lines = self.cmd("version", timeout=4)
            return lines[0] if lines else ""
        except Exception:
            return ""

    def set_rbw(self, khz):
        return self.try_cmd("rbw auto" if khz is None else f"rbw {khz:g}")

    def set_input(self, high):
        return self.try_cmd("mode high input" if high else "mode low input")

    def expect_scan(self, points, rbw_khz, step_khz=None):
        """Temps de silence toléré pendant un scan (le tinySA ne répond qu'à la fin du segment).
        RBW auto : le tinySA la règle sur le pas ; un pas fin (beaucoup de points) = RBW étroite = scan bien plus
        long. Avant, on supposait toujours 0,05 s / point : avec 10 000 points ou plus le tinySA était déclaré
        « muet » à tort → liaison perdue (retour de Clément)."""
        if rbw_khz is None and step_khz:
            rbw_khz = auto_rbw(step_khz)
        per_pt = 0.05 if rbw_khz is None else max(0.002, 3.0 / max(rbw_khz, 0.1))
        self.idle = self.NET_IDLE_MIN + points * per_pt

    def scan(self, start_hz, stop_hz, points):
        """Renvoie (freqs Hz ou None, niveaux dBm)."""
        lines = self.cmd(f"scan {int(start_hz)} {int(stop_hz)} {int(points)} 3", timeout=900)
        why = tinysa_refusal(lines)
        if why:
            raise RuntimeError(why)
        freqs, levels = parse_scan_lines(lines)
        if not len(levels):
            raise RuntimeError("Le tinySA n'a renvoyé aucune mesure (scan).")
        return freqs, levels


# --------------------------------------------------------------------------
# V8 : SDR (HackRF One, RTL-SDR) vus comme un tinySA, par leur outil de balayage officiel
# --------------------------------------------------------------------------
SDR_TOOL_DIRS = [r"C:\Program Files\PothosSDR\bin", r"C:\Program Files (x86)\PothosSDR\bin",
                 r"C:\Program Files\HackRF\bin", r"C:\Program Files\rtl-sdr\bin", r"C:\Program Files\rx_tools\bin",
                 r"C:\Program Files\SoapySDR\bin", "/usr/bin", "/usr/local/bin",
                 "/opt/homebrew/bin"]


SDR_PROCS = set()               # étape 14 (7.) : tous les outils SDR lancés (hackrf_sweep, hackrf_transfer, rx_sdr…)
SDR_PROCS_LOCK = threading.Lock()


def sdr_proc_track(p):
    """Retient un outil SDR lancé, pour pouvoir le tuer à coup sûr à la fermeture de l'appli."""
    with SDR_PROCS_LOCK:
        SDR_PROCS.add(p)
        for q in [q for q in SDR_PROCS if q.poll() is not None]:
            SDR_PROCS.discard(q)
    return p


def sdr_kill_all():
    """Tue tous les outils SDR encore vivants (sinon, sous Windows, ils survivent à l'appli et gardent le SDR occupé).
    -> nombre tués."""
    n = 0
    with SDR_PROCS_LOCK:
        procs = list(SDR_PROCS)
        SDR_PROCS.clear()
    for p in procs:
        try:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=3)
                n += 1
        except Exception:  # noqa: BLE001
            pass
    return n


import atexit  # noqa: E402
atexit.register(sdr_kill_all)


def find_sdr_tool(name, extra_dir=""):
    """Chemin de hackrf_sweep / rtl_power : dossier choisi, à côté de l'appli (et ./outils), PATH, dossiers
    d'installation habituels (PothosSDR…). -> chemin ou None."""
    exe = name + (".exe" if sys.platform.startswith("win") else "")
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for d in [extra_dir, str(here), str(here / "outils"), str(here / "tools")]:
        if d and (Path(d) / exe).is_file():
            return str(Path(d) / exe)
    for kit in sdr_kit_dirs(here):                    # V8 étape 11 : kit SDR dézippé à côté de l'appli
        if (kit / "bin" / exe).is_file():
            os.environ.setdefault("SOAPY_SDR_ROOT", str(kit))      # modules SoapySDR du kit (lib/SoapySDR)
            return str(kit / "bin" / exe)
    w = shutil.which(name)
    if w:
        return w
    for d in SDR_TOOL_DIRS:
        if (Path(d) / exe).is_file():
            return str(Path(d) / exe)
    return None


def sdr_kit_dirs(here=None):
    """V8 étape 11 : où chercher le kit SDR (outils open source pour Windows, kit-sdr-windows.zip dézippé) : à côté de
    l'appli, puis dans Documents/RF Technical Monitor."""
    here = Path(here) if here else (Path(sys.executable).parent if getattr(sys, "frozen", False)
                                    else Path(__file__).resolve().parent)
    return [here / "kit-sdr", DOCS_ROOT / "kit-sdr"]


SDR_KIT_HINT = ("Le plus simple : le kit SDR. Télécharge kit-sdr-windows.zip (pré-release « Kit SDR » du dépôt) et dézippe-le "
                "À CÔTÉ de RF-Technical-Monitor.exe (dossier « kit-sdr ») : hackrf_sweep, rtl_power, rx_tools et SoapySDR sont "
                "trouvés tout seuls. Restent à installer à part : le pilote USB (Zadig), et pour un SDRplay ou un "
                "WiNRADiO, le logiciel de la marque.")


import abc  # noqa: E402  (V8 : interface commune des appareils de mesure)


class SpectrumDevice(abc.ABC):
    """V8 : ce que le ScanWorker attend d'un appareil de mesure (tinySA, SDR, plus tard WiNRADiO / Airspy…).
    Un appareil = une classe avec ces méthodes, inscrite par register_spectrum_driver(nom, reconnaît, fabrique) :
    - scan(début Hz, fin Hz, points) -> (fréquences Hz, niveaux dB) : le SEUL indispensable ;
    - version() (texte pour le diagnostic), set_rbw(kHz), set_input(haute ?), try_cmd(texte) -> (accepté, réponse) ;
    - expect_scan(points, rbw, pas) : prévenir de la durée d'un balayage (délai de silence) ;
    - configure(bandes, rbw, gains) : appelé une fois par cycle (un SDR y lance son outil sur toutes les bandes) ;
    - close() ; attributs abort (fonction -> True = arrêter), rx_bytes / tx_bytes / rtt (compteur réseau).
    `family` (« tinysa », « sdr »…) et `caps` (listen : peut démoduler, realtime : flux IQ, sweep_all : balaye toutes
    les bandes d'un coup, calibrated : niveaux en vrais dBm) disent à l'interface ce que l'appareil sait faire."""
    PROMPT = None
    family = "?"
    caps = dict(listen=False, realtime=False, sweep_all=False, calibrated=False)
    abort = None
    rx_bytes = tx_bytes = 0
    rtt = None

    @abc.abstractmethod
    def scan(self, start_hz, stop_hz, points):
        """-> (fréquences Hz, niveaux dB)."""

    def version(self):
        return type(self).__name__

    def try_cmd(self, text):
        return True, ""

    def set_rbw(self, khz):
        return True, ""

    def set_input(self, high):
        return True, ""

    def expect_scan(self, points, rbw_khz, step_khz=None):
        return None

    def configure(self, bands, rbw_khz, gains):
        return None

    def close(self):
        return None


SpectrumDevice.register(TinySA)            # le tinySA (classe V7) respecte déjà l'interface
TinySA.family = "tinysa"
TinySA.caps = dict(listen=False, realtime=False, sweep_all=False, calibrated=True)
SPECTRUM_DRIVERS = []                      # [(nom, reconnaît(adresse) -> bool, fabrique(adresse, worker))]


def register_spectrum_driver(name, match, make):
    """Inscrit un type d'appareil (le dernier inscrit est essayé en premier ; le tinySA reste le défaut)."""
    SPECTRUM_DRIVERS[:] = [d for d in SPECTRUM_DRIVERS if d[0] != name]
    SPECTRUM_DRIVERS.insert(0, (name, match, make))


def spectrum_driver(addr):
    """Nom du pilote pour une adresse (« COM4 » -> « tinysa », « hackrf » -> « sdr »)."""
    return next((n for n, match, _mk in SPECTRUM_DRIVERS if match(addr or "")), "tinysa")


def open_spectrum_device(addr, worker):
    """Ouvre l'appareil d'une adresse pour un ScanWorker (tinySA par défaut)."""
    for _n, match, make in SPECTRUM_DRIVERS:
        if match(addr or ""):
            return make(addr, worker)
    return TinySA(addr, worker.baud, worker._tr)


WINRADIO_DIRS = [r"C:\Program Files\WiNRADiO", r"C:\Program Files (x86)\WiNRADiO",
                 r"C:\Program Files\WiNRADiO\G39DDC", r"C:\Program Files (x86)\WiNRADiO\G39DDC"]


def find_winradio_dll(extra_dir="", name="G39DDCAPI.dll"):
    """Chemin de la DLL WiNRADiO : dossier choisi, à côté de l'appli (et ./outils), dossiers d'installation
    WiNRADiO (et leurs sous-dossiers), PATH. -> chemin ou None (Windows seulement en pratique)."""
    here = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    for d in [extra_dir, str(here), str(here / "outils"), str(here / "tools")]:
        if d and (Path(d) / name).is_file():
            return str(Path(d) / name)
    for d in WINRADIO_DIRS:
        p = Path(d)
        if (p / name).is_file():
            return str(p / name)
        try:
            for q in p.glob("*/" + name):
                return str(q)
        except OSError:
            pass
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and (Path(d) / name).is_file():
            return str(Path(d) / name)
    return None


class SDRSweep(SpectrumDevice):
    """Un SDR qui se comporte comme un TinySA pour le ScanWorker : l'outil de balayage tourne en continu sur
    toutes les bandes (une seule commande), un fil lit ses lignes (SweepAccum) ; scan(a, z, pts) rend le dernier
    passage complet rééchantillonné (max par cellule). Outil arrêté (SDR débranché) ou muet : erreur → le worker
    reconnecte comme pour un tinySA. Niveaux non étalonnés en dBm : offset / calibration avec un tinySA."""
    PROMPT = None

    def __init__(self, addr, tool_dir="", trace=None, tool=None):
        self.kind, self.serial = parse_sdr_addr(addr)
        self.spec = SDR_KINDS[self.kind]
        exe = tool if tool is not None else find_sdr_tool(self.spec["tool"], tool_dir)
        if exe is None:
            raise RuntimeError(f"{self.spec['tool']} introuvable : installe les outils {self.spec['name']} "
                               f"(PothosSDR sous Windows) ou indique leur dossier dans Outils › 📡 Réglages SDR.")
        self.exe, self.trace, self.abort = exe, trace, None
        self.idle = 30.0
        self.proc, self.key, self.rbw = None, None, None
        self.acc, self.lock = SweepAccum(), threading.Lock()
        self.err = deque(maxlen=30)
        self.served = {}

    def _t(self, txt):
        if self.trace is not None:
            self.trace(txt)

    def version(self):
        name = self.exe if isinstance(self.exe, str) else " ".join(map(str, self.exe))
        return f"{self.spec['name']} · {os.path.basename(str(name))}" + (f" · {self.serial}" if self.serial else "")

    def try_cmd(self, text):
        return True, ""

    def set_rbw(self, khz):
        self.rbw = khz
        return True, ""

    def set_input(self, high):
        return True, ""

    def expect_scan(self, points, rbw_khz, step_khz=None):
        self.idle = 30.0 + points * 0.0005

    def configure(self, bands, rbw_khz, gains):
        """Bandes du cycle -> (re)lance l'outil si les plages, la case ou les gains ont changé."""
        rng = sdr_ranges([(b["start_hz"], b["stop_hz"]) for b in bands], 10 if self.kind == "hackrf" else 1,
                         self.spec["fmin"], self.spec["fmax"])
        if not rng:
            return
        bw = sdr_bin_hz(self.kind, bands, rbw_khz)
        g = dict(lna=24, vga=20, amp=False)
        g.update(gains or {})
        key = (tuple(rng), bw, g["lna"], g["vga"], bool(g["amp"]))
        if self.proc is not None and self.proc.poll() is not None:
            time.sleep(0.1)                              # outil mort tout seul : panne, pas un simple réglage
            why = self.err[-1] if self.err else f"code {self.proc.returncode}"
            raise RuntimeError(f"{self.spec['tool']} s'est arrêté ({why}) — {self.spec['name']} débranché ?")
        if key == self.key and self.proc is not None:
            return
        self.key = key
        self._start(sdr_cmd(self.kind, self.exe, rng, bw, g["lna"], g["vga"], g["amp"], self.serial))

    def _start(self, argv):
        self._stop()
        with self.lock:
            self.acc = SweepAccum()
        self.served = {}
        self._t("lancement : " + " ".join(str(x) for x in argv))
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = sdr_proc_track(subprocess.Popen([str(x) for x in argv], stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True,
                                                    bufsize=1, creationflags=flags))
        proc = self.proc
        threading.Thread(target=self._read_out, args=(proc,), daemon=True).start()
        threading.Thread(target=self._read_err, args=(proc,), daemon=True).start()

    def _read_out(self, proc):
        acc = self.acc
        try:
            for line in proc.stdout:
                it = sweep_line(line)
                if it is not None:
                    with self.lock:
                        acc.feed(it)
        except Exception:  # noqa: BLE001 — processus tué pendant la lecture
            pass

    def _read_err(self, proc):
        try:
            for line in proc.stderr:
                line = line.strip()
                if line:
                    self.err.append(line)
                    self._t("outil : " + line[:160])
        except Exception:  # noqa: BLE001
            pass

    def scan(self, start_hz, stop_hz, points):
        """-> (freqs Hz, niveaux dB) du dernier passage complet pas encore servi pour cette plage."""
        if self.proc is None:
            raise RuntimeError(f"{self.spec['tool']} pas lancé (aucune bande ?)")
        key = (round(start_hz), round(stop_hz), int(points))
        need = self.served.get(key, 0)
        t0 = time.time()
        while True:
            with self.lock:
                passes, snap = self.acc.passes, self.acc.snapshot()
            if snap is not None and passes > need:
                break
            if self.abort is not None and self.abort():
                raise Aborted()
            if self.proc.poll() is not None:
                time.sleep(0.1)                          # laisse le fil d'erreur lire la dernière ligne
                why = self.err[-1] if self.err else f"code {self.proc.returncode}"
                raise RuntimeError(f"{self.spec['tool']} s'est arrêté ({why}) — {self.spec['name']} débranché ?")
            if time.time() - t0 > self.idle:
                raise TimeoutError(f"{self.spec['name']} muet depuis {self.idle:.0f} s")
            time.sleep(0.02)
        self.served[key] = passes
        F, L = snap
        x = np.linspace(start_hz, stop_hz, int(points))
        return x, resample_max(F, L, start_hz, stop_hz, int(points))

    def _stop(self):
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=3)
            except Exception:  # noqa: BLE001
                pass

    def close(self):
        self._stop()


# --------------------------------------------------------------------------
# Thread de balayage
# --------------------------------------------------------------------------
class ScanWorker(QtCore.QThread):
    sweep = Signal(int, object, object)            # id bande, freqs MHz, niveaux dBm
    partial = Signal(int, object, object, int, int)  # id bande, freqs, niveaux, segment, total
    cycle = Signal(float, int)                     # durée du cycle, nb de bandes
    status = Signal(str)
    info = Signal(str)
    error = Signal(str)
    link = Signal(bool)                            # liaison perdue (False) / retrouvée (True)
    devid = Signal(int)                            # numéro gravé dans le tinySA (« deviceid »), 0 = aucun

    RETRY_S = 5

    def __init__(self, port, demo, get_cfg, get_ver, label=""):
        super().__init__()
        self.port, self.demo = port, demo
        self.get_cfg, self.get_ver = get_cfg, get_ver
        self.label = label                         # « tinySA 2 » quand il y a plusieurs appareils
        self.retry_first = False                   # True : réessaie même si la toute 1re connexion échoue
        self.rng = np.random.default_rng()
        self.demo_carriers = {}
        self.seg_auto = 290
        self.ultra = False                         # tinySA Ultra (une seule prise, mode « ultra » > 800 MHz)
        self.baud = 115200
        self.trace = deque(maxlen=800)             # derniers échanges avec le tinySA (diagnostic)
        self.sdr = parse_sdr_addr(port) is not None    # V8 : HackRF / RTL-SDR par leur outil de balayage
        self.sdr_dir, self.sdr_tool = "", None          # dossier des outils ; sdr_tool : commande imposée (tests)
        self.get_sdr = lambda: {}                       # gains LNA / VGA / ampli
        self.paused = False                             # écoute en cours sur ce SDR : balayage suspendu
        self.st = dict(rbw="?", front="?", high=None)
        self.dev = None
        self.cmdq = queue.Queue()
        # statistiques (🩺 diagnostic) : où passe le temps, combien de balayages incomplets / reconnexions
        self.sweep_t = {}                         # id bande -> heure de la dernière mesure (time.time)
        self.stats = dict(segments=0, seg_s=0.0, seg_max=0.0, cycles=0, cycle_s=0.0, short=0, invalid=0,
                          reconnects=0, refused=0, settings_s=0.0, pts=0)
        self._warned = {}                          # message -> dernière fois affiché (pas de répétition chaque cycle)                  # commandes à glisser entre deux bandes (identifier, numéroter)
        self._stop_ev = threading.Event()          # 7.66.5 : arrêt demandé, lu sans appeler Qt (voir plus bas)

    # 7.66.5 (2ᵉ crash.log de Clément, 17/11/2026 : « access violation » dans ce fil, boucle d'attente de reconnexion,
    # pendant que l'interface jouait le son d'alarme APPAREIL ; même endroit que le 16/11) : le fil ne rappelle plus
    # l'objet Qt (isInterruptionRequested) des centaines de fois pendant l'attente : un simple drapeau Python.
    def requestInterruption(self):
        self._stop_ev.set()
        try:
            super().requestInterruption()
        except RuntimeError:                         # objet Qt déjà détruit
            pass

    def isInterruptionRequested(self):
        return self._stop_ev.is_set()

    def force_close(self):
        """Arrêt qui traîne (tinySA qui ne répond plus) : on ferme le port depuis l'extérieur."""
        d = self.dev
        if d is not None:
            d.close()

    def _say(self, txt):
        return f"{self.label} : {txt}" if self.label else txt

    def _warn(self, txt, every=60.0):
        """Avertissement dans la barre d'état, au plus une fois par minute pour le même message."""
        now = time.monotonic()
        if now - self._warned.get(txt, -1e9) >= every:
            self._warned[txt] = now
            self.status.emit(self._say(txt))
        self._tr("⚠ " + txt)

    def stats_text(self):
        s_ = self.stats
        avg = s_["seg_s"] / s_["segments"] if s_["segments"] else 0.0
        cyc = s_["cycle_s"] / s_["cycles"] if s_["cycles"] else 0.0
        spd = ""
        if s_.get("pts") and s_["seg_s"] > 0:
            spd = (f" · vitesse {s_['pts'] / s_['seg_s']:.0f} points/s "
                   f"({1000.0 * s_['seg_s'] / s_['pts']:.1f} ms par point)")
        return (f"segments {s_['segments']} (moy. {avg:.2f} s, max {s_['seg_max']:.2f} s) · cycles {s_['cycles']} "
                f"(moy. {cyc:.1f} s) · réglages {s_['settings_s']:.1f} s · incomplets {s_['short']} · invalides "
                f"{s_['invalid']} · refus {s_['refused']} · reconnexions {s_['reconnects']}" + spd
                + speed_table(s_.get("by")))

    def _tr(self, txt):
        self.trace.append(f"{datetime.now():%H:%M:%S.%f}"[:-3] + " " + txt)

    def run(self):
        """Balaye en boucle. Liaison perdue (câble, réseau) : signal link(False), nouvel essai toutes les
        RETRY_S secondes, link(True) au retour. Échec de la toute 1re connexion : error (sauf retry_first)."""
        was_up, lost, fails = False, False, 0
        while not self.isInterruptionRequested():
            dev = None
            try:
                if not self.demo and self.sdr:
                    self._tr(f"SDR {self.port}")
                    while self.paused and not self.isInterruptionRequested():
                        self.msleep(100)                    # écoute en cours : le SDR est à l'écoute
                    if self.isInterruptionRequested():
                        return
                    dev = open_spectrum_device(self.port, self)
                    dev.abort = lambda: self.isInterruptionRequested() or self.paused
                    self.dev = dev
                    self.info.emit(dev.version())
                    self.status.emit(self._say(f"{dev.spec['name']} prêt ({dev.spec.get('tool') or dev.spec.get('dll')})"))
                elif not self.demo:
                    self._tr(f"connexion à {self.port} ({self.baud} bauds)")
                    dev = TinySA(self.port, self.baud, self._tr)
                    dev.abort = self.isInterruptionRequested
                    self.dev = dev
                    ver = dev.version()
                    self.ultra = "tinysa4" in ver.lower()
                    if self.ultra:
                        self.seg_auto = 450
                    self.info.emit(ver or "tinySA")
                    try:
                        n_ = parse_deviceid(dev.cmd("deviceid", timeout=3))
                        if n_ is not None:
                            self.devid.emit(n_)
                    except Exception:  # noqa: BLE001 — vieux firmware : pas de numéro
                        pass
                    self.status.emit(self._say(f"Connecté sur {self.port}"))
                else:
                    self.info.emit("Mode démo")
                    self.status.emit(self._say("Mode démo (signaux simulés)"))
                self.st = dict(rbw="?", front="?", high=None)
                was_up, fails = True, 0
                if lost:
                    lost = False
                    self.link.emit(True)
                self._loop(dev)
                return
            except Exception as e:  # noqa: BLE001
                if self.isInterruptionRequested():
                    return                                  # Arrêter : pas une panne
                if self.paused and isinstance(e, Aborted):
                    self._tr("balayage en pause (écoute)")
                    self.status.emit(self._say("🎧 écoute en cours : balayage du SDR en pause"))
                    continue                                # le SDR est libéré (finally) pour l'écoute
                if not was_up and not self.retry_first:
                    self.error.emit(self._say(str(e)))
                    return
                if not lost:
                    lost = True
                    self.link.emit(False)
                fails += 1
                self.stats["reconnects"] += 1
                self._tr(f"liaison perdue : {e}")
                hint = (" · le tinySA semble figé : débranche / rebranche son USB (ou éteins-le / rallume-le)"
                        if fails >= 3 else "")
                self.status.emit(self._say(f"⚠ liaison perdue ({e}) — nouvel essai dans {self.RETRY_S} s{hint}"))
                for _ in range(self.RETRY_S * 10):
                    if self.isInterruptionRequested():
                        return
                    self.msleep(100)
            finally:
                self.dev = None
                if dev is not None:
                    dev.close()

    def _loop(self, dev):
        while not self.isInterruptionRequested():
            cfg = self.get_cfg()
            bands = [b for b in cfg["bands"] if b["enabled"]]
            if not bands:
                if not self.label:
                    self.status.emit("Aucune bande active")
                self.msleep(300)
                continue
            if dev is not None:
                t_s = time.monotonic()
                self._apply_settings(dev, cfg)
                if hasattr(dev, "configure"):
                    dev.configure(bands, cfg["rbw"], self.get_sdr())
                self.stats["settings_s"] += time.monotonic() - t_s
                self._tr("cycle : " + ", ".join(f"{b['name']} {b['start_hz'] / 1e6:g}–{b['stop_hz'] / 1e6:g} MHz "
                                                f"{int(b['n'])} pts" for b in bands)
                         + f" · RBW {cfg['rbw'] or 'auto'} · entrée {cfg['input']}")
            t0, aborted = time.monotonic(), False
            for b in bands:
                self._run_cmds(dev)
                res = self._scan_band(dev, b, cfg)
                if res is None:
                    aborted = True
                    break
                if len(res[0]):
                    self.sweep_t[b["id"]] = time.time()   # heure de la MESURE (pas de son traitement par l'interface)
                    self.sweep.emit(b["id"], res[0], res[1])
            if not aborted and not self.isInterruptionRequested():
                dt = time.monotonic() - t0
                self.stats["cycles"] += 1
                self.stats["cycle_s"] += dt
                self.cycle.emit(dt, len(bands))

    def _run_cmds(self, dev):
        """👋 identifier (le fond de l'écran clignote en orange, puis ses couleurs reviennent) / 🔢 numéroter."""
        while True:
            try:
                c = self.cmdq.get_nowait()
            except queue.Empty:
                return
            if c[0] == "identify":
                if dev is None:
                    self.status.emit(self._say("👋 (démo) l'écran de ce tinySA clignoterait en orange"))
                    continue
                try:
                    orig = palette_color(dev.cmd("color", timeout=3), 0)
                    for _ in range(4):
                        dev.try_cmd(f"color 0 {0xFF9F1C}")
                        self.msleep(450)
                        dev.try_cmd(f"color 0 {orig if orig is not None else 0}")
                        self.msleep(350)
                    self.status.emit(self._say("👋 Écran du tinySA : clignotement orange terminé"))
                except Exception as e:  # noqa: BLE001
                    self.status.emit(self._say(f"👋 Identification impossible : {e}"))
            elif c[0] == "setid":
                n_ = int(c[1])
                if dev is not None:
                    dev.try_cmd(f"deviceid {n_}")
                    dev.try_cmd("saveconfig")
                self.devid.emit(n_)

    def _apply_settings(self, dev, cfg):
        """Un réglage n'est retenu comme appliqué QUE si le tinySA l'a accepté (revue de code 7.41 : un refus était
        mémorisé comme fait, jamais retenté, et l'appli croyait le tinySA réglé autrement qu'il ne l'était)."""
        if cfg["rbw"] != self.st["rbw"]:
            ok, msg = dev.set_rbw(cfg["rbw"])
            self.st["rbw"] = cfg["rbw"] if ok else "?"
            if not ok:
                self.stats["refused"] += 1
                self._warn(f"⚠ Réglage refusé par le tinySA — {msg} : le réglage précédent reste actif, nouvel essai "
                           f"au prochain balayage")
        front = (cfg["lna"], cfg["att"])
        if front != self.st["front"]:
            self.st["front"] = front if self._apply_front(dev, cfg) else "?"

    def _apply_front(self, dev, cfg):
        """LNA + atténuateur (mutuellement exclusifs sur le tinySA)."""
        fails = []
        if cfg["lna"] is True:
            ok, m = dev.try_cmd("lna on")
            if not ok:
                fails.append(m)
        else:
            if cfg["lna"] is False:
                ok, m = dev.try_cmd("lna off")
                if not ok:
                    fails.append(m)
            ok, m = dev.try_cmd("attenuate auto" if cfg["att"] == "auto" else f"attenuate {cfg['att']}")
            if not ok:
                fails.append(m)
        if fails:
            self.stats["refused"] += 1
            self._warn(f"⚠ Réglage refusé par le tinySA — {' ; '.join(fails)} : le réglage précédent reste actif, "
                       f"nouvel essai au prochain balayage")
        return not fails

    def _scan_band(self, dev, b, cfg):
        """Balaye une bande en segments. Renvoie None si la config a changé / arrêt demandé."""
        n = max(2, int(b["n"]))
        grid = np.linspace(b["start_hz"], b["stop_hz"], n)
        step = (b["stop_hz"] - b["start_hz"]) / (n - 1)
        seg = 10 ** 7 if self.sdr else (cfg["seg"] or self.seg_auto)     # SDR : une bande d'un coup
        plan = segment_plan(n, seg)
        fo, lo = [], []
        for k, (i0, i1) in enumerate(plan):
            if self.isInterruptionRequested() or self.get_ver() != cfg["ver"]:
                return None
            a, z = grid[i0], grid[i1 - 1]
            pts = i1 - i0
            if z <= a:
                z = a + step
            if pts < MIN_PTS:
                pts = MIN_PTS
            if dev is not None:
                want = input_plan(self.ultra, cfg["input"], a)
                if want is not None and (want == "high") != self.st["high"]:
                    high = want == "high"
                    ok, msg = dev.set_input(high)
                    self.st["high"] = high if ok else None     # refusé : on réessaiera au prochain segment
                    if not ok:
                        self.stats["refused"] += 1
                        self._warn(f"⚠ Changement d'entrée refusé — {msg} : l'entrée précédente reste active, nouvel "
                                   f"essai au prochain segment")
                    else:
                        self.st["front"] = (cfg["lna"], cfg["att"]) if self._apply_front(dev, cfg) else "?"
                if self.ultra and a >= 800e6 and not self.st.get("ultra"):
                    ok, _m = dev.try_cmd("ultra on")       # au-delà de 800 MHz (sans effet si déjà actif)
                    self.st["ultra"] = ok
                dev.expect_scan(pts, cfg["rbw"], (z - a) / max(1, pts - 1) / 1e3)
                t_seg = time.monotonic()
                fr, lv = dev.scan(a, z, pts)
                dt = time.monotonic() - t_seg
                self.stats["segments"] += 1
                self.stats["seg_s"] += dt
                self.stats["pts"] += int(pts)              # 7.56 : vitesse réelle du tinySA (points / s) au 🩺
                kb = (cfg["rbw"] or 0, int(round((z - a) / max(1, pts - 1) / 1e3)), bool(cfg["lna"] is True))
                sp = self.stats.setdefault("by", {}).setdefault(kb, [0, 0.0])   # 7.57.1 : vitesse par réglage
                sp[0] += int(pts)
                sp[1] += dt
                self.stats["seg_max"] = max(self.stats["seg_max"], dt)
                fr, state, note = scan_check(fr, lv, a, z, pts)
                if state == "invalide":
                    self.stats["invalid"] += 1
                    raise RuntimeError(f"balayage inutilisable ({note})")      # → reconnexion, nouvel essai
                if state == "court":
                    self.stats["short"] += 1
                    self._warn(f"⚠ Balayage incomplet du tinySA ({note}) : résolution réduite sur {b['name']}")
            else:
                fr = np.linspace(a, z, pts)
                lv = self._demo_levels(fr, b, cfg)
                self.msleep(30 + pts // 10)
            fo.append(fr / 1e6)
            lo.append(lv + cfg["offset"])
            if len(plan) > 1 and k < len(plan) - 1:
                self.partial.emit(b["id"], np.concatenate(fo), np.concatenate(lo), k + 1, len(plan))
        if not fo:
            return np.array([]), np.array([])
        return np.concatenate(fo), np.concatenate(lo)

    def _demo_levels(self, fr, b, cfg):
        lv = -98 + self.rng.normal(0, 1.2, len(fr))
        if cfg.get("demo_plan") is not None:             # 8.0.3 : même plan que le SDR démo (toute ta liste)
            key = ("bg", b["id"], round(b["start_hz"] / 1e5), round(b["stop_hz"] / 1e5))
            if len(self.demo_carriers) > 40:
                self.demo_carriers.clear()
            bg = self.demo_carriers.setdefault(          # quelques signaux inconnus en plus
                key, [(self.rng.uniform(b["start_hz"], b["stop_hz"]), self.rng.uniform(-78, -60),
                       self.rng.uniform(0.3, 1.2), self.rng.uniform(0, 6)) for _ in range(3)])
            t = time.time()
            for pos, amp, w, ph in bg:
                if fr[0] - 2e5 <= pos <= fr[-1] + 2e5 and np.sin(t * w + ph) > -0.2:
                    lv = np.maximum(lv, amp - 12 * ((fr - pos) / 100e3) ** 2 + self.rng.normal(0, 0.8, len(fr)))
            pl = demo_plan_levels(fr / 1e6, cfg["demo_plan"], t, self.rng)
            return np.fmax(lv, pl)
        key = (b["id"], round(b["start_hz"] / 1e5), round(b["stop_hz"] / 1e5))
        if len(self.demo_carriers) > 40:
            self.demo_carriers.clear()
        rnd = self.demo_carriers.setdefault(
            key, [(self.rng.uniform(b["start_hz"], b["stop_hz"]),
                   self.rng.uniform(-70, -40), self.rng.uniform(0.3, 1.2),
                   self.rng.uniform(0, 6)) for _ in range(5)])
        car = list(rnd)
        for k, f in enumerate(cfg["demo_freqs"]):
            if k % 4 == 0:
                car.append((f * 1e6, -62 - (k % 5) * 4, 0.4 + (k % 3) * 0.3, k))
        for fc, bw in cfg.get("demo_blocks", ()):        # porteur large Spectera / WMAS : plateau
            m = (fr >= (fc - bw / 2) * 1e6) & (fr <= (fc + bw / 2) * 1e6)
            if m.any():
                lv[m] = np.maximum(lv[m], -68 + self.rng.normal(0, 1.5, int(m.sum())))
        t = time.time()
        for pos, amp, w, ph in car:
            if fr[0] - 2e5 <= pos <= fr[-1] + 2e5 and np.sin(t * w + ph) > -0.2:
                d = (fr - pos) / 100e3
                lv = np.maximum(lv, amp - 12 * d ** 2 + self.rng.normal(0, 0.8, len(fr)))
        return lv


# --------------------------------------------------------------------------
# Relais réseau : partage un tinySA branché en USB sur un autre PC
# --------------------------------------------------------------------------
def local_ips():
    """Adresses IPv4 de ce PC sur le réseau local (pour les afficher à l'utilisateur)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))          # aucun paquet envoyé : sert juste à choisir l'interface
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


class SerialRelay(threading.Thread):
    """Relaie les octets entre un port série (le tinySA) et UN client TCP (RF Technical Monitor sur l'autre PC).
    Un nouveau client remplace l'ancien (reconnexion après une coupure réseau). Port USB débranché :
    réouverture automatique toutes les 2 s."""

    def __init__(self, port, tcp_port=RELAY_PORT, host="0.0.0.0", opener=None, allow=None):
        super().__init__(daemon=True)
        self.port, self.tcp_port, self.host = port, int(tcp_port), host
        self.allow = [a for a in (allow or []) if a] or None   # adresses IP autorisées (None = toutes), comme le Pi
        self.refused = ""                         # dernière adresse refusée (affichée dans la fenêtre)
        self.opener = opener or (lambda p: serial.serial_for_url(p, 115200, timeout=0.05, write_timeout=2.0))
        self.stop_evt, self.ready = threading.Event(), threading.Event()
        self.client, self.error, self.serial_ok = None, "", False
        self.rx = self.tx = 0                     # octets tinySA → réseau / réseau → tinySA

    def stop(self):
        self.stop_evt.set()

    def _open_serial(self):
        try:
            ser = self.opener(self.port)
            self.serial_ok, self.error = True, ""
            return ser
        except Exception as e:  # noqa: BLE001
            self.serial_ok, self.error = False, f"Port {self.port} : {e}"
            return None

    def run(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if os.name != "nt":      # sous Windows, SO_REUSEADDR laisserait deux programmes prendre le même port
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.tcp_port))
            srv.listen(2)
            self.tcp_port = srv.getsockname()[1]
        except OSError as e:
            self.error = f"Port réseau {self.tcp_port} indisponible : {e}"
            self.ready.set()
            return
        ser, conn = self._open_serial(), None
        self.ready.set()
        try:
            while not self.stop_evt.is_set():
                if ser is None:
                    if self.stop_evt.wait(2.0):
                        break
                    ser = self._open_serial()
                    continue
                socks = [srv] + ([conn] if conn is not None else [])
                rd, _, _ = select.select(socks, [], [], 0.01)
                if srv in rd:                      # nouveau client : il remplace l'ancien
                    new, addr = srv.accept()
                    if self.allow and addr[0] not in self.allow:
                        self.refused = addr[0]
                        new.close()
                        continue
                    new.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    new.settimeout(5.0)    # client qui ne lit plus : envoi abandonné au bout de 5 s, client lâché
                    if conn is not None:
                        conn.close()
                    conn, self.client = new, addr[0]
                    try:
                        ser.reset_input_buffer()
                    except Exception:  # noqa: BLE001
                        pass
                try:
                    if conn is not None and conn in rd:
                        data = conn.recv(4096)
                        if not data:
                            conn.close()
                            conn, self.client = None, None
                        else:
                            ser.write(data)
                            self.tx += len(data)
                    n = ser.in_waiting
                    if n:
                        data = ser.read(n)
                        if conn is not None:
                            conn.sendall(data)
                            self.rx += len(data)
                except (OSError, socket.error) as e:
                    if conn is not None and isinstance(e, (ConnectionError, socket.timeout)):
                        conn.close()
                        conn, self.client = None, None
                    else:                          # erreur côté USB : on rouvre le port
                        self.serial_ok, self.error = False, f"Port {self.port} : {e}"
                        try:
                            ser.close()
                        except Exception:  # noqa: BLE001
                            pass
                        ser = None
                except Exception as e:  # noqa: BLE001   (serial.SerialException)
                    self.serial_ok, self.error = False, f"Port {self.port} : {e}"
                    try:
                        ser.close()
                    except Exception:  # noqa: BLE001
                        pass
                    ser = None
        finally:
            for x in (conn, srv, ser):
                try:
                    if x is not None:
                        x.close()
                except Exception:  # noqa: BLE001
                    pass
            self.client = None
