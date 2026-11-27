# SDR : postes, mode, récepteurs en réseau, sons, démo, assistant, écrans (méthodes de la fenêtre).
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


# ---------------------------------------------------------------- V8 étape 6 : branchements sur les prises de la V7
class V8Bridge(QtCore.QObject):
    """Passe une commande du fil du serveur web au fil de l'interface (signal en file d'attente)."""
    req = Signal(object)


# Étape 17 : les SDR sur la carte, comme les tinySA (tuile « 📡 », glisser sur une scène = la surveiller, liens, état)


def _v8_post_live(e):
    return e is not None and e.running() and e.last is not None and time.time() - float(e.last.get("t") or 0) < 5


# ---------------------------------------------------------------- V8 étape 16 : le SDR au cœur (panneaux, modes)
SDR_DOCKS = (("rx", "📡 SDR · Récepteur", "dock_sdr_rx", "SdrReceiverPanel"),
             ("spec", "📡 SDR · Spectre", "dock_sdr_spec", "SdrSpectrumPanel"),
             ("wf", "📡 SDR · Waterfall", "dock_sdr_wf", "SdrWaterfallPanel"),
             ("mics", "📡 SDR · Mes micros", "dock_sdr_mics", "SdrMicsPanel"),
             ("diag", "📡 SDR · Diagnostic", "dock_sdr_diag", "SdrDiagPanel"))


class SdrPostsMixin:
    """Postes SDR : panneaux, carte, page web, incidents. (Méthodes de MainWindow, regroupées par thème.)"""

    def web_extra(self):
        br = getattr(self, "_v8_bridge", None)
        if br is None:
            br = self._v8_bridge = V8Bridge()
            br.req.connect(self.web_listen_do, Qt.ConnectionType.QueuedConnection)
        return ({"/ecoute.pcm": (("ecoute",), self.web_listen_pcm), "/ecoute.json": (("ecoute",), self.web_listen_json)},
                {"/ecoute": (listen_request, br.req.emit)})

    def open_incidents(self):
        """9. 📦 Rejouer un incident SDR : choisir son dossier (journaux/incidents/date/incident_…)."""
        root = Path(self.log_dir) / "incidents"
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier d'incident à rejouer", str(root if root.is_dir()
                                                                                               else self.log_dir))
        if d:
            open_incident(self, d)

    def open_sdr_posts(self):
        """📡 Mes SDR (fenêtre gardée)."""
        d = getattr(self, "_posts_dlg", None)
        if d is None:
            d = self._posts_dlg = SdrPostsDialog(self)
        d.fill()
        d.show()
        d.raise_()
        return d

    def _make_post(self, pid):
        """Étape 17 : un poste SDR = un moteur + ses 4 panneaux (déplaçables, dans 🪟 Fenêtres et les vraies fenêtres)."""
        eng = self.sdr_engs[pid] = SdrEngine(self, pid)
        docks = self.post_docks[pid] = {}
        B = Qt.DockWidgetArea.BottomDockWidgetArea
        acts = self.win_menu.actions()
        sep = next((x for x in acts if x.isSeparator()), None)
        for key, title, name, cls in SDR_DOCKS:
            nm = name if pid == 1 else name.replace("dock_sdr_", f"dock_sdr{pid}_")
            pw = globals()[cls](self, eng)
            if key == "rx":
                pw = SdrScroll(pw)          # 8.0.1 : le Récepteur défile au lieu d'imposer sa taille (fenêtre trop grande,
            d = self._make_dock(self._post_title(pid, title), nm, pw, B)   # « Mes fréquences » sous le bord de l'écran)
            d.hide()
            docks[key] = d
            self.docks.append(d)
            if sep is not None:
                self.win_menu.insertAction(sep, d.toggleViewAction())
            else:
                self.win_menu.addAction(d.toggleViewAction())
        return eng

    def _post_title(self, pid, title):
        if pid == 1:
            return title
        p = next((x for x in sdr_posts_norm(self.sdr_cfg.get("posts")) if x["id"] == pid), None)
        return title.replace("SDR", (p or {}).get("name") or f"SDR {pid}", 1)

    def _sdr_posts_sync(self):
        """Moteurs et panneaux d'après la liste des postes (config, 📡 Mes SDR) : création, renommage, retrait."""
        if not hasattr(self, "sdr_engs"):
            return
        posts = sdr_posts_norm(self.sdr_cfg.get("posts"))
        ids = {p["id"] for p in posts}
        for pid in list(self.sdr_engs):
            if pid not in ids and pid != 1:
                self.sdr_engs.pop(pid).stop()
                for d in self.post_docks.pop(pid, {}).values():
                    self.panel_window(d, False)
                    self.win_menu.removeAction(d.toggleViewAction())
                    if d in self.docks:
                        self.docks.remove(d)
                    self.removeDockWidget(d)
                    d.deleteLater()
        for p in posts:
            if p["id"] not in self.sdr_engs:
                self._make_post(p["id"])
                if getattr(self, "rf_mode", "tiny") != "tiny":
                    self._post_show(p["id"])
            for key, title, _n, _c in SDR_DOCKS:
                d = self.post_docks[p["id"]][key]
                t = self._post_title(p["id"], title)
                if d.windowTitle() != t:
                    d.setWindowTitle(t)
            for d in self.post_docks[p["id"]].values():
                if hasattr(self.dock_widget(d), "refresh"):
                    self.dock_widget(d).refresh()

    def _post_show(self, pid):
        """Panneaux d'un poste 2…4 : en onglets à côté de ceux du poste 1 (l'utilisateur les place ensuite)."""
        base, mine = self.post_docks[1], self.post_docks[pid]
        for key in ("rx", "spec", "wf", "mics", "diag"):
            d = mine[key]
            if d.objectName() in self.panel_wins:
                continue
            if base[key].isVisible() and not base[key].isFloating():
                self.tabifyDockWidget(base[key], d)
            else:
                self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d)
            d.show()
            if key == "wf" and not base["wf"].isVisible():
                d.hide()

    def all_sdr_docks(self):
        return [d for ds in (getattr(self, "post_docks", None) or {}).values() for d in ds.values()]

    def _fit_screen(self):
        """8.0.1 (captures de Clément) : après un changement de mode, une fenêtre agrandie pouvait rester plus grande
        que l'écran (bords coupés, il fallait ré-agrandir) : on la recale sur l'écran."""
        try:
            if self.isMinimized():
                return
            av = self.screen().availableGeometry()
            if self.width() <= av.width() + 16 and self.height() <= av.height() + 16:
                return
            if self.isFullScreen():
                self.showNormal()
                self.showFullScreen()
            elif self.isMaximized():
                self.showNormal()
                self.showMaximized()
            else:
                self.resize(min(self.width(), av.width()), min(self.height(), av.height()))
                self.move(max(av.x(), min(self.x(), av.right() - self.width())), max(av.y(), self.y()))
        except Exception:  # noqa: BLE001
            pass


ALARM_HELP["PILOTE"] = (                         # étape 20 : porteuse là, mais pas le pilote de TON émetteur
    "Le SDR entend une porteuse sur ce micro, mais pas la tonalité pilote de ton émetteur (retenue la 1re fois) : un "
    "autre émetteur est peut-être sur ta fréquence, ou ton pack a changé de réglage.",
    "Écoute (le SDR y est calé) ; éteins ton pack : si la porteuse reste, c'est un brouilleur (chasse, fréquence de "
    "secours). Pilote changé exprès : clic droit sur la ligne d'info du Récepteur › Oublier le pilote.")


# Étape 16 : le mode et le poste SDR suivent le PROFIL UTILISATEUR (8.1 : dans user_doc / user_apply de la partie PURE).


