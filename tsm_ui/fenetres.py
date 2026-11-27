# Coordination, remplacement, saisie express, ajout depuis le scan, mur, profils, shows.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


def spectrum_qimage(F, L, w=1600, h=560, thr=None, marks=(), tv=()):
    """Image du spectre pour le dossier de préparation (QPainter seul, sans pyqtgraph). 7.67.1 (PDF de Clément :
    spectre minuscule, 48 traits par-dessus, grand vide 700-820 MHz) : axe COUPÉ (axis_panels : une case par groupe de
    bandes, coupure grise entre deux), fréquences du plan = petits repères en haut, canaux TV grisés et numérotés.
    marks = [(MHz, nom)] ; tv = [(début, fin, canal)]."""
    img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor("#ffffff"))
    F = np.asarray(F, dtype=float)
    L = np.asarray(L, dtype=float)
    ok = np.isfinite(F) & np.isfinite(L)
    if ok.sum() < 2:
        return img
    F, L = F[ok], L[ok]
    o = np.argsort(F)
    F, L = F[o], L[o]
    panels = axis_panels(scan_segments(F))
    y0 = math.floor((min(float(np.percentile(L, 1)), thr if thr is not None else 0) - 5) / 10.0) * 10
    y1 = math.ceil((float(L.max()) + 5) / 10.0) * 10
    ml, mr, mt, mb, brk = 62, 14, 34, 40, 18
    pw, ph = w - ml - mr - brk * (len(panels) - 1), h - mt - mb
    spans = [max(1e-6, b_ - a_) for a_, b_ in panels]
    ws_ = [max(0.12 * pw, pw * s_ / sum(spans)) for s_ in spans]
    ws_ = [x * pw / sum(ws_) for x in ws_]
    xs, x = [], float(ml)
    for wd in ws_:
        xs.append((x, wd))
        x += wd + brk
    Y = lambda v: mt + (y1 - v) / max(1e-9, y1 - y0) * ph          # noqa: E731

    def X(k, f):
        a_, b_ = panels[k]
        return xs[k][0] + (f - a_) / max(1e-9, b_ - a_) * xs[k][1]
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    fnt = p.font()
    fnt.setPixelSize(17)
    p.setFont(fnt)
    grid, mut = QtGui.QColor("#dde2ea"), QtGui.QColor("#6e6e73")
    for v in range(int(y0), int(y1) + 1, 10):
        p.setPen(mut)
        p.drawText(QtCore.QRectF(0, Y(v) - 10, ml - 8, 20), Qt.AlignmentFlag.AlignRight, f"{v}")
    for k, (a_, b_) in enumerate(panels):
        x0_, wd = xs[k]
        for c0, c1, ch in tv:                         # canaux TV : bandeau gris + numéro
            lo_, hi_ = max(a_, c0), min(b_, c1)
            if hi_ > lo_:
                p.fillRect(QtCore.QRectF(X(k, lo_), mt, X(k, hi_) - X(k, lo_), ph), QtGui.QColor(120, 120, 130, 38))
                p.setPen(mut)
                p.drawText(QtCore.QRectF(X(k, lo_), mt + ph - 22, X(k, hi_) - X(k, lo_), 20),
                           Qt.AlignmentFlag.AlignHCenter, f"{ch}")
        p.setPen(QtGui.QPen(grid, 1))
        for v in range(int(y0), int(y1) + 1, 10):
            p.drawLine(QtCore.QPointF(x0_, Y(v)), QtCore.QPointF(x0_ + wd, Y(v)))
        span = b_ - a_
        nt = max(2, int(wd / 120))
        stepx = next((s_ for s_ in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500) if span / s_ <= nt), 1000)
        f_ = math.ceil(a_ / stepx) * stepx
        while f_ <= b_ + 1e-9:
            p.setPen(QtGui.QPen(grid, 1))
            p.drawLine(QtCore.QPointF(X(k, f_), mt), QtCore.QPointF(X(k, f_), mt + ph))
            p.setPen(mut)
            p.drawText(QtCore.QRectF(X(k, f_) - 40, mt + ph + 6, 80, 20), Qt.AlignmentFlag.AlignHCenter, f"{f_:g}")
            f_ += stepx
        p.setPen(QtGui.QPen(QtGui.QColor("#c7ccd6"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QtCore.QRectF(x0_, mt, wd, ph))
        if thr is not None:
            p.setPen(QtGui.QPen(QtGui.QColor("#ff9f0a"), 1.6, Qt.PenStyle.DashLine))
            p.drawLine(QtCore.QPointF(x0_, Y(thr)), QtCore.QPointF(x0_ + wd, Y(thr)))
        m = (F >= a_ - 1e-9) & (F <= b_ + 1e-9)
        Fk, Lk = F[m], L[m]
        path = QtGui.QPainterPath()
        gaps = set(int(i) for i in scan_gaps(Fk)) if len(Fk) > 2 else set()
        for i in range(len(Fk)):
            pt = QtCore.QPointF(X(k, Fk[i]), Y(min(y1, max(y0, Lk[i]))))
            if i == 0 or i in gaps:                  # trou entre deux bandes : pas de trait par-dessus
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        p.setPen(QtGui.QPen(QtGui.QColor("#0a5bd3"), 1.4))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor("#e8590c"))
        for f, _n in marks:                          # fréquences du plan : petit triangle au-dessus du cadre
            if a_ <= f <= b_:
                xx = X(k, f)
                p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(xx - 5, mt - 14), QtCore.QPointF(xx + 5, mt - 14),
                                               QtCore.QPointF(xx, mt - 3)]))
        if k:                                        # coupure de l'axe
            bx = x0_ - brk
            p.setPen(QtGui.QPen(QtGui.QColor("#9aa0aa"), 1.4))
            for dx in (4, brk - 4):
                p.drawLine(QtCore.QPointF(bx + dx - 4, mt + ph + 6), QtCore.QPointF(bx + dx + 4, mt + ph - 6))
    p.setPen(mut)
    p.drawText(QtCore.QRectF(ml, h - 18, pw + brk * (len(panels) - 1), 18), Qt.AlignmentFlag.AlignRight, "MHz · dBm")
    p.drawText(QtCore.QRectF(ml, 0, pw, 18), Qt.AlignmentFlag.AlignLeft,
               TR("▼ fréquences du plan · gris = canaux TV · tirets = seuil « occupé »"))
    p.end()
    return img


class CoordScanDialog(QtWidgets.QDialog):
    """📏 7.67 (Clément : « qu'il faut un RBW fin ») : scan pour la coordination fait tout seul. RBW fine + points
    calés sur la RBW, pics remis à zéro, balayage N minutes, puis scan gardé dans Scans par lieu (avec sa RBW) et
    réglages de surveillance remis comme avant."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Scan pour la coordination")
        self.setModal(False)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Le tinySA balaye tes bandes avec une RBW fine et des points calés sur cette RBW (aucun "
                                "signal ne passe entre deux points), en gardant les pics, pendant le temps choisi. À la "
                                "fin, le scan est gardé dans Scans par lieu avec sa RBW, et tes réglages de surveillance "
                                "reviennent comme avant.")
        info.setWordWrap(True)
        lay.addWidget(info)
        f = QtWidgets.QFormLayout()
        self.rbw = QtWidgets.QComboBox()
        for v, lab in ((10, "10 kHz (très fin, très lent)"), (30, "30 kHz (conseillé)"), (100, "100 kHz (rapide, moins précis)")):
            self.rbw.addItem(lab, v)
        self.rbw.setCurrentIndex(1)
        self.rbw.setToolTip(COORD_RBW_TIP)
        self.minutes = QtWidgets.QSpinBox()
        self.minutes.setRange(1, 120)
        self.minutes.setValue(5)
        self.minutes.setSuffix(" min")
        self.minutes.setToolTip("Plus long = plus de chances d'attraper ce qui émet par moments (talkies, liaisons).")
        self.scene = QtWidgets.QComboBox()
        self.scene.setEditable(True)
        for sc in o.scenes:
            self.scene.addItem(sc["name"])
        one = {k[0] for k in o.scope or [] if k}
        self.scene.setEditText(next(iter(one)) if len(one) == 1 else (o.scenes[0]["name"] if o.scenes else "Site"))
        self.scene.setToolTip("Lieu (scène) où le scan sera rangé dans Scans par lieu.")
        self.label = QtWidgets.QLineEdit("")
        self.label.setPlaceholderText("ex. jardin, régie… (sinon l'heure)")
        self.label.setToolTip("Étiquette du scan (facultatif).")
        f.addRow("Finesse (RBW) :", self.rbw)
        f.addRow("Durée :", self.minutes)
        f.addRow("Lieu :", self.scene)
        f.addRow("Étiquette :", self.label)
        lay.addLayout(f)
        self.est = QtWidgets.QLabel("")
        self.est.setWordWrap(True)
        lay.addWidget(self.est)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        row = QtWidgets.QHBoxLayout()
        self.go = QtWidgets.QPushButton("▶ Lancer le scan")
        self.go.setToolTip("Règle la RBW et les points, efface les pics gardés et balaye le temps choisi.")
        self.go.clicked.connect(lambda *_: self.start() if self._state is None else self.stop(cancel=True))
        self.sites_btn = QtWidgets.QPushButton("📍 Scans par lieu…")
        self.sites_btn.setToolTip("Voir les scans gardés (comparer, exporter avec la RBW dans le nom).")
        self.sites_btn.clicked.connect(lambda *_: o.open_sites())
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        row.addWidget(self.go)
        row.addWidget(self.sites_btn)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self._state = None
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.rbw.currentIndexChanged.connect(lambda *_: self._estimate())
        self._estimate()
        fit_dialog(self, 560, 420)

    def _estimate(self):
        o = self.owner
        act = [b for b in o.bands if b["enabled"]] or o.bands
        total = sum(max(0.0, b["stop"] - b["start"]) for b in act)
        rbw = float(self.rbw.currentData())
        step = auto_scan_step(total, rbw, AUTO_BUDGET.get(0, 4500))
        n = int(total * 1000.0 / max(step, 0.001))
        self.est.setText(TR("Bandes balayées : {} MHz au total · pas de {} kHz ≈ {} points par tour (plus lent qu'en "
                            "surveillance : c'est normal).").format(f"{total:g}", f"{step:g}", n))

    def start(self):
        o = self.owner
        st = dict(rbw=o.rbw_combo.currentIndex(), pts=o.points_combo.currentIndex(), hold=o.hold_chk.isChecked(),
                  running=o.is_running(), t0=time.time(), dur=self.minutes.value() * 60.0, extra=0.0,
                  scene=self.scene.currentText().strip() or "Site", label=self.label.text().strip(),
                  rbw_v=float(self.rbw.currentData()))
        for i in range(o.rbw_combo.count()):
            v = o.rbw_combo.itemData(i)
            if v is not None and abs(float(v) - st["rbw_v"]) < 1e-6:
                o.rbw_combo.setCurrentIndex(i)
                break
        i_auto = o.points_combo.findData(0)
        if i_auto >= 0:
            o.set_points_choice(i_auto)
        o.hold_chk.setChecked(True)
        o.reset_max()
        self._state = st
        if not st["running"]:
            o.toggle_run(auto=True)
        self.go.setText(TR("■ Arrêter (sans garder)"))
        for w_ in (self.rbw, self.minutes, self.scene, self.label):
            w_.setEnabled(False)
        self.bar.setValue(0)
        self.bar.show()
        self.msg.setText(TR("Scan en cours… laisse le tinySA balayer."))
        self.timer.start(1000)

    def _tick(self):
        st, o = self._state, self.owner
        if st is None:
            return
        el = time.time() - st["t0"]
        tot = st["dur"] + st["extra"]
        self.bar.setValue(int(1000 * min(1.0, el / max(1.0, tot))))
        left = max(0, int(tot - el))
        self.msg.setText(TR("Scan en cours… encore {} min {} s.").format(left // 60, f"{left % 60:02d}"))
        if el > 8 and not o.is_running():
            self.stop(cancel=True, why=TR("La surveillance s'est arrêtée : scan abandonné."))
            return
        if el >= tot:
            F, L = o.fresh_FL(use_max=True, any_age=True)
            if F is None and st["extra"] < 180:
                st["extra"] += 30                 # pas encore un tour complet : on attend un peu
                return
            self.stop(cancel=F is None, F=F, L=L,
                      why=None if F is not None else TR("Aucun tour complet mesuré : scan abandonné."))

    def stop(self, cancel=False, F=None, L=None, why=None):
        st, o = self._state, self.owner
        if st is None:
            return
        self.timer.stop()
        self._state = None
        saved = None
        if not cancel and F is not None:
            names = {d["name"] for d in o.site_scans}
            name = snapshot_name(st["scene"], st["label"], names, time.strftime("%H:%M"))
            o.site_scans.append(site_scan_doc(name, F, L, time.time(), scene=st["scene"],
                                              dur=time.time() - st["t0"], rbw=st["rbw_v"]))
            saved = name
            o.undo_track()
            o.update_site_curve()
            o._bump()
        o.rbw_combo.setCurrentIndex(st["rbw"])        # réglages de surveillance comme avant
        o.set_points_choice(st["pts"])
        o.hold_chk.setChecked(st["hold"])
        if not st["running"] and o.is_running():
            o.toggle_run()
        for w_ in (self.rbw, self.minutes, self.scene, self.label):
            w_.setEnabled(True)
        self.go.setText(TR("▶ Lancer le scan"))
        self.bar.hide()
        if saved:
            line, _ok = rbw_coord_line(st["rbw_v"], False, TR, step=scan_step_khz(F))
            self.msg.setText(TR("✔ Scan gardé : « {} » ({}). Il est dans Scans par lieu, prêt pour la coordination "
                                "et l'export. Réglages de surveillance remis comme avant.").format(
                                    saved, fmt_duration(time.time() - st["t0"])) + "\n" + line)
            o.set_status(TR("📏 Scan pour la coordination gardé : {}").format(saved))
        else:
            self.msg.setText(why or TR("Scan arrêté sans rien garder. Réglages de surveillance remis comme avant."))

    def closeEvent(self, e):
        if self._state is not None:
            self.stop(cancel=True)
        super().closeEvent(e)


class RecurringDialog(QtWidgets.QDialog):
    """🔁 7.67 : perturbations qui reviennent à la même heure sur plusieurs jours, d'après les journaux automatiques."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Perturbations qui reviennent")
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("D'après les journaux automatiques (un fichier par jour) : ce qui se répète à la même "
                                "heure sur plusieurs jours. Ex. un talkie qui s'allume tous les soirs vers 19 h, un "
                                "micro qui décroche toujours au même moment.")
        info.setWordWrap(True)
        lay.addWidget(info)
        row = QtWidgets.QHBoxLayout()
        self.days = QtWidgets.QComboBox()
        for n in (3, 7, 14, 30, 90):
            self.days.addItem(TR("{} derniers jours").format(n), n)
        self.days.setCurrentIndex(1)
        self.days.setToolTip("Combien de journaux (jours) lire.")
        self.tol = QtWidgets.QSpinBox()
        self.tol.setRange(5, 120)
        self.tol.setValue(20)
        self.tol.setPrefix("± ")
        self.tol.setSuffix(" min")
        self.tol.setToolTip("« Même heure » à plus ou moins tant de minutes.")
        self.mind = QtWidgets.QSpinBox()
        self.mind.setRange(2, 30)
        self.mind.setValue(2)
        self.mind.setSuffix(TR(" jours mini"))
        self.mind.setToolTip("Nombre de jours différents où ça doit revenir.")
        self.occ = QtWidgets.QCheckBox("Inclure les signaux présents (OCCUPÉ)")
        self.occ.setChecked(True)
        self.occ.setToolTip("Un signal qui s'allume sur une fréquence sans statut (pas tes micros « doit émettre »).")
        for w_ in (self.days, self.tol, self.mind, self.occ):
            row.addWidget(w_)
        row.addStretch(1)
        lay.addLayout(row)
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Quoi", "Où", "MHz", "Vers", "Jours", "Fois"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setToolTip("Double-clic : chasser ce signal (zoom sur sa fréquence).")
        self.table.cellDoubleClicked.connect(self._hunt)
        lay.addWidget(self.table, 1)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        b = QtWidgets.QHBoxLayout()
        cp = QtWidgets.QPushButton("Copier")
        cp.setToolTip("Copie la liste en texte (message, rapport).")
        cp.clicked.connect(lambda *_: QtWidgets.QApplication.clipboard().setText("\n".join(self.lines)))
        cl = QtWidgets.QPushButton("Fermer")
        cl.clicked.connect(self.close)
        b.addWidget(cp)
        b.addStretch(1)
        b.addWidget(cl)
        lay.addLayout(b)
        self.pats, self.lines = [], []
        for w_ in (self.days, self.tol, self.mind):
            (w_.currentIndexChanged if isinstance(w_, QtWidgets.QComboBox) else w_.valueChanged).connect(
                lambda *_: self.refresh())
        self.occ.toggled.connect(lambda *_: self.refresh())
        fit_dialog(self, 820, 520)
        self.refresh()

    def refresh(self):
        o = self.owner
        rows, nfiles = o.journal_rows(self.days.currentData())
        kinds = [k for k in RECUR_KINDS if self.occ.isChecked() or k != "OCCUPÉ"]
        on = [s["name"] for s in o.statuses if s.get("on")]
        self.pats = recurring_events(rows, kinds, self.tol.value(), self.mind.value(), on)
        self.lines = [recurring_text(p_, TR) for p_ in self.pats]
        t = self.table
        t.setRowCount(len(self.pats))
        for r, p_ in enumerate(self.pats):
            vals = [TR(p_["kind"]) + " — " + TR(RECUR_LABELS.get(p_["kind"], "")), p_["name"],
                    f"{p_['mhz']:.3f}" if p_["mhz"] is not None else "—",
                    f"{p_['center'] // 60:02d}:{p_['center'] % 60:02d} ± {p_['spread']}'",
                    f"{p_['days']} / {p_['total_days']}", str(p_["count"])]
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                it.setToolTip(TR("Jours : {}").format(", ".join(p_["dates"])))
                t.setItem(r, c, it)
        t.resizeColumnsToContents()
        if not nfiles:
            self.msg.setText(TR("Aucun journal automatique trouvé dans {} : coche « Journal auto (CSV / jour) » (onglet "
                                "Journal) pour que l'appli note chaque jour dans un fichier.").format(o.log_dir))
        elif not self.pats:
            self.msg.setText(TR("{} journal(aux) lu(s) : rien ne revient à la même heure sur plusieurs jours.").format(nfiles))
        else:
            self.msg.setText(TR("{} journal(aux) lu(s) · {} perturbation(s) qui reviennent.").format(nfiles, len(self.pats)))

    def _hunt(self, r, _c):
        if 0 <= r < len(self.pats) and self.pats[r]["mhz"] is not None:
            self.owner.open_hunt(self.pats[r]["mhz"])


