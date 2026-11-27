# Réglages, configuration, shows, ports, surveillance ▶ / ■, erreurs. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenConfig:
    """Réglages, configuration, shows, ports, surveillance ▶ / ■, erreurs. (méthodes de MainWindow, regroupées par thème.)"""

    def _style_start(self, running):
        self._keep_awake(running)
        t = self.theme
        col = t["st_occ"] if running else t["st_free"]
        hov = blend("#ffffff", col, 0.18)
        self.start_btn.setText("■ Arrêter" if running else "▶ Démarrer")
        self.start_btn.setStyleSheet(
            "QPushButton{background:%s;color:%s;font-weight:bold;padding:7px 24px;border-radius:5px;}"
            "QPushButton:hover{background:%s;}" % (col, contrast_text(col), hov))

    def set_status(self, txt):
        self.stat_lbl.setText(txt)

    # ------------------------------------------------------- configuration
    def _bump(self):
        self._ver += 1

    def get_ver(self):
        return self._ver

    def _sync_cfg(self, *_):
        c = dict(self._cfg)     # audit 7.44 : on prépare une copie, puis on la pose d'un coup sous le verrou
        c["rbw"] = self.rbw_combo.currentData()
        c["zrbw"] = self.zrbw_combo.currentData()
        c["zpts"] = self.zpts_combo.currentData()
        c["input"] = self.input_combo.currentData()
        c["lna"] = self.lna_combo.currentData()
        c["att"] = self.att_combo.currentData()
        c["offset"] = self.offset_spin.value()
        c["seg"] = self.seg_combo.currentData()
        pd_ = self.points_combo.currentData()
        c["points"] = int(pd_) if pd_ and pd_ > 0 else 1000
        c["points_auto"] = pd_ in AUTO_BUDGET
        c["points_sel"] = pd_
        with self.lock:
            self._cfg.update(c)
        c = self._cfg
        if c["points_auto"] and getattr(self, "bands", None) and self._auto_steps() is not None and self._auto_changed:
            self.rebuild_band_table()
            self.update_estimate()
        self.att_combo.setEnabled(c["lna"] is not True)
        self._bump()
        self._refresh_focus()

    @staticmethod
    def _npts(b):
        return max(2, int(round((b["stop"] - b["start"]) * 1000.0 / b["step"])) + 1)

    def update_estimate(self):
        seg = self._cfg["seg"] or getattr(self, "seg_known", None) or 290
        act = [b for b in self.scan_bands() if self._scan_now(b)]
        tot = sum(self._npts(b) for b in act)
        nseg = sum(len(segment_plan(self._npts(b), seg)) for b in act)
        pre = f"🎯 Scan ciblé ({len(act)} zone(s)) · " if self._focus_bands else ""
        txt = pre + f"{tot:,} points au total · {nseg} commande(s) de ≤ {seg} pts par cycle".replace(",", " ")
        if self.points_auto() is not None and act:
            txt += f" · ⚡ Auto : pas de {act[0]['step']:g} kHz"
        self._update_pts_btn()
        if nseg > 40:
            txt += "\n⚠ Cycle long : réduis les points ou la largeur des bandes."
        self.est_lbl.setText(txt)

    def dev_slots(self):
        """tinySA en service -> [(n°, adresse, offset)] ; n° fixe : 0 = 1er, 1 = 2ᵉ, 2… = 3ᵉ… (devx)."""
        out = [(0, None, 0.0)]
        if self.dev2.get("on"):
            out.append((1, self.dev2.get("addr", ""), float(self.dev2.get("offset", 0.0))))
        for k, x in enumerate(getattr(self, "devx", [])[:MAX_DEVS - 2]):
            if x.get("on"):
                out.append((k + 2, x.get("addr", ""), float(x.get("offset", 0.0))))
        return out

    def dev_list(self):
        """N° des tinySA en service (0 = le 1er toujours)."""
        return [d for d, _a, _o in self.dev_slots()]

    def ndev(self):
        """Nombre de tinySA en service."""
        return len(self.dev_list())

    def dev_offset(self, d):
        return next((o for d_, _a, o in self.dev_slots() if d_ == d), 0.0)

    def live_mask(self):
        """[bool] × MAX_DEVS : tinySA en service ET en ligne."""
        ids = set(self.dev_list())
        return [d in ids and (d >= len(self.dev_live) or bool(self.dev_live[d])) for d in range(MAX_DEVS)]

    def multi_site_on(self):
        return multi_site(self.dev_scenes, MAX_DEVS, self.live_mask())

    def diversity_on(self):
        """🔀 Diversity : 2 tinySA (deux antennes) balayent les mêmes bandes, on garde le meilleur niveau. Pas quand ils
        sont posés à deux scènes différentes (là, chacun juge sa scène)."""
        return (self.ndev() >= 2 and bool(self.dev2.get("div"))
                and not self.multi_site_on())

    def band_devices(self):
        """{id bande: n° du tinySA qui la balaye} (tout sur le 1er quand il n'y en a qu'un)."""
        bs = [b for b in self.scan_bands() if self._scan_now(b)]
        if self.ndev() == 1:
            return {b["id"]: 0 for b in bs}
        if self.multi_site_on() or self.diversity_on():
            return {b["id"]: -1 for b in bs}          # -1 = chaque tinySA balaye la bande (chez lui / 🔀 diversity)
        return assign_bands([dict(id=b["id"], pts=self._npts(b), dev=b.get("dev")) for b in bs],
                            MAX_DEVS, self.live_mask())

    def get_cfg(self, dev=0):
        with self.lock:
            c = self._cfg
            cal = self._calib
            if cal is not None and dev in cal["data"]:
                b = cal["band"]
                return dict(bands=[dict(id=CALIB_IDS[dev], name="Calibration", start_hz=b["start"] * 1e6,
                                        stop_hz=b["stop"] * 1e6, n=self._npts(b), enabled=True)],
                            rbw=c["rbw"], input=c["input"], lna=c["lna"], att=c["att"],
                            offset=c["offset"] + self.dev_offset(dev),
                            seg=c["seg"], demo_freqs=[w["freq"] for w in self.watch], ver=self._ver)
            if self._zoom:
                a, b = self._zoom
                n = zoom_points(b - a, c.get("zpts"), c["points"])
                step_khz = (b - a) * 1000.0 / (n - 1)
                bands = [dict(id=ZOOM_ID, name="Zoom", start_hz=a * 1e6, stop_hz=b * 1e6, n=n, enabled=True)]
                rbw = c["zrbw"] if c["zrbw"] is not None else auto_rbw(step_khz)
                ids, lm = self.dev_list(), self.live_mask()
                pref = self.zoom_dev if self.zoom_dev in ids else 0     # chasse : le tinySA choisi (ex. celui du Pi)
                zdev = pref if (len(ids) == 1 or lm[pref] or not any(lm)) else next(d for d in ids if lm[d])
                if dev != zdev:
                    # le zoom live est fait par un seul tinySA ; l'autre continue de surveiller toutes les bandes
                    bands = [dict(id=b["id"], name=b["name"], start_hz=b["start"] * 1e6, stop_hz=b["stop"] * 1e6,
                                  n=self._npts(b), enabled=True) for b in self.scan_bands() if b["enabled"]]
                    rbw = c["rbw"]
            else:
                asg = self.band_devices()
                bands = [dict(id=b["id"], name=b["name"], start_hz=b["start"] * 1e6, stop_hz=b["stop"] * 1e6,
                              n=self._npts(b), enabled=self._scan_now(b)) for b in self.scan_bands()
                         if asg.get(b["id"], 0) in (dev, -1)]
                rbw = c["rbw"]
            freqs = [w["freq"] for w in self.watch if not w.get("bw")]
            blocks = [(w["freq"], w["bw"]) for w in self.watch if w.get("bw") and self.is_keep_on(w["status"])]
            off = c["offset"] + self.dev_offset(dev)
            try:                                         # 8.0.3 : le démo du tinySA suit le plan du SDR démo
                plan = demo_sdr_plan(self.demo_mics()) if self.watch else None
            except Exception:  # noqa: BLE001
                plan = None
            return dict(bands=bands, rbw=rbw, input=c["input"], lna=c["lna"], att=c["att"],
                        offset=off, seg=c["seg"], demo_freqs=freqs, demo_blocks=blocks, ver=self._ver,
                        demo_plan=plan)

    def _load_config(self):
        data = {}
        for i, path in enumerate((CFG_PATH, CFG_BAK)):     # config abîmée : on reprend la copie de secours
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("config illisible")
                if i:
                    QtCore.QTimer.singleShot(500, lambda: self.set_status(
                        "⚠ Config abîmée : la copie de secours (sauvegarde automatique) a été rechargée."))
                break
            except FileNotFoundError:
                data = {}
            except Exception:  # noqa: BLE001
                data = {}
        self._apply_config(data, startup=True)
        g = data.get("geometry")
        if g:
            try:
                self.restoreGeometry(QtCore.QByteArray.fromBase64(g.encode()))
            except Exception:
                pass
        self._panel_cfg = data.get("panel_windows")         # vraies fenêtres : rouvertes après le 1er affichage
        st = data.get("docks")
        if int(data.get("layout_ver", 0) or 0) < LAYOUT_VER:
            st = None                    # ancienne disposition (spectre minuscule…) : on repart de la base
        if st:
            try:
                self._state_restored = bool(self.restoreState(QtCore.QByteArray.fromBase64(st.encode())))
            except Exception:
                pass

    def _apply_config_base(self, data, startup=False):
        """Applique un dictionnaire de réglages (config au démarrage, ou profil d'événement)."""
        if "rx_custom" in data:                  # profils d'appareil perso (avant la liste : w["rx"] y renvoie)
            rx_set_custom(data.get("rx_custom"))
        if not startup:
            with self.lock:
                self.bands.clear()
            self.watch.clear()
            self.scenes.clear()
            self.scope = None
            for d in (self.latest, self.latest_t, self.maxhold, self.partial_data, self.history, self.unk_now):
                d.clear()
            self.alarms.reset()
        for b in data.get("bands", []):
            try:
                dv = b.get("dev")
                self._append_band(b["name"], float(b["start"]), float(b["stop"]),
                                  float(b["step"]), bool(b.get("enabled", True)),
                                  dv if dv in (0, 1) else None)
            except Exception:
                pass
        if not self.bands:
            self._append_band("UHF 470–694 MHz", 470.0, 694.0, 200.0, True)
        sts = []
        for s in data.get("statuses", []):
            if isinstance(s, dict) and "name" in s and "color" in s:
                free = s.get("free", str(s["name"]).strip().lower() in ("libre", "free"))
                sts.append(dict(name=s["name"], color=s["color"], free=bool(free), on=bool(s.get("on", False))))
        if sts:
            if not any("on" in s0 for s0 in data.get("statuses", []) if isinstance(s0, dict)) \
                    and not any(x["name"].lower() == "en service" for x in sts):
                sts.append(dict(name="En service", color="#f1c40f", free=False, on=True))    # config d'avant la v7
            self.statuses = sts
        for sc in data.get("scenes", []):
            try:
                sn = str(sc["name"]).strip()
                if not sn:
                    continue
                self.ensure_group(sn)
                srow = self.scene_by_name(sn)
                if isinstance(sc.get("color"), str):
                    srow["color"] = sc["color"]
                for g in sc.get("groups", []):
                    gn = str(g["name"]).strip()
                    if not gn:
                        continue
                    self.ensure_group(sn, gn)
                    grow = next(x for x in srow["groups"] if x["name"] == gn)
                    if isinstance(g.get("color"), str):
                        grow["color"] = g["color"]
                    if g.get("prio") in (0, 1, 2):
                        grow["prio"] = int(g["prio"])
                    rxs = self.group_rxs(g)             # appareil(s) du groupe (facultatif ; ancien format : 1 clé)
                    if rxs:
                        grow["rx"] = rxs
            except Exception:
                pass
        for w in data.get("watch", []):
            try:
                thr = w.get("thr")
                self._append_watch(w["name"], float(w["freq"]), w.get("status", ""),
                                   None if thr is None else float(thr), str(w.get("scene", "") or ""),
                                   str(w.get("group", "") or ""))
                if w.get("hide_mk"):
                    self.watch[-1]["hide_mk"] = True
                if w.get("bw"):
                    self.watch[-1]["bw"] = max(0.0, float(w["bw"]))
                if w.get("hide_wall"):
                    self.watch[-1]["hide_wall"] = True
                if rx_profile(w.get("rx")) is not None:
                    self.watch[-1]["rx"] = w["rx"]          # profil d'appareil (🧮 Vérifier le plan)
                if w.get("iso"):
                    self.watch[-1]["iso"] = True             # 📸 toujours active, quel que soit l'état
                if w.get("muted"):
                    self.watch[-1]["muted"] = True           # 💤 éteinte exprès (je sais)
                if w.get("ez"):
                    self.watch[-1]["ez"] = str(w["ez"])[:200]   # 🔗 venue d'un plan .ezrf3 suivi
                    if w.get("ezsrc"):
                        self.watch[-1]["ezsrc"] = str(w["ezsrc"])[:200]   # … de quel fichier (7.50)
            except Exception:
                pass
        if "ezrf_link" in data:                  # 🔗 plan .ezrf3 suivi
            lk = data.get("ezrf_link")
            self.ezrf_link = dict(lk) if isinstance(lk, dict) and lk.get("path") else None
            if self.ezrf_link and self.ezrf_link.get("kind") == ".ezrf3":   # nom du format de 7.66.1 à 7.68.0
                self.ezrf_link["kind"] = "EazyRF"
        if "states" in data:                     # 📸 états (après la liste : l'état met ses fréquences en pause)
            self.states = states_norm(data.get("states"))
            cur = str(data.get("state_cur") or "")
            self.state_cur = ""
            self.apply_state(cur if any(x["name"] == cur for x in self.states) else "", quiet=True)
        sp = data.get("scope")
        if isinstance(sp, list):
            ks = []
            for k in sp:
                try:
                    ks.append((str(k[0]), None if k[1] in (None, "") else str(k[1])))
                except Exception:
                    pass
            self.scope = ks or None
        self.focus_chk.setChecked(bool(data.get("focus", False)))
        th = data.get("theme")
        if isinstance(th, dict) and not data.get("theme_v") and all(
                th.get(k) == v for k, v in OLD_DEFAULT_THEME.items()):
            th = None                             # 7.54 : l'ancien thème par défaut, jamais retouché -> « Pro sombre »
        if isinstance(th, dict) and int(data.get("theme_v") or 0) < 3:
            for _nm, _old in OLD_CRT_THEMES.items():   # 7.57.1 : thème analo d'avant -> autour neutre, spectre gardé
                if th.get("curve") == THEMES[_nm]["curve"] and all(th.get(k) == v for k, v in _old.items()):
                    th = dict(th, **{k: THEMES[_nm][k] for k in _old})
                    break
        if isinstance(th, dict):
            base = dict(THEMES[DEFAULT_THEME])
            base.update({k: v for k, v in th.items() if k in base and isinstance(v, str)})
            self.theme = base

        def setc(combo, key):
            if key in data:
                i = combo.findData(data[key])
                if i >= 0:
                    combo.setCurrentIndex(i)

        for combo, key in [(self.points_combo, "points"), (self.rbw_combo, "rbw"), (self.zrbw_combo, "zrbw"), (self.zpts_combo, "zpts"),
                           (self.input_combo, "input"), (self.lna_combo, "lna"), (self.att_combo, "att"),
                           (self.seg_combo, "seg"), (self.mark_combo, "mark"), (self.persist_combo, "persist"),
                           (self.occ_combo, "occ_minutes"), (self.country_combo, "country"),
                           (self.baud_combo, "baud")]:
            setc(combo, key)
        sel_ = data.get("points_sel", 0)               # pas encore de choix enregistré : ⚡ Auto équilibré
        if sel_ in AUTO_BUDGET:
            self.points_combo.setCurrentIndex(self.points_combo.findData(sel_))
            self._cfg["points_auto"] = True
        self.scan_follow = bool(data.get("scan_follow", False))
        if "site_scans" in data:
            self.site_scans = site_scans_norm(data.get("site_scans"))
        self.sites_coord = bool(data.get("sites_coord", self.sites_coord))
        if "dev_scenes" in data or "dev_sites" in data:      # dev_sites : réglage à un seul lieu (7.21.0)
            self.dev_scenes = dev_scenes_norm(data.get("dev_scenes", data.get("dev_sites")))
        di_ = data.get("devid_scenes")
        if isinstance(di_, dict):
            self.devid_scenes = {int(k): [str(x) for x in v] for k, v in di_.items()
                                 if str(k).isdigit() and isinstance(v, list)}
        QtCore.QTimer.singleShot(0, self.update_site_curve)
        if "planning" in data:
            self.planning = planning_norm(data.get("planning"))
            self._plan_next = 0.0
        self.sound.cfg = sound_cfg_norm(data.get("sound"))
        if isinstance(data.get("alarm_timing"), dict):      # 7.57 : rythme des alarmes du show / du profil
            self.sound.cfg = sound_cfg_norm(dict(self.sound.cfg, **{k: v for k, v in data["alarm_timing"].items()
                                                                    if k in ("confirm", "repeat")}))
        self.alarms.repeat_s = float(self.sound.cfg["repeat"])
        if "festival" in data:
            self.festival = festival_cfg_norm(data.get("festival"))
        pc = data.get("plan_custom")
        self.plan_custom = {k: v for k, v in pc.items() if isinstance(v, str)} if isinstance(pc, dict) else {}
        self.offset_spin.setValue(data.get("offset", 0.0))
        self.thr_spin.setValue(data.get("thr", -80))
        self.weak_spin.setValue(data.get("weak_thr", -90))
        self.weak_chk.setChecked(data.get("weak_on", True))
        self.win_spin.setValue(data.get("win", 100))
        self.absent_spin.setValue(int(data.get("absent_s", 20)))
        self.alert_chk.setChecked(data.get("alert", True))
        self.unk_chk.setChecked(data.get("unk", True))
        self.names_chk.setChecked(data.get("names", True))
        self.set_unit(str(data.get("unit", "dbm")))
        wc = data.get("watch_cols")
        if isinstance(wc, str) and wc and data.get("watch_cols_v") == WATCH_COLS_V:   # avant la colonne Marge : ignoré
            try:
                self.watch_table.horizontalHeader().restoreState(QtCore.QByteArray.fromBase64(wc.encode()))
            except Exception:  # noqa: BLE001
                pass
        lb = data.get("labels")
        if isinstance(lb, dict):
            self.sig_labels = {k: str(v)[:30] for k, v in lb.items() if k in SIGNAL_DEFAULTS and str(v).strip()}
        if "sig_colors" in data:
            self.sig_colors = clean_colors(data.get("sig_colors"))
        sd = data.get("sdr")
        if isinstance(sd, dict):
            for k_, cast in (("dir", str), ("lna", int), ("vga", int), ("amp", bool), ("rec_max_gb", int)):
                try:
                    if k_ in sd:
                        self.sdr_cfg[k_] = cast(sd[k_])
                except (TypeError, ValueError):
                    pass
            self.sdr_cfg.update(sdr_cfg_extra(sd))        # étape 7 : modèle, gains et corrections par modèle
        if data.get("port"):
            self._want_port = str(data["port"])
            ix = self.port_combo.findData(self._want_port)
            if ix >= 0:
                self.port_combo.setCurrentIndex(ix)
        po = data.get("plan_opts")
        if isinstance(po, dict):
            if rx_profile(po.get("prof")) is not None:
                self.plan_opts["prof"] = po["prof"]
            if po.get("coord_order") in dict(COORD_ORDERS):
                self.plan_opts["coord_order"] = po["coord_order"]
            if po.get("busy_mode") in dict(BUSY_MODES):
                self.plan_opts["busy_mode"] = po["busy_mode"]
            for k_, lo_, hi_ in (("busy_margin", 3.0, 40.0), ("busy_fixed", -130.0, 0.0)):
                try:
                    self.plan_opts[k_] = min(hi_, max(lo_, float(po[k_])))
                except (KeyError, TypeError, ValueError):
                    pass
            for k_ in ("sep", "filt", "step"):
                try:
                    self.plan_opts[k_] = float(po[k_]) if k_ == "filt" else int(po[k_])
                except (KeyError, TypeError, ValueError):
                    pass
        self.strong_chk.setChecked(bool(data.get("strong_on", True)))
        try:
            self.strong_spin.setValue(float(data.get("strong_thr", -25.0)))
        except (TypeError, ValueError):
            pass
        self._strong_changed()
        self.set_expert(bool(data.get("expert", False)))
        lv_ = data.get("ui_level")
        if lv_ in dict(UI_LEVELS):
            self.ui_level = lv_
        if "tour_done" in data:
            self.tour_done = bool(data.get("tour_done"))
        ix = self.wall.size_combo.findData(data.get("wall_size", "auto"))
        self.wall.size_combo.setCurrentIndex(max(0, ix))
        self.more_spec_btn.setChecked(bool(data.get("spec_more")))
        so = data.get("sections")
        if isinstance(so, dict):
            for k_, v_ in so.items():
                self.open_section(k_, bool(v_))
        mk, base = data.get("markers"), mk_default()
        if isinstance(mk, dict):
            ok_states = {k for k, _ in MK_STATES}
            for k in ("on", "alarms", "unk"):
                base[k] = bool(mk.get(k, base[k]))
            if mk.get("style") in ("full", "top"):
                base["style"] = mk["style"]
            if isinstance(mk.get("states"), list):
                base["states"] = [x for x in mk["states"] if x in ok_states]
            for k in ("hide_layers", "hide_status"):
                if isinstance(mk.get(k), list):
                    base[k] = [str(x) for x in mk[k]]
        self.mk = base
        self._sync_mk_menu()
        self.hold_chk.setChecked(data.get("hold", True))
        self.alloc_chk.setChecked(data.get("show_alloc", True))
        self.tv_chk.setChecked(data.get("show_tv", True))
        self.ref_chk.setChecked(data.get("ref_rel", False))
        self.ref_margin.setValue(data.get("ref_margin", 8.0))
        self.showref_chk.setChecked(data.get("show_ref", True))
        self.autolog_chk.setChecked(data.get("log_auto", True))
        ld = data.get("log_dir")
        if isinstance(ld, str) and ld:
            self.log_dir = Path(ld)
        self.logdir_lbl.setText(str(self.log_dir))
        ex = data.get("export")
        self.export_prefs = ex if isinstance(ex, dict) else {}
        if "smooth" in data:
            self.set_smooth(bool(data.get("smooth")))
        self.set_coord(bool(data.get("coord_tools", False)))
        self.reg_only = bool(data.get("reg_only", True))
        self.reg_chk.setChecked(self.reg_only)
        self.mod_history = history_norm(data.get("history"))       # 🕘 7.63
        self.map_cfg = map_cfg_norm(data.get("map"))              # 🗺 7.64
        self._map_bg_restore()
        if self._map_scene is not None:
            self._map_scene.sync()
        self._hist_rows = None                               # nouvelle référence au prochain tick (pas d'entrée)
        try:
            self.auto_occ_spin.setValue(int(data.get("auto_occ", AUTO_THR_DEFAULT[0])))
            self.auto_weak_spin.setValue(int(data.get("auto_weak", AUTO_THR_DEFAULT[1])))
        except (TypeError, ValueError):
            pass
        self.set_thr_auto(bool(data.get("thr_auto", getattr(self, "_first_run", False) if startup else self.thr_auto)))
        self.set_home(bool(data.get("home", True)))
        if isinstance(data.get("user_name"), str):
            self.user_name = data["user_name"][:60]
        if "tnt" in data:
            self.tnt_cfg = tnt_cfg_norm(data.get("tnt"))
            QtCore.QTimer.singleShot(0, self.tnt_mark_saved)
        if isinstance(data.get("user_presets"), list):      # 7.57 : préréglages perso du PC + ceux du show / profil
            self.user_presets = user_presets_merge(getattr(self, "user_presets", []), data["user_presets"])
        if isinstance(data.get("net_profiles"), list):      # adresses du PC + celles du show
            self.net_profiles = net_profiles_merge(self.net_profiles, data["net_profiles"])
        if "net_addr" in data:
            self.net_addr = str(data.get("net_addr") or "")[:120]
            self.port_net = bool(data.get("port_net")) and bool(self.net_addr)
            if not startup:
                self.refresh_ports()
        d2 = data.get("dev2")
        if isinstance(d2, dict):
            self.dev2_chk.setChecked(bool(d2.get("on")))
            self.div_chk.setChecked(bool(d2.get("div")))
            self.dev2_addr.setEditText(str(d2.get("addr", "")))
            try:
                self.dev2_off.setValue(float(d2.get("offset", 0.0)))
            except (TypeError, ValueError):
                pass
            self._read_dev2()
        for key, d in (("notify", self.notify_cfg), ("web", self.web_cfg)):
            v = data.get(key)
            if isinstance(v, dict):
                d.update({k: v[k] for k in d if k in v and isinstance(v[k], type(d[k]))})
        self.web_cfg["views"] = web_views_norm(self.web_cfg.get("views"))
        QtCore.QTimer.singleShot(0, self.apply_web)
        if "devx" in data:                       # tinySA 3 à 8
            self.devx = devx_norm(data.get("devx"), MAX_DEVS)
            self._devx_fill()
        dn = data.get("dev_names")
        if isinstance(dn, list) and len(dn) == 2:
            self.dev1_name.setText("" if dn[0] == "tinySA 1" else str(dn[0]))
            self.dev2_name.setText("" if dn[1] == "tinySA 2" else str(dn[1]))
            self._dev_names_changed()
        if startup:
            self.demo_chk.setChecked(data.get("demo", False))
            sm = data.get("show_meta")
            if isinstance(sm, dict):
                self.show_meta = {k: str(sm.get(k, "") or "") for k in SHOW_META}
            self.show_path = str(data.get("show_path") or "")
            rs = data.get("recent_shows")
            self.recent_shows = [str(x) for x in rs if isinstance(x, str)][:8] if isinstance(rs, list) else []
            self.session_cfg = session_cfg_norm(data.get("session"))
            self.log_kinds = log_kinds_norm(data.get("log_kinds"))
            self._sync_log_menu()
            if hasattr(self, "sess_ask_chk"):
                self.sess_ask_chk.blockSignals(True)
                self.sess_ask_chk.setChecked(self.session_cfg["ask"])
                self.sess_ask_chk.blockSignals(False)
            self.update_title()
            vu = data.get("vocab")
            if isinstance(vu, dict):
                self.vocab_user = {k: [x for x in vu.get(k, []) if isinstance(x, str)][:300]
                                   for k in ("name", "scene", "group")}
        else:
            self._after_apply()

    def _apply_config(self, data, startup=False):
        """Config -> fenêtre : la partie V7 (_apply_config_base), puis la V8 (repliée en 8.1 : postes SDR, sons des
        alarmes, réglage d'écoute et pilote par micro, plusieurs écrans)."""
        r = self._apply_config_base(data, startup)
        try:
            self._sdr_posts_sync()           # avant restoreState au démarrage : les panneaux des postes y sont replacés
        except Exception:  # noqa: BLE001
            pass
        try:                                 # étape 21 : sons des alarmes au choix
            if isinstance(data, dict) and "alarm_sounds" in data:
                self.sound.custom = alarm_sounds_norm(data.get("alarm_sounds"))
                for sp in self.sound.custom.values():
                    if sp["src"] == "wav":
                        wav_load(sp["path"])
        except Exception:  # noqa: BLE001
            pass
        try:                                 # étapes 19 / 20 : réglage d'écoute choisi à la main, pilote appris
            src = data.get("watch") if isinstance(data, dict) else None
            if isinstance(src, list) and len(src) == len(self.watch):
                for d_, w in zip(src, self.watch):
                    k_ = d_.get("demod") if isinstance(d_, dict) else None
                    if k_ and (demod_preset(k_) is not None or k_ == DEMOD_DIGITAL):
                        w["demod"] = k_
                    pl = d_.get("pilot") if isinstance(d_, dict) else None
                    if isinstance(pl, (int, float)) and 5000.0 <= float(pl) <= 120000.0:
                        w["pilot"] = float(pl)
        except Exception:  # noqa: BLE001
            pass
        if isinstance(data, dict) and "screens" in data:          # 8.0.2 : plusieurs écrans
            self.screens_cfg = screens_norm(data.get("screens"))
        if isinstance(data, dict) and "audio_ref" in data:        # 8.1 : échelles audio
            self.audio_ref = audio_ref_norm(data.get("audio_ref"))
        return r

    def _after_apply(self):
        self._fit_x = True
        self._sync_cfg()
        self.rebuild_plan()
        self.apply_theme()
        self.rebuild_band_table()
        self.refresh_view_combo()
        self.rebuild_watch_table()
        self.update_ref_curve()
        self.set_status("Profil chargé.")

    def _collect_config_base(self, full=True):
        c = self._cfg
        data = dict(
            bands=[{k: v for k, v in b.items() if k != "id"} for b in self.bands],
            watch=[dict(name=w["name"], freq=w["freq"], status=w["status"], thr=w["thr"],
                        scene=w["scene"], group=w["group"], **({"hide_mk": True} if w.get("hide_mk") else {}),
                        **({"bw": w["bw"]} if w.get("bw") else {}),
                        **({"hide_wall": True} if w.get("hide_wall") else {}),
                        **({"rx": w["rx"]} if w.get("rx") else {}),
                        **({"iso": True} if w.get("iso") else {}),
                        **({"muted": True} if w.get("muted") else {}),
                        **({"ez": w["ez"]} if w.get("ez") else {}),
                        **({"ezsrc": w["ezsrc"]} if w.get("ezsrc") else {}))
                   for w in self.watch],
            scenes=[dict(name=s["name"], color=s["color"],
                         groups=[dict(name=g["name"], color=g["color"], prio=int(g.get("prio", 1)),
                                      **({"rx": self.group_rxs(g)} if self.group_rxs(g) else {}))
                                 for g in s["groups"]])
                    for s in self.scenes],
            scope=[list(k) for k in self.scope] if self.scope else None,
            focus=self.focus_chk.isChecked(),
            rx_custom=rx_custom_dump(),
            statuses=[dict(name=s["name"], color=s["color"], free=bool(s.get("free")), on=bool(s.get("on")))
                      for s in self.statuses],
            theme=self.theme,
            scan_follow=self.scan_follow,
            site_scans=self.site_scans, sites_coord=self.sites_coord,
            dev_scenes={str(k): v for k, v in self.dev_scenes.items() if v},
            devid_scenes={str(k): v for k, v in self.devid_scenes.items()},
            planning=self.planning,
            sound=dict(self.sound.cfg),
            festival=dict(self.festival, was_running=bool(getattr(self, "_relaunch_resume", False)
                                                          or (self.is_running() and not self._closing))),
            points=c["points"], points_auto=bool(c.get("points_auto")),
            points_sel=self.points_combo.currentData(), rbw=c["rbw"], zrbw=c["zrbw"], zpts=c.get("zpts"), input=c["input"], lna=c["lna"],
            att=c["att"], seg=c["seg"], offset=c["offset"], mark=self.mark_combo.currentData(),
            baud=self.baud_combo.currentData(),
            persist=self.persist_combo.currentData(),
            thr=self.thr_spin.value(), weak_thr=self.weak_spin.value(), weak_on=self.weak_chk.isChecked(),
            win=self.win_spin.value(), alert=self.alert_chk.isChecked(), unk=self.unk_chk.isChecked(),
            absent_s=self.absent_spin.value(),
            names=self.names_chk.isChecked(), hold=self.hold_chk.isChecked(), markers=dict(self.mk),
            country=self.country_combo.currentData(), show_alloc=self.alloc_chk.isChecked(),
            show_tv=self.tv_chk.isChecked(), plan_custom=self.plan_custom,
            occ_minutes=self.occ_combo.currentData(), ref_rel=self.ref_chk.isChecked(),
            ref_margin=self.ref_margin.value(), show_ref=self.showref_chk.isChecked(),
            log_auto=self.autolog_chk.isChecked(), log_dir=str(self.log_dir), export=self.export_prefs,
            net_addr=self.net_addr, port_net=self.port_net, net_profiles=list(self.net_profiles),
            smooth=bool(getattr(self, "smooth", False)),
            coord_tools=bool(getattr(self, "coord_on", False)), reg_only=bool(getattr(self, "reg_only", True)), theme_v=3, tnt=dict(self.tnt_cfg), history=list(getattr(self, "mod_history", [])), map=self._map_cfg_dump(),
            user_presets=user_presets_norm(getattr(self, "user_presets", [])), user_name=getattr(self, "user_name", ""),
            alarm_timing=dict(confirm=int(self.sound.cfg.get("confirm", 3)), repeat=int(self.sound.cfg.get("repeat", 30))),
            thr_auto=bool(self.thr_auto), auto_occ=self.auto_occ_spin.value(), auto_weak=self.auto_weak_spin.value(),
            home=bool(getattr(self, "home_on", True)),
            dev2=dict(self.dev2), devx=[dict(x) for x in self.devx], states=[dict(x) for x in self.states],
            state_cur=self.state_cur, ezrf_link=dict(self.ezrf_link) if self.ezrf_link else None, dev_names=list(self.dev_names), web={k: v for k, v in self.web_cfg.items() if k not in ("pin", "password", "tech")},
            expert=self.expert, sections=dict(self.sections_open), spec_more=self.more_spec_btn.isChecked() is True, wall_size=self.wall.size_combo.currentData(),
            strong_on=self.strong_chk.isChecked(), strong_thr=self.strong_spin.value(), labels=dict(self.sig_labels),
            sig_colors=dict(self.sig_colors), plan_opts=dict(self.plan_opts), sdr=dict(self.sdr_cfg),
            port=self.port1() or "",
            unit=self.unit, watch_cols=bytes(self.watch_table.horizontalHeader().saveState().toBase64()).decode(),
            watch_cols_v=WATCH_COLS_V)
        if full:
            data["demo"] = self.demo_chk.isChecked()
            data["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
            data["docks"] = bytes(self.saveState().toBase64()).decode()
            data["panel_windows"] = self.panel_state()
            data["layout_ver"] = LAYOUT_VER
            data["vocab"] = self.vocab_user
            data["notify"] = dict(self.notify_cfg)     # pas dans les profils partagés (jeton Telegram)
            data["web"]["pin"] = self.web_cfg.get("pin", "")          # code PIN : idem
            data["web"]["password"] = self.web_cfg.get("password", "")
            data["web"]["tech"] = self.web_cfg.get("tech", "")       # 🛠 mot de passe Tech : jamais dans un show
            data["show_meta"] = dict(self.show_meta)
            data["show_path"] = self.show_path
            data["recent_shows"] = list(self.recent_shows)
            data["session"] = dict(self.session_cfg)
            data["ui_level"] = self.ui_level
            data["tour_done"] = bool(self.tour_done)
            data["log_kinds"] = dict(self.log_kinds)
            data["lang"] = self.lang
        return data

    def _collect_config(self, *a, **k):
        """Fenêtre -> config : la partie V7 (_collect_config_base), puis la V8 (repliée en 8.1)."""
        data = self._collect_config_base(*a, **k)
        try:                                 # étapes 19 / 20 : réglage d'écoute choisi à la main, pilote appris
            if isinstance(data.get("watch"), list) and len(data["watch"]) == len(self.watch):
                for d_, w in zip(data["watch"], self.watch):
                    if w.get("demod"):
                        d_["demod"] = w["demod"]
                    if isinstance(w.get("pilot"), (int, float)):
                        d_["pilot"] = float(w["pilot"])
            data["alarm_sounds"] = alarm_sounds_norm(getattr(self.sound, "custom", None))   # étape 21
        except Exception:  # noqa: BLE001
            pass
        try:
            data["screens"] = self.screens_state()                 # 8.0.2 : plusieurs écrans
        except Exception:  # noqa: BLE001
            pass
        data["audio_ref"] = audio_ref_norm(self.audio_ref)         # 8.1 : échelles audio (unité, alignement…)
        return data

    def _save_config(self):
        """Écriture sûre : fichier temporaire puis remplacement (une coupure de courant ne laisse jamais une
        config à moitié écrite), l'ancienne version gardée en .bak."""
        try:
            CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = CFG_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._collect_config(True), ensure_ascii=False, indent=1), encoding="utf-8")
            if CFG_PATH.exists():
                try:
                    os.replace(CFG_PATH, CFG_BAK)
                except OSError:
                    pass
            os.replace(tmp, CFG_PATH)
            return True
        except Exception:  # noqa: BLE001
            return False

    # --------------------------------------------------------------- shows
    def _build_show_menu(self):
        m = self.show_menu
        m.clear()
        cur = self.show_meta.get("name") or ""
        m.addAction("🆕 Nouveau show…").triggered.connect(lambda *_: self.new_show())
        m.addAction("📐 Nouveau show depuis un modèle (un show existant)…").triggered.connect(
            lambda *_: self.new_show_from_template())
        m.addAction("📂 Ouvrir un show…").triggered.connect(lambda *_: self.open_show_dialog())
        m.addAction("📦 Sauvegarde complète (ZIP : show, journaux, rapports)…").triggered.connect(
            lambda *_: self.export_bundle())
        m.addAction(f"💾 Enregistrer « {cur} »  (Ctrl+S)" if cur else "💾 Enregistrer le show…  (Ctrl+S)"
                    ).triggered.connect(lambda *_: self.save_show())
        m.addAction("💾 Enregistrer sous… (nouvelle édition, autre scène)").triggered.connect(
            lambda *_: self.save_show(as_new=True))
        m.addAction("📝 Infos du show (nom, lieu, dates, notes)…").triggered.connect(lambda *_: self.edit_show_info())
        rec = [p for p in self.recent_shows if Path(p).exists()]
        if rec:
            sub = m.addMenu("Récents")
            for pth in rec:
                sub.addAction(Path(pth).stem).triggered.connect(lambda *_, x=pth: self.open_show(x))
        m.addSeparator()
        m.addAction("Ouvrir le dossier des shows").triggered.connect(lambda *_: self.open_show_dir())

    def update_title(self):
        nm = self.show_meta.get("name") or ""
        yr = (self.show_meta.get("date_from") or "")[:4]
        show = f" — {nm}" + (f" {yr}" if yr and yr not in nm else "") if nm else ""
        self.setWindowTitle(f"{APP_NAME} {APP_VER}{show}" + (f" — {self.scope_text()}" if self.scope else "")
                            + (" — " + TR("🧪 DÉMO : données simulées") if getattr(self.alarms, "sim", False) else ""))

    def edit_show_info(self, title="Infos du show"):
        cur = getattr(self, "country", None) or self.country_combo.currentData() or "FR"
        dlg = ShowInfoDialog(self, self.show_meta, title, country=cur)
        if not dlg.exec():
            return False
        self.show_meta = dlg.values()
        self.update_title()
        new = dlg.country() if hasattr(dlg, "country") else None
        if new and (new != cur or title == "Nouveau show"):
            self.set_show_country(new, fresh=title == "Nouveau show")
        return True

    def set_show_country(self, code, fresh=False):
        """7.57 : pays du show -> plan du pays, bande UHF des micros balayée (ajoutée / réactivée si besoin),
        Vue posée dessus (toujours pour un nouveau show ; sinon seulement en « Toutes les bandes »)."""
        i_ = self.country_combo.findData(code)
        if i_ >= 0 and i_ != self.country_combo.currentIndex():
            self.country_combo.setCurrentIndex(i_)            # -> rebuild_plan
        need = uhf_band_needed(self.bands, code)
        if need and need[0] == "resize":                 # 7.58.3 : la bande « UHF … » suit le pays
            _k, bid, nm, lo, hi = need
            b = next((x for x in self.bands if x["id"] == bid), None)
            if b is not None:
                old = (b["name"], b["start"], b["stop"])
                with self.lock:
                    b.update(name=nm, start=lo, stop=hi)
                self._bands_changed()
                try:
                    self.show_hint("country:" + str(code),
                                   f"🌍 Bande recalée sur {lo:g}–{hi:g} MHz ({dict(COUNTRIES).get(code, code)}).",
                                   [("Annuler", lambda b=b, old=old: self._band_restore(b, old))])
                except Exception:  # noqa: BLE001
                    pass
        elif need and need[0] == "enable":
            self.set_band_enabled(need[1], True)
        elif need:
            _k, nm, lo, hi, st = need
            self._append_band(nm, lo, hi, st, True)
            self._bands_changed()
        if fresh and self._zoom is None:
            i_ = self.view_combo.findData(None)
            if i_ >= 0:
                self.view_combo.setCurrentIndex(i_)
        self.auto_view()
        nm_ = dict(COUNTRIES).get(code, code)
        lo, hi = country_uhf(code)
        self.set_status(f"🌍 Show en {nm_} : plan de fréquences du pays, bande UHF {lo:g}–{hi:g} MHz balayée et affichée.")

    def save_show(self, as_new=False):
        if not self.show_meta.get("name"):
            if not self.edit_show_info("Enregistrer le show"):
                return
            if not self.show_meta.get("name"):
                self.set_status("Donne un nom au show pour l'enregistrer.")
                return
        path = self.show_path
        if as_new or not path:
            try:
                SHOW_DIR.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Enregistrer le show", str(SHOW_DIR / show_filename(self.show_meta)), f"Show (*{SHOW_EXT})")
            if not path:
                return
            if not path.endswith(SHOW_EXT):
                path += SHOW_EXT
        self.save_show_to(path)

    def save_show_to(self, path):
        try:
            cfg_ = self._collect_config(False)
            cfg_["map"] = self.map_for_show(cfg_.get("map"))     # 🗺 7.65 : plan de fond dans le show
            doc = show_doc(cfg_, self.show_meta, self.ref_curves, APP_VER)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            tmp = Path(str(path) + ".tmp")                # écriture sûre : jamais de show à moitié écrit
            tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, path)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Impossible d'enregistrer le show :\n{e}")
            return False
        self.show_path = str(path)
        self._add_recent(self.show_path)
        self.update_title()
        self.set_status(f"🎪 Show enregistré : {path}")
        return True

    def _add_recent(self, path):
        self.recent_shows = [str(path)] + [p for p in self.recent_shows if p != str(path)]
        del self.recent_shows[8:]

    def open_show_dialog(self):
        dlg = ShowOpenDialog(self, [(SHOW_DIR, "*" + SHOW_EXT), (PROFILE_DIR, "*.json")])
        if dlg.exec() and dlg.path:
            self.open_show(dlg.path)

    def open_show(self, path, ask=True):
        try:
            doc = read_show(Path(path).read_text(encoding="utf-8"), Path(path).stem)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Show illisible :\n{e}")
            return False
        sm = show_summary(doc)
        if ask:
            r = QtWidgets.QMessageBox.question(
                self, APP_NAME, f"Ouvrir « {sm['name']} » ({sm['dates'] or 'sans date'}, {sm['n_freq']} fréquences) ?\n\n"
                                "Remplace les fréquences, scènes, bandes, statuts et seuils actuels.\n"
                                "Tes préférences (couleurs, fenêtres, alertes, 2ᵉ tinySA) ne bougent pas.")
            if r != QtWidgets.QMessageBox.StandardButton.Yes:
                return False
        self._apply_config(show_apply(self._collect_config(True), doc))
        self.auto_view()                             # 7.57 : Vue sur l'UHF du pays du show (si « Toutes les bandes »)
        if doc["ref"]:
            self._set_ref([(np.array(f), np.array(l)) for f, l in doc["ref"]])
            self._save_ref_file(REF_PATH)
        self.show_meta = dict(doc["meta"])
        legacy = str(path).endswith(".json")
        self.show_path = "" if legacy else str(path)    # un ancien profil sera enregistré en .tsashow
        if not legacy:
            self._add_recent(self.show_path)
        self.update_title()
        self.set_status(f"🎪 Show « {sm['name']} » ouvert : {sm['n_freq']} fréquences"
                        + (", courbe de référence du lieu chargée" if doc["ref"] else "") + ".")
        return True

    def new_show(self):
        r = QtWidgets.QMessageBox.question(
            self, APP_NAME, "Nouveau show : la liste de fréquences, les scènes, les groupes, les scans par lieu, la courbe "
                            "de référence et le max hold sont vidés.\n"
                            "Les bandes, statuts et seuils sont gardés comme point de départ.\n"
                            "Pense à enregistrer le show en cours avant (Ctrl+S). Continuer ?")
        if r != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.clear_show_data()

    def new_show_from_template(self, path=None):
        """📐 Nouveau show qui reprend la structure d'un show existant (scènes, groupes, appareils, statuts, bandes,
        réglages) sans ses fréquences ni ses scans."""
        if path is None:
            dlg = ShowOpenDialog(self, [(SHOW_DIR, "*" + SHOW_EXT), (PROFILE_DIR, "*.json")])
            dlg.setWindowTitle(TR("Choisir le show qui sert de modèle"))
            if not dlg.exec() or not dlg.path:
                return False
            path = dlg.path
        try:
            doc = show_template(read_show(Path(path).read_text(encoding="utf-8"), Path(path).stem))
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Show illisible :\n{e}")
            return False
        self.clear_show_data(template=doc)
        sc = doc["show"].get("scenes") or []
        self.set_status(TR("📐 Nouveau show d'après « {} » : {} scène(s), {} groupe(s) ; liste et scans vides.").format(
            doc["template"] or Path(path).stem, len(sc), sum(len(x.get("groups") or []) for x in sc)))
        return True

    def clear_show_data(self, template=None):
        """Nouveau show : tout ce qui appartient au show précédent part (liste, scènes, scans par lieu ET leur max hold
        en mémoire, référence, max hold), les réglages restent. Avant 7.31.1 les scans par lieu et la référence restaient
        sur le spectre (retour de Clément) et le max hold d'une scène recréait son scan 30 s plus tard."""
        data = self._collect_config(True)
        data.update(watch=[], scenes=[], scope=None, focus=False, site_scans=[], states=[], state_cur="", ezrf_link=None, history=[], map=None,
                    tnt=dict(self.tnt_cfg, place="", manual={}, plan=[], plan_src=""))
        self.tnt_mark(None)
        for k in list(self.site_mh):
            self.forget_site(k)
        self.dev_scenes = {d: [] for d in self.dev_scenes}
        data["dev_scenes"] = {}
        if template is not None:                   # 📐 7.62 : structure d'un show existant
            data = show_apply(data, template)
        self._apply_config(data)
        self.site_scans = []
        self._set_ref([])
        try:
            REF_PATH.unlink()
        except Exception:  # noqa: BLE001
            pass
        self.reset_max()
        self.reeval()
        self.update_site_curve()
        self.show_meta = {k: "" for k in SHOW_META}
        if template is not None:
            self.show_meta.update(venue=template["meta"].get("venue", ""))
        self.show_path = ""
        self.update_title()
        self.auto_view()                               # 7.57 : Vue directement sur l'UHF du pays
        self.edit_show_info("Nouveau show")
        self._hints_done, self._tnt_measured = set(), False
        try:
            self.open_wizard(1)                       # 7.59 : la suite pas à pas (étape 1 faite par la fenêtre d'infos)
        except Exception:  # noqa: BLE001
            pass

    def open_show_dir(self):
        try:
            SHOW_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(SHOW_DIR)))

    # --------------------------------------------------------------- profils (ancien format)
    def save_profile(self):
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Enregistrer le profil de l'événement", str(PROFILE_DIR / "evenement.json"), "Profil (*.json)")
        if not path:
            return
        try:
            data = self._collect_config(False)
            data["profil"] = APP_NAME
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            self.set_status(f"Profil enregistré : {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Impossible d'enregistrer le profil :\n{e}")

    def load_profile(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Charger un profil", str(PROFILE_DIR), "Profil (*.json);;Tous les fichiers (*)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not ("bands" in data or "watch" in data):
                raise ValueError("ce fichier ne ressemble pas à un profil")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Profil illisible :\n{e}")
            return
        r = QtWidgets.QMessageBox.question(
            self, APP_NAME, "Charger ce profil remplace les bandes, fréquences, statuts et réglages actuels.\n"
                            "Continuer ?")
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            self._apply_config(data)
            self.set_status(f"Profil chargé : {os.path.basename(path)}")

    def open_profile_dir(self):
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(PROFILE_DIR)))

    def refresh_ports(self):
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())
        ports.sort(key=lambda p: not (p.vid == TINYSA_VID and p.pid == TINYSA_PID))
        net = parse_device_addr(self.net_addr)[1] if self.net_addr else None
        # 🌐 adresses réseau : celle choisie la dernière fois en tête, puis les ports USB, puis les autres enregistrées
        nets = [(p["name"], p["addr"]) for p in getattr(self, "net_profiles", [])]
        if net and not any(parse_device_addr(a)[1] == net for _n, a in nets):
            nets.insert(0, ("", self.net_addr))

        def add_net(name, addr):
            self.port_combo.addItem(f"🌐 {name} — {addr}" if name else f"🌐 {addr} (réseau)", parse_device_addr(addr)[1])
        first = [x for x in nets if self.port_net and parse_device_addr(x[1])[1] == net][:1]
        for x in first:
            add_net(*x)
        for p in ports:
            tag = "  ✔ tinySA" if (p.vid == TINYSA_VID and p.pid == TINYSA_PID) else ""
            desc = str(p.description or "").replace(f" ({p.device})", "")      # 7.59 : « (COM4) » en double
            self.port_combo.addItem(f"{p.device} — {desc}{tag}", p.device)
        for x in nets:
            if x not in first:
                add_net(*x)
        if not ports and not nets:
            self.port_combo.addItem("Aucun port détecté", None)
        for k, sp in SDR_KINDS.items():                 # V8 : SDR par leur outil de balayage
            self.port_combo.addItem(f"📡 {sp['name']} ({sp.get('tool') or sp.get('dll')})", k)
        ix = self.port_combo.findData(getattr(self, "_want_port", None))
        if ix >= 0:
            self.port_combo.setCurrentIndex(ix)
        self.port_combo.addItem("🌐 tinySA en réseau : adresses enregistrées…", self.NET_ITEM)
        self.port_combo.blockSignals(False)

    def port1(self):
        """Adresse du 1er tinySA (port USB, ou « socket://… » en réseau), None si rien de choisi."""
        d = self.port_combo.currentData()
        return None if d in (None, self.NET_ITEM) else d

    def _port_chosen(self, *_):
        """Choix dans la liste des ports : « 🌐 tinySA en réseau… » demande l'adresse du relais (Raspberry Pi ou
        RF-Technical-Monitor.exe --relais) ; le 1er tinySA peut alors être dans le sac, loin du PC."""
        d = self.port_combo.currentData()
        if d != self.NET_ITEM:
            self.port_net = bool(d) and str(d).startswith("socket://")
            if self.port_net:                       # une adresse enregistrée : elle devient l'adresse du 1er tinySA
                p = next((x for x in self.net_profiles if parse_device_addr(x["addr"])[1] == d), None)
                if p is not None:
                    self.net_addr = p["addr"]
                    self.set_status(f"🌐 1er tinySA : {p['name']} ({p['addr']}). ▶ Démarrer pour s'y connecter.")
                self._bump()
            return
        self.open_net_profiles()

    def open_net_profiles(self):
        """🌐 Adresses réseau des tinySA (une par Wi-Fi / lieu) : ajouter, tester, choisir pour le 1er ou le 2ᵉ."""
        if not self.net_profiles and self.net_addr:          # la 1re fois : l'adresse déjà utilisée devient une entrée
            self.net_profiles = net_profiles_norm([dict(name="Pi", addr=self.net_addr)])
        NetProfilesDialog(self).exec()
        self.refresh_ports()
        if not self.port_net:
            ix = self.port_combo.findData(self.NET_ITEM)
            if self.port_combo.currentIndex() == ix:
                self.port_combo.setCurrentIndex(0)
        self._save_config()

    def use_net_addr(self, addr):
        """Le 1er tinySA passe sur cette adresse réseau (choisie dans la liste des ports)."""
        kind, url = parse_device_addr(addr)
        if kind != "net":
            return False
        self.net_addr, self.port_net = addr.strip(), True
        self.refresh_ports()
        ix = self.port_combo.findData(url)
        self.port_combo.setCurrentIndex(max(0, ix))
        self._bump()
        self.set_status(f"🌐 1er tinySA en réseau : {addr} (relais sur le port {RELAY_PORT} par défaut). "
                        "▶ Démarrer pour s'y connecter.")
        return True

    # ----------------------------------------------------------- run / stop
    def is_running(self):
        return any(w.isRunning() for w in self.workers)

    def _retire_workers(self):
        """Avant de recréer les fils de balayage (crash.log de Clément, 16/11/2026 : « access violation » dans
        ScanWorker.run, boucle de reconnexion → objet du fil détruit alors qu'il tournait encore ; ses mesures se
        mélangeaient aux nouvelles) : un ancien fil encore vivant est arrêté, rendu muet (plus aucune mesure prise en
        compte) et gardé jusqu'à sa fin ; un fil terminé est libéré proprement."""
        keep = []
        for w in list(getattr(self, "_zombies", [])) + list(self.workers):
            try:
                if w.isRunning():
                    w.requestInterruption()
                    w.blockSignals(True)
                    keep.append(w)
                elif w.parent() is self:
                    w.deleteLater()
            except RuntimeError:                      # objet déjà détruit côté Qt
                pass
        self._zombies = keep

    def toggle_run(self, auto=False):
        if self.is_running():
            for w in self.workers:
                w.requestInterruption()
            self.start_btn.setEnabled(False)
            self.set_status("Arrêt en cours…")
            QtCore.QTimer.singleShot(STOP_FORCE_MS, self._force_stop)
            return
        demo = self.demo_chk.isChecked()
        port = self.port1()
        self._last_problem = None                  # nouvel essai : l'ancien souci est oublié (revient s'il persiste)
        self._run_t0 = time.time()                 # accueil : seules les mesures d'après ▶ Démarrer comptent
        if not demo and not port:
            self.show_problem(key="no_port")
            return
        if not any(b["enabled"] for b in self.bands):
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Coche au moins une bande à balayer.")
            return
        if not self._session_prompt(auto):
            return
        self._read_dev2()
        targets = [(0, port, "")]
        if self.ndev() > 1:
            targets = [(0, port, self.dev_name(0))]
            seen_addr = {port}
            for d, addr, _off in self.dev_slots()[1:]:
                kind, url = parse_device_addr(self.resolve_addr(addr))
                if not demo and kind is None:
                    QtWidgets.QMessageBox.warning(self, APP_NAME, f"Adresse du {dev_ord(d)} tinySA illisible.\nExemples : "
                                                  "COM4 (USB) · 192.168.1.20:5025 (réseau, relais lancé sur l'autre PC).")
                    return
                if not demo and url in seen_addr:
                    QtWidgets.QMessageBox.warning(self, APP_NAME, f"Le {dev_ord(d)} tinySA a la même adresse qu'un autre.")
                    return
                seen_addr.add(url)
                targets.append((d, url, self.dev_name(d)))
        self.dev_live = [d in self.dev_list() for d in range(MAX_DEVS)]
        self.dev_cycle = {}
        self.band_src = {}
        self.div_buf, self.div_src = {}, {}
        self._retire_workers()
        self.workers = []
        for i, addr, label in targets:
            w = ScanWorker(addr, demo, (lambda d=i: self.get_cfg(d)), self.get_ver, label)
            w.slot = i                                    # n° fixe du tinySA (0 = 1er, 1 = 2ᵉ, 2… = 3ᵉ…)
            w.setParent(self)                             # 7.66.2 : jamais détruit par Python tant qu'il tourne
            w.retry_first = (i > 0 or str(addr).startswith("socket://")      # en réseau, il peut arriver après
                             or os.environ.get("TSM_GUARD_RESTART") == "1")  # relance : l'ancienne libère le port
            w.baud = int(self.baud_combo.currentData() or 115200)
            w.sdr_dir = self.sdr_cfg.get("dir", "")
            w.get_sdr = lambda w=w: self.sdr_gains((parse_sdr_addr(w.port) or ("",))[0])
            w.sweep.connect(lambda bid, f, l, d=i: self.band_src.__setitem__(bid, d))
            w.sweep.connect(self.on_sweep)
            w.partial.connect(self.on_partial)
            w.cycle.connect(lambda dt, nb, d=i: self.on_cycle(dt, nb, d))
            w.status.connect(self.set_status)
            w.info.connect(lambda txt, d=i: self.on_info(txt, d))
            w.devid.connect(lambda n, d=i: self.on_devid(d, n))
            w.error.connect(lambda msg, d=i: self.on_error(msg, d))
            w.link.connect(lambda ok, d=i: self.on_link(d, ok))
            w.finished.connect(self.on_finished)
            self.workers.append(w)
        self.worker = self.workers[0]
        self._bump()
        for w in self.workers:
            w.start()
        self._style_start(True)
        self.port_combo.setEnabled(False)
        self.demo_chk.setEnabled(False)
        for wd in (self.dev2_chk, self.dev2_addr, self.devx_table, self.devx_add_btn, self.devx_del_btn):
            wd.setEnabled(False)
        self.update_dev2_label()

    def _force_stop(self):
        """Le tinySA ne rend pas la main : on ferme les ports pour débloquer l'arrêt."""
        stuck = [w for w in self.workers if w.isRunning()]
        if not stuck:
            return
        for w in stuck:
            w.force_close()
        self.set_status("Arrêt forcé : le tinySA ne répondait plus (port fermé). Rebranche-le si le prochain "
                        "démarrage échoue.")
        QtCore.QTimer.singleShot(3000, lambda: self.on_finished() if not self.is_running() else None)

    def _net_tick(self, now):
        """🌐 Toutes les 2 s : débit et délai de réponse de chaque tinySA en réseau, à côté de sa version."""
        if now < getattr(self, "_net_next", 0):
            return
        self._net_next = now + 2.0
        st = getattr(self, "_net_last", {})
        for i, w in enumerate(self.workers):
            d = getattr(w, "dev", None)
            if d is None or not getattr(d, "net", False) or not w.isRunning():
                self._net_txt[i] = ""
                continue
            tot = d.rx_bytes + d.tx_bytes
            t0, b0 = st.get(i, (now, tot))
            self._net_txt[i] = net_text(tot - b0, now - t0, d.rtt) if now > t0 else ""
            st[i] = (now, tot)
            self._show_info(i)
        self._net_last = st

    def _show_info(self, dev):
        net = self._net_txt.get(dev, "")
        txt = self._info_base.get(dev, "") + (f"  ·  {net}" if net else "")
        if dev == 0:
            self.info_lbl.setText(f"  {txt}")
            self.info_lbl.setToolTip("Version du tinySA" + ("\n🌐 débit du lien réseau et délai de réponse du tinySA "
                                                             "(Raspberry Pi, autre PC)" if net else ""))
        else:
            self.dev2_info = txt
            self.update_dev2_label()

    def on_info(self, txt, dev=0):
        self._info_base[dev] = txt
        self._net_txt.pop(dev, None)
        if dev == 0:
            self.info_lbl.setText(f"  {txt}")
            self.seg_known = 450 if "tinysa4" in txt.lower() else 290
            self.update_estimate()
        else:
            self.dev2_info = txt
            self.update_dev2_label()

    def dump_diag(self, reason="", quiet=False):
        """Écrit un fichier de diagnostic (pour le support) : versions, réglages, bandes, derniers échanges avec
        le(s) tinySA. -> chemin, ou None."""
        now = time.time()
        if quiet and now - getattr(self, "_diag_t", 0.0) < 60:          # automatique : au plus une fois par minute
            return None
        self._diag_t = now
        c = self._cfg
        out = [f"{APP_NAME} {APP_VER} — diagnostic du {datetime.now():%d/%m/%Y %H:%M:%S}",
               f"Raison : {reason or 'demandé'}", f"Python {sys.version.split()[0]} · Qt {QtCore.qVersion()} · {sys.platform}",
               f"tinySA : {self.info_lbl.text().strip() or '—'} · port {self.port1() or '—'}"
               f" · {self.baud_combo.currentData()} bauds · démo {self.demo_chk.isChecked()}",
               f"Réglages : points {c['points']} · RBW {c['rbw'] or 'auto'} · RBW zoom {c['zrbw'] or 'auto'} · points zoom {c.get('zpts') or 'auto'} · "
               f"entrée {c['input']} · LNA {c['lna']} · atténuateur {c['att']} · segment {c['seg'] or 'auto'} · "
               f"offset {c['offset']}", "", "Bandes :"]
        for b in self.bands:
            out.append(f"  [{'x' if b['enabled'] else ' '}] {b['name']} : {b['start']:g}–{b['stop']:g} MHz, "
                       f"pas {b['step']:g} kHz, {self._npts(b)} points")
        for k, w in enumerate(list(self.workers)):
            k = getattr(w, "slot", k)
            tr = getattr(w, "trace", None)
            if hasattr(w, "stats_text"):
                out += ["", f"Statistiques de {self.dev_name(k)} : {w.stats_text()}"]
            out += ["", f"Échanges avec {self.dev_name(k)} (plus récents en bas) :"] + [str(x) for x in list(tr or [])]
        try:
            d = self.log_dir / "diagnostic"
            d.mkdir(parents=True, exist_ok=True)
            p_ = d / f"diagnostic_tinysa_{datetime.now():%Y%m%d_%H%M%S}.txt"
            p_.write_text("\n".join(out) + "\n", encoding="utf-8")
            return p_
        except Exception as e:  # noqa: BLE001
            if not quiet:
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Diagnostic impossible à écrire :\n{e}")
            return None

    def open_diag(self):
        p_ = self.dump_diag("demandé depuis le menu")
        if p_ is not None:
            QtWidgets.QMessageBox.information(
                self, APP_NAME, f"Fichier de diagnostic écrit :\n{p_}\n\nEnvoie-le avec la description du problème "
                                "(et le crash.log s'il y en a un). Un fichier est aussi écrit tout seul quand un tinySA "
                                "décroche.")
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(p_.parent)))

    def on_error(self, msg, dev=0):
        self._diag_pending = f"erreur : {msg}"          # écrit par _alarm_tick (crash 7.6.2 avec un singleShot)
        if dev == 0:                              # le 1er tinySA ne répond pas : on arrête tout
            for w in self.workers:
                w.requestInterruption()
        self.show_problem(msg)

    def problem_help(self):
        """Bouton « ❓ Que faire ? » de l'accueil : la fiche du dernier problème."""
        pb = getattr(self, "_last_problem", None) or problem_card("", "other")
        ProblemDialog(self, pb).exec()

    def show_problem(self, msg="", key=None):
        """Fiche « ce qui se passe / quoi faire » (7.46) au lieu d'un message technique brut."""
        card = problem_card(msg, key)
        self._last_problem = card
        self.update_home()
        dlg = ProblemDialog(self, card)
        dlg.exec()

    def on_link(self, dev, ok):
        """Un tinySA décroche (câble, réseau, relais) ou revient : alarme + répartition des bandes."""
        with self.lock:
            if len(self.dev_live) < MAX_DEVS:
                self.dev_live = list(self.dev_live) + [True] * (MAX_DEVS - len(self.dev_live))
            self.dev_live[dev] = bool(ok)
        if not ok and self._calib is not None:
            self._calib_end("⚠ Calibration annulée : un tinySA a décroché.")
        self._bump()
        now = time.time()
        key = ("APPAREIL", -(dev + 1))
        name = self.dev_name(dev)
        w = dict(name=name, freq=0.0)
        if ok:
            if self.alarms.clear(key, now) is not None and self.notify_cfg["mode"] != "off":
                self.send_notify(f"✔ {name} de nouveau en ligne", "Les bandes sont réparties à nouveau.", 1)
            self.log_event(w, 0.0, "APPAREIL RETROUVÉ")
            self._last_problem = None
            self.set_status(f"✔ {name} de nouveau en ligne : bandes réparties à nouveau.")
        else:
            self._diag_pending = f"liaison perdue avec {self.dev_name(dev)}"     # écrit par _alarm_tick
            alive = [self.dev_name(d) for d in self.dev_list() if d != dev and self.live_mask()[d]]
            other = (f"{' + '.join(alive)} reprend ses bandes" if len(alive) == 1 else
                     f"{' + '.join(alive)} reprennent ses bandes") if alive else "plus aucune mesure"
            if self.alarms.raise_(key, "APPAREIL", name, 0.0, 2, now, layer="",
                                  info=f"liaison perdue — {other}"):
                self._alarm_sound(2)
            self.log_event(w, 0.0, "APPAREIL PERDU")
            self._last_problem = problem_card(f"{name} : liaison perdue", "lost")
            self.set_status(f"⚠ {name} : liaison perdue — {other}. Nouvel essai toutes les {ScanWorker.RETRY_S} s.")
        self.update_dev2_label()
        self.refresh_alarms()
        self.update_band_dev_col()

    def on_finished(self):
        if self.is_running():
            return                                # l'autre tinySA tourne encore
        self._style_start(False)
        self.start_btn.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.demo_chk.setEnabled(True)
        for wd in (self.dev2_chk, self.dev2_addr, self.devx_table, self.devx_add_btn, self.devx_del_btn):
            wd.setEnabled(True)
        self.partial_data.clear()
        if self._calib is not None:
            self._calib_end("Calibration annulée (balayage arrêté).", popup=False)
        for d in range(MAX_DEVS):
            self.alarms.clear(("APPAREIL", -(d + 1)), time.time())
        self.dev_live = [True] * MAX_DEVS
        self.update_dev2_label()
        self.set_status("Arrêté.")
        if self._session is not None:
            self._session_end()
