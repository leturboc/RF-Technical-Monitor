# Outils : conversion de scans, appel des micros, son, chasse, états, planning, scans par lieu, réglages.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class ScanConvertDialog(QtWidgets.QDialog):
    """Convertit un scan d'un logiciel à l'autre : entrée (auto, CSV au choix, scan en cours) → sortie (WWB, WSM,
    CSV au choix), avec un aperçu."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Convertir / exporter un scan")
        self.resize(820, 600)
        self.paths, self.F, self.L = [], None, None
        lay = QtWidgets.QVBoxLayout(self)
        R = owner._row
        # ---- entrée
        ib = QtWidgets.QGroupBox("Entrée")
        il = QtWidgets.QVBoxLayout(ib)
        self.open_btn = QtWidgets.QPushButton("📂 Ouvrir un ou plusieurs fichiers…")
        self.open_btn.setToolTip("Scans exportés de WSM, WWB, EazyRF, d'un tableur…")
        self.open_btn.clicked.connect(lambda *_: self.open_files())
        self.cur_btn = QtWidgets.QPushButton("📈 Prendre le scan en cours")
        self.cur_btn.setToolTip("Le spectre mesuré par le tinySA (max hold ou dernier balayage).")
        self.cur_btn.clicked.connect(lambda *_: self.use_current())
        self.cur_combo = QtWidgets.QComboBox()
        self.cur_combo.addItem("Max hold (recommandé)", True)
        self.cur_combo.addItem("Dernier balayage", False)
        self.cur_combo.setToolTip("Quelle courbe prendre quand on part du scan en cours.")
        self.src_lbl = QtWidgets.QLabel("Aucun scan chargé.")
        self.src_lbl.setWordWrap(True)
        self.in_fmt = QtWidgets.QComboBox()
        self.in_fmt.addItem("Format : reconnaître tout seul (WSM, WWB, « fréquence ; niveau »)", "auto")
        self.in_fmt.addItem("Format : CSV personnalisé (je choisis les colonnes)", "custom")
        self.in_fmt.setToolTip("Auto : export WSM (kHz, %) ou fichier « fréquence, niveau ».\n"
                               "Personnalisé : séparateur, colonnes, unités et lignes à sauter au choix.")
        self.in_sep = QtWidgets.QComboBox()
        for k, t in SCAN_SEPS:
            self.in_sep.addItem(t, k)
        self.in_sep.setToolTip("Séparateur des colonnes du fichier.")
        self.in_fcol, self.in_lcol, self.in_skip = QtWidgets.QSpinBox(), QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        for sp_, v, tip in ((self.in_fcol, 1, "Numéro de la colonne des fréquences (1 = la première)."),
                            (self.in_lcol, 2, "Numéro de la colonne des niveaux."),
                            (self.in_skip, 0, "Lignes à sauter au début (titre, réglages…). Les lignes illisibles\n"
                                              "sont de toute façon ignorées.")):
            sp_.setRange(0 if sp_ is self.in_skip else 1, 200)
            sp_.setValue(v)
            sp_.setToolTip(tip)
        self.in_funit, self.in_lunit = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for u in SCAN_FREQ_UNITS:
            self.in_funit.addItem("auto (d'après les valeurs)" if u == "auto" else u, u)
        for k, t in SCAN_LEVEL_UNITS:
            self.in_lunit.addItem(t, k)
        self.in_funit.setToolTip("Unité des fréquences du fichier.")
        self.in_lunit.setToolTip("Unité des niveaux du fichier.")
        self.custom_box = QtWidgets.QWidget()
        cb = QtWidgets.QVBoxLayout(self.custom_box)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.addLayout(R("Séparateur :", self.in_sep, "Colonne fréquence :", self.in_fcol, "Colonne niveau :",
                       self.in_lcol, None))
        cb.addLayout(R("Fréquences en :", self.in_funit, "Niveaux en :", self.in_lunit, "Sauter :", self.in_skip,
                       "ligne(s)", None))
        il.addLayout(R(self.open_btn, self.cur_btn, self.cur_combo, None))
        il.addWidget(self.in_fmt)
        il.addWidget(self.custom_box)
        il.addWidget(self.src_lbl)
        lay.addWidget(ib)
        # ---- sortie
        ob = QtWidgets.QGroupBox("Sortie")
        ol = QtWidgets.QVBoxLayout(ob)
        self.out_fmt = QtWidgets.QComboBox()
        self.out_fmt.addItem("Shure WWB (scan à importer)", "wwb")
        self.out_fmt.addItem("Sennheiser WSM (comme ses exports)", "wsm")
        self.out_fmt.addItem("Wisycom Manager (comme ses exports)", "wisycom")
        self.out_fmt.addItem("TTI (comme ses exports)", "tti")
        self.out_fmt.addItem("CSV personnalisé (EazyRF, tableur…)", "csv")
        self.out_fmt.setToolTip("Comme les vrais exports de chaque logiciel :\n"
                                "WWB : « 470.000,-104.531 » (MHz, dBm), sans en-tête.\n"
                                "WSM : en-tête du scan, kHz, niveau en dB µV.\n"
                                "Wisycom : « Freq2D;RFA;RFB;MaxRFA;MaxRFB », MHz, dBµV.\n"
                                "TTI : « 470.0000,-88.0 » (MHz, dBm).\n"
                                "CSV : à toi de choisir séparateur, décimale, unités.")
        self.out_sep, self.out_dec = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for k, t in SCAN_SEPS[1:]:
            self.out_sep.addItem(t, k)
        self.out_dec.addItem("virgule (0,5)", ",")
        self.out_dec.addItem("point (0.5)", ".")
        self.out_funit, self.out_lunit = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        for u in SCAN_FREQ_UNITS[1:]:
            self.out_funit.addItem(u, u)
        self.out_funit.setCurrentIndex(2)
        for k, t in SCAN_LEVEL_UNITS:
            self.out_lunit.addItem(t, k)
        self.out_hdr = QtWidgets.QCheckBox("Ligne d'en-tête")
        self.out_hdr.setChecked(True)
        for wd, tip in ((self.out_sep, "Séparateur des colonnes."), (self.out_dec, "Séparateur décimal."),
                        (self.out_funit, "Unité des fréquences."), (self.out_lunit, "Unité des niveaux."),
                        (self.out_hdr, "Ajoute « Fréquence (MHz) ; Niveau (dBm) » en première ligne.")):
            wd.setToolTip(tip)
        self.csv_box = QtWidgets.QWidget()
        xb = QtWidgets.QVBoxLayout(self.csv_box)
        xb.setContentsMargins(0, 0, 0, 0)
        xb.addLayout(R("Séparateur :", self.out_sep, "Décimale :", self.out_dec, self.out_hdr, None))
        xb.addLayout(R("Fréquences en :", self.out_funit, "Niveaux en :", self.out_lunit, None))
        ol.addWidget(self.out_fmt)
        ol.addWidget(self.csv_box)
        self.range = RangeBox(owner)               # seulement la bande utile (ex. 470–608 pour le logiciel de coord)
        self.range.preset.currentIndexChanged.connect(lambda *_: self.reload())
        for sp_ in (self.range.lo, self.range.hi):
            sp_.valueChanged.connect(lambda *_: self.reload())
        ol.addLayout(R("Plage :", self.range))
        lay.addWidget(ob)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setToolTip("Les premières lignes du fichier qui sera écrit.")
        f_ = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        self.preview.setFont(f_)
        lay.addWidget(QtWidgets.QLabel("Aperçu du fichier de sortie :"))
        lay.addWidget(self.preview, 1)
        self.save_btn = QtWidgets.QPushButton("💾 Convertir et enregistrer…")
        self.save_btn.setToolTip("Écrit le fichier (un par fichier d'entrée s'il y en a plusieurs, à côté d'eux).")
        self.save_btn.clicked.connect(lambda *_: self.save())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addLayout(R(None, self.save_btn, close))
        for wd in (self.in_fmt, self.in_sep, self.in_funit, self.in_lunit, self.out_fmt, self.out_sep, self.out_dec,
                   self.out_funit, self.out_lunit):
            wd.currentIndexChanged.connect(lambda *_: self.reload())
        for wd in (self.in_fcol, self.in_lcol, self.in_skip):
            wd.valueChanged.connect(lambda *_: self.reload())
        self.out_hdr.toggled.connect(lambda *_: self.reload())
        self.reload()

    def _read(self, text):
        if self.in_fmt.currentData() == "custom":
            return parse_scan_custom(text, self.in_sep.currentData(), self.in_fcol.value() - 1,
                                     self.in_lcol.value() - 1, self.in_funit.currentData(),
                                     self.in_lunit.currentData(), self.in_skip.value())
        return parse_scan_text(text)

    def _write(self, F, L, title=""):
        lo, hi = self.range.values() if hasattr(self, "range") else (None, None)
        F, L = scan_crop(F, L, lo=lo, hi=hi)
        return scan_write(F, L, self.out_fmt.currentData(), self.out_sep.currentData(), self.out_dec.currentData(),
                          self.out_funit.currentData(), self.out_lunit.currentData(), self.out_hdr.isChecked(), title)

    def open_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Scans à convertir", "",
                                                          "Scans (*.csv *.txt *.sdb3);;Tous les fichiers (*)")
        if paths:
            self.paths = list(paths)
            self.F = self.L = None
            self.reload()

    def use_current(self):
        F, L = self.owner.fresh_FL(use_max=self.cur_combo.currentData(), any_age=True)
        if F is None:
            self.src_lbl.setText("Pas encore de balayage : lance d'abord ▶ Démarrer.")
            return
        self.paths, self.F, self.L = [], F, L
        self.reload()

    def reload(self):
        self.custom_box.setVisible(self.in_fmt.currentData() == "custom")
        self.csv_box.setVisible(self.out_fmt.currentData() == "csv")
        F = L = None
        try:
            if self.paths:
                F, L, info = self._read(decode_text(Path(self.paths[0]).read_bytes()))
                kind = {"wsm": "export WSM", "simple": "fichier « fréquence, niveau »", "sdb3": "scan WWB natif (.sdb3)",
                        "custom": "CSV personnalisé"}.get(info["fmt"], info["fmt"])
                more = f" (+ {len(self.paths) - 1} autre(s) fichier(s))" if len(self.paths) > 1 else ""
                self.src_lbl.setText(f"✔ {os.path.basename(self.paths[0])}{more} : {kind}, {len(F)} points, "
                                     f"{F[0]:.3f} – {F[-1]:.3f} MHz, {L.min():.0f} … {L.max():.0f} dBm"
                                     + (f" · ⚠ {info['note']}" if info.get("note") else ""))
            elif self.F is not None:
                F, L = self.F, self.L
                self.src_lbl.setText(f"✔ Scan en cours : {len(F)} points, {F[0]:.3f} – {F[-1]:.3f} MHz")
        except Exception as e:  # noqa: BLE001
            self.src_lbl.setText(f"⚠ Illisible avec ces réglages : {e}. Essaie « CSV personnalisé ».")
        self.cur = (F, L)
        if F is None:
            self.preview.setPlainText("")
            self.save_btn.setEnabled(False)
            return
        txt = self._write(F, L)
        lines = txt.splitlines()
        self.preview.setPlainText("\n".join(lines[:14]) + (f"\n… ({len(lines)} lignes)" if len(lines) > 14 else ""))
        self.save_btn.setEnabled(True)

    def save(self):
        ext = {"wwb": "_WWB.csv", "wsm": "_WSM.csv"}.get(self.out_fmt.currentData(), "_conv.csv")
        done, errs = [], []
        if not self.paths:
            F, L = self.cur
            out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le scan",
                                                           f"scan_{datetime.now():%Y%m%d_%H%M%S}{ext}", "CSV (*.csv)")
            if not out:
                return
            jobs = [(None, out, F, L)]
        else:
            jobs = []
            for k, p_ in enumerate(self.paths):
                dflt = Path(p_).with_name(Path(p_).stem + ext)
                if len(self.paths) == 1:
                    out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le scan converti", str(dflt),
                                                                   "CSV (*.csv)")
                    if not out:
                        return
                else:
                    out, n_ = dflt, 2
                    while Path(out).exists():
                        out = dflt.with_name(f"{dflt.stem} ({n_}).csv")
                        n_ += 1
                jobs.append((p_, str(out), None, None))
        for p_, out, F, L in jobs:
            try:
                if p_ is not None:
                    F, L, _i = self._read(decode_text(Path(p_).read_bytes()))
                with open(out, "w", newline="", encoding="utf-8") as fh:
                    fh.write(self._write(F, L, Path(p_).stem if p_ else ""))
                done.append(os.path.basename(out))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p_ or out)} : {e}")
        if done:
            self.src_lbl.setText(f"✔ {len(done)} fichier(s) écrit(s) : {', '.join(done[:3])}" + (" …" if len(done) > 3 else ""))
            self.owner.set_status(f"Scan converti : {', '.join(done[:3])}")
        if errs:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Conversion impossible pour :\n" + "\n".join(errs))


class LineCheckDialog(QtWidgets.QDialog):
    """Appel des micros : allume tes émetteurs un par un, chaque fréquence passe ✓ dès que son signal arrive."""
    COLS = ["État", "Nom", "MHz", "Niveau", "Heure", "Scène › Groupe"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Appel des micros")
        self.resize(760, 620)
        self.lc, self.keys, self.unknown, self.t0 = {}, [], {}, time.time()
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Allume tes émetteurs (micros, IEM, intercom…) : chaque fréquence passe ✓ dès que le tinySA voit son "
            "signal. À la fin, « Terminer » note le résultat dans le journal. Un signal inconnu tout près d'une "
            "fréquence qui manque = pack sans doute réglé sur le mauvais canal.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 3)
        lay.addWidget(info)
        self.what_combo = QtWidgets.QComboBox()
        self.what_combo.addItem("Les « doit émettre » de la couche active", "on")
        self.what_combo.addItem("Toute la couche active (sauf « doit rester libre »)", "all")
        self.what_combo.setToolTip("Quelles fréquences sont appelées. La couche active se choisit dans « Fréquences et "
                                   "couches » (Global = tout).")
        self.what_combo.currentIndexChanged.connect(lambda *_: self.restart())
        self.beep_chk = QtWidgets.QCheckBox("Bip à chaque ✓")
        self.beep_chk.setChecked(True)
        self.beep_chk.setToolTip("Un bip du PC quand une fréquence est validée : pratique quand tu es loin de l'écran.")
        self.restart_btn = QtWidgets.QPushButton("🔄 Recommencer")
        self.restart_btn.setToolTip("Remet toutes les fréquences « en attente » (nouvel appel).")
        self.restart_btn.clicked.connect(lambda *_: self.restart())
        lay.addLayout(owner._row(self.what_combo, self.beep_chk, None, self.restart_btn))
        self.run_lbl = QtWidgets.QLabel("La surveillance est arrêtée : démarre-la pour que l'appel avance.")
        self.run_btn = QtWidgets.QPushButton("▶ Démarrer la surveillance")
        self.run_btn.setToolTip("Lance les balayages (comme le bouton Démarrer en haut).")
        self.run_btn.clicked.connect(lambda *_: owner.toggle_run())
        self.run_box = QtWidgets.QWidget()
        rb = QtWidgets.QHBoxLayout(self.run_box)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.addWidget(self.run_lbl, 1)
        rb.addWidget(self.run_btn)
        lay.addWidget(self.run_box)
        self.sum_lbl = QtWidgets.QLabel("")
        f_ = self.sum_lbl.font()
        f_.setPointSize(f_.pointSize() + 5)
        f_.setBold(True)
        self.sum_lbl.setFont(f_)
        self.sum_lbl.setWordWrap(True)
        self.sum_lbl.setMinimumHeight(self.sum_lbl.fontMetrics().height() * 2 + 4)
        lay.addWidget(self.sum_lbl)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setFormat("%v / %m")
        self.bar.setToolTip("Fréquences validées / fréquences appelées.")
        lay.addWidget(self.bar)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Double-clic : voir la fréquence sur le spectre.")
        self.table.cellDoubleClicked.connect(lambda r, c: self._goto(r))
        for c, w_ in enumerate((96, 130, 72, 80, 64)):
            self.table.setColumnWidth(c, w_)
        lay.addWidget(self.table, 1)
        self.hint_lbl = QtWidgets.QLabel("")
        self.hint_lbl.setWordWrap(True)
        lay.addWidget(self.hint_lbl)
        self.ok_btn = QtWidgets.QPushButton("✓ Valider à la main")
        self.ok_btn.setToolTip("Valide les lignes choisies sans signal mesuré (vérifiée à l'oreille, émetteur hors "
                               "de portée du tinySA…).")
        self.ok_btn.clicked.connect(lambda *_: self.mark("manual"))
        self.skip_btn = QtWidgets.QPushButton("⏭ Ignorer")
        self.skip_btn.setToolTip("Retire les lignes choisies de l'appel (spare, émetteur pas utilisé ce soir…).")
        self.skip_btn.clicked.connect(lambda *_: self.mark("skip"))
        self.undo_btn = QtWidgets.QPushButton("↺ Remettre en attente")
        self.undo_btn.setToolTip("Les lignes choisies redeviennent « en attente ».")
        self.undo_btn.clicked.connect(lambda *_: self.mark(None))
        self.copy_btn = QtWidgets.QPushButton("📋 Copier le résumé")
        self.copy_btn.setToolTip("Copie le résultat (une ligne par fréquence) pour l'envoyer à la régie, sur WhatsApp…")
        self.copy_btn.clicked.connect(lambda *_: self.copy())
        self.done_btn = QtWidgets.QPushButton("📝 Terminer")
        self.done_btn.setToolTip("Note le résultat de l'appel dans le journal (et le journal auto CSV), puis ferme.")
        self.done_btn.clicked.connect(lambda *_: self.finish())
        lay.addLayout(owner._row(self.ok_btn, self.skip_btn, self.undo_btn, None, self.copy_btn, self.done_btn))
        self.restart()

    def _wanted(self):
        ow, mode = self.owner, self.what_combo.currentData()
        out = []
        for w in ow.watch:
            if not ow.in_scope(w) or ow.is_keep_free(w["status"]):
                continue
            if mode == "on" and not ow.is_keep_on(w["status"]):
                continue
            out.append(w)
        return out

    def restart(self):
        ws = self._wanted()
        if not ws and self.what_combo.currentData() == "on" and self.owner.watch:
            self.what_combo.blockSignals(True)          # aucun « doit émettre » : on appelle toute la couche
            self.what_combo.setCurrentIndex(1)
            self.what_combo.blockSignals(False)
            ws = self._wanted()
        self.keys = [int(round(w["freq"] * 1000)) for w in ws]
        self.lc = lc_new([(k, w["name"], w["freq"], self.owner.layer_text(w)) for k, w in zip(self.keys, ws)])
        self.keys = sorted(set(self.keys), key=lambda k: self.lc[k]["freq"])
        self.unknown, self.t0 = {}, time.time()
        self.table.setRowCount(len(self.keys))
        self.feed(beep=False)

    def feed(self, beep=True):
        """Appelé après chaque balayage (MainWindow.on_sweep)."""
        ow, now, new = self.owner, time.time(), 0
        for w in ow.watch:
            new += lc_feed(self.lc, int(round(w["freq"] * 1000)), w["state"], w["level"], now)
        for lst in ow.unk_now.values():
            for fr in lst:
                self.unknown[round(fr, 3)] = now
        self.unknown = {f: t for f, t in self.unknown.items() if now - t < 120}
        if new and beep and self.beep_chk.isChecked():
            self.owner.sound.play(TONE_OK)
        self.refresh()

    def refresh(self):
        ow, th = self.owner, self.owner.theme
        sm = lc_summary(self.lc)
        running = ow.is_running()
        self.run_box.setVisible(not running)
        col = {"ok": th["st_free"], "manual": th["st_free"], "weak": th["st_weak"], "skip": th["st_none"]}
        for r, k in enumerate(self.keys):
            e = self.lc[k]
            vals = [LC_TEXT[e["res"]], e["name"], f"{e['freq']:.3f}",
                    ow.lvl(e["lvl"], suffix=True) if e["lvl"] is not None else "",
                    datetime.fromtimestamp(e["t"]).strftime("%H:%M:%S") if e["t"] else "", e["layer"]]
            bg = QtGui.QColor(col.get(e["res"], th["ui_base"]))
            for c, v in enumerate(vals):
                it = self.table.item(r, c)
                if it is None:
                    it = QtWidgets.QTableWidgetItem()
                    self.table.setItem(r, c, it)
                if it.text() != v:
                    it.setText(v)
                if c == 0:
                    it.setBackground(bg)
                    it.setForeground(QtGui.QColor(contrast_text(bg.name())))
        self.bar.setMaximum(max(1, sm["n"]))
        self.bar.setValue(sm["ok"] + sm["weak"])
        self.sum_lbl.setText(sm["text"])
        self.sum_lbl.setStyleSheet(f"color:{th['st_free'] if sm['done'] else th['ui_text']}")
        hints = lc_hints(self.lc, list(self.unknown))
        self.hint_lbl.setText("" if not hints else "🔎 " + " · ".join(
            f"{n} ({fa:.3f}) manque, mais signal inconnu à {fu:.3f} MHz ({(fu - fa) * 1000:+.0f} kHz) : mauvais canal ?"
            for n, fa, fu in hints[:4]))

    def _sel_keys(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.keys[r] for r in rows if r < len(self.keys)]

    def mark(self, res):
        now = time.time()
        for k in self._sel_keys():
            e = self.lc[k]
            e["res"], e["t"] = res, (now if res else None)
            if res is None:
                e["lvl"] = None
        self.refresh()

    def _goto(self, r):
        if r < len(self.keys):
            f = self.lc[self.keys[r]]["freq"]
            try:
                self.owner.spec.getPlotItem().vb.setXRange(f - 2.0, f + 2.0, padding=0)
            except Exception:
                pass

    def summary_text(self):
        ow = self.owner
        return lc_text(self.lc, ow.show_meta.get("name", ""), datetime.now().strftime("%d/%m %H:%M"),
                       lambda v: ow.lvl(v, suffix=True))

    def copy(self):
        QtWidgets.QApplication.clipboard().setText(self.summary_text())
        self.owner.set_status("Résumé de l'appel copié : colle-le où tu veux.")

    def finish(self):
        sm = lc_summary(self.lc)
        self.owner.log_event(dict(name="Appel des micros", freq=0.0, note=sm["text"]), 0.0,
                             "APPEL OK" if sm["done"] else "APPEL INCOMPLET")
        self.owner.set_status(f"Appel des micros : {sm['text']}")
        self.close()

    def closeEvent(self, e):
        if self.owner._linecheck is self:
            self.owner._linecheck = None
        super().closeEvent(e)

    def done(self, r):
        if self.owner._linecheck is self:
            self.owner._linecheck = None
        super().done(r)


class SoundOut:
    """Sons de l'appli joués sur la sortie audio choisie (⚙ Réglages › Son) ; bip de Windows si QtMultimedia manque
    ou si aucune sortie ne répond. Une note à la fois : la suivante coupe la précédente."""

    def __init__(self):
        self.cfg = dict(SOUND_DEFAULT)
        self.sink = self.buf = None
        self.error = ""

    @staticmethod
    def _mm():
        try:
            from PySide6 import QtMultimedia
            return QtMultimedia
        except Exception:  # noqa: BLE001
            return None

    @classmethod
    def devices(cls):
        """Sorties audio de l'ordinateur -> [(id, nom)]."""
        mm = cls._mm()
        if mm is None:
            return []
        try:
            return [(bytes(d.id()).hex(), d.description()) for d in mm.QMediaDevices.audioOutputs()]
        except Exception:  # noqa: BLE001
            return []

    def _device(self, mm):
        want = self.cfg.get("device") or ""
        if want:
            for d in mm.QMediaDevices.audioOutputs():
                if bytes(d.id()).hex() == want or d.description() == want:
                    return d
        return mm.QMediaDevices.defaultAudioOutput()

    def _play_base(self, seq):
        if not self.cfg.get("volume"):
            return
        style = self.cfg.get("style", "tones")
        mm = self._mm() if style in ("tones", "classic") else None
        if mm is None:
            QtWidgets.QApplication.beep()
            return
        try:
            dev = self._device(mm)
            if dev is None or dev.isNull():
                raise RuntimeError("aucune sortie audio")
            fmt = mm.QAudioFormat()
            fmt.setSampleRate(22050)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(mm.QAudioFormat.SampleFormat.Int16)
            if self.sink is not None:
                self.sink.stop()
            self.sink = mm.QAudioSink(dev, fmt)
            self.sink.setVolume(self.cfg.get("volume", 70) / 100.0)
            self.buf = QtCore.QBuffer()
            if style == "classic":                       # 8.0.3 : les anciens bips, au choix
                seq = next((ALARM_TONES_CLASSIC[k] for k, v in ALARM_TONES.items() if v is seq),
                           TONE_OK_CLASSIC if seq is TONE_OK else seq)
            self.buf.setData(QtCore.QByteArray(tone_pcm(seq, 22050, 1.0, "sine" if style == "classic" else "chime")))
            self.buf.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
            self.sink.start(self.buf)
            self.error = ""
        except Exception as e:  # noqa: BLE001 — jamais de plantage pour un son
            self.error = str(e)
            QtWidgets.QApplication.beep()

    def play(self, seq):
        """Un son d'alarme / d'appel personnalisé (self.custom {clé: source}) remplace les notes d'origine ; sinon V7."""
        key = {id(ALARM_TONES[2]): "alarm2", id(ALARM_TONES[1]): "alarm1", id(ALARM_TONES[0]): "alarm0",
               id(TONE_OK): "ok"}.get(id(seq))
        sp = (getattr(self, "custom", None) or {}).get(key) if key else None
        if sp is None or not self.cfg.get("volume") or self.cfg.get("style", "tones") != "tones":
            return self._play_base(seq)
        mm = self._mm()
        if mm is None:
            return self._play_base(seq)
        try:
            if audio_spec_norm(sp)["src"] == "wav":
                wav_load(audio_spec_norm(sp)["path"])
            a = alarm_pcm(sp)
            dev = self._device(mm)
            if dev is None or dev.isNull():
                raise RuntimeError("aucune sortie audio")
            fmt = mm.QAudioFormat()
            fmt.setSampleRate(48000)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(mm.QAudioFormat.SampleFormat.Int16)
            if self.sink is not None:
                self.sink.stop()
            self.sink = mm.QAudioSink(dev, fmt)
            self.sink.setVolume(self.cfg.get("volume", 70) / 100.0)
            self.buf = QtCore.QBuffer()
            self.buf.setData(QtCore.QByteArray((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()))
            self.buf.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
            self.sink.start(self.buf)
            self.error = ""
            self.last_custom = key
        except Exception as e:  # noqa: BLE001 — jamais de plantage pour un son : on joue le son d'origine
            self.error = str(e)
            return self._play_base(seq)

    def alarm(self, prio):
        self.play(ALARM_TONES.get(int(prio), ALARM_TONES[0]))


class HuntDialog(QtWidgets.QDialog):
    """🔎 Chasse au brouilleur : zoom live serré sur la fréquence gênante et un bip qui accélère et monte quand le
    niveau monte. Avec une antenne directive sur le tinySA, on se promène et on remonte jusqu'à la source."""

    def __init__(self, owner, f0=None):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Chasse au brouilleur")
        self.setModal(False)
        self.resize(520, 420)
        self.level = self.fpk = None
        self.best = None
        self.we_zoomed = False
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Mets une <b>antenne directive</b> sur le tinySA, lance la chasse puis tourne-toi / "
                                "déplace-toi : le bip <b>accélère et monte</b> quand tu te rapproches de la source. "
                                "Baisse l'atténuation (ou ajoute-en) si le niveau sature tout près.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.f_spin = QtWidgets.QDoubleSpinBox()
        self.f_spin.setDecimals(3)
        self.f_spin.setRange(0.1, 6000.0)
        self.f_spin.setSuffix(" MHz")
        self.f_spin.setValue(float(f0) if f0 else 600.0)
        self.f_spin.setToolTip("Fréquence du signal à chasser (prise de la ligne choisie dans ta liste, ou de M1).")
        self.span_spin = QtWidgets.QDoubleSpinBox()
        self.span_spin.setDecimals(1)
        self.span_spin.setRange(0.2, 50.0)
        self.span_spin.setValue(2.0)
        self.span_spin.setSuffix(" MHz")
        self.span_spin.setToolTip("Largeur balayée autour : petite = balayage très rapide, donc bip plus réactif.")
        self.follow_chk = QtWidgets.QCheckBox("Suivre le plus fort de la zone")
        self.follow_chk.setToolTip("Coché : le bip suit le pic le plus haut de la zone (signal qui bouge un peu).\n"
                                   "Décoché : le niveau à ± 100 kHz de la fréquence choisie.")
        self.mute_chk = QtWidgets.QCheckBox("Muet")
        self.mute_chk.setToolTip("Coupe le bip (l'affichage continue).")
        self.dev_combo = QtWidgets.QComboBox()
        for d_ in o.dev_list():
            self.dev_combo.addItem(f"{dev_ord(d_)} tinySA · {o.dev_name(d_)}", d_)
        self.dev_combo.setCurrentIndex(o.ndev() - 1)          # le dernier (portable, sur un Pi) par défaut
        self.dev_combo.setToolTip("Le tinySA qui chasse. Avec 2 tinySA : le portable (2ᵉ, ex. sur un Raspberry Pi\n"
                                  "dans un sac) chasse, le 1er continue de surveiller toutes les bandes.")
        self.dev_combo.setVisible(o.ndev() > 1)
        self.go_btn = QtWidgets.QPushButton("▶ Chasser")
        self.go_btn.setCheckable(True)
        self.go_btn.setToolTip("Zoom live sur la zone + bip. Il faut que la surveillance tourne (▶ Démarrer).")
        self.go_btn.toggled.connect(lambda *_: self.toggle(self.go_btn.isChecked()))
        lay.addLayout(owner._row("Fréquence :", self.f_spin, "Zone :", self.span_spin, self.dev_combo, None))
        lay.addLayout(owner._row(self.follow_chk, self.mute_chk, None, self.go_btn))
        self.big = QtWidgets.QLabel("—")
        self.big.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big.setStyleSheet("font-size:44px;font-weight:bold")
        lay.addWidget(self.big)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(-110, -20)
        self.bar.setTextVisible(False)
        self.bar.setMinimumHeight(26)
        self.bar.setToolTip("Niveau mesuré : plus la barre est longue, plus tu es près.")
        lay.addWidget(self.bar)
        self.sub = QtWidgets.QLabel("")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub.setWordWrap(True)
        lay.addWidget(self.sub)
        rst = QtWidgets.QPushButton("↺ Remettre le max à zéro")
        rst.setToolTip("Oublie le plus fort niveau vu (pour recommencer à un autre endroit).")
        rst.clicked.connect(lambda *_: self._reset_best())
        xb = []
        for txt, fn in owner.FREQ_ACTIONS:             # 7.68 : actions d'une autre version (V8 : 🎧 écouter ce signal)
            if callable(getattr(owner, fn, None)):
                b_ = QtWidgets.QPushButton(txt)
                b_.setToolTip(txt)
                b_.clicked.connect(lambda *_, fn=fn: getattr(owner, fn)(float(self.f_spin.value()), None))
                xb.append(b_)
        lay.addLayout(owner._row(*xb, None, rst))
        lay.addStretch(1)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)

    def _reset_best(self):
        self.best = None
        self._show()

    def toggle(self, on):
        o = self.owner
        if on:
            if not o.is_running():
                self.sub.setText("Lance d'abord la surveillance (▶ Démarrer), puis la chasse.")
                self.go_btn.blockSignals(True)
                self.go_btn.setChecked(False)
                self.go_btn.blockSignals(False)
                return
            f, h = self.f_spin.value(), self.span_spin.value() / 2.0
            o.zoom_dev = int(self.dev_combo.currentData() or 0)
            o.spec.getPlotItem().setXRange(f - h, f + h, padding=0)
            o._fit_x = False
            if o._zoom is None:
                if o._last_xy is None:
                    self.sub.setText("Attends le premier balayage, puis relance la chasse.")
                    self.go_btn.blockSignals(True)
                    self.go_btn.setChecked(False)
                    self.go_btn.blockSignals(False)
                    return
                if o.zoom_btn.isChecked():               # bouton resté coché sans zoom en cours
                    o.toggle_zoom(True)
                else:
                    o.zoom_btn.setChecked(True)
                self.we_zoomed = True
            else:
                o._set_zoom(f - h, f + h)
            self.go_btn.setText("■ Arrêter la chasse")
            self.timer.start(1000)
            self.sub.setText("Chasse en cours : attends le premier balayage…")
        else:
            self.timer.stop()
            self.go_btn.setText("▶ Chasser")
            if self.we_zoomed and o._zoom is not None:
                o.zoom_btn.setChecked(False)
                o.toggle_zoom(False)
            self.we_zoomed = False
            o.zoom_dev = 0

    def feed(self, F, L):
        if not self.go_btn.isChecked():
            return
        lvl, fpk = hunt_level(F, L, self.f_spin.value(), 100.0, self.follow_chk.isChecked(), self.span_spin.value())
        self.level, self.fpk = lvl, fpk
        if lvl is not None:
            self.best = lvl if self.best is None else max(self.best, lvl)
        self._show()
        hz, per = hunt_tone(lvl)
        self.timer.setInterval(max(60, per))

    def _show(self):
        o = self.owner
        if self.level is None:
            self.big.setText("—")
            return
        self.big.setText(o.lvl(self.level, suffix=True))
        self.bar.setValue(int(max(-110, min(-20, self.level))))
        d = "" if self.best is None else f" · max vu {o.lvl(self.best, suffix=True)} ({self.level - self.best:+.1f} dB)"
        self.sub.setText(f"Pic à {self.fpk:.3f} MHz" + d)

    def _tick(self):
        if self.mute_chk.isChecked() or self.level is None:
            return
        hz, _per = hunt_tone(self.level)
        if hz:
            self.owner.sound.play([(hz, 45)])

    def closeEvent(self, e):
        self.toggle(False)
        if self.owner._hunt is self:
            self.owner._hunt = None
        super().closeEvent(e)

    def done(self, r):
        self.toggle(False)
        if self.owner._hunt is self:
            self.owner._hunt = None
        super().done(r)