class RfDiagDialog(QtWidgets.QDialog):
    """🩺 7.68 : diagnostic RF automatique. Lit le spectre en direct et la liste, dit en clair ce qui cloche dans la
    MESURE (saturation, bruit de fond, zones bruyantes, seuil, micros pile au seuil, micros dans un canal TV, signaux
    hors liste) et propose « Régler »."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Diagnostic RF")
        self.setModal(False)
        self.resize(760, 560)
        lay = QtWidgets.QVBoxLayout(self)
        self.head = QtWidgets.QLabel("")
        self.head.setStyleSheet("font-size:18px; font-weight:bold; padding:6px")
        lay.addWidget(self.head)
        intro = QtWidgets.QLabel("Ce que le tinySA voit en ce moment, relu pour toi : ce qui fausse la mesure et quoi "
                                 "faire. Les seuils de ce diagnostic sont des valeurs de départ : fie-toi aussi à ton "
                                 "oreille et au spectre.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "Point", "Ce qui se passe · quoi faire"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 200)
        self.table.setToolTip("Chaque ligne = un point relevé dans la mesure. « Régler » applique ou ouvre la correction.")
        lay.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        self.again_btn = QtWidgets.QPushButton("↻ Relancer le diagnostic")
        self.again_btn.setToolTip("Relit le spectre et la liste maintenant (c'est aussi refait toutes les 5 s).")
        self.again_btn.clicked.connect(lambda *_: self.refresh())
        man = QtWidgets.QPushButton("❓ Manuel")
        man.setToolTip("Le chapitre du manuel sur les seuils et la lecture du spectre.")
        man.clicked.connect(lambda *_: owner.open_manual("seuils"))
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme cette fenêtre.")
        close.clicked.connect(self.close)
        row.addWidget(self.again_btn)
        row.addWidget(man)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.items = []
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()
        fit_dialog(self, 760, 560)

    def refresh(self):
        o = self.owner
        try:
            self.items = rf_diagnose(o.rf_diag_info())
        except Exception as e:  # noqa: BLE001
            self.msg.setText(TR("Diagnostic impossible : {}").format(e))
            return
        lvl, txt = rf_diag_summary(self.items)
        col = {"ok": o.theme.get("st_free", "#3fb950"), "warn": o.theme.get("st_weak", "#d29922"),
               "bad": o.theme.get("st_occ", "#f85149")}
        self.head.setText(TR(txt))
        self.head.setStyleSheet(f"font-size:18px; font-weight:bold; padding:6px; color:{col.get(lvl, '')}")
        t = self.table
        t.setRowCount(len(self.items))
        for r, c in enumerate(self.items):
            t.setItem(r, 0, QtWidgets.QTableWidgetItem(DIAG_ICONS.get(c["level"], "")))
            it = QtWidgets.QTableWidgetItem(TR(c["title"]))
            it.setToolTip(TR(c["title"]))
            t.setItem(r, 1, it)
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w)
            hl.setContentsMargins(4, 2, 4, 2)
            tx = TR(c["text"]).replace("\n", " ")
            ad = TR(c["advice"]).replace("\n", " ") if c["advice"] else ""
            lb = QtWidgets.QLabel(html_esc(tx) + (f"<br><b>→</b> {html_esc(ad)}" if ad else ""))
            lb.setWordWrap(True)
            lb.setTextFormat(Qt.TextFormat.RichText)
            hl.addWidget(lb, 1)
            if c["fix"] and c["level"] != "ok" and hasattr(o, c["fix"]):
                b = QtWidgets.QPushButton("Régler")
                b.setToolTip("Applique la correction proposée ou ouvre le bon réglage.")
                b.clicked.connect(lambda *_, c=c: self.fix(c))
                hl.addWidget(b)
            t.setItem(r, 2, QtWidgets.QTableWidgetItem(""))
            t.setCellWidget(r, 2, w)
        t.resizeRowsToContents()

    def fix(self, c):
        o = self.owner
        try:
            fn = getattr(o, c["fix"])
            a = c.get("arg")
            if a is None:
                fn()
            elif isinstance(a, tuple):
                fn(*a)
            else:
                fn(a)
        except Exception as e:  # noqa: BLE001
            self.msg.setText(TR("Impossible : {}").format(e))
            return
        self.refresh()

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


class ReplaceDialog(QtWidgets.QDialog):
    """🆘 7.62 Remplacer un micro brouillé : 3 propositions (son appareil, sa bande, compatibles avec tout le plan,
    libres d'après la mesure), un clic = remplacé + journal. Le calcul tourne en arrière-plan."""

    def __init__(self, owner, w):
        super().__init__(owner)
        self.owner, self.w = owner, w
        o = owner
        self.setWindowTitle("Remplacer un micro")
        lay = QtWidgets.QVBoxLayout(self)
        rx = o.rx_of(w)
        self.head = QtWidgets.QLabel(f"<b style='font-size:16px'>🆘 {_hesc(w['name'])} · {w['freq']:.3f} MHz</b><br>"
                                     + _hesc(TR("Appareil : {}").format(rx_short(rx) if rx else TR("réglages par défaut"))))
        self.head.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.head)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.box = QtWidgets.QVBoxLayout()
        lay.addLayout(self.box)
        self.done_lbl = QtWidgets.QLabel("")
        self.done_lbl.setWordWrap(True)
        lay.addWidget(self.done_lbl)
        again = QtWidgets.QPushButton("↻ Recalculer")
        again.setToolTip("Refait les propositions avec la mesure actuelle.")
        again.clicked.connect(lambda *_: self.compute())
        more = QtWidgets.QPushButton("Plus d'options (fréquence de secours)…")
        more.setToolTip("Recherche détaillée : plage, écart, intermod, spectre d'une scène…")
        more.clicked.connect(lambda *_: o.open_rescue())
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.close)
        lay.addLayout(o._row(again, more, None, close))
        self.resize(520, 300)
        self.found, self._job = [], None
        self.compute()

    def compute(self):
        o = self.owner
        if not any(x is self.w for x in o.watch):
            self.msg.setText("Ce micro n'est plus dans la liste.")
            return
        while self.box.count():
            it = self.box.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        a = o.replace_args(self.w)
        self._args = a
        self._job = o.run_heavy(lambda: o.replace_compute(a, 3), self._computed, self.msg, "Recherche des remplaçantes")

    def _computed(self, sg, err):
        o = self.owner
        self._job = None
        if err is not None:
            self.msg.setText(f"Calcul impossible : {err}")
            return
        self.found = o.replace_decorate(self._args, sg, self.w)
        if not self.found:
            self.msg.setText("Aucune fréquence libre et compatible trouvée avec ces règles"
                             + (TR(" dans la bande de l'appareil ({}–{} MHz)").format(*self._args["band"])
                                if self._args["band"] else "") + ". Essaie « Plus d'options ».")
            return
        bd = self._args["band"]
        relaxed = any(x.get("relaxed") for x in self.found)
        head = (TR("⚠ Rien ne passe avec toutes tes règles : propositions vérifiées en 2A − B SEULEMENT (A + B − C et "
                   "5ᵉ ordre NON vérifiés). Libres d'après la mesure")
                if relaxed else TR("Libres d'après la mesure, compatibles avec tout ton plan"))
        self.msg.setText(head + (TR(", dans la bande de l'appareil ({}–{} MHz)").format(*bd) if bd else "")
                         + TR(". Un clic = remplacer :"))
        self.msg.setStyleSheet("color:#e0a040" if relaxed else "")
        for x in self.found:
            lv = f" · {o.lvl(x['level'], suffix=True)}" if x["level"] is not None else ""
            b = QtWidgets.QPushButton(f"{x['f']:.3f} MHz   ({x['d'] * 1000:+.0f} kHz{lv})"
                                      + (f"   ⚠ {TR(x['tag'])}" if x["tag"] else ""))
            b.setMinimumHeight(40)
            b.setToolTip("Remplace la fréquence dans la liste et le note au journal.\nPense à régler l'émetteur ET le "
                         "récepteur.")
            b.clicked.connect(lambda *_, f=x["f"]: self.pick(f))
            self.box.addWidget(b)

    def pick(self, f):
        if self.owner.replace_watch(self.w, f):
            self.done_lbl.setText(TR("✔ Remplacé : {} est maintenant sur {} MHz. Règle l'émetteur ET le récepteur."
                                     ).format(self.w["name"], f"{f:.3f}"))
            while self.box.count():
                it = self.box.takeAt(0)
                if it.widget() is not None:
                    it.widget().deleteLater()

    def closeEvent(self, e):
        if self._job is not None:
            self._job["cancel"] = True
            self._job = None
        super().closeEvent(e)


