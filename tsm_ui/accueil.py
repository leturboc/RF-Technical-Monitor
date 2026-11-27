# Accueil, recherche, fiches problème, mode Show, assistant, TNT, préréglages, tutos, QR.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


def qss_rgba(hexcol, alpha):
    """Couleur + transparence pour une feuille de style Qt. ⚠ Qt lit « #rrggbbaa » comme #AARRGGBB (8.1 : le contour
    des cartes de l'accueil sortait jaune) : toujours passer par rgba()."""
    c = QtGui.QColor(hexcol)
    return f"rgba({c.red()},{c.green()},{c.blue()},{int(round(max(0.0, min(1.0, alpha)) * 255))})"


class HomeBar(QtWidgets.QWidget):
    """🏠 Accueil (7.43, Clément : « l'écran de base est assez imbuvable, penser hyper user friendly pour des gens qui
    ne connaissent ni la HF ni le tinySA ») : 3 grosses cartes ① tinySA ② Mes micros ③ Surveiller, la prochaine étape
    entourée, et une phrase d'état en gros. Mis à jour chaque seconde par MainWindow.update_home."""

    def __init__(self, owner):
        super().__init__()
        self.owner = o = owner
        self.setObjectName("accueil")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(3)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.cards = {}

        def card(key, title):
            fr = QtWidgets.QFrame()
            fr.setObjectName("carte")
            v = QtWidgets.QVBoxLayout(fr)
            v.setContentsMargins(8, 3, 8, 4)
            v.setSpacing(2)
            top = QtWidgets.QHBoxLayout()                # titre et état sur une seule ligne (place en hauteur)
            top.setSpacing(8)
            t = QtWidgets.QLabel(title)
            t.setStyleSheet("font-weight:bold; font-size:14px")
            if key == "port":                            # 8.0 : c'est quoi un tinySA
                t.setToolTip(TR(DEVICE_HELP["tiny"]))
            info = QtWidgets.QLabel("")
            info.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
            top.addWidget(t)
            top.addWidget(info, 1)
            h = QtWidgets.QHBoxLayout()
            h.setSpacing(6)
            v.addLayout(top)
            v.addLayout(h)
            self.cards[key] = (fr, info, h)
            row.addWidget(fr, 1)
            return h

        h = card("port", "① Le tinySA")
        self.port_btn = QtWidgets.QPushButton("🔌 Choisir…")
        self.port_btn.setToolTip("Choisir le tinySA : branché en USB, en réseau (Raspberry Pi), ou le mode démo pour\n"
                                 "essayer sans tinySA.")
        self.port_menu = QtWidgets.QMenu(self.port_btn)
        self.port_menu.aboutToShow.connect(self._fill_ports)
        self.port_btn.setMenu(self.port_menu)
        h.addWidget(self.port_btn)
        self.help_btn = QtWidgets.QPushButton("❓ Que faire ?")
        self.help_btn.setToolTip("Le tinySA a un souci : ce qui se passe et comment le régler, pas à pas.")
        self.help_btn.clicked.connect(lambda *_: o.problem_help())
        self.help_btn.setVisible(False)
        h.addWidget(self.help_btn)
        h.addStretch(1)
        h = card("list", "② Mes micros")
        self.imp_btn = QtWidgets.QPushButton("📥 Importer")
        self.imp_btn.setToolTip("Importer ton plan de fréquences (EazyRF, WWB, WSM, Excel / CSV…).")
        self.imp_btn.clicked.connect(lambda *_: o.import_watch())
        self.add_btn = QtWidgets.QPushButton("＋ Ajouter")
        self.add_btn.setToolTip("Ajouter des micros : tape ou colle « HF1 558.2, HF2 574… ».")
        self.add_btn.clicked.connect(lambda *_: o.add_watch_dialog())
        self.scan_btn = QtWidgets.QPushButton("📡 Depuis le scan")
        self.scan_btn.setToolTip("Ajouter les signaux que le tinySA voit en ce moment (au-dessus d'un seuil).")
        self.scan_btn.clicked.connect(lambda *_: o.open_scan_add())
        for b in (self.imp_btn, self.add_btn, self.scan_btn):
            h.addWidget(b)
        h.addStretch(1)
        h = card("run", "③ Surveiller")
        self.run_btn = QtWidgets.QPushButton("▶ Démarrer")
        self.run_btn.setToolTip("Démarrer / arrêter la surveillance de tes micros.")
        self.run_btn.clicked.connect(lambda *_: o.toggle_run())
        self.ready_btn = QtWidgets.QPushButton("✅ Prêt ?")
        self.ready_btn.setToolTip("Tout vérifier avant le show (son, alertes, fréquences hors bandes…).")
        self.ready_btn.clicked.connect(lambda *_: o.open_ready())
        self.show_btn = QtWidgets.QPushButton("🖥 Mode Show")
        self.show_btn.setToolTip("Plein écran, seulement l'essentiel en très gros (F10).")
        self.show_btn.clicked.connect(lambda *_: o.open_show_mode())
        for b in (self.run_btn, self.ready_btn, self.show_btn):
            h.addWidget(b)
        h.addStretch(1)
        side = QtWidgets.QVBoxLayout()
        self.tour_btn = QtWidgets.QPushButton("🎓 Tuto")
        self.tour_btn.setToolTip("Visites guidées pas à pas, pour débutants.")
        self.tour_btn.clicked.connect(lambda *_: o.start_tour())
        self.hide_btn = QtWidgets.QToolButton()
        self.hide_btn.setText("✕")
        self.hide_btn.setAutoRaise(True)
        self.hide_btn.setToolTip("Masquer l'accueil (☰ Plus › 👁 Affichage › 🏠 Accueil pour le remettre).")
        self.hide_btn.clicked.connect(lambda *_: o.set_home(False))
        side.addWidget(self.hide_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.wiz_btn = QtWidgets.QPushButton("🧭 Assistant")
        self.wiz_btn.setToolTip("L'assistant pas à pas : show, micros, scan, canaux TNT, prêt pour le show.")
        self.wiz_btn.clicked.connect(lambda *_: o.open_wizard())
        self.sim_btn = QtWidgets.QPushButton("🧪 Simuler")
        self.sim_btn.setCheckable(True)
        self.sim_btn.setToolTip("Essayer sans matériel : tinySA et SDR simulés (micros avec du son), surveillance lancée.\n"
                                "Tout est marqué SIMULÉ. Recliquer pour revenir au vrai matériel.")
        self.sim_btn.clicked.connect(lambda *_: o.simulate(self.sim_btn.isChecked()))
        _row = QtWidgets.QHBoxLayout()
        _row.setSpacing(4)
        _row.addWidget(self.sim_btn)
        _row.addWidget(self.wiz_btn)
        _row.addWidget(self.tour_btn)
        side.addLayout(_row)
        side.addStretch(1)
        row.addLayout(side)
        lay.addLayout(row)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        self.status.setToolTip("Ce qui se passe, en une phrase.")
        lay.addWidget(self.status)

    def _fill_ports(self):
        o, m = self.owner, self.port_menu
        m.clear()
        cur = o.port_combo.currentIndex()
        for i in range(o.port_combo.count()):
            a = m.addAction(o.port_combo.itemText(i))
            a.setCheckable(True)
            a.setChecked(i == cur and not o.demo_chk.isChecked())
            a.triggered.connect(lambda *_, i=i: o.switch_source(False, i))
        m.addSeparator()
        m.addAction("↻ Chercher à nouveau les tinySA branchés").triggered.connect(lambda *_: o.refresh_ports())
        a = m.addAction("🎭 Mode démo (essayer sans tinySA)")
        a.setCheckable(True)
        a.setChecked(o.demo_chk.isChecked())
        a.triggered.connect(lambda *_, a=a: o.switch_source(a.isChecked()))

    def refresh(self, info):
        o = self.owner
        try:
            on_ = bool(o.simulating())
            if self.sim_btn.isChecked() != on_:
                self.sim_btn.setChecked(on_)
        except Exception:  # noqa: BLE001
            pass
        th = o.theme
        nxt = home_next(info)
        acc = th.get("ui_accent", "#3b82f6")
        for k, (fr, _i, _h) in self.cards.items():
            fr.setStyleSheet("QFrame#carte{border:%s; border-radius:10px; background:%s}"     # 8.1 : cartes discrètes
                             % (f"2px solid {acc}" if k == nxt else f"1px solid {qss_rgba(th['ui_text'], 0.12)}",
                                th["ui_base"]))
        pi = self.cards["port"][1]
        if info.get("demo"):
            pi.setText("🎭 Mode démo : signaux simulés")
        elif info.get("lost"):
            who = ", ".join(info["lost"])
            pi.setText(f"○ Déconnecté : {who}")
        elif info.get("running"):
            pi.setText(f"● Relié · {info.get('port_txt', '')}")
        elif info.get("port"):
            pi.setText(f"Prêt : {info.get('port_txt', '')}")
        else:
            pi.setText("○ Aucun tinySA trouvé : branche-le en USB et allume-le.")
        prob = info.get("problem")
        self.help_btn.setVisible(bool(prob))
        if prob and not info.get("lost") and not info.get("running"):
            pi.setText(f"⚠ {prob}")
        n = int(info.get("n_watch") or 0)
        self.cards["list"][1].setText(f"{n} fréquence(s) dans ta liste" if n else "Ta liste est vide.")
        run = bool(info.get("running"))
        self.cards["run"][1].setText("● Surveillance en cours" if run else "■ Arrêtée")
        self.run_btn.setText("■ Arrêter" if run else "▶ Démarrer")
        col = th["st_occ"] if run else th["st_free"]
        self.run_btn.setStyleSheet("QPushButton{background:%s;color:%s;font-weight:bold;padding:5px 14px;"
                                   "border-radius:5px;}" % (col, contrast_text(col)))
        tone, txt = home_status(info)
        c = {"ok": th["st_free"], "warn": th["st_weak"], "bad": th["st_occ"], "wait": th.get("st_none")}.get(tone)
        self.status.setText(txt)
        self.status.setStyleSheet("font-size:16px; font-weight:600; padding:4px 10px; border-radius:9px; "
                                  + (soft_style(c, th["ui_bg"], th["ui_text"]) if c else ""))


class FeatureSearchDialog(QtWidgets.QDialog):
    """🔎 Chercher une fonction (Ctrl+K, revue UX) : tape un mot (« secours », « RBW », « relais »…), Entrée lance
    l'outil. Cherche dans les 4 menus du travail et ☰ Plus (nom ET bulle d'aide), sans accents ni majuscules."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("🔎 Chercher une fonction")
        self.resize(560, 420)
        lay = QtWidgets.QVBoxLayout(self)
        self.edit = QtWidgets.QLineEdit()
        self.edit.setPlaceholderText("Ex. : secours, relais, RBW, rapport, mur…")
        self.edit.setToolTip("Tape un ou plusieurs mots ; Entrée ouvre la 1ʳᵉ fonction trouvée.")
        self.listw = QtWidgets.QListWidget()
        self.listw.setToolTip("Double-clic ou Entrée : ouvrir cette fonction.")
        lay.addWidget(self.edit)
        lay.addWidget(self.listw, 1)
        self.items = self._collect()
        self.edit.textChanged.connect(lambda *_: self.refresh())
        self.edit.returnPressed.connect(lambda *_: self.go())
        self.listw.itemActivated.connect(lambda *_: self.go())
        self.refresh()

    def _collect(self):
        o, out = self.owner, []

        def walk(menu, path):
            for a in menu.actions():
                if a.isSeparator() or not a.isVisible() or not a.text().strip():
                    continue
                name = a.text().split("\t")[0].replace("&", "")
                if a.menu() is not None:
                    walk(a.menu(), path + [name])
                else:
                    out.append((" › ".join(path + [name]), a.toolTip() if a.toolTip() != a.text() else "", a))
        for k, mn in getattr(o, "step_menus", {}).items():
            walk(mn, [o.step_btns[k].text()])
        walk(o.more_menu, ["☰ Plus"])
        return out

    def refresh(self):
        self.listw.clear()
        for i in feature_match([(n, t) for n, t, _a in self.items], self.edit.text()):
            it = QtWidgets.QListWidgetItem(self.items[i][0])
            it.setToolTip(self.items[i][1])
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.listw.addItem(it)
        if self.listw.count():
            self.listw.setCurrentRow(0)

    def go(self):
        it = self.listw.currentItem()
        if it is None:
            return
        act = self.items[it.data(Qt.ItemDataRole.UserRole)][2]
        self.accept()
        QtCore.QTimer.singleShot(0, act.trigger)


class ProblemDialog(QtWidgets.QDialog):
    """Fiche « problème » (7.46) : un titre clair, ce qui se passe, quoi faire 1-2-3, et des boutons pour le faire
    (Réessayer, Mode démo, Diagnostic). Le message technique d'origine reste lisible en petit, en bas."""

    def __init__(self, owner, card):
        super().__init__(owner)
        self.owner, self.card = owner, card
        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(480)
        lay = QtWidgets.QVBoxLayout(self)
        t = QtWidgets.QLabel("⚠ " + card["title"])
        t.setStyleSheet("font-size:17px; font-weight:bold")
        t.setWordWrap(True)
        lay.addWidget(t)
        what = QtWidgets.QLabel(card["what"])
        what.setWordWrap(True)
        lay.addWidget(what)
        if card.get("impact"):
            lay.addWidget(QtWidgets.QLabel("<b>Conséquence :</b>"))
            imp = QtWidgets.QLabel(card["impact"])
            imp.setWordWrap(True)
            imp.setStyleSheet("color: #f59e0b; font-weight: bold")
            lay.addWidget(imp)
        lay.addWidget(QtWidgets.QLabel("<b>Quoi faire :</b>"))
        for i, st in enumerate(card["steps"], 1):
            h_ = QtWidgets.QHBoxLayout()
            h_.setContentsMargins(12, 0, 0, 0)
            n_ = QtWidgets.QLabel(f"{i}.")              # numéro à part : la phrase reste traduisible telle quelle
            n_.setAlignment(Qt.AlignmentFlag.AlignTop)
            lb = QtWidgets.QLabel(st)
            lb.setWordWrap(True)
            h_.addWidget(n_)
            h_.addWidget(lb, 1)
            lay.addLayout(h_)
        if card.get("detail"):
            d = QtWidgets.QLabel(f"Détail technique : {card['detail']}")
            d.setWordWrap(True)
            d.setStyleSheet("color: gray; font-size: 11px")
            d.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(d)
        row = QtWidgets.QHBoxLayout()
        self.btns = {}
        acts = [] if card["key"] == "lost" else [("retry", "↻ Réessayer", self._retry),
                                                  ("demo", "🎭 Essayer en mode démo", self._demo)]
        acts += [("diag", "🩺 Diagnostic", self._diag), ("close", "Fermer", self.reject)]
        for k, txt, fn in acts:
            b = QtWidgets.QPushButton(txt)
            b.setToolTip({"retry": "Relancer la mesure avec le tinySA.",
                          "demo": "Lancer l'appli avec des signaux simulés, sans tinySA.",
                          "diag": "Écrire un fichier qui raconte ce qui s'est passé (à envoyer pour de l'aide).",
                          "close": "Fermer cette fiche."}[k])
            b.clicked.connect(lambda *_, f=fn: f())
            row.addWidget(b)
            self.btns[k] = b
        row.addStretch(1)
        lay.addLayout(row)
        (self.btns.get("retry") or self.btns["close"]).setDefault(True)

    def _retry(self):
        self.accept()
        o = self.owner
        if not o.is_running():
            QtCore.QTimer.singleShot(0, lambda: o.toggle_run())

    def _demo(self):
        self.accept()
        o = self.owner
        o.demo_chk.setChecked(True)
        if not o.is_running():
            QtCore.QTimer.singleShot(0, lambda: o.toggle_run())

    def _diag(self):
        self.owner.open_diag()


def free_plot_menus(widget):
    """Les graphiques pyqtgraph créent des menus « clic droit » SANS parent (ViewBox.menu, PlotItem.ctrlMenu) : ils
    survivent à la fenêtre détruite (fuite vue au test du singe 7.41). À appeler avant de détruire la fenêtre."""
    n = 0
    for gv in widget.findChildren(pg.GraphicsView):
        sc = gv.scene()
        for it in (sc.items() if sc is not None else []):
            for attr in ("menu", "ctrlMenu"):
                mn = getattr(it, attr, None)
                if isinstance(mn, QtWidgets.QMenu):
                    try:
                        mn.deleteLater()
                        setattr(it, attr, None)
                        n += 1
                    except RuntimeError:
                        pass
    return n


def _hesc(x):
    import html
    return html.escape(str(x))


class ShowModeWindow(QtWidgets.QWidget):
    """🖥 Mode Show : plein écran, l'essentiel en très gros. Alarmes en haut (sinon « Tout va bien »), une tuile par
    fréquence (rouge / orange / vert…), et seulement les boutons utiles pendant le show."""

    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)      # fermée = détruite (sinon elle reste en mémoire)
        self.owner = o = owner
        self.setWindowTitle(f"{APP_NAME} — Mode Show")
        self.setStyleSheet(f"background:{o.theme['ui_bg']}; color:{o.theme['ui_text']}")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        bar = QtWidgets.QHBoxLayout()
        big = "font-size:20px; padding:6px 14px"
        self.run_lbl = QtWidgets.QLabel("")
        self.run_lbl.setStyleSheet("font-size:22px; font-weight:bold")
        self.run_btn = QtWidgets.QPushButton("")
        self.run_btn.setStyleSheet(big)
        self.run_btn.setToolTip("Démarrer / arrêter la surveillance.")
        self.run_btn.clicked.connect(lambda *_: (o.toggle_run(), self.refresh()))
        self.ack_btn = QtWidgets.QPushButton("✔ Tout acquitter")
        self.ack_btn.setStyleSheet(big)
        self.ack_btn.setToolTip("Coupe le son de toutes les alarmes en cours (elles restent affichées). Touche Espace.")
        self.ack_btn.clicked.connect(lambda *_: (o.ack_all_alarms(), self.refresh()))
        self.snz_btn = QtWidgets.QToolButton()
        self.snz_btn.setText("🔕 Silence")
        self.snz_btn.setStyleSheet(big)
        self.snz_btn.setToolTip("Couper le son des alarmes pendant quelques minutes.")
        self.snz_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        sm = QtWidgets.QMenu(self.snz_btn)
        for mn in (5, 15, 30, 60):
            sm.addAction(f"🔕 {mn} min").triggered.connect(lambda *_, s_=mn * 60: (o.snooze(s_), self.refresh()))
        sm.addAction("🔔 Remettre le son").triggered.connect(lambda *_: (o.snooze(0), self.refresh()))
        self.snz_btn.setMenu(sm)
        self.state_btn = QtWidgets.QToolButton()
        self.state_btn.setStyleSheet(big)
        self.state_btn.setToolTip("📸 État actif : quelles fréquences sont surveillées en ce moment.")
        self.state_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.state_menu = QtWidgets.QMenu(self.state_btn)
        self.state_menu.aboutToShow.connect(self._fill_states)
        self.state_btn.setMenu(self.state_menu)
        self.ready_btn = QtWidgets.QPushButton("✅ Prêt ?")
        self.ready_btn.setStyleSheet(big)
        self.ready_btn.setToolTip("Vérifie tout ce qui peut faire rater une alarme.")
        self.ready_btn.clicked.connect(lambda *_: o.open_ready())
        self.scr_btn = QtWidgets.QPushButton("🖥")
        self.scr_btn.setStyleSheet(big)
        self.scr_btn.setToolTip("Passer sur l'écran suivant.")
        self.scr_btn.clicked.connect(lambda *_: self.next_screen())
        self.scr_btn.setVisible(len(QtGui.QGuiApplication.screens()) > 1)
        self.clock = QtWidgets.QLabel("")
        self.clock.setStyleSheet("font-size:22px; font-weight:bold")
        self.quit_btn = QtWidgets.QPushButton("✖ Quitter")
        self.quit_btn.setStyleSheet(big)
        self.quit_btn.setToolTip("Revenir à l'écran normal (Échap). La surveillance continue.")
        self.quit_btn.clicked.connect(self.close)
        bar.addWidget(self.run_lbl)
        bar.addWidget(self.run_btn)
        bar.addStretch(1)
        for w_ in (self.ack_btn, self.snz_btn, self.state_btn, self.ready_btn, self.scr_btn):
            bar.addWidget(w_)
        bar.addStretch(1)
        bar.addWidget(self.clock)
        bar.addWidget(self.quit_btn)
        lay.addLayout(bar)
        self.banner = QtWidgets.QLabel("")
        self.banner.setWordWrap(True)
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.banner)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.inner = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.inner)
        self.grid.setSpacing(8)
        self.scroll.setWidget(self.inner)
        lay.addWidget(self.scroll, 1)
        self.tiles, self._sig, self._cols = [], None, 0
        for k, fn in ((Qt.Key.Key_Escape, self.close), (Qt.Key.Key_Space, lambda: (o.ack_all_alarms(), self.refresh())),
                      (Qt.Key.Key_F10, self.close), (Qt.Key.Key_F11, self.toggle_full)):
            QtGui.QShortcut(QtGui.QKeySequence(k), self, activated=fn)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def _fill_states(self):
        o = self.owner
        m = self.state_menu
        m.clear()
        a = m.addAction("Tout actif (aucun état)")
        a.setCheckable(True)
        a.setChecked(not o.state_cur)
        a.triggered.connect(lambda *_: (o.apply_state(""), self.refresh()))
        for st in o.states:
            a = m.addAction(f"📸 {st['name']}")
            a.setCheckable(True)
            a.setChecked(st["name"] == o.state_cur)
            a.triggered.connect(lambda *_, n=st["name"]: (o.apply_state(n), self.refresh()))

    def toggle_full(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def next_screen(self):
        scr = QtGui.QGuiApplication.screens()
        cur = self.screen()
        i = (scr.index(cur) + 1) % len(scr) if cur in scr else 0
        full = self.isFullScreen()
        self.showNormal()
        self.setGeometry(scr[i].availableGeometry())
        if full:
            self.showFullScreen()

    def alarm_line(self, a):
        o = self.owner
        f = a.get("freq") or 0
        parts = [a["kind"], a.get("name") or ""]
        if f and f > 0:
            parts.append(f"{f:.3f} MHz")
        if a.get("level") is not None:
            parts.append(o.lvl(a["level"], True))
        return " · ".join(p for p in parts if p)

    def refresh(self):
        o = self.owner
        th = o.theme
        run = o.is_running()
        self.run_lbl.setText("● SURVEILLANCE" if run else "■ ARRÊTÉE")
        self.run_lbl.setStyleSheet(f"font-size:22px; font-weight:bold; color:{th['st_free'] if run else th['st_occ']}")
        self.run_btn.setText("■ Arrêter" if run else "▶ Démarrer")
        self.clock.setText(time.strftime("%H:%M:%S"))
        left = snooze_left(o.snooze_until, time.time()) if o.snooze_until else 0
        self.snz_btn.setText(f"🔕 {int(left // 60) + 1} min" if left else "🔕 Silence")
        self.state_btn.setText(f"📸 {o.state_cur}" if o.state_cur else "📸 Tout actif")
        self.state_btn.setVisible(bool(o.states))
        cur = [a for a in o.alarms.listing() if a.get("t_end") is None]
        # état de la surveillance (audit 7.52, fail-safe) : arrêtée ou indéterminée n'est JAMAIS « tout va bien »
        if not run:
            hl = dict(tone="bad", text=STOPPED_HEALTH)
        else:
            try:
                hl = o.health().get("data") or dict(tone="bad", text=UNKNOWN_HEALTH)
            except Exception:  # noqa: BLE001
                hl = dict(tone="bad", text=UNKNOWN_HEALTH)
        if cur:                                  # les alarmes ET un éventuel problème de surveillance, ensemble
            rows = "".join(
                f"<div style='font-size:30px; font-weight:bold; margin:4px'>{'🔔' if not a['acked'] else '🔕'} "
                f"{_hesc(self.alarm_line(a))}</div>" for a in cur[:6])
            more = f"<div style='font-size:18px'>+ {len(cur) - 6} autre(s)</div>" if len(cur) > 6 else ""
            extra = (f"<div style='font-size:20px; margin-top:6px'>{_hesc(hl['text'])}</div>"
                     if hl["tone"] != "ok" else "")
            # 7.56 : quoi faire pour l'alarme la plus récente non acquittée (sinon la première)
            a0 = next((a for a in cur if not a["acked"]), cur[0])
            adv = ALARM_HELP.get(a0["kind"], ("", ""))[1]
            hint = (f"<div style='font-size:18px; margin-top:6px'>→ {_hesc(TR(adv))}</div>" if adv else "")
            self.banner.setText(rows + more + hint + extra)
            self.banner.setStyleSheet(f"background:{th['st_occ']}; color:white; border-radius:10px; padding:10px")
        elif hl["tone"] != "ok":                 # pas d'alarme MAIS arrêtée / mesures absentes / périmées / partielles
            self.banner.setText(f"<div style='font-size:24px; font-weight:bold'>{_hesc(hl['text'])}</div>")
            bg = th["st_occ"] if hl["tone"] == "bad" else th["st_weak"]
            self.banner.setStyleSheet(soft_style(bg, th["ui_bg"], th["ui_text"]) + "; padding:10px")
        else:
            self.banner.setText("<div style='font-size:30px; font-weight:600'>✔ Tout va bien</div>")
            self.banner.setStyleSheet(soft_style(th["st_free"], th["ui_bg"], th["ui_text"]) + "; padding:10px")
        ws = [w for w in o.scope_ws() if not w.get("off")]
        sig = tuple((w["name"], round(w["freq"], 4)) for w in ws)
        cols = max(1, self.scroll.viewport().width() // 260)
        if sig != self._sig or cols != self._cols:
            self._sig, self._cols = sig, cols
            for t in self.tiles:
                t.deleteLater()
            self.tiles = []
            for i in range(len(ws)):
                t = QtWidgets.QLabel()
                t.setTextFormat(Qt.TextFormat.RichText)
                t.setAlignment(Qt.AlignmentFlag.AlignCenter)
                t.setMinimumHeight(96)
                t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                t.customContextMenuRequested.connect(lambda pos, i_=i, t_=t: self.tile_menu(i_, t_, pos))
                t.setToolTip("Clic droit : 💤 éteint (je sais) / 🔔 rallumer.")
                self.grid.addWidget(t, i // cols, i % cols)
                self.tiles.append(t)
        for t, w in zip(self.tiles, ws):
            txt, tone, col = o.sig_view(w)
            lv = o.lvl(w["level"], True) if w.get("level") is not None else ""
            if lv and w.get("margin") is not None and o.is_keep_on(w["status"]):
                lv += f" · {w['margin']:+.0f} dB"              # marge au-dessus du bruit
            th_ = o.theme
            if tone == "bad":                    # problème : tuile pleine, elle doit se voir de loin
                card = f"background:{col}; color:{contrast_text(col)}; border-radius:12px; padding:6px"
                stc = contrast_text(col)
            else:                                # 7.54 (look « pro ») : carte sombre, liseré et état en couleur
                card = (f"background:{blend(col, th_['ui_button'], 0.14)}; color:{th_['ui_text']}; "
                        f"border:1.5px solid {blend(col, th_['ui_bg'], 0.60)}; border-radius:14px; padding:6px")
                stc = blend(col, th_["ui_text"], 0.80)
            t.setText(f"<div style='font-size:22px; font-weight:600'>{_hesc(w['name'] or '')}</div>"
                      f"<div style='font-size:17px; opacity:.8'>{w['freq']:.3f} MHz</div>"
                      f"<div style='font-size:16px; font-weight:600; color:{stc}'>{_hesc(txt)}"
                      f"<span style='font-weight:400'>{(' · ' + lv) if lv else ''}</span></div>")
            t.setStyleSheet(card)

    def tile_menu(self, i, tile, pos):
        ws = [w for w in self.owner.scope_ws() if not w.get("off")]
        if i >= len(ws):
            return
        w = ws[i]
        m = QtWidgets.QMenu(self)
        a_rep = m.addAction("🆘 Remplacer ce micro…")
        a = m.addAction("🔔 Rallumer (surveiller à nouveau)" if w.get("muted") else "💤 Éteint (je sais) : pas d'alarme ABSENT")
        xa = self.owner.add_freq_actions(m, w["freq"], w)
        act = m.exec(tile.mapToGlobal(pos))
        if self.owner.run_freq_action(xa, act, w["freq"], w):
            return
        if act is a:
            self.owner.set_muted([w], not w.get("muted"))
            self.refresh()
        elif act is a_rep:
            d = self.owner.open_replace(w)
            if d is not None:                      # au-dessus du plein écran
                d.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                d.show()
                d.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QtCore.QTimer.singleShot(0, self.refresh)

    def closeEvent(self, e):
        self.timer.stop()
        if getattr(self.owner, "_show_mode", None) is self:
            self.owner._show_mode = None
        super().closeEvent(e)


def anfr_read_files(paths):
    """Fichiers ANFR choisis par l'utilisateur (les .zip de data.gouv.fr ou les SUP_*.txt dézippés) -> base réduite."""
    import zipfile
    want = ("SUP_EMETTEUR", "SUP_SUPPORT", "SUP_STATION", "SUP_EXPLOITANT")
    found, zips = {}, []
    for p_ in paths:
        p_ = Path(p_)
        if p_.suffix.lower() == ".zip":
            z = zipfile.ZipFile(p_)
            zips.append(z)
            for n in z.namelist():
                stem = Path(n).stem.upper()
                if stem in want and stem not in found:
                    found[stem] = (z, n)
        elif p_.stem.upper() in want:
            found[p_.stem.upper()] = (None, p_)
    if "SUP_EMETTEUR" not in found or "SUP_SUPPORT" not in found:
        for z in zips:
            z.close()
        raise ValueError("Il faut au moins les tables SUP_EMETTEUR et SUP_SUPPORT (fichier « Tables supports "
                         "antennes émetteurs bandes » de l'ANFR).")
    opened = []

    def lines(k):
        if k not in found:
            return []
        z, n = found[k]
        f = z.open(n) if z is not None else open(n, "rb")
        opened.append(f)
        return f
    try:
        return anfr_tnt_sites(lines("SUP_EMETTEUR"), lines("SUP_SUPPORT"), lines("SUP_STATION"),
                              lines("SUP_EXPLOITANT"))
    finally:
        for f in opened:
            f.close()
        for z in zips:
            z.close()


def anfr_download(job):
    """Fil de travail : télécharge la base ANFR (data.gouv.fr), la réduit aux sites TNT. job = dict partagé (pct, msg,
    done, err, db, date). Aucun objet Qt ici."""
    tmpd = Path(tempfile.mkdtemp(prefix="tsm_anfr_"))
    hdr = {"User-Agent": "RF-Technical-Monitor"}
    try:
        job["msg"] = "Recherche de la dernière version de la base ANFR…"
        with urllib.request.urlopen(urllib.request.Request(ANFR_DATASET, headers=hdr), timeout=30) as r:
            api = json.loads(r.read().decode("utf-8"))
        data_url, ref_url, date = anfr_pick(api)
        if not data_url:
            raise RuntimeError("fichier des émetteurs introuvable sur data.gouv.fr")
        paths = []
        for i, u in enumerate([data_url] + ([ref_url] if ref_url else [])):
            dst = tmpd / f"anfr_{i}.zip"
            with urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=60) as r, open(dst, "wb") as f:
                tot = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    if job.get("cancel"):
                        raise RuntimeError("annulé")
                    b = r.read(1 << 18)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    if i == 0:
                        job["pct"] = int(90 * got / tot) if tot else 0
                        job["msg"] = f"Téléchargement : {got / 1e6:.0f} / {tot / 1e6:.0f} Mo" if tot else \
                            f"Téléchargement : {got / 1e6:.0f} Mo"
            paths.append(dst)
        job["msg"] = "Lecture des émetteurs TNT…"
        job["db"] = anfr_read_files(paths)
        job["date"] = date
        job["pct"] = 100
    except Exception as e:  # noqa: BLE001
        job["err"] = str(e)
    finally:
        import shutil
        shutil.rmtree(tmpd, ignore_errors=True)
        job["done"] = True


class HintBar(QtWidgets.QFrame):
    """7.59 : bandeau discret au-dessus du spectre : une proposition au bon moment (TNT trouvée, liste vide, bande
    recalée…) avec 1-2 boutons et ✕. Caché quand il n'y a rien à proposer."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.key = None
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(8, 3, 4, 3)
        self.lbl = QtWidgets.QLabel()
        self.lbl.setWordWrap(True)
        h.addWidget(self.lbl, 1)
        self.btns = []
        for _i in range(2):
            b = QtWidgets.QPushButton()
            b.setVisible(False)
            b.setToolTip("Le faire maintenant.")
            h.addWidget(b)
            self.btns.append(b)
        x = QtWidgets.QToolButton()
        x.setText("✕")
        x.setAutoRaise(True)
        x.setToolTip("Ne plus proposer (pour ce show).")
        x.clicked.connect(lambda *_: self.dismiss())
        h.addWidget(x)
        self.setVisible(False)

    def show_hint(self, key, text, actions):
        self.key = key
        self.lbl.setText(text)
        t = self.owner.theme
        self.setStyleSheet("HintBar { " + soft_style(t.get("ui_accent", "#0a84ff"), t.get("ui_bg", "#1c1c1e"),
                                                    t.get("ui_text", "#f2f2f7")) + " }")
        for b, act in zip(self.btns, list(actions) + [None, None]):
            try:
                b.clicked.disconnect()
            except (RuntimeError, TypeError):
                pass
            b.setVisible(act is not None)
            if act is not None:
                lab, fn = act
                b.setText(lab)
                b.clicked.connect(lambda *_, f=fn: self._do(f))
        self.setVisible(True)

    def _do(self, fn):
        f = fn if callable(fn) else getattr(self.owner, fn, None)
        self.dismiss()
        if f is not None:
            f()

    def dismiss(self):
        if self.key:
            self.owner._hints_done.add(self.key)
        self.key = None
        self.setVisible(False)


class SpecLegend(QtWidgets.QFrame):
    """7.59 : légende cliquable posée en haut à gauche du spectre : Direct · Pics gardés · Seuil · TNT · Mes micros.
    Un clic = ce que c'est + quoi faire. Ne prend aucune place dans la mise en page (enfant du graphique)."""

    def __init__(self, owner):
        super().__init__(owner.spec)
        self.owner = owner
        self.sig = None
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(2)
        self.chips = {}
        for key, name, _ck, _expl in LEGEND_ITEMS:
            b = QtWidgets.QToolButton()
            b.setText(name)
            b.setAutoRaise(True)
            b.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            m = QtWidgets.QMenu(b)
            m.aboutToShow.connect(lambda k=key, mm=m: self._fill(k, mm))
            b.setMenu(m)
            b.setToolTip("Clique : ce que c'est et quoi faire.")
            h.addWidget(b)
            self.chips[key] = b
        owner.spec.installEventFilter(self)
        self.refresh()

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Type.Resize:
            self._place()
        return False

    def _place(self):
        try:
            x0 = int(self.owner.spec.getPlotItem().getAxis("left").width()) + 10
        except Exception:  # noqa: BLE001
            x0 = 70
        self.adjustSize()
        self.move(x0, 6)
        self.raise_()

    def _fill(self, key, m):
        o = self.owner
        m.clear()
        expl = next(x for k, _n, _c, x in LEGEND_ITEMS if k == key)
        if key == "thr" and o.thr_auto:
            expl = AUTO_THR_HELP[0][1]
        lbl = QtWidgets.QLabel(TR(expl))
        lbl.setWordWrap(True)
        lbl.setMaximumWidth(360)
        lbl.setContentsMargins(10, 6, 10, 6)
        wa = QtWidgets.QWidgetAction(m)
        wa.setDefaultWidget(lbl)
        m.addAction(wa)
        m.addSeparator()
        if key == "curve":
            m.addAction("❓ Toutes les courbes du spectre…").triggered.connect(lambda *_: o.open_spectrum_legend())
        elif key == "hold":
            m.addAction("Effacer les pics").triggered.connect(lambda *_: o.reset_max())
            m.addAction("Masquer les pics gardés").triggered.connect(lambda *_: o.hold_chk.setChecked(False))
        elif key == "thr":
            m.addAction("❓ Comment marche le seuil auto").triggered.connect(lambda *_: o.show_auto_thr_help())
            m.addAction("⚙ Réglages des seuils…").triggered.connect(lambda *_: o.open_settings("detect"))
        elif key == "tnt":
            m.addAction("📺 Canaux TNT du lieu…").triggered.connect(lambda *_: o.open_tnt())
            m.addAction("Ne plus griser").triggered.connect(lambda *_: o.tnt_mark(None))
        elif key == "mk":
            m.addAction("📍 Choisir les repères…").triggered.connect(lambda *_: o.mk_menu.exec(QtGui.QCursor.pos()))

    def refresh(self):
        """Chaque seconde : pastilles visibles selon ce qui est à l'écran, couleurs du thème."""
        o = self.owner
        th = o.theme
        vis = {"curve": True, "hold": o.hold_chk.isChecked(), "thr": True, "tnt": bool(o._tnt_items),
               "mk": bool(o.watch)}
        sig = (tuple(sorted(vis.items())), bool(o.thr_auto), th.get("curve"), th.get("plot_bg"))
        if sig == self.sig:
            return
        self.sig = sig
        for key, name, ck, _x in LEGEND_ITEMS:
            b = self.chips[key]
            b.setVisible(vis[key])
            nm = "Seuil auto" if (key == "thr" and o.thr_auto) else name
            b.setText(("╍ " if key == "thr" and o.thr_auto else "━ ") + TR(nm))
            b.setStyleSheet("QToolButton { color: %s; font-size: 11px; padding: 1px 4px; border: none; } "
                            "QToolButton::menu-indicator { image: none; width: 0; }" % th.get(ck, "#8e8e93"))
        bg = QtGui.QColor(th.get("plot_bg", "#161618"))
        self.setStyleSheet("SpecLegend { background: rgba(%d,%d,%d,200); border-radius: 6px; }"
                           % (bg.red(), bg.green(), bg.blue()))
        self._place()


class ShowWizard(QtWidgets.QDialog):
    """7.59 🧭 Assistant « nouveau show » : les 5 étapes dans l'ordre (show, micros, scan, canaux TNT, prêt), chacune
    avec pourquoi / comment / les boutons qui le font. Non bloquant : on peut travailler dans l'appli à côté."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Assistant nouveau show")
        lay = QtWidgets.QHBoxLayout(self)
        self.lst = QtWidgets.QListWidget()
        self.lst.setMaximumWidth(250)
        self.lst.setToolTip("Les étapes : ✓ = fait. Clique pour y aller.")
        for _k, title, _w, _h in WIZARD_STEPS:
            self.lst.addItem(title)
        lay.addWidget(self.lst)
        right = QtWidgets.QVBoxLayout()
        lay.addLayout(right, 1)
        self.title = QtWidgets.QLabel()
        self.title.setStyleSheet("font-size: 18px; font-weight: 600;")
        right.addWidget(self.title)
        self.why = QtWidgets.QLabel()
        self.why.setWordWrap(True)
        right.addWidget(self.why)
        self.how = QtWidgets.QLabel()
        self.how.setWordWrap(True)
        right.addWidget(self.how)
        self.stack = QtWidgets.QStackedWidget()
        right.addWidget(self.stack)
        self.state = QtWidgets.QLabel()
        self.state.setWordWrap(True)
        right.addWidget(self.state)
        right.addStretch(1)

        def page(*ws):
            w = QtWidgets.QWidget()
            g = QtWidgets.QVBoxLayout(w)
            g.setContentsMargins(0, 6, 0, 6)
            for x in ws:
                g.addWidget(x)
            self.stack.addWidget(w)
            return w

        def btn(txt, fn, tip):
            b = QtWidgets.QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(lambda *_: (fn(), self.refresh()))
            return b
        self.place = QtWidgets.QLineEdit(o.tnt_cfg.get("place", ""))
        self.place.setPlaceholderText("Code postal du lieu (75007) ou GPS (48.8584, 2.2945) — facultatif")
        self.place.setToolTip("Sert à trouver les émetteurs TNT proches (📺 Canaux TNT › Émetteurs proches). "
                              "Gardé avec le show.")
        self.place.editingFinished.connect(
            lambda: setattr(o, "tnt_cfg", tnt_cfg_norm(dict(o.tnt_cfg, place=self.place.text()))))
        page(btn("✏ Nom, dates et pays du show…", lambda: o.edit_show_info("Infos du show"),
                 "Le nom, les dates et le pays du show (le pays règle la bande UHF et les canaux TV)."), self.place)
        page(btn("📥 Importer un plan ou une liste…", o.import_watch, "EazyRF, WWB, WSM, Wisycom, DPA, CSV…"),
             btn("📋 Coller une liste…", o.paste_watch, "Colle une liste copiée d'un tableur ou d'un mail."),
             btn("⌨ Ajouter des micros…", o.add_watch_dialog, "Tape ou colle « HF1 558.2, HF2 574… »."),
             btn("📡 Depuis le scan…", o.open_scan_add, "Ajoute les signaux vus dans le scan (après l'étape 3)."))
        page(btn("▶ Scanner ici", o.step_scan, "Démarre le balayage et repart de pics gardés vides."))
        page(btn("📺 Mesurer et griser", self.measure_tnt, "Repère les canaux TNT dans le scan et les grise."),
             btn("Voir le détail (griser à la main, émetteurs proches)…", o.open_tnt,
                 "La fenêtre 📺 Canaux TNT complète."))
        page(btn("✅ Prêt pour le show ?", o.open_ready, "La vérification complète, avec « Régler » sur chaque point."),
             btn("▶ Démarrer la surveillance", lambda: (None if o.is_running() else o.toggle_run()),
                 "Lance la surveillance si elle ne tourne pas déjà."),
             btn("🖥 Mode Show (plein écran)", o.open_show_mode, "Le grand écran pour la régie."))
        nav = QtWidgets.QHBoxLayout()
        man = QtWidgets.QPushButton("❓ Manuel")
        man.setToolTip("Le chapitre du manuel « Les étapes d'un festival ».")
        man.clicked.connect(lambda *_: o.open_manual("vue"))
        nav.addWidget(man)
        nav.addStretch(1)
        self.prev_btn = QtWidgets.QPushButton("◀ Précédent")
        self.prev_btn.setToolTip("Étape précédente.")
        self.prev_btn.clicked.connect(lambda *_: self.go(self.lst.currentRow() - 1))
        self.next_btn = QtWidgets.QPushButton("Suivant ▶")
        self.next_btn.setToolTip("Étape suivante (tu peux sauter une étape et y revenir).")
        self.next_btn.clicked.connect(lambda *_: self.go(self.lst.currentRow() + 1))
        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.setToolTip("Ferme l'assistant (🧭 Assistant sur l'accueil ou 📋 Préparer pour le rouvrir).")
        close_btn.clicked.connect(lambda *_: self.close())
        for b in (self.prev_btn, self.next_btn, close_btn):
            nav.addWidget(b)
        right.addLayout(nav)
        self.lst.currentRowChanged.connect(self._show)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        fit_dialog(self, 760, 440)
        self.go(0)

    def measure_tnt(self):
        res = self.owner.tnt_measure_now()
        self.owner.tnt_mark(res)
        self.owner.set_status(tnt_summary(res))

    def go(self, i):
        self.lst.setCurrentRow(max(0, min(len(WIZARD_STEPS) - 1, i)))

    def _show(self, i):
        if i < 0:
            return
        _k, title, why, how = WIZARD_STEPS[i]
        self.title.setText(TR(title))
        self.why.setText("<b>" + TR("Pourquoi ?") + "</b> " + TR(why))
        self.how.setText("<b>" + TR("Comment ?") + "</b> " + TR(how))
        self.stack.setCurrentIndex(i)
        self.prev_btn.setEnabled(i > 0)
        self.next_btn.setEnabled(i < len(WIZARD_STEPS) - 1)
        self.refresh()

    def refresh(self):
        st = wizard_status(self.owner.wizard_info())
        for r, (_k, done, _t) in enumerate(st):
            it = self.lst.item(r)
            if it is not None:
                it.setText(("✓ " if done else "   ") + TR(WIZARD_STEPS[r][1]))
        i = self.lst.currentRow()
        if 0 <= i < len(st):
            self.state.setText(("✓ " if st[i][1] else "• ") + TR(st[i][2]))


class TntDialog(QtWidgets.QDialog):
    """📺 Canaux TNT du lieu (7.58) : canaux pris / libres d'après le spectre MESURÉ (sans internet), et émetteurs TNT
    proches d'après la base ouverte de l'ANFR (facultatif : à télécharger une fois ou à importer)."""

    COLS = ("Canal", "MHz", "Niveau", "Au-dessus du bruit", "État")
    SCOLS = ("Distance", "Site", "Code postal", "Multiplex", "Hauteur", "Exploitant")

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.res = None
        self._job = None
        self.setWindowTitle("Canaux TNT et émetteurs proches")
        lay = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        lay.addWidget(self.tabs, 1)
        # --- onglet 1 : canaux mesurés
        w1 = QtWidgets.QWidget()
        l1 = QtWidgets.QVBoxLayout(w1)
        h1 = QtWidgets.QLabel("La TNT occupe des canaux entiers (8 MHz) : un plateau plat bien au-dessus du bruit. "
                              "L'appli les repère dans ton scan, au lieu même du show : pas besoin d'internet. "
                              "Scanne d'abord (pics gardés), puis clique « Mesurer ».")
        h1.setWordWrap(True)
        l1.addWidget(h1)
        r1 = QtWidgets.QHBoxLayout()
        self.spec_combo = QtWidgets.QComboBox()
        owner.fill_coord_combo(self.spec_combo)
        self.spec_combo.setToolTip("Le spectre analysé : les pics gardés actuels, tout le site (scans par lieu) ou une "
                                   "scène.")
        r1.addWidget(self.spec_combo, 1)
        r1.addWidget(QtWidgets.QLabel("Plateau dès"))
        self.margin_spin = QtWidgets.QSpinBox()
        self.margin_spin.setRange(3, 30)
        self.margin_spin.setSuffix(" dB")
        self.margin_spin.setValue(int(owner.tnt_cfg["margin"]))
        self.margin_spin.setToolTip("Un canal est « TNT » si son plateau dépasse le bruit de fond d'au moins cette "
                                    "valeur sur plus de la moitié de sa largeur.")
        r1.addWidget(self.margin_spin)
        self.measure_btn = QtWidgets.QPushButton("Mesurer")
        self.measure_btn.setToolTip("Analyse le spectre choisi canal par canal.")
        self.measure_btn.clicked.connect(lambda *_: self.measure())
        r1.addWidget(self.measure_btn)
        l1.addLayout(r1)
        self.sum_lbl = QtWidgets.QLabel()
        self.sum_lbl.setWordWrap(True)
        l1.addWidget(self.sum_lbl)
        self.tab = QtWidgets.QTableWidget(0, len(self.COLS))
        self.tab.setHorizontalHeaderLabels(list(self.COLS))
        self.tab.verticalHeader().setVisible(False)
        self.tab.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tab.setToolTip("📺 TNT = canal pris par la télé ; autre signal = quelque chose d'étroit (micro, porteuse) ; "
                            "libre = rien au-dessus du bruit ; pas mesuré = hors de tes bandes balayées.\n"
                            "Double-clic ou clic droit : griser / dégriser un canal à la main.")
        self.tab.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.tab.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(lambda pos: self._man_menu(pos))
        self.tab.cellDoubleClicked.connect(lambda r, c: self.cycle(r))
        l1.addWidget(self.tab, 1)
        self.plan_lbl = QtWidgets.QLabel()
        self.plan_lbl.setWordWrap(True)
        self.plan_lbl.setVisible(False)
        l1.addWidget(self.plan_lbl)
        hint = QtWidgets.QLabel("Double-clic sur un canal (ou clic droit, plusieurs à la fois) pour le griser ou le "
                                "dégriser à la main : ton choix passe avant la mesure et reste avec le show.")
        hint.setWordWrap(True)
        l1.addWidget(hint)
        r2 = QtWidgets.QHBoxLayout()
        self.mark_chk = QtWidgets.QCheckBox("Griser les canaux TNT sur le spectre")
        self.mark_chk.setChecked(bool(owner.tnt_cfg.get("mark", True)))
        self.mark_chk.setToolTip("Les canaux pris par la TNT apparaissent en bandes grisées « TNT n » sur le spectre.")
        self.mark_chk.toggled.connect(lambda *_: self.set_mark(self.mark_chk.isChecked()))
        r2.addWidget(self.mark_chk)
        r2.addStretch(1)
        self.reset_btn = QtWidgets.QToolButton()
        self.reset_btn.setText("↺ Nouveau lieu")
        self.reset_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.reset_btn.setToolTip("En tournée ou après un nouveau plan : remettre les canaux TV en libre et les "
                                  "remesurer.")
        rm = QtWidgets.QMenu(self.reset_btn)
        rm.addAction("Tout remettre en automatique (oublier les choix à la main et les canaux du plan)").triggered.connect(
            lambda *_: owner.tnt_reset(False))
        rm.addAction("Tout remettre à zéro et effacer les pics gardés (rescanner ce lieu)").triggered.connect(
            lambda *_: owner.tnt_reset(True))
        self.reset_btn.setMenu(rm)
        r2.addWidget(self.reset_btn)
        self.copy_btn = QtWidgets.QPushButton("Copier")
        self.copy_btn.setToolTip("Copie le tableau (pour un mail, un tableur, le plan de coordination).")
        self.copy_btn.clicked.connect(lambda *_: self.copy())
        r2.addWidget(self.copy_btn)
        l1.addLayout(r2)
        self.tabs.addTab(w1, "Canaux mesurés ici")
        # --- onglet 2 : émetteurs proches (ANFR)
        w2 = QtWidgets.QWidget()
        l2 = QtWidgets.QVBoxLayout(w2)
        h2 = QtWidgets.QLabel("Facultatif. La base ouverte de l'ANFR liste les émetteurs TNT de France avec leur "
                              "position : on en déduit les sites proches du lieu du show (pas leurs canaux : la base ne "
                              "les donne pas). À télécharger une fois (≈ 65 Mo) ou à importer, ensuite tout marche "
                              "sans internet.")
        h2.setWordWrap(True)
        l2.addWidget(h2)
        self.db_lbl = QtWidgets.QLabel()
        self.db_lbl.setWordWrap(True)
        l2.addWidget(self.db_lbl)
        r3 = QtWidgets.QHBoxLayout()
        self.dl_btn = QtWidgets.QPushButton("⬇ Télécharger la base ANFR (≈ 65 Mo)")
        self.dl_btn.setToolTip("Télécharge la dernière base ANFR depuis data.gouv.fr et n'en garde que les sites TNT "
                               "(≈ 0,3 Mo sur le PC).")
        self.dl_btn.clicked.connect(lambda *_: self.download())
        self.imp_btn = QtWidgets.QPushButton("📂 Importer les fichiers ANFR…")
        self.imp_btn.setToolTip("Si tu as déjà les fichiers : le .zip « Tables supports antennes émetteurs bandes » "
                                "(et, en plus, le .zip « Tables de référence » pour le nom des exploitants), ou les "
                                "fichiers SUP_*.txt dézippés.")
        self.imp_btn.clicked.connect(lambda *_: self.import_files())
        r3.addWidget(self.dl_btn)
        r3.addWidget(self.imp_btn)
        r3.addStretch(1)
        l2.addLayout(r3)
        self.prog = QtWidgets.QProgressBar()
        self.prog.setRange(0, 100)
        self.prog.setVisible(False)
        l2.addWidget(self.prog)
        r4 = QtWidgets.QHBoxLayout()
        r4.addWidget(QtWidgets.QLabel("Lieu du show :"))
        self.place_edit = QtWidgets.QLineEdit(owner.tnt_cfg.get("place", ""))
        self.place_edit.setPlaceholderText("code postal (75007) ou GPS (48.8584, 2.2945)")
        self.place_edit.setToolTip("Code postal à 5 chiffres, ou latitude, longitude en degrés décimaux (clic droit sur "
                                   "une carte en ligne pour les copier). Gardé avec le show.")
        self.place_edit.returnPressed.connect(lambda: self.search())
        r4.addWidget(self.place_edit, 1)
        r4.addWidget(QtWidgets.QLabel("Rayon"))
        self.radius_spin = QtWidgets.QSpinBox()
        self.radius_spin.setRange(5, 200)
        self.radius_spin.setSuffix(" km")
        self.radius_spin.setValue(int(owner.tnt_cfg["radius"]))
        self.radius_spin.setToolTip("Les sites TNT à moins de cette distance du lieu.")
        r4.addWidget(self.radius_spin)
        self.search_btn = QtWidgets.QPushButton("Chercher")
        self.search_btn.setToolTip("Liste les sites TNT proches, du plus proche au plus loin.")
        self.search_btn.clicked.connect(lambda *_: self.search())
        r4.addWidget(self.search_btn)
        l2.addLayout(r4)
        self.near_lbl = QtWidgets.QLabel()
        self.near_lbl.setWordWrap(True)
        l2.addWidget(self.near_lbl)
        self.stab = QtWidgets.QTableWidget(0, len(self.SCOLS))
        self.stab.setHorizontalHeaderLabels(list(self.SCOLS))
        self.stab.verticalHeader().setVisible(False)
        self.stab.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stab.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.stab.setToolTip("Multiplex = nombre de programmes TNT émis par ce site (5 à 7 pour un site principal).")
        l2.addWidget(self.stab, 1)
        src = QtWidgets.QLabel("Source : ANFR, « Données sur les installations radioélectriques de plus de 5 watts », "
                               "data.gouv.fr (Licence Ouverte Etalab).")
        src.setWordWrap(True)
        l2.addWidget(src)
        self.tabs.addTab(w2, "Émetteurs proches (ANFR)")
        bb = QtWidgets.QHBoxLayout()
        man_btn = QtWidgets.QPushButton("❓ Manuel")
        man_btn.setToolTip("Le chapitre du manuel sur les canaux TNT et le scan du lieu.")
        man_btn.clicked.connect(lambda *_: owner.open_manual("arrivee"))
        bb.addWidget(man_btn)
        bb.addStretch(1)
        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.setToolTip("Ferme la fenêtre (les canaux grisés restent sur le spectre).")
        close_btn.clicked.connect(lambda *_: self.close())
        bb.addWidget(close_btn)
        lay.addLayout(bb)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._poll)
        fit_dialog(self, 760, 560)
        self.refresh()

    def _save(self):
        self.owner.tnt_cfg = tnt_cfg_norm(dict(self.owner.tnt_cfg, place=self.place_edit.text(),
                                               radius=self.radius_spin.value(), margin=self.margin_spin.value(),
                                               mark=self.mark_chk.isChecked()))

    def refresh(self):
        self.measure()
        self.show_db()
        if self.owner.tnt_cfg.get("place") and self.owner.tnt_db():
            self.search()

    # ----- canaux mesurés
    def measure(self):
        self._save()
        res = self.owner.tnt_measure_now(self.spec_combo.currentData() or "live", self.margin_spin.value())
        self.res = res
        self.sum_lbl.setText(tnt_summary(res))
        txt = {"tv": "📺 TNT", "other": "autre signal", "free": "libre", "none": "pas mesuré"}
        mtxt = {"tv": "📺 TNT (à la main)", "free": "libre (à la main)"}
        plan = self.owner.tnt_cfg.get("plan") or []
        self.plan_lbl.setVisible(bool(plan))
        if plan:
            self.plan_lbl.setText(f"📋 Canaux TV du plan « {self.owner.tnt_cfg.get('plan_src') or '?'} » : "
                                  f"{', '.join(map(str, plan))} (grisés « (plan) » ; mis à jour si tu suis le fichier).")
        col = {"tv": self.owner.theme.get("bp_tv", "#3b82f6"), "other": self.owner.theme.get("st_weak", "#ffc35c"),
               "free": self.owner.theme.get("st_free", "#4fd1c5")}
        rows = res.get("rows") or []
        self.tab.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [str(r["ch"]), f"{r['lo']:g}–{r['hi']:g}",
                    self.owner.lvl(r["level"]) if r["level"] is not None else "—",
                    f"+{r['above']:.0f} dB" if r["above"] is not None else "—",
                    mtxt[r["state"]] if r.get("manual") else
                    "📺 TNT (plan)" if r.get("src") == "plan" else txt[r["state"]]]
            for j, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if j == 4 and r["state"] in col:
                    it.setForeground(QtGui.QColor(col[r["state"]]))
                self.tab.setItem(i, j, it)
        n = self.owner.tnt_mark(res)
        return n

    def _rows_sel(self):
        rows = sorted({i.row() for i in self.tab.selectedIndexes()})
        return [self.res["rows"][i]["ch"] for i in rows if self.res and i < len(self.res["rows"])]

    def set_manual(self, chans, state):
        """Force des canaux : « tv » (griser), « free » (pas de TNT) ou None (automatique, d'après la mesure)."""
        man = dict(self.owner.tnt_cfg.get("manual") or {})
        for ch in chans:
            if state in ("tv", "free"):
                man[str(ch)] = state
            else:
                man.pop(str(ch), None)
        self.owner.tnt_cfg = tnt_cfg_norm(dict(self.owner.tnt_cfg, manual=man))
        sel = self._rows_sel()
        self.measure()
        for i, r in enumerate(self.res["rows"]):
            if r["ch"] in sel:
                self.tab.selectRow(i)

    def cycle(self, row):
        """Double-clic : automatique → TNT → libre → automatique."""
        if not self.res or row >= len(self.res["rows"]):
            return
        ch = self.res["rows"][row]["ch"]
        cur = (self.owner.tnt_cfg.get("manual") or {}).get(str(ch))
        self.set_manual([ch], {None: "tv", "tv": "free", "free": None}[cur])

    def _man_menu(self, pos):
        chans = self._rows_sel()
        if not chans:
            return
        m = QtWidgets.QMenu(self)
        for label, st in (("📺 Griser (TNT, à la main)", "tv"), ("Libre (pas de TNT, à la main)", "free"),
                          ("Automatique (d'après la mesure)", None)):
            m.addAction(label).triggered.connect(lambda *_, st=st: self.set_manual(chans, st))
        m.exec(self.tab.viewport().mapToGlobal(pos))

    def set_mark(self, on):
        self._save()
        self.owner.tnt_mark(self.res if on else None)

    def copy(self):
        lines = ["\t".join(self.COLS)]
        for i in range(self.tab.rowCount()):
            lines.append("\t".join(self.tab.item(i, j).text() if self.tab.item(i, j) else ""
                                   for j in range(self.tab.columnCount())))
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
        self.owner.set_status("📺 Tableau des canaux TNT copié.")

    # ----- base ANFR
    def show_db(self):
        db = self.owner.tnt_db()
        busy = self._job is not None and not self._job.get("done")
        self.dl_btn.setEnabled(not busy)
        self.imp_btn.setEnabled(not busy)
        if busy:
            return
        if not db:
            self.db_lbl.setText("Pas encore de base ANFR sur ce PC : télécharge-la (internet, une fois) ou importe les "
                                "fichiers. Les canaux mesurés marchent sans.")
            self.dl_btn.setText("⬇ Télécharger la base ANFR (≈ 65 Mo)")
        else:
            n_s, n_c, made = len(db.get("sites") or []), len(db.get("cp") or {}), db.get("made") or "?"
            if db.get("date"):
                self.db_lbl.setText(f"Base ANFR du {db['date']} : {n_s} sites TNT, {n_c} codes postaux (sur ce PC "
                                    f"depuis le {made}).")
            else:
                self.db_lbl.setText(f"Base ANFR importée le {made} : {n_s} sites TNT, {n_c} codes postaux.")
            self.dl_btn.setText("⬇ Mettre à jour la base ANFR (≈ 65 Mo)")

    def download(self):
        if self._job is not None and not self._job.get("done"):
            return
        self._job = dict(pct=0, msg="", done=False, err=None, db=None, date="")
        self.prog.setValue(0)
        self.prog.setVisible(True)
        threading.Thread(target=anfr_download, args=(self._job,), daemon=True).start()
        self.timer.start(300)
        self.show_db()

    def _poll(self):
        j = self._job
        if j is None:
            self.timer.stop()
            return
        self.prog.setValue(int(j.get("pct") or 0))
        self.db_lbl.setText(j.get("msg") or "")
        if not j.get("done"):
            return
        self.timer.stop()
        self.prog.setVisible(False)
        if j.get("err") or not j.get("db"):
            self.db_lbl.setText(f"⚠ Téléchargement impossible : {j.get('err') or 'base vide'}. Vérifie la connexion, ou "
                                f"importe les fichiers depuis data.gouv.fr.")
        else:
            self.owner.tnt_db_save(j["db"], j.get("date", ""), "data.gouv.fr")
            self.show_db()
            self.owner.set_status("📺 Base ANFR enregistrée sur ce PC.")
            if self.place_edit.text().strip():
                self.search()
        self.dl_btn.setEnabled(True)
        self.imp_btn.setEnabled(True)

    def import_files(self, paths=None):
        if paths is None:
            paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, "Fichiers ANFR", str(Path.home() / "Downloads"), "Base ANFR (*.zip *.txt)")
        if not paths:
            return False
        try:
            db = anfr_read_files(paths)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Fichiers ANFR illisibles :\n{e}")
            return False
        if not db.get("sites"):
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Aucun émetteur TNT trouvé dans ces fichiers.")
            return False
        self.owner.tnt_db_save(db, "", "import")
        self.show_db()
        if self.place_edit.text().strip():
            self.search()
        return True

    def search(self):
        self._save()
        db = self.owner.tnt_db()
        self.stab.setRowCount(0)
        if not db:
            self.near_lbl.setText("Il faut d'abord la base ANFR (bouton au-dessus).")
            return []
        pl = place_parse(self.place_edit.text(), db.get("cp"))
        if pl is None:
            self.near_lbl.setText("Lieu non reconnu : tape un code postal à 5 chiffres (75007) ou « latitude, "
                                  "longitude » (48.8584, 2.2945).")
            return []
        near = tnt_sites_near(db.get("sites"), pl[0], pl[1], self.radius_spin.value())
        self.near_lbl.setText(tnt_near_text(near))
        self.stab.setRowCount(len(near))
        for i, (d, s_) in enumerate(near):
            vals = [f"{d:.1f} km", s_[4] or "—", s_[5] or "—", str(s_[2]), f"{s_[3]} m" if s_[3] else "—", s_[6] or "—"]
            for j, v in enumerate(vals):
                self.stab.setItem(i, j, QtWidgets.QTableWidgetItem(v))
        return near

    def closeEvent(self, e):
        self._save()
        super().closeEvent(e)


class PresetDialog(QtWidgets.QDialog):
    """⚡ Préréglages rapides (7.56) : une situation type à gauche, ce qui va changer à droite (maintenant → après),
    Appliquer. Rien n'est touché avant le clic."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Préréglages rapides")
        lay = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel("Choisis ta situation : l'appli règle d'un coup les seuils, la mesure, la rémanence et les "
                                "alarmes. Tu vois ce qui change avant d'appliquer, et tout reste modifiable ensuite.")
        head.setWordWrap(True)
        lay.addWidget(head)
        row = QtWidgets.QHBoxLayout()
        self.lst = QtWidgets.QListWidget()
        self.lst.setMaximumWidth(230)
        self.lst.setToolTip("Les situations types, puis tes préréglages perso (⭐). Celui qui correspond à tes "
                            "réglages actuels est marqué ✓.")
        self._fill()
        row.addWidget(self.lst)
        right = QtWidgets.QVBoxLayout()
        self.desc = QtWidgets.QLabel()
        self.desc.setWordWrap(True)
        self.desc.setMinimumHeight(70)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.addWidget(self.desc)
        self.tab = QtWidgets.QTableWidget(0, 3)
        self.tab.setHorizontalHeaderLabels(["Réglage", "Maintenant", "Après"])
        self.tab.verticalHeader().setVisible(False)
        self.tab.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tab.setToolTip("Ce que ce préréglage va changer par rapport à tes réglages actuels.")
        right.addWidget(self.tab, 1)
        self.note = QtWidgets.QLabel()
        self.note.setWordWrap(True)
        right.addWidget(self.note)
        row.addLayout(right, 1)
        lay.addLayout(row, 1)
        bb = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("⭐ Enregistrer mes réglages actuels…")
        self.save_btn.setToolTip("Crée un préréglage perso avec tes réglages actuels (seuils, mesure, rémanence, "
                                 "alarmes).\nIl est gardé dans l'appli, dans le show enregistré et dans ton profil.")
        self.save_btn.clicked.connect(lambda *_: self.save_current())
        self.del_btn = QtWidgets.QPushButton("Supprimer")
        self.del_btn.setToolTip("Supprime ce préréglage perso (les préréglages intégrés restent).")
        self.del_btn.clicked.connect(lambda *_: self.delete())
        bb.addWidget(self.save_btn)
        bb.addWidget(self.del_btn)
        bb.addStretch(1)
        self.apply_btn = QtWidgets.QPushButton("Appliquer")
        self.apply_btn.setToolTip("Règle l'appli selon ce préréglage (tout reste modifiable à la main ensuite).")
        self.apply_btn.clicked.connect(lambda *_: self.apply())
        close_btn = QtWidgets.QPushButton("Fermer")
        close_btn.setToolTip("Ferme sans rien changer de plus.")
        close_btn.clicked.connect(lambda *_: self.close())
        bb.addWidget(self.apply_btn)
        bb.addWidget(close_btn)
        lay.addLayout(bb)
        self.lst.currentRowChanged.connect(lambda *_: self.refresh())
        cur = preset_match(owner.preset_current(), owner.user_presets)
        keys = [p[0] for p in presets_all(owner.user_presets)]
        self.lst.setCurrentRow(keys.index(cur) if cur in keys else 0)
        fit_dialog(self, 780, 480)
        self.refresh()

    def _fill(self, select=None):
        self.lst.blockSignals(True)
        self.lst.clear()
        for key, name, _d, _st, _a in presets_all(self.owner.user_presets):
            it = QtWidgets.QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.lst.addItem(it)
        keys = [p[0] for p in presets_all(self.owner.user_presets)]
        if select in keys:
            self.lst.setCurrentRow(keys.index(select))
        self.lst.blockSignals(False)

    def save_current(self):
        o = self.owner
        name, ok = QtWidgets.QInputDialog.getText(self, "Préréglage perso", "Nom du préréglage (ex. « Concert jazz », "
                                                  "« Théâtre du Rond-Point ») :")
        name = " ".join(str(name or "").split())[:40]
        if not ok or not name:
            return
        if any(p["name"].lower() == name.lower() for p in o.user_presets):
            r = QtWidgets.QMessageBox.question(self, "Préréglage perso", f"« {name} » existe déjà : le remplacer ?")
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        desc, ok = QtWidgets.QInputDialog.getText(self, "Préréglage perso", "Pour quoi ? (une phrase, facultatif) :")
        o.user_presets = user_presets_merge(o.user_presets, [dict(name=name, desc=desc if ok else "",
                                                                   st=o.preset_current())])
        o.set_status(f"⭐ Préréglage perso « {name} » enregistré.")
        self._fill("u:" + name)
        self.refresh()

    def delete(self):
        k = self.key() or ""
        if not k.startswith("u:"):
            return
        o = self.owner
        o.user_presets = [p for p in o.user_presets if "u:" + p["name"] != k]
        o.set_status(f"Préréglage perso « {k[2:]} » supprimé.")
        self._fill()
        self.lst.setCurrentRow(0)
        self.refresh()

    def key(self):
        it = self.lst.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def refresh(self):
        up = self.owner.user_presets
        cur = self.owner.preset_current()
        match = preset_match(cur, up)
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            k = it.data(Qt.ItemDataRole.UserRole)
            p = quick_preset(k, up)
            if p:                                   # noms perso jamais traduits
                it.setText((p[1] if k.startswith("u:") else TR(p[1])) + ("  ✓" if k == match else ""))
        p = quick_preset(self.key(), up)
        self.del_btn.setEnabled(bool(p) and p[0].startswith("u:"))
        if not p:
            return
        perso = p[0].startswith("u:")
        self.desc.setText(f"<b>{_hesc(p[1] if perso else TR(p[1]))}</b><br>"
                          f"{_hesc(p[2] if perso else TR(p[2])) or _hesc(TR('Préréglage perso.'))}")
        ch = preset_changes(cur, p[0], up)
        self.tab.setRowCount(len(ch))
        for r, (lab, a, b) in enumerate(ch):
            for c, txt in enumerate((lab, a, b)):
                self.tab.setItem(r, c, QtWidgets.QTableWidgetItem(TR(txt)))
        self.note.setText("✓ Tes réglages correspondent déjà à ce préréglage." if not ch else
                          f"{len(ch)} réglage(s) vont changer. Les fréquences, scènes et bandes ne bougent pas.")
        self.apply_btn.setEnabled(bool(ch))

    def apply(self):
        k = self.key()
        if not k:
            return
        self.owner.apply_preset(k)
        self.refresh()
        after = quick_preset(k, self.owner.user_presets)[4]
        if after and hasattr(self.owner, after):
            r = QtWidgets.QMessageBox.question(
                self, "Préréglages rapides", "Préréglage appliqué. Ouvrir aussi le mode festival (relance automatique, "
                "PC qui ne s'endort pas, bilan chaque matin) ?")
            if r == QtWidgets.QMessageBox.StandardButton.Yes:
                getattr(self.owner, after)()


class ReadyDialog(QtWidgets.QDialog):
    """✅ Prêt pour le show ? Tout ce qui peut faire rater une alarme, vérifié d'un coup d'œil, avec « Régler »."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Prêt pour le show ?")
        self.setModal(False)
        self.resize(640, 560)
        lay = QtWidgets.QVBoxLayout(self)
        self.head = QtWidgets.QLabel("")
        self.head.setStyleSheet("font-size:18px; font-weight:bold; padding:6px")
        lay.addWidget(self.head)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "Point", "Détail"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("Chaque ligne = une vérification. « Régler » ouvre le bon réglage.")
        lay.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        self.snd_btn = QtWidgets.QPushButton("🔊 Tester le son")
        self.snd_btn.setToolTip("Joue le son d'une alarme critique sur la sortie audio choisie.")
        self.snd_btn.clicked.connect(lambda *_: owner.sound.alarm(2))
        self.ntf_btn = QtWidgets.QPushButton("📨 Alerte test")
        self.ntf_btn.setToolTip("Envoie un message de test sur le téléphone (ntfy / Telegram).")
        self.ntf_btn.clicked.connect(lambda *_: self.notify_test())
        self.again_btn = QtWidgets.QPushButton("↻ Revérifier")
        self.again_btn.setToolTip("Refait toutes les vérifications (elles se refont aussi toutes seules).")
        self.again_btn.clicked.connect(lambda *_: self.refresh())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme cette fenêtre.")
        close.clicked.connect(self.close)
        for b in (self.snd_btn, self.ntf_btn, self.again_btn):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(3000)
        self.checks = []
        self.refresh()

    def notify_test(self):
        o = self.owner
        if o.notify_cfg.get("mode", "off") == "off":
            self.msg.setText("Alertes téléphone désactivées : règle-les d'abord (📣 Alertes).")
            return
        err = o.send_notify("✅ Test de RF Technical Monitor", "Les alertes arrivent bien sur ce téléphone.", 0)
        self.msg.setText(err or "Message de test envoyé : vérifie le téléphone.")

    def refresh(self):
        o = self.owner
        try:
            self.checks = ready_checks(o.ready_info())
        except Exception as e:  # noqa: BLE001
            self.msg.setText(f"Vérification impossible : {e}")
            return
        lvl, txt = ready_summary(self.checks)
        col = {"ok": o.theme.get("st_free", "#3fb950"), "warn": o.theme.get("st_weak", "#d29922"),
               "bad": o.theme.get("st_occ", "#f85149")}
        self.head.setText(txt)
        self.head.setStyleSheet(f"font-size:18px; font-weight:bold; padding:6px; color:{col.get(lvl, '')}")
        t = self.table
        t.setRowCount(len(self.checks))
        for r, c in enumerate(self.checks):
            t.setItem(r, 0, QtWidgets.QTableWidgetItem(READY_ICONS.get(c["level"], "")))
            t.setItem(r, 1, QtWidgets.QTableWidgetItem(c["title"]))
            if c["fix"] and c["level"] != "ok" and hasattr(o, c["fix"]):
                w = QtWidgets.QWidget()
                hl = QtWidgets.QHBoxLayout(w)
                hl.setContentsMargins(4, 0, 4, 0)
                lb = QtWidgets.QLabel(c["text"])
                lb.setWordWrap(True)
                b = QtWidgets.QPushButton("Régler")
                b.setToolTip("Ouvre le réglage qui corrige ce point.")
                b.clicked.connect(lambda *_, f=c["fix"]: self.fix(f))
                hl.addWidget(lb, 1)
                hl.addWidget(b)
                t.setItem(r, 2, QtWidgets.QTableWidgetItem(""))
                t.setCellWidget(r, 2, w)
            else:
                t.removeCellWidget(r, 2)
                t.setItem(r, 2, QtWidgets.QTableWidgetItem(c["text"]))
        t.resizeRowsToContents()

    def fix(self, name):
        getattr(self.owner, name)()
        self.refresh()

    def closeEvent(self, e):
        self.timer.stop()
        if getattr(self.owner, "_ready", None) is self:
            self.owner._ready = None
        super().closeEvent(e)


class FestivalDialog(QtWidgets.QDialog):
    """🌙 Mode festival : faire tourner la surveillance toute la nuit, toute la semaine, sans y penser."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        c = o.festival
        self.setWindowTitle("Mode festival (nuit complète)")
        self.resize(560, 470)
        lay = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Pour laisser le PC surveiller seul toute la nuit (ou toute la semaine) : il reprend tout seul après une "
            "coupure, ne se met pas en veille, et chaque jour il écrit un rapport et t'envoie un bilan sur le "
            "téléphone (« tout va bien », ou ce qui s'est passé).")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.on_chk = QtWidgets.QCheckBox("🌙 Activer le mode festival")
        self.on_chk.setChecked(c["on"])
        self.on_chk.setStyleSheet("font-weight:bold")
        lay.addWidget(self.on_chk)
        self.box = QtWidgets.QGroupBox("")
        f = QtWidgets.QVBoxLayout(self.box)
        self.auto_chk = QtWidgets.QCheckBox("Reprendre la surveillance tout seul au lancement de l'appli\n"
                                            "(après une coupure de courant, un plantage, un redémarrage de Windows)")
        self.auto_chk.setChecked(c["autostart"])
        self.boot_chk = QtWidgets.QCheckBox("Lancer RF Technical Monitor au démarrage de Windows")
        self.boot_chk.setChecked(o.windows_startup_on())
        self.boot_chk.setEnabled(sys.platform == "win32")
        self.boot_chk.setToolTip("Ajoute l'appli aux programmes lancés à l'ouverture de ta session Windows.\n"
                                 "Avec la case du dessus : après une coupure, le PC redémarre et la surveillance reprend.\n"
                                 "(Le PC doit ouvrir la session tout seul, et le BIOS se rallumer après une coupure.)")
        self.sleep_chk = QtWidgets.QCheckBox("Empêcher Windows de se mettre en veille pendant la surveillance")
        self.sleep_chk.setChecked(c["nosleep"])
        self.guard_chk = QtWidgets.QCheckBox("🛡 Garde : relancer l'appli toute seule si elle plante ou se fige")
        self.guard_chk.setChecked(c.get("guard", True))
        self.guard_chk.setToolTip("Un petit programme sans fenêtre lance l'appli et la surveille : si elle plante, ou ne\n"
                                  "répond plus depuis 90 s, il la ferme et la relance, et la surveillance reprend.\n"
                                  "Utilisée au démarrage de Windows (case du dessus), ou tout de suite avec le bouton.")
        self.guard_lbl = QtWidgets.QLabel("")
        self.guard_lbl.setWordWrap(True)
        self.guard_btn = QtWidgets.QPushButton("🛡 Relancer maintenant sous garde")
        self.guard_btn.setToolTip("Ferme l'appli et la rouvre aussitôt sous garde (la surveillance reprend si elle tournait).")
        self.guard_btn.clicked.connect(lambda *_: self.relaunch())
        if o.guarded():
            self.guard_lbl.setText("✔ L'appli tourne en ce moment sous garde.")
            self.guard_btn.hide()
        else:
            self.guard_lbl.setText("L'appli ne tourne pas sous garde en ce moment.")
        self.guard_lbl.setStyleSheet("color:gray")
        self.daily_chk = QtWidgets.QCheckBox("Bilan chaque jour à")
        self.daily_chk.setChecked(c["daily"])
        self.hour_spin = QtWidgets.QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(c["hour"])
        self.hour_spin.setSuffix(" h")
        hl = QtWidgets.QHBoxLayout()
        hl.addWidget(self.daily_chk)
        hl.addWidget(self.hour_spin)
        hl.addStretch(1)
        dl = QtWidgets.QLabel("Le bilan = un rapport HTML du jour (dossier des journaux › rapports) + un message sur le "
                              "téléphone (réglé dans 📣 Alertes : ntfy ou Telegram) : « ✔ Tout va bien » ou les alarmes "
                              "des dernières 24 h.")
        dl.setWordWrap(True)
        dl.setStyleSheet("color:gray")
        for w_ in (self.auto_chk, self.boot_chk, self.sleep_chk, self.guard_chk):
            f.addWidget(w_)
        gl = QtWidgets.QHBoxLayout()
        gl.addWidget(self.guard_lbl, 1)
        gl.addWidget(self.guard_btn)
        # tester la garde sans chercher le bon processus dans le Gestionnaire des tâches (Clément : « comment simuler
        # un crash pour voir si l'appli se réouvre ? ») : seulement quand l'appli tourne sous garde
        self.crash_btn = QtWidgets.QPushButton("💥 Tester : plantage")
        self.crash_btn.setToolTip("Fait planter l'appli exprès : la garde doit la rouvrir en quelques secondes et la\n"
                                  "surveillance doit reprendre toute seule si elle tournait.")
        self.crash_btn.clicked.connect(lambda *_: o.guard_test("crash"))
        self.freeze_btn = QtWidgets.QPushButton("🧊 Tester : appli figée")
        self.freeze_btn.setToolTip("Fige l'appli exprès (plus aucune réponse) : la garde doit la fermer au bout de 90 s\n"
                                   "et la rouvrir.")
        self.freeze_btn.clicked.connect(lambda *_: o.guard_test("freeze"))
        for b_ in (self.crash_btn, self.freeze_btn):
            b_.setVisible(o.guarded())
            gl.addWidget(b_)
        f.addLayout(gl)
        f.addLayout(hl)
        f.addWidget(dl)
        lay.addWidget(self.box)
        self.on_chk.toggled.connect(lambda *_: self.box.setEnabled(self.on_chk.isChecked()))
        self.box.setEnabled(c["on"])
        self.on_chk.setToolTip("Tout ce qu'il faut pour laisser tourner la surveillance seule, nuit et jour.")
        self.auto_chk.setToolTip("Si l'appli s'arrête PENDANT la surveillance (coupure, plantage), elle la relance\n"
                                 "toute seule à son prochain lancement. Fermée exprès : elle ne relance rien.")
        self.sleep_chk.setToolTip("Le PC reste éveillé tant que la surveillance tourne (l'écran peut s'éteindre).")
        self.daily_chk.setToolTip("Une fois par jour, à cette heure : rapport du jour + message sur le téléphone.")
        self.hour_spin.setToolTip("Heure du bilan quotidien (rattrapé plus tard si le PC dormait à cette heure).")
        self.test_btn = QtWidgets.QPushButton("📨 Faire le bilan maintenant (test)")
        self.test_btn.setToolTip("Écrit le rapport et envoie le message tout de suite, pour vérifier que tout marche.")
        self.test_btn.clicked.connect(lambda *_: self.test())
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.test_btn)
        lay.addWidget(self.msg)
        lay.addStretch(1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        return dict(self.owner.festival, on=self.on_chk.isChecked(), autostart=self.auto_chk.isChecked(),
                    nosleep=self.sleep_chk.isChecked(), daily=self.daily_chk.isChecked(), hour=self.hour_spin.value(),
                    guard=self.guard_chk.isChecked())

    def relaunch(self):
        o = self.owner
        o.festival = festival_cfg_norm(self.values())
        if sys.platform == "win32" and self.boot_chk.isChecked():
            o.set_windows_startup(True)                 # la commande suit la case « Garde »
        self.accept()
        o.relaunch_guarded()

    def test(self):
        self.msg.setText(self.owner.festival_bilan(test=True))


class ReportDialog(QtWidgets.QDialog):
    def __init__(self, owner, prefs, has_im):
        super().__init__(owner)
        self.setWindowTitle("Rapport de show")
        self.resize(520, 420)
        p = prefs or {}
        lay = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Crée une page HTML autonome : événements, conflits, émetteurs absents, occupation par scène et groupe, "
            "spectre max hold, intermodulation. Ouvre-la dans le navigateur puis « Imprimer › Enregistrer en PDF ».")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QtWidgets.QFormLayout()
        self.title = QtWidgets.QLineEdit(p.get("title") or f"Rapport de show — {datetime.now():%d/%m/%Y}")
        self.venue = QtWidgets.QLineEdit(p.get("venue", ""))
        self.venue.setPlaceholderText("Festival, lieu, scène…")
        self.operator = QtWidgets.QLineEdit(p.get("operator", ""))
        self.operator.setPlaceholderText("Ton nom / ta société")
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlainText(p.get("notes", ""))
        self.notes.setPlaceholderText("Remarques : matériel, météo, incidents, fréquences changées…")
        self.im_chk = QtWidgets.QCheckBox("Inclure le dernier calcul d'intermodulation")
        self.im_chk.setChecked(has_im)
        self.im_chk.setEnabled(has_im)
        self.open_chk = QtWidgets.QCheckBox("Ouvrir dans le navigateur après l'enregistrement")
        self.open_chk.setChecked(True)
        form.addRow("Titre :", self.title)
        form.addRow("Lieu :", self.venue)
        form.addRow("Par :", self.operator)
        form.addRow("Notes :", self.notes)
        form.addRow(self.im_chk)
        form.addRow(self.open_chk)
        lay.addLayout(form)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        return dict(title=self.title.text().strip(), venue=self.venue.text().strip(),
                    operator=self.operator.text().strip(), notes=self.notes.toPlainText().strip(),
                    im=self.im_chk.isChecked(), open=self.open_chk.isChecked())


# --------------------------------------------------------------------------
# Dialogue : export des fréquences par scène / groupe
# --------------------------------------------------------------------------
class ExportListDialog(QtWidgets.QDialog):
    def __init__(self, owner, n_all, n_scope, n_sel, prefs):
        super().__init__(owner)
        self.setWindowTitle("Exporter les fréquences")
        self.resize(560, 300)
        p = prefs or {}
        form = QtWidgets.QFormLayout(self)
        self.src = QtWidgets.QComboBox()
        self.src.addItem(f"Toute la liste ({n_all})", "all")
        self.src.addItem(f"La couche active ({n_scope})", "scope")
        self.src.addItem(f"Les lignes sélectionnées ({n_sel})", "sel")
        self.split = QtWidgets.QComboBox()
        self.split.addItem("Un seul fichier", "all")
        self.split.addItem("Un fichier par scène", "scene")
        self.split.addItem("Un fichier par groupe", "group")
        self.fmt = QtWidgets.QComboBox()
        for lab, v in FREQ_FORMATS:
            self.fmt.addItem(lab, v)
        for combo, key in ((self.src, "src"), (self.split, "split"), (self.fmt, "fmt")):
            i = combo.findData(p.get(key))
            if i >= 0:
                combo.setCurrentIndex(i)
        form.addRow("Quoi :", self.src)
        form.addRow("Découpage :", self.split)
        form.addRow("Format :", self.fmt)
        note = QtWidgets.QLabel("Les fichiers sont créés dans un nouveau dossier daté. Le format « Complet » se "
                                "réimporte tel quel (📥 Importer CSV). Pour un format précis d'EazyRF / WWB / WSM, "
                                "envoie-moi un exemple d'import de ton logiciel et j'ajoute l'option.")
        note.setWordWrap(True)
        form.addRow(note)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self):
        return dict(src=self.src.currentData(), split=self.split.currentData(), fmt=self.fmt.currentData())


# --------------------------------------------------------------------------
# Fenêtre : mur de fréquences (tuiles, pour un 2e écran)
# --------------------------------------------------------------------------
class LevelSpin(QtWidgets.QDoubleSpinBox):
    """Case de saisie d'un niveau : value() / setValue() restent en dBm (tout le code interne), mais l'affichage et
    la saisie se font dans l'unité choisie (dBm, dBµV ou %)."""
    unit = "dbm"                                  # unité commune, réglée par MainWindow.set_unit

    def textFromValue(self, v):
        return fmt_level(v, LevelSpin.unit, 1, suffix=True)

    def valueFromText(self, text):
        t = text.replace(UNIT_SUFFIX.get(LevelSpin.unit, ""), "").replace(",", ".").strip()
        try:
            return from_unit(float(t), LevelSpin.unit)
        except ValueError:
            return self.value()

    def validate(self, text, pos):
        t = text.replace(UNIT_SUFFIX.get(LevelSpin.unit, ""), "").replace(",", ".").strip()
        if t in ("", "-", "+"):
            return QtGui.QValidator.State.Intermediate, text, pos
        try:
            float(t)
            return QtGui.QValidator.State.Acceptable, text, pos
        except ValueError:
            return QtGui.QValidator.State.Invalid, text, pos

    def refresh(self):
        self.lineEdit().setText(self.textFromValue(self.value()))


def tour_steps(o, key="ecran"):
    """Étapes d'un tuto : (widget montré, titre, c'est quoi, pourquoi, comment, action ou None). action = (texte du
    bouton, nom de la méthode de MainWindow) : le bouton « Fais-le » ouvre l'outil. Écrit pour quelqu'un qui n'y
    connaît rien : mots simples, une idée par étape."""
    sb = getattr(o, "step_btns", {})
    g = lambda name: getattr(o, name, None)         # noqa: E731 — un widget absent = étape sautée
    dock = lambda name: (g(name).widget() if g(name) is not None else None)  # noqa: E731
    if key == "show":
        return [
            (g("port_combo"), "1. Brancher le tinySA",
             "Le tinySA est un petit analyseur de spectre : il « écoute » toutes les fréquences radio autour de lui. "
             "Il se branche en USB sur le PC, avec son antenne vissée dessus.",
             "Sans lui, l'appli ne voit rien. Le mode démo permet d'essayer sans appareil.",
             "Visse l'antenne, allume le tinySA, branche-le en USB, ferme tinySA-App s'il est ouvert (un seul "
             "logiciel à la fois). Dans cette liste, choisis la ligne « ✔ tinySA ». S'il est sur un Raspberry Pi : "
             "« 🌐 tinySA en réseau… ».", None),
            (g("bands_btn"), "2. Les bandes à surveiller",
             "Une bande = une plage de fréquences que le tinySA balaye, par exemple 470–694 MHz (la bande des micros).",
             "Plus la plage est large, plus un balayage est long. On ne surveille que là où sont tes appareils.",
             "📶 Bandes : coche celles qui t'intéressent. Le pays (réglages) choisit les canaux TV affichés. Laisse "
             "« ⚡ Points » en Auto : l'appli règle la finesse toute seule.", None),
            (sb.get("scan"), "3. Scanner le lieu",
             "Avant de choisir tes fréquences, on regarde ce qui occupe DÉJÀ le lieu : télé (TNT), autres équipes, "
             "brouilleurs.",
             "Choisir une fréquence déjà prise, c'est la garantie d'un micro qui coupe pendant le show.",
             "📋 Préparer › ▶ Scanner ici : le balayage démarre et le max hold (courbe orange) repart de zéro. Laisse tourner 5 à 10 "
             "minutes, idéalement avec les écrans LED et les lumières allumés.", ("▶ Scanner le lieu", "step_scan")),
            (dock("dock_spec"), "4. Regarder le résultat",
             "Les bosses sont des émetteurs. Les grands plateaux de 8 MHz sont des chaînes de télé (TNT). Le bas "
             "irrégulier, c'est le bruit de fond.",
             "Tes fréquences doivent tomber dans les creux, loin des bosses et des plateaux.",
             "Survole le spectre : la fréquence et le niveau s'affichent. Le bandeau en dessous dit à quoi sert "
             "chaque morceau de bande dans ton pays. Le tuto « Lire le spectre » explique tout en détail.", None),
            (sb.get("list"), "5. Entrer tes fréquences",
             "Ta liste = toutes les fréquences de tes appareils (micros, ears, talkies…), une par ligne.",
             "C'est cette liste que l'appli surveille pendant le show.",
             "Importe ton plan (fichier EazyRF, WWB, WSM, Excel), colle une liste, ajoute à la main, ou « 📡 Ajouter "
             "depuis le scan » pour reprendre les signaux vus.", ("📥 Importer ma liste…", "import_watch")),
            (g("watch_table"), "6. Le statut de chaque fréquence : LE réglage important",
             "« En service » (doit émettre) : ton émetteur doit être là. « Libre » (doit rester libre) : une "
             "fréquence que tu gardes en réserve, personne ne doit y être.",
             "C'est ce qui décide des alarmes : un « En service » qui se tait → ABSENT ; un signal sur un « Libre » → "
             "CONFLIT.",
             "Double-clic dans la colonne Statut, ou sélectionne des lignes puis Ctrl+E (= En service). Ctrl+1…9 "
             "pour les autres statuts.", ("❓ C'est quoi exactement ?", "status_help")),
            (sb.get("plan"), "7. Vérifier que tes fréquences s'entendent",
             "La coordination vérifie qu'aucune fréquence n'est trop près d'une autre et qu'aucune « fréquence "
             "fantôme » (intermodulation) ne tombe sur un de tes micros.",
             "Deux micros mal coordonnés se brouillent, même si chacun est sur une fréquence libre.",
             "🧮 Vérifier le plan : chaque fréquence en ✗ a une remplaçante proposée (« Remplacer »). Ou 🪄 Trouver N "
             "fréquences : l'appli les choisit pour toi.", ("🧮 Vérifier mon plan…", "open_plan_check")),
            (g("thr_spin"), "8. Les seuils",
             "Le seuil « occupé » est la ligne rouge sur le spectre : au-dessus, on considère qu'il y a un signal.",
             "Trop bas : fausses alarmes à cause du bruit. Trop haut : tu rates des signaux faibles.",
             "Clique « Auto » : il se place un peu au-dessus du bruit de fond. « TX absent après » = combien de "
             "secondes sans signal avant l'alarme ABSENT (5 à 10 s, c'est bien).", None),
            (sb.get("show"), "9. Surveiller le show",
             "La surveillance balaye en continu et compare ce qu'elle voit à ta liste.",
             "C'est le cœur de l'appli : elle te prévient dès qu'un micro tombe ou qu'un intrus arrive.",
             "🎚 Surveiller › ▶ Démarrer. L'appli propose d'enregistrer la session (dis oui : tu pourras tout revoir). La colonne "
             "« Signal » passe au vert pour les émetteurs présents.", None),
            (g("alarm_btn"), "10. Quand une alarme sonne",
             "Une alarme = un problème sur une fréquence : ABSENT (ton micro ne se voit plus) ou CONFLIT (quelqu'un "
             "est sur ta réserve).",
             "Réagir vite, c'est éviter le trou dans le son.",
             "ABSENT : pile, émetteur allumé ? antenne ? artiste trop loin ? CONFLIT : regarde le spectre, passe sur "
             "une fréquence de secours. « Acquitter » coupe le son ; l'alarme reste tant que le problème dure.", None),
            (sb.get("show"), "11. Juste avant d'ouvrir : l'appel des micros",
             "Le line check : tu allumes tes émetteurs un par un, l'appli coche ceux qu'elle voit.",
             "Tu sais en une minute si un émetteur manque ou s'il est sur la mauvaise fréquence.",
             "🎚 Surveiller › 🎤 Appel des micros (Ctrl+L). Une fréquence inconnue proche d'une manquante = sûrement l'émetteur "
             "mal réglé.", ("🎤 Ouvrir l'appel des micros", "open_linecheck")),
            (sb.get("show"), "12. Être prévenu sur ton téléphone",
             "Les alarmes peuvent partir sur ton téléphone (ntfy, Telegram) et une page web montre tout aux autres "
             "techniciens du site.",
             "Tu n'es pas collé à l'écran pendant tout le show.",
             "🎚 Surveiller › 📣 Alertes téléphone et page web : le bouton 📖 Tuto explique chaque étape.",
             ("📣 Régler les alertes…", "open_alerts")),
            (sb.get("after"), "13. Après le show",
             "Tout ce qui s'est passé est enregistré : spectre, alarmes, journal.",
             "Pour comprendre un incident (« à 21 h 34 le micro 3 a coupé : pourquoi ? ») et faire un compte rendu.",
             "📊 Analyser › ⏪ Relecture pour revoir n'importe quel moment ; 📄 Rapport de show pour un document propre ; 📊 "
             "Occupation par heure.", ("⏪ Ouvrir la relecture", "open_replay")),
            (g("more_btn"), "14. Garder tout ton travail",
             "Un « show » 🎪 est un fichier qui contient tout : fréquences, scènes, bandes, scans gardés.",
             "L'an prochain, au même festival, tu repars de là en deux clics.",
             "Ctrl+S (ou 🎪 Shows en haut) pour enregistrer, 🎪 › Ouvrir pour le reprendre. Bon show ! 🎤", None),
        ]
    if key == "spectre":
        return [
            (dock("dock_spec"), "1. Ce que montre le graphique",
             "De gauche à droite : les fréquences en MHz (comme les stations d'une radio). De bas en haut : la "
             "puissance reçue en dBm.",
             "C'est la « photo » de tout ce qui émet autour du tinySA.",
             "−100 dBm en bas = presque rien, −40 dBm en haut = très fort. Un émetteur fait une bosse pointue à sa "
             "fréquence.", None),
            (dock("dock_spec"), "2. Le bruit de fond",
             "Même sans aucun émetteur, la courbe n'est jamais tout en bas : c'est le bruit de fond (le « tapis »), "
             "vers −100 dBm.",
             "Un signal compte quand il dépasse nettement ce tapis (10 dB et plus).",
             "Si le tapis monte d'un coup sur une zone : un écran LED, un éclairage ou un ordinateur rayonne. Approche "
             "ou éloigne le tinySA pour voir.", None),
            (g("legend_btn"), "3. Les courbes",
             "Bleu = ce que le tinySA voit maintenant. Orange = le plus haut vu depuis le dernier « Reset max » (max "
             "hold). Rouge pointillé = le seuil « occupé ».",
             "Le direct bouge tout le temps ; le max hold garde la trace d'un émetteur qui n'a émis qu'une seconde.",
             "❓ Courbes explique chaque trait et permet de les régler.", ("❓ Ouvrir l'explication des courbes",
                                                                          "open_spectrum_legend")),
            (g("hold_chk"), "4. Max hold et Reset max",
             "Le max hold mémorise le plus haut niveau vu à chaque fréquence.",
             "Pour un scan du lieu, c'est lui qu'on regarde : il montre tout ce qui a émis, même brièvement.",
             "Décoche pour le cacher ; « Reset max » le remet à zéro (par exemple en arrivant dans un nouveau lieu).",
             None),
            (g("view_combo"), "5. Choisir ce qu'on regarde",
             "La vue : toutes les bandes d'un coup, ou une seule bande.",
             "Sur une bande étroite on voit mieux les détails.",
             "Choisis une bande dans la liste ; molette de la souris pour zoomer, glisser pour déplacer, double-clic "
             "pour revenir.", None),
            (g("zoom_btn"), "6. Zoom live",
             "Le zoom live fait balayer au tinySA SEULEMENT la zone que tu regardes, beaucoup plus finement.",
             "Pour voir un signal en détail (sa largeur, s'il bouge) ou séparer deux signaux proches.",
             "Zoome sur la zone, puis 🔍 Zoom live. Re-clique pour revenir au balayage complet.", None),
            (g("mkr_btn"), "7. Marqueurs",
             "Deux repères M1 et M2 que tu poses sur le spectre.",
             "Pour lire précisément une fréquence, un niveau, l'écart entre deux signaux ou la largeur d'un signal.",
             "🎯 Marqueurs, puis clique sur le spectre ; « sur le pic » cale le marqueur sur le maximum voisin.",
             None),
            (g("pts_btn"), "8. Vitesse ou détail",
             "Le nombre de mesures par balayage.",
             "Beaucoup de points = détaillé mais lent ; peu = rapide mais on peut rater un signal étroit.",
             "Laisse « ⚡ Auto équilibré ». « Rapide » pour surveiller beaucoup de bandes, « Détaillé » pour un scan "
             "précis.", None),
            (dock("dock_wf"), "9. Le waterfall (chute d'eau)",
             "L'historique du spectre qui défile : chaque ligne = un balayage, la couleur = le niveau.",
             "On voit ce qui apparaît et disparaît dans le temps : un talkie qui parle, un émetteur qui saute.",
             "Visible en mode simple ou expert (☰ Plus › 👁 Affichage).", None),
            (g("tv_chk"), "10. Les canaux TV et le plan du pays",
             "Le bandeau sous le spectre : les canaux de télévision et à quoi sert chaque bande dans ton pays.",
             "Une fréquence dans un canal TV allumé ne marchera pas bien.",
             "Survole le bandeau pour le détail ; le pays se règle dans les réglages.", None),
        ]
    if key == "coord":
        return [
            (sb.get("plan"), "1. C'est quoi coordonner ?",
             "Choisir les fréquences de TOUS tes appareils pour qu'aucune ne gêne une autre.",
             "Il ne suffit pas qu'une fréquence soit libre : deux émetteurs proches créent des « fréquences "
             "fantômes » (intermodulation) qui peuvent tomber sur un troisième micro.",
             "Trois règles : assez d'écart entre les fréquences, pas de fantôme dessus, loin de ce qui occupe déjà "
             "le lieu (scan).", None),
            (sb.get("plan"), "2. Dire quel matériel tu as",
             "Un profil d'appareil = les réglages de coordination d'une marque (écart minimum, filtre du récepteur, "
             "pas de réglage).",
             "Un récepteur sélectif (Wisycom…) supporte des fréquences plus serrées qu'un modèle d'entrée de gamme.",
             "🎛 Profils d'appareil : choisis le tien, ou crée le tien avec les valeurs de ton logiciel de "
             "coordination.", ("🎛 Profils d'appareil…", "open_rx_profiles")),
            (sb.get("plan"), "3. Laisser l'appli trouver",
             "🪄 Trouver N fréquences : tu dis combien il t'en faut, l'appli cherche les meilleures.",
             "Elle tient compte de ta liste, de l'intermodulation et du spectre du lieu.",
             "Choisis l'appareil, combien, la plage (celle de tes émetteurs), et le « Spectre » à éviter : tout le "
             "site ou une scène. Puis « Ajouter à ma liste ».", ("🪄 Trouver N fréquences…", "open_coord")),
            (sb.get("plan"), "4. Vérifier un plan existant",
             "🧮 Vérifier le plan contrôle ta liste comme un logiciel de coordination.",
             "Pour valider un plan importé ou repérer la fréquence qui pose problème.",
             "Les lignes en ✗ disent pourquoi (trop près, intermod) ; « Remplacer » propose une fréquence qui ne crée "
             "aucun nouveau problème.", ("🧮 Vérifier le plan…", "open_plan_check")),
            (sb.get("im"), "5. L'intermodulation",
             "Le calcul des fréquences fantômes de tes émetteurs (2A − B, A + B − C…).",
             "Pour comprendre d'où vient un signal gênant, ou vérifier un emplacement.",
             "📋 Préparer › ⚡ Intermod : la liste des produits qui tombent sur tes fréquences, du plus grave au moins grave. Les "
             "« règles » choisissent quels produits on compte.", ("⚡ Ouvrir l'intermod…", "open_intermod")),
            (sb.get("show"), "6. Une fréquence de secours",
             "Quand un micro est brouillé pendant le show, il faut une autre fréquence, vite.",
             "L'appli cherche une fréquence libre MAINTENANT, compatible avec le reste.",
             "🎚 Surveiller › 🆘 Fréquence de secours ; prépare-en quelques-unes avant le show (statut « Libre » : elles sont "
             "surveillées).", ("🆘 Fréquence de secours…", "open_rescue")),
            (sb.get("plan"), "7. Coordination par scène ou globale",
             "Avec des scans gardés par scène, tu peux coordonner une scène avec SON spectre, ou tout le site d'un "
             "coup.",
             "Une scène loin des autres a son propre environnement radio.",
             "Dans 🪄 Trouver N et 🆘 Secours, la liste « Spectre : … » : max hold actuel, tout le site, ou une "
             "scène.", ("📍 Scans par lieu…", "open_sites")),
        ]
    if key == "scenes":
        return [
            (g("layer_box"), "1. Scènes et groupes",
             "Un classement de tes fréquences : une scène (Grande scène, Club…) contient des groupes (Micros, Ears, "
             "Talkies…).",
             "En festival on s'y retrouve, on filtre l'écran par scène, et chaque groupe peut avoir sa priorité "
             "d'alarme.",
             "＋ Scène, ＋ Groupe ; clic sur une scène = n'afficher qu'elle ; clic droit = renommer, couleur, "
             "priorité.", None),
            (sb.get("plan"), "2. Garder un scan par lieu",
             "Un scan gardé = la mémoire du spectre d'un endroit.",
             "Chaque scène a son environnement radio : la coordination peut en tenir compte.",
             "📍 Scans par lieu : choisis le lieu, « 📍 Garder », ou importe un scan d'un autre logiciel (WWB, WSM…).",
             ("📍 Scans par lieu…", "open_sites")),
            (g("port_combo"), "3. Le tinySA dans le sac (Raspberry Pi)",
             "Un tinySA branché sur un Raspberry Pi, avec une batterie, partagé en Wi-Fi : le PC reste en régie, toi "
             "tu te déplaces.",
             "Pour scanner chaque scène sans déplacer le PC, ou chercher un brouilleur.",
             "Kit à télécharger avec l'exe (relais-raspberry-pi.zip, mode d'emploi dedans). Dans l'appli : liste des "
             "ports › « 🌐 tinySA en réseau… » › l'adresse du Pi.", None),
            (g("sites_btn"), "4. Dire où est chaque tinySA (mode expert)",
             "Chaque tinySA peut surveiller une ou plusieurs scènes : ses balayages alimentent le spectre de ces "
             "scènes.",
             "Cliquer une scène dans « Mes fréquences » montre alors SON spectre en direct.",
             "📡 Scènes ▾ › Mes tinySA et leurs scènes, ou clic droit sur une scène › Surveillée par. 👋 Identifier "
             "fait clignoter l'écran du tinySA.", ("📡 Mes tinySA et leurs scènes…", "open_devices")),
            (sb.get("show"), "5. Depuis le téléphone : la vue Terrain",
             "Une vue cachée de la page web : dire où est le tinySA volant, voir son spectre (rémanence, max hold "
             "par scène) et garder des scans, tout depuis le téléphone.",
             "Tu fais le tour du site sans revenir au PC : chaque scan est enregistré sur le PC, dans sa scène.",
             "📣 Alertes et page web : coche la vue « 🎒 Terrain » et règle un code PIN, puis ouvre l'adresse de la "
             "page sur ton téléphone.", ("📣 Page web…", "open_alerts")),
            (sb.get("plan"), "6. Coordonner par scène ou tout le site",
             "Avec tes scans gardés, la coordination évite ce qui est occupé sur une scène, ou partout.",
             "Des fréquences qui marchent partout pour le matériel qui circule, ou au plus serré par scène.",
             "🪄 Trouver N fréquences › « Spectre : scène … » ou « tout le site ».", ("🪄 Trouver N fréquences…",
                                                                                    "open_coord")),
        ]
    if key == "live":
        return [
            (dock("dock_alarm"), "1. Le tableau des alarmes",
             "Toutes les alarmes en cours et terminées : quoi, où, depuis quand, quel niveau.",
             "D'un coup d'œil tu sais ce qui ne va pas, même si tu n'as pas entendu le bip.",
             "Rouge = à acquitter. « Acquitter » coupe le son ; double-clic = voir la fréquence sur le spectre.",
             None),
            (g("alarm_btn"), "2. Que faire face à une alarme ?",
             "ABSENT : un émetteur ne se voit plus. CONFLIT : un signal sur une fréquence réservée. TROP FORT : un "
             "signal énorme.",
             "Chaque type a ses causes habituelles.",
             "ABSENT → pile, interrupteur, antenne, artiste hors portée. CONFLIT → qui émet ? (spectre, chasse au "
             "brouilleur), sinon fréquence de secours. TROP FORT → un émetteur collé au tinySA, ou un brouilleur.",
             None),
            (sb.get("show"), "3. Le mur pour la régie",
             "Une grande tuile par fréquence, lisible de loin, à mettre sur un 2ᵉ écran.",
             "Toute l'équipe voit l'état des micros sans lire de chiffres.",
             "🧱 Mur, puis ⛶ Plein écran ; 🖥 Autre écran s'il y en a deux.", ("🧱 Ouvrir le mur", "open_wall")),
            (sb.get("show"), "4. Chasser un brouilleur",
             "Un bip qui accélère quand tu te rapproches du signal, comme un détecteur de métaux.",
             "Pour trouver l'appareil qui pollue (talkie oublié, écran LED, émetteur d'une autre équipe).",
             "🔎 Chasse : la fréquence, ▶ Chasser, et promène le tinySA (ou le kit Pi avec le téléphone qui bippe).",
             ("🔎 Chasse au brouilleur…", "open_hunt")),
            (sb.get("show"), "5. Le planning des plateaux",
             "Qui joue quand, par scène : pendant un changement de plateau, les micros éteints ne déclenchent pas "
             "d'alarme ABSENT.",
             "Moins de fausses alarmes, et le journal note chaque changement.",
             "🎬 Planning : une ligne par créneau (scène, groupe, début, fin).", ("🎬 Planning…", "open_planning")),
            (sb.get("show"), "6. La nuit et plusieurs jours",
             "Le mode festival : l'appli reprend toute seule après une coupure, empêche la mise en veille et envoie "
             "un bilan chaque matin.",
             "Tu dors tranquille, et le matin tu sais si quelque chose s'est passé.",
             "🌙 Mode festival : coche ce que tu veux, l'heure du bilan.", ("🌙 Mode festival…", "open_festival")),
        ]
    return [
        (g("port_combo"), "Bienvenue 👋",
         "RF Technical Monitor écoute en permanence les fréquences radio de tes micros sans fil grâce à un petit appareil, "
         "le tinySA.",
         "Il te prévient tout de suite si un micro se tait ou si quelqu'un vient émettre sur ta fréquence.",
         "Ici tu choisis où est branché le tinySA (la ligne « ✔ tinySA »).", None),
        (g("demo_chk"), "Le mode démo",
         "De faux signaux, pour essayer sans appareil.",
         "Pour apprendre tranquillement avant le jour J.",
         "Coche « Mode démo » puis ▶ Démarrer.", None),
        (g("start_btn"), "Démarrer / arrêter",
         "Lance ou arrête le balayage : le tinySA mesure les fréquences en boucle.",
         "Rien ne se passe tant que ce n'est pas démarré.",
         "▶ Démarrer ; ■ Arrêter pour stopper.", None),
        (sb.get("prep"), "Les 4 menus du travail",
         "En haut, quatre boutons rangent tous les outils selon le moment : 📋 Préparer (scanner le lieu, ta liste), "
         "🎚 Surveiller (pendant le show), 📊 Analyser (après le show), 🔌 Matériel (tinySA, réseau, mesure).",
         "Tu cherches un outil ? Demande-toi « je prépare, je surveille, j'analyse, ou c'est le matériel ? ».",
         "Clique un des quatre boutons : son menu s'ouvre.", None),
        (dock("dock_spec"), "Le spectre",
         "Le graphique : de gauche à droite les fréquences, de bas en haut la puissance reçue.",
         "Tu vois ce qui émet autour de toi.",
         "Bleu = maintenant, orange = le plus haut vu (max hold), rouge = seuil « occupé ». Tuto « Lire le "
         "spectre » pour tout comprendre.", None),
        (g("bands_btn"), "Bandes et points",
         "📶 Bandes : quelles plages balayer. ⚡ Points : vitesse ou détail.",
         "Moins de bandes = balayage plus rapide.",
         "Laisse ⚡ en Auto si tu débutes.", None),
        (g("watch_table"), "Ta liste de fréquences",
         "Une ligne par fréquence surveillée, avec son état en direct.",
         "C'est ce qui déclenche les alarmes.",
         "Colonne Signal : vert = OK, bleu = libre, orange = faible, rouge = problème. Colonne Statut : « En "
         "service » = doit émettre, « Libre » = doit rester libre (double-clic pour changer).", None),
        (g("layer_box"), "Scènes et groupes (facultatif)",
         "Pour ranger tes fréquences par scène et par groupe.",
         "Utile en festival ; inutile pour un petit événement.",
         "Clic sur une scène = n'afficher qu'elle ; « Global » = tout.", None),
        (g("thr_bar"), "Les seuils",
         "La petite barre au-dessus du spectre : à partir de quel niveau une fréquence est « occupée » ou "
         "« faible », et au bout de combien de temps un micro muet devient « absent ».",
         "Ce sont eux qui décident quand une alarme part.",
         "Commence par « Auto » à côté du seuil « occupé ».", None),
        (g("alarm_btn"), "Les alarmes 🔔",
         "Le compteur des alarmes en cours.",
         "Rouge = quelque chose à regarder tout de suite.",
         "Clique pour ouvrir le tableau ; « Acquitter » coupe le son.", None),
        (g("settings_btn"), "⚙ Réglages",
         "Tout ce qu'on règle une fois : seuils et alarmes, bandes à balayer, mesure, 2ᵉ tinySA, pays, langue, son, "
         "dossiers, connexions.",
         "Pour adapter l'appli à ton matériel et à ton PC.",
         "Ctrl+, l'ouvre aussi.", None),
        (g("more_btn"), "☰ Plus",
         "Les réglages, les fenêtres, l'apparence, le niveau d'affichage et l'aide.",
         "Tout ce qui sert à régler l'appli elle-même est là.",
         "« 👁 Affichage » : ultra simple (l'essentiel), simple, ou expert (tout). 📖 Manuel et 📚 Lexique dans "
         "Aide.", None),
        (getattr(g("home"), "tour_btn", None), "Les autres tutos",
         "D'autres visites guidées : mon premier show de A à Z, lire le spectre, coordonner, plusieurs scènes, "
         "pendant le show.",
         "Chacune prend quelques minutes et ouvre les bons outils pour toi.",
         "Clique 🎓 Tuto à tout moment ; 📚 Lexique explique chaque mot.", None),
    ]


class TourDialog(QtWidgets.QDialog):
    """Tuto : une bulle par étape, posée à côté de la partie de l'écran concernée (entourée en orange) :
    c'est quoi / pourquoi / comment, et un bouton « Fais-le » qui ouvre l'outil."""

    def __init__(self, owner, steps, title="Tuto"):
        super().__init__(owner)
        self.owner = owner
        self.steps = [s_ for s_ in steps if s_[0] is not None]
        self.i, self._hl = 0, None
        self.setWindowTitle(title)
        self.setModal(False)
        lay = QtWidgets.QVBoxLayout(self)
        self.title = QtWidgets.QLabel("")
        f_ = self.title.font()
        f_.setPointSize(f_.pointSize() + 3)
        f_.setBold(True)
        self.title.setFont(f_)
        self.title.setWordWrap(True)
        lay.addWidget(self.title)
        self.parts = []
        for head in ("🧐 C'est quoi ?", "🎯 Pourquoi ?", "👉 Comment ?"):
            h_ = QtWidgets.QLabel(head)
            hf = h_.font()
            hf.setBold(True)
            h_.setFont(hf)
            t_ = QtWidgets.QLabel("")
            t_.setWordWrap(True)
            t_.setMinimumWidth(420)
            t_.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(h_)
            lay.addWidget(t_)
            self.parts.append(t_)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:#d29922")
        lay.addWidget(self.note)
        self.act_btn = QtWidgets.QPushButton("")
        self.act_btn.setToolTip("Ouvre l'outil dont parle cette étape (le tuto reste ouvert).")
        self.act_btn.clicked.connect(lambda *_: self._do())
        self.count = QtWidgets.QLabel("")
        self.prev_btn = QtWidgets.QPushButton("◀ Précédent")
        self.prev_btn.setToolTip("Étape précédente.")
        self.next_btn = QtWidgets.QPushButton("Suivant ▶")
        self.next_btn.setToolTip("Étape suivante.")
        gl_btn = QtWidgets.QPushButton("📚 Lexique")
        gl_btn.setToolTip("Tous les mots de la HF expliqués simplement.")
        gl_btn.clicked.connect(lambda *_: owner.open_glossary())
        quit_btn = QtWidgets.QPushButton("Quitter le tuto")
        quit_btn.setToolTip("Ferme le tuto (relançable : bouton 🎓 Tuto, ou ☰ Plus › Aide).")
        self.prev_btn.clicked.connect(lambda *_: self.go(self.i - 1))
        self.next_btn.clicked.connect(lambda *_: self.go(self.i + 1) if self.i + 1 < len(self.steps) else self.close())
        quit_btn.clicked.connect(self.close)
        lay.addLayout(owner._row(self.act_btn, None, gl_btn))
        lay.addLayout(owner._row(self.count, None, quit_btn, self.prev_btn, self.next_btn))
        self.resize(500, 360)

    def _mark(self, w):
        if self._hl is not None:
            try:
                self._hl[0].setStyleSheet(self._hl[1])
            except RuntimeError:
                pass
        self._hl = None
        if w is not None:
            self._hl = (w, w.styleSheet())
            w.setStyleSheet(w.styleSheet() + "; border: 3px solid #f5a623; border-radius: 4px;")

    def _do(self):
        act = self.steps[self.i][5]
        if act is not None and callable(getattr(self.owner, act[1], None)):
            getattr(self.owner, act[1])()

    def go(self, i):
        i = max(0, min(len(self.steps) - 1, i))
        self.i = i
        w, t, what, why, how, act = self.steps[i]
        self.title.setText(t)
        for lab, txt in zip(self.parts, (what, why, how)):
            lab.setText(txt)
        hidden = False
        try:
            hidden = not w.isVisible()
        except RuntimeError:
            pass
        self.note.setText("Cette partie est cachée dans l'affichage actuel : ☰ Plus › 👁 Affichage › Simple ou Expert "
                          "pour la voir." if hidden else "")
        self.act_btn.setVisible(act is not None)
        if act is not None:
            self.act_btn.setText(act[0])
        self.count.setText(f"{i + 1} / {len(self.steps)}")
        self.prev_btn.setEnabled(i > 0)
        self.next_btn.setText("Terminer ✔" if i == len(self.steps) - 1 else "Suivant ▶")
        self._mark(w)
        try:                                       # la bulle à côté de la partie montrée, sans sortir de l'écran
            g = w.mapToGlobal(w.rect().bottomLeft())
            scr = (w.screen() or QtWidgets.QApplication.primaryScreen()).availableGeometry()
            x = min(max(scr.left(), g.x()), scr.right() - self.width())
            y = g.y() + 8
            if y + self.height() > scr.bottom():
                y = max(scr.top(), w.mapToGlobal(w.rect().topLeft()).y() - self.height() - 8)
            self.move(x, y)
        except Exception:  # noqa: BLE001 — position seulement
            pass

    def closeEvent(self, e):
        self._mark(None)
        self.owner.tour_finished()
        super().closeEvent(e)


class TourChooser(QtWidgets.QDialog):
    """🎓 Choisir un tuto (pour débutants complets), ou ouvrir le lexique."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Tutos")
        lay = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel("Des visites guidées pas à pas : chaque étape montre une partie de l'écran (entourée "
                                "en orange) et explique c'est quoi, pourquoi et comment, avec un bouton qui ouvre "
                                "l'outil. Aucune connaissance nécessaire.")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.buttons = {}
        for k, t, mins, desc in TOURS:
            if k in COORD_TOURS and not getattr(owner, "coord_on", False):
                continue
            b = QtWidgets.QPushButton(f"{t}  ·  {mins} min")
            b.setToolTip(desc)
            b.setStyleSheet("text-align:left; padding:6px 10px; font-weight:bold")
            b.clicked.connect(lambda *_, k=k: (self.accept(), owner.start_tour(k)))
            d_ = QtWidgets.QLabel(desc)
            d_.setWordWrap(True)
            d_.setStyleSheet("color:gray; margin:0 0 6px 12px")
            lay.addWidget(b)
            lay.addWidget(d_)
            self.buttons[k] = b
        gl = QtWidgets.QPushButton("📚 Lexique : tous les mots de la HF expliqués")
        gl.setToolTip("dBm, max hold, intermodulation, RBW… expliqués simplement.")
        gl.clicked.connect(lambda *_: owner.open_glossary())
        man = QtWidgets.QPushButton("📖 Manuel complet")
        man.setToolTip("Le manuel détaillé, avec le processus complet d'un festival.")
        man.clicked.connect(lambda *_: owner.open_manual())
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.reject)
        lay.addLayout(owner._row(gl, man, None, close))
        self.resize(560, 520)


class GlossaryDialog(QtWidgets.QDialog):
    """📚 Lexique : les mots de la HF et de l'appli expliqués à quelqu'un qui n'y connaît rien (avec recherche)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle("Lexique")
        self.setModal(False)
        lay = QtWidgets.QVBoxLayout(self)
        self.q = QtWidgets.QLineEdit()
        self.q.setPlaceholderText("🔎 Chercher un mot (ex. intermod, dBm, max hold)…")
        self.q.setToolTip("Tape un mot : la liste ne garde que ce qui en parle.")
        self.q.setClearButtonEnabled(True)
        lay.addWidget(self.q)
        self.view = QtWidgets.QTextBrowser()
        self.view.setToolTip("Les mots de la HF, du plus simple au plus technique.")
        lay.addWidget(self.view, 1)
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.close)
        lay.addLayout(owner._row(None, close))
        self.q.textChanged.connect(lambda *_: self.fill())
        self.resize(620, 620)
        self.fill()

    def fill(self):
        import html
        items = glossary_find(self.q.text())
        self.view.setHtml("".join(f"<p><b>{html.escape(TR(t))}</b><br>{html.escape(TR(x))}</p>" for t, x in items)
                          or f"<p>{html.escape(TR('Aucun mot trouvé.'))}</p>")
        self.count = len(items)