class EzrfSyncDialog(QtWidgets.QDialog):
    """🔗 Le plan .ezrf3 suivi a été réenregistré : liste des changements, tu coches ceux que tu reprends."""

    def __init__(self, owner, d):
        super().__init__(owner)
        self.owner, self.d = owner, d
        lk = owner.ezrf_link or {}
        kind = lk.get("kind") or "EazyRF"
        self.setWindowTitle(f"Plan {kind} modifié")
        self.resize(560, 460)
        lay = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel(f"🔗 « {lk.get('name', '')} » a été réenregistré dans {kind}. Coche ce que tu reprends "
                                f"dans ta liste :")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.lst = QtWidgets.QListWidget()
        self.lst.setToolTip("Décoche ce que tu ne veux pas reprendre.")
        by_ez = {w["ez"]: w for w in owner.watch if w.get("ez")}
        for e in d["add"]:
            self._item(f"＋ {e[0]}  {e[1]:.3f} MHz" + (f"  ({e[2]}{' › ' + e[3] if e[3] else ''})" if e[2] else ""),
                       ("add", e))
        for c in d["change"]:
            w = by_ez.get(c[0])
            self._item(f"✏ {w['name'] if w else c[3][0]} : {c[1]:.3f} → {c[2]:.3f} MHz", ("change", c))
        for i in d["remove"]:
            w = by_ez.get(i)
            self._item(f"🗑 {w['name'] if w else i}" + (f"  {w['freq']:.3f} MHz" if w else ""), ("remove", i))
        lay.addWidget(self.lst, 1)
        b_ok = QtWidgets.QPushButton("Appliquer les changements cochés")
        b_ok.setToolTip("Ajoute, déplace ou retire les fréquences cochées (Ctrl+Z pour revenir).")
        b_ok.clicked.connect(lambda *_: self.apply())
        b_later = QtWidgets.QPushButton("Plus tard")
        b_later.setToolTip("Ne change rien maintenant (☰ Plus › 📋 Liste › 🔗 Plan EazyRF suivi › Vérifier maintenant).")
        b_later.clicked.connect(lambda *_: self.reject())
        b_stop = QtWidgets.QPushButton("Ne plus suivre ce fichier")
        b_stop.setToolTip("Arrête de surveiller ce fichier EazyRF.")
        b_stop.clicked.connect(lambda *_: (setattr(owner, "ezrf_link", None), self.reject()))
        lay.addLayout(owner._row(b_ok, b_later, None, b_stop))

    def _item(self, txt, data):
        it = QtWidgets.QListWidgetItem(txt)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked)
        it.setData(Qt.ItemDataRole.UserRole, data)
        self.lst.addItem(it)

    def apply(self):
        add, change, remove = [], [], []
        for r in range(self.lst.count()):
            it = self.lst.item(r)
            if it.checkState() != Qt.CheckState.Checked:
                continue
            kind, v = it.data(Qt.ItemDataRole.UserRole)
            {"add": add, "change": change, "remove": remove}[kind].append(v)
        self.result_n = self.owner.apply_ezrf_diff(self.d, add, change, remove)
        self.accept()