class QuickAddDialog(QtWidgets.QDialog):
    """⌨ 7.62 Saisie express : on tape ou on colle « HF1 558.2, HF2 574, IEM 606.5 PSM » (ou un message, un tableau),
    l'aperçu se met à jour, « Ajouter » crée les micros dans la scène / le groupe choisis. Non modale."""

    def __init__(self, owner, text="", preset=("", "")):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Ajouter des micros (saisie express)")
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Tape ou colle tes fréquences, n'importe comment : « HF1 558.2, HF2 574, IEM 606.5 », "
                                "une par ligne, ou un message reçu (mail, SMS). Les nombres qui ne sont pas des "
                                "fréquences sont ignorés.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.edit = QtWidgets.QPlainTextEdit()
        self.edit.setPlaceholderText("HF1 558.2, HF2 574\nIEM 606.5 PSM\nGuitare 470.125")
        self.edit.setToolTip("Fréquences en MHz (558.2 ou 558,2) ou en kHz (558200). Le texte avant chaque\n"
                             "fréquence devient son nom ; sans nom, l'appli numérote (HF 1, HF 2…).")
        self.edit.setPlainText(text or "")
        self.edit.textChanged.connect(lambda *_: self.refresh())
        lay.addWidget(self.edit, 1)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nom", "MHz", "Remarque"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("Ce qui va être ajouté.")
        lay.addWidget(self.table, 1)
        self.scene = QtWidgets.QComboBox()
        self.scene.setEditable(True)
        self.scene.addItems([""] + [sc["name"] for sc in o.scenes])
        self.scene.setEditText(preset[0] or "")
        self.scene.setToolTip("Scène (facultatif ; une nouvelle est créée si tu tapes un nom).")
        self.group = QtWidgets.QComboBox()
        self.group.setEditable(True)
        self.group.setToolTip("Groupe dans la scène (facultatif).")
        self.scene.currentTextChanged.connect(lambda *_: self._groups())
        self._groups()
        self.group.setEditText(preset[1] or "")
        self.scene.setMinimumWidth(160)
        self.group.setMinimumWidth(130)
        self.status = QtWidgets.QComboBox()
        self.status.addItem("(aucun statut)", "")
        for st in o.statuses:
            self.status.addItem(st["name"], st["name"])
        self.status.setToolTip("Statut des nouveaux micros (« doit émettre » : alarme s'ils disparaissent).")
        self.prefix = QtWidgets.QLineEdit("HF")
        self.prefix.setMaximumWidth(90)
        self.prefix.setToolTip("Nom donné aux fréquences sans nom : HF 1, HF 2…")
        self.prefix.textChanged.connect(lambda *_: self.refresh())
        lay.addLayout(o._row("Scène :", self.scene, "Groupe :", self.group, "Statut :", self.status,
                             "Sans nom :", self.prefix, None))
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        self.add_btn = QtWidgets.QPushButton("＋ Ajouter")
        self.add_btn.setToolTip("Ajoute ces micros à ta liste (Ctrl+Entrée).")
        self.add_btn.clicked.connect(lambda *_: self.add())
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self, activated=self.add)
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.close)
        lay.addLayout(o._row(self.msg, None, self.add_btn, close))
        self.resize(640, 520)
        self.items = []
        self.refresh()

    def _groups(self):
        sc = self.owner.scene_by_name(self.scene.currentText().strip())
        cur = self.group.currentText()
        self.group.blockSignals(True)
        self.group.clear()
        self.group.addItems([""] + ([g["name"] for g in sc["groups"]] if sc else []))
        self.group.setEditText(cur)
        self.group.blockSignals(False)

    def refresh(self):
        o = self.owner
        self.items, ign = parse_quick_entry(self.edit.toPlainText())
        names = quick_names(self.items, self.prefix.text().strip() or "HF", {w["name"] for w in o.watch})
        have = {int(round(w["freq"] * 1000)) for w in o.watch}
        self.table.setRowCount(len(self.items))
        for r, (it, nm) in enumerate(zip(self.items, names)):
            it["final"] = nm
            dup = int(round(it["freq"] * 1000)) in have
            it["dup"] = dup
            rem = "déjà dans la liste : ignorée" if dup else ("" if o.in_scanned_band(it["freq"]) else
                                                                   "hors des bandes balayées (proposées après l'ajout)")
            if it.get("khz") and not dup:
                rem = TR("⚠ nombre lu en kHz : vérifie que c'est bien une fréquence") + (f" · {TR(rem)}" if rem else "")
            for c, v in enumerate((nm, f"{it['freq']:.3f}", rem)):
                cell = QtWidgets.QTableWidgetItem(v)
                if dup:
                    cell.setForeground(QtGui.QColor("#8b95a5"))
                self.table.setItem(r, c, cell)
        n = sum(1 for it in self.items if not it["dup"])
        self.add_btn.setText(TR("＋ Ajouter {} micro(s)").format(n) if n else TR("＋ Ajouter"))
        self.add_btn.setEnabled(n > 0)
        self.msg.setText(TR("Ignoré (pas de fréquence) : {}").format(" · ".join(ign[:4]) + (" …" if len(ign) > 4 else ""))
                         if ign else "")

    def add(self):
        o = self.owner
        new = [it for it in self.items if not it.get("dup")]
        if not new:
            return 0
        sc, gr = self.scene.currentText().strip(), self.group.currentText().strip()
        if sc:
            o.ensure_group(sc, gr)
        st = self.status.currentData() or ""
        for it in new:
            o._append_watch(it["final"], it["freq"], st, None, sc, gr if sc else "")
        o.sort_watch()
        o.rebuild_tree()
        o.rebuild_watch_table()
        o._update_markers()
        o.undo_track()
        o.set_status(TR("⌨ {} micro(s) ajouté(s).").format(len(new)))
        self.edit.clear()
        self.msg.setText(TR("✔ {} micro(s) ajouté(s). Tu peux en taper d'autres.").format(len(new)))
        o.offer_missing_bands()
        return len(new)


