# Spectre, repères, marqueurs, seuils, thème, bandeaux, référence, noms. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenSpectre:
    """Spectre, repères, marqueurs, seuils, thème, bandeaux, référence, noms. (méthodes de MainWindow, regroupées par thème.)"""

    # ------------------------------------------------------------- graphes
    def _series(self, k):
        """Courbe à afficher : le balayage en cours posé sur l'ancien (comme un vrai analyseur)."""
        part, old = self.partial_data.get(k), self.latest.get(k)
        if part is None:
            return old
        if old is None or len(part[0]) == 0:
            return part
        keep = old[0] > part[0][-1]
        return np.concatenate([part[0], old[0][keep]]), np.concatenate([part[1], old[1][keep]])

    def _fit_range(self):
        if self.view_id == -1:
            bs = [b for b in self.scan_bands() if b["enabled"]]
        else:
            bs = [b for b in self.scan_bands() if b["id"] == self.view_id]
        if not bs:
            return None
        return min(b["start"] for b in bs), max(b["stop"] for b in bs)

    def set_coord(self, on):
        """Montre / cache les outils de coordination (parcours ③ ④, ☰ Plus, tutos, clic droit du journal)."""
        self.coord_on = bool(on)
        for k in COORD_STEPS:
            a_ = self.__dict__.get("_step_acts", {}).get(k)
            if a_ is not None:
                a_.setVisible(self.coord_on)
            a_ = self.__dict__.get("_step_arrows", {}).get(k)
            if a_ is not None:
                a_.setVisible(self.coord_on)
        for a_ in self.__dict__.get("_coord_acts", []):
            a_.setVisible(self.coord_on)
        h_ = self.__dict__.get("_coord_hint")
        if h_ is not None:                          # caché : une entrée dit où les réactiver (Clément : « où est la coord ? »)
            h_.setVisible(not self.coord_on)

    def set_smooth(self, on):
        """Courbes lissées (antialiasing) du spectre, de la rémanence et des scans gardés : plus joli, plus lourd."""
        self.smooth = bool(on)
        pg.setConfigOptions(antialias=self.smooth)
        items = [getattr(self, n_, None) for n_ in ("curve", "maxcurve", "refcurve")] + list(getattr(self, "_hist_items", []))
        try:                                       # (objets factices dans les tests : rien à faire)
            for it in items:
                if it is None:
                    continue
                it.opts["antialias"] = self.smooth
                it.curve.opts["antialias"] = self.smooth
                it.curve.update()
            sc = getattr(self, "sitecurve", None)
            if sc is not None:
                sc.opts["antialias"] = self.smooth
                sc.update()
        except (TypeError, AttributeError, KeyError):
            pass

    def update_plot(self, hist=True):
        try:
            self._update_plot(hist)
        finally:
            self.marker_refresh()

    def _update_plot(self, hist=True):
        nan = np.array([np.nan])
        sites = self.view_sites()
        if sites is not None and self._zoom is None:
            # 📍 scène choisie = un lieu : son direct à lui (tinySA posé là), sinon rien en direct (son spectre
            # gardé reste en pointillés, voir update_site_curve)
            xs, ys, mxs, mys = [], [], [], []
            now, stale = time.time(), max(15.0, 4 * self.last_cycle)
            for site in sites:
                for bid, (f, l, t) in sorted(self.site_live.get(site, {}).items(), key=lambda kv: float(kv[1][0][0])):
                    if now - t > stale or (self.view_id != -1 and bid != self.view_id):
                        continue
                    xs += [f, nan]
                    ys += [l, nan]
                    mh = self.site_mh.get(site, {}).get(bid)
                    mxs += [mh[0] if mh is not None else f, nan]
                    mys += [mh[1] if mh is not None and mh[1].shape == l.shape else l, nan]
            if xs:
                x, y = np.concatenate(xs), np.concatenate(ys)
                self._last_xy = (x, y)
                self.curve.setData(x, y)
                self.maxcurve.setData(np.concatenate(mxs), np.concatenate(mys)) if self.hold_chk.isChecked() \
                    else self.maxcurve.setData([], [])
            else:
                self.curve.setData([], [])
                self.maxcurve.setData([], [])
            self._update_history([])
            if self._fit_x:
                rng = self._fit_range()
                if rng:
                    span = rng[1] - rng[0]
                    self.spec.getPlotItem().setXRange(rng[0] - 0.01 * span, rng[1] + 0.01 * span, padding=0)
                self._fit_x = False
            self._update_markers()
            return
        if self.view_id == -1:
            live = {b["id"] for b in self.scan_bands() if b["enabled"]}
            keys = [k for k in set(self.latest) | set(self.partial_data) if k != ZOOM_ID and k in live]
            keys = [k for k in keys if self._series(k) is not None and len(self._series(k)[0])]
            keys.sort(key=lambda k: self._series(k)[0][0])
        else:
            keys = [self.view_id] if self._series(self.view_id) is not None else []
        if not keys:
            self._clear_plot()
            if self._fit_x and self._zoom is None:       # pas encore de mesure : l'axe montre déjà les bandes
                rng = self._fit_range()                    # (1er lancement : 470–694 MHz, pas 0–1 MHz — Clément)
                if rng:
                    span = rng[1] - rng[0]
                    self.spec.getPlotItem().setXRange(rng[0] - 0.01 * span, rng[1] + 0.01 * span, padding=0)
            return
        xs, ys, mxs, mys = [], [], [], []
        for k in keys:
            f, l = self._series(k)
            xs += [f, nan]
            ys += [l, nan]
            old, mh = self.latest.get(k), self.maxhold.get(k)
            if old is not None and mh is not None and mh.shape == old[1].shape:
                mxs += [old[0], nan]
                mys += [mh, nan]
            else:
                mxs += [f, nan]
                mys += [l, nan]
        x, y = np.concatenate(xs), np.concatenate(ys)
        mx, my = np.concatenate(mxs), np.concatenate(mys)
        self._last_xy = (x, y)
        self.curve.setData(x, y)
        if self.hold_chk.isChecked():
            self.maxcurve.setData(mx, my)
        else:
            self.maxcurve.setData([], [])
        if hist:
            self._update_history(keys)
        if self._fit_x and self._zoom is None:
            rng = self._fit_range()
            if rng:
                span = rng[1] - rng[0]
                self.spec.getPlotItem().setXRange(rng[0] - 0.01 * span, rng[1] + 0.01 * span, padding=0)
            self._fit_x = False
        elif self._zoom is not None:
            self._fit_x = False
        self._update_markers()

    def _clear_plot(self):
        self.curve.setData([], [])
        self.maxcurve.setData([], [])
        self._update_history([])
        self._update_markers()

    def _update_history(self, keys):
        """Rémanence (7.55, façon analyseur numérique) : les anciens balayages ne sont plus N courbes empilées mais UNE
        image de densité (density_raster) : ce qui revient souvent brille, un passage rare reste en trace fantôme.
        Une seule image à dessiner (au lieu de N chemins) : ≈ −10 % de processeur mesuré en démo."""
        n = self.persist_combo.currentData() or 0
        traces = []
        for i in range(n):
            xs, ys = [], []
            for k in keys:
                h = self.history.get(k)
                if k in self.latest and h and len(h) > i:
                    f, l = h[-1 - i]
                    xs += [np.asarray(f, dtype=float), np.array([np.nan])]
                    ys += [np.asarray(l, dtype=float), np.array([np.nan])]
            if xs:
                traces.append((np.concatenate(xs), np.concatenate(ys)))
        self._dens_traces = traces
        self._dens_n = n
        self._density_draw()

    def _density_item(self):
        img = getattr(self, "_dens_img", None)
        if img is None:
            img = pg.ImageItem()
            img.setZValue(-1)
            img.setLookupTable(density_lut(self.theme["curve"]))
            img.setLevels((0.0, 1.0))
            self.spec.getPlotItem().addItem(img, ignoreBounds=True)
            self._dens_img = img
            # vue déplacée / zoomée / fenêtre redimensionnée : image refaite (calcul ≈ 20 ms, regroupé)
            self._dens_timer = QtCore.QTimer(self)
            self._dens_timer.setSingleShot(True)
            self._dens_timer.setInterval(60)
            self._dens_timer.timeout.connect(self._density_draw)
            vb = self.spec.getPlotItem().vb
            vb.sigXRangeChanged.connect(lambda *a: self._dens_timer.start())
            vb.sigYRangeChanged.connect(lambda *a: self._dens_timer.start())
            vb.sigResized.connect(lambda *a: self._dens_timer.start())
        return img

    def _density_draw(self):
        traces = getattr(self, "_dens_traces", None)
        img = getattr(self, "_dens_img", None)
        if not traces:
            if img is not None:
                img.setVisible(False)
            return
        img = self._density_item()
        vb = self.spec.getPlotItem().vb
        (x0, x1), (y0, y1) = vb.viewRange()
        W = int(min(1800, max(64, vb.width())))
        H = int(min(700, max(48, vb.height())))
        n = max(1, getattr(self, "_dens_n", len(traces)))
        w = [1.0 - i / (n + 1.0) for i in range(len(traces))]
        try:
            arr = density_glow(density_raster(traces, x0, x1, y0, y1, W, H, w))
        except Exception:
            img.setVisible(False)
            return
        img.setImage(arr, autoLevels=False, levels=(0.0, 1.0))
        img.setRect(QtCore.QRectF(x0, y0, x1 - x0, y1 - y0))
        img.setVisible(True)

    def _clear_hist_pool(self):
        """Changement de thème : la rémanence prend la couleur de la nouvelle trace."""
        pi = self.spec.getPlotItem()
        for it in self._hist_items:
            pi.removeItem(it)
        self._hist_items = []
        img = getattr(self, "_dens_img", None)
        if img is not None:
            img.setLookupTable(density_lut(self.theme["curve"]))

    def _build_mk_menu(self):
        """Menu 📍 Repères, reconstruit à chaque ouverture (couches et statuts peuvent avoir changé)."""
        m = self.mk_menu
        m.clear()
        mk = self.mk

        def check(menu, txt, on, setter):
            a = menu.addAction(txt)
            a.setCheckable(True)
            a.setChecked(bool(on))
            # on lit l'état de la case : avec un paramètre optionnel, PySide6 appelle la fonction SANS l'argument
            # « checked » (il valait toujours False : impossible de recocher à la souris)
            a.triggered.connect(lambda *_, a=a: setter(a.isChecked()))
            return a

        def toggle_in(key, value):
            def f(on):
                lst = [x for x in mk[key] if x != value]
                if not on:
                    lst.append(value)
                self.set_markers(**{key: lst})
            return f

        def toggle_state(value):
            def f(on):
                lst = [x for x in mk["states"] if x != value] + ([value] if on else [])
                self.set_markers(states=lst)
            return f

        m.addAction("✔ Tout afficher (enlève les filtres)").triggered.connect(lambda *_: self.reset_markers())
        check(m, "Masquer tous les repères  (Ctrl+M)", not mk["on"], lambda on: self.set_markers(on=not on))
        m.addSection("Afficher selon l'état mesuré")
        for key, txt in MK_STATES:
            check(m, txt, key in mk["states"], toggle_state(key))
        check(m, "Toujours montrer les fréquences en alarme", mk["alarms"], lambda on: self.set_markers(alarms=on))
        sub_l = m.addMenu("Par scène › groupe")
        for sc in self.scenes:
            groups = [g["name"] for g in sc["groups"]] or [""]
            for g in groups:
                k = mk_layer_key(sc["name"], g)
                check(sub_l, f"{sc['name']} › {g}" if g else sc["name"], k not in mk["hide_layers"],
                      toggle_in("hide_layers", k))
        check(sub_l, "Sans scène", "" not in mk["hide_layers"], toggle_in("hide_layers", ""))
        sub_s = m.addMenu("Par statut")
        for st in [x["name"] for x in self.statuses] + [""]:
            check(sub_s, st or "(sans statut)", st not in mk["hide_status"], toggle_in("hide_status", st))
        n_hid = sum(1 for w in self.watch if w.get("hide_mk"))
        if n_hid:
            m.addAction(f"Réafficher les {n_hid} repère(s) masqué(s) à la main").triggered.connect(
                lambda *_: self.hide_marker_rows([i for i, w in enumerate(self.watch) if w.get("hide_mk")], False))
        m.addSection("Affichage")
        check(m, "Noms des fréquences", self.names_chk.isChecked(), self.names_chk.setChecked)
        check(m, "Signaux inconnus (pointillés)", mk["unk"] and self.unk_chk.isChecked(), self.set_unk_markers)
        m.addSection("Style")
        grp = QtGui.QActionGroup(m)
        for key, txt in self.MK_STYLE:
            grp.addAction(check(m, txt, mk["style"] == key, lambda on, k=key: on and self.set_markers(style=k)))
        m.addSection("Couleur")
        grp2 = QtGui.QActionGroup(m)
        for i in range(self.mark_combo.count()):
            key, txt = self.mark_combo.itemData(i), self.mark_combo.itemText(i).replace(TR("Repères : "), "")
            grp2.addAction(check(m, txt, self.mark_combo.currentData() == key,
                                 lambda on, k=key: on and self.mark_combo.setCurrentIndex(self.mark_combo.findData(k))))

    def _sync_mk_menu(self):
        if hasattr(self, "mk_btn"):
            self.mk_btn.setText("📍 Repères" + (" (masqués)" if not self.mk["on"] else
                                                 " (filtrés)" if mk_filtered(self.mk) else ""))

    def set_markers(self, **kw):
        for k, v in kw.items():
            if k in self.mk:
                self.mk[k] = v
        self._sync_mk_menu()
        self._update_markers()

    def set_unk_markers(self, on):
        """Repères des signaux inconnus ; les afficher demande aussi la détection (Réglages › Détection)."""
        if on and not self.unk_chk.isChecked():
            self.unk_chk.setChecked(True)
            self.set_status("Détection des signaux inconnus activée (Réglages › Détection) : leurs repères "
                            "apparaissent au prochain balayage.")
        self.set_markers(unk=on)

    def reset_markers(self):
        style, unk = self.mk["style"], self.mk["unk"]
        self.mk = dict(mk_default(), style=style, unk=unk)
        for w in self.watch:
            w.pop("hide_mk", None)
        self.set_markers()

    def toggle_markers(self):
        """Ctrl+M : tout masquer / réafficher (les filtres choisis sont gardés)."""
        self.set_markers(on=not self.mk["on"])
        self.set_status("Repères masqués (Ctrl+M pour les réafficher)." if not self.mk["on"] else "Repères affichés.")

    def hide_marker_rows(self, rows, hide=True):
        for r in rows:
            if 0 <= r < len(self.watch):
                if hide:
                    self.watch[r]["hide_mk"] = True
                else:
                    self.watch[r].pop("hide_mk", None)
        self.set_markers()

    def _marker_item(self, key):
        it = self._mk_items.get(key)
        if it is None:
            c_ = QtGui.QColor(key[0])
            c_.setAlphaF(0.72)                   # 7.54 : repères plus fins et un peu transparents (moins de « barreaux »)
            pen = pg.mkPen(c_, width=1.5, style=Qt.PenStyle.DotLine if key[1] else Qt.PenStyle.SolidLine)
            it = pg.PlotCurveItem(pen=pen, connect="pairs")
            self.spec.getPlotItem().addItem(it)
            self._mk_items[key] = it
        return it

    def _clear_marker_pool(self):
        pi = self.spec.getPlotItem()
        for it in self._mk_items.values():
            pi.removeItem(it)
        self._mk_items = {}

    def _update_markers(self):
        vb = self.spec.getPlotItem().vb
        (x0, x1), (y0, y1) = vb.viewRange()
        vis = [w for w in self.watch if x0 <= w["freq"] + (w.get("bw") or 0) / 2 and
               w["freq"] - (w.get("bw") or 0) / 2 <= x1 and self.in_scope(w)]
        unk = [f for lst in self.unk_now.values() for f in lst if x0 <= f <= x1]
        mk = self.mk
        vis = [w for w in vis if marker_visible(
            w, mk, alarm=bool(w.get("absent")) or (w["state"] == "occ" and self.is_keep_free(w["status"])))]
        if not mk["on"] or not mk["unk"]:
            unk = []
        ys = [-130.0, 0.0] if self.mk["style"] == "full" else [y1 - (y1 - y0) * 0.07, y1]
        mode = self.mark_combo.currentData()
        groups, colors = {}, []
        for w in vis:
            col = None
            if mode == "status" and w["status"]:
                col = self.status_color(w["status"])
            elif mode == "group":
                col = self.group_color(w["scene"], w["group"])
            if col is None:
                col = self.sig_view(w)[2] if w["state"] is not None else self.theme["st_none"]
            seg = groups.setdefault((col, False), ([], []))
            bw = w.get("bw") or 0.0
            if bw:                         # bloc : bord gauche, bord droit, barre en haut
                a, b = w["freq"] - bw / 2, w["freq"] + bw / 2
                ybar = min(ys[1], y1 - (y1 - y0) * 0.015)
                seg[0].extend([a, a, b, b, a, b])
                seg[1].extend([ys[0], ys[1], ys[0], ys[1], ybar, ybar])
            else:
                seg[0].extend([w["freq"], w["freq"]])
                seg[1].extend(ys)
            colors.append(col)
        for f in unk:
            seg = groups.setdefault((self.theme["st_unk"], True), ([], []))
            seg[0].extend([f, f])
            seg[1].extend(ys)
        for key, (xs_, ys_) in groups.items():
            self._marker_item(key).setData(np.array(xs_), np.array(ys_))
        for key, it in self._mk_items.items():
            if key not in groups:
                it.setData(np.array([]), np.array([]))

        show = self.names_chk.isChecked() and 0 < len(vis) <= MAX_LABELS
        pi = self.spec.getPlotItem()
        while len(self.labels) < MAX_LABELS:
            lab = pg.TextItem("", anchor=(0.5, 0))
            pi.addItem(lab, ignoreBounds=True)
            lab.setVisible(False)
            self.labels.append(lab)
        for i, lab in enumerate(self.labels):
            if show and i < len(vis):
                lab.setText(vis[i]["name"], color=colors[i])
                dy = (y1 - y0) * (0.08 if self.mk["style"] == "top" else 0.0)
                lab.setPos(vis[i]["freq"], y1 - 2.0 - dy - (i % 3) * 5.5)
                lab.setVisible(True)
            else:
                lab.setVisible(False)
        self._update_selection()
        self._place_site_lbl()

    def _on_watch_sel(self):
        self._update_selection()
        rows = self._sel_rows()
        if len(rows) == 1 and self._last_xy is not None:
            w = self.watch[rows[0]]
            (x0, x1), _ = self.spec.getPlotItem().vb.viewRange()
            if not x0 <= w["freq"] <= x1:
                self.set_status(f"« {w['name']} » ({w['freq']:.3f} MHz) est hors de la vue du spectre : "
                                f"double-clic sur son niveau pour zoomer dessus.")

    def _update_selection(self):
        """Fréquence(s) choisie(s) dans la liste : ressortent sur le spectre (bande ambrée, trait épais, nom)."""
        pi = self.spec.getPlotItem()
        if self._sel_items is None:
            c = QtGui.QColor(SEL_COLOR)
            c.setAlpha(80)
            regs = []
            for _i in range(SEL_MAX):
                r = pg.LinearRegionItem(values=(0, 0), movable=False, brush=pg.mkBrush(c),
                                        pen=pg.mkPen(SEL_COLOR, width=1))
                r.setZValue(-5)
                r.setVisible(False)
                pi.addItem(r, ignoreBounds=True)
                regs.append(r)
            line = pg.PlotCurveItem(pen=pg.mkPen(SEL_COLOR, width=3.5), connect="pairs")
            line.setZValue(40)
            pi.addItem(line, ignoreBounds=True)
            lab = pg.TextItem("", color=SEL_COLOR, anchor=(0.5, 1), fill=pg.mkBrush(0, 0, 0, 170),
                              border=pg.mkPen(SEL_COLOR))
            lab.setZValue(50)
            lab.setVisible(False)
            pi.addItem(lab, ignoreBounds=True)
            self._sel_items = (regs, line, lab)
        regs, line, lab = self._sel_items
        rows = self._sel_rows()[:SEL_MAX]
        (x0, x1), (y0, y1) = pi.vb.viewRange()
        xs, ys = [], []
        for i, r in enumerate(regs):
            if i < len(rows):
                w = self.watch[rows[i]]
                half = max((w.get("bw") or 0.0) / 2, (x1 - x0) * 0.006)
                r.setRegion((w["freq"] - half, w["freq"] + half))
                r.setVisible(True)
                if not w.get("bw"):
                    xs += [w["freq"], w["freq"]]
                    ys += [y0, y1]
            else:
                r.setVisible(False)
        line.setData(np.array(xs, dtype=float), np.array(ys, dtype=float))
        if len(rows) == 1:
            w = self.watch[rows[0]]
            lvl = "" if w.get("level") is None else "  " + self.lvl(w["level"], suffix=True)
            lab.setText(f"{w['name']}  {w['freq']:.3f}" + lvl)
            rel = (w["freq"] - x0) / max(1e-9, x1 - x0)          # près d'un bord : texte du côté intérieur
            lab.setAnchor((0.0, 1) if rel < 0.2 else (1.0, 1) if rel > 0.8 else (0.5, 1))
            lab.setPos(w["freq"], y0 + (y1 - y0) * 0.16)
            lab.setVisible(True)
        else:
            lab.setVisible(False)

    def update_waterfall(self, bid, f, l):
        lr = decimate_max(l, WF_MAX_COLS)
        if self.wf_hist is None or self.wf_id != bid or self.wf_hist.shape[0] != len(lr):
            self.wf_hist = np.full((len(lr), WF_ROWS), np.nan, dtype=np.float32)   # 8.1 : vide = transparent
            self.wf_id = bid
        self.wf_hist = np.roll(self.wf_hist, 1, axis=1)
        self.wf_hist[:, 0] = lr
        self.wf_img.setImage(self.wf_hist, autoLevels=False, levels=(-115, -40))
        self.wf_img.setRect(QtCore.QRectF(float(f[0]), 0.0, float(f[-1] - f[0]), float(WF_ROWS)))
        self.wf.getPlotItem().setYRange(0, WF_ROWS, padding=0)

    def on_mouse(self, evt):
        pos = evt[0]
        if not self.spec.sceneBoundingRect().contains(pos):
            return
        xm = self.spec.getPlotItem().vb.mapSceneToView(pos).x()
        self._show_band_info(float(xm))
        if self._last_xy is None:
            return
        x, y = self._last_xy
        try:
            k = int(np.nanargmin(np.abs(x - xm)))
        except ValueError:
            return
        self.readout.setText(f"{x[k]:.3f} MHz   {self.lvl(float(y[k]), suffix=True)}")
        self.readout.setToolTip(TR("Sur 50 Ω : {}").format(rf_linear_text(float(y[k]))))   # 8.1 : µV, pW…

    def capture(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Capture du spectre", f"spectre_{datetime.now():%Y%m%d_%H%M%S}.png", "PNG (*.png)")
        if path:
            ex = pg.exporters.ImageExporter(self.spec.getPlotItem())
            ex.parameters()["width"] = 1800
            ex.export(path)
            self.set_status(f"Capture enregistrée : {path}")

    # ----------------------------------------------------------- seuils
    def _thr_from_spin(self, v):
        if abs(self.thr_line.value() - v) > 1e-6:
            self.thr_line.setValue(v)

    def _thr_from_line(self):
        v = round(self.thr_line.value(), 1)
        if abs(self.thr_spin.value() - v) > 1e-6:
            self.thr_spin.setValue(max(-130, min(0, v)))

    def _weak_from_spin(self, v):
        if abs(self.weak_line.value() - v) > 1e-6:
            self.weak_line.setValue(v)

    def _weak_from_line(self):
        v = round(self.weak_line.value(), 1)
        if abs(self.weak_spin.value() - v) > 1e-6:
            self.weak_spin.setValue(max(-130, min(0, v)))

    def _weak_toggled(self, on):
        self.weak_spin.setEnabled(on)
        self.auto_weak_spin.setEnabled(on)
        self.weak_line.setVisible(on and not self.thr_auto)

    def auto_threshold(self):
        """Ancien bouton « Auto » (une seule fois) : allume maintenant les seuils automatiques."""
        self.thr_auto_btn.setChecked(True)

    def auto_margins(self):
        return float(self.auto_occ_spin.value()), float(self.auto_weak_spin.value())

    def set_thr_auto(self, on):
        """Seuils automatiques : bruit de fond appris + marges, fréquence par fréquence."""
        on = bool(on)
        self.thr_auto = on
        if self.thr_auto_btn.isChecked() != on:
            self.thr_auto_btn.setChecked(on)
        for w_ in (self.thr_spin, self.weak_spin):
            w_.setVisible(not on)
        for w_ in (self.auto_occ_spin, self.auto_weak_spin):
            w_.setVisible(on)
        self.thr_line.setVisible(not on)
        self.weak_line.setVisible(not on and self.weak_chk.isChecked())
        if not on:
            self.auto_curve.setVisible(False)
        self._auto_curve_draw()
        self.reeval()

    def _auto_margins_changed(self):
        self._auto_curve_draw()
        self.reeval()

    def show_auto_thr_help(self):
        """❓ Fiche « Comment marche le seuil auto ? » (non bloquante)."""
        d = getattr(self, "_auto_help", None)
        if d is None:
            d = QtWidgets.QDialog(self)
            d.setWindowTitle("Comment marche le seuil auto ?")
            lay = QtWidgets.QVBoxLayout(d)
            lb = QtWidgets.QLabel(auto_thr_help_html(TR))
            lb.setWordWrap(True)
            lb.setTextFormat(Qt.TextFormat.RichText)
            sc = QtWidgets.QScrollArea()
            sc.setWidgetResizable(True)
            sc.setWidget(lb)
            lay.addWidget(sc, 1)
            row = QtWidgets.QHBoxLayout()
            man = QtWidgets.QPushButton("❓ Manuel")
            man.setToolTip("Le chapitre du manuel sur les seuils.")
            man.clicked.connect(lambda *_: self.open_manual("seuils"))
            tnt = QtWidgets.QPushButton("📺 Canaux TNT…")
            tnt.setToolTip("Les canaux pris par la TNT, comparés au vrai bruit du lieu.")
            tnt.clicked.connect(lambda *_: self.open_tnt())
            ok_ = QtWidgets.QPushButton("Fermer")
            ok_.setToolTip("Ferme la fiche.")
            ok_.clicked.connect(lambda *_: d.close())
            row.addWidget(man)
            row.addWidget(tnt)
            row.addStretch(1)
            row.addWidget(ok_)
            lay.addLayout(row)
            fit_dialog(d, 620, 560)
            self._auto_help = d
        d.show()
        d.raise_()
        return d

    def _auto_curve_update(self, now=None):
        """Bruit de fond le long du spectre (courbe en tirets) + valeurs « typiques » des seuils globaux (utilisées par
        les outils : coordination, scans…)."""
        if not self.thr_auto or not self.latest:
            return
        now = time.time() if now is None else now
        F = np.concatenate([v[0] for v in self.latest.values()])
        L = np.concatenate([v[1] for v in self.latest.values()])
        Fc, Lc = floor_curve(F, L)
        if Fc is None:
            return
        prev = self._acurve
        if prev is not None and len(prev[0]) == len(Fc) and np.allclose(prev[0], Fc):
            Lc = floor_track(prev[1], Lc, now - prev[2])
        self._acurve = (Fc, Lc, now)
        fin = Lc[np.isfinite(Lc)]
        if len(fin):
            m_occ, m_weak = self.auto_margins()
            med = float(np.median(fin))
            self.thr_spin.setValue(max(-130, min(0, round(med + m_occ))))
            self.weak_spin.setValue(max(-130, min(0, round(med + m_weak))))
        self._auto_curve_draw()

    def _auto_curve_draw(self):
        on = self.thr_auto and self._acurve is not None
        self.auto_curve.setVisible(bool(on))
        if on:
            Fc, Lc, _ = self._acurve
            self.auto_curve.setData(Fc, Lc + self.auto_margins()[0])     # en dBm : l'axe gauche convertit

    def auto_thr_at(self, f):
        """Seuil « occupé » automatique à f (MHz) d'après la courbe de bruit, ou None."""
        if not self.thr_auto or self._acurve is None:
            return None
        Fc, Lc, _ = self._acurve
        if f < Fc[0] - 1.0 or f > Fc[-1] + 1.0:
            return None
        ok = np.isfinite(Lc)
        if not ok.any():
            return None
        return float(np.interp(f, Fc[ok], Lc[ok])) + self.auto_margins()[0]

    # ------------------------------------------------------- marqueurs M1 / M2
    def _build_markers_bar(self):
        bar = QtWidgets.QWidget()
        self.mkr_bar = bar
        self.mkr_spins, self.mkr_lines = [], []
        cols = ("#ffd166", "#06d6a0")
        pi = self.spec.getPlotItem()
        for i, col in enumerate(cols):
            sp_ = QtWidgets.QDoubleSpinBox()
            sp_.setDecimals(3)
            sp_.setRange(0.0, 6000.0)
            sp_.setSuffix(" MHz")
            sp_.setKeyboardTracking(False)
            sp_.setToolTip(f"Fréquence du marqueur M{i + 1} : tape-la, ou molette / flèches (pas choisi à droite).")
            ln = pg.InfiniteLine(pos=0.0, angle=90, movable=True, pen=pg.mkPen(col, width=1.4, style=Qt.PenStyle.DashLine),
                                 label=f"M{i + 1}", labelOpts=dict(position=0.96, color=col, fill=(0, 0, 0, 160)))
            ln.setVisible(False)
            pi.addItem(ln, ignoreBounds=True)
            ln.sigPositionChanged.connect(lambda *_, i=i: self._mkr_from_line(i))
            sp_.valueChanged.connect(lambda v, i=i: self._mkr_from_spin(i, v))
            self.mkr_spins.append(sp_)
            self.mkr_lines.append(ln)
        self.mkr_step = self._combo([("pas 1 kHz", 0.001), ("pas 5 kHz", 0.005), ("pas 25 kHz", 0.025),
                                     ("pas 100 kHz", 0.1), ("pas 1 MHz", 1.0)], 0.025)
        self.mkr_step.setToolTip("De combien bougent les marqueurs à chaque cran de molette / flèche.")
        self.mkr_step.currentIndexChanged.connect(lambda *_: [s_.setSingleStep(self.mkr_step.currentData())
                                                              for s_ in self.mkr_spins])
        for s_ in self.mkr_spins:
            s_.setSingleStep(0.025)
        pk = QtWidgets.QPushButton("⤒ Pic")
        pk.setToolTip("Place M1 sur le plus haut signal à ±0,5 MHz.")
        pk.clicked.connect(lambda *_: self.marker_to_peak(0))
        self.mkr2_chk = QtWidgets.QCheckBox("M2")
        self.mkr2_chk.setToolTip("Deuxième marqueur : écart en fréquence et en niveau entre M1 et M2.")
        self.mkr2_chk.toggled.connect(lambda *_: self._mkr_visible())
        self.mkr_drop = QtWidgets.QSpinBox()
        self.mkr_drop.setRange(3, 60)
        self.mkr_drop.setValue(20)
        self.mkr_drop.setPrefix("largeur à −")
        self.mkr_drop.setSuffix(" dB")
        self.mkr_drop.setToolTip("Bande occupée autour du pic près de M1 : là où le niveau reste au-dessus du pic moins "
                                 "cette valeur.")
        self.mkr_drop.valueChanged.connect(lambda *_: self.marker_refresh())
        self.mkr_lbl = QtWidgets.QLabel("")
        self._elastic(self.mkr_lbl)
        self.mkr_lbl.setStyleSheet("font-family:Consolas,monospace;")
        self.mkr_lbl.setMinimumWidth(260)
        self.mkr_lbl.setToolTip("M1 : fréquence et niveau · Δ : écart M1 → M2 · largeur occupée autour du pic.")
        lay = self._flow(("M1 :", self.mkr_spins[0], pk), (self.mkr2_chk, self.mkr_spins[1]), self.mkr_step,
                         self.mkr_drop, self.mkr_lbl)
        lay.setContentsMargins(0, 0, 0, 0)
        bar.setLayout(lay)
        bar.setVisible(False)
        return bar

    def show_markers_bar(self, on):
        self.mkr_bar.setVisible(bool(on))
        if on and not any(s_.value() for s_ in self.mkr_spins):
            x0, x1 = self.spec.getPlotItem().vb.viewRange()[0]
            self.mkr_spins[0].setValue((x0 + x1) / 2.0)
            self.mkr_spins[1].setValue(x0 + (x1 - x0) * 0.6)
        self._mkr_visible()
        self.marker_refresh()

    def _mkr_visible(self):
        on = self.mkr_btn.isChecked()
        self.mkr_lines[0].setVisible(on)
        self.mkr_lines[1].setVisible(on and self.mkr2_chk.isChecked())
        self.mkr_spins[1].setEnabled(self.mkr2_chk.isChecked())
        self.marker_refresh()

    def _mkr_from_line(self, i):
        sp_ = self.mkr_spins[i]
        sp_.blockSignals(True)
        sp_.setValue(self.mkr_lines[i].value())
        sp_.blockSignals(False)
        self.marker_refresh()

    def _mkr_from_spin(self, i, v):
        ln = self.mkr_lines[i]
        ln.blockSignals(True)
        ln.setValue(float(v))
        ln.blockSignals(False)
        self.marker_refresh()

    def _mkr_trace(self):
        try:
            x, y = self.curve.getData()
        except (TypeError, ValueError):            # pas encore de courbe
            return None, None
        return (None, None) if x is None or not isinstance(x, np.ndarray) else (x, y)

    def marker_to_peak(self, i=0):
        F, L = self._mkr_trace()
        pk = None if F is None else peak_near(F, L, self.mkr_spins[i].value())
        if pk is not None:
            self.mkr_spins[i].setValue(pk[0])

    def marker_refresh(self):
        if not getattr(self, "mkr_btn", None) or not self.mkr_btn.isChecked():
            return
        F, L = self._mkr_trace()
        f1 = self.mkr_spins[0].value()
        p1 = None if F is None else trace_at(F, L, f1)
        txt = f"M1 {f1:.3f} MHz " + (self.lvl(p1[1], suffix=True) if p1 else "—")
        if self.mkr2_chk.isChecked():
            f2 = self.mkr_spins[1].value()
            p2 = None if F is None else trace_at(F, L, f2)
            txt += f" · M2 {f2:.3f} · Δ {(f2 - f1) * 1000:+.0f} kHz"
            if p1 and p2:
                txt += f" / {p2[1] - p1[1]:+.1f} dB"
        ow = None if F is None else occupied_width(F, L, f1, self.mkr_drop.value())
        if ow:
            txt += f" · largeur {(ow[1] - ow[0]) * 1000:.0f} kHz"
        self.mkr_lbl.setText(txt)
        self.mkr_lbl.setToolTip(txt)

    def open_spectrum_legend(self):
        d = getattr(self, "_legend", None)
        if d is None:
            d = self._legend = SpectrumLegendDialog(self)        # gardée (cachée à la fermeture) : ses liens
        d.show()
        d.raise_()

    def reset_max(self):
        self.maxhold.clear()
        for w in self.watch:
            w["max"] = None
            w["occw"].clear()
        self.update_watch_table(force=True)
        self.update_plot()

    # ---------------------------------------------------------------- thème
    def apply_theme(self):
        t = self.theme
        app = QtWidgets.QApplication.instance()
        app.setStyle("Fusion")
        app.setPalette(build_palette(t))
        app.setStyleSheet(make_stylesheet(t) + qss_icons(t))
        try:
            for w in (self.spec, self.wf, self.bandw):
                w.setBackground(t["plot_bg"])
                pi = w.getPlotItem()
                for ax in ("bottom", "left"):
                    a = pi.getAxis(ax)
                    a.setPen(pg.mkPen(t["plot_fg"]))
                    a.setTextPen(pg.mkPen(t["plot_fg"]))
            crt = t.get("plot_style") == "crt"
            self.curve.setPen(pg.mkPen(t["curve"], width=1.8 if crt else 1.6))
            # 7.54.2 (fluidité, mesuré en démo à 1920 × 1080) : la grille fine (sous-graduations) coûtait ~16 % de
            # processeur à elle seule -> grands carreaux seulement, pour tous les thèmes (59 % -> 43 %). Le halo du
            # phosphore (stylo de plus d'1 px sous la trace) doublait le coût du dessin (43 % -> 87 %) : retiré.
            self.spec.getPlotItem().showGrid(x=True, y=True, alpha=0.40 if crt else 0.25)
            for ax in ("bottom", "left"):
                a_ = self.spec.getPlotItem().getAxis(ax)
                a_.setStyle(maxTickLevel=0, maxTextLevel=0)
                a_.setTickDensity(2.6 if ax == "left" else 1.6)
            self.maxcurve.setPen(pg.mkPen(t["maxhold"], width=1))
            self.refcurve.setPen(pg.mkPen(t["ref"], width=1.3, style=Qt.PenStyle.DashLine))
            self.thr_line.setPen(pg.mkPen(t["thr"], width=1.5, style=Qt.PenStyle.DashLine))
            self.weak_line.setPen(pg.mkPen(t["thr_weak"], width=1.2, style=Qt.PenStyle.DotLine))
            if getattr(self, "auto_curve", None) is not None:
                self.auto_curve.setPen(pg.mkPen(t["thr"], width=1.3, style=Qt.PenStyle.DashLine))
            self.wf_img.setLookupTable(make_lut(t.get("wf", "Inferno")))
        except Exception:
            pass
        self._clear_marker_pool()
        self._clear_hist_pool()
        self._style_start(self.is_running())
        self.readout.setStyleSheet("font-family:Consolas,monospace;")
        self.update_strips()
        self.update_watch_table(force=True)
        self._update_markers()

    # ------------------------------------------------- pays / plan de fréquences
    def on_country(self, *_):
        self.rebuild_plan()

    def rebuild_plan(self):
        code = self.country_combo.currentData() or "FR"
        self.country = code
        self.plan = build_plan(code, self.plan_custom.get(code))
        self.tv = tv_channels(code)
        note = COUNTRY_NOTES.get(code, "")
        if code in self.plan_custom:
            note += "\n(plan modifié par toi)"
        self.country_note.setText(note + "\nIndicatif : vérifie toujours auprès du régulateur de ton pays.")
        rs = reg_summary(code, TR)
        self.reg_lbl.setToolTip(reg_detail(code, TR))
        a_, b_ = country_uhf(code)
        self.reg_lbl.setText(f"Micros autorisés (indicatif) : {rs}\nBalayé : {a_:g}-{b_:g} MHz (mesurer n'est pas "
                             f"émettre)." if rs else "⚠ Aucune liste de bandes autorisées pour ce pays : rien n'est "
                             "vérifié réglementairement.")
        self.update_strips()
        for w in self.watch:
            w["band"], w["cat"] = spectrum_info(w["freq"], self.plan, self.tv)
            w["sig"] = None
        self.update_watch_table(force=True)

    def edit_plan(self):
        code = self.country_combo.currentData() or "FR"
        name = dict(COUNTRIES).get(code, code)
        dlg = PlanDialog(self, name, plan_to_text(self.plan))
        if not dlg.exec():
            return
        txt = dlg.result_text()
        if txt.strip():
            self.plan_custom[code] = txt
        else:
            self.plan_custom.pop(code, None)
        self.rebuild_plan()

    def _update_legend(self):
        used = {e[3] for e in self.plan} | {e[3] for e in self.tv}
        lines = [f"<span style='color:{self.theme.get('bp_' + k, '#888')}'>■</span> {lab}"
                 for k, (lab, _c) in CATEGORIES.items() if k in used]
        self.legend_lbl.setText("<br>".join(lines))

    def update_strips(self, *_):
        pi = self.bandw.getPlotItem()
        for it in self._strip_rects:
            pi.removeItem(it)
        self._strip_rects = []
        rows = []
        if self.alloc_chk.isChecked() and self.plan:
            rows.append(self.plan)
        if self.tv_chk.isChecked() and self.tv:
            rows.append(self.tv)
        self._strip_rows = []
        self.bandw.setVisible(bool(rows))
        self._update_legend()
        if not rows:
            self.update_strip_labels()
            return
        n = len(rows)
        self.bandw.setFixedHeight(30 * n + 4)
        pi.setYRange(0, n, padding=0)
        th = self.theme
        edge = pg.mkPen(th["plot_bg"], width=1)
        for k, entries in enumerate(rows):
            y0 = n - 1 - k
            self._strip_rows.append((entries, y0))
            for (a, b, lab, cat, note) in entries:
                r = QtWidgets.QGraphicsRectItem(a, y0 + 0.06, b - a, 0.88)
                r.setBrush(pg.mkBrush(blend(th.get("bp_" + cat, "#64748b"), th["plot_bg"], 0.62)))
                r.setPen(edge)
                pi.addItem(r, ignoreBounds=True)
                self._strip_rects.append(r)
        self.update_strip_labels()

    def update_strip_labels(self):
        if not self._strip_rows:
            for lb in self._strip_labels:
                lb.setVisible(False)
            return
        pi = self.bandw.getPlotItem()
        x0, x1 = pi.vb.viewRange()[0]
        px = max(50.0, float(pi.vb.width())) / max(1e-6, x1 - x0)     # pixels par MHz
        th, k = self.theme, 0
        for entries, y0 in self._strip_rows:
            for (a, b, lab, cat, note) in entries:
                if b < x0 or a > x1:
                    continue
                lo, hi = max(a, x0), min(b, x1)
                nch = int((hi - lo) * px / 6.4)
                lab = TR(lab)                             # libellé dessiné (pas un widget Qt) : traduit ici
                if lab.startswith("CH "):
                    txt = lab if nch >= 5 else lab[3:]
                    if nch < 2 or len(txt) > nch:
                        continue
                else:
                    if nch < 4:
                        continue
                    txt = lab if len(lab) <= nch else lab[:nch - 1] + "…"
                while len(self._strip_labels) <= k:
                    t = pg.TextItem("", anchor=(0.5, 0.5))
                    t.setFont(QtGui.QFont("Segoe UI", 8))
                    t.setZValue(5)
                    pi.addItem(t, ignoreBounds=True)
                    self._strip_labels.append(t)
                t = self._strip_labels[k]
                t.setText(txt, color=contrast_text(blend(th.get("bp_" + cat, "#64748b"), th["plot_bg"], 0.62)))
                t.setPos((lo + hi) / 2.0, y0 + 0.5)
                t.setVisible(True)
                k += 1
        for t in self._strip_labels[k:]:
            t.setVisible(False)

    def on_mouse_band(self, evt):
        pos = evt[0]
        if not self.bandw.sceneBoundingRect().contains(pos):
            return
        self._show_band_info(self.bandw.getPlotItem().vb.mapSceneToView(pos).x())

    def _show_band_info(self, f):
        if f > 0:
            self.band_lbl.setText(describe_freq(f, self.plan, self.tv))

    # --------------------------------------------------- options de détection
    def reeval(self, *_):
        if self.latest:
            self.update_watch_levels()
        self.update_watch_table(force=True)

    def on_occ_window(self, *_):
        m = int(self.occ_combo.currentData() or 60)
        for w in self.watch:
            w["occw"].minutes = m
        self.update_watch_table(force=True)

    # ------------------------------------------------------ courbe de référence
    def _set_ref(self, curves):
        self.ref_curves = curves
        if curves:
            F = np.concatenate([c[0] for c in curves])
            L = np.concatenate([c[1] for c in curves])
            o = np.argsort(F)
            self._ref_F, self._ref_L = F[o], L[o]
        else:
            self._ref_F = self._ref_L = None
        self.update_ref_curve()

    def update_ref_curve(self):
        if not self.ref_curves or not self.showref_chk.isChecked():
            self.refcurve.setData([], [])
            return
        nan = np.array([np.nan])
        xs, ys = [], []
        for f, l in sorted(self.ref_curves, key=lambda c: c[0][0]):
            xs += [f, nan]
            ys += [l, nan]
        self.refcurve.setData(np.concatenate(xs), np.concatenate(ys))

    def capture_ref(self, src):
        curves = []
        for k in sorted(self.latest):
            f, l = self.latest[k]
            if src == "max":
                mh = self.maxhold.get(k)
                if mh is not None and mh.shape == l.shape:
                    l = mh
            curves.append((np.array(f, dtype=float), np.array(l, dtype=float)))
        if not curves:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        self._set_ref(curves)
        self._save_ref_file(REF_PATH)
        self.reeval()
        self.set_status("Référence enregistrée (" + ("max hold" if src == "max" else "balayage actuel") +
                        "). Coche « Seuil = courbe de référence + » pour l'utiliser.")

    def _save_ref_file(self, path):
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            data = dict(version=1, created=datetime.now().isoformat(timespec="seconds"),
                        curves=[dict(f=np.round(f, 6).tolist(), l=np.round(l, 1).tolist())
                                for f, l in self.ref_curves])
            Path(path).write_text(json.dumps(data), encoding="utf-8")
            return True
        except Exception as e:
            self.set_status(f"Référence non enregistrée : {e}")
            return False

    def _load_ref_file(self, path, silent=False):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            curves = []
            for c in data["curves"]:
                f, l = np.array(c["f"], dtype=float), np.array(c["l"], dtype=float)
                if len(f) and len(f) == len(l):
                    curves.append((f, l))
            if not curves:
                raise ValueError("aucune courbe dans ce fichier")
        except FileNotFoundError:
            return False
        except Exception as e:
            if not silent:
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Référence illisible :\n{e}")
            return False
        self._set_ref(curves)
        return True

    def save_ref_as(self):
        if not self.ref_curves:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Aucune référence : capture-en une d'abord.")
            return
        d = CFG_PATH.parent / "references"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer la référence",
                                                        str(d / "reference_lieu.json"), "Référence (*.json)")
        if path and self._save_ref_file(path):
            self.set_status(f"Référence enregistrée : {path}")

    def load_ref_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Charger une référence",
                                                        str(CFG_PATH.parent / "references"),
                                                        "Référence (*.json);;Tous les fichiers (*)")
        if path and self._load_ref_file(path):
            self._save_ref_file(REF_PATH)
            self.reeval()
            self.set_status(f"Référence chargée : {os.path.basename(path)}")

    def clear_ref(self):
        self._set_ref([])
        try:
            REF_PATH.unlink()
        except Exception:
            pass
        self.reeval()
        self.set_status("Référence effacée.")

    # --------------------------------------------------------- export du scan
    def export_scan(self):
        if not self.latest:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        dlg = ExportScanDialog(self, self.export_prefs)
        if not dlg.exec():
            return
        v = dlg.values()
        self.export_prefs = {k: x for k, x in v.items() if k not in ("lo", "hi")}
        if v["scope"] == "view" and self.view_id in self.latest:
            keys = [self.view_id]
        else:
            keys = list(self.latest)
        keys.sort(key=lambda k: float(self.latest[k][0][0]))
        fs, live, mxs = [], [], []
        for k in keys:
            f, l = self.latest[k]
            mh = self.maxhold.get(k)
            fs.append(f)
            live.append(l)
            mxs.append(mh if (mh is not None and mh.shape == l.shape) else l)
        F, LV, MX = np.concatenate(fs), np.concatenate(live), np.concatenate(mxs)
        o = np.argsort(F, kind="stable")
        F, LV, MX = scan_crop(F[o], LV[o], MX[o], lo=v.get("lo"), hi=v.get("hi"))     # plage choisie
        if not len(F):
            QtWidgets.QMessageBox.information(self, APP_NAME, "Rien de mesuré dans cette plage.")
            return
        cols, names = [], []
        if v["src"] in ("live", "both"):
            cols.append(LV)
            names.append("Niveau (dBm)")
        if v["src"] in ("max", "both"):
            cols.append(MX)
            names.append("Max hold (dBm)")
        text = scan_csv(F, cols, v["unit"], v["delim"], v["dec"], v["header"], names)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exporter le scan", f"scan_{datetime.now():%Y%m%d_%H%M%S}"
            + (f"_{rbw_tag(self.live_rbw()[0])}" if rbw_tag(self.live_rbw()[0]) else "") + ".csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                fh.write(text)
            self.set_status(f"Scan exporté ({len(F)} points) : {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")

    # --------------------------------------------------- mur / journal auto
    def open_wall(self):
        """Le mur est un panneau : on l'affiche (en onglet à côté du spectre, ou là où tu l'as rangé)."""
        self.dock_wall.show()
        self.dock_wall.raise_()
        self.wall.rebuild()

    # ------------------------------------------------------- vocabulaire / saisie assistée
    def vocab_all(self, kind):
        """Mots proposés pour nommer : liste de base + mots appris + ce qui existe déjà."""
        base = {"name": NAME_WORDS, "scene": SCENE_WORDS, "group": GROUP_WORDS}[kind]
        extra = list(self.vocab_user.get(kind, []))
        if kind == "name":
            extra += label_words([w["name"] for w in self.watch])
        elif kind == "scene":
            extra += [s["name"] for s in self.scenes]
        else:
            extra += [g["name"] for s in self.scenes for g in s["groups"]]
        out, seen = [], set()
        for w in list(base) + extra:
            k = w.strip().lower()
            if k and k not in seen:
                seen.add(k)
                out.append(w.strip())
        return out

    def learn_word(self, kind, word):
        word = str(word).strip()
        if word and word.lower() not in {w.lower() for w in self.vocab_all(kind)}:
            lst = self.vocab_user.setdefault(kind, [])
            lst.append(word)
            del lst[:-300]

    def name_suggestions(self):
        return name_candidates(self.vocab_all("name"), [w["name"] for w in self.watch])

    def ask_name(self, kind, title, label, text=""):
        dlg = NameDialog(self, title, label, self.vocab_all(kind), text)
        if dlg.exec():
            return dlg.value(), True
        return "", False

    def edit_vocab(self):
        cur = "\n".join(self.vocab_user.get("name", []))
        txt, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Mon vocabulaire", "Un mot par ligne (ex. Bolero, Cor anglais…). Ils seront proposés quand tu "
                                     "nommes une fréquence. Les mots de base (MIC, HF, IEM, Intercom…) y sont déjà.", cur)
        if ok:
            words = [x.strip() for x in txt.splitlines() if x.strip()]
            self.vocab_user["name"] = []
            for w in words:
                self.learn_word("name", w)
            self.set_status(f"Vocabulaire enregistré ({len(self.vocab_user['name'])} mot(s) à toi).")

    def quick_name_dialog(self, rows=None):
        rows = list(rows) if rows else self._sel_rows()
        if not rows:
            rows = [i for i, w in enumerate(self.watch) if self.in_scope(w)]
            if not rows:
                self.set_status("Aucune fréquence à nommer.")
                return
            self.set_status(f"Aucune ligne sélectionnée : on nomme les {len(rows)} fréquence(s) de la couche active.")
        dlg = QuickNameDialog(self, rows)
        if not dlg.exec():
            return
        names = dlg.names()
        if not names:
            return
        for i, nm in zip(rows, names):
            self.watch[i]["name"] = nm
            self.watch[i]["sig"] = None
        if dlg.learn_chk.isChecked():
            self.learn_word("name", dlg.word())
        self.update_watch_table(force=True)
        self._update_markers()
        self.set_status(f"{len(rows)} fréquence(s) nommée(s) : {names[0]} … {names[-1]}")

    def fill_down_names(self, rows=None):
        rows = list(rows) if rows else self._sel_rows()
        if len(rows) < 2:
            self.set_status("Sélectionne au moins 2 lignes : la 1ʳᵉ donne le nom de départ (ex. HF 1) et les "
                            "suivantes prennent HF 2, HF 3…")
            return
        names = number_run(self.watch[rows[0]]["name"], len(rows))
        for i, nm in zip(rows, names):
            self.watch[i]["name"] = nm
            self.watch[i]["sig"] = None
        self.update_watch_table(force=True)
        self._update_markers()
        self.set_status(f"Numérotées : {names[0]} … {names[-1]}")

    # ------------------------------------------------------- intermodulation / secours
    def fresh_FL(self, use_max=False, any_age=False):
        """Spectre actuel (toutes les bandes récentes) : (F trié, L) ou (None, None)."""
        now = time.time()
        stale = max(15.0, 4 * self.last_cycle)
        keys = [k for k in self.latest if k != ZOOM_ID and (any_age or now - self.latest_t.get(k, 0) <= stale)]
        if not keys:
            return None, None
        Fs, Ls = [], []
        for k in keys:
            f, l = self.latest[k]
            mh = self.maxhold.get(k) if use_max else None
            Fs.append(f)
            Ls.append(mh if (mh is not None and mh.shape == l.shape) else l)
        F, L = np.concatenate(Fs), np.concatenate(Ls)
        o = np.argsort(F)
        return F[o], L[o]

    def view_range(self, a, b, msg=None):
        self._fit_x = False
        self.spec.getPlotItem().setXRange(a, b, padding=0)
        self.set_status((msg + " : " if msg else "") + f"vue sur {a:g} – {b:g} MHz.")

    def open_intermod(self):
        self._im_dlg = IntermodDialog(self)
        self._im_dlg.show()

    def open_intermod_for(self, f):
        self._im_dlg = IntermodDialog(self, origin=f)
        self._im_dlg.show()

    def manual_path(self):
        """Le manuel (docs/manuel.html, en anglais docs/manual_en.html) : embarqué dans l'exe, ou à côté du
        script. None s'il manque."""
        names = (["manual_en.html"] if self.lang == "en" else []) + ["manuel.html"]
        for name in names:
            for base in (getattr(sys, "_MEIPASS", None), Path(__file__).resolve().parent):
                if base:
                    p_ = Path(base) / "docs" / name
                    if p_.is_file():
                        return p_
        return None

    def set_language(self, code):
        """Langue de l'interface : enregistrée tout de suite, appliquée au prochain démarrage (proposé)."""
        if code == self.lang:
            return
        self.lang = code
        self._save_config()
        if QtWidgets.QMessageBox.question(
                self, APP_NAME, "La langue changera au prochain démarrage. Redémarrer maintenant ?\n"
                                "The language will change at the next start. Restart now?") \
                != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if self.close() and not restart_app():
            QtWidgets.QMessageBox.information(None, APP_NAME, "Relance l'appli à la main pour changer de langue.\n"
                                              "Restart the app by hand to change the language.")

    def open_manual(self, chapter=None):
        p_ = self.manual_path()
        if p_ is None:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Manuel introuvable à côté de l'appli : il est aussi "
                                              "dans le dépôt GitHub, fichier docs/manuel.html.")
            return
        url = QtCore.QUrl.fromLocalFile(str(p_))
        if chapter:                               # 7.59 : ❓ d'une fenêtre -> son chapitre
            url.setFragment(str(chapter))
        QtGui.QDesktopServices.openUrl(url)
        self.set_status("Manuel ouvert dans le navigateur.")

    def show_about(self):
        fw = self.info_lbl.text().strip() or "pas encore connecté"
        fw2 = f"<br>2ᵉ tinySA : {getattr(self, 'dev2_info', '') or '—'}" if self.dev2.get("on") else ""
        QtWidgets.QMessageBox.information(
            self, f"À propos de {APP_NAME}",
            f"<b>{APP_NAME}</b> version <b>{APP_VER}</b><br>"
            f"<i>{TR('Anciennement « TinySA Monitor » (jusqu’à la 8.0).')}</i><br>"
            f"Python {sys.version.split()[0]} · Qt {QtCore.qVersion()}<br><br>"
            f"tinySA : {fw}{fw2}<br><br>"
            f"Config : {CFG_PATH}<br>Journaux : {self.log_dir}<br><br>"
            f"<small>{COORD_NOTE}<br>{TRADEMARKS}</small>")