class StatesDialog(QtWidgets.QDialog):
    """📸 États (comme les Snapshots du logiciel de coord) : plusieurs plans dans le même show (artistes, scènes, jours). Un état =
    les fréquences actives ; les autres passent en pause (pas d'alarme, hors du calcul d'intermod). « 🔒 Toujours » =
    active dans tous les états (intercom, talkies…)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("📸 États")
        self.resize(820, 560)
        lay = QtWidgets.QVBoxLayout(self)
        hint = QtWidgets.QLabel("Un état = les fréquences qui jouent ensemble (un artiste, une scène, un jour). ▶ Activer : "
                                "celles de l'état sont surveillées, les autres passent en pause (pas d'alarme, pas comptées "
                                "dans l'intermod). « 🔒 Toujours » : active quel que soit l'état (intercom, talkies…).")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        sp = QtWidgets.QSplitter()
        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.lst = QtWidgets.QListWidget()
        self.lst.setToolTip("Les états du show. Double-clic = l'activer. Suppr = le supprimer.")
        self.lst.currentRowChanged.connect(lambda *_: self.fill_table())
        self.lst.itemDoubleClicked.connect(lambda *_: self.activate())
        del_key(self.lst, self.delete)
        ll.addWidget(self.lst, 1)
        bn = QtWidgets.QPushButton("＋ Nouveau (fréquences actives)")
        bn.setToolTip("Crée un état avec les fréquences surveillées en ce moment.")
        bn.clicked.connect(lambda *_: self.new())
        bd = QtWidgets.QPushButton("⧉ Dupliquer")
        bd.setToolTip("Copie l'état choisi (pratique pour un artiste proche du précédent).")
        bd.clicked.connect(lambda *_: self.duplicate())
        br = QtWidgets.QPushButton("Renommer…")
        br.setToolTip("Renomme l'état choisi.")
        br.clicked.connect(lambda *_: self.rename())
        bx = QtWidgets.QPushButton("Supprimer")
        bx.setToolTip("Supprime l'état choisi (les fréquences restent dans la liste).")
        bx.clicked.connect(lambda *_: self.delete())
        ba = QtWidgets.QPushButton("▶ Activer")
        ba.setToolTip("Bascule sur l'état choisi.")
        ba.clicked.connect(lambda *_: self.activate())
        b0 = QtWidgets.QPushButton("Tout actif")
        b0.setToolTip("Plus d'état : toutes les fréquences sont surveillées.")
        b0.clicked.connect(lambda *_: (owner.apply_state(""), self.fill()))
        for b_ in (bn, bd, br, bx, ba, b0):
            ll.addWidget(b_)
        sp.addWidget(left)
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.tbl = QtWidgets.QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Dans l'état", "🔒 Toujours", "Nom", "MHz", "Scène › groupe"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tbl.setToolTip("Coche les fréquences qui jouent dans l'état choisi à gauche.")
        self.tbl.itemChanged.connect(self._changed)
        rl.addWidget(self.tbl, 1)
        ball = QtWidgets.QPushButton("Tout cocher")
        ball.setToolTip("Toutes les fréquences dans l'état choisi.")
        ball.clicked.connect(lambda *_: self.check_all(True))
        bnone = QtWidgets.QPushButton("Tout décocher")
        bnone.setToolTip("Aucune fréquence dans l'état choisi (sauf les « toujours »).")
        bnone.clicked.connect(lambda *_: self.check_all(False))
        self.scene_combo = QtWidgets.QComboBox()
        self.scene_combo.setToolTip("Ne cocher que les fréquences d'une scène (ou d'un groupe).")
        self.scene_combo.addItem("Cocher une scène / un groupe…", None)
        for sc in owner.scenes:
            self.scene_combo.addItem(sc["name"], (sc["name"], ""))
            for g in sc["groups"]:
                self.scene_combo.addItem(f"   {sc['name']} › {g['name']}", (sc["name"], g["name"]))
        self.scene_combo.activated.connect(lambda *_: self.check_layer())
        rl.addLayout(owner._row(ball, bnone, self.scene_combo, None))
        sp.addWidget(right)
        sp.setSizes([240, 560])
        lay.addWidget(sp, 1)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.fill()

    def _cur(self):
        r = self.lst.currentRow()
        return self.owner.states[r] if 0 <= r < len(self.owner.states) else None

    def fill(self, keep=None):
        o = self.owner
        keep = keep if keep is not None else (self._cur() or {}).get("name") or o.state_cur
        self.lst.blockSignals(True)
        self.lst.clear()
        for st in o.states:
            it = QtWidgets.QListWidgetItem(("▶ " if st["name"] == o.state_cur else "") + f"{st['name']}  ({len(st['keys'])})")
            self.lst.addItem(it)
        idx = next((i for i, st in enumerate(o.states) if st["name"] == keep), 0 if o.states else -1)
        self.lst.setCurrentRow(idx)
        self.lst.blockSignals(False)
        self.fill_table()
        self.msg.setText(f"Actif : « {o.state_cur} »." if o.state_cur else "Actif : tout (aucun état).")

    def fill_table(self):
        o, st = self.owner, self._cur()
        keys = set(st["keys"]) if st else set()
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(len(o.watch))
        for r, w in enumerate(o.watch):
            k = int(round(w["freq"] * 1000))
            a = QtWidgets.QTableWidgetItem("")
            a.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            a.setCheckState(Qt.CheckState.Checked if (k in keys or w.get("iso")) else Qt.CheckState.Unchecked)
            if st is None or w.get("iso"):
                a.setFlags(Qt.ItemFlag.ItemIsUserCheckable)          # grisée : pas d'état choisi / toujours active
            a.setData(Qt.ItemDataRole.UserRole, k)
            self.tbl.setItem(r, 0, a)
            b = QtWidgets.QTableWidgetItem("")
            b.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            b.setCheckState(Qt.CheckState.Checked if w.get("iso") else Qt.CheckState.Unchecked)
            b.setData(Qt.ItemDataRole.UserRole, k)
            self.tbl.setItem(r, 1, b)
            for c, txt in ((2, w["name"]), (3, f"{w['freq']:.3f}"), (4, o.layer_text(w))):
                it = QtWidgets.QTableWidgetItem(txt)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.tbl.setItem(r, c, it)
        self.tbl.resizeColumnsToContents()
        self.tbl.blockSignals(False)

    def _w(self, k):
        return next((w for w in self.owner.watch if int(round(w["freq"] * 1000)) == k), None)

    def _changed(self, it):
        o, st = self.owner, self._cur()
        k = it.data(Qt.ItemDataRole.UserRole)
        on = it.checkState() == Qt.CheckState.Checked
        if it.column() == 1:
            w = self._w(k)
            if w is not None:
                w["iso"] = on
                if not on:
                    w.pop("iso", None)
        elif st is not None:
            ks = set(st["keys"])
            st["keys"] = sorted(ks | {k} if on else ks - {k})
        self._reapply()
        self.fill()

    def _reapply(self):
        o = self.owner
        o.apply_state(o.state_cur, quiet=False)

    def check_all(self, on):
        st = self._cur()
        if st is None:
            return
        st["keys"] = sorted(int(round(w["freq"] * 1000)) for w in self.owner.watch) if on else []
        self._reapply()
        self.fill()

    def check_layer(self):
        st, sel = self._cur(), self.scene_combo.currentData()
        self.scene_combo.setCurrentIndex(0)
        if st is None or sel is None:
            return
        sc, gr = sel
        add = {int(round(w["freq"] * 1000)) for w in self.owner.watch if w["scene"] == sc and (not gr or w["group"] == gr)}
        st["keys"] = sorted(set(st["keys"]) | add)
        self._reapply()
        self.fill()

    def new(self):
        name = self.owner.new_state()
        if name:
            self.owner.apply_state(name)
            self.fill(name)

    def duplicate(self):
        st = self._cur()
        if st is None:
            return
        o, n, base = self.owner, 2, st["name"][:34]
        name = f"{base} ({n})"
        while o.state_by_name(name) is not None:
            n += 1
            name = f"{base} ({n})"
        o.states.append(dict(name=name, keys=list(st["keys"])))
        self.fill(name)

    def rename(self):
        st = self._cur()
        if st is None:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Renommer l'état", "Nouveau nom :", text=st["name"])
        name = re.sub(r"\s+", " ", name or "").strip()[:40]
        if not ok or not name or (name != st["name"] and self.owner.state_by_name(name) is not None):
            return
        if self.owner.state_cur == st["name"]:
            self.owner.state_cur = name
        st["name"] = name
        self.owner._update_state_btn()
        self.fill(name)

    def delete(self):
        st = self._cur()
        if st is None:
            return
        o = self.owner
        o.states.remove(st)
        if o.state_cur == st["name"]:
            o.apply_state("")
        self.fill()

    def activate(self):
        st = self._cur()
        if st is not None:
            self.owner.apply_state(st["name"])
            self.fill(st["name"])


class PlanningDialog(QtWidgets.QDialog):
    """🎬 Planning des plateaux : pour chaque scène, quel groupe joue quand. Pendant son créneau (marges comprises),
    un groupe doit émettre (alarme ABSENT normale) ; hors créneau ses micros sont « 💤 pas sur scène », sans alarme."""
    COLS = ["Scène", "Groupe", "Jour", "Début", "Fin"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        pl = o.planning
        self.setWindowTitle("Planning des plateaux")
        self.resize(760, 520)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Qui joue quand, scène par scène. Pendant son créneau (avec les marges), un groupe <b>doit émettre</b> : "
            "alarme ABSENT si un micro se tait. Hors créneau, ses micros sont « 💤 pas sur scène » : plus d'alarme "
            "pour un groupe pas encore arrivé ou déjà parti. Une scène sans créneau n'est pas touchée.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.on_chk = QtWidgets.QCheckBox("Utiliser le planning")
        self.on_chk.setChecked(pl["on"])
        self.on_chk.setToolTip("Décoché : tous les groupes sont surveillés tout le temps, comme avant.")
        self.pre = QtWidgets.QSpinBox()
        self.pre.setRange(0, 240)
        self.pre.setValue(pl["pre"])
        self.pre.setSuffix(" min")
        self.pre.setToolTip("Le groupe est « sur scène » ce temps-là AVANT son créneau (line check, changement de plateau).")
        self.post = QtWidgets.QSpinBox()
        self.post.setRange(0, 240)
        self.post.setValue(pl["post"])
        self.post.setSuffix(" min")
        self.post.setToolTip("… et ce temps-là APRÈS (rappel, fin qui déborde).")
        lay.addLayout(owner._row(self.on_chk, None, "Marge avant :", self.pre, "après :", self.post))
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        b_add = QtWidgets.QPushButton("＋ Créneau")
        b_add.setToolTip("Ajoute un créneau (scène, groupe, jour, début, fin).")
        b_add.clicked.connect(lambda *_: self.add_row())
        b_del = QtWidgets.QPushButton("🗑 Supprimer")
        b_del.setToolTip("Supprime les créneaux choisis.")
        b_del.clicked.connect(lambda *_: self.del_rows())
        lay.addLayout(owner._row(b_add, b_del, None))
        self.now_lbl = QtWidgets.QLabel("")
        self.now_lbl.setWordWrap(True)
        lay.addWidget(self.now_lbl)
        for s_ in pl["slots"]:
            self.add_row(s_)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.refresh_now()

    def _days(self):
        today = datetime.now().date()
        return [("Tous les jours", "")] + [((today + timedelta(days=i)).strftime("%a %d/%m"),
                                            (today + timedelta(days=i)).isoformat()) for i in range(-1, 8)]

    def add_row(self, s_=None):
        o = self.owner
        s_ = s_ or {}
        r = self.table.rowCount()
        self.table.insertRow(r)
        sc = QtWidgets.QComboBox()
        names = [x["name"] for x in o.scenes]
        if s_.get("scene") and s_["scene"] not in names:
            names.append(s_["scene"])
        sc.addItems(names)
        sc.setToolTip("La scène (un planning par scène).")
        gr = QtWidgets.QComboBox()
        gr.setToolTip("Le groupe qui joue ; « toute la scène » = tous ses groupes.")
        day = QtWidgets.QComboBox()
        for t, k in self._days():
            day.addItem(t, k)
        if s_.get("day") and day.findData(s_["day"]) < 0:
            day.addItem(s_["day"], s_["day"])
        day.setCurrentIndex(max(0, day.findData(s_.get("day", ""))))
        day.setToolTip("Tous les jours, ou un jour précis du festival.")
        t0, t1 = QtWidgets.QTimeEdit(), QtWidgets.QTimeEdit()
        for te, v, dflt in ((t0, s_.get("start"), "20:00"), (t1, s_.get("end"), "21:30")):
            te.setDisplayFormat("HH:mm")
            m_ = _hm(v or dflt)
            te.setTime(QtCore.QTime(m_ // 60 % 24, m_ % 60))
            te.setToolTip("Heure de début / de fin du set (fin avant le début = finit après minuit).")
            te.timeChanged.connect(lambda *_: self.refresh_now())

        def fill_groups(*_a, sc=sc, gr=gr, want=None):
            cur = want if want is not None else gr.currentData()
            gr.blockSignals(True)
            gr.clear()
            gr.addItem("(toute la scène)", "")
            scn = o.scene_by_name(sc.currentText())
            for g in (scn["groups"] if scn else []):
                gr.addItem(g["name"], g["name"])
            if cur and gr.findData(cur) < 0:
                gr.addItem(cur, cur)
            gr.setCurrentIndex(max(0, gr.findData(cur or "")))
            gr.blockSignals(False)
            self.refresh_now()
        if s_.get("scene"):
            sc.setCurrentText(s_["scene"])
        fill_groups(want=s_.get("group", ""))
        sc.currentIndexChanged.connect(fill_groups)
        for w_ in (gr, day):
            w_.currentIndexChanged.connect(lambda *_: self.refresh_now())
        for c, w_ in enumerate((sc, gr, day, t0, t1)):
            self.table.setCellWidget(r, c, w_)

    def del_rows(self):
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)
        self.refresh_now()

    def values(self):
        slots = []
        for r in range(self.table.rowCount()):
            sc, gr, day, t0, t1 = (self.table.cellWidget(r, c) for c in range(5))
            if None in (sc, gr, day, t0, t1) or not sc.currentText().strip():   # ligne en cours de création
                continue
            slots.append(dict(scene=sc.currentText(), group=gr.currentData() or "", day=day.currentData() or "",
                              start=t0.time().toString("HH:mm"), end=t1.time().toString("HH:mm")))
        return planning_norm(dict(on=self.on_chk.isChecked(), pre=self.pre.value(), post=self.post.value(),
                                  slots=slots))

    def refresh_now(self):
        if not hasattr(self, "now_lbl"):
            return
        pl = self.values()
        n = datetime.now()
        act, _pl = self.owner._planning_now(pl, n)
        lines = planning_lines(pl, act, n.date().isoformat(), n.hour * 60 + n.minute)
        self.now_lbl.setText(("Maintenant (" + n.strftime("%H:%M") + ") :\n" + "\n".join(lines)) if lines
                             else "Aucun créneau : toutes les fréquences sont surveillées tout le temps.")


class EmitDialog(QtWidgets.QDialog):
    """📡 Mode émission : le tinySA Ultra devient un petit générateur (porteuse, FM, AM) pour tester un récepteur,
    son afficheur RF, son squelch, un câble… EN CÂBLE, avec un atténuateur. La surveillance doit être arrêtée."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.dev = None
        self.on = False
        self.setWindowTitle("Mode émission (générateur)")
        self.resize(560, 520)
        lay = QtWidgets.QVBoxLayout(self)
        warn = QtWidgets.QLabel(
            "⚠ <b>En câble seulement</b>, avec un atténuateur vers l'entrée antenne du récepteur. Émettre en l'air "
            "sans autorisation est interdit (ANFR / ARCEP). Niveau faible : de −115 à environ −20 dBm.")
        warn.setWordWrap(True)
        lay.addWidget(warn)
        f = QtWidgets.QFormLayout()
        self.f_spin = QtWidgets.QDoubleSpinBox()
        self.f_spin.setDecimals(3)
        self.f_spin.setRange(0.1, 6000.0)
        self.f_spin.setSuffix(" MHz")
        rows = o._sel_rows()
        self.f_spin.setValue(o.watch[rows[0]]["freq"] if rows else 600.0)
        self.f_spin.setToolTip("Fréquence émise. tinySA Ultra : jusqu'à ~800 MHz en sortie directe (au-delà : niveau "
                               "non garanti).")
        self.list_combo = QtWidgets.QComboBox()
        self.list_combo.addItem("— choisir dans ma liste —", None)
        for w in o.watch:
            self.list_combo.addItem(f"{w['name']}  {w['freq']:.3f}", w["freq"])
        self.list_combo.setToolTip("Prendre la fréquence d'une ligne de ta liste.")
        self.list_combo.activated.connect(lambda *_: self.list_combo.currentData() and
                                          self.f_spin.setValue(self.list_combo.currentData()))
        self.lvl = QtWidgets.QDoubleSpinBox()
        self.lvl.setRange(-115.0, -10.0)
        self.lvl.setValue(-60.0)
        self.lvl.setSuffix(" dBm")
        self.lvl.setToolTip("Niveau de sortie (le firmware le borne à ce que le tinySA sait faire).")
        self.mod = QtWidgets.QComboBox()
        for k, t in GEN_MODS:
            self.mod.addItem(t, k)
        self.mod.setCurrentIndex(1)
        self.mod.setToolTip("Porteuse pure, FM (son d'un micro analogique), AM.")
        self.dev_spin = QtWidgets.QDoubleSpinBox()
        self.dev_spin.setRange(1.0, 300.0)
        self.dev_spin.setValue(25.0)
        self.dev_spin.setSuffix(" kHz")
        self.dev_spin.setToolTip("Excursion FM (un micro HF : quelques dizaines de kHz).")
        self.tone = QtWidgets.QSpinBox()
        self.tone.setRange(100, 6000)
        self.tone.setValue(1000)
        self.tone.setSuffix(" Hz")
        self.tone.setToolTip("Fréquence du son de test (modulation).")
        f.addRow("Fréquence :", self.f_spin)
        f.addRow("", self.list_combo)
        f.addRow("Niveau :", self.lvl)
        f.addRow("Modulation :", self.mod)
        f.addRow("Excursion FM :", self.dev_spin)
        f.addRow("Son de test :", self.tone)
        lay.addLayout(f)
        self.walk_chk = QtWidgets.QCheckBox("Parcourir ma liste (une fréquence toutes les")
        self.walk_chk.setToolTip("Passe d'une fréquence de ta liste à l'autre : vérifier chaque récepteur à la suite.")
        self.walk_s = QtWidgets.QSpinBox()
        self.walk_s.setRange(1, 120)
        self.walk_s.setValue(5)
        self.walk_s.setSuffix(" s)")
        self.walk_s.setToolTip("Temps passé sur chaque fréquence.")
        lay.addLayout(owner._row(self.walk_chk, self.walk_s, None))
        self.cable_chk = QtWidgets.QCheckBox("Je suis en câble (atténuateur), pas sur une antenne")
        self.cable_chk.setToolTip("Obligatoire pour émettre.")
        self.go = QtWidgets.QPushButton("📡 Émettre")
        self.go.setCheckable(True)
        self.go.setToolTip("Met le tinySA en générateur et allume la sortie. La surveillance doit être arrêtée.")
        self.go.toggled.connect(lambda *_: self.toggle(self.go.isChecked()))
        lay.addLayout(owner._row(self.cable_chk, None, self.go))
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch(1)
        for w_ in (self.f_spin, self.lvl, self.dev_spin, self.tone):
            w_.valueChanged.connect(lambda *_: self.apply())
        self.mod.currentIndexChanged.connect(lambda *_: self.apply())
        self.walk_i = 0
        self.walk_t = QtCore.QTimer(self)
        self.walk_t.timeout.connect(self._walk)
        self.walk_chk.toggled.connect(lambda *_: self._walk_toggle())
        self.sent = []                             # commandes envoyées (diagnostic, tests)

    def _send(self, cmds):
        self.sent += cmds
        if self.dev is None:                       # mode démo : rien à envoyer
            return ""
        for c in cmds:
            ok_, err = self.dev.try_cmd(c)
            if not ok_:
                return err
        return ""

    def toggle(self, on):
        o = self.owner
        if on:
            def no(txt):
                self.msg.setText(txt)
                self.go.blockSignals(True)
                self.go.setChecked(False)
                self.go.blockSignals(False)
            if not self.cable_chk.isChecked():
                return no("Coche d'abord « je suis en câble ».")
            if o.is_running():
                return no("Arrête d'abord la surveillance (■ Arrêter) : le tinySA ne peut pas balayer et émettre "
                          "en même temps.")
            if not o.demo_chk.isChecked():
                port = o.port1()
                if not port:
                    return no("Aucun tinySA branché.")
                try:
                    self.dev = TinySA(port, int(o.baud_combo.currentData() or 115200))
                except Exception as e:  # noqa: BLE001
                    return no(f"tinySA injoignable : {e}")
            err = self._send(["mode low output"] + self._cmds() + ["output on"])
            self.on = True
            self.go.setText("■ Couper l'émission")
            self.msg.setText(("⚠ " + err) if err else self._state_txt())
            o.set_status("📡 Mode émission : le tinySA émet. ■ Couper l'émission pour revenir à l'analyse.")
            self._walk_toggle()
        else:
            self.walk_t.stop()
            if self.on:
                self._send(["output off", "mode low input"])
            self.on = False
            if self.dev is not None:
                self.dev.close()
                self.dev = None
            self.go.setText("📡 Émettre")
            self.msg.setText("Émission coupée, tinySA revenu en analyseur.")

    def _cmds(self):
        return gen_commands(self.f_spin.value(), self.lvl.value(), self.mod.currentData(), self.dev_spin.value(),
                            self.tone.value())

    def _state_txt(self):
        return (f"📡 Émission : {self.f_spin.value():.3f} MHz · {self.lvl.value():.1f} dBm · "
                f"{self.mod.currentText()}")

    def apply(self):
        self.dev_spin.setEnabled(self.mod.currentData() == "fm")
        self.tone.setEnabled(self.mod.currentData() != "off")
        if self.on:
            err = self._send(self._cmds())
            self.msg.setText(("⚠ " + err) if err else self._state_txt())

    def _walk_toggle(self):
        if self.on and self.walk_chk.isChecked() and self.owner.watch:
            self.walk_t.start(self.walk_s.value() * 1000)
            self._walk()
        else:
            self.walk_t.stop()

    def _walk(self):
        ws = self.owner.watch
        if not ws:
            return
        w = ws[self.walk_i % len(ws)]
        self.walk_i += 1
        self.f_spin.setValue(w["freq"])
        self.msg.setText(self._state_txt() + f" · {w['name']}")

    def closeEvent(self, e):
        self.toggle(False)
        super().closeEvent(e)

    def done(self, r):
        self.toggle(False)
        super().done(r)


