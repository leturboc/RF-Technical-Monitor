# Ouverture des outils, SDR, remplacement, états, plans suivis, pays, prêt ?, festival, garde. (MainWindow)
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FenOutils:
    """Ouverture des outils, SDR, remplacement, états, plans suivis, pays, prêt ?, festival, garde. (méthodes de MainWindow, regroupées par thème.)"""

    def set_watch_freq(self, w, v):
        """Change la fréquence d'une ligne (mesures remises à zéro, liste retriée)."""
        k0, k1 = int(round(w["freq"] * 1000)), int(round(float(v) * 1000))
        for st in self.states:                     # 📸 elle reste dans ses états
            if k0 in st["keys"]:
                st["keys"] = sorted((set(st["keys"]) - {k0}) | {k1})
        w.update(freq=float(v), level=None, max=None, state=None, t_acc=None)
        w["occw"].clear()
        self.sort_watch()
        QtCore.QTimer.singleShot(0, self.rebuild_watch_table)
        self._update_markers()

    def open_listen(self, rows=None):
        self.sdr_timer()                                 # étape 12 : ménage des enregistrements
        if getattr(self, "_listen", None) is not None and self._listen.worker is not None:
            self._listen.raise_()
            self._listen.activateWindow()
            return
        self._listen = ListenDialog(self, rows if rows is not None else self._sel_rows())
        self._listen.show()

    def open_realtime(self, center=None):
        rt = getattr(self, "_rt", None)
        if rt is not None and rt.isVisible():
            if center is not None and rt.worker is None:
                rt.center_spin.setValue(center)
            rt.raise_()
            rt.activateWindow()
            return
        if center is None:
            rows = self._sel_rows()
            if rows:
                center = self.watch[rows[0]]["freq"]
            elif self._zoom:
                center = (self._zoom[0] + self._zoom[1]) / 2.0
            else:
                b = next((b for b in self.bands if b["enabled"]), None)
                center = (b["start"] + b["stop"]) / 2.0 if b else 600.0
        self._rt = RealtimeDialog(self, center)
        self._rt.show()

    def open_sdr(self):
        d = SdrDialog(self)
        if d.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.sdr_cfg.update(d.values())
            for w in self.workers:
                w.sdr_dir = self.sdr_cfg.get("dir", "")
            self.set_status("Réglages SDR enregistrés" + (" (appliqués au prochain cycle)." if self.is_running()
                                                          else "."))

    # ---------------------------------------------------------------- V8 étape 6 : écouter de partout
    def sdr_model_for(self, kind):
        """Étape 7 : fiche du modèle choisi pour ce genre de SDR (⚙ Réglages SDR), sinon le modèle par défaut."""
        return sdr_model_of(kind, self.sdr_cfg.get("models"))

    def sdr_gains(self, kind):
        """Gains à passer aux outils pour ce genre de SDR, d'après son modèle."""
        return sdr_gains_for(self.sdr_model_for(kind), self.sdr_cfg.get("gains"),
                             {k: self.sdr_cfg[k] for k in ("lna", "vga", "amp") if k in self.sdr_cfg})

    def sdr_offset(self, kind):
        """Correction dBFS -> dBm du modèle (0 pour un appareil calibré)."""
        if kind == "demo":                              # étape 21 : SDR démo
            return DEMO_DBM
        m = self.sdr_model_for(kind)
        if m is None or m.get("cal"):
            return 0.0
        return float((self.sdr_cfg.get("offsets") or {}).get(m["key"], 0.0))

    def listen_freq(self, f, w=None):
        """🎧 Écouter une fréquence (FREQ_ACTIONS : alarme, tuile, chasse ; téléphone). Fréquence de la liste ou non."""
        d = getattr(self, "_listen", None)
        if d is not None:
            try:
                d.close()
            except RuntimeError:
                pass
        i = next((k for k, x in enumerate(self.watch) if x is w), None) if w is not None else None
        if i is None:
            i = next((k for k, x in enumerate(self.watch) if abs(x["freq"] - float(f)) < 0.0005), None)
        self._listen = ListenDialog(self, rows=[i] if i is not None else [], freqs=[] if i is not None else [float(f)])
        self._listen.show()
        self._listen.raise_()
        self._listen.toggle()
        return self._listen

    def sdr_burst_conflict(self, kind, w, ev):
        """Étape 8 : signal bref vu par le temps réel sur une fréquence « doit rester libre » -> alarme CONFLIT (clé
        « BREF » : pas effacée par le balayage suivant, qui ne l'a pas vu) qui se termine seule après 60 s."""
        if not self.is_keep_free(w.get("status")) or w.get("off"):
            return False
        now = time.time()
        fk = int(round(w["freq"] * 1000))
        key = ("BREF", fk)
        dur = max(0.0, ev["t1"] - ev["t0"])
        lvl = float(ev["peak"]) + self.sdr_offset(kind)
        prio = self.freq_prio(w)
        info = TR("signal bref de {} s vu par le SDR (temps réel)").format(f"{dur:.2f}")
        if not self.alarms.raise_(key, "CONFLIT", w["name"], w["freq"], prio, now, lvl, self.layer_text(w), info):
            return False
        self.log_event(dict(w, note=info), lvl, "CONFLIT")
        self._alarm_sound(prio)
        self.refresh_alarms()
        QtCore.QTimer.singleShot(60000, lambda k_=key: (self.alarms.clear(k_, time.time()), self.refresh_alarms()))
        return True

    def analyze_freq(self, f, w=None):
        """🔎 Étape 8 (FREQ_ACTIONS) : « c'est quoi ce signal ? » -> temps réel centré sur f, analyse affichée."""
        self.open_realtime(float(f))
        rt = getattr(self, "_rt", None)
        if rt is not None:
            rt._ana_f = float(f)
            if rt.worker is None and rt._src is None:
                rt.toggle()
        return rt

    def sdr_listen_feed(self, kind, F, L, bid=None):
        """Étape 7 (Clément : surveiller ET écouter en même temps) : le spectre de la fenêtre écoutée (dBFS + correction
        du modèle, ou dBm d'un WiNRADiO) sert à surveiller les fréquences qui y tombent, SI aucun autre appareil ne
        balaye (un tinySA garde la main : pas de mélange dBFS / dBm). -> True si utilisé."""
        if any(w.isRunning() and not getattr(w, "paused", False) for w in self.workers):
            return False
        F = np.asarray(F, dtype=float)
        L = np.asarray(L, dtype=float) + self.sdr_offset(kind)
        if len(F) < 2:
            return False
        bid = self.SDR_LISTEN_ID if bid is None else bid       # étape 17 : une « bande » par poste SDR
        self.latest[bid] = (F, L)
        self.latest_t[bid] = time.time()
        try:
            self.update_watch_levels()
            self.update_watch_table()
            if self._hunt is not None and self._hunt.isVisible():   # 13. chasse (et carte de chaleur) avec le SDR
                self._hunt.feed(F, L)
        except Exception:  # noqa: BLE001
            pass
        return True

    def sdr_listen_clear(self, bid=None):
        bid = self.SDR_LISTEN_ID if bid is None else bid
        self.latest.pop(bid, None)
        self.latest_t.pop(bid, None)

    def open_multimon(self):
        """📡 V8 étape 9 : moniteur multicanal SDR (fenêtre gardée : rouverte telle quelle)."""
        self.sdr_timer()
        d = getattr(self, "_multimon", None)
        if d is None:
            d = self._multimon = MultiMonitorDialog(self)
        d.show()
        d.raise_()
        d.activateWindow()
        return d

    def rt_freq(self, f, w=None):
        """⏱ Temps réel autour d'une fréquence (FREQ_ACTIONS)."""
        self.open_realtime(float(f))

    def listen_web_push(self, b):
        """Son de l'écoute -> téléphone (vue 🎧 Écoute), seulement si quelqu'un la regarde."""
        if self.web is None or not self.web.watching(("ecoute",)):
            return
        if getattr(self, "_v8_ring", None) is None:
            self._v8_ring, self._v8_ring_lock = PcmRing(), threading.Lock()
        pcm = pcm_mono16k(b)
        with self._v8_ring_lock:
            self._v8_ring.push(pcm)

    def listen_web_clear(self):
        if getattr(self, "_v8_ring", None) is not None:
            with self._v8_ring_lock:
                self._v8_ring.clear()

    def web_listen_pcm(self, qs):
        """GET /ecoute.pcm?s=n (fil du serveur web) : le son arrivé après le morceau n."""
        n = next((v for k, _, v in (p.partition("=") for p in qs.split("&")) if k == "s"), "0")
        try:
            n = int(n)
        except ValueError:
            n = 0
        if getattr(self, "_v8_ring", None) is None:
            return pcm_packet(0, LISTEN_WEB_RATE, b""), "application/octet-stream"
        with self._v8_ring_lock:
            seq, data = self._v8_ring.since(n)
        return pcm_packet(seq, LISTEN_WEB_RATE, data), "application/octet-stream"

    def web_listen_json(self, qs):
        """GET /ecoute.json : ce que le PC écoute (fil du serveur web : lit un dict remplacé d'un bloc)."""
        st = dict(getattr(self, "_v8_listen", None) or dict(on=False))
        return json.dumps(st, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"

    def web_listen_do(self, cmd):
        """Commande 🎧 du téléphone (code PIN vérifié par le serveur), dans le fil de l'interface."""
        if cmd.get("action") == "stop":
            d = getattr(self, "_listen", None)
            if d is not None and d.worker is not None:
                d.stop()
            self.set_status(TR("📱 Écoute arrêtée depuis le téléphone."))
            return
        f = cmd["f"]
        d = self.listen_freq(f)
        if cmd.get("mode"):
            k = d.mode_combo.findData(cmd["mode"])
            if k >= 0 and d.worker is None:
                d.mode_combo.setCurrentIndex(k)
        self.set_status(TR("📱 Écoute demandée depuis le téléphone : {} MHz").format(f"{f:.3f}"))

    # ------------------------------------------------------- 🆘 7.62 : remplacer un micro en un clic
    def replace_args(self, w):
        """Tout ce qu'il faut (préparé dans le fil de l'interface) pour chercher des remplaçantes de w : le plan actif,
        l'appareil de chaque fréquence (bande comprise), ce que le tinySA voit occupé, les bandes du pays."""
        ws = [x for x in self.watch if x is w or not x.get("off")]
        i = next(k for k, x in enumerate(ws) if x is w)
        po = self.plan_opts
        dflt = dict(sep=po.get("sep", 300) / 1000.0, filt=float(po.get("filt", 32.0)), tol=IM_TOL_PRESETS[0][1],
                    step=po.get("step", 25) / 1000.0)
        P = [rx_profile(self.rx_of(x)) or dflt for x in ws]
        busy = None
        Fm, Lm = self.fresh_FL(use_max=True)
        if Fm is not None:
            lim = self.busy_limit(Lm, weak=True)
            busy = busy_pred(Fm, Lm, lim, max(0.05, self.win_spin.value() / 1000.0))
        F, B = [x["freq"] for x in ws], [float(x.get("bw") or 0.0) for x in ws]
        bd = rx_band(P[i])
        ext = self._band_extent()
        return dict(i=i, F=F, T=[not self.is_keep_free(x["status"]) for x in ws], B=B, sep=[q["sep"] for q in P],
                    tol=[q["tol"] for q in P], filt=[q["filt"] for q in P],
                    img=[float(q.get("img") or 0.0) for q in P], step=P[i].get("step", 0.025), busy=self.reg_busy(busy),
                    near=band_clip(F[i] - 10.0, F[i] + 10.0, bd, B[i]),
                    ext=band_clip(ext[0], ext[1], bd, B[i]) if ext else (band_clip(bd[0], bd[1], bd, B[i]) if bd else None),
                    band=bd, Fm=Fm, Lm=Lm)

    @staticmethod
    def replace_compute(a, n=3):
        """Calcul PUR (peut tourner dans un fil à part) : jusqu'à n remplaçantes, les plus proches d'abord.
        Rien avec toutes les règles (plan très chargé : les 3 TX recouvrent tout) -> nouvel essai en 2A − B seulement,
        signalé (relaxed). -> [(MHz, écart, relaxed)]."""
        st = float(a["step"] or 0.025)
        step = st * max(1, math.ceil(0.025 / st - 1e-9))     # au moins 25 kHz, multiple du pas de l'appareil (rapide)
        gap = max(0.2, float(a["sep"][a["i"]] or 0.0))         # 3 propositions vraiment différentes

        def spread(sg, have):
            out = list(have)
            for c, d in sg:
                if all(abs(c - x[0]) >= gap - 1e-9 for x in out):
                    out.append((c, d))
            return out

        tol2 = [dict(t, **{"3tx3": 0.0, "5": 0.0, "7": 0.0}) for t in a["tol"]]
        kw = dict(n=14 * n, busy=a["busy"], step=step, filt=a["filt"], img=a["img"], max_check=80)
        f0, bd = a["F"][a["i"]], a["band"]
        wins = []
        for half in (10.0, 40.0):
            win = band_clip(f0 - half, f0 + half, bd, a["B"][a["i"]])
            if a["ext"] and win:                      # pas au-delà des bandes balayées (rien de mesuré)
                win = (max(win[0], a["ext"][0]), min(win[1], a["ext"][1]))
            if win and win[1] > win[0]:
                wins.append(win)
        for tol, rel in ((a["tol"], False), (tol2, True)):   # règles complètes, sinon 2A − B seulement (signalé)
            got = []
            for win in wins:                          # près d'abord, plus loin pour compléter
                got = spread(pf_suggest(a["i"], a["F"], a["T"], a["B"], a["sep"], tol, None, lo=win[0], hi=win[1], **kw),
                             got)
                if len(got) >= n:
                    break
            if got:
                got.sort(key=lambda x: abs(x[1]))
                return [(c, d, rel) for c, d in got[:n]]
        return []

    def replace_decorate(self, a, sg, w):
        """Propositions -> [dict(f, d, level, tag)] (niveau mesuré, réserve réglementaire)."""
        out = []
        for c, d, rel in sg:
            lv = level_at(a["Fm"], a["Lm"], c, 0.1) if a["Fm"] is not None else None
            tag = self.reg_tag(c, float(w.get("bw") or 0.0))
            if rel:
                tag = "règles allégées : 2A − B seulement" + (f" · {tag}" if tag else "")
            out.append(dict(f=round(float(c), 4), d=float(d), level=lv, tag=tag, relaxed=rel))
        return out

    def suggest_replacements(self, w, n=3):
        """Version directe (fil de l'interface) : page Tech, tests."""
        a = self.replace_args(w)
        return self.replace_decorate(a, self.replace_compute(a, n), w)

    def replace_watch(self, w, f, how="🆘 remplacement"):
        """Remplace la fréquence de w par f : alarmes de l'ancienne effacées, journal « NOUVELLE FRÉQUENCE »."""
        if not any(x is w for x in self.watch):
            return False
        old = w["freq"]
        k0 = int(round(old * 1000))
        now = time.time()
        for kind in ("CONFLIT", "ABSENT"):
            self.alarms.clear((kind, k0), now)
        self.set_watch_freq(w, f)
        self.log_event(dict(name=w["name"], freq=0.0, note=f"{old:.3f} → {f:.3f} MHz ({how})"), 0.0, "NOUVELLE FRÉQUENCE")
        self.refresh_alarms()
        self.undo_track()
        self.set_status(TR("🆘 {} : {} → {} MHz. Règle l'émetteur ET le récepteur sur la nouvelle fréquence.").format(
            w["name"], f"{old:.3f}", f"{f:.3f}"))
        return True

    def open_replace(self, w=None):
        """🆘 Fenêtre « Remplacer ce micro » : w = la fréquence (sinon celle choisie dans la liste, sinon l'alarme)."""
        if w is None:
            rows = self._sel_rows()
            w = self.watch[rows[0]] if rows else self._alarm_watch()
        if w is None:
            self.set_status("Choisis d'abord le micro à remplacer (dans la liste ou dans les alarmes).")
            return None
        if self._replace is not None:
            try:
                self._replace.close()
            except RuntimeError:
                pass
        self._replace = ReplaceDialog(self, w)
        self._replace.show()
        return self._replace

    def _alarm_watch(self):
        """La fréquence de la liste liée à l'alarme choisie (sinon la plus récente non acquittée)."""
        ids = self._alarm_selected_ids()
        items = self.alarms.listing()
        a = next((x for x in items if ids and x["id"] == ids[0]), None) or next(
            (x for x in items if x["t_end"] is None and not x["acked"] and x.get("freq")), None)
        if a is None or not a.get("freq"):
            return None
        return min(self.watch, key=lambda x: abs(x["freq"] - a["freq"]), default=None) if any(
            abs(x["freq"] - a["freq"]) < 0.0015 for x in self.watch) else None

    def open_scan_convert(self):
        self._conv_dlg = ScanConvertDialog(self)
        self._conv_dlg.show()

    def open_plan_check(self):
        self._plan_dlg = PlanCheckDialog(self)
        self._plan_dlg.show()

    def rx_library(self):
        """Bibliothèque d'appareils (.lst4) importée (fichier à part : ~1 200 appareils, pas dans la config)."""
        if not RX_LIBRARY and self.LIB_PATH.exists():
            try:
                RX_LIBRARY[:] = json.loads(self.LIB_PATH.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                pass
        return RX_LIBRARY

    def set_rx_library(self, lib):
        RX_LIBRARY[:] = lib
        try:
            self.LIB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.LIB_PATH.write_text(json.dumps(lib, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def rx_profiles_changed(self):
        """Profils perso modifiés : listes d'appareils rafraîchies, config enregistrée."""
        d = getattr(self, "_plan_dlg", None)
        if d is not None:
            try:
                d.refill_profiles()
            except RuntimeError:                 # fenêtre déjà détruite
                self._plan_dlg = None
        self._save_config()

    def open_rx_profiles(self):
        RxProfilesDialog(self).exec()

    def open_linecheck(self):
        if self._linecheck is not None:
            self._linecheck.raise_()
            self._linecheck.activateWindow()
            return
        self._linecheck = LineCheckDialog(self)
        self._linecheck.show()

    def open_rescue(self):
        self._rescue_dlg = RescueDialog(self)
        self._rescue_dlg.show()

    def open_hunt(self, f0=None):
        """🔎 Chasse au brouilleur sur f0, sinon la fréquence choisie dans la liste, sinon M1, sinon le centre de la vue."""
        if f0 is None:
            rows = self._sel_rows()
            if rows:
                f0 = self.watch[rows[0]]["freq"]
            elif getattr(self, "mkr_bar", None) is not None and self.mkr_bar.isVisible():
                f0 = self.mkr_spins[0].value()
            else:
                vr = self.spec.getPlotItem().vb.viewRange()[0]
                f0 = (vr[0] + vr[1]) / 2.0
        if self._hunt is not None:
            self._hunt.f_spin.setValue(f0)
            self._hunt.raise_()
            return
        self._hunt = HuntDialog(self, f0)
        self._hunt.show()

    @staticmethod
    def _planning_now(pl, n):
        return planning_active(pl, n.date().isoformat(), n.hour * 60 + n.minute,
                               (n.date() - timedelta(days=1)).isoformat(), (n.date() + timedelta(days=1)).isoformat())

    def _planning_tick(self, now, force=False):
        """Toutes les 15 s : qui est sur scène ? Un changement = journal « CHANGEMENT DE PLATEAU » et les ABSENT des
        groupes qui viennent de quitter la scène sont effacés."""
        if not force and now < self._plan_next:
            return
        self._plan_next = now + 15.0
        st = self._planning_now(self.planning, datetime.now())
        if st == self._plan_state:
            return
        old_act = self._plan_state[0]
        self._plan_state = st
        act, planned = st
        for sc in sorted(planned, key=str.lower):
            was = sorted(g or "toute la scène" for (c, g) in old_act if c == sc)
            is_ = sorted(g or "toute la scène" for (c, g) in act if c == sc)
            if was != is_ and not force:
                note = f"{', '.join(was) or 'personne'} → {', '.join(is_) or 'personne'}"
                self.log_event(dict(name=sc, freq=0.0, note=note), 0.0, "CHANGEMENT DE PLATEAU")
                self.set_status(f"🎬 {sc} : {note}")
        for w in self.watch:
            w["sig"] = None
            if self.w_paused(w) and w.get("absent"):
                w["absent"] = False
                w["free_since"] = None
                self.alarms.clear(("ABSENT", int(round(w["freq"] * 1000))), now)
        self.update_watch_table(force=True)
        self._update_markers()
        if self.wall is not None and self.wall.isVisible():
            self.wall.rebuild()

    # ------------------------------------------------------------- 📸 états (Snapshots)
    def _update_state_btn(self):
        if hasattr(self, "state_btn"):
            self.state_btn.setText(f"📸 {self.state_cur}" if self.state_cur else "📸 Tout")

    def _build_state_menu(self):
        m = self.state_menu
        m.clear()
        a = m.addAction("Tout actif (aucun état)")
        a.setCheckable(True)
        a.setChecked(not self.state_cur)
        a.triggered.connect(lambda *_: self.apply_state(""))
        for st in self.states:
            a = m.addAction(f"📸 {st['name']}  ({len(st['keys'])})")
            a.setCheckable(True)
            a.setChecked(st["name"] == self.state_cur)
            a.triggered.connect(lambda *_, n=st["name"]: self.apply_state(n))
        m.addSeparator()
        m.addAction("＋ Nouvel état avec les fréquences actives…").triggered.connect(lambda *_: self.new_state())
        m.addAction("Gérer les états…").triggered.connect(lambda *_: self.open_states())

    def state_by_name(self, name):
        return next((x for x in self.states if x["name"] == name), None)

    def apply_state(self, name, quiet=False):
        """📸 Active un état : ses fréquences (et les « toujours actives ») surveillées, les autres en pause."""
        st = self.state_by_name(name) if name else None
        self.state_cur = st["name"] if st else ""
        keys = set(st["keys"]) if st else None
        now = time.time()
        n_off = 0
        for w in self.watch:
            k = int(round(w["freq"] * 1000))
            off = keys is not None and k not in keys and not w.get("iso")
            w["off"] = off
            if off:
                n_off += 1
                for kind in ("CONFLIT", "ABSENT"):
                    self.alarms.clear((kind, k), now)
                w["absent"] = False
        self._update_state_btn()
        if not quiet:
            self.rebuild_watch_table()
            self._update_markers()
            self.refresh_alarms()
            self.set_status(f"📸 État « {self.state_cur} » : {len(self.watch) - n_off} fréquence(s) surveillée(s), "
                            f"{n_off} en pause." if self.state_cur else "📸 Tout actif : toutes les fréquences sont surveillées.")
        return n_off

    def new_state(self, name=None):
        if name is None:
            name, ok = QtWidgets.QInputDialog.getText(self, "Nouvel état", "Nom (artiste, scène, jour…) :")
            if not ok:
                return None
        name = re.sub(r"\s+", " ", str(name)).strip()[:40]
        if not name:
            return None
        if self.state_by_name(name) is not None:
            self.set_status(f"Un état « {name} » existe déjà.")
            return None
        keys = sorted(int(round(w["freq"] * 1000)) for w in self.watch if not w.get("off"))
        self.states.append(dict(name=name, keys=keys))
        self.state_cur = name
        self._update_state_btn()
        self.set_status(f"📸 État « {name} » créé avec {len(keys)} fréquence(s) : décoche celles qui ne jouent pas "
                        "dans « Gérer les états ».")
        return name

    def open_states(self):
        StatesDialog(self).exec()

    # ------------------------------------------------------------- 🔗 plan .ezrf3 suivi
    def _ezrf_tick(self, now, force=False):
        """Toutes les 5 s : le fichier .ezrf3 suivi a-t-il été réenregistré ? -> fenêtre des changements."""
        lk = self.ezrf_link
        if not lk or (now < self._ezrf_next and not force):
            return None
        self._ezrf_next = now + 5.0
        try:
            mt = os.path.getmtime(lk["path"])
        except OSError:
            return None
        if mt == lk.get("mtime") and not force:
            return None
        if now - mt < 1.0 and not force:            # le logiciel de coord est peut-être encore en train d'écrire
            return None
        lk["mtime"] = mt
        kind = lk.get("kind") or "EazyRF"
        try:
            doc, _k = parse_plan_file(Path(lk["path"]).read_bytes(), lk["path"])
        except (OSError, ValueError) as e:
            self.set_status(f"🔗 Plan {kind} « {lk.get('name', '')} » illisible : {e}")
            return None
        doc = plan_fill_pending(doc, lk.get("manual") or {})   # canaux complétés à la main (récepteurs Wisycom)
        fname = os.path.basename(str(lk["path"]))
        if doc.get("tv") or self.tnt_cfg.get("plan_src") == fname:  # 7.58.2 : canaux TV du plan suivis aussi
            if self.tnt_set_plan(doc.get("tv") or [], fname):
                self.set_status(f"📺 Canaux TV du plan « {fname} » mis à jour : "
                                f"{', '.join(map(str, self.tnt_cfg['plan'])) or 'aucun'}.")
        d = ezrf_diff(ezrf_remap(ezrf_entries(doc, lk.get("skip_off", True), lk.get("naming", "dev")), lk.get("map")), self._ezrf_cur(lk))
        d["add"] = [e for e in d["add"] if not any(abs(w["freq"] - e[1]) < 1e-6 for w in self.watch)]
        if not (d["add"] or d["change"] or d["remove"]):
            self.set_status(f"🔗 Plan {kind} « {lk.get('name', '')} » réenregistré : rien n'a changé dans la liste.")
            return d
        if self._ezrf_dlg is not None:
            try:
                self._ezrf_dlg.close()
            except RuntimeError:
                pass
        self._ezrf_dlg = EzrfSyncDialog(self, d)
        self._ezrf_dlg.show()
        self._alarm_sound(1)
        return d

    def _ezrf_cur(self, lk):
        """Fréquences de la liste venues du plan suivi -> [(id, MHz)]. Seulement celles de CE fichier (7.50 : sinon,
        en suivant un .wshow après avoir importé un .ezrf3, l'appli proposait de retirer toutes celles du logiciel de coord)."""
        src = lk.get("name", "")
        return [(w["ez"], w["freq"]) for w in self.watch if w.get("ez") and w.get("ezsrc", src) == src]

    def apply_ezrf_diff(self, d, add, change, remove):
        """Applique les changements cochés -> (ajoutées, modifiées, retirées) ; 🕘 notés « 🔗 nom du plan »."""
        self.history_track()
        out = self._apply_ezrf_diff(d, add, change, remove)
        self.history_track("🔗 " + ((self.ezrf_link or {}).get("name", "") or TR("plan suivi")))
        return out

    def _apply_ezrf_diff(self, d, add, change, remove):
        st = self._resolve_status(self.ezrf_link.get("status", "")) if self.ezrf_link and self.ezrf_link.get("status") else ""
        src = (self.ezrf_link or {}).get("name", "")
        by_ez = {w["ez"]: w for w in self.watch if w.get("ez") and w.get("ezsrc", src) == src}
        n = [0, 0, 0]
        for e in add:
            name, f, sc, gr, _dk, _note = e
            if any(abs(w["freq"] - f) < 1e-6 for w in self.watch):
                continue
            self._append_watch(name, f, st, None, sc, gr)
            self.watch[-1]["ez"] = ezrf_id(sc, gr, name)
            if src:
                self.watch[-1]["ezsrc"] = src
            n[0] += 1
        for i, _old, new_f, _e in change:
            w = by_ez.get(i)
            if w is not None:
                self.set_watch_freq(w, new_f)
                n[1] += 1
        for i in remove:
            w = by_ez.get(i)
            if w is not None and w in self.watch:
                self.watch.remove(w)
                n[2] += 1
        self.sort_watch()
        self.rebuild_tree()
        self.rebuild_watch_table()
        self._update_markers()
        self.undo_track()
        self.set_status(f"🔗 Plan {(self.ezrf_link or {}).get('kind') or 'EazyRF'} : {n[0]} ajoutée(s), {n[1]} "
                        f"modifiée(s), {n[2]} retirée(s).")
        return tuple(n)

    def ezrf_follow_info(self):
        lk = self.ezrf_link
        if not lk:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Aucun plan suivi. Pour en suivre un : 📥 Importer une "
                                              "liste, choisis le plan (EazyRF .ezrf3, Shure WWB .shw / .cug, Sennheiser "
                                              "WSM .wsm, Wisycom .wshow, DPA .acp) et coche « 🔗 Suivre ce fichier ».")
            return
        kind = lk.get("kind") or "EazyRF"
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Plan suivi")
        box.setText(f"🔗 Suivi : « {lk.get('name', '')} »\n{lk.get('path', '')}\n\nÀ chaque réenregistrement dans {kind}, "
                    f"l'appli te propose les fréquences ajoutées, modifiées ou retirées.")
        b_now = box.addButton("Vérifier maintenant", QtWidgets.QMessageBox.ButtonRole.ActionRole)
        b_stop = box.addButton("Arrêter de suivre", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QtWidgets.QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is b_now:
            if self._ezrf_tick(time.time(), force=True) is None:
                self.set_status("🔗 Fichier introuvable ou illisible.")
        elif box.clickedButton() is b_stop:
            self.ezrf_link = None
            self.set_status("🔗 Le plan n'est plus suivi.")

    def open_planning(self):
        d = PlanningDialog(self)
        if not d.exec():
            return
        self.planning = d.values()
        self._planning_tick(time.time(), force=True)
        n = len(self.planning["slots"])
        self.set_status(f"🎬 Planning : {n} créneau(x)." if n else "🎬 Planning vide : tout est surveillé tout le temps.")

    def open_emit(self):
        d = EmitDialog(self)
        d.exec()

    def open_sites(self, before_after=False, freq=None):
        d = SitesDialog(self)
        if freq is not None:                       # 📍 7.68 : une fréquence dans chaque lieu
            d.show_freq(*freq) if isinstance(freq, tuple) else d.show_freq(freq)
        if before_after:                           # 📸 7.63 : directement sur « avant → après »
            d.tabs.setCurrentIndex(1)
            d.cmp_mode.setCurrentIndex(d.cmp_mode.findData("time"))
        d.exec()
        self.update_site_curve()

    def open_before_after(self):
        """📸 7.63 : comparer un scan « avant » (installation, changement) et un scan « après »."""
        if len(self.site_scans) < 2:
            QtWidgets.QMessageBox.information(
                self, APP_NAME, TR("Il faut deux scans gardés : un AVANT (📍 Scans par lieu › « 📍 Garder », avant "
                                   "d'allumer les micros ou de changer quelque chose) puis un APRÈS. Ensuite reviens ici."))
            if not self.site_scans:
                return self.open_sites()
        return self.open_sites(before_after=True)

    def scan_rbw(self, F):
        """RBW (kHz) d'un scan fait maintenant -> (rbw, estimée ?) : la RBW forcée, sinon celle que le tinySA choisit en
        auto d'après le pas (estimation)."""
        r = self.rbw_combo.currentData()
        if r is not None:
            return float(r), False
        F = np.asarray(F if F is not None else [], dtype=float)
        if len(F) < 2:
            return None, False
        step = float(np.median(np.diff(F))) * 1000.0
        return (float(auto_rbw(step)), True) if step > 0 else (None, False)

    def live_rbw(self):
        """RBW du balayage en cours (d'après les bandes balayées) -> (rbw, estimée)."""
        if not self.latest:
            r = self.rbw_combo.currentData()
            return (float(r), False) if r is not None else (None, False)
        return rbw_combine([self.scan_rbw(v[0]) for v in self.latest.values()])

    def coord_rbw(self, src=None):
        """RBW du spectre que la coordination évite (scans gardés + direct) -> (rbw | "mixed" | None, estimée)."""
        if src is None:
            src = "all" if self.sites_coord else "live"
        items = [(d.get("rbw"), bool(d.get("rbw_est"))) for d in coord_docs(self.site_scans, src)]
        if src in ("live", "all") or self.site_mh.get(src):
            if self.latest or src == "live":
                items.append(self.live_rbw())
        return rbw_combine(items)

    def set_rbw_fine(self):
        """Finesse de mesure (RBW) à 30 kHz : scan pour une coordination."""
        for i in range(self.rbw_combo.count()):
            v = self.rbw_combo.itemData(i)
            if v is not None and abs(float(v) - COORD_RBW_MAX) < 1e-6:
                self.rbw_combo.setCurrentIndex(i)
                break
        self.set_status("Finesse de mesure (RBW) à 30 kHz : scan pour la coordination (plus lent). "
                        "Efface les pics gardés et laisse balayer quelques minutes.")

    def busy_limit(self, L, mode=None, weak=False):
        """Seuil « occupé » des outils qui évitent un spectre gardé / max hold (coordination, secours, remplacer,
        proposer) : réglage `plan_opts["busy_mode"]` ; par défaut « auto » en seuil auto, sinon le seuil de la fenêtre
        (« faible » s'il est coché et `weak`)."""
        po = self.plan_opts
        mode = mode or po.get("busy_mode") or ("auto" if self.thr_auto else "global")
        glob = self.weak_spin.value() if (weak and self.weak_chk.isChecked()) else self.thr_spin.value()
        return busy_lim(L, mode, po.get("busy_margin", BUSY_MARGIN), po.get("busy_fixed", -80.0), glob)

    def coord_FL(self, src=None):
        """Spectre à éviter pour la coordination. src : « live » = max hold actuel ; « all » = tout le site (fusion de
        tous les scans gardés + max hold) ; une scène = ses scans gardés + son max hold en cours (tinySA volant).
        None = réglage « éviter l'occupé de TOUS les lieux » (Scans par lieu)."""
        if src is None:
            src = "all" if self.sites_coord else "live"
        docs = coord_docs(self.site_scans, src)
        if src in ("live", "all"):
            F, L = self.fresh_FL(use_max=True, any_age=True)
        else:
            F, L = self._site_mh_FL(src)
        if not docs:
            return F, L
        return merge_scans([(d["f"], d["l"]) for d in docs] + ([(F, L)] if F is not None else []))

    def fill_coord_combo(self, combo):
        """Liste « Spectre à éviter » : max hold actuel, tout le site, ou une scène (ses scans gardés)."""
        combo.clear()
        combo.addItem("Spectre : max hold actuel (ce que voient les tinySA)", "live")
        combo.addItem(f"Spectre : tout le site (fusion de {len(self.site_scans)} scan(s) gardé(s) + max hold)", "all")
        per = {}
        for d in self.site_scans:
            per[site_doc_scene(d)] = per.get(site_doc_scene(d), 0) + 1
        for sc in list(dict.fromkeys([x["name"] for x in self.scenes] + list(per))):
            if per.get(sc) or self.site_mh.get(sc):
                combo.addItem(f"Spectre : scène {sc} ({per.get(sc, 0)} scan(s) gardé(s))", sc)
        want = "all" if self.sites_coord else "live"
        one = {k[0] for k in self.scope or [] if k}
        if len(one) == 1 and combo.findData(next(iter(one))) >= 0:
            want = next(iter(one))                 # la scène choisie dans « Mes fréquences »
        combo.setCurrentIndex(max(0, combo.findData(want)))
        combo.setToolTip("Le spectre dont on évite les signaux : coordination GLOBALE (tout le site) ou PAR SCÈNE\n"
                         "(les scans gardés de cette scène, par ex. avec le tinySA volant et la vue web 🎒 Terrain).")

    def open_settings(self, tab=0):
        d = SettingsDialog(self)
        d.show_page(tab)
        d.exec()
        self._save_config()

    def _reap_dialogs(self, now, after=10.0):
        """Libère les fenêtres fermées. Chaque QDialog(self) restait en mémoire après sa fermeture (≈ 4 Mo à chaque
        ouverture de Réglages, Vérifier le plan… : test du singe 7.41). Une fenêtre cachée depuis `after` s et que la
        fenêtre principale ne garde pas (attribut, liste ou dict : _legend, _ready, _tech_boxes…) est détruite."""
        keep = set()
        for v in self.__dict__.values():
            for x in (v if isinstance(v, (list, tuple, set)) else v.values() if isinstance(v, dict) else (v,)):
                if isinstance(x, QtWidgets.QDialog):
                    keep.add(id(x))
        seen = self.__dict__.setdefault("_hidden_since", {})
        alive = set()
        for d in self.findChildren(QtWidgets.QDialog, "", Qt.FindChildOption.FindDirectChildrenOnly):
            k = id(d)
            if d.isVisible() or k in keep:
                continue
            alive.add(k)
            t = seen.setdefault(k, now)
            if now - t >= after:
                free_plot_menus(d)
                d.setParent(None)
                d.deleteLater()
                alive.discard(k)
        for k in list(seen):
            if k not in alive:
                seen.pop(k, None)

    # ---------------------------------------------------------------- 7.60.2 : calculs longs hors de l'interface
    def run_heavy(self, fn, done, label=None, what="Calcul", status=None):
        """Lance fn() (calcul PUR, sans Qt) dans un fil à part ; done(résultat, erreur) est appelé ensuite dans le fil
        de l'interface. L'appli reste réactive pendant un long calcul : le battement de la garde continue (avant :
        une coordination de 40 fréquences figeait l'interface plus de 90 s et la garde la relançait).
        -> job {done, cancel} ; mettre job["cancel"] = True pour ignorer le résultat."""
        job = dict(res=None, err=None, done=False, cancel=False, t0=time.time())

        def work():
            try:
                job["res"] = fn()
            except Exception as e:  # noqa: BLE001
                job["err"] = e
            job["done"] = True
        threading.Thread(target=work, daemon=True, name="calcul").start()
        tm = QtCore.QTimer(self)
        tm.setInterval(250)

        def poll():
            if job["cancel"]:
                tm.stop()
                tm.deleteLater()
                return
            if job["done"]:
                tm.stop()
                tm.deleteLater()
                try:
                    done(job["res"], job["err"])
                except RuntimeError:              # fenêtre supprimée pendant le calcul : résultat ignoré
                    pass
            elif label is not None:
                try:
                    st = status() if status is not None else ""
                    label.setText(f"⏳ {TR(what)} en cours… {int(time.time() - job['t0'])} s"
                                  + (f" · {st}" if st else "") + " (l'appli reste utilisable)")
                except RuntimeError:              # fenêtre fermée entre-temps
                    job["cancel"] = True
        tm.timeout.connect(poll)
        tm.start()
        return job

    # ---------------------------------------------------------------- 7.60 : bandes autorisées du pays
    def country_code(self):
        return self.country_combo.currentData() or "FR"

    def reg_pred(self, bw=0.0):
        """Prédicat « dans une plage autorisée du pays » pour secours / coordination ; None = pas de filtre."""
        if not getattr(self, "reg_only", True):
            return None
        return reg_allowed_pred(self.country_code(), bw)

    def reg_busy(self, busy):
        """busy(c) de la coordination + hors des plages autorisées = occupé (jamais proposé)."""
        p = self.reg_pred()
        if p is None:
            return busy

        def f(c):
            return (not p(c)) or (busy is not None and bool(busy(c)))

        def vec(cs):
            cs = np.asarray(cs, dtype=float)
            pv = getattr(p, "vec", None)
            out = ~(pv(cs) if pv is not None else np.array([bool(p(float(c))) for c in cs], dtype=bool))
            if busy is not None:
                bv = getattr(busy, "vec", None)
                out |= bv(cs) if bv is not None else np.array([bool(busy(float(c))) for c in cs], dtype=bool)
            return out
        f.vec = vec
        return f

    def reg_note(self):
        """Phrase pour les fenêtres de secours / coordination."""
        code = self.country_code()
        cn = TR(dict(COUNTRIES).get(code, code))
        if not reg_known(code):
            return f"⚠ Réglementation inconnue pour {cn} : propositions NON vérifiées réglementairement."
        if self.reg_pred() is None:
            return "⚠ Filtre des bandes autorisées coupé (⚙ › Pays) : propositions non vérifiées réglementairement."
        return (f"Propositions dans les bandes autorisées pour {cn} (indicatif, ⚙ › Pays). Libre ici = d'après la mesure ; "
                "« sous licence » = autorisation à obtenir AVANT d'émettre.")

    def reg_tag(self, f, bw=0.0):
        """Étiquette réglementaire d'une fréquence proposée ("" = rien à signaler)."""
        if self.reg_pred() is None and reg_known(self.country_code()):
            return "filtre coupé : non vérifiée"
        return reg_tag(self.country_code(), f, bw)

    def reg_info(self, ws):
        code = self.country_code()
        items = [(w.get("name") or "", w["freq"], float(w.get("bw") or 0.0), not self.is_keep_free(w.get("status")))
                 for w in ws]
        out, cond = reg_issues(code, items)
        fmt = lambda x: f"{x[0] or '?'} ({x[1]:.3f})" + (f" {TR(x[2])}" if x[2] else "")
        lora = [f"{w.get('name') or '?'} ({w['freq']:.3f})" for w in ws if not self.is_keep_free(w.get("status"))
                and lora_overlap(code, w["freq"], float(w.get("bw") or 0.0))]
        return dict(reg_out=[fmt(x) for x in out], reg_cond=[fmt(x) for x in cond], lora=lora,
                    reg_unknown=not reg_known(code),
                    country_name=TR(dict(COUNTRIES).get(code, code)))

    def open_country(self):
        self.open_settings("country")

    # ---------------------------------------------------------------- ✅ prêt pour le show ?
    def ready_info(self):
        """État de l'appli pour ready_checks (PURE)."""
        now = time.time()
        bands = [b for b in self.scan_bands() if self._scan_now(b)]
        ws = [w for w in self.watch if not w.get("off")]

        def covered(w):
            hw = float(w.get("bw") or 0.0) / 2.0
            return any(b["start"] - 1e-6 <= w["freq"] - hw and w["freq"] + hw <= b["stop"] + 1e-6 for b in bands)
        devs = [dict(name=self.dev_name(d), live=bool(self.dev_live[d]) if d < len(self.dev_live) else True)
                for d in self.dev_list()]
        ts = [t for k, t in self.latest_t.items() if k != ZOOM_ID]
        plan = None
        try:
            tx = [w for w in ws if not self.is_keep_free(w["status"])]
            if 0 < len(ws) <= 80 and self.coord_on:
                dflt = dict(sep=self.plan_opts.get("sep", 300) / 1000.0, filt=float(self.plan_opts.get("filt", 32.0)),
                            tol=IM_TOL_PRESETS[0][1])
                P = [rx_profile(self.rx_of(w)) or dflt for w in ws]
                iss, _ = pf_check([w["freq"] for w in ws], [not self.is_keep_free(w["status"]) for w in ws],
                                  [float(w.get("bw") or 0.0) for w in ws], [q["sep"] for q in P],
                                  [q["tol"] for q in P], None, [q["filt"] for q in P],
                                  [float(q.get("img") or 0.0) for q in P])
                for k_, (w, q) in enumerate(zip(ws, P)):     # 7.61 : hors de la bande de son appareil
                    if band_issue(w["freq"], w.get("bw"), rx_band(q)):
                        iss[k_].append(dict(kind="band"))
                plan = sum(1 for x in iss if x) if tx else 0
        except Exception:  # noqa: BLE001
            plan = None
        disk = None
        try:
            import shutil
            d = Path(self.log_dir)
            while not d.exists() and d != d.parent:
                d = d.parent
            disk = shutil.disk_usage(str(d)).free / 1e9
        except Exception:  # noqa: BLE001
            pass
        snd = self.sound.cfg
        dev_missing = False
        if snd.get("style", "tones") == "tones" and snd.get("device"):
            outs = SoundOut.devices()
            dev_missing = bool(outs) and snd["device"] not in [i for i, _ in outs] + [n for _, n in outs]
        nc = self.notify_cfg
        ready = bool(nc.get("topic")) if nc.get("service") == "ntfy" else bool(nc.get("tg_token") and nc.get("tg_chat"))
        return dict(running=self.is_running(), demo=self.demo_chk.isChecked(), devs=devs,
                    sweep_age=(now - max(ts)) if ts else None, cycle=getattr(self, "last_cycle", 0.0) or 0.0,
                    watch_n=len(ws), uncovered=sum(1 for w in ws if not covered(w)),
                    no_status=sum(1 for w in ws if not w.get("status")), plan_issues=plan,
                    muted=sum(1 for w in ws if w.get("muted")), **self.reg_info(ws),
                    conflicts=sum(1 for a in self.alarms.active.values() if a.get("kind") != "APPAREIL")
                    if isinstance(self.alarms.active, dict) else len(self.alarms.active),
                    snooze=max(0.0, self.snooze_until - now) if self.snooze_until else 0.0,
                    sound_device_missing=dev_missing, volume=snd.get("volume", 70),
                    notify_mode=nc.get("mode", "off"), notify_ready=ready,
                    web_on=bool(self.web_cfg.get("on")), web_up=self.web is not None,
                    web_url=self.web_urls_text() if self.web is not None else "",
                    web_pin=bool(self.web_cfg.get("pin")), show_path=self.show_path,
                    session_rec=bool(self.session_cfg.get("rec")), disk_gb=disk,
                    windows=sys.platform == "win32", guarded=self.guarded(), rbw=self._cfg.get("rbw"),
                    **(self.quality_info() if self.is_running() else {}))

    def quality_info(self):
        """Indicateurs de qualité de mesure (7.44) : saturation, marges faibles, résolution, mesures anciennes."""
        now = time.time()
        stale_s = max(15.0, 4 * (getattr(self, "last_cycle", 0.0) or 0.0))
        sm = [v for t_, v in self.__dict__.get("_sat_max", {}).values() if now - t_ <= stale_s]
        sat_dbm = max(sm) if sm else None
        lna = self._cfg.get("lna") is True
        ws = [w for w in self.watch if not w.get("off") and not w.get("muted")]
        low = [w["name"] or f"{w['freq']:.3f}" for w in ws
               if self.is_keep_on(w["status"]) and w.get("level") is not None and w.get("margin") is not None
               and w["state"] in ("weak", "occ") and w["margin"] < SNR_LOW]
        bands = [b for b in self.scan_bands() if self._scan_now(b)]
        rbw = self._cfg.get("rbw")

        def res_of(f):
            for b in bands:
                if b["start"] <= f <= b["stop"]:
                    return max(b["step"] / 1000.0, (rbw or 0) / 1000.0)
            return None
        items = [(w["name"] or f"{w['freq']:.3f}", w["freq"], res_of(w["freq"])) for w in ws if not w.get("bw")]
        items = [x for x in items if x[2]]
        pairs = resolution_pairs(items, 0.0) if items else []
        stale, stale_names = 0, []
        if self.is_running():
            for w in ws:
                if w.get("level") is None and not self.w_paused(w):   # hors bandes, ou bande pas encore balayée
                    stale_names.append(w["name"] or f"{w['freq']:.3f}")
                    stale += bool(res_of(w["freq"]))                   # dans une bande balayée : mesure en retard
        return dict(sat=sat_level(sat_dbm, lna), sat_dbm=sat_dbm, low_snr=low, res_pairs=pairs,
                    stale=stale, stale_names=stale_names)

    def open_feature_search(self):
        """🔎 Ctrl+K : chercher une fonction par un mot et l'ouvrir."""
        FeatureSearchDialog(self).exec()

    def show_coord_setting(self):
        """🔒 Les outils de coordination sont cachés : ⚙ Réglages › Général, où se trouve la case pour les afficher."""
        self.open_settings(0)

    def open_devs_settings(self):
        """🔌 Matériel › Plusieurs tinySA : la rubrique des tinySA dans ⚙ Réglages."""
        self.open_settings("dev2")

    def open_measure(self):
        self.open_settings("measure")

    def set_rbw_auto(self):
        """7.57.1 : « Régler » de la vitesse du balayage (Prêt ?) : finesse de mesure (RBW) en Auto."""
        i = self.rbw_combo.findData(None)
        if i >= 0:
            self.rbw_combo.setCurrentIndex(i)
        self.set_status("Finesse de mesure (RBW) en Auto : le tinySA choisit selon le pas (balayage plus rapide).")

    def open_show_mode(self):
        """🖥 Mode Show plein écran (sur l'écran de la fenêtre principale)."""
        if getattr(self, "_show_mode", None) is not None:
            self._show_mode.close()
            return None
        self._show_mode = w = ShowModeWindow(self)
        scr = self.screen() or QtGui.QGuiApplication.primaryScreen()
        if scr is not None:
            w.setGeometry(scr.availableGeometry())
        w.showFullScreen()
        return w

    # ---------------------------------------------------- ⚡ préréglages rapides (7.56)
    def preset_current(self):
        """Réglages actuels, avec les clés des préréglages (voir QUICK_PRESETS)."""
        return dict(thr_auto=bool(getattr(self, "thr_auto", False)), auto_occ=self.auto_occ_spin.value(),
                    auto_weak=self.auto_weak_spin.value(), points=self.points_combo.currentData(),
                    persist=self.persist_combo.currentData() or 0, absent=self.absent_spin.value(),
                    confirm=int(self.sound.cfg.get("confirm", 0)), repeat=int(self.sound.cfg.get("repeat", 30)),
                    strong=self.strong_chk.isChecked(), strong_lvl=round(float(self.strong_spin.value()), 1),
                    hold=self.hold_chk.isChecked())

    def apply_preset(self, key):
        """Applique le préréglage key (seulement des réglages : liste, scènes et bandes ne bougent pas)."""
        p = quick_preset(key, self.user_presets)
        if not p:
            return False
        st = p[3]
        self.thr_auto_btn.setChecked(bool(st["thr_auto"]))
        self.set_thr_auto(bool(st["thr_auto"]))
        self.auto_occ_spin.setValue(int(st["auto_occ"]))
        self.auto_weak_spin.setValue(int(st["auto_weak"]))
        i = self.points_combo.findData(st["points"])
        if i >= 0 and i != self.points_combo.currentIndex():
            self.set_points_choice(i)
        i = self.persist_combo.findData(st["persist"])
        if i >= 0:
            self.persist_combo.setCurrentIndex(i)
        self.absent_spin.setValue(int(st["absent"]))
        self.sound.cfg = sound_cfg_norm(dict(self.sound.cfg, confirm=st["confirm"], repeat=st["repeat"]))
        self.alarms.repeat_s = float(self.sound.cfg["repeat"])
        self.strong_chk.setChecked(bool(st["strong"]))
        self.strong_spin.setValue(float(st["strong_lvl"]))
        self.hold_chk.setChecked(bool(st["hold"]))
        self.preset_last = key
        nm = p[1] if key.startswith("u:") else TR(p[1])
        self.set_status(f"⚡ Préréglage « {nm} » appliqué (tout reste modifiable à la main).")
        return True

    # ---------------------------------------------------- 👤 profils utilisateur (7.57)
    def user_profile_save(self, name, path=None):
        """Préférences actuelles -> fichier .tsauser (dans USER_DIR sauf chemin donné). -> chemin ou None."""
        doc = user_doc(self._collect_config(True), name, APP_VER)
        try:
            p_ = Path(path) if path else USER_DIR / user_filename(doc["name"])
            p_.parent.mkdir(parents=True, exist_ok=True)
            p_.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Profil non enregistré :\n{e}")
            return None
        self.user_name = doc["name"]
        self.set_status(f"👤 Profil « {doc['name']} » enregistré ({p_.name}).")
        return p_

    def _user_profile_load_base(self, path):
        """Charge un profil : ses préférences remplacent les tiennes, le show ne bouge pas."""
        try:
            doc = read_user(Path(path).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Profil illisible :\n{e}")
            return False
        self._apply_config(user_apply(self._collect_config(True), doc))
        if "ui_level" in doc["prefs"]:
            self.set_level(doc["prefs"]["ui_level"])
        self.user_apply_layout(doc["prefs"].get("layout"))
        self.user_name = doc["name"]
        self.set_status(f"👤 Profil « {doc['name']} » chargé : affichage, disposition des fenêtres, seuils, alarmes et préréglages perso appliqués.")
        return True

    def user_profile_load(self, path):
        """Profil utilisateur : la partie V7, puis le poste SDR relu (mode, réglages) et relancé / arrêté."""
        ok = self._user_profile_load_base(path)
        if ok:
            self._sdr_reload()
            for e_ in self.sdr_engs.values():
                if self.rf_mode == "tiny":
                    e_.stop()
                elif not e_.running():
                    e_.start()
        return ok

    def user_apply_layout(self, lay):
        """7.57.1 : disposition des fenêtres d'un profil (taille de la fenêtre, panneaux, vraies fenêtres)."""
        if not isinstance(lay, dict) or int(lay.get("layout_ver", 0) or 0) < LAYOUT_VER:
            return False
        try:
            if self.wall_is_fullscreen():
                self.wall_fullscreen(False)
            self.panel_attach_all()
            if lay.get("geometry"):
                self.restoreGeometry(QtCore.QByteArray.fromBase64(str(lay["geometry"]).encode()))
            if lay.get("docks"):
                self.restoreState(QtCore.QByteArray.fromBase64(str(lay["docks"]).encode()))
            self.panel_restore(lay.get("panel_windows"))
        except Exception:  # noqa: BLE001 — écran absent, données illisibles : on garde la disposition actuelle
            return False
        return True

    def open_user_profiles(self):
        if getattr(self, "_userprof", None) is not None:
            self._userprof.refresh()
            self._userprof.show()
            self._userprof.raise_()
            return self._userprof
        self._userprof = UserProfilesDialog(self)
        self._userprof.show()
        return self._userprof

    # ---------------------------------------------------------------- 📺 TNT (7.58)
    def open_tnt(self):
        if getattr(self, "_tnt", None) is not None:
            self._tnt.refresh()
            self._tnt.show()
            self._tnt.raise_()
            return self._tnt
        self._tnt = TntDialog(self)
        self._tnt.show()
        return self._tnt

    def tnt_measure_now(self, src="live", margin=None):
        """Canaux TNT d'après le spectre choisi (max hold, tout le site ou une scène) + choix faits à la main."""
        try:
            F, L = self.coord_FL(src)
        except Exception:  # noqa: BLE001 — pas encore de spectre (démarrage)
            F = L = None
        chans = tnt_channel_list(self.country_combo.currentData() or "FR")
        res = tnt_measure(F, L, chans, float(margin if margin is not None else self.tnt_cfg["margin"]))
        return tnt_apply_manual(res, self.tnt_cfg.get("manual"), self.tnt_cfg.get("plan"))

    def tnt_set_plan(self, chans, src=""):
        """7.58.2 : canaux TV actifs du plan de coordination importé / suivi -> grisés « (plan) » sur le spectre."""
        old = list(self.tnt_cfg.get("plan") or [])
        self.tnt_cfg = tnt_cfg_norm(dict(self.tnt_cfg, plan=list(chans or []), plan_src=src))
        try:
            self.tnt_mark(self.tnt_measure_now())
            if getattr(self, "_tnt", None) is not None and self._tnt.isVisible():
                self._tnt.measure()
        except Exception:  # noqa: BLE001
            pass
        return old != self.tnt_cfg["plan"]

    def tnt_reset(self, clear_peaks=False):
        """↺ Nouveau lieu (tournée) : canaux grisés à la main et canaux TV du plan oubliés -> tout redevient
        automatique (d'après la mesure) ; clear_peaks = pics gardés effacés aussi, pour rescanner le lieu."""
        self.tnt_cfg = tnt_cfg_norm(dict(self.tnt_cfg, manual={}, plan=[], plan_src=""))
        if clear_peaks:
            self.reset_max()
        self.tnt_mark(None)
        if getattr(self, "_tnt", None) is not None:
            try:
                self._tnt.measure()
            except RuntimeError:
                pass
        self.set_status("📺 Canaux TNT remis à zéro : laisse scanner quelques minutes puis clique « Mesurer »."
                        if clear_peaks else "📺 Canaux TNT remis en automatique (d'après la mesure).")

    # ---------------------------------------------------------------- 🧭 7.59 : assistant, propositions, légende
    def open_wizard(self, step=0):
        d = getattr(self, "_wizard", None)
        if d is None:
            d = self._wizard = ShowWizard(self)
        d.go(step)
        d.refresh()
        d.show()
        d.raise_()
        return d

    def _scan_s(self, now=None):
        now = time.time() if now is None else now
        t0 = getattr(self, "_mh_t0", None)
        return (now - t0) if (self.is_running() and t0) else None

    def wizard_info(self):
        q = None
        try:
            q = ready_summary(ready_checks(self.ready_info()))[0]
        except Exception:  # noqa: BLE001
            pass
        code = self.country_combo.currentData() or "FR"
        return dict(name=self.show_meta.get("name", ""), country_name=dict(COUNTRIES).get(code, code),
                    place=self.tnt_cfg.get("place", ""), n_watch=len(self.watch), running=self.is_running(),
                    scan_s=self._scan_s(), tnt_done=bool(self._tnt_items) or self._tnt_measured,
                    tnt_tv=len(self._tnt_items), ready=q)

    def hint_info(self, now=None):
        now = time.time() if now is None else now
        sc = self._scan_s(now)
        chs = []
        if sc is not None and sc >= HINT_TNT_S and not self._tnt_items and "tnt" not in self._hints_done:
            try:
                chs = [r["ch"] for r in self.tnt_measure_now()["rows"] if r["state"] == "tv"]
            except Exception:  # noqa: BLE001
                chs = []
        t0 = getattr(self, "_run_t0", None)
        return dict(running=self.is_running(), scan_s=sc, tnt_tv=len(chs), tnt_chs=chs,
                    tnt_marked=bool(self._tnt_items), n_watch=len(self.watch),
                    run_s=(now - t0) if (t0 and self.is_running()) else 0)

    def _hints_tick(self, now):
        if now < self._hint_next or self.hint_bar.isVisible():
            return
        self._hint_next = now + 5.0
        h = hint_due(self.hint_info(now), self._hints_done)
        if h:
            self.hint_bar.show_hint(*h)

    def show_hint(self, key, text, actions=()):
        self.hint_bar.show_hint(key, text, actions)

    def hint_tnt_mark(self):
        res = self.tnt_measure_now()
        self.tnt_mark(res)
        self.set_status(tnt_summary(res))

    def tnt_mark_saved(self):
        """Canaux grisés À LA MAIN (show / config) remis sur le spectre, même sans mesure."""
        try:
            if any(v == "tv" for v in (self.tnt_cfg.get("manual") or {}).values()) or self.tnt_cfg.get("plan"):
                self.tnt_mark(self.tnt_measure_now())
        except Exception:  # noqa: BLE001
            pass

    def tnt_mark(self, res):
        """Grise les canaux TNT mesurés sur le spectre (None = tout effacer)."""
        if res:
            self._tnt_measured = True
        pi = self.spec.getPlotItem()
        for it in self._tnt_items:
            try:
                pi.removeItem(it)
            except Exception:  # noqa: BLE001
                pass
        self._tnt_items = []
        if not res or not self.tnt_cfg.get("mark", True):
            return 0
        c = QtGui.QColor(self.theme.get("bp_tv", "#3b82f6"))
        c.setAlpha(46)
        lc = QtGui.QColor(self.theme.get("plot_fg", "#8e8e93"))
        prev_hi, alt = None, False
        for r in res.get("rows") or []:
            if r["state"] != "tv":
                continue
            alt = (not alt) if prev_hi is not None and abs(r["lo"] - prev_hi) < 0.01 else False   # canaux collés
            prev_hi = r["hi"]
            reg = pg.LinearRegionItem(values=(r["lo"], r["hi"]), movable=False, brush=pg.mkBrush(c),
                                      pen=pg.mkPen(None))
            reg.setZValue(-20)
            for ln in reg.lines:
                ln.setPen(pg.mkPen(None))
            pg.InfLineLabel(reg.lines[0], text=f"TNT {r['ch']}", position=0.80 if alt else 0.87, anchor=(0, 0),   # sous la légende
                            color=lc)
            pi.addItem(reg, ignoreBounds=True)
            self._tnt_items.append(reg)
        return len(self._tnt_items)

    def tnt_db(self):
        """Base ANFR réduite (sites TNT + codes postaux) ou None si pas encore téléchargée / importée."""
        if self._tnt_db is None and TNT_DB_PATH.exists():
            try:
                d = json.loads(TNT_DB_PATH.read_text(encoding="utf-8"))
                if isinstance(d, dict) and isinstance(d.get("sites"), list):
                    self._tnt_db = d
            except Exception:  # noqa: BLE001
                self._tnt_db = None
        return self._tnt_db

    def tnt_db_save(self, db, date="", source=""):
        db = dict(db, date=date, made=datetime.now().strftime("%Y-%m-%d"), source=source)
        TNT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = TNT_DB_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(db, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, TNT_DB_PATH)
        self._tnt_db = db
        return db

    def open_presets(self):
        if getattr(self, "_presets", None) is not None:
            self._presets.refresh()
            self._presets.show()
            self._presets.raise_()
            return self._presets
        self._presets = PresetDialog(self)
        self._presets.show()
        return self._presets

    # ---------------------------------------------------------------- 🩺 7.68 : diagnostic RF automatique
    def open_rf_diag(self):
        d = getattr(self, "_rfdiag", None)
        if d is not None:
            try:
                d.refresh()
                d.show()
                d.raise_()
                d.activateWindow()
                return d
            except RuntimeError:
                pass
        self._rfdiag = RfDiagDialog(self)
        self._rfdiag.show()
        return self._rfdiag

    def rf_diag_info(self):
        """État de la mesure pour rf_diagnose (PURE)."""
        now = time.time()
        stale = max(15.0, 4 * (getattr(self, "last_cycle", 0.0) or 0.0))
        fresh = [k for k in self.latest if k != ZOOM_ID and now - self.latest_t.get(k, 0) <= stale]
        F = L = None
        if fresh:
            F = np.concatenate([self.latest[k][0] for k in fresh])
            L = np.concatenate([self.latest[k][1] for k in fresh])
            o_ = np.argsort(F)
            F, L = F[o_], L[o_]
        q = self.quality_info() if self.is_running() else {}
        tv = []
        try:
            res = tnt_measure(F, L, tnt_channel_list(self.country_combo.currentData() or "FR")) if F is not None else None
            res = tnt_apply_manual(res, self.tnt_cfg.get("manual"), self.tnt_cfg.get("plan")) if res else None
            tv = [(r_["lo"], r_["hi"], r_["ch"]) for r_ in (res or {}).get("rows", []) if r_["state"] == "tv"]
        except Exception:  # noqa: BLE001
            tv = []
        step = scan_step_khz(F) if F is not None else None
        rbw = self._cfg.get("rbw")
        ws = []
        for w in self.watch:
            if w.get("off") or w.get("muted"):
                continue
            ch = next(((a, b, c) for a, b, c in tv if a <= w["freq"] <= b), None)
            tvl = None
            if ch is not None and F is not None:
                m = (F >= ch[0] + 0.5) & (F <= ch[1] - 0.5) & (np.abs(F - w["freq"]) > 0.3)
                tvl = float(np.median(L[m])) if m.sum() >= 3 else None
            lv = [v for t_, v in w.get("_lvh") or () if now - t_ <= 600]
            ws.append(dict(key=int(round(w["freq"] * 1000)), name=w["name"], freq=w["freq"],
                           keep_free=self.is_keep_free(w["status"]), keep_on=self.is_keep_on(w["status"]),
                           paused=self.w_paused(w), level=w.get("level"),
                           typ=float(np.median(lv)) if len(lv) >= 5 else None, floor=w.get("floor"),
                           margin=w.get("margin"), ethr=w.get("ethr"), own_thr=w.get("thr"),
                           flaps=flap_count(w.get("_flips"), now), state=w.get("state"),
                           tv=ch[2] if ch else None, tv_level=tvl))
        unk = [f for v in self.unk_now.values() for f in v]
        return dict(running=self.is_running(), demo=self.demo_chk.isChecked(), F=F, L=L, rbw=rbw,
                    rbw_est=auto_rbw(step) if (step and not rbw) else None, step_khz=step,
                    lna=self._cfg.get("lna") is True, sat_dbm=q.get("sat_dbm"), thr=self.thr_spin.value(),
                    thr_auto=self.thr_auto, tv=tv, unknown=unk, watch=ws,
                    fmt=lambda v: self.lvl(v, suffix=True))

    def watch_by_key(self, key):
        """Fréquence de la liste d'après sa clé (kHz arrondis) ou None."""
        return next((w for w in self.watch if int(round(w["freq"] * 1000)) == int(key)), None)

    def diag_set_thr(self, key, v):
        """🩺 « Régler » d'un micro pile au seuil : lui donne un seuil propre."""
        w = self.watch_by_key(key)
        if w is None or v is None:
            return
        w["thr"] = float(v)
        self.rebuild_watch_table()
        self.log_event(dict(w, note=f"seuil propre {self.lvl(v, suffix=True)} (diagnostic RF)"), w.get("level"),
                       "RÉGLAGE")
        self.set_status(TR("🩺 {} : seuil propre à {}").format(w["name"] or f"{w['freq']:.3f}",
                                                                self.lvl(v, suffix=True)))
        try:
            self.undo_track()
        except Exception:  # noqa: BLE001
            pass

    def open_replace_key(self, key):
        w = self.watch_by_key(key)
        if w is not None:
            self.open_replace(w)

    def open_ready(self):
        if getattr(self, "_ready", None) is not None:
            self._ready.refresh()
            self._ready.raise_()
            self._ready.activateWindow()
            return self._ready
        self._ready = ReadyDialog(self)
        self._ready.show()
        return self._ready

    def switch_source(self, demo, index=None, restart=True):
        """Démo ↔ tinySA (carte ① de l'accueil). Pendant la surveillance : arrêt propre, bascule, puis reprise (journal de
        Clément 16/11/2026 : la démo se décochait en pleine surveillance, le balayage continuait en démo puis l'appli
        plantait)."""
        def apply():
            self.demo_chk.setChecked(bool(demo))
            if index is not None and 0 <= index < self.port_combo.count():
                self.port_combo.setCurrentIndex(index)
        if not self.is_running():
            apply()
            return
        self.set_status("Changement de source : arrêt de la surveillance…")
        self.toggle_run()
        t_end = time.time() + STOP_FORCE_MS / 1000.0 + 5.0

        def wait():
            if self.is_running():
                if time.time() < t_end:
                    QtCore.QTimer.singleShot(200, wait)
                else:
                    self.set_status("La surveillance ne s'arrête pas : change de source une fois arrêtée.")
                return
            apply()
            if restart:
                QtCore.QTimer.singleShot(300, lambda: self.toggle_run(auto=True))
        QtCore.QTimer.singleShot(200, wait)

    def toggle_demo_off(self):
        if self.is_running():
            self.toggle_run()
        self.demo_chk.setChecked(False)

    def snooze_off(self):
        self.snooze(0)

    def open_sound(self):
        self.open_settings("sound")

    def open_settings_files(self):
        self.open_settings("files")

    # ---------------------------------------------------------------- 🌙 mode festival
    def open_festival(self):
        d = FestivalDialog(self)
        if not d.exec():
            return
        self.festival = festival_cfg_norm(d.values())
        if sys.platform == "win32" and (d.boot_chk.isChecked() or self.windows_startup_on()):   # suit aussi « Garde »
            err = self.set_windows_startup(d.boot_chk.isChecked())
            if err:
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Lancement avec Windows impossible :\n{err}")
        self._keep_awake(self.is_running())
        self._save_config()
        self.set_status("🌙 Mode festival activé." if self.festival["on"] else "Mode festival désactivé.")

    def _festival_autostart(self):
        """Reprise après une coupure : la surveillance tournait quand l'appli s'est arrêtée (sans être fermée)."""
        if self.is_running():
            return
        if not self.demo_chk.isChecked() and not self.port1():
            self.set_status("🌙 Mode festival : reprise impossible, aucun tinySA trouvé (nouvel essai dans 30 s).")
            QtCore.QTimer.singleShot(30000, self._festival_autostart)
            return
        self.log_event(dict(name="Mode festival", freq=0.0, note="la surveillance tournait avant l'arrêt de l'appli"),
                       0.0, "REPRISE AUTO")
        self.toggle_run(auto=True)
        self.set_status("🌙 Mode festival : surveillance reprise automatiquement.")

    def _keep_awake(self, on):
        """Windows : pas de veille pendant la surveillance (mode festival). L'écran peut s'éteindre."""
        want = bool(on and self.festival.get("on") and self.festival.get("nosleep"))
        if want == self._awake or sys.platform != "win32":
            self._awake = want if sys.platform == "win32" else False
            return
        try:
            import ctypes
            es_continuous, es_system = 0x80000000, 0x00000001
            ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | (es_system if want else 0))
            self._awake = want
        except Exception:  # noqa: BLE001
            pass

    def _startup_cmd(self):
        g = " --garde" if self.festival.get("guard") else ""
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"{g}'
        return f'"{sys.executable}" "{Path(__file__).resolve()}"{g}'

    def guard_test(self, how="crash"):
        """💥 / 🧊 Tester la garde : plantage (sortie brutale, code 3) ou appli figée (le fil de l'interface dort
        GUARD_HANG_S + 30 s). La config est enregistrée avant : la surveillance en cours reprend après la relance."""
        if not self.guarded():
            return False
        txt = ("L'appli va planter exprès. La garde doit la rouvrir en quelques secondes ; si la surveillance tourne, "
               "elle reprend toute seule. Continuer ?" if how == "crash" else
               f"L'appli va se figer exprès (plus aucune réponse). La garde doit la fermer au bout de {GUARD_HANG_S:.0f} s "
               "puis la rouvrir. Continuer ?")
        if QtWidgets.QMessageBox.question(self, APP_NAME, txt) != QtWidgets.QMessageBox.StandardButton.Yes:
            return False
        self.log_event(dict(name="Garde", freq=0.0), 0.0, "TEST DE LA GARDE")
        self._save_config()
        if how == "crash":
            os._exit(3)
        time.sleep(GUARD_HANG_S + 30)           # figé : plus de battement -> la garde coupe et relance
        return True

    @staticmethod
    def guarded():
        """L'appli a-t-elle été lancée par la garde (--garde) ?"""
        return bool(os.environ.get("TSM_HEARTBEAT"))

    def relaunch_guarded(self):
        """Ferme l'appli et la relance sous garde ; la surveillance reprend si elle tournait."""
        import subprocess
        frozen = getattr(sys, "frozen", False)
        cmd = [sys.executable] + ([] if frozen else [str(Path(__file__).resolve())]) + ["--garde"]
        env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI_") and k not in ("_MEIPASS2", "_MEIPASS")}
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        running = self.is_running()
        env["TSM_RESUME"] = "1" if running else "0"
        try:
            flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0     # DETACHED + NEW_PROCESS_GROUP
            subprocess.Popen(cmd, env=env, creationflags=flags, close_fds=True,
                             cwd=str(Path(sys.executable).parent if frozen else Path.cwd()))
        except OSError as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Relance impossible :\n{e}")
            return False
        self._closing = not running                     # elle tournait : la garde la fera reprendre
        self._relaunch_resume = running
        self.close()
        return True

    def windows_startup_on(self):
        if sys.platform != "win32":
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                for nm in ("RFTechnicalMonitor", "TinySAMonitor"):       # 8.1 : l'ancien nom compte aussi
                    try:
                        if winreg.QueryValueEx(k, nm)[0]:
                            return True
                    except OSError:
                        pass
                return False
        except OSError:
            return False

    def set_windows_startup(self, on):
        """Programme lancé à l'ouverture de la session Windows (clé Run de l'utilisateur). -> "" ou l'erreur."""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                winreg.KEY_SET_VALUE) as k:
                if on:
                    winreg.SetValueEx(k, "RFTechnicalMonitor", 0, winreg.REG_SZ, self._startup_cmd())
                for nm in (("TinySAMonitor",) if on else ("RFTechnicalMonitor", "TinySAMonitor")):
                    try:
                        winreg.DeleteValue(k, nm)                # 8.1 : l'entrée de l'ancien nom disparaît
                    except FileNotFoundError:
                        pass
            return ""
        except Exception as e:  # noqa: BLE001
            return str(e)

    def _festival_tick(self, now):
        if not self.festival["on"] or now < self._fest_next:
            return
        self._fest_next = now + 30.0
        dt = datetime.now()
        ymd = dt.strftime("%Y-%m-%d")
        if festival_due(ymd, dt.hour, self.festival):
            self.festival["last"] = ymd
            try:
                self.festival_bilan()
                self._save_config()
            except Exception as e:  # noqa: BLE001 — le bilan ne doit jamais faire tomber la surveillance
                self.set_status(f"⚠ Bilan du jour impossible : {e}")

    def festival_bilan(self, test=False):
        """Bilan du jour : rapport HTML (événements depuis le bilan précédent) + message sur le téléphone.
        -> texte de compte rendu."""
        now = datetime.now()
        site = self.notify_cfg.get("site", "") or self.show_meta.get("name", "")
        path = self.log_dir / "rapports" / f"bilan_{now:%Y-%m-%d_%H%M}.html"
        v = dict(title=f"Bilan du {now:%d/%m/%Y}", venue=site, operator="", im=False, open=False,
                 notes="Rapport automatique du mode festival : événements depuis le bilan précédent.")
        rep_txt = ""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(TR.html(build_report_html(self.collect_report(v, self._log_n - self._fest_log_mark))),
                            encoding="utf-8")
            rep_txt = path.name
        except Exception as e:  # noqa: BLE001
            rep_txt = ""
            self.set_status(f"⚠ Rapport du jour impossible : {e}")
        self._fest_log_mark = self._log_n
        running = self.is_running()
        devs = self.ndev()
        devs_ok = sum(self.live_mask()) if running else 0
        run_h = (time.time() - self._t_start) / 3600.0 if running and self._t_start else 0.0
        stats = alarm_stats(self.alarms.listing(), time.time() - 86400.0)
        title, body, ok = festival_text(site, stats, len(self.alarms.active), len(self.alarms.unacked()),
                                        len(self.watch), running, run_h, devs_ok, devs, rep_txt)
        if test:
            title = "[TEST] " + title
        err = self.send_notify(title, body, -1 if ok else 1)
        self.log_event(dict(name="Mode festival", freq=0.0, note=title), 0.0, "BILAN DU JOUR")
        out = f"Rapport : {path}" if rep_txt else "Pas de rapport."
        out += "\n" + (f"Message pas envoyé : {err}" if err else f"Message envoyé : {title}")
        return out

    def im_cause(self, w, f_at=None):
        """Le signal apparu sur w (doit rester libre), mesuré à f_at MHz (son pic), est-il un produit d'intermod de
        tes émetteurs qui émettent ? -> formule (« IM3 : 2×HF 1 − HF 3 ») ou ""."""
        tx = [x for x in self.watch if x is not w and x["state"] in ("occ", "weak") and not self.is_keep_free(x["status"])]
        if len(tx) < 2:
            return ""
        tx.sort(key=lambda x: -(x["level"] if x["level"] is not None else -999.0))
        tx = tx[:25]
        tol = max(0.05, self.win_spin.value() / 1000.0)
        rows, _info = im_explain(w["freq"] if f_at is None else f_at, [x["freq"] for x in tx], (3, 5), 3, tol, 3,
                                 bws=[float(x.get("bw") or 0.0) for x in tx])
        if not rows:
            return ""
        r = rows[0]
        return f"{IM_NAMES.get(r['order'], 'IM')} : " + im_formula(r["terms"], [x["name"] for x in tx])

    def im_note(self, fr, step):
        """Pour un signal inconnu : combinaison d'émetteurs actifs qui pourrait l'expliquer (IM3), sinon ''."""
        act = [w for w in self.watch if w["state"] in ("occ", "weak")]
        if len(act) < 2:
            return ""
        act.sort(key=lambda w: -(w["level"] if w["level"] is not None else -999.0))
        act = act[:25]
        rows, _info = im_explain(fr, [w["freq"] for w in act], (3,), 3, max(0.1, step * 1.5), 3,
                                 bws=[float(w.get("bw") or 0.0) for w in act])
        if not rows:
            return ""
        r = rows[0]
        return f"{IM_NAMES.get(r['order'], 'IM')} probable : " + im_formula(r["terms"], [w["name"] for w in act])

    def add_im_watches(self, items):
        """items = [(MHz, nom)] -> ajoutés à la scène « Intermod », statut « Libre » (doit rester libre)."""
        st = self._resolve_status("Libre")
        known = {int(round(w["freq"] * 1000)) for w in self.watch}
        n = 0
        for f, name in items:
            k = int(round(f * 1000))
            if k in known:
                continue
            known.add(k)
            self._append_watch(name, f, st, None, "Intermod", "Produits")
            n += 1
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        return n

    def add_free_freqs(self, freqs, scene, group, rx=""):
        known = {int(round(w["freq"] * 1000)) for w in self.watch}
        n = 0
        for f in freqs:
            k = int(round(f * 1000))
            if k in known:
                continue
            known.add(k)
            self._append_watch(f"Secours {f:.3f}", f, "", None, scene, group)
            if rx and rx_profile(rx) is not None and self.rx_of(self.watch[-1]) != rx:
                self.watch[-1]["rx"] = rx                 # 7.61 : l'appareil choisi pour la recherche
            n += 1
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        return n