def qr_image(text, px=360, dark="#000000", light="#ffffff"):
    """📱 7.63 : QR code (segno, niveau de correction M) -> QImage carrée d'environ px pixels, marge de 4 modules.
    None si segno manque (l'adresse reste affichée en texte)."""
    try:
        import segno
    except Exception:  # noqa: BLE001
        return None
    q = segno.make(text, error="m", micro=False)
    rows = [list(r) for r in q.matrix]
    n = len(rows) + 8
    sc = max(2, px // n)
    img = QtGui.QImage(n * sc, n * sc, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor(light))
    p = QtGui.QPainter(img)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QtGui.QColor(dark))
    for y, r in enumerate(rows):
        for x, v in enumerate(r):
            if v:
                p.drawRect((x + 4) * sc, (y + 4) * sc, sc, sc)
    p.end()
    return img


class HistoryDialog(QtWidgets.QDialog):
    """🕘 7.63 : historique des modifications de la liste : heure, qui (PC / téléphone / plan suivi), quoi, avant,
    après ; filtre, export CSV. Gardé dans le show."""

    COLS = ["Heure", "Qui", "Quoi", "Micro", "Avant", "Après"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Historique des modifications")
        lay = QtWidgets.QVBoxLayout(self)
        self.q = QtWidgets.QLineEdit()
        self.q.setPlaceholderText("🔎 Filtrer : nom, fréquence, qui…")
        self.q.setClearButtonEnabled(True)
        self.q.textChanged.connect(lambda *_: self.fill())
        lay.addWidget(self.q)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("Chaque changement de ta liste : ajout, retrait, fréquence, nom, statut, scène › groupe.\n"
                              "« 📱 nom » = fait depuis la page Tech d'un téléphone. Le plus récent en haut.")
        lay.addWidget(self.table, 1)
        self.msg = QtWidgets.QLabel("")
        exp = QtWidgets.QPushButton("Exporter en CSV…")
        exp.setToolTip("Pour l'archiver ou l'envoyer (tableur).")
        exp.clicked.connect(lambda *_: self.export())
        clr = QtWidgets.QPushButton("Vider l'historique")
        clr.setToolTip("Efface l'historique de ce show (la liste ne change pas).")
        clr.clicked.connect(lambda *_: self.clear())
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.close)
        lay.addLayout(o._row(self.msg, None, exp, clr, close))
        self.resize(820, 520)
        self.fill()

    def rows(self):
        q = self.q.text().strip().lower()
        out = []
        for x in reversed(self.owner.mod_history):
            vals = (datetime.fromtimestamp(x["t"]).strftime("%d/%m %H:%M:%S"), x["who"], TR(HIST_WHAT.get(x["what"], x["what"])),
                    x["name"], x["old"], x["new"])
            if q and q not in " ".join(vals).lower():
                continue
            out.append(vals)
        return out

    def fill(self):
        rows = self.rows()
        self.table.setRowCount(len(rows))
        for r, vals in enumerate(rows):
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QtWidgets.QTableWidgetItem(v))
        self.msg.setText(TR("{} changement(s)").format(len(rows)))

    def export(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter l'historique", "historique.csv", "CSV (*.csv)")
            if not path:
                return False
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            wr = csv.writer(fh, delimiter=";")
            wr.writerow([TR(c) for c in self.COLS])
            wr.writerows(self.rows())
        return True

    def clear(self):
        r = QtWidgets.QMessageBox.question(self, APP_NAME, TR("Vider l'historique des modifications de ce show ?"))
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            self.owner.mod_history = []
            self.fill()


class QrDialog(QtWidgets.QDialog):
    """📱 7.63 : QR code de la page web : l'équipe le scanne avec l'appareil photo du téléphone et arrive sur la bonne
    vue (accueil, mur, alarmes, régie, Tech…), sans avoir à dicter l'adresse. Enregistrable en PNG pour l'imprimer."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("QR code pour les téléphones")
        lay = QtWidgets.QVBoxLayout(self)
        self.info = QtWidgets.QLabel("Scanne ce code avec l'appareil photo du téléphone (même Wi-Fi / réseau que ce PC) : "
                                     "la page s'ouvre directement sur la vue choisie.")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.ip_combo = QtWidgets.QComboBox()
        self.ip_combo.setToolTip("Adresse de ce PC sur le réseau (s'il y en a plusieurs : celle du réseau de l'équipe).")
        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.setToolTip("Vue ouverte en arrivant (seulement les vues partagées dans 📣 Alertes et page web).")
        lay.addLayout(o._row("Adresse :", self.ip_combo, "Ouvrir sur :", self.view_combo, None))
        self.qr = QtWidgets.QLabel("")
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setMinimumSize(300, 300)
        lay.addWidget(self.qr, 1)
        self.url = QtWidgets.QLabel("")
        self.url.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        f = self.url.font()
        f.setPointSizeF(f.pointSizeF() * 1.3)
        self.url.setFont(f)
        lay.addWidget(self.url)
        self.web_btn = QtWidgets.QPushButton("📣 Activer la page web…")
        self.web_btn.setToolTip("La page web est coupée : l'activer dans 📣 Alertes et page web.")
        self.web_btn.clicked.connect(lambda *_: o.open_alerts())
        copy = QtWidgets.QPushButton("Copier l'adresse")
        copy.setToolTip("Copie l'adresse dans le presse-papiers (pour un message à l'équipe).")
        copy.clicked.connect(lambda *_: QtWidgets.QApplication.clipboard().setText(self.link()))
        save = QtWidgets.QPushButton("Enregistrer en PNG…")
        save.setToolTip("Image à imprimer et coller en régie ou au plateau.")
        save.clicked.connect(lambda *_: self.save_png())
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.close)
        lay.addLayout(o._row(self.web_btn, None, copy, save, close))
        self.ip_combo.currentIndexChanged.connect(lambda *_: self.draw())
        self.view_combo.currentIndexChanged.connect(lambda *_: self.draw())
        self.fill()
        self.resize(460, 560)

    def fill(self):
        o = self.owner
        self.ip_combo.blockSignals(True)
        self.view_combo.blockSignals(True)
        self.ip_combo.clear()
        for ip in local_ips() or ["127.0.0.1"]:
            self.ip_combo.addItem(ip, ip)
        self.view_combo.clear()
        self.view_combo.addItem("🏠 Accueil", "")
        views = (o.web_cfg or {}).get("views") or {}
        for k, ic, name, _d in WEB_VIEWS:
            if views.get(k, k not in WEB_VIEWS_HIDDEN):
                self.view_combo.addItem(f"{ic} {name}", k)
        self.ip_combo.blockSignals(False)
        self.view_combo.blockSignals(False)
        self.draw()

    def link(self):
        o = self.owner
        port = o.web.port if o.web is not None else int((o.web_cfg or {}).get("port", 8080) or 8080)
        return web_link(self.ip_combo.currentData() or "127.0.0.1", port, self.view_combo.currentData() or "")

    def draw(self):
        on = self.owner.web is not None
        self.web_btn.setVisible(not on)
        url = self.link()
        self.url.setText(url if on else TR("Page web coupée : active-la pour que ce code fonctionne."))
        img = qr_image(url, 360)
        self._img = img
        if img is None:
            self.qr.setText("(QR code indisponible : ouvre l'adresse ci-dessous à la main)")
        else:
            self.qr.setPixmap(QtGui.QPixmap.fromImage(img))
        self.qr.setEnabled(on)

    def save_png(self, path=None):
        if self._img is None:
            return False
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le QR code", "tinysa_qr.png", "Image PNG (*.png)")
            if not path:
                return False
        return bool(self._img.save(path, "PNG"))