class SdrModeMixin:
    """Mode tinySA / SDR / combiné, micros, favoris, compandeur deviné. (Méthodes de MainWindow, regroupées par thème.)"""

    def mic_demod(self, w):
        """Réglage d'écoute d'un micro -> (préréglage | DEMOD_DIGITAL | None, « manual » | « auto » | None)."""
        k = w.get("demod")
        if k and (demod_preset(k) is not None or k == DEMOD_DIGITAL):
            return k, "manual"
        g = self.group_row(w.get("scene"), w.get("group")) if hasattr(self, "group_row") else None
        grx = list(self.group_rxs(g)) if g and hasattr(self, "group_rxs") else []
        own = [x for x in [w.get("rx") or ""] + grx if x]              # appareil du micro, puis de son groupe
        names = [n for k_, n, *_r in rx_all() if k_ in own]
        key = demod_guess(*own, *names, w.get("group"), w.get("name"), w.get("scene"))
        if not key and hasattr(self, "rx_of"):                        # en dernier : l'appareil par défaut du plan
            d = self.rx_of(w) or ""
            key = demod_guess(d, *[n for k_, n, *_r in rx_all() if k_ == d])
        return (key, "auto") if key else (None, None)

    def mic_demod_set(self, w, key):
        """Retient le réglage d'écoute choisi à la main pour ce micro (rien si c'est celui qu'on aurait deviné)."""
        w.pop("demod", None)
        if key and self.mic_demod(w)[0] != key:
            w["demod"] = key

    def _engine_for(self, w):
        """Le SDR qui doit écouter ce micro : celui rattaché à sa scène (et qui couvre sa fréquence), sinon le 1er."""
        engs = sorted((getattr(self, "sdr_engs", None) or {}).items())
        for _pid, e in engs:
            sc = e.post()["scenes"]
            if sc and w.get("scene") in sc and sdr_in_range(e.model(), w["freq"]):
                return e
        return next((e for _pid, e in engs if sdr_in_range(e.model(), w["freq"])), self.sdr_eng)

    def sdr_tune_mic(self, w, slot="a"):
        """Étape 18 : le SDR se cale sur ce micro (recentré si besoin) et on l'entend ; son panneau Récepteur passe devant."""
        e = self._engine_for(w)
        if self.rf_mode == "tiny":
            self.set_rf_mode("sdr")
        if slot == "b":
            e.set_b(f=w["freq"], on=True)
        else:
            e.set_a(w["freq"])
        if not e.running():
            e.start()
        d = self.post_docks.get(e.pid, {}).get("rx")
        if d is not None:
            if d.isHidden():
                d.show()
            d.raise_()
        self.set_status(TR("🎧 {} ({} MHz) sur {}").format(w["name"] or "—", f"{w['freq']:.3f}", e.name()))
        return e

    def sdr_fav(self, k):
        """Touche k du pavé numérique : bascule l'écoute sur le micro rangé là."""
        favs = favs_norm(self.sdr_cfg.get("favs"))
        w = self.watch_by_key(favs[k]) if k in favs else None
        if w is None:
            self.set_status(TR("⭐ Touche {} libre : clic droit sur un micro (📡 Mes micros) ou sur le bouton {} du Récepteur "
                               "pour l'y mettre.").format(k, k))
            return None
        return self.sdr_tune_mic(w)

    def sdr_set_fav(self, k, w):
        self.sdr_cfg["favs"] = fav_assign(self.sdr_cfg.get("favs"), k, int(round(w["freq"] * 1000)) if w else None)
        for d in self.all_sdr_docks():
            if hasattr(self.dock_widget(d), "_favs_refresh"):
                self.dock_widget(d)._favs_refresh()
        if w:
            self.set_status(TR("⭐ Touche {} du pavé numérique : {}").format(k, w["name"] or f"{w['freq']:.3f}"))

    def _sdr_watch_dbl(self, row, col):
        """Double-clic sur le nom ou la fréquence d'un micro (mode SDR / combiné) : le SDR se cale dessus."""
        if col in (C_NAME, C_FREQ) and getattr(self, "rf_mode", "tiny") != "tiny" and 0 <= row < len(self.watch):
            self.sdr_tune_mic(self.watch[row])

    def _sdr_arrange(self, mode, layout="listen", base=True):
        """Place les panneaux pour un mode et un pré-affichage (ensuite, l'utilisateur bouge tout comme il veut).
        mode : sdr (le spectre SDR remplace celui du tinySA) | both (les deux spectres côte à côte) ;
        layout : listen | watch | analyze | dual (spectre SDR sur l'autre écran)."""
        if base:
            self._layout_base()
        R, B = Qt.DockWidgetArea.RightDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea
        sd = self.sdr_docks
        for d in sd.values():
            if d.objectName() in self.panel_wins:
                continue                                     # déjà en vraie fenêtre : on la laisse où l'utilisateur l'a mise
            self.removeDockWidget(d)                         # repartir propre (pas d'onglet caché derrière un autre)
            d.setFloating(False)
        if mode == "sdr":
            self.dock_spec.hide()
            self.dock_wf.hide()
            self.addDockWidget(B, sd["spec"])
        else:                                                # combiné : le spectre SDR dans sa colonne, à droite du tinySA
            self.addDockWidget(B, sd["spec"], Qt.Orientation.Horizontal)
        self.splitDockWidget(sd["spec"], sd["wf"], Qt.Orientation.Vertical)
        for d in sd.values():
            d.show()
        if mode != "sdr":
            sd["wf"].hide()
        self.addDockWidget(R, sd["rx"])
        self.splitDockWidget(sd["rx"], self.dock_freq, Qt.Orientation.Vertical)
        self.dock_log.setFloating(False)
        self.tabifyDockWidget(self.dock_freq, self.dock_log)     # 8.0.1 : le Journal restait seul au-dessus du Récepteur
        self.tabifyDockWidget(self.dock_freq, sd["mics"])
        self.tabifyDockWidget(self.dock_freq, sd["diag"])      # 8.2 : historique, appareil, système, session
        if layout == "watch":
            sd["mics"].raise_()
            sd["wf"].hide()
        elif layout == "analyze":
            sd["mics"].hide()
            sd["wf"].show()
            self.sdr_eng.set_opts(maxhold=True)
        else:
            self.dock_freq.raise_()
        try:
            self.set_level(self.ui_level)                    # ce que le niveau d'affichage cache reste caché
            self.resizeDocks([sd["rx"]], [min(sd["rx"].widget().sizeHint().height() + 36, int(self.height() * 0.55))],
                             Qt.Orientation.Vertical)
            if mode == "both":                               # les deux spectres à parts égales
                w_ = max(400, self.dock_spec.width() + sd["spec"].width())
                self.resizeDocks([self.dock_spec, sd["spec"]], [w_ // 2, w_ // 2], Qt.Orientation.Horizontal)
        except Exception:  # noqa: BLE001
            pass
        try:                                                  # 8.0.1 : petit écran (portable) -> Récepteur en onglet
            if self.minimumSizeHint().height() > self.screen().availableGeometry().height() - 20 \
                    and sd["rx"].objectName() not in self.panel_wins:
                self.tabifyDockWidget(self.dock_freq, sd["rx"])
                sd["rx"].raise_()
        except Exception:  # noqa: BLE001
            pass
        QtCore.QTimer.singleShot(0, self._fit_screen)
        if layout == "dual":
            scr = self._other_screen()
            if scr is None:
                self.set_status(TR("Un seul écran : tire le panneau « 📡 SDR · Spectre » par sa barre de titre pour en "
                                   "faire une fenêtre, ou branche le 2ᵉ écran."))
            else:
                self.panel_window(sd["spec"], True, scr, "max")

    def set_rf_mode(self, mode, layout=None):
        """📟 tinySA / 📡 SDR / 📟+📡 Combiné : quels panneaux de base, et le SDR lancé ou arrêté. Les panneaux prêtés à
        d'autres écrans reviennent d'abord (8.0.2)."""
        self.screens_off(relayout=False)
        if self.lab_view_on:                                 # 8.2 : changer de mode = quitter l'affichage Labo
            self.lab_view_on = False
            for d in self.lab_docks.values():
                if d.objectName() not in self.panel_wins:
                    d.hide()
            self._sdrlab.view_btn.setText(TR("⛶ Affichage Labo"))
        mode = rf_mode_norm(mode)
        self.rf_mode = mode
        self.sdr_cfg["rf_mode"] = mode
        if mode == "tiny":
            for e_ in self.sdr_engs.values():
                e_.stop()
            self._layout_mode()
        else:
            self._sdr_arrange(mode, layout or "listen")
            for pid in sorted(self.sdr_engs):               # étape 17 : tous les postes SDR
                if pid != 1:
                    self._post_show(pid)
                if not self.sdr_engs[pid].running():
                    self.sdr_engs[pid].start()
        self._update_mode_btn()
        self.set_status(dict(tiny=TR("📟 Mode tinySA."), sdr=TR("📡 Mode SDR : tout est déplaçable (barres de titre), "
                                                                  "ta disposition est retenue."),
                             both=TR("📟+📡 Mode combiné : tinySA et SDR côte à côte, tout est déplaçable."))[mode])
        return mode

    def _update_mode_btn(self):
        b = getattr(self, "mode_btn", None)
        if b is not None:
            b.setText(dict(RF_MODES).get(self.rf_mode, "📟 tinySA") + " ▾")

    def _build_mode_menu(self):
        m = self.mode_btn.menu()
        m.clear()
        m.addSection(TR("Mode"))
        m.setToolTipsVisible(True)
        for k, t in RF_MODES:
            a_ = m.addAction(TR(t))
            a_.setToolTip(TR(DEVICE_HELP[k]))                   # 8.0 : c'est quoi un tinySA / un SDR
            a_.setCheckable(True)
            a_.setChecked(k == self.rf_mode)
            a_.triggered.connect(lambda *_, k=k: self.set_rf_mode(k))
        m.addSection(TR("Pré-affichages SDR (ensuite, bouge tout comme tu veux)"))
        for k, t in SDR_LAYOUTS:
            a_ = m.addAction(TR(t))
            a_.triggered.connect(lambda *_, k=k: self.set_rf_mode("both" if self.rf_mode == "both" else "sdr", k))
        m.addSeparator()
        m.addAction(TR("📡 Mes SDR (plusieurs, scènes, carte)…")).triggered.connect(lambda *_: self.open_sdr_posts())
        a_ = m.addAction(TR("🧪 SDR démo (sans matériel, avec du son)"))          # étape 21
        a_.setCheckable(True)
        a_.setChecked(bool(self.sdr_cfg.get("demo")))
        a_.triggered.connect(lambda *_, a=a_: self.set_sdr_demo(a.isChecked()))
        m.addAction(TR("📡 Émettre avec un HackRF (en câble)…")).triggered.connect(lambda *_: self.open_sdr_tx())
        m.addAction(TR("🎵 Générateur audio (20 Hz – 20 kHz)…")).triggered.connect(lambda *_: self.open_audio_gen())
        m.addAction(TR("🧪 Labo SDR (RF Compander Lab)…")).triggered.connect(lambda *_: self.open_sdr_lab())
        lm = m.addMenu(TR("⛶ Affichage Labo"))
        lm.setToolTip(TR("La fenêtre ne montre plus que le labo : rangé, en grille ou sur 2 écrans."))
        for k_, t_ in LAB_VIEWS:
            lm.addAction(TR(t_)).triggered.connect(lambda *_, k_=k_: self.lab_view(True, k_))
        if self.lab_view_on:
            lm.addAction(TR("↩ Quitter l'affichage Labo")).triggered.connect(lambda *_: self.lab_view(False))
        m.addSeparator()
        m.addAction(TR("🔌 Premier branchement SDR (assistant)…")).triggered.connect(lambda *_: self.open_sdr_setup())
        m.addAction(TR("📏 Caler les niveaux du SDR sur le tinySA…")).triggered.connect(lambda *_: self.open_sdr_calib())
        m.addAction(TR("⏪ Remonter le temps (dernières minutes)…")).triggered.connect(lambda *_: self.open_rewind())
        m.addAction(TR("📖 Manuel SDR")).triggered.connect(lambda *_: self.open_sdr_manual())
        m.addAction(TR("↺ Disposition de base du mode")).triggered.connect(lambda *_: self.set_rf_mode(self.rf_mode))
        m.addAction(TR("📡 Réglages SDR…")).triggered.connect(lambda *_: self.open_sdr())
        acts = m.actions()                                   # 8.0.2 : plusieurs écrans, avant la 1re séparation
        a_ = QtGui.QAction(TR("🖥 Plusieurs écrans (tinySA sur l'un, SDR sur l'autre…)"), m)
        a_.setToolTip(TR("Choisis quel panneau va sur quel écran : tinySA complet sur l'un, SDR complet sur l'autre, ou "
                         "ton mélange."))
        a_.triggered.connect(lambda *_: self.open_screens())
        sec = next((x for x in acts if x.isSeparator()), None)
        if sec is not None:
            m.insertAction(sec, a_)
        else:
            m.addAction(a_)

    def mode_setup(self):
        """Bouton de mode dans la barre du haut (créé une fois), réglages du poste relus de la config."""
        if getattr(self, "mode_btn", None) is not None:
            return
        b = self.mode_btn = QtWidgets.QToolButton()
        b.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        b.setMenu(QtWidgets.QMenu(b))
        b.menu().aboutToShow.connect(self._build_mode_menu)
        b.setToolTip(TR("Ce que tu utilises :") + "\n\n" + "\n\n".join(TR(DEVICE_HELP[k]) for k in ("tiny", "sdr", "both"))
                     + "\n\n" + TR("Chaque mode a sa disposition de base et des pré-affichages ; ensuite tu bouges les "
                                     "panneaux comme tu veux (ta disposition est retenue)."))
        try:
            self.cmd_bar.insertWidget(self._more_act, b)
        except Exception:  # noqa: BLE001
            self.cmd_bar.addWidget(b)
        self._sdr_reload()
        self.watch_table.cellDoubleClicked.connect(self._sdr_watch_dbl)      # étape 18 : double-clic = le SDR s'y cale
        self.fav_keys = []
        for k in range(1, FAV_KEYS + 1):                   # touches 1…9 du PAVÉ NUMÉRIQUE = favoris
            sc_ = QtGui.QShortcut(QtGui.QKeySequence(QtCore.QKeyCombination(Qt.KeyboardModifier.KeypadModifier,
                                                                            Qt.Key(int(Qt.Key.Key_0.value) + k))), self)
            sc_.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc_.activated.connect(lambda k=k: self.sdr_fav(k))
            sc_.activatedAmbiguously.connect(lambda k=k: self.sdr_fav(k) if self.isVisible() else None)   # 2 fenêtres
            self.fav_keys.append(sc_)
        if self.rf_mode != "tiny" and any(d.isVisible() for d in self.all_sdr_docks()):
            QtCore.QTimer.singleShot(1500, lambda: [e_.start() for e_ in self.sdr_engs.values()])   # rouverte en mode SDR
        QtCore.QTimer.singleShot(400, self._fit_screen)     # 8.0.1 : disposition rouverte plus grande que l'écran

    def _sdr_reload(self):
        """Réglages du poste et mode relus de sdr_cfg (démarrage, profil chargé), sans toucher à la disposition."""
        self._sdr_posts_sync()
        for e in self.sdr_engs.values():                 # chaque poste relit SES réglages
            st = station_norm(e._st_cfg())
            e.a, e.b, e.b_on, e.step, e.vol, e.sq, e.split, e.nfft, e.maxhold = (st[k] for k in (
                "a", "b", "b_on", "step", "vol", "sq", "split", "nfft", "maxhold"))
            if e.running():
                e._push()
        self.rf_mode = rf_mode_norm(self.sdr_cfg.get("rf_mode"))
        self._update_mode_btn()
        for d in self.all_sdr_docks():
            pw_ = self.dock_widget(d)
            if hasattr(pw_, "apply_level"):
                pw_.apply_level()
            if hasattr(pw_, "refresh"):
                pw_.refresh()


class SdrReceiversMixin:
    """Vie privée des enregistrements, récepteurs en réseau (Shure, Sennheiser). (Méthodes de MainWindow, regroupées par thème.)"""

    def privacy(self):
        """Étape 12 : réglages « son et vie privée » (toujours complets)."""
        p = self.sdr_cfg.get("privacy")
        if not isinstance(p, dict) or set(p) != set(PRIVACY_DEFAULT):
            p = self.sdr_cfg["privacy"] = privacy_norm(p)
        return p

    def privacy_ok(self, parent=None):
        """Accord explicite avant le 1er enregistrement de son (ou d'IQ). -> True si on peut enregistrer."""
        p = self.privacy()
        if p["ack"]:
            return True
        r = QtWidgets.QMessageBox.question(
            parent or self, TR("Enregistrer du son ?"),
            TR(PRIVACY_TEXT) + "\n\n" + TR("Conservation : {} (réglable dans 📡 Réglages SDR).").format(
                keep_text(p["keep_days"], TR)) + "\n\n" + TR("D'accord pour enregistrer ?"))
        if r != QtWidgets.QMessageBox.StandardButton.Yes:
            return False
        p["ack"] = True
        try:
            self._save_config()
        except Exception:  # noqa: BLE001
            pass
        return True

    def sdr_retention(self, now=None):
        """Étape 12 : efface le son, l'IQ et les dossiers d'incident plus vieux que la durée choisie. -> nombre effacé."""
        days = self.privacy()["keep_days"]
        if not days:
            return 0
        now = time.time() if now is None else now
        ent = []
        for sub in ("enregistrements_audio", "enregistrements_iq", "incidents"):
            root = Path(self.log_dir) / sub
            if not root.is_dir():
                continue
            try:
                for d in root.iterdir():
                    for p in (d.iterdir() if d.is_dir() else [d]):
                        ent.append((p, p.stat().st_mtime))
            except OSError:
                continue
        n = 0
        for p in retention_pick(ent, now, days):
            try:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
                n += 1
            except OSError:
                pass
        for sub in ("enregistrements_audio", "enregistrements_iq", "incidents"):
            root = Path(self.log_dir) / sub
            try:
                for d in (root.iterdir() if root.is_dir() else []):
                    if d.is_dir() and not any(d.iterdir()):
                        d.rmdir()
            except OSError:
                pass
        return n

    def sdr_timer(self):
        """Minuteur V8 (créé à l'ouverture d'une fenêtre SDR) : ménage des enregistrements toutes les heures."""
        if getattr(self, "_v8_tm", None) is None:
            self._v8_tm = QtCore.QTimer(self)
            self._v8_tm.timeout.connect(lambda: self.sdr_retention())
            self._v8_tm.start(3600 * 1000)
            try:
                self.sdr_retention()
            except Exception:  # noqa: BLE001
                pass

    def receivers_start(self, text):
        """14. Connecte (ou reconnecte) les récepteurs de la liste (toutes marques : « g4:… », « ssc:… », Shure sans
        préfixe), retenue dans la config (clé « shure », gardée pour les configs de l'étape 11)."""
        addrs = receiver_addrs(text)
        self.sdr_cfg["shure"] = receiver_addrs_text(addrs)
        cur = getattr(self, "_shure", None) or {}
        keep = {f"{b}:{h}:{p}" for b, h, p in addrs}
        for k in list(cur):
            if k not in keep:
                cur.pop(k).stop()
        for b, h, p in addrs:
            if f"{b}:{h}:{p}" not in cur:
                c = cur[f"{b}:{h}:{p}"] = ReceiverClient(h, p, b)
                c.start()
        self._shure = cur

    def receivers(self):
        """Tous les canaux des récepteurs Shure connectés : [dict(host, ch, name, freq, rf, ant, audio, batt, div, hist)]."""
        out = []
        for c in (getattr(self, "_shure", None) or {}).values():
            for ch, st in sorted(c.snapshot().items()):
                age = time.time() - float(st.get("t") or 0.0) if st.get("t") else None
                out.append(dict(st, host=c.host, ch=ch, brand=c.brand, age=age,
                                live=bool(c.ok and age is not None and age < RX_STALE_S)))
        return out

    def receiver_for(self, f, tol=0.025, live_only=True):
        """Canal de récepteur réglé sur la fréquence f (MHz, ± 25 kHz), ou None. live_only : seulement s'il a donné des
        nouvelles récentes (étape 14 : une valeur ancienne n'alimente ni le diagnostic ni la comparaison)."""
        best = None
        for x in self.receivers():
            if live_only and not x.get("live"):
                continue
            if x.get("freq") is not None and abs(x["freq"] - f) <= tol and (best is None or abs(x["freq"] - f) <
                                                                             abs(best["freq"] - f)):
                best = x
        return best

    def watch_near(self, f, tol=0.025):
        if f is None:
            return None
        return min((w for w in self.watch if abs(w["freq"] - f) <= tol), key=lambda w: abs(w["freq"] - f), default=None)

    def open_receivers(self):
        """📶 V8 étape 11 : récepteurs Shure en réseau (fenêtre gardée)."""
        d = getattr(self, "_recvdlg", None)
        if d is None:
            d = self._recvdlg = ReceiversDialog(self)
        if self.sdr_cfg.get("shure") and not getattr(self, "_shure", None):
            self.receivers_start(self.sdr_cfg["shure"])
        d.show()
        d.raise_()
        d.activateWindow()
        return d

    def tsa_live(self):
        """Un tinySA (pas un SDR) balaye en ce moment : ses niveaux peuvent être comparés à ceux du SDR."""
        return any(w.isRunning() and not getattr(w, "paused", False) and not getattr(w, "sdr", False) for w in self.workers)

WEB_VIEWS.append(("ecoute", "🎧", "Écoute", "Écouter un micro analogique sur le téléphone, avec le SDR du PC"))
WEB_VIEW_KEYS.append("ecoute")
# vue 🎧 Écoute : le PC démodule avec son SDR, le son arrive en PCM 16 kHz (1re ligne en code : pas du texte à traduire)
WEB_EXTRA_JS += r"""
function e8(){return 8}
let EA=null,ESEQ=0,ENEXT=0,ETIMER=null,EST=null;
EXT.ecoute={mount(el){el.innerHTML=`<div class="tools"><button class="btn" id="eon">🔊 Activer le son ici</button><span id="est" class="mut"></span></div><div class="mut" style="margin:6px 0">Le PC écoute avec son SDR (HackRF, RTL-SDR…). Touche 🎧 sur un micro : le son arrive ici, avec un petit retard. Code PIN demandé (celui du PC). Les micros numériques ne s'écoutent pas.</div><div class="tools"><input class="in" id="eq" placeholder="🔎 Nom, fréquence…"><input class="in" id="ef" placeholder="Autre fréquence (MHz)" inputmode="decimal" style="width:11em"><button class="btn" id="ego">🎧 Écouter</button></div><div class="grid" id="eg"></div>`;
 $("#eon").onclick=()=>eAudio();$("#eq").oninput=()=>update("ecoute");$("#ego").onclick=()=>{const f=parseFloat(($("#ef").value||"").replace(",","."));if(f>0)eCmd("start",f)};eState()},
 update(st){const q=($("#eq").value||"").toLowerCase(),L=EST||{};
  $("#est").textContent=L.on?("🎧 "+(L.name||"")+" · "+(L.f?L.f.toFixed(3)+" MHz":"")+(L.rf!=null?" · "+L.rf+" dBFS":"")+(L.rec?" · ⏺":"")+(L.hop?" · 🔁":"")):"Pas d'écoute en cours";
  $("#eg").innerHTML=st.rows.filter(r=>!q||(r.name+" "+r.freq.toFixed(3)).toLowerCase().includes(q)).map(r=>{const on=L.on&&L.f!=null&&Math.abs(L.f-r.freq)<0.0006;
   return `<div class="c ${r.tone}"><div class="n">${esc(r.name)}</div><div>${r.freq.toFixed(3)} MHz</div><button class="btn" data-ef="${on?"stop":r.freq}">${on?"■ Arrêter":"🎧 Écouter"}</button></div>`}).join("");
  eState()}};
async function eState(){try{const r=await api("ecoute.json");if(r.ok)EST=await r.json()}catch(e){}}
document.addEventListener("click",e=>{const b=e.target.closest("button[data-ef]");if(!b)return;if(b.dataset.ef==="stop")eCmd("stop");else eCmd("start",+b.dataset.ef)});
async function eCmd(a,f){let pin=LS.get("pin","");if(!pin){pin=prompt("Code PIN (réglé sur le PC de surveillance) :")||"";if(!pin)return}
 let r;try{r=await post("ecoute",{pin:pin,action:a,f:f})}catch(x){alert("PC injoignable");return}
 if(r.ok){LS.set("pin",pin);if(a==="start")eAudio();setTimeout(eState,600);return}
 if(r.status===403){LS.set("pin","");alert("Code PIN incorrect.")}else if(r.status===429)alert("Trop d'essais : attends une minute.");else alert("Refusé ("+r.status+")")}
function eAudio(){try{if(!EA){const C=window.AudioContext||window.webkitAudioContext;EA=new C()}EA.resume();ESEQ=0;ENEXT=0}catch(e){alert("Son impossible sur ce navigateur");return}
 if(!ETIMER)ETIMER=setInterval(ePull,250);const b=$("#eon");if(b)b.textContent="🔊 Son actif"}
async function ePull(){if(route()!=="ecoute"||!EA)return;
 let r;try{r=await api("ecoute.pcm?s="+ESEQ)}catch(e){return}if(!r.ok)return;const b=await r.arrayBuffer();if(b.byteLength<12)return;
 const h=new DataView(b);ESEQ=h.getUint32(4,true);const rate=h.getUint32(8,true),n=(b.byteLength-12)>>1;if(!n)return;
 const buf=EA.createBuffer(1,n,rate),ch=buf.getChannelData(0);for(let i=0;i<n;i++)ch[i]=h.getInt16(12+2*i,true)/32768;
 const s=EA.createBufferSource();s.buffer=buf;s.connect(EA.destination);const now=EA.currentTime;
 if(ENEXT<now+0.05||ENEXT>now+1.5)ENEXT=now+0.25;s.start(ENEXT);ENEXT+=n/rate}
"""


# ------------------------------------------------------------------ V8 étape 21 : SDR démo + émission HackRF
def wav_load(path, max_s=180.0):
    """Fichier WAV (PCM 8 / 16 / 24 / 32 bits, mono ou stéréo, n'importe quel débit) -> WAV_PCM[path] en mono 48 kHz,
    3 min au plus (audit : 10 min = 115 Mo de mémoire par fichier).
    -> (ok, texte)."""
    import wave
    path = str(path or "")
    if path in WAV_PCM:
        return True, ""
    try:
        with wave.open(path, "rb") as w:
            ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(min(n, int(max_s * fr)))
    except (OSError, EOFError, wave.Error) as e:
        return False, TR("WAV illisible : {}").format(e)
    if sw == 1:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        a = (np.where(v >= 1 << 23, v - (1 << 24), v)).astype(np.float32) / float(1 << 23)
    elif sw == 4:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / float(1 << 31)
    else:
        return False, TR("WAV : format non pris en charge")
    if ch > 1:
        a = a[: len(a) // ch * ch].reshape(-1, ch).mean(axis=1)
    if fr != 48000 and len(a) > 1:
        x = np.arange(int(len(a) * 48000 / fr)) * (fr / 48000.0)
        a = np.interp(x, np.arange(len(a)), a).astype(np.float32)
    if not len(a):
        return False, TR("WAV vide")
    pk = float(np.max(np.abs(a)))
    WAV_PCM[path] = (a / pk * 0.9 if pk > 0.9 else a).astype(np.float32)
    return True, TR("{} s de son").format(f"{len(a) / 48000:.1f}")


_TEMP_WAV_N = [0]


def temp_wav_path(kind, old=None):
    """8.0.2 (Clément : « le générateur audio n'a qu'un 1 kHz ») : QSoundEffect garde en mémoire le son d'un fichier
    déjà lu (cache par adresse) -> réécrire le MÊME fichier rejouait le 1er son. Un nom neuf à chaque lecture ; l'ancien
    est effacé si possible (sous Windows il peut être encore ouvert : il partira au prochain coup)."""
    import tempfile
    _TEMP_WAV_N[0] += 1
    d = tempfile.gettempdir()
    for p_ in ([old] if old else []) + [os.path.join(d, n_) for n_ in os.listdir(d)
                                        if n_.startswith(f"tsm_{kind}_{os.getpid()}_")]:
        try:
            os.remove(p_)
        except OSError:
            pass
    return os.path.join(d, f"tsm_{kind}_{os.getpid()}_{_TEMP_WAV_N[0]}.wav")


class AudioMeterBar(QtWidgets.QWidget):
    """8.1 : vu-mètre audio horizontal (−60 … 0 dBFS) : barre = niveau RMS (convention AES17 : sinus plein = 0 dBFS),
    trait = crête, losange ambre = niveau visé ; fond en zones (vert / jaune dès −9 / rouge dès −1), gradué tous les
    1 à 5 dB selon la largeur, valeurs écrites tous les 5 / 10 dB, repère d'alignement (−18 EBU / −20 SMPTE) en ambre."""
    LO, HI = -60.0, 0.0

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner, self.m, self.target = owner, None, None
        self.setMinimumSize(160, 30)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setToolTip(TR("Vu-mètre : barre = niveau moyen (RMS), trait = crête, losange = niveau visé.\n"
                           "Repères −18 et −20 dBFS = niveaux d'alignement EBU / SMPTE. Clic = fiche des échelles."))

    def set_meter(self, m, target=None):
        self.m, self.target = m, target
        self.update()

    def mousePressEvent(self, e):
        self.owner.open_scales()

    def paintEvent(self, ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        bh = 10
        x0, x1 = 6.0, W - 6.0
        pos = lambda db: x0 + (x1 - x0) * (min(self.HI, max(self.LO, db)) - self.LO) / (self.HI - self.LO)  # noqa: E731
        p.setPen(QtCore.Qt.PenStyle.NoPen)
        for a_, b_, col in ((-60, -9, "#4fd1c5"), (-9, -1, "#ffb300"), (-1, 0, "#ff6b6b")):   # zones en fond
            c = QtGui.QColor(col)
            c.setAlpha(45)
            p.setBrush(c)
            p.drawRect(QtCore.QRectF(pos(a_), 2, pos(b_) - pos(a_), bh))
        m = self.m or {}
        rms, pk = m.get("rms", -math.inf), m.get("peak", -math.inf)
        if math.isfinite(rms):
            col = "#ff6b6b" if rms > -1 else ("#ffb300" if rms > -9 else "#4fd1c5")
            p.setBrush(QtGui.QColor(col))
            p.drawRoundedRect(QtCore.QRectF(x0, 2, pos(rms) - x0, bh), 2, 2)
        if math.isfinite(pk):
            p.setPen(QtGui.QPen(QtGui.QColor("#ff6b6b" if m.get("clip") else "#f5f5f7"), 2))
            p.drawLine(QtCore.QPointF(pos(pk), 1), QtCore.QPointF(pos(pk), bh + 3))
        try:
            align = audio_align(getattr(self.owner, "audio_ref", None))[0]
        except Exception:
            align = -18.0
        f = p.font()
        f.setPointSizeF(max(6.5, f.pointSizeF() - 2))
        p.setFont(f)
        mins, mids, labs = meter_ticks(int(self.LO), int(self.HI), x1 - x0,
                                       label_px=QtGui.QFontMetrics(f).horizontalAdvance("−60") + 8)
        yt = bh + 2
        for vs, ln, col in ((mins, 2.5, QtGui.QColor(160, 160, 170, 110)), (mids, 4.0, QtGui.QColor(160, 160, 170, 190)),
                            (labs, 5.0, QtGui.QColor(170, 170, 180))):
            p.setPen(QtGui.QPen(col, 1.0))
            for db in vs:
                p.drawLine(QtCore.QPointF(pos(db), yt), QtCore.QPointF(pos(db), yt + ln))
        if self.LO <= align <= self.HI:                  # repère d'alignement (−18 dBFS = 0 dBu en EBU…)
            p.setPen(QtGui.QPen(QtGui.QColor("#ffb300"), 1.4))
            p.drawLine(QtCore.QPointF(pos(align), 1), QtCore.QPointF(pos(align), yt + 5))
        if self.target is not None:
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(QtGui.QColor("#ffb300"))
            xt = pos(self.target)
            p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(xt, bh + 2), QtCore.QPointF(xt - 4, bh + 7),
                                           QtCore.QPointF(xt + 4, bh + 7)]))
        p.setPen(QtGui.QColor(160, 160, 170))
        for db in labs:
            p.drawText(QtCore.QRectF(pos(db) - 15, yt + 4, 30, 12), Qt.AlignmentFlag.AlignCenter, str(db))
        p.end()


class ScalesDialog(QtWidgets.QDialog):
    """8.1 : 📏 Échelles et niveaux : unité des vu-mètres, alignement numérique / analogique, référence dBr, niveau visé,
    et la fiche (tableau : où chaque unité sert et comment l'utiliser ici)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle(TR("📏 Échelles et niveaux"))
        lay = QtWidgets.QVBoxLayout(self)
        ref = owner.audio_ref
        f = QtWidgets.QFormLayout()
        self.unit = QtWidgets.QComboBox()
        for k, t in AUDIO_UNITS:
            self.unit.addItem(TR(t), k)
        self.unit.setCurrentIndex(max(0, self.unit.findData(ref["unit"])))
        self.unit.setToolTip(TR("Unité des vu-mètres audio de l'appli (générateur, écoute SDR)."))
        self.align = QtWidgets.QComboBox()
        for k, t, _a, _b in AUDIO_ALIGNS:
            self.align.addItem(TR(t), k)
        self.align.setCurrentIndex(max(0, self.align.findData(ref["align"])))
        self.align.setToolTip(TR("Quel niveau numérique (dBFS) correspond à quel niveau analogique (dBu) chez toi :\n"
                                 "EBU (Europe) −18 dBFS = 0 dBu ; SMPTE (USA) −20 dBFS = +4 dBu ; ou le tien."))
        self.c_fs, self.c_u, self.dbr, self.tgt = (QtWidgets.QDoubleSpinBox() for _ in range(4))
        for sp_, lo, hi, v, sfx, tip in ((self.c_fs, -60, 0, ref["dbfs"], " dBFS", "Alignement perso : ce niveau numérique…"),
                                         (self.c_u, -40, 30, ref["dbu"], " dBu", "… correspond à ce niveau analogique."),
                                         (self.dbr, -60, 0, ref["dbr"], " dBFS", "Niveau qui vaut 0 dBr (ta référence)."),
                                         (self.tgt, -60, 0, ref["target"], " dBFS",
                                          "Niveau visé par défaut (générateur, réglage d'un pack).")):
            sp_.setRange(lo, hi)
            sp_.setDecimals(1)
            sp_.setSingleStep(0.5)
            sp_.setValue(v)
            sp_.setSuffix(sfx)
            sp_.setToolTip(TR(tip))
        f.addRow(TR("Unité des vu-mètres :"), self.unit)
        f.addRow(TR("Alignement :"), self.align)
        f.addRow(TR("Perso :"), self.owner._row(self.c_fs, "=", self.c_u, None))
        f.addRow(TR("Référence dBr :"), self.dbr)
        f.addRow(TR("Niveau visé :"), self.tgt)
        lay.addLayout(f)
        self.conv = QtWidgets.QLabel("")
        self.conv.setWordWrap(True)
        lay.addWidget(self.conv)
        tb = QtWidgets.QTextBrowser()
        tb.setHtml(scales_help_html(TR))
        tb.setMinimumHeight(260)
        lay.addWidget(tb, 1)
        close = QtWidgets.QPushButton(TR("Fermer"))
        close.setToolTip(TR("Ferme cette fenêtre (les réglages sont gardés)."))
        close.clicked.connect(lambda *_: self.close())
        lay.addLayout(owner._row(None, close))
        for w_ in (self.unit, self.align):
            w_.currentIndexChanged.connect(lambda *_: self.apply())
        for w_ in (self.c_fs, self.c_u, self.dbr, self.tgt):
            w_.valueChanged.connect(lambda *_: self.apply())
        self.resize(820, 640)
        fit_dialog(self, 820, 640)
        self.apply()

    def apply(self):
        o = self.owner
        o.audio_ref = audio_ref_norm(dict(unit=self.unit.currentData(), align=self.align.currentData(),
                                          dbfs=self.c_fs.value(), dbu=self.c_u.value(), dbr=self.dbr.value(),
                                          target=self.tgt.value()))
        cust = o.audio_ref["align"] == "custom"
        self.c_fs.setEnabled(cust)
        self.c_u.setEnabled(cust)
        r = o.audio_ref
        self.conv.setText(TR("Avec ces réglages : {} = {} = {} = {} · niveau visé {} = {}").format(
            fmt_audio(-18, r, "dbfs"), fmt_audio(-18, r, "dbu"), fmt_audio(-18, r, "dbv"), fmt_audio(-18, r, "vrms"),
            fmt_audio(r["target"], r, "dbfs"), fmt_audio(r["target"], r, "dbu")))


class AudioPickDialog(QtWidgets.QDialog):
    """🎵 Choisir un son (étape 21) : générateur 20 Hz – 20 kHz (une fréquence ou un balayage), bruits, voix / mélodie /
    bips de démo, sons de l'appli, ton fichier WAV ; ▶ pour l'écouter sur le PC. Seul (standalone) = 🎵 Générateur
    audio qui joue en boucle sur la sortie audio de l'appli."""

    def __init__(self, owner, spec=None, standalone=False, title=None):
        super().__init__(owner)
        self.owner, self.standalone, self.fx, self._tmp = owner, standalone, None, None
        self.setWindowTitle(title or ("🎵 Générateur audio (20 Hz – 20 kHz)" if standalone else "🎵 Choisir un son"))
        sp = audio_spec_norm(spec or dict(src="tone" if standalone else "voice"))
        lay = QtWidgets.QVBoxLayout(self)
        if standalone:
            why = QtWidgets.QLabel(TR("À quoi ça sert ? Écouter un son de test ici, ou l'affecter (en bas) : à un micro de ta "
                                      "liste (il l'émet dans les modes démo tinySA et SDR), à un son d'alarme, ou à "
                                      "l'émission avec un HackRF."))
            why.setWordWrap(True)
            lay.addWidget(why)
        f = QtWidgets.QFormLayout()
        self.src = QtWidgets.QComboBox()
        for k_, t_ in AUDIO_SRCS:
            self.src.addItem(t_, k_)
        self.src.setCurrentIndex(max(0, self.src.findData(sp["src"])))
        self.src.setToolTip("D'où vient le son.")
        f.addRow("Source :", self.src)

        def hz(v, tip):
            b = QtWidgets.QDoubleSpinBox()
            b.setRange(20.0, 20000.0)
            b.setDecimals(0)
            b.setSuffix(" Hz")
            b.setValue(v)
            b.setToolTip(tip)
            return b
        self.f = hz(sp["f"], "Fréquence du son (20 Hz – 20 kHz).")
        self.f1 = hz(sp["f1"], "Fréquence de départ du balayage.")
        self.f2 = hz(sp["f2"], "Fréquence d'arrivée du balayage.")
        self.dur = QtWidgets.QDoubleSpinBox()
        self.dur.setRange(1.0, 120.0)
        self.dur.setDecimals(0)
        self.dur.setSuffix(" s")
        self.dur.setValue(sp["dur"])
        self.dur.setToolTip("Durée d'un balayage (il recommence ensuite).")
        self.log = QtWidgets.QCheckBox("Logarithmique (autant de temps par octave)")
        self.log.setChecked(sp["log"])
        self.log.setToolTip("Coché : chaque octave dure le même temps (comme à l'oreille). Décoché : linéaire en Hz.")
        self.app = QtWidgets.QComboBox()
        for k_, t_ in APP_SOUNDS:
            self.app.addItem(t_, k_)
        self.app.setCurrentIndex(max(0, self.app.findData(sp["app"])))
        self.app.setToolTip("Les sons que joue l'appli (alarmes, appel des micros), répétés.")
        self.path, self.wav_lbl = sp["path"], QtWidgets.QLabel("")
        wb = QtWidgets.QPushButton("📂 Choisir un WAV…")
        wb.setToolTip("Ton fichier WAV (voix, musique, signal de test), joué en boucle.")
        wb.clicked.connect(lambda *_: self.pick_wav())
        self.rows = {}
        for key, lab, w in (("f", "Fréquence :", self.f), ("f1", "De :", self.f1), ("f2", "À :", self.f2),
                            ("dur", "Durée :", self.dur), ("log", "", self.log), ("app", "Son :", self.app)):
            f.addRow(lab, w)
            self.rows[key] = w
        rw = QtWidgets.QWidget()
        rl = QtWidgets.QHBoxLayout(rw)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(wb)
        rl.addWidget(self.wav_lbl, 1)
        f.addRow("Fichier :", rw)
        self.rows["wav"] = rw
        ref = owner.audio_ref                                 # 8.1 : niveau visé, vu-mètre, déviation
        self.lvl_chk = QtWidgets.QCheckBox("Régler le niveau à")
        self.lvl_chk.setChecked(sp.get("lvl") is not None)
        self.lvl_chk.setToolTip("Coché : le son est amené à ce niveau (moyen, RMS). Décoché : son niveau d'origine.\n"
                                "Repère d'alignement courant : −18 dBFS (EBU) ou −20 dBFS (SMPTE).")
        self.lvl = QtWidgets.QDoubleSpinBox()
        self.lvl.setDecimals(1)
        self.lvl.setSingleStep(0.5)
        self.lvl_unit = ref["unit"] if ref["unit"] != "vrms" else "dbu"
        lo_, hi_ = (dbfs_to_unit(-60, ref, self.lvl_unit), dbfs_to_unit(0, ref, self.lvl_unit))
        self.lvl.setRange(min(lo_, hi_), max(lo_, hi_))
        self.lvl.setSuffix(" " + dict(AUDIO_UNITS).get(self.lvl_unit, "dBFS"))
        self.lvl.setValue(dbfs_to_unit(sp["lvl"] if sp.get("lvl") is not None else ref["target"], ref, self.lvl_unit))
        self.lvl.setToolTip("Niveau visé, dans l'unité choisie dans 📏 Échelles et niveaux.")
        tgt = QtWidgets.QPushButton("🎯")
        tgt.setToolTip("Mettre le niveau visé du réglage (📏 Échelles et niveaux).")
        tgt.clicked.connect(lambda *_: (self.lvl_chk.setChecked(True),
                                        self.lvl.setValue(dbfs_to_unit(owner.audio_ref["target"], owner.audio_ref,
                                                                       self.lvl_unit))))
        helpb = QtWidgets.QPushButton("📏")
        helpb.setToolTip("Échelles et niveaux : unité, alignement, et la fiche qui explique dBFS, dBu, dBV…")
        helpb.clicked.connect(lambda *_: owner.open_scales())
        f.addRow(owner._row(self.lvl_chk, self.lvl, tgt, helpb, None))
        self.gain = QtWidgets.QDoubleSpinBox()              # 8.1 : gain à la main (ou celui calculé, affiché)
        self.gain.setRange(-60.0, 40.0)
        self.gain.setDecimals(1)
        self.gain.setSingleStep(1.0)
        self.gain.setSuffix(" dB")
        self.gain.setValue(float(sp.get("gain") or 0.0))
        self.gain.setToolTip("Gain appliqué au son. « Régler le niveau » décoché : c'est toi qui le règles.\n"
                             "Coché : il est calculé pour atteindre le niveau visé (sur tout le fichier), sans jamais "
                             "écrêter.")
        self.gain_lbl = QtWidgets.QLabel("")
        f.addRow("Gain :", owner._row(self.gain, self.gain_lbl, None))
        self.gain.valueChanged.connect(lambda *_: None if self.lvl_chk.isChecked() else self._changed())
        self.meter = AudioMeterBar(owner, self)
        f.addRow("Niveau :", self.meter)
        self.meter_txt = QtWidgets.QLabel("")
        self.meter_txt.setWordWrap(True)
        self.meter_txt.setToolTip("Mesuré sur le son qui sera joué : moyen (RMS), crête, True Peak, et la déviation FM\n"
                                  "que ce niveau donne sur un micro (0 dBFS = déviation max du réglage d'écoute).")
        f.addRow(self.meter_txt)
        self.lvl_chk.toggled.connect(lambda *_: self._changed())
        self.lvl.valueChanged.connect(lambda *_: self._changed())
        lay.addLayout(f)
        note = QtWidgets.QLabel("Dans l'écoute d'un micro HF (FM), les aigus au-delà de ~15 kHz sont coupés : c'est la "
                                "bande audio d'un micro, pas un défaut.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8e8e93;")
        lay.addWidget(note)
        self.play_btn = QtWidgets.QPushButton("▶ Écouter ici")
        self.play_btn.setCheckable(True)
        self.play_btn.setToolTip("Joue le son sur la sortie audio de l'appli (⚙ Réglages › Son).")
        self.play_btn.toggled.connect(lambda on: self.play(on))
        self.vol = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(40)
        self.vol.setMaximumWidth(140)
        self.vol.setToolTip("Volume (commence bas : un générateur peut être fort).")
        self.vol.valueChanged.connect(lambda v: self.fx.setVolume(v / 100.0) if self.fx is not None else None)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addLayout(owner._row(self.play_btn, "Volume :", self.vol, None))
        lay.addWidget(self.msg)
        if standalone:                                      # 8.0.3 : « le générateur sert à quoi ? » -> l'affecter
            box = QtWidgets.QGroupBox(TR("Utiliser ce son pour…"))
            bl = QtWidgets.QFormLayout(box)
            self.target = QtWidgets.QComboBox()
            self.target.setToolTip(TR("Où va ce son : un micro de ta liste (il l'émet dans les démos tinySA / SDR), un son "
                                      "d'alarme, ou l'émission avec un HackRF."))
            self.sig = QtWidgets.QComboBox()
            for k_, t_ in DEMO_SIG_KINDS:
                self.sig.addItem(TR(t_), k_)
            self.sig.setToolTip(TR("Ce que ce micro émet dans les démos (tinySA et SDR) : micro FM avec ce son, micro "
                                   "numérique, coupures, brouilleur, rien."))
            self.assign_btn = QtWidgets.QPushButton(TR("✔ Affecter"))
            self.assign_btn.setToolTip(TR("Applique ce son (et ce type de signal) à la cible choisie."))
            self.assign_btn.clicked.connect(lambda *_: self.assign())
            bl.addRow(TR("Cible :"), self.target)
            bl.addRow(TR("Signal (démos) :"), self.sig)
            bl.addRow("", self.assign_btn)
            self.target.currentIndexChanged.connect(lambda *_: self._target_changed())
            lay.addWidget(box)
            self.fill_targets()
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close if standalone else
                                        QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for w in (self.src, self.app):
            w.currentIndexChanged.connect(lambda *_: self._changed())
        for w in (self.f, self.f1, self.f2, self.dur):
            w.valueChanged.connect(lambda *_: self._changed())
        self.log.toggled.connect(lambda *_: self._changed())
        self.finished.connect(lambda *_: self.play(False))
        self._changed()

    def fill_targets(self):
        """Cibles : tes micros (démos), les sons d'alarme, l'émission HackRF."""
        o = self.owner
        cur = self.target.currentData()
        self.target.blockSignals(True)
        self.target.clear()
        for w in sorted(o.watch, key=lambda w: w["freq"]):
            self.target.addItem(TR("🎤 {} · {} MHz (démos tinySA / SDR)").format(w.get("name") or "—", f"{w['freq']:.3f}"),
                                f"mic:{int(round(w['freq'] * 1000))}")
        for k_, t_ in (("alarm2", "🔔 Son d'alarme critique"), ("alarm1", "🔔 Son d'alarme normale"),
                       ("alarm0", "🔔 Son d'alarme info"), ("ok", "✓ Son de l'appel des micros")):
            self.target.addItem(TR(t_), f"alarm:{k_}")
        self.target.addItem(TR("📡 Émettre avec un HackRF (nouvelle ligne)"), "tx:")
        i = self.target.findData(cur) if cur is not None else -1
        self.target.setCurrentIndex(max(0, i))
        self.target.blockSignals(False)
        self._target_changed()

    def _tgt(self):
        k, _, v = str(self.target.currentData() or ":").partition(":")
        return k, (int(v) if k == "mic" and v.isdigit() else v)

    def _target_changed(self):
        if hasattr(self, "meter"):
            QtCore.QTimer.singleShot(0, self._measure)      # la déviation dépend du micro visé
        t = self._tgt()
        self.sig.setEnabled(t[0] == "mic")
        if t[0] == "mic":
            k = (self.owner.sdr_cfg.get("demo_kind") or {}).get(str(t[1])) or "auto"
            self.sig.setCurrentIndex(max(0, self.sig.findData(k)))

    def assign(self):
        o, sp = self.owner, self.spec()
        t = self._tgt()
        if t[0] == "mic":
            w = o.watch_by_key(t[1])
            if w is None:
                return
            o.demo_sound(w, sp)
            dk = dict(o.sdr_cfg.get("demo_kind") or {})
            if self.sig.currentData() == "auto":
                dk.pop(str(t[1]), None)
            else:
                dk[str(t[1])] = self.sig.currentData()
            o.sdr_cfg["demo_kind"] = dk
            for e_ in (getattr(o, "sdr_engs", None) or {}).values():
                e_._t_demo = 0.0                            # le SDR démo prend le nouveau signal tout de suite
            self.msg.setText(TR("✔ {} : « {} », {} — lance le mode démo (tinySA ou 🧪 SDR démo) pour le voir et "
                                "l'écouter.").format(w.get("name") or f"{w['freq']:.3f}", audio_text(sp, TR),
                                                     self.sig.currentText()))
        elif t[0] == "alarm":
            o.set_alarm_sound(t[1], sp)
            self.msg.setText(TR("✔ Son « {} » affecté : {}.").format(self.target.currentText(), audio_text(sp, TR)))
        elif t[0] == "tx":
            d = o.open_sdr_tx()
            if d is not None:
                d.add_row(dict(f=606.0, kind="fm", audio=sp))
                self.msg.setText(TR("✔ Ligne ajoutée à l'émission HackRF : règle sa fréquence."))

    def spec(self):
        lvl = unit_to_dbfs(self.lvl.value(), self.owner.audio_ref, self.lvl_unit) if self.lvl_chk.isChecked() else None
        return audio_spec_norm(dict(src=self.src.currentData(), f=self.f.value(), f1=self.f1.value(), f2=self.f2.value(),
                                    dur=self.dur.value(), log=self.log.isChecked(), app=self.app.currentData(),
                                    path=self.path, lvl=lvl, gain=0.0 if lvl is not None else self.gain.value()))

    def _measure(self):
        """8.1 : vu-mètre et déviation du son choisi (mesurés sur 1 à 3 s du son réel)."""
        try:
            sp = self.spec()
            if sp["src"] == "wav" and sp["path"]:
                wav_load(sp["path"])
            secs = min(3.0, sp["dur"]) if sp["src"] == "sweep" else 1.5
            ref = self.owner.audio_ref
            g_, lim_ = audio_gain(sp, 0)
            if sp["src"] == "wav" and len(WAV_PCM.get(sp["path"], [])):   # 8.1 : un WAV est mesuré EN ENTIER
                x_ = np.clip(np.asarray(WAV_PCM[sp["path"]], dtype=np.float32) * 10.0 ** (g_ / 20.0), -1.0, 1.0)
                m = audio_meter(x_)
            else:
                m = audio_meter(demo_audio(sp, np.arange(int(secs * 48000)) / 48000.0, 0))
            self.gain.setEnabled(sp.get("lvl") is None)
            if sp.get("lvl") is not None:
                self.gain.blockSignals(True)
                self.gain.setValue(g_)
                self.gain.blockSignals(False)
            self.gain_lbl.setText(TR("⚠ limité par la crête : niveau visé pas atteint (le son écrêterait)") if lim_
                                  else (TR("calculé pour le niveau visé") if sp.get("lvl") is not None else ""))
            self.gain_lbl.setStyleSheet("color: #ff9f0a;" if lim_ else "color: #8e8e93;")
            self.meter.set_meter(m, sp["lvl"] if sp.get("lvl") is not None else None)
            nom = 48.0
            t_ = self._tgt() if hasattr(self, "target") else ("", None)
            if t_[0] == "mic":
                w = self.owner.watch_by_key(t_[1])
                p_ = demod_preset(self.owner.mic_demod(w)[0]) if w else None
                nom = float((p_ or {}).get("dev") or 48000) / 1000.0
            self.meter_txt.setText(TR("moyen {} · crête {} · True Peak {} · en FM : déviation crête {} kHz (0 dBFS = {} kHz)")
                                   .format(fmt_audio(m["rms"], ref), fmt_audio(m["peak"], ref, "dbfs"),
                                           fmt_audio(m["tp"], ref, "dbfs").replace("dBFS", "dBTP"),
                                           f"{fm_deviation(m['peak'], nom):.1f}".replace(".", ","), f"{nom:g}"))
        except Exception as e:  # noqa: BLE001
            self.meter_txt.setText(str(e))

    def _changed(self):
        src = self.src.currentData()
        show = {"tone": ("f",), "sweep": ("f1", "f2", "dur", "log"), "app": ("app",), "wav": ("wav",)}.get(src, ())
        lay = self.layout().itemAt(0).layout()
        for k, w in self.rows.items():
            try:
                lay.setRowVisible(w, k in show)
            except Exception:  # noqa: BLE001
                w.setVisible(k in show)
        self.wav_lbl.setText(audio_text(self.spec(), TR) if self.path else TR("(aucun fichier)"))
        if hasattr(self, "meter"):
            self._measure()
        if self.play_btn.isChecked():                       # on change le son en l'écoutant : on relance
            self.play(True)                                 # (8.0.2 : play(False) décochait ▶ -> plus de relance)

    def pick_wav(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Fichier WAV", "", "Son WAV (*.wav);;Tous (*)")
        if not p:
            return
        ok, txt = wav_load(p)
        self.msg.setText(txt)
        if ok:
            self.path = p
            self.src.setCurrentIndex(max(0, self.src.findData("wav")))
        self._changed()

    def play(self, on):
        if self.fx is not None:
            try:
                self.fx.stop()
            except Exception:  # noqa: BLE001
                pass
            self.fx = None
        if not on:
            if self.play_btn.isChecked():
                self.play_btn.blockSignals(True)
                self.play_btn.setChecked(False)
                self.play_btn.blockSignals(False)
            if getattr(self, "_live_t", None) is not None:
                self._live_t.stop()
                self._live = None
                self._measure()                              # retour à la mesure du son entier
            return
        import tempfile
        import wave
        sp = self.spec()
        if sp["src"] == "wav" and sp["path"]:
            wav_load(sp["path"])
        secs = sp["dur"] if sp["src"] == "sweep" else (min(30.0, len(WAV_PCM.get(sp["path"], [])) / 48000.0)
                                                         if sp["src"] == "wav" else 4.0)
        t = np.arange(int(max(0.5, secs) * 48000)) / 48000.0
        a = demo_audio(sp, t, 0)
        try:
            self._tmp = temp_wav_path("gen", self._tmp)  # 8.0.2 : un NOUVEAU fichier à chaque lecture (voir temp_wav_path)
            with wave.open(self._tmp, "wb") as w:        # stéréo 16 bits 48 kHz : le format le plus partout lu
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(48000)
                w.writeframes(np.repeat((np.clip(a, -1, 1) * 32767).astype("<i2"), 2).tobytes())
            from PySide6 import QtMultimedia
            dev = self.owner.sound._device(QtMultimedia) if hasattr(self.owner, "sound") else None
            fx = QtMultimedia.QSoundEffect(dev, self) if dev is not None else QtMultimedia.QSoundEffect(self)
            fx.setSource(QtCore.QUrl.fromLocalFile(self._tmp))
            fx.setLoopCount(-2)                              # QSoundEffect.Infinite : en boucle
            fx.setVolume(self.vol.value() / 100.0)
            fx.play()
            self.fx = fx
            self._live = (a.astype(np.float32), time.monotonic(), sp.get("lvl"))   # 8.1 : vu-mètre en direct
            self._live_pk = -math.inf
            if getattr(self, "_live_t", None) is None:
                self._live_t = QtCore.QTimer(self)
                self._live_t.timeout.connect(self._live_tick)
            self._live_t.start(50)
            self.msg.setText(TR("▶ {} (en boucle)").format(audio_text(sp, TR)))
        except Exception as e:  # noqa: BLE001 — jamais de plantage pour un son
            self.msg.setText(TR("⚠ Son impossible ici : {}").format(e))
            self.play(False)


    def _live_tick(self):
        """8.1 : pendant « Écouter ici », le vu-mètre suit ce qui sort (50 ms autour de la position de lecture,
        crête tenue qui redescend) : un WAV, une voix ou un balayage font bouger la barre en direct."""
        lv = getattr(self, "_live", None)
        if not lv or self.fx is None:
            return
        a, t0, tgt = lv
        n = len(a)
        if not n:
            return
        i = int((time.monotonic() - t0) * 48000) % n
        seg = a[i:i + 2400] if i + 2400 <= n else np.concatenate([a[i:], a[:i + 2400 - n]])
        m = audio_meter(seg)
        self._live_pk = max(m["peak"], self._live_pk - 0.6) if math.isfinite(m["peak"]) else self._live_pk - 0.6
        m = dict(m, peak=self._live_pk)
        self.meter.set_meter(m, tgt)


def audio_button(owner, spec, on_change=None):
    """Bouton « 🎵 son » qui ouvre AudioPickDialog ; le choix est dans b.spec."""
    b = QtWidgets.QPushButton()
    b.spec = audio_spec_norm(spec)
    b.setToolTip("Le son qui module ce signal : générateur, balayage, bruit, sons de l'appli, ton WAV…")

    def upd():
        b.setText("🎵 " + audio_text(b.spec, TR))

    def pick():
        d = AudioPickDialog(owner, b.spec)
        if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            b.spec = d.spec()
            upd()
            if on_change:
                on_change(b.spec)
    b.clicked.connect(lambda *_: pick())
    upd()
    return b


# ---- étape 21 (Clément : « on peut même choisir les sons d'alarmes » -> « garde ça en V8 ») : sons des alarmes au choix


class SdrTxDialog(QtWidgets.QDialog):
    """📡 Émettre avec un HackRF, EN CÂBLE (étape 21) : faux micros FM (son + pilote), porteuses, talkies, blocs larges,
    brouilleur intermittent — pour tester un récepteur, l'écoute de l'appli, l'intermod ou s'entraîner à la chasse.
    En SDR démo, rien n'est émis : le SDR démo « reçoit » l'émission simulée."""
    COLS = ("MHz", "Type", "Son", "Pilote", "Intermittent", "Niveau")

    def __init__(self, owner):
        super().__init__(owner)
        self.owner, self.run = owner, None
        self.setWindowTitle("📡 Émettre avec un HackRF (en câble)")
        lay = QtWidgets.QVBoxLayout(self)
        warn = QtWidgets.QLabel("⚠ Émettre à l'antenne sans autorisation est interdit. En CÂBLE seulement, avec un "
                                "atténuateur (30 dB ou plus) avant l'entrée du récepteur ou du tinySA.")
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {owner.tone_color('bad')}; font-weight: bold;")
        lay.addWidget(warn)
        self.demo_lbl = QtWidgets.QLabel("")
        self.demo_lbl.setWordWrap(True)
        lay.addWidget(self.demo_lbl)
        self.tbl = QtWidgets.QTableWidget(0, len(self.COLS))
        self.tbl.setHorizontalHeaderLabels(list(self.COLS))
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setToolTip("Ce que le HackRF émet en même temps (8 au plus, tous dans une même fenêtre de quelques MHz).")
        lay.addWidget(self.tbl, 1)
        add = QtWidgets.QPushButton("＋ Ajouter un signal")
        add.setToolTip("Un faux micro FM de plus (change le type, le son…).")
        add.clicked.connect(lambda *_: self.add_row())
        mine = QtWidgets.QPushButton("Depuis ma liste")
        mine.setToolTip("Ajoute les micros choisis dans « Mes fréquences » (ou les 3 premiers).")
        mine.clicked.connect(lambda *_: self.from_list())
        dele = QtWidgets.QPushButton("Retirer")
        dele.setToolTip("Retire les lignes choisies.")
        dele.clicked.connect(lambda *_: self.del_rows())
        lay.addLayout(owner._row(add, mine, dele, None))
        self.gain = QtWidgets.QSpinBox()
        self.gain.setRange(0, 47)
        self.gain.setSuffix(" dB")
        self.gain.setToolTip("Gain d'émission du HackRF (0 à 47 dB). Commence à 0 : en câble, c'est déjà bien assez.")
        self.amp = QtWidgets.QCheckBox("Ampli (+ ~11 dB)")
        self.amp.setToolTip("Ampli de sortie du HackRF. Inutile en câble : laisse-le coupé.")
        self.dur = QtWidgets.QComboBox()
        for m_ in TX_DURATIONS:
            self.dur.addItem(TR("{} min").format(m_), m_)
        self.dur.setCurrentIndex(1)
        self.dur.setToolTip("L'émission s'arrête toute seule au bout de ce temps.")
        lay.addLayout(owner._row("Gain :", self.gain, self.amp, "Durée :", self.dur, None))
        self.cable = QtWidgets.QCheckBox("Je suis EN CÂBLE avec un atténuateur, aucune antenne branchée")
        self.cable.setToolTip("Obligatoire pour émettre.")
        lay.addWidget(self.cable)
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.go = QtWidgets.QPushButton("📡 Émettre")
        self.go.setToolTip("Lance / arrête l'émission.")
        self.go.clicked.connect(lambda *_: self.toggle())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre (l'émission s'arrête).")
        close.clicked.connect(self.close)
        lay.addLayout(owner._row(self.go, None, close))
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(500)
        fit_dialog(self, 760, 520)
        self.add_row(dict(f=606.0))
        self.refresh()

    # ---- lignes
    def add_row(self, r=None):
        r = dict(dict(f=606.0, kind="fm", audio="voice", pilot=True, burst=False, lvl=0.0), **(r or {}))
        if self.tbl.rowCount() >= TX_MAX_SIGS:
            return
        i = self.tbl.rowCount()
        self.tbl.insertRow(i)
        f = QtWidgets.QDoubleSpinBox()
        f.setRange(1.0, 6000.0)
        f.setDecimals(3)
        f.setSingleStep(0.025)
        f.setValue(float(r["f"]))
        k = QtWidgets.QComboBox()
        for k_, t_ in SIG_KINDS:
            k.addItem(t_, k_)
        k.setCurrentIndex(max(0, k.findData(r["kind"])))
        a = audio_button(self.owner, r["audio"])
        p = QtWidgets.QCheckBox()
        p.setChecked(bool(r["pilot"]))
        p.setToolTip("Tonalité pilote inaudible (32,768 kHz) comme beaucoup de micros analogiques.")
        b = QtWidgets.QCheckBox()
        b.setChecked(bool(r["burst"]))
        b.setToolTip("Allumé 1 s toutes les 4 s : un brouilleur qui va et vient (chasse, alarmes).")
        lv = QtWidgets.QSpinBox()
        lv.setRange(-40, 0)
        lv.setSuffix(" dB")
        lv.setValue(int(r["lvl"]))
        lv.setToolTip("Niveau par rapport au signal le plus fort (0 dB).")
        for c, w in enumerate((f, k, a, p, b, lv)):
            self.tbl.setCellWidget(i, c, w)
        for w in (f, lv):
            w.valueChanged.connect(lambda *_: self.refresh())
        k.currentIndexChanged.connect(lambda *_: self.refresh())

    def rows(self):
        out = []
        for i in range(self.tbl.rowCount()):
            w = [self.tbl.cellWidget(i, c) for c in range(len(self.COLS))]
            out.append(dict(f=w[0].value(), kind=w[1].currentData(), audio=w[2].spec, pilot=w[3].isChecked(),
                            burst=w[4].isChecked(), lvl=float(w[5].value())))
        return out

    def from_list(self):
        o = self.owner
        rows = sorted({ix.row() for ix in o.watch_table.selectionModel().selectedRows()}) if hasattr(o, "watch_table") \
            else []
        ws = [o.watch[r] for r in rows if 0 <= r < len(o.watch)] or list(o.watch[:3])
        for w in ws:
            dig = o.mic_demod(w)[0] == DEMOD_DIGITAL if hasattr(o, "mic_demod") else False
            self.add_row(dict(f=w["freq"], kind="noise" if dig or (w.get("bw") or 0) > 0 else "fm"))
        self.refresh()

    def del_rows(self):
        for r in sorted({ix.row() for ix in self.tbl.selectionModel().selectedIndexes()}, reverse=True):
            self.tbl.removeRow(r)
        self.refresh()

    # ---- émission
    def demo(self):
        return bool(self.owner.sdr_cfg.get("demo"))

    def plan(self):
        return tx_plan(self.rows())

    def refresh(self):
        r = self.run
        on = r is not None and r.running()
        if r is not None and not on:
            self._ended(r)
        self.demo_lbl.setText(TR("🧪 SDR démo allumé : émission SIMULÉE, rien ne sort. Le SDR démo la « reçoit » : regarde "
                                 "le spectre et écoute.") if self.demo() else "")
        if on:
            left = max(0, int(r.until - time.time()))
            self.info.setText(TR("📡 Émission en cours · {} min {:02d} s restantes").format(left // 60, left % 60))
        else:
            p = self.plan()
            self.info.setText(p if isinstance(p, str) else TR("Centre {} MHz · débit {} MS/s · {} signal(aux)").format(
                f"{p[0] / 1e6:.3f}", f"{p[1] / 1e6:g}", len(p[2])))
        t = "■ Arrêter l'émission" if on else "📡 Émettre"
        if getattr(self, "_gt", None) != t:
            self._gt = t
            self.go.setText(t)

    def toggle(self):
        if self.run is not None and self.run.running():
            self.stop()
            return
        o = self.owner
        if not self.cable.isChecked() and not self.demo():
            self.info.setText(TR("Coche d'abord « en câble avec un atténuateur »."))
            return
        p = self.plan()
        if isinstance(p, str):
            self.info.setText(p)
            return
        fc, rate, sigs = p
        until = time.time() + 60.0 * int(self.dur.currentData() or 5)
        if self.demo():
            self.run = TxRunner(fc, rate, sigs, until, demo=True)
        else:
            busy = [e for e in (getattr(o, "sdr_engs", None) or {}).values() if e.running() and e.kind() == "hackrf"]
            busy += [w for w in getattr(o, "workers", []) if w.isRunning() and getattr(w, "sdr", False)
                     and (parse_sdr_addr(getattr(w, "port", "")) or ("",))[0] == "hackrf"]     # audit : balayage hackrf_sweep
            if busy:
                self.info.setText(TR("Un poste SDR utilise le HackRF : arrête-le d'abord (un HackRF reçoit OU émet)."))
                return
            exe = getattr(o, "_tx_tool", None) or find_sdr_tool("hackrf_transfer", o.sdr_cfg.get("dir", ""))
            if not exe:
                self.info.setText(TR("hackrf_transfer introuvable (outils HackRF : PothosSDR, ou 📡 Réglages SDR)."))
                return
            ser = next((pp["serial"] for pp in sdr_posts_norm(o.sdr_cfg.get("posts"))
                        if (sdr_model(pp["model"]) or {}).get("kind") == "hackrf" and pp["serial"]), "")
            try:
                self.run = TxRunner(fc, rate, sigs, until, exe=exe, gain=self.gain.value(), amp=self.amp.isChecked(),
                                    serial=ser)
            except OSError as ex:
                self.info.setText(TR("⚠ Impossible de lancer hackrf_transfer : {}").format(ex))
                return
        o.log_event(dict(name=TR("Émission SDR"), freq=fc / 1e6, note=TR("{} · gain {} dB{} · {}").format(
            ", ".join(f"{s_['f']:.3f}" for s_ in sigs), self.gain.value(), TR(" · ampli") if self.amp.isChecked() else "",
            TR("simulée (SDR démo)") if self.demo() else TR("en câble"))), 0.0, "ÉMISSION SDR")
        self.refresh()

    def _ended(self, r):
        self.run = None
        why = r.why or (r.err[-1] if r.err else "")
        self.owner.log_event(dict(name=TR("Émission SDR"), freq=r.fc / 1e6, note=why or TR("arrêtée")), 0.0,
                             "FIN D'ÉMISSION SDR")
        if why:
            self.owner.set_status(TR("⚠ Émission arrêtée : {}").format(why))

    def stop(self):
        r = self.run
        if r is not None:
            r.stop()
            self._ended(r)
        self.refresh()

    def closeEvent(self, ev):
        self.stop()
        super().closeEvent(ev)


class SdrDemoMixin:
    """Générateur audio, sons des alarmes, SDR démo et émission. (Méthodes de MainWindow, regroupées par thème.)"""

    def open_audio_gen(self):
        d = getattr(self, "_audiogen", None)
        if d is None:
            d = self._audiogen = AudioPickDialog(self, standalone=True)
        d.fill_targets()
        d.show()
        d.raise_()
        return d

    def set_alarm_sound(self, key, spec):
        d = alarm_sounds_norm(getattr(self.sound, "custom", None))
        if spec is None:
            d.pop(key, None)
        else:
            d[key] = audio_spec_norm(spec)
            if d[key]["src"] == "wav":
                wav_load(d[key]["path"])
        self.sound.custom = d

    def test_alarm_sound(self, key):
        self.sound.play({"alarm2": ALARM_TONES[2], "alarm1": ALARM_TONES[1], "alarm0": ALARM_TONES[0],
                         "ok": TONE_OK}.get(key, ALARM_TONES[2]))

    def demo_sound(self, w, spec):
        """🎵 Son d'un micro dans le SDR démo (sdr_cfg « demo_snd » {kHz: source}) ; None = son par défaut."""
        d = dict(self.sdr_cfg.get("demo_snd") or {})
        k = str(int(round(w["freq"] * 1000)))
        if spec is None:
            d.pop(k, None)
        else:
            d[k] = audio_spec_norm(spec)
            if d[k]["src"] == "wav":
                wav_load(d[k]["path"])
        self.sdr_cfg["demo_snd"] = d
        for e in (getattr(self, "sdr_engs", None) or {}).values():
            e._t_demo = 0.0                                   # le SDR démo prend le nouveau son tout de suite

    def pick_demo_sound(self, w):
        cur = (self.sdr_cfg.get("demo_snd") or {}).get(str(int(round(w["freq"] * 1000))))
        d = AudioPickDialog(self, cur, title=TR("🎵 Son de {} dans le SDR démo").format(w.get("name") or f"{w['freq']:.3f}"))
        if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.demo_sound(w, d.spec())

    def demo_mics(self):
        """Micros que « reçoit » le SDR démo : ta liste (sauf les 💤 éteints et ceux hors de l'état 📸 actif)."""
        out = []
        tuned = {}                     # 8.1 : micro écouté sur A -> le « pack » démo est réglé comme ton écoute (même
        for e_ in (getattr(self, "sdr_engs", None) or {}).values():       # déviation nominale, même compander) : un
            cm = getattr(e_, "cur_mic", None)                             # −18 dBFS envoyé se lit −18 dBFS à l'écoute
            if cm is not None and isinstance(getattr(e_, "demod", None), dict):
                d_ = e_.demod
                tuned[id(cm)] = (float(d_.get("dev") or LISTEN_MODES.get(d_.get("mode", ""), {}).get("dev") or 0) or None,
                                 d_.get("compander") or "")
        for w in self.watch:
            if w.get("muted") or w.get("off"):
                continue
            snd = (self.sdr_cfg.get("demo_snd") or {}).get(str(int(round(w["freq"] * 1000))))
            if snd and audio_spec_norm(snd)["src"] == "wav" and audio_spec_norm(snd)["path"] not in WAV_PCM:
                wav_load(audio_spec_norm(snd)["path"])
            out.append(dict(f=w["freq"], name=w.get("name", ""), bw=float(w.get("bw") or 0.0),
                            free=self.is_keep_free(w.get("status")),
                            digital=self.mic_demod(w)[0] == DEMOD_DIGITAL, snd=snd,
                            dev=float((demod_preset(self.mic_demod(w)[0]) or {}).get("dev") or 0) or None,
                            comp=(demod_preset(self.mic_demod(w)[0]) or {}).get("comp") or "",
                            kind=(self.sdr_cfg.get("demo_kind") or {}).get(str(int(round(w["freq"] * 1000)))) or "auto"))
            if id(w) in tuned:
                out[-1]["dev"], out[-1]["comp"] = tuned[id(w)]
        return out

    def set_sdr_demo(self, on):
        """🧪 SDR démo allumé / éteint : les postes en marche repartent sur la nouvelle source."""
        on = bool(on)
        if bool(self.sdr_cfg.get("demo")) == on:
            return
        run = [e for e in (getattr(self, "sdr_engs", None) or {}).values() if e.running()]
        for e in run:
            e.stop()
        self.sdr_cfg["demo"] = on
        tx = getattr(self, "_sdrtx", None)
        if tx is not None and tx.run is not None:
            tx.stop()
        if on:
            if self.rf_mode == "tiny":
                self.set_rf_mode("sdr")
            for e in run or [self.sdr_eng]:
                e.start()
            self.set_status(TR("🧪 SDR démo : tes micros sont « reçus » avec du son et un pilote ; un brouilleur passe de temps "
                               "en temps, un micro s'éteint, un autre perd son pilote."))
        else:
            sdr_demo_set(plan=[], tx=[])
            self.set_status(TR("SDR démo coupé : le poste SDR reprendra ton vrai SDR au prochain ▶."))
        for d in self.all_sdr_docks():
            if hasattr(self.dock_widget(d), "refresh"):
                self.dock_widget(d).refresh()

    sdr_demo_on = lambda self: self.set_sdr_demo(True)

    sdr_demo_off = lambda self: self.set_sdr_demo(False)

    def open_sdr_tx(self):
        d = getattr(self, "_sdrtx", None)
        if d is None:
            d = self._sdrtx = SdrTxDialog(self)
        d.show()
        d.raise_()
        return d

    toggle_sdr_demo = lambda self: self.set_sdr_demo(not self.sdr_cfg.get("demo"))


# ------------------------------------------------------------------ V8 étape 22 : premier branchement, calibration,
# remonter le temps (8.0 : les chapitres SDR sont dans le manuel principal, partie « Le SDR (bêta) »)


def sdr_gain_scan(kind, model, base_gains, tool_dir="", iq_tool=None, center=600e6, key="lna", secs=0.4, cancel=None,
                  progress=None, wr_lib=None):
    """🎚 Essaie chaque valeur de l'étage `key` (sans Qt, dans un fil) : saturation (part d'échantillons à pleine
    échelle), bruit (médiane du spectre) et crête (dBFS de l'échantillon le plus fort). -> [dict(gain, ovf, floor,
    peak)] ou lève RuntimeError (SDR introuvable…)."""
    steps = gain_steps(model, key) or [None]
    rate = sdr_rate(model, kind)
    rows = []
    for i, g in enumerate(steps):
        if cancel is not None and cancel():
            break
        gains = dict(base_gains or {})
        if g is not None:
            gains[key] = g
        src = open_iq_source(kind, center, rate, gains, tool=iq_tool, tool_dir=tool_dir, wr_lib=wr_lib)
        dog = threading.Timer(secs + 6.0, src.close)
        dog.daemon = True
        dog.start()
        try:
            nb = IQ_BYTES[src.dtype]
            want = int((secs + 0.15) * src.rate) * nb
            buf, t0 = bytearray(), time.time()
            while len(buf) < want and time.time() - t0 < secs + 4.0:
                d = src.read(min(262144, want - len(buf)))
                if not d:
                    break
                buf += d
        finally:
            dog.cancel()
            src.close()
        skip = int(0.15 * src.rate) * nb
        if len(buf) <= skip + 4096 * nb:
            raise RuntimeError((list(src.err or []) or [TR("aucune donnée reçue")])[-1][:160])
        iq = iq_decode(src.dtype, bytes(buf[skip: skip + (len(buf) - skip) // nb * nb]))
        ovf = float(np.mean((np.abs(iq.real) > 0.98) | (np.abs(iq.imag) > 0.98)))
        avg, _mx = rt_frames(iq, 4096)
        pk = float(np.max(np.abs(iq))) if len(iq) else 0.0
        rows.append(dict(gain=g, ovf=round(ovf, 5), floor=round(float(np.median(avg)), 1) if avg is not None else None,
                         peak=round(20.0 * math.log10(max(pk, 1e-6)), 1)))
        if progress:
            progress(i + 1, len(steps))
    return rows


class SdrSetupWizard(QtWidgets.QDialog):
    """🔌 Premier branchement SDR (étape 22) : choisir son SDR, le trouver, régler le gain tout seul, écouter un micro,
    caler les niveaux sur le tinySA, et un diagnostic à envoyer. Chaque étape dit ✔ / ✖ et quoi faire."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner, self.res, self.job = owner, {}, None
        self.setWindowTitle("🔌 Premier branchement SDR")
        lay = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel("Branche ton SDR, puis fais les étapes dans l'ordre. Si une étape bloque, le 🩺 diagnostic "
                                 "en bas résume tout pour le support.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.demo_lbl = QtWidgets.QLabel("")
        self.demo_lbl.setWordWrap(True)
        self.demo_btn = QtWidgets.QPushButton("Couper le SDR démo")
        self.demo_btn.setToolTip("Le SDR démo est allumé : coupe-le pour régler ton vrai SDR.")
        self.demo_btn.clicked.connect(lambda *_: (owner.set_sdr_demo(False), self.refresh()))
        lay.addLayout(owner._row(self.demo_lbl, self.demo_btn))
        g = QtWidgets.QGridLayout()
        self.model = QtWidgets.QComboBox()
        for m_ in SDR_MODELS:
            if m_["kind"]:
                self.model.addItem(m_["name"], m_["key"])
        cur = owner.sdr_cfg.get("model") or SDR_MODEL_DEFAULT.get("hackrf")
        self.model.setCurrentIndex(max(0, self.model.findData(cur)))
        self.model.setToolTip("Le modèle exact de ton SDR (règle ses débits, gains et plage).")
        self.model.currentIndexChanged.connect(lambda *_: self.set_model())
        self.st = {}
        steps = (("model", "1. Mon SDR", self.model),
                 ("probe", "2. Le trouver", self._btn("🔌 Chercher mon SDR", "Outil trouvé, SDR détecté, signal reçu, débit tenu.", self.probe)),
                 ("gain", "3. Régler le gain tout seul", self._btn("🎚 Régler le gain", "Essaie chaque gain et garde le plus fort qui ne sature pas.", self.gain)),
                 ("listen", "4. Écouter un micro", self._btn("🎧 Écouter", "Lance le poste SDR sur un de tes micros : tu dois l'entendre.", self.listen)),
                 ("calib", "5. Caler les niveaux (facultatif)", self._btn("📏 Caler sur le tinySA", "Compare les mêmes signaux vus par le tinySA et le SDR : niveaux du SDR en vrais dBm.", lambda: owner.open_sdr_calib())),
                 ("diag", "6. Diagnostic", self._btn("🩺 Diagnostic à envoyer", "Écrit un fichier qui résume tout (à m'envoyer si ça coince).", self.diag)))
        for r, (k, t, w) in enumerate(steps):
            g.addWidget(QtWidgets.QLabel(f"<b>{TR(t)}</b>"), r, 0)
            g.addWidget(w, r, 1)
            lab = QtWidgets.QLabel("")
            lab.setWordWrap(True)
            lab.setMinimumWidth(320)
            g.addWidget(lab, r, 2)
            self.st[k] = lab
        g.setColumnStretch(2, 1)
        lay.addLayout(g)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        lay.addStretch(1)
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme l'assistant (ce qui est réglé reste réglé).")
        close.clicked.connect(self.close)
        lay.addLayout(owner._row(None, close))
        fit_dialog(self, 860, 460)
        self.refresh()

    def _btn(self, text, tip, fn):
        b = QtWidgets.QPushButton(text)
        b.setToolTip(tip)
        b.clicked.connect(lambda *_: fn())
        return b

    def mdl(self):
        return sdr_model(self.model.currentData()) or sdr_model(SDR_MODEL_DEFAULT["hackrf"])

    def set_model(self):
        o, m_ = self.owner, self.mdl()
        o.sdr_cfg["model"] = m_["key"]
        o.sdr_cfg.setdefault("models", {})[m_["kind"]] = m_["key"]
        self.say("model", "✔", TR("{} : {} – {} MHz, fenêtre jusqu'à {} MHz").format(
            m_["name"], f"{m_['fmin']:g}", f"{m_['fmax']:g}", f"{sdr_span_mhz(m_, sdr_rate(m_)):.1f}"))

    def say(self, key, mark, txt):
        self.res[key] = (mark, txt)
        c = {"✔": "ok", "✖": "bad", "⚠": "warn"}.get(mark)
        self.st[key].setText(f"{mark} {txt}")
        self.st[key].setStyleSheet(f"color: {self.owner.tone_color(c)};" if c else "")

    def refresh(self):
        on = bool(self.owner.sdr_cfg.get("demo"))
        self.demo_lbl.setText(TR("🧪 Le SDR démo est allumé : l'assistant règle ton VRAI SDR, coupe la démo d'abord.")
                              if on else "")
        self.demo_btn.setVisible(on)
        if "model" not in self.res:
            self.set_model()

    def _busy(self):
        if self.job is not None and not self.job.get("done"):
            return True
        run = [e for e in (getattr(self.owner, "sdr_engs", None) or {}).values() if e.running()]
        if run:                                          # audit : on demande avant d'arrêter l'écoute en cours
            q = QtWidgets.QMessageBox.question(self, TR("Poste SDR en marche"),
                                               TR("Le poste SDR est en marche : l'arrêter le temps du test ?\n"
                                                  "(un SDR ne sert qu'à un logiciel à la fois)"))
            if q != QtWidgets.QMessageBox.StandardButton.Yes:
                return True
            for e in run:
                e.stop()
        return False

    def probe(self):
        if self._busy():
            return
        o, m_ = self.owner, self.mdl()
        self.say("probe", "…", TR("recherche…"))

        def done(res, err=None):
            if err is not None or not isinstance(res, dict):
                self.say("probe", "✖", str(err or res)[:200])
                return
            lines, ok = probe_report(res, TR)
            self.say("probe", "✔" if ok else "✖", " · ".join(lines) if lines else TR("rien"))
        self.job = o.run_heavy(lambda: sdr_probe(m_["kind"], m_, o.sdr_gains(m_["kind"]), o.sdr_cfg.get("dir", ""),
                                                 getattr(o, "_listen_tool", None), 2.0, wr_lib=WINRADIO_LIB),
                               done, self.st["probe"], what="Test du SDR")

    def gain(self):
        if self._busy():
            return
        o, m_ = self.owner, self.mdl()
        key = "lna" if gain_steps(m_, "lna") else None
        if key is None or m_["kind"] == "winradio":
            self.say("gain", "⚠", TR("ce SDR n'a pas de gain réglable ici : règle-le dans 📡 Réglages SDR"))
            return
        self.say("gain", "…", TR("essai des gains…"))
        self.bar.setVisible(True)
        self.bar.setRange(0, len(gain_steps(m_, key)))
        prog = {"v": 0}
        mics = [w["freq"] for w in o.watch if sdr_in_range(m_, w["freq"])]
        center = (mics[0] if mics else (600.0 if sdr_in_range(m_, 600.0) else (m_["fmin"] + m_["fmax"]) / 2)) * 1e6

        ref = {}

        def run():
            return sdr_gain_scan(m_["kind"], m_, o.sdr_gains(m_["kind"]), o.sdr_cfg.get("dir", ""),
                                 getattr(o, "_listen_tool", None), center, key,
                                 cancel=lambda: (ref.get("job") or {}).get("cancel"),
                                 progress=lambda a, b: prog.update(v=a), wr_lib=WINRADIO_LIB)

        def done(rows, err=None):
            self.bar.setVisible(False)
            if err is not None or isinstance(rows, Exception) or not rows:
                self.say("gain", "✖", TR("essai impossible : {}").format(err or rows or TR("rien reçu")))
                return
            g_, why = auto_gain_pick(rows)
            self.gain_rows = rows
            gs = o.sdr_cfg.setdefault("gains", {}).setdefault(m_["key"], {})
            gs[key] = int(g_)
            o.log_event(dict(name=TR("SDR"), freq=center / 1e6, note=TR("gain auto {} : {} dB ({})").format(
                key.upper(), g_, TR(why))), 0.0, "RÉGLAGE")
            self.say("gain", "⚠" if ("sature" in why or "peu de marge" in why) else "✔", TR("{} = {} dB : {}").format(key.upper(), g_, TR(why)) +
                     " · " + " ".join(f"{r_['gain']}:{100 * r_['ovf']:.1f}%" for r_ in rows))
        self.job = ref["job"] = o.run_heavy(run, done, self.st["gain"], what="Réglage du gain")
        t = QtCore.QTimer(self)
        t.timeout.connect(lambda: self.bar.setValue(prog["v"]) if self.bar.isVisible() else t.stop())
        t.start(300)

    def listen(self):
        o = self.owner
        m_ = self.mdl()
        ws = [w for w in o.watch if sdr_in_range(m_, w["freq"]) and not w.get("muted")]
        if ws:
            o.sdr_tune_mic(ws[0])
            self.say("listen", "✔", TR("poste SDR lancé sur {} : tu dois l'entendre (🔊 volume du Récepteur)").format(
                ws[0]["name"] or f"{ws[0]['freq']:.3f}"))
        else:
            o.set_rf_mode("sdr")
            o.sdr_eng.start()
            self.say("listen", "⚠", TR("aucun micro dans la plage du SDR : règle A à la main (fréquence du Récepteur)"))

    def report(self):
        o, m_ = self.owner, self.mdl()
        lines = [f"RF Technical Monitor {APP_VER} — {TR('premier branchement SDR')} — {datetime.now():%Y-%m-%d %H:%M:%S}",
                 f"{TR('Modèle')} : {m_['name']} ({m_['key']}, {m_['kind']})",
                 f"{TR('Gains')} : {o.sdr_gains(m_['kind'])}",
                 f"{TR('Correction de niveau')} : {o.sdr_offset(m_['kind']):+.1f} dB",
                 f"{TR('Dossier des outils')} : {o.sdr_cfg.get('dir', '') or '—'}", ""]
        for k, (mark, txt) in self.res.items():
            lines.append(f"[{k}] {mark} {txt}")
        for r_ in getattr(self, "gain_rows", []) or []:
            lines.append(f"  gain {r_['gain']} : {TR('saturation')} {100 * r_['ovf']:.2f} %, {TR('bruit')} {r_['floor']} dBFS, "
                         f"{TR('crête')} {r_['peak']} dBFS")
        for e in (getattr(o, "sdr_engs", None) or {}).values():
            lines.append(f"{TR('Poste')} {e.pid} ({e.name()}) : {TR('en marche') if e.running() else TR('arrêté')} · {e.msg}")
            w = e.worker
            if w is not None:
                lines += [f"  err : {x}" for x in list(getattr(w, "err", []) or [])[-10:]]
        return "\n".join(lines) + "\n"

    def diag(self):
        d = Path(self.owner.log_dir) / "diagnostic"
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"diagnostic_sdr_{datetime.now():%Y%m%d_%H%M%S}.txt"
            write_atomic(str(p), self.report())
            self.say("diag", "✔", str(p))
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(d)))
        except OSError as ex:
            self.say("diag", "✖", str(ex))


class SdrCalibDialog(QtWidgets.QDialog):
    """📏 Caler les niveaux du SDR sur le tinySA (étape 22) : les mêmes signaux vus par les deux pendant ~15 s
    (puissance de canal ± 100 kHz), écart médian = correction dBFS -> dBm du modèle de SDR."""
    SECS = 15.0

    def __init__(self, owner):
        super().__init__(owner)
        self.owner, self.t0, self.acc = owner, None, None
        self.setWindowTitle("📏 Caler les niveaux du SDR sur le tinySA")
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Le tinySA mesure en dBm, le SDR en dBFS (relatif à son convertisseur). Avec les DEUX en "
                                "marche (mode combiné) et des signaux dans la fenêtre du SDR (tes micros allumés), l'appli "
                                "compare les mêmes signaux pendant 15 s et en déduit la correction du SDR. Mets les deux "
                                "antennes au même endroit.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.tbl = QtWidgets.QTableWidget(0, 4)
        self.tbl.setHorizontalHeaderLabels([TR("MHz"), TR("tinySA (dBm)"), TR("SDR (dBFS)"), TR("Écart (dB)")])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setToolTip("Les signaux vus par les deux (puissance sur ± 100 kHz).")
        lay.addWidget(self.tbl, 1)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.go = QtWidgets.QPushButton("▶ Mesurer (15 s)")
        self.go.setToolTip("Lance la comparaison.")
        self.go.clicked.connect(lambda *_: self.start())
        self.apply_btn = QtWidgets.QPushButton("✔ Appliquer la correction")
        self.apply_btn.setToolTip("Garde cette correction pour ce modèle de SDR (📡 Réglages SDR › correction de niveau).")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(lambda *_: self.apply())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addLayout(owner._row(self.go, self.apply_btn, None, close))
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.result = None
        fit_dialog(self, 640, 460)

    def eng(self):
        return next((e for e in (getattr(self.owner, "sdr_engs", None) or {}).values() if e.running()), None)

    def start(self):
        o, e = self.owner, self.eng()
        if o.sdr_cfg.get("demo"):
            self.msg.setText(TR("Le SDR démo n'a rien à caler : ses niveaux sont fabriqués. Coupe-le pour caler ton vrai SDR."))
            return
        if e is None:
            self.msg.setText(TR("Lance d'abord le poste SDR (▶ du Récepteur), en mode combiné avec le tinySA."))
            return
        if not o.is_running():
            self.msg.setText(TR("Lance d'abord la surveillance du tinySA (▶ Démarrer)."))
            return
        self.e, self.t0, self.acc, self.tsa, self.result = e, time.time(), None, {}, None
        self.apply_btn.setEnabled(False)
        self.timer.start(500)
        self._tick()

    def _tick(self):
        o, e = self.owner, getattr(self, "e", None)
        if self.t0 is None or e is None:
            return
        fr = e.last
        if fr is not None and len(fr["F"]) == len(fr["avg"]):
            F, L = np.asarray(fr["F"], dtype=float), np.asarray(fr["avg"], dtype=float)
            if self.acc is not None and len(self.acc[0]) == len(F) and abs(self.acc[0][0] - F[0]) < 1e-6:
                self.acc = (F, np.maximum(self.acc[1], L))
            else:
                self.acc = (F, L)
        for bid, v in list(o.latest.items()):
            if isinstance(bid, int) and bid >= 0 and v is not None and len(v[0]):
                F, L = np.asarray(v[0], dtype=float), np.asarray(v[1], dtype=float)
                old = self.tsa.get(bid)
                self.tsa[bid] = (F, np.maximum(old[1], L)) if old is not None and len(old[0]) == len(F) else (F, L)
        left = self.SECS - (time.time() - self.t0)
        if left > 0:
            self.msg.setText(TR("Mesure… {} s").format(int(left) + 1))
            return
        self.timer.stop()
        self.t0 = None
        self.compute()

    def compute(self):
        o = self.owner
        if self.acc is None or not self.tsa:
            self.msg.setText(TR("Rien à comparer : le tinySA balaye-t-il la fenêtre du SDR ?"))
            return
        Fs, Ls = self.acc
        parts = sorted(self.tsa.values(), key=lambda v: float(v[0][0]))
        Ft = np.concatenate([p[0] for p in parts])
        Lt = np.concatenate([p[1] for p in parts])
        rbw = (o.live_rbw()[0] if hasattr(o, "live_rbw") else None) or 100.0
        cands = calib_candidates(Ft, Lt, Fs, Ls, rbw)
        self.tbl.setRowCount(len(cands))
        for r, c in enumerate(cands):
            for col, v in enumerate((f"{c['f']:.3f}", f"{c['tsa']:.1f}", f"{c['sdr']:.1f}", f"{c['tsa'] - c['sdr']:+.1f}")):
                self.tbl.setItem(r, col, QtWidgets.QTableWidgetItem(v))
        res = sdr_tsa_offset(cands)
        self.result = res
        if res is None:
            self.msg.setText(TR("Pas assez de signaux vus par les deux (il en faut {}) : allume des micros dans la fenêtre du "
                                "SDR, ou rapproche les antennes.").format(CAL_MIN_SIGNALS))
            return
        cur = o.sdr_offset(self.e.kind())
        stp = float(np.median(np.diff(Ft))) * 1000.0 if len(Ft) > 2 else 0.0
        self.msg.setText(TR("Correction mesurée : {} dB (± {} dB sur {} signaux) · actuelle : {} dB").format(
            f"{res['offset']:+.1f}", f"{res['spread']:.1f}", res["n"], f"{cur:+.1f}") +
            (TR(" · ⚠ écarts importants : antennes à des endroits différents ?") if res["spread"] > 6 else "") +
            (TR(" · ⚠ pas du tinySA ({} kHz) plus grand que sa RBW ({} kHz) : mesure moins sûre (zoome ou affine le "
                "pas)").format(f"{stp:.0f}", f"{rbw:g}") if stp > 1.5 * rbw else ""))
        self.apply_btn.setEnabled(True)

    def apply(self):
        o, res = self.owner, self.result
        if not res:
            return
        m_ = self.e.model()
        o.sdr_cfg.setdefault("offsets", {})[m_["key"]] = float(res["offset"])
        o.log_event(dict(name=TR("SDR"), freq=0.0, note=TR("niveaux calés sur le tinySA : {} dB ({})").format(
            f"{res['offset']:+.1f}", m_["name"])), 0.0, "RÉGLAGE")
        self.msg.setText(TR("✔ Correction gardée pour {} : {} dB.").format(m_["name"], f"{res['offset']:+.1f}"))
        self.apply_btn.setEnabled(False)

    def closeEvent(self, ev):
        self.timer.stop()
        super().closeEvent(ev)


class RewindDialog(QtWidgets.QDialog):
    """⏪ Remonter le temps (étape 22) : le waterfall des dernières minutes du poste SDR (le plus récent en haut, les
    alarmes en repères), clic = choisir un instant, ▶ réécouter à partir de là, 💾 garder le passage (son + image).
    Tout est en mémoire (rien sur le disque tant qu'on ne garde pas)."""

    def __init__(self, owner, eng=None):
        super().__init__(owner)
        self.owner, self.eng = owner, eng or owner.sdr_eng
        self.t_sel, self.fx, self._tmp, self.img_arr = None, None, None, None
        self.setWindowTitle(TR("⏪ Remonter le temps · {}").format(self.eng.name()))
        lay = QtWidgets.QVBoxLayout(self)
        self.dur = QtWidgets.QComboBox()
        for m_ in REWIND_MINUTES:
            self.dur.addItem(TR("{} min gardées").format(m_) if m_ else TR("Désactivé (rien gardé)"), m_)
        rm = owner.sdr_cfg.get("rewind_min", 3)
        self.dur.setCurrentIndex(max(0, self.dur.findData(rm if rm in REWIND_MINUTES else 3)))
        self.dur.setToolTip("Combien de temps CHAQUE poste SDR garde en mémoire (son : ~11 Mo par minute et par poste ;\n"
                            "5 min avec 4 postes ≈ 230 Mo). « Désactivé » : rien n'est gardé.")
        self.dur.currentIndexChanged.connect(lambda *_: self.set_dur())
        rf = QtWidgets.QPushButton("↻ Mettre à jour")
        rf.setToolTip("Recharge les dernières secondes.")
        rf.clicked.connect(lambda *_: self.draw())
        self.mem = QtWidgets.QLabel("")
        lay.addLayout(owner._row(self.dur, rf, None, self.mem))
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "MHz")
        self.plot.setLabel("left", TR("il y a (s)"))
        sdr_light_axes(self.plot)
        self.plot.setToolTip("Le plus récent en haut. Clic = choisir cet instant.")
        self.img = pg.ImageItem()
        self.img.setLookupTable(make_lut(owner.theme.get("wf", "Inferno")))
        self.plot.addItem(self.img)
        self.sel_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#ffd60a", width=1.5))
        self.plot.addItem(self.sel_line)
        self.sel_line.hide()
        self.plot.scene().sigMouseClicked.connect(self._click)
        self.marks = []
        lay.addWidget(self.plot, 1)
        self.at = QtWidgets.QLabel("Clique sur le waterfall pour choisir un instant.")
        self.at.setWordWrap(True)
        lay.addWidget(self.at)
        self.play_btn = QtWidgets.QPushButton("▶ Réécouter à partir d'ici")
        self.play_btn.setCheckable(True)
        self.play_btn.setToolTip("Rejoue ce que le poste SDR faisait entendre à cet instant (60 s au plus).")
        self.play_btn.toggled.connect(lambda on: self.play(on))
        self.keep_btn = QtWidgets.QPushButton("💾 Garder ce passage")
        self.keep_btn.setToolTip("Enregistre le son (WAV, 60 s) et l'image du waterfall. Demande ton accord la 1re fois.")
        self.keep_btn.clicked.connect(lambda *_: self.keep())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre (la mémoire continue de se remplir).")
        close.clicked.connect(self.close)
        lay.addLayout(owner._row(self.play_btn, self.keep_btn, None, close))
        self.finished.connect(lambda *_: self.play(False))
        fit_dialog(self, 900, 600)
        self.draw()

    def set_dur(self):
        m_ = int(self.dur.currentData() if self.dur.currentData() is not None else 3)
        self.owner.sdr_cfg["rewind_min"] = m_
        for e in (getattr(self.owner, "sdr_engs", None) or {}).values():
            e.rew.set_minutes(m_)

    def draw(self):
        rb = self.eng.rew
        fr = list(rb.frames)
        now = time.time()
        self.mem.setText(TR("{} Mo en mémoire").format(f"{rb.mem_mb():.0f}"))
        for it in self.marks:
            self.plot.removeItem(it)
        self.marks = []
        if not fr:
            self.img.clear()
            self.at.setText(TR("Désactivé : choisis une durée en haut à gauche.") if not rb.keep else
                            TR("Rien en mémoire : lance le poste SDR (▶ du Récepteur), puis reviens ici."))
            return
        lo = min(float(f[0]) for _t, f, _l in fr)
        hi = max(float(f[-1]) for _t, f, _l in fr)
        cols = 800
        grid = np.linspace(lo, hi, cols)
        arr = np.full((len(fr), cols), np.nan, dtype=np.float32)
        for i, (_t, f, l) in enumerate(fr):
            m = (grid >= f[0]) & (grid <= f[-1])
            arr[i, m] = np.interp(grid[m], f, l.astype(np.float32))
        fl = float(np.nanpercentile(arr, 10)) if np.isfinite(arr).any() else -100.0
        arr = np.nan_to_num(arr, nan=fl)
        self.img_arr, self.t_rows = arr, np.array([t for t, _f, _l in fr])
        age_old = now - fr[0][0]
        self.img.setImage(arr[::-1].T, autoLevels=False, levels=(fl, fl + 50.0))
        self.img.setRect(QtCore.QRectF(lo, 0.0, max(1e-6, hi - lo), max(0.5, age_old)))
        self.plot.getViewBox().invertY(True)                 # 0 s (maintenant) en haut
        self.plot.setXRange(lo, hi, padding=0)
        self.plot.setYRange(0, max(0.5, age_old), padding=0)
        o = self.owner
        for a in list(o.alarms.active.values()) + list(o.alarms.done):
            if a.get("freq") and lo <= float(a["freq"]) <= hi and fr[0][0] <= a["t0"] <= now:
                ti = pg.TextItem(f"⚠ {a['kind']}", color=o.tone_color("bad"), anchor=(0.5, 1.0))
                ti.setPos(float(a["freq"]), now - a["t0"])
                self.plot.addItem(ti)
                self.marks.append(ti)

    def _click(self, ev):
        vb = self.plot.getViewBox()
        p = vb.mapSceneToView(ev.scenePos())
        self.select(time.time() - float(p.y()))

    def select(self, t):
        self.t_sel = float(t)
        self.sel_line.setValue(time.time() - self.t_sel)
        self.sel_line.show()
        tu = self.eng.rew.tune_at(self.t_sel)
        ago = int(max(0, time.time() - self.t_sel))
        self.at.setText(TR("Il y a {} min {:02d} s · A = {}").format(ago // 60, ago % 60, (
            f"{tu[0]:.3f} MHz" + (f" ({tu[1]})" if tu[1] else "")) if tu else "—"))
        if self.play_btn.isChecked():
            self.play(False)
            self.play(True)

    def play(self, on):
        if self.fx is not None:
            try:
                self.fx.stop()
            except Exception:  # noqa: BLE001
                pass
            self.fx = None
        if not on:
            if self.play_btn.isChecked():
                self.play_btn.blockSignals(True)
                self.play_btn.setChecked(False)
                self.play_btn.blockSignals(False)
            return
        if self.t_sel is None:
            self.select((self.eng.rew.span() or (time.time() - 10, time.time()))[0])
        b = self.eng.rew.audio_from(self.t_sel, 60.0)
        if not b:
            self.at.setText(TR("Pas de son gardé à cet instant (poste arrêté, ou trop ancien)."))
            self.play(False)
            return
        import tempfile
        import wave
        try:
            self._tmp = temp_wav_path("rewind", self._tmp)
            with wave.open(self._tmp, "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(LISTEN_RATE)
                w.writeframes(b)
            from PySide6 import QtMultimedia
            dev = self.owner.sound._device(QtMultimedia) if hasattr(self.owner, "sound") else None
            fx = QtMultimedia.QSoundEffect(dev, self) if dev is not None else QtMultimedia.QSoundEffect(self)
            fx.setSource(QtCore.QUrl.fromLocalFile(self._tmp))
            fx.setVolume(0.8)
            fx.play()
            self.fx = fx
        except Exception as ex:  # noqa: BLE001
            self.at.setText(TR("⚠ Son impossible ici : {}").format(ex))
            self.play(False)

    def keep(self):
        import wave
        o = self.owner
        if self.t_sel is None:
            self.at.setText(TR("Choisis d'abord un instant (clic sur le waterfall)."))
            return
        if not o.privacy_ok(self):
            return
        d = Path(o.log_dir) / "enregistrements_audio" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
            base = d / f"rewind_{datetime.fromtimestamp(self.t_sel):%H%M%S}"
            with wave.open(str(base) + ".wav", "wb") as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(LISTEN_RATE)
                w.writeframes(self.eng.rew.audio_from(self.t_sel, 60.0))
            self.plot.grab().save(str(base) + ".png")
        except OSError as ex:
            self.at.setText(TR("⚠ Enregistrement impossible : {}").format(ex))
            return
        tu = self.eng.rew.tune_at(self.t_sel)
        o.log_event(dict(name=(tu[1] if tu else "") or TR("SDR"), freq=tu[0] if tu else 0.0,
                         note=TR("passage gardé : {}").format(str(base) + ".wav")), 0.0, "ENREGISTRÉ (SDR)")
        self.at.setText(TR("✔ Gardé : {}").format(str(base) + ".wav / .png"))


class SdrToolsMixin:
    """Assistant de branchement, calibration, remonter le temps, manuel SDR. (Méthodes de MainWindow, regroupées par thème.)"""

    def open_sdr_setup(self):
        d = getattr(self, "_sdrsetup", None)
        if d is None:
            d = self._sdrsetup = SdrSetupWizard(self)
        d.refresh()
        d.show()
        d.raise_()
        return d

    def open_sdr_calib(self):
        d = getattr(self, "_sdrcalib", None)
        if d is None:
            d = self._sdrcalib = SdrCalibDialog(self)
        d.show()
        d.raise_()
        return d

    def open_rewind(self, eng=None):
        d = getattr(self, "_rewind", None)
        if d is None or (eng is not None and d.eng is not eng):
            d = self._rewind = RewindDialog(self, eng)
        d.draw()
        d.show()
        d.raise_()
        return d

    def open_sdr_manual(self):
        """📖 Manuel SDR : le manuel principal, partie « Le SDR (bêta) » (8.0)."""
        return self.open_manual("sdr-poste")


class ScreenWindow(QtWidgets.QMainWindow):
    """8.0.2 : une fenêtre COMPLÈTE sur un autre écran, qui réunit plusieurs panneaux (rangeables, en onglets). Les
    panneaux y sont prêtés : leurs objets restent ceux de la fenêtre principale (tout le programme continue de leur
    parler). Fermer = tout ramener dans la fenêtre principale."""

    def __init__(self, owner, idx):
        super().__init__(None)
        self.owner, self.idx, self.closing, self.items = owner, idx, False, {}
        self.setWindowTitle(f"{APP_NAME} – " + TR("Écran {}").format(idx + 1))
        self.setWindowIcon(owner.windowIcon())
        self.setDockNestingEnabled(True)
        c = QtWidgets.QWidget()
        c.setMaximumHeight(0)
        self.setCentralWidget(c)
        for cn, ar in ((Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea),
                       (Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)):
            self.setCorner(cn, ar)
        tb = QtWidgets.QToolBar()
        tb.setObjectName("barre_ecran")
        tb.setMovable(False)
        self.addToolBar(tb)
        lab = QtWidgets.QLabel(" 🖥 " + TR("Écran {}").format(idx + 1) + "  ")
        lab.setToolTip(TR("Fenêtre de cet écran : ses panneaux se déplacent par leur barre de titre (côte à côte, en "
                          "onglets). F11 : plein écran."))
        tb.addWidget(lab)
        for txt, tip, fn in (("⛶ Plein écran", "Plein écran sur cet écran (F11 ; Échap pour sortir).", self.toggle_full),
                             ("🖥 Écrans…", "Choisir quel panneau va sur quel écran.", lambda: owner.open_screens()),
                             ("📌 Tout ramener", "Remet tous les panneaux dans la fenêtre principale.",
                              lambda: owner.screens_off())):
            b = QtWidgets.QPushButton(TR(txt))
            b.setToolTip(TR(tip))
            b.clicked.connect(lambda *_, fn=fn: fn())
            tb.addWidget(b)
        QtGui.QShortcut(QtGui.QKeySequence("F11"), self, activated=self.toggle_full)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self, activated=lambda: self.isFullScreen() and self.toggle_full())

    def put(self, name, title, w):
        d = QtWidgets.QDockWidget(title, self)
        d.setObjectName("scr_" + name)
        d.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable)
        d.setWidget(w)
        w.show()
        self.items[name] = d

    def arrange(self):
        """Disposition de départ : spectres en haut, waterfalls dessous, Récepteur + listes (onglets) à droite."""
        B, R = Qt.DockWidgetArea.BottomDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea
        it = self.items
        center = [n for n in ("dock_spectre", "dock_sdr_spec", "dock_wf", "dock_sdr_wf", "dock_alarmes") if n in it]
        tops = [n for n in ("dock_spectre", "dock_sdr_spec") if n in it]
        prev = None
        for n in tops:
            if prev is None:
                self.addDockWidget(B, it[n])
            else:
                self.splitDockWidget(it[prev], it[n], Qt.Orientation.Horizontal)
            prev = n
        for wf, sp in (("dock_wf", "dock_spectre"), ("dock_sdr_wf", "dock_sdr_spec")):
            if wf in it:
                if sp in it:
                    self.splitDockWidget(it[sp], it[wf], Qt.Orientation.Vertical)
                elif prev is None:
                    self.addDockWidget(B, it[wf])
                    prev = wf
                else:
                    self.splitDockWidget(it[prev], it[wf], Qt.Orientation.Horizontal)
                    prev = wf
        if "dock_alarmes" in it:
            below = next((n for n in ("dock_wf", "dock_spectre", "dock_sdr_wf", "dock_sdr_spec") if n in it), None)
            if below:
                self.splitDockWidget(it[below], it["dock_alarmes"], Qt.Orientation.Vertical)
            else:
                self.addDockWidget(B, it["dock_alarmes"])
        side = R if center else B
        tabs = [n for n in ("dock_freq", "dock_journal", "dock_sdr_mics", "dock_sdr_diag") if n in it]
        if "dock_sdr_rx" in it:
            self.addDockWidget(side, it["dock_sdr_rx"])
            if tabs:
                self.splitDockWidget(it["dock_sdr_rx"], it[tabs[0]], Qt.Orientation.Vertical)
        elif tabs:
            self.addDockWidget(side, it[tabs[0]])
        for n in tabs[1:]:
            self.tabifyDockWidget(it[tabs[0]], it[n])
        if tabs:
            it[tabs[0]].raise_()
        labs = [n for n in it if n.startswith("dock_lab")]      # 8.2 : labo SDR, en onglets
        if labs and len(labs) == len(it):                        # écran du labo seul : vrai affichage Labo (grille)
            lab_grid(self, {k: it[n] for k, _t, n in LAB_DOCKS if n in it})
            labs = []
        if labs:
            self.addDockWidget(B, it[labs[0]])
            for n in labs[1:]:
                self.tabifyDockWidget(it[labs[0]], it[n])
            it[labs[0]].raise_()
        for d in it.values():
            d.show()

    def place(self, screen, full=False):
        self.setGeometry(screen.availableGeometry().adjusted(30, 30, -30, -30))
        if full:
            self.showFullScreen()
        else:
            self.showMaximized()
        QtCore.QTimer.singleShot(120, self._sizes)

    def _sizes(self):
        try:
            it, W = self.items, max(self.width(), 800)
            side = [it[n] for n in ("dock_sdr_rx", "dock_freq") if n in it]
            if side and any(n in it for n in ("dock_spectre", "dock_sdr_spec", "dock_wf", "dock_sdr_wf")):
                self.resizeDocks(side[:1], [int(W * 0.32)], Qt.Orientation.Horizontal)
        except Exception:  # noqa: BLE001
            pass

    def toggle_full(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def take(self):
        """Rend les panneaux (nom, widget) et vide la fenêtre."""
        out = []
        for n, d in list(self.items.items()):
            w = d.widget()
            d.setWidget(QtWidgets.QWidget())
            out.append((n, w))
        self.items = {}
        return out

    def state(self):
        return dict(geo=bytes(self.saveGeometry().toBase64()).decode(),
                    state=bytes(self.saveState().toBase64()).decode())

    def closeEvent(self, e):
        if not self.closing:
            QtCore.QTimer.singleShot(0, lambda: self.owner.screens_off())
        super().closeEvent(e)


class ScreensDialog(QtWidgets.QDialog):
    """🖥 Plusieurs écrans : quel panneau sur quel écran (ou caché), préréglages, identifier les écrans."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle(TR("🖥 Plusieurs écrans"))
        lay = QtWidgets.QVBoxLayout(self)
        self.info = QtWidgets.QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        ident = QtWidgets.QPushButton(TR("👋 Identifier les écrans"))
        ident.setToolTip(TR("Affiche un grand numéro sur chaque écran pendant 3 secondes."))
        ident.clicked.connect(lambda *_: owner.identify_screens())
        lay.addLayout(owner._row(ident, None))
        pre = QtWidgets.QGroupBox(TR("Préréglages"))
        pl = FlowLayout(pre)
        self.pre_btns = {}
        for k, t in SCREEN_PRESETS:
            b = QtWidgets.QPushButton(TR(t))
            b.setToolTip(TR("Remplit le tableau ci-dessous ; « Appliquer » pour le mettre en place."))
            b.clicked.connect(lambda *_, k=k: self.preset(k))
            pl.addWidget(b)
            self.pre_btns[k] = b
        lay.addWidget(pre)
        self.tbl = QtWidgets.QTableWidget(len(SCREEN_PANELS), 2)
        self.tbl.setHorizontalHeaderLabels([TR("Panneau"), TR("Va sur")])
        self.tbl.verticalHeader().hide()
        self.tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tbl.setColumnWidth(1, 250)
        self.tbl.setToolTip(TR("Pour chaque panneau : l'écran où il va (« fenêtre principale » = celui de la fenêtre "
                               "avec les menus), ou caché. Les panneaux d'un même autre écran sont réunis dans une "
                               "fenêtre complète, où tu les ranges comme tu veux."))
        self.combos = {}
        for r, (n, _g, t) in enumerate(SCREEN_PANELS):
            it = QtWidgets.QTableWidgetItem(TR(t))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 0, it)
            cb = QtWidgets.QComboBox()
            cb.setToolTip(TR("Écran où va ce panneau, ou « Caché »."))
            self.tbl.setCellWidget(r, 1, cb)
            self.combos[n] = cb
        lay.addWidget(self.tbl, 1)
        self.full = QtWidgets.QCheckBox(TR("Plein écran sur les autres écrans (sans barre des tâches)"))
        self.full.setToolTip(TR("Sinon : fenêtre agrandie (la barre des tâches reste visible). F11 pour basculer."))
        lay.addWidget(self.full)
        ok = QtWidgets.QPushButton(TR("✔ Appliquer"))
        ok.setToolTip(TR("Met les panneaux sur les écrans choisis."))
        ok.clicked.connect(lambda *_: self.apply())
        back = QtWidgets.QPushButton(TR("📌 Tout ramener"))
        back.setToolTip(TR("Remet tous les panneaux dans la fenêtre principale (disposition de base du mode)."))
        back.clicked.connect(lambda *_: (owner.screens_off(), self.fill()))
        close = QtWidgets.QPushButton(TR("Fermer"))
        close.setToolTip(TR("Ferme cette fenêtre (la répartition reste en place)."))
        close.clicked.connect(lambda *_: self.close())
        lay.addLayout(owner._row(ok, back, None, close))
        self.resize(640, 580)
        fit_dialog(self, 640, 580)
        self.fill()

    def fill(self):
        o = self.owner
        scrs, main = o.screen_list()
        lines = [TR("Écran {} : {} · {}×{}").format(k + 1, sc.name(), sc.size().width(), sc.size().height())
                 + (" · " + TR("fenêtre principale ici") if k == main else "") for k, sc in enumerate(scrs)]
        if len(scrs) < 2:
            lines.append(TR("⚠ Un seul écran détecté : branche le 2ᵉ (Windows : Paramètres › Affichage › « Étendre "
                            "ces affichages »), puis rouvre cette fenêtre. Tu peux déjà cacher ou montrer des panneaux."))
        self.info.setText("\n".join(lines))
        for k, b in self.pre_btns.items():
            b.setEnabled(len(scrs) > 1 or k == "all_here")
        plan = o.screens_cfg["plan"] if o.screen_hosts else o.screens_current()
        for n, cb in self.combos.items():
            cb.blockSignals(True)
            cb.clear()
            for k in range(len(scrs)):
                cb.addItem(TR("Écran {}").format(k + 1) + (" · " + TR("fenêtre principale") if k == main else ""), k)
            cb.addItem(TR("Caché"), SCREEN_HIDE)
            v = plan.get(n, SCREEN_HIDE)
            i = cb.findData(v if v < len(scrs) else main)
            cb.setCurrentIndex(max(0, i))
            cb.blockSignals(False)
        self.full.setChecked(bool(o.screens_cfg.get("full")))

    def plan(self):
        return {n: int(cb.currentData()) for n, cb in self.combos.items()}

    def preset(self, key):
        scrs, main = self.owner.screen_list()
        other = next((k for k in range(len(scrs)) if k != main), main)
        pl = screen_preset(key, main, other, sdr=getattr(self.owner, "rf_mode", "tiny") != "tiny"
                           or key in ("tiny_sdr", "sdr_tiny"))
        for n, cb in self.combos.items():
            cb.setCurrentIndex(max(0, cb.findData(pl.get(n, SCREEN_HIDE))))

    def apply(self):
        self.owner.screens_apply(self.plan(), self.full.isChecked())
        self.fill()


class SdrFollowMixin:
    """Micros suivis par le SDR, échelles, sortie audio, vu-mètres. (Méthodes de MainWindow, regroupées par thème.)"""

    def watch_selected(self):
        """Lignes choisies dans « Mes fréquences »."""
        try:
            return [self.watch[r] for r in self._sel_rows() if 0 <= r < len(self.watch)]
        except Exception:  # noqa: BLE001
            return []

    def sdr_follow(self, ws, on, pid=1):
        """8.0.2 : ajoute (on) / retire des micros de ceux que suit le poste SDR pid."""
        ws = [w for w in (ws or []) if w]
        if not ws:
            self.set_status(TR("Choisis d'abord une ou plusieurs lignes dans « Mes fréquences »."))
            return False
        posts = sdr_posts_norm(self.sdr_cfg.get("posts"))
        p = next((x for x in posts if x["id"] == pid), None)
        if p is None:
            return False
        keys = [int(round(w["freq"] * 1000)) for w in ws]
        before = set(p["mics"])
        if not on and not before:                     # « tous » : retirer = garder tous les autres
            before = {int(round(w["freq"] * 1000)) for w in self.sdr_engs[pid].ws()} if pid in self.sdr_engs else set()
        p["mics"] = post_mics_set(sorted(before), keys, on)
        if not on and not p["mics"] and before:
            p["mics"] = []                            # plus aucun : il suit de nouveau tous les micros
        self.sdr_cfg["posts"] = posts
        nm = self.sdr_engs[pid].name() if pid in self.sdr_engs else f"SDR {pid}"
        n = len(set(keys) - before) if on else len(set(keys) & before)
        self.set_status((TR("📡 {} : {} micro(s) ajouté(s), {} suivi(s) en tout.") if on else
                         TR("📡 {} : {} micro(s) retiré(s), {} suivi(s) en tout.")).format(nm, n, len(p["mics"]))
                        if p["mics"] else TR("📡 {} suit de nouveau tous les micros.").format(nm))
        self._sdr_follow_refresh()
        return True

    def sdr_follow_clear(self, pid=1):
        posts = sdr_posts_norm(self.sdr_cfg.get("posts"))
        for x in posts:
            if x["id"] == pid:
                x["mics"] = []
        self.sdr_cfg["posts"] = posts
        self.set_status(TR("📡 Le SDR suit de nouveau tous les micros."))
        self._sdr_follow_refresh()

    def _sdr_follow_refresh(self):
        for d in self.all_sdr_docks():
            pw = self.dock_widget(d)
            if isinstance(pw, SdrMicsPanel):
                pw.ws = []
                pw.refresh()

    def _sdr_follow_menu(self, m, ws):
        """Clic droit dans Mes fréquences : 📡 suivre / ne plus suivre avec le SDR (un sous-menu par SDR s'il y en a
        plusieurs)."""
        keys = {int(round(w["freq"] * 1000)) for w in ws}
        posts = sdr_posts_norm(self.sdr_cfg.get("posts"))
        for p in posts:
            mine = set(p["mics"])
            tgt = m.addMenu(TR("📡 Suivre avec {}").format(p["name"])) if len(posts) > 1 else m
            if not keys <= mine:
                tgt.addAction(TR("📡 Suivre avec le SDR ({} micro(s))  Ctrl+Maj+F").format(len(keys)) if len(posts) == 1
                              else TR("Suivre ({} micro(s))").format(len(keys))).triggered.connect(
                    lambda *_, pid=p["id"]: self.sdr_follow(ws, True, pid))
            if keys & mine:
                tgt.addAction(TR("📡 Ne plus suivre avec le SDR") if len(posts) == 1 else TR("Ne plus suivre")).triggered.connect(
                    lambda *_, pid=p["id"]: self.sdr_follow(ws, False, pid))
            if mine:
                tgt.addAction(TR("📡 Le SDR suit de nouveau tous les micros") if len(posts) == 1
                              else TR("Suivre de nouveau tous les micros")).triggered.connect(
                    lambda *_, pid=p["id"]: self.sdr_follow_clear(pid))

    def sdr_follow_key(self):
        """Ctrl+Maj+F dans Mes fréquences : la sélection rejoint (ou quitte, si elle y est déjà) les micros du SDR 1."""
        ws = self.watch_selected()
        if not ws:
            return
        mine = set(sdr_posts_norm(self.sdr_cfg.get("posts"))[0]["mics"])
        keys = {int(round(w["freq"] * 1000)) for w in ws}
        self.sdr_follow(ws, not (keys <= mine), 1)

    def open_scales(self):
        """📏 Échelles et niveaux : réglages des vu-mètres audio + la fiche (8.1)."""
        d = getattr(self, "_scales", None)
        if d is None:
            d = self._scales = ScalesDialog(self)
        d.show()
        d.raise_()
        d.activateWindow()
        return d

    audio_ref = audio_ref_norm(None)

    def set_sdr_audio(self, key):
        """Sortie de l'écoute SDR choisie (⚙ › Son) : enregistrée, et le son en cours repart tout de suite dessus."""
        self.sdr_cfg["audio_dev"] = str(key or "")
        holders = list((getattr(self, "sdr_engs", None) or {}).values()) + \
            [getattr(self, nm, None) for nm in ("_listen", "_multimon", "_rt")]
        for h in holders:
            a = getattr(h, "audio", None) if h is not None else None
            if isinstance(a, AudioPump):
                q = a.q
                a.close()
                h.audio = AudioPump(q, sdr_audio_device(self))
                h.audio.start()

    def set_meter_style(self, style):
        """8.1 : vu-mètre RF en aiguille (« analog ») ou en barre (« bar ») : tous les vu-mètres du SDR suivent, choix gardé."""
        if style not in dict(METER_STYLES):
            return
        self.sdr_cfg["meter_style"] = style
        for w in QtWidgets.QApplication.allWidgets():
            if isinstance(w, SMeterGauge):
                w.set_style(style)


class ScreensMixin:
    """Plusieurs écrans : quel panneau sur quel écran. (Méthodes de MainWindow, regroupées par thème.)"""

    screen_hosts = {}

    screens_cfg = screens_norm(None)

    def dock_widget(self, d):
        """Le vrai panneau d'un dock, où qu'il soit (fenêtre principale, vraie fenêtre, fenêtre d'un autre écran)."""
        n = d.objectName()
        for host in (getattr(self, "screen_hosts", None) or {}).values():
            if n in host.items:
                return host.items[n].widget()
        pw = (getattr(self, "panel_wins", None) or {}).get(n)
        if pw is not None and pw.body.count():
            return pw.body.itemAt(0).widget()
        return d.widget()

    def screen_list(self):
        scrs = QtGui.QGuiApplication.screens()
        cur = self.screen()
        main = next((k for k, s_ in enumerate(scrs) if s_ == cur), 0)
        return scrs, main

    def screens_docks(self):
        by = {d.objectName(): d for d in list(self.docks) + self.all_sdr_docks()}
        return {n: by[n] for n, _g, _t in SCREEN_PANELS if n in by}

    def screens_current(self):
        """Plan qui décrit ce qu'on voit maintenant (tout dans la fenêtre principale)."""
        _scrs, main = self.screen_list()
        return {n: (main if d.isVisible() or n in self.panel_wins else SCREEN_HIDE) for n, d in self.screens_docks().items()}

    def screens_apply(self, plan, full=False, quiet=False, keep_mode=False):
        """Met chaque panneau sur l'écran choisi (plan {panneau: écran | -1}) ; les autres écrans reçoivent une fenêtre
        complète avec leurs panneaux. Le mode (tinySA / SDR / combiné) suit les panneaux montrés."""
        self.screens_off(relayout=False)
        self.panel_attach_all()
        scrs, main = self.screen_list()
        docks = self.screens_docks()
        plan = screen_plan_fit({n: plan.get(n, SCREEN_HIDE) for n in docks}, len(scrs), main)
        mode = self.rf_mode if keep_mode else screen_rf_mode(plan)    # 8.2 : labo sur 2 écrans -> le mode ne bouge pas
        self.rf_mode = mode
        self.sdr_cfg["rf_mode"] = mode
        groups = {n: g for n, g, _t in SCREEN_PANELS}
        here = {groups[n] for n, v in plan.items() if v == main}
        try:
            if "sdr" in here and "tiny" in here:
                self._sdr_arrange("both", "listen")
            elif "sdr" in here:
                self._sdr_arrange("sdr", "listen")
            else:
                self._layout_base()
                for d in self.all_sdr_docks():
                    d.hide()
        except Exception:  # noqa: BLE001
            pass
        for n, d in docks.items():
            v = plan[n]
            if v == main:
                d.show()
            elif v == SCREEN_HIDE:
                d.hide()
        self.screen_hosts = {}
        for idx in screens_used(plan, main):
            host = ScreenWindow(self, idx)
            for n, _g, _t in SCREEN_PANELS:
                if plan.get(n) != idx or n not in docks:
                    continue
                d = docks[n]
                w = d.widget()
                ph = QtWidgets.QPushButton(TR("🖥 « {} » est sur l'écran {} — cliquer pour tout ramener").format(
                    d.windowTitle(), idx + 1))
                ph.setToolTip(TR("Remet tous les panneaux dans la fenêtre principale."))
                ph.clicked.connect(lambda *_: self.screens_off())
                d.setWidget(ph)
                d.hide()
                host.put(n, d.windowTitle(), w)
            host.arrange()
            host.place(scrs[idx], full)
            self.screen_hosts[idx] = host
        if keep_mode:
            pass                                             # 8.2 : labo — le SDR garde son état
        elif mode != "tiny":
            for e_ in self.sdr_engs.values():
                if not e_.running():
                    e_.start()
        else:
            for e_ in self.sdr_engs.values():
                e_.stop()
        self._update_mode_btn()
        self.screens_cfg = dict(self.screens_cfg, on=bool(self.screen_hosts), plan=plan, full=bool(full))
        for d in self.all_sdr_docks():
            try:
                self.dock_widget(d).apply_level()
            except Exception:  # noqa: BLE001
                pass
        QtCore.QTimer.singleShot(0, self._fit_screen)
        if not quiet:
            self.set_status(TR("🖥 Panneaux répartis sur {} écran(s) : bouge-les par leur barre de titre ; « 📌 Tout ramener » "
                               "pour revenir.").format(1 + len(self.screen_hosts)) if self.screen_hosts
                            else TR("🖥 Tout est dans la fenêtre principale."))
        return plan

    def screens_off(self, relayout=True):
        """Ramène les panneaux des autres écrans dans la fenêtre principale."""
        hosts = getattr(self, "screen_hosts", None) or {}
        if not hosts:
            return False
        docks = self.screens_docks()
        for host in hosts.values():
            for n, w in host.take():
                d = docks.get(n)
                if d is None:
                    w.deleteLater()
                    continue
                old = d.widget()
                d.setWidget(w)
                w.show()
                if old is not None:
                    old.deleteLater()
            host.closing = True
            host.close()
            host.deleteLater()
        self.screen_hosts = {}
        self.screens_cfg["on"] = False
        if relayout:
            self._layout_mode()
            self.set_status(TR("📌 Tous les panneaux sont revenus dans la fenêtre principale."))
        return True

    def screens_state(self):
        st = dict(self.screens_cfg)
        st["on"] = bool(getattr(self, "screen_hosts", None))
        st["hosts"] = {str(k): h.state() for k, h in (getattr(self, "screen_hosts", None) or {}).items()}
        return st

    def screens_restore(self):
        """Au démarrage : les fenêtres des autres écrans rouvertes comme on les a laissées (écran débranché : ses panneaux
        reviennent dans la fenêtre principale)."""
        cfg = self.screens_cfg
        if not cfg.get("on") or not cfg.get("plan"):
            return
        try:
            self.screens_apply(cfg["plan"], cfg.get("full"), quiet=True)
            for k, host in self.screen_hosts.items():
                h = cfg.get("hosts", {}).get(str(k)) or {}
                if h.get("state"):
                    host.restoreState(QtCore.QByteArray.fromBase64(h["state"].encode()))
        except Exception:  # noqa: BLE001
            self.screens_off()

    def identify_screens(self):
        """Un grand numéro sur chaque écran (3 s)."""
        for lb in getattr(self, "_ident_lbls", []):
            lb.close()
        self._ident_lbls = []
        _scrs, main = self.screen_list()
        for k, sc in enumerate(_scrs):
            lb = QtWidgets.QLabel(f"{k + 1}" + ("\n" + TR("fenêtre principale") if k == main else ""))
            lb.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setStyleSheet("background: rgba(10,132,255,0.92); color: white; font-size: 96px; font-weight: bold; "
                             "border-radius: 24px; padding: 20px;")
            g = sc.availableGeometry()
            lb.setGeometry(g.center().x() - 220, g.center().y() - 160, 440, 320)
            lb.show()
            self._ident_lbls.append(lb)
        QtCore.QTimer.singleShot(3000, lambda: [lb.close() for lb in getattr(self, "_ident_lbls", [])])

    def open_screens(self):
        dlg = getattr(self, "_screens_dlg", None)
        if dlg is None:
            dlg = self._screens_dlg = ScreensDialog(self)
        dlg.fill()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg
