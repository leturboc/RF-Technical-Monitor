# Liste des fréquences, annuler, imports, journal, mesures et états. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenListe:
    """Liste des fréquences, annuler, imports, journal, mesures et états. (méthodes de MainWindow, regroupées par thème.)"""

    def rebuild_watch_table(self):
        self._updating = True
        t = self.watch_table
        t.setRowCount(len(self.watch))
        for r, w in enumerate(self.watch):
            w["sig"] = None
            w["band"], w["cat"] = spectrum_info(w["freq"], self.plan, self.tv)
            t.setItem(r, C_NAME, self._item(w["name"], True))
            t.setItem(r, C_FREQ, self._item(f'{w["freq"]:.3f}', True, True))
            for c in (C_LVL, C_MAX):
                t.setItem(r, c, self._item("—", False, True))
            t.setItem(r, C_THR, self._item("—", True, True))
            t.setItem(r, C_SIG, self._item("—"))
            t.setItem(r, C_STAT, self._item("—"))
            t.setItem(r, C_OCC, self._item("—", False, True))
            t.setItem(r, C_LAYER, self._item("—"))
            t.setItem(r, C_BAND, self._item("—"))
            t.setItem(r, C_MARG, self._item("—", False, True))
        self._updating = False
        self.rebuild_tree()
        self._refresh_focus()
        self.update_watch_table(force=True)

    def update_watch_table(self, force=False):
        t, th = self.watch_table, self.theme
        base = th["ui_base"]
        self._updating = True
        n = dict(occ=0, weak=0, free=0)
        n_conf = n_ws = n_abs = 0
        overlaps = block_overlaps([(w["name"], w["freq"], w.get("bw") or 0.0) for w in self.watch])
        for r, w in enumerate(self.watch):
            if r >= t.rowCount():
                break
            st = w["state"]
            conf = st == "occ" and self.is_keep_free(w["status"])
            absn = bool(w.get("absent"))
            if self.in_scope(w):
                n_ws += 1
                if st in n:
                    n[st] += 1
                n_conf += conf
                n_abs += absn
            lv, mx = self.lvl(w["level"]), self.lvl(w["max"])
            stat = w["status"] or "—"
            thr_txt = self.lvl(w["thr"])
            if w["thr"] is None and w.get("athr") is not None:
                thr_txt = "auto " + self.lvl(w["athr"])
            pct = w["occw"].pct()
            occ_txt = "—" if pct is None else f"{pct:.0f} %"
            band = w["band"] or "—"
            if w.get("bw"):
                band = f"▬ bloc {w['bw']:g} MHz · {band}"
            if r in overlaps:
                band = f"⚠ dans le bloc « {overlaps[r]} » · {band}"
            layer = self.layer_text(w)
            gc = self.group_color(w["scene"], w["group"]) if layer else None
            keep_free = self.is_keep_free(w["status"])
            m_txt, m_tone, m_tip = snr_view(w.get("margin") if w.get("level") is not None else None, keep_free)
            # 7.54.1 (Clément : « je vois plus le éteint ») : 💤 dans la case Statut et ligne grisée, même si le micro
            # émet encore (la case Signal, elle, montre ce qui est mesuré)
            if w.get("muted"):
                stat = "💤 éteint · " + stat if w["status"] else "💤 éteint"
            elif w.get("off"):
                stat = "💤 hors état · " + stat if w["status"] else "💤 hors état"
            sig = (lv, mx, st, conf, stat, w["name"], round(w["freq"], 3), thr_txt, occ_txt, band, layer, gc, absn,
                   m_txt)
            if not force and w["sig"] == sig:
                continue
            w["sig"] = sig
            sig_txt, tone, tone_col = self.sig_view(w)
            # 7.54 (look « pro ») : la ligne n'est que légèrement teintée, la couleur forte reste sur la case Signal
            row_bg = {"bad": blend(th["st_occ"], base, 0.20), "warn": blend(th["st_weak"], base, 0.10)}.get(tone, base)
            row_fg = th["ui_text"]
            dim = bool(w.get("muted") or w.get("off"))
            if dim:
                row_fg = blend(th["ui_text"], base, 0.55)
            cells = ((C_NAME, w["name"]), (C_FREQ, f'{w["freq"]:.3f}'), (C_LVL, lv), (C_MAX, mx),
                     (C_THR, thr_txt), (C_SIG, sig_txt), (C_STAT, stat), (C_OCC, occ_txt),
                     (C_LAYER, layer or "—"), (C_BAND, band), (C_MARG, m_txt))
            for c, txt in cells:
                it = t.item(r, c)
                if it is None:
                    continue
                if it.text() != txt:
                    it.setText(txt)
                bg, fg = row_bg, row_fg
                if c == C_SIG and tone != "none":
                    bg = blend(tone_col, base, 1.0 if tone == "bad" else 0.85)
                    fg = contrast_text(bg)
                elif c == C_STAT and w["status"]:
                    bg = blend(self.status_color(w["status"]), row_bg, 0.32 * (0.5 if dim else 1.0))
                    fg = row_fg
                elif c == C_LAYER and gc:
                    bg = blend(gc, row_bg, 0.30)
                    fg = th["ui_text"]
                elif c == C_MARG:
                    fl_ = w.get("floor")
                    it.setToolTip(m_tip + (f"\nBruit de fond utilisé : {self.lvl(fl_, True)} (± 2 MHz autour)"
                                           if fl_ is not None and w.get("level") is not None else ""))
                    if m_tone in ("warn", "bad") and not (keep_free and m_tone == "ok"):
                        bg = blend(th["st_weak"] if m_tone == "warn" else th["st_occ"], row_bg, 0.35)
                        fg = th["ui_text"]
                elif c == C_BAND and w["cat"]:
                    bg = blend(th.get("bp_" + w["cat"], th["st_none"]), row_bg, 0.25)
                    fg = th["ui_text"]
                    tip = describe_freq(w["freq"], self.plan, self.tv)
                    if it.toolTip() != tip:
                        it.setToolTip(tip)
                it.setBackground(QtGui.QColor(bg))
                it.setForeground(QtGui.QColor(fg))
        self._updating = False
        total = f"{n_ws} fréquences" + (f" (sur {len(self.watch)})" if self.scope else "")
        txt = (f'{total} · {n["occ"]} occupée(s) · '
               f'{n["weak"]} faible(s) · {n["free"]} libre(s)')
        if n_conf:
            txt += f" · {CONFLICT_TEXT} ×{n_conf}"
        if n_abs:
            txt += f" · {ABSENT_TEXT} ×{n_abs}"
        self.count_lbl.setText(txt)
        self.apply_filter()
        self.update_tree_counts()
        if self.wall is not None and self.wall.isVisible():
            self.wall.refresh()

    def apply_filter(self, *_):
        t = self.watch_table
        txt = self.filter_edit.text().strip().lower().replace(",", ".")
        occ = self.occ_only_chk.isChecked()
        for r, w in enumerate(self.watch):
            if r >= t.rowCount():
                break
            hide = (not self.in_scope(w)) or (occ and w["state"] != "occ") or bool(
                txt and not (txt in w["name"].lower() or txt in f'{w["freq"]:.3f}'
                             or txt in (w["status"] or "").lower() or txt in (w["band"] or "").lower()
                             or txt in self.layer_text(w).lower()))
            if t.isRowHidden(r) != hide:
                t.setRowHidden(r, hide)

    def on_watch_edit(self, item):
        if self._updating or item.row() >= len(self.watch):
            return
        w = self.watch[item.row()]
        if item.column() == C_NAME:
            w["name"] = item.text()
            w["sig"] = None
            self._update_markers()
        elif item.column() == C_FREQ:
            v = parse_freq_cell(item.text())
            if v is None:
                QtCore.QTimer.singleShot(0, self.rebuild_watch_table)
                return
            self.set_watch_freq(w, v)
        elif item.column() == C_THR:
            txt = item.text().strip().lower()
            if txt in ("", "—", "-", "global"):
                w["thr"] = None
            else:
                v = _num(txt)
                if v is not None and -140.0 <= v <= 20.0:
                    w["thr"] = v
            w["sig"] = None
            QtCore.QTimer.singleShot(0, lambda: self.update_watch_table(force=True))

    def on_watch_dbl(self, row, col):
        if col == C_STAT:
            self.status_popup([row])
        elif col == C_LAYER:
            self.layer_popup([row])
        elif col in (C_LVL, C_MAX, C_SIG):
            self.zoom_on(row)

    def _sel_rows(self):
        return sorted({i.row() for i in self.watch_table.selectedIndexes() if i.row() < len(self.watch)})

    def _status_menu(self, parent):
        m = QtWidgets.QMenu(parent)
        a0 = m.addAction("— aucun statut\tCtrl+0")
        a0.setData("")
        for i, s in enumerate(self.statuses):
            a = m.addAction(color_icon(s["color"]), s["name"] + (f"\tCtrl+{i + 1}" if i < 9 else ""))
            a.setData(s["name"])
        return m

    def quick_status(self, which):
        """Raccourci clavier : statut n° which (0 = le 1er), None = aucun, "on" = le 1er « doit émettre »."""
        rows = self._sel_rows()
        if not rows:
            self.set_status("Sélectionne d'abord des fréquences dans la liste (clic, Maj+clic, Ctrl+A…).")
            return
        if which == "on":
            st = next((x for x in self.statuses if x.get("on")), None)
        elif which is None:
            st = dict(name="")
        else:
            st = self.statuses[which] if which < len(self.statuses) else None
        if st is None:
            self.set_status("Aucun statut à ce numéro (☰ Plus › Statuts… pour les voir / les ranger).")
            return
        self.set_status_rows(rows, st["name"])
        self.set_status(f"{len(rows)} fréquence(s) → « {st['name'] or 'aucun statut'} ».")

    def status_popup(self, rows):
        m = self._status_menu(self)
        act = m.exec(QtGui.QCursor.pos())
        if act is not None and act.data() is not None:
            self.set_status_rows(rows, act.data())

    def set_status_rows(self, rows, name):
        for r in rows:
            if r < len(self.watch):
                self.watch[r]["status"] = name
        self.update_watch_table(force=True)
        self._update_markers()

    def watch_menu(self, pos):
        rows = self._sel_rows()
        if not rows:
            r = self.watch_table.rowAt(pos.y())
            rows = [r] if 0 <= r < len(self.watch) else []
        if not rows:
            return
        m = QtWidgets.QMenu(self)
        sub = self._status_menu(m)
        sub.setTitle(f"Statut ({len(rows)} sélectionnée(s))" if len(rows) > 1 else "Statut")
        m.addMenu(sub)
        lay_sub = self.assign_menu(m)
        lay_sub.setTitle("Scène › Groupe")
        m.addMenu(lay_sub)
        a_rep = m.addAction("🆘 Remplacer ce micro (3 propositions)…")
        a_zoom = m.addAction("🔍 Zoom live sur cette fréquence")
        a_lis = m.addAction("🎧 Écouter avec le SDR…")
        a_rt = m.addAction("⏱ Temps réel autour de cette fréquence…")
        if getattr(self, "sdr_engs", None):
            self._sdr_follow_menu(m, [self.watch[r] for r in rows])     # 8.0.2 : suivre avec le SDR
        a_ren = m.addAction("Renommer…")
        a_qn = m.addAction("✏ Nommer la sélection (HF 1, HF 2…)…")
        a_fd = m.addAction("⇣ Numéroter vers le bas depuis la 1ʳᵉ ligne")
        a_thr = m.addAction("Seuil propre à la fréquence…")
        a_thr0 = m.addAction("Revenir au seuil global")
        a_occ0 = m.addAction("Remettre l'occupation à zéro")
        a_blk = m.addAction("📶 Bloc large (Spectera / WMAS)…")
        wall_hid = all(self.watch[r].get("hide_wall") for r in rows)
        a_wall = m.addAction("🧱 Afficher sur le mur" if wall_hid else "🧱 Masquer sur le mur")
        hid = all(self.watch[r].get("hide_mk") for r in rows)
        a_mk = m.addAction("📍 Réafficher le repère sur le spectre" if hid else "📍 Masquer le repère sur le spectre")
        a_ev = m.addAction("📍 Niveau de cette fréquence dans chaque lieu…") if self.site_scans else None
        muted = all(self.watch[r].get("muted") for r in rows)
        m.addSeparator()
        a_mute = m.addAction("🔔 Rallumer (surveiller à nouveau)  Ctrl+Espace" if muted
                             else "💤 Éteint (je sais) : pas d'alarme ABSENT  Ctrl+Espace")
        m.addSeparator()
        a_del = m.addAction("Supprimer")
        act = m.exec(self.watch_table.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_mute:
            self.set_muted([self.watch[r] for r in rows], not muted)
        elif act is a_rep:
            self.open_replace(self.watch[rows[0]])
        elif act is a_zoom:
            self.zoom_on(rows[0])
        elif act is a_lis:
            self.open_listen(rows)
        elif act is a_rt:
            self.open_realtime(self.watch[rows[0]]["freq"])
        elif act is a_thr:
            w0 = self.watch[rows[0]]
            cur = w0["thr"] if w0["thr"] is not None else self.thr_spin.value()
            u = self.unit
            lo_, hi_ = (0.0, 100.0) if u == "pct" else (to_unit(-140.0, u), to_unit(20.0, u))
            v, ok = QtWidgets.QInputDialog.getDouble(
                self, "Seuil propre", f"Seuil « occupé » ({UNIT_SUFFIX[u]}) pour {len(rows)} fréquence(s) :",
                round(to_unit(cur, u), 1), lo_, hi_, 1)
            v = from_unit(v, u)
            if ok:
                for r in rows:
                    self.watch[r]["thr"] = v
                self.update_watch_table(force=True)
        elif act is a_thr0:
            for r in rows:
                self.watch[r]["thr"] = None
            self.update_watch_table(force=True)
        elif act is a_occ0:
            for r in rows:
                self.watch[r]["occw"].clear()
            self.update_watch_table(force=True)
        elif act is a_qn:
            self.quick_name_dialog(rows)
        elif act is a_fd:
            self.fill_down_names(rows)
        elif act is a_ren:
            w = self.watch[rows[0]]
            txt, ok = self.ask_name("name", "Renommer", f"Nom de {w['freq']:.3f} MHz :", w["name"])
            if ok and txt.strip():
                w["name"] = txt.strip()
                self.update_watch_table(force=True)
                self._update_markers()
        elif act is a_del:
            self.del_watch()
        elif act is a_mk:
            self.hide_marker_rows(rows, not hid)
        elif a_ev is not None and act is a_ev:
            w0 = self.watch[rows[0]]
            self.open_sites(freq=(w0["freq"], float(w0.get("bw") or 0.0)))
        elif act is a_blk:
            self.set_block_rows(rows)
        elif act is a_wall:
            self.set_wall_rows(rows, wall_hid)
        elif self._assign_action(rows, act.data()):
            pass
        elif act.data() is not None:
            self.set_status_rows(rows, act.data())

    def set_muted(self, ws, on, quiet=False):
        """💤 Éteint (je sais) : le micro est éteint exprès, pas d'alarme ABSENT, jusqu'à ce qu'on le rallume.
        La fréquence reste dans le plan (elle se rallumera) et un signal sur une « doit rester libre » sonne toujours."""
        now = time.time()
        n = 0
        for w in ws:
            if bool(w.get("muted")) == bool(on):
                continue
            n += 1
            if on:
                w["muted"] = True
                w["free_since"] = None
                if w.get("absent"):
                    w["absent"] = False
                self.alarms.clear(("ABSENT", int(round(w["freq"] * 1000))), now)
            else:
                w.pop("muted", None)
                w["free_since"] = None
            self.log_event(w, w.get("level") if w.get("level") is not None else 0.0,
                           "ÉTEINT (je sais)" if on else "RALLUMÉ")
        if n:
            w0 = ws[0]
            self.update_watch_table(force=True)
            self._update_markers()
            self.refresh_alarms()
            if self.wall is not None and self.wall.isVisible():
                self.wall.rebuild()
            if not quiet:
                one = w0["name"] or f"{w0['freq']:.3f} MHz"
                self.set_status((f"💤 {one} éteint (je sais) : pas d'alarme ABSENT." if on else f"🔔 {one} rallumé.")
                                if n == 1 else (f"💤 {n} fréquence(s) éteintes (je sais)." if on
                                                else f"🔔 {n} fréquence(s) rallumées."))
        return n

    def toggle_muted_sel(self):
        rows = self._sel_rows()
        ws = [self.watch[r] for r in rows if 0 <= r < len(self.watch)]
        if ws:
            self.set_muted(ws, not all(w.get("muted") for w in ws))

    def layer_ws(self, key):
        """Fréquences d'une scène (key = (scène, "")) ou d'un groupe (key = (scène, groupe))."""
        return [w for w in self.watch if w["scene"] == key[0] and (not key[1] or w["group"] == key[1])]

    def set_block_rows(self, rows):
        """Fréquence simple ↔ bloc large (Spectera / WMAS) pour les lignes choisies."""
        rows = [r for r in rows if 0 <= r < len(self.watch)]
        if not rows:
            return
        labels = [t for t, _ in self.BLOCK_WIDTHS]
        cur = self.watch[rows[0]].get("bw") or 0.0
        idx = next((i for i, (_t, v) in enumerate(self.BLOCK_WIDTHS) if v == cur), len(labels) - 1)
        txt, ok = QtWidgets.QInputDialog.getItem(
            self, "Bloc large", "Spectera / WMAS : un porteur large (canal TV) au lieu d'une fréquence.\n"
                                "« Doit émettre » : niveau médian du bloc · « Doit rester libre » : pic dans le bloc.\n\n"
                                "Largeur :", labels, idx, False)
        if not ok:
            return
        bw = dict(self.BLOCK_WIDTHS)[txt]
        if bw is None:
            bw, ok = QtWidgets.QInputDialog.getDouble(self, "Bloc large", "Largeur du bloc (MHz) :",
                                                      max(cur, 1.0), 0.2, 40.0, 1)
            if not ok:
                return
        for r in rows:
            self.watch[r]["bw"] = float(bw)
            self.watch[r]["sig"] = None
        self._refresh_focus()
        self.update_watch_levels()
        self.update_watch_table(force=True)
        self._update_markers()

    def add_block_dialog(self):
        """Ajoute un bloc Spectera / WMAS : canal TV du pays, ou fréquence centrale + largeur."""
        ch = block_choices(self.tv)
        other = "Autre : fréquence centrale et largeur…"
        txt, ok = QtWidgets.QInputDialog.getItem(self, "Bloc Spectera / WMAS", "Canal (selon le pays choisi) :",
                                                 [c[0] for c in ch] + [other], 0, False)
        if not ok:
            return
        if txt == other:
            f, ok = QtWidgets.QInputDialog.getDouble(self, "Bloc Spectera / WMAS", "Fréquence centrale (MHz) :",
                                                     610.0, 0.1, 6000.0, 3)
            if not ok:
                return
            bw, ok = QtWidgets.QInputDialog.getDouble(self, "Bloc Spectera / WMAS", "Largeur (MHz) :",
                                                      8.0 if self.country not in ("US", "CA") else 6.0, 0.2, 40.0, 1)
            if not ok:
                return
            name = f"Spectera {f:.1f}"
        else:
            _lab, f, bw = next(c for c in ch if c[0] == txt)
            name = "Spectera " + txt.split(" — ")[0].replace("CH ", "ch ")
        sc, gr = self._scope_preset()
        on = next((x["name"] for x in self.statuses if x.get("on")), "")
        self._append_watch(name, f, status=on, scene=sc, group=gr, bw=bw)
        self.sort_watch()
        self.rebuild_watch_table()
        self._refresh_focus()
        self._update_markers()
        self.set_status(f"Bloc « {name} » ajouté : {f - bw / 2:g}–{f + bw / 2:g} MHz (statut « {on or 'aucun'} »).")

    def add_watch_dialog(self, text=""):
        """⌨ 7.62 : « Ajouter » ouvre la saisie express (une ou plusieurs fréquences, nommées ou non)."""
        if self._quickadd is not None and self._quickadd.isVisible():
            if text:
                self._quickadd.edit.setPlainText(text)
            self._quickadd.raise_()
            self._quickadd.activateWindow()
            return self._quickadd
        self._quickadd = QuickAddDialog(self, text, self._scope_preset())
        self._quickadd.show()
        return self._quickadd

    def in_scanned_band(self, f):
        """La fréquence est-elle dans une bande cochée (balayée) ?"""
        return any(b.get("enabled", True) and b["start"] - 1e-6 <= f <= b["stop"] + 1e-6 for b in self.bands)

    def del_watch(self):
        rows = self._sel_rows()
        for r in reversed(rows):
            self.watch.pop(r)
        self.rebuild_watch_table()
        self._update_markers()
        if rows:
            self.undo_track()
            self.set_status(f"{len(rows)} fréquence(s) supprimée(s) · Ctrl+Z pour annuler.")

    def _undo_state(self):
        """Ce qu'on peut annuler : liste, scènes / groupes, bandes, statuts (en JSON) + scans par lieu."""
        c = self._collect_config(True)
        txt = json.dumps({k: c.get(k) for k in self.UNDO_KEYS}, ensure_ascii=False, sort_keys=True, default=str)
        sites = list(self.site_scans)
        sig = txt + "|" + json.dumps([(d["name"], d.get("scene", "")) for d in sites], ensure_ascii=False)
        return (txt, sites), sig

    def undo_track(self):
        """Appelé chaque seconde (et après une suppression) : met de côté l'état d'avant s'il a changé."""
        if getattr(self, "_undo_busy", False):
            return
        try:
            st, sig = self._undo_state()
        except Exception:  # noqa: BLE001 — jamais bloquant
            return
        self.undo_stack.track(st, sig)

    def _undo_restore(self, st, what):
        txt, sites = st
        self._undo_busy = True
        self.history_track()
        pre = self._hist_rows
        try:
            data = self._collect_config(True)
            data.update(json.loads(txt))
            data["site_scans"] = list(sites)
            self._apply_config(data)
            self._hist_rows = pre                  # 🕘 l'annulation est notée (« ↶ Annulé »)
            self.history_track(TR(what.split(" ·")[0]))
            self.site_scans = list(sites)
            self.update_site_curve()
            self.undo_stack.resync(self._undo_state()[1])
        finally:
            self._undo_busy = False
        self._bump()
        n_u, n_r = len(self.undo_stack.undo), len(self.undo_stack.redo)
        self.set_status(f"{what} · encore {n_u} retour(s) possible(s), {n_r} à rétablir (Ctrl+Y).")

    def undo(self):
        self.undo_track()                          # le dernier changement, même de moins d'une seconde
        st = self.undo_stack.back()
        if st is None:
            self.set_status("Rien à annuler.")
            return False
        self._undo_restore(st, "↶ Annulé")
        return True

    def redo(self):
        st = self.undo_stack.fwd()
        if st is None:
            self.set_status("Rien à rétablir.")
            return False
        self._undo_restore(st, "↷ Rétabli")
        return True

    def delete_selected_layer(self):
        k = self._sel_layer_key()
        if k is not None and self.scene_by_name(k[0]) is not None:
            self.delete_layer(k)

    def edit_statuses(self):
        dlg = StatusDialog(self, self.statuses)
        if not dlg.exec():
            return
        rows = dlg.result_rows()
        for w in self.watch:
            new = ""
            for s in rows:
                if s["orig"] is not None and s["orig"] == w["status"]:
                    new = s["name"]
                    break
            w["status"] = new
        self.statuses = [dict(name=s["name"], color=s["color"], free=bool(s.get("free")), on=bool(s.get("on")))
                         for s in rows]
        self.update_watch_table(force=True)
        self._update_markers()

    def edit_colors(self):
        dlg = ColorsDialog(self, self.theme, self.preview_theme)
        if dlg.exec():
            self.theme = dict(dlg.theme)
            if dlg.recolor_chk.isChecked():
                self.recolor_layers()
        self.apply_theme()

    def recolor_layers(self):
        """Scènes, groupes et statuts aux couleurs de la palette du thème (7.54.1)."""
        self.scenes, self.statuses = layers_recolor(self.scenes, self.statuses, self.theme)
        self.rebuild_tree()
        for w in self.watch:
            w["sig"] = None
        self.update_watch_table(force=True)
        self._update_markers()
        if self.wall is not None and self.wall.isVisible():
            self.wall.rebuild()
        self.set_status("🎨 Scènes, groupes et statuts aux couleurs du thème (Ctrl+Z pour annuler).")

    def preview_theme(self, t):
        self.theme = dict(t)
        self.apply_theme()

    # ---------------------------------------------------- import / export
    def _resolve_status(self, st):
        if not st:
            return ""
        for s in self.statuses:
            if s["name"].lower() == st.lower():
                return s["name"]
        pal = theme_pal(self.theme)
        self.statuses.append(dict(name=st, color=pal[(len(self.statuses) + 3) % len(pal)],
                                  free=False, on=False))
        return st

    def import_watch(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Importer des fréquences", "", "Listes et plans (*.csv *.txt *.tsv *.ezrf3 *.shw *.cug *.wsm *.wshow "
            "*.acp);;Plan EazyRF (*.ezrf3);;Show Shure WWB (*.shw);;Groupe Shure (*.cug);;Projet Sennheiser WSM (*.wsm);;"
            "Show Wisycom Manager (*.wshow);;Projet DPA (*.acp);;Tous les fichiers (*)")
        for p in paths:
            if Path(p).suffix.lower() in PLAN_EXTS:
                self.import_ezrf_file(p)
                continue
            self.open_import(decode_text(Path(p).read_bytes()), os.path.basename(p), preset=self._scope_preset())

    def paste_watch(self):
        txt, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Coller une liste", "Colle un tableau (Excel, WWB, WSM, Wisycom…) ou une fréquence par ligne :")
        if ok and txt.strip():
            self.open_import(txt, "Texte collé", preset=self._scope_preset())

    def import_ezrf_file(self, path, opts=None):
        """Plan d'un logiciel de coordination (.ezrf3, Shure WWB .shw / .cug, Sennheiser WSM .wsm) -> aperçu
        puis import ; le fichier peut ensuite être suivi (🔗)."""
        try:
            doc, kind = parse_plan_file(Path(path).read_bytes(), os.path.basename(path))
        except (OSError, ValueError) as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Impossible de lire « {os.path.basename(path)} » : {e}")
            return None
        return self.open_ezrf(doc, os.path.basename(path), opts=opts, path=path, kind=kind)

    def open_ezrf(self, doc, source, opts=None, path=None, kind="EazyRF"):
        """Plan -> fenêtre d'aperçu puis import (opts donné = sans fenêtre, pour les tests)."""
        if opts is None:
            dlg = EzrfImportDialog(self, doc, source, path, kind)
            if not dlg.exec():
                return None
            opts = dlg.options()
        opts = dict(opts, kind=opts.get("kind") or kind)
        if opts.get("manual"):                       # récepteurs Wisycom complétés dans « À compléter »
            doc = plan_fill_pending(doc, opts["manual"])
        return self.apply_ezrf(doc, opts, source, path)

    def _ezrf_profiles(self, doc):
        """Appareils du plan -> {clé appareil: clé de profil}. Réglages connus (.ezrf3) : profil perso créé ou
        réutilisé (même nom ET mêmes réglages) ; copier-coller : profil perso ou bibliothèque du même nom."""
        names = ezrf_profile_names(doc["devices"])

        def same(d, p):
            return (abs(d["sep"] - p["sep"]) < 1e-6 and abs(d["filt"] - p["filt"]) < 1e-6
                    and abs(d["step"] - p["step"]) < 1e-6
                    and all(abs(d["tol"].get(k, 0) - p["tol"].get(k, 0)) < 1e-6 for k in ("2tx3", "3tx3", "5"))
                    and abs(float(d.get("img") or 0) - float(p.get("img") or 0)) < 1e-6)
        new, want = [], {}
        have = {n: (k, d) for k, n, d, _w in RX_CUSTOM}
        low = lambda x: str(x).strip().lower()
        for dk, p in doc["devices"].items():
            name = names[dk]
            if "sep" in p:
                k = 2
                while name in have and not same(have[name][1], p):
                    name, k = f"{names[dk][:55]} ({k})", k + 1
                if name not in have and name not in [x["name"] for x in new]:
                    d = rx_from_library(dict(p, type=""))
                    d["name"] = name
                    d["note"] = (f"Plan EazyRF « {doc['title'] or 'sans titre'} » · {p['lo']:g}–{p['hi']:g} MHz"
                                 + (f" · FI {p['img']:g} MHz (fréquence image vérifiée)" if p.get("img") else ""))
                    new.append(d)
                want[dk] = name
            else:
                hit = next((n for n in have if low(n) == low(name)), None)
                if hit is None:
                    lib = next((d for d in RX_LIBRARY if low(d["name"]) == low(name)), None)
                    if lib is not None and lib["name"] not in [x["name"] for x in new]:
                        new.append(rx_from_library(lib))
                    hit = lib["name"] if lib is not None else None
                if hit:
                    want[dk] = hit
        if new:
            rx_set_custom(rx_custom_dump() + new)
            self.rx_profiles_changed()
        by_name = {n: k for k, n, _d, _w in RX_CUSTOM}
        return {dk: by_name[n] for dk, n in want.items() if n in by_name}

    def apply_ezrf(self, doc, opts, source="EazyRF", path=None):
        """Importe le plan : fréquences (scène = groupe du document, groupe = section), appareils posés sur les groupes,
        interférences en émetteurs extérieurs, scan de fond dans Scans par lieu. -> nombre de fréquences ajoutées."""
        entries = ezrf_remap(ezrf_entries(doc, opts.get("skip_off", True), opts.get("naming", "dev")), opts.get("map"))   # 🗂 7.66 : rangement
        keymap = self._ezrf_profiles(doc) if opts.get("profiles", True) else {}
        if opts.get("replace"):
            self.watch.clear()
        by_key = {int(round(w["freq"] * 1000)): w for w in self.watch}
        st = self._resolve_status(opts["status"]) if opts.get("status") else ""
        added, groups = 0, {}
        for name, f, sc, gr, dk, _note in entries:
            rx = keymap.get(dk, "")
            if rx and gr:
                lst = groups.setdefault((sc or DEFAULT_SCENE, gr), [])
                if rx not in lst:
                    lst.append(rx)
            k = int(round(f * 1000))
            src = os.path.basename(str(path)) if path else ""
            if k in by_key:
                if not by_key[k].get("ez"):           # 🔗 déjà là : reliée au plan quand même (pas volée à un autre plan)
                    by_key[k]["ez"] = ezrf_id(sc, gr, name)
                    if src:
                        by_key[k]["ezsrc"] = src
                continue
            self._append_watch(name, f, st, None, sc, gr)
            self.watch[-1]["ez"] = ezrf_id(sc, gr, name)
            if src:
                self.watch[-1]["ezsrc"] = src
            if rx:
                self.watch[-1]["rx"] = rx
            by_key[k] = self.watch[-1]
            added += 1
        for (sc, gr), rxs in groups.items():
            g = self.group_row(sc, gr)
            if g is not None:
                old = self.group_rxs(g)
                g["rx"] = old + [r for r in rxs if r not in old]
        for w in self.watch:                     # appareil = celui du groupe par défaut : inutile de le répéter
            if w.get("rx") and w["rx"] == self.rx_of(dict(w, rx="")):
                w.pop("rx", None)
        n_ext = 0
        if opts.get("interf"):
            for f in doc["interf"]:
                k = int(round(f * 1000))
                if k not in by_key:
                    self._append_watch(f"Ext. {f:.3f}", f, "", None, "", "")
                    by_key[k] = self.watch[-1]
                    n_ext += 1
        if doc.get("tv") or opts.get("replace"):   # 7.58.2 : canaux TV du plan -> 📺 grisés ; liste remplacée (tournée,
            self.tnt_set_plan(doc.get("tv") or [], os.path.basename(str(path)) if path else source)  # nouveau lieu) :
            # ceux de l'ancien plan repartent, même si le nouveau n'en a pas
        scan_name = ""
        if opts.get("scan") and doc["scan"] is not None:
            names = {d["name"] for d in self.site_scans}
            scan_name = snapshot_name("EazyRF", doc["scan_title"] or doc["title"], names, time.strftime("%H:%M"))
            self.site_scans.append(site_scan_doc(scan_name, doc["scan"][0], doc["scan"][1], time.time()))
        self.sort_watch()
        self.rebuild_tree()
        self.rebuild_watch_table()
        self._update_markers()
        if scan_name:
            self.update_site_curve()
        self.undo_track()
        if opts.get("follow") and path:            # 🔗 suivre le fichier
            try:
                self.ezrf_link = dict(path=str(path), mtime=os.path.getmtime(path), name=os.path.basename(str(path)),
                                      status=opts.get("status", ""), skip_off=bool(opts.get("skip_off", True)),
                                      kind=opts.get("kind") or "EazyRF", manual=dict(opts.get("manual") or {}),
                                      map=ezrf_map_norm(opts.get("map")), naming=opts.get("naming", "dev"))
            except OSError:
                self.ezrf_link = None
        msg = f"📥 Plan {opts.get('kind') or 'EazyRF'} : {added} fréquence(s) importée(s)"
        if len(entries) > added:
            msg += f" ({len(entries) - added} déjà présente(s))"
        if keymap:
            msg += f", {len(set(keymap.values()))} appareil(s) posé(s) sur leurs groupes"
        if n_ext:
            msg += f", {n_ext} émetteur(s) extérieur(s)"
        if scan_name:
            msg += f", scan « {scan_name} » gardé dans Scans par lieu"
        if opts.get("planning"):                   # 🎬 7.66 : créneaux lus dans les noms des passages
            slots = ezrf_planning(entries)
            have = {(x["scene"], x["group"], x["day"], x["start"], x["end"]) for x in self.planning["slots"]}
            new = [x for x in slots if (x["scene"], x["group"], x["day"], x["start"], x["end"]) not in have]
            if new:
                self.planning = planning_norm(dict(self.planning, slots=self.planning["slots"] + new))
                msg += TR(", {} créneau(x) ajouté(s) au planning").format(len(new))
        self.set_status(msg + ".")
        if added:
            self.offer_missing_bands()
        return added

    def open_import(self, text, source, preset=("", "")):
        if is_ezrf_paste(text):
            try:
                return self.open_ezrf(parse_ezrf_paste(text), source)
            except ValueError:
                pass
        dlg = ImportDialog(self, text, source, self.scenes, preset)
        if not dlg.an["data"]:
            QtWidgets.QMessageBox.information(self, APP_NAME, f"Aucune fréquence reconnue dans « {source} ».")
            return
        if not dlg.exec():
            return
        entries = dlg.entries()
        if dlg.replace():
            self.watch.clear()
        by_key = {int(round(w["freq"] * 1000)): w for w in self.watch}
        added = moved = 0
        for name, f, st, sc, gr in entries:
            k = int(round(f * 1000))
            if k in by_key:
                w = by_key[k]
                if (sc or gr) and not w["scene"] and not w["group"]:
                    if gr and not sc:
                        sc = DEFAULT_SCENE
                    self.ensure_group(sc, gr)
                    w["scene"], w["group"] = sc, gr
                    moved += 1
                continue
            self._append_watch(name, f, self._resolve_status(st), None, sc, gr)
            by_key[k] = self.watch[-1]
            added += 1
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        extra = f", {moved} rangée(s) dans leur groupe" if moved else ""
        self.set_status(f"{added} fréquence(s) importée(s) depuis {source} "
                        f"({len(entries) - added} déjà présente(s){extra}).")
        if added:
            self.offer_missing_bands()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p and Path(p).suffix.lower() in PLAN_EXTS:
                self.import_ezrf_file(p)
            elif p and Path(p).suffix.lower() in (".csv", ".txt", ".tsv"):
                self.open_import(decode_text(Path(p).read_bytes()), os.path.basename(p),
                                 preset=self._scope_preset())

    def export_watch(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter", "frequences.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                wr = csv.writer(f, delimiter=";")
                wr.writerow(["Nom", "MHz", "Statut", "Scène", "Groupe", "Niveau dBm", "Max dBm", "Signal",
                             "Seuil dBm", "Occupation %", "Spectre"])
                for w in self.watch:
                    pct = w["occw"].pct()
                    wr.writerow([w["name"], fmt_comma(w["freq"]), w["status"], w["scene"], w["group"],
                                 "" if w["level"] is None else fmt_comma(w["level"], 1),
                                 "" if w["max"] is None else fmt_comma(w["max"], 1), SIG_TEXT[w["state"]],
                                 "" if w["thr"] is None else fmt_comma(w["thr"], 1),
                                 "" if pct is None else fmt_comma(pct, 0), w["band"]])

    def bands_from_list(self):
        ws = self.scope_ws()
        if not ws:
            QtWidgets.QMessageBox.information(self, APP_NAME, "La liste de fréquences (ou la couche active) est vide.")
            return
        fs = sorted(x for w in ws for x in block_points(w["freq"], w.get("bw")))
        groups, cur = [], [fs[0]]
        for f in fs[1:]:
            if f - cur[-1] <= 20.0:
                cur.append(f)
            else:
                groups.append(cur)
                cur = [f]
        groups.append(cur)
        new = [(f"{g[0]:.0f}–{g[-1]:.0f} MHz", max(0.1, g[0] - 0.5), g[-1] + 0.5, 200.0) for g in groups]
        tot = sum(int((b[2] - b[1]) * 1000 / b[3]) + 1 for b in new)
        r = QtWidgets.QMessageBox.question(
            self, APP_NAME, f"Remplacer les bandes actuelles par {len(new)} bande(s) "
                            f"couvrant {'la couche active' if self.scope else 'ta liste'} "
                            f"({tot} points au total, pas de 200 kHz) ?")
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            with self.lock:
                self.bands.clear()
            for d in (self.latest, self.maxhold, self.partial_data):
                d.clear()
            for b in new:
                self._append_band(*b)
            self._bands_changed()

    # -------------------------------------------------------------- journal
    def simulated(self):
        """8.1 : True si une source SIMULÉE alimente la surveillance (démo du tinySA, ou un poste SDR sur le SDR démo).
        Tout ce qui en sort est marqué 🧪 (journal, alarmes, alertes, page web, titre) : jamais pris pour une mesure."""
        try:
            if self.demo_chk.isChecked() and self.is_running():
                return True
            return any(e.running() and e.kind() == "demo" for e in (getattr(self, "sdr_engs", None) or {}).values())
        except Exception:  # noqa: BLE001
            return False

    def log_event(self, w, level, event):
        if not self.log_kinds.get(log_kind(event), True):
            return                                # type d'événement décoché dans « 📝 Quoi noter »
        if self.alarms.sim:                       # 8.1 : événement né d'une source simulée -> marqué dans le journal
            w = dict(w, note=("🧪 SIMULÉ (démo) · " + w["note"]) if w.get("note") else "🧪 SIMULÉ (démo)")
        self._log_n += 1
        t = self.log_table
        t.insertRow(0)
        vals = [datetime.now().strftime("%H:%M:%S"), w["name"], f'{w["freq"]:.3f}' if w["freq"] else "—",
                f"{level:.1f}" if w["freq"] else "—", event,
                self.layer_text(w) if "scene" in w else "", w.get("note", "")]
        col = (self.theme["st_occ"] if event in ("OCCUPÉ", "CONFLIT", "INTERMOD", "ABSENT", "APPAREIL PERDU", "TROP FORT",
                                                 "APPEL INCOMPLET")
               else self.theme["st_unk"]
               if event == "INCONNU" else self.theme["st_free"])
        self._auto_log(vals, w)                      # fichier : toujours en dBm
        if self._session is not None:
            self._session_log(vals, w)
        if w["freq"]:
            vals = list(vals)
            vals[3] = self.lvl(level)
        for c, v in enumerate(vals):
            it = self._item(v, False, c in (2, 3))
            if c == 4:
                it.setForeground(QtGui.QColor(col))
            t.setItem(0, c, it)
        while t.rowCount() > 2000:
            t.removeRow(t.rowCount() - 1)

    def _sync_log_menu(self):
        for k, a_ in getattr(self, "_logwhat_acts", {}).items():
            a_.blockSignals(True)
            a_.setChecked(self.log_kinds.get(k, True))
            a_.blockSignals(False)

    def on_log_dbl(self, row, col):
        it = self.log_table.item(row, 4)
        if it is None or it.text() != TR("INCONNU"):
            return
        f = _num(self.log_table.item(row, 2).text())
        if f is None:
            return
        sc, gr = self._scope_preset()
        self._append_watch(f"Nouveau {f:.3f}", f, scene=sc, group=gr)
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        self.set_status(f"{f:.3f} MHz ajoutée à la liste (renomme-la : clic droit › Renommer).")

    def export_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter le journal", "journal.csv", "CSV (*.csv)")
        if not path:
            return
        t = self.log_table
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f, delimiter=";")
            wr.writerow([TR(x) for x in ("Heure", "Nom", "MHz", "dBm", "Événement", "Scène › Groupe", "Note")])
            for r in range(t.rowCount() - 1, -1, -1):
                wr.writerow([t.item(r, c).text() for c in range(7)])

    # --------------------------------------------------------- données live
    def _sweep_time(self, bid):
        """Heure de la mesure donnée par le worker (audit 7.44 : interface chargée = balayages datés en retard) ;
        heure actuelle si l'appareil ne la donne pas (ou si elle est incohérente)."""
        now = time.time()
        try:
            t = (getattr(self.sender(), "sweep_t", None) or {}).get(bid)
        except Exception:  # noqa: BLE001
            t = None
        if isinstance(t, (float, int)) and not isinstance(t, bool):
            return min(float(t), now)            # audit 7.53 : une mesure ANCIENNE garde son âge (avant : remise à
        return now                               # « maintenant » au-delà de 2 min = fraîcheur artificielle)

    def on_sweep(self, bid, f, l):
        if bid in CALIB_IDS:
            self._calib_add(CALIB_IDS.index(bid), f, l)
            return
        self.partial_data.pop(bid, None)
        if bid != ZOOM_ID:
            f, l = self._site_feed(bid, f, l)
            if self.diversity_on():
                f, l = self._div_feed(bid, f, l)
        old = self.latest.get(bid)
        if (old is not None and old[0].shape == f.shape and abs(old[0][0] - f[0]) < 1e-6
                and abs(old[0][-1] - f[-1]) < 1e-6):
            self.history.setdefault(bid, deque(maxlen=20)).append(old)
        else:
            self.history.pop(bid, None)
        self.latest[bid] = (f, l)
        self.latest_t[bid] = self._sweep_time(bid)
        if bid != ZOOM_ID and len(l):
            self.__dict__.setdefault("_sat_max", {})[bid] = (self.latest_t[bid], float(np.nanmax(l)))
        if bid != ZOOM_ID:
            if self._t_start is None:
                self._t_start = self.latest_t[bid]
            self.store.add(bid, self.latest_t[bid], f, l)
            if self.recorder is not None:
                self.recorder.add(bid, self.latest_t[bid], f, l)
        mh = self.maxhold.get(bid)
        if not self.maxhold:
            self._mh_t0 = time.time()            # le max hold repart : la durée d'un scan gardé se compte d'ici
        self.maxhold[bid] = np.maximum(mh, l) if (mh is not None and mh.shape == l.shape) else l.copy()
        self.update_watch_levels()
        self.check_strong(bid, f, l)
        self.update_watch_table()
        if self.unk_chk.isChecked() or self._linecheck is not None:     # l'appel repère les packs mal réglés
            self.detect_unknown(bid, f, l)
        if self._linecheck is not None and bid != ZOOM_ID:
            self._linecheck.feed()
        if self._hunt is not None and bid == ZOOM_ID:
            self._hunt.feed(f, l)
        if self.view_id in (-1, bid):
            self.update_plot()
        if self._wf_bid() == bid:
            self.update_waterfall(bid, f, l)

    def offer_missing_bands(self):
        """7.57 : après un import, des fréquences hors des bandes balayées -> on propose d'ajouter les bandes qui
        manquent (fenêtre non bloquante)."""
        miss = missing_bands([w["freq"] for w in self.watch], self.bands)
        if not miss:
            return []
        txt = "\n".join(f"• {a:g}–{z:g} MHz ({n} fréquence(s))" for a, z, n in miss)
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Question, APP_NAME,
                                    "Des fréquences de ta liste sont en dehors des bandes balayées : elles ne seraient "
                                    "pas surveillées.\nAjouter ces bandes ?\n\n" + txt, parent=self)
        yes = box.addButton("Ajouter les bandes", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Plus tard", QtWidgets.QMessageBox.ButtonRole.RejectRole)

        def done(btn, miss=miss):
            if btn is yes:
                for a, z, _n in miss:
                    self._append_band(f"{a:g}–{z:g} MHz", a, z, 100.0, True)
                self._bands_changed()
                self.set_status(f"📶 {len(miss)} bande(s) ajoutée(s) : toute ta liste est maintenant surveillée.")
        box.buttonClicked.connect(done)
        box.setModal(False)
        self._band_offer = box
        box.show()
        return miss

    def _wf_bid(self):
        """Bande du waterfall (7.57) : la bande de la Vue, ou la seule bande balayée en « Toutes les bandes »."""
        return single_band_view(self.view_id, self.bands, ZOOM_ID)

    def auto_view(self):
        """7.57 : Vue « Toutes les bandes » -> directement sur la bande UHF du pays (ou la seule bande balayée)."""
        if self._zoom is not None or self.view_id != -1:
            return
        bid = default_view_band(self.bands, getattr(self, "country", "FR"))
        i_ = self.view_combo.findData(bid) if bid is not None else -1
        if i_ >= 0:
            self.view_combo.setCurrentIndex(i_)

    def on_partial(self, bid, f, l, i, n):
        if bid in CALIB_IDS:
            return
        self.partial_data[bid] = (f, l)
        name = next((b["name"] for b in self.scan_bands() if b["id"] == bid), "Zoom")
        self.set_status(f"Balayage « {name} » : segment {i}/{n}")
        if self.view_id in (-1, bid):
            now = time.monotonic()                 # fluidité (7.31.1) : 5 images / s au plus pendant un balayage
            if now - getattr(self, "_partial_t", 0.0) >= 0.2:
                self._partial_t = now
                self.update_plot(hist=False)

    def on_cycle(self, dt, nb, dev=0):
        self.dev_cycle[dev] = dt
        live = [v for k, v in self.dev_cycle.items() if k >= len(self.dev_live) or self.dev_live[k]]
        dt = max(live) if live else dt          # le plus lent des tinySA fixe le rythme de rafraîchissement
        nb = len([b for b in self.scan_bands() if self._scan_now(b)]) if self.ndev() > 1 and self._zoom is None else nb
        self.last_cycle = dt
        ids = {b["id"] for b in self.scan_bands() if b["enabled"]}
        if self._zoom is not None:
            ids.add(ZOOM_ID)
        for k in list(self.latest):
            if k not in ids:
                for d in (self.latest, self.maxhold, self.unk_now, self.history):
                    d.pop(k, None)
        ws = self.scope_ws()
        occ = sum(1 for w in ws if w["state"] == "occ")
        conf = sum(1 for w in ws if w["state"] == "occ" and self.is_keep_free(w["status"]))
        absn = sum(1 for w in ws if w.get("absent"))
        mode = "ZOOM · " if self._zoom is not None else ("🎯 " if self._focus_bands else "")
        self.cycle_lbl.setText(f"{mode}Cycle {dt:.2f} s · {nb} bande(s) · {len(ws)} fréq. · "
                               f"{occ} occupée(s)" + (f" · {CONFLICT_TEXT} ×{conf}" if conf else "")
                               + (f" · {ABSENT_TEXT} ×{absn}" if absn else "") + "   ")

    def update_watch_levels(self):
        try:
            self._auto_curve_update()
        except Exception:
            pass
        if not self.watch:
            return
        now = time.time()
        stale = max(15.0, 4 * self.last_cycle)
        fresh = [k for k in self.latest if now - self.latest_t.get(k, 0) <= stale]
        if not fresh:
            for w in self.watch:
                w["level"], w["state"], w["t_acc"] = None, None, None
                self._alarm_reset(w, now)
            return
        F = np.concatenate([self.latest[k][0] for k in fresh])
        L = np.concatenate([self.latest[k][1] for k in fresh])
        o = np.argsort(F)
        F0, L0 = F[o], L[o]
        # 📍 deux tinySA à deux lieux : une fréquence de la scène X est jugée par le tinySA posé à X
        per_site = {}
        if self.multi_site_on():
            for site in {x for v in self.dev_scenes.values() for x in v}:
                Fs, Ls = self.site_fresh(site)
                if Fs is not None:
                    per_site[site] = (Fs, Ls)
        win = self.win_spin.value() / 1000.0
        gthr, gweak, weak_on = self.thr_spin.value(), self.weak_spin.value(), self.weak_chk.isChecked()
        rel = self.ref_chk.isChecked() and self._ref_F is not None
        margin = self.ref_margin.value()
        cap = max(5.0, 2.0 * self.last_cycle)
        delay = max(float(self.absent_spin.value()), 2.0 * self.last_cycle)
        alert = conflict = absent = None
        new_prio = -1
        for w in self.watch:
            if not self.in_scope(w):
                w["t_acc"] = None
                self._alarm_reset(w, now)
                continue
            f = w["freq"]
            bw = w.get("bw") or 0.0
            F, L = per_site.get(w.get("scene"), (F0, L0))
            how = "max" if self.is_keep_free(w["status"]) else "median"
            lvl = level_block(F, L, f, bw, how) if bw else level_at(F, L, f, win)
            w["level"] = lvl
            fl_ = noise_floor(F, L, f, win=2.0 + bw / 2.0, exclude=max(0.15, win, bw / 2.0)) if lvl is not None else None
            w["margin"] = (lvl - fl_) if fl_ is not None else None
            w["floor"] = fl_
            if self.thr_auto and fl_ is not None:      # seuils auto : bruit appris, qui ne monte pas si c'est occupé
                w["afl"] = floor_track(w.get("afl"), fl_, now - (w.get("afl_t") or now), busy=w.get("state") == "occ")
                w["afl_t"] = now
            if lvl is None:
                w["state"], w["t_acc"] = None, None
                self._alarm_reset(w, now)
                continue
            w["max"] = lvl if w["max"] is None else max(w["max"], lvl)
            ref_l = ((level_block(self._ref_F, self._ref_L, f, bw, how) if bw else
                      level_at(self._ref_F, self._ref_L, f, win)) if rel else None)
            thr, weak = eff_thresholds(w["thr"], ref_l, rel, margin, gthr, gweak,
                                       w.get("afl") if self.thr_auto else None, self.auto_margins())
            w["athr"] = thr if self.thr_auto and w["thr"] is None else None
            w["ethr"] = thr                         # seuil réellement appliqué (explication des alarmes, 7.56)
            prev = w["state"]
            new = next_state(prev, lvl, thr, weak, weak_on)
            t0 = w["t_acc"]
            w["t_acc"] = now
            if t0 is not None:
                w["occw"].add(now, min(now - t0, cap), new == "occ")
            keep_free = self.is_keep_free(w["status"])
            if new == "occ" and prev != "occ":
                w["peak"], w["since"] = lvl, now
                seen = self.seen_by(f)
                if keep_free:
                    f_at = f
                    if bw:                              # bloc : l'intrus est au pic mesuré dans le bloc
                        lo_ = int(np.searchsorted(F, f - bw / 2.0))
                        hi_ = int(np.searchsorted(F, f + bw / 2.0, side="right"))
                        if hi_ > lo_:
                            f_at = float(F[lo_ + int(np.argmax(L[lo_:hi_]))])
                    w["im"] = self.im_cause(w, f_at)
                    note = " · ".join(x for x in (w["im"], seen) if x)
                    self.log_event(dict(w, note=note) if note else w, lvl, "INTERMOD" if w["im"] else "CONFLIT")
                    conflict = w
                else:
                    w["occ_log"] = False                # noté seulement s'il dure (OCC_LOG_S), voir plus bas
                    if OCC_LOG_S <= 0 and not self.w_paused(w):
                        w["occ_log"] = True
                        self.log_event(dict(w, note=seen) if seen else w, lvl, "OCCUPÉ")
                    alert = w
            elif new == "occ":
                w["peak"] = max(w["peak"] or lvl, lvl)
                if (not keep_free and w.get("occ_log") is False and now - (w.get("since") or now) >= OCC_LOG_S
                        and not self.w_paused(w)):
                    w["occ_log"] = True
                    nb, seen = w.pop("blips", 0), self.seen_by(f)
                    note = " · ".join(x for x in (seen, f"+ {nb} passage(s) de moins de {OCC_LOG_S:.0f} s avant"
                                                  if nb else "") if x)
                    self.log_event(dict(w, note=note) if note else w, w["peak"], "OCCUPÉ")
            elif prev == "occ" and not keep_free and w.get("occ_log") is False:
                w["occ_log"] = None                     # occupation trop courte (ou micro en pause) : pas de ligne
                w["blips"] = w.get("blips", 0) + (0 if self.w_paused(w) else 1)
                w["im"] = ""
            elif prev == "occ":
                w["occ_log"] = None
                w["im"] = ""
                # bilan de Clément (7.53) : « Libre » affichait le PIC de l'occupation (−69,7) et paraissait plus fort que
                # le « OCCUPÉ » (−91,7) : on note le niveau ACTUEL, le pic va dans la note
                pk = w.get("peak")
                self.log_event(dict(w, note=f"max pendant l'occupation : {self.lvl(pk)}") if pk is not None else w,
                               lvl, f"Libre ({now - w['since']:.0f} s)")
            if prev is not None and (prev == "occ") != (new == "occ"):     # 🩺 7.68 : « pile au seuil »
                fl_q = w.get("_flips")
                if fl_q is None:
                    fl_q = w["_flips"] = deque(maxlen=200)
                fl_q.append(now)
            lh = w.get("_lvh")
            if lh is None:
                lh = w["_lvh"] = deque(maxlen=400)
            if not lh or now - lh[-1][0] >= 2.0:
                lh.append((now, lvl))
            w["state"] = new
            # ---- alarmes : CONFLIT (signal sur une fréquence « doit rester libre ») et ABSENT (« doit émettre » muette)
            fk = int(round(f * 1000))
            confirm = float(self.sound.cfg.get("confirm", 0))
            if new == "occ" and keep_free and now - (w.get("since") or now) < confirm:
                pass                                # signal trop court pour l'instant : on attend la confirmation
            elif new == "occ" and keep_free and not w.get("off"):      # 📸 en pause : pas d'alarme
                prio = self.freq_prio(w)
                kind = "INTERMOD" if w.get("im") else "CONFLIT"
                if self.alarms.raise_(("CONFLIT", fk), kind, w["name"], f, prio, now, lvl, self.layer_text(w),
                                      " · ".join(x for x in (w.get("im", ""), self.seen_by(f)) if x)):
                    new_prio = max(new_prio, prio)
            else:
                self.alarms.clear(("CONFLIT", fk), now)
            if self.is_keep_on(w["status"]) and not self.w_paused(w):
                if new == "free":
                    fs = w.get("free_since")
                    if fs is None:
                        fs = w["free_since"] = now
                    if now - fs >= delay:
                        prio = self.freq_prio(w)
                        if self.alarms.raise_(("ABSENT", fk), "ABSENT", w["name"], f, prio, now, lvl,
                                              self.layer_text(w), f"silence depuis {now - fs:.0f} s"):
                            w["absent"] = True
                            self.log_event(dict(w, note=f"aucun signal depuis {now - fs:.0f} s"), lvl, "ABSENT")
                            absent = w
                            new_prio = max(new_prio, prio)
                else:
                    w["free_since"] = None
                    a_ = self.alarms.clear(("ABSENT", fk), now)
                    if w.get("absent") or a_ is not None:
                        w["absent"] = False
                        self.log_event(w, lvl, f"Retour ({now - a_['t0']:.0f} s)" if a_ else "Retour")
            else:
                w["free_since"] = None
                if w.get("absent"):
                    w["absent"] = False
                    self.alarms.clear(("ABSENT", fk), now)
        if conflict is not None:
            self.set_status(f"⚠ CONFLIT : {conflict['name']} ({conflict['freq']:.3f} MHz) est occupée "
                            f"alors qu'elle doit rester libre.")
        if absent is not None:
            self.set_status(f"⚠ ABSENT : {absent['name']} ({absent['freq']:.3f} MHz) n'émet plus alors qu'elle "
                            f"doit émettre.")
        if alert is not None and conflict is None and self.alert_chk.isChecked() and self.sound.cfg.get("occ_beep") \
                and not snooze_left(self.snooze_until, now):
            self.sound.alarm(0)
        if new_prio >= 0:
            self._alarm_sound(new_prio)
            self.refresh_alarms()

    def detect_unknown(self, bid, f, l):
        """Pics au-dessus du seuil qui ne correspondent à aucune fréquence de la liste."""
        self.unk_now[bid] = []
        if len(l) < 3:
            return
        thr = self.thr_spin.value()
        if self.thr_auto and self._acurve is not None:   # seuils auto : la courbe du bruit + la marge, point par point
            Fc, Lc, _ = self._acurve
            ok = np.isfinite(Lc)
            if ok.any():
                thr = (np.interp(f, Fc[ok], Lc[ok]) + self.auto_margins()[0])[1:-1]
        mid = l[1:-1]
        idx = np.where((mid >= thr) & (mid >= l[:-2]) & (mid > l[2:]))[0] + 1
        if not len(idx):
            return
        wf = np.array([w["freq"] for w in self.watch]) if self.watch else np.array([])
        step = float(np.median(np.diff(f))) if len(f) > 1 else 0.2
        guard = self.win_spin.value() / 1000.0 + step / 2 + 0.05
        now, logged = time.time(), 0
        for i in idx[:200]:
            fr = float(f[i])
            if len(wf) and float(np.min(np.abs(wf - fr))) <= guard:
                continue
            self.unk_now[bid].append(fr)
            key = round(fr / 0.1)
            last = self.unk_seen.get(key, 0.0)
            self.unk_seen[key] = now
            if now - last > 30 and logged < 10:
                note = self.im_note(fr, step)
                self.log_event({"name": "Signal inconnu", "freq": fr, "note": note}, float(l[i]), "INCONNU")
                logged += 1
