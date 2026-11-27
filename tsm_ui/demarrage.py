# Démarrage : journal des plantages, langue, garde, auto-test, main().
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


def _html_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


C_NAME, C_FREQ, C_LVL, C_MAX, C_THR, C_SIG, C_STAT, C_OCC, C_LAYER, C_BAND = range(10)
WATCH_HEADERS = ["Nom", "MHz", "Niveau", "Max", "Seuil", "Signal", "Statut", "Occ.", "Scène › Groupe",
                 "Spectre"]
C_MARG = 10                                     # 7.44 : marge au-dessus du bruit (colonne ajoutée en dernier)
WATCH_HEADERS.append("Marge")
WATCH_COLS_V = 2                                # ordre des colonnes mémorisé : ignoré s'il date d'avant la colonne Marge
SIG_TEXT = {None: "—", "free": "libre", "weak": "faible", "occ": "OCCUPÉ"}
CONFLICT_TEXT = "⚠ CONFLIT"
ABSENT_TEXT = "⚠ ABSENT"


def log_crash(kind, text, path=None):
    """Ajoute une erreur inattendue à crash.log (horodatée, avec la version). -> chemin du fichier."""
    path = Path(path or CRASH_PATH)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} · {APP_NAME} {APP_VER} · {kind}\n{text}\n")
    except OSError:
        pass
    return path