class SitesDialog(QtWidgets.QDialog):
    """📍 Scans par lieu : un tinySA promené de scène en scène, un scan (max hold) gardé par lieu, tous superposés,
    et leur FUSION (le pire cas de tout le site) pour coordonner l'ensemble ou l'exporter vers WWB / WSM / le logiciel de coord."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Scans par lieu")
        self.resize(1000, 640)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Promène le tinySA : à chaque scène, laisse tourner le scan quelques minutes (max hold), puis "
            "« 📍 Garder le scan » pour ce lieu. Les spectres de tous les lieux se superposent ; la <b>fusion</b> "
            "(le plus fort de tous, en blanc) sert à coordonner tout le site et s'exporte vers WWB / WSM / EazyRF.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.site_combo = QtWidgets.QComboBox()
        self.site_combo.setEditable(True)
        names = [x["name"] for x in o.site_scans] + [x["name"] for x in o.scenes]
        for n_ in dict.fromkeys(names):
            self.site_combo.addItem(n_)
        if not names:
            self.site_combo.setEditText("Lieu 1")
        self.site_combo.setToolTip("Nom du lieu (les scènes sont proposées) ; tape un nouveau nom pour un autre lieu.")
        self.merge_chk = QtWidgets.QCheckBox("Ajouter au scan déjà gardé (max)")
        self.merge_chk.setChecked(True)
        self.merge_chk.setToolTip("Coché : on garde le plus fort de l'ancien et du nouveau scan de ce lieu.\n"
                                  "Décoché : le nouveau remplace l'ancien.")
        b_keep = QtWidgets.QPushButton("📍 Garder le scan actuel pour ce lieu")
        b_keep.setToolTip("Enregistre le max hold actuel (toutes les bandes) comme scan de ce lieu.")
        b_keep.clicked.connect(lambda *_: self.keep_current())
        b_imp = QtWidgets.QPushButton("📥 Importer un scan…")
        b_imp.setToolTip("Un scan WWB, WSM, CSV… (autre scanner, autre jour) rangé dans ce lieu.")
        b_imp.clicked.connect(lambda *_: self.import_file())
        lay.addLayout(owner._row("Lieu :", self.site_combo, self.merge_chk, b_keep, b_imp, None))
        b_dev = QtWidgets.QPushButton("📡 Mes tinySA et leurs scènes…")
        b_dev.setToolTip("Quel tinySA surveille quelle(s) scène(s) : ses balayages alimentent EN CONTINU le spectre de\n"
                         "ces scènes (clique la scène dans « Mes fréquences » pour le voir).")
        b_dev.clicked.connect(lambda *_: o.open_devices())
        lay.addLayout(owner._row(b_dev, None))
        mid = QtWidgets.QHBoxLayout()
        left = QtWidgets.QVBoxLayout()
        self.lst = QtWidgets.QListWidget()
        self.lst.setMaximumWidth(300)
        self.lst.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lst.setToolTip("Coche les scans à afficher et à fusionner ; clique un scan pour voir ses infos et ses signaux.\n"
                            "Ctrl + clic / Maj + clic / Ctrl+A : plusieurs scans à la fois (supprimer, masquer, ranger…).\n"
                            "Espace : afficher / masquer les scans choisis · clic droit : toutes les actions.")
        self.lst.itemChanged.connect(lambda it: self._check_changed(it))
        self.lst.currentItemChanged.connect(lambda *_: self._sel_changed())
        self.lst.itemSelectionChanged.connect(lambda *_: self._sel_count())
        self.lst.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lst.customContextMenuRequested.connect(lambda pos: self.list_menu(self.lst.viewport().mapToGlobal(pos)))
        del_key(self.lst, self.delete)             # Suppr = supprimer les scans sélectionnés
        sp = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_Space), self.lst)
        sp.setContext(Qt.ShortcutContext.WidgetShortcut)
        sp.activated.connect(lambda *_: self.toggle_selected())
        for seq, fn in (("Ctrl+Z", o.undo), ("Ctrl+Y", o.redo), ("Ctrl+Shift+Z", o.redo)):
            QtGui.QShortcut(QtGui.QKeySequence(seq), self).activated.connect(
                lambda *_, fn=fn: (fn(), self.fill(), self.msg.setText(o.stat_lbl.text())))
        left.addWidget(self.lst, 1)
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setMaximumWidth(300)
        self.info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        left.addWidget(self.info)
        b_ren = QtWidgets.QPushButton("Renommer…")
        b_ren.setToolTip("Renomme le scan sélectionné (il reste rangé dans sa scène).")
        b_ren.clicked.connect(lambda *_: self.rename())
        b_mv = QtWidgets.QPushButton("Ranger dans une scène…")
        b_mv.setToolTip("Range le scan sélectionné dans une autre scène (coordination par scène, évolution dans le temps).")
        b_mv.clicked.connect(lambda *_: self.move())
        b_del = QtWidgets.QPushButton("Supprimer")
        b_del.setToolTip("Oublie les scans sélectionnés (Suppr) · Ctrl+Z pour annuler.")
        b_del.clicked.connect(lambda *_: self.delete())
        self.vis_btn = QtWidgets.QToolButton()
        self.vis_btn.setText("👁 Afficher")
        self.vis_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.vis_btn.setToolTip("Afficher / masquer plusieurs scans d'un coup. Un scan masqué n'est plus tracé (ici et sur le\n"
                                "spectre principal) ni fusionné ; il reste gardé et se réaffiche quand tu veux.")
        vm = QtWidgets.QMenu(self.vis_btn)
        for txt, fn in (("Afficher les scans choisis", lambda: self.set_hidden(self.sel_names(), False)),
                        ("Masquer les scans choisis", lambda: self.set_hidden(self.sel_names(), True)),
                        ("Afficher seulement les scans choisis", lambda: self.only_selected()),
                        (None, None),
                        ("Tout afficher", lambda: self.set_hidden(self.all_names(), False)),
                        ("Tout masquer", lambda: self.set_hidden(self.all_names(), True))):
            if txt is None:
                vm.addSeparator()
            else:
                vm.addAction(txt).triggered.connect(lambda *_, fn=fn: fn())
        self.vis_btn.setMenu(vm)
        self.sel_lbl = QtWidgets.QLabel("")
        self.sel_lbl.setStyleSheet("color:gray")
        left.addLayout(owner._row(b_ren, b_mv))
        left.addLayout(owner._row(self.vis_btn, b_del))
        left.addWidget(self.sel_lbl)
        mid.addLayout(left)
        self.tabs = QtWidgets.QTabWidget()
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Fréquence (MHz)")
        self.plot.setLabel("left", "Niveau (dBm)")
        self.plot.addLegend(offset=(10, 10))
        self.tabs.addTab(self.plot, "Spectres")
        # --- comparer deux lieux
        cw = QtWidgets.QWidget()
        cv = QtWidgets.QVBoxLayout(cw)
        self.cmp_a, self.cmp_b = QtWidgets.QComboBox(), QtWidgets.QComboBox()
        self.cmp_a.setToolTip("Le scan A (en bleu).")
        self.cmp_b.setToolTip("Le scan B (en orange), comparé à A.")
        for c_ in (self.cmp_a, self.cmp_b):
            c_.currentIndexChanged.connect(lambda *_: self.cmp_draw())
        self.cmp_mode = QtWidgets.QComboBox()
        self.cmp_mode.addItem("Deux lieux", "sites")
        self.cmp_mode.addItem("Avant → après (A = avant, B = après)", "time")
        self.cmp_mode.setToolTip("Avant → après : garde un scan avant l'installation des micros (ou avant un changement),\n"
                                 "un autre après : la liste dit ce qui est apparu, a disparu, est monté ou a baissé.")
        self.cmp_mode.currentIndexChanged.connect(lambda *_: self._cmp_mode_changed())
        cv.addLayout(owner._row(self.cmp_mode, "A :", self.cmp_a, "comparé à B :", self.cmp_b, None))
        self.cmp_plot = pg.PlotWidget()
        self.cmp_plot.showGrid(x=True, y=True, alpha=0.25)
        self.cmp_plot.setLabel("left", "Niveau (dBm)")
        self.diff_plot = pg.PlotWidget()
        self.diff_plot.showGrid(x=True, y=True, alpha=0.25)
        self.diff_plot.setLabel("left", "A − B (dB)")
        self.diff_plot.setLabel("bottom", "Fréquence (MHz)")
        self.diff_plot.setXLink(self.cmp_plot)
        self.diff_plot.setMaximumHeight(170)
        cv.addWidget(self.cmp_plot, 2)
        cv.addWidget(self.diff_plot, 1)
        self.cmp_txt = QtWidgets.QLabel("")
        self.cmp_txt.setWordWrap(True)
        self.cmp_txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cv.addWidget(self.cmp_txt)
        self.chg_table = QtWidgets.QTableWidget(0, 5)
        self.chg_table.setHorizontalHeaderLabels(["Changement", "MHz", "Avant", "Après", "Écart"])
        self.chg_table.verticalHeader().setVisible(False)
        self.chg_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.chg_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.chg_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.chg_table.setToolTip("Ce qui a changé entre « avant » (A) et « après » (B). Double-clic = voir sur le spectre.")
        self.chg_table.cellDoubleClicked.connect(lambda r, c: self._chg_view(r))
        self.chg_table.setMaximumHeight(170)
        self.chg_table.hide()
        cv.addWidget(self.chg_table)
        self.tabs.addTab(cw, "Comparer (lieux, avant / après)")
        # --- signaux du scan sélectionné
        sw = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(sw)
        self.pk_thr = QtWidgets.QDoubleSpinBox()
        self.pk_thr.setRange(-130.0, 0.0)
        self.pk_thr.setSuffix(" dBm")
        self.pk_thr.setDecimals(1)
        self.pk_thr.setValue(o.thr_spin.value())
        self.pk_thr.setToolTip("Signaux au-dessus de ce niveau (au départ : ton seuil « occupé »).")
        self.pk_only = QtWidgets.QCheckBox("Seulement ceux vus uniquement ici")
        self.pk_only.setToolTip("Au moins 10 dB plus forts que dans tous les autres lieux : un émetteur proche de ce lieu.")
        for w_ in (self.pk_thr.valueChanged, self.pk_only.toggled):
            w_.connect(lambda *_: self.peaks_fill())
        sv.addLayout(owner._row("Au-dessus de", self.pk_thr, self.pk_only, None))
        self.pk_table = QtWidgets.QTableWidget(0, 5)
        self.pk_table.setHorizontalHeaderLabels(["MHz", "Niveau (dBm)", "Largeur (kHz)", "Type", "Dans ma liste"])
        self.pk_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.pk_table.verticalHeader().setVisible(False)
        self.pk_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.pk_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pk_table.setToolTip("Les signaux du scan sélectionné. Sélectionne des lignes puis ajoute-les à ta liste.")
        sv.addWidget(self.pk_table, 1)
        b_ext = QtWidgets.QPushButton("＋ Ajouter comme émetteurs extérieurs (la coordination les évite)")
        b_ext.setToolTip("Ajoute les signaux choisis (tous si rien n'est choisi) à ta liste, sans statut : ce sont des\n"
                         "émetteurs pour Vérifier le plan et Coordonner (écart et intermod), sans alarme.")
        b_ext.clicked.connect(lambda *_: self.add_ext())
        b_copy = QtWidgets.QPushButton("Copier")
        b_copy.setToolTip("Copie la liste des signaux (MHz, niveau) pour un mail ou un tableur.")
        b_copy.clicked.connect(lambda *_: self.copy_peaks())
        sv.addLayout(owner._row(b_ext, None, b_copy))
        self.tabs.addTab(sw, "Signaux du lieu")
        # --- une scène dans le temps
        tw = QtWidgets.QWidget()
        tv = QtWidgets.QVBoxLayout(tw)
        self.tl_scene = QtWidgets.QComboBox()
        self.tl_scene.setToolTip("Une scène scannée plusieurs fois (après-midi, soir, jour 2…).")
        self.tl_scene.currentIndexChanged.connect(lambda *_: self.tl_draw())
        tv.addLayout(owner._row("Scène :", self.tl_scene, None))
        self.tl_plot = pg.PlotWidget()
        self.tl_plot.showGrid(x=True, y=True, alpha=0.25)
        self.tl_plot.setLabel("bottom", "Fréquence (MHz)")
        self.tl_plot.setLabel("left", "Niveau (dBm)")
        self.tl_plot.addLegend(offset=(10, 10))
        tv.addWidget(self.tl_plot, 1)
        self.tl_txt = QtWidgets.QLabel("")
        self.tl_txt.setWordWrap(True)
        self.tl_txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tv.addWidget(self.tl_txt)
        self.tabs.addTab(tw, "Dans le temps")
        # --- 📍 7.68 : une fréquence dans chaque lieu
        fw = QtWidgets.QWidget()
        fv = QtWidgets.QVBoxLayout(fw)
        self.ev_f = QtWidgets.QDoubleSpinBox()
        self.ev_f.setRange(1.0, 6000.0)
        self.ev_f.setDecimals(3)
        self.ev_f.setSuffix(" MHz")
        self.ev_f.setValue(o.watch[0]["freq"] if o.watch else 600.0)
        self.ev_f.setToolTip("La fréquence à regarder dans chaque scan gardé.")
        self.ev_pick = QtWidgets.QComboBox()
        self.ev_pick.addItem("— ou choisis dans ta liste —", None)
        for w_ in sorted(o.watch, key=lambda x: x["freq"]):
            self.ev_pick.addItem(f"{w_['freq']:.3f}  {w_['name'] or ''}", (w_["freq"], float(w_.get("bw") or 0.0)))
        self.ev_pick.setToolTip("Prend une fréquence de « Mes fréquences » (un bloc large garde sa largeur).")
        self.ev_pick.activated.connect(lambda *_: self._ev_from_list())
        self.ev_bw = 0.0
        self.ev_f.valueChanged.connect(lambda *_: self.ev_draw())
        fv.addLayout(owner._row("Fréquence :", self.ev_f, self.ev_pick, None))
        self.ev_table = QtWidgets.QTableWidget(0, 6)
        self.ev_table.setHorizontalHeaderLabels(["Scan", "Scène", "Date", "Niveau", "Au-dessus du bruit", "RBW"])
        for c_ in range(1, 6):
            self.ev_table.horizontalHeader().setSectionResizeMode(c_, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.ev_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.ev_table.verticalHeader().setVisible(False)
        self.ev_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ev_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ev_table.setToolTip("Niveau de cette fréquence dans chaque scan gardé, du plus fort au plus calme.\n"
                                 "Attention : des scans à RBW différentes n'ont pas les mêmes niveaux.")
        fv.addWidget(self.ev_table, 2)
        self.ev_plot = pg.PlotWidget()
        self.ev_plot.showGrid(x=False, y=True, alpha=0.25)
        self.ev_plot.setLabel("left", "Niveau (dBm)")
        self.ev_plot.setMinimumHeight(120)
        fv.addWidget(self.ev_plot, 1)
        self.ev_txt = QtWidgets.QLabel("")
        self.ev_txt.setWordWrap(True)
        self.ev_txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        fv.addWidget(self.ev_txt)
        self.tabs.addTab(fw, "Une fréquence partout")
        self.tabs.currentChanged.connect(lambda *_: self.refresh_tab())
        mid.addWidget(self.tabs, 1)
        lay.addLayout(mid, 1)
        b_rep = QtWidgets.QPushButton("📄 Rapport d'étude de site…")
        b_rep.setToolTip("Une page à imprimer en PDF : chaque lieu (infos, spectre, signaux, ce qui n'est vu qu'ici), la\n"
                         "fusion du site et l'évolution des scènes scannées plusieurs fois. Pour la prod ou la coord.")
        b_rep.clicked.connect(lambda *_: self.report())
        self.what = QtWidgets.QComboBox()
        self.what.addItem("la fusion (lieux cochés)", "merge")
        self.what.addItem("le lieu sélectionné", "one")
        self.what.setToolTip("Quoi exporter.")
        self.fmt = QtWidgets.QComboBox()
        for k, t in (("wwb", "Shure WWB (.csv)"), ("wsm", "Sennheiser WSM (.csv)"), ("wisycom", "Wisycom Manager (.csv)"),
                     ("tti", "TTI (.csv)"), ("csv", "CSV MHz ; dBm")):
            self.fmt.addItem(t, k)
        self.fmt.setToolTip("Comme les exports de chaque logiciel : WWB, WSM, Wisycom Manager, TTI · CSV : EazyRF, Excel…")
        b_exp = QtWidgets.QPushButton("💾 Exporter…")
        b_exp.setToolTip("Enregistre le scan choisi pour un logiciel de coordination.")
        b_exp.clicked.connect(lambda *_: self.export())
        b_ref = QtWidgets.QPushButton("📏 Fusion = référence")
        b_ref.setToolTip("La fusion devient la courbe de référence (seuil = référence + marge possible).")
        b_ref.clicked.connect(lambda *_: self.as_ref())
        lay.addLayout(owner._row(b_rep, None, "Exporter", self.what, self.fmt, b_exp, b_ref))
        self.range = RangeBox(owner)
        lay.addLayout(owner._row(None, "Plage exportée :", self.range))
        rb_note = QtWidgets.QLabel("📏 Scan pour une coordination : RBW fine (30 kHz ou moins). La RBW de chaque scan "
                                   "est notée dans ses infos et dans le nom du fichier exporté.")
        rb_note.setWordWrap(True)
        rb_note.setToolTip(COORD_RBW_TIP)
        lay.addWidget(rb_note)
        self.coord_chk = QtWidgets.QCheckBox("🪄 Coordination et fréquence de secours : éviter ce qui est occupé sur "
                                             "TOUS les lieux (fusion)")
        self.coord_chk.setChecked(o.sites_coord)
        self.coord_chk.setToolTip("Coché : « Trouver N fréquences » et « Fréquence de secours » évitent ce qui est\n"
                                  "occupé n'importe où sur le site (scans gardés + scan en cours), pas seulement ici.")
        self.coord_chk.toggled.connect(lambda *_: setattr(o, "sites_coord", self.coord_chk.isChecked()))
        lay.addWidget(self.coord_chk)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.fill()

    def fill(self, select=None):
        o = self.owner
        cur = select or self._cur_name()
        sel = set(self.sel_names()) if self.lst.count() else set()
        self.lst.blockSignals(True)
        self.lst.clear()
        for i, d in enumerate(o.site_scans):
            when = datetime.fromtimestamp(d["t"]).strftime("%d/%m %H:%M") if d["t"] else ""
            sc = site_doc_scene(d)
            it = QtWidgets.QListWidgetItem(f"{d['name']}  ·  {when}" + (f"  ·  ({sc})" if sc != d["name"] else ""))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked if d.get("hidden") else Qt.CheckState.Checked)
            it.setData(Qt.ItemDataRole.UserRole, d["name"])
            it.setForeground(QtGui.QColor(GROUP_COLORS[i % len(GROUP_COLORS)]))
            self.lst.addItem(it)
            if d["name"] == cur:                  # sans toucher à la sélection (plusieurs scans choisis gardés)
                self.lst.setCurrentItem(it, QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
            if d["name"] in sel or (not sel and d["name"] == cur):
                it.setSelected(True)
        self.lst.blockSignals(False)
        self._sel_count()
        names = [d["name"] for d in o.site_scans]
        for c_, k in ((self.cmp_a, 0), (self.cmp_b, 1)):
            old = c_.currentText()
            c_.blockSignals(True)
            c_.clear()
            c_.addItems(names)
            c_.setCurrentIndex(c_.findText(old) if old in names else min(k, len(names) - 1))
            c_.blockSignals(False)
        old = self.tl_scene.currentText()
        scenes = [s_ for s_ in dict.fromkeys(site_doc_scene(d) for d in o.site_scans)
                  if len(scene_timeline(o.site_scans, s_)) > 1]
        self.tl_scene.blockSignals(True)
        self.tl_scene.clear()
        self.tl_scene.addItems(scenes)
        if old in scenes:
            self.tl_scene.setCurrentText(old)
        self.tl_scene.blockSignals(False)
        self.redraw()
        self._sel_changed()

    def sel_names(self):
        """Scans choisis dans la liste (plusieurs possibles), sinon celui qui a le focus."""
        names = [it.data(Qt.ItemDataRole.UserRole) for it in self.lst.selectedItems()]
        if not names and self.lst.currentItem() is not None:
            names = [self.lst.currentItem().data(Qt.ItemDataRole.UserRole)]
        order = [d["name"] for d in self.owner.site_scans]
        return [n_ for n_ in order if n_ in set(names)]

    def all_names(self):
        return [d["name"] for d in self.owner.site_scans]

    def _sel_count(self):
        n_ = len(self.lst.selectedItems())
        self.sel_lbl.setText(TR("{} scans choisis").format(n_) if n_ > 1 else "")

    def _check_changed(self, it):
        name = it.data(Qt.ItemDataRole.UserRole)
        hide = it.checkState() != Qt.CheckState.Checked
        names = self.sel_names()
        self.set_hidden(names if name in names and len(names) > 1 else [name], hide)   # case cochée dans une sélection

    def set_hidden(self, names, hidden):
        o = self.owner
        names = list(names)
        if not names:
            self.msg.setText("Choisis d'abord un ou plusieurs scans dans la liste.")
            return
        o.site_scans = site_set_hidden(o.site_scans, names, hidden)
        self.fill()
        o.update_site_curve()
        self.msg.setText((TR("{} scan(s) masqué(s) : plus tracés ni fusionnés (toujours gardés).") if hidden
                          else TR("{} scan(s) affiché(s).")).format(len(names)))

    def only_selected(self):
        names = set(self.sel_names())
        if not names:
            self.msg.setText("Choisis d'abord un ou plusieurs scans dans la liste.")
            return
        o = self.owner
        o.site_scans = site_set_hidden(site_set_hidden(o.site_scans, self.all_names(), True), names, False)
        self.fill()
        o.update_site_curve()
        self.msg.setText(TR("Seulement {} scan(s) affiché(s).").format(len(names)))

    def toggle_selected(self):
        names = self.sel_names()
        if names:
            first = next(d for d in self.owner.site_scans if d["name"] == names[0])
            self.set_hidden(names, not first.get("hidden"))

    def select_scene(self, scene):
        self.lst.clearSelection()
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            d = self._doc(it.data(Qt.ItemDataRole.UserRole))
            if d is not None and site_doc_scene(d) == scene:
                it.setSelected(True)

    def list_menu(self, gpos):
        names = self.sel_names()
        m = QtWidgets.QMenu(self)
        n_ = len(names)
        acts = {}
        if n_:
            acts[m.addAction(TR("👁 Afficher ({})").format(n_))] = lambda: self.set_hidden(names, False)
            acts[m.addAction(TR("🙈 Masquer ({})").format(n_))] = lambda: self.set_hidden(names, True)
            acts[m.addAction("Afficher seulement ceux-ci")] = lambda: self.only_selected()
            m.addSeparator()
            if n_ == 1:
                acts[m.addAction("Renommer…")] = lambda: self.rename()
            acts[m.addAction(TR("Ranger dans une scène… ({})").format(n_))] = lambda: self.move()
            d0 = self._doc(names[0])
            if d0 is not None:
                sc = site_doc_scene(d0)
                acts[m.addAction(TR("Choisir tous les scans de « {} »").format(sc))] = lambda: self.select_scene(sc)
            m.addSeparator()
            acts[m.addAction(TR("🗑 Supprimer ({})").format(n_))] = lambda: self.delete()
            m.addSeparator()
        acts[m.addAction("Tout choisir (Ctrl+A)")] = lambda: self.lst.selectAll()
        acts[m.addAction("Tout afficher")] = lambda: self.set_hidden(self.all_names(), False)
        a = m.exec(gpos)
        if a in acts:
            acts[a]()

    def _cur_name(self):
        it = self.lst.currentItem() if hasattr(self, "lst") else None
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def _cur(self):
        n_ = self._cur_name()
        return next((d for d in self.owner.site_scans if d["name"] == n_), None)

    def _sel_changed(self):
        d = self._cur()
        if d is None:
            self.info.setText("Clique un scan pour voir ses infos." if self.owner.site_scans else "")
        else:
            i_ = site_scan_info(d)
            when = datetime.fromtimestamp(i_["t"]).strftime("%d/%m/%Y %H:%M") if i_["t"] else "—"
            self.info.setText(f"<b>{html_esc(d['name'])}</b><br>Scène : {html_esc(i_['scene'])}<br>Le {when}"
                              + (f" · durée {fmt_duration(i_['dur'])}" if i_["dur"] else "")
                              + f"<br>{i_['lo']:.3f}–{i_['hi']:.3f} MHz · {i_['bands']} bande(s)<br>"
                              f"{i_['n']} points · pas {i_['step']:g} kHz · "
                              + TR(rbw_text(i_["rbw"], i_["rbw_est"])))
        self.refresh_tab()

    def refresh_tab(self):
        k = self.tabs.currentIndex()
        if k == 1:
            self.cmp_draw()
        elif k == 2:
            self.peaks_fill()
        elif k == 3:
            self.tl_draw()
        elif k == 4:
            self.ev_draw()

    def rename(self):
        d = self._cur()
        if d is None:
            self.msg.setText("Choisis d'abord un scan dans la liste.")
            return
        new, ok = QtWidgets.QInputDialog.getText(self, "Renommer le scan", "Nouveau nom :", text=d["name"])
        if ok:
            self.do_rename(d["name"], new)

    def do_rename(self, old, new):
        o = self.owner
        lst, err = site_rename(o.site_scans, old, new)
        if err:
            self.msg.setText(err)
            return False
        o.site_scans = lst
        self.fill(select=new.strip()[:60])
        o.update_site_curve()
        self.msg.setText(f"« {old} » renommé en « {new.strip()[:60]} ».")
        return True

    def move(self):
        names = self.sel_names()
        if not names:
            self.msg.setText("Choisis d'abord un scan dans la liste.")
            return
        o = self.owner
        d = self._doc(names[0])
        none_ = TR("(aucune : le scan est son propre lieu)")
        items = [none_] + [s_["name"] for s_ in o.scenes]
        what = f"« {names[0]} »" if len(names) == 1 else TR("{} scans").format(len(names))
        sc, ok = QtWidgets.QInputDialog.getItem(self, "Ranger dans une scène", TR("Scène de {} :").format(what), items,
                                                max(0, items.index(site_doc_scene(d))) if site_doc_scene(d) in items
                                                else 0, True)
        if ok:
            self.do_move(names, "" if sc == none_ else sc.strip())

    def do_move(self, names, scene):
        o = self.owner
        names = [names] if isinstance(names, str) else list(names)
        for name in names:
            o.site_scans = site_move(o.site_scans, name, scene)
        self.fill(select=names[0])
        o.update_site_curve()
        self.msg.setText(f"« {names[0]} » rangé dans « {scene or names[0]} »." if len(names) == 1 else
                         TR("{} scans rangés dans « {} ».").format(len(names), scene or "—"))

    def _doc(self, name):
        return next((d for d in self.owner.site_scans if d["name"] == name), None)

    def cmp_draw(self):
        a, b = self._doc(self.cmp_a.currentText()), self._doc(self.cmp_b.currentText())
        self.cmp_plot.clear()
        self.diff_plot.clear()
        if a is None or b is None or a is b:
            self.cmp_txt.setText("Choisis deux scans différents." if len(self.owner.site_scans) > 1 else
                                 "Il faut au moins deux scans gardés pour comparer.")
            return
        for d, c_ in ((a, "#4f8ef7"), (b, "#f0a030")):
            Fd, Ld = gap_nan(d["f"], d["l"])
            self.cmp_plot.plot(Fd, Ld, pen=pg.mkPen(c_, width=1.2), connect="finite")
        F, D = diff_spectra(a["f"], a["l"], b["f"], b["l"])
        if F is not None:
            Fg, Dg = gap_nan(F, D)
            self.diff_plot.plot(Fg, Dg, pen=pg.mkPen("#e5e7eb", width=1.0), connect="finite")
            self.diff_plot.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen("#888", style=Qt.PenStyle.DashLine)))
        thr = self.owner.thr_spin.value()
        na, nb = compare_spectra(a["f"], a["l"], b["f"], b["l"], thr)

        def lst_(x):
            return ", ".join(f"{p['f']:.3f} ({p['level']:.0f} dBm)" for p in x[:12]) + (" …" if len(x) > 12 else "") \
                or "rien"
        if self.cmp_mode.currentData() == "time":
            self._changes = scan_changes(a["f"], a["l"], b["f"], b["l"], thr)
            t = self.chg_table
            t.setRowCount(len(self._changes))
            for r, x in enumerate(self._changes):
                vals = (TR(CHANGE_LABELS[x["kind"]]), f"{x['f']:.3f}",
                        "" if x["before"] is None else self.owner.lvl(x["before"], suffix=True),
                        "" if x["after"] is None else self.owner.lvl(x["after"], suffix=True),
                        "" if x["delta"] is None else f"{x['delta']:+.0f} dB")
                for c_, v in enumerate(vals):
                    t.setItem(r, c_, QtWidgets.QTableWidgetItem(v))
            cnt = {k: sum(1 for x in self._changes if x["kind"] == k) for k in CHANGE_LABELS}
            self.cmp_txt.setText("<b>" + TR("Avant « {} » → après « {} »").format(html_esc(a["name"]), html_esc(b["name"]))
                                 + "</b> " + TR(": {} apparu(s), {} disparu(s), {} plus fort(s), {} plus faible(s).").format(
                                     cnt["new"], cnt["gone"], cnt["up"], cnt["down"])
                                 + ("" if self._changes else "<br>" + TR("Rien n'a changé au-dessus du seuil.")))
            return
        self.cmp_txt.setText(f"<b>Seulement à « {html_esc(a['name'])} »</b> (≥ 10 dB de plus) : {lst_(na)}<br>"
                             f"<b>Seulement à « {html_esc(b['name'])} »</b> : {lst_(nb)}")

    def _cmp_mode_changed(self):
        """Avant → après : A = le plus ancien des deux, B = le plus récent (on peut les changer)."""
        tm = self.cmp_mode.currentData() == "time"
        self.chg_table.setVisible(tm)
        if tm:
            a, b = self._doc(self.cmp_a.currentText()), self._doc(self.cmp_b.currentText())
            if a is not None and b is not None and float(a.get("t") or 0) > float(b.get("t") or 0):
                ia, ib = self.cmp_a.currentIndex(), self.cmp_b.currentIndex()
                self.cmp_a.blockSignals(True)
                self.cmp_a.setCurrentIndex(ib)
                self.cmp_a.blockSignals(False)
                self.cmp_b.setCurrentIndex(ia)
        self.cmp_draw()

    def _chg_view(self, r):
        ch = getattr(self, "_changes", [])
        if 0 <= r < len(ch):
            self.owner.view_range(ch[r]["f"] - 1.0, ch[r]["f"] + 1.0, TR("Changement à {} MHz").format(f"{ch[r]['f']:.3f}"))

    def peaks_fill(self):
        o = self.owner
        d = self._cur()
        self.pk_table.setRowCount(0)
        self._peaks = []
        if d is None:
            return
        thr = self.pk_thr.value()
        pk = only_here(o.site_scans, d["name"], thr) if self.pk_only.isChecked() else scan_peaks(d["f"], d["l"], thr)
        known = np.asarray(sorted(w["freq"] for w in o.watch), dtype=float)
        self._peaks = pk
        self.pk_table.setRowCount(len(pk))
        for r, p in enumerate(pk):
            hit = len(known) and float(np.min(np.abs(known - p["f"]))) * 1000.0 <= max(100.0, p["width"] / 2.0)
            vals = (f"{p['f']:.3f}", f"{p['level']:.1f}", f"{p['width']:.0f}",
                    "large (TNT, bloc numérique…)" if p["wide"] else "porteuse", "oui" if hit else "")
            for c_, v in enumerate(vals):
                self.pk_table.setItem(r, c_, QtWidgets.QTableWidgetItem(v))

    def _sel_peaks(self):
        rows = sorted({i.row() for i in self.pk_table.selectedIndexes()})
        return [self._peaks[r] for r in rows if r < len(self._peaks)] or list(getattr(self, "_peaks", []))

    def add_ext(self):
        o = self.owner
        d = self._cur()
        pk = self._sel_peaks()
        if d is None or not pk:
            self.msg.setText("Aucun signal à ajouter.")
            return 0
        sc = site_doc_scene(d) if o.scene_by_name(site_doc_scene(d)) is not None else ""
        for p in pk:
            o._append_watch(f"Ext. {p['f']:.3f}", float(p["f"]), status="", scene=sc,
                            bw=round(p["width"] / 1000.0, 3) if p["wide"] else 0.0)
        o.sort_watch()
        o.rebuild_tree()
        o.rebuild_watch_table()
        o._update_markers()
        self.peaks_fill()
        self.msg.setText(f"＋ {len(pk)} émetteur(s) extérieur(s) ajouté(s) à ta liste (sans statut, sans alarme) : "
                         "Vérifier le plan et Coordonner en tiennent compte.")
        return len(pk)

    def copy_peaks(self):
        d = self._cur()
        txt = "\n".join(f"{p['f']:.3f}\t{p['level']:.1f}" for p in self._sel_peaks())
        QtWidgets.QApplication.clipboard().setText(txt)
        self.msg.setText(f"📋 {len(txt.splitlines())} signal(aux) copié(s)" + (f" ({d['name']})." if d else "."))

    def _ev_from_list(self):
        v = self.ev_pick.currentData()
        if v:
            self.ev_bw = float(v[1] or 0.0)
            self.ev_f.blockSignals(True)
            self.ev_f.setValue(float(v[0]))
            self.ev_f.blockSignals(False)
            self.ev_draw()

    def show_freq(self, f, bw=0.0):
        """Ouvre l'onglet « Une fréquence partout » sur f (clic droit de la liste)."""
        self.ev_bw = float(bw or 0.0)
        self.ev_f.blockSignals(True)
        self.ev_f.setValue(float(f))
        self.ev_f.blockSignals(False)
        self.tabs.setCurrentIndex(4)
        self.ev_draw()

    def ev_draw(self):
        o = self.owner
        f = self.ev_f.value()
        rows = level_everywhere(o.site_scans, f, self.ev_bw)
        self.ev_rows = rows
        t = self.ev_table
        t.setRowCount(len(rows))
        for r, d in enumerate(rows):
            vals = (d["name"], d["scene"] or "—", _fmt_ts(d["t"], "%d/%m %H:%M"),
                    o.lvl(d["level"], suffix=True) if d["level"] is not None else TR("pas mesurée"),
                    f"{d['margin']:+.0f} dB" if d["margin"] is not None else "—",
                    rbw_text(d["rbw"], d["rbw_est"], TR))
            for c, v in enumerate(vals):
                t.setItem(r, c, QtWidgets.QTableWidgetItem(str(v)))
        self.ev_plot.clear()
        got = [d for d in rows if d["level"] is not None]
        if got:
            lo = min(d["floor"] if d["floor"] is not None else d["level"] for d in got) - 5.0
            col = QtGui.QColor(o.theme.get("accent", "#0a84ff"))
            self.ev_plot.addItem(pg.BarGraphItem(x=list(range(len(got))), y0=lo, y1=[d["level"] for d in got], width=0.6,
                                                 brush=col))
            fl = [(k, d["floor"]) for k, d in enumerate(got) if d["floor"] is not None]
            if fl:
                self.ev_plot.plot([k for k, _ in fl], [v for _, v in fl], pen=None, symbol="t", symbolSize=9,
                                  symbolBrush=o.theme.get("thr", "#ff9f0a"), name="bruit")
            ax = self.ev_plot.getAxis("bottom")
            ax.setTicks([[(k, d["name"][:18]) for k, d in enumerate(got)]])
        self.ev_txt.setText(TR(level_everywhere_text(rows, f, lambda v: o.lvl(v, suffix=True)))
                            + ("<br>" + TR("Triangle = bruit de fond du scan ; barre = niveau de la fréquence.") if got else ""))

    def tl_draw(self):
        o = self.owner
        self.tl_plot.clear()
        sc = self.tl_scene.currentText()
        tl = scene_timeline(o.site_scans, sc) if sc else []
        if len(tl) < 2:
            self.tl_txt.setText("Aucune scène n'a encore plusieurs scans : garde un scan de la même scène à un autre moment "
                                "(📍 Garder, ou 💾 depuis la vue Terrain du téléphone).")
            return
        n = len(tl)
        for k, d in enumerate(tl):                 # du plus ancien (bleu pâle) au plus récent (orange vif)
            t_ = k / max(1, n - 1)
            c_ = QtGui.QColor.fromRgbF(0.3 + 0.65 * t_, 0.55 - 0.05 * t_, 0.95 - 0.75 * t_)
            Fd, Ld = gap_nan(d["f"], d["l"])
            when = datetime.fromtimestamp(d["t"]).strftime("%d/%m %H:%M") if d["t"] else d["name"]
            self.tl_plot.plot(Fd, Ld, pen=pg.mkPen(c_, width=1.2), connect="finite", name=when)
        new, gone = compare_spectra(tl[-1]["f"], tl[-1]["l"], tl[0]["f"], tl[0]["l"], o.thr_spin.value())

        def lst_(x):
            return ", ".join(f"{p['f']:.3f} ({p['level']:.0f} dBm)" for p in x[:12]) + (" …" if len(x) > 12 else "") \
                or "aucun"
        self.tl_txt.setText(f"Du plus ancien au plus récent ({n} scans). <b>Apparus :</b> {lst_(new)}<br>"
                            f"<b>Disparus :</b> {lst_(gone)}")

    def report(self, path=None):
        o = self.owner
        if not o.site_scans:
            self.msg.setText("Aucun scan gardé : rien à mettre dans le rapport.")
            return None
        meta = getattr(o, "show_meta", {}) or {}
        html_ = TR.html(site_report_html(o.site_scans, o.thr_spin.value(),
                                         title=TR("Étude de site") + (f" — {meta['name']}" if meta.get("name") else ""),
                                         venue=meta.get("venue", ""), generated=datetime.now().strftime("%d/%m/%Y %H:%M")))
        ask = path is None
        if ask:
            dflt = str(o.log_dir / "rapports" / f"etude_site_{datetime.now():%Y%m%d_%H%M}.html")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le rapport d'étude de site", dflt,
                                                            "Page web (*.html)")
            if not path:
                return None
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(html_, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            self.msg.setText(f"Rapport impossible : {e}")
            return None
        self.msg.setText(f"📄 Rapport enregistré : {path} (navigateur › Imprimer › Enregistrer en PDF)")
        if ask:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
        return path

    def checked(self):
        names = {self.lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lst.count())
                 if self.lst.item(i).checkState() == Qt.CheckState.Checked}
        return [d for d in self.owner.site_scans if d["name"] in names]

    def merged(self):
        return merge_scans([(d["f"], d["l"]) for d in self.checked()])

    def redraw(self):
        o = self.owner
        self._hidden = {self.lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lst.count())
                        if self.lst.item(i).checkState() != Qt.CheckState.Checked}
        self.plot.clear()
        for i, d in enumerate(o.site_scans):
            if d in self.checked():
                Fd, Ld = gap_nan(d["f"], d["l"])             # pas de trait entre deux bandes
                self.plot.plot(Fd, Ld, pen=pg.mkPen(GROUP_COLORS[i % len(GROUP_COLORS)], width=1.2), name=d["name"],
                               connect="finite")
        F, L = self.merged()
        if F is not None and len(self.checked()) > 1:
            Fp, Lp = gap_nan(F, L)
            self.plot.plot(Fp, Lp, pen=pg.mkPen("#ffffff", width=1.6, style=Qt.PenStyle.DashLine), name="Fusion",
                           connect="finite")
        n = len(o.site_scans)
        self.msg.setText(f"{n} lieu(x) gardé(s)." if n else "Aucun lieu encore : lance un scan, puis « 📍 Garder ».")

    def _store(self, name, F, L, dur=None):
        o = self.owner
        name = name.strip()
        if not name:
            self.msg.setText("Donne un nom au lieu.")
            return False
        old = next((d for d in o.site_scans if d["name"] == name), None)
        rbw, est = o.scan_rbw(F)
        if old is not None and self.merge_chk.isChecked():
            F, L = merge_scans([(old["f"], old["l"]), (F, L)])
            rbw = rbw_merge(old.get("rbw"), rbw)
            est = est or bool(old.get("rbw_est"))
            if dur and old.get("dur"):
                dur += old["dur"]                   # le scan gardé cumule les deux passages
        o.site_scans = site_replace(o.site_scans, site_scan_doc(name, F, L, time.time(),
                                                                scene=old.get("scene") if old else None, dur=dur,
                                                                rbw=rbw, rbw_est=est))
        if name in o._site_base:                   # la fusion continue (tinySA posé ici) repart de ce scan
            o._site_base[name] = next(d for d in o.site_scans if d["name"] == name)
        self.fill()
        return True

    def keep_current(self):
        F, L = self.owner.fresh_FL(use_max=True, any_age=True)
        if F is None:
            self.msg.setText("Pas encore de scan : lance ▶ Démarrer et laisse tourner quelques minutes ici.")
            return
        name = self.site_combo.currentText()
        t0 = self.owner._mh_t0
        if self._store(name, F, L, dur=time.time() - t0 if t0 else None):
            self.msg.setText(f"📍 Scan gardé pour « {name.strip()} » ({len(F)} points).")

    def import_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Importer un scan (WWB, WSM, CSV…)", "",
                                                        "Scans (*.csv *.txt *.sdb3);;Tous les fichiers (*)")
        if not path:
            return
        try:
            F, L, _info = parse_scan_text(decode_text(Path(path).read_bytes()))
        except Exception as e:  # noqa: BLE001
            self.msg.setText(f"Scan illisible : {e}")
            return
        name = self.site_combo.currentText().strip() or Path(path).stem
        if self._store(name, F, L):
            self.msg.setText(f"📥 Scan importé dans « {name} » ({len(F)} points).")

    def delete(self, names=None):
        names = list(names) if names is not None else self.sel_names()
        if not names:
            self.msg.setText("Choisis d'abord un scan dans la liste.")
            return
        gone = set(names)
        self.owner.undo_track()                    # l'état d'avant est bien noté (Ctrl+Z ramène TOUT ce qui est supprimé)
        self.owner.site_scans = [d for d in self.owner.site_scans if d["name"] not in gone]
        for name in names:
            self.owner.forget_site(name)           # sinon le max hold en mémoire de cette scène le recrée 30 s après
        self.lst.clearSelection()
        self.fill()
        self.owner.update_site_curve()
        self.owner.undo_track()
        self.msg.setText(f"« {names[0]} » supprimé · Ctrl+Z pour annuler." if len(names) == 1 else
                         TR("{} scans supprimés · Ctrl+Z pour annuler.").format(len(names)))

    def _pick(self):
        if self.what.currentData() == "merge":
            F, L = self.merged()
            return F, L, "fusion"
        it = self.lst.currentItem()
        d = next((x for x in self.owner.site_scans if it is not None and x["name"] == it.data(Qt.ItemDataRole.UserRole)),
                 None)
        return (None, None, "") if d is None else (np.asarray(d["f"]), np.asarray(d["l"]), d["name"])

    def export(self, path=None):
        F, L, label = self._pick()
        if F is None:
            self.msg.setText("Rien à exporter (coche des lieux, ou sélectionne-en un).")
            return None
        lo, hi = self.range.values()
        F, L = scan_crop(F, L, lo=lo, hi=hi)        # seulement la plage choisie (ex. la bande de tes appareils)
        if not len(F):
            self.msg.setText("Rien de mesuré dans cette plage.")
            return None
        fmt = self.fmt.currentData()
        docs = self.checked() if self.what.currentData() == "merge" else [
            d for d in self.owner.site_scans if d["name"] == label]
        rb, est = rbw_combine([(d.get("rbw"), bool(d.get("rbw_est"))) for d in docs])
        if path is None:
            tag = rbw_tag(rb)
            dflt = str(self.owner.log_dir / f"scan_{session_name(label)}_{fmt}{'_' + tag if tag else ''}.csv")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter le scan", dflt, "CSV (*.csv)")
            if not path:
                return None
        try:
            Path(path).write_text(scan_write(F, L, fmt, title=label), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            self.msg.setText(f"Export impossible : {e}")
            return None
        self.msg.setText(f"💾 « {label} » exporté : {path}\n" + rbw_coord_line(rb, est, TR, step=scan_step_khz(F))[0])
        return path

    def as_ref(self):
        F, L = self.merged()
        if F is None:
            return
        o = self.owner
        o._set_ref([(F, L)])
        o._save_ref_file(REF_PATH)
        o.showref_chk.setChecked(True)
        o.reeval()
        self.msg.setText("📏 La fusion est la nouvelle courbe de référence.")


def net_test(addr, timeout=1.5):
    """🔌 Le relais (Raspberry Pi, autre PC) répond-il à cette adresse ? -> (bool, texte court)."""
    hp = net_host_port(addr)
    if hp is None:
        return False, TR("adresse illisible")
    t0 = time.time()
    try:
        with socket.create_connection(hp, timeout=timeout):
            pass
    except socket.gaierror:
        return False, TR("nom introuvable sur ce réseau")
    except OSError:
        return False, TR("ne répond pas")
    return True, TR("répond") + f" ({(time.time() - t0) * 1000:.0f} ms)"


class NewBandDialog(QtWidgets.QDialog):
    """＋ Nouvelle bande à balayer (depuis la liste « Vue ») : un préréglage ou une plage à la main."""

    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle("Nouvelle bande à balayer")
        lay = QtWidgets.QVBoxLayout(self)
        f = QtWidgets.QFormLayout()
        self.preset = QtWidgets.QComboBox()
        self.preset.addItem("Plage à la main", None)
        for p in BAND_PRESETS:
            self.preset.addItem(p[0], p)
        self.preset.setToolTip("Une bande toute prête (UHF micros, IEM, 1G4, 2,4 GHz, aéro…) ou ta propre plage.")
        self.name = QtWidgets.QLineEdit("Ma bande")
        self.name.setToolTip("Nom de la bande (affiché dans « Vue »).")
        self.lo, self.hi = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for sp_, v in ((self.lo, 470.0), (self.hi, 608.0)):
            sp_.setDecimals(3)
            sp_.setRange(0.1, 6000.0)
            sp_.setSuffix(" MHz")
            sp_.setValue(v)
            sp_.setToolTip("Début et fin de la bande.")
        self.preset.currentIndexChanged.connect(lambda *_: self._from_preset())
        f.addRow("Préréglage :", self.preset)
        f.addRow("Nom :", self.name)
        f.addRow("De :", owner._row(self.lo, "à", self.hi))
        lay.addLayout(f)
        note = QtWidgets.QLabel("Le pas suit le réglage ⚡ Points (Auto conseillé). La bande est balayée tout de suite.")
        note.setWordWrap(True)
        lay.addWidget(note)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._step = 200.0

    def _from_preset(self):
        p = self.preset.currentData()
        if p:
            self.name.setText(p[0])
            self.lo.setValue(p[1])
            self.hi.setValue(p[2])
            self._step = float(p[3])

    def values(self):
        lo, hi = sorted((self.lo.value(), self.hi.value()))
        if hi - lo < 0.01:
            hi = lo + 1.0
        return (self.name.text().strip() or "Ma bande"), lo, hi, self._step


class NetProfilesDialog(QtWidgets.QDialog):
    """🌐 tinySA en réseau : les adresses du relais (Raspberry Pi, autre PC) enregistrées, une par Wi-Fi ou par lieu
    (l'IP change d'un réseau à l'autre) ; chacune se choisit en un clic pour le 1er ou le 2ᵉ tinySA. Gardées sur ce PC ET
    dans le show (🎪)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("tinySA en réseau")
        self.resize(720, 460)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Le Raspberry Pi (ou l'autre PC) n'a pas la même adresse sur chaque Wi-Fi : enregistre-en une par réseau "
            "(« Pi · maison », « Pi · festival », « Pi · partage du téléphone »…) et choisis la bonne en un clic, dans la "
            "liste des ports en haut ou ici. Astuce : le nom <b>tinysa-sac.local</b> marche sur la plupart des réseaux, "
            "quelle que soit l'IP (pas sur tous : certains Wi-Fi d'événement le bloquent, d'où les adresses de secours).")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 4)
        lay.addWidget(info)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nom", "Adresse", "Test"])
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 220)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setToolTip("Double-clic pour modifier le nom ou l'adresse (ex. 192.168.1.42, 10.0.0.5:5025, "
                              "tinysa-sac.local).")
        lay.addWidget(self.table, 1)
        del_key(self.table, self.del_row)
        b_add = QtWidgets.QPushButton("＋ Ajouter")
        b_add.setToolTip("Nouvelle adresse (le Pi sur un autre Wi-Fi).")
        b_add.clicked.connect(lambda *_: self.add_row())
        b_del = QtWidgets.QPushButton("Supprimer")
        b_del.setToolTip("Supprime l'adresse sélectionnée.")
        b_del.clicked.connect(lambda *_: self.del_row())
        b_test = QtWidgets.QPushButton("🔌 Tester")
        b_test.setToolTip("Essaie de joindre le relais à chaque adresse (celles choisies, ou toutes) : « répond » = le\n"
                          "Pi est allumé, sur ce réseau, et son relais tourne.")
        b_test.clicked.connect(lambda *_: self.test())
        lay.addLayout(o._row(b_add, b_del, None, b_test))
        b_1 = QtWidgets.QPushButton("Utiliser pour le 1er tinySA")
        b_1.setToolTip("Le 1er tinySA (liste des ports en haut) passe sur cette adresse.")
        b_1.clicked.connect(lambda *_: self.use(0))
        b_2 = QtWidgets.QPushButton("Utiliser pour le 2ᵉ tinySA")
        b_2.setToolTip("Le 2ᵉ tinySA (⚙ Réglages › 2ᵉ tinySA) passe sur cette adresse et est activé.")
        b_2.clicked.connect(lambda *_: self.use(1))
        lay.addLayout(o._row(b_1, b_2, None))
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for p in o.net_profiles:
            self.add_row(p["name"], p["addr"])
        cur = o.net_addr if o.port_net else ""
        self.msg.setText((f"1er tinySA en ce moment : {cur}" + (f" ({net_profile_name(o.net_profiles, cur)})"
                                                                 if net_profile_name(o.net_profiles, cur) else ""))
                         if cur else "Le 1er tinySA est en USB (ou pas encore choisi).")
        self.finished.connect(lambda *_: self.save())

    def add_row(self, name="", addr=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        if not name:
            n = r + 1
            names = {self.table.item(i, 0).text() for i in range(r) if self.table.item(i, 0)}
            while f"Pi {n}" in names:
                n += 1
            name = f"Pi {n}"
        for c_, v in enumerate((name, addr or "192.168.1.", "")):
            it = QtWidgets.QTableWidgetItem(v)
            if c_ == 2:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, c_, it)
        self.table.setCurrentCell(r, 1)

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            n, a = self.table.item(r, 0), self.table.item(r, 1)
            out.append(dict(name=n.text().strip() if n else "", addr=a.text().strip() if a else ""))
        return out

    def values(self):
        return net_profiles_norm(self.rows())

    def save(self):
        o = self.owner
        o.net_profiles = self.values()
        o.refresh_ports()
        o._dev2_ports()
        o._bump()

    def _sel(self):
        rs = sorted({i.row() for i in self.table.selectedIndexes()})
        return rs or list(range(self.table.rowCount()))

    def test(self):
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for r in self._sel():
                a = self.table.item(r, 1).text().strip() if self.table.item(r, 1) else ""
                ok, txt = net_test(a)
                self.table.item(r, 2).setText(("✔ " if ok else "✖ ") + txt)
                QtWidgets.QApplication.processEvents()
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def use(self, dev):
        o = self.owner
        r = self.table.currentRow()
        rows = self.rows()
        if not 0 <= r < len(rows) or parse_device_addr(rows[r]["addr"])[0] != "net":
            self.msg.setText("Choisis une ligne avec une adresse réseau valide (ex. 192.168.1.42).")
            return False
        self.save()
        p = rows[r]
        if dev == 0:
            o.use_net_addr(p["addr"])
        else:
            o.dev2_addr.setEditText(p["addr"])
            o.dev2_chk.setChecked(True)
            o._dev2_changed()
        self.msg.setText((f"1er tinySA → {p['name']} ({p['addr']})." if dev == 0 else
                          f"2ᵉ tinySA → {p['name']} ({p['addr']}).")
                         + " " + TR("Arrête puis relance la surveillance pour s'y connecter." if o.is_running() else
                                    "▶ Démarrer pour s'y connecter."))
        return True


class DevicesDialog(QtWidgets.QDialog):
    """📡 Mes tinySA et leurs scènes (mode expert) : une colonne par tinySA, une ligne par scène, une case = « ce tinySA
    surveille cette scène ». Une ou plusieurs scènes par tinySA, changeable à tout moment, appliqué tout de suite.
    👋 Identifier : l'écran du tinySA clignote ; 🔢 Numéroter : un numéro gravé dedans, ses scènes le suivent."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Mes tinySA et leurs scènes")
        self.setModal(False)
        self.resize(640, 380)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Coche les scènes que surveille chaque tinySA (une ou plusieurs ; tu peux changer à tout moment). Ses "
            "balayages alimentent en continu le spectre de ces scènes : clique une scène dans « Mes fréquences » pour "
            "voir le sien. Deux tinySA sur des scènes différentes : chacun balaye toutes les bandes chez lui. "
            "Tu ne sais plus lequel est lequel ? <b>👋 Identifier</b> fait clignoter son écran.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.grid = QtWidgets.QGridLayout()
        lay.addLayout(self.grid)
        lay.addStretch(1)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.close)
        lay.addWidget(bb)
        self.checks = {}
        self.refresh()

    def refresh(self):
        o = self.owner
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        self.checks = {}
        nd = o.dev_list()
        for ci, d in enumerate(nd):
            col = ci + 1
            live = o.is_running() and d < len(o.dev_live) and o.dev_live[d]
            addr = ("démo" if o.demo_chk.isChecked() else (o.port1() or "—")) if d == 0 \
                else (next((a for d_, a, _o in o.dev_slots() if d_ == d), "") or "—")
            n_ = o.dev_ids.get(d)
            head = QtWidgets.QLabel(f"<b>{dev_ord(d)} tinySA · {o.dev_name(d)}</b><br>"
                                    f"{'● en ligne' if live else '○ pas connecté'} · {addr}"
                                    + (f"<br>n° {n_}" if n_ else ""))
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(head, 0, col)
            b_id = QtWidgets.QPushButton("👋 Identifier")
            b_id.setToolTip("Fait clignoter l'écran de CE tinySA en orange quelques secondes (il faut ▶ Démarrer).")
            b_id.clicked.connect(lambda *_, d=d: o.identify_device(d))
            self.grid.addWidget(b_id, 1, col)
            b_num = QtWidgets.QPushButton("🔢 Numéroter")
            b_num.setToolTip("Grave un numéro dans ce tinySA : si un jour les tinySA sont branchés à l'envers,\n"
                             "l'appli les reconnaît et leurs scènes les suivent.")
            b_num.clicked.connect(lambda *_, d=d: self._number(d))
            self.grid.addWidget(b_num, 2, col)
            mine = o.dev_scenes.get(d, [])
            b_none = QtWidgets.QPushButton("∅ Aucune scène (tout le site)")
            b_none.setToolTip("Ce tinySA ne surveille plus de scène précise : il compte pour tout le site.")
            b_none.setEnabled(bool(mine))
            b_none.clicked.connect(lambda *_, d=d: (o.set_dev_scenes(d, []), self.refresh()))
            self.grid.addWidget(b_none, 3, col)
            sm = QtWidgets.QLabel(("Surveille : " + ", ".join(mine)) if mine else "Surveille : tout le site")
            sm.setWordWrap(True)
            sm.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sm.setStyleSheet("color:#d29922" if mine else "color:gray")
            self.grid.addWidget(sm, 4, col)
        names = list(dict.fromkeys([x["name"] for x in o.scenes] + [x for v in o.dev_scenes.values() for x in v]))
        if not names:
            self.grid.addWidget(QtWidgets.QLabel("Crée d'abord tes scènes (« Classer par scène › groupe »)."), 5, 0, 1, len(nd) + 1)
        for r, name in enumerate(names, start=5):
            lab = QtWidgets.QLabel(name)
            sc = o.scene_by_name(name)
            if sc is not None:
                lab.setStyleSheet(f"color:{sc['color']};font-weight:bold")
            self.grid.addWidget(lab, r, 0)
            for ci, d in enumerate(nd):
                cb = QtWidgets.QCheckBox("")
                cb.setChecked(name in o.dev_scenes.get(d, []))
                cb.setToolTip(f"Le {dev_ord(d)} tinySA surveille « {name} ».")
                cb.toggled.connect(lambda *_, d=d, name=name, cb=cb: self._toggle(d, name, cb.isChecked()))
                self.grid.addWidget(cb, r, ci + 1, alignment=Qt.AlignmentFlag.AlignCenter)
                self.checks[(d, name)] = cb
        if len(nd) < 2:
            tip = QtWidgets.QLabel("Un 2ᵉ tinySA ? Réglages › 2ᵉ tinySA (USB ou réseau, ex. un Raspberry Pi).")
            tip.setStyleSheet("color:gray")
            self.grid.addWidget(tip, len(names) + 5, 0, 1, len(nd) + 1)

    def _toggle(self, d, name, on):
        self.owner.toggle_dev_scene(d, name, on)
        self.msg.setText(self.owner.stat_lbl.text())
        QtCore.QTimer.singleShot(0, self.refresh)            # le résumé « Surveille : … » suit

    def _number(self, d):
        n, ok_ = QtWidgets.QInputDialog.getInt(self, "Numéroter le tinySA", "Numéro à graver dans ce tinySA :",
                                               self.owner.dev_ids.get(d) or (d + 1), 1, 999)
        if ok_:
            self.owner.number_device(d, n)
            self.msg.setText(self.owner.stat_lbl.text())

    def closeEvent(self, e):
        if self.owner._devdlg is self:
            self.owner._devdlg = None
        super().closeEvent(e)

    def done(self, r):
        if self.owner._devdlg is self:
            self.owner._devdlg = None
        super().done(r)


