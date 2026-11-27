# Labo SDR (RF Compander Lab).
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


# ---- 8.2 : 🧪 Labo SDR / RF Compander Lab (Clément : « j'adoooore l'idée du labo SDR en démo », « comparer les
# compandeurs des marques en live avec phase, EQ et tout ») — un moteur de mesure commun (tsm_core : CompChain,
# measure_*, comp_compare, xfer_spectrum, stair_fit), deux usages : simulé (reproductible) et observé (SDR réel).
LAB_COLORS = ("#64d2ff", "#ff9f0a", "#30d158", "#bf5af2", "#ff453a", "#ffd60a", "#5e5ce6", "#ff375f", "#66d4cf",
              "#ac8e68")


def _lab_plot(title, xl, yl):
    p = pg.PlotWidget()
    p.setTitle(TR(title), size="9pt")
    p.setLabel("bottom", TR(xl))
    p.setLabel("left", TR(yl))
    p.showGrid(x=True, y=True, alpha=0.2)
    sdr_light_axes(p)
    p.addLegend(offset=(6, 6), labelTextSize="8pt")
    p.setMinimumHeight(110)
    p.setMinimumWidth(120)                       # rétrécit avec le panneau au lieu d'être coupé à droite
    p.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
    return p


def _log_hz(p):
    """Axe des fréquences en log, graduations lisibles (50 Hz … 20 kHz)."""
    p.setLogMode(x=True, y=False)
    fs = (50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000)
    p.getAxis("bottom").setTicks([[(math.log10(f), f"{f // 1000}k" if f >= 1000 else str(f)) for f in fs], []])
    p.setXRange(math.log10(50), math.log10(20000), padding=0.0)


def _coh_mask(xf, a, lim=0.6):
    """Valeurs où le son ne permet pas de mesurer (cohérence faible : pas d'énergie à cette fréquence) -> NaN."""
    a = np.asarray(a, dtype=float).copy()
    a[np.asarray(xf["coh"]) < lim] = np.nan
    return a


def _comp_combo(cur="", none_label="Aucun (pas de compresseur)"):
    c = QtWidgets.QComboBox()
    c.addItem(TR(none_label), "")
    for k, v in COMPANDERS.items():
        if k != "none":
            c.addItem(TR(v["name"]), k)
    c.setCurrentIndex(max(0, c.findData(cur)))
    return c


def _model_list(checked=()):
    lw = QtWidgets.QListWidget()
    for k, v in COMPANDERS.items():
        it = QtWidgets.QListWidgetItem(TR(v["name"]))
        it.setData(Qt.ItemDataRole.UserRole, k)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if k in checked else Qt.CheckState.Unchecked)
        card = compander_card(k)
        it.setToolTip(TR(card["maker"]) + " · " + TR(CMP_IMPL[card["impl"]]) + "\n" + TR(card["limits"]))
        lw.addItem(it)
    lw.setMaximumWidth(330)
    return lw


def _checked(lw):
    return [lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lw.count())
            if lw.item(i).checkState() == Qt.CheckState.Checked]


LAB_DOCKS = (("chain", "🧪 Labo · Chaîne complète", "dock_lab_chain"),
             ("cmp", "🧪 Labo · Compandeurs", "dock_lab_cmp"),
             ("live", "🧪 Labo · En direct (SDR)", "dock_lab_live"),
             ("mod", "🧪 Labo · Modulations", "dock_lab_mod"),
             ("fault", "🧪 Labo · Pannes simulées", "dock_lab_fault"))
LAB_KEYS = [k for k, _t, _n in LAB_DOCKS]


