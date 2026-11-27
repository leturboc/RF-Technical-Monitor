# Plusieurs tinySA, calibration, sauvegarde ZIP, carte, page web, bandes, zoom. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenAppareils:
    """Plusieurs tinySA, calibration, sauvegarde ZIP, carte, page web, bandes, zoom. (méthodes de MainWindow, regroupées par thème.)"""

    # ------------------------------------------------------------ 2ᵉ tinySA
    def _build_dev2_box(self):
        box = QtWidgets.QGroupBox("Plusieurs tinySA (USB ou réseau) · noms")
        self.dev2_box = box
        f = QtWidgets.QFormLayout(box)
        self.dev2_chk = QtWidgets.QCheckBox("Utiliser un 2ᵉ tinySA")
        self.dev2_chk.setToolTip("Deux tinySA balayent en parallèle : chaque bande est faite par l'un ou l'autre\n"
                                 "(colonne « tinySA » des bandes). Cycle deux fois plus court, et si l'un décroche,\n"
                                 "l'autre reprend toutes les bandes (alarme ⚠ APPAREIL).")
        self.dev2_chk.toggled.connect(lambda *_: self._dev2_changed())
        self.div_chk = QtWidgets.QCheckBox("🔀 Fusion des mesures (diversity) : les deux balayent tout, on garde le meilleur")
        self.div_chk.setToolTip("Deux antennes espacées, une par tinySA : les deux balayent les MÊMES bandes et, pour\n"
                                "chaque fréquence, on garde le plus fort des deux (comme un récepteur diversity).\n"
                                "Fini les « absent » quand une antenne tombe dans un creux. Cycle pas plus court\n"
                                "qu'avec un seul tinySA. Calibre d'abord le 2ᵉ sur le 1er (⚖, même antenne).\n"
                                "Décoché : les deux se partagent les bandes (cycle deux fois plus court).")
        self.div_chk.toggled.connect(lambda *_: self._dev2_changed())
        self.dev2_addr = QtWidgets.QComboBox()
        self.dev2_addr.setEditable(True)
        self.dev2_addr.setToolTip("USB : choisis le port (COM4…).\nRéseau : adresse du PC où le tinySA est branché, "
                                  "ex. 192.168.1.20:5025\n(sur ce PC-là : 🔧 Outils › 📡 Relais réseau, ou "
                                  "RF-Technical-Monitor.exe --relais).")
        self.dev2_addr.lineEdit().setPlaceholderText("COM4  ou  192.168.1.20:5025")
        self.dev2_addr.currentTextChanged.connect(lambda *_: self._dev2_changed())
        self.dev2_off = QtWidgets.QDoubleSpinBox()
        self.dev2_off.setRange(-40.0, 40.0)
        self.dev2_off.setDecimals(1)
        self.dev2_off.setSuffix(" dB")
        self.dev2_off.setToolTip("Correction ajoutée aux mesures du 2ᵉ tinySA (en plus de l'offset général),\n"
                                 "pour aligner deux appareils qui ne lisent pas tout à fait pareil.")
        self.dev2_off.valueChanged.connect(lambda *_: self._dev2_changed())
        self.dev2_lbl = QtWidgets.QLabel("")
        self.dev2_lbl.setWordWrap(True)
        relay_btn = QtWidgets.QPushButton("📡 Relais réseau (sur le PC du 2ᵉ tinySA)…")
        relay_btn.setToolTip("Partage un tinySA branché sur CE PC pour qu'un autre PC l'utilise par le réseau.")
        relay_btn.clicked.connect(lambda *_: self.open_relay())
        self.dev1_name, self.dev2_name = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        for e, n in ((self.dev1_name, 1), (self.dev2_name, 2)):
            e.setPlaceholderText(f"tinySA {n}")
            e.setToolTip("Nom de position (Plateau, FOH, Scène B…) : affiché dans les alarmes, le journal\n"
                         "(« vu par … ») et les messages. Utile pour savoir quelle antenne a vu le signal.")
            e.textChanged.connect(lambda *_: self._dev_names_changed())
        f.addRow("Nom du 1er :", self.dev1_name)
        f.addRow(self.dev2_chk)
        f.addRow(self.div_chk)
        f.addRow("Nom du 2ᵉ :", self.dev2_name)
        net_btn = QtWidgets.QPushButton("🌐 Adresses enregistrées…")
        net_btn.setToolTip("Les adresses réseau du relais (Raspberry Pi, autre PC), une par Wi-Fi : ajouter, tester,\n"
                           "choisir pour le 1er ou le 2ᵉ tinySA.")
        net_btn.clicked.connect(lambda *_: self.open_net_profiles())
        f.addRow("Adresse :", self._row(self.dev2_addr, net_btn))
        f.addRow("Offset :", self.dev2_off)
        self.calib_btn = QtWidgets.QPushButton("⚖ Calibrer les autres tinySA sur le 1er…")
        self.calib_btn.setToolTip("Les deux tinySA doivent recevoir le MÊME signal (même antenne via un splitter, ou\n"
                                  "antennes côte à côte). Pendant ~20 s ils balayent la même bande, puis l'offset du\n"
                                  "2ᵉ est réglé pour qu'il lise comme le 1er. La surveillance reprend ensuite.")
        self.calib_btn.clicked.connect(lambda *_: self.start_calib())
        f.addRow(self.dev2_lbl)
        f.addRow(self.calib_btn)
        f.addRow(relay_btn)
        # tinySA 3 à 8 (une scène chacun, un Pi chacun…)
        self.devx_table = QtWidgets.QTableWidget(0, 4)
        self.devx_table.setHorizontalHeaderLabels(["Actif", "Nom", "Adresse", "Offset dB"])
        self.devx_table.verticalHeader().setVisible(False)
        self.devx_table.horizontalHeader().setStretchLastSection(False)
        self.devx_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.devx_table.setMinimumHeight(110)
        self.devx_table.setToolTip("Les tinySA en plus (3ᵉ à 8ᵉ) : un par scène, ou plusieurs sur une même scène.\n"
                                   "Adresse : port USB (COM5…), adresse réseau (192.168.1.21:5025) ou le NOM d'une "
                                   "adresse enregistrée.\nIl faut d'abord le 2ᵉ tinySA. Suppr retire la ligne choisie.")
        self.devx_table.itemChanged.connect(lambda *_: self._devx_from_table())
        del_key(self.devx_table, self.devx_del)
        self.devx_add_btn = QtWidgets.QPushButton("＋ Ajouter un tinySA")
        self.devx_add_btn.setToolTip("Un tinySA de plus (jusqu'à 8 en tout) : branché en USB sur ce PC (hub) ou en\n"
                                     "réseau (un Raspberry Pi par tinySA). Rattache-le ensuite à sa scène (📡 Scènes).")
        self.devx_add_btn.clicked.connect(lambda *_: self.devx_add())
        self.devx_del_btn = QtWidgets.QPushButton("Retirer")
        self.devx_del_btn.setToolTip("Retire le tinySA choisi dans le tableau.")
        self.devx_del_btn.clicked.connect(lambda *_: self.devx_del())
        f.addRow(QtWidgets.QLabel("<b>Autres tinySA (3ᵉ à 8ᵉ)</b>"))
        f.addRow(self.devx_table)
        f.addRow(self._row(self.devx_add_btn, self.devx_del_btn, None))
        self._dev2_form, self.relay_btn = f, relay_btn
        self.dev2_info = ""
        self._dev2_ports()
        return box

    def _devx_fill(self):
        t = getattr(self, "devx_table", None)
        if t is None:
            return
        t.blockSignals(True)
        t.setRowCount(len(self.devx))
        for r, x in enumerate(self.devx):
            on = QtWidgets.QTableWidgetItem(dev_ord(r + 2))
            on.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            on.setCheckState(Qt.CheckState.Checked if x.get("on") else Qt.CheckState.Unchecked)
            t.setItem(r, 0, on)
            t.setItem(r, 1, QtWidgets.QTableWidgetItem(x.get("name", "")))
            t.setItem(r, 2, QtWidgets.QTableWidgetItem(x.get("addr", "")))
            t.setItem(r, 3, QtWidgets.QTableWidgetItem(f"{float(x.get('offset', 0.0)):+.1f}"))
        t.resizeColumnToContents(0)
        t.blockSignals(False)

    def _devx_from_table(self):
        t = self.devx_table
        out = []
        for r in range(t.rowCount()):
            def txt(c):
                it = t.item(r, c)
                return it.text().strip() if it is not None else ""
            try:
                off = float(txt(3).replace(",", ".") or 0)
            except ValueError:
                off = self.devx[r].get("offset", 0.0) if r < len(self.devx) else 0.0
            it0 = t.item(r, 0)
            out.append(dict(on=it0 is not None and it0.checkState() == Qt.CheckState.Checked, name=txt(1),
                            addr=txt(2), offset=off))
        self.devx = devx_norm(out, MAX_DEVS)
        self._dev2_changed()

    def devx_add(self):
        if self.is_running():
            self.set_status("Arrête d'abord la surveillance pour ajouter un tinySA.")
            return
        if len(self.devx) >= MAX_DEVS - 2:
            self.set_status(f"Au plus {MAX_DEVS} tinySA en même temps.")
            return
        if not self.dev2.get("on"):
            self.dev2_chk.setChecked(True)          # le 2ᵉ d'abord
        self.devx.append(dict(on=True, addr="", name="", offset=0.0))
        self._devx_fill()
        self.devx_table.setCurrentCell(len(self.devx) - 1, 2)
        self._dev2_changed()
        self.set_status(f"{dev_ord(len(self.devx) + 1)} tinySA ajouté : saisis son adresse (COM5, 192.168.1.21:5025 ou le "
                        "nom d'une adresse enregistrée), puis rattache-le à sa scène (📡 Scènes).")

    def devx_del(self):
        if self.is_running():
            self.set_status("Arrête d'abord la surveillance pour retirer un tinySA.")
            return
        r = self.devx_table.currentRow()
        if not 0 <= r < len(self.devx):
            return
        d = r + 2
        self.devx.pop(r)
        # les n° suivants descendent d'un cran : leurs scènes suivent
        sc = {}
        for k, v in self.dev_scenes.items():
            if k == d:
                continue
            sc[k - 1 if k > d else k] = v
        self.dev_scenes = sc
        self._devx_fill()
        self._dev2_changed()

    def set_dev_offset(self, d, v):
        if d == 1:
            self.dev2_off.setValue(v)
        elif d >= 2 and d - 2 < len(self.devx):
            self.devx[d - 2]["offset"] = round(float(v), 1)
            self._devx_fill()
            self._bump()

    def resolve_addr(self, a):
        """Adresse d'un tinySA : telle quelle, ou celle d'une adresse enregistrée portant ce nom."""
        a = str(a or "").strip()
        return next((p["addr"] for p in getattr(self, "net_profiles", []) if p["name"].lower() == a.lower()), a)

    def _dev2_ports(self):
        cur = self.dev2_addr.currentText()
        self.dev2_addr.blockSignals(True)
        self.dev2_addr.clear()
        for p in serial.tools.list_ports.comports():
            tag = "  ✔ tinySA" if (p.vid == TINYSA_VID and p.pid == TINYSA_PID) else ""
            self.dev2_addr.addItem(f"{p.device}{tag}", p.device)
        for k in SDR_KINDS:
            self.dev2_addr.addItem(k, k)                 # V8 : « hackrf », « rtlsdr » (ou « hackrf:n° de série »)
        for p in getattr(self, "net_profiles", []):     # 🌐 adresses enregistrées (Raspberry Pi…)
            self.dev2_addr.addItem(f"{p['addr']}  · {p['name']}", p["addr"])
        self.dev2_addr.setEditText(cur)
        self.dev2_addr.blockSignals(False)

    def _read_dev2(self):
        txt = self.dev2_addr.currentText().replace("✔ tinySA", "").split("  · ")[0].strip()   # « COM4  ✔ tinySA » -> « COM4 »
        self.dev2.update(on=self.dev2_chk.isChecked(), addr=txt, offset=float(self.dev2_off.value()),
                         div=self.div_chk.isChecked())

    def _dev2_changed(self):
        self._read_dev2()
        self._bump()
        self.update_band_dev_col()
        self.update_dev2_label()
        self.update_estimate()

    def update_dev2_label(self):
        if not hasattr(self, "dev2_lbl"):
            return
        d = self.dev2
        if not d["on"]:
            self.dev2_lbl.setText("Désactivé : un seul tinySA balaye tout.")
            return
        kind, url = parse_device_addr(d["addr"])
        where = {"serial": f"USB {d['addr']}", "net": f"réseau {url.split('://', 1)[-1]}"}.get(
            kind, "⚠ adresse à saisir (COM4 ou 192.168.1.20:5025)")
        if self.demo_chk.isChecked():
            where = "démo"
        run = self.is_running()
        st = ("✔ en ligne" if self.dev_live[1] else "⚠ liaison perdue (nouvel essai…)") if run else "prêt"
        more = [d for d in self.dev_list() if d >= 2]
        if more:
            lm = self.live_mask()
            st += "\n" + " · ".join(f"{self.dev_name(d)} : " + (("✔" if lm[d] else "⚠ perdu") if run else "prêt")
                                    for d in more)
        cyc = "  ·  ".join(f"{self.dev_name(k)} : {v:.1f} s" for k, v in sorted(self.dev_cycle.items())) if run else ""
        div = ""
        if self.diversity_on():
            now = time.time()
            srcs = [s_ for _F, s_, t in self.div_src.values() if now - t < 60]
            sh = diversity_share(srcs, MAX_DEVS)
            div = "\n🔀 Diversity" + (" · meilleur niveau : " + " · ".join(f"{self.dev_name(d)} {sh[d]} %"
                                                                          for d in self.dev_list())
                                     if run and srcs else " : tous balayent toutes les bandes")
        self.dev2_lbl.setText(f"{where} · {st}" + (f" · {self.dev2_info}" if run and self.dev2_info else "")
                              + (f"\nCycle  {cyc}" if cyc else "") + div)

    def start_calib(self):
        """Les deux tinySA balayent la même bande quelques cycles ; l'offset du 2e est ajusté sur le 1er."""
        if self._calib is not None:
            self._calib_end("Calibration annulée.", popup=False)
            return
        if self.ndev() < 2 or not self.is_running() or not all(self.live_mask()[d] for d in self.dev_list()):
            QtWidgets.QMessageBox.information(self, APP_NAME, "Calibration : lance d'abord le balayage avec tous les "
                                              "tinySA en ligne (et le même signal sur toutes les antennes).")
            return
        if self._zoom is not None:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Coupe le zoom live avant de calibrer.")
            return
        bs = [b for b in self.scan_bands() if b["enabled"]]
        if not bs:
            return
        band = max(bs, key=lambda b: sum(1 for w in self.watch if b["start"] <= w["freq"] <= b["stop"]))
        with self.lock:
            self._calib = dict(band=dict(band), t0=time.time(), data={d: [] for d in self.dev_list()})
        self._bump()
        self.calib_btn.setText("⚖ Calibration en cours… (clic = annuler)")
        self.set_status(f"⚖ Calibration : les tinySA balayent tous « {band['name']} » ({CALIB_SWEEPS} fois chacun)…")

    def _calib_add(self, dev, f, l):
        cal = self._calib
        if cal is None:
            return
        cal["data"][dev].append((np.asarray(f), np.asarray(l)))
        if time.time() - cal["t0"] > CALIB_TIMEOUT:
            self._calib_end("⚠ Calibration abandonnée : trop long.")
            return
        if all(len(v) >= CALIB_SWEEPS for v in cal["data"].values()):
            ref = calib_maxhold(cal["data"][0], CALIB_SWEEPS)          # même nombre de balayages pour tous
            msgs, bad = [], []
            for d in sorted(cal["data"]):
                if d == 0:
                    continue
                oth = calib_maxhold(cal["data"][d], CALIB_SWEEPS)
                res = calib_offset(*ref, *oth) if (ref is not None and oth is not None) else None
                if res is None:
                    bad.append(self.dev_name(d))
                    continue
                delta, n, kind = res
                rep_ = calib_repeat(cal["data"][0], cal["data"][d], CALIB_SWEEPS)
                spread = f", répétabilité ±{rep_[1] / 2:.1f} dB" if rep_ is not None else ""
                new = max(-40.0, min(40.0, round(self.dev_offset(d) + delta, 1)))
                self.set_dev_offset(d, new)
                msgs.append(f"{self.dev_name(d)} {delta:+.1f} dB → offset {new:+.1f} dB (sur {n} points, base : {kind}"
                            f"{spread})")
            if not msgs:
                self._calib_end("⚠ Calibration impossible : pas assez de points communs.")
                return
            self._calib_end("⚖ Calibration faite : " + " · ".join(msgs)
                            + (f" · ⚠ pas assez de points communs : {', '.join(bad)}" if bad else "") + ".")

    def _calib_end(self, msg, popup=True):
        with self.lock:
            self._calib = None
        if msg.startswith("⚖"):     # audit 7.44 : offsets changés -> max hold / historique d'avant = autre échelle
            self.history.clear()
            self.reset_max()
        self._bump()
        self.calib_btn.setText("⚖ Calibrer les autres tinySA sur le 1er…")
        self.calib_msg = msg
        self.set_status(msg)
        if popup:                                  # la barre d'état est vite réécrite par le balayage
            QtWidgets.QMessageBox.information(self, APP_NAME, msg)

    # ------------------------------------------------- alertes téléphone / page web
    def export_bundle(self, path=None):
        """📦 7.63 : sauvegarde complète en un ZIP (pour l'archiver ou l'envoyer en cas de souci) : le show (fréquences,
        scènes, scans par lieu, historique…), la config SANS secrets, un diagnostic tout frais, et des 7 derniers jours :
        journaux, rapports, diagnostics, crash.log, garde.log. Pas les enregistrements de spectre (trop gros).
        -> chemin du ZIP ou None."""
        import zipfile
        now = datetime.now()
        if path is None:
            base = safe_filename(self.show_meta.get("name") or "TinySA", "TinySA")
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, TR("Sauvegarde complète (ZIP)"), str(Path.home() / f"{base}_sauvegarde_{now:%Y%m%d_%H%M}.zip"),
                "ZIP (*.zip)")
            if not path:
                return None
        try:
            diag = self.dump_diag("sauvegarde complète")
        except Exception:  # noqa: BLE001
            diag = None
        cand = []
        for folder, pat in ((self.log_dir, "journal_*.csv"), (self.log_dir / "rapports", "*.html"),
                            (self.log_dir / "diagnostic", "*.txt")):
            try:
                for p_ in Path(folder).glob(pat):
                    st = p_.stat()
                    cand.append((str(p_), st.st_size, st.st_mtime))
            except OSError:
                pass
        for p_ in (CRASH_PATH, GUARD_LOG):
            try:
                st = Path(p_).stat()
                cand.append((str(p_), st.st_size, now.timestamp()))   # toujours (petits, souvent utiles)
            except OSError:
                pass
        picked = bundle_pick(cand, now.timestamp())
        if diag is not None and str(diag) not in picked:
            picked.append(str(diag))
        cfg = self._collect_config(True)
        names = []
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                doc = show_doc(dict(cfg, map=self.map_for_show(cfg.get("map"))), self.show_meta, self.ref_curves,
                               APP_VER)
                z.writestr("show" + SHOW_EXT, json.dumps(doc, ensure_ascii=False, indent=1))
                z.writestr("config_sans_secrets.json", json.dumps(config_public(cfg), ensure_ascii=False, indent=1,
                                                                  default=str))
                for p_ in picked:
                    pp = Path(p_)
                    sub = "journaux" if pp.name.startswith("journal_") else pp.parent.name if pp.parent.name in (
                        "rapports", "diagnostic") else "journaux_appli"
                    arc = f"{sub}/{pp.name}"
                    z.write(p_, arc)
                    names.append(arc)
                readme = [f"{APP_NAME} {APP_VER} — sauvegarde complète du {now:%d/%m/%Y %H:%M}",
                          f"Show : {self.show_meta.get('name') or '(sans nom)'} · {len(self.watch)} fréquence(s)",
                          f"Python {sys.version.split()[0]} · Qt {QtCore.qVersion()} · {sys.platform}", "",
                          "show.tsashow : à rouvrir avec 🎪 Shows › Ouvrir un show.",
                          "config_sans_secrets.json : réglages (jetons, PIN et mots de passe retirés).", "",
                          "Fichiers :"] + [f"  {n}" for n in names]
                z.writestr("LISEZMOI.txt", "\n".join(readme) + "\n")
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, TR("Sauvegarde impossible :\n{}").format(e))
            return None
        self.set_status(TR("📦 Sauvegarde complète : {} ({} fichier(s) en plus du show).").format(path, len(names)))
        return path

    def history_track(self, who=None):
        """🕘 Compare la liste à la dernière fois et note les changements (qui : « PC » par défaut)."""
        rows = watch_rows(self.watch)
        if self._hist_rows is None:
            self._hist_rows = rows
            return 0
        if rows == self._hist_rows:
            return 0
        ch = watch_diff(self._hist_rows, rows)
        self._hist_rows = rows
        now = time.time()
        for x in ch:
            self.mod_history.append(dict(x, t=now, who=who or "PC"))
        del self.mod_history[:-HIST_MAX]
        if self._hist_dlg is not None:
            try:
                if self._hist_dlg.isVisible():
                    self._hist_dlg.fill()
            except RuntimeError:
                self._hist_dlg = None
        return len(ch)

    def open_history(self):
        """🕘 7.63 : historique des modifications de la liste (qui, quand, quoi)."""
        self.history_track()
        if self._hist_dlg is not None:
            try:
                self._hist_dlg.fill()
                self._hist_dlg.show()
                self._hist_dlg.raise_()
                return self._hist_dlg
            except RuntimeError:
                pass
        self._hist_dlg = HistoryDialog(self)
        self._hist_dlg.show()
        return self._hist_dlg

    # ------------------------------------------------------- 🗺 7.64 : carte du site
    def _map_cfg_dump(self):
        d = dict(getattr(self, "map_cfg", None) or map_cfg_norm(None))
        d.pop("bg_data", None)                     # l'image n'est embarquée que dans les shows (map_for_show)
        d.pop("bg_name", None)
        bg = self._map_scene.bg_item if getattr(self, "_map_scene", None) is not None else None
        if bg is not None:                         # le plan a pu être déplacé à la souris
            d["bg_pos"] = [round(bg.pos().x(), 1), round(bg.pos().y(), 1)]
        return d

    def map_for_show(self, m):
        """Carte à écrire dans un show / un ZIP : avec l'image du plan EMBARQUÉE (le show reste complet sur un autre
        PC ; le plan n'a plus besoin d'être au même chemin)."""
        m = dict(m or {})
        p_ = m.get("bg") or ""
        try:
            if p_ and Path(p_).is_file():
                return map_bg_embed(m, Path(p_).read_bytes(), Path(p_).name)
        except OSError:
            pass
        return m

    def _map_bg_restore(self):
        """Show ouvert sur ce PC : son plan embarqué est recopié dans Documents/RF Technical Monitor/Plans (si le chemin
        d'origine n'existe pas ici) ; config.json ne garde que le chemin."""
        m = self.map_cfg
        got = map_bg_extract(m)
        m.pop("bg_data", None)
        name = m.pop("bg_name", None)
        if not got:
            return
        data, name = got
        try:
            if m.get("bg") and Path(m["bg"]).is_file() and Path(m["bg"]).read_bytes() == data:
                return
            import hashlib
            d_ = SHOW_DIR.parent / "Plans"
            d_.mkdir(parents=True, exist_ok=True)
            dst = d_ / f"{hashlib.sha1(data).hexdigest()[:10]}_{name}"
            if not dst.is_file():
                dst.write_bytes(data)
            m["bg"] = str(dst)
        except OSError:
            pass

    def map_scene(self):
        if self._map_scene is None:
            self._map_scene = MapScene(self)
            self._map_scene.sync()
        return self._map_scene

    def open_map(self):
        """🗺 Carte du site : scènes et tinySA à glisser, liens, plan facultatif, carte de chaleur."""
        if self._map is not None:
            try:
                self._map.show()
                self._map.raise_()
                self._map.activateWindow()
                return self._map
            except RuntimeError:
                self._map = None
        if not self.map_cfg["pos"]:            # 1re ouverture : tout est posé d'office, on déplace ensuite
            self.map_cfg["pos"].update(map_auto_place(self.map_scene().keys_all(), {}))
        self._map = MapWindow(self)
        self._map.show()
        return self._map

    def map_png(self, maxw=900):
        """Image de la carte (pour le téléphone et l'export) -> (octets PNG, rectangle de carte représenté)."""
        sc = self.map_scene()
        if sc.unplaced():                          # 7.65 (audit) : nouvelle scène / nouveau tinySA posé même si la
            sc.auto_place()                        # carte du PC est fermée (sinon absent de l'image du téléphone)
        else:
            sc.sync()
        sc.refresh()                               # états à jour (refresh ne tourne d'habitude que fenêtre ouverte)
        r = sc.itemsBoundingRect()
        if r.isEmpty():
            return b"", None
        r = r.adjusted(-40, -40, 40, 40)
        k = min(1.0, maxw / max(1.0, r.width()))
        img = QtGui.QImage(max(1, int(r.width() * k)), max(1, int(r.height() * k)), QtGui.QImage.Format.Format_RGB32)
        img.fill(QtGui.QColor(self.theme["ui_bg"]))
        p = QtGui.QPainter(img)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        sc.render(p, QtCore.QRectF(0, 0, img.width(), img.height()), r)
        p.end()
        ba = QtCore.QByteArray()
        buf = QtCore.QBuffer(ba)
        buf.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        return bytes(ba), r

    def _map_web_tick(self, now):
        """PNG de la carte pour le téléphone (vue 🔎 Chasse), refait toutes les 5 s si quelqu'un regarde."""
        if self.web is None or now - self._map_png_t < 5.0 or not self.map_cfg["pos"]:
            return
        if not self.web.watching(("chasse",)):
            return
        self._map_png_t = now
        try:
            self._map_png, self._map_rect = self.map_png(900)
        except Exception:  # noqa: BLE001 — une image ratée ne doit pas gêner la surveillance
            self._map_png = b""

    def map_mark_rel(self, x, y):
        """📍 « Je suis ici » touché sur l'image du téléphone (x, y entre 0 et 1) -> point de chaleur, ou None."""
        r = self._map_rect
        if r is None:
            return None
        pt = self.map_scene().mark(r.left() + x * r.width(), r.top() + y * r.height())
        if pt is not None and self._map is not None:
            try:
                self._map.fill_heat()
            except RuntimeError:
                pass
        self._map_png_t = 0.0
        return pt

    def map_marks_rel(self):
        """Points de la chasse en cours, en coordonnées de l'image du téléphone (0..1)."""
        r, h = self._map_rect, self._hunt
        if r is None or h is None:
            return []
        f = h.f_spin.value()
        out = []
        pts = heat_for(self.map_cfg["heat"], f, 0.05)[-200:]
        lo, hi = heat_scale([p["level"] for p in pts])
        st = heat_stops(self.map_cfg.get("heat_pal", HEAT_PAL_DEFAULT), self.theme["ui_accent"])
        for p in pts:
            out.append(dict(x=round((p["x"] - r.left()) / max(1.0, r.width()), 4),
                            y=round((p["y"] - r.top()) / max(1.0, r.height()), 4), level=p["level"],
                            c=heat_hex(p["level"], lo, hi, st)))
        return out

    def open_qr(self):
        """📱 7.63 : QR code de la page web pour les téléphones de l'équipe."""
        if self._qr is not None:
            try:
                self._qr.fill()
                self._qr.show()
                self._qr.raise_()
                return self._qr
            except RuntimeError:
                pass
        self._qr = QrDialog(self)
        self._qr.show()
        return self._qr

    def open_alerts(self):
        dlg = AlertsDialog(self)
        if dlg.exec():
            n, w = dlg.values()
            self.notify_cfg.update(n)
            pw_changed = w.get("password", "") != self.web_cfg.get("password", "")
            tech_changed = w.get("tech", "") != self.web_cfg.get("tech", "")
            self.web_cfg.update(w)
            if pw_changed and self.web is not None:
                self.web.revoke_all()              # nouveau mot de passe : tout le monde se reconnecte
            elif tech_changed and self.web is not None:
                self.web.revoke_tech()             # nouveau mot de passe Tech : plus personne n'a l'accès
            self.apply_web()

    def send_notify(self, title, body, prio, cfg=None):
        """Met une alerte dans la file d'envoi. -> message d'erreur de réglage, ou "" si c'est parti."""
        c = cfg or self.notify_cfg
        lang = c.get("lang", "app")                       # langue des alertes : celle de l'appli, ou imposée
        tr = TR if lang == "app" else (en_translator() if lang == "en" else (lambda x: x))
        title, body = tr(title), tr(body)
        if c["service"] == "telegram":
            if not c["tg_token"] or not c["tg_chat"]:
                return "Telegram : jeton du bot et chat id requis."
            req = telegram_request(c["tg_token"], c["tg_chat"], title, body)
        else:
            if not c["topic"]:
                return "ntfy : choisis un nom de canal."
            req = ntfy_request(c["server"], c["topic"], title, body, prio)
        if self.notifier is None:
            self.notifier = Notifier()
        self.notifier.post(req)
        return ""

    def _notify_new_alarms(self):
        for a in list(self.alarms.active.values()):
            if a["id"] in self._notified:
                continue
            self._notified.add(a["id"])
            if notify_wanted(a["prio"], self.notify_cfg["mode"]):
                title, body = notify_text(a, self.notify_cfg.get("site", ""))
                self.send_notify(title, body, a["prio"])

    def web_json(self):
        rows = []
        for w in self.watch:
            txt, tone, c_ = self.sig_view(w)
            rows.append(dict(w, conflict=(w["state"] == "occ" and self.is_keep_free(w["status"])), sig_txt=txt,
                             paused=self.w_paused(w),
                             tone=tone, color=c_ if tone != "none" else "", level_txt="" if w["level"] is None else self.lvl(w["level"], suffix=True)))
        cyc = f"{self.last_cycle:.1f} s" if self.is_running() else ""
        site = self.notify_cfg.get("site", "")
        st = web_state(rows, self.alarms.listing(), dict(
            title=(f"RF Technical Monitor — {site}" if site else "RF Technical Monitor")
            + (" · 🧪 DÉMO (simulé)" if self.alarms.sim else ""), time=datetime.now().strftime("%H:%M:%S"),
            running=self.is_running(), cycle=cyc, ack=len(self.web_cfg.get("pin", "").strip()) >= 4, ver=APP_VER,
            hunt=self.hunt_state(), terrain=self.terrain_state(), health=self.health(),
            thr=round(float(self.thr_spin.value()), 1),
            # 7.56 : le spectre de la page web prend les couleurs du thème de l'appli (gamme Analyseur comprise)
            plot=dict(bg=self.theme["plot_bg"], fg=self.theme["plot_fg"], curve=self.theme["curve"],
                      mh=self.theme["maxhold"], thr=self.theme["thr"], crt=self.theme.get("plot_style") == "crt")))
        out = {"fr": json.dumps(st, ensure_ascii=False).encode("utf-8")}
        tr = en_translator()                              # chaque personne choisit sa langue sur la page
        for r in st["rows"]:
            r.update(state_txt=tr(r["state_txt"]), status=tr(r["status"]), alarm=tr(r["alarm"]))
        for a in st["alarms"]:
            a.update(kind=tr(a["kind"]), info=tr(a["info"]), hint=tr(a.get("hint") or ""))
        if st.get("health"):
            d_ = st["health"].get("data")
            st["health"] = dict(st["health"], text=tr(st["health"]["text"]),
                                data=dict(d_, text=tr(d_["text"])) if d_ else None)
        if st.get("hunt"):
            st["hunt"] = dict(st["hunt"], devs=[tr(x) for x in st["hunt"]["devs"]], msg=tr(st["hunt"].get("msg") or ""))
        if st.get("terrain"):
            st["terrain"] = dict(st["terrain"], msg=tr(st["terrain"].get("msg") or ""),
                                 devs=[dict(d, label=tr(d["label"])) for d in st["terrain"]["devs"]])
        out["en"] = json.dumps(st, ensure_ascii=False).encode("utf-8")
        return out

    def web_spec_json(self):
        """Spectre allégé pour les vues Spectre / Waterfall de la page web (une entrée par bande récente)."""
        now = time.time()
        stale = max(15.0, 4 * self.last_cycle)
        names = {b["id"]: b["name"] for b in self.scan_bands()}
        segs, t = [], 0.0
        for k in sorted((k for k in self.latest if k != ZOOM_ID and now - self.latest_t.get(k, 0) <= stale),
                        key=lambda k: float(self.latest[k][0][0]) if len(self.latest[k][0]) else 0.0):
            f, l = self.latest[k]
            segs.append((names.get(k, f"{f[0]:.0f}–{f[-1]:.0f} MHz"), f, l, self.maxhold.get(k)))
            t = max(t, self.latest_t.get(k, 0.0))
        scenes = {}
        if self.web is not None and self.web.watching(("terrain",)):      # 🎒 max hold de chaque scène
            for sc, bands in self.site_mh.items():
                parts = sorted(bands.values(), key=lambda x: float(x[0][0]))
                scenes[sc] = dict(color=self.scene_color(sc),
                                  segs=[dict(f=b["f"], l=b["l"]) for b in web_spectrum([(sc, F, L, None) for F, L in parts],
                                                                                        n_max=600)])
        return json.dumps(dict(t=round(t, 3), bands=web_spectrum(segs), scenes=scenes), ensure_ascii=False).encode("utf-8")

    def apply_web(self):
        want = self.web_cfg["on"]
        if self.web is not None and (not want or self.web.port != self.web_cfg["port"]):
            self.web.stop()
            self.web = None
        if want and self.web is None:
            self._web_json = self.web_json()
            ws = WebServer(self.web_cfg["port"], lambda lang="fr": self._web_json.get(lang, self._web_json["fr"]),
                           get_pin=lambda: self.web_cfg.get("pin", ""), on_ack=self._web_acks.put,
                           on_hunt=self._web_hunts.put, on_terrain=self._web_terrain.put,
                           on_tech=self._web_tech.put, on_tech_req=self._web_techreq.put,
                           get_tech=lambda: self._tech_json, get_map=lambda: self._map_png,
                           get_spec=lambda: self._web_spec, get_cfg=lambda: self.web_cfg, get_page=web_page_bytes,
                           default_lang=self.lang, extra_get=self.web_extra()[0], extra_pin=self.web_extra()[1])
            ws.start()
            ws.ready.wait(3)
            if ws.error:
                self.set_status(f"⚠ Page web : {ws.error}")
                return
            self.web = ws
            self.set_status("🌐 Page web active : " + self.web_urls_text())

    def web_urls_text(self):
        if self.web is None:
            return "Page web désactivée."
        ips = local_ips() or ["<adresse de ce PC>"]
        return "Adresse à ouvrir sur le téléphone : " + "  ou  ".join(f"http://{ip}:{self.web.port}" for ip in ips)

    def dev_name(self, d):
        if d >= 2:
            x = self.devx[d - 2] if d - 2 < len(self.devx) else {}
            return (x.get("name") or "").strip() or f"tinySA {d + 1}"
        n = (self.dev_names[d] if d < len(self.dev_names) else "").strip()
        return n or f"tinySA {d + 1}"

    def seen_by(self, f):
        """« vu par <nom> » : le tinySA qui a mesuré la fréquence f (MHz) en dernier, si deux appareils ; sinon ""."""
        if self.ndev() < 2:
            return ""
        if self.diversity_on():                    # 🔀 : le tinySA qui a donné le meilleur niveau à cette fréquence
            for bid, (F, src, t) in self.div_src.items():
                if len(F) and F[0] - 0.05 <= f <= F[-1] + 0.05 and time.time() - t < 60:
                    return f"meilleur : {self.dev_name(int(src[int(np.argmin(np.abs(F - f)))]))}"
        best = None
        for bid, (F, _L) in self.latest.items():
            if len(F) and F[0] - 0.05 <= f <= F[-1] + 0.05 and bid in self.band_src:
                t = self.latest_t.get(bid, 0)
                if best is None or t > best[0]:
                    best = (t, self.band_src[bid])
        return f"vu par {self.dev_name(best[1])}" if best else ""

    def _dev_names_changed(self):
        self.dev_names = [self.dev1_name.text().strip() or "tinySA 1", self.dev2_name.text().strip() or "tinySA 2"]
        self.update_dev2_label()

    def open_relay(self):
        if getattr(self, "_relay_win", None) is None:
            self._relay_win = RelayWindow()
        self._relay_win.show()
        self._relay_win.raise_()

    def update_band_dev_col(self):
        """Colonne « tinySA » de la table des bandes : choix (Auto / 1 / 2) et appareil réellement utilisé."""
        if not hasattr(self, "band_table"):
            return
        asg = self.band_devices() if self.ndev() > 1 else {}
        self._updating = True
        for r, b in enumerate(self.bands):
            if r >= self.band_table.rowCount():
                break
            d = b.get("dev")
            if self.ndev() == 1:
                txt = "1" if d is None else f"{d + 1}"
            else:
                real = asg.get(b["id"])
                txt = "Auto" if d is None else f"{d + 1}"
                if real == -1:                        # tous la balayent (🔀 diversity, ou tinySA à des scènes)
                    txt = " + ".join(str(d + 1) for d in self.dev_list())
                elif real is not None and (d is None or real != d):
                    txt += f" → {real + 1}"
            self.band_table.setItem(r, 5, self._item(txt))
        self._updating = False

    def on_band_dbl(self, row, col):
        if col != 5 or row >= len(self.bands):
            return
        b = self.bands[row]
        cyc = [None] + self.dev_list()
        with self.lock:
            b["dev"] = cyc[(cyc.index(b.get("dev")) + 1) % len(cyc)] if b.get("dev") in cyc else None
        self._bands_changed()

    def cut_band(self):
        r = self.band_table.currentRow()
        if r < 0 or r >= len(self.bands):
            self.set_status("Sélectionne d'abord la bande à couper.")
            return
        b = self.bands[r]
        (a1, m1, st), (m2, z2, _st) = split_band(b["start"], b["stop"], b["step"])
        if m1 - a1 < 1.0:
            self.set_status("Bande trop étroite pour être coupée.")
            return
        with self.lock:
            self.bands.pop(r)
            for d in (self.latest, self.maxhold, self.partial_data):
                d.pop(b["id"], None)
            for k, (lo, hi) in enumerate(((a1, m1), (m2, z2))):
                self.bands.insert(r + k, dict(id=self._next_id, name=f"{b['name']} ({'bas' if k == 0 else 'haut'})",
                                              start=lo, stop=hi, step=st, enabled=b["enabled"], dev=None))
                self._next_id += 1
        self._fit_x = True
        self._bands_changed()
        self.set_status(f"« {b['name']} » coupée en deux : {a1:g}–{m1:g} et {m2:g}–{z2:g} MHz.")

    # --------------------------------------------------------------- bandes
    def _append_band(self, name, start, stop, step, enabled=True, dev=None):
        with self.lock:
            self.bands.append(dict(id=self._next_id, name=name, start=start, stop=stop,
                                   step=step, enabled=enabled, dev=dev))
            self._next_id += 1

    def _bands_changed(self):
        self._auto_steps()                         # ⚡ Auto : le pas suit la largeur totale des bandes
        self._bump()
        live = {b["id"] for b in self.scan_bands() if b["enabled"]} | {ZOOM_ID} | set(CALIB_IDS)
        for d in (self.latest, self.maxhold, self.partial_data, self.history):
            for k in [k for k in d if k not in live]:
                d.pop(k, None)
        self.rebuild_band_table()
        self.refresh_view_combo()
        self.update_estimate()
        if self._zoom is None and hasattr(self, "wf_hint"):
            self._wf_show(self._wf_bid() is not None)      # une seule bande balayée : waterfall d'office (7.57)

    def _band_restore(self, b, old):
        with self.lock:
            b.update(name=old[0], start=old[1], stop=old[2])
        self._bands_changed()
        self.set_status(f"Bande remise sur {old[1]:g}–{old[2]:g} MHz.")

    def show_band(self, bid):
        """Vue sur une bande (réactivée si elle n'était pas balayée)."""
        b = next((x for x in self.bands if x["id"] == bid), None)
        if b is None:
            return
        if not b["enabled"]:
            self.set_band_enabled(bid, True)
        self.refresh_view_combo()
        ix = self.view_combo.findData(bid)
        if ix >= 0:
            self.view_combo.setCurrentIndex(ix)

    def new_band_dialog(self):
        """＋ Nouvelle bande à balayer depuis « Vue » : un préréglage ou une plage à la main, puis on l'affiche."""
        d = NewBandDialog(self)
        if not d.exec():
            return None
        name, lo, hi, step = d.values()
        self.add_band(name, lo, hi, step)
        bid = self.bands[-1]["id"]
        self.show_band(bid)
        self.set_status(f"＋ Bande « {name} » ajoutée ({lo:g}–{hi:g} MHz) et affichée.")
        return bid

    def add_band(self, name, start, stop, step, enabled=True):
        self._append_band(name, start, stop, step, enabled)
        self._bands_changed()

    def on_preset(self, idx):
        if idx > 0:
            p = self.preset_combo.itemData(idx)
            self.add_band(p[0], p[1], p[2], p[3])
        self.preset_combo.setCurrentIndex(0)

    def del_band(self):
        r = self.band_table.currentRow()
        if r < 0 or r >= len(self.bands):
            return
        if len(self.bands) <= 1:
            self.set_status("Il faut garder au moins une bande.")
            return
        with self.lock:
            b = self.bands.pop(r)
        for d in (self.latest, self.maxhold, self.partial_data):
            d.pop(b["id"], None)
        self._bands_changed()
        self.undo_track()
        self.set_status(f"Bande « {b['name']} » supprimée · Ctrl+Z pour annuler.")

    def points_auto(self):
        """Points par cycle visés en ⚡ Auto, ou None si un nombre fixe est choisi."""
        return AUTO_BUDGET.get(self.points_combo.currentData())

    def _auto_steps(self):
        """⚡ Auto : un même pas pour toutes les bandes, d'après leur largeur totale (et la RBW si elle est imposée).
        -> pas en kHz (None si pas en Auto). Les données des bandes dont le pas change sont oubliées."""
        self._auto_changed = False
        budget = self.points_auto()
        if budget is None:
            return None
        act = [b for b in self.bands if b["enabled"]] or self.bands
        total = sum(max(0.0, b["stop"] - b["start"]) for b in act)
        step = auto_scan_step(total, self.rbw_combo.currentData(), budget)
        with self.lock:
            for b in self.bands:
                if abs(b["step"] - step) > 1e-9:
                    b["step"] = float(step)
                    self._auto_changed = True
                    for d in (self.latest, self.maxhold, self.partial_data):
                        d.pop(b["id"], None)
        if self._auto_changed:
            self._bump()
        return step

    def apply_points(self, _=None):
        if self.points_auto() is not None:
            step = self._auto_steps()
            self._sync_cfg()
            self.rebuild_band_table()
            self.update_estimate()
            tot = sum(self._npts(b) for b in self.bands if b["enabled"])
            self.set_status(f"⚡ Points Auto : pas de {step:g} kHz sur toutes les bandes ({tot} points par cycle).")
            return
        pts = int(self.points_combo.currentData() or 1000)
        with self.lock:
            for b in self.bands:
                b["step"] = round((b["stop"] - b["start"]) * 1000.0 / (pts - 1), 6)
        self._update_pts_btn()
        self.latest.clear()
        self.maxhold.clear()
        self.partial_data.clear()
        self.rebuild_band_table()
        self._sync_cfg()
        self.set_status(f"{pts} points par bande (pas recalculé pour chaque bande).")

    def rebuild_band_table(self):
        self._updating = True
        t = self.band_table
        t.setRowCount(len(self.bands))
        for r, b in enumerate(self.bands):
            it = QtWidgets.QTableWidgetItem(b["name"])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable |
                        Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Checked if b["enabled"] else Qt.CheckState.Unchecked)
            t.setItem(r, 0, it)
            t.setItem(r, 1, self._item(f'{b["start"]:g}', True, True))
            t.setItem(r, 2, self._item(f'{b["stop"]:g}', True, True))
            t.setItem(r, 3, self._item(str(self._npts(b)), True, True))
            t.setItem(r, 4, self._item(f'{b["step"]:.4g}', True, True))
        self._updating = False
        self.update_band_dev_col()

    def on_band_edit(self, item):
        if self._updating or item.row() >= len(self.bands):
            return
        r, col, t = item.row(), item.column(), self.band_table
        name = t.item(r, 0).text()
        enabled = t.item(r, 0).checkState() == Qt.CheckState.Checked
        start, stop, step = (_num(t.item(r, c).text()) for c in (1, 2, 3 + 1))
        pts = _num(t.item(r, 3).text())
        if None in (start, stop, step, pts) or start < 0.1 or stop <= start or step <= 0 or pts < 2:
            QtCore.QTimer.singleShot(0, self.rebuild_band_table)
            return
        if col == 3:
            step = (stop - start) * 1000.0 / (int(pts) - 1)
        if col in (3, 4) and self.points_auto() is not None:
            self.points_combo.blockSignals(True)               # réglé à la main : plus d'Auto
            self.points_combo.setCurrentIndex(self.points_combo.findData(1000))
            self.points_combo.blockSignals(False)
            self._cfg["points_auto"] = False
            self.set_status("Points réglés à la main : ⚡ Auto désactivé.")
        b = self.bands[r]
        with self.lock:
            b.update(name=name, start=start, stop=stop, step=round(step, 6), enabled=enabled)
        if col != 0:
            for d in (self.latest, self.maxhold, self.partial_data):
                d.pop(b["id"], None)
        self._fit_x = True
        QtCore.QTimer.singleShot(0, self._bands_changed)

    def _build_pts_menu(self):
        m = self.pts_menu
        m.clear()
        cur = self.points_combo.currentData()
        grp = QtGui.QActionGroup(m)
        for i in range(self.points_combo.count()):
            k = self.points_combo.itemData(i)
            if i == len(AUTO_POINTS):
                m.addSeparator()
                hd = m.addAction("Nombre fixe par bande :")
                hd.setEnabled(False)
            a = m.addAction(self.points_combo.itemText(i) if k in AUTO_BUDGET else self.points_combo.itemText(i) + " pts")
            a.setCheckable(True)
            a.setChecked(k == cur)
            grp.addAction(a)
            a.triggered.connect(lambda *_, i=i: self.set_points_choice(i))

    def set_points_choice(self, i):
        self.points_combo.setCurrentIndex(i)
        self.apply_points()

    def _update_pts_btn(self):
        b = getattr(self, "pts_btn", None)
        if b is None:
            return
        if self.points_auto() is not None:
            st = next((x["step"] for x in self.bands if x["enabled"]), None)
            b.setText("⚡ Auto" + (f" · {st:g} kHz" if st else ""))
        else:
            b.setText(f"⚡ {self.points_combo.currentText()} pts")

    def _build_bands_menu(self):
        m = self.bands_menu
        m.clear()
        a = m.addAction("📶 Balayer toutes les bandes")
        a.triggered.connect(lambda *_: self.scan_all_bands())
        m.addSeparator()
        hd = m.addAction("Bandes balayées (cocher / décocher) :")
        hd.setEnabled(False)
        for b in self.bands:
            a = m.addAction(b["name"] + f"   {b['start']:g}–{b['stop']:g} MHz")
            a.setCheckable(True)
            a.setChecked(bool(b["enabled"]))
            a.toggled.connect(lambda *_, a=a, bid=b["id"]: self.set_band_enabled(bid, a.isChecked()))
        m.addSeparator()
        a = m.addAction("🎯 Ne balayer que la bande affichée dans « Vue »")
        a.setCheckable(True)
        a.setChecked(self.scan_follow)
        a.setToolTip("Choisis une bande dans « Vue » : seule celle-ci est balayée (beaucoup plus rapide).\n"
                     "« Toutes les bandes » dans « Vue » = toutes les bandes cochées.")
        a.toggled.connect(lambda *_, a=a: self.set_scan_follow(a.isChecked()))

    def set_band_enabled(self, bid, on):
        b = next((x for x in self.bands if x["id"] == bid), None)
        if b is None or bool(b["enabled"]) == bool(on):
            return
        if not on and sum(1 for x in self.bands if x["enabled"]) <= 1:
            self.set_status("Il faut garder au moins une bande à balayer.")
            return
        with self.lock:
            b["enabled"] = bool(on)
        self._bands_changed()
        n = sum(1 for x in self.bands if x["enabled"])
        self.set_status(f"{n} bande(s) balayée(s) sur {len(self.bands)}. Les fréquences des bandes non balayées "
                        f"ne sont plus surveillées.")

    def scan_all_bands(self):
        with self.lock:
            for b in self.bands:
                b["enabled"] = True
        self.scan_follow = False
        self._bands_changed()
        self.set_status("Toutes les bandes sont balayées.")

    def set_scan_follow(self, on):
        self.scan_follow = bool(on)
        self._bump()
        self.update_estimate()
        if on and self._follow_id() is None:
            self.set_status("Choisis maintenant une bande dans « Vue » : seule celle-ci sera balayée.")
        elif on:
            self.set_status("Seule la bande affichée est balayée. Les autres fréquences ne sont plus surveillées.")
        else:
            self.set_status("Toutes les bandes cochées sont de nouveau balayées.")

    def _follow_id(self):
        """Bande seule à balayer (mode « bande affichée »), sinon None."""
        if not self.scan_follow or self._zoom is not None:
            return None
        vid = getattr(self, "view_id", -1)
        return vid if any(b["id"] == vid and b["enabled"] for b in self.scan_bands()) else None

    def _scan_now(self, b):
        fid = self._follow_id()
        return bool(b["enabled"]) and (fid is None or b["id"] == fid)

    def refresh_view_combo(self):
        cur = self.view_combo.currentData()
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItem("Toutes les bandes", -1)
        for b in self.scan_bands():
            self.view_combo.addItem(b["name"], b["id"])
        off = [b for b in self.bands if not b["enabled"]]
        if off:
            self.view_combo.insertSeparator(self.view_combo.count())
            for b in off:                            # bandes pas balayées : les choisir les réactive
                self.view_combo.addItem(f"○ {b['name']} (pas balayée)", f"on:{b['id']}")
        self.view_combo.insertSeparator(self.view_combo.count())
        self.view_combo.addItem("＋ Nouvelle bande à balayer…", "__add__")
        self.view_combo.addItem("Gérer les bandes…", "__manage__")
        idx = self.view_combo.findData(cur) if cur is not None else 0    # None = séparateur : « Vue » restait vide
        self.view_combo.setCurrentIndex(max(idx, 0))
        self._view_prev = self.view_combo.currentIndex()
        self.view_combo.blockSignals(False)
        self.on_view_changed()

    def on_view_changed(self, *_):
        v = self.view_combo.currentData()
        if isinstance(v, str):                       # entrées d'action de la liste « Vue »
            self.view_combo.blockSignals(True)
            self.view_combo.setCurrentIndex(max(0, getattr(self, "_view_prev", 0)))
            self.view_combo.blockSignals(False)
            if v == "__add__":
                self.new_band_dialog()
            elif v == "__manage__":
                self.open_settings("bands")
            elif v.startswith("on:"):
                self.show_band(int(v[3:]))
            return
        self._view_prev = self.view_combo.currentIndex()
        if self._zoom is not None:
            return
        self.view_id = -1 if v is None else v
        if self.scan_follow:
            self._bump()
            self.update_estimate()
        self._wf_show(self._wf_bid() is not None)
        self.wf_hist, self.wf_id = None, None
        self._fit_x = True
        self.update_plot()

    # ----------------------------------------------------------- zoom live
    def toggle_zoom(self, on):
        if on:
            if self._last_xy is None:
                QtWidgets.QMessageBox.information(
                    self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer), zoome sur la zone qui "
                                    "t'intéresse, puis active le zoom live.")
                self.zoom_btn.setChecked(False)
                return
            vr = self.spec.getPlotItem().vb.viewRange()[0]
            self._set_zoom(vr[0], vr[1])
            self.view_id = ZOOM_ID
            self.view_combo.setEnabled(False)
            self._wf_show(True)
            self.zoom_timer.start()
            self.set_status("Zoom live : le tinySA scanne uniquement la zone visible. Zoome / déplace-toi, le "
                            "scan suit (les autres fréquences sont suspendues). " + self.zoom_info())
        else:
            if self._zoom is None:
                return
            self.zoom_timer.stop()
            with self.lock:
                self._zoom = None
            for d in (self.latest, self.maxhold, self.partial_data):
                d.pop(ZOOM_ID, None)
            self._bump()
            self.view_combo.setEnabled(True)
            self.on_view_changed()
            self.set_status("Zoom live désactivé.")

    def _band_extent(self):
        """Étendue des bandes balayées (min début, max fin) : le zoom live n'en sort pas."""
        bs = [b for b in self.scan_bands() if b["enabled"]] or self.bands
        if not bs:
            return 0.1, 6000.0
        return min(b["start"] for b in bs), max(b["stop"] for b in bs)

    def _set_zoom(self, a, b):
        self._zoom_view = (a, b)
        lo, hi = self._band_extent()
        a, b = max(0.1, lo, a), min(6000.0, hi, b)
        if b <= a:                                  # vue entièrement hors des bandes : on reste au bord
            a, b = (lo, min(hi, lo + 1.0)) if b <= lo else (max(lo, hi - 1.0), hi)
        if b - a < 0.05:
            mid = (a + b) / 2
            a, b = mid - 0.025, mid + 0.025
        with self.lock:
            self._zoom = (a, b)
        for d in (self.latest, self.maxhold, self.partial_data):
            d.pop(ZOOM_ID, None)
        self.wf_hist, self.wf_id = None, None
        self._bump()

    def zoom_follow(self):
        if self._zoom is None or self._zoom_view is None:
            return
        vr = self.spec.getPlotItem().vb.viewRange()[0]
        a, b = self._zoom_view
        tol = 0.02 * (b - a)
        if abs(vr[0] - a) > tol or abs(vr[1] - b) > tol:
            self._set_zoom(vr[0], vr[1])
            self.set_status(self.zoom_info())

    def zoom_info(self):
        """« 2.000 MHz · 201 points (pas 10.0 kHz) » : ce que scanne le zoom live."""
        z = self._zoom
        if not z:
            return ""
        c = self._cfg
        n = zoom_points(z[1] - z[0], c.get("zpts"), c["points"])
        step = (z[1] - z[0]) * 1000.0 / (n - 1)
        return f"Zoom : {z[1] - z[0]:.3f} MHz · {n} points (pas {step:.1f} kHz)"

    def zoom_on(self, row, half=1.0):
        if row >= len(self.watch):
            return
        if self._last_xy is None:
            self.set_status("Lance d'abord un balayage (▶ Démarrer) pour pouvoir zoomer.")
            return
        f = self.watch[row]["freq"]
        self.spec.getPlotItem().setXRange(f - half, f + half, padding=0)
        self._fit_x = False
        if not self.zoom_btn.isChecked():
            self.zoom_btn.setChecked(True)
        else:
            self._set_zoom(f - half, f + half)
