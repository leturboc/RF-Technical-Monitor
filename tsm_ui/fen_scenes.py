# Scènes et groupes, scans par lieu, rattachement des tinySA, mur. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenScenes:
    """Scènes et groupes, scans par lieu, rattachement des tinySA, mur. (méthodes de MainWindow, regroupées par thème.)"""

    # ------------------------------------------------- couches : scènes › groupes
    def scene_by_name(self, name):
        return next((x for x in self.scenes if x["name"] == name), None)

    def duplicate_layer(self, key):
        """⧉ 7.63 : copie d'un groupe (dans la même scène) ou d'une scène avec tous ses groupes : couleur, priorité,
        appareils gardés ; AUCUNE fréquence copiée. -> nom de la copie."""
        import copy as _copy
        sc = self.scene_by_name(key[0])
        if sc is None:
            return None
        if key[1]:
            g = next((x for x in sc["groups"] if x["name"] == key[1]), None)
            if g is None:
                return None
            ng = _copy.deepcopy(g)
            ng["name"] = copy_name(g["name"], [x["name"] for x in sc["groups"]])
            sc["groups"].insert(sc["groups"].index(g) + 1, ng)
            new = ng["name"]
            what = f"{sc['name']} › {new}"
        else:
            ns = _copy.deepcopy(sc)
            ns["name"] = copy_name(sc["name"], [x["name"] for x in self.scenes])
            self.scenes.insert(self.scenes.index(sc) + 1, ns)
            new = what = ns["name"]
        self.rebuild_tree()
        self.undo_track()
        self.set_status(TR("⧉ Copie créée : « {} » (sans fréquences). Renomme-la par clic droit si besoin.").format(what))
        return new

    def ensure_group(self, scene, group=""):
        """Crée la scène (et le groupe) s'ils n'existent pas encore."""
        scene, group = (scene or "").strip(), (group or "").strip()
        if not scene:
            return
        sc = self.scene_by_name(scene)
        if sc is None:
            pal = theme_pal(self.theme)                  # 7.54.1 : couleurs qui suivent le thème
            sc = dict(name=scene, color=pal[len(self.scenes) % len(pal)], groups=[])
            self.scenes.append(sc)
        if group and not any(g["name"] == group for g in sc["groups"]):
            n = sum(len(x["groups"]) for x in self.scenes)
            pal = theme_pal(self.theme)
            sc["groups"].append(dict(name=group, color=pal[(n + 1) % len(pal)]))

    def group_color(self, scene, group):
        sc = self.scene_by_name(scene)
        if sc is None:
            return None
        for g in sc["groups"]:
            if g["name"] == group:
                return g["color"]
        return sc["color"]

    def in_scope(self, w):
        return scope_match(self.scope, w["scene"], w["group"])

    def scope_ws(self):
        return [w for w in self.watch if self.in_scope(w)]

    @staticmethod
    def layer_text(w):
        if w["scene"] and w["group"]:
            return f'{w["scene"]} › {w["group"]}'
        return w["scene"] or w["group"] or ""

    def scope_text(self):
        if not self.scope:
            return "Global"
        return " + ".join((f"{a} › {b}" if b else (a or "Sans scène")) for a, b in self.scope)

    def _scope_preset(self):
        """Scène / groupe proposés par défaut pour une nouvelle fréquence (la couche active, si c'est un groupe)."""
        if self.scope and len(self.scope) == 1 and self.scope[0][0]:
            return self.scope[0][0], (self.scope[0][1] or "")
        return "", ""

    def _tree_counts(self):
        cnt = {}
        for w in self.watch:
            keys = [(w["scene"], None)]
            if w["group"]:
                keys.append((w["scene"], w["group"]))
            for k in keys:
                c = cnt.setdefault(k, [0, 0, 0])
                c[0] += 1
                if w["state"] == "occ":
                    c[1] += 1
                    if self.is_keep_free(w["status"]):
                        c[2] += 1
                if w.get("absent"):
                    c[2] += 1
        return cnt

    @staticmethod
    def _tree_label(name, c):
        txt = f"{name}   ·  {c[0]} fréq."
        if c[2]:
            txt += f"  ·  ⚠ {c[2]} alarme(s)"
        elif c[1]:
            txt += f"  ·  {c[1]} occupée(s)"
        return txt

    def rebuild_tree(self):
        tree = self.layer_tree
        cnt = self._tree_counts()
        self._tree_lock = True
        tree.clear()
        self._tree_items, self._tree_sig = {}, {}

        def mk(parent, scene, group, name, color):
            it = QtWidgets.QTreeWidgetItem()
            it.setText(0, self._tree_label(name, cnt.get((scene, group), [0, 0, 0])))
            it.setIcon(0, color_icon(color))
            it.setData(0, Qt.ItemDataRole.UserRole, key_enc(scene, group))
            if parent is None:
                tree.addTopLevelItem(it)
            else:
                parent.addChild(it)
            self._tree_items[(scene, group)] = (it, name)
            return it

        for sc in self.scenes:
            top = mk(None, sc["name"], None, sc["name"] + self.dev_tag(sc["name"]), sc["color"])
            for g in sc["groups"]:
                mk(top, sc["name"], g["name"], g["name"] + self.prio_mark(g)
                   + (f"  · {' + '.join(rx_short(k) for k in self.group_rxs(g))}" if self.group_rxs(g) else ""),
                   g["color"])
        if self.scenes and any(w["scene"] == "" for w in self.watch):
            mk(None, "", None, "Sans scène", self.theme["st_none"])
        tree.expandAll()
        cur = list(self.scope or [])
        valid = [k for k in cur if k in self._tree_items]
        for k in valid:
            self._tree_items[k][0].setSelected(True)
        self._tree_lock = False
        if cur != valid:
            self.set_scope(valid or None)
        else:
            self.update_scope_ui()
        self._layer_compact()

    def list_tips(self):
        QtWidgets.QMessageBox.information(self, TR("Astuces de la liste"), getattr(self, "_list_tips", ""))

    def _layer_compact(self):
        """8.1 (DA épurée) : sans scène, le cadre « Classer par scène › groupe » se réduit à sa rangée de boutons
        (pas d'arbre vide, pas de ligne « Couche active » qui répète le compteur de la liste)."""
        has = bool(self.scenes)
        for w_ in (self.layer_tree, self.focus_chk, self.layer_lbl):
            w_.setVisible(has)
        try:
            sp = self.freq_split
            row = self.layer_box.sizeHint().height() if not has else 230
            tot = sum(sp.sizes()) or 830
            sp.setSizes([min(row, tot // 2), max(200, tot - min(row, tot // 2))])
        except Exception:  # noqa: BLE001
            pass

    def update_tree_counts(self):
        cnt = self._tree_counts()
        th = self.theme
        for k, (it, name) in self._tree_items.items():
            c = cnt.get(k, [0, 0, 0])
            txt = self._tree_label(name, c)
            col = th["st_occ"] if c[2] else (th["st_weak"] if c[1] else th["ui_text"])
            if self._tree_sig.get(k) != (txt, col):
                self._tree_sig[k] = (txt, col)
                it.setText(0, txt)
                it.setForeground(0, QtGui.QBrush(QtGui.QColor(col)))

    def update_scope_ui(self):
        n = len(self.scope_ws())
        if self.scope:
            self.layer_lbl.setText(f"Couche active : {self.scope_text()} — {n} fréquence(s)")
        else:
            self.layer_lbl.setText(f"Couche active : Global — {len(self.watch)} fréquence(s)")
        self.focus_chk.setEnabled(bool(self.scope))
        col = self.theme["ui_accent"]
        self.global_btn.setStyleSheet(
            "QPushButton{background:%s;color:%s;font-weight:600;border-color:%s;}" % (col, contrast_text(col), col)
            if not self.scope else "")
        self.update_title()

    def _site_feed(self, bid, f, l):
        """📍 Balayage d'un tinySA posé à un lieu : rangé dans le direct et le max hold de ce lieu. Avec deux tinySA à
        deux lieux, la vue Global prend le plus fort des deux (le pire cas) -> (F, L) à garder en global."""
        mine = self.dev_scenes.get(self.band_src.get(bid, 0), [])
        if not mine:
            return f, l
        now = time.time()
        for site in mine:                          # un tinySA peut couvrir plusieurs scènes : chacune reçoit le balayage
            self.site_live.setdefault(site, {})[bid] = (f, l, now)
            if site not in self.site_mh:
                self._site_mh_t0[site] = now
            mh = self.site_mh.setdefault(site, {})
            old = mh.get(bid)
            mh[bid] = (f, np.maximum(old[1], l) if old is not None and old[1].shape == l.shape else l.copy())
            if site not in self._site_base:
                self._site_base[site] = next((d for d in self.site_scans if d["name"] == site), None)
        if self.multi_site_on():
            stale = max(15.0, 4 * self.last_cycle)
            for s_, bands in self.site_live.items():
                x = bands.get(bid)
                if s_ not in mine and x is not None and now - x[2] <= stale and x[1].shape == l.shape:
                    l = np.maximum(l, x[1])
        return f, l

    def _div_feed(self, bid, f, l):
        """🔀 Garde le dernier balayage de chaque tinySA pour cette bande -> meilleur des deux, point par point."""
        now = time.time()
        buf = self.div_buf.setdefault(bid, {})
        buf[self.band_src.get(bid, 0)] = (f, l, now)
        r = diversity_merge(buf, now, max(10.0, 2.5 * self.last_cycle))
        if r is None:
            return f, l
        F, L, src = r
        self.div_src[bid] = (F, src, now)
        return F, L

    def site_fresh(self, site):
        """Direct d'un lieu (bandes récentes) -> (F, L) trié, ou (None, None)."""
        now, stale = time.time(), max(15.0, 4 * self.last_cycle)
        segs = [(f, l) for f, l, t in self.site_live.get(site, {}).values() if now - t <= stale]
        if not segs:
            return None, None
        F, L = np.concatenate([x[0] for x in segs]), np.concatenate([x[1] for x in segs])
        o = np.argsort(F)
        return F[o], L[o]

    def forget_site(self, site):
        """Oublie le max hold EN MÉMOIRE d'une scène (sinon _sites_tick recrée son scan gardé 30 s plus tard)."""
        self.site_mh.pop(site, None)
        self._site_mh_t0.pop(site, None)
        self._site_base.pop(site, None)

    def _sites_tick(self, now):
        """Toutes les 30 s : le max hold de chaque lieu est gardé tout seul (fusionné au scan déjà gardé)."""
        if now < self._sites_next or not self.site_mh:
            return
        self._sites_next = now + 30.0
        for site in [s_ for s_ in self.site_mh if self.scene_by_name(s_) is None]:
            self.forget_site(site)               # scène supprimée (ou nouveau show) : son scan ne revient pas
        for site, bands in self.site_mh.items():
            segs = sorted(bands.values(), key=lambda x: float(x[0][0]))
            F, L = np.concatenate([x[0] for x in segs]), np.concatenate([x[1] for x in segs])
            base = self._site_base.get(site)
            rbw, est = self.scan_rbw(F)
            if base is not None:
                F, L = merge_scans([(base["f"], base["l"]), (F, L)])
                rbw = rbw_merge(base.get("rbw"), rbw) if "rbw" in base else rbw
            if F is None:
                continue
            self.site_scans = site_replace(self.site_scans, site_scan_doc(site, F, L, now, rbw=rbw, rbw_est=est))
        self.update_site_curve()

    def view_sites(self):
        """Lieux à montrer sur le spectre : la (les) scène(s) choisie(s) dans « Mes fréquences » qui sont des lieux
        (un tinySA y est, ou un scan y est gardé). None = vue normale (Global, ou scène qui n'est pas un lieu)."""
        if not self.scope or not getattr(self, "sites_btn", None) or not self.sites_btn.isChecked():
            return None
        if not any(self.dev_scenes.values()):     # aucun tinySA rattaché à une scène : le direct reste celui de
            return None                            # tous (sinon une scène avec un scan gardé n'avait plus de direct)
        known = set(self.site_live) | {d["name"] for d in self.site_scans} | {x for v in self.dev_scenes.values() for x in v}
        sel = sorted({k[0] for k in self.scope if k and k[0] in known})
        return sel or None

    def set_dev_site(self, dev, site):
        """« Le tinySA n° dev est à : site » ("" = aucun lieu) : une seule scène."""
        self.set_dev_scenes(dev, [site] if (site or "").strip() else [])

    def toggle_dev_scene(self, dev, scene, on):
        cur = list(self.dev_scenes.get(int(dev), []))
        if on and scene not in cur:
            cur.append(scene)
        elif not on and scene in cur:
            cur.remove(scene)
        self.set_dev_scenes(dev, cur)

    def set_dev_scenes(self, dev, scenes):
        """📡 Les scènes que surveille le tinySA n° dev (une ou plusieurs ; vide = aucune) : appliqué tout de suite."""
        dev = int(dev)
        scenes = list(dict.fromkeys(x.strip() for x in scenes if (x or "").strip()))
        if scenes:
            self.dev_scenes[dev] = scenes
        else:
            self.dev_scenes.pop(dev, None)
        if self.dev_ids.get(dev):                  # tinySA numéroté : ses scènes le suivront s'il change de port
            self.devid_scenes[self.dev_ids[dev]] = scenes
        self._bump()
        self.rebuild_tree()
        self.update_site_curve()
        self.update_plot()
        who = f"{dev_ord(dev)} tinySA ({self.dev_name(dev)})"
        self.set_status(f"📡 {who} : " + (", ".join(scenes) if scenes else "aucune scène")
                        + (" · scènes différentes : chaque tinySA balaye toutes les bandes chez lui"
                           if self.multi_site_on() else ""))

    def dev_tag(self, scene):
        """« 📡 Plateau » : quel(s) tinySA surveille(nt) cette scène (dans l'arbre, dès qu'un rattachement existe : il
        change ce que montre le spectre, il ne doit pas être caché)."""
        if not any(self.dev_scenes.values()):
            return ""
        who = [self.dev_name(d) for d in sorted(self.dev_scenes) if scene in self.dev_scenes[d]]
        return f"   📡 {' + '.join(who)}" if who else ""

    def on_devid(self, dev, n):
        """🔢 Numéro gravé dans le tinySA lu à la connexion : s'il a déjà été rattaché à des scènes sous ce numéro,
        elles le suivent (ex. les deux tinySA ont été branchés à l'envers)."""
        self.dev_ids[dev] = int(n)
        if not n:
            return
        want = self.devid_scenes.get(int(n))
        if want is not None and want != self.dev_scenes.get(dev, []):
            self.dev_scenes[dev] = list(want)
            if not want:
                self.dev_scenes.pop(dev, None)
            self._bump()
            self.rebuild_tree()
            self.set_status(f"🔁 tinySA n° {n} reconnu en {dev_ord(dev)} : ses scènes le suivent "
                            f"({', '.join(want) or 'aucune'}).")
        elif want is None and self.dev_scenes.get(dev):
            self.devid_scenes[int(n)] = list(self.dev_scenes[dev])
        if self._devdlg is not None:
            self._devdlg.refresh()

    def identify_device(self, dev):
        """👋 Fait clignoter l'écran du tinySA n° dev (pour savoir lequel est lequel)."""
        ws = [w for i, w in enumerate(self.workers) if getattr(w, "slot", i) == dev and w.isRunning()]
        if not ws:
            self.set_status("👋 Lance d'abord ▶ Démarrer : il faut être connecté au tinySA pour le faire clignoter.")
            return False
        ws[0].cmdq.put(("identify",))
        self.set_status(f"👋 Regarde les tinySA : celui dont l'écran clignote en orange est le "
                        f"{dev_ord(dev)} ({self.dev_name(dev)}).")
        return True

    def number_device(self, dev, n):
        """🔢 Grave un numéro dans le tinySA (gardé même débranché, même sur un autre PC)."""
        ws = [w for i, w in enumerate(self.workers) if getattr(w, "slot", i) == dev and w.isRunning()]
        if not ws:
            self.set_status("🔢 Lance d'abord ▶ Démarrer : il faut être connecté au tinySA pour le numéroter.")
            return False
        ws[0].cmdq.put(("setid", int(n)))
        if self.dev_scenes.get(dev):
            self.devid_scenes[int(n)] = list(self.dev_scenes[dev])
        self.set_status(f"🔢 Numéro {n} gravé dans le {dev_ord(dev)} tinySA.")
        return True

    def open_devices(self):
        if self._devdlg is not None:
            self._devdlg.raise_()
            return
        self._devdlg = DevicesDialog(self)
        self._devdlg.show()

    def _build_sites_menu(self):
        m = self.sites_menu
        m.clear()
        m.addAction("📡 Mes tinySA et leurs scènes…").triggered.connect(lambda *_: self.open_devices())
        names = list(dict.fromkeys([x["name"] for x in self.scenes] + [d["name"] for d in self.site_scans]
                                   + [x for v in self.dev_scenes.values() for x in v]))
        for d_ in self.dev_list():
            sm = m.addMenu(f"📡 {dev_ord(d_)} tinySA ({self.dev_name(d_)}) surveille…")
            for n_ in names:
                a = sm.addAction(n_)
                a.setCheckable(True)
                a.setChecked(n_ in self.dev_scenes.get(d_, []))
                a.triggered.connect(lambda *_, d_=d_, n_=n_, a=a: self.toggle_dev_scene(d_, n_, a.isChecked()))
        m.addSeparator()
        a = m.addAction("👁 Afficher les lieux sur le spectre")
        a.setCheckable(True)
        a.setChecked(self.sites_btn.isChecked())
        a.triggered.connect(lambda *_, a=a: self.sites_btn.setChecked(a.isChecked()))
        m.addAction("📍 Scans par lieu (fusion, export)…").triggered.connect(lambda *_: self.open_sites())

    def update_site_curve(self):
        """📍 Scan gardé du lieu choisi (scène sélectionnée dans « Mes fréquences »), ou fusion de tous en Global."""
        if not hasattr(self, "sitecurve"):
            return
        self.update_site_bar()
        docs = sites_for_scope(self.site_scans, self.scope) if self.sites_btn.isChecked() else []
        if not docs:
            self.sitecurve.setData([], [])
            self.site_lbl.setVisible(False)
            return
        F, L = merge_scans([(d["f"], d["l"]) for d in docs]) if len(docs) > 1 else (np.asarray(docs[0]["f"]),
                                                                                    np.asarray(docs[0]["l"]))
        if F is None:
            return
        F, L = gap_nan(F, L)
        scs = {site_doc_scene(d) for d in docs}
        if self.scope and len(scs) == 1 and len(docs) > 1:      # une scène, plusieurs scans gardés : leur fusion
            sc = next(iter(scs))
            col = self.scene_color(sc)
            txt = (f"📍 {sc} : en direct · pointillés = fusion de {len(docs)} scans gardés"
                   if self.site_fresh(sc)[0] is not None or not any(self.dev_scenes.values())
                   else f"📍 {sc} : fusion de {len(docs)} scans gardés")
        elif len(docs) == 1:
            col = self.scene_color(docs[0]["name"]) if self.scene_by_name(docs[0]["name"]) else "#e5e7eb"
            when = datetime.fromtimestamp(docs[0]["t"]).strftime("%d/%m %H:%M") if docs[0]["t"] else ""
            if self.scope and self.site_fresh(docs[0]["name"])[0] is not None:
                txt = f"📍 {docs[0]['name']} : en direct (pointillés = max gardé)"
            elif self.scope and not any(self.dev_scenes.values()):
                txt = f"📍 {docs[0]['name']} : scan gardé en pointillés" + (f" ({when})" if when else "")
            elif self.scope:
                txt = f"📍 {docs[0]['name']} : pas de tinySA ici en ce moment · dernier spectre gardé" + (
                    f" ({when})" if when else "")
            else:
                txt = f"📍 Scan gardé : {docs[0]['name']}" + (f" ({when})" if when else "")
        else:
            col = "#e5e7eb"
            txt = f"📍 Tous les lieux : fusion de {len(docs)} scans"
        self.sitecurve.setPen(pg.mkPen(col, width=1.2, style=Qt.PenStyle.DashLine))
        self.sitecurve.setData(F, L)
        self.site_lbl.setText(txt, color=col)
        self.site_lbl.setVisible(True)
        self._place_site_lbl()

    def update_site_bar(self):
        """Bandeau au-dessus du spectre quand la scène regardée n'a AUCUN tinySA rattaché (son direct est donc vide) :
        qui surveille quoi, et en un clic « ce tinySA est ici » ou « tout le site » (retour de Clément 7.26.1 : « j'avais
        mal assigné le tiny, il faut que ce soit intuitif »)."""
        bar = getattr(self, "site_bar", None)
        if bar is None:
            return
        sites = self.view_sites()
        watched = {x for v in self.dev_scenes.values() for x in v}
        lost = [x for x in (sites or []) if x not in watched]
        n_ = self.site_bar_btns.count()
        for _ in range(n_ if isinstance(n_, int) else 0):      # (faux Qt des tests : count() n'est pas un entier)
            it = self.site_bar_btns.takeAt(0)
            if it is not None and it.widget() is not None:
                it.widget().deleteLater()
        if not sites or len(lost) < len(sites):
            bar.setVisible(False)
            return
        sc = lost[0]
        where = " · ".join(f"{dev_ord(d)} tinySA ({self.dev_name(d)}) : {', '.join(self.dev_scenes[d])}"
                           for d in sorted(self.dev_scenes) if self.dev_scenes[d])
        self.site_bar_lbl.setText(f"📡 Aucun tinySA ne surveille « {sc} » : pas de direct ici. Actuellement : {where}.")
        for d in self.dev_list():
            b = QtWidgets.QPushButton(f"📡 Le {dev_ord(d)} tinySA ({self.dev_name(d)}) est ici")
            b.setToolTip(f"Ce tinySA surveille désormais « {sc} » (à la place de ses scènes actuelles).")
            b.clicked.connect(lambda *_, d=d, sc=sc: self.set_dev_scenes(d, [sc]))
            self.site_bar_btns.addWidget(b)
        g_ = QtWidgets.QPushButton("🌐 Tout le site")
        g_.setToolTip("Revenir à la vue globale : le direct de tous les tinySA.")
        g_.clicked.connect(lambda *_: self.go_global())
        self.site_bar_btns.addWidget(g_)
        o_ = QtWidgets.QPushButton("⚙")
        o_.setToolTip("Mes tinySA et leurs scènes : qui surveille quoi.")
        o_.clicked.connect(lambda *_: self.open_devices())
        self.site_bar_btns.addWidget(o_)
        bar.setVisible(True)

    def _place_site_lbl(self):
        if getattr(self, "site_lbl", None) is not None and self.site_lbl.isVisible():
            (x0, x1), (y0, y1) = self.spec.getPlotItem().vb.viewRange()
            self.site_lbl.setPos(x0 + (x1 - x0) * 0.01, y1 - (y1 - y0) * 0.24)   # sous les noms des fréquences

    def scene_color(self, name):
        sc = self.scene_by_name(name)
        return sc["color"] if sc else "#e5e7eb"

    def set_scope(self, scope):
        self.scope = [tuple(k) for k in scope] if scope else None
        self.update_site_curve()
        for w in self.watch:
            w["t_acc"] = None
            w["sig"] = None
        self._refresh_focus()
        self.update_scope_ui()
        self.update_watch_table(force=True)
        self._update_markers()
        if self.wall is not None and self.wall.isVisible():
            self.wall.relayout()

    def on_tree_sel(self):
        if self._tree_lock:
            return
        keys = []
        for it in self.layer_tree.selectedItems():
            k = key_dec(it.data(0, Qt.ItemDataRole.UserRole))
            if k is not None:
                keys.append(k)
        self.set_scope(keys or None)

    def go_global(self):
        self._tree_lock = True
        self.layer_tree.clearSelection()
        self._tree_lock = False
        self.set_scope(None)

    def _layers_changed(self):
        for w in self.watch:
            w["sig"] = None
        self.rebuild_tree()
        self._refresh_focus()
        self.update_watch_table(force=True)
        self._update_markers()
        if self.wall is not None and self.wall.isVisible():
            self.wall.relayout()

    def _sel_layer_key(self):
        its = self.layer_tree.selectedItems()
        return key_dec(its[0].data(0, Qt.ItemDataRole.UserRole)) if its else None

    def add_scene(self):
        txt, ok = self.ask_name("scene", "Nouvelle scène", "Nom de la scène (ex. Main Stage) :")
        name = txt.strip()
        if ok and name:
            self.ensure_group(name)
            self._layers_changed()
            return name
        return None

    def _pick_scene(self):
        k = self._sel_layer_key()
        if k is not None and k[0] and self.scene_by_name(k[0]) is not None:
            return k[0]
        if len(self.scenes) == 1:
            return self.scenes[0]["name"]
        if self.scenes:
            name, ok = QtWidgets.QInputDialog.getItem(self, "Scène", "Dans quelle scène ?",
                                                      [x["name"] for x in self.scenes], 0, False)
            return name if ok else None
        return None

    def add_group(self, scene=None):
        """Crée un groupe (et la scène si besoin) ; renvoie (scène, groupe) ou None."""
        scene = scene or self._pick_scene()
        if not scene:
            txt, ok = self.ask_name("scene", "Nouvelle scène", "Il n'y a pas encore de scène. Nom de la scène :")
            if not (ok and txt.strip()):
                return None
            scene = txt.strip()
        txt, ok = self.ask_name("group", "Nouveau groupe", f"Nom du groupe / de l'artiste dans « {scene} » :")
        name = txt.strip()
        if ok and name:
            self.ensure_group(scene, name)
            self._layers_changed()
            return scene, name
        return None

    def assign_rows(self, rows, scene, group=""):
        if group and not scene:
            scene = DEFAULT_SCENE
        self.ensure_group(scene, group)
        for r in rows:
            if r < len(self.watch):
                self.watch[r]["scene"], self.watch[r]["group"] = scene, group
        self._layers_changed()

    def assign_menu(self, parent):
        m = QtWidgets.QMenu(parent)
        for sc in self.scenes:
            sm = m.addMenu(color_icon(sc["color"]), sc["name"])
            a = sm.addAction(f"{sc['name']} (toute la scène)")
            a.setData(key_enc(sc["name"]))
            sm.addSeparator()
            for g in sc["groups"]:
                a = sm.addAction(color_icon(g["color"]), g["name"])
                a.setData(key_enc(sc["name"], g["name"]))
            sm.addSeparator()
            a = sm.addAction("＋ Nouveau groupe…")
            a.setData("N" + SEP + sc["name"])
        if self.scenes:
            m.addSeparator()
        a = m.addAction("＋ Nouvelle scène + groupe…")
        a.setData("NS" + SEP)
        a = m.addAction("— Aucune scène")
        a.setData("X" + SEP)
        return m

    def _assign_action(self, rows, d):
        """Traite l'action d'un menu « affecter » ; False si ce n'en est pas une."""
        if not (isinstance(d, str) and SEP in d):
            return False
        p = d.split(SEP)
        if p[0] == "X":
            self.assign_rows(rows, "", "")
        elif p[0] == "S" and len(p) == 2:
            self.assign_rows(rows, p[1], "")
        elif p[0] == "G" and len(p) == 3:
            self.assign_rows(rows, p[1], p[2])
        elif p[0] == "N" and len(p) == 2:
            r = self.add_group(p[1])
            if r:
                self.assign_rows(rows, r[0], r[1])
        elif p[0] == "NS":
            txt, ok = self.ask_name("scene", "Nouvelle scène", "Nom de la scène :")
            if ok and txt.strip():
                r = self.add_group(txt.strip())
                if r:
                    self.assign_rows(rows, r[0], r[1])
        return True

    def layer_popup(self, rows):
        m = self.assign_menu(self)
        act = m.exec(QtGui.QCursor.pos())
        if act is not None:
            self._assign_action(rows, act.data())

    def rename_layer(self, key):
        scene, group = key
        old = group if group else scene
        txt, ok = self.ask_name("scene" if group is None else "group", "Renommer", "Nouveau nom :", old)
        new = txt.strip()
        sc = self.scene_by_name(scene)
        if not ok or not new or new == old or sc is None:
            return
        if group is None:
            if self.scene_by_name(new) is not None:
                QtWidgets.QMessageBox.information(self, APP_NAME, "Une scène porte déjà ce nom.")
                return
            sc["name"] = new
            for w in self.watch:
                if w["scene"] == scene:
                    w["scene"] = new
            if self.scope:
                self.scope = [(new if k[0] == scene else k[0], k[1]) for k in self.scope]
        else:
            if any(g["name"] == new for g in sc["groups"]):
                QtWidgets.QMessageBox.information(self, APP_NAME, "Un groupe porte déjà ce nom dans cette scène.")
                return
            for g in sc["groups"]:
                if g["name"] == group:
                    g["name"] = new
            for w in self.watch:
                if w["scene"] == scene and w["group"] == group:
                    w["group"] = new
            if self.scope:
                self.scope = [(k[0], new if (k[0] == scene and k[1] == group) else k[1]) for k in self.scope]
        self._layers_changed()

    def delete_layer(self, key):
        scene, group = key
        sc = self.scene_by_name(scene)
        if sc is None:
            return
        if group is None:
            n = sum(1 for w in self.watch if w["scene"] == scene)
            msg = (f"Supprimer la scène « {scene} » et ses {len(sc['groups'])} groupe(s) ?\n"
                   f"Les {n} fréquence(s) restent dans ta liste, sans scène.")
        else:
            n = sum(1 for w in self.watch if w["scene"] == scene and w["group"] == group)
            msg = (f"Supprimer le groupe « {group} » ?\n"
                   f"Les {n} fréquence(s) restent dans la scène « {scene} », sans groupe.")
        if QtWidgets.QMessageBox.question(self, APP_NAME, msg) != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if group is None:
            self.scenes.remove(sc)
            for w in self.watch:
                if w["scene"] == scene:
                    w["scene"], w["group"] = "", ""
        else:
            sc["groups"] = [g for g in sc["groups"] if g["name"] != group]
            for w in self.watch:
                if w["scene"] == scene and w["group"] == group:
                    w["group"] = ""
        self._layers_changed()

    def pick_layer_color(self, key):
        scene, group = key
        sc = self.scene_by_name(scene)
        if sc is None:
            return
        tgt = sc if group is None else next((g for g in sc["groups"] if g["name"] == group), None)
        if tgt is None:
            return
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(tgt["color"]), self, "Couleur")
        if c.isValid():
            tgt["color"] = c.name()
            self._layers_changed()

    def layer_action(self, what):
        k = self._sel_layer_key()
        if k is None or self.scene_by_name(k[0]) is None:
            self.set_status("Sélectionne d'abord une scène ou un groupe dans l'arbre.")
            return
        if what == "rename":
            self.rename_layer(k)
        elif what == "delete":
            self.delete_layer(k)

    def layer_menu(self, pos):
        it = self.layer_tree.itemAt(pos)
        key = key_dec(it.data(0, Qt.ItemDataRole.UserRole)) if it is not None else None
        real = key is not None and self.scene_by_name(key[0]) is not None
        m = QtWidgets.QMenu(self)
        a_scene = m.addAction("＋ Nouvelle scène…")
        a_group = m.addAction("＋ Nouveau groupe…")
        a_imp = a_asg = a_ren = a_col = a_del = a_mu_on = a_mu_off = None
        rows = self._sel_rows()
        if real:
            m.addSeparator()
            a_imp = m.addAction("📥 Importer un CSV dans " + ("ce groupe…" if key[1] else "cette scène…"))
            if rows:
                a_asg = m.addAction(f"Affecter les {len(rows)} fréquence(s) sélectionnée(s) ici")
            m.addSeparator()
            lws = self.layer_ws(key)
            if lws:
                if not all(w.get("muted") for w in lws):
                    a_mu_on = m.addAction("💤 Tout éteindre (je sais) : pas d'alarme ABSENT")
                if any(w.get("muted") for w in lws):
                    a_mu_off = m.addAction("🔔 Tout rallumer")
            a_dup = m.addAction("⧉ Dupliquer ce groupe (sans les fréquences)" if key[1]
                                else "⧉ Dupliquer cette scène et ses groupes (sans les fréquences)")
            a_ren = m.addAction("Renommer…")
            a_col = m.addAction("Couleur…")
            sub = QtWidgets.QMenu("🔔 Priorité des alarmes" + (" (ce groupe)" if key[1] else " (tous ses groupes)"), m)
            a_prio = {sub.addAction(f"{lab}{'  ✔' if cur else ''}"): p
                      for p, lab, cur in ((2, "❗ Critique : son répété jusqu'à acquittement", self._cur_prio(key) == 2),
                                          (1, "Normale : bip à l'apparition", self._cur_prio(key) == 1),
                                          (0, "🔕 Info : pas de son", self._cur_prio(key) == 0))}
            m.addMenu(sub)
            rxm = m.addMenu("📻 Appareils de ce groupe (coordination)" if key[1] else "📻 Appareils de ses groupes (coordination)")
            rxm.setToolTipsVisible(True)
            cur_rx = self._cur_rxs(key)
            a_ = rxm.addAction("Aucun (réglages par défaut)")
            a_.setCheckable(True)
            a_.setChecked(not cur_rx)
            a_.triggered.connect(lambda *_, key_=key: self.set_group_rx(key_, ""))
            rxm.addSeparator()
            for k_, n_ in [(k, n) for k, n, _d, _w in rx_all()]:   # plusieurs possibles : coord entre appareils
                a_ = rxm.addAction(n_)
                a_.setCheckable(True)
                a_.setChecked(k_ in cur_rx)
                a_.triggered.connect(lambda *_, k_=k_, key_=key, a_=a_: self.toggle_group_rx(key_, k_, a_.isChecked()))
            if self.expert:                         # 7.61 : un modèle précis, avec sa bande (mode expert seulement)
                rxm.addSeparator()
                a_ = rxm.addAction("📚 Depuis la bibliothèque (avec sa bande)…")
                a_.setToolTip("Choisis le modèle exact (ex. SLX-D G58) : il est ajouté à ce groupe avec sa bande ;\n"
                              "Vérifier le plan, Coordonner et la fréquence de secours restent dans cette bande.")
                a_.triggered.connect(lambda *_, key_=key: self.pick_library_rx(key_))
            if self.expert and not key[1]:          # 📡 quel(s) tinySA surveille(nt) cette scène
                dm = m.addMenu("📡 Surveillée par")
                for d_ in self.dev_list():
                    a_ = dm.addAction(f"{dev_ord(d_)} tinySA ({self.dev_name(d_)})")
                    a_.setCheckable(True)
                    a_.setChecked(key[0] in self.dev_scenes.get(d_, []))
                    a_.triggered.connect(lambda *_, d_=d_, a_=a_, n_=key[0]: self.toggle_dev_scene(d_, n_, a_.isChecked()))
                dm.addSeparator()
                dm.addAction("📡 Mes tinySA et leurs scènes…").triggered.connect(lambda *_: self.open_devices())
            a_del = m.addAction("Supprimer")
        act = m.exec(self.layer_tree.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_scene:
            self.add_scene()
        elif act is a_group:
            if real:
                self.add_group(key[0])
            else:
                self.add_group()
        elif act is a_imp:
            self.import_into(key)
        elif act is a_asg:
            self.assign_rows(rows, key[0], key[1] or "")
        elif act is not None and act in (a_mu_on, a_mu_off):
            self.set_muted(self.layer_ws(key), act is a_mu_on)
        elif act is a_dup:
            self.duplicate_layer(key)
        elif act is a_ren:
            self.rename_layer(key)
        elif act is a_col:
            self.pick_layer_color(key)
        elif act is a_del:
            self.delete_layer(key)
        elif real and act in a_prio:
            self.set_prio(key, a_prio[act])

    def _cur_prio(self, key):
        """Priorité d'un groupe (ou de la scène si tous ses groupes sont identiques, sinon -1)."""
        sc = self.scene_by_name(key[0])
        if sc is None:
            return -1
        ps = {int(g.get("prio", 1)) for g in sc["groups"] if not key[1] or g["name"] == key[1]}
        return ps.pop() if len(ps) == 1 else -1

    def import_into(self, key):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Importer des fréquences", "", "CSV / texte (*.csv *.txt *.tsv);;Tous les fichiers (*)")
        for p in paths:
            self.open_import(decode_text(Path(p).read_bytes()), os.path.basename(p),
                             preset=(key[0], key[1] or ""))

    # ------------------------------------------------------ scan ciblé (focus)
    def scan_bands(self):
        """Bandes réellement balayées : zones ciblées autour de la couche active, sinon tes bandes."""
        return self._focus_bands if self._focus_bands else self.bands

    def _on_focus_toggled(self, on):
        self._refresh_focus()
        if on and self.scope:
            self.set_status("🎯 Scan ciblé : seules les zones autour des fréquences de la couche active sont "
                            "balayées. Repasse en Global pour tout revoir.")
        elif on:
            self.set_status("Le scan ciblé s'active dès qu'une scène ou un groupe est sélectionné.")

    def _refresh_focus(self):
        new = []
        if self.scope and self.focus_chk.isChecked():
            fr = [x for w in self.watch if self.in_scope(w) for x in block_points(w["freq"], w.get("bw"))]
            for i, (a, b, n) in enumerate(focus_plan(fr, self._cfg["points"])):
                new.append(dict(id=-100 - i, name=f"{a:.2f}–{b:.2f} MHz", start=a, stop=b,
                                step=round((b - a) * 1000.0 / (n - 1), 6), enabled=True))
        sig = [(b["start"], b["stop"], b["step"]) for b in new]
        if sig != self._focus_sig:
            with self.lock:
                self._focus_bands, self._focus_sig = new, sig
            self._bump()
            ids = {b["id"] for b in self.scan_bands()}
            for d in (self.latest, self.latest_t, self.maxhold, self.partial_data, self.history, self.unk_now):
                for k in [k for k in d if k != ZOOM_ID and k not in ids]:
                    d.pop(k, None)
            self._fit_x = True
            self.refresh_view_combo()
        self.update_estimate()

    # ------------------------------------------------- fréquences surveillées
    def _append_watch(self, name, freq, status="", thr=None, scene="", group="", bw=0.0):
        scene, group = (scene or "").strip(), (group or "").strip()
        if group and not scene:
            scene = DEFAULT_SCENE
        self.ensure_group(scene, group)
        band, cat = spectrum_info(freq, self.plan, self.tv)
        st_ = self.state_by_name(self.state_cur) if getattr(self, "state_cur", "") else None
        if st_ is not None and int(round(freq * 1000)) not in st_["keys"]:     # 📸 nouvelle = active dans l'état
            st_["keys"] = sorted(st_["keys"] + [int(round(freq * 1000))])
        self.watch.append(dict(name=name, freq=freq, status=status, level=None, max=None,
                               state=None, peak=None, since=0.0, sig=None, thr=thr,
                               occw=OccWindow(self.occ_combo.currentData() or 60), t_acc=None,
                               band=band, cat=cat, scene=scene, group=group, free_since=None, absent=False,
                               bw=float(bw or 0.0)))     # bw > 0 : bloc large (Spectera / WMAS), en MHz

    def sort_watch(self):
        self.watch.sort(key=lambda w: w["freq"])

    def is_keep_free(self, name):
        return bool(name) and any(s["name"] == name and s.get("free") for s in self.statuses)

    def _strong_changed(self):
        self.strong_line.setValue(self.strong_spin.value())
        self.strong_line.setVisible(self.strong_chk.isChecked())
        if not self.strong_chk.isChecked():
            now = time.time()
            for k in [k for k in self.alarms.active if k[0] == "FORT"]:
                self.alarms.clear(k, now)
            self._strong_src = {}

    def check_strong(self, bid, f, l):
        """Alarme ⚠ TROP FORT : un signal au-dessus du seuil « trop fort » dans la bande qui vient d'être balayée.
        Une alarme par MHz ; elle se termine quand ce MHz repasse 3 dB sous le seuil."""
        src = self._strong_src
        if bid in CALIB_IDS or not self.strong_chk.isChecked() or l is None or not len(l):
            return
        thr, now = self.strong_spin.value(), time.time()
        peaks = strong_peaks(f, l, thr)
        keep = {("FORT", int(round(pf))) for pf, _ in peaks}
        # fin d'alarme : seulement pour les MHz couverts par CE balayage (hystérésis 3 dB)
        for key in [k for k, b in src.items() if b == bid and k not in keep]:
            mhz = key[1]
            seg = l[(f >= mhz - 0.5) & (f <= mhz + 0.5)]
            if not len(seg) or seg.max() < thr - 3.0:
                self.alarms.clear(key, now)
                src.pop(key, None)
        new = None
        for pf, pl in peaks:
            key = ("FORT", int(round(pf)))
            src[key] = bid
            w = min(self.watch, key=lambda w_: abs(w_["freq"] - pf), default=None)
            near = w is not None and abs(w["freq"] - pf) <= max(0.3, (w.get("bw") or 0) / 2)
            name = f"{w['name']} (trop près ?)" if near else f"Signal {pf:.3f} MHz"
            seen = self.seen_by(pf)
            if self.alarms.raise_(key, "TROP FORT", name, pf, 2, now, pl, self.layer_text(w) if near else "",
                                  ("risque de décrochage" + (f" · {seen}" if seen else ""))):
                new = (name, pf, pl)
                self.log_event(dict(name=name, freq=pf, scene="", group="", note=f"> {thr:.0f} dBm"), pl, "TROP FORT")
        if new is not None:
            self._alarm_sound(2)
            self.set_status(f"⚠ TROP FORT : {new[0]} à {new[2]:.0f} dBm ({new[1]:.3f} MHz) — risque de saturation / "
                            f"décrochage des récepteurs.")
            self.refresh_alarms()

    def set_unit(self, unit):
        """Unité d'affichage des niveaux (dBm, dBµV, %). Les valeurs internes, fichiers et shows restent en dBm."""
        unit = unit if unit in UNIT_SUFFIX else "dbm"
        self.unit = LevelSpin.unit = LevelAxis.unit = unit
        if self.unit_combo.currentData() != unit:
            self.unit_combo.blockSignals(True)
            self.unit_combo.setCurrentIndex(max(0, self.unit_combo.findData(unit)))
            self.unit_combo.blockSignals(False)
        for sp_ in (self.thr_spin, self.weak_spin, self.strong_spin):
            sp_.setSingleStep(1.0)
            sp_.refresh()
        u = UNIT_SUFFIX[unit]
        ax = self.spec.getPlotItem().getAxis("left")
        self.spec.getPlotItem().setLabel("left", f"Niveau ({u})")
        ax.picture = None
        ax.update()
        for c, base_ in ((C_LVL, "Niveau"), (C_MAX, "Max"), (C_THR, "Seuil")):
            it = self.watch_table.horizontalHeaderItem(c)
            if it is not None:
                it.setText(base_ if unit == "dbm" else f"{base_} ({u})")
        for w in self.watch:
            w["sig"] = None
        self.update_watch_table(force=True)
        self.refresh_alarms()
        if self.wall is not None and self.wall.isVisible():
            self.wall.rebuild()

    def lvl(self, dbm, suffix=False):
        return fmt_level(dbm, self.unit, 1, suffix)

    def wall_is_fullscreen(self):
        return getattr(self, "_wall_full", None) is not None

    def wall_fullscreen(self, on, screen=None):
        """Plein écran du mur : il quitte son panneau pour une vraie fenêtre, et y revient en sortant."""
        if on and not self.wall_is_fullscreen():
            if screen is None:
                screen = self.wall.screen()                 # l'écran où est le mur (2ᵉ écran s'il y est)
            win_ = WallFullWindow(self)
            hold = QtWidgets.QLabel("🧱 Mur en plein écran — Échap ou F11 pour le ramener ici.")
            hold.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dock_wall.setWidget(hold)
            win_.layout().addWidget(self.wall)
            self.wall.show()                # le panneau le cache en le lâchant : sinon plein écran tout noir (7.6.0)
            self._wall_full = win_
            if screen is not None:
                win_.setScreen(screen)
                win_.move(screen.geometry().topLeft())
            win_.showFullScreen()
            win_.activateWindow()
            QtCore.QTimer.singleShot(150, self.wall.rebuild)
            self.wall.full_btn.setText("⛶ Quitter (Échap)")
        elif not on and self.wall_is_fullscreen():
            win_, self._wall_full = self._wall_full, None
            self.dock_wall.setWidget(self.wall)
            self.wall.show()
            win_.hide()
            win_.deleteLater()
            self.wall.full_btn.setText("⛶ Plein écran")
            self.dock_wall.show()
            self.dock_wall.raise_()
        self.wall.relayout()

    def wall_detach(self, on):
        """Mur dans sa propre fenêtre (taille libre à la souris) ou en onglet à côté du spectre."""
        d = self.dock_wall
        if self.wall_is_fullscreen():
            self.wall_fullscreen(False)
        d.show()
        if on and not d.isFloating():
            d.setFloating(True)
            if d.width() > 900 or d.height() > 650 or d.width() < 250:     # 1re fois : une taille de vignette
                d.resize(560, 380)
                g = self.frameGeometry()
                d.move(g.right() - 600, g.top() + 80)
        elif not on and d.isFloating():
            d.setFloating(False)
        d.raise_()
        d.activateWindow()
        self._wall_float_txt()

    def _wall_float_txt(self, *_):
        if self.wall is not None:
            self.wall.float_btn.setText("📌 Raccrocher" if self.dock_wall.isFloating() else "🗗 Détacher")

    def in_alarm(self, w):
        return bool(w.get("absent")) or (w.get("state") == "occ" and self.is_keep_free(w["status"]))

    def set_wall_rows(self, rows, show):
        for r in rows:
            if 0 <= r < len(self.watch):
                if show:
                    self.watch[r].pop("hide_wall", None)
                else:
                    self.watch[r]["hide_wall"] = True
        if self.wall is not None and self.wall.isVisible():
            self.wall.relayout()
            self.wall.refresh()

    def pick_wall(self):
        if not self.watch:
            self.set_status("La liste de fréquences est vide.")
            return
        dlg = WallPickDialog(self)
        if dlg.exec():
            shown = dlg.shown()
            self.set_wall_rows([i for i, on in shown.items() if on], True)
            self.set_wall_rows([i for i, on in shown.items() if not on], False)

    def edit_labels(self):
        dlg = LabelsDialog(self, self.sig_labels, self.sig_colors,
                           lambda k: self.tone_color(SIGNAL_TONES.get(k, "none")))
        if dlg.exec():
            self.sig_labels = dlg.values()
            self.sig_colors = dlg.colors()
            for w in self.watch:
                w["sig"] = None
            self.update_watch_table(force=True)
            self._update_markers()
            if self.wall is not None and self.wall.isVisible():
                self.wall.rebuild()

    def w_paused(self, w):
        """🎬 Groupe pas sur scène en ce moment (planning), 📸 fréquence hors de l'état actif, ou 💤 éteinte exprès :
        pas d'alarme ABSENT."""
        if w.get("off") or w.get("muted"):
            return True
        act, planned = self._plan_state
        return planning_paused(w.get("scene", ""), w.get("group", ""), act, planned)

    def sig_view(self, w):
        """(texte, ton, couleur) du signal de w selon son statut (voir signal_view)."""
        if w.get("off"):
            return "💤 en pause (état)", "none", self.theme["st_none"]
        if w.get("muted") and w["state"] in (None, "free"):
            return "💤 éteint (je sais)", "none", self.theme["st_none"]
        if w["state"] in (None, "free") and self.is_keep_on(w["status"]) and self.w_paused(w):
            return "💤 pas sur scène", "none", self.theme["st_none"]
        key, tone = signal_key(w["state"], self.is_keep_free(w["status"]), self.is_keep_on(w["status"]),
                               bool(w.get("absent")), bool(w.get("im")))
        txt, _t = signal_view(w["state"], self.is_keep_free(w["status"]), self.is_keep_on(w["status"]),
                              bool(w.get("absent")), bool(w.get("im")), self.sig_labels)
        return txt, tone, self.sig_colors.get(key) or self.tone_color(tone)

    def tone_color(self, tone):
        th = self.theme
        return {"ok": th["st_free"], "free": th.get("st_libre", LIBRE_COLOR), "bad": th["st_occ"],
                "warn": th["st_weak"]}.get(tone, th["st_none"])

    def state_color(self, st):
        return {"free": self.theme["st_free"], "weak": self.theme["st_weak"],
                "occ": self.theme["st_occ"]}.get(st, self.theme["st_none"])

    def status_color(self, name):
        for s in self.statuses:
            if s["name"] == name:
                return s["color"]
        return self.theme["st_none"]