SETTINGS_PAGES = (("detect", "Seuils et alarmes"), ("bands", "Bandes à balayer"), ("measure", "Mesure"),
                  ("dev2", "Plusieurs tinySA et noms"), ("country", "Pays et plan"))


class SettingsDialog(QtWidgets.QDialog):
    """⚙ Réglages : ce qu'on règle une fois (langue, affichage, son, dossiers, connexions), rangé au même endroit.
    Tout s'applique tout de suite."""

    def _init_base(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Réglages")
        self.resize(860, 600)
        lay = QtWidgets.QVBoxLayout(self)
        body = QtWidgets.QHBoxLayout()
        lay.addLayout(body, 1)
        self.nav = QtWidgets.QListWidget()
        self.nav.setFixedWidth(180)
        self.nav.setStyleSheet("QListWidget::item{padding:7px 8px;}")
        self.nav.setToolTip("Les rubriques des réglages.")
        tabs = QtWidgets.QTabWidget()
        tabs.tabBar().hide()
        body.addWidget(self.nav)
        body.addWidget(tabs, 1)
        self.tabs = tabs
        # pages empruntées à la fenêtre principale (seuils, bandes, mesure, 2ᵉ tinySA, pays), rendues à la fermeture
        self.keys, self._borrowed = [], []
        for key, title in SETTINGS_PAGES:
            page = getattr(o, "set_pages", {}).get(key)
            if page is not None:
                tabs.addTab(page, title)            # surtout pas page.show() : la page s'affichait par-dessus les autres
                self.keys.append(key)
                self._borrowed.append(page)
        self.finished.connect(lambda *_: self._give_back())
        # --- Général
        g = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(g)
        self.lang_combo = QtWidgets.QComboBox()
        for k, t in LANGS:
            self.lang_combo.addItem(t, k)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(o.lang or "fr")))
        self.lang_combo.setToolTip("Langue de l'interface (redémarrage proposé).")
        self.lang_combo.activated.connect(lambda *_: o.set_language(self.lang_combo.currentData()))
        self.level_combo = QtWidgets.QComboBox()
        for k, t in UI_LEVELS:
            self.level_combo.addItem(t, k)
        self.level_combo.setCurrentIndex(max(0, self.level_combo.findData(o.ui_level)))
        self.level_combo.setToolTip("Ultra simple : spectre, liste, alarmes · Simple : + réglages essentiels · "
                                    "Expert : tout.")
        self.level_combo.activated.connect(lambda *_: o.set_level(self.level_combo.currentData()))
        self.unit_combo = QtWidgets.QComboBox()
        for k, t in LEVEL_UNITS:
            self.unit_combo.addItem(t, k)
        self.unit_combo.setCurrentIndex(max(0, self.unit_combo.findData(o.unit)))
        self.unit_combo.setToolTip("Unité d'affichage des niveaux (les fichiers restent en dBm).")
        self.unit_combo.activated.connect(lambda *_: o.set_unit(self.unit_combo.currentData()))
        col_btn = QtWidgets.QPushButton("🎨 Couleurs et thèmes…")
        col_btn.setToolTip("Thèmes (Pro sombre, gamme Analyseur, daltoniens…) et chaque couleur une par une.")
        col_btn.clicked.connect(lambda *_: o.edit_colors())
        lab_btn = QtWidgets.QPushButton("🔤 Mots et couleurs (OK, libre, ABSENT…)…")
        lab_btn.setToolTip("Les mots de la colonne Signal et leurs couleurs.")
        lab_btn.clicked.connect(lambda *_: o.edit_labels())
        f.addRow("Langue / Language :", self.lang_combo)
        f.addRow("Interface :", self.level_combo)
        f.addRow("Unité des niveaux :", self.unit_combo)
        pre_btn = QtWidgets.QPushButton("⚡ Préréglages rapides (festival, salle, nuit…)…")
        pre_btn.setToolTip("Règle d'un coup les seuils, la mesure, la rémanence et les alarmes pour une situation type.")
        pre_btn.clicked.connect(lambda *_: o.open_presets())
        f.addRow(pre_btn)
        usr_btn = QtWidgets.QPushButton("👤 Profils utilisateur (mes préférences)…")
        usr_btn.setToolTip("Enregistre / charge tes préférences (affichage, seuils, alarmes, préréglages perso) et "
                           "passe-les à un collègue.")
        usr_btn.clicked.connect(lambda *_: o.open_user_profiles())
        f.addRow(usr_btn)
        f.addRow(col_btn)
        f.addRow(lab_btn)
        self.smooth_chk = QtWidgets.QCheckBox("Courbes lissées (plus joli, mais plus gourmand en processeur)")
        self.smooth_chk.setChecked(bool(getattr(o, "smooth", False)))
        self.smooth_chk.setToolTip("Lissage (antialiasing) des courbes du spectre. Décoché (conseillé) : l'appli consomme\n"
                                   "bien moins de processeur, surtout avec beaucoup de points ou la rémanence.")
        self.smooth_chk.toggled.connect(lambda *_: o.set_smooth(self.smooth_chk.isChecked()))
        f.addRow(self.smooth_chk)
        self.coord_chk = QtWidgets.QCheckBox("Outils de coordination (avancé) : vérifier le plan, coordonner, intermod, profils")
        self.coord_chk.setChecked(bool(getattr(o, "coord_on", False)))
        self.coord_chk.setToolTip("Cachés par défaut : RF Technical Monitor surveille, il ne remplace pas un logiciel de\n"
                                  "coordination. La fréquence de secours reste toujours disponible.")
        self.coord_chk.toggled.connect(lambda *_: o.set_coord(self.coord_chk.isChecked()))
        f.addRow(self.coord_chk)
        tabs.addTab(g, "Général")
        self.keys.append("general")
        # --- Son
        sw = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(sw)
        c = o.sound.cfg
        self.alert_chk = QtWidgets.QCheckBox("Alarmes sonores")
        self.alert_chk.setChecked(o.alert_chk.isChecked())
        self.alert_chk.setToolTip("Son quand une alarme arrive (les critiques sont rejouées selon le réglage ci-dessous).")
        self.alert_chk.toggled.connect(lambda *_: o.alert_chk.setChecked(self.alert_chk.isChecked()))
        self.style_combo = QtWidgets.QComboBox()
        for k, t in SOUND_STYLES:
            self.style_combo.addItem(t, k)
        self.style_combo.setCurrentIndex(max(0, self.style_combo.findData(c["style"])))
        self.style_combo.setToolTip("Sons de l'appli : 3 notes = critique, 2 = normale, 1 = info, sur la sortie choisie.\n"
                                    "Bip de Windows : le son système, toujours sur la sortie par défaut.")
        self.dev_combo = QtWidgets.QComboBox()
        self.dev_combo.addItem("Sortie par défaut de Windows", "")
        for k, t in SoundOut.devices():
            self.dev_combo.addItem(t, k)
        i = self.dev_combo.findData(c["device"])
        self.dev_combo.setCurrentIndex(i if i >= 0 else 0)
        self.dev_combo.setToolTip("Carte son, casque, enceinte HDMI, interface audio… : où sortent les alarmes\n"
                                  "et le bip de la chasse au brouilleur.")
        self.vol = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(c["volume"])
        self.vol.setToolTip("Volume des sons de l'appli (0 = muet).")
        t_crit = QtWidgets.QPushButton("▶ Alarme critique")
        t_crit.setToolTip("Écouter le son d'une alarme critique.")
        t_crit.clicked.connect(lambda *_: (self._apply_sound(), o.sound.alarm(2)))
        t_norm = QtWidgets.QPushButton("▶ Alarme normale")
        t_norm.setToolTip("Écouter le son d'une alarme normale.")
        t_norm.clicked.connect(lambda *_: (self._apply_sound(), o.sound.alarm(1)))
        for w_ in (self.style_combo, self.dev_combo):
            w_.currentIndexChanged.connect(lambda *_: self._apply_sound())
        self.dev_combo.currentIndexChanged.connect(          # 8.1 : l'écoute SDR « même sortie » suit
            lambda *_: QtCore.QTimer.singleShot(0, lambda: o.set_sdr_audio(o.sdr_cfg.get("audio_dev", ""))))
        self.vol.valueChanged.connect(lambda *_: self._apply_sound())
        self.rep_combo = QtWidgets.QComboBox()
        for v_, t_ in ALARM_REPEATS:
            self.rep_combo.addItem(t_, v_)
        self.rep_combo.setCurrentIndex(max(0, self.rep_combo.findData(c["repeat"])))
        self.rep_combo.setToolTip("Tant qu'une alarme critique n'est pas acquittée, son son est rejoué à ce rythme.")
        self.conf_spin = QtWidgets.QSpinBox()
        self.conf_spin.setRange(0, 60)
        self.conf_spin.setSuffix(" s")
        self.conf_spin.setValue(c["confirm"])
        self.conf_spin.setToolTip("Un signal sur une fréquence « doit rester libre » doit durer au moins ce temps avant\n"
                                  "l'alarme CONFLIT : un pic d'une fraction de seconde ne sonne plus. 0 = tout de suite.")
        self.occ_chk = QtWidgets.QCheckBox("Petit bip quand une fréquence sans alarme devient occupée")
        self.occ_chk.setChecked(c["occ_beep"])
        self.occ_chk.setToolTip("Décoché (conseillé) : seules les alarmes (CONFLIT, ABSENT, TROP FORT) font du bruit.")
        self.rep_combo.currentIndexChanged.connect(lambda *_: self._apply_sound())
        self.conf_spin.valueChanged.connect(lambda *_: self._apply_sound())
        self.occ_chk.toggled.connect(lambda *_: self._apply_sound())
        self.snd_msg = QtWidgets.QLabel("" if SoundOut.devices() else
                                        "Aucune sortie audio trouvée : le bip de Windows sera utilisé.")
        self.snd_msg.setWordWrap(True)
        f.addRow(self.alert_chk)
        f.addRow("Sons :", self.style_combo)
        f.addRow("Sortie audio :", self.dev_combo)
        self.sdr_out = QtWidgets.QComboBox()                  # 8.1 : sortie de l'écoute SDR (casque, enceinte…)
        self.sdr_out.addItem("Même sortie que les sons de l'appli", "")
        self.sdr_out.addItem("Sortie par défaut de Windows", "__win__")
        for k, t in SoundOut.devices():
            self.sdr_out.addItem(t, k)
        i_ = self.sdr_out.findData(str(o.sdr_cfg.get("audio_dev") or ""))
        self.sdr_out.setCurrentIndex(i_ if i_ >= 0 else 0)
        self.sdr_out.setToolTip("Où sort le son des micros écoutés avec le SDR (poste SDR, 🎧 Écouter, moniteur, temps\n"
                                "réel). Par ex. l'écoute dans un casque, les alarmes sur les enceintes.")
        self.sdr_out.currentIndexChanged.connect(lambda *_: o.set_sdr_audio(self.sdr_out.currentData()))
        f.addRow("Sortie de l'écoute SDR :", self.sdr_out)
        sc_btn = QtWidgets.QPushButton("📏 Échelles et niveaux (dBFS, dBu, dBV…)")
        sc_btn.setToolTip("Unité des vu-mètres, alignement numérique / analogique (EBU, SMPTE), niveau visé, et la\n"
                          "fiche qui explique toutes les échelles (RF et audio).")
        sc_btn.clicked.connect(lambda *_: o.open_scales())
        f.addRow(sc_btn)
        f.addRow("Volume :", self.vol)
        f.addRow(owner._row(t_crit, t_norm, None))
        f.addRow("Rejouer les critiques :", self.rep_combo)
        f.addRow("CONFLIT après :", self.conf_spin)
        f.addRow(self.occ_chk)
        f.addRow(self.snd_msg)
        tabs.addTab(sw, "Son")
        self.keys.append("sound")
        # --- Fichiers
        fw = QtWidgets.QWidget()
        f = QtWidgets.QFormLayout(fw)
        self.log_lbl = QtWidgets.QLabel(str(o.log_dir))
        self.log_lbl.setWordWrap(True)
        b_log = QtWidgets.QPushButton("📁 Changer…")
        b_log.setToolTip("Dossier du journal automatique, des rapports, des diagnostics.")
        b_log.clicked.connect(lambda *_: (o.pick_log_dir(), self.log_lbl.setText(str(o.log_dir))))
        b_open = QtWidgets.QPushButton("📂 Ouvrir")
        b_open.setToolTip("Ouvrir ce dossier dans l'explorateur.")
        b_open.clicked.connect(lambda *_: o.open_log_dir())
        self.sess_lbl = QtWidgets.QLabel(o.session_cfg.get("dir") or str(o.log_dir / "enregistrements"))
        self.sess_lbl.setWordWrap(True)
        b_sess = QtWidgets.QPushButton("📁 Changer…")
        b_sess.setToolTip("Où ranger les sessions enregistrées (proposé aussi à chaque ▶ Démarrer).")
        b_sess.clicked.connect(lambda *_: self._pick_sess())
        self.ask_chk = QtWidgets.QCheckBox("Demander à chaque démarrage s'il faut enregistrer la session")
        self.ask_chk.setChecked(o.sess_ask_chk.isChecked())
        self.ask_chk.setToolTip("Sinon, l'appli suit ton dernier choix sans poser la question.")
        self.ask_chk.toggled.connect(lambda *_: o.sess_ask_chk.setChecked(self.ask_chk.isChecked()))
        f.addRow("Journaux et rapports :", self.log_lbl)
        f.addRow(owner._row(b_log, b_open, None))
        f.addRow("Sessions enregistrées :", self.sess_lbl)
        f.addRow(owner._row(b_sess, None))
        f.addRow(self.ask_chk)
        f.addRow("Shows :", QtWidgets.QLabel(str(SHOW_DIR)))
        tabs.addTab(fw, "Fichiers")
        self.keys.append("files")
        # --- Connexions et nuit
        cw = QtWidgets.QWidget()
        f = QtWidgets.QVBoxLayout(cw)
        for txt, tip, fn in (
                ("📣 Alertes téléphone et page web…", "ntfy / Telegram, page web pour l'équipe, vue Régie.", o.open_alerts),
                ("🌙 Mode festival (nuit complète, bilan chaque jour)…", "Reprise auto, pas de veille, bilan du jour.",
                 o.open_festival),
                ("🌐 tinySA en réseau : adresses enregistrées…", "Le Raspberry Pi change d'adresse selon le Wi-Fi : une "
                 "adresse par réseau, à tester et choisir en un clic.", o.open_net_profiles),
                ("📡 Relais réseau : partager le tinySA de CE PC…", "Pour brancher un 2ᵉ tinySA par le réseau.",
                 o.open_relay),
                ("🩺 Diagnostic tinySA (fichier pour le support)…", "Le fichier à m'envoyer en cas de souci.",
                 o.open_diag)):
            b_ = QtWidgets.QPushButton(txt)
            b_.setToolTip(tip)
            b_.clicked.connect(lambda *_, fn=fn: fn())
            f.addWidget(b_)
        f.addStretch(1)
        tabs.addTab(cw, "Connexions")
        self.keys.append("links")
        for i in range(tabs.count()):
            self.nav.addItem(tabs.tabText(i))
        self.nav.currentRowChanged.connect(lambda r: tabs.setCurrentIndex(r) if r >= 0 else None)
        tabs.currentChanged.connect(lambda i: self.nav.setCurrentRow(i) if self.nav.currentRow() != i else None)
        self.nav.setCurrentRow(0)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def __init__(self, owner, *a, **k):
        self._init_base(owner, *a, **k)
        try:                                           # rubrique « Son » : un choix par son d'alarme
            page = self.tabs.widget(self.keys.index("sound"))
            f = page.layout()
            f.addRow(QtWidgets.QLabel(TR("<b>Sons des alarmes</b> (générateur, sons, ton WAV…)")))
            self.alarm_snd_btns = {}
            for key, name in APP_SOUNDS:
                cur = (getattr(owner.sound, "custom", None) or {}).get(key)
                b = QtWidgets.QPushButton()
                b.setToolTip(TR("Le son joué pour : {}. Clic = choisir (générateur, bruit, autre son, ton WAV…).").format(TR(name)))

                def upd(b=b, key=key):
                    sp = (getattr(owner.sound, "custom", None) or {}).get(key)
                    b.setText(TR("🎵 {}").format(audio_text(sp, TR)) if sp else TR("🎵 Son d'origine"))

                def pick(*_, key=key, upd=upd, name=name):
                    d = AudioPickDialog(owner, (getattr(owner.sound, "custom", None) or {}).get(key) or dict(src="app", app=key),
                                        title=TR("🎵 Son : {}").format(TR(name)))
                    if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                        owner.set_alarm_sound(key, d.spec())
                        upd()
                b.clicked.connect(pick)
                t_ = QtWidgets.QToolButton()
                t_.setText("▶")
                t_.setToolTip(TR("Écouter ce son."))
                t_.clicked.connect(lambda *_, key=key: (self._apply_sound(), owner.test_alarm_sound(key)))
                r_ = QtWidgets.QToolButton()
                r_.setText("↺")
                r_.setToolTip(TR("Revenir au son d'origine."))
                r_.clicked.connect(lambda *_, key=key, upd=upd: (owner.set_alarm_sound(key, None), upd()))
                upd()
                self.alarm_snd_btns[key] = b
                f.addRow(TR(name) + " :", owner._row(b, t_, r_))
        except Exception as ex:  # noqa: BLE001 — la fenêtre des réglages s'ouvre quoi qu'il arrive
            log_crash("Réglages (sons des alarmes)", repr(ex))

    def show_page(self, key):
        """Ouvre la rubrique key (detect, bands, measure, dev2, country, general, sound, files, links) ou un n°."""
        i = self.keys.index(key) if key in self.keys else key if isinstance(key, int) else 0
        self.tabs.setCurrentIndex(max(0, min(self.tabs.count() - 1, i)))

    def _give_back(self):
        park = getattr(self.owner, "set_park", None)
        for page in self._borrowed:
            if park is not None:
                park.layout().addWidget(page)
        self._borrowed = []

    def _apply_sound(self):
        self.owner.sound.cfg = sound_cfg_norm(dict(device=self.dev_combo.currentData() or "",
                                                   volume=self.vol.value(), style=self.style_combo.currentData(),
                                                   repeat=self.rep_combo.currentData(), confirm=self.conf_spin.value(),
                                                   occ_beep=self.occ_chk.isChecked()))
        self.owner.alarms.repeat_s = float(self.owner.sound.cfg["repeat"])
        self.dev_combo.setEnabled(self.style_combo.currentData() == "tones")

    def _pick_sess(self):
        o = self.owner
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier des sessions enregistrées",
                                                       o.session_cfg.get("dir") or str(o.log_dir))
        if d:
            o.session_cfg["dir"] = d
            self.sess_lbl.setText(d)