class SdrLab(QtCore.QObject):
    """🧪 Labo SDR (RF Compander Lab), en PANNEAUX comme le SDR (Clément : « en full fenêtrage, choisir sur quel écran,
    mettre tout ce qu'on veut où on veut ») : 1. la chaîne complète d'un micro HF pas à pas ; 2. comparateur de
    compandeurs (transfert, transitoires, EQ, phase, rapport) ; 3. en direct (SDR réel = observé, ou SDR démo = simulé) :
    plusieurs modèles en parallèle sur le son reçu, écoute A/B, mesure d'un vrai émetteur avec l'escalier ;
    4. modulations ; 5. pannes simulées dans le SDR démo. Chaque partie = un panneau (🪟 Fenêtres, vraie fenêtre, écran)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self._tmp, self.fx, self._job, self.res_cmp, self.observed = None, None, None, None, None
        self._focus, self._detail, self._sess_win, self._help_box, self.res_real = {}, None, None, None, None
        self._grab, self._st_res, self._md_order, self.res_mod = None, None, [], None
        self.panels = {}
        for key, build in (("chain", self._tab_chain), ("cmp", self._tab_cmp), ("live", self._tab_live),
                           ("mod", self._tab_mod), ("fault", self._tab_fault)):
            self.panels[key] = build()
        intro = QtWidgets.QLabel(TR("Un banc de mesure : les mêmes signaux et les mêmes mesures pour tous les modèles. "
                                    "Chaque résultat dit d'où il vient : 🧪 simulé, 📡 observé (SDR réel) ou 🧮 calculé."))
        intro.setWordWrap(True)
        man = QtWidgets.QPushButton(TR("❓ Manuel"))
        man.setToolTip(TR("Le chapitre du manuel sur le labo SDR."))
        man.clicked.connect(lambda *_: owner.open_manual("sdr-labo"))
        self.view_btn = QtWidgets.QToolButton()
        self.view_btn.setText(TR("⛶ Affichage Labo"))
        self.view_btn.setToolTip(TR("La fenêtre ne montre plus que le labo : rangé en onglets, tout en grille, ou sur 2 écrans. "
                                    "Clic droit sur un graphe : le détacher en fenêtre ou le masquer."))
        self.view_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        vm = QtWidgets.QMenu(self.view_btn)
        vm.aboutToShow.connect(lambda m=vm: self._view_menu(m))
        self.view_btn.setMenu(vm)
        self.ses_btn = QtWidgets.QPushButton(TR("🗂 Sessions du labo"))
        self.ses_btn.setToolTip(TR("Comparaisons et mesures gardées : les retrouver, en comparer deux, les exporter."))
        self.ses_btn.clicked.connect(lambda *_: self.open_sessions())
        top = QtWidgets.QHBoxLayout()
        self._top = top
        self.sim_btn = QtWidgets.QPushButton(TR("🧪 Simuler (sans matériel)"))
        self.sim_btn.setToolTip(TR("Allume le SDR démo (tes micros simulés, avec du son) pour que les panneaux « En direct », "
                                   "« Pannes » et « Signal de A » aient quelque chose à recevoir."))
        self.sim_btn.clicked.connect(lambda *_: owner.simulate(True))
        top.addWidget(intro, 1)
        top.addWidget(self.sim_btn)
        top.addWidget(self.ses_btn)
        top.addWidget(self.view_btn)
        top.addWidget(man)
        self.panels["chain"].layout().insertLayout(0, top)
        self._plot_setup()
        self._badges_setup()
        self.tm = QtCore.QTimer(self)
        self.tm.timeout.connect(self._tick)
        self.tm.start(250)

    def _view_menu(self, m):
        o = self.owner
        m.clear()
        cur = o.sdr_cfg.get("lab_view", "tabs") if o.lab_view_on else None
        for k, t in LAB_VIEWS:
            a = m.addAction(TR(t))
            a.setCheckable(True)
            a.setChecked(k == cur)
            a.triggered.connect(lambda *_, k=k: o.lab_view(True, k))
        m.addSeparator()
        a = m.addAction(TR("↺ Remettre tous les graphes"))
        a.triggered.connect(lambda *_: self.plots_restore())
        if o.lab_view_on:
            m.addAction(TR("↩ Quitter l'affichage Labo")).triggered.connect(lambda *_: o.lab_view(False))

    # ---- 8.2 : chaque graphe détachable / masquable (clic droit)
    def _plots(self):
        return [p for w in self.panels.values() for p in w.findChildren(pg.PlotWidget)] + list(self._detached.keys())

    def _plot_key(self, p):
        return p.objectName() or ""

    def _plot_setup(self):
        """Ajoute à chaque graphe du labo (menu du clic droit) : détacher en fenêtre, masquer, tout remettre."""
        self._detached, self._ph = {}, {}
        for w in self.panels.values():
            for i, p in enumerate(w.findChildren(pg.PlotWidget)):
                t = p.getPlotItem().titleLabel.text or f"g{i}"
                p.setObjectName("lab:" + re.sub(r"<[^>]+>", "", t)[:60])
                vb = p.getPlotItem().vb
                vb.menu.addSeparator()
                vb.menu.addAction(TR("⧉ Détacher ce graphe (fenêtre)")).triggered.connect(
                    lambda *_, p=p: self.plot_detach(p))
                vb.menu.addAction(TR("✕ Masquer ce graphe")).triggered.connect(lambda *_, p=p: self.plot_hide(p))
                vb.menu.addAction(TR("↺ Remettre tous les graphes")).triggered.connect(lambda *_: self.plots_restore())
                self._plot_menu(p)

    def apply_hidden(self):
        """Graphes masqués d'après la config (appelé à l'ouverture du labo : la config est lue APRÈS sa création)."""
        hidden = set(self.owner.sdr_cfg.get("lab_hidden") or [])
        for p in self._plots():
            p.setVisible(self._plot_key(p) not in hidden)

    def plot_hide(self, p):
        if p in self._detached:
            self.plot_attach(p)
        p.hide()
        h = set(self.owner.sdr_cfg.get("lab_hidden") or [])
        h.add(self._plot_key(p))
        self.owner.sdr_cfg["lab_hidden"] = sorted(h)
        self.owner.set_status(TR("Graphe masqué : clic droit sur un autre graphe › « ↺ Remettre tous les graphes »."))

    def plot_detach(self, p):
        """Le graphe part dans sa propre fenêtre (à mettre sur l'écran qu'on veut) ; une étiquette garde sa place."""
        if p in self._detached:
            return self._detached[p]
        par = p.parentWidget()
        lay = par.layout() if par is not None else None
        if lay is None:
            return None
        ph = QtWidgets.QPushButton(TR("⧉ graphe détaché — cliquer pour le raccrocher"))
        ph.setToolTip(TR("Ce graphe est dans sa propre fenêtre. Clic : le remettre ici."))
        ph.clicked.connect(lambda *_, p=p: self.plot_attach(p))
        lay.replaceWidget(p, ph)
        self._ph[p] = (ph, lay)
        win = QtWidgets.QWidget(None, Qt.WindowType.Window)
        win.setWindowTitle(TR("🧪 Labo · {}").format(p.getPlotItem().titleLabel.text or ""))
        v = QtWidgets.QVBoxLayout(win)
        v.setContentsMargins(4, 4, 4, 4)
        bar = QtWidgets.QHBoxLayout()
        nxt = QtWidgets.QPushButton(TR("🖥 Écran suivant"))
        nxt.setToolTip(TR("Envoie cette fenêtre sur l'écran suivant."))
        nxt.clicked.connect(lambda *_, w=win: self._next_screen(w))
        back = QtWidgets.QPushButton(TR("📌 Raccrocher"))
        back.setToolTip(TR("Remet ce graphe dans son panneau du labo."))
        back.clicked.connect(lambda *_, p=p: self.plot_attach(p))
        bar.addWidget(nxt)
        bar.addStretch(1)
        bar.addWidget(back)
        v.addLayout(bar)
        v.addWidget(p, 1)
        p.show()
        win.closeEvent = lambda ev, p=p: (self.plot_attach(p), ev.accept())
        win.resize(720, 460)
        win.show()
        self._detached[p] = win
        return win

    def _next_screen(self, w):
        scrs = QtGui.QGuiApplication.screens()
        if len(scrs) < 2:
            self.owner.set_status(TR("Un seul écran : déplace la fenêtre où tu veux."))
            return
        i = (scrs.index(w.screen()) + 1) % len(scrs) if w.screen() in scrs else 0
        g = scrs[i].availableGeometry()
        w.move(g.x() + 40, g.y() + 40)

    def plot_attach(self, p):
        win = self._detached.pop(p, None)
        ph, lay = self._ph.pop(p, (None, None))
        if ph is not None:
            lay.replaceWidget(ph, p)
            ph.deleteLater()
            p.show()
        if win is not None:
            win.closeEvent = lambda ev: ev.accept()
            win.close()
            win.deleteLater()

    def plots_restore(self):
        for p in list(self._detached):
            self.plot_attach(p)
        for p in self._plots():
            p.show()
        self.owner.sdr_cfg["lab_hidden"] = []

    def _shown(self, key):
        """Panneau vraiment à l'écran (un onglet caché derrière un autre reste « visible » pour Qt : sa zone est vide)."""
        w = self.panels.get(key)
        try:
            return w is not None and w.isVisible() and not w.visibleRegion().isEmpty()
        except RuntimeError:                              # panneau détruit : ne pas remplir crash.log 4 fois / s
            return False

    # ------------------------------------------------------------------ outils
    def _play(self, a, label=""):
        import wave
        try:
            if self.fx is not None:
                self.fx.stop()
            a = np.asarray(a, dtype=np.float32)
            self._tmp = temp_wav_path("lab", self._tmp)
            with wave.open(self._tmp, "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(48000)
                w.writeframes(np.repeat((np.clip(a, -1, 1) * 32767).astype("<i2"), 2).tobytes())
            from PySide6 import QtMultimedia
            dev = self.owner.sound._device(QtMultimedia) if hasattr(self.owner, "sound") else None
            fx = QtMultimedia.QSoundEffect(dev, self) if dev is not None else QtMultimedia.QSoundEffect(self)
            fx.setSource(QtCore.QUrl.fromLocalFile(self._tmp))
            fx.setVolume(0.8)
            fx.play()
            self.fx = fx
            return TR("▶ {}").format(label)
        except Exception as e:  # noqa: BLE001
            return TR("⚠ Son impossible ici : {}").format(e)

    def _busy(self, on, btn, txt):
        btn.setEnabled(not on)
        btn.setText(TR("⏳ Calcul…") if on else TR(txt))

    # ------------------------------------------------------------------ ① chaîne complète
    def _tab_chain(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        self.ch_src = audio_button(self.owner, "voice")
        self.ch_mode = QtWidgets.QComboBox()
        for k, t in LAB_MODES:
            self.ch_mode.addItem(TR(t), k)
        self.ch_dev = QtWidgets.QSpinBox()
        self.ch_dev.setRange(1, 75)
        self.ch_dev.setValue(30)
        self.ch_dev.setSuffix(" kHz")
        self.ch_dev.setToolTip(TR("Déviation crête de l'émetteur (= 0 dBFS du son)."))
        self.ch_tx = _comp_combo("evo")
        self.ch_tx.setToolTip(TR("Compresseur de l'émetteur (le pack)."))
        self.ch_rx = _comp_combo("evo", "Aucun (pas d'expanseur)")
        self.ch_rx.setToolTip(TR("Expanseur du récepteur. Différent de l'émetteur = dynamique faussée (essaie !)."))
        self.ch_snr = QtWidgets.QSpinBox()
        self.ch_snr.setRange(0, 80)
        self.ch_snr.setValue(40)
        self.ch_snr.setSuffix(" dB")
        self.ch_snr.setToolTip(TR("Rapport porteuse / bruit dans le canal (C/N)."))
        self.ch_fault = QtWidgets.QComboBox()
        for k, t in LAB_FAULTS:
            self.ch_fault.addItem(TR(t), k)
        self.ch_go = QtWidgets.QPushButton(TR("▶ Calculer"))
        self.ch_go.clicked.connect(lambda *_: self.chain_run())
        self.ch_in = QtWidgets.QPushButton(TR("🔊 Entrée"))
        self.ch_in.clicked.connect(lambda *_: self._chain_play("src"))
        self.ch_out = QtWidgets.QPushButton(TR("🔊 Sortie"))
        self.ch_out.clicked.connect(lambda *_: self._chain_play("out"))
        g = QtWidgets.QGridLayout()
        for i, (lab, wid) in enumerate(((TR("Son"), self.ch_src), (TR("Modulation"), self.ch_mode),
                                        (TR("Déviation"), self.ch_dev), (TR("Émetteur"), self.ch_tx),
                                        (TR("Récepteur"), self.ch_rx), (TR("C/N"), self.ch_snr),
                                        (TR("Panne"), self.ch_fault))):
            g.addWidget(QtWidgets.QLabel(lab), i // 4, 2 * (i % 4))
            g.addWidget(wid, i // 4, 2 * (i % 4) + 1)
        self.ch_real = QtWidgets.QPushButton(TR("📡 Signal de A"))
        self.ch_real.setToolTip(TR("Capture 1 s d'IQ du poste SDR autour du récepteur A et montre la même chaîne sur ce "
                                   "VRAI signal (sans le son d'origine : pas d'« erreur » mesurable)."))
        self.ch_real.clicked.connect(lambda *_: self.chain_real())
        self.ch_file = QtWidgets.QPushButton(TR("📂 IQ enregistré…"))
        self.ch_file.setToolTip(TR("La même chaîne sur un enregistrement IQ SigMF (⏺ du temps réel, dossier d'incident)."))
        self.ch_file.clicked.connect(lambda *_: self.chain_file())
        h = QtWidgets.QHBoxLayout()
        h.addWidget(self.ch_go)
        h.addWidget(self.ch_in)
        h.addWidget(self.ch_out)
        h.addWidget(self.ch_real)
        h.addWidget(self.ch_file)
        self.ch_live = QtWidgets.QPushButton(TR("⏯ En direct"))
        self.ch_live.setCheckable(True)
        self.ch_live.setToolTip(TR("Les 6 graphes suivent en continu le signal reçu par le poste SDR sur A (environ 2 fois "
                                   "par seconde). Pas de SDR ? La simulation (SDR démo, avec son générateur) démarre "
                                   "toute seule."))
        self.ch_live.toggled.connect(lambda on: self.chain_live(on))
        h.addWidget(self.ch_live)
        h.addStretch(1)
        g.addLayout(h, 1, 6, 1, 2)
        v.addLayout(g)
        self.ch_help = QtWidgets.QLabel("")
        self.ch_help.setWordWrap(True)
        v.addWidget(self.ch_help)
        self.ch_fault.currentIndexChanged.connect(lambda *_: self._fault_help())
        self._fault_help()
        flow = QtWidgets.QLabel(TR("Le trajet du signal :  🎵 son  →  compresseur (émetteur)  →  modulation FM = I et Q (3, 4) "
                                   " →  l'air : bruit, panne (5)  →  démodulation (6)  →  expanseur (récepteur)  →  🔊 son "
                                   "(1, 2)"))
        flow.setWordWrap(True)
        flow.setStyleSheet("color: #8e8e93;")
        flow.setToolTip(TR("Chaque graphe montre une étape : les numéros renvoient aux titres des graphes."))
        v.addWidget(flow)
        grid = QtWidgets.QGridLayout()
        self.p_wave = _lab_plot("1. Son : entrée et sortie (100 ms)", "ms", "amplitude")
        self.p_env = _lab_plot("2. Niveau dans le temps", "s", "dBFS")
        self.p_iq = _lab_plot("3. IQ dans le temps (2 ms) : I et Q", "ms", "")
        self.p_const = _lab_plot("4. Constellation (canal)", "I", "Q")
        self.p_const.setAspectLocked(True)
        self.p_spec = _lab_plot("5. Spectre de l'IQ", "kHz autour de la porteuse", "dBFS")
        self.p_fi = _lab_plot("6. Fréquence instantanée", "ms", "kHz")
        for i, p in enumerate((self.p_wave, self.p_env, self.p_iq, self.p_const, self.p_spec, self.p_fi)):
            grid.addWidget(p, i // 3, i % 3)
        v.addLayout(grid, 1)
        self.ch_res = QtWidgets.QLabel(TR("Choisis un son, des compandeurs, une panne, puis ▶ Calculer."))
        self.ch_res.setWordWrap(True)
        self.ch_res.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(self.ch_res)
        return w

    def _fault_help(self):
        a, b = LAB_FAULT_HELP.get(self.ch_fault.currentData(), ("", ""))
        self.ch_help.setText(TR(a) + (" " + TR("Ce qu'on voit :") + " " + TR(b) if b else ""))

    def chain_args(self):
        return dict(audio=self.ch_src.spec, mode=self.ch_mode.currentData(), dev=self.ch_dev.value() * 1000.0,
                    tx_comp=self.ch_tx.currentData(), rx_comp=self.ch_rx.currentData(), snr=float(self.ch_snr.value()),
                    fault=self.ch_fault.currentData())

    def chain_run(self, wait=False):
        a = self.chain_args()
        if a["audio"].get("src") == "wav":
            wav_load(a["audio"]["path"])
        if wait:
            self._chain_done(lab_chain(**a), None)
            return
        self._busy(True, self.ch_go, "▶ Calculer")
        self.owner.run_heavy(lambda: lab_chain(**a), self._chain_done, what="Labo SDR")

    def _chain_done(self, r, err):
        self._busy(False, self.ch_go, "▶ Calculer")
        if err is not None or r is None:
            self.ch_res.setText(TR("⚠ Calcul impossible : {}").format(err))
            return
        self.res_chain = r
        self.set_prov("chain", "sim")
        for p in (self.p_wave, self.p_env, self.p_iq, self.p_const, self.p_spec, self.p_fi):
            p.clear()
        s0 = int(0.5 * 48000)
        k = slice(s0, s0 + 4800)
        tm = np.arange(4800) / 48.0
        self.p_wave.plot(tm, r["src"][k], pen=pg.mkPen(LAB_COLORS[0], width=1.2), name=TR("entrée"))
        self.p_wave.plot(tm, r["out"][k], pen=pg.mkPen(LAB_COLORS[1], width=1.0), name=TR("sortie"))
        for key, c, nm in (("env_src", 0, "entrée"), ("env_comp", 2, "après le compresseur"), ("env_out", 1, "sortie")):
            self.p_env.plot(r["te"], r[key][:len(r["te"])], pen=pg.mkPen(LAB_COLORS[c], width=1.2), name=TR(nm))
        self.p_env.setYRange(-80, 5)
        self.p_iq.plot(r["iq_t"], r["I"], pen=pg.mkPen(LAB_COLORS[0], width=1), name="I")
        self.p_iq.plot(r["iq_t"], r["Q"], pen=pg.mkPen(LAB_COLORS[3], width=1), name="Q")
        v = r.get("views")
        if v:
            self.p_const.plot(v["I"], v["Q"], pen=None, symbol="o", symbolSize=3, symbolPen=None,
                              symbolBrush=pg.mkBrush(LAB_COLORS[0]))
            self.p_fi.plot(v["tf"], v["finst"], pen=pg.mkPen(LAB_COLORS[2], width=1))
        if r["L"] is not None:
            self.p_spec.plot(r["F"], r["L"], pen=pg.mkPen(LAB_COLORS[0], width=1), name=TR("moyenne"))
            self.p_spec.plot(r["F"], r["Lmax"], pen=pg.mkPen(LAB_COLORS[1], width=1), name=TR("max"))
            self.p_spec.setXRange(-200, 200)
        m = r["m"]
        rows = [(TR("Niveau entrée / sortie"), f"{m['src']:.1f} / {m['out']:.1f} dBFS ({m['diff']:+.1f} dB)"),
                (TR("Crête entrée / sortie"), f"{m['pk_src']:.1f} / {m['pk_out']:.1f} dBFS"),
                (TR("Erreur résiduelle"), f"{m['err']:.0f} dB"), (TR("Retard"), f"{m['lat']:.1f} ms"),
                (TR("Pompage"), f"± {m['pump']:.1f} dB")]
        fl = "".join(f"<li style='color:{self.owner.tone_color(t) if t != 'ok' else 'inherit'}'>{_hesc(x)}</li>"
                     for x, t in lab_findings(r, TR))
        self.ch_res.setText(f"<b>{_hesc(TR(PROVENANCE['sim']))}</b> · " + " · ".join(
            f"{_hesc(a)} : <b>{_hesc(b)}</b>" for a, b in rows) + f"<ul>{fl}</ul>")

    def _chain_play(self, which):
        r = getattr(self, "res_chain", None)
        if r is None:
            self.ch_res.setText(TR("Calcule d'abord (▶ Calculer)."))
            return
        self.ch_help.setText(self._play(r[which], TR("entrée") if which == "src" else TR("sortie")))

    # ------------------------------------------------------------------ ② comparateur
    def _tab_cmp(self):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        left = QtWidgets.QVBoxLayout()
        left.addWidget(QtWidgets.QLabel(TR("Modèles du récepteur à comparer :")))
        self.cm_list = _model_list(("evo", "x2", "wisy_enr", "wisy_ens"))
        self.cm_list.currentItemChanged.connect(lambda *_: self._card())
        left.addWidget(self.cm_list, 1)
        f = QtWidgets.QFormLayout()
        self.cm_tx = _comp_combo("evo")
        self.cm_tx.setToolTip(TR("Compresseur de l'émetteur, le même pour tous (la référence de la comparaison)."))
        f.addRow(TR("Émetteur"), self.cm_tx)
        self.cm_src = audio_button(self.owner, "voice")
        f.addRow(TR("Son"), self.cm_src)
        self.cm_de = QtWidgets.QComboBox()
        for us in (50.0, 75.0, 0.0):
            self.cm_de.addItem(f"{us:g} µs" if us else TR("aucune"), us)
        self.cm_de.setToolTip(TR("Désaccentuation (et pré-accentuation de l'émetteur) quand le modèle n'impose pas la sienne."))
        f.addRow(TR("Désaccentuation"), self.cm_de)
        left.addLayout(f)
        self.cm_go = QtWidgets.QPushButton(TR("▶ Comparer"))
        self.cm_go.clicked.connect(lambda *_: self.cmp_run())
        self.cm_play = QtWidgets.QPushButton(TR("🔊 Écouter le modèle choisi"))
        self.cm_play.clicked.connect(lambda *_: self._cmp_play())
        self.cm_rep = QtWidgets.QPushButton(TR("📄 Rapport comparatif"))
        self.cm_rep.clicked.connect(lambda *_: self.cmp_report())
        self.cm_det = QtWidgets.QPushButton(TR("🔍 Comparaison détaillée"))
        self.cm_det.setToolTip(TR("Les 4 graphes en grand dans une fenêtre, modèles à cocher, EQ et phase zoomés ensemble."))
        self.cm_det.clicked.connect(lambda *_: self.cmp_detail())
        for b in (self.cm_go, self.cm_det, self.cm_play, self.cm_rep):
            left.addWidget(b)
        self.cm_card = QtWidgets.QLabel("")
        self.cm_card.setWordWrap(True)
        self.cm_card.setTextFormat(Qt.TextFormat.RichText)
        self.cm_card.setMaximumWidth(330)
        left.addWidget(self.cm_card)
        sp = QtWidgets.QSplitter(Qt.Orientation.Horizontal)      # poignée : agrandir les graphes si le panneau est étroit
        lw_ = QtWidgets.QWidget()
        lw_.setLayout(left)
        lw_.setMaximumWidth(330)                                 # les graphes gardent la place
        sp.addWidget(lw_)
        rw_ = QtWidgets.QWidget()
        sp.addWidget(rw_)
        sp.setStretchFactor(1, 1)
        sp.setChildrenCollapsible(True)
        h.addWidget(sp)
        right = QtWidgets.QVBoxLayout(rw_)
        right.setContentsMargins(0, 0, 0, 0)
        grid = QtWidgets.QGridLayout()
        self.p_tf = _lab_plot("Transfert du récepteur", "entrée dBFS", "sortie dBFS")
        self.p_tr = _lab_plot("Saut −30 → −10 → −30 dBFS", "s", "dBFS")
        self.p_eq = _lab_plot("EQ de la chaîne", "Hz", "dB")
        self.p_ph = _lab_plot("Phase (retard retiré)", "Hz", "degrés")
        for p in (self.p_eq, self.p_ph):
            _log_hz(p)
        for p, tip in ((self.p_tf, "Courbe de transfert du récepteur, MESURÉE avec un escalier de sinus ; pointillés = formule."),
                       (self.p_tr, "Saut de niveau −30 → −10 → −30 dBFS à travers émetteur + récepteur : montée, descente, dépassement."),
                       (self.p_eq, "Réponse en fréquence (EQ) de la chaîne émetteur + récepteur (bruit rose à −20 dBFS)."),
                       (self.p_ph, "Phase de la chaîne, retard pur retiré.")):
            p.setToolTip(TR(tip))
        for i, p in enumerate((self.p_tf, self.p_tr, self.p_eq, self.p_ph)):
            grid.addWidget(p, i // 2, i % 2)
        right.addLayout(grid, 1)
        self.cm_tbl = QtWidgets.QTableWidget(0, 9)
        self.cm_tbl.setHorizontalHeaderLabels([TR(x) for x in ("Modèle", "Pente", "Niveau", "Erreur", "Pompage",
                                                               "Montée", "Descente", "Dépassement", "Retard")])
        self.cm_tbl.verticalHeader().setVisible(False)
        self.cm_tbl.setMaximumHeight(190)
        self.cm_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cm_tbl.setToolTip(TR("Pente : 2 = expanseur 2:1. Niveau : sortie − entrée. Erreur : ce qui reste quand on "
                                  "retire le gain (plus bas = plus fidèle).\nPompage : le niveau qui bouge sans raison. "
                                  "Montée / descente : temps pour se poser après un saut de 20 dB."))
        right.addWidget(self.cm_tbl)
        self.cm_msg = QtWidgets.QLabel(TR("Coche les modèles à comparer, puis ▶ Comparer."))
        self.cm_msg.setWordWrap(True)
        right.addWidget(self.cm_msg)
        self._card()
        return w

    def _card(self):
        it = self.cm_list.currentItem()
        key = it.data(Qt.ItemDataRole.UserRole) if it is not None else "evo"
        c = compander_card(key)
        if not c:
            return
        rows = ((TR("Fabricant"), TR(c["maker"])), (TR("Modèle"), TR(c["model"])), (TR("Technologie"), TR(c["tech"])),
                (TR("Documentation"), TR(c["doc"])), (TR("Implémentation"), TR(CMP_IMPL[c["impl"]])),
                (TR("Fidélité"), TR(c["fidelity"])), (TR("Limites"), TR(c["limits"])), (TR("Version"), c["ver"]))
        p = c["params"]
        rows += ((TR("Réglages du modèle"), f"{p['ratio']:g}:1 · {TR('montée')} {p['attack']:g} · {TR('descente')} "
                  f"{p['release']:g} · {p['det']}" + (f" · {TR('genou')} {p['knee']:g} dB" if p["knee"] is not None else "")),)
        self.cm_card.setText(f"<b>{_hesc(TR('Fiche du modèle'))}</b><br>" + "<br>".join(
            f"<span style='color:#8e8e93'>{_hesc(a)}</span> : {_hesc(str(b))}" for a, b in rows))

    def cmp_args(self):
        return dict(keys=_checked(self.cm_list), tx_key=self.cm_tx.currentData(), audio=self.cm_src.spec,
                    deemph_us=self.cm_de.currentData())

    def cmp_run(self, wait=False):
        a = self.cmp_args()
        if not a["keys"]:
            self.cm_msg.setText(TR("Coche au moins un modèle."))
            return
        if a["audio"].get("src") == "wav":
            wav_load(a["audio"]["path"])
        if wait:
            self._cmp_done(comp_compare(**a), None)
            return
        self._busy(True, self.cm_go, "▶ Comparer")
        self.owner.run_heavy(lambda: comp_compare(**a), self._cmp_done, what="Labo SDR")

    def _cmp_done(self, r, err):
        self._busy(False, self.cm_go, "▶ Comparer")
        if err is not None or r is None:
            self.cm_msg.setText(TR("⚠ Calcul impossible : {}").format(err))
            return
        self.res_cmp = r
        for p in (self.p_tf, self.p_tr, self.p_eq, self.p_ph):
            p.clear()
        t = self.cm_tbl
        t.setRowCount(0)
        for i, row in enumerate(r["rows"]):
            col = LAB_COLORS[i % len(LAB_COLORS)]
            nm = TR(row["card"]["model"])
            self.p_tf.plot(row["xin"], row["rx"], pen=pg.mkPen(col, width=1.6), name=nm)
            th = comp_curve(row["key"], "rx")
            if th is not None:
                self.p_tf.plot(th[0], th[1], pen=pg.mkPen(col, width=1, style=Qt.PenStyle.DashLine))
            tr_ = row["transient"]
            self.p_tr.plot(tr_["t"], tr_["env"], pen=pg.mkPen(col, width=1.2), name=nm)
            fq = row["freq"]
            if fq:
                self.p_eq.plot(fq["f"], _coh_mask(fq, fq["mag"]), pen=pg.mkPen(col, width=1.2), name=nm, connect="finite")
                self.p_ph.plot(fq["f"], _coh_mask(fq, fq["phase"]), pen=pg.mkPen(col, width=1.2), name=nm,
                               connect="finite")
            m = row["m"]
            t.insertRow(i)
            vals = (nm, f"{row['slope']:.2f}", f"{m['diff']:+.1f} dB", f"{m['err']:.0f} dB", f"± {m['pump']:.1f} dB",
                    f"{m['up']:.0f} ms", f"{m['down']:.0f} ms", f"{m['over']:+.1f} dB", f"{m['lat']:.1f} ms")
            for j, v_ in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v_)
                if j == 0:
                    it.setForeground(QtGui.QColor(col))
                t.setItem(i, j, it)
        self.p_tf.plot([-60, 0], [-60, 0], pen=pg.mkPen("#8e8e93", width=1, style=Qt.PenStyle.DotLine))
        self.p_tf.setYRange(-90, 10)
        self.p_tr.setYRange(-60, 0)
        self.p_eq.setYRange(-20, 10)
        self.p_ph.setYRange(-180, 180)
        t.resizeColumnsToContents()
        self.cm_msg.setText(TR("{} · {} modèle(s) · mêmes signaux et mêmes mesures pour tous. Les modèles « approchés » "
                               "ne sont PAS les vrais traitements des marques.").format(TR(PROVENANCE["sim"]), len(r["rows"])))
        a = self.cmp_args()
        self.session_save("cmp", "sim", dict(tx=a["tx_key"], deemph=a["deemph_us"], audio=audio_text(a["audio"])),
                          cmp_metrics(r))

    def _cmp_play(self):
        r = self.res_cmp
        if not r or not r["rows"]:
            self.cm_msg.setText(TR("Compare d'abord (▶ Comparer)."))
            return
        i = max(0, self.cm_tbl.currentRow())
        row = r["rows"][min(i, len(r["rows"]) - 1)]
        self.cm_msg.setText(self._play(row["out"], TR(row["card"]["model"])))

    def cmp_report(self, path=None):
        r = self.res_cmp
        if not r:
            self.cm_msg.setText(TR("Compare d'abord (▶ Comparer)."))
            return None
        d = Path(self.owner.log_dir) / "rapports"
        try:
            d.mkdir(parents=True, exist_ok=True)
            path = path or str(d / f"compander_lab_{datetime.now():%Y%m%d_%H%M%S}.html")
            write_atomic(path, comp_report_html(r, TR, observed=self.observed))
        except OSError as e:
            self.cm_msg.setText(TR("⚠ Rapport impossible : {}").format(e))
            return None
        self.cm_msg.setText(TR("📄 Rapport : {}").format(path))
        if not os.environ.get("TSM_NO_BROWSER"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        return path

    # ------------------------------------------------------------------ ③ en direct
    def _tab_live(self):
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        left = QtWidgets.QVBoxLayout()
        self.lv_src = QtWidgets.QLabel("")
        self.lv_src.setWordWrap(True)
        left.addWidget(self.lv_src)
        left.addWidget(QtWidgets.QLabel(TR("Modèles appliqués au son reçu :")))
        self.lv_list = _model_list(("none_d50", "x2", "evo", "wisy_enr"))
        self.lv_list.itemChanged.connect(lambda *_: self._live_reset())
        left.addWidget(self.lv_list, 1)
        self.lv_ab = QtWidgets.QPushButton(TR("🎧 Écouter avec le modèle choisi"))
        self.lv_ab.setToolTip(TR("Le récepteur A du poste SDR passe sur ce compandeur, tout de suite : compare à l'oreille "
                                 "(A/B) en changeant de ligne."))
        self.lv_ab.clicked.connect(lambda *_: self.live_listen())
        left.addWidget(self.lv_ab)
        box = QtWidgets.QGroupBox(TR("📏 Mesurer mon vrai émetteur"))
        bl = QtWidgets.QVBoxLayout(box)
        t = QtWidgets.QLabel(TR("1. Dans 🎵 Générateur audio, choisis « Signal de test : escalier de niveaux » et envoie-le "
                                "dans l'entrée audio du pack (câble).\n2. Écoute ce micro au poste SDR (A).\n"
                                "3. Attends au moins {} s, puis mesure : la pente donne le vrai taux de compression de "
                                "l'émetteur.").format(f"{2 * STAIR_PERIOD + 1:.0f}"))
        t.setWordWrap(True)
        bl.addWidget(t)
        b = QtWidgets.QPushButton(TR("🎵 Ouvrir le générateur audio"))
        b.clicked.connect(lambda *_: self.owner.open_audio_gen())
        bl.addWidget(b)
        self.lv_fit_btn = QtWidgets.QPushButton(TR("📏 Mesurer maintenant"))
        self.lv_fit_btn.clicked.connect(lambda *_: self.live_fit())
        bl.addWidget(self.lv_fit_btn)
        self.lv_state = QtWidgets.QLabel("")
        self.lv_state.setWordWrap(True)
        self.lv_state.setToolTip(TR("État de la mesure : prêt, en cours (le son s'accumule), terminé (valable), invalide "
                                    "(avec la raison) ou interrompu (le poste SDR s'est arrêté)."))
        bl.addWidget(self.lv_state)
        self.lv_fit = QtWidgets.QLabel("")
        self.lv_fit.setWordWrap(True)
        bl.addWidget(self.lv_fit)
        left.addWidget(box)
        self.lv_snap = QtWidgets.QPushButton(TR("🔬 Figer 4 s et comparer en détail"))
        self.lv_snap.setToolTip(TR("Garde les 4 dernières secondes du son reçu, les passe dans chaque modèle coché et "
                                   "ouvre la comparaison détaillée (marquée 📡 observé avec un vrai SDR)."))
        self.lv_snap.clicked.connect(lambda *_: self.live_snapshot())
        left.addWidget(self.lv_snap)
        lw = QtWidgets.QWidget()
        lw.setLayout(left)
        lw.setMaximumWidth(340)
        sp = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(lw)
        rw_ = QtWidgets.QWidget()
        sp.addWidget(rw_)
        sp.setStretchFactor(1, 1)
        h.addWidget(sp)
        right = QtWidgets.QVBoxLayout(rw_)
        right.setContentsMargins(0, 0, 0, 0)
        grid = QtWidgets.QGridLayout()
        self.p_lvl = _lab_plot("Niveau de chaque modèle", "s", "dBFS")
        self.p_leq = _lab_plot("EQ en direct", "Hz", "dB")
        self.p_lph = _lab_plot("Phase en direct", "Hz", "degrés")
        for p in (self.p_leq, self.p_lph):
            _log_hz(p)
        self.p_lin = _lab_plot("Son reçu (avant expanseur)", "s", "dBFS")
        for i, p in enumerate((self.p_lvl, self.p_lin, self.p_leq, self.p_lph)):
            grid.addWidget(p, i // 2, i % 2)
        right.addLayout(grid, 1)
        self.lv_tbl = QtWidgets.QTableWidget(0, 4)
        self.lv_tbl.setHorizontalHeaderLabels([TR(x) for x in ("Modèle", "Niveau", "Crête", "Écart au son reçu")])
        self.lv_tbl.verticalHeader().setVisible(False)
        self.lv_tbl.setMaximumHeight(170)
        self.lv_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lv_tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        right.addWidget(self.lv_tbl)
        self._live_reset()
        self._live_tap = None
        return w

    def _eng(self):
        es = [e for e in (getattr(self.owner, "sdr_engs", None) or {}).values() if e.running()]
        return es[0] if es else None

    def _live_reset(self):
        self.lv_keys = _checked(self.lv_list)
        self.lv_ch = {}
        self.lv_in = deque(maxlen=int(30 * 48000 / 2400) + 10)     # morceaux bruts (30 s)
        self.lv_out = {k: deque(maxlen=60) for k in self.lv_keys}
        self.lv_hist = {k: deque(maxlen=80) for k in self.lv_keys}
        self.lv_inh = deque(maxlen=80)
        self._lv_t = 0.0
        self._st_res = None

    def _live_on(self, on):
        self._tap_on = bool(on)
        e = self._eng()
        for e_ in (getattr(self.owner, "sdr_engs", None) or {}).values():
            if e_.worker is not None:
                e_.worker.lab_tap = bool(on) and e_ is e

    def _tick(self):
        if self._shown("fault"):
            self._fault_refresh()
        if not self._shown("live"):
            if getattr(self, "_tap_on", False):
                self._live_on(False)
            return
        e = self._eng()
        if e is None or e.worker is None:
            self.lv_src.setText(TR("Démarre un poste SDR (▶ dans le Récepteur) et écoute un micro FM en A : le son reçu "
                                   "passe ici dans chaque modèle. Pas de SDR ? 🧪 SDR démo."))
            self.stair_status()
            return
        self._live_on(True)
        demo = e.kind() == "demo"
        self.set_prov("live", "sim" if demo else "obs")
        self.stair_status()
        dem = e.demod
        self.lv_src.setText(TR("Source : {} · A = {} MHz · écouté avec {}").format(
            TR(PROVENANCE["sim" if demo else "obs"]), f"{e.a:.4f}" if e.a is not None else "—",
            TR(COMPANDERS.get(dem.get("compander") or "none", {}).get("name", ""))))
        q = e.worker.a_pre
        new = []
        while q:
            new.append(q.popleft()[1])
        if not new:
            return
        x = np.concatenate(new).astype(np.float32)
        self.lv_in.append(x)
        de = float(dem.get("deemph") or 50.0)
        for k in self.lv_keys:
            ch = self.lv_ch.get(k)
            if ch is None:
                ch = self.lv_ch[k] = CompChain(k, de)
            self.lv_out[k].append(ch(x))
        now = time.time()
        if now - self._lv_t < 0.5:
            return
        self._lv_t = now
        self._live_draw(now)

    def _live_draw(self, now):
        xs = list(self.lv_in)[-40:]                     # ~2 s
        if not xs:
            return
        xin = np.concatenate(xs)
        n2 = len(xin)
        db_in = _lab_db(xin[-24000:])
        self.lv_inh.append((now, db_in))
        for p in (self.p_lvl, self.p_leq, self.p_lph, self.p_lin):
            p.clear()
        t0 = now
        th = np.array([a for a, _ in self.lv_inh]) - t0
        self.p_lin.plot(th, np.array([b for _, b in self.lv_inh]), pen=pg.mkPen(LAB_COLORS[0], width=1.4),
                        name=TR("son reçu"))
        tb = self.lv_tbl
        tb.setRowCount(0)
        for i, k in enumerate(self.lv_keys):
            col = LAB_COLORS[i % len(LAB_COLORS)]
            outs = list(self.lv_out[k])
            if not outs:
                continue
            y = np.concatenate(outs)[-n2:]
            m = audio_meter(y[-24000:])
            self.lv_hist[k].append((now, m["rms"]))
            hh = list(self.lv_hist[k])
            nm = TR(compander_card(k)["model"])
            self.p_lvl.plot(np.array([a for a, _ in hh]) - t0, np.array([b for _, b in hh]), pen=pg.mkPen(col, width=1.3),
                            name=nm)
            xf = xfer_spectrum(xin[-len(y):], y)
            if xf:                                       # seulement là où le son reçu permet de mesurer (cohérence)
                self.p_leq.plot(xf["f"], _coh_mask(xf, xf["mag"]), pen=pg.mkPen(col, width=1.2), name=nm,
                                connect="finite")
                self.p_lph.plot(xf["f"], _coh_mask(xf, xf["phase"]), pen=pg.mkPen(col, width=1.2), name=nm,
                                connect="finite")
            tb.insertRow(i)
            for j, v_ in enumerate((nm, f"{m['rms']:.1f} dBFS", f"{m['peak']:.1f} dBFS", f"{m['rms'] - db_in:+.1f} dB")):
                it = QtWidgets.QTableWidgetItem(v_)
                it.setData(Qt.ItemDataRole.UserRole, k)
                if j == 0:
                    it.setForeground(QtGui.QColor(col))
                tb.setItem(i, j, it)
        tb.resizeColumnsToContents()
        self.p_leq.setYRange(-24, 12)
        self.p_lph.setYRange(-180, 180)

    def live_listen(self):
        e = self._eng()
        it = self.lv_tbl.item(max(0, self.lv_tbl.currentRow()), 0) if self.lv_tbl.rowCount() else None
        key = it.data(Qt.ItemDataRole.UserRole) if it is not None else (self.lv_keys[0] if self.lv_keys else None)
        cur = self.lv_list.currentItem()
        if cur is not None and cur.checkState() == Qt.CheckState.Checked and self.lv_tbl.currentRow() < 0:
            key = cur.data(Qt.ItemDataRole.UserRole)
        if e is None or key is None:
            self.lv_fit.setText(TR("Pas de poste SDR en marche."))
            return False
        e.demod = dict(e.demod, compander=key)
        e._push()
        self.lv_fit.setText(TR("🎧 A écoute maintenant avec : {}").format(TR(COMPANDERS[key]["name"])))
        return True

    def live_fit(self, x=None):
        if x is None:
            xs = list(self.lv_in)
            x = np.concatenate(xs) if xs else np.zeros(0, dtype=np.float32)
        r = stair_fit(x)
        e = self._eng()
        prov = "sim" if (e is None or e.kind() == "demo") else "obs"
        r["prov"] = prov
        secs = len(x) / 48000.0
        st, why = stair_validity(r, _lab_db(x) if len(x) else None, secs)
        r["state"], r["reasons"] = st, why
        self._st_res = (st, why, r)
        self.observed = r if st == "done" else None          # le rapport ne reprend qu'une mesure valable
        if r["ok"]:
            self.lv_fit.setText(TR("{} · pente {} → taux de compression ≈ {}:1 · linéarité R² {}").format(
                TR(PROVENANCE[prov]), f"{r['slope']:.2f}", f"{r['ratio']:.2f}" if r["ratio"] else "—", f"{r['r2']:.3f}"))
        else:
            self.lv_fit.setText("⚠ " + TR(r["why"]))
        self.stair_status()
        if len(x):
            self.session_save("stair", prov, dict(seconds=round(secs, 1)),
                              dict(ratio=r.get("ratio"), slope=r.get("slope"), r2=r.get("r2"), state=st),
                              " ".join(why))
        return r

    # ------------------------------------------------------------------ ④ modulations
    def _tab_mod(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        h = QtWidgets.QHBoxLayout()
        self.md_src = audio_button(self.owner, "melody")
        self.md_go = QtWidgets.QPushButton(TR("▶ Comparer les modulations"))
        self.md_go.clicked.connect(lambda *_: self.mod_run())
        self.md_step = QtWidgets.QComboBox()
        for k, t in LAB_MOD_STEPS:
            self.md_step.addItem(TR(t), k)
        self.md_step.setToolTip(TR("① les noms et ce que l'appli devine ; ② seulement des indices ; ③ quiz : à toi de "
                                   "reconnaître chaque spectre (ordre mélangé)."))
        self.md_step.currentIndexChanged.connect(lambda *_: self._mod_step())
        self.md_a = QtWidgets.QPushButton(TR("📡 Ajouter le signal de A"))
        self.md_a.setToolTip(TR("Le vrai spectre autour du récepteur A du poste SDR, avec ce que l'appli en devine."))
        self.md_a.clicked.connect(lambda *_: self.mod_add_a())
        h.addWidget(QtWidgets.QLabel(TR("Son")))
        h.addWidget(self.md_src)
        h.addWidget(self.md_go)
        h.addWidget(self.md_step)
        h.addWidget(self.md_a)
        h.addStretch(1)
        v.addLayout(h)
        t = QtWidgets.QLabel(TR("Le même son, six façons d'occuper l'air : à quoi chacune ressemble sur un spectre, et ce que "
                                "l'appli en devine (« C'est quoi ce signal ? »)."))
        t.setWordWrap(True)
        v.addWidget(t)
        self.md_grid = QtWidgets.QGridLayout()
        self.md_plots = []
        self.md_ans = []
        for i in range(6):
            p = _lab_plot("—", "kHz", "dBFS")
            self.md_plots.append(p)
            self.md_grid.addWidget(p, 2 * (i // 3), i % 3)
            cb = QtWidgets.QComboBox()
            cb.addItem(TR("— ta réponse —"), "")
            for c_ in MOD_QUIZ_CHOICES:
                cb.addItem(TR(c_), c_)
            cb.setVisible(False)
            self.md_ans.append(cb)
            self.md_grid.addWidget(cb, 2 * (i // 3) + 1, i % 3)
        self.md_aplot = _lab_plot("📡 Signal de A", "kHz", "dBFS")
        self.md_aplot.hide()
        self.md_grid.addWidget(self.md_aplot, 4, 0, 1, 3)
        v.addLayout(self.md_grid, 1)
        q = QtWidgets.QHBoxLayout()
        self.md_check = QtWidgets.QPushButton(TR("✔ Vérifier"))
        self.md_check.clicked.connect(lambda *_: self.mod_check())
        self.md_check.setVisible(False)
        self.md_score = QtWidgets.QLabel("")
        self.md_score.setWordWrap(True)
        self.md_score.setVisible(False)
        q.addWidget(self.md_check)
        q.addWidget(self.md_score, 1)
        v.addLayout(q)
        self.md_info = QtWidgets.QLabel("")
        self.md_info.setWordWrap(True)
        v.addWidget(self.md_info)
        return w

    def mod_run(self, wait=False):
        a = self.md_src.spec
        if wait:
            self._mod_done(lab_modulations(a), None)
            return
        self._busy(True, self.md_go, "▶ Comparer les modulations")
        self.owner.run_heavy(lambda: lab_modulations(a), self._mod_done, what="Labo SDR")

    def _mod_done(self, rows, err):
        self._busy(False, self.md_go, "▶ Comparer les modulations")
        if err is not None or not rows:
            return
        self.res_mod = rows
        self._md_order = [int(i) for i in np.random.default_rng().permutation(len(rows))]
        self._mod_draw()

    # ------------------------------------------------------------------ ⑤ pannes simulées (SDR démo en direct)
    def _tab_fault(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        sb = QtWidgets.QGroupBox(TR("🎬 Scénarios guidés"))          # 8.2 : un clic = chaîne réglée + panne + quoi regarder
        sl = QtWidgets.QVBoxLayout(sb)
        self.sc_combo = QtWidgets.QComboBox()
        for sc in LAB_SCENARIOS:
            self.sc_combo.addItem(TR(sc["name"]), sc["key"])
        self.sc_combo.setToolTip(TR("Un scénario règle la chaîne complète (et pose une panne dans le SDR démo s'il est "
                                    "allumé), puis dit quoi regarder et pourquoi."))
        self.sc_go = QtWidgets.QPushButton(TR("▶ Lancer le scénario"))
        self.sc_go.clicked.connect(lambda *_: self.scenario(self.sc_combo.currentData()))
        sl.addLayout(self.owner._row(self.sc_combo, self.sc_go, None))
        self.sc_txt = QtWidgets.QLabel(TR("Choisis un scénario : le labo le joue, tu regardes ce qui change."))
        self.sc_txt.setWordWrap(True)
        self.sc_txt.setTextFormat(Qt.TextFormat.RichText)
        sl.addWidget(self.sc_txt)
        v.addWidget(sb)
        t = QtWidgets.QLabel(TR("Injecte une panne dans le 🧪 SDR démo, en direct, pour voir comment l'appli la détecte "
                                "(ligne « Flux » du Récepteur, alarmes, journal). Tout est marqué SIMULÉ. Rien ne touche un "
                                "vrai SDR."))
        t.setWordWrap(True)
        v.addWidget(t)
        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel(TR("Durée")))
        self.ft_dur = QtWidgets.QSpinBox()
        self.ft_dur.setRange(5, 300)
        self.ft_dur.setValue(30)
        self.ft_dur.setSuffix(" s")
        h.addWidget(self.ft_dur)
        stop = QtWidgets.QPushButton(TR("■ Arrêter la panne"))
        stop.clicked.connect(lambda *_: self.fault(None))
        h.addWidget(stop)
        h.addStretch(1)
        v.addLayout(h)
        g = QtWidgets.QGridLayout()
        for i, (k, txt) in enumerate(DEMO_FAULTS):
            b = QtWidgets.QPushButton(TR(txt))
            b.setToolTip(TR(DEMO_FAULT_HELP[k]))
            b.clicked.connect(lambda *_, k=k: self.fault(k))
            g.addWidget(b, i // 2, 2 * (i % 2))
            lab = QtWidgets.QLabel(TR(DEMO_FAULT_HELP[k]))
            lab.setWordWrap(True)
            g.addWidget(lab, i // 2, 2 * (i % 2) + 1)
        v.addLayout(g)
        self.ft_lbl = QtWidgets.QLabel("")
        self.ft_lbl.setWordWrap(True)
        v.addWidget(self.ft_lbl)
        v.addStretch(1)
        return w

    def scenario(self, key, wait=False):
        """Joue un scénario : chaîne complète réglée et calculée, panne posée dans le SDR démo (s'il tourne), texte."""
        sc = next((x for x in LAB_SCENARIOS if x["key"] == key), None)
        if sc is None:
            return None
        c = sc["chain"]
        for combo, val in ((self.ch_tx, c.get("tx_comp", "")), (self.ch_rx, c.get("rx_comp", "")),
                           (self.ch_fault, c.get("fault", "none")), (self.ch_mode, c.get("mode", "wfm"))):
            combo.setCurrentIndex(max(0, combo.findData(val)))
        self.ch_snr.setValue(int(c.get("snr", 40)))
        self.chain_run(wait=wait)
        live = ""
        if sc["live"]:
            if self.owner.sdr_cfg.get("demo") and self._eng() is not None:
                self.fault(sc["live"])
                live = TR("Panne posée dans le SDR démo en direct ({} s).").format(self.ft_dur.value())
            else:
                live = TR("Allume le 🧪 SDR démo et ▶ le poste pour voir aussi l'effet en direct.")
        self.sc_txt.setText(f"<b>{_hesc(TR(sc['name']))}</b><br>{_hesc(TR('À regarder :'))} {_hesc(TR(sc['watch']))}"
                            f"<br>{_hesc(TR('Pourquoi :'))} {_hesc(TR(sc['why']))}" + (f"<br><i>{_hesc(live)}</i>" if live else ""))
        try:
            self.owner.open_sdr_lab("chain")
        except Exception:  # noqa: BLE001
            pass
        return sc

    def fault(self, k):
        o = self.owner
        if k and not o.sdr_cfg.get("demo"):
            self.ft_lbl.setText(TR("Les pannes ne se posent que sur le 🧪 SDR démo : allume-le (menu du mode), puis ▶ dans "
                                   "le Récepteur."))
            return False
        sdr_demo_fault(k, self.ft_dur.value())
        for e_ in (getattr(o, "sdr_engs", None) or {}).values():      # 8.2 : notée dans l'historique du poste
            if e_.running() and e_.kind() == "demo":
                e_._ev("fault", TR(dict(DEMO_FAULTS)[k]) if k else TR("fin"), journal=False)
        o.log_event(dict(name=TR("Labo SDR"), freq=0.0, note=("🧪 " + TR(dict(DEMO_FAULTS)[k])) if k else TR("fin")),
                    0.0, "PANNE SIMULÉE")
        self._fault_refresh()
        return True

    def _fault_refresh(self):
        f = sdr_demo_fault_now()
        e = self._eng()
        q = e.quality() if e is not None else None
        if f:
            self.ft_lbl.setText(TR("🧪 Panne en cours : {} · encore {} s").format(
                TR(dict(DEMO_FAULTS)[f["kind"]]), f"{max(0.0, f['until'] - time.time()):.0f}") +
                ("\n" + TR("Flux : {}").format(q[0]) if q else ""))
        else:
            self.ft_lbl.setText(TR("Aucune panne en cours.") + ("\n" + TR("Flux : {}").format(q[0]) if q else ""))

    def stop(self):
        if getattr(self, "_clive", False):
            self.chain_live(False)
        for p in list(getattr(self, "_detached", {})):
            self.plot_attach(p)
        self._live_on(False)
        if self.fx is not None:
            self.fx.stop()

    # ================================================================== 8.2 : Full Lab v2
    # ---- provenance bien visible (🧪 simulé / 📡 observé) sur chaque panneau
    PROV_STYLE = {"sim": ("#ffb300", "rgba(255,179,0,0.14)"), "obs": ("#30d158", "rgba(48,209,88,0.14)"),
                  "calc": ("#8e8e93", "rgba(142,142,147,0.14)")}

    def _badges_setup(self):
        self.badges = {}
        for key in LAB_KEYS:
            b = QtWidgets.QLabel("")
            b.setToolTip(TR("D'où viennent les résultats de ce panneau : 🧪 simulé (signal fabriqué par l'appli), "
                            "📡 observé (reçu par un vrai SDR) ou 🧮 calculé (formule). Un résultat simulé n'est jamais "
                            "une mesure."))
            self.badges[key] = b
            w = self.panels[key]
            try:
                if key == "chain":
                    self._top.insertWidget(0, b)
                elif key in ("cmp", "live"):
                    w.findChild(QtWidgets.QSplitter).widget(0).layout().insertWidget(0, b)
                else:
                    w.layout().insertWidget(0, b)
            except Exception:  # noqa: BLE001
                pass
            self.set_prov(key, "sim")

    def set_prov(self, key, prov):
        b = getattr(self, "badges", {}).get(key)
        if b is None:
            return
        c, bg = self.PROV_STYLE.get(prov, self.PROV_STYLE["sim"])
        b.setText(TR(PROVENANCE.get(prov, PROVENANCE["sim"])).upper())
        b.setStyleSheet(f"QLabel {{ color: {c}; background: {bg}; border: 1px solid {c}; border-radius: 6px; "
                        f"padding: 2px 8px; font-weight: 600; }}")
        b.setProperty("prov", prov)

    # ---- aide, focus et export de chaque graphe
    def _plot_title(self, p):
        if p in getattr(self, "md_plots", []) or p is getattr(self, "md_aplot", None):
            return "Spectre d'une modulation"
        t = p.objectName()[4:] if p.objectName().startswith("lab:") else ""
        return t if t in LAB_PLOT_HELP else re.sub(r"<[^>]+>", "", p.getPlotItem().titleLabel.text or "")

    def plot_help_text(self, p):
        h = lab_plot_help(self._plot_title(p), TR)
        if not h:
            return None
        return (TR("Ce que montre ce graphe : {}").format(h["shows"]) + "\n" +
                TR("On peut en déduire : {}").format(h["can"]) + "\n" + TR("On ne peut PAS en déduire : {}").format(h["cannot"]))

    def plot_help(self, p):
        txt = self.plot_help_text(p) or TR("Pas d'explication pour ce graphe.")
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Information, TR("❓ Que montre ce graphe ?"), txt,
                                    QtWidgets.QMessageBox.StandardButton.Ok, p.window())
        box.setWindowModality(Qt.WindowModality.NonModal)
        box.show()
        self._help_box = box
        return txt

    def _plot_menu(self, p, full=True):
        vb = p.getPlotItem().vb
        vb.menu.addSeparator()
        vb.menu.addAction(TR("❓ Que montre ce graphe ?")).triggered.connect(lambda *_, p=p: self.plot_help(p))
        if full:
            vb.menu.addAction(TR("🔍 Agrandir ce graphe (focus)")).triggered.connect(lambda *_, p=p: self.plot_focus(p))
        vb.menu.addAction(TR("💾 Exporter ce graphe (PNG)")).triggered.connect(lambda *_, p=p: self.plot_export(p))
        tip = self.plot_help_text(p)
        if tip:
            p.setToolTip((p.toolTip() + "\n\n" if p.toolTip() else "") + tip)
        if full:
            try:
                p.scene().sigMouseClicked.connect(lambda ev, p=p: ev.double() and self.plot_focus(p))
            except Exception:  # noqa: BLE001
                pass

    def plot_focus(self, p):
        """Double-clic (ou menu) : ce graphe prend toute la place de son panneau ; encore une fois = tout revient."""
        panel = next((w for w in self.panels.values() if w.isAncestorOf(p)), None)
        if panel is None:
            return False
        cur = self._focus.get(id(panel))
        if cur is not None:
            for q in cur[1]:
                q.show()
            self._focus.pop(id(panel), None)
            if cur[0] is p:
                self.owner.set_status(TR("Tous les graphes du panneau sont revenus."))
                return False
        hidden = [q for q in panel.findChildren(pg.PlotWidget) if q is not p and q.isVisible()]
        for q in hidden:
            q.hide()
        self._focus[id(panel)] = (p, hidden)
        self.owner.set_status(TR("Focus : double-clic sur le graphe (ou clic droit) pour revoir les autres."))
        return True

    def plot_export(self, p, path=None):
        d = Path(self.owner.log_dir) / "rapports"
        try:
            d.mkdir(parents=True, exist_ok=True)
            nm = re.sub(r"[^\w-]+", "_", self._plot_title(p))[:40].strip("_") or "graphe"
            path = path or str(d / f"labo_{nm}_{datetime.now():%Y%m%d_%H%M%S}.png")
            ok = p.grab().save(path)
        except OSError:
            ok = False
        self.owner.set_status(TR("💾 Graphe enregistré : {}").format(path) if ok else TR("⚠ Image impossible à enregistrer."))
        return path if ok else None

    # ---- sessions du labo (JSON dans <journaux>/labo/)
    def _sess_dir(self):
        return Path(self.owner.log_dir) / "labo"

    def session_save(self, kind, prov, params, metrics, note=""):
        doc = lab_session_doc(kind, prov, params, metrics, time.time(), note)
        try:
            d = self._sess_dir()
            d.mkdir(parents=True, exist_ok=True)
            path = str(d / f"{datetime.now():%Y%m%d_%H%M%S_%f}_{kind}.json")
            write_atomic(path, json.dumps(doc, ensure_ascii=False, indent=1, default=float))
        except (OSError, TypeError, ValueError):
            return None
        if getattr(self, "_sess_win", None) is not None and self._sess_win.isVisible():
            self.sessions_fill()
        return path

    def sessions_load(self):
        out = []
        d = self._sess_dir()
        if not d.is_dir():
            return out
        for f in sorted(d.glob("*.json"), reverse=True)[:300]:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if lab_session_ok(doc):
                out.append((str(f), doc))
        return out

    def _sess_label(self, doc):
        t = datetime.fromtimestamp(doc.get("t") or 0)
        m = doc.get("metrics") or {}
        extra = ""
        if doc["kind"] == "stair":
            extra = (f" · {m.get('ratio'):.2f}:1" if m.get("ratio") else "") + " · " + TR(STAIR_STATES.get(m.get("state"), ""))
        elif isinstance(m, dict):
            extra = " · " + TR("{} modèle(s)").format(len(m))
        return f"{t:%d/%m %H:%M:%S} · {TR(LAB_SESSION_KINDS[doc['kind']])} · {TR(PROVENANCE[doc['prov']])}{extra}" + (
            f" · {doc['note'][:60]}" if doc.get("note") else "")

    def open_sessions(self):
        w = getattr(self, "_sess_win", None)
        if w is None:
            w = QtWidgets.QWidget(None, Qt.WindowType.Window)
            w.setWindowTitle(TR("🗂 Sessions du labo"))
            v = QtWidgets.QVBoxLayout(w)
            t = QtWidgets.QLabel(TR("Chaque comparaison et chaque mesure à l'escalier est gardée ici (conditions + résultats "
                                    "chiffrés). Choisis-en deux du même genre pour voir ce qui a changé."))
            t.setWordWrap(True)
            v.addWidget(t)
            self.ss_list = QtWidgets.QListWidget()
            self.ss_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
            self.ss_list.itemSelectionChanged.connect(lambda *_: self.sessions_compare())
            v.addWidget(self.ss_list, 1)
            row = QtWidgets.QHBoxLayout()
            for txt, fn, tip in (("⚖ Comparer les 2 choisies", lambda: self.sessions_compare(), "Écarts entre les deux sessions."),
                                 ("💾 Exporter (CSV)", lambda: self.sessions_export(), "Les sessions choisies (ou toutes) en CSV."),
                                 ("📁 Dossier", lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self._sess_dir()))),
                                  "Ouvre le dossier des sessions."),
                                 ("🗑 Supprimer", lambda: self.sessions_delete(), "Efface les sessions choisies.")):
                b = QtWidgets.QPushButton(TR(txt))
                b.setToolTip(TR(tip))
                b.clicked.connect(lambda *_, fn=fn: fn())
                row.addWidget(b)
            v.addLayout(row)
            self.ss_tbl = QtWidgets.QTableWidget(0, 6)
            self.ss_tbl.setHorizontalHeaderLabels([TR(x) for x in ("Modèle", "Mesure", "A", "B", "B − A", "Unité")])
            self.ss_tbl.verticalHeader().setVisible(False)
            self.ss_tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            v.addWidget(self.ss_tbl, 1)
            self.ss_msg = QtWidgets.QLabel(TR("Un écart dit seulement ce qui a changé, pas lequel est « juste »."))
            self.ss_msg.setWordWrap(True)
            v.addWidget(self.ss_msg)
            w.resize(760, 560)
            fit_dialog(w, 760, 560)
            self._sess_win = w
        self.sessions_fill()
        w.show()
        w.raise_()
        return w

    def sessions_fill(self):
        lw = self.ss_list
        lw.blockSignals(True)
        lw.clear()
        for path, doc in self.sessions_load():
            it = QtWidgets.QListWidgetItem(self._sess_label(doc))
            it.setData(Qt.ItemDataRole.UserRole, path)
            lw.addItem(it)
        lw.blockSignals(False)

    def _sess_sel(self):
        lw = getattr(self, "ss_list", None)
        if lw is None:
            return []
        out = []
        for it in lw.selectedItems():
            try:
                out.append((it.data(Qt.ItemDataRole.UserRole),
                            json.loads(Path(it.data(Qt.ItemDataRole.UserRole)).read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                pass
        return out

    def sessions_compare(self, a=None, b=None):
        if a is None or b is None:
            sel = self._sess_sel()
            if len(sel) != 2:
                if hasattr(self, "ss_msg"):
                    self.ss_msg.setText(TR("Choisis exactement 2 sessions du même genre."))
                return None
            b, a = sel[0][1], sel[1][1]                  # la liste va du plus récent au plus ancien : A = l'ancienne
        rows = lab_session_diff(a, b)
        if hasattr(self, "ss_tbl"):
            t = self.ss_tbl
            t.setRowCount(0)
            for i, r in enumerate(rows):
                t.insertRow(i)
                for j, v_ in enumerate(r):
                    if j == 0 and v_ != "—":
                        v_ = TR(compander_card(v_)["model"]) if compander_card(v_) else v_
                    elif j == 1:
                        v_ = TR(v_)
                    elif isinstance(v_, float):
                        v_ = f"{v_:+.2f}" if j == 4 else f"{v_:.2f}"
                    t.setItem(i, j, QtWidgets.QTableWidgetItem("—" if v_ is None else str(v_)))
            t.resizeColumnsToContents()
            if a.get("kind") != b.get("kind"):
                self.ss_msg.setText(TR("Ces deux sessions ne sont pas du même genre : rien à comparer."))
            else:
                notes = [TR("⚠ Provenances différentes ({} / {}) : un simulé n'est pas une mesure.").format(
                    TR(PROVENANCE[a["prov"]]), TR(PROVENANCE[b["prov"]]))] if a["prov"] != b["prov"] else []
                if a.get("ver") != b.get("ver"):
                    notes.append(TR("⚠ Versions des modèles différentes ({} / {}).").format(a.get("ver"), b.get("ver")))
                self.ss_msg.setText(" ".join(notes) or TR("Un écart dit seulement ce qui a changé, pas lequel est « juste »."))
        return rows

    def sessions_export(self, path=None):
        sel = self._sess_sel() or self.sessions_load()
        d = self._sess_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
            path = path or str(d / f"sessions_{datetime.now():%Y%m%d_%H%M%S}.csv")
            buf = io.StringIO()
            wr = csv.writer(buf, delimiter=";")
            wr.writerow(["date", "genre", "provenance", "version", "modele", "mesure", "valeur", "note"])
            for _p, doc in sel:
                dt = f"{datetime.fromtimestamp(doc.get('t') or 0):%Y-%m-%d %H:%M:%S}"
                m = doc.get("metrics") or {}
                items = [("—", k, v) for k, v in m.items() if not isinstance(v, dict)] + \
                        [(k, k2, v2) for k, v in m.items() if isinstance(v, dict) for k2, v2 in v.items()]
                for mod, k, v in items:
                    wr.writerow([dt, doc["kind"], doc["prov"], doc.get("ver", ""), mod, k, v, doc.get("note", "")])
            write_atomic(path, buf.getvalue())
        except OSError as e:
            if hasattr(self, "ss_msg"):
                self.ss_msg.setText(TR("⚠ Export impossible : {}").format(e))
            return None
        if hasattr(self, "ss_msg"):
            self.ss_msg.setText(TR("💾 Exporté : {}").format(path))
        return path

    def sessions_delete(self):
        for path, _doc in self._sess_sel():
            try:
                os.remove(path)
            except OSError:
                pass
        self.sessions_fill()

    # ---- comparaison détaillée (grande fenêtre synchronisée)
    def cmp_detail(self, res=None):
        res = res or self.res_cmp
        if not res or not res.get("rows"):
            self.cm_msg.setText(TR("Compare d'abord (▶ Comparer)."))
            return None
        old = getattr(self, "_detail", None)
        if old is not None:
            old.close()
            old.deleteLater()
        real = "xin" not in res["rows"][0]               # son reçu (sinon : signaux de test de la comparaison)
        w = QtWidgets.QWidget(None, Qt.WindowType.Window)
        w.setWindowTitle(TR("🔍 Comparaison détaillée des compandeurs"))
        v = QtWidgets.QVBoxLayout(w)
        top = QtWidgets.QHBoxLayout()
        bd = QtWidgets.QLabel("")
        top.addWidget(bd)
        prov = res.get("meta", {}).get("prov") or "sim"
        c, bg = self.PROV_STYLE.get(prov, self.PROV_STYLE["sim"])
        bd.setText(TR(PROVENANCE[prov]).upper())
        bd.setStyleSheet(f"color:{c}; background:{bg}; border:1px solid {c}; border-radius:6px; padding:2px 8px; "
                         "font-weight:600;")
        meta = res.get("meta", {})
        info = QtWidgets.QLabel(TR("Son reçu, {} s · chaque modèle appliqué au même son (sans le son d'origine, on voit ce "
                                   "qu'il en fait, pas lequel est juste).").format(f"{meta.get('seconds', 0):.1f}") if real else
                                TR("Mêmes signaux et mêmes mesures pour tous les modèles · modèles {}").format(CMP_MODEL_VER))
        info.setWordWrap(True)
        top.addWidget(info, 1)
        v.addLayout(top)
        chk_row = QtWidgets.QHBoxLayout()
        chk_row.addWidget(QtWidgets.QLabel(TR("Afficher :")))
        w.chks = []
        for i, row in enumerate(res["rows"]):
            cb = QtWidgets.QCheckBox(TR(row["card"]["model"]))
            cb.setChecked(True)
            cb.setStyleSheet(f"color: {LAB_COLORS[i % len(LAB_COLORS)]}; font-weight: 600;")
            cb.toggled.connect(lambda *_: self._detail_draw())
            chk_row.addWidget(cb)
            w.chks.append(cb)
        chk_row.addStretch(1)
        v.addLayout(chk_row)
        grid = QtWidgets.QGridLayout()
        if real:
            titles = (("Niveau de chaque modèle", "s", "dBFS"), ("Son reçu (avant expanseur)", "s", "dBFS"),
                      ("EQ en direct", "Hz", "dB"), ("Phase en direct", "Hz", "degrés"))
        else:
            titles = (("Transfert du récepteur", "entrée dBFS", "sortie dBFS"), ("Saut −30 → −10 → −30 dBFS", "s", "dBFS"),
                      ("EQ de la chaîne", "Hz", "dB"), ("Phase (retard retiré)", "Hz", "degrés"))
        w.plots = []
        for i, (tt, xl, yl) in enumerate(titles):
            p = _lab_plot(tt, xl, yl)
            p.setObjectName("lab:" + tt)
            p.setMinimumSize(300, 220)
            if i >= 2:
                _log_hz(p)
            self._plot_menu(p, full=False)
            grid.addWidget(p, i // 2, i % 2)
            w.plots.append(p)
        w.plots[3].setXLink(w.plots[2])                      # EQ et phase : même zoom en fréquence
        if real:
            w.plots[1].setXLink(w.plots[0])                  # niveau et son reçu : même instant
        v.addLayout(grid, 1)
        cols = (("Modèle", None, ""),) + ((("Niveau", "out", "dBFS"), ("Crête", "pk", "dBFS"), ("Dynamique", "dyn", "dB"),
                                            ("Écart au son reçu", "gain", "dB"))
                                           if real else tuple((lab, k, u) for k, lab, u in LAB_DIFF_KEYS))
        tb = QtWidgets.QTableWidget(len(res["rows"]), len(cols))
        tb.setHorizontalHeaderLabels([TR(c_[0]) + (" (" + c_[2] + ")" if c_[2] else "") for c_ in cols])
        tb.verticalHeader().setVisible(False)
        tb.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, row in enumerate(res["rows"]):
            m = dict(row["m"], slope=row.get("slope"))
            for j, (_lab, k, _u) in enumerate(cols):
                if k is None:
                    it = QtWidgets.QTableWidgetItem(TR(row["card"]["model"]))
                    it.setForeground(QtGui.QColor(LAB_COLORS[i % len(LAB_COLORS)]))
                else:
                    val = m.get(k)
                    it = QtWidgets.QTableWidgetItem("—" if val is None else f"{val:.2f}")
                tb.setItem(i, j, it)
        tb.resizeColumnsToContents()
        tb.setMaximumHeight(60 + 28 * len(res["rows"]))
        v.addWidget(tb)
        w.tbl, w.res, w.real = tb, res, real
        self._detail = w
        self._detail_draw()
        w.resize(1100, 760)
        fit_dialog(w, 1100, 760)
        w.show()
        w.raise_()
        return w

    def _detail_draw(self):
        w = getattr(self, "_detail", None)
        if w is None:
            return
        res = w.res
        for p in w.plots:
            p.clear()
        for i, (row, cb) in enumerate(zip(res["rows"], w.chks)):
            if not cb.isChecked():
                continue
            col = LAB_COLORS[i % len(LAB_COLORS)]
            nm = TR(row["card"]["model"])
            pen = pg.mkPen(col, width=2.0)
            if w.real:
                w.plots[0].plot(row["te"], row["env_out"][:len(row["te"])], pen=pen, name=nm)
            else:
                w.plots[0].plot(row["xin"], row["rx"], pen=pen, name=nm)
                th = comp_curve(row["key"], "rx")
                if th is not None:
                    w.plots[0].plot(th[0], th[1], pen=pg.mkPen(col, width=1, style=Qt.PenStyle.DashLine))
                w.plots[1].plot(row["transient"]["t"], row["transient"]["env"], pen=pen, name=nm)
            fq = row.get("freq")
            if fq:
                w.plots[2].plot(fq["f"], _coh_mask(fq, fq["mag"]), pen=pen, name=nm, connect="finite")
                w.plots[3].plot(fq["f"], _coh_mask(fq, fq["phase"]), pen=pen, name=nm, connect="finite")
        if w.real:
            w.plots[1].plot(res["te"], res["env_src"][:len(res["te"])], pen=pg.mkPen(LAB_COLORS[0], width=1.6),
                            name=TR("son reçu"))
            w.plots[0].setYRange(-80, 5)
            w.plots[1].setYRange(-80, 5)
        else:
            w.plots[0].plot([-60, 0], [-60, 0], pen=pg.mkPen("#8e8e93", width=1, style=Qt.PenStyle.DotLine))
            w.plots[0].setYRange(-90, 10)
            w.plots[1].setYRange(-60, 0)
        w.plots[2].setYRange(-24, 12)
        w.plots[3].setYRange(-180, 180)

    # ---- sources réelles : chaîne complète sur l'IQ du poste SDR ou d'un enregistrement
    def chain_real(self, secs=1.0, wait=False):
        e = self._eng()
        if e is None or e.worker is None or e.a is None:
            self.ch_res.setText(TR("Pas de poste SDR en marche : démarre-le (▶ dans le Récepteur) et cale A sur un micro."))
            return False
        wk = e.worker
        g = dict(parts=[], n=0, want=int(wk.rate * secs), done=False, center=wk.center, rate=wk.rate)
        wk.iq_grab = g
        self._grab = (g, e)
        self.ch_res.setText(TR("⏳ Capture de {} s d'IQ autour de A…").format(f"{secs:g}"))
        if wait:
            t0 = time.time()
            while not g["done"] and time.time() - t0 < 10:
                QtWidgets.QApplication.processEvents()
                time.sleep(0.02)
            return self._grab_check(wait=True)
        QtCore.QTimer.singleShot(100, self._grab_check)
        return True

    def _grab_check(self, wait=False):
        gr = getattr(self, "_grab", None)
        if gr is None:
            return False
        g, e = gr
        if not g["done"]:
            if e.worker is None or e.worker.iq_grab is not g:
                self._grab = None
                self.ch_res.setText(TR("⚠ Capture interrompue : le poste SDR s'est arrêté."))
                return False
            QtCore.QTimer.singleShot(100, self._grab_check)
            return True
        self._grab = None
        iq = np.concatenate(g["parts"]) if g["parts"] else np.zeros(0, dtype=np.complex64)
        dem = e.demod or {}
        args = dict(iq=iq, fs=g["rate"], f_off=e.a * 1e6 - g["center"], mode=dem.get("mode", "wfm"),
                    dev=dem.get("dev"), rx_comp=dem.get("compander") or None, deemph_us=float(dem.get("deemph") or 0.0))
        self._real_src = TR("poste SDR, A = {} MHz").format(f"{e.a:.4f}")
        self._real_prov = "sim" if e.kind() == "demo" else "obs"
        return self._chain_real_go(args, wait)

    def chain_file(self, path=None, secs=1.0, f_mhz=None, wait=False):
        """Chaîne complète sur un enregistrement IQ SigMF (⏺ du temps réel, incident…)."""
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self.panels["chain"], TR("Enregistrement IQ"),
                                                            str(Path(self.owner.log_dir)),
                                                            "SigMF (*.sigmf-meta *.sigmf-data)")
            if not path:
                return False
        base = re.sub(r"\.sigmf-(meta|data)(\.part)?$", "", path)
        try:
            with open(base + ".sigmf-meta", encoding="utf-8") as fm:
                info = sigmf_info(json.load(fm))
            nb = IQ_BYTES[info["dtype"]]
            with open(base + ".sigmf-data", "rb") as fd:
                raw = fd.read(int(info["rate"] * secs) * nb)
            iq = np.asarray(iq_decode(info["dtype"], raw), dtype=np.complex64)
        except (OSError, ValueError, KeyError) as ex:
            self.ch_res.setText(TR("⚠ Lecture impossible : {}").format(ex))
            return False
        if len(iq) < int(info["rate"] * 0.05):
            self.ch_res.setText(TR("⚠ Enregistrement trop court."))
            return False
        if f_mhz is not None:
            f_off = f_mhz * 1e6 - info["center"]
        else:                                             # le signal le plus fort (hors continu au centre)
            nfft = 8192
            avg, _mx = rt_frames(iq[: (len(iq) // nfft) * nfft], nfft)
            Fo = (np.arange(nfft) - nfft // 2) * (info["rate"] / nfft)
            avg = np.where(np.abs(Fo) < 30e3, -300, avg)
            f_off = round(float(Fo[int(np.argmax(avg))]) / 1000.0) * 1000.0     # au kHz près (pas d'une case FFT)
        args = dict(iq=iq, fs=info["rate"], f_off=f_off, mode="wfm", dev=None, rx_comp=None, deemph_us=50.0)
        self._real_src = TR("enregistrement {} ({} MHz)").format(Path(base).name, f"{(info['center'] + f_off) / 1e6:.4f}")
        self._real_prov = "obs"
        return self._chain_real_go(args, wait)

    def _chain_real_go(self, args, wait):
        if wait:
            try:
                r = lab_chain_iq(**args)
            except Exception as ex:  # noqa: BLE001
                return self._chain_real_done(None, ex)
            return self._chain_real_done(r, None)
        self._busy(True, self.ch_go, "▶ Calculer")
        self.owner.run_heavy(lambda: lab_chain_iq(**args), self._chain_real_done, what="Labo SDR")
        return True

    # ---- 8.1 : chaîne complète EN DIRECT (Clément : « voir les courbes simulées en direct avec le générateur qui tourne »)
    def chain_live(self, on=True):
        self._clive = bool(on)
        if self.ch_live.isChecked() != self._clive:
            self.ch_live.blockSignals(True)
            self.ch_live.setChecked(self._clive)
            self.ch_live.blockSignals(False)
        tm = getattr(self, "_clive_tm", None)
        if tm is None:
            tm = self._clive_tm = QtCore.QTimer(self)
            tm.setInterval(150)
            tm.timeout.connect(self._clive_step)
        self._clive_grab, self._clive_job, self._clive_tuned = None, False, False
        if not on:
            tm.stop()
            self.ch_res.setText(TR("En direct arrêté : les graphes gardent la dernière image."))
            return False
        if self._eng() is None:
            self.owner.simulate(True)
            self.ch_res.setText(TR("⏳ Démarrage de la simulation (SDR démo)…"))
        tm.start()
        return True

    def _clive_target(self, e):
        """A n'est sur aucun signal ? -> la fréquence où le caler : le micro suivi le plus proche (sinon, en démo, un micro
        simulé ; sinon le signal le plus fort de la fenêtre). None = A est déjà sur une porteuse."""
        fr = e.last
        if fr is not None and len(fr["F"]) == len(fr["avg"]) and sdr_carrier(fr["F"], fr["avg"], e.a):
            return None
        fs = [float(w["freq"]) for w in (e.ws() or []) if not w.get("muted") and not w.get("off") and not w.get("bw")]
        if not fs and e.kind() == "demo":
            fs = [float(s["f"]) for s in SDR_DEMO_STATE.get("plan") or [] if s.get("kind") == "fm"]
        if fs:
            return min(fs, key=lambda f: abs(f - e.a))
        if fr is not None and len(fr["F"]) == len(fr["avg"]) and len(fr["F"]) > 8:
            F, L = np.asarray(fr["F"], dtype=float), np.asarray(fr["avg"], dtype=float)
            L = np.where(np.abs(F - float(np.median(F))) < 0.05, -300, L)       # pas le pic du continu au centre
            return float(F[int(np.argmax(L))])
        return None

    def _clive_step(self):
        if not getattr(self, "_clive", False) or self._clive_job:
            return
        e = self._eng()
        if e is None or e.worker is None or e.a is None:
            self.ch_res.setText(TR("⏳ En direct : en attente du poste SDR (▶ dans le Récepteur, A sur un micro)…"))
            self._clive_grab = None
            return
        gr = self._clive_grab
        wk = e.worker
        if gr is None:
            if not self._shown("chain"):
                return
            if not getattr(self, "_clive_tuned", False) and e.last is not None:
                self._clive_tuned = True
                f_ = self._clive_target(e)
                if f_ is not None and e.set_a(f_) is not False:
                    self.owner.set_status(TR("⏯ En direct : A n'était sur aucun signal, calé sur {} MHz.").format(f"{f_:.4f}"))
                    return                                     # le poste se recentre : on capture au tour suivant
            g = dict(parts=[], n=0, want=int(wk.rate * 0.4), done=False, center=wk.center, rate=wk.rate)
            wk.iq_grab = g
            self._clive_grab = (g, e, time.time())
            return
        g, e0, t0 = gr
        if e0 is not e or (not g["done"] and (wk.iq_grab is not g or time.time() - t0 > 4.0)):
            self._clive_grab = None                         # poste changé, arrêté ou trop lent : on recommence
            return
        if not g["done"]:
            return
        self._clive_grab = None
        iq = np.concatenate(g["parts"]) if g["parts"] else np.zeros(0, dtype=np.complex64)
        dem = e.demod or {}
        args = dict(iq=iq, fs=g["rate"], f_off=e.a * 1e6 - g["center"], mode=dem.get("mode", "wfm"),
                    dev=dem.get("dev"), rx_comp=dem.get("compander") or None, deemph_us=float(dem.get("deemph") or 0.0))
        self._real_src = TR("poste SDR, A = {} MHz").format(f"{e.a:.4f}") + " · " + TR("en direct")
        self._real_prov = "sim" if e.kind() == "demo" else "obs"
        self._clive_job = True

        def done(r, err):
            self._clive_job = False
            if getattr(self, "_clive", False):
                self._chain_real_done(r, err, live=True)
        self.owner.run_heavy(lambda: lab_chain_iq(**args), done, what="Labo SDR")

    def _chain_real_done(self, r, err, live=False):
        if not live:
            self._busy(False, self.ch_go, "▶ Calculer")
        if err is not None or r is None:
            self.ch_res.setText(TR("⚠ Calcul impossible : {}").format(err))
            return None
        self.res_chain = r
        prov = getattr(self, "_real_prov", "obs")
        self.set_prov("chain", prov)
        self.ch_help.setText(TR("Signal réel : les réglages Son, Émetteur, C/N et Panne ne s'appliquent pas ici (ils servent "
                                "à la simulation, ▶ Calculer). Vues RF prises au moment où le son est le plus fort."))
        for p in (self.p_wave, self.p_env, self.p_iq, self.p_const, self.p_spec, self.p_fi):
            p.clear()
        out = r["out"]
        s0 = max(0, min(len(out) - 4800, int(0.2 * 48000)))
        tm = np.arange(min(4800, len(out) - s0)) / 48.0
        self.p_wave.plot(tm, out[s0:s0 + len(tm)], pen=pg.mkPen(LAB_COLORS[1], width=1.0), name=TR("son démodulé"))
        self.p_env.plot(r["te"], r["env_out"][:len(r["te"])], pen=pg.mkPen(LAB_COLORS[1], width=1.2), name=TR("sortie"))
        self.p_env.setYRange(-80, 5)
        self.p_iq.plot(r["iq_t"], r["I"], pen=pg.mkPen(LAB_COLORS[0], width=1), name="I")
        self.p_iq.plot(r["iq_t"], r["Q"], pen=pg.mkPen(LAB_COLORS[3], width=1), name="Q")
        v = r.get("views")
        if v:
            self.p_const.plot(v["I"], v["Q"], pen=None, symbol="o", symbolSize=3, symbolPen=None,
                              symbolBrush=pg.mkBrush(LAB_COLORS[0]))
            self.p_fi.plot(v["tf"], v["finst"], pen=pg.mkPen(LAB_COLORS[2], width=1))
        if r["L"] is not None:
            self.p_spec.plot(r["F"], r["L"], pen=pg.mkPen(LAB_COLORS[0], width=1), name=TR("moyenne"))
            self.p_spec.plot(r["F"], r["Lmax"], pen=pg.mkPen(LAB_COLORS[1], width=1), name=TR("max"))
            if not live or not getattr(self, "live_frames", 0):     # en direct : le zoom choisi est gardé
                self.p_spec.setXRange(-200, 200)
        m = r["m"]
        rows = [(TR("Source"), getattr(self, "_real_src", "")), (TR("Niveau du son"), f"{m['out']:.1f} dBFS"),
                (TR("Crête"), f"{m['pk_out']:.1f} dBFS"),
                (TR("Dynamique"), "—" if m["dyn"] is None else f"{m['dyn']:.0f} dB"), (TR("Durée"), f"{m['seconds']:.2f} s")]
        fl = "".join(f"<li style='color:{self.owner.tone_color(t) if t != 'ok' else 'inherit'}'>{_hesc(x)}</li>"
                     for x, t in lab_findings_real(r, TR))
        self.ch_res.setText(f"<b>{_hesc(TR(PROVENANCE[prov]))}</b> · " + " · ".join(
            f"{_hesc(a)} : <b>{_hesc(b)}</b>" for a, b in rows) + f"<ul>{fl}</ul>")
        if live:
            self.live_frames = getattr(self, "live_frames", 0) + 1
            return r
        mm = {k: (None if v_ is None or not np.isfinite(v_) else round(float(v_), 3)) for k, v_ in m.items()}
        self.session_save("chain", prov, dict(source=getattr(self, "_real_src", ""), mode=r["mode"], dev=r["dev"]), mm)
        return r

    # ---- compandeurs sur le vrai son reçu : figer quelques secondes et comparer en grand
    def live_snapshot(self, secs=4.0, wait=False):
        xs = list(self.lv_in)
        x = np.concatenate(xs) if xs else np.zeros(0, dtype=np.float32)
        x = x[-int(secs * 48000):]
        if len(x) < 48000 or not self.lv_keys:
            self.lv_fit.setText(TR("Pas assez de son reçu (au moins 1 s) ou aucun modèle coché."))
            return None
        e = self._eng()
        de = float((e.demod or {}).get("deemph") or 50.0) if e is not None else 50.0
        prov = "sim" if (e is None or e.kind() == "demo") else "obs"
        keys = list(self.lv_keys)

        def done(r, err):
            if err is not None or r is None:
                self.lv_fit.setText(TR("⚠ Calcul impossible : {}").format(err))
                return
            r["meta"]["prov"] = prov
            self.res_real = r
            self.session_save("cmp_real", prov, dict(seconds=round(len(x) / 48000.0, 2), deemph=de),
                              {row["key"]: {k: (None if v_ is None else round(float(v_), 3)) for k, v_ in row["m"].items()}
                               for row in r["rows"]})
            self.cmp_detail(r)
        if wait:
            done(comp_compare_real(keys, x, de), None)
            return self.res_real
        self.owner.run_heavy(lambda: comp_compare_real(keys, x, de), done, what="Labo SDR")
        return True

    # ---- état de la mesure à l'escalier
    def stair_status(self):
        xs = list(self.lv_in)
        secs = sum(len(a) for a in xs) / 48000.0
        need = 2 * STAIR_PERIOD + 1
        r = getattr(self, "_st_res", None)
        e = self._eng()
        if r is not None:
            st, why = r[0], r[1]
            txt = TR(STAIR_STATES[st]) + (" · " + " ".join(TR(x) for x in why) if why else " · " + TR("mesure valable"))
        elif e is None:
            st = "stopped" if secs > 0 else "ready"
            txt = (TR(STAIR_STATES[st]) + " · " + (TR("le poste SDR s'est arrêté pendant l'enregistrement")
                                                   if secs > 0 else TR("démarre un poste SDR et écoute le micro en A")))
        elif secs < need:
            st = "running"
            txt = TR(STAIR_STATES[st]) + f" · {secs:.0f} / {need:.0f} s"
        else:
            st = "ready"
            txt = TR(STAIR_STATES[st]) + " · " + TR("assez de son pour mesurer")
        col = {"done": "#30d158", "invalid": "#ff453a", "stopped": "#ff9f0a", "running": "#64d2ff"}.get(st, "#8e8e93")
        if hasattr(self, "lv_state"):
            self.lv_state.setText(f"● {txt}")
            self.lv_state.setStyleSheet(f"color: {col}; font-weight: 600;")
        return st, txt

    # ---- modulations : découverte / indices / quiz, + le signal de A
    def _mod_draw(self):
        rows = getattr(self, "res_mod", None)
        if not rows:
            return
        step = self.md_step.currentData()
        order = self._md_order if step == "quiz" else list(range(len(rows)))
        for i, (p, idx) in enumerate(zip(self.md_plots, order)):
            r = rows[idx]
            p.clear()
            c = r["cls"]
            p.plot((r["F"] - 100.0) * 1000.0, r["L"], pen=pg.mkPen(LAB_COLORS[0], width=1))
            if step == "discover":
                ok = (" (" + TR("pas de case « AM » dans la détection") + ")") if r["ok"] is None else \
                    (" ✔" if r["ok"] else " ✖")
                p.setTitle(TR(r["name"]), size="9pt")
                col = "#8e8e93" if r["ok"] is None else (LAB_COLORS[2] if r["ok"] else LAB_COLORS[4])
                ti = pg.TextItem(TR("deviné : {}").format(TR(c.get("name", ""))) + ok, color=col, anchor=(0, 0),
                                 fill=pg.mkBrush(20, 20, 22, 200))
                ti.setPos(-r["span"] * 1000.0, float(np.nanmax(r["L"])) + 2.0)
                p.addItem(ti)
                p.setToolTip(TR(c.get("why", "")) + (f"\n−20 dB : {c['bw_khz']:.1f} kHz" if c.get("bw_khz") else ""))
            else:
                p.setTitle(TR("Signal {}").format(i + 1), size="9pt")
                if step == "hints":
                    ti = pg.TextItem(mod_hint(r, TR), color="#8e8e93", anchor=(0, 0), fill=pg.mkBrush(20, 20, 22, 200))
                    ti.setPos(-r["span"] * 1000.0, float(np.nanmax(r["L"])) + 2.0)
                    p.addItem(ti)
                p.setToolTip(TR("Quel est ce signal ?"))
            p.setXRange(-r["span"] * 1000.0, r["span"] * 1000.0, padding=0.02)
            p.enableAutoRange(axis="y", enable=True)
        quiz = step == "quiz"
        for cb in self.md_ans:
            cb.setVisible(quiz)
        self.md_check.setVisible(quiz)
        self.md_score.setVisible(quiz)
        if quiz:
            self.md_score.setText(TR("Choisis un nom sous chaque spectre, puis ✔ Vérifier."))

    def _mod_step(self):
        rows = getattr(self, "res_mod", None)
        if self.md_step.currentData() == "quiz" and rows:
            self._md_order = [int(i) for i in np.random.default_rng().permutation(len(rows))]
            for cb in self.md_ans:
                cb.setCurrentIndex(0)
        self._mod_draw()

    def mod_check(self, answers=None):
        rows = getattr(self, "res_mod", None)
        if not rows:
            return None
        truth = [rows[i]["name"] for i in self._md_order]
        if answers is None:
            answers = [cb.currentData() for cb in self.md_ans]
        good, tot, ok = mod_quiz_score(answers, truth)
        for cb, k in zip(self.md_ans, ok):
            cb.setStyleSheet(f"color: {LAB_COLORS[2] if k else LAB_COLORS[4]}; font-weight: 600;")
        self.md_score.setText(TR("{} / {} bonnes réponses · réponses : {}").format(
            good, tot, " · ".join(f"{i + 1}. {TR(t)}" for i, t in enumerate(truth))))
        return good, tot, ok

    def mod_add_a(self):
        """📡 Le signal réel de A (spectre du poste SDR) à côté des modèles, avec ce que l'appli en devine."""
        e = self._eng()
        fr = e.last if e is not None else None
        if e is None or fr is None or e.a is None or len(fr["F"]) != len(fr["avg"]):
            self.md_info.setText(TR("Pas de poste SDR en marche : démarre-le et cale A sur un signal."))
            return None
        F, L = np.asarray(fr["F"], dtype=float), np.asarray(fr["avg"], dtype=float)
        mx = fr.get("mx")                                 # crêtes du dernier morceau : l'excursion FM s'y voit mieux
        if mx is not None and len(mx) == len(F):
            L = np.maximum(L, np.asarray(mx, dtype=float))
        span = 0.5
        msk = np.abs(F - e.a) <= span
        if msk.sum() < 8:
            self.md_info.setText(TR("A est au bord de la fenêtre du SDR : recentre-le."))
            return None
        c = classify_signal(F[msk], L[msk], e.a, getattr(e, "pilot", None), span=span)
        p = self.md_aplot
        p.clear()
        p.show()
        prov = "sim" if e.kind() == "demo" else "obs"
        p.setTitle(TR("📡 Signal de A ({} MHz) · {}").format(f"{e.a:.4f}", TR(PROVENANCE[prov])), size="9pt")
        p.plot((F[msk] - e.a) * 1000.0, L[msk], pen=pg.mkPen(LAB_COLORS[1], width=1.2))
        ti = pg.TextItem(TR("deviné : {}").format(TR(c.get("name", ""))), color=LAB_COLORS[1], anchor=(0, 0),
                         fill=pg.mkBrush(20, 20, 22, 200))
        ti.setPos(-span * 1000.0, float(np.nanmax(L[msk])) + 2.0)
        p.addItem(ti)
        p.setXRange(-span * 1000.0, span * 1000.0, padding=0.02)
        self.set_prov("mod", prov)
        self.md_info.setText(TR("À côté des modèles : le vrai signal de A. Compare sa largeur et sa forme."))
        return c


def lab_grid(mw, docks):
    """8.2 : vrai affichage Labo : les 5 panneaux en grille dans la fenêtre mw (QMainWindow) — chaîne | compandeurs en
    haut, en direct | modulations + pannes (onglets) en bas. docks = {clé: QDockWidget}."""
    B = Qt.DockWidgetArea.BottomDockWidgetArea
    ks = [k for k in LAB_KEYS if k in docks]
    for k in ks:
        mw.removeDockWidget(docks[k])
        docks[k].setFloating(False)
    if not ks:
        return
    mw.addDockWidget(B, docks[ks[0]])
    pos = {"chain": None, "cmp": ("chain", Qt.Orientation.Horizontal), "live": ("chain", Qt.Orientation.Vertical),
           "mod": ("cmp", Qt.Orientation.Vertical), "fault": ("mod", None)}
    placed = {ks[0]}
    for k in ks[1:]:
        ref, ori = pos.get(k) or (None, None)
        if ref not in placed:
            ref, ori = ks[0], Qt.Orientation.Horizontal
        if ori is None:
            mw.tabifyDockWidget(docks[ref], docks[k])
        else:
            mw.splitDockWidget(docks[ref], docks[k], ori)
        placed.add(k)
    for k in ks:
        docks[k].show()
    if "mod" in docks:
        docks["mod"].raise_()

    def sizes():                                             # grille à parts égales (sinon Qt donne tout à la chaîne)
        try:
            W, H = max(800, mw.width()), max(500, mw.height())
            cols = [docks[k] for k in ("chain", "cmp") if k in docks]
            if len(cols) == 2:
                mw.resizeDocks(cols, [W // 2, W // 2], Qt.Orientation.Horizontal)
            rows = [docks[k] for k in ("chain", "live") if k in docks]
            if len(rows) == 2:
                mw.resizeDocks(rows, [int(H * 0.6), int(H * 0.4)], Qt.Orientation.Vertical)
        except RuntimeError:
            pass
    QtCore.QTimer.singleShot(0, sizes)
    QtCore.QTimer.singleShot(150, sizes)


LAB_VIEWS = (("tabs", "▤ Rangé : un panneau à la fois (onglets)"), ("grid", "▦ Tout à l'écran (grille)"),
             ("dual", "🖥🖥 Sur 2 écrans (chaîne et direct ici, le reste sur l'autre)"))


class LabMixin:
    """Labo SDR : panneaux, affichage Labo, tableau des SDR. (Méthodes de MainWindow, regroupées par thème.)"""

    def open_sdr_lab(self, tab=0):
        """Montre les panneaux du labo (en onglets en bas la 1re fois ; ensuite là où tu les as mis) et met devant celui
        demandé (n° ou clé)."""
        key = LAB_KEYS[int(tab)] if isinstance(tab, int) else str(tab)
        docks = self.lab_docks
        if not getattr(self, "_lab_hid_done", False):        # graphes masqués (config lue après la création du labo)
            self._lab_hid_done = True
            self._sdrlab.apply_hidden()
        if not any(d.isVisible() or d.objectName() in self.panel_wins for d in docks.values()):
            first = None
            for k in LAB_KEYS:
                d = docks[k]
                if d.objectName() in self.panel_wins:
                    continue
                if first is None:
                    if d.isFloating() or self.dockWidgetArea(d) == Qt.DockWidgetArea.NoDockWidgetArea:
                        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d)
                    first = d
                elif self.dockWidgetArea(d) == self.dockWidgetArea(first) and not d.isFloating():
                    self.tabifyDockWidget(first, d)
                d.show()
        d = docks[key]
        w = self.panel_wins.get(d.objectName())
        if w is not None:
            w.show()
            w.raise_()
        else:
            d.show()
            d.raise_()
        return self._sdrlab

    def close_sdr_lab(self):
        for d in self.lab_docks.values():
            self.panel_window(d, False)
            d.hide()
        self._sdrlab.stop()

    def lab_view(self, on=True, how=None):
        """8.2 (Clément : « avec un vrai affichage labo ? », puis « trop de fenêtres, plus rangé ou double écran ») : la
        fenêtre principale ne montre plus que le labo — rangé en onglets (défaut), en grille, ou réparti sur 2 écrans ; les
        panneaux sortis en vraie fenêtre restent où ils sont. off = retour à la disposition du mode."""
        if on is True and how is None:
            how = self.sdr_cfg.get("lab_view", "tabs")
        if on and not getattr(self, "_lab_hid_done", False):
            self._lab_hid_done = True
            self._sdrlab.apply_hidden()
        docks = {k: d for k, d in self.lab_docks.items() if d.objectName() not in self.panel_wins}
        if on:
            how = how if how in dict(LAB_VIEWS) else "tabs"
            self.sdr_cfg["lab_view"] = how
            if self.screen_hosts:
                self.screens_off(relayout=False)
            if how == "dual" and len(self.screen_list()[0]) < 2:
                how = "grid"
                self.set_status(TR("Un seul écran : le labo s'affiche en grille."))
            if how == "dual":
                scrs, main = self.screen_list()
                other = next(i for i in range(len(scrs)) if i != main)
                plan = {n: SCREEN_HIDE for n, _g, _t in SCREEN_PANELS}
                for k, _t, n in LAB_DOCKS:
                    plan[n] = main if k in ("chain", "live") else other
                self.screens_apply(plan, quiet=True, keep_mode=True)
                docks = {k: d for k, d in self.lab_docks.items() if k in ("chain", "live")}
            for d in self.docks:
                if d not in self.lab_docks.values() and d.objectName() not in self.panel_wins:
                    d.hide()
            self.dock_wall.hide()
            if how == "tabs":
                B = Qt.DockWidgetArea.BottomDockWidgetArea
                ks = [k for k in LAB_KEYS if k in docks]
                for k in ks:
                    self.removeDockWidget(docks[k])
                    docks[k].setFloating(False)
                if ks:
                    self.addDockWidget(B, docks[ks[0]])
                    for k in ks[1:]:
                        self.tabifyDockWidget(docks[ks[0]], docks[k])
                    for k in ks:
                        docks[k].show()
                    docks[ks[0]].raise_()
            else:
                lab_grid(self, docks)
            self.lab_view_on = True
            QtCore.QTimer.singleShot(0, self._fit_screen)
            self.set_status(TR("🧪 Affichage Labo : bouge les panneaux comme tu veux ; « ↩ Quitter l'affichage Labo » "
                               "(menu du mode ou panneau Chaîne) pour revenir."))
        else:
            self.lab_view_on = False
            for d in docks.values():
                d.hide()
            self._sdrlab.stop()
            self.set_rf_mode(self.rf_mode)
        try:
            self._sdrlab.view_btn.setText(TR("↩ Quitter l'affichage Labo") if on else TR("⛶ Affichage Labo"))
        except Exception:  # noqa: BLE001
            pass
        return how if on else False

    lab_view_on = False

    def _make_lab(self):
        """8.2 : le labo SDR en 5 panneaux (créés avec les autres : la disposition enregistrée les replace ; ils sont dans
        🪟 Fenêtres, se sortent en vraie fenêtre, se mettent sur l'écran qu'on veut)."""
        self._sdrlab = SdrLab(self)
        self.lab_docks = {}
        B = Qt.DockWidgetArea.BottomDockWidgetArea
        acts = self.win_menu.actions()
        sep = next((x for x in acts if x.isSeparator()), None)
        for key, title, name in LAB_DOCKS:
            d = self._make_dock(TR(title), name, self._sdrlab.panels[key], B)
            d.hide()
            self.lab_docks[key] = d
            self.docks.append(d)
            if sep is not None:
                self.win_menu.insertAction(sep, d.toggleViewAction())
            else:
                self.win_menu.addAction(d.toggleViewAction())

    def all_lab_docks(self):
        return list((getattr(self, "lab_docks", None) or {}).values())

    def open_sdr_compat(self):
        """8.2 : tableau de compatibilité des SDR (ce que l'appli sait faire avec chacun, et ce qui a été essayé en vrai)."""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(TR("📋 SDR pris en charge"))
        fit_dialog(d, 1000, 520)
        v = QtWidgets.QVBoxLayout(d)
        t = QtWidgets.QLabel(TR("Ce que l'appli sait faire avec chaque SDR. « Essayé en vrai » : non pour tous à ce jour (fait "
                                "sur des faux SDR et le 🧪 SDR démo)."))
        t.setWordWrap(True)
        v.addWidget(t)
        rows = sdr_compat_rows()
        cols = ("SDR", "Plage", "Bits", "Débit max", "Fenêtre utile", "Balayage", "Écoute / IQ", "Émission",
                "dBm calibrés", "Essayé en vrai", "Fiche")
        tb = QtWidgets.QTableWidget(len(rows), len(cols))
        tb.setHorizontalHeaderLabels([TR(c) for c in cols])
        tb.verticalHeader().setVisible(False)
        tb.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        yes, no = "✔", "—"
        for i, r in enumerate(rows):
            vals = (r["name"], r["range"], str(r["bits"] or "—"), f"{r['rate']:g} MS/s" if r["rate"] else "—",
                    f"{r['span']:g} MHz" if r["span"] else "—", yes if r["sweep"] else no, yes if r["iq"] else no,
                    yes if r["tx"] else no, yes if r["dbm"] else no, TR("non"), TR(r["src"]))
            for j, x in enumerate(vals):
                tb.setItem(i, j, QtWidgets.QTableWidgetItem(x))
        tb.resizeColumnsToContents()
        v.addWidget(tb, 1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(d.close)
        v.addWidget(bb)
        self._compat_dlg = d
        d.show()
        return d


def self_test(path):
    """RF-Technical-Monitor.exe --selftest fichier : vérifie que l'EXE contient bien ce qui est chargé à la demande
    (réseau socket://, traductions, son). Lancé par la CI après PyInstaller (7.23.2 : sans protocol_socket dans
    l'exe, le tinySA en réseau était impossible : « invalid URL, protocol 'socket' not known »)."""
    import importlib
    import socket as _s
    out, fails = [], 0

    def check(label, fn):
        nonlocal fails
        try:
            fn()
            out.append(f"OK   {label}")
        except Exception as e:  # noqa: BLE001
            fails += 1
            out.append(f"FAIL {label} : {type(e).__name__} : {e}")

    def net():
        srv = _s.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        ser = serial.serial_for_url(f"socket://127.0.0.1:{srv.getsockname()[1]}", 115200, timeout=2)
        conn, _ = srv.accept()
        conn.sendall(b"ch> ")
        got = ser.read(4)
        ser.close()
        conn.close()
        srv.close()
        assert got == b"ch> ", got

    check("tinySA en réseau (socket://, relais / Raspberry Pi)", net)
    check("traductions anglaises (lang_en)", lambda: importlib.import_module("lang_en"))
    check("son (PySide6.QtMultimedia)", lambda: importlib.import_module("PySide6.QtMultimedia"))
    check("une seule instance (PySide6.QtNetwork)", lambda: importlib.import_module("PySide6.QtNetwork").QLocalServer)
    check("QR code (segno)", lambda: importlib.import_module("segno").make("http://192.168.1.2:8080/").matrix)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    check("manuels embarqués (FR + EN)", lambda: [(base / "docs" / n).stat() for n in ("manuel.html", "manual_en.html")])
    out.append(f"ÉCHECS: {fails}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return fails


def _instance_name():
    """Nom du canal local de l'appli (un par dossier de config, donc un par utilisateur Windows)."""
    import hashlib
    return "RFTechnicalMonitor-" + hashlib.sha1(str(CFG_PATH.parent).encode("utf-8")).hexdigest()[:12]


def single_instance(app):
    """8.0.3 (Clément : « je peux ouvrir plusieurs fois le logiciel ») : un verrou dans le dossier de config. Déjà
    ouverte -> on lui demande de revenir devant et on rend None (cette 2ᵉ copie se ferme). Une relance (langue, garde)
    attend jusqu'à 20 s que l'ancienne soit fermée. TSM_MULTI=1 : plusieurs copies permises (dépannage).
    -> le serveur local (QLocalServer) à garder, ou None."""
    from PySide6 import QtNetwork
    if os.environ.get("TSM_MULTI") == "1":
        return QtNetwork.QLocalServer(app)
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = QtCore.QLockFile(str(CFG_PATH.parent / "instance.lock"))
    lock.setStaleLockTime(0)                 # verrou d'une appli plantée (processus mort) : repris tout seul
    wait = 20000 if os.environ.get("TSM_WAIT_INSTANCE") == "1" else 300
    if not lock.tryLock(wait):
        sock = QtNetwork.QLocalSocket()
        sock.connectToServer(_instance_name())
        if sock.waitForConnected(1500):
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(1000)
            sock.disconnectFromServer()
        else:
            QtWidgets.QMessageBox.information(None, APP_NAME, TR("RF Technical Monitor est déjà ouvert sur ce PC (regarde dans la "
                                                                 "barre des tâches)."))
        return None
    app._instance_lock = lock
    srv = QtNetwork.QLocalServer(app)
    QtNetwork.QLocalServer.removeServer(_instance_name())
    srv.listen(_instance_name())
    return srv


def _instance_wake(srv, win):
    """Une 2ᵉ copie a été lancée : la fenêtre déjà ouverte revient devant."""
    while srv.hasPendingConnections():
        c = srv.nextPendingConnection()
        c.disconnected.connect(c.deleteLater)
    try:
        if win.isMinimized():
            win.showNormal()
        win.show()
        win.raise_()
        win.activateWindow()
        win.set_status(TR("RF Technical Monitor était déjà ouvert : le voici."))
    except Exception:  # noqa: BLE001
        pass


def main():
    if "--selftest" in sys.argv:            # CI : contrôle de l'exe, sans fenêtre
        i = sys.argv.index("--selftest")
        sys.exit(1 if self_test(sys.argv[i + 1] if i + 1 < len(sys.argv) else "selftest.txt") else 0)
    if "--garde" in sys.argv:               # garde : lance l'appli et la relance si elle plante / se fige
        run_guard()
        sys.exit(0)
    app = QtWidgets.QApplication(sys.argv)
    app._gc_timer = install_gc_main_thread(app)
    app._lang = read_language()
    if not install_language(app._lang):
        app._lang = "fr"
        install_french(app)
    ico = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for cand in (ico / "icone.png", ico / "assets" / "icone.png"):     # exe (PyInstaller) ou sources
        if cand.exists():
            app.setWindowIcon(QtGui.QIcon(str(cand)))
            break
    app._crash_fh = install_crash_log(app)
    if "--relais" in sys.argv:              # PC où est branché le 2ᵉ tinySA : juste le relais réseau
        win = RelayWindow()
    else:
        inst = single_instance(app)         # 8.0.3 : déjà ouverte -> on la ramène devant, on ne s'ouvre pas 2 fois
        if inst is None:
            sys.exit(0)
        win = MainWindow()
        inst.newConnection.connect(lambda: _instance_wake(inst, win))
    win.show()
    sys.exit(app.exec())