class ScanAddDialog(QtWidgets.QDialog):
    """📡 Ajouter depuis le scan : les signaux vus au-dessus d'un seuil deviennent des fréquences de la liste
    (à renommer, ranger, supprimer ensuite comme les autres)."""
    COLS = ["", "MHz", "Niveau", "Largeur", "Où (plan du pays)"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.peaks = []
        self.setWindowTitle("Ajouter des fréquences depuis le scan")
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Les signaux que le tinySA voit au-dessus du seuil deviennent des fréquences de ta liste, sans les "
            "taper. Laisse tourner le balayage un moment avant : le <b>max hold</b> garde aussi les émetteurs "
            "intermittents. Ensuite, renomme-les, range-les ou supprime le bruit comme n'importe quelle fréquence.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 3)
        lay.addWidget(info)
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Max hold (tout ce qui est passé)", "max")
        self.src_combo.addItem("Balayage en direct", "live")
        self.src_combo.setToolTip("Max hold : garde les signaux brefs ou intermittents. Direct : seulement ce qui "
                                  "émet maintenant.")
        self.thr = LevelSpin()
        self.thr.setRange(-120.0, 0.0)
        self.thr.setValue(o.thr_spin.value())
        self.thr.setToolTip("Seuls les signaux au-dessus de ce niveau sont proposés (par défaut : ton seuil "
                            "« occupé »).")
        self.merge = QtWidgets.QSpinBox()
        self.merge.setRange(10, 2000)
        self.merge.setSingleStep(25)
        self.merge.setValue(150)
        self.merge.setSuffix(" kHz")
        self.merge.setToolTip("Deux morceaux de signal plus proches que ça = un seul signal.")
        self.excl_chk = QtWidgets.QCheckBox("Sans celles déjà dans ma liste")
        self.excl_chk.setChecked(True)
        self.excl_chk.setToolTip("N'affiche pas les signaux à moins de 100 kHz d'une fréquence déjà dans ta liste.")
        self.wide_chk = QtWidgets.QCheckBox("Sans les plateaux larges (TNT…)")
        self.wide_chk.setChecked(True)
        self.wide_chk.setToolTip("Écarte les signaux de plus de 1,5 MHz de large (TNT, Spectera, bloc numérique) :\n"
                                 "décoche pour les ajouter comme blocs larges.")
        go = QtWidgets.QPushButton("🔄 Chercher")
        go.setToolTip("Relance la recherche avec ces réglages.")
        go.clicked.connect(lambda *_: self.refresh())
        for w_ in (self.src_combo,):
            w_.currentIndexChanged.connect(lambda *_: self.refresh())
        for w_ in (self.excl_chk, self.wide_chk):
            w_.toggled.connect(lambda *_: self.refresh())
        lay.addLayout(o._row(self.src_combo, "Seuil :", self.thr, "Réunir à :", self.merge, None, go))
        lay.addLayout(o._row(self.excl_chk, self.wide_chk, None))
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("Coche les signaux à ajouter. Double-clic : voir ce signal sur le spectre (zoom).")
        self.table.cellDoubleClicked.connect(lambda r, c: self.zoom(r))
        lay.addWidget(self.table, 1)
        b_all = QtWidgets.QPushButton("Tout cocher")
        b_all.setToolTip("Coche toutes les lignes.")
        b_all.clicked.connect(lambda *_: self.check_all(True))
        b_none = QtWidgets.QPushButton("Tout décocher")
        b_none.setToolTip("Décoche toutes les lignes.")
        b_none.clicked.connect(lambda *_: self.check_all(False))
        self.count_lbl = QtWidgets.QLabel("")
        lay.addLayout(o._row(b_all, b_none, None, self.count_lbl))
        f = QtWidgets.QFormLayout()
        self.prefix = QtWidgets.QLineEdit("Scan")
        self.prefix.setToolTip("Nom donné aux nouvelles fréquences, numéroté : Scan 1, Scan 2… (à renommer ensuite).")
        self.scene = QtWidgets.QComboBox()
        self.scene.setEditable(True)
        self.scene.addItem("")
        for sc in o.scenes:
            self.scene.addItem(sc["name"])
        self.scene.setEditText("")
        self.scene.setToolTip("Scène où les ranger (facultatif ; on peut les ranger plus tard).")
        self.group = QtWidgets.QLineEdit("")
        self.group.setPlaceholderText(f"ex. Scan {datetime.now():%d/%m %H:%M}")
        self.group.setToolTip("Groupe où les ranger (facultatif).")
        self.status = QtWidgets.QComboBox()
        self.status.addItem("aucun statut (simple surveillance)", "")
        for st in o.statuses:
            self.status.addItem(st["name"], st["name"])
        self.status.setToolTip("Statut des nouvelles fréquences : « aucun » = on surveille sans alarme ; « En "
                               "service » = elles doivent émettre (alarme si elles se taisent).")
        f.addRow("Nom :", self.prefix)
        f.addRow("Scène :", self.scene)
        f.addRow("Groupe :", self.group)
        f.addRow("Statut :", self.status)
        lay.addLayout(f)
        add = QtWidgets.QPushButton("＋ Ajouter les cochées à ma liste")
        add.setToolTip("Ajoute les signaux cochés comme fréquences surveillées.")
        add.clicked.connect(lambda *_: self.add())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addLayout(o._row(add, None, close))
        self.resize(760, 640)
        self.refresh()

    def refresh(self):
        o = self.owner
        F, L = o.fresh_FL(use_max=self.src_combo.currentData() == "max", any_age=True)
        ex = [w["freq"] for w in o.watch] if self.excl_chk.isChecked() else []
        pk = [] if F is None else scan_peaks(F, L, self.thr.value(), self.merge.value(), exclude=ex)
        if self.wide_chk.isChecked():
            pk = [p_ for p_ in pk if not p_["wide"]]
        self.peaks = pk
        t = self.table
        t.setRowCount(len(pk))
        for r, p_ in enumerate(pk):
            it = QtWidgets.QTableWidgetItem("")
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            t.setItem(r, 0, it)
            where = spectrum_info(p_["f"], o.plan, o.tv)[0]
            vals = (f"{p_['f']:.3f}", o.lvl(p_["level"]),
                    (f"{p_['width'] / 1000:.1f} MHz (plateau)" if p_["wide"] else f"{p_['width']:.0f} kHz"), where)
            for c, v in enumerate(vals, start=1):
                it2 = QtWidgets.QTableWidgetItem(v)
                if c in (1, 2, 3):
                    it2.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                t.setItem(r, c, it2)
        t.resizeColumnsToContents()
        t.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        if F is None:
            self.count_lbl.setText("Pas encore de balayage : lance ▶ Démarrer (ou 📋 Préparer › ▶ Scanner ici).")
        else:
            self.count_lbl.setText(f"{len(pk)} signal(aux) au-dessus du seuil")

    def check_all(self, on):
        for r in range(self.table.rowCount()):
            self.table.item(r, 0).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def zoom(self, r):
        if 0 <= r < len(self.peaks):
            p_ = self.peaks[r]
            half = max(1.0, p_["width"] / 1000.0)
            self.owner.spec.getPlotItem().setXRange(p_["f"] - half, p_["f"] + half, padding=0)

    def add(self):
        o = self.owner
        rows = [r for r in range(self.table.rowCount()) if self.table.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not rows:
            self.msg.setText("Coche au moins un signal.")
            return
        pre = self.prefix.text().strip() or "Scan"
        taken = {w["name"] for w in o.watch}
        scene, group, status = self.scene.currentText().strip(), self.group.text().strip(), self.status.currentData()
        k, n = 1, 0
        for r in rows:
            p_ = self.peaks[r]
            while f"{pre} {k}" in taken:
                k += 1
            name = f"{pre} {k}"
            taken.add(name)
            o._append_watch(name, p_["f"], status=status or "", scene=scene, group=group,
                            bw=round(p_["width"] / 1000.0, 1) if p_["wide"] else 0.0)
            n += 1
        o.sort_watch()
        o.rebuild_tree()
        o.rebuild_watch_table()
        o._update_markers()
        o.set_status(f"📡 {n} fréquence(s) ajoutée(s) depuis le scan : renomme-les, range-les, ou supprime le bruit "
                     f"(clic droit sur la liste).")
        self.msg.setText(f"✔ {n} fréquence(s) ajoutée(s) à ta liste.")
        self.refresh()


class CoordDialog(QtWidgets.QDialog):
    """🪄 Coordination automatique : « trouve-moi N fréquences compatibles » pour un appareil, compatibles avec ta
    liste et entre elles, en évitant ce que le tinySA voit occupé, puis ajoutées à la liste."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.found = []
        self.setWindowTitle("Trouver des fréquences compatibles")
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(coord_note())
        info = QtWidgets.QLabel(
            "Comme un logiciel de coordination : choisis l'appareil et combien de fréquences il te faut. L'appli "
            "cherche, de bas en haut de la plage, des fréquences <b>compatibles avec toute ta liste et entre elles</b> "
            "(écart, intermod, filtre de l'appareil), sur le pas de l'appareil, en évitant ce que le tinySA voit "
            "occupé (max hold). Lance d'abord 📋 Préparer › ▶ Scanner ici quelques minutes.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 4)
        lay.addWidget(info)
        f = QtWidgets.QFormLayout()
        self.prof = QtWidgets.QComboBox()
        fill_rx_combo(self.prof, "✏ réglages de « Vérifier le plan »")
        ix = self.prof.findData("wisycom")
        self.prof.setCurrentIndex(max(0, ix))
        self.prof.setToolTip("Le profil d'appareil (filtre, écart, pas, tolérances) des nouvelles fréquences.\n"
                             "Un profil d'appareil avec une plage règle aussi « De … à ».")
        self.prof.currentIndexChanged.connect(lambda *_: self._range_from_prof())
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1, 64)
        self.n_spin.setValue(8)
        self.n_spin.setToolTip("Combien de fréquences chercher.")
        ext = o._band_extent() or (470.0, 694.0)
        self.lo = QtWidgets.QDoubleSpinBox()
        self.hi = QtWidgets.QDoubleSpinBox()
        for sp_, v in ((self.lo, ext[0]), (self.hi, ext[1])):
            sp_.setDecimals(3)
            sp_.setRange(0.1, 6000.0)
            sp_.setSuffix(" MHz")
            sp_.setValue(v)
            sp_.setToolTip("Plage où chercher (la bande de tes appareils : ex. 470–608 pour un modèle G4 « A »).")
        self.avoid = QtWidgets.QCheckBox("Éviter ce qui est occupé")
        self.avoid.setChecked(True)
        self.avoid.setToolTip("Écarte les fréquences où le spectre choisi dépasse ton seuil « occupé ».")
        self.spec_combo = QtWidgets.QComboBox()
        o.fill_coord_combo(self.spec_combo)
        self.avoid.toggled.connect(self.spec_combo.setEnabled)
        self.prefix = QtWidgets.QLineEdit("HF")
        self.prefix.setToolTip("Nom des nouvelles fréquences, numéroté : HF 1, HF 2…")
        self.scene = QtWidgets.QComboBox()
        self.scene.setEditable(True)
        self.scene.addItem("")
        for sc in o.scenes:
            self.scene.addItem(sc["name"])
        self.scene.setEditText("")
        self.scene.setToolTip("Scène où les ranger (facultatif).")
        self.group = QtWidgets.QLineEdit("")
        self.group.setToolTip("Groupe où les ranger (facultatif).")
        f.addRow("Appareil :", self.prof)
        f.addRow("Combien :", self.n_spin)
        f.addRow("De :", o._row(self.lo, "à", self.hi, None))
        f.addRow(self.avoid, self.spec_combo)
        # 7.66.3 : seuil « occupé » propre à la coordination (le seuil auto de la fenêtre suit le bruit INSTANTANÉ)
        po = o.plan_opts
        self.busy_mode = QtWidgets.QComboBox()
        for k_, lab_ in BUSY_MODES:
            self.busy_mode.addItem(lab_, k_)
        self.busy_mode.setCurrentIndex(max(0, self.busy_mode.findData(
            po.get("busy_mode") or ("auto" if o.thr_auto else "global"))))
        self.busy_mode.setToolTip("Quand une fréquence du spectre choisi est-elle « occupée » ?\n"
                                  "Auto : bruit de fond de CE spectre + la marge (conseillé, surtout en seuil auto :\n"
                                  "le max hold garde des heures de pics de bruit, plus hauts que le bruit du moment).\n"
                                  "Mon seuil « occupé » : celui de la barre des seuils. Seuil fixe : la valeur donnée.")
        self.busy_val = QtWidgets.QDoubleSpinBox()
        self.busy_val.setDecimals(0)
        self.busy_lbl = QtWidgets.QLabel("")
        self.busy_lbl.setToolTip("Seuil réellement utilisé avec le spectre choisi.")
        self.busy_mode.currentIndexChanged.connect(lambda *_: self._busy_ui())
        self.busy_val.valueChanged.connect(lambda *_: self._busy_store())
        self.spec_combo.currentIndexChanged.connect(lambda *_: self._busy_preview())
        f.addRow("Occupé si :", o._row(self.busy_mode, self.busy_val, self.busy_lbl, None))
        self.rbw_lbl = QtWidgets.QLabel("")
        self.rbw_lbl.setWordWrap(True)
        self.rbw_lbl.setToolTip(COORD_RBW_TIP)
        self.rbw_btn = QtWidgets.QPushButton("RBW 30 kHz")
        self.rbw_btn.setToolTip("Passe la finesse de mesure à 30 kHz (balayage plus lent) : refais ensuite le scan "
                                "(efface les pics gardés et laisse balayer quelques minutes).")
        self.rbw_btn.clicked.connect(lambda *_: (o.set_rbw_fine(), self._busy_preview()))
        f.addRow("Scan :", o._row(self.rbw_lbl, self.rbw_btn))
        for w_ in (self.busy_mode, self.busy_val, self.busy_lbl):
            self.avoid.toggled.connect(w_.setEnabled)
        self._busy_ui()
        f.addRow("Nom :", self.prefix)
        self.spec_combo.currentIndexChanged.connect(lambda *_: self._scene_from_spec())
        self._scene_from_spec()
        f.addRow("Scène :", self.scene)
        f.addRow("Groupe :", self.group)
        for w_ in (self.scene.currentTextChanged, self.group.textChanged):
            w_.connect(lambda *_: self._prof_from_group())
        lay.addLayout(f)
        # plusieurs appareils d'un coup (QLX-D + PSM 1000…) : des « lots », tous compatibles entre eux
        self.lots = []
        lbox = QtWidgets.QGroupBox("Plusieurs appareils (facultatif)")
        lbox.setToolTip("Coordination entre appareils : chaque lot = un appareil, combien, sa plage et son nom. Les lots\n"
                        "sont cherchés dans l'ordre et tous compatibles entre eux, chacun avec les règles de SON appareil.\n"
                        "Mets l'appareil le plus exigeant (le plus d'écart, les plus grandes tolérances) en premier.")
        lv = QtWidgets.QVBoxLayout(lbox)
        self.lot_list = QtWidgets.QListWidget()
        self.lot_list.setMaximumHeight(96)
        self.lot_list.setToolTip(lbox.toolTip())
        b_lot = QtWidgets.QPushButton("＋ Ajouter ce lot (appareil, combien, plage, nom ci-dessus)")
        b_lot.setToolTip("Garde les réglages ci-dessus comme un lot ; change d'appareil et ajoute le suivant.")
        b_lot.clicked.connect(lambda *_: self.add_lot())
        b_unlot = QtWidgets.QPushButton("Retirer")
        b_unlot.setToolTip("Retire le lot choisi (tous si aucun n'est choisi).")
        b_unlot.clicked.connect(lambda *_: self.del_lot())
        lv.addWidget(self.lot_list)
        lv.addLayout(o._row(b_lot, b_unlot))
        self.lot_hint = QtWidgets.QLabel("Aucun lot : on cherche seulement pour l'appareil ci-dessus.")
        self.lot_hint.setWordWrap(True)
        lv.addWidget(self.lot_hint)
        lay.addWidget(lbox)
        go = QtWidgets.QPushButton("🪄 Chercher")
        self.go_btn, self._job = go, None
        go.setToolTip("Cherche les fréquences. Le calcul tourne en arrière-plan : l'appli reste utilisable, et le bouton\n"
                      "devient « Annuler le calcul » pendant ce temps.")
        go.clicked.connect(lambda *_: self.compute())
        # 7.60.2 (Clément : « une méthode aléatoire aussi, à la suite ça fonctionne pas en général »)
        self.order_combo = QtWidgets.QComboBox()
        for k_, lab_ in COORD_ORDERS:
            self.order_combo.addItem(lab_, k_)
        self.order_combo.setCurrentIndex(max(0, self.order_combo.findData(o.plan_opts.get("coord_order", "random"))))
        self.order_combo.setToolTip("Comment placer les nouvelles fréquences :\n"
                                    "🎲 au hasard : chaque fréquence part d'un point tiré au hasard dans la plage, donc\n"
                                    "elles sont réparties ; « meilleur de 3 essais » refait le tirage 3 fois et garde\n"
                                    "celui qui en trouve le plus (puis le plus espacé). Bien plus rapide avec beaucoup\n"
                                    "de fréquences.\n"
                                    "⬆ à la suite : la plus basse compatible d'abord, tout se tasse en bas de la plage\n"
                                    "(lent et souvent moins bon avec beaucoup de fréquences).")
        self.order_combo.currentIndexChanged.connect(
            lambda *_: o.plan_opts.__setitem__("coord_order", self.order_combo.currentData()))
        lay.addLayout(o._row(QtWidgets.QLabel("Méthode :"), self.order_combo, go))
        self.bar = QtWidgets.QProgressBar()            # 7.61 : fréquences trouvées pendant le calcul
        self.bar.setFormat("%v / %m")
        self.bar.setToolTip("Fréquences trouvées pendant le calcul (essai en cours).")
        self.bar.hide()
        lay.addWidget(self.bar)
        self.res = QtWidgets.QListWidget()
        self.res.setToolTip("Fréquences trouvées, compatibles avec ta liste et entre elles.")
        lay.addWidget(self.res, 1)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        add = QtWidgets.QPushButton("＋ Ajouter à ma liste (statut En service)")
        add.setToolTip("Ajoute les fréquences trouvées, avec cet appareil, au statut « doit émettre ».")
        add.clicked.connect(lambda *_: self.add())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addLayout(o._row(add, None, close))
        self.resize(620, 640)

    def _prof_from_group(self):
        """Le groupe choisi a un ou des appareils (📻, clic droit dans « Mes fréquences ») : le 1er devient celui de la
        recherche ; s'il y en a plusieurs, un lot par appareil est préparé (si aucun lot n'existe encore)."""
        rxs = self.owner.group_rxs(self.owner.group_row(self.scene.currentText().strip(), self.group.text().strip()))
        if not rxs:
            return
        ix = self.prof.findData(rxs[0])
        if ix >= 0:
            self.prof.setCurrentIndex(ix)
        if len(rxs) > 1 and not self.lots:
            for k in rxs:
                d = rx_profile(k)
                lo, hi = ((d["lo"], d["hi"]) if d.get("hi", 0) > d.get("lo", 0) > 0
                          else (self.lo.value(), self.hi.value()))
                nm = rx_short(k).split(" ", 1)          # « Shure PSM 900 » -> « PSM 900 » (nom des fréquences)
                self.lots.append(dict(rx=k, n=self.n_spin.value(), lo=lo, hi=hi,
                                      prefix=nm[1] if len(nm) > 1 else nm[0]))
            self._show_lots()

    def _lot_now(self):
        return dict(rx=self.prof.currentData() or "", n=self.n_spin.value(), lo=self.lo.value(), hi=self.hi.value(),
                    prefix=self.prefix.text().strip() or "HF")

    def add_lot(self):
        self.lots.append(self._lot_now())
        self._show_lots()

    def del_lot(self):
        r = self.lot_list.currentRow()
        if 0 <= r < len(self.lots):
            self.lots.pop(r)
        else:
            self.lots = []
        self._show_lots()

    def _show_lots(self):
        self.lot_list.clear()
        for L_ in self.lots:
            self.lot_list.addItem(f"{L_['n']} × {rx_short(L_['rx']) if L_['rx'] else 'réglages par défaut'}   "
                                  f"{L_['lo']:.3f}–{L_['hi']:.3f} MHz   « {L_['prefix']} »")
        self.lot_hint.setText("Les lots sont cherchés dans l'ordre, tous compatibles entre eux et avec ta liste."
                              if self.lots else "Aucun lot : on cherche seulement pour l'appareil ci-dessus.")

    def _range_from_prof(self):
        d = rx_profile(self.prof.currentData())
        if d and d.get("hi", 0) > d.get("lo", 0) > 0:
            self.lo.setValue(d["lo"])
            self.hi.setValue(d["hi"])

    def _scene_from_spec(self):
        """Coordination pour une scène : les nouvelles fréquences y sont rangées (si une telle scène existe)."""
        sc = self.spec_combo.currentData()
        if sc not in ("live", "all", None) and self.owner.scene_by_name(sc) is not None:
            self.scene.setEditText(sc)

    def _new_profile(self):
        d = rx_profile(self.prof.currentData())
        if d is None:
            po = self.owner.plan_opts
            d = dict(sep=po["sep"] / 1000.0, filt=po["filt"], step=po["step"] / 1000.0, tol=IM_TOL_PRESETS[0][1])
        return d

    def _lot_profile(self, rx):
        d = rx_profile(rx)
        if d is None:
            po = self.owner.plan_opts
            d = dict(sep=po["sep"] / 1000.0, filt=po["filt"], step=po["step"] / 1000.0, tol=IM_TOL_PRESETS[0][1])
        return d

    def _busy_ui(self):
        mode = self.busy_mode.currentData()
        po = self.owner.plan_opts
        self.busy_val.blockSignals(True)
        if mode == "fixed":
            self.busy_val.setRange(-130, 0)
            self.busy_val.setPrefix("")
            self.busy_val.setSuffix(" dBm")
            self.busy_val.setValue(po.get("busy_fixed", -80.0))
        else:
            self.busy_val.setRange(3, 40)
            self.busy_val.setPrefix("bruit + ")
            self.busy_val.setSuffix(" dB")
            self.busy_val.setValue(po.get("busy_margin", BUSY_MARGIN))
        self.busy_val.blockSignals(False)
        self.busy_val.setVisible(mode != "global")
        self._busy_store()

    def _busy_store(self):
        po = self.owner.plan_opts
        mode = self.busy_mode.currentData()
        po["busy_mode"] = mode
        if mode == "fixed":
            po["busy_fixed"] = float(self.busy_val.value())
        elif mode == "auto":
            po["busy_margin"] = float(self.busy_val.value())
        self._busy_preview()

    def _busy_lim(self, L):
        return self.owner.busy_limit(L, self.busy_mode.currentData())

    def _busy_preview(self):
        o = self.owner
        try:
            Fm, Lm = o.coord_FL(self.spec_combo.currentData())
        except Exception:  # noqa: BLE001 — aperçu seulement
            Fm, Lm = None, None
        rb, est = o.coord_rbw(self.spec_combo.currentData())
        txt, ok = rbw_coord_line(rb, est, TR, step=scan_step_khz(Fm))
        self.rbw_lbl.setText(txt)
        self.rbw_lbl.setStyleSheet("" if ok else f"color: {o.theme.get('st_weak', '#f59e0b')};")
        self.rbw_btn.setVisible(not ok and o.rbw_combo.currentData() != COORD_RBW_MAX)
        if Fm is None:
            self.busy_lbl.setText("")
            return
        lim = self._busy_lim(Lm)
        pct = 100.0 * float(np.mean(np.asarray(Lm, float) >= lim)) if len(Lm) else 0.0
        self.busy_lbl.setText(TR("= {} · {} % du spectre au-dessus").format(o.lvl(lim, suffix=True), f"{pct:.0f}"))

    def compute(self):
        """7.60.2 (Clément : 40 fréquences, plusieurs appareils -> plus de 90 s de calcul, interface figée, la garde
        relançait l'appli) : le calcul tourne dans un fil à part (MainWindow.run_heavy) ; le bouton devient
        « Annuler le calcul » pendant ce temps."""
        o = self.owner
        if self._job is not None and not self._job["done"]:
            self._job["cancel"] = True
            getattr(self, "_info", {})["cancel"] = True
            self._job = None
            self.go_btn.setText(TR("🪄 Chercher"))
            self.msg.setText("Calcul annulé.")
            return
        ws = list(o.watch)
        P = [rx_profile(o.rx_of(w)) or self._new_profile() for w in ws]
        busy = None
        if self.avoid.isChecked():
            Fm, Lm = o.coord_FL(self.spec_combo.currentData())
            if Fm is not None:                     # seuil « occupé » : le max hold du bruit dépasse souvent « faible »
                lim = self._busy_lim(Lm)
                self._lim_used = lim
                win = max(0.05, o.win_spin.value() / 1000.0)
                busy = busy_pred(Fm, Lm, lim, win)
        lots = list(self.lots) or [self._lot_now()]
        spec = []
        clipped = []
        for L_ in lots:
            d = self._lot_profile(L_["rx"])
            lo, hi = L_["lo"], L_["hi"]
            bd = rx_band(d)
            if bd:                                   # 7.61 : jamais hors de la bande de l'appareil
                cl = band_clip(lo, hi, bd)
                if cl is None:
                    self.msg.setText(f"La plage {lo:g}–{hi:g} MHz est hors de la bande de {rx_short(L_['rx'])} "
                                     f"({bd[0]:g}–{bd[1]:g} MHz).")
                    return
                if cl != (lo, hi):
                    clipped.append(f"{rx_short(L_['rx'])} : {cl[0]:g}–{cl[1]:g} MHz")
                lo, hi = cl
            spec.append(dict(n=L_["n"], sep=d["sep"], tol=d["tol"], filt=d["filt"], lo=lo, hi=hi, step=d["step"],
                             img=float(d.get("img") or 0.0)))
        self._clipped = clipped
        args = (spec, [w["freq"] for w in ws], [not o.is_keep_free(w["status"]) for w in ws],
                [float(w.get("bw") or 0.0) for w in ws], [q["sep"] for q in P], [q["tol"] for q in P],
                [q["filt"] for q in P], o.reg_busy(busy))
        self.res.clear()
        self.go_btn.setText(TR("■ Annuler le calcul"))
        order = self.order_combo.currentData() or "random"
        info = self._info = {}          # partagé avec le fil : « cancel » posé par Annuler / la fermeture
        allowed = o.reg_pred()

        def work():
            got = pf_fill_lots(*args, order="low" if order == "low" else "random", tries=COORD_TRIES.get(order, 1),
                               img=[float(q.get("img") or 0.0) for q in P],
                               progress=lambda k, n: info.update(step=(k, n)),
                               cancel=lambda: bool(info.get("cancel")),
                               found=lambda k, n: info.update(found=(k, n)))
            whys = []                   # 7.61 : pour chaque lot incomplet, ce qui bloque (plan final)
            allF = args[1] + [c for g in got for c in g]
            allS = args[4] + [sp["sep"] for sp, g in zip(spec, got) for _c in g]
            allB = args[3] + [0.0 for g in got for _c in g]
            for sp, g in zip(spec, got):
                whys.append(coord_blockers(sp["lo"], sp["hi"], sp["step"], allF, allB, sp["sep"], allS, busy, allowed)
                            if len(g) < sp["n"] else None)
            return got, whys
        self.bar.setRange(0, max(1, sum(int(sp["n"]) for sp in spec)))
        self.bar.setValue(0)
        self.bar.show()

        def status():
            if info.get("found"):
                self.bar.setValue(info["found"][0])
            st = TR("{} / {} trouvées").format(*info["found"]) if info.get("found") else ""
            if info.get("step") and info["step"][1] > 1:
                st = TR("essai {} / {}").format(*info["step"]) + (f" · {st}" if st else "")
            return st
        self._job = o.run_heavy(work, lambda res, err: self._computed(lots, res, err), self.msg,
                                "Recherche des fréquences", status=status)

    def closeEvent(self, e):
        if self._job is not None:
            self._job["cancel"] = True             # le fil s'arrête à la fin de l'essai en cours ; résultat ignoré
            getattr(self, "_info", {})["cancel"] = True
            self._job = None
            self.go_btn.setText(TR("🪄 Chercher"))
        super().closeEvent(e)

    def _computed(self, lots, res, err):
        o = self.owner
        self._job = None
        self.go_btn.setText(TR("🪄 Chercher"))
        self.bar.hide()
        if err is not None:
            self.msg.setText(f"Calcul impossible : {err}")
            return
        got, whys = res
        self.found = [(L_, c) for L_, cs in zip(lots, got) for c in cs]
        self.res.clear()
        for L_, cs in zip(lots, got):
            for k, c in enumerate(cs, 1):
                rt = o.reg_tag(c)
                self.res.addItem(f"{L_['prefix']} {k}   {c:.3f} MHz" + (f"   ({rx_short(L_['rx'])})" if len(lots) > 1
                                                                        and L_["rx"] else "")
                                 + (f"   ⚠ {TR(rt)}" if rt else ""))
        short = [f"{len(cs)} / {L_['n']} {L_['prefix']}" for L_, cs in zip(lots, got) if len(cs) < L_["n"]]
        n_ = len(self.found)
        self.msg.setText((f"✔ {n_} fréquence(s) trouvée(s), toutes compatibles entre elles." if len(lots) > 1 else
                          f"✔ {n_} fréquence(s) trouvée(s).")
                         if not short else
                         f"⚠ Seulement {', '.join(short)} : la plage est pleine pour ces règles. Élargis la plage, "
                         "choisis un appareil plus robuste (écart et tolérances plus serrés) ou des règles plus souples.")
        for L_, wy in zip(lots, whys):               # 7.61 : pourquoi pas plus
            if wy:
                self.msg.setText(self.msg.text() + "\n" + TR("Ce qui bloque ({}) : {}").format(
                    L_["prefix"], coord_why_text(wy, TR)) + "\n" + TR(coord_why_advice(wy)))
        if getattr(self, "_clipped", None):
            self.msg.setText(self.msg.text() + "\n" + TR("Plage ramenée à la bande de l'appareil : {}").format(
                " · ".join(self._clipped)))
        if o.reg_note():
            self.msg.setText(self.msg.text() + "\n" + o.reg_note())

    def add(self):
        o = self.owner
        if not self.found:
            self.msg.setText("Lance d'abord « 🪄 Chercher ».")
            return
        taken = {w["name"] for w in o.watch}
        st = next((s_["name"] for s_ in o.statuses if s_.get("on")), "")
        nums = {}
        for L_, c in self.found:
            pre = L_["prefix"] or "HF"
            k = nums.get(pre, 1)
            while f"{pre} {k}" in taken:
                k += 1
            nums[pre] = k
            taken.add(f"{pre} {k}")
            o._append_watch(f"{pre} {k}", c, status=st, scene=self.scene.currentText().strip(),
                            group=self.group.text().strip())
            if L_["rx"] and L_["rx"] != o.rx_of(o.watch[-1]):
                o.watch[-1]["rx"] = L_["rx"]           # sinon : il hérite de l'appareil (du 1er) du groupe
        o.sort_watch()
        o.rebuild_tree()
        o.rebuild_watch_table()
        o._update_markers()
        o.set_status(f"🪄 {len(self.found)} fréquence(s) coordonnée(s) ajoutée(s) à ta liste.")
        self.msg.setText(f"✔ {len(self.found)} fréquence(s) ajoutée(s). Vérifie avec 📋 Préparer › 🧮 Vérifier le plan.")
        self.found = []
        self.res.clear()


class OccupancyDialog(QtWidgets.QDialog):
    """📊 Occupation par heure : pour chaque fréquence, le % du temps où elle était occupée, heure par heure (mémoire
    ou session enregistrée). Une réserve « doit rester libre » touchée = créneau à risque."""

    def __init__(self, owner, store=None, watch=None, title=""):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Occupation par heure" + (f" — {title}" if title else ""))
        lay = QtWidgets.QVBoxLayout(self)
        ws = list(watch if watch is not None else o.watch)
        store = store or o.store
        thr = o.thr_spin.value()
        occ = store_occupancy(store, [w["freq"] for w in ws], thr,
                              lambda t: datetime.fromtimestamp(t).hour, max(0.05, o.win_spin.value() / 1000.0))
        hours = sorted(occ)
        info = QtWidgets.QLabel(
            f"% du temps où chaque fréquence dépassait le seuil « occupé » ({o.lvl(thr, suffix=True)}), heure par "
            "heure. Pour une fréquence qui doit émettre, c'est normal ; pour une <b>réserve qui doit rester libre</b>, "
            "c'est un créneau à risque (quelqu'un d'autre émet). Survole une case pour le détail.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 3)
        lay.addWidget(info)
        t = QtWidgets.QTableWidget(len(ws), len(hours))
        t.setHorizontalHeaderLabels([f"{h:02d} h" for h in hours])
        t.setVerticalHeaderLabels([f"{w['name']}  {w['freq']:.3f}" for w in ws])
        t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        th, base = o.theme, o.theme["ui_base"]
        risky = []
        for c, h in enumerate(hours):
            n, k = occ[h]
            for r, w in enumerate(ws):
                if not n[r]:
                    continue
                pct = 100.0 * k[r] / n[r]
                it = QtWidgets.QTableWidgetItem(f"{pct:.0f} %")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                free = o.is_keep_free(w["status"])
                col = th["st_occ"] if free else th["st_free"]
                if pct > 0:
                    bg = blend(col, base, min(0.85, 0.2 + pct / 120.0))
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                it.setToolTip(f"{w['name']} ({w['freq']:.3f} MHz) à {h:02d} h : occupée {pct:.0f} % du temps "
                              f"({int(k[r])} balayages sur {int(n[r])})")
                t.setItem(r, c, it)
                if free and pct >= 5:
                    risky.append((pct, w["name"], h))
        t.resizeColumnsToContents()
        lay.addWidget(t, 1)
        risky.sort(reverse=True)
        self.risky = risky
        self.sum_lbl = QtWidgets.QLabel(
            ("⚠ Réserves touchées : " + ", ".join(f"{n_} à {h:02d} h ({p:.0f} %)" for p, n_, h in risky[:8])
             + (" …" if len(risky) > 8 else "")) if risky else
            ("✔ Aucune réserve « doit rester libre » touchée." if hours else
             "Pas encore de balayage à analyser (lance ▶ Démarrer, ou ouvre une session dans la relecture)."))
        self.sum_lbl.setWordWrap(True)
        lay.addWidget(self.sum_lbl)
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self.table = t
        self.resize(900, 600)


class SpectrumLegendDialog(QtWidgets.QDialog):
    """« ❓ Courbes » : ce que montre chaque courbe / ligne du spectre, et les réglages correspondants (reliés dans les
    deux sens aux réglages de la fenêtre principale)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Le spectre : courbes, seuils et repères")
        th = o.theme
        lay = QtWidgets.QVBoxLayout(self)
        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        self._links = []

        def swatch(color, style="━━━"):
            lb = QtWidgets.QLabel(style)
            lb.setStyleSheet(f"color:{color}; font-weight:bold; font-size:16px;")
            lb.setToolTip("Couleur à l'écran (modifiable : ☰ Plus › 🎨 Couleurs).")
            return lb

        def text(t):
            lb = QtWidgets.QLabel(t)
            lb.setWordWrap(True)
            lb.setMinimumWidth(380)
            return lb

        def lspin(main):
            sp = LevelSpin()
            sp.setRange(main.minimum(), main.maximum())
            sp.setSingleStep(main.singleStep())
            sp.setValue(main.value())
            sp.setToolTip(main.toolTip() or "Même réglage que dans la fenêtre principale.")
            self._link(sp, main)
            return sp

        def lchk(main, txt):
            c = QtWidgets.QCheckBox(txt)
            c.setChecked(main.isChecked())
            c.setToolTip(main.toolTip() or "Même case que dans la fenêtre principale.")
            c.toggled.connect(lambda *_: main.setChecked(c.isChecked()))
            main.toggled.connect(lambda *_: (c.blockSignals(True), c.setChecked(main.isChecked()), c.blockSignals(False)))
            return c

        def btn(txt, fn, tip):
            b = QtWidgets.QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(lambda *_: fn())
            return b

        def ctrls(*ws):
            w = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            for x in ws:
                h.addWidget(x)
            h.addStretch(1)
            return w

        rows = [
            (swatch(th["curve"]), "Direct",
             "Le dernier balayage : le niveau reçu à chaque fréquence, en dBm. Le « tapis » du bas est le bruit de "
             "fond (le tinySA + le lieu) ; une bosse qui sort du tapis = un émetteur.",
             None),
            (swatch(th["maxhold"]), "Max hold",
             "Le plus haut niveau vu à chaque fréquence depuis le dernier « Reset max » : garde la trace des "
             "signaux brefs ou intermittents (talkie, burst, brouilleur qui passe).",
             ctrls(lchk(o.hold_chk, "Afficher"), btn("Reset max", o.reset_max, "Efface le max hold."))),
            (swatch(th["ref"], "┅┅┅"), "Référence",
             "Le spectre « calme » du lieu, capturé avant le show (📏 Référence › Capturer). Sert à voir ce qui a "
             "changé, et au seuil « sur référence » (mode expert).",
             ctrls(lchk(o.showref_chk, "Afficher"),
                   btn("Capturer (max hold)", lambda: o.capture_ref("max"), "Enregistre le max hold comme référence."))),
            (swatch(th["thr"], "╍╍╍"), "Seuil « occupé »",
             "Au-dessus = la fréquence est occupée : CONFLIT si elle doit rester libre, « OK » si elle doit "
             "émettre. Ligne déplaçable à la souris sur le spectre. Règle-le quelques dB au-dessus du tapis "
             "(« Auto » le fait d'après le bruit mesuré).",
             ctrls(lspin(o.thr_spin))),
            (swatch(th["thr"], "- - -"), "Seuil auto (tirets)",
             "Avec « Auto » : un seuil par fréquence = bruit de fond local + marge. Il monte sur les canaux TNT "
             "(le fond local, c'est la TNT) pour qu'un micro posé dedans reste surveillé.",
             ctrls(btn("❓ Comment ça marche", o.show_auto_thr_help, "La fiche complète du seuil auto."))),
            (swatch(th["thr_weak"], "┈┈┈"), "Niveau « faible »",
             "Entre ce niveau et le seuil occupé : signal faible (micro loin, pile faible, porteuse lointaine). "
             "Ne déclenche pas de CONFLIT, mais s'affiche en jaune.",
             ctrls(lchk(o.weak_chk, "Actif"), lspin(o.weak_spin))),
            (swatch("#b06cff", "━·━"), "Trop fort",
             "Au-dessus : alarme ⚠ TROP FORT. Un signal très fort (talkie collé à une antenne, émetteur trop "
             "près) sature les récepteurs et fabrique de l'intermod. Le tinySA lui-même sature vers −10 dBm.",
             ctrls(lchk(o.strong_chk, "Actif"), lspin(o.strong_spin))),
            (swatch(th["st_free"], "┃"), "Repères",
             "Un trait vertical par fréquence de ta liste, coloré selon l'état du signal (vert = OK, bleu = libre, "
             "rouge = problème, jaune = faible). Pointillés = signal inconnu hors liste.",
             ctrls(btn("📍 Repères…", lambda: o.mk_menu.exec(QtGui.QCursor.pos()), "Quels repères afficher."))),
            (swatch("#64748b", "▬▬"), "Bandeaux du bas",
             "Canaux TV et attributions du pays (TNT, 4G/5G, aéro…) : survole-les pour le détail. Indicatif.",
             None),
        ]
        for r, (sw, name, expl, ctl) in enumerate(rows):
            nm = QtWidgets.QLabel(f"<b>{name}</b>")
            grid.addWidget(sw, r, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(nm, r, 1, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(text(expl), r, 2)
            if ctl is not None:
                grid.addWidget(ctl, r, 3, Qt.AlignmentFlag.AlignTop)
        rf = QtWidgets.QLabel(
            "<b>Pour aller plus loin (RF)</b><br>"
            "• <b>dBm</b> : puissance reçue, échelle logarithmique ; +3 dB = deux fois plus, +10 dB = dix fois plus. "
            "Un micro à 10 m donne typiquement −40 à −60 dBm, le bruit de fond est vers −100.<br>"
            "• <b>RBW</b> (largeur de résolution, mode expert) : la « finesse » du tinySA. RBW large = balayage "
            "rapide mais tapis plus haut et signaux proches fusionnés ; RBW étroit = tapis plus bas, plus lent.<br>"
            "• Un émetteur <b>numérique</b> ou un bloc large (Spectera) ressemble à un plateau, pas à une pointe.<br>"
            "• Le niveau dépend de l'antenne, du câble, de la distance et de l'atténuateur : compare des mesures "
            "faites avec le même montage.")
        rf.setWordWrap(True)
        rf.setMinimumHeight(rf.fontMetrics().height() * 7)
        lay.addWidget(rf)
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre (les réglages sont déjà appliqués).")
        close.clicked.connect(self.close)
        lay.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)
        self.resize(900, 640)

    def _link(self, sp, main):
        sp.valueChanged.connect(lambda v: main.setValue(v))

        def back(*_):
            sp.blockSignals(True)
            sp.setValue(main.value())
            sp.blockSignals(False)
        main.valueChanged.connect(back)


class LevelAxis(pg.AxisItem):
    """Axe vertical du spectre gradué dans l'unité choisie (les courbes restent en dBm)."""
    unit = "dbm"

    def tickStrings(self, values, scale, spacing):
        return [fmt_level(v * scale, LevelAxis.unit, 0) for v in values]


class WallFullWindow(QtWidgets.QWidget):
    """Vraie fenêtre plein écran pour le mur (un panneau détaché refuse souvent le plein écran)."""

    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.Window)
        self.owner = owner
        self.setWindowTitle(f"{APP_NAME} – Mur de fréquences")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

    def closeEvent(self, e):
        if self.owner.wall_is_fullscreen():
            self.owner.wall_fullscreen(False)
        super().closeEvent(e)


class PanelWindow(QtWidgets.QWidget):
    """Un panneau (Spectre, Liste, Waterfall…) sorti dans une VRAIE fenêtre Windows : barre de titre normale
    (agrandir, réduire), plein écran (F11), placée sur l'écran voulu. Un panneau « flottant » de Qt reste une fenêtre
    outil (pas d'agrandir, toujours au-dessus, se ré-accroche quand on le frôle). Fermer = raccrocher le panneau."""

    def __init__(self, owner, dock):
        super().__init__(None, Qt.WindowType.Window)
        self.owner, self.dock, self.closing = owner, dock, False
        self.setWindowTitle(f"{APP_NAME} – {dock.windowTitle()}")
        self.setWindowIcon(owner.windowIcon())
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.bar = QtWidgets.QWidget()
        hb = QtWidgets.QHBoxLayout(self.bar)
        hb.setContentsMargins(6, 2, 6, 2)
        hint = QtWidgets.QLabel("F11 : plein écran")
        hint.setStyleSheet("color: gray")
        nxt = QtWidgets.QPushButton("🖥 Écran suivant")
        nxt.setToolTip("Envoie cette fenêtre sur l'écran suivant (agrandie).")
        nxt.clicked.connect(lambda *_: self.owner.panel_next_screen(self.dock))
        full = QtWidgets.QPushButton("⛶ Plein écran")
        full.setToolTip("Plein écran sur cet écran (F11 ; Échap pour sortir).")
        full.clicked.connect(lambda *_: self.toggle_full())
        back = QtWidgets.QPushButton("📌 Raccrocher")
        back.setToolTip("Remet ce panneau dans la fenêtre principale (comme fermer cette fenêtre).")
        back.clicked.connect(lambda *_: self.owner.panel_window(self.dock, False))
        for w_ in (hint, None, nxt, full, back):
            hb.addStretch(1) if w_ is None else hb.addWidget(w_)
        lay.addWidget(self.bar)
        self.body = QtWidgets.QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self.body, 1)
        QtGui.QShortcut(QtGui.QKeySequence("F11"), self, activated=self.toggle_full)
        QtGui.QShortcut(QtGui.QKeySequence("Escape"), self,
                        activated=lambda: self.isFullScreen() and self.toggle_full())

    def toggle_full(self):
        if self.isFullScreen():
            self.showNormal()
            self.bar.show()
        else:
            self.bar.hide()                       # tout l'écran pour le contenu ; F11 / Échap pour sortir
            self.showFullScreen()

    def mode(self):
        return "full" if self.isFullScreen() else ("max" if self.isMaximized() else "normal")

    def closeEvent(self, e):
        if not self.closing:
            QtCore.QTimer.singleShot(0, lambda d=self.dock: self.owner.panel_window(d, False))
        super().closeEvent(e)


class WallPickDialog(QtWidgets.QDialog):
    """Cases à cocher : quelles fréquences ont une tuile sur le mur (rangées par scène › groupe)."""

    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle("Fréquences du mur")
        self.resize(460, 560)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Fréquence", "MHz"])
        self.tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.items = []                                   # (item, index dans owner.watch)
        groups = {}
        for i, w in enumerate(owner.watch):
            key = owner.layer_text(w) or "Sans scène"
            parent = groups.get(key)
            if parent is None:
                parent = QtWidgets.QTreeWidgetItem([key, ""])
                parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                self.tree.addTopLevelItem(parent)
                groups[key] = parent
            it = QtWidgets.QTreeWidgetItem([w["name"], f"{w['freq']:.3f}"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Unchecked if w.get("hide_wall") else Qt.CheckState.Checked)
            parent.addChild(it)
            self.items.append((it, i))
        self.tree.expandAll()
        b_all = QtWidgets.QPushButton("Tout cocher")
        b_none = QtWidgets.QPushButton("Tout décocher")
        b_all.clicked.connect(lambda *_: self._set_all(True))
        b_none.clicked.connect(lambda *_: self._set_all(False))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        info = QtWidgets.QLabel("Coche les fréquences qui ont une tuile sur le mur. Cocher une scène / un groupe "
                                "coche tout ce qu'il contient.")
        info.setWordWrap(True)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.tree, 1)
        lay.addLayout(MainWindow._row(b_all, b_none, None))
        lay.addWidget(bb)

    def _set_all(self, on):
        for it, _i in self.items:
            it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)

    def shown(self):
        """-> {index: True si la fréquence a une tuile}."""
        return {i: it.checkState(0) == Qt.CheckState.Checked for it, i in self.items}