def install_crash_log(app=None):
    """L'exe n'a pas de console : toute erreur imprévue part dans crash.log, avec un message (au plus 1 / min).
    Plantage dur (segfault) : faulthandler écrit aussi dans crash.log."""
    state = {"last": 0.0}

    def hook(t, v, tb):
        if issubclass(t, KeyboardInterrupt):
            return
        path = log_crash("erreur", "".join(traceback.format_exception(t, v, tb)))
        if app is not None and time.time() - state["last"] > 60:
            state["last"] = time.time()
            try:
                QtWidgets.QMessageBox.warning(
                    None, APP_NAME, f"Erreur inattendue : {t.__name__}: {v}\n\nLe logiciel continue. Le détail est dans :\n"
                                    f"{path}\n(envoie ce fichier pour qu'on corrige).")
            except Exception:  # noqa: BLE001
                pass

    def thook(args):
        log_crash(f"erreur dans un fil ({getattr(args.thread, 'name', '?')})",
                  "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

    sys.excepthook = hook
    threading.excepthook = thook
    try:
        CRASH_PATH.parent.mkdir(parents=True, exist_ok=True)
        fh = open(CRASH_PATH, "a", encoding="utf-8")
        faulthandler.enable(fh)
        return fh                                  # à garder ouvert
    except OSError:
        return None


def _tr_args(tr, args, kw, which="first", lists=(), kws=()):
    """Traduit des arguments : which = "first" (1re chaîne seulement : le texte, pas la donnée associée),
    "all" (toutes les chaînes), ou une liste d'indices."""
    a = list(args)
    if which == "first":
        for i, x in enumerate(a):
            if isinstance(x, str):
                a[i] = tr(x)
                break
    else:
        for i, x in enumerate(a):
            if isinstance(x, str) and (which == "all" or i in which):
                a[i] = tr(x)
    for i in lists:
        if i < len(a) and isinstance(a[i], (list, tuple)):
            a[i] = [tr(x) if isinstance(x, str) else x for x in a[i]]
    for k in kws:
        if isinstance(kw.get(k), str):
            kw[k] = tr(kw[k])
    return a, kw


def _patch(cls, name, which="first", lists=(), kws=(), static=False):
    orig = getattr(cls, name, None)
    if orig is None or getattr(orig, "_tsm_tr", False):
        return
    tr = TR
    if static:
        def f(*args, **kw):
            a, kw = _tr_args(tr, args, kw, which, lists, kws)
            return orig(*a, **kw)
        f._tsm_tr = True
        setattr(cls, name, staticmethod(f))
    else:
        def f(self, *args, **kw):
            a, kw = _tr_args(tr, args, kw, which, lists, kws)
            return orig(self, *a, **kw)
        f._tsm_tr = True
        setattr(cls, name, f)


def install_plain_buttons():
    """Boutons sans emoji de tête (look « pro » 7.54) : posé sur QAbstractButton.setText et les constructeurs de
    QPushButton / QToolButton, AVANT install_language (la traduction s'applique au texte complet, puis on retire
    l'emoji). Les menus et listes gardent leurs emojis."""
    W = QtWidgets
    o_set = W.QAbstractButton.setText
    if getattr(o_set, "_tsm_plain", False):
        return

    def set_text(self, t, _o=o_set):
        return _o(self, plain_btn_text(t))
    set_text._tsm_plain = True
    W.QAbstractButton.setText = set_text
    for cls in (W.QPushButton, W.QToolButton):
        o_init = cls.__init__

        def init(self, *a, _o=o_init, **kw):
            _o(self, *a, **kw)
            t = W.QAbstractButton.text(self)
            if t:
                o_set(self, plain_btn_text(t))
        cls.__init__ = init


install_plain_buttons()


def _load_lang_en():
    """-> (exact, modèles, morceaux de page web, vocabulaire) anglais (lang_en + lang_en_v8), ou None."""
    here = str(Path(__file__).resolve().parent)          # à côté du programme, d'où qu'on le lance
    if here not in sys.path:
        sys.path.append(here)
    try:
        import lang_en                                    # fichier de traductions à côté du programme / dans l'exe
    except ImportError:
        return None
    exact, tpl = dict(lang_en.EXACT), dict(lang_en.TEMPLATES)
    try:
        import lang_en_v8                                 # textes propres à la V8 (SDR), dans leur propre fichier
        exact.update(lang_en_v8.EXACT)
        tpl.update(lang_en_v8.TEMPLATES)
        if not getattr(lang_en, "_v8_web", False):        # morceaux de la page web propres à la V8 (vue 🎧 Écoute)
            lang_en.WEB = list(lang_en.WEB) + list(getattr(lang_en_v8, "WEB", []))
            lang_en._v8_web = True
    except ImportError:
        pass
    return exact, tpl, lang_en.WEB, lang_en.VOCAB


_EN_TR = []


def en_translator():
    """Traducteur anglais, même si l'appli est en français (page web / alertes au choix de chacun)."""
    if not _EN_TR:
        if TR:
            _EN_TR.append(TR)
        else:
            d = _load_lang_en()
            _EN_TR.append(Translator(d[0], d[1]) if d else Translator())
    return _EN_TR[0]


_WEB_PAGES = {}


WEB_EXTRA_JS = ""        # 7.68 : JavaScript ajouté par une autre version (V8 : vues EXT) ; vide en V7


def web_page_full():
    """WEB_PAGE + vues et JavaScript ajoutés par une autre version (WEB_VIEWS complétée, WEB_EXTRA_JS)."""
    base = set(_WEB_BASE_VIEWS)
    xv = "{" + ",".join(f'"{k}":["{i}","{t}","{d}"]' for k, i, t, d in WEB_VIEWS if k not in base) + "}"
    return WEB_PAGE.replace("/*__VIEWS_X__*/{}", xv).replace("/*__EXTRA_JS__*/", WEB_EXTRA_JS)


def web_page_bytes(lang):
    """Page web de l'équipe dans la langue de la personne (« fr » : la page d'origine)."""
    if lang not in _WEB_PAGES:
        d = _load_lang_en() if lang == "en" else None
        page = web_page_lang(web_page_full(), d[2], en_translator())[0] if d else web_page_full()
        _WEB_PAGES[lang] = page.encode("utf-8")
    return _WEB_PAGES[lang]


def install_language(code):
    """Langue de l'interface. « fr » : rien à faire (le programme est écrit en français). « en » : charge
    lang_en.py et fait passer tout texte donné à Qt par TR (constructeurs et setters des widgets, menus, tableaux,
    boîtes de message, sélecteurs de fichiers, axes pyqtgraph). À appeler AVANT de construire les fenêtres.
    -> True si la langue est active."""
    if code != "en":
        return False
    d = _load_lang_en()
    if d is None:
        return False
    exact, tpl, _web, vocab = d
    TR.__init__(exact, tpl)
    for lst in (NAME_WORDS, SCENE_WORDS, GROUP_WORDS):    # mots proposés pour les noms : en anglais
        lst[:] = list(dict.fromkeys(vocab.get(w, w) for w in lst))
    W = QtWidgets
    for cls in (W.QLabel, W.QPushButton, W.QCheckBox, W.QRadioButton, W.QToolButton, W.QGroupBox, W.QDockWidget,
                W.QMenu, W.QListWidgetItem, W.QTableWidgetItem, QtGui.QAction, W.QCommandLinkButton, W.QToolBar):
        _patch(cls, "__init__")
    _patch(W.QTreeWidgetItem, "__init__", which=(), lists=(0, 1))
    for cls, names in ((W.QAbstractButton, ("setText",)), (W.QLabel, ("setText",)), (W.QGroupBox, ("setTitle",)),
                       (W.QWidget, ("setToolTip", "setStatusTip", "setWhatsThis", "setWindowTitle")),
                       (W.QMenu, ("setTitle", "addAction", "addMenu", "addSection")),
                       (W.QToolBar, ("addAction",)),
                       (QtGui.QAction, ("setText", "setToolTip", "setStatusTip", "setIconText")),
                       (W.QComboBox, ("setPlaceholderText",)),
                       (W.QLineEdit, ("setPlaceholderText",)), (W.QTextEdit, ("setPlaceholderText",)),
                       (W.QPlainTextEdit, ("setPlaceholderText",)),
                       (W.QAbstractSpinBox, ("setSpecialValueText",)),
                       (W.QSpinBox, ("setSuffix", "setPrefix")), (W.QDoubleSpinBox, ("setSuffix", "setPrefix")),
                       (W.QTabWidget, ("addTab", "insertTab", "setTabText", "setTabToolTip")),
                       (W.QTabBar, ("setTabText", "setTabToolTip")),
                       (W.QTableWidgetItem, ("setText", "setToolTip", "setStatusTip")),
                       (W.QListWidgetItem, ("setText", "setToolTip", "setStatusTip")),
                       (W.QTreeWidgetItem, ("setText", "setToolTip", "setStatusTip")),
                       (W.QListWidget, ("addItem",)), (W.QFormLayout, ("addRow", "insertRow")),
                       (W.QStatusBar, ("showMessage",)),
                       (W.QMessageBox, ("setText", "setInformativeText", "setDetailedText", "addButton")),
                       (W.QDialogButtonBox, ("addButton",)),
                       (W.QProgressDialog, ("setLabelText", "setCancelButtonText"))):
        for n in names:
            _patch(cls, n)
    for n, lists in (("addItem", ()), ("insertItem", ()), ("setItemText", ()), ("addItems", (0,))):
        orig_c = getattr(W.QComboBox, n)                  # liste modifiable (noms de scène, de groupe…) : on n'y
        if getattr(orig_c, "_tsm_tr", False):              # touche pas, son texte est relu par le programme
            continue

        def combo(self, *args, _o=orig_c, _l=lists, **kw):
            if not self.isEditable():
                args, kw = _tr_args(TR, args, kw, () if _l else "first", _l)
            return _o(self, *args, **kw)
        combo._tsm_tr = True
        setattr(W.QComboBox, n, combo)
    _patch(W.QListWidget, "addItems", which=(), lists=(0,))
    for cls in (W.QTableWidget,):
        _patch(cls, "setHorizontalHeaderLabels", which=(), lists=(0,))
        _patch(cls, "setVerticalHeaderLabels", which=(), lists=(0,))
    _patch(W.QTreeWidget, "setHeaderLabels", which=(), lists=(0,))
    _patch(W.QTreeWidget, "setHeaderLabel")
    orig_data = W.QComboBox.setItemData                   # bulle d'un choix de liste (rôle ToolTip) seulement
    if not getattr(orig_data, "_tsm_tr", False):
        def set_item_data(self, i, value, role=Qt.ItemDataRole.UserRole):
            if role == Qt.ItemDataRole.ToolTipRole and isinstance(value, str):
                value = TR(value)
            return orig_data(self, i, value, role)
        set_item_data._tsm_tr = True
        W.QComboBox.setItemData = set_item_data
    orig_html = W.QTextEdit.setHtml
    if not getattr(orig_html, "_tsm_tr", False):
        def set_html(self, h):
            return orig_html(self, TR.html(h))
        set_html._tsm_tr = True
        W.QTextEdit.setHtml = set_html
    _patch(W.QMessageBox, "__init__", which="all")
    for n in ("information", "warning", "critical", "question", "about"):
        _patch(W.QMessageBox, n, which=(1, 2), static=True)
    for n in ("getText", "getMultiLineText", "getInt", "getDouble"):
        _patch(W.QInputDialog, n, which=(1, 2), static=True)
    orig_item = W.QInputDialog.getItem
    if not getattr(orig_item, "_tsm_tr", False):
        def get_item(parent, title, label, items, *a, **kw):
            items = list(items)
            shown = [TR(x) for x in items]
            res, ok = orig_item(parent, TR(title), TR(label), shown, *a, **kw)
            return (items[shown.index(res)] if res in shown else res), ok    # on rend le texte d'origine
        get_item._tsm_tr = True
        W.QInputDialog.getItem = staticmethod(get_item)
    for n in ("getOpenFileName", "getOpenFileNames", "getSaveFileName"):
        _patch(W.QFileDialog, n, which=(1, 3), kws=("caption", "filter"), static=True)
    _patch(W.QFileDialog, "getExistingDirectory", which=(1,), kws=("caption",), static=True)
    _patch(W.QColorDialog, "getColor", which=(2,), kws=("title",), static=True)
    _patch(pg.PlotItem, "setLabel", which=(1,), kws=("text",))
    _patch(pg.PlotItem, "setTitle")
    _patch(pg.LabelItem, "setText")
    return True


def restart_app():
    """Relance l'appli dans un NOUVEAU processus indépendant. Exe PyInstaller « un seul fichier » : sans précaution,
    le nouveau processus hérite des variables d'environnement de l'ancien et réutilise son dossier temporaire
    (_MEI…), que l'ancien efface en se fermant → « No module named numpy._core._multiarray_umath » (bug 7.11.0
    vu par Clément). PYINSTALLER_RESET_ENVIRONMENT=1 (PyInstaller ≥ 6.9) + variables _PYI_* / _MEIPASS2 retirées
    = il repart de zéro avec son propre dossier. -> True si le processus a démarré."""
    frozen = getattr(sys, "frozen", False)
    args = sys.argv[1:] if frozen else [str(Path(__file__).resolve())] + sys.argv[1:]
    env = QtCore.QProcessEnvironment.systemEnvironment()
    for k in list(env.keys()):
        if k.startswith("_PYI_") or k in ("_MEIPASS2", "_MEIPASS"):
            env.remove(k)
    env.insert("PYINSTALLER_RESET_ENVIRONMENT", "1")
    env.insert("TSM_WAIT_INSTANCE", "1")              # 8.0.3 : attend que l'ancienne fenêtre soit fermée
    pr = QtCore.QProcess()
    pr.setProgram(sys.executable)
    pr.setArguments(args)
    pr.setProcessEnvironment(env)
    pr.setWorkingDirectory(str(Path(sys.executable).parent if frozen else Path.cwd()))
    ok = pr.startDetached()
    return bool(ok[0] if isinstance(ok, tuple) else ok)


GUARD_LOG = CFG_PATH.parent / "garde.log"


def _guard_env(beat, restarted):
    """Environnement de l'appli lancée par la garde (exe PyInstaller : dossier _MEI… à elle, cf. restart_app)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI_") and k not in ("_MEIPASS2", "_MEIPASS")}
    env.update(PYINSTALLER_RESET_ENVIRONMENT="1", TSM_HEARTBEAT=str(beat), TSM_GUARD_RESTART="1" if restarted else "0",
               TSM_WAIT_INSTANCE="1")
    return env


def _beat_pid(beat):
    """N° de processus de l'appli écrit dans le battement (7.60.2), ou None."""
    try:
        parts = Path(beat).read_text(encoding="utf-8").split()
        return int(parts[1]) if len(parts) > 1 else None
    except (OSError, ValueError):
        return None


def _pid_alive(pid):
    """Le processus pid tourne-t-il encore ?"""
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000 | 0x00100000, False, int(pid))   # QUERY_LIMITED_INFORMATION | SYNCHRONIZE
            if not h:
                return False
            try:
                return k.WaitForSingleObject(h, 0) == 0x102           # WAIT_TIMEOUT = encore vivant
            finally:
                k.CloseHandle(h)
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _kill_pid(pid):
    try:
        if os.name == "nt":
            subprocess.run("taskkill /F /T /PID".split() + [str(pid)], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            import signal
            os.kill(int(pid), signal.SIGKILL)
    except Exception:  # noqa: BLE001
        pass


def _kill_tree(pr):
    """Ferme de force l'appli ET ses processus enfants. L'exe PyInstaller « un seul fichier » = un lanceur + l'appli
    Python dans un 2ᵉ processus : tuer le seul lanceur laissait l'appli figée vivante (port COM gardé, puis 2 appli
    après le dégel ; vu par Clément en 7.52 : « COM4 accès refusé » après la relance)."""
    try:
        if os.name == "nt":
            subprocess.run("taskkill /F /T /PID".split() + [str(pr.pid)], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:  # noqa: BLE001
        pass
    try:
        pr.kill()
    except Exception:  # noqa: BLE001
        pass
    try:
        pr.wait(15)
    except Exception:  # noqa: BLE001
        pass


def run_guard(cmd=None, beat=None, log=None, hang_s=GUARD_HANG_S, grace_s=GUARD_GRACE_S, poll_s=2.0,
              max_runs=None, stop=None):
    """RF-Technical-Monitor.exe --garde : petit processus SANS fenêtre qui lance l'appli et la surveille. Elle plante
    (code ≠ 0) -> relancée ; elle ne bat plus depuis `hang_s` (figée) -> fermée de force puis relancée ; fermée
    exprès (code 0) -> la garde s'arrête aussi. Relancée, l'appli reprend la surveillance si elle tournait.
    -> nombre de relances."""
    import subprocess
    frozen = getattr(sys, "frozen", False)
    if cmd is None:
        args = [a for a in sys.argv[1:] if a != "--garde"]
        cmd = [sys.executable] + ([] if frozen else [str(Path(__file__).resolve())]) + args
    beat = Path(beat or (CFG_PATH.parent / "battement.txt"))
    log = Path(log or GUARD_LOG)

    def note(msg):
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
        except OSError:
            pass

    starts, runs, restarts = [], 0, 0
    note(f"garde démarrée ({APP_NAME} {APP_VER})")
    while True:
        try:
            beat.unlink()
        except OSError:
            pass
        t0 = time.time()
        starts.append(t0)
        runs += 1
        try:
            pr = subprocess.Popen(cmd, env=_guard_env(beat, runs > 1),
                                  cwd=str(Path(sys.executable).parent if frozen else Path.cwd()))
        except OSError as e:
            note(f"lancement impossible : {e}")
            return restarts
        last_loop, ref = time.time(), t0
        why = ""
        while True:
            if stop is not None and stop.is_set():
                _kill_tree(pr)
                note("garde arrêtée")
                return restarts
            time.sleep(poll_s)
            now = time.time()
            if now - last_loop > max(30.0, 10 * poll_s):     # le PC dormait : on ne compte pas ce temps
                ref = now
            last_loop = now
            try:
                hb = max(beat.stat().st_mtime, ref)
                age = now - hb
            except OSError:
                age = None if ref == t0 else now - ref
            act = guard_action(pr.poll(), age, now - t0, hang_s, grace_s)
            if act == "wait":
                continue
            if act == "stop":
                note("appli fermée normalement : fin de la garde")
                return restarts
            if act == "kill":
                why = f"figée (plus de signe de vie depuis {int(age if age is not None else now - t0)} s) : fermée de force"
                app_pid = _beat_pid(beat)
                _kill_tree(pr)
                # 7.60.2 (Clément : « l'autre s'est pas arrêtée, le tiny est bloqué ») : on vise AUSSI l'appli par son
                # propre n° (écrit dans le battement) et on attend qu'elle soit vraiment fermée avant de relancer —
                # sinon la nouvelle n'a pas le port COM.
                for _try in range(6):
                    if not _pid_alive(app_pid):
                        break
                    _kill_pid(app_pid)
                    time.sleep(2.0)
                if _pid_alive(app_pid):
                    note(f"⚠ l'appli figée (processus {app_pid}) ne se ferme pas : le port du tinySA peut rester pris")
                elif app_pid:
                    note(f"appli figée (processus {app_pid}) bien fermée")
            else:
                why = f"arrêtée avec le code {pr.returncode} (plantage)"
            break
        restarts += 1
        if max_runs is not None and runs >= max_runs:
            note(f"appli {why} ; nombre maximal de lancements atteint")
            return restarts
        wait_s = guard_delay(starts, time.time())
        note(f"appli {why} ; relance dans {int(wait_s)} s")
        log_crash("garde", f"L'appli s'est {why}. Relancée automatiquement par la garde.")
        end = time.time() + wait_s
        while time.time() < end:
            if stop is not None and stop.is_set():
                return restarts
            time.sleep(min(1.0, poll_s))


def guard_beat(path=None):
    """Battement de cœur pour la garde (rien si l'appli n'a pas été lancée par la garde)."""
    path = path or os.environ.get("TSM_HEARTBEAT")
    if not path:
        return False
    try:
        Path(path).write_text(f"{time.time()} {os.getpid()}", encoding="utf-8")   # 7.60.2 : + n° du processus
        return True
    except OSError:
        return False


def read_language():
    """Langue choisie (config.json « lang »), sinon celle du système : français si Windows est en français,
    anglais sinon. TSM_LANG (variable d'environnement) l'impose (tests)."""
    env = os.environ.get("TSM_LANG")
    if env in ("fr", "en"):
        return env
    for path in (CFG_PATH, CFG_BAK):
        try:
            v = json.loads(path.read_text(encoding="utf-8")).get("lang")
            if v in ("fr", "en"):
                return v
            break
        except Exception:  # noqa: BLE001
            continue
    return "fr" if QtCore.QLocale.system().language() == QtCore.QLocale.Language.French else "en"


def install_french(app):
    """Boutons standard de Qt en français (Oui / Non, OK / Annuler, Ouvrir…). Cherche aussi dans l'exe PyInstaller."""
    dirs = [QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.TranslationsPath)]
    base = getattr(sys, "_MEIPASS", None)
    if base:
        dirs += [os.path.join(base, "PySide6", "Qt", "translations"), os.path.join(base, "PySide6", "translations")]
    ok = False
    for name in ("qtbase_fr", "qt_fr"):
        tr = QtCore.QTranslator(app)
        if any(tr.load(name, d) for d in dirs if d):
            app.installTranslator(tr)
            ok = True
    return ok


def install_gc_main_thread(app, interval_ms=500):
    """Le ramasse-miettes de Python ne tourne plus que dans le fil de l'interface.
    Sinon (Python 3.12+) il peut se déclencher dans le fil du tinySA et y détruire des objets Qt de l'interface
    (courbes, lignes de tableau jetées quand on change le nombre de points…) → « access violation » (crash.log de
    Clément, 7.4.2 : ScanWorker.run, boucle d'attente de reconnexion). Même remède que GarbageCollector de pyqtgraph."""
    gc.disable()
    thr = gc.get_threshold()

    def tick():
        c0, c1, c2 = gc.get_count()
        if c0 > thr[0]:
            gc.collect(0)
            if c1 > thr[1]:
                gc.collect(1)
                if c2 > thr[2]:
                    gc.collect(2)

    t = QtCore.QTimer(app)
    t.timeout.connect(tick)
    t.start(interval_ms)
    return t


# Branche V8 : bulles des menus SDR, ajoutées ici (et pas dans MainWindow.TIPS_MENU, partagé avec la V7 : sinon
# chaque ajout de bulle côté V7 au même endroit provoquait un conflit de fusion).
