# Construction de la fenêtre, accueil, niveaux d'affichage, tutos. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenConstruction:
    """Construction de la fenêtre, accueil, niveaux d'affichage, tutos. (méthodes de MainWindow, regroupées par thème.)"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VER}")
        lang_ = getattr(QtWidgets.QApplication.instance(), "_lang", None)
        self.lang = lang_ if lang_ in ("fr", "en") else ("en" if TR else "fr")
        self.resize(1700, 980)
        self._fit_to_screen()
        self.setAcceptDrops(True)
        self.lock = threading.Lock()
        self._next_id = 1
        self._ver = 0
        self.bands, self.watch = [], []
        self.scenes = []                # [{name, color, groups:[{name, color}]}]
        self.scope = None               # None = global ; sinon [(scène, groupe|None), …]
        self._focus_bands, self._focus_sig = [], []
        self._tree_items, self._tree_sig, self._tree_lock = {}, {}, False
        self._guide = None
        self._im_dlg = self._rescue_dlg = self._replay = None
        self._linecheck = None          # appel des micros en cours (LineCheckDialog)
        self.alarms = AlarmBook()
        self.snooze_until = 0.0                # 🔕 silence des alarmes jusqu'à (horodatage) ; 0 = pas de silence
        self._info_base, self._net_txt = {}, {}  # version de chaque tinySA ; 🌐 débit / délai s'il est en réseau
        self.store = SweepStore(1800.0, 300.0)
        self.recorder = None
        self.session_cfg = dict(SESSION_DEFAULT)
        self.ui_level = "simple" if CFG_PATH.exists() else "ultra"     # 1er lancement : ultra simple
        self._first_run = not CFG_PATH.exists()
        self.thr_auto = False
        self.user_presets = []                     # ⭐ préréglages perso (7.57)
        self.user_name = ""                        # 👤 profil utilisateur chargé (7.57)
        self.tnt_cfg = dict(TNT_DEFAULT)           # 📺 canaux TNT / émetteurs proches (7.58)
        self._tnt_items, self._tnt_db = [], None
        self._hints_done, self._hint_next, self._tnt_measured = set(), 0.0, False   # 7.59 : propositions
        self._acurve = None                     # (Fc, Lc, t) : bruit de fond appris le long du spectre (seuils auto)
        self.tour_done = CFG_PATH.exists()
        self._tour = None
        self.log_kinds = log_kinds_norm(None)
        self._session = None                     # dossier de la session enregistrée en cours
        self._last_session = None
        self._t_start = None
        self.report_prefs, self.export_list_prefs = {}, {}
        self.vocab_user = dict(name=[], scene=[], group=[])
        self.docks, self._state_restored = [], False
        self.statuses = [dict(name=n, color=c, free=(n == "Libre"), on=(n == "En service")) for n, c in DEFAULT_STATUSES]
        self.theme = dict(THEMES[DEFAULT_THEME])
        self.country, self.plan_custom = "FR", {}
        self.plan, self.tv = [], []
        self._strip_rects, self._strip_labels = [], []
        self._strip_rows = []
        self.ref_curves = []            # courbe de référence : liste de (freq, niveau)
        self._ref_F = self._ref_L = None
        self.wall = None                # mur de fréquences (panneau dock_wall, créé avec les panneaux)
        self.panel_wins = {}            # panneaux sortis en vraie fenêtre : nom du dock -> PanelWindow
        self._log_err_shown = False
        self.log_dir = LOG_DIR
        self.export_prefs = {}
        self.latest, self.latest_t, self.maxhold, self.partial_data = {}, {}, {}, {}
        self.history = {}          # anciens balayages complets par bande (rémanence)
        self._hist_items = []
        self.unk_now, self.unk_seen = {}, {}
        self.worker = None              # 1er tinySA (compatibilité) ; tous les appareils : self.workers
        self.workers = []
        self.net_addr, self.port_net = "", False   # 🌐 1er tinySA en réseau (Raspberry Pi…) : adresse, choisi ou non
        self.net_profiles = []                     # 🌐 adresses enregistrées [{name, addr}] (une par Wi-Fi / lieu)
        self.dev2 = dict(on=False, addr="", offset=0.0, div=False)   # 2ᵉ tinySA : USB (« COM4 ») ou réseau (« 192.168.1.20:5025 »)
        self.states, self.state_cur = [], ""    # 📸 états (plans à basculer) ; "" = tout actif
        self.ezrf_link, self._ezrf_next, self._ezrf_dlg = None, 0.0, None   # 🔗 plan .ezrf3 suivi
        self.devx = []                  # tinySA 3 à 8 : [{on, addr, name, offset}] (le 2ᵉ reste dans dev2)
        self.dev_live = [True] * MAX_DEVS   # liaison de chaque appareil (False = perdue, ses bandes passent aux autres)
        self.dev_cycle = {}
        self.dev_names = ["tinySA 1", "tinySA 2"]   # noms de position (« Plateau », « FOH »…) ; 3ᵉ… : dans devx
        self.band_src = {}              # id bande -> n° du tinySA qui a fourni le dernier balayage
        self.div_buf, self.div_src = {}, {}   # 🔀 diversity : {bande: {tinySA: (F, L, t)}}, {bande: (F, gagnant, t)}
        self._calib = None              # calibration en cours : {band, t0, data:{0:[], 1:[]}}
        self._strong_src = {}           # alarmes « trop fort » en cours -> bande qui les a vues
        self.sig_labels = {}            # tes mots pour la colonne Signal (clé SIGNAL_LABELS -> texte)
        self.sig_colors = {}            # tes couleurs par situation (clé SIGNAL_LABELS -> "#rrggbb")
        self.sdr_cfg = dict(dir="", lna=24, vga=20, amp=False, rec_max_gb=20)    # V8 : HackRF / RTL-SDR
        self.plan_opts = dict(sep=int(round(PF_SEP * 1000)), filt=32.0, step=25, prof="")   # 🧮 : kHz, MHz, kHz, profil
        self.unit = "dbm"               # unité d'affichage des niveaux (en interne : toujours dBm)
        self.show_meta = {k: "" for k in SHOW_META}   # show en cours (🎪 Shows)
        self.show_path = ""
        self.recent_shows = []
        self.notify_cfg = dict(mode="off", service="ntfy", server="https://ntfy.sh", topic="", tg_token="",
                               tg_chat="", site="", lang="app")
        self.notifier = None
        self._notified = set()          # id des alarmes déjà traitées pour l'envoi sur téléphone
        self.web_cfg = dict(on=False, port=WEB_PORT, pin="", password="", views=web_views_norm(None), tech="",
                            tech_approve=True)          # 🛠 mot de passe Tech + accord sur le PC pour chaque appareil
        self._web_spec = b'{"t":0,"bands":[]}'
        self._web_acks = queue.Queue()      # acquittements reçus de la page web (fil du serveur → fil Qt)
        self._web_hunts = queue.Queue()     # 🔎 chasse commandée depuis un téléphone
        self._web_terrain = queue.Queue()   # 🎒 tinySA volant : scènes / scans gardés depuis un téléphone
        self._web_tech, self._web_techreq = queue.Queue(), queue.Queue()   # 🛠 commandes Tech / demandes d'accès
        self._tech_msg, self._tech_json, self._tech_boxes = "", b"{}", []
        self._terrain_msg = ""
        self.web = None
        self._web_json = {"fr": b"{}", "en": b"{}"}
        self.view_id = -1
        self.wf_hist, self.wf_id = None, None
        self._fit_x = True
        self._updating = False
        self._last_xy = None
        self.last_cycle = 10.0
        self.labels = []
        self._sel_items = None                 # surbrillance des fréquences choisies dans la liste
        self.scan_follow = False               # ne balayer que la bande affichée dans « Vue »
        self.sound = SoundOut()                # sons de l'appli sur la sortie audio choisie (⚙ Réglages › Son)
        self.undo_stack = UndoStack()            # ↶ / ↷ (Ctrl+Z / Ctrl+Y) : liste, scènes, bandes, statuts, scans
        self.alarms.repeat_s = float(self.sound.cfg["repeat"])
        self._hunt = None                      # 🔎 chasse au brouilleur ouverte
        self._quickadd = None                  # ⌨ saisie express (7.62)
        self._replace = None                   # 🆘 remplacer un micro (7.62)
        self._qr = None                        # 📱 QR code de la page web (7.63)
        self.map_cfg, self._map, self._map_scene = map_cfg_norm(None), None, None      # 🗺 carte (7.64)
        self._map_png, self._map_rect, self._map_png_t = b"", None, 0.0
        self.mod_history, self._hist_rows, self._hist_dlg = [], None, None     # 🕘 historique (7.63)
        self._tech_sugg = None                 # 🆘 propositions demandées depuis la page Tech
        self.zoom_dev = 0                      # tinySA qui fait le zoom live (0 = le 1er ; 1 = le 2ᵉ, ex. sur un Pi)
        self.site_scans = []                   # 📍 scans gardés par lieu [{name, t, f, l}]
        self.dev_scenes = {}                   # 📡 scènes de chaque tinySA {n° appareil: [scènes]} (en continu)
        self.dev_ids = {}                      # 🔢 numéro gravé dans chaque tinySA branché {n° appareil: deviceid}
        self.devid_scenes = {}                 # {deviceid: [scènes]} : un tinySA numéroté retrouve ses scènes
        self._devdlg = None
        self.site_live = {}                    # {lieu: {bande: (F, L, t)}} derniers balayages faits sur place
        self.site_mh = {}                      # {lieu: {bande: max hold}} depuis le lancement
        self._site_mh_t0 = {}                  # {lieu: début de son max hold} (durée d'un scan gardé)
        self._mh_t0 = None                     # début du max hold global (durée d'un scan gardé)
        self._site_base = {}                   # {lieu: scan gardé au 1er balayage de la séance} (fusion continue)
        self._sites_next = 0.0
        self.sites_coord = False               # coordination / secours : éviter l'occupé de TOUS les lieux
        self.planning = planning_norm(None)    # 🎬 qui joue quand, par scène
        self._plan_state = (set(), set())      # (actifs, scènes planifiées) au dernier calcul
        self._plan_next = 0.0
        self._auto_changed = False             # ⚡ points Auto : un pas a-t-il changé au dernier calcul ?
        self.festival = festival_cfg_norm(None)  # 🌙 mode festival
        self._fest_next = 0.0
        self._log_n = 0                        # événements notés depuis le lancement (bilan : depuis le précédent)
        self._fest_log_mark = 0
        self._closing = False
        self._awake = False
        self._mk_items = {}
        self.mk = mk_default()          # repères du spectre : filtres (état, couche, statut), style
        self.expert = False             # mode simple par défaut (☰ Plus › Mode expert)
        self.sections_open = dict(self.SECTIONS_OPEN)
        self._zoom = None
        self._zoom_view = None
        self._cfg = dict(rbw=None, zrbw=None, zpts=None, input="auto", lna=None, att="auto", offset=0.0,
                         seg=None, points=1000)
        self._build_ui()
        self._load_config()
        self._load_ref_file(REF_PATH, silent=True)
        self.refresh_ports()
        self._sync_cfg()
        self.rebuild_plan()
        self.apply_theme()
        self.rebuild_band_table()
        self.refresh_view_combo()
        self.rebuild_watch_table()
        self.set_status("Prêt. Ferme tinySA-App, choisis le port puis ▶ Démarrer (ou essaie le mode démo).")
        self._alarm_timer = QtCore.QTimer(self)
        self._alarm_timer.setInterval(1000)
        self._alarm_timer.timeout.connect(self._alarm_tick)
        self._alarm_timer.start()
        self._autosave = QtCore.QTimer(self)          # coupure de courant / plantage : on perd au plus une minute
        self._autosave.setInterval(AUTOSAVE_MS)
        self._autosave.timeout.connect(self._save_config)
        self._autosave.start()
        self.set_coord(self.coord_on)             # outils de coordination cachés sauf si la config les montre
        self._first_show = True

    def _fit_to_screen(self):
        """Petit écran (portable 1366×768…) : la fenêtre ne doit pas déborder."""
        scr = QtGui.QGuiApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        if g.width() > 0 and g.height() > 0:
            self.resize(min(self.width(), g.width()), min(self.height(), g.height()))

    def showEvent(self, e):
        super().showEvent(e)
        if getattr(self, "_first_show", False):
            self._first_show = False
            QtCore.QTimer.singleShot(120, self._late_layout)    # la fenêtre a alors sa vraie taille

    def _late_layout(self):
        guarded = "1" in (os.environ.get("TSM_GUARD_RESTART"), os.environ.get("TSM_RESUME"))   # relancée par la garde
        if self.festival["was_running"] and (guarded or (self.festival["on"] and self.festival["autostart"])):
            QtCore.QTimer.singleShot(4000, self._festival_autostart)
        self.panel_restore(getattr(self, "_panel_cfg", None))
        self.set_level(self.ui_level)
        if not self.tour_done:
            self.tour_btn.setText("🎓 Première fois ? Tuto")
            self.step_lbl.setText("👋 Suis les étapes de gauche à droite, ou lance le tuto.")
        if getattr(self, "_first_run", False):
            # 7.57 : 1er lancement : le pays d'après Windows, puis la Vue directement sur l'UHF de ce pays
            code = country_from_locale(QtCore.QLocale.system().name())
            i_ = self.country_combo.findData(code) if code else -1
            if i_ >= 0 and i_ != self.country_combo.currentIndex():
                self.country_combo.setCurrentIndex(i_)
            self.auto_view()
        if not self._state_restored:
            if self._wf_bid() is None:
                self.dock_wf.hide()      # pas de waterfall en vue « tout le spectre » : le spectre prend la place
            self._dock_sizes()
        self._late_layout_v8()

    def _migration_notice(self):
        """8.1 : l'ancien dossier « TinySA Monitor » et le nouveau existaient tous les deux : les fichiers en double sont
        restés dans l'ancien (rien n'a été écrasé). On le dit une fois, avec les deux chemins."""
        for old_, new_, n_ in MIGRATION_INFO:
            m = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Information, TR("Changement de nom : tes fichiers"),
                                      TR("RF Technical Monitor range maintenant tes shows, journaux et profils dans :\n{}"
                                         "\n\nL'ancien dossier existait encore : tout ce qui manquait a été déplacé. "
                                         "{} fichier(s) existaient des deux côtés avec le même nom : ils sont RESTÉS "
                                         "dans\n{}\n(rien n'a été écrasé ; la liste est dans LISEZMOI_migration.txt)."
                                         ).format(new_, n_, old_), QtWidgets.QMessageBox.StandardButton.Ok, self)
            m.setModal(False)
            m.show()
            self._mig_box = m
        MIGRATION_INFO.clear()

    def _late_layout_v8(self):
        """V8 (repliée en 8.1) : ménage des enregistrements SDR, bouton de mode, plusieurs écrans, logo, démarrage avec
        Windows sous le nouveau nom, Ctrl+Maj+F (micros suivis par le SDR)."""
        for fn in (self.sdr_timer, self.mode_setup):     # audit V8 (5.) ; étape 16 : bouton 📟 / 📡 / combiné
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.win_menu.addSeparator()
            self.win_menu.addAction(TR("🖥 Plusieurs écrans (tinySA, SDR, listes)…")).triggered.connect(
                lambda *_: self.open_screens())
        except Exception:  # noqa: BLE001
            pass
        QtCore.QTimer.singleShot(900, self.screens_restore)
        if MIGRATION_INFO:                          # 8.1 (audit) : fusion partielle des dossiers -> le dire, une fois
            QtCore.QTimer.singleShot(1500, self._migration_notice)
        try:                                        # 8.1 : le logo de RF Technical Monitor en tête de la barre (clic = À propos)
            if getattr(self, "brand_btn", None) is None and not self.windowIcon().isNull():
                b = self.brand_btn = QtWidgets.QToolButton()
                b.setIcon(self.windowIcon())
                b.setIconSize(QtCore.QSize(22, 22))
                b.setAutoRaise(True)
                b.setToolTip(f"{APP_NAME} {APP_VER} — " + TR("À propos, version, où sont tes fichiers"))
                b.clicked.connect(lambda *_: self.show_about())
                acts = self.cmd_bar.actions()
                self.cmd_bar.insertWidget(acts[0], b) if acts else self.cmd_bar.addWidget(b)
        except Exception:  # noqa: BLE001
            pass
        try:                                        # 8.1 : démarrage avec Windows réglé sous l'ancien nom -> nouveau nom
            if sys.platform == "win32" and self.windows_startup_on():
                self.set_windows_startup(True)
        except Exception:  # noqa: BLE001
            pass
        try:
            sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self.watch_table)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(self.sdr_follow_key)
        except Exception:  # noqa: BLE001
            pass

    # ---------------------------------------------------------------- UI
    @staticmethod
    def _item(text, editable=False, right=False):
        it = QtWidgets.QTableWidgetItem(text)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        it.setFlags(flags)
        if right:
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return it

    @staticmethod
    def _row(*ws):
        h = QtWidgets.QHBoxLayout()
        for w in ws:
            if isinstance(w, str):
                h.addWidget(QtWidgets.QLabel(w))
            elif w is None:
                h.addStretch(1)
            else:
                h.addWidget(w)
        return h

    @staticmethod
    def _elastic(lab):
        """Texte qui change en direct (compteurs, état) : coupé si trop long, n'élargit jamais la fenêtre."""
        lab.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, lab.sizePolicy().verticalPolicy())
        lab.setMinimumWidth(40)
        return lab

    def add_freq_actions(self, menu, f, w=None):
        """Ajoute les FREQ_ACTIONS au menu -> {action: nom de méthode}."""
        out = {}
        if not f or not self.FREQ_ACTIONS:
            return out
        menu.addSeparator()
        for txt, fn in self.FREQ_ACTIONS:
            if callable(getattr(self, fn, None)):
                out[menu.addAction(txt)] = fn
        return out

    def run_freq_action(self, acts, act, f, w=None):
        """Lance l'action choisie si c'en est une de FREQ_ACTIONS -> True."""
        fn = acts.get(act) if act is not None else None
        if fn is None:
            return False
        getattr(self, fn)(float(f), w)
        return True

    def _install_tips(self):
        """Une explication sur chaque bouton / case / liste, aussi recopiée dans la barre d'état au survol."""
        tips_text = {TR(k): t for k, t in self.TIPS_TEXT.items()}      # les boutons affichent le texte traduit
        tips_text.update({plain_btn_text(k): t for k, t in list(tips_text.items())})   # 7.54 : boutons sans emoji
        tips_menu = [(TR(k), t) for k, t in self.TIPS_MENU.items()]
        for name, tip in self.TIPS_ATTR.items():
            w_ = getattr(self, name, None)
            if w_ is not None and not w_.toolTip():
                w_.setToolTip(tip)
        for w_ in self.findChildren(QtWidgets.QAbstractButton):
            if not w_.toolTip() and w_.text() in tips_text:
                w_.setToolTip(tips_text[w_.text()])
        for btn, _box in self.sections.values():
            btn.setToolTip("Clic : replier / déplier cette section (l'état est mémorisé).")
        for w_ in self.findChildren(QtWidgets.QWidget):
            if w_.toolTip() and not w_.statusTip():
                w_.setStatusTip(w_.toolTip().split("\n")[0])
        menus = set(self.findChildren(QtWidgets.QMenu))
        todo = [self.more_menu] + list(getattr(self, "step_menus", {}).values())   # menus rattachés à des boutons
        while todo:
            m_ = todo.pop()
            menus.add(m_)
            todo += [a_.menu() for a_ in m_.actions() if a_.menu() is not None and a_.menu() not in menus]
        for m_ in menus:
            m_.setToolTipsVisible(True)
            for a_ in m_.actions():
                tip = next((t for k, t in tips_menu if a_.text().startswith(k)), None)
                if tip:
                    a_.setToolTip(tip)
                    a_.setStatusTip(tip.split("\n")[0])

    def set_expert(self, on):
        """Mode simple : seulement l'essentiel (seuils, bandes, 2ᵉ tinySA, pays). Expert : tous les réglages."""
        self.expert = bool(on)
        self._apply_words(self.expert)
        if self.expert:
            self.ui_level = "expert"
        elif getattr(self, "ui_level", "simple") == "expert":
            self.ui_level = "simple"
        for k_, a_ in getattr(self, "level_acts", {}).items():
            a_.setChecked(k_ == getattr(self, "ui_level", "simple"))
        for form, w_ in getattr(self, "_expert_rows", []):
            form.setRowVisible(w_, self.expert)
        for w_ in (getattr(self, "ref_row", None), getattr(self, "persist_combo", None)):
            if w_ is not None:
                w_.setVisible(self.expert)
        if hasattr(self, "expert_hint"):
            self.expert_hint.setText("🎛 Mode expert : revenir au mode simple" if self.expert
                                     else "🎛 Mode simple : afficher tous les réglages")
        if getattr(self, "sites_btn", None) is not None:      # 📡 tinySA ↔ scènes : réservé au mode expert
            self.sites_btn.setVisible(self.expert)
        if getattr(self, "layer_tree", None) is not None and hasattr(self, "watch"):
            self.rebuild_tree()

    # ------------------------------------------------------- parcours (7.13, Clément : « dans l'ordre logique :
    # scan → plan → intermod → monitoring ») et niveaux d'affichage (« un mode ultra simple »)
    def _build_steps_bar(self):
        """Les 4 familles (📋 Préparer, 🎚 Surveiller, 📊 Analyser, 🔌 Matériel) dans la barre du haut, juste avant
        ☰ Plus (7.46 : une seule porte d'entrée ; remplace la barre de parcours ①…⑥)."""
        tb = self.cmd_bar
        self.step_btns, self.step_menus = {}, {}
        self._coord_acts = list(getattr(self, "_coord_acts", []))
        for key, txt, tip, items in STEPS:
            b = QtWidgets.QPushButton(txt)
            b.setToolTip(tip)
            m_ = QtWidgets.QMenu(b)
            m_.setToolTipsVisible(True)
            for it_txt, meth in items:
                if it_txt is None:
                    m_.addSeparator()
                    continue
                if it_txt.startswith("§"):                # titre de rubrique (7.49 : menus rangés par rubriques)
                    m_.addSection(it_txt[1:])
                    continue
                a_ = m_.addAction(it_txt)
                a_.triggered.connect(lambda *_, k=key, n=meth: self.do_step(k, n))
                if meth in COORD_METHODS:
                    self._coord_acts.append(a_)
                elif meth == "show_coord_setting":
                    self._coord_hint = a_
            if key == "hw":
                for title, its in self.EXTRA_MENUS:       # sous-menus ajoutés par une autre version (V8 : SDR)
                    sm = m_.addMenu(title)
                    for t_, n_ in its:
                        sm.addAction(t_).triggered.connect(lambda *_, n=n_: getattr(self, n)())
            b.setMenu(m_)
            self.__dict__.setdefault("_step_acts", {})[key] = tb.insertWidget(self._more_act, b)
            self.step_btns[key] = b
            self.step_menus[key] = m_
        self.find_btn = QtWidgets.QPushButton("🔎")
        self.find_btn.setToolTip("Chercher une fonction par un mot (secours, relais, RBW, rapport…)  Ctrl+K")
        self.find_btn.clicked.connect(lambda *_: self.open_feature_search())
        tb.insertWidget(self._more_act, self.find_btn)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), self).activated.connect(lambda *_: self.open_feature_search())
        tb.insertSeparator(self._more_act)
        for old, new in STEP_ALIAS.items():               # tutos : anciennes étapes -> leur famille
            self.step_btns.setdefault(old, self.step_btns[new])
        self.tour_btn = QtWidgets.QToolButton()          # gardés (tutos, anciennes configs) mais hors écran
        self.tour_btn.setText("🎓 Tuto")
        self.tour_btn.clicked.connect(lambda *_: self.start_tour())
        self.step_lbl = QtWidgets.QLabel("")
        self.steps_bar = None

    def _build_home(self):
        bar = QtWidgets.QToolBar("Accueil")
        bar.setObjectName("barre_accueil")
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.toggleViewAction().setEnabled(False)
        self.home = HomeBar(self)
        self.home.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        bar.addWidget(self.home)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self.home_bar = bar

    def set_home(self, on):
        """🏠 Accueil affiché ou non (config « home »). Avec l'accueil, la barre de parcours n'est montrée qu'en expert."""
        self.home_on = bool(on)
        if getattr(self, "home_bar", None) is not None:
            self.home_bar.setVisible(self.home_on)
        self._home_layout()
        a = getattr(self, "home_act", None)
        if a is not None:
            a.setChecked(self.home_on)
        self.update_home()

    def _home_layout(self):
        """Avec l'accueil (hors expert) : pas de barre de parcours ni de Port / Démarrer en double en haut."""
        full = not self.home_on or getattr(self, "ui_level", "simple") == "expert"
        if getattr(self, "steps_bar", None) is not None:
            self.steps_bar.setVisible(full)
        for a_ in getattr(self, "_dup_acts", []):
            a_.setVisible(not self.home_on)      # 7.59 : avec l'accueil, Port / Démarrer n'apparaissent qu'une fois

    def home_info(self):
        lost = [self.dev_name(d) for d in self.dev_list()
                if self.is_running() and d < len(self.dev_live) and not self.dev_live[d]]
        cur = [a for a in self.alarms.active.values()] if isinstance(self.alarms.active, dict) else []
        cur.sort(key=lambda a: (a["acked"], -a["prio"]))
        ws = [w for w in self.watch if not w.get("off")]
        ok = free = weak = muted = silent = 0
        for w in ws:
            if w.get("muted"):
                muted += 1
                continue
            _t, tone, _c = self.sig_view(w)
            ok += tone == "ok"
            free += tone == "free"
            if tone == "warn":
                if w.get("state") == "weak":
                    weak += 1
                else:
                    silent += 1                      # doit émettre, rien reçu (pas encore ABSENT)
        p = self.port1()
        pb = getattr(self, "_last_problem", None)
        problem = pb["title"] if pb and (lost or (not self.is_running() and pb["key"] != "lost")) else ""
        return dict(running=self.is_running(), demo=self.demo_chk.isChecked(), port=bool(p), problem=problem,
                    port_txt=self.port_combo.currentText() if p else "", n_watch=len(ws), lost=lost,
                    alarms=[(a["kind"], a.get("name") or "") for a in cur if a["kind"] != "APPAREIL"],
                    ok=ok, free=free, weak=weak, muted=muted, silent=silent,
                    **(self._home_fresh() if self.is_running() else {}))

    def health(self):
        """État général (accueil, mode Show, vue Régie) : {tone ok|warn|bad|wait|idle, text}."""
        try:
            info = self.home_info()
            tone, text = home_status(info)
            ds = data_status(info) if self.is_running() else None
        except Exception:  # noqa: BLE001        audit 7.52 : jamais « tout va bien » si on n'a pas pu vérifier
            now = time.time()
            if now - getattr(self, "_health_err_t", 0) > 600:     # noté au plus toutes les 10 min (appelé chaque s)
                self._health_err_t = now
                try:
                    log_crash("état indéterminé", traceback.format_exc())
                except Exception:  # noqa: BLE001
                    pass
            try:
                run = bool(self.is_running())
            except Exception:  # noqa: BLE001
                run = True                       # dans le doute : on suppose qu'on surveille (= alerte visible)
            bad = dict(tone="bad", text=UNKNOWN_HEALTH)
            return dict(tone="bad", text=UNKNOWN_HEALTH, data=bad if run else None)
        run = self.is_running()
        # data : None = surveillance arrêtée ; {tone ok} = mesures fraîches ; sinon le problème (ou l'état inconnu)
        data = dict(tone=ds[0], text=ds[1]) if ds else (dict(tone="ok", text="") if run else None)
        return dict(tone=tone, text=text, data=data)

    def _home_fresh(self):
        """Fraîcheur des mesures pour l'accueil : âge de la dernière mesure (None = aucune depuis ▶ Démarrer),
        limite au-delà de laquelle c'est périmé, fréquences sans mesure, saturation."""
        now = time.time()
        t0 = getattr(self, "_run_t0", None)
        run_age = (now - t0) if t0 else 0.0
        # âge = celui de la bande la PLUS EN RETARD (revue UX : une bande figée pendant que les autres tournent ne doit
        # pas passer inaperçue) ; une bande jamais mesurée depuis ▶ Démarrer compte pour run_age.
        ages, seen = [], False
        for b in self.scan_bands():
            if not self._scan_now(b):
                continue
            t = self.latest_t.get(b["id"])
            if t is not None and (t0 is None or t >= t0 - 1):
                seen = True
                ages.append(now - t)
            else:
                ages.append(run_age)
        live = [d for d in self.dev_list() if d < len(self.live_mask()) and self.live_mask()[d]]
        zoom = bool(getattr(self, "_zoom", None)) and len(live) <= 1    # avec 2 tinySA, l'autre garde les bandes
        if zoom:                                   # 🔍 zoom live : seule la zone zoomée est mesurée (voulu)
            tz = self.latest_t.get(ZOOM_ID)
            ages, seen = ([now - tz] if tz is not None and (t0 is None or tz >= t0 - 1) else []), tz is not None
        q = self.quality_info()
        return dict(last_age=max(ages) if (seen and ages) else None, run_age=run_age, zoom=zoom,
                    stale_lim=max(15.0, 4 * (self.last_cycle or 0.0)), stale=q.get("stale", 0),
                    stale_names=q.get("stale_names", []), sat=q.get("sat"), sat_dbm=q.get("sat_dbm"))

    def update_home(self):
        h = getattr(self, "home", None)
        if h is None or not self.home_on:
            return
        try:
            h.refresh(self.home_info())
        except Exception:  # noqa: BLE001 — l'accueil ne doit jamais gêner la surveillance
            try:                                 # audit 7.52 : ne pas laisser l'ancienne phrase (peut-être « OK »)
                th_ = self.theme
                h.status.setText(UNKNOWN_HEALTH)
                h.status.setStyleSheet("font-size:16px; font-weight:600; padding:4px 10px; "
                                       + soft_style(th_["st_occ"], th_["ui_bg"], th_["ui_text"]))
            except Exception:  # noqa: BLE001
                pass

    def do_step(self, key, meth=None):
        """Une étape du parcours : met l'étape en avant, explique, et lance l'action (ou celle du menu)."""
        for k_, b in self.step_btns.items():
            f_ = b.font()
            f_.setBold(k_ == key)
            b.setFont(f_)
        key = STEP_ALIAS.get(key, key)
        if STEP_HINTS.get(key):
            self.set_status(STEP_HINTS[key])
        fn = getattr(self, meth or STEP_DEFAULT.get(key, ""), None)
        if fn is not None:
            fn()

    def step_scan(self):
        """① Scanner le lieu : démarre le balayage (max hold remis à zéro) pour voir ce qui occupe déjà le lieu."""
        self.hold_chk.setChecked(True)
        self.reset_max()
        if not self.is_running():
            self.toggle_run()

    def open_occupancy(self):
        OccupancyDialog(self).exec()

    def open_coord(self):
        CoordDialog(self).exec()

    def open_scan_add(self):
        ScanAddDialog(self).exec()

    def step_monitor(self):
        if not self.is_running():
            self.toggle_run()

    def status_help(self):
        QtWidgets.QMessageBox.information(self, APP_NAME, STATUS_HELP)

    def _set_level_base(self, level):
        """Ultra simple : spectre + liste + alarmes, rien d'autre. Simple : + réglages essentiels, journal,
        classement par scène / groupe. Expert : tous les réglages."""
        level = level if level in dict(UI_LEVELS) else "simple"
        self.ui_level = level
        self.set_expert(level == "expert")
        ultra = level == "ultra"
        d = getattr(self, "dock_log", None)
        if d is not None and d.objectName() not in getattr(self, "panel_wins", {}):
            d.setVisible(not ultra)
        if getattr(self, "thr_bar", None) is not None:
            self.thr_bar.setVisible(not ultra)
        if ultra and getattr(self, "dock_wf", None) is not None:
            self.dock_wf.setVisible(False)
        elif getattr(self, "dock_wf", None) is not None and getattr(self, "_prev_level", "") == "ultra":
            if self._wf_bid() is not None:             # 7.57 : en quittant l'ultra simple, le waterfall revient
                self._wf_show(True)
        self._prev_level = level
        if getattr(self, "layer_box", None) is not None:
            self.layer_box.setVisible(not ultra)
        for k_, a_ in getattr(self, "level_acts", {}).items():
            a_.setChecked(k_ == level)
        self._home_layout()

    def set_level(self, level):
        """Niveau d'affichage : la partie V7, puis les panneaux SDR (Simple / Plus / Expert)."""
        r = self._set_level_base(level)
        if getattr(self, "rf_mode", "tiny") == "sdr":       # 8.0.1 : le niveau réaffichait le waterfall du tinySA
            self.dock_spec.hide()                           # à côté du spectre SDR (3ᵉ colonne, fenêtre trop large)
            self.dock_wf.hide()
        for d in self.all_sdr_docks():
            try:
                self.dock_widget(d).apply_level()
            except Exception:  # noqa: BLE001
                pass
        try:
            rx = self.sdr_docks["rx"]
            if rx.isVisible() and not rx.isFloating():
                QtCore.QTimer.singleShot(0, lambda: self.resizeDocks(
                    [rx], [rx.widget().sizeHint().height() + 36], Qt.Orientation.Vertical))
        except Exception:  # noqa: BLE001
            pass
        return r

    def _apply_words(self, expert):
        """Mots simples hors expert (« Pics gardés » au lieu de « Max hold ») ; le terme technique reste dans la bulle."""
        for k in UI_WORDS:
            w_ = getattr(self, k, None)
            if w_ is None:
                continue
            try:
                base = self.__dict__.setdefault("_word_tips", {}).setdefault(k, w_.toolTip())
                w_.setText(ui_word(k, expert))
                w_.setToolTip(base if expert else (base + "\n" if base else "") + f"(terme technique : {ui_word(k, True)})")
            except Exception:  # noqa: BLE001 — objets factices des tests
                pass

    def start_tour(self, key=None):
        """🎓 Sans clé : choisir un tuto ; avec : le lancer (ecran, show, spectre, coord, scenes, live)."""
        if key is None:
            self._tour_chooser = TourChooser(self)
            self._tour_chooser.show()
            return
        if getattr(self, "_tour", None) is not None:
            self._tour.close()
        title = next((t for k, t, *_ in TOURS if k == key), "Tuto")
        steps = tour_steps(self, key)
        if self.home_on and getattr(self, "home", None) is not None and self.ui_level != "expert":
            hidden = {id(x) for x in (self.port_combo, self.demo_chk, self.start_btn, self.steps_bar)}
            steps = [st for st in steps if id(st[0]) not in hidden]
            if key == "ecran":                     # l'accueil remplace port / démo / démarrer / parcours
                c = self.home.cards
                steps = [
                    (c["port"][0], "Bienvenue 👋",
                     "RF Technical Monitor écoute en permanence les fréquences radio de tes micros sans fil grâce à un "
                     "petit appareil, le tinySA.",
                     "Il te prévient tout de suite si un micro se tait ou si quelqu'un vient émettre sur ta fréquence.",
                     "① « 🔌 Choisir… » : où est branché le tinySA (USB, réseau), ou le mode démo pour essayer sans "
                     "appareil.", None),
                    (c["list"][0], "② Mes micros",
                     "Ta liste de fréquences à surveiller : tes micros, tes ears, tes réserves.",
                     "Sans liste, l'appli ne sait pas quoi surveiller.",
                     "📥 Importer ton plan, ＋ Ajouter à la main, ou 📡 Depuis le scan.", ("📥 Importer…", "import_watch")),
                    (c["run"][0], "③ Surveiller",
                     "Lance ou arrête le balayage : le tinySA mesure les fréquences en boucle.",
                     "Rien ne se passe tant que ce n'est pas démarré.",
                     "▶ Démarrer. La grande phrase en dessous dit en permanence si tout va bien ; ✅ Prêt ? vérifie "
                     "tout avant le show.", None),
                ] + steps
        if not self.coord_on:                      # outils de coordination cachés : leurs étapes aussi
            steps = [st for st in steps if not (st[-1] and st[-1][1] in COORD_METHODS)] or steps
        self._tour = TourDialog(self, steps, title)
        self._tour.show()
        self._tour.go(0)

    def open_glossary(self):
        if getattr(self, "_glossary", None) is None or not self._glossary.isVisible():
            self._glossary = GlossaryDialog(self)
        self._glossary.show()
        self._glossary.raise_()

    def tour_finished(self):
        self.tour_done = True
        self._tour = None
        self.step_lbl.setText("")

    def open_section(self, key, on=True):
        """Ancien panneau à sections repliables (≤ 7.27) : l'état reste retenu dans la config, sans effet visible."""
        self.sections_open[key] = bool(on)

    @staticmethod
    def _flow(*groups):
        """Barre qui se replie : chaque groupe (widget, texte ou tuple) reste d'un seul tenant."""
        fl = FlowLayout()
        for g in groups:
            if not isinstance(g, tuple):
                g = (g,)
            if len(g) == 1 and not isinstance(g[0], str):
                fl.addWidget(g[0])
                continue
            box = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            for w in g:
                h.addWidget(QtWidgets.QLabel(w) if isinstance(w, str) else w)
            fl.addWidget(box)
        return fl

    @staticmethod
    def _combo(items, current=None):
        c = QtWidgets.QComboBox()
        for txt, data in items:
            c.addItem(txt, data)
        if current is not None:
            c.setCurrentIndex(max(0, c.findData(current)))
        return c

    def _build_ui(self):
        # courbes lissées (antialiasing) : joli mais gourmand (7.31.1 : 40 % de processeur chez Clément) -> coupé par
        # défaut, ⚙ › Général › « Courbes lissées » (set_smooth)
        pg.setConfigOptions(antialias=bool(getattr(self, "smooth", False)), background=self.theme["plot_bg"],
                            foreground=self.theme["plot_fg"])
        # --- barre du haut
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(220)
        btn_ports = QtWidgets.QToolButton()
        btn_ports.setText("⟳")
        btn_ports.setToolTip("Rafraîchir les ports")
        btn_ports.clicked.connect(self.refresh_ports)
        self.port_combo.activated.connect(self._port_chosen)
        self.demo_chk = QtWidgets.QCheckBox("Mode démo")
        self.demo_chk.setToolTip("Signaux simulés, sans appareil branché")
        self.info_lbl = QtWidgets.QLabel("")
        colors_btn = QtWidgets.QPushButton("🎨 Couleurs")
        colors_btn.clicked.connect(self.edit_colors)
        status_btn = QtWidgets.QPushButton("🏷 Statuts")
        status_btn.clicked.connect(self.edit_statuses)
        self.start_btn = QtWidgets.QPushButton("▶ Démarrer")
        self.start_btn.clicked.connect(self.toggle_run)
        wall_btn = QtWidgets.QPushButton("🧱 Mur")
        wall_btn.setToolTip("Ouvre une fenêtre de grandes tuiles (une par fréquence), à mettre sur un 2e écran.\n"
                            "F11 : plein écran.")
        wall_btn.clicked.connect(self.open_wall)
        prof_btn = QtWidgets.QPushButton("🎪 Shows")
        prof_btn.setToolTip("Enregistre / rappelle un show d'une année à l'autre : fréquences, scènes, bandes, statuts,\n"
                            "seuils, courbe de référence du lieu, infos et notes. Tes préférences (couleurs,\n"
                            "fenêtres, alertes, 2ᵉ tinySA…) ne bougent pas.  Ctrl+S : enregistrer.")
        self.show_menu = QtWidgets.QMenu(prof_btn)
        self.show_menu.aboutToShow.connect(lambda *_: self._build_show_menu())
        pmenu = self.show_menu
        sc_save = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        sc_save.activated.connect(lambda *_: self.save_show())
        sc_lc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self)
        sc_lc.activated.connect(lambda *_: self.open_linecheck())
        QtGui.QShortcut(QtGui.QKeySequence("F10"), self).activated.connect(lambda *_: self.open_show_mode())
        for seq, fn in (("Ctrl+Z", lambda *_: self.undo()), ("Ctrl+Y", lambda *_: self.redo()),
                        ("Ctrl+Shift+Z", lambda *_: self.redo())):
            QtGui.QShortcut(QtGui.QKeySequence(seq), self).activated.connect(fn)
        sc_set = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+,"), self)
        sc_set.activated.connect(lambda *_: self.open_settings())
        prof_btn.setMenu(pmenu)
        tools_btn = QtWidgets.QPushButton("🔧 Outils")
        tools_btn.setToolTip("Intermodulation, fréquence de secours, relecture, rapport, scans WSM/WWB, export par scène, "
                             "nommage rapide, vocabulaire.")
        def submenu(parent, title, items):
            sm = parent.addMenu(title)
            for txt, fn in items:
                if txt is None:
                    sm.addSeparator()
                else:
                    sm.addAction(txt).triggered.connect(fn)
            return sm

        win_btn = QtWidgets.QPushButton("🪟 Fenêtres")
        win_btn.setToolTip("Affiche / cache / détache les panneaux, dispositions prêtes à l'emploi (double écran…).\n"
                           "Tu peux aussi attraper un panneau par sa barre de titre et le poser où tu veux.")
        self.win_menu = QtWidgets.QMenu(win_btn)
        win_btn.setMenu(self.win_menu)
        self.alarm_btn = QtWidgets.QPushButton("🔔")
        self.alarm_btn.setToolTip("Alarmes : conflits (signal sur une fréquence « doit rester libre ») et émetteurs "
                                  "absents (« doit émettre »).\nRouge = à acquitter · orange = acquittées, toujours là.")
        self.alarm_btn.clicked.connect(lambda *_: self.toggle_alarm_dock())
        # barre du haut épurée : l'essentiel visible, le reste dans « ☰ Plus », rangé par moment du travail
        # (7.12, Clément : « ranger de façon logique, intuitive et efficace ») : pendant le show en haut,
        # préparer / après le show / connexions / apparence en sous-menus, aide en bas.
        self.settings_btn = QtWidgets.QPushButton("⚙")
        self.settings_btn.setToolTip("Réglages : seuils et alarmes, bandes à balayer, mesure, 2ᵉ tinySA, pays,\n"
                                     "langue, son et sortie audio, dossiers, connexions (Ctrl+,).")
        self.settings_btn.clicked.connect(lambda *_: self.open_settings())
        more_btn = QtWidgets.QPushButton("☰ Plus")
        self.more_btn = more_btn
        more_btn.setToolTip("Pendant le show (appel des micros, mur, relecture), préparer le plan, après le show,\n"
                            "connexions (alertes, relais), fenêtres, apparence, mode expert, manuel.")
        self.more_menu = QtWidgets.QMenu(more_btn)
        more_btn.setMenu(self.more_menu)
        mm = self.more_menu
        mm.addAction("↶ Annuler la dernière modification\tCtrl+Z").triggered.connect(lambda *_: self.undo())
        mm.addAction("↷ Rétablir\tCtrl+Y").triggered.connect(lambda *_: self.redo())
        # 7.46 : préparer / surveiller / analyser / matériel sont dans les 4 boutons de la barre (STEPS) ;
        # ☰ Plus ne garde que réglages, fenêtres, apparence, affichage et aide.
        self._coord_acts = []
        mm.addSection("Réglages et affichage")
        mm.addAction("⚙ Réglages (seuils, bandes, son, langue…)…  Ctrl+,").triggered.connect(lambda *_: self.open_settings())
        mm.addAction("🔎 Chercher une fonction…  Ctrl+K").triggered.connect(lambda *_: self.open_feature_search())
        mm.addAction("👤 Profils utilisateur (mes préférences)…").triggered.connect(lambda *_: self.open_user_profiles())
        self.win_menu.setTitle("🪟 Fenêtres et dispositions")
        mm.addMenu(self.win_menu)
        amenu = mm.addMenu("🎨 Apparence et langue")
        amenu.addAction("🎨 Couleurs et thèmes…").triggered.connect(lambda *_: self.edit_colors())
        amenu.addAction("🏷 Statuts…").triggered.connect(lambda *_: self.edit_statuses())
        amenu.addAction("🔤 Mots et couleurs (OK, libre, ABSENT…)…").triggered.connect(lambda *_: self.edit_labels())
        self.lang_menu = amenu.addMenu("🌐 Langue / Language")
        grp_l = QtGui.QActionGroup(self.lang_menu)
        for code, lname in LANGS:
            a_ = self.lang_menu.addAction(lname)
            a_.setCheckable(True)
            a_.setChecked(code == self.lang)
            grp_l.addAction(a_)
            a_.triggered.connect(lambda *_, c=code: self.set_language(c))
        lvl_menu = mm.addMenu("👁 Affichage : ultra simple / simple / expert")
        grp_v = QtGui.QActionGroup(lvl_menu)
        self.level_acts = {}
        for key_, txt_ in UI_LEVELS:
            a_ = lvl_menu.addAction(txt_)
            a_.setCheckable(True)
            grp_v.addAction(a_)
            a_.triggered.connect(lambda *_, k=key_: self.set_level(k))
            self.level_acts[key_] = a_
        self.expert_act = self.level_acts["expert"]
        lvl_menu.addSeparator()
        self.home_act = lvl_menu.addAction("🏠 Accueil (les 3 étapes en haut de l'écran)")
        self.home_act.setCheckable(True)
        self.home_act.setChecked(True)
        self.home_act.triggered.connect(lambda *_: self.set_home(self.home_act.isChecked()))
        mm.addSection("Aide")
        mm.addAction("🎓 Tutos pas à pas (débutants)…").triggered.connect(lambda *_: self.start_tour())
        mm.addAction("📚 Lexique : les mots de la HF expliqués…").triggered.connect(lambda *_: self.open_glossary())
        mm.addAction("📏 Échelles et niveaux (dBm, dBFS, dBu…)").triggered.connect(lambda *_: self.open_scales())
        mm.addAction("📖 Manuel d'utilisation").triggered.connect(lambda *_: self.open_manual())
        mm.addAction(f"ℹ À propos (version {APP_VER})…").triggered.connect(lambda *_: self.show_about())
        self._spare_btns = [tools_btn, win_btn, wall_btn, colors_btn, status_btn]   # gardés pour leurs menus
        # barre d'outils sur toute la largeur (au-dessus des panneaux) : jamais coupée par les colonnes
        tb = QtWidgets.QToolBar("Commandes")
        tb.setObjectName("barre_commandes")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.toggleViewAction().setEnabled(False)
        port_box = QtWidgets.QWidget()
        ph = QtWidgets.QHBoxLayout(port_box)
        ph.setContentsMargins(4, 2, 8, 2)
        for wd in (QtWidgets.QLabel("Port :"), self.port_combo, btn_ports, self.demo_chk, self.info_lbl):
            ph.addWidget(wd)
        self._port_act = tb.addWidget(port_box)
        self._dup_acts = [self._port_act]          # en double avec l'accueil : cachés quand il est affiché (hors expert)
        for wd in (self.start_btn, prof_btn, self.alarm_btn, more_btn, self.settings_btn):
            a_ = tb.addWidget(wd)
            if wd is more_btn:
                self._more_act = a_                # les 4 familles (STEPS) se glissent juste avant ☰ Plus
            s_ = tb.addSeparator()
            if wd is self.start_btn:
                self._dup_acts += [a_, s_]
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.cmd_bar = tb
        self._build_steps_bar()
        self._build_home()

        # --- panneau de gauche : réglages
        self.points_combo = self._combo([(t, k) for k, t, _b in AUTO_POINTS]
                                        + [(f"{p:,}".replace(",", " "), p) for p in POINTS_CHOICES], 1000)
        self.points_combo.setToolTip("Nombre de points par balayage et par bande (appliqué à toutes les bandes).\n"
                                     "Plus il y en a, plus c'est précis… et plus c'est long.\n"
                                     "⚡ Auto : l'appli choisit le pas d'après la largeur totale balayée (10 kHz sur une\n"
                                     "petite zone, plus large sur toute l'UHF) pour garder un cycle de quelques secondes.\n"
                                     "Rapide ≈ 2 000 points par cycle · équilibré ≈ 4 500 · détaillé ≈ 9 000.")
        self.points_combo.activated.connect(self.apply_points)
        self.rbw_combo = self._combo([("Auto", None)] + [(f"{v:g} kHz", v) for v in RBW_LIST])   # 7.57.1 : Auto par défaut
        self.zrbw_combo = self._combo([("Auto (selon zoom)", None)] + [(f"{v:g} kHz", v) for v in RBW_LIST])
        self.zpts_combo = self._combo([("Auto (selon zoom)", None)]
                                      + [(f"{p:,}".replace(",", " "), p) for p in POINTS_CHOICES])
        self.input_combo = self._combo([("Auto", "auto"), ("Basse (≤ 800 MHz)", "low"),
                                        ("Haute (> 800 MHz)", "high")])
        self.input_combo.setToolTip("Auto : tinySA d'origine → prise « haute » au-delà de 800 MHz ; tinySA Ultra (une\n"
                                    "seule prise) → rien n'est changé, il passe en mode « ultra » au-delà de 800 MHz.\n"
                                    "Basse / Haute : forcé (seulement utile sur un tinySA d'origine).")
        self.lna_combo = self._combo([("Inchangé", None), ("ON", True), ("OFF", False)])
        self.lna_combo.setToolTip("LNA interne du tinySA Ultra (désactive l'atténuateur quand il est ON)")
        self.att_combo = self._combo([("Auto", "auto")] + [(f"{n} dB", n) for n in (0, 5, 10, 15, 20, 25, 30)])
        self.offset_spin = QtWidgets.QDoubleSpinBox()
        self.offset_spin.setRange(-60, 60)
        self.offset_spin.setSingleStep(0.5)
        self.offset_spin.setSuffix(" dB")
        self.offset_spin.setToolTip("Ajouté à toutes les mesures (gain d'antenne, perte de câble, ampli externe…)")
        self.seg_combo = self._combo([("Auto (selon le modèle)", None), ("145 pts", 145), ("290 pts", 290),
                                      ("450 pts", 450)])
        self.seg_combo.setToolTip("Nombre max de points demandés au tinySA par commande.\n"
                                  "Les balayages plus longs sont découpés en segments.\n"
                                  "Auto = 450 sur tinySA Ultra, 290 sinon.")
        self.est_lbl = QtWidgets.QLabel("")
        self.est_lbl.setWordWrap(True)
        for c in (self.rbw_combo, self.zrbw_combo, self.zpts_combo, self.input_combo, self.lna_combo, self.att_combo,
                  self.seg_combo):
            c.currentIndexChanged.connect(self._sync_cfg)
        self.offset_spin.valueChanged.connect(self._sync_cfg)

        mbox, mform = QtWidgets.QGroupBox("Mesure"), None
        mform = QtWidgets.QFormLayout(mbox)
        m_help = QtWidgets.QLabel(
            "Laisse tout en <b>Auto</b> si tu débutes. <b>Finesse (RBW)</b> : plus fine = distingue deux signaux "
            "proches, mais balaye plus lentement. <b>Préampli (LNA)</b> : rend visibles les signaux faibles, mais "
            "sature plus vite près d'un émetteur fort. <b>Atténuateur</b> : baisse le niveau d'entrée quand un "
            "émetteur proche fausse la mesure (« signal très fort » dans ✅ Prêt ?).")
        m_help.setWordWrap(True)
        m_help.setMinimumHeight(m_help.fontMetrics().lineSpacing() * 4)
        mform.addRow(m_help)
        mform.addRow("Points / balayage :", self.points_combo)
        mform.addRow("Finesse de mesure (RBW) :", self.rbw_combo)
        mform.addRow("Finesse en zoom (RBW) :", self.zrbw_combo)
        mform.addRow("Points en zoom :", self.zpts_combo)
        mform.addRow("Entrée :", self.input_combo)
        mform.addRow("Préampli (LNA) :", self.lna_combo)
        mform.addRow("Atténuateur :", self.att_combo)
        mform.addRow("Correction de niveau (offset) :", self.offset_spin)
        mform.addRow("Points par commande (segment) :", self.seg_combo)
        self.baud_combo = self._combo([(f"{b:,}".replace(",", " ") + " bauds", b)
                                       for b in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)], 115200)
        self.baud_combo.setToolTip("Vitesse du port série. En USB elle ne sert à rien (port COM virtuel : la vitesse\n"
                                   "est ignorée). Seulement pour un vrai port série (adaptateur USB-série, connecteur\n"
                                   "interne du tinySA, module série réseau) : mets la même que dans le tinySA.")
        mform.addRow("Vitesse série :", self.baud_combo)
        mform.addRow(self.est_lbl)

        self.thr_spin = LevelSpin()
        self.thr_spin.setRange(-130, 0)
        self.thr_spin.setValue(-80)
        self.thr_spin.valueChanged.connect(self._thr_from_spin)
        auto_btn = QtWidgets.QPushButton("Auto")
        auto_btn.setCheckable(True)
        auto_btn.setToolTip("Seuils automatiques : chaque fréquence a son propre seuil = son bruit de fond + une marge.\n"
                            "Le bruit est appris en continu (il redescend vite, remonte lentement en 10 min, et ne\n"
                            "remonte jamais pendant qu'une fréquence est occupée). Courbe en tirets sur le spectre.\n"
                            "Un seuil propre à une fréquence (colonne Seuil) reste prioritaire. Décoche = seuils fixes.\n"
                            "Sur un canal TNT, le fond local est la TNT : la courbe monte avec elle (voulu, ❓ explique).")
        auto_btn.toggled.connect(lambda on: self.set_thr_auto(bool(on)))
        self.thr_auto_btn = auto_btn
        self.auto_occ_spin = QtWidgets.QSpinBox()
        self.auto_occ_spin.setRange(3, 40)
        self.auto_occ_spin.setValue(int(AUTO_THR_DEFAULT[0]))
        self.auto_occ_spin.setPrefix("bruit + ")
        self.auto_occ_spin.setSuffix(" dB")
        self.auto_occ_spin.setToolTip("Seuils auto : « occupé » dès que le niveau dépasse le bruit de fond local de cette "
                                      "marge.\nPlus petit = plus sensible (plus de fausses alertes), plus grand = moins "
                                      "sensible.")
        self.auto_weak_spin = QtWidgets.QSpinBox()
        self.auto_weak_spin.setRange(1, 30)
        self.auto_weak_spin.setValue(int(AUTO_THR_DEFAULT[1]))
        self.auto_weak_spin.setPrefix("bruit + ")
        self.auto_weak_spin.setSuffix(" dB")
        self.auto_weak_spin.setToolTip("Seuils auto : « faible » dès que le niveau dépasse le bruit de fond local de "
                                       "cette marge.")
        self.auto_occ_spin.valueChanged.connect(lambda *_: self._auto_margins_changed())
        self.auto_weak_spin.valueChanged.connect(lambda *_: self._auto_margins_changed())
        self.weak_chk = QtWidgets.QCheckBox("Faible dès")
        self.weak_chk.setChecked(True)
        self.weak_spin = LevelSpin()
        self.weak_spin.setRange(-130, 0)
        self.weak_spin.setValue(-90)
        self.weak_spin.valueChanged.connect(self._weak_from_spin)
        self.weak_chk.toggled.connect(self._weak_toggled)
        self.win_spin = QtWidgets.QSpinBox()
        self.win_spin.setRange(10, 2000)
        self.win_spin.setSingleStep(10)
        self.win_spin.setValue(100)
        self.win_spin.setPrefix("± ")
        self.win_spin.setSuffix(" kHz")
        self.win_spin.setToolTip("Fenêtre autour de chaque fréquence (on prend le max)")
        self.alert_chk = QtWidgets.QCheckBox("Alerte sonore")
        self.alert_chk.setChecked(True)
        self.unk_chk = QtWidgets.QCheckBox("Détecter les signaux inconnus")
        self.unk_chk.setToolTip("Signale tout pic au-dessus du seuil qui n'est pas dans ta liste")
        self.unk_chk.setChecked(True)
        self.occ_combo = self._combo([("10 minutes", 10), ("1 heure", 60), ("4 heures", 240), ("12 heures", 720)], 60)
        self.occ_combo.setToolTip("Durée sur laquelle est calculé le taux d'occupation (colonne « Occ. »)")
        self.occ_combo.currentIndexChanged.connect(self.on_occ_window)
        self.ref_chk = QtWidgets.QCheckBox("Seuil = courbe de référence +")
        self.ref_chk.setToolTip("Chaque fréquence est « occupée » quand elle dépasse la référence de cette marge.\n"
                                "Capture d'abord une référence (bouton 📏 Référence) quand le spectre est calme.\n"
                                "Un seuil propre à une fréquence reste prioritaire.")
        self.ref_margin = QtWidgets.QDoubleSpinBox()
        self.ref_margin.setRange(1, 60)
        self.ref_margin.setValue(8)
        self.ref_margin.setPrefix("+ ")
        self.ref_margin.setSuffix(" dB")
        self.ref_chk.toggled.connect(self.reeval)
        self.ref_margin.valueChanged.connect(self.reeval)
        self.absent_spin = QtWidgets.QSpinBox()
        self.absent_spin.setRange(3, 3600)
        self.absent_spin.setValue(20)
        self.absent_spin.setSuffix(" s")
        self.absent_spin.setToolTip("Une fréquence au statut « Doit émettre » sans signal pendant ce délai déclenche\n"
                                    "⚠ ABSENT (micro éteint, pile vide, TX coupé…). Jamais moins de 2 cycles de balayage.")
        dbox = QtWidgets.QGroupBox("Seuils : quand est-ce occupé ?")
        dform = QtWidgets.QFormLayout(dbox)
        self.unit_combo = self._combo([(t, k) for k, t in LEVEL_UNITS], "dbm")
        self.unit_combo.setToolTip("Unité des niveaux partout (seuils, liste, mur, spectre, alarmes, page web).\n"
                                   "dBµV = dBm + 107 (50 Ω). % = échelle Sennheiser WSM : 0 % = −120 dBm, 100 % = 0 dBm.\n"
                                   "Les fichiers (journal CSV, shows, exports) restent en dBm.")
        self.unit_combo.currentIndexChanged.connect(lambda *_: self.set_unit(self.unit_combo.currentData()))
        dform.addRow("Unité des niveaux :", self.unit_combo)
        dform.addRow(self.ref_chk)
        dform.addRow("", self.ref_margin)
        dform.addRow("Fenêtre :", self.win_spin)
        dform.addRow("Occupation sur :", self.occ_combo)
        abox = QtWidgets.QGroupBox("Alarmes")
        aform = QtWidgets.QFormLayout(abox)
        self.strong_chk = QtWidgets.QCheckBox("Alerte « trop fort » au-dessus de")
        self.strong_chk.setChecked(True)
        self.strong_chk.setToolTip(
            "Un signal très fort (talkie collé à l'antenne, burst, émetteur trop près, intermod) peut saturer les\n"
            "récepteurs et faire décrocher les liaisons : alarme ⚠ TROP FORT dès qu'un signal des bandes balayées\n"
            "dépasse ce niveau (ligne violette sur le spectre). Le tinySA lui-même sature vers −10 dBm.")
        self.strong_spin = LevelSpin()
        self.strong_spin.setRange(-80.0, 10.0)
        self.strong_spin.setValue(-25.0)
        self.strong_spin.setToolTip(self.strong_chk.toolTip())
        for w_ in (self.strong_chk, self.strong_spin):
            (w_.toggled if w_ is self.strong_chk else w_.valueChanged).connect(lambda *_: self._strong_changed())
        aform.addRow(self.strong_chk)
        aform.addRow("", self.strong_spin)
        aform.addRow(self.alert_chk)
        aform.addRow(self.unk_chk)
        b_logwhat = QtWidgets.QPushButton("📝 Quoi noter au journal…")
        b_logwhat.setToolTip("Les types d'événements notés au journal (onglet Journal).")
        b_logwhat.clicked.connect(lambda *_: self.logwhat_menu.exec(QtGui.QCursor.pos()))
        aform.addRow(b_logwhat)

        self.country_combo = self._combo([(name, code) for code, name in COUNTRIES], "FR")
        self.country_combo.currentIndexChanged.connect(self.on_country)
        # 7.58.3 : choisi À LA MAIN (pas au chargement d'une config) -> la bande UHF suit le pays, comme pour un show
        self.country_combo.activated.connect(lambda *_: self.set_show_country(self.country_combo.currentData() or "FR"))
        # 7.60 (audit : « séparer balayé / autorisé / occupé ») : secours et coordination restent dans les plages autorisées
        self.reg_only = True
        self.reg_chk = QtWidgets.QCheckBox("Secours et coordination : seulement dans les bandes autorisées du pays")
        self.reg_chk.setChecked(True)
        self.reg_chk.setToolTip("Les fréquences proposées (secours, coordination, Vérifier le plan) restent dans les\n"
                                "plages où un micro peut émettre d'après la note du pays (indicatif).\n"
                                "La plage BALAYÉE peut être plus large : mesurer n'est pas émettre.")
        self.reg_chk.toggled.connect(lambda on: setattr(self, "reg_only", bool(on)))
        self.reg_lbl = QtWidgets.QLabel("")
        self.reg_lbl.setWordWrap(True)
        self.alloc_chk = QtWidgets.QCheckBox("Attributions (4G/5G, TNT, militaire…)")
        self.alloc_chk.setChecked(True)
        self.tv_chk = QtWidgets.QCheckBox("Canaux TV")
        self.tv_chk.setChecked(True)
        self.alloc_chk.toggled.connect(self.update_strips)
        self.tv_chk.toggled.connect(self.update_strips)
        plan_btn = QtWidgets.QPushButton("Éditer le plan…")
        plan_btn.setToolTip("Corrige ou complète les attributions de ce pays (elles sont indicatives).")
        plan_btn.clicked.connect(self.edit_plan)
        guide_btn = QtWidgets.QPushButton("📖 Guide des bandes…")
        guide_btn.setToolTip("À quoi correspond chaque bande entre 100 kHz et 5,9 GHz ? Police, pompiers, aéro,\n"
                             "marine, 4G/5G, CB, PMR, amateur, satellites, radars… avec recherche, zoom\n"
                             "et ajout aux bandes à balayer.")
        guide_btn.clicked.connect(self.open_guide)
        self.country_note = QtWidgets.QLabel("")
        self.country_note.setWordWrap(True)
        self.legend_lbl = QtWidgets.QLabel("")
        self.legend_lbl.setWordWrap(True)
        self.legend_lbl.setTextFormat(Qt.TextFormat.RichText)
        pbox = QtWidgets.QGroupBox("Pays et plan de fréquences")
        pform = QtWidgets.QFormLayout(pbox)
        pform.addRow("Pays :", self.country_combo)
        pform.addRow(self.alloc_chk)
        pform.addRow(self.tv_chk)
        pform.addRow(guide_btn)
        pform.addRow(plan_btn)
        pform.addRow(self.country_note)
        pform.addRow(self.reg_lbl)
        pform.addRow(self.reg_chk)
        pform.addRow(self.legend_lbl)

        bbox = QtWidgets.QGroupBox("Bandes à balayer")
        bl = QtWidgets.QVBoxLayout(bbox)
        self.band_table = QtWidgets.QTableWidget(0, 6)
        self.band_table.setHorizontalHeaderLabels(["Bande", "Début MHz", "Fin MHz", "Points", "Pas kHz", "tinySA"])
        self.band_table.horizontalHeaderItem(5).setToolTip(
            "Quel tinySA balaye la bande (2ᵉ tinySA activé). Double-clic : Auto → 1 → 2.\n"
            "Auto = répartition équilibrée. Si un appareil décroche, l'autre reprend toutes les bandes.")
        self.band_table.cellDoubleClicked.connect(self.on_band_dbl)
        self.band_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.band_table.verticalHeader().setVisible(False)
        self.band_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.band_table.setMinimumHeight(150)
        self.band_table.itemChanged.connect(self.on_band_edit)
        bl.addWidget(self.band_table)
        b_add = QtWidgets.QPushButton("＋ Bande")
        b_add.clicked.connect(lambda: self.add_band("Nouvelle bande", 470.0, 608.0, 200.0))
        b_del = QtWidgets.QPushButton("Supprimer")
        b_del.clicked.connect(self.del_band)
        b_cut = QtWidgets.QPushButton("✂ Couper")
        b_cut.setToolTip("Coupe la bande sélectionnée en deux moitiés : avec deux tinySA, chacun en balaye une\n"
                         "(une seule grosse bande ne se partage pas).")
        b_cut.clicked.connect(lambda *_: self.cut_band())
        bl.addLayout(self._row(b_add, b_del, b_cut))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItem("➕ Ajouter un préréglage…")
        for p in BAND_PRESETS:
            self.preset_combo.addItem(p[0], p)
        self.preset_combo.activated.connect(self.on_preset)
        bl.addWidget(self.preset_combo)

        self.expert_hint = QtWidgets.QPushButton("🎛 Mode simple : afficher tous les réglages")
        self.expert_hint.setFlat(True)
        self.expert_hint.setToolTip("Le mode expert montre aussi RBW, entrée, LNA, atténuateur, offset, segments,\n"
                                    "fenêtre, seuil sur référence, calibration, relais… (☰ Plus › Mode expert).")
        self.expert_hint.clicked.connect(lambda *_: self.set_level("simple" if self.expert else "expert"))
        self.sections = {}
        dev2_box = self._build_dev2_box()
        # 7.28 (Clément : « trop fouillis, usine à gaz ») : plus de panneau Réglages à gauche. Ces réglages sont des
        # pages de ⚙ Réglages (SettingsDialog les emprunte à l'ouverture et les rend à la fermeture : les widgets
        # vivent toujours ici) ; les 3 seuils du direct sont dans la barre au-dessus du spectre (thr_bar).
        thr_note = QtWidgets.QLabel("Les seuils « occupé », « faible » et « TX absent » se règlent dans la barre "
                                    "au-dessus du spectre.")
        thr_note.setWordWrap(True)
        self.set_park = QtWidgets.QWidget(self)
        self.set_park.hide()
        QtWidgets.QVBoxLayout(self.set_park)
        self.set_pages = {}
        for key, widgets in (("detect", (thr_note, dbox, abox)), ("bands", (bbox,)),
                             ("measure", (self.expert_hint, mbox)), ("dev2", (dev2_box,)), ("country", (pbox,))):
            inner = QtWidgets.QWidget()
            iv = QtWidgets.QVBoxLayout(inner)
            iv.setContentsMargins(4, 4, 4, 4)
            for w_ in widgets:
                iv.addWidget(w_, 1 if w_ is bbox else 0)
            if key != "bands":
                iv.addStretch(1)
            page = QtWidgets.QScrollArea()
            page.setWidgetResizable(True)
            page.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            page.setWidget(inner)
            self.set_park.layout().addWidget(page)
            self.set_pages[key] = page
        self._expert_rows = [(mform, w_) for w_ in (self.rbw_combo, self.zrbw_combo, self.zpts_combo, self.input_combo, self.lna_combo,
                                                   self.att_combo, self.offset_spin, self.seg_combo, self.baud_combo)]
        self._expert_rows += [(dform, w_) for w_ in (self.ref_chk, self.ref_margin, self.win_spin, self.occ_combo)]
        self._expert_rows += [(aform, self.unk_chk)]
        self._expert_rows += [(self._dev2_form, w_) for w_ in (self.dev2_off, self.calib_btn, self.relay_btn)]
        self._expert_rows += [(pform, plan_btn)]

        # --- centre : graphiques
        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.setMinimumWidth(170)
        self.view_combo.currentIndexChanged.connect(self.on_view_changed)
        self.pts_btn = QtWidgets.QToolButton()
        self.pts_btn.setText("⚡ Points")
        self.pts_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.pts_btn.setToolTip("Points par balayage : ⚡ Auto (le pas suit la largeur totale des bandes : rapide,\n"
                                "équilibré ou détaillé) ou un nombre fixe. Plus de points = plus fin, mais plus lent.")
        self.pts_menu = QtWidgets.QMenu(self.pts_btn)
        self.pts_menu.aboutToShow.connect(self._build_pts_menu)
        self.pts_btn.setMenu(self.pts_menu)
        self.bands_btn = QtWidgets.QToolButton()
        self.bands_btn.setText("📶 Bandes")
        self.bands_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bands_btn.setToolTip("Quelles bandes le tinySA balaye : toutes, seulement certaines (cocher / décocher),\n"
                                  "ou seulement celle affichée dans « Vue ». Moins de bandes = cycle plus rapide.")
        self.bands_menu = QtWidgets.QMenu(self.bands_btn)
        self.bands_menu.aboutToShow.connect(self._build_bands_menu)
        self.bands_btn.setMenu(self.bands_menu)
        self.zoom_btn = QtWidgets.QPushButton("🔍 Zoom live")
        self.zoom_btn.setCheckable(True)
        self.zoom_btn.setToolTip("Le tinySA ne scanne plus que la zone visible, avec le nombre de points choisi.\n"
                                 "Zoome / déplace-toi sur le graphique : le scan suit.")
        self.zoom_btn.toggled.connect(self.toggle_zoom)
        self.names_chk = QtWidgets.QCheckBox("Noms")
        self.names_chk.setChecked(True)
        self.names_chk.toggled.connect(lambda *_: self._update_markers())
        self.hold_chk = QtWidgets.QCheckBox("Max hold")
        self.hold_chk.setChecked(True)
        self.mark_combo = self._combo([("Repères : état du signal", "signal"), ("Repères : statut manuel", "status"),
                                       ("Repères : couleur du groupe", "group")])
        self.mark_combo.currentIndexChanged.connect(lambda *_: self._update_markers())
        self.mk_btn = QtWidgets.QPushButton("📍 Repères")
        self.mk_btn.setToolTip("Repères des fréquences sur le spectre : lesquels afficher, noms, style, couleur.\n"
                               "Ctrl+M : tout masquer / réafficher.")
        self.mk_menu = QtWidgets.QMenu(self.mk_btn)
        self.mk_btn.setMenu(self.mk_menu)
        self.mk_menu.aboutToShow.connect(lambda *_: self._build_mk_menu())
        sc_mk = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+M"), self)
        sc_mk.activated.connect(lambda *_: self.toggle_markers())
        self.persist_combo = self._combo([("Rémanence : aucune", 0), ("Rémanence : 3 balayages", 3),
                                          ("Rémanence : 5 balayages", 5), ("Rémanence : 10 balayages", 10),
                                          ("Rémanence : 20 balayages", 20)])
        self.persist_combo.setToolTip("Rémanence façon analyseur : les anciens balayages restent à l'écran en lueur.\n"
                                      "Ce qui revient à chaque balayage brille, un signal passager laisse une trace pâle.")
        self.persist_combo.currentIndexChanged.connect(lambda *_: self.update_plot())
        reset_btn = QtWidgets.QPushButton("Reset max")
        reset_btn.clicked.connect(self.reset_max)
        self.reset_btn = reset_btn
        cap_btn = QtWidgets.QPushButton("📷 Capture")
        cap_btn.clicked.connect(self.capture)
        self.legend_btn = QtWidgets.QPushButton("❓ Courbes")
        self.legend_btn.setToolTip("Ce que montre chaque courbe et ligne du spectre (direct, max hold, référence, "
                                   "seuils, trop fort, repères) et leurs réglages.")
        self.legend_btn.clicked.connect(lambda *_: self.open_spectrum_legend())
        self.sites_btn = QtWidgets.QToolButton()
        self.sites_btn.setText("📡 Scènes")
        self.sites_btn.setCheckable(True)
        self.sites_btn.setChecked(True)
        self.sites_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.sites_btn.setToolTip("Spectre par scène : dis quel tinySA surveille quelle(s) scène(s) (flèche ▾) ; clique une\n"
                                  "scène dans « Mes fréquences » pour voir SON spectre (en direct si un tinySA la surveille,\n"
                                  "sinon son dernier spectre gardé). Global : tout. Clic sur le bouton = afficher / cacher.")
        self.sites_menu = QtWidgets.QMenu(self.sites_btn)
        self.sites_menu.aboutToShow.connect(self._build_sites_menu)
        self.sites_btn.setMenu(self.sites_menu)
        self.sites_btn.toggled.connect(lambda *_: (self.update_site_curve(), self.update_plot()))
        self.mkr_btn = QtWidgets.QPushButton("🎯 Marqueurs")
        self.mkr_btn.setCheckable(True)
        self.mkr_btn.setToolTip("Marqueurs déplaçables M1 / M2 : fréquence au kHz près (saisie, molette, flèches),\n"
                                "niveau, « ⤒ Pic », écart M1 → M2, largeur occupée.")
        self.mkr_btn.toggled.connect(lambda on: self.show_markers_bar(on))
        ref_btn = QtWidgets.QPushButton("📏 Référence")
        ref_btn.setToolTip("Courbe de référence (spectre calme / bruit de fond du lieu), affichée en pointillés.")
        rmenu = QtWidgets.QMenu(ref_btn)
        for txt, fn in (("Capturer : balayage actuel", lambda: self.capture_ref("live")),
                        ("Capturer : max hold", lambda: self.capture_ref("max")),
                        (None, None),
                        ("Enregistrer sous…", self.save_ref_as),
                        ("Charger…", self.load_ref_dialog),
                        ("Importer un scan WSM / WWB…", self.import_scan_as_ref),
                        (None, None),
                        ("Effacer la référence", self.clear_ref)):
            if txt is None:
                rmenu.addSeparator()
            else:
                rmenu.addAction(txt).triggered.connect(fn)
        ref_btn.setMenu(rmenu)
        self.showref_chk = QtWidgets.QCheckBox("Afficher")
        self.showref_chk.setChecked(True)
        self.showref_chk.toggled.connect(lambda *_: self.update_ref_curve())
        exp_btn = QtWidgets.QPushButton("💾 Exporter le scan…")
        exp_btn.clicked.connect(self.export_scan)
        self.band_lbl = QtWidgets.QLabel("Survole le spectre ou les bandeaux pour voir le canal TV et "
                                         "l'attribution de la fréquence.")
        self._elastic(self.band_lbl)                 # une seule ligne, coupée si besoin : le spectre garde la place
        self.band_lbl.setStyleSheet("color: #8e8e93;")   # 8.1 : indication discrète (le texte devient l'info au survol)
        self.readout = QtWidgets.QLabel("")
        self.readout.setMinimumWidth(210)
        self.readout.setStyleSheet("font-family:Consolas,monospace;")

        self.spec = pg.PlotWidget(axisItems={"left": LevelAxis(orientation="left")})
        pi = self.spec.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "Fréquence", units="MHz")
        pi.setLabel("left", "Niveau (dBm)")
        pi.setYRange(-120, -10, padding=0)
        pi.getAxis("left").setWidth(65)
        pi.getAxis("bottom").enableAutoSIPrefix(False)
        pi.getAxis("left").enableAutoSIPrefix(False)
        self.refcurve = pi.plot(pen=pg.mkPen(self.theme["ref"], width=1.3, style=Qt.PenStyle.DashLine),
                                connect="finite")
        self.sitecurve = pg.PlotCurveItem(connect="finite")      # 📍 scan gardé du lieu choisi (ou fusion en Global)
        pi.addItem(self.sitecurve, ignoreBounds=True)
        self.site_lbl = pg.TextItem("", anchor=(0, 0), fill=pg.mkBrush(0, 0, 0, 150))
        self.site_lbl.setZValue(60)
        self.site_lbl.setVisible(False)
        pi.addItem(self.site_lbl, ignoreBounds=True)
        self.maxcurve = pi.plot(pen=pg.mkPen(self.theme["maxhold"], width=1), connect="finite")
        self.curve = pi.plot(pen=pg.mkPen(self.theme["curve"], width=1.6), connect="finite")
        for c_ in (self.refcurve, self.maxcurve, self.curve):
            # fluidité : on ne dessine que la partie visible, réduite à ~1 point par pixel en gardant les pics
            # (sans ça : des milliers de points anti-crénelés redessinés à chaque déplacement de fenêtre)
            c_.setClipToView(True)
            c_.setDownsampling(auto=True, method="peak")
        self.thr_line = pg.InfiniteLine(pos=-80, angle=0, movable=True,
                                        pen=pg.mkPen(self.theme["thr"], width=1.5, style=Qt.PenStyle.DashLine))
        self.thr_line.sigPositionChanged.connect(self._thr_from_line)
        self.weak_line = pg.InfiniteLine(pos=-90, angle=0, movable=True,
                                         pen=pg.mkPen(self.theme["thr_weak"], width=1.2, style=Qt.PenStyle.DotLine))
        self.weak_line.sigPositionChanged.connect(self._weak_from_line)
        pi.addItem(self.thr_line)
        pi.addItem(self.weak_line)
        self.auto_curve = pg.PlotDataItem(pen=pg.mkPen(self.theme["thr"], width=1.3, style=Qt.PenStyle.DashLine), connect="finite")
        self.auto_curve.setVisible(False)
        pi.addItem(self.auto_curve, ignoreBounds=True)
        self.strong_line = pg.InfiniteLine(pos=-25, angle=0, movable=False,
                                           pen=pg.mkPen("#b06cff", width=1.4, style=Qt.PenStyle.DashDotLine))
        pi.addItem(self.strong_line)
        self.proxy = pg.SignalProxy(self.spec.scene().sigMouseMoved, rateLimit=30, slot=self.on_mouse)
        self._ovl_timer = QtCore.QTimer(self)
        self._ovl_timer.setSingleShot(True)
        self._ovl_timer.setInterval(40)
        self._ovl_timer.timeout.connect(self._update_markers)
        self._ovl_timer.timeout.connect(self.update_strip_labels)
        pi.vb.sigXRangeChanged.connect(lambda *a: self._ovl_timer.start())
        pi.vb.sigYRangeChanged.connect(lambda *a: self._ovl_timer.start())   # repères « discrets » collés en haut
        self.zoom_timer = QtCore.QTimer(self)
        self.zoom_timer.setInterval(500)
        self.zoom_timer.timeout.connect(self.zoom_follow)

        self.wf = pg.PlotWidget()
        wi = self.wf.getPlotItem()
        wi.invertY(True)
        wi.setMouseEnabled(x=True, y=False)
        wi.setXLink(pi)
        wi.getAxis("left").setWidth(65)
        wi.setLabel("left", "temps")
        wi.getAxis("bottom").enableAutoSIPrefix(False)
        self.wf_img = pg.ImageItem()
        wi.addItem(self.wf_img)
        self.wf.setVisible(False)

        # bandeaux : attributions du spectre + canaux TV (alignés sur l'axe des fréquences)
        self.bandw = pg.PlotWidget()
        bi = self.bandw.getPlotItem()
        bi.hideButtons()
        bi.setMenuEnabled(False)
        bi.vb.setMenuEnabled(False)
        bi.setMouseEnabled(x=True, y=False)
        bi.setXLink(pi)
        bi.hideAxis("bottom")
        bi.getAxis("left").setWidth(65)
        bi.getAxis("left").setStyle(showValues=False, tickLength=0)
        bi.setYRange(0, 2, padding=0)
        self.bandw.setFixedHeight(62)
        bi.vb.sigResized.connect(lambda *a: self._ovl_timer.start())
        self.bandw_proxy = pg.SignalProxy(self.bandw.scene().sigMouseMoved, rateLimit=30, slot=self.on_mouse_band)

        self.wf_hint = QtWidgets.QLabel("Choisis une bande dans « Vue » (ou active le zoom live) "
                                        "pour voir le waterfall.")
        self.wf_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wf_hint.setWordWrap(True)
        self.wf_box = QtWidgets.QWidget()
        wfl = QtWidgets.QVBoxLayout(self.wf_box)
        wfl.setContentsMargins(0, 0, 0, 0)
        wfl.addWidget(self.wf_hint)
        wfl.addWidget(self.wf, 1)
        center = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(center)
        cl.setContentsMargins(6, 4, 6, 0)
        # barre du spectre allégée (7.28) : l'essentiel, le reste derrière « ⋯ »
        self.ref_row = QtWidgets.QWidget()
        rl = self._row("Référence :", ref_btn, self.showref_chk, exp_btn)
        rl.setContentsMargins(0, 0, 0, 0)
        self.ref_row.setLayout(rl)
        self.spec_more = QtWidgets.QWidget()
        sml = self._flow(self.mk_btn, self.mkr_btn, self.persist_combo, cap_btn, self.sites_btn, self.legend_btn,
                         self.ref_row)
        sml.setContentsMargins(0, 0, 0, 0)
        self.spec_more.setLayout(sml)
        self.spec_more.setVisible(False)
        self.more_spec_btn = QtWidgets.QToolButton()
        self.more_spec_btn.setText("⋯")
        self.more_spec_btn.setCheckable(True)
        self.more_spec_btn.setToolTip("Plus d'outils du spectre : repères, marqueurs M1 / M2, rémanence, capture, "
                                      "légende des courbes,\ncourbe de référence (mode expert).")
        self.more_spec_btn.toggled.connect(lambda *_: self.spec_more.setVisible(self.more_spec_btn.isChecked()))
        cl.addLayout(self._flow(("Vue :", self.view_combo), self.bands_btn, self.pts_btn, self.zoom_btn, self.hold_chk,
                                reset_btn, self.more_spec_btn, self.readout))
        cl.addWidget(self.spec_more)
        cl.addWidget(self._build_markers_bar())
        cl.addWidget(self.band_lbl)
        self.site_bar = QtWidgets.QFrame()          # 📡 « aucun tinySA ne surveille cette scène » + boutons
        self.site_bar.setStyleSheet("QFrame { background:#3a2a00; border:1px solid #d29922; border-radius:4px; }")
        sbl = QtWidgets.QHBoxLayout(self.site_bar)
        sbl.setContentsMargins(8, 3, 8, 3)
        self.site_bar_lbl = QtWidgets.QLabel("")
        self.site_bar_lbl.setWordWrap(True)
        self.site_bar_lbl.setStyleSheet("border:0")
        sbl.addWidget(self.site_bar_lbl, 1)
        self.site_bar_btns = QtWidgets.QHBoxLayout()
        sbl.addLayout(self.site_bar_btns)
        self.site_bar.setVisible(False)
        cl.addWidget(self.site_bar)
        # les 3 seuils du direct, toujours sous la main (le reste : ⚙ Réglages › Seuils et alarmes)
        thr_set = QtWidgets.QToolButton()
        thr_set.setText("⚙")
        thr_set.setAutoRaise(True)
        thr_set.setToolTip("Tous les réglages des seuils et des alarmes (⚙ Réglages).")
        thr_set.clicked.connect(lambda *_: self.open_settings("detect"))
        auto_help = QtWidgets.QToolButton()
        auto_help.setText("❓")
        auto_help.setAutoRaise(True)
        auto_help.setToolTip("Comment marche le seuil auto (et pourquoi la courbe monte sur la TNT).")
        auto_help.clicked.connect(lambda *_: self.show_auto_thr_help())
        self.auto_help_btn = auto_help
        self.thr_bar = QtWidgets.QWidget()
        tl = self._flow(("Occupé au-dessus de", self.thr_spin, self.auto_occ_spin, auto_btn, auto_help),
                        (self.weak_chk, self.weak_spin, self.auto_weak_spin),
                        ("TX absent après", self.absent_spin), thr_set)
        tl.setContentsMargins(0, 0, 0, 0)
        self.thr_bar.setLayout(tl)
        self.hint_bar = HintBar(self)                     # 7.59 : propositions au bon moment (caché d'office)
        cl.addWidget(self.hint_bar)
        cl.addWidget(self.thr_bar)
        cl.addWidget(self.spec, 1)
        self.spec_legend = SpecLegend(self)               # 7.59 : légende cliquable posée sur le spectre
        cl.addWidget(self.bandw)

        # --- droite : fréquences + journal
        ftab = QtWidgets.QWidget()
        fl = QtWidgets.QVBoxLayout(ftab)
        self.layer_lbl = QtWidgets.QLabel("")
        self.layer_lbl.setWordWrap(True)
        self.global_btn = QtWidgets.QPushButton("🌐 Global")
        self.global_btn.setToolTip("Surveille toutes les fréquences, toutes scènes confondues.")
        self.global_btn.clicked.connect(lambda *_: self.go_global())
        lb_sc = QtWidgets.QPushButton("＋ Scène")
        lb_sc.clicked.connect(lambda *_: self.add_scene())
        lb_gr = QtWidgets.QPushButton("＋ Groupe")
        lb_gr.clicked.connect(lambda *_: self.add_group())
        lb_rn = QtWidgets.QPushButton("✎")
        lb_rn.setToolTip("Renommer la scène / le groupe sélectionné")
        lb_rn.clicked.connect(lambda *_: self.layer_action("rename"))
        lb_dl = QtWidgets.QPushButton("🗑")
        lb_dl.setToolTip("Supprimer la scène / le groupe sélectionné (les fréquences restent dans la liste)")
        lb_dl.clicked.connect(lambda *_: self.layer_action("delete"))
        for b in (lb_rn, lb_dl):
            b.setMaximumWidth(38)
        self.layer_tree = QtWidgets.QTreeWidget()
        self.layer_tree.setHeaderHidden(True)
        self.layer_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.layer_tree.setMinimumHeight(46)
        self.layer_tree.itemSelectionChanged.connect(self.on_tree_sel)
        self.layer_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layer_tree.customContextMenuRequested.connect(self.layer_menu)
        self.focus_chk = QtWidgets.QCheckBox("🎯 Scanner seulement la sélection")
        self.focus_chk.setToolTip("Le tinySA ne balaye plus que les petites zones autour des fréquences de la couche\n"
                                  "active (au lieu de toutes tes bandes) : cycles beaucoup plus rapides, donc\n"
                                  "détection plus réactive. Inactif en mode Global.")
        self.focus_chk.toggled.connect(self._on_focus_toggled)
        lbox = QtWidgets.QGroupBox("Classer par scène › groupe (facultatif)")
        lbox.setToolTip("Comme des dossiers, pour s'y retrouver avec beaucoup de fréquences :\n"
                        "• une SCÈNE = un lieu ou un plateau (Grande scène, Club, Plateau TV…)\n"
                        "• un GROUPE = un artiste ou un type de matériel (HF chant, Ears batterie…)\n"
                        "Clic sur un groupe = on ne surveille que lui ; 🌐 Global = tout.\n"
                        "Pas obligatoire : tout marche sans (mode ultra simple : caché).")
        self.layer_box = lbox
        lv2 = QtWidgets.QVBoxLayout(lbox)
        lv2.setContentsMargins(6, 4, 6, 4)
        for b_ in (self.global_btn, lb_sc, lb_gr, lb_rn, lb_dl):      # rétrécissables : le spectre d'abord
            b_.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, b_.sizePolicy().verticalPolicy())
            b_.setMinimumWidth(30)
        lv2.addLayout(self._row(self.global_btn, lb_sc, lb_gr, lb_rn, lb_dl))
        lv2.addWidget(self.layer_tree)
        lv2.addWidget(self.focus_chk)
        lv2.addWidget(self.layer_lbl)
        layer_tip = QtWidgets.QLabel("Clic sur un groupe = on ne surveille que lui · Ctrl+clic = plusieurs · "
                                     "🌐 Global = tout. Clic droit : importer un CSV dans le groupe, renommer, "
                                     "couleur. Clic droit sur une fréquence ou double-clic sur « Scène › Groupe » "
                                     "pour l'affecter.")
        layer_tip.setToolTip(layer_tip.text())
        layer_tip.setText("ⓘ Clic = surveiller ce groupe · Ctrl+clic = plusieurs · clic droit = menu (survole pour l'aide)")
        layer_tip.setWordWrap(True)
        lbox.setToolTip(lbox.toolTip() + "\n\n" + layer_tip.toolTip())      # 8.1 : l'aide en bulle, pas en ligne fixe
        layer_tip.hide()
        # un QSplitter ignore la hauteur réelle des textes repliés : on la réserve (sinon chevauchements)
        lh = self.fontMetrics().lineSpacing()
        for lab, n in ((self.layer_lbl, 1), (layer_tip, 2)):
            lab.setMinimumHeight(lh * n + 4)
        # couches et table dans un séparateur : la table garde la place, la poignée se tire à la souris
        wbox = QtWidgets.QWidget()
        outer = fl
        fl = QtWidgets.QVBoxLayout(wbox)
        fl.setContentsMargins(0, 0, 0, 0)
        self.freq_split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.freq_split.setObjectName("freq_split")
        self.freq_split.setChildrenCollapsible(False)
        self.freq_split.addWidget(lbox)
        self.freq_split.addWidget(wbox)
        self.freq_split.setStretchFactor(0, 0)
        self.freq_split.setStretchFactor(1, 1)
        self.freq_split.setSizes([230, 600])
        outer.addWidget(self.freq_split, 1)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("🔎 Rechercher un nom, une fréquence, un statut…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.occ_only_chk = QtWidgets.QCheckBox("Occupées seulement")
        self.occ_only_chk.toggled.connect(self.apply_filter)
        fl.addLayout(self._row(self.filter_edit, self.occ_only_chk))
        self.count_lbl = self._elastic(QtWidgets.QLabel(""))
        fl.addWidget(self.count_lbl)
        r1, r2 = QtWidgets.QHBoxLayout(), QtWidgets.QHBoxLayout()
        self._plain_btns = []                  # boutons secondaires : emoji retiré après les bulles (7.28)
        # libellés courts (le panneau doit pouvoir rétrécir pour laisser la place au spectre) ; détail en bulle
        for txt, tip, fn, lay in [
                ("＋ Ajouter", "Ajoute des micros : tape ou colle « HF1 558.2, HF2 574… » (dans la couche active).", self.add_watch_dialog, r1),
                ("📥 Importer", "Importe une liste de fréquences (EazyRF, WWB, WSM, Excel…). Tu peux aussi glisser\n"
                               "le fichier sur la fenêtre.", self.import_watch, r1),
                ]:
            b = QtWidgets.QPushButton(txt)
            b.setToolTip(tip)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, b.sizePolicy().verticalPolicy())
            b.setMinimumWidth(40)
            b.clicked.connect(fn)
            lay.addWidget(b)
            self._plain_btns.append(b)
        self.state_btn = QtWidgets.QToolButton()
        self.state_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.state_btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, self.state_btn.sizePolicy().verticalPolicy())
        self.state_btn.setToolTip("📸 État actif : un clic pour basculer de plan.\n"
                                  "Les fréquences hors de l'état passent en pause (pas d'alarme, pas d'intermod).")
        self.state_menu = QtWidgets.QMenu(self.state_btn)
        self.state_menu.aboutToShow.connect(self._build_state_menu)
        self.state_btn.setMenu(self.state_menu)
        r1.addWidget(self.state_btn)
        self._update_state_btn()
        self.list_more = QtWidgets.QToolButton()            # 8.1 (DA épurée) : une seule rangée, le reste ici
        self.list_more.setText("⋯")
        self.list_more.setToolTip("Plus d'actions sur la liste : coller, exporter, supprimer, bandes, astuces.")
        self.list_more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        lm = QtWidgets.QMenu(self.list_more)
        lm.setToolTipsVisible(True)
        for txt, tip, fn in (("📋 Coller une liste", "Colle une liste copiée (Excel, mail…) : nom et fréquence par ligne.",
                              self.paste_watch),
                             ("📤 Exporter la liste", "Exporte ta liste de fréquences (CSV).", self.export_watch),
                             ("🗑 Supprimer la sélection  (Suppr)", "Supprime la ou les lignes sélectionnées.", self.del_watch),
                             ("↔ Bandes d'après la liste", "Remplace les bandes par des zones qui couvrent juste tes\n"
                              "fréquences (scan plus rapide).", self.bands_from_list),
                             ("❓ Astuces de la liste", "Raccourcis et doubles-clics de la liste.", self.list_tips)):
            a_ = lm.addAction(txt)
            a_.setToolTip(tip)
            a_.triggered.connect(lambda *_, fn=fn: fn())
        self.list_more.setMenu(lm)
        r1.addWidget(self.list_more)
        fl.addLayout(r1)
        self.watch_table = QtWidgets.QTableWidget(0, len(WATCH_HEADERS))
        self.watch_table.setHorizontalHeaderLabels(WATCH_HEADERS)
        for c, tip in ((C_THR, "Seuil propre à cette fréquence (dBm). Double-clic pour le modifier ; "
                               "vide = seuil global."),
                       (C_OCC, "Taux d'occupation sur la durée choisie dans « Détection »."),
                       (C_LAYER, "Scène et groupe de cette fréquence. Double-clic pour l'affecter."),
                       (C_BAND, "Canal TV et attribution du spectre à cette fréquence (selon le pays)."),
                       (C_MARG, "De combien le signal dépasse le bruit de fond autour de lui (dB).\n≥ 20 très bon · "
                                "≥ 10 correct · 6 à 10 juste · moins : noyé dans le bruit.")):
            self.watch_table.horizontalHeaderItem(c).setToolTip(tip)
        # le nom ne s'étire pas (sinon Signal / Statut sortent de la vue quand le panneau est étroit) : la dernière
        # colonne (attribution) prend la place restante
        self.watch_table.horizontalHeader().setSectionResizeMode(C_NAME, QtWidgets.QHeaderView.ResizeMode.Interactive)
        self.watch_table.setColumnWidth(C_NAME, 100)
        self.watch_table.horizontalHeader().setStretchLastSection(True)
        # ce qu'on lit d'abord : Nom, MHz, Signal, Statut ; colonnes déplaçables à la souris (ordre mémorisé)
        hh_ = self.watch_table.horizontalHeader()
        hh_.setSectionsMovable(True)
        hh_.moveSection(hh_.visualIndex(C_SIG), 2)
        hh_.moveSection(hh_.visualIndex(C_STAT), 3)
        hh_.moveSection(hh_.visualIndex(C_MARG), 4)
        for c, w in ((C_FREQ, 64), (C_LVL, 56), (C_MAX, 56), (C_THR, 56), (C_SIG, 78), (C_STAT, 84),
                     (C_OCC, 48), (C_LAYER, 120), (C_BAND, 190), (C_MARG, 58)):
            self.watch_table.setColumnWidth(c, w)
        self.watch_table.verticalHeader().setVisible(False)
        self.watch_table.setWordWrap(False)
        self.watch_table.setMinimumHeight(84)
        self.watch_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.watch_table.itemChanged.connect(self.on_watch_edit)
        self.watch_table.cellDoubleClicked.connect(self.on_watch_dbl)
        self.watch_table.itemSelectionChanged.connect(self._on_watch_sel)
        self.watch_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.watch_table.customContextMenuRequested.connect(self.watch_menu)
        sc_mu = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Space"), self.watch_table)
        sc_mu.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_mu.activated.connect(lambda *_: self.toggle_muted_sel())
        self.watch_table.setItemDelegateForColumn(C_NAME, NameDelegate(self))
        sc_fill = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+D"), self.watch_table)
        sc_fill.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_fill.activated.connect(lambda *_: self.fill_down_names())
        # statut de la sélection au clavier : Ctrl+1…9 = statut n° 1…9, Ctrl+0 = aucun, Ctrl+E = « doit émettre »
        for key, which in [(f"Ctrl+{n}", n - 1) for n in range(1, 10)] + [("Ctrl+0", None), ("Ctrl+E", "on")]:
            sc_ = QtGui.QShortcut(QtGui.QKeySequence(key), self.watch_table)
            sc_.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc_.activated.connect(lambda *_, w_=which: self.quick_status(w_))
        fl.addWidget(self.watch_table, 1)
        tip = QtWidgets.QLabel("Double-clic sur « Statut » : change le statut · sur Niveau / Signal : zoom live · "
                               "sur « Seuil » : seuil propre à la fréquence.\n"
                               "Clic droit : menu complet. Tu peux aussi glisser un CSV sur la fenêtre.\n"
                               "Nom : l'auto-complétion propose MIC, HF 5, IEM… · Ctrl+D numérote vers le bas "
                               "(HF 1, HF 2…).\n"
                               "Statut de la sélection au clavier : Ctrl+E = En service (doit émettre), Ctrl+1…9 = "
                               "statut n° 1…9 (ordre du menu Statut), Ctrl+0 = aucun. Sélection rapide : Maj+clic, "
                               "Ctrl+clic, Ctrl+A.\n"
                               "Un statut « Doit rester libre » déclenche ⚠ CONFLIT si un signal apparaît.")
        tip.setToolTip(tip.text())
        tip.setText("ⓘ Double-clic Statut / Niveau / Seuil · clic droit = menu · Ctrl+E = en service · Ctrl+D numérote "
                    "(survole pour l'aide)")
        tip.setWordWrap(True)
        self._list_tips = tip.toolTip()                     # 8.1 : ⋯ › Astuces de la liste (plus de ligne fixe)
        tip.hide()

        ltab = QtWidgets.QWidget()
        lg = QtWidgets.QVBoxLayout(ltab)
        b1 = QtWidgets.QPushButton("Exporter le journal")
        b1.clicked.connect(self.export_log)
        b2 = QtWidgets.QPushButton("Effacer")
        b2.clicked.connect(lambda: self.log_table.setRowCount(0))
        lg.addLayout(self._row(b1, b2, None))
        self.autolog_chk = QtWidgets.QCheckBox("Journal auto (CSV / jour)")
        self.autolog_chk.setToolTip("Chaque événement est ajouté tout de suite à journal_AAAAMMJJ.csv :\n"
                                    "rien n'est perdu si le logiciel ou l'ordinateur plante.")
        self.autolog_chk.setChecked(True)
        b_dir = QtWidgets.QPushButton("📂 Ouvrir le dossier")
        b_dir.clicked.connect(self.open_log_dir)
        b_pick = QtWidgets.QPushButton("Choisir le dossier…")
        b_pick.clicked.connect(self.pick_log_dir)
        self.logdir_lbl = QtWidgets.QLabel(str(self.log_dir))
        self.logdir_lbl.setWordWrap(True)
        self.logwhat_btn = QtWidgets.QToolButton()
        self.logwhat_btn.setText("📝 Quoi noter…")
        self.logwhat_btn.setToolTip("Choisis ce qui est noté au journal (tableau, CSV du jour, session enregistrée).\n"
                                    "Les alarmes sonnent quand même : seul le journal est filtré.")
        self.logwhat_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.logwhat_menu = QtWidgets.QMenu(self.logwhat_btn)
        self.logwhat_menu.setToolTipsVisible(True)
        self._logwhat_acts = {}
        for k, txt in LOG_KINDS:
            a_ = self.logwhat_menu.addAction(txt)
            a_.setCheckable(True)
            a_.setChecked(True)
            a_.toggled.connect(lambda *_, k=k, a_=a_: self.log_kinds.__setitem__(k, a_.isChecked()))
            self._logwhat_acts[k] = a_
        self.logwhat_btn.setMenu(self.logwhat_menu)
        lg.addWidget(self.autolog_chk)
        lg.addWidget(self.logwhat_btn)
        lg.addLayout(self._row(b_dir, b_pick, None))
        lg.addWidget(self.logdir_lbl)
        self.rec_chk = QtWidgets.QCheckBox("💾 Enregistrer les balayages")
        self.rec_chk.setToolTip("Garde tous les balayages sur disque (un dossier par session, compressé, 2 Go max) pour\n"
                                "revoir le spectre plus tard : 🔧 Outils › ⏪ Relecture. Sans cette case, le logiciel\n"
                                "garde quand même les 30 dernières minutes en mémoire.")
        self.rec_chk.toggled.connect(self.toggle_rec)
        self.rec_lbl = QtWidgets.QLabel("")
        self.rec_lbl.setWordWrap(True)
        self.sess_ask_chk = QtWidgets.QCheckBox("Demander à chaque démarrage")
        self.sess_ask_chk.setChecked(True)
        self.sess_ask_chk.setToolTip("À chaque démarrage : enregistrer tout le scan (spectre + journal) dans le dossier\n"
                                     "de ton choix, pour le revoir après le show (⏪ Relecture › 📂 Ouvrir une session).")
        self.sess_ask_chk.toggled.connect(lambda *_: self.session_cfg.__setitem__("ask", self.sess_ask_chk.isChecked()))
        lg.addWidget(self.rec_chk)
        lg.addWidget(self.sess_ask_chk)
        lg.addWidget(self.rec_lbl)
        self.log_table = QtWidgets.QTableWidget(0, 7)
        self.log_table.setHorizontalHeaderLabels(["Heure", "Nom", "MHz", "dBm", "Événement", "Scène › Groupe", "Note"])
        self.log_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.log_table.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.cellDoubleClicked.connect(self.on_log_dbl)
        self.log_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self.log_menu)
        lg.addWidget(self.log_table, 1)
        tip2 = QtWidgets.QLabel("Double-clic sur un « INCONNU » : l'ajoute à ta liste de fréquences. Clic droit : "
                                "d'où ça peut venir (intermodulation). La colonne Note propose une origine IM3 "
                                "probable quand les émetteurs actifs peuvent l'expliquer.")
        tip2.setWordWrap(True)
        lg.addWidget(tip2)

        # pas de zone centrale fixe : le spectre est un panneau comme les autres (détachable, déplaçable sur
        # l'autre écran, ré-accrochable). Qt exige un widget central : une case vide de taille nulle.
        root = QtWidgets.QWidget()
        root.setMaximumHeight(0)          # seulement la hauteur : la largeur doit suivre la colonne du milieu
        root.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setCentralWidget(root)
        self.setDockNestingEnabled(True)
        self.setAnimated(False)         # panneaux : pas d'animation en les déplaçant (plus réactif, moins saccadé)
        # colonnes Réglages / Fréquences sur toute la hauteur ; spectre, waterfall, alarmes au milieu
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self._build_docks(ftab, ltab, self.wf_box, center)
        for wd_, fn_ in ((self.watch_table, self.del_watch), (self.layer_tree, self.delete_selected_layer),
                         (self.band_table, self.del_band)):
            del_key(wd_, fn_)                      # Suppr = supprimer la sélection (Ctrl+Z pour revenir)
        self._install_tips()
        self._word_tips = {}                      # bulles d'origine relues maintenant qu'elles sont posées
        self._apply_words(getattr(self, "expert", False))
        # emojis seulement sur les boutons clés (7.28, Clément : « trop fouillis ») : les secondaires en texte seul
        for b in getattr(self, "_plain_btns", []):
            b.setText(re.sub(r"^[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]+\s*", "", b.text()))
        # listes déroulantes : ne pas s'élargir au plus long choix (noms de ports COM à rallonge sous Windows…) ;
        # le menu déroulé affiche toujours le texte complet
        for cb in self.findChildren(QtWidgets.QComboBox):
            cb.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(12)

        self.stat_lbl = self._elastic(QtWidgets.QLabel(""))
        self.cycle_lbl = self._elastic(QtWidgets.QLabel(""))
        self.cycle_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addWidget(self.stat_lbl, 3)
        self.statusBar().addPermanentWidget(self.cycle_lbl, 2)
        self.ver_lbl = QtWidgets.QLabel(f" v{APP_VER} ")
        self.ver_lbl.setToolTip(f"{APP_NAME} version {APP_VER} (☰ Plus › À propos pour les détails).")
        self.statusBar().addPermanentWidget(self.ver_lbl)