class LabelsDialog(QtWidgets.QDialog):
    """Tes mots ET tes couleurs pour la colonne Signal (et le mur, la page web) : un réglage par situation."""

    def __init__(self, parent, labels, colors=None, default_color=None):
        super().__init__(parent)
        self.setWindowTitle("Mots et couleurs affichés")
        self.resize(720, 500)
        self._dflt = default_color or (lambda k: "#808080")
        self._cols = dict(colors or {})
        info = QtWidgets.QLabel("Pour chaque situation : le mot que tu veux voir (colonne Signal, mur, page web) et sa "
                                "couleur (clic sur la pastille). Vide = mot par défaut. Par défaut : vert = mon "
                                "émetteur est là (OK), bleu = libre, orange = à surveiller, rouge = problème.")
        info.setWordWrap(True)
        self.table = QtWidgets.QTableWidget(len(SIGNAL_LABELS), 3)
        self.table.setHorizontalHeaderLabels(["Situation", "Mot affiché", "Couleur"])
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        for r, (key, situ, dflt) in enumerate(SIGNAL_LABELS):
            it = QtWidgets.QTableWidgetItem(situ)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            it.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(r, 0, it)
            ed = QtWidgets.QTableWidgetItem(labels.get(key, dflt))
            ed.setToolTip(f"Par défaut : {dflt}")
            self.table.setItem(r, 1, ed)
            b = QtWidgets.QPushButton()
            b.setToolTip("Clic : choisir la couleur de cette situation.")
            b.clicked.connect(lambda *_, k=key: self.pick_color(k))
            self.table.setCellWidget(r, 2, b)
        self._paint()
        b_reset = QtWidgets.QPushButton("Revenir aux mots et couleurs par défaut")
        b_reset.clicked.connect(lambda *_: self.reset())
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.addButton(b_reset, QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.table, 1)
        lay.addWidget(bb)

    def _paint(self):
        for r, (key, _s, _d) in enumerate(SIGNAL_LABELS):
            c = self._cols.get(key) or self._dflt(key)
            b = self.table.cellWidget(r, 2)
            b.setText(("● " if key in self._cols else "") + c)
            b.setStyleSheet(f"QPushButton{{background:{c};color:{contrast_text(c)};border-radius:4px;padding:2px 8px}}")

    def pick_color(self, key):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self._cols.get(key) or self._dflt(key)), self,
                                            "Couleur de la situation")
        if c.isValid():
            self._cols[key] = c.name()
            self._paint()

    def reset(self):
        for r, (_k, _s, d) in enumerate(SIGNAL_LABELS):
            self.table.item(r, 1).setText(d)
        self._cols = {}
        self._paint()

    def colors(self):
        """Seulement les couleurs choisies (clé -> "#rrggbb")."""
        return clean_colors(self._cols)

    def values(self):
        """Seulement les mots changés (clé -> texte)."""
        out = {}
        for r, (key, _situ, dflt) in enumerate(SIGNAL_LABELS):
            txt = self.table.item(r, 1).text().strip()
            if txt and txt != dflt:
                out[key] = txt[:30]
        return out


