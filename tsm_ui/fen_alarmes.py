# Panneaux et disposition, priorités, alarmes, page web / Tech, sessions, rapports, fermeture. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenAlarmes:
    """Panneaux et disposition, priorités, alarmes, page web / Tech, sessions, rapports, fermeture. (méthodes de MainWindow, regroupées par thème.)"""

    def log_menu(self, pos):
        r = self.log_table.rowAt(pos.y())
        if r < 0 or r >= self.log_table.rowCount():
            return
        f = _num(self.log_table.item(r, 2).text())
        if f is None:
            return
        m = QtWidgets.QMenu(self)
        a_or = m.addAction("⚡ D'où ça peut venir ? (intermodulation)…")
        a_or.setVisible(self.coord_on)
        a_zoom = m.addAction("🔍 Voir sur le spectre")
        a_hunt = m.addAction("🔎 Chasser ce signal (bip)…")
        a_add = m.addAction("＋ Ajouter à ma liste")
        act = m.exec(self.log_table.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_hunt:
            self.open_hunt(f)
        elif act is a_or:
            self.open_intermod_for(f)
        elif act is a_zoom:
            self.view_range(f - 1.0, f + 1.0)
        elif act is a_add:
            sc, gr = self._scope_preset()
            self._append_watch(f"Nouveau {f:.3f}", f, scene=sc, group=gr)
            self.sort_watch()
            self.rebuild_watch_table()
            self._update_markers()

    # ------------------------------------------------------- fenêtres (docks)
    def _make_dock(self, title, name, widget, area):
        d = QtWidgets.QDockWidget(title, self)
        d.setObjectName(name)
        d.setWidget(widget)
        self.addDockWidget(area, d)
        return d

    def _build_docks_base(self, ftab, ltab, wf_box, center):
        R, B = Qt.DockWidgetArea.RightDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea
        self.dock_freq = self._make_dock("Mes fréquences", "dock_freq", ftab, R)
        self.dock_log = self._make_dock("Journal", "dock_journal", ltab, R)
        self.dock_spec = self._make_dock("Spectre", "dock_spectre", center, B)
        self.dock_wf = self._make_dock("Waterfall", "dock_wf", wf_box, B)
        self.dock_alarm = self._make_dock("Alarmes", "dock_alarmes", self._build_alarm_panel(), B)
        self.wall = WallWindow(self)
        self.dock_wall = self._make_dock("Mur de fréquences", "dock_mur", self.wall, B)
        self.dock_wall.topLevelChanged.connect(self._wall_float_txt)
        self.splitDockWidget(self.dock_spec, self.dock_wf, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_wf, self.dock_alarm, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.dock_spec, self.dock_wall)       # en onglet à côté du spectre
        self.dock_spec.raise_()
        self.dock_alarm.hide()
        self.dock_wall.hide()
        self.docks = [self.dock_spec, self.dock_freq, self.dock_log, self.dock_wf, self.dock_alarm,
                      self.dock_wall]
        self.tabifyDockWidget(self.dock_freq, self.dock_log)
        self.dock_freq.raise_()
        self.win_menu.clear()
        for d in self.docks:
            self.win_menu.addAction(d.toggleViewAction())
        self.win_menu.addSeparator()
        for txt, fn in (("Disposition standard", self.layout_standard),
                        ("Analyseur seul (spectre + waterfall)", self.layout_analyzer),
                        ("Monitoring (liste + couches + alarmes)", self.layout_monitor),
                        ("Double écran : panneaux sur l'autre écran", self.layout_dual)):
            self.win_menu.addAction(txt).triggered.connect(fn)
        self.win_menu.addSeparator()
        self.panel_menu = self.win_menu.addMenu("🗗 Vraies fenêtres / double écran")
        self.panel_menu.aboutToShow.connect(self._fill_panel_menu)
        self._fill_panel_menu()
        self.win_menu.addSeparator()
        self.win_menu.addAction("🧱 Ouvrir le mur de fréquences").triggered.connect(self.open_wall)
        self.win_menu.addAction("🧱 Mur sur l'autre écran (fenêtre)").triggered.connect(
            lambda *_: self.wall_window_other_screen())
        self.win_menu.addAction("🧱 Mur en plein écran sur l'autre écran").triggered.connect(self.wall_other_screen)

    def _build_docks(self, *a, **k):
        """Panneaux de l'appli, puis (V8) ceux du poste SDR 1 : créés AVEC les autres, la disposition enregistrée
        (restoreState) les replace ; ils sont dans 🪟 Fenêtres et se déplacent comme les autres."""
        r = self._build_docks_base(*a, **k)
        self.rf_mode = "tiny"
        self.sdr_engs, self.post_docks = {}, {}
        self._make_post(1)
        self.sdr_eng, self.sdr_docks = self.sdr_engs[1], self.post_docks[1]
        self._make_lab()                             # 8.2 : labo SDR en panneaux
        return r

    def _dock_sizes(self):
        """Disposition de base : le spectre a la place (≈ la moitié de la largeur, ~70 % de la hauteur de sa
        colonne), liste à droite, waterfall et alarmes en bandeaux sous le spectre (réglages : ⚙)."""
        W = max(self.width(), 900)
        right = max(290, min(600, int(W * 0.34)))
        self.resizeDocks([self.dock_freq], [right], Qt.Orientation.Horizontal)
        self._middle_sizes()

    def _middle_sizes(self):
        """Colonne du milieu : spectre ~76 %, waterfall ~24 %, alarmes en bandeau (~170 px)."""
        H = max(self.height(), 600) - 80
        docks, sizes = [self.dock_spec], [0]
        if self.dock_wf.isVisible() and not self.dock_wf.isFloating():
            docks.append(self.dock_wf)
            sizes.append(int(H * 0.22))
        if self.dock_alarm.isVisible() and not self.dock_alarm.isFloating():
            docks.append(self.dock_alarm)
            sizes.append(170)
        sizes[0] = max(250, H - sum(sizes[1:]))
        if len(docks) > 1:
            self.resizeDocks(docks, sizes, Qt.Orientation.Vertical)

    def _layout_base(self):
        R, B = Qt.DockWidgetArea.RightDockWidgetArea, Qt.DockWidgetArea.BottomDockWidgetArea
        self.panel_attach_all()
        for d in self.docks:
            d.setFloating(False)
            if not d.objectName().startswith(("dock_sdr", "dock_lab")):   # 8.0 : les panneaux SDR suivent le mode (montés ici, le
                d.show()                                    # Récepteur agrandissait la fenêtre : 1 028 -> 1 491 px)
        self.addDockWidget(R, self.dock_freq)
        self.addDockWidget(R, self.dock_log)
        self.addDockWidget(B, self.dock_spec)
        self.splitDockWidget(self.dock_spec, self.dock_wf, Qt.Orientation.Vertical)
        self.splitDockWidget(self.dock_wf, self.dock_alarm, Qt.Orientation.Vertical)
        self.tabifyDockWidget(self.dock_freq, self.dock_log)
        self.tabifyDockWidget(self.dock_spec, self.dock_wall)
        self.dock_freq.raise_()
        self.dock_spec.raise_()
        self.dock_alarm.hide()
        self.dock_wall.hide()
        if self.view_id == -1 and self._zoom is None:
            self.dock_wf.hide()      # rien à afficher en vue « toutes les bandes »
        self._dock_sizes()

    def layout_standard(self):
        """Disposition de base : tout revient des autres écrans (8.0.2), puis celle du mode."""
        self.screens_off(relayout=False)
        self._layout_mode()

    def _layout_mode(self):
        """Disposition de base de l'appli, puis celle du mode (tinySA / SDR / combiné)."""
        sz, big = self.size(), self.isMaximized() or self.isFullScreen()
        self._layout_base()
        for d in self.all_sdr_docks():
            d.hide()
        if getattr(self, "rf_mode", "tiny") == "tiny" and not big and self.size() != sz:
            self.resize(sz)      # 8.0 (CI Windows) : les panneaux SDR, montés un instant, agrandissaient la fenêtre
        if getattr(self, "rf_mode", "tiny") != "tiny":
            self._sdr_arrange(self.rf_mode, "listen", base=False)
        QtCore.QTimer.singleShot(0, self._fit_screen)

    def layout_analyzer(self):
        self.layout_standard()
        self.dock_freq.hide()
        self.dock_log.hide()
        self.set_status("Disposition « analyseur » : réaffiche les panneaux par le menu 🪟 Fenêtres.")

    def layout_monitor(self):
        self.layout_standard()
        self.dock_wf.hide()
        self.dock_alarm.show()
        self.set_status("Disposition « monitoring » : réaffiche les panneaux par le menu 🪟 Fenêtres.")

    def _other_screen(self):
        cur = self.screen()
        for s in QtGui.QGuiApplication.screens():
            if s != cur:
                return s
        return None

    def layout_dual(self):
        scr = self._other_screen()
        if scr is None:
            self.set_status("Un seul écran détecté. Branche le 2ᵉ écran, ou tire les panneaux par leur barre de "
                            "titre : ils deviennent des fenêtres libres.")
            return
        self.layout_standard()
        self.panel_window(self.dock_freq, True, scr, "max")
        self.set_status("Liste des fréquences en vraie fenêtre sur l'autre écran. Menu 🪟 › 🗗 Vraies fenêtres pour "
                        "y envoyer d'autres panneaux (spectre, waterfall, alarmes…).")

    # ------------------------------------------------------- vraies fenêtres (double écran)
    def _panel_docks_base(self):
        """Panneaux qu'on peut sortir en vraie fenêtre (le mur a son propre mécanisme)."""
        return [self.dock_spec, self.dock_wf, self.dock_freq, self.dock_log, self.dock_alarm]

    def panel_docks(self):
        """Panneaux qu'on peut sortir en vraie fenêtre : ceux de l'appli + du SDR, sauf ceux prêtés à un autre écran."""
        hosted = {n for h in (getattr(self, "screen_hosts", None) or {}).values() for n in h.items}
        return [d for d in self._panel_docks_base() + self.all_sdr_docks() + self.all_lab_docks()
                if d.objectName() not in hosted]

    def panel_window(self, d, on, screen=None, mode=None):
        """Sort le panneau d dans une vraie fenêtre (on) ou le raccroche (off). screen : écran où la placer
        (agrandie par défaut) ; mode : normal | max | full."""
        key = d.objectName()
        win = self.panel_wins.get(key)
        if not on:
            if win is None:
                return
            self.panel_wins.pop(key, None)
            w = win.body.takeAt(0).widget() if win.body.count() else None
            if w is not None:
                old = d.widget()
                d.setWidget(w)
                if old is not None:
                    old.deleteLater()
            win.closing = True
            win.close()
            win.deleteLater()
            d.show()
            d.raise_()
            QtCore.QTimer.singleShot(0, self._middle_sizes)
            self.set_status(f"« {d.windowTitle()} » raccroché à la fenêtre principale.")
            return
        if win is None:
            w = d.widget()
            if d.isFloating():
                d.setFloating(False)
            ph = QtWidgets.QPushButton(f"📌 « {d.windowTitle()} » est dans sa propre fenêtre — cliquer pour le raccrocher")
            ph.setToolTip("Remet ce panneau ici.")
            ph.clicked.connect(lambda *_, d=d: self.panel_window(d, False))
            d.setWidget(ph)
            win = PanelWindow(self, d)
            win.body.addWidget(w)
            w.show()
            self.panel_wins[key] = win
            d.hide()
            win.resize(max(640, w.width()), max(420, w.height()))
            g = self.frameGeometry()
            win.move(g.x() + 60, g.y() + 60)
        if screen is not None:
            if win.isFullScreen():
                win.showNormal()
                win.bar.show()
            ag = screen.availableGeometry()
            win.setGeometry(ag.adjusted(40, 40, -40, -40))
            mode = mode or "max"
        if mode == "full":
            win.show()
            win.toggle_full() if not win.isFullScreen() else None
        elif mode == "max":
            win.showMaximized()
        else:
            win.show()
        win.raise_()
        win.activateWindow()
        self.set_status(f"« {d.windowTitle()} » dans sa propre fenêtre : déplace-la où tu veux (F11 = plein écran, "
                        "fermer = raccrocher).")

    def panel_next_screen(self, d):
        win = self.panel_wins.get(d.objectName())
        scrs = QtGui.QGuiApplication.screens()
        if win is None or not scrs:
            return
        cur = win.screen()
        i = next((k for k, s_ in enumerate(scrs) if s_ == cur), -1)
        self.panel_window(d, True, scrs[(i + 1) % len(scrs)], "max")

    def _fill_panel_menu(self):
        """Sous-menu « Vraies fenêtres » reconstruit à chaque ouverture (les écrans peuvent changer)."""
        m = self.panel_menu
        m.clear()
        scrs = QtGui.QGuiApplication.screens()
        for d in self.panel_docks():
            sub = m.addMenu(("🗗 " if d.objectName() in self.panel_wins else "") + d.windowTitle())
            a = sub.addAction("Dans la fenêtre principale")
            a.setCheckable(True)
            a.setChecked(d.objectName() not in self.panel_wins)
            a.triggered.connect(lambda *_, d=d: self.panel_window(d, False))
            sub.addAction("Fenêtre libre (à placer à la souris)").triggered.connect(
                lambda *_, d=d: self.panel_window(d, True, None, "normal"))
            for k, sc in enumerate(scrs):
                nm = f"Écran {k + 1} ({sc.name()}, {sc.size().width()}×{sc.size().height()})"
                sub.addAction(f"{nm} : agrandie").triggered.connect(
                    lambda *_, d=d, sc=sc: self.panel_window(d, True, sc, "max"))
                sub.addAction(f"{nm} : plein écran").triggered.connect(
                    lambda *_, d=d, sc=sc: self.panel_window(d, True, sc, "full"))
        m.addSeparator()
        m.addAction("📌 Tout raccrocher").triggered.connect(lambda *_: self.panel_attach_all())

    def panel_attach_all(self):
        for d in self.panel_docks():
            self.panel_window(d, False)

    def panel_state(self):
        """Pour config.json : {nom du panneau: {geo, mode, screen}}."""
        out = {}
        for key, win in self.panel_wins.items():
            scr = win.screen()
            out[key] = dict(geo=bytes(win.saveGeometry().toBase64()).decode(), mode=win.mode(),
                            screen=scr.name() if scr is not None else "")
        return out

    def panel_restore(self, st):
        if not isinstance(st, dict):
            return
        byname = {d.objectName(): d for d in self.panel_docks()}
        for key, v in st.items():
            d = byname.get(key)
            if d is None or not isinstance(v, dict):
                continue
            try:
                self.panel_window(d, True, None, "normal")
                win = self.panel_wins[key]
                win.restoreGeometry(QtCore.QByteArray.fromBase64(str(v.get("geo", "")).encode()))
                scr = next((s_ for s_ in QtGui.QGuiApplication.screens() if s_.name() == v.get("screen")), None)
                if v.get("mode") == "full" and scr is not None:
                    win.setGeometry(scr.availableGeometry())
                    win.toggle_full()
                elif v.get("mode") == "max":
                    win.showMaximized()
            except Exception:  # noqa: BLE001 — écran débranché, géométrie illisible : on laisse le panneau ici
                self.panel_window(d, False)

    def wall_window_other_screen(self):
        """Le mur dans une fenêtre normale qui occupe l'autre écran (la barre des tâches reste visible)."""
        scr = self._other_screen()
        self.open_wall()
        if scr is None:
            self.set_status("Un seul écran détecté : branche le 2ᵉ écran (ou détache le mur et place-le à la souris).")
            return
        if self.wall_is_fullscreen():
            self.wall_fullscreen(False)
        self.wall_detach(True)
        self.dock_wall.setGeometry(scr.availableGeometry())
        self.dock_wall.raise_()
        self.set_status("Mur sur l'autre écran. « 📌 Raccrocher » le remet à côté du spectre ; F11 = plein écran.")

    def wall_other_screen(self):
        scr = self._other_screen()
        self.open_wall()
        if scr is None:
            self.set_status("Un seul écran détecté : le mur est ouvert en fenêtre (F11 pour le plein écran).")
            return
        self.wall_fullscreen(True, scr)

    def _wf_show(self, on):
        self.wf.setVisible(bool(on))
        self.wf_hint.setVisible(not on)
        if on and getattr(self, "dock_wf", None) is not None and not self.dock_wf.isVisible():
            self.dock_wf.show()
            QtCore.QTimer.singleShot(0, self._middle_sizes)      # bandeau sous le spectre, pas la moitié

    # ------------------------------------------------------- statuts / priorités
    def is_keep_on(self, name):
        return bool(name) and any(s["name"] == name and s.get("on") for s in self.statuses)

    def freq_prio(self, w):
        """Priorité des alarmes d'une fréquence = celle de son groupe (2 critique, 1 normale, 0 info)."""
        sc = self.scene_by_name(w["scene"]) if w["scene"] else None
        if sc is not None and w["group"]:
            for g in sc["groups"]:
                if g["name"] == w["group"]:
                    return int(g.get("prio", 1))
        return 1

    def set_prio(self, key, prio):
        sc = self.scene_by_name(key[0])
        if sc is None:
            return
        for g in sc["groups"]:
            if not key[1] or g["name"] == key[1]:
                g["prio"] = int(prio)
        self.rebuild_tree()
        what = f"« {key[1]} »" if key[1] else f"tous les groupes de « {key[0]} »"
        self.set_status(f"Priorité des alarmes pour {what} : {ALARM_PRIO[int(prio)]}."
                        + (" Critique = son répété toutes les 10 s jusqu'à acquittement." if prio == 2 else "")
                        + (" Info = pas de son." if prio == 0 else ""))

    def group_row(self, scene, group):
        sc = self.scene_by_name(scene) if scene else None
        return next((g for g in sc["groups"] if g["name"] == group), None) if sc is not None and group else None

    def rx_of(self, w):
        """Appareil d'une fréquence (clé de profil) : le sien s'il en a un, sinon celui de son groupe, sinon "".
        Facultatif partout : sans appareil, ce sont les réglages par défaut de la coordination qui comptent."""
        if rx_profile(w.get("rx")) is not None:
            return w["rx"]
        g = self.group_row(w.get("scene"), w.get("group"))
        rxs = self.group_rxs(g)
        return rxs[0] if rxs else ""             # plusieurs appareils dans le groupe : le 1er = celui par défaut

    @staticmethod
    def group_rxs(g):
        """Appareils d'un groupe (liste de clés valides ; un groupe peut en avoir plusieurs : QLX-D + PSM 1000…)."""
        if g is None:
            return []
        r = g.get("rx")
        r = [r] if isinstance(r, str) else list(r or [])
        return [k for k in r if rx_profile(k) is not None]

    def _set_rxs(self, key, fn):
        sc = self.scene_by_name(key[0])
        if sc is None:
            return
        for g in sc["groups"]:
            if not key[1] or g["name"] == key[1]:
                rxs = fn(self.group_rxs(g))
                if rxs:
                    g["rx"] = rxs
                else:
                    g.pop("rx", None)
        self.rebuild_tree()
        what = f"« {key[1]} »" if key[1] else f"tous les groupes de « {key[0]} »"
        cur = self._cur_rxs(key)
        self.set_status(f"📻 Appareils de {what} : {' + '.join(rx_short(k) for k in cur) if cur else 'aucun'}. Ils "
                        "servent à la coordination (écart, filtre, tolérances) ; une fréquence qui a son propre appareil "
                        "garde le sien.")

    def set_group_rx(self, key, rx):
        """📻 Un seul appareil pour le groupe (ou tous les groupes d'une scène) ; rx "" = aucun."""
        self._set_rxs(key, lambda _old: [rx] if rx else [])

    def toggle_group_rx(self, key, rx, on):
        """📻 Ajoute / retire un appareil d'un groupe (plusieurs possibles : coordination entre appareils)."""
        self._set_rxs(key, lambda old: (old + [rx] if rx not in old else old) if on else [k for k in old if k != rx])

    def pick_library_rx(self, key):
        """📚 Bibliothèque -> les appareils choisis deviennent des profils (avec leur bande) et rejoignent le groupe."""
        dlg = RxLibraryDialog(self, pick=True)
        dlg.exec()
        names = getattr(dlg, "added", None) or []
        keys = [k for k, n, _d, _w in RX_CUSTOM if n in names]
        for k in keys:
            self.toggle_group_rx(key, k, True)
        return keys

    def _cur_rxs(self, key):
        sc = self.scene_by_name(key[0])
        if sc is None:
            return []
        rs = [self.group_rxs(g) for g in sc["groups"] if not key[1] or g["name"] == key[1]]
        return rs[0] if rs and all(r == rs[0] for r in rs) else []

    @staticmethod
    def prio_mark(g):
        return {2: "  ❗", 0: "  🔕"}.get(int(g.get("prio", 1)), "")

    # ------------------------------------------------------- alarmes
    def _alarm_reset(self, w, now):
        """La fréquence n'est plus évaluée (hors couche, pas de mesure…) : ses alarmes s'arrêtent."""
        w["free_since"] = None
        w["absent"] = False
        fk = int(round(w["freq"] * 1000))
        self.alarms.clear(("CONFLIT", fk), now)
        self.alarms.clear(("ABSENT", fk), now)

    def _alarm_sound(self, prio):
        if prio < 0:
            return
        if prio >= 2 and getattr(self, "dock_alarm", None) is not None:
            was = self.dock_alarm.isVisible()
            self.dock_alarm.show()
            self.dock_alarm.raise_()
            if not was:
                QtCore.QTimer.singleShot(0, self._middle_sizes)
        if prio < 1 or not self.alert_chk.isChecked() or snooze_left(self.snooze_until, time.time()):
            return
        if self.sound.cfg.get("style") == "beep":
            QtWidgets.QApplication.beep()
            QtCore.QTimer.singleShot(260, QtWidgets.QApplication.beep)
            if prio >= 2:
                QtCore.QTimer.singleShot(520, QtWidgets.QApplication.beep)
            return
        self.sound.alarm(prio)

    def snooze(self, secs):
        """🔕 Coupe le son des alarmes pendant secs secondes (0 = remettre le son tout de suite)."""
        self.snooze_until = time.time() + secs if secs else 0.0
        self.snooze_btn.setText(f"🔕 jusqu'à {datetime.fromtimestamp(self.snooze_until):%H:%M}" if secs else "🔕 Silence")
        self.set_status(f"🔕 Alarmes muettes pendant {secs // 60} min (toujours affichées et envoyées au téléphone)."
                        if secs else "🔔 Son des alarmes rétabli.")

    def _alarm_tick(self):
        """Chaque seconde : nettoie les alarmes de fréquences supprimées, rejoue les critiques, met l'écran à jour."""
        now = time.time()
        sim = self.simulated()                    # 8.1 : source simulée ? (marque 🧪 partout)
        if sim != self.alarms.sim:
            self.alarms.sim = sim
            self.update_title()
        if self.alarms.active:
            fks = {int(round(w["freq"] * 1000)) for w in self.watch}
            for key in [k for k in self.alarms.active if k[0] not in ("APPAREIL", "FORT") and k[1] not in fks]:
                self.alarms.clear(key, now)
        if self.snooze_until and now >= self.snooze_until:
            self.snooze(0)
        for a in self.alarms.due_repeat(now):
            self._alarm_sound(a["prio"])
        self._notify_new_alarms()
        self._festival_tick(now)
        if now >= getattr(self, "_beat_next", 0.0):
            self._beat_next = now + GUARD_BEAT_S
            guard_beat()
            self._reap_dialogs(now)
        self.update_home()
        try:                                          # 7.59 : propositions + légende du spectre
            self._hints_tick(now)
            self.spec_legend.refresh()
        except Exception:  # noqa: BLE001
            pass
        self._planning_tick(now)
        self._ezrf_tick(now)
        self._sites_tick(now)
        self._net_tick(now)
        reason = getattr(self, "_diag_pending", None)
        if reason:
            self._diag_pending = None
            try:
                self.dump_diag(reason, quiet=True)
            except Exception:  # noqa: BLE001 — le diagnostic ne doit jamais faire tomber l'appli
                pass
        self._web_ack_pending()
        self._web_hunt_pending()
        self._web_terrain_pending()
        self._web_techreq_pending()
        self._web_tech_pending()
        self.undo_track()                          # ↶ : met de côté l'état d'avant chaque changement
        self.history_track()                       # 🕘 7.63 : qui a changé quoi
        self._map_web_tick(now)                    # 🗺 7.64 : image de la carte pour le téléphone
        if self.web is not None:
            self._web_json = self.web_json()
            if self.web_cfg["views"].get("tech") and self.web.watching(("tech",)):
                try:
                    self._tech_json = json.dumps(self.tech_state(), ensure_ascii=False).encode("utf-8")
                except Exception:  # noqa: BLE001 — la page Tech ne doit jamais faire tomber l'appli
                    pass
            if self.web_cfg["views"].get("spectre") or self.web_cfg["views"].get("waterfall"):
                if self.web.watching(("spectre", "waterfall", "terrain")):   # seulement si quelqu'un regarde
                    self._web_spec = self.web_spec_json()
        if self.recorder is not None:
            self.recorder.maybe_flush(now)
            if self.recorder.error:
                self.set_status(f"⚠ Enregistrement arrêté : {self.recorder.error}")
                self.rec_chk.setChecked(False)
        self.refresh_alarms()

    def refresh_alarms(self):
        n_un, n_act, _pm = self.alarms.counts()
        th = self.theme
        if n_un:
            self.alarm_btn.setText(f"🔔 {n_un}")
            self.alarm_btn.setStyleSheet("QPushButton{background:%s;color:%s;font-weight:bold;}"
                                         % (th["st_occ"], contrast_text(th["st_occ"])))
        elif n_act:
            self.alarm_btn.setText(f"🔕 {n_act}")
            self.alarm_btn.setStyleSheet("QPushButton{background:%s;color:%s;}" % (th["st_weak"], contrast_text(th["st_weak"])))
        else:
            self.alarm_btn.setText("🔔")
            self.alarm_btn.setStyleSheet("")
        if not self.alarm_table.isVisible():
            return                      # panneau caché : seul le bouton 🔔 est tenu à jour
        self.alarm_lbl.setText(f"{n_un} à acquitter · {n_act} en cours · {len(self.alarms.done)} terminée(s)")
        now = time.time()
        items = self.alarms.listing()[:200]
        t, base = self.alarm_table, th["ui_base"]
        t.setRowCount(len(items))
        for r, a in enumerate(items):
            active = a["t_end"] is None
            end = now if active else a["t_end"]
            state = ("à acquitter" if not a["acked"] else "acquittée") if active else "terminée"
            why_tip = self.alarm_why_text(a, html=False)
            vals = (ALARM_PRIO.get(a["prio"], "?"), a["kind"], a["name"], f'{a["freq"]:.3f}' if a["freq"] else "—",
                    fmt_clock(a["t0"]), fmt_dur(end - a["t0"]), self.lvl(a["level"], suffix=True),
                    " · ".join(x for x in (a["layer"], "" if a["kind"] == "ABSENT" else a.get("info", "")) if x),
                    state)
            for c, v in enumerate(vals):
                it = self._item(v, False, c in (3, 6))
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, a["id"])
                if active and not a["acked"]:
                    bg = blend(th["st_occ"], base, 0.9 if a["prio"] >= 2 else 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif active:
                    bg = blend(th["st_weak"], base, 0.35)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                else:
                    it.setForeground(QtGui.QColor(th["st_none"]))
                it.setToolTip(why_tip)
                t.setItem(r, c, it)
        self._alarm_why_update()

    def alarm_explain(self, a):
        """{measured, deduced, advice} de l'alarme a, avec le niveau et le seuil dans l'unité de l'appli."""
        thr = None
        if a.get("kind") == "TROP FORT":
            thr = self.strong_spin.value()
        elif a.get("freq"):
            w = next((w_ for w_ in self.watch if abs(w_["freq"] - a["freq"]) < 1e-6), None)
            thr = w.get("ethr") if w is not None else None
        return alarm_explain(a, time.time(), self.lvl(a["level"], True) if a.get("level") is not None else "",
                             self.lvl(thr, True) if thr is not None else "")

    def alarm_why_text(self, a, html=True):
        e = self.alarm_explain(a)
        rows = (("Mesuré", e["measured"]), ("Cause probable", e["deduced"]), ("À faire", e["advice"]))
        if html:
            return "<br>".join(f"<b>{_hesc(TR(k))} :</b> {_hesc(TR(v))}" for k, v in rows if v)
        return "\n".join(f"{TR(k)} : {TR(v)}" for k, v in rows if v)

    def _alarm_why_update(self):
        lab = getattr(self, "alarm_why", None)
        if lab is None:
            return
        ids = self._alarm_selected_ids()
        items = self.alarms.listing()
        a = next((x for x in items if ids and x["id"] == ids[0]), None)
        if a is None:
            a = next((x for x in items if x["t_end"] is None and not x["acked"]), None)
        if a is None:
            lab.setVisible(False)
            return
        lab.setText(f"<b>{_hesc(a['kind'])} — {_hesc(a.get('name') or '')}</b><br>" + self.alarm_why_text(a))
        lab.setVisible(True)

    def _alarm_selected_ids(self):
        rows = sorted({i.row() for i in self.alarm_table.selectedIndexes()})
        out = []
        for r in rows:
            it = self.alarm_table.item(r, 0)
            if it is not None and it.data(Qt.ItemDataRole.UserRole) is not None:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

    def ack_selected(self):
        ids = self._alarm_selected_ids()
        n = sum(1 for i in ids if self.alarms.ack(i))
        self.refresh_alarms()
        self.set_status(f"{n} alarme(s) acquittée(s)." if n else "Sélectionne une alarme en cours à acquitter.")

    def _web_ack_pending(self):
        """Acquittements faits depuis un téléphone (page web, code PIN)."""
        n = 0
        while True:
            try:
                target = self._web_acks.get_nowait()
            except queue.Empty:
                break
            n += self.alarms.ack_all() if target == "all" else int(self.alarms.ack(target))
        if n:
            self.refresh_alarms()
            self.set_status(f"📱 {n} alarme(s) acquittée(s) depuis la page web.")
        return n

    def _web_hunt_pending(self):
        """🔎 Chasse commandée depuis un téléphone (vue Chasse de la page web) : le téléphone bippe, le PC se tait."""
        while True:
            try:
                c = self._web_hunts.get_nowait()
            except queue.Empty:
                return
            if c["action"] == "start":
                self.open_hunt(c["f"])
                h = self._hunt
                h.go_btn.setChecked(False)
                h.f_spin.setValue(c["f"])
                h.span_spin.setValue(c["span"])
                h.follow_chk.setChecked(c["follow"])
                ids = self.dev_list()                    # la page envoie le rang dans la liste des tinySA
                h.dev_combo.setCurrentIndex(max(0, h.dev_combo.findData(ids[max(0, min(int(c["dev"]), len(ids) - 1))])))
                h.mute_chk.setChecked(True)
                h.best = None
                h.go_btn.setChecked(True)
                self.set_status(f"📱 Chasse lancée depuis un téléphone sur {c['f']:.3f} MHz.")
            elif c["action"] == "mark":                    # 🗺 « je suis ici » touché sur le plan
                pt = self.map_mark_rel(c["x"], c["y"])
                self.set_status(TR("📱 Point de chaleur noté : {} dBm.").format(f"{pt['level']:.1f}") if pt else
                                TR("📱 Point refusé : la chasse ne tourne pas."))
            elif c["action"] == "unmark":
                f = self._hunt.f_spin.value() if self._hunt is not None else None
                hs = self.map_cfg["heat"]
                for i in range(len(hs) - 1, -1, -1):
                    if f is None or abs(hs[i]["f"] - f) <= 0.05:
                        hs.pop(i)
                        break
                self.map_scene().sync_heat()
                self._map_png_t = 0.0
            elif self._hunt is not None and c["action"] == "stop":
                self._hunt.go_btn.setChecked(False)
                self.set_status("📱 Chasse arrêtée depuis un téléphone.")
            elif self._hunt is not None:
                self._hunt._reset_best()

    def _site_mh_FL(self, scene):
        """Max hold de la scène depuis le dernier « nouveau scan » (toutes ses bandes) -> (F, L) ou (None, None)."""
        bands = self.site_mh.get(scene) or {}
        if not bands:
            return None, None
        segs = sorted(bands.values(), key=lambda x: float(x[0][0]))
        F, L = np.concatenate([x[0] for x in segs]), np.concatenate([x[1] for x in segs])
        o = np.argsort(F, kind="stable")
        return F[o], L[o]

    def terrain_save(self, scenes, label=""):
        """💾 Garde le scan en cours (max hold) de chaque scène comme un scan à part (« Scène · étiquette ») : on peut en
        garder plusieurs par scène, ils comptent tous pour la fusion et la coordination."""
        done, empty = [], []
        hhmm = datetime.now().strftime("%H:%M")
        for sc in scenes:
            F, L = self._site_mh_FL(sc)
            if F is None:
                empty.append(sc)
                continue
            name = snapshot_name(sc, label, {d["name"] for d in self.site_scans}, hhmm)
            t0 = self._site_mh_t0.get(sc)
            rbw, est = self.scan_rbw(F)
            self.site_scans.append(site_scan_doc(name, F, L, time.time(), scene=sc,
                                                 dur=time.time() - t0 if t0 else None, rbw=rbw, rbw_est=est))
            done.append(name)
        if done:
            self._bump()
            self.update_site_curve()
        msg = (f"💾 Gardé : {', '.join(done)}" if done else "") + (
            (" · " if done else "") + f"rien à garder pour {', '.join(empty)} (pas encore de balayage)" if empty else "")
        return msg or "Aucune scène : dis d'abord où est ce tinySA."

    def terrain_reset(self, scenes):
        """↺ Nouveau scan ici : le max hold de ces scènes repart de zéro (les scans gardés ne bougent pas)."""
        for sc in scenes:
            self.site_mh.pop(sc, None)
            self._site_mh_t0.pop(sc, None)
            self._site_base[sc] = next((d for d in self.site_scans if d["name"] == sc), None)
        return f"↺ Nouveau scan pour : {', '.join(scenes)}" if scenes else "Aucune scène : dis d'abord où est ce tinySA."

    # ------------------------------------------------- 🛠 page web Tech (gérer le serveur depuis un téléphone)
    def _web_techreq_pending(self):
        """Demandes d'accès Tech : le PC demande l'accord (fenêtre non bloquante)."""
        while True:
            try:
                r = self._web_techreq.get_nowait()
            except queue.Empty:
                return
            box = QtWidgets.QMessageBox(self)
            box.setIcon(QtWidgets.QMessageBox.Icon.Question)
            box.setWindowTitle("Accès Tech")
            box.setText(f"🛠 « {r['name']} » ({r['addr']}) demande l'accès Tech : démarrer / arrêter, changer les seuils, "
                        "les fréquences et les tinySA depuis la page web.\n\nL'autoriser ?")
            box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
            box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
            box.setModal(False)

            def done(btn, r=r, box=box):
                ok = box.standardButton(btn) == QtWidgets.QMessageBox.StandardButton.Yes
                if self.web is not None:
                    self.web.tech_decide(r["token"], ok)
                self.set_status(f"🛠 Accès Tech {'accordé à' if ok else 'refusé pour'} « {r['name']} » ({r['addr']}).")
                if box in self._tech_boxes:
                    self._tech_boxes.remove(box)
            box.buttonClicked.connect(done)
            self._tech_boxes.append(box)
            box.show()
            self._alarm_sound(1)

    def _web_tech_pending(self):
        while True:
            try:
                c = self._web_tech.get_nowait()
            except queue.Empty:
                return
            self.history_track()                   # 🕘 ce qui précède est au PC ; la commande, au téléphone
            try:
                msg = self.tech_do(c)
            except Exception as e:  # noqa: BLE001 — une commande ratée ne doit pas faire tomber l'appli
                msg = f"⚠ impossible : {e}"
            self.history_track(TR("📱 {}").format(c.get("by") or "?"))
            self._tech_msg = f"{time.strftime('%H:%M:%S')} · {c.get('by', '?')} : {msg}"
            self.set_status(f"🛠 {self._tech_msg}")

    def _tech_w(self, key):
        return next((w for w in self.watch if int(round(w["freq"] * 1000)) == key), None)

    def tech_do(self, c):
        """Exécute une commande Tech (déjà vérifiée par tech_request) -> message pour la page."""
        a = c["action"]
        names = names_ = [st["name"] for st in self.statuses]
        if a == "run":
            if c["on"] and not self.is_running():
                self.toggle_run(auto=True)
                return "▶ surveillance lancée" if self.is_running() else "⚠ démarrage impossible (voir le PC)"
            if not c["on"] and self.is_running():
                self.toggle_run()
                return "■ surveillance arrêtée"
            return "rien à faire"
        if a == "snooze":
            self.snooze(c["min"] * 60)
            return f"🔕 silence {c['min']} min" if c["min"] else "🔔 son rétabli"
        if a == "ack_all":
            n = self.alarms.ack_all()
            self.refresh_alarms()
            return f"✔ {n} alarme(s) acquittée(s)"
        if a == "thr":
            self.set_thr_auto(False)                    # seuil tapé depuis la page Tech = seuils fixes
            self.thr_spin.setValue(c["occ"])
            self.weak_chk.setChecked(c["weak_on"])
            if c["weak"] is not None:
                self.weak_spin.setValue(c["weak"])
            if c["absent"] is not None:
                self.absent_spin.setValue(int(c["absent"]))
            return "seuils appliqués"
        if a == "watch_add":
            if self._tech_w(int(round(c["freq"] * 1000))) is not None:
                return f"{c['freq']:.3f} MHz déjà dans la liste"
            st = c["status"] if c["status"] in names else ""
            self._append_watch(c["name"] or f"{c['freq']:.3f}", c["freq"], st, None, c["scene"], c["group"])
            self.sort_watch()
            self.rebuild_tree()
            self.rebuild_watch_table()
            self._update_markers()
            return f"＋ {c['name'] or c['freq']} ({c['freq']:.3f} MHz) ajoutée"
        if a == "quick_add":
            items, ign = parse_quick_entry(c["text"])
            have = {int(round(w["freq"] * 1000)) for w in self.watch}
            items = [it for it in items if int(round(it["freq"] * 1000)) not in have]
            if not items:
                return "aucune nouvelle fréquence trouvée dans le texte" + (" (déjà dans la liste ?)" if not ign else "")
            names = quick_names(items, "HF", {w["name"] for w in self.watch})
            st = c["status"] if c["status"] in names_ else ""
            if c["scene"]:
                self.ensure_group(c["scene"], c["group"])
            for it, nm in zip(items, names):
                self._append_watch(nm, it["freq"], st, None, c["scene"], c["group"] if c["scene"] else "")
            self.sort_watch()
            self.rebuild_tree()
            self.rebuild_watch_table()
            self._update_markers()
            self.undo_track()
            return f"⌨ {len(items)} micro(s) ajouté(s) : " + ", ".join(names[:6]) + (" …" if len(names) > 6 else "")
        if a == "sugg_close":
            self._tech_sugg = None
            return ""
        if a in ("suggest", "replace"):
            w = self._tech_w(c["key"])
            if w is None:
                return "fréquence introuvable (liste changée entre-temps ?)"
            if a == "replace":
                if self._tech_w(int(round(c["f"] * 1000))) is not None:
                    return f"{c['f']:.3f} MHz déjà dans la liste"
                old = w["freq"]
                self.replace_watch(w, c["f"], "🆘 remplacement depuis le téléphone")
                self._tech_sugg = None
                return f"🆘 {w['name']} : {old:.3f} → {c['f']:.3f} MHz · règle l'émetteur ET le récepteur"
            args = self.replace_args(w)              # 7.62 : calcul en arrière-plan (le PC ne fige jamais)
            self._tech_sugg = dict(key=c["key"], name=w["name"], freq=round(w["freq"], 4), cands=[], busy=True)

            def done(sg, err, w=w, key=c["key"]):
                if self._tech_sugg is None or self._tech_sugg.get("key") != key:
                    return                            # fermé ou autre micro demandé entre-temps
                cands = [] if err is not None else self.replace_decorate(args, sg, w)
                self._tech_sugg = dict(key=key, name=w["name"], freq=round(w["freq"], 4), busy=False,
                                       cands=[dict(f=x["f"], d=round(x["d"] * 1000),
                                                   level=self.lvl(x["level"], suffix=True) if x["level"] is not None else "",
                                                   tag=TR(x["tag"]) if x["tag"] else "") for x in cands])
                self._tech_msg = (f"🆘 {len(cands)} proposition(s) pour {w['name']}" if cands
                                  else f"🆘 rien de libre et compatible pour {w['name']}")
            self.run_heavy(lambda: self.replace_compute(args, 3), done)
            return f"🆘 calcul des propositions pour {w['name']}…"
        if a in ("watch_edit", "watch_del", "mute"):
            w = self._tech_w(c["key"])
            if w is None:
                return "fréquence introuvable (liste changée entre-temps ?)"
            if a == "mute":
                self.set_muted([w], c["on"], quiet=True)
                return f"💤 {w['name']} éteint (je sais)" if c["on"] else f"🔔 {w['name']} rallumé"
            if a == "watch_del":
                self.watch.remove(w)
                self.rebuild_watch_table()
                self._update_markers()
                return f"🗑 {w['name']} retirée"
            if c["name"]:
                w["name"] = c["name"]
            if c["status"] is not None:
                w["status"] = c["status"] if c["status"] in names else ""
            if c["freq"] is not None and abs(c["freq"] - w["freq"]) > 1e-6:
                if self._tech_w(int(round(c["freq"] * 1000))) is not None:
                    return f"{c['freq']:.3f} MHz déjà dans la liste"
                self.set_watch_freq(w, c["freq"])
            self.rebuild_watch_table()
            self._update_markers()
            return f"✏ {w['name']} modifiée"
        if a in ("dev_scenes", "identify"):
            ids = self.dev_list()
            if c["dev"] >= len(ids):
                return "tinySA inconnu"
            d = ids[c["dev"]]
            if a == "identify":
                return f"👋 {self.dev_name(d)} clignote" if self.identify_device(d) else "lance d'abord la surveillance"
            self.set_dev_scenes(d, c["scenes"])
            return f"📡 {self.dev_name(d)} : " + (", ".join(c["scenes"]) or "tout le site")
        if a == "state":
            if c["name"] and self.state_by_name(c["name"]) is None:
                return f"état « {c['name']} » inconnu"
            n_off = self.apply_state(c["name"])
            return f"📸 état « {c['name']} » ({n_off} en pause)" if c["name"] else "📸 tout actif"
        if a == "save":
            if self.show_path:
                self.save_show_to(self.show_path)
                return f"💾 show enregistré ({os.path.basename(self.show_path)})"
            self._save_config()
            return "💾 réglages enregistrés (pas encore de fichier show : enregistre-le une fois sur le PC)"
        return "commande inconnue"

    def tech_state(self):
        """État complet pour la page Tech."""
        ids, lm, run = self.dev_list(), self.live_mask(), self.is_running()
        demo = self.demo_chk.isChecked()
        devs = []
        for i, (d, addr, _o) in enumerate(self.dev_slots()):
            a_ = ("démo" if demo else (self.port1() or "—")) if d == 0 else (self.resolve_addr(addr) or "—")
            devs.append(dict(rank=i, ord=dev_ord(d), name=self.dev_name(d), addr=a_, live=bool(run and lm[d]),
                             cycle=round(float(self.dev_cycle.get(d, 0.0)), 1), scenes=list(self.dev_scenes.get(d, []))))
        rows = []
        for w in self.watch:
            txt, _tone, col = self.sig_view(w)
            rows.append(dict(key=int(round(w["freq"] * 1000)), name=w["name"], freq=round(w["freq"], 4),
                             status=w["status"] or "", scene=w["scene"], group=w["group"], sig=txt, color=col,
                             muted=bool(w.get("muted")),
                             level=self.lvl(w["level"], suffix=True) if w["level"] is not None else ""))
        clients = []
        if self.web is not None:
            for e in self.web.client_list():
                clients.append(dict(name=e["name"], addr=e["addr"], view=e.get("view", ""), online=e["online"],
                                    tech=e.get("tech") or ""))
        return dict(ver=APP_VER, running=run, demo=demo, msg=self._tech_msg, ndev=len(ids),
                    snooze=int(snooze_left(self.snooze_until, time.time())),
                    thr=dict(occ=self.thr_spin.value(), weak=self.weak_spin.value(), weak_on=self.weak_chk.isChecked(),
                             absent=self.absent_spin.value()),
                    statuses=[dict(name=st["name"], on=bool(st.get("on")), free=bool(st.get("free")))
                              for st in self.statuses],
                    scenes=[dict(name=sc["name"], groups=[g["name"] for g in sc["groups"]]) for sc in self.scenes],
                    devs=devs, watch=rows, clients=clients, alarms=len(self.alarms.active),
                    show=self.show_meta.get("name", ""), saved=bool(self.show_path),
                    states=[x["name"] for x in self.states], state_cur=self.state_cur, sugg=self._tech_sugg)

    def _web_terrain_pending(self):
        """🎒 Commandes de la vue Terrain (téléphone) : où est le tinySA volant, garder / effacer des scans."""
        while True:
            try:
                c = self._web_terrain.get_nowait()
            except queue.Empty:
                return
            ids = self.dev_list()
            dev = ids[max(0, min(int(c["dev"]), len(ids) - 1))]     # la page envoie le rang dans la liste
            mine = list(self.dev_scenes.get(dev, []))
            if c["action"] == "assign":
                self.set_dev_scenes(dev, c["scenes"])
                self._terrain_msg = (f"📡 {self.dev_name(dev)} : " + (", ".join(c["scenes"]) or "aucune scène"))
            elif c["action"] == "reset":
                self._terrain_msg = self.terrain_reset(mine)
            elif c["action"] == "save":
                self._terrain_msg = self.terrain_save(c["scenes"] or mine, c["label"])
            elif c["action"] == "delete":
                n0 = len(self.site_scans)
                self.site_scans = [d for d in self.site_scans if d["name"] != c["name"]]
                if self._site_base.get(c["name"]) is not None:      # scan continu effacé : il repart de zéro
                    self._site_base[c["name"]] = None
                    self.site_mh.pop(c["name"], None)
                if len(self.site_scans) < n0:
                    self._bump()
                    self.update_site_curve()
                self._terrain_msg = f"🗑 Effacé : {c['name']}"
            self.set_status(f"📱 {self._terrain_msg}")

    def terrain_state(self):
        """État de la vue Terrain pour la page web."""
        now = time.time()
        names = list(dict.fromkeys([x["name"] for x in self.scenes] + [x for v in self.dev_scenes.values() for x in v]))
        devs = [dict(label=f"{dev_ord(d)} tinySA · {self.dev_name(d)}",
                     live=bool(self.is_running() and d < len(self.dev_live) and self.dev_live[d]),
                     scenes=list(self.dev_scenes.get(d, []))) for d in self.dev_list()]
        assigned = {x for v in self.dev_scenes.values() for x in v}
        live = {}
        for sc, bands in self.site_live.items():
            mh = self.site_mh.get(sc) or {}
            if bands:
                live[sc] = dict(age=int(now - max(x[2] for x in bands.values())), bands=len(mh))
        saved = [dict(name=d["name"], scene=site_doc_scene(d), t=d["t"], n=len(d["f"]), lo=d["f"][0], hi=d["f"][-1],
                      auto="scene" not in d and d["name"] in assigned) for d in sorted(self.site_scans, key=lambda d: (site_doc_scene(d), -d["t"]))]
        return dict(devs=devs, scenes=names, live=live, saved=saved, msg=self._terrain_msg)

    def hunt_state(self):
        """État de la chasse pour la page web (vue Chasse)."""
        h = self._hunt
        ids = self.dev_list()
        devs = [f"{dev_ord(d)} tinySA · {self.dev_name(d)}" for d in ids]
        mp = dict(map=bool(self._map_png), map_t=round(self._map_png_t, 1), marks=self.map_marks_rel())
        if h is None:
            return dict(on=False, f=None, span=2.0, follow=False, dev=len(ids) - 1, devs=devs, level=None, **mp)
        on = h.go_btn.isChecked()
        return dict(on=on, f=round(h.f_spin.value(), 4), span=h.span_spin.value(), follow=h.follow_chk.isChecked(),
                    dev=ids.index(int(h.dev_combo.currentData() or 0))
                    if int(h.dev_combo.currentData() or 0) in ids else 0, devs=devs,
                    level=None if (h.level is None or not on) else round(h.level, 1),
                    level_txt="" if h.level is None else self.lvl(h.level, suffix=True),
                    best=None if h.best is None else round(h.best, 1),
                    best_txt="" if h.best is None else self.lvl(h.best, suffix=True),
                    fpk=None if h.fpk is None else round(h.fpk, 4), msg="" if on else h.sub.text(), **mp)

    def ack_all_alarms(self):
        n = self.alarms.ack_all()
        self.refresh_alarms()
        self.set_status(f"{n} alarme(s) acquittée(s)." if n else "Aucune alarme à acquitter.")

    def purge_alarms(self):
        n = self.alarms.purge_done()
        self.refresh_alarms()
        self.set_status(f"{n} alarme(s) terminée(s) effacée(s).")

    def alarm_menu(self, pos):
        """7.62.1 : clic droit sur une alarme -> voir, remplacer le micro, chasser, d'où ça vient, acquitter."""
        r = self.alarm_table.rowAt(pos.y())
        if r < 0:
            return
        self.alarm_table.selectRow(r)
        it = self.alarm_table.item(r, 3)
        f = _num(it.text()) if it is not None else None
        w = self._alarm_watch()
        m = QtWidgets.QMenu(self)
        a_view = m.addAction("🔍 Voir sur le spectre") if f else None
        a_rep = m.addAction("🆘 Remplacer ce micro (3 propositions)…") if w is not None else None
        a_hunt = m.addAction("🔎 Chasser le brouilleur ici…") if f else None
        a_or = m.addAction("⚡ D'où ça peut venir ? (intermodulation)…") if f and self.coord_on else None
        xa = self.add_freq_actions(m, f, w)
        m.addSeparator()
        a_ack = m.addAction("✔ Acquitter")
        act = m.exec(self.alarm_table.viewport().mapToGlobal(pos))
        if act is None or self.run_freq_action(xa, act, f, w):
            return
        if act is a_view:
            self.view_range(f - 1.0, f + 1.0)
        elif act is a_rep:
            self.open_replace(w)
        elif act is a_hunt:
            self.open_hunt(f)
        elif act is a_or:
            self.open_intermod_for(f)
        elif act is a_ack:
            self.ack_selected()

    def alarm_jump(self, row, col):
        it = self.alarm_table.item(row, 3)
        f = _num(it.text()) if it is not None else None
        if f:
            self.view_range(f - 1.0, f + 1.0)

    def toggle_alarm_dock(self):
        d = self.dock_alarm
        if d.isVisible():
            d.hide()
        else:
            d.show()
            d.raise_()
            QtCore.QTimer.singleShot(0, self._middle_sizes)

    def _build_alarm_panel(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 4, 6, 4)
        self.alarm_table = QtWidgets.QTableWidget(0, 9)
        self.alarm_table.setHorizontalHeaderLabels(["Prio", "Type", "Nom", "MHz", "Depuis", "Durée", "Niveau",
                                                    "Scène › Groupe", "État"])
        hh = self.alarm_table.horizontalHeader()
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.alarm_table.verticalHeader().setVisible(False)
        self.alarm_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.alarm_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.alarm_table.cellDoubleClicked.connect(self.alarm_jump)
        self.alarm_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.alarm_table.customContextMenuRequested.connect(self.alarm_menu)
        self.alarm_lbl = self._elastic(QtWidgets.QLabel(""))
        b_ack = QtWidgets.QPushButton("✔ Acquitter la sélection")
        b_ack.setToolTip("Coupe le son de l'alarme sans l'effacer : elle reste affichée tant que la cause est là.")
        b_ack.clicked.connect(lambda *_: self.ack_selected())
        b_all = QtWidgets.QPushButton("✔✔ Tout acquitter")
        b_all.clicked.connect(lambda *_: self.ack_all_alarms())
        b_clr = QtWidgets.QPushButton("🗑 Effacer les terminées")
        b_clr.clicked.connect(lambda *_: self.purge_alarms())
        self.snooze_btn = QtWidgets.QToolButton()
        self.snooze_btn.setText("🔕 Silence")
        self.snooze_btn.setToolTip("Coupe le son des alarmes un moment (elles restent affichées et partent toujours\n"
                                   "sur le téléphone). Utile pendant un line check ou un changement de plateau.")
        self.snooze_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        sm_ = QtWidgets.QMenu(self.snooze_btn)
        for mins in (5, 15, 30, 60):
            sm_.addAction(f"🔕 {mins} min").triggered.connect(lambda *_, mins=mins: self.snooze(mins * 60))
        sm_.addSeparator()
        sm_.addAction("🔔 Remettre le son").triggered.connect(lambda *_: self.snooze(0))
        self.snooze_btn.setMenu(sm_)
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(self.alarm_lbl, 1)
        b_rep = QtWidgets.QPushButton("🆘 Remplacer ce micro")
        b_rep.setToolTip("Le micro de l'alarme choisie est brouillé ? 3 fréquences de remplacement libres et\n"
                         "compatibles (son appareil, sa bande, ton plan), puis un clic pour remplacer.")
        b_rep.clicked.connect(lambda *_: self.open_replace())
        bar.addLayout(self._flow(b_ack, b_all, b_rep, b_clr, self.snooze_btn), 2)
        lay.addLayout(bar)
        lay.addWidget(self.alarm_table, 1)
        # 7.56 : l'alarme choisie (sinon la plus récente à acquitter) expliquée : mesuré / cause probable / quoi faire
        self.alarm_why = QtWidgets.QLabel("")
        self.alarm_why.setWordWrap(True)
        self.alarm_why.setTextFormat(Qt.TextFormat.RichText)
        self.alarm_why.setToolTip("Ce qui est MESURÉ (sûr), ce qu'on en DÉDUIT (cause probable, à vérifier) et ce qu'on "
                                  "CONSEILLE.\nClique une alarme dans la liste pour l'expliquer.")
        self.alarm_why.setVisible(False)
        lay.addWidget(self.alarm_why)
        self.alarm_table.itemSelectionChanged.connect(lambda *_: self._alarm_why_update())
        tip = QtWidgets.QLabel("⚠ CONFLIT : un signal sur une fréquence « Doit rester libre » · ⚠ ABSENT : une fréquence "
                               "« Doit émettre » reste sans signal. Double-clic = voir sur le spectre. Priorité "
                               "(Critique ❗ / Normale / Info 🔕) : clic droit sur un groupe. Critique = son rejoué "
                               "jusqu'à acquittement (rythme : ⚙ Réglages › Son).")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        return w

    # ------------------------------------------------------- scans WSM / WWB
    def import_scan_as_ref(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Importer un scan (export WSM, WWB, CSV…)", "", "Scans (*.csv *.txt *.sdb3);;Tous les fichiers (*)")
        if not path:
            return
        try:
            F, L, info = parse_scan_text(decode_text(Path(path).read_bytes()))
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Scan illisible :\n{e}")
            return
        self._set_ref([(F, L)])
        self._save_ref_file(REF_PATH)
        self.showref_chk.setChecked(True)
        self.reeval()
        kind = {"wsm": "export WSM", "sdb3": "scan WWB natif (.sdb3)"}.get(info["fmt"], "fichier fréquence, niveau")
        self.set_status(f"Scan importé comme référence ({kind}) : {len(F)} points, {F[0]:.3f} – {F[-1]:.3f} MHz"
                        + (f" · {info['note']}" if info.get("note") else "")
                        + ". Courbe en pointillés ; coche « Seuil = courbe de référence + » pour l'utiliser.")

    def convert_wsm_wwb(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Scans exportés de WSM à convertir pour WWB", "", "Scans WSM (*.csv *.txt);;Tous les fichiers (*)")
        if not paths:
            return
        done, errs, notes = [], [], []
        for p in paths:
            try:
                text, info = wsm_to_wwb_text(decode_text(Path(p).read_bytes()))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p)} : {e}")
                continue
            dflt = Path(p).with_name(Path(p).stem + "_WWB.csv")
            if len(paths) == 1:
                out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le fichier pour WWB", str(dflt),
                                                               "CSV (*.csv)")
                if not out:
                    return
            else:
                out, k = dflt, 2
                while Path(out).exists():
                    out = dflt.with_name(f"{dflt.stem} ({k}).csv")
                    k += 1
            try:
                with open(out, "w", newline="", encoding="utf-8") as fh:
                    fh.write(text)
                done.append(os.path.basename(str(out)))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p)} : {e}")
                continue
            if info["fmt"] != "wsm":
                notes.append(os.path.basename(p))
        if done:
            msg = f"{len(done)} fichier(s) converti(s) pour WWB : {', '.join(done[:3])}" + (" …" if len(done) > 3 else "")
            if notes:
                msg += f" · ⚠ {len(notes)} ne ressemblai(en)t pas à un export WSM (converti comme « fréquence, niveau »)"
            self.set_status(msg + ". Dans WWB : importe-le comme un scan.")
        if errs:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Conversion impossible pour :\n" + "\n".join(errs))

    def export_scan_wwb(self):
        F, L = self.fresh_FL(use_max=True, any_age=True)
        if F is None:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        choice, ok = QtWidgets.QInputDialog.getItem(self, "Scan pour WWB", "Quelle courbe envoyer à WWB ?",
                                                    ["Max hold (recommandé)", "Balayage actuel"], 0, False)
        if not ok:
            return
        if choice.startswith("Balayage"):
            F, L = self.fresh_FL(use_max=False, any_age=True)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter le scan pour WWB",
                                                        f"scan_WWB_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write(wwb_scan_text(F, L))
            self.set_status(f"Scan WWB exporté ({len(F)} points, {F[0]:.3f} – {F[-1]:.3f} MHz) : {path}")
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")

    # ------------------------------------------------------- enregistrement / relecture
    def toggle_rec(self, on):
        if on:
            d = self.log_dir / "enregistrements" / f"{datetime.now():%Y%m%d_%H%M%S}"
            self.recorder = SweepRecorder(d)
            self._set_rec_lbl(f"Enregistrement → {d}")
            self.set_status("Enregistrement des balayages en cours (relecture : 🔧 Outils › ⏪ Relecture).")
        else:
            self._rec_stop()

    def _set_rec_lbl(self, txt):
        """Texte avec un chemin : coupures possibles après \\ et / (sinon un long chemin sans espace empêche la
        colonne de rétrécir : vu sous Windows en 7.12)."""
        self.rec_lbl.setText(str(txt).replace("\\", "\\\u200b").replace("/", "/\u200b"))

    def _rec_stop(self):
        if self._session is not None:            # case décochée pendant une session : la session s'arrête
            self._session_end(stop_rec=False)
        r, self.recorder = self.recorder, None
        if r is None:
            return
        r.close()
        self._set_rec_lbl(f"Enregistrement terminé : {r.n_sweeps} balayages" + (f" · ⚠ {r.error}" if r.error else "")
                             + f"  ({r.folder})")

    def open_replay(self):
        self._replay = ReplayDialog(self)
        self._replay.show()

    # ------------------------------------------------------- sessions enregistrées
    def session_default_name(self):
        return session_name(datetime.now().strftime("%Y-%m-%d_%H%M"), self.show_meta.get("name", ""))

    def rec_estimate_txt(self):
        pts = sum(self._npts(b) for b in self.bands if b.get("enabled"))
        mb = rec_mb_per_hour(pts, self.last_cycle if self.last_cycle else max(1.0, pts / 2000.0))
        return f"≈ {mb:.0f} Mo par heure" if mb else ""

    def _session_prompt(self, auto=False):
        """Avant ▶ Démarrer. -> False si l'utilisateur annule. auto (reprise du mode festival) : sans question,
        selon le dernier choix « enregistrer ou pas »."""
        if self.recorder is not None:
            return True                          # « 💾 Enregistrer les balayages » déjà coché à la main
        c = self.session_cfg
        name = self.session_default_name()
        if c.get("ask", True) and not auto:
            d = SessionDialog(self)
            if not d.exec():
                return False
            c.update(rec=d.rec, dir=d.dir_edit.text().strip(), ask=not d.never.isChecked())
            name = session_name(d.name_edit.text().strip() or name)
            self.sess_ask_chk.blockSignals(True)
            self.sess_ask_chk.setChecked(c["ask"])
            self.sess_ask_chk.blockSignals(False)
        if c.get("rec"):
            self._session_begin(Path(c.get("dir") or (self.log_dir / "enregistrements")) / name)
        return True

    def _session_meta(self, end=None):
        cfg = self._collect_config(full=False)
        return dict(app=APP_NAME, version=APP_VER, start=self._session_t0, end=end,
                    show=dict(self.show_meta), watch=cfg.get("watch", []), bands=cfg.get("bands", []),
                    statuses=cfg.get("statuses", []), scenes=cfg.get("scenes", []),
                    thr=round(float(self.thr_spin.value()), 1))

    def _write_session_json(self, path, end=None):
        try:
            (Path(path) / "session.json").write_text(
                json.dumps(self._session_meta(end), ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            self.set_status(f"⚠ Session : {e}")

    def _session_begin(self, path):
        base, k = Path(path), 2
        while base.exists() and any(base.iterdir()):
            base = Path(f"{path}_{k}")
            k += 1
        try:
            base.mkdir(parents=True, exist_ok=True)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Dossier de session impossible à créer :\n{e}\n\n"
                                          "Le scan démarre sans enregistrement.")
            return
        self._session, self._session_t0 = base, datetime.now().isoformat(timespec="seconds")
        self._write_session_json(base)
        self.recorder = SweepRecorder(base)
        self.rec_chk.blockSignals(True)
        self.rec_chk.setChecked(True)
        self.rec_chk.blockSignals(False)
        self._set_rec_lbl(f"💾 Session → {base}")
        self.set_status(f"💾 Session enregistrée dans {base}")

    def _session_log(self, vals, w):
        p = self._session / "journal.csv"
        try:
            new = not p.exists()
            with open(p, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
                wr = csv.writer(fh, delimiter=";")
                if new:
                    wr.writerow(SESSION_JOURNAL_HEAD)
                wr.writerow([datetime.now().strftime("%Y-%m-%d"), vals[0], vals[1], vals[2].replace(".", ","),
                             vals[3].replace(".", ","), vals[4], w.get("status", ""), w.get("scene", ""),
                             w.get("group", ""), w.get("band", ""), vals[6] if len(vals) > 6 else ""])
        except Exception:  # noqa: BLE001
            pass

    def _session_end(self, stop_rec=True):
        path, self._session = self._session, None
        if path is None:
            return
        self._last_session = path
        if stop_rec and self.recorder is not None:
            self._rec_stop()
            self.rec_chk.blockSignals(True)
            self.rec_chk.setChecked(False)
            self.rec_chk.blockSignals(False)
        self._write_session_json(path, end=datetime.now().isoformat(timespec="seconds"))
        self._set_rec_lbl(f"💾 Session enregistrée : {path}")
        self.set_status(f"💾 Session enregistrée : {path}  (⏪ Relecture › 📂 Ouvrir une session)")

    # ------------------------------------------------------- rapport de show
    def collect_report(self, v, last_n=None):
        """last_n : seulement les last_n derniers événements du journal (bilan du mode festival)."""
        now = datetime.now()
        t = self.log_table
        top = t.rowCount() if last_n is None else max(0, min(t.rowCount(), int(last_n)))
        events = [tuple(t.item(r, c).text() if t.item(r, c) is not None else "" for c in range(7))
                  for r in range(top - 1, -1, -1)]
        per = {}
        for e in events:
            d = per.setdefault(e[2], dict(events=0, conflicts=0, absents=0, occ=0))
            d["events"] += 1
            k = e[4].split(" (")[0]
            if k == "CONFLIT":
                d["conflicts"] += 1
            elif k == "ABSENT":
                d["absents"] += 1
            elif k == "OCCUPÉ":
                d["occ"] += 1
        rows = []
        for w in self.watch:
            d = per.get(f'{w["freq"]:.3f}', {})
            rows.append(dict(name=w["name"], freq=w["freq"], status=w["status"] or "", layer=self.layer_text(w),
                             max=w["max"], occ_pct=w["occw"].pct(), events=d.get("events", 0),
                             conflicts=d.get("conflicts", 0), absents=d.get("absents", 0), occ_events=d.get("occ", 0)))
        groups = []

        def add_group(label, ws, prio=""):
            if not ws:
                return
            ds = [per.get(f'{w["freq"]:.3f}', {}) for w in ws]
            groups.append(dict(name=label, n=len(ws), occ=sum(1 for w in ws if w["state"] == "occ"),
                               events=sum(d.get("events", 0) for d in ds), conflicts=sum(d.get("conflicts", 0) for d in ds),
                               absents=sum(d.get("absents", 0) for d in ds), prio=prio))

        for sc in self.scenes:
            for g in sc["groups"]:
                add_group(f'{sc["name"]} › {g["name"]}', [w for w in self.watch if w["scene"] == sc["name"] and w["group"] == g["name"]],
                          ALARM_PRIO.get(int(g.get("prio", 1)), ""))
            add_group(sc["name"] + " (sans groupe)", [w for w in self.watch if w["scene"] == sc["name"] and not w["group"]])
        add_group("Sans scène", [w for w in self.watch if not w["scene"]])
        F, L = self.fresh_FL(use_max=True, any_age=True)
        im = []
        if v.get("im") and self._im_dlg is not None:
            for r in getattr(self._im_dlg, "rows", [])[:200]:
                im.append(dict(f=r["f"], order=IM_NAMES.get(r["order"], str(r["order"])), text=r["text"], tname=r["tname"],
                               delta="" if r["delta"] is None else f'{r["delta"] * 1000:+.0f}', verdict=r["verdict"]))
        return dict(title=v["title"], venue=v["venue"], operator=v["operator"], notes=v["notes"],
                    generated=now.strftime("%d/%m/%Y %H:%M"),
                    duration=fmt_dur(time.time() - self._t_start) if self._t_start else "",
                    events=events, rows=rows, groups=groups, F=F, L=L, thr=self.thr_spin.value(), im=im,
                    app=f"{APP_NAME} {APP_VER}")

    def open_night_summary(self):
        """🌅 7.61 : rapport de tout le journal (résumé « en un coup d'œil » en tête), ouvert dans le navigateur."""
        now = datetime.now()
        site = self.notify_cfg.get("site", "") or self.show_meta.get("name", "")
        v = dict(title=f"Résumé du {now:%d/%m/%Y %H:%M}", venue=site, operator="", im=False, open=True, notes="")
        path = self.log_dir / "rapports" / f"resume_{now:%Y-%m-%d_%H%M}.html"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(TR.html(build_report_html(self.collect_report(v))), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            self.set_status(f"⚠ Résumé impossible : {e}")
            return None
        self.set_status(f"🌅 Résumé enregistré : {path}")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
        return path

    # ------------------------------------------------------------ 7.67 : scan de coord, dossier, perturbations
    def open_coord_scan(self):
        """📏 Scan pour la coordination : RBW fine, points calés dessus, gardé avec sa RBW."""
        d = getattr(self, "_cscan", None)
        if d is None:
            d = self._cscan = CoordScanDialog(self)
        d.show()
        d.raise_()
        d.activateWindow()
        return d

    def journal_rows(self, days=7):
        """Lignes des journaux automatiques des `days` derniers jours -> (lignes, nombre de fichiers lus)."""
        rows, n = [], 0
        try:
            files = sorted(self.log_dir.glob("journal_*.csv"))[-int(days):]
        except Exception:  # noqa: BLE001
            files = []
        for p_ in files:
            try:
                rows.extend(journal_csv_rows(p_.read_text(encoding="utf-8-sig", errors="replace")))
                n += 1
            except Exception:  # noqa: BLE001
                continue
        return rows, n

    def open_recurring(self):
        """🔁 Perturbations qui reviennent à la même heure, d'après les journaux de plusieurs jours."""
        RecurringDialog(self).exec()

    def prep_info(self):
        """Tout ce que met le dossier de préparation (show, plan, réglementation, TNT, scans, vérification)."""
        meta = self.show_meta or {}
        code = self.country_code()
        cname = dict(COUNTRIES).get(code, code or "")
        dates = prep_dates(meta.get("date_from"), meta.get("date_to"))
        rows = []
        for w in self.watch:
            rows.append(dict(scene=w.get("scene") or "", group=w.get("group") or "", name=w["name"], mhz=w["freq"],
                             status=w.get("status") or "", rx=rx_short(self.rx_of(w)) if self.rx_of(w) else "",
                             note=w.get("note") or "", off=bool(w.get("off") or w.get("muted")),
                             why="muted" if w.get("muted") else ("state" if w.get("off") else ""),
                             reg=(self.reg_tag(w["freq"], float(w.get("bw") or 0.0))
                                  if not self.is_keep_free(w.get("status")) else "")))
        order = [sc["name"] for sc in self.scenes]
        rows.sort(key=lambda r: (order.index(r["scene"]) if r["scene"] in order else len(order), r["group"], r["mhz"]))
        reg_lines = [x for x in reg_detail(code, TR).split("\n") if x.strip()] if reg_known(code) else []
        try:
            tn = self.tnt_measure_now()
            tnt = [dict(ch=r["ch"], lo=r["lo"], hi=r["hi"], state=r["state"]) for r in tn["rows"]
                   if r["state"] != "none"]
        except Exception:  # noqa: BLE001
            tnt = []
        scans = []
        for d in self.site_scans:
            i_ = site_scan_info(d)
            scans.append(dict(name=d["name"], scene=i_["scene"], lo=i_["lo"], hi=i_["hi"], rbw=i_["rbw"],
                              rbw_est=i_["rbw_est"], date=_fmt_ts(i_["t"], "%d/%m/%Y %H:%M")))
        plan = None
        if self.coord_on:
            try:
                ws = [w for w in self.watch if not w.get("off")]
                if 0 < len(ws) <= 120:
                    dflt = dict(sep=self.plan_opts.get("sep", 300) / 1000.0, filt=float(self.plan_opts.get("filt", 32.0)),
                                tol=IM_TOL_PRESETS[0][1])
                    P = [rx_profile(self.rx_of(w)) or dflt for w in ws]
                    F = [w["freq"] for w in ws]
                    iss, inf = pf_check(F, [not self.is_keep_free(w["status"]) for w in ws],
                                        [float(w.get("bw") or 0.0) for w in ws], [q["sep"] for q in P],
                                        [q["tol"] for q in P], None, [q["filt"] for q in P])
                    names = [w["name"] for w in ws]
                    lines = []
                    for k_, its in enumerate(iss):
                        for it in its:
                            lines.append(f"{names[k_]} ({F[k_]:.3f}) : " + TR(pf_issue_text(it, names, F)))
                    plan = dict(n=sum(1 for x in iss if x), lines=lines, reduced=bool((inf or {}).get("reduced")))
            except Exception:  # noqa: BLE001
                plan = None
        return dict(title=meta.get("name") or TR("Dossier de préparation"), place=meta.get("venue") or "",
                    dates=dates, country=cname, generated=datetime.now().strftime("%d/%m/%Y %H:%M"), rows=rows,
                    reg_lines=reg_lines, tnt=tnt, scans=scans, plan=plan, notes=meta.get("notes") or "",
                    disclaimer=COORD_NOTE, state=self.state_cur or "")

    def export_prep(self, path=None):
        """🖨 Dossier de préparation du show : PDF (à imprimer / envoyer) ou page web."""
        if path is None:
            meta = self.show_meta or {}
            dflt = self.log_dir / "rapports" / f"preparation_{session_name(meta.get('name') or 'show')}_{datetime.now():%Y%m%d}.pdf"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Dossier de préparation", str(dflt),
                                                            "PDF (*.pdf);;Page web (*.html)")
            if not path:
                return None
        info = self.prep_info()
        F, L = self.coord_FL("all")
        img = None
        if F is not None and len(F) > 2:
            img = spectrum_qimage(F, L, thr=self.busy_limit(L), marks=[(r["mhz"], r["name"]) for r in info["rows"]],
                                  tv=[(t["lo"], t["hi"], t["ch"]) for t in info["tnt"] if t["state"] == "tv"])
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            if str(path).lower().endswith(".html"):
                src = None
                if img is not None:
                    ba = QtCore.QByteArray()
                    buf = QtCore.QBuffer(ba)
                    buf.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
                    img.save(buf, "PNG")
                    src = "data:image/png;base64," + bytes(ba.toBase64()).decode("ascii")
                Path(path).write_text(prep_html(info, TR, src), encoding="utf-8")
            else:
                doc = QtGui.QTextDocument()
                if img is not None:
                    doc.addResource(QtGui.QTextDocument.ResourceType.ImageResource, QtCore.QUrl("spectre.png"), img)
                wr = QtGui.QPdfWriter(str(path))
                wr.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
                wr.setPageMargins(QtCore.QMarginsF(12, 12, 12, 12), QtGui.QPageLayout.Unit.Millimeter)
                wr.setResolution(150)
                info["img_w"] = int(wr.width() * 0.97)       # 7.67.1 : l'image prend toute la largeur de la page
                doc.setHtml(prep_html(info, TR, "spectre.png" if img is not None else None))
                wr.setTitle(info["title"])
                doc.setPageSize(QtCore.QSizeF(wr.width(), wr.height()))
                doc.print_(wr)
        except Exception as e:  # noqa: BLE001
            self.set_status(f"⚠ Dossier impossible : {e}")
            return None
        self.set_status(f"🖨 Dossier de préparation enregistré : {path}")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
        return path

    def make_report(self):
        has_im = bool(self._im_dlg is not None and getattr(self._im_dlg, "rows", None))
        dlg = ReportDialog(self, self.report_prefs, has_im)
        if not dlg.exec():
            return
        v = dlg.values()
        self.report_prefs = dict(venue=v["venue"], operator=v["operator"])
        d = self.log_dir / "rapports"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport", str(d / f"rapport_{datetime.now():%Y%m%d_%H%M}.html"), "Page web (*.html)")
        if not path:
            return
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(TR.html(build_report_html(self.collect_report(v))))
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Rapport impossible :\n{e}")
            return
        self.set_status(f"Rapport enregistré : {path}  (navigateur › Imprimer › Enregistrer en PDF)")
        if v["open"]:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------- export des fréquences
    def export_by_scene(self):
        if not self.watch:
            QtWidgets.QMessageBox.information(self, APP_NAME, "La liste de fréquences est vide.")
            return
        scope_idx = [i for i, w in enumerate(self.watch) if self.in_scope(w)]
        sel = self._sel_rows()
        dlg = ExportListDialog(self, len(self.watch), len(scope_idx), len(sel), self.export_list_prefs)
        if not dlg.exec():
            return
        v = dlg.values()
        self.export_list_prefs = v
        idx = {"all": list(range(len(self.watch))), "scope": scope_idx, "sel": sel}[v["src"]]
        if not idx:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Aucune fréquence dans ce choix.")
            return
        base = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier où créer l'export", str(self.log_dir))
        if not base:
            return
        out = Path(base) / f"frequences_{datetime.now():%Y%m%d_%H%M}"
        rows = [dict(name=self.watch[i]["name"], freq=self.watch[i]["freq"], status=self.watch[i]["status"] or "",
                     scene=self.watch[i]["scene"], group=self.watch[i]["group"]) for i in idx]
        enc = "utf-8-sig" if v["fmt"] in ("full", "name_mhz") else "utf-8"
        used, n = set(), 0
        try:
            out.mkdir(parents=True, exist_ok=True)
            for name, rs in split_freq_rows(rows, v["split"]):
                fn, k = name, 2
                while fn.lower() in used:
                    fn = f"{name} ({k})"
                    k += 1
                used.add(fn.lower())
                with open(out / (fn + ".csv"), "w", newline="", encoding=enc) as fh:
                    fh.write(freq_list_text(rs, v["fmt"]))
                n += 1
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")
            return
        self.set_status(f"{len(rows)} fréquence(s) exportée(s) dans {n} fichier(s) : {out}")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(out)))

    # ------------------------------------------------------- guide des bandes
    def open_guide(self):
        name = dict(COUNTRIES).get(self.country, self.country)
        self._guide = BandGuideDialog(self, name, self.plan, self.tv, self.theme, self._guide_add, self._guide_view)
        self._guide.show()

    def _guide_add(self, label, a, b):
        a, b = max(0.1, float(a)), min(6000.0, float(b))
        if b - a < 0.05:
            mid = (a + b) / 2.0
            a, b = max(0.1, mid - 0.025), mid + 0.025
        pts = max(MIN_PTS, int(self._cfg["points"]))
        self.add_band(label, a, b, round((b - a) * 1000.0 / (pts - 1), 6))
        self.set_status(f"« {label} » ajoutée aux bandes à balayer ({pts} points).")

    def _guide_view(self, a, b):
        pad = 0.03 * (b - a)
        self._fit_x = False
        self.spec.getPlotItem().setXRange(a - pad, b + pad, padding=0)
        self.set_status(f"Vue sur {a:g} – {b:g} MHz. Pas de courbe ? Cette zone n'est pas dans tes bandes "
                        f"à balayer : utilise « Ajouter aux bandes à balayer ».")

    def _auto_log(self, vals, w):
        if not self.autolog_chk.isChecked():
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            p = self.log_dir / f"journal_{datetime.now():%Y%m%d}.csv"
            new = not p.exists()
            with open(p, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
                wr = csv.writer(fh, delimiter=";")
                if new:
                    wr.writerow(["Date", "Heure", "Nom", "MHz", "dBm", "Événement", "Statut", "Scène", "Groupe",
                                 "Spectre", "Note"])
                wr.writerow([datetime.now().strftime("%Y-%m-%d"), vals[0], vals[1], vals[2].replace(".", ","),
                             vals[3].replace(".", ","), vals[4], w.get("status", ""), w.get("scene", ""),
                             w.get("group", ""), w.get("band", ""), vals[6] if len(vals) > 6 else ""])
        except Exception as e:
            if not self._log_err_shown:
                self._log_err_shown = True
                self.set_status(f"Journal automatique impossible : {e}")

    def open_log_dir(self):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.log_dir)))

    def pick_log_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier du journal automatique", str(self.log_dir))
        if d:
            self.log_dir = Path(d)
            self._log_err_shown = False
            self.logdir_lbl.setText(str(self.log_dir))

    # ---------------------------------------------------------------- close
    def _close_base(self, e):
        self._closing = True                       # fermé exprès : pas de reprise automatique au prochain lancement
        self._keep_awake(False)
        alive = list(self.workers) + list(getattr(self, "_zombies", []))
        for w in alive:
            if w.isRunning():
                w.requestInterruption()
        for w in alive:
            if not w.wait(8000):                    # tinySA bloqué : on ferme son port, sinon le fil meurt avec l'appli
                w.force_close()
                w.wait(3000)
        if getattr(self, "_relay_win", None) is not None:
            self._relay_win.close()
        if self.web is not None:
            self.web.stop()
            self.web = None
        if self.wall is not None and self.wall_is_fullscreen():
            self.wall_fullscreen(False)
        self._panel_cfg = self.panel_state()             # gardé pour la config (les fenêtres vont se fermer)
        if self.recorder is not None:
            try:
                self.recorder.close()
            except Exception:
                pass
            self.recorder = None
        if self._session is not None:
            self._session_end(stop_rec=False)
        if self._replay is not None:
            try:
                self._replay.close()
            except Exception:
                pass
        self._save_config()
        for win in list(self.panel_wins.values()):        # sinon l'appli resterait ouverte derrière ces fenêtres
            win.closing = True
            win.close()
        e.accept()

    def closeEvent(self, ev):
        """Fermeture : la partie V7 (_close_base), puis, si elle est acceptée, la V8 (repliée en 8.1) : fenêtres SDR,
        récepteurs, émission, outils SDR restés vivants, fenêtres des autres écrans."""
        self._close_base(ev)
        if not getattr(ev, "isAccepted", lambda: True)():
            return
        for d in [getattr(self, nm, None) for nm in ("_multimon", "_listen", "_rt")] + \
                list((getattr(self, "sdr_engs", None) or {}).values()):
            try:
                if d is not None and hasattr(d, "stop"):
                    d.stop()
            except Exception:  # noqa: BLE001
                pass
        for c in list((getattr(self, "_shure", None) or {}).values()):
            c.stop()
        tx = getattr(self, "_sdrtx", None)               # étape 21 : l'émission s'arrête avec l'appli
        if tx is not None:
            try:
                tx.stop()
            except Exception:  # noqa: BLE001
                pass
        sdr_kill_all()
        for host in (getattr(self, "screen_hosts", None) or {}).values():
            host.closing = True
            host.close()
        for lb in getattr(self, "_ident_lbls", []):
            lb.close()