class ShowInfoDialog(QtWidgets.QDialog):
    """Infos d'un show : nom, lieu, dates, notes (pour le retrouver l'année suivante)."""

    def __init__(self, parent, meta, title="Infos du show", country=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 400)
        self.name = QtWidgets.QLineEdit(meta.get("name", ""))
        self.name.setPlaceholderText("ex. Festival des Vieilles Charrues")
        self.venue = QtWidgets.QLineEdit(meta.get("venue", ""))
        self.venue.setPlaceholderText("ex. Carhaix — scène Glenmor")
        today = QtCore.QDate.currentDate()
        self.d_from, self.d_to = QtWidgets.QDateEdit(), QtWidgets.QDateEdit()
        for wd, key in ((self.d_from, "date_from"), (self.d_to, "date_to")):
            wd.setCalendarPopup(True)
            wd.setDisplayFormat("dd/MM/yyyy")
            d = QtCore.QDate.fromString(meta.get(key, ""), "yyyy-MM-dd")
            wd.setDate(d if d.isValid() else today)
        self.notes = QtWidgets.QPlainTextEdit(meta.get("notes", ""))
        self.notes.setPlaceholderText("Contacts, coordinateur du site, antennes, ce qui a coincé l'an dernier…")
        f = QtWidgets.QFormLayout()
        f.addRow("Nom du show :", self.name)
        f.addRow("Lieu / scène :", self.venue)
        f.addRow("Du :", self.d_from)
        f.addRow("Au :", self.d_to)
        # 7.57 (Clément : « demander où se situe le show pour déduire la bande ») : pays -> plan de fréquences du pays,
        # bande UHF des micros ajoutée si besoin, Vue posée dessus
        self.country_combo = None
        if country is not None:
            self.country_combo = QtWidgets.QComboBox()
            for code, nm in COUNTRIES:
                self.country_combo.addItem(nm, code)
            self.country_combo.setCurrentIndex(max(0, self.country_combo.findData(country)))
            self.country_combo.setToolTip("Le pays où a lieu le show : l'appli prend son plan de fréquences (télé,\n"
                                          "bandes autorisées) et balaye directement la bande UHF des micros.")
            f.addRow("Pays du show :", self.country_combo)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(f)
        lay.addWidget(QtWidgets.QLabel("Notes :"))
        lay.addWidget(self.notes, 1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        a, b = self.d_from.date(), self.d_to.date()
        if b < a:
            b = a
        return dict(name=self.name.text().strip(), venue=self.venue.text().strip(),
                    date_from=a.toString("yyyy-MM-dd"), date_to=b.toString("yyyy-MM-dd"),
                    notes=self.notes.toPlainText().strip())

    def country(self):
        return self.country_combo.currentData() if self.country_combo is not None else None


class UserProfilesDialog(QtWidgets.QDialog):
    """👤 Profils utilisateur (7.57) : les préférences de chacun (affichage, couleurs, mots, seuils, alarmes, son,
    préréglages perso) dans un fichier .tsauser, à charger d'un clic ou à passer à un collègue."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Profils utilisateur")
        lay = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QLabel(
            "Un profil garde TES préférences : affichage (thème, niveau, unité, colonnes), mots et couleurs, seuils, "
            "alarmes et son (sauf la sortie audio), préréglages perso, disposition des fenêtres. Il ne touche jamais au show (fréquences, scènes, "
            "bandes, tinySA) : charge ton profil sur n'importe quel PC, ou passe-le à un collègue.")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.lst = QtWidgets.QListWidget()
        self.lst.setToolTip("Les profils du dossier Documents › RF Technical Monitor › Profils. ✓ = le profil chargé.")
        self.lst.itemDoubleClicked.connect(lambda *_: self.load())
        lay.addWidget(self.lst, 1)
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QtWidgets.QHBoxLayout()
        b_load = QtWidgets.QPushButton("Charger ce profil")
        b_load.setToolTip("Applique les préférences de ce profil (le show en cours ne bouge pas).")
        b_load.clicked.connect(lambda *_: self.load())
        b_save = QtWidgets.QPushButton("💾 Enregistrer mes préférences…")
        b_save.setToolTip("Crée ou met à jour un profil avec tes préférences actuelles.")
        b_save.clicked.connect(lambda *_: self.save())
        b_imp = QtWidgets.QPushButton("📥 Importer…")
        b_imp.setToolTip("Ajoute un profil reçu (fichier .tsauser) à la liste et le charge.")
        b_imp.clicked.connect(lambda *_: self.import_file())
        b_exp = QtWidgets.QPushButton("📤 Exporter…")
        b_exp.setToolTip("Enregistre le profil choisi ailleurs (clé USB, mail…) pour le passer à quelqu'un.")
        b_exp.clicked.connect(lambda *_: self.export_file())
        b_del = QtWidgets.QPushButton("Supprimer")
        b_del.setToolTip("Supprime le fichier du profil choisi (tes préférences actuelles ne bougent pas).")
        b_del.clicked.connect(lambda *_: self.delete())
        b_dir = QtWidgets.QPushButton("📂 Dossier")
        b_dir.setToolTip("Ouvre le dossier des profils.")
        b_dir.clicked.connect(lambda *_: self.open_dir())
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.setToolTip("Ferme cette fenêtre.")
        b_close.clicked.connect(lambda *_: self.close())
        for b in (b_load, b_save, b_imp, b_exp, b_del, b_dir):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.lst.currentRowChanged.connect(lambda *_: self.show_info())
        fit_dialog(self, 820, 420)
        self.refresh()

    def refresh(self, select=None):
        self.lst.blockSignals(True)
        self.lst.clear()
        try:
            files = sorted(USER_DIR.glob("*.tsauser"), key=lambda p_: p_.stem.lower())
        except OSError:
            files = []
        cur = getattr(self.owner, "user_name", "")
        for p_ in files:
            try:
                doc = read_user(p_.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — fichier abîmé : listé quand même
                doc = dict(name=p_.stem, prefs={})
            it = QtWidgets.QListWidgetItem(doc["name"] + ("  ✓" if doc["name"] == cur else ""))
            it.setData(Qt.ItemDataRole.UserRole, str(p_))
            self.lst.addItem(it)
            if select and str(p_) == str(select):
                self.lst.setCurrentItem(it)
        if self.lst.currentRow() < 0 and self.lst.count():
            self.lst.setCurrentRow(0)
        self.lst.blockSignals(False)
        self.show_info()

    def path(self):
        it = self.lst.currentItem()
        return Path(it.data(Qt.ItemDataRole.UserRole)) if it is not None else None

    def show_info(self):
        p_ = self.path()
        if p_ is None:
            self.info.setText("Aucun profil pour l'instant : « 💾 Enregistrer mes préférences » crée le tien.")
            return
        try:
            doc = read_user(p_.read_text(encoding="utf-8"))
            pr = doc["prefs"]
            th = "thème perso" if isinstance(pr.get("theme"), dict) else "—"
            self.info.setText(f"{len(pr)} préférence(s) · {th} · {len(user_presets_norm(pr.get('user_presets')))} "
                              f"préréglage(s) perso · {p_.name}")
        except Exception as e:  # noqa: BLE001
            self.info.setText(f"⚠ {p_.name} : {e}")

    def load(self):
        p_ = self.path()
        if p_ is not None:
            self.owner.user_profile_load(p_)
            self.refresh(p_)

    def save(self):
        o = self.owner
        name, ok = QtWidgets.QInputDialog.getText(self, "Profil utilisateur", "Nom du profil (ton prénom, ton poste…) :",
                                                  text=getattr(o, "user_name", "") or "")
        name = " ".join(str(name or "").split())[:60]
        if ok and name:
            p_ = o.user_profile_save(name)
            if p_ is not None:
                self.refresh(p_)

    def import_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Importer un profil", "",
                                                        "Profils RF Technical Monitor (*.tsauser);;Tous les fichiers (*)")
        if not path:
            return
        try:
            doc = read_user(Path(path).read_text(encoding="utf-8"))
            USER_DIR.mkdir(parents=True, exist_ok=True)
            dst = USER_DIR / user_filename(doc["name"])
            if Path(path).resolve() != dst.resolve():
                dst.write_text(Path(path).read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Profil illisible :\n{e}")
            return
        self.owner.user_profile_load(dst)
        self.refresh(dst)

    def export_file(self):
        p_ = self.path()
        if p_ is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter le profil", p_.name,
                                                        "Profils RF Technical Monitor (*.tsauser)")
        if path:
            try:
                Path(path).write_text(p_.read_text(encoding="utf-8"), encoding="utf-8")
                self.owner.set_status(f"📤 Profil exporté : {path}")
            except OSError as e:
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")

    def delete(self):
        p_ = self.path()
        if p_ is None:
            return
        r = QtWidgets.QMessageBox.question(self, APP_NAME, f"Supprimer le fichier du profil « {p_.stem} » ?")
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                p_.unlink()
            except OSError:
                pass
            self.refresh()

    def open_dir(self):
        try:
            USER_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(USER_DIR)))


class ShowOpenDialog(QtWidgets.QDialog):
    """Liste des shows enregistrés (et des anciens profils) : nom, lieu, dates, nb de fréquences."""

    def __init__(self, parent, folders):
        super().__init__(parent)
        self.setWindowTitle("Ouvrir un show")
        self.resize(820, 460)
        self.path = ""
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Show", "Lieu", "Dates", "Fréquences", "Référence", "Fichier"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda *_: self.accept_sel())
        self.notes = QtWidgets.QLabel("")
        self.notes.setWordWrap(True)
        self.table.itemSelectionChanged.connect(self.on_sel)
        self.rows = []
        for folder, pat in folders:
            try:
                files = sorted(Path(folder).glob(pat))
            except OSError:
                files = []
            for fp in files:
                try:
                    doc = read_show(fp.read_text(encoding="utf-8"), fp.stem)
                except Exception:  # noqa: BLE001
                    continue
                self.rows.append((fp, doc, fp.stat().st_mtime))
        self.rows.sort(key=lambda r: (r[1]["meta"]["date_from"] or "", r[2]), reverse=True)
        self.table.setRowCount(len(self.rows))
        for i, (fp, doc, _mt) in enumerate(self.rows):
            sm = show_summary(doc)
            fr = f"{sm['n_freq']}" + (f" (dont {sm['n_blocks']} bloc(s))" if sm["n_blocks"] else "")
            for c, v in enumerate((sm["name"], sm["venue"], sm["dates"], fr, "✔" if sm["has_ref"] else "—",
                                   fp.name + ("  (ancien profil)" if fp.suffix == ".json" else ""))):
                self.table.setItem(i, c, QtWidgets.QTableWidgetItem(v))
        empty = QtWidgets.QLabel("Aucun show enregistré pour l'instant : 🎪 Shows › Enregistrer le show."
                                 if not self.rows else "")
        b_browse = QtWidgets.QPushButton("Parcourir…")
        b_browse.clicked.connect(lambda *_: self.browse())
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Open |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.button(QtWidgets.QDialogButtonBox.StandardButton.Open).setText("Ouvrir")
        bb.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        bb.accepted.connect(self.accept_sel)
        bb.rejected.connect(self.reject)
        bb.addButton(b_browse, QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.table, 1)
        lay.addWidget(empty)
        lay.addWidget(self.notes)
        lay.addWidget(bb)
        if self.rows:
            self.table.selectRow(0)

    def on_sel(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.rows):
            n = self.rows[r][1]["meta"]["notes"]
            self.notes.setText(f"Notes : {n}" if n else "")

    def accept_sel(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.rows):
            self.path = str(self.rows[r][0])
            self.accept()

    def browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Ouvrir un show", str(SHOW_DIR),
                                                        f"Show (*{SHOW_EXT});;Ancien profil (*.json);;Tous (*)")
        if path:
            self.path = path
            self.accept()


class WallWindow(QtWidgets.QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setWindowTitle(f"{APP_NAME} – Mur de fréquences")
        self.resize(1100, 680)
        self.tiles, self._sig, self._vis, self._fs = [], [], None, 0
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        top = FlowLayout()          # se replie : le panneau peut devenir étroit (avant : 929 px minimum)
        self.only_chk = QtWidgets.QCheckBox("Occupées / faibles")
        self.only_chk.toggled.connect(self.relayout)
        self.sum_lbl = QtWidgets.QLabel("")
        self.pick_btn = QtWidgets.QPushButton("📋 Choisir…")
        self.pick_btn.setToolTip("Choisis les fréquences qui ont une tuile sur le mur (case à cocher, par scène › groupe).\n"
                                 "Aussi : clic droit sur une tuile, ou dans la liste des fréquences.")
        self.pick_btn.clicked.connect(lambda *_: self.owner.pick_wall())
        self.alarm_chk = QtWidgets.QCheckBox("Alarmes toujours visibles")
        self.alarm_chk.setChecked(True)
        self.alarm_chk.setToolTip("Une fréquence retirée du mur y revient tant qu'elle est en alarme\n"
                                  "(ABSENT, CONFLIT, INTERMOD).")
        self.alarm_chk.toggled.connect(self.relayout)
        self.full_btn = QtWidgets.QPushButton("⛶ Plein écran")
        self.full_btn.clicked.connect(self.toggle_full)
        self.float_btn = QtWidgets.QPushButton("🗗 Détacher")
        self.float_btn.setToolTip("Détache le mur dans sa propre petite fenêtre : tu la poses où tu veux (2ᵉ écran,\n"
                                  "coin de l'écran) et tu choisis sa taille à la souris, les tuiles suivent.\n"
                                  "« Raccrocher » le remet en onglet à côté du spectre.")
        self.float_btn.clicked.connect(lambda *_: self.owner.wall_detach(not self.owner.dock_wall.isFloating()))
        self.screen_btn = QtWidgets.QPushButton("🖥 Autre écran")
        self.screen_btn.setToolTip("Envoie le mur dans une fenêtre sur l'autre écran (2ᵉ écran branché).\n"
                                   "F11 ensuite : plein écran sur cet écran-là.")
        self.screen_btn.clicked.connect(lambda *_: self.owner.wall_window_other_screen())
        try:
            n_scr = len(QtGui.QGuiApplication.screens())
        except TypeError:                     # (faux Qt des tests)
            n_scr = 1
        self.screen_btn.setVisible(n_scr > 1)
        self.size_combo = QtWidgets.QComboBox()
        for k, t in WALL_SIZES:
            self.size_combo.addItem(t, k)
        self.size_combo.setToolTip("Taille des tuiles. Auto : elles remplissent le panneau.\n"
                                   "Petites / Moyennes / Grandes : taille fixe, on fait défiler s'il y en a trop\n"
                                   "(pratique pour un mur rangé dans un petit panneau).")
        self.size_combo.currentIndexChanged.connect(lambda *_: self.relayout())
        for wd in (self.only_chk, self.alarm_chk, self.pick_btn, self.size_combo, self.float_btn, self.screen_btn,
                   self.full_btn):
            top.addWidget(wd)
        lay.addLayout(top)
        self.sum_lbl.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        lay.addWidget(self.sum_lbl)
        self.host = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.host)
        self.scroll.setMinimumSize(120, 60)
        self.scroll.viewport().installEventFilter(self)     # la barre qui se replie change la place des tuiles
        lay.addWidget(self.scroll, 1)
        for key, fn in (("F11", self.toggle_full), ("Escape", self.leave_full)):
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)    # seulement quand le mur a le focus
            sc.activated.connect(fn)
        self.only_chk.setToolTip("N'affiche que les fréquences occupées ou faibles : les tuiles grossissent.")
        self.full_btn.setToolTip("Le mur se détache et passe en plein écran (F11 ; Échap pour revenir).")
        self.sum_lbl.setToolTip("Résumé : couche affichée, nombre de fréquences, occupées, faibles.")
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.relayout)

    def tile_menu(self, k, pos):
        if k >= len(self.owner.watch):
            return
        m = QtWidgets.QMenu(self)
        w = self.owner.watch[k]
        a_rep = m.addAction("🆘 Remplacer ce micro…")
        a_mute = m.addAction("🔔 Rallumer" if w.get("muted") else "💤 Éteint (je sais)")
        a_hide = m.addAction(f"Retirer « {w['name']} » du mur")
        a_pick = m.addAction("📋 Choisir les fréquences du mur…")
        xa = self.owner.add_freq_actions(m, w["freq"], w)
        act = m.exec(self.tiles[k].mapToGlobal(pos))
        if self.owner.run_freq_action(xa, act, w["freq"], w):
            return
        if act is a_rep:
            self.owner.open_replace(w)
        elif act is a_mute:
            self.owner.set_muted([w], not w.get("muted"))
        elif act is a_hide:
            self.owner.set_wall_rows([k], False)
        elif act is a_pick:
            self.owner.pick_wall()

    def toggle_full(self):
        self.owner.wall_fullscreen(not self.owner.wall_is_fullscreen())

    def leave_full(self):
        if self.owner.wall_is_fullscreen():
            self.owner.wall_fullscreen(False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def eventFilter(self, obj, e):
        if e.type() == QtCore.QEvent.Type.Resize and obj is self.scroll.viewport():
            self._timer.start()
        return super().eventFilter(obj, e)

    def showEvent(self, e):
        super().showEvent(e)
        self.rebuild()

    def rebuild(self):
        for t in self.tiles:
            self.grid.removeWidget(t)
            t.deleteLater()
        self.tiles = []
        for _ in self.owner.watch:
            lb = QtWidgets.QLabel("")
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setWordWrap(True)
            lb.setTextFormat(Qt.TextFormat.RichText)
            lb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
            lb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lb.customContextMenuRequested.connect(lambda pos, k=len(self.tiles): self.tile_menu(k, pos))
            self.tiles.append(lb)
        self._sig = [None] * len(self.tiles)
        self._vis = None
        self.relayout()
        self.refresh()

    def _visible_idx(self):
        ow = self.owner
        ws = ow.watch
        return [i for i, w in enumerate(ws)
                if wall_visible(w, ow.in_scope(w), ow.in_alarm(w), self.only_chk.isChecked(), self.alarm_chk.isChecked())]

    def relayout(self, *_):
        if len(self.tiles) != len(self.owner.watch):
            self.rebuild()
            return
        vis = self._visible_idx()
        self._vis = tuple(vis)
        for t in self.tiles:
            self.grid.removeWidget(t)
            t.setVisible(False)
        n = len(vis)
        size = self.size_combo.currentData() or "auto"
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if size in WALL_TILE
                                               else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vp = self.scroll.viewport()
        W, H = vp.width(), vp.height()
        cols, rows, tile_h, fs = wall_grid(n, W, H, size)
        for k in range(self.grid.columnCount() + 1):
            self.grid.setColumnStretch(k, 0)
        for k in range(self.grid.rowCount() + 2):
            self.grid.setRowStretch(k, 0)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)
        for r in range(rows):
            self.grid.setRowStretch(r, 0 if tile_h else 1)
        if tile_h:
            self.grid.setRowStretch(rows, 1)            # tuiles fixes : calées en haut
        for k, i in enumerate(vis):
            t = self.tiles[i]
            if tile_h:
                t.setFixedHeight(tile_h)
            else:
                t.setMinimumHeight(0)
                t.setMaximumHeight(16777215)
            self.grid.addWidget(t, k // cols, k % cols)
            t.setVisible(True)
        if tile_h:
            self.host.setMaximumHeight(16777215)
            self.host.setMinimumHeight(rows * (tile_h + 6))
        else:       # auto : calé sur la partie visible (le texte replié des tuiles réclamerait plus de hauteur)
            self.host.setMinimumHeight(0)
            self.host.setMaximumHeight(max(1, H))
        if fs != self._fs:
            self._fs = fs
            self._sig = [None] * len(self.tiles)
        self.refresh()

    def refresh(self):
        if not self.isVisible():
            return
        ow = self.owner
        if len(self.tiles) != len(ow.watch):
            self.rebuild()
            return
        if self._vis != tuple(self._visible_idx()):
            self.relayout()
            return
        th, base, fs = ow.theme, ow.theme["ui_base"], self._fs
        n_occ = n_weak = n_tot = 0
        one_group = bool(ow.scope and len(ow.scope) == 1 and ow.scope[0][1])
        for i, w in enumerate(ow.watch):
            if not ow.in_scope(w):
                continue
            n_tot += 1
            st = w["state"]
            n_occ += st == "occ"
            n_weak += st == "weak"
            conf = st == "occ" and ow.is_keep_free(w["status"])
            absn = bool(w.get("absent"))
            lv = ow.lvl(w["level"], suffix=True)
            pct = w["occw"].pct()
            layer = "" if one_group else ow.layer_text(w)
            sig = (st, conf, absn, lv, w["name"], w["status"], round(w["freq"], 3), fs, layer,
                   None if pct is None else int(pct), th["ui_base"], th["st_occ"], th["st_free"], th["st_weak"])
            if self._sig[i] == sig:
                continue
            self._sig[i] = sig
            sig_txt, tone, tone_col = ow.sig_view(w)
            bg = {"bad": blend(tone_col, base, 0.85), "warn": blend(tone_col, base, 0.6),
                  "ok": blend(tone_col, base, 0.45), "free": blend(tone_col, base, 0.45)}.get(tone, blend(th["st_none"], base, 0.25))
            fg = contrast_text(bg)
            bd = ow.status_color(w["status"]) if w["status"] else bg
            name = ("⚠ " if (conf or absn) else "") + (w["name"] or "—")
            occ = "" if pct is None else f" · occ. {pct:.0f} %"
            html = (f"<div style='font-size:{fs}px;font-weight:bold'>{_html_esc(name)}</div>"
                    f"<div style='font-size:{max(8, int(fs * 0.72))}px'>{w['freq']:.3f} MHz</div>"
                    f"<div style='font-size:{int(fs * 0.95)}px'>{_html_esc(sig_txt)} · {lv}{occ}</div>")
            if layer:
                html += f"<div style='font-size:{max(8, int(fs * 0.6))}px'>{_html_esc(layer)}</div>"
            self.tiles[i].setText(html)
            self.tiles[i].setStyleSheet(
                "QLabel{background:%s;color:%s;border:4px solid %s;border-radius:8px;}" % (bg, fg, bd))
        n_hid = sum(1 for w in ow.watch if ow.in_scope(w) and w.get("hide_wall"))
        self.sum_lbl.setText(f"  {ow.scope_text()} · {n_tot} fréquences · {n_occ} occupée(s) · {n_weak} faible(s)"
                             + (f" · {n_hid} retirée(s) du mur" if n_hid else ""))
