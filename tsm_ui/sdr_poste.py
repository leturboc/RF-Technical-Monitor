# SDR : poste SDR (moteur et panneaux), temps réel.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class FreqDisplay(QtWidgets.QWidget):
    """Grande fréquence façon poste SDR : chaque chiffre se règle à la MOLETTE (au-dessus du chiffre voulu) ou aux
    flèches (←/→ choisit le chiffre) ; double-clic = taper la fréquence. Signal changed(MHz)."""
    changed = Signal(float)

    def __init__(self, parent=None, pt=24, color=None):
        super().__init__(parent)
        self.hz, self.lo, self.hi = 600000000, 1000, 100000000000
        self.sel, self.hover, self.rects = None, None, []
        self.color = color or "#64d2ff"
        self.fnt = QtGui.QFont("DejaVu Sans Mono")
        self.fnt.setStyleHint(QtGui.QFont.StyleHint.Monospace)
        self.fnt.setPointSize(pt)
        self.fnt.setBold(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setToolTip("Fréquence : molette sur un chiffre = le change ; flèches ←/→ puis ↑/↓ au clavier ;\n"
                        "double-clic = taper la fréquence.")
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)

    def setRange(self, lo_mhz, hi_mhz):
        self.lo, self.hi = int(lo_mhz * 1e6), int(hi_mhz * 1e6)

    def value(self):
        return self.hz / 1e6

    def setValue(self, mhz, emit=False):
        hz = int(min(self.hi, max(self.lo, round(float(mhz) * 1e6))))
        if hz != self.hz:
            self.hz = hz
            self.update()
            if emit:
                self.changed.emit(self.hz / 1e6)

    def sizeHint(self):
        fm = QtGui.QFontMetrics(self.fnt)
        return QtCore.QSize(fm.horizontalAdvance("00000.000 000") + fm.horizontalAdvance(" MHz") // 2 + 40,
                            fm.height() + 16)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        r = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(QtGui.QColor(10, 14, 20))
        p.setPen(QtGui.QPen(QtGui.QColor(self.color if self.hasFocus() else "#2c3440"), 1.2))
        p.drawRoundedRect(r, 8, 8)
        txt, places = freq_digits(self.hz)
        fm = QtGui.QFontMetrics(self.fnt)
        p.setFont(self.fnt)
        x = 12.0
        y = (self.height() + fm.ascent() - fm.descent()) / 2.0
        self.rects = []
        lead = True
        for ch, pl in zip(txt, places):
            w = fm.horizontalAdvance(ch)
            if pl and ch != "0":
                lead = False
            col = QtGui.QColor(self.color)
            if pl and lead and pl >= 1e7:
                col.setAlpha(70)                          # zéros de tête discrets
            if pl and pl == self.sel and self.hasFocus():
                p.fillRect(QtCore.QRectF(x - 1, 4, w + 2, self.height() - 8), QtGui.QColor(100, 210, 255, 50))
            if pl and pl == self.hover:
                p.fillRect(QtCore.QRectF(x, self.height() - 6, w, 2), QtGui.QColor(self.color))
            p.setPen(col)
            p.drawText(QtCore.QPointF(x, y), ch)
            if pl:
                self.rects.append((QtCore.QRectF(x, 0, w, self.height()), pl))
            x += w
        small = QtGui.QFont(self.fnt)
        small.setPointSize(max(8, self.fnt.pointSize() // 2))
        p.setFont(small)
        p.setPen(QtGui.QColor("#8e8e93"))
        p.drawText(QtCore.QPointF(x + 6, y), "MHz")
        p.end()

    def _place_at(self, pos):
        return next((pl for rc, pl in self.rects if rc.contains(QtCore.QPointF(pos))), None)

    def _bump(self, place, sign):
        if place:
            self.setValue((self.hz + sign * place) / 1e6, emit=True)

    def wheelEvent(self, ev):
        pl = self._place_at(ev.position()) or self.sel or 1000
        self._bump(pl, 1 if ev.angleDelta().y() > 0 else -1)
        ev.accept()

    def mouseMoveEvent(self, ev):
        h = self._place_at(ev.position())
        if h != self.hover:
            self.hover = h
            self.update()

    def leaveEvent(self, _ev):
        self.hover = None
        self.update()

    def mousePressEvent(self, ev):
        self.sel = self._place_at(ev.position()) or self.sel
        self.setFocus()
        self.update()

    def mouseDoubleClickEvent(self, _ev):
        v, ok = QtWidgets.QInputDialog.getDouble(self, TR("Fréquence"), TR("Fréquence (MHz) :"), self.hz / 1e6,
                                                 self.lo / 1e6, self.hi / 1e6, 4)
        if ok:
            self.setValue(v, emit=True)

    def keyPressEvent(self, ev):
        pls = [pl for _rc, pl in self.rects]
        if not pls:
            return
        if self.sel not in pls:
            self.sel = 1000 if 1000 in pls else pls[-1]
        i = pls.index(self.sel)
        k = ev.key()
        if k == Qt.Key.Key_Left and i > 0:
            self.sel = pls[i - 1]
        elif k == Qt.Key.Key_Right and i < len(pls) - 1:
            self.sel = pls[i + 1]
        elif k in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._bump(self.sel, 1 if k == Qt.Key.Key_Up else -1)
        else:
            super().keyPressEvent(ev)
            return
        self.update()


class SMeterGauge(QtWidgets.QWidget):
    """Vu-mètre du signal reçu, en mots simples : échelle en dBm (−120 → −20) graduée tous les 5 dB (valeurs écrites
    tous les 10 / 20 dB), zones en couleur (très faible · faible · bon · fort · trop fort) et « −62 dBm · bon » ; la
    crête redescend doucement. 8.1 : deux affichages au choix (clic ou clic droit) : aiguille (analogique) ou barre
    (linéaire, comme le vu-mètre du générateur) ; choix gardé dans les réglages SDR (« meter_style »)."""
    LO, HI = -125.0, -15.0
    ZONES = ((-125.0, -95.0, "#ff453a"), (-95.0, -80.0, "#ff9f0a"), (-80.0, -30.0, "#30d158"), (-30.0, -15.0, "#ff453a"))
    S_LO, S_HI = -120, -20                              # échelle graduée

    def __init__(self, parent=None, small=False, owner=None):
        super().__init__(parent)
        self.dbm, self.peak, self.small = None, None, small
        self.owner = owner or getattr(parent, "owner", None)
        st = (getattr(self.owner, "sdr_cfg", None) or {}).get("meter_style")
        self.style = st if st in dict(METER_STYLES) else "analog"
        self._sizes()
        self.setToolTip(TR("Force du signal reçu dans le canal écouté (dBm) :\n"
                           "rouge à gauche = très faible (risque de décrochage), orange = faible, vert = bon,\n"
                           "rouge à droite = trop fort (le SDR sature : baisse la sensibilité).\n"
                           "Le petit trait orange = le plus fort récemment. Valeurs justes si le SDR est calé (avec un tinySA).\n"
                           "Clic = changer d'affichage (aiguille / barre)."))

    def _sizes(self):
        if self.style == "bar":
            self.setMinimumSize(150 if self.small else 230, 46 if self.small else 56)
        else:
            self.setMinimumSize(130 if self.small else 190, 70 if self.small else 100)
        self.updateGeometry()

    def set_style(self, style):
        if style in dict(METER_STYLES) and style != self.style:
            self.style = style
            self._sizes()
            self.update()

    def _choose(self, style):
        o = self.owner
        if o is not None and hasattr(o, "set_meter_style"):
            o.set_meter_style(style)
        else:
            self.set_style(style)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            m = QtWidgets.QMenu(self)
            for k, t in METER_STYLES:
                a = m.addAction(TR(t))
                a.setCheckable(True)
                a.setChecked(k == self.style)
                a.triggered.connect(lambda *_, k=k: self._choose(k))
            m.exec(e.globalPosition().toPoint())
        else:
            self._choose("bar" if self.style == "analog" else "analog")

    def set_dbm(self, dbm):
        self.dbm = dbm
        if dbm is not None:
            self.peak = dbm if self.peak is None or dbm > self.peak else self.peak - 0.4
        self.update()

    def format(self):
        if self.dbm is None:
            return "—"
        return f"{self.dbm:.0f} dBm · {level_words(self.dbm, TR)[0]}"

    def _ang(self, v):
        f = (min(self.HI, max(self.LO, v)) - self.LO) / (self.HI - self.LO)
        return math.radians(150.0 - 120.0 * f)

    def _frame(self, p, W, H):
        p.setBrush(QtGui.QColor(10, 14, 20))
        p.setPen(QtGui.QPen(QtGui.QColor("#2c3440"), 1.2))
        p.drawRoundedRect(QtCore.QRectF(1, 1, W - 2, H - 2), 8, 8)

    def _text(self, p, f, W, y, h):
        f.setPointSize(8 if self.small else 10)
        f.setBold(True)
        p.setFont(f)
        word, tone = level_words(self.dbm, TR)
        col = {"bad": "#ff453a", "warn": "#ff9f0a", "ok": "#30d158"}.get(tone, "#ffffff")
        p.setPen(QtGui.QColor(col if self.dbm is not None else "#8e8e93"))
        txt = self.format() if not self.small or self.dbm is None else f"{self.dbm:.0f} dBm"
        txt = QtGui.QFontMetrics(f).elidedText(txt, Qt.TextElideMode.ElideRight, W - 8)
        p.drawText(QtCore.QRectF(0, y, W, h), Qt.AlignmentFlag.AlignCenter, txt)

    def paintEvent(self, _ev):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        self._frame(p, W, H)
        if self.style == "bar":
            self._paint_bar(p, W, H)
        else:
            self._paint_analog(p, W, H)
        p.end()

    def _paint_analog(self, p, W, H):
        txt_h = 14 if self.small else 18
        R = min((W - 16) / (2 * math.cos(math.radians(30))), (H - txt_h - 10) / (1 - math.sin(math.radians(30)) + 0.12))
        R = max(20.0, R * 0.98)
        cx, cy = W / 2.0, 6 + R
        for v0, v1, col in self.ZONES:
            p.setPen(QtGui.QPen(QtGui.QColor(col), 4))
            a0, a1 = math.degrees(self._ang(v0)), math.degrees(self._ang(v1))
            p.drawArc(QtCore.QRectF(cx - R, cy - R, 2 * R, 2 * R), int(a1 * 16), int((a0 - a1) * 16))
        arc_px = R * math.radians(120.0) * (self.S_HI - self.S_LO) / (self.HI - self.LO)
        mins, mids, labs = meter_ticks(self.S_LO, self.S_HI, arc_px, label_px=30 if self.small else 26)
        f = QtGui.QFont()
        f.setPointSize(7)
        p.setFont(f)
        pt = lambda r, a: QtCore.QPointF(cx + r * math.cos(a), cy - r * math.sin(a))  # noqa: E731
        p.setPen(QtGui.QPen(QtGui.QColor(199, 199, 204, 120), 1.0))
        for v in mins:
            a = self._ang(v)
            p.drawLine(pt(R - 3, a), pt(R, a))
        p.setPen(QtGui.QPen(QtGui.QColor(199, 199, 204, 190), 1.1))
        for v in mids:
            a = self._ang(v)
            p.drawLine(pt(R - 5, a), pt(R, a))
        for v in labs:
            a = self._ang(v)
            p.setPen(QtGui.QPen(QtGui.QColor("#c7c7cc"), 1.3))
            p.drawLine(pt(R - 7, a), pt(R, a))
            q = pt(R - 16, a)
            p.drawText(QtCore.QRectF(q.x() - 14, q.y() - 6, 28, 12), Qt.AlignmentFlag.AlignCenter, str(v))
        if self.peak is not None:
            a = self._ang(self.peak)
            p.setPen(QtGui.QPen(QtGui.QColor("#ff9f0a"), 2))
            p.drawLine(pt(R - 9, a), pt(R + 1, a))
        a = self._ang(self.dbm if self.dbm is not None else self.LO)
        p.setPen(QtGui.QPen(QtGui.QColor("#ffffff" if self.dbm is not None else "#555555"), 2))
        p.drawLine(pt(0.45 * R, a), pt(R - 4, a))
        self._text(p, f, W, H - txt_h - 5, txt_h)

    def _paint_bar(self, p, W, H):
        x0, x1 = 8.0, W - 8.0
        txt_h = 14 if self.small else 16
        y0, bh = 6.0, (7.0 if self.small else 9.0)
        pos = lambda v: x0 + (x1 - x0) * (min(self.HI, max(self.LO, v)) - self.LO) / (self.HI - self.LO)  # noqa: E731
        for v0, v1, col in self.ZONES:                  # bandeau des zones sous la barre
            c = QtGui.QColor(col)
            c.setAlpha(60)
            p.setPen(QtCore.Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawRect(QtCore.QRectF(pos(v0), y0, pos(v1) - pos(v0), bh))
        if self.dbm is not None:
            word, tone = level_words(self.dbm, TR)
            p.setBrush(QtGui.QColor({"bad": "#ff453a", "warn": "#ff9f0a", "ok": "#30d158"}.get(tone, "#c7c7cc")))
            p.drawRoundedRect(QtCore.QRectF(x0, y0, max(0.0, pos(self.dbm) - x0), bh), 2, 2)
        if self.peak is not None:
            p.setPen(QtGui.QPen(QtGui.QColor("#ff9f0a"), 2))
            p.drawLine(QtCore.QPointF(pos(self.peak), y0 - 2), QtCore.QPointF(pos(self.peak), y0 + bh + 2))
        px = pos(self.S_HI) - pos(self.S_LO)
        mins, mids, labs = meter_ticks(self.S_LO, self.S_HI, px, label_px=30 if self.small else 28)
        f = QtGui.QFont()
        f.setPointSize(7)
        p.setFont(f)
        yt = y0 + bh + 1
        for vs, ln, col in ((mins, 2.5, QtGui.QColor(199, 199, 204, 110)), (mids, 4.0, QtGui.QColor(199, 199, 204, 180)),
                            (labs, 5.5, QtGui.QColor("#c7c7cc"))):
            p.setPen(QtGui.QPen(col, 1.0))
            for v in vs:
                p.drawLine(QtCore.QPointF(pos(v), yt), QtCore.QPointF(pos(v), yt + ln))
        p.setPen(QtGui.QColor("#c7c7cc"))
        for v in labs:
            p.drawText(QtCore.QRectF(pos(v) - 15, yt + 5, 30, 11), Qt.AlignmentFlag.AlignCenter, str(v))
        self._text(p, f, W, H - txt_h - 3, txt_h)


class SdrEngine(QtCore.QObject):
    """V8 étape 16 : LE poste SDR de l'appli (un seul flux, partagé par les panneaux Récepteur / Spectre / Waterfall /
    Mes micros) : récepteurs A et B, spectre sans trou, surveillance de la fenêtre (sdr_listen_feed), son, recentrage
    tout seul quand A sort de la fenêtre. Moteur = RealtimeWorker (même code que la fenêtre Temps réel)."""
    frame = Signal(object)
    changed = Signal()
    status = Signal(str)

    def __init__(self, owner, pid=1):
        super().__init__(owner)
        self.owner, self.pid = owner, int(pid)
        st = station_norm(self._st_cfg())
        self.a, self.b, self.b_on, self.step = st["a"], st["b"], st["b_on"], st["step"]
        self.vol, self.sq, self.split, self.nfft, self.maxhold = st["vol"], st["sq"], st["split"], st["nfft"], st["maxhold"]
        d0 = DEMOD_PRESETS[0] if DEMOD_PRESETS else None
        dp = demod_preset(d0[0]) if d0 else None
        self.demod = dict(mode=(dp or {}).get("mode", "wfm"), compander=(dp or {}).get("comp", "none"),
                          deemph=float((dp or {}).get("deemph", 50.0)), dev=(dp or {}).get("dev"),
                          cut=(dp or {}).get("cut"), audio=(dp or {}).get("audio"))
        self.worker = self.audio = self.wav = None
        self.center, self.rate, self.last, self.paused, self.msg = None, None, None, [], ""
        self.demod_key, self.cur_mic, self.demod_how = (d0[0] if d0 else None), None, None   # étape 19
        self._t_feed = 0.0
        self.q = deque(maxlen=60)
        self.af = deque(maxlen=8)                       # derniers blocs de son (spectre du son)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._pump)
        self.retune = QtCore.QTimer(self)
        self.retune.setSingleShot(True)
        self.retune.timeout.connect(self._restart)
        # étape 20 : alarme -> calage + son, patrouille, pilote, « c'est quoi »
        self.pre = PreRing(ALARM_REC_PRE_S, LISTEN_RATE * 4)
        self._a_t, self._internal, self._user_t = time.time(), False, 0.0
        self.patrol, self._back, self.arec = None, None, None
        self._seen_al, self._al_key_t, self._al_until = set(), {}, 0.0
        self._pil_hist, self._pil_miss, self._pil_bad, self.pil_v = None, None, None, None
        self.what, self._t_what = None, 0.0
        self.pil_pending, self._al_offer, self._pil_ok_t, self._pil_key = None, None, None, None   # audit
        rm = owner.sdr_cfg.get("rewind_min", 3)
        self.rew = RewindBuffer(int(rm) if rm in REWIND_MINUTES else 3, LISTEN_RATE * 4)        # étape 22 : ⏪
        self.tick = QtCore.QTimer(self)
        self.tick.timeout.connect(self._tick)
        # 8.2 : diagnostic du poste (posés ici : un attribut absent ne doit jamais être lu par défaut)
        self.hist, self.sess_rows = deque(maxlen=SDR_HIST_MAX), deque(maxlen=43200)
        self._sess, self._fails, self.recon, self._recovering = None, 0, 0, False
        self._qst, self._mst, self.sess_t0, self._t_dg, self._t_row = {}, {}, time.time(), 0.0, 0.0

    # ---- poste (étape 17 : plusieurs SDR)
    def _st_cfg(self):
        c = self.owner.sdr_cfg
        return c.get("station") if self.pid == 1 else (c.get("stations") or {}).get(str(self.pid))

    def post(self):
        return next((p for p in sdr_posts_norm(self.owner.sdr_cfg.get("posts")) if p["id"] == self.pid),
                    dict(id=self.pid, name=f"SDR {self.pid}", model="", serial="", scenes=[], mics=[]))

    def name(self):
        return self.post()["name"]

    def ws(self):
        """Micros suivis par ce poste (choisis, sinon ceux de ses scènes, sinon tous)."""
        p = self.post()
        return post_watch(self.owner.watch, p["scenes"], p.get("mics"))

    def bid(self):
        """« Bande » de ses mesures dans la surveillance (une par poste)."""
        return self.owner.SDR_LISTEN_ID if self.pid == 1 else -100 - self.pid

    # ---- appareil
    def model(self):
        if self.owner.sdr_cfg.get("demo"):                 # étape 21 : SDR démo (sans matériel)
            return SDR_DEMO_MODEL
        m = sdr_model(self.post()["model"] or self.owner.sdr_cfg.get("model"))
        return m if m and m.get("kind") else sdr_model(SDR_MODEL_DEFAULT.get("hackrf"))

    def kind(self):
        return (self.model() or {}).get("kind") or "hackrf"

    def span(self):
        m = self.model()
        return sdr_span_mhz(m, self.rate or sdr_rate(m, self.kind()))

    def running(self):
        return self.worker is not None

    def dbm(self, lv):
        return None if lv is None else float(lv) + self.owner.sdr_offset(self.kind())

    def save(self):
        st = dict(a=self.a, b=self.b, b_on=self.b_on, step=self.step, vol=self.vol, sq=self.sq,
                  split=self.split, nfft=self.nfft, maxhold=self.maxhold)
        if self.pid == 1:
            self.owner.sdr_cfg["station"] = st
        else:
            self.owner.sdr_cfg.setdefault("stations", {})[str(self.pid)] = st

    # ---- marche / arrêt
    def start(self):
        o = self.owner
        if self.worker is not None:
            return True
        for d in (getattr(o, "_multimon", None), getattr(o, "_listen", None), getattr(o, "_rt", None)):
            if d is not None and getattr(d, "worker", None) is not None:
                self._say(TR("⚠ Le SDR est déjà pris (moniteur, écoute ou temps réel) : ferme-les d'abord."))
                return False
        m, kind = self.model(), self.kind()
        others = [(e_.pid, e_.kind(), e_.post()["serial"]) for e_ in (getattr(o, "sdr_engs", None) or {}).values()
                  if e_ is not self and e_.running()]
        if kind != "demo" and sdr_post_clash([(self.pid, kind, self.post()["serial"])] + others):   # 17 : un SDR = un poste
            self._say(TR("⚠ Un autre poste utilise déjà un {} : donne à chacun son n° de série (📡 Mes SDR).").format(
                m["name"]))
            return False
        self.rate = sdr_rate(m, kind)
        if self.a is None or not sdr_in_range(m, self.a):
            ws = [w["freq"] for w in self.ws() if sdr_in_range(m, w["freq"])]
            self.a = ws[0] if ws else (600.0 if sdr_in_range(m, 600.0) else (m["fmin"] + m["fmax"]) / 2.0)
        if self.b is None or not sdr_in_range(m, self.b):
            self.b = round(self.a + 0.2, 6)
        self.center = vfo_center(self.a, self.span())
        if not self.paused:
            self.paused = [w for w in o.workers if w.isRunning() and getattr(w, "sdr", False)
                           and (parse_sdr_addr(getattr(w, "port", "")) or ("",))[0] == kind]
            for w in self.paused:
                w.paused = True
        w = self.worker = RealtimeWorker(kind, self.center, self.rate, self.nfft, o.sdr_gains(kind),
                                         serial=self.post()["serial"], tool=getattr(o, "_listen_tool", None),
                                         tool_dir=o.sdr_cfg.get("dir", ""))
        w.listen, w.listen_b, w.split = self._listen("a"), self._listen("b"), self.split
        w.frame.connect(lambda fr, w_=w: self._frame_in(fr) if w_ is self.worker else None)
        w.stopped.connect(lambda why, w_=w: self._stopped(why) if w_ is self.worker else None)
        w.status.connect(lambda t, w_=w: self._say(t) if w_ is self.worker else None)
        if self.audio is None:
            self.audio = AudioPump(self.q, sdr_audio_device(self.owner))   # 8.1 : son nourri par son propre fil
            self.audio.start()
        self.timer.start(10)                             # 8.1 : son nourri plus souvent (moins de trous)
        if kind == "demo":                              # étape 21 : le SDR démo connaît tout de suite tes micros
            self._t_demo = time.time()
            sdr_demo_set(plan=demo_sdr_plan(o.demo_mics()))
        if not self.tick.isActive():                    # étape 20 : seules les alarmes NOUVELLES font se caler
            self._seen_al = {a.get("id") for a in o.alarms.active.values()}
            self.tick.start(500)
        QtCore.QTimer.singleShot(300 if self.paused else 0, w.start)
        self._qst, self._mst = {}, {}
        if getattr(self, "_fails", 0) or getattr(self, "_recovering", False):
            self._recovering = True                      # reconnexion : « SDR revenu » à la 1re trame
            self._ev("retry", TR("essai n° {}").format(getattr(self, "recon", 0)), journal=False)
        else:
            self._sess_open()
            self._ev("start", (m or {}).get("name", ""))
        self.changed.emit()
        return True

    def stop(self, keep_paused=False, user=True):
        self.timer.stop()
        self.retune.stop()
        if getattr(self, "_retry", None) is not None and not keep_paused and user:
            self._retry.stop()
        if self.worker is not None and not keep_paused and user:
            self._recovering = False
            self._ev("stop", "", journal=False)
            self._sess_close()
        w, self.worker = self.worker, None
        if w is not None:
            w.requestInterruption()
            w.wait(5000)
        if not keep_paused:
            if self.audio is not None:
                self.audio.close()
                self.audio = None
            for w_ in self.paused:
                w_.paused = False
            self.paused = []
            self.rec_audio(False)
            self.tick.stop()                             # étape 20
            self._arec_end()
            self.patrol, self._back = None, None
            self._pilot_alarm(None)
        self.owner.sdr_listen_clear(self.bid())
        self.changed.emit()

    def _restart(self):
        if self.worker is None:
            return
        self.stop(keep_paused=True)
        self.start()

    def _stopped(self, why):
        self.stop(user=not why)
        if why:
            hint = TR(" Pas de SDR sous la main ? Essaie 🧪 SDR démo (menu du mode).") if "introuvable" in why else ""
            self._ev("lost", why)
            if not hint:                                 # 8.2 : SDR décroché -> nouvel essai tout seul (3, 10, 30 s)
                self._recovering = True
                self._fails = getattr(self, "_fails", 0) + 1
                self.recon = getattr(self, "recon", 0) + 1
                d = reconnect_delay(self._fails)
                self._retry_t().start(int(d * 1000))
                hint = " — " + TR("nouvel essai dans {} s").format(f"{d:.0f}")
            self._say(TR("⚠ SDR arrêté : {}").format(why) + hint)

    def _retry_t(self):
        t = getattr(self, "_retry", None)
        if t is None:
            t = self._retry = QtCore.QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda: self.start() if self.worker is None else None)
        return t

    # ---- 8.2 : historique des événements du poste, session enregistrée
    def _ev(self, kind, text="", journal=None):
        o = self.owner
        lv = None
        fr = self.last
        if fr is not None and self.worker is not None:
            lv = fr.get("lv_a")
        ev = sdr_event(kind, text, time.time(), dict(a=self.a, lv=lv), sim=self.kind() == "demo")
        if not hasattr(self, "hist"):
            self.hist = deque(maxlen=SDR_HIST_MAX)
        self.hist.append(ev)
        if journal is None:
            journal = ev["sev"] in ("warn", "bad")
        if journal:
            try:
                o.log_event(dict(name=self.name(), freq=float(self.a or 0.0),
                                 note=TR(ev["label"]) + (f" · {text}" if text else "")), float(lv or 0.0), "SDR FLUX")
            except Exception:  # noqa: BLE001
                pass
        f = getattr(self, "_sess", None)
        if f is not None:
            try:
                f["ev"].writerow(sdr_event_row(ev))
                f["evf"].flush()
            except Exception:  # noqa: BLE001
                pass
        self.changed.emit()
        return ev

    def _sess_open(self):
        """Session du poste (8.2) : une ligne toutes les 2 s + les événements, en CSV dans
        <journaux>/sessions_sdr/<date>/ (désactivable : Diagnostic › Session)."""
        self._sess_close()
        self.sess_rows = deque(maxlen=43200)
        self.sess_t0 = time.time()
        if not self.owner.sdr_cfg.get("sdr_session", True):
            return
        try:
            d = Path(self.owner.log_dir) / "sessions_sdr" / datetime.now().strftime("%Y-%m-%d")
            d.mkdir(parents=True, exist_ok=True)
            base = d / f"sdr{self.pid}_{datetime.now():%H%M%S}"
            rf = open(str(base) + "_mesures.csv", "w", newline="", encoding="utf-8-sig")
            ef = open(str(base) + "_evenements.csv", "w", newline="", encoding="utf-8-sig")
            rw, ew = csv.writer(rf, delimiter=";"), csv.writer(ef, delimiter=";")
            rw.writerow(SDR_SESSION_HEAD)
            ew.writerow(SDR_EVENTS_HEAD)
            self._sess = dict(rf=rf, evf=ef, rows=rw, ev=ew, base=str(base))
        except OSError as ex:
            self._sess = None
            log_crash("Session SDR", repr(ex))

    def _sess_close(self):
        f, self._sess = getattr(self, "_sess", None), None
        if f:
            for k in ("rf", "evf"):
                try:
                    f[k].close()
                except Exception:  # noqa: BLE001
                    pass

    def _diag_tick(self, now):
        """1 fois par seconde : transitions de la qualité du flux, porteuse sans son, ligne de session."""
        fr = self.last
        if self.worker is None or fr is None or now - getattr(self, "_t_dg", 0.0) < 1.0:
            return
        self._t_dg = now
        if not hasattr(self, "_qst"):
            self._qst = {}
        for kind, txt in sdr_quality_events(self._qst, fr.get("q"), fr.get("ovf") or 0.0, now):
            self._ev(kind, txt)
        car = None
        try:
            if fr.get("lv_a") is not None and len(fr.get("avg", ())):
                car = float(fr["lv_a"]) - float(np.median(fr["avg"]))
            raw = list(getattr(self.worker, "a_raw", ()))[-6:]
            adb = audio_meter(np.concatenate(raw))["rms"] if raw else None
        except Exception:  # noqa: BLE001
            adb = None
        if self.demod.get("mode") in ("wfm", "nfm", "wfm_st", "am"):
            ch = mute_check(self.__dict__.setdefault("_mst", {}), car, adb, now)
            if ch == "on":
                self._ev("mute_on", f"{self.a:.4f} MHz" if self.a is not None else "")
            elif ch == "off":
                self._ev("mute_off", "")
        if now - getattr(self, "_t_row", 0.0) >= 2.0:
            self._t_row = now
            q = fr.get("q") or {}
            row = [now, self.a, fr.get("lv_a"), q.get("lost"), q.get("gaps") or 0, 100.0 * (fr.get("ovf") or 0.0),
                   100.0 * (fr.get("load") or 0.0)]
            if not hasattr(self, "sess_rows"):
                self.sess_rows = deque(maxlen=43200)
            self.sess_rows.append(row)
            f = getattr(self, "_sess", None)
            if f is not None:
                try:
                    f["rows"].writerow(sdr_session_row(now, self.a, fr.get("lv_a"), q, fr.get("ovf"), fr.get("load"),
                                                       self.kind() == "demo"))
                    f["rf"].flush()
                except Exception:  # noqa: BLE001
                    pass

    def session_report(self, path):
        """Rapport de la session (HTML, ou PDF si le chemin finit par .pdf) -> chemin."""
        m = self.model() or {}
        rows = list(getattr(self, "sess_rows", []))
        meta = dict(name=self.name(), model=m.get("name", ""), sim=self.kind() == "demo",
                    t0=getattr(self, "sess_t0", rows[0][0] if rows else time.time()), t1=time.time())
        html = sdr_session_html(meta, rows, list(getattr(self, "hist", [])), TR)
        if str(path).lower().endswith(".pdf"):
            doc = QtGui.QTextDocument()
            doc.setHtml(re.sub(r"<svg.*?</svg>", "", html, flags=re.S))
            w = QtGui.QPdfWriter(str(path))
            w.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
            doc.print_(w)
        else:
            write_atomic(path, html)
        return path

    def quality(self):
        """8.2 : qualité du flux (dernière trame) -> (texte, ton) ; None si le SDR ne tourne pas."""
        fr = self.last if self.worker is not None else None
        if fr is None:
            return None
        txt, tone = stream_quality(fr.get("q"), fr.get("ovf") or 0.0, TR)
        if getattr(self, "recon", 0):
            txt += " · " + TR("{} reconnexion(s)").format(self.recon)
        return txt, tone

    def _say(self, t):
        self.msg = t
        self.status.emit(t)

    # ---- réglages (A, B, démodulation…) : appliqués tout de suite au flux
    def _listen(self, slot):
        f = self.a if slot == "a" else (self.b if self.b_on else None)
        if f is None:
            return None
        return dict(f=float(f), volume=float(self.vol), sq=self.sq, **self.demod)

    def _push(self):
        w = self.worker
        if w is not None:
            w.listen, w.listen_b, w.split = self._listen("a"), self._listen("b"), self.split
        self.save()
        self.changed.emit()

    def mic_at(self, f, tol=0.0015):
        """Le micro de ce poste réglé sur f (± 1,5 kHz), ou None."""
        ws = [w for w in self.ws() if abs(w["freq"] - f) <= tol]
        return min(ws, key=lambda w: abs(w["freq"] - f)) if ws else None

    def set_demod_key(self, key, push=True):
        """Réglage d'écoute d'après un préréglage (démodulation, compander, désaccentuation…)."""
        d = demod_preset(key)
        if d is None:
            return False
        self.demod_key = key
        self.demod = dict(mode=d.get("mode", "wfm"), compander=d.get("comp", "none"), deemph=float(d.get("deemph", 50.0)),
                          dev=d.get("dev"), cut=d.get("cut"), audio=d.get("audio"))
        if push:
            self._push()
        return True

    def set_a(self, f):
        m = self.model()
        f = round(float(f), 6)
        if m and not sdr_in_range(m, f):
            return False
        if self.a is None or abs(self.a - f) > 1e-6:    # étape 20 : autre fréquence -> tampon et pilote repartent
            self.pre = PreRing(ALARM_REC_PRE_S, LISTEN_RATE * 4)
            self._a_t, self._pil_hist, self._pil_miss, self._pil_bad, self.pil_v = time.time(), None, None, None, None
            self.pil_pending = None
            self.what, self._t_what = None, 0.0
        if not self._internal:                          # tu as pris la main (même sur le micro en cours) : stop
            self._user_t = time.time()
            if self.patrol is not None:
                self.patrol = None
                self._say(TR("🔁 Patrouille arrêtée : tu as choisi une fréquence."))
            self._back = None
        self.a = f
        w = self.mic_at(f)                               # étape 19
        self.rew.push_tune(time.time(), f, (w or {}).get("name", ""))     # étape 22 : ⏪ A dans le temps : on tombe sur un micro -> SON réglage d'écoute
        self.cur_mic = w
        if w is not None:                                # (recalculé à chaque fois : groupe / nom changés)
            new = w is not getattr(self, "_mic_done", None)
            self._mic_done = w
            key, how = self.owner.mic_demod(w)
            self.demod_how = how
            if key == DEMOD_DIGITAL:
                if new:
                    self._say(TR("📵 {} : système numérique, il ne s'écoute pas (son chiffré). Le niveau et la santé "
                                  "RF restent surveillés.").format(w["name"] or f"{w['freq']:.3f}"))
            elif key and key != self.demod_key:
                self.set_demod_key(key, push=False)
        elif w is None:
            self._mic_done, self.demod_how = None, None
        if self.worker is not None and not vfo_inside(self.center, self.span(), f):
            self.retune.start(350)                      # hors de la fenêtre : on recentre (après le réglage)
        self._push()
        return True

    def set_b(self, f=None, on=None):
        if f is not None:
            m = self.model()
            if m and not sdr_in_range(m, f):
                return False
            self.b = round(float(f), 6)
            if self.worker is not None and self.b_on and not vfo_inside(self.center, self.span(), self.b):
                self._say(TR("B est hors de la fenêtre du SDR ({} MHz autour de A) : il ne s'entend pas.").format(
                    f"{self.span():.1f}"))
        if on is not None:
            self.b_on = bool(on)
        self._push()
        return True

    def set_opts(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        if "nfft" in kw and self.worker is not None:
            self.retune.start(100)
        self._push()

    # ---- flux
    def _frame_in(self, fr):
        """Trame reçue : on ne garde que la DERNIÈRE en attente (pics des trames sautées fusionnés). Sans ça, avec 2 SDR
        (ou un PC lent) l'interface prenait du retard sans fin : minuteries, son et clics figés."""
        p = getattr(self, "_fr_pend", None)
        if p is not None and len(p.get("mx", ())) == len(fr.get("mx", ())):
            try:
                fr = dict(fr, mx=np.maximum(p["mx"], fr["mx"]))
            except Exception:  # noqa: BLE001
                pass
        self._fr_pend = fr
        if not getattr(self, "_fr_sched", False):
            self._fr_sched = True                       # 8.1 : 12 images / s au plus (l'œil ne voit pas plus, et le
            wait = max(0.0, 0.083 - (time.monotonic() - getattr(self, "_fr_last", 0.0)))   # PC garde de la marge)
            QtCore.QTimer.singleShot(int(wait * 1000), self._frame_go)

    def _frame_go(self):
        self._fr_sched = False
        self._fr_last = time.monotonic()
        fr, self._fr_pend = getattr(self, "_fr_pend", None), None
        if fr is not None and self.worker is not None:
            self._frame(fr)

    def _frame(self, fr):
        self.last = fr
        self._fails = 0                                  # 8.2 : des données arrivent : le compte des échecs repart
        if getattr(self, "_recovering", False):
            self._recovering = False
            self._ev("back", TR("après {} reconnexion(s)").format(getattr(self, "recon", 0)))
        now = time.time()
        if now - self._t_feed >= 0.5 and len(fr["F"]) == len(fr["avg"]):
            self._t_feed = now                          # la fenêtre du SDR surveille aussi tes fréquences
            self.owner.sdr_listen_feed(self.kind(), fr["F"], fr["avg"], self.bid())
        try:
            if len(fr["F"]) == len(fr["avg"]):
                self.rew.push_frame(now, fr["F"], fr["avg"])      # étape 22 : ⏪
            self._watch_a(fr, now)                       # étape 20 : pilote et « c'est quoi » de A
        except Exception:  # noqa: BLE001
            pass
        self.frame.emit(fr)

    def _pump(self):
        w = self.worker
        if w is None:
            return
        while w.audio:
            b = w.audio.popleft()
            if self.wav is not None:
                try:
                    self.wav["wv"].writeframes(b)
                except Exception:  # noqa: BLE001
                    self.rec_audio(False)
            self.q.append(b)
            self.af.append(b)
            self.pre.push(b)                             # étape 20 : 10 s d'avant, pour l'alarme
            self.rew.push_audio(time.time() - len(b) / (LISTEN_RATE * 4.0), b)   # étape 22 : ⏪ remonter le temps
            if self.arec is not None:
                try:
                    self.arec["wv"].writeframes(b)
                except Exception:  # noqa: BLE001
                    self._arec_end()
        if self.audio is not None:
            self.audio.feed(self.q)

    def level_at(self, f, half=0.1):
        """Niveau du dernier spectre autour de f (dBm, correction du modèle comprise), ou None hors fenêtre."""
        fr = self.last
        if not fr or self.center is None or not vfo_inside(self.center, self.span(), f, 0.0):
            return None
        F, L = np.asarray(fr["F"]), np.asarray(fr["avg"])
        sel = np.abs(F - f) <= half
        return self.dbm(float(np.max(L[sel]))) if sel.any() else None


    # ---- étape 20 : réglages automatiques
    def auto(self):
        return sdr_auto_norm(self.owner.sdr_cfg.get("auto"))

    def set_auto(self, **kw):
        a = self.auto()
        a.update(kw)
        self.owner.sdr_cfg["auto"] = sdr_auto_norm(a)
        self.changed.emit()

    def _tune(self, f, key=None):
        """Calage décidé par l'appli (patrouille, alarme, retour) : ne compte pas comme « tu as pris la main »."""
        self._internal = True
        try:
            ok = self.set_a(f)
            if key and ok:
                self.set_demod_key(key)
        finally:
            self._internal = False
        return ok

    def _tick(self):
        now = time.time()
        if self.kind() == "demo" and now - getattr(self, "_t_demo", 0.0) >= 2.0:   # étape 21 : micros du SDR démo
            self._t_demo = now
            try:
                sdr_demo_set(plan=demo_sdr_plan(self.owner.demo_mics()))
            except Exception as ex:  # noqa: BLE001
                log_crash("SDR démo", repr(ex))
        for fn in (self._patrol_tick, self._alarm_watch, self._pilot_tick, self._diag_tick):
            try:
                fn(now)
            except Exception as ex:  # noqa: BLE001
                log_crash("SDR (étape 20)", f"{fn.__name__} : {ex!r}")

    # ---- patrouille d'écoute
    def _patrol_items(self):
        o, m = self.owner, self.model()
        paused = getattr(o, "w_paused", lambda w: bool(w.get("muted") or w.get("off")))
        mics = [(int(round(w["freq"] * 1000)), bool(paused(w))) for w in self.ws() if not m or sdr_in_range(m, w["freq"])]
        return patrol_items(o.sdr_cfg.get("favs"), mics, self.auto()["src"])

    def patrol_start(self):
        items = self._patrol_items()
        if not items:
            self._say(TR("🔁 Rien à parcourir : mets des micros en favoris ⭐ (clic droit sur 1…9) ou choisis "
                         "« Tous les micros »."))
            return False
        if not self.running() and not self.start():
            return False
        self._back = None
        self.patrol = dict(cur=None, t_next=0.0, n=len(items))
        self._patrol_tick(time.time())
        self.changed.emit()
        return True

    def patrol_stop(self):
        if self.patrol is not None:
            self.patrol = None
            self._say(TR("🔁 Patrouille arrêtée."))
        self.changed.emit()

    def _patrol_tick(self, now):
        p = self.patrol
        if p is None or self.worker is None or now < p["t_next"]:
            return
        items = self._patrol_items()
        k = patrol_next(items, p["cur"])
        if k is None:
            self.patrol_stop()
            return
        w = self.owner.watch_by_key(k)
        p.update(cur=k, t_next=now + self.auto()["dwell"], n=len(items), i=items.index(k) + 1)
        if w is not None:
            self._tune(w["freq"])
        self.changed.emit()

    def patrol_text(self, now=None):
        p = self.patrol
        if p is None:
            return ""
        w = self.owner.watch_by_key(p["cur"]) if p.get("cur") is not None else None
        nm = (w["name"] or f"{w['freq']:.3f}") if w else "…"
        return TR("🔁 {} / {} · {} · encore {} s").format(p.get("i", 0), p.get("n", 0), nm,
                                                       max(0, int(round(p["t_next"] - (now or time.time())))))

    # ---- alarme : le SDR se cale dessus (et enregistre si tu l'as permis)
    def _alarm_watch(self, now):
        o = self.owner
        if self.arec is not None and now >= self.arec["until"]:
            self._arec_end()
        if self._al_until and now >= self._al_until:      # fin de l'épisode : la patrouille reprend
            self._al_until = 0.0
            if self._back and self._back.get("patrol") and self.patrol is None:
                self._back = None
                self.patrol_start()
        au = self.auto()
        if not au["tune"] or self.worker is None or self.arec is not None or now < self._al_until:
            return                                       # déjà sur une alarme : on y reste (la suivante après)
        m = self.model()
        if now - self._user_t < ALARM_USER_HOLD_S:       # tu viens de choisir une fréquence : on ne te la vole pas
            self._seen_al |= {a_.get("id") for a_ in o.alarms.active.values()}
            return

        def ok(f):
            if m and not sdr_in_range(m, f):
                return False
            w = o.watch_near(f, 0.003) if hasattr(o, "watch_near") else None
            if w is None:
                return self.pid == 1
            eng = o._engine_for(w) if hasattr(o, "_engine_for") else self
            return eng is self
        self._seen_al &= {a_.get("id") for a_ in o.alarms.active.values()}   # audit : ne grossit plus sans fin
        al = [a for a in o.alarms.active.values() if now - self._al_key_t.get(a.get("key"), -1e9) >= ALARM_TUNE_COOLDOWN_S]
        a = alarm_pick(al, self._seen_al, ok)
        for a_ in o.alarms.active.values():               # les autres restent « vues » : une seule à la fois
            if a_ is a or not ok(float(a_.get("freq") or 0.0)):
                self._seen_al.add(a_.get("id"))
        if a is None:
            return
        f = float(a["freq"])
        alone = not any(w_.isRunning() and not getattr(w_, "paused", False) for w_ in getattr(o, "workers", []))
        if alone and self.center is not None and not vfo_inside(self.center, self.span(), f):
            self._al_offer = a                           # audit : en SDR seul, y aller = les autres micros perdent
            self._seen_al.add(a.get("id"))               # leur mesure -> on propose au lieu d'y aller
            self.changed.emit()
            return
        self._alarm_go(a, now)

    def alarm_offer(self):
        """Alarme proposée (hors de la fenêtre, SDR seul à surveiller) encore en cours, ou None."""
        a = getattr(self, "_al_offer", None)
        if a is not None and a.get("key") not in self.owner.alarms.active:
            a = self._al_offer = None
        return a

    def go_alarm(self):
        a = self.alarm_offer()
        self._al_offer = None
        if a is not None:
            self._alarm_go(a, time.time())
        self.changed.emit()

    def _alarm_go(self, a, now):
        au = self.auto()
        self._al_key_t[a.get("key")] = now
        f = float(a["freq"])
        here = self.a is not None and abs(self.a - f) < 0.0015 and now - self._a_t > 1.0
        if self._back is None and not here:
            self._back = dict(a=self.a, key=self.demod_key, patrol=self.patrol is not None)
        self.patrol = None
        if not here:
            self._tune(f)
        self._al_until = now + ALARM_REC_POST_S
        rec = ""
        if au["rec"]:
            rec = self._arec_start(a, with_pre=here)
        nm = a.get("name") or f"{f:.3f}"
        self._say(TR("🚨 {} sur {} : le SDR s'y est calé.").format(a.get("kind", ""), nm) + (" " + rec if rec else ""))
        QtCore.QTimer.singleShot(1500, lambda a_=a: self._alarm_what(a_))
        self.changed.emit()

    def _alarm_what(self, a):
        """1,5 s après le calage : « c'est quoi » noté au journal et dans l'info de l'alarme."""
        if self.worker is None or self.last is None:
            return
        f = float(a["freq"])
        fr = self.last
        c = what_is(fr["F"], fr["avg"], f, fr.get("pilot"))
        txt = signal_report(c, TR)
        o = self.owner
        cur = o.alarms.active.get(a.get("key"))
        if cur is not None and TR("SDR : ") not in (cur.get("info") or ""):
            cur["info"] = ((cur.get("info") or "") + " · " if cur.get("info") else "") + TR("SDR : ") + txt
            try:
                o.refresh_alarms()
            except Exception:  # noqa: BLE001
                pass
        w = o.watch_near(f, 0.003) if hasattr(o, "watch_near") else None
        o.log_event(dict(name=a.get("name", ""), freq=f, note=TR("{} · {} : {}").format(
            self.name(), a.get("kind", ""), txt)), self.level_at(f) or 0.0, "SDR SUR ALARME")
        if w is not None and self.pil_v and self.pil_v[0] in ("missing", "other", "same"):
            o.log_event(dict(w, note=self.pil_v[1]), 0.0, "SDR SUR ALARME")

    def _arec_start(self, a, with_pre):
        import wave
        if not self.owner.privacy().get("ack"):
            return TR("(son non enregistré : accord pas encore donné)")
        d = Path(self.owner.log_dir) / "enregistrements_audio" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"alarme_{datetime.now():%H%M%S}_{float(a['freq']):.3f}MHz.wav"
            wv = wave.open(str(p), "wb")
            wv.setnchannels(2)
            wv.setsampwidth(2)
            wv.setframerate(LISTEN_RATE)
            if with_pre:
                wv.writeframes(self.pre.dump())
        except Exception as ex:  # noqa: BLE001
            return TR("⚠ Enregistrement impossible : {}").format(ex)
        self.arec = dict(wv=wv, path=p, until=time.time() + ALARM_REC_POST_S, a=a, pre=with_pre)
        return TR("⏺ Son enregistré ({} s avant, {} s après).").format(
            f"{ALARM_REC_PRE_S:.0f}" if with_pre else "0", f"{ALARM_REC_POST_S:.0f}")

    def _arec_end(self):
        r, self.arec = self.arec, None
        if r is None:
            return
        try:
            r["wv"].close()
        except Exception:  # noqa: BLE001
            pass
        a = r["a"]
        self.owner.log_event(dict(name=a.get("name", ""), freq=float(a.get("freq") or 0.0),
                                  note=TR("son de l'alarme : {}").format(r["path"])), 0.0, "ENREGISTRÉ (alarme)")
        self._say(TR("⏺ Son de l'alarme enregistré : {}").format(r["path"]))
        self.changed.emit()

    def go_back(self):
        """↩ Revenir où on était avant l'alarme (fréquence, écoute, patrouille)."""
        b, self._back = self._back, None
        self._al_until = 0.0
        if not b:
            return False
        if b.get("patrol"):
            return self.patrol_start()
        if b.get("a") is not None:
            self._tune(b["a"], b.get("key"))
        self.changed.emit()
        return True

    def back_text(self):
        b = self._back
        if not b or b.get("a") is None and not b.get("patrol"):
            return ""
        if b.get("patrol"):
            return TR("↩ Reprendre la patrouille")
        w = self.mic_at(b["a"])
        return TR("↩ Revenir à {}").format(w["name"] if w and w.get("name") else f"{b['a']:.3f}")

    # ---- pilote et « c'est quoi » de A
    def _watch_a(self, fr, now):
        if self.a is None:
            return
        if now - self._t_what >= 1.0 and len(fr["F"]) == len(fr["avg"]):
            self._t_what = now
            self.what = what_is(fr["F"], fr["avg"], self.a, fr.get("pilot"))
        w = self.cur_mic
        if w is not None and not any(x is w for x in self.owner.watch):   # liste relue (show, profil) : même micro
            w = self.cur_mic = self.mic_at(self.a)
        fm = str(self.demod.get("mode", "")).startswith(("wfm", "nfm"))
        if w is None or not fm or self.demod_key == DEMOD_DIGITAL:
            self.pil_v, self._pil_hist, self._pil_miss = None, None, None
            return
        carrier = sdr_carrier(fr["F"], fr["avg"], self.a)  # jugé sur le spectre du SDR lui-même
        pilot = fr.get("pilot") if carrier else None
        if pilot is not None and abs(pilot[0] - 19000.0) < 400:     # pilote stéréo : pas un pilote de micro
            pilot = None
        learned = w.get("pilot")
        if learned is None:
            self._pil_hist, hz = pilot_learn(self._pil_hist, pilot, now)
            rej = w.get("_pil_rej") or []
            if hz and not any(abs(hz - r_) <= PILOT_TOL_HZ for r_ in rej) and getattr(self, "pil_pending", None) is None:
                self.pil_pending = (w, hz)              # audit : on demande avant de retenir (un brouilleur a aussi
                self.changed.emit()                     # parfois un pilote)
        bad = carrier and learned is not None and (pilot is None or abs(pilot[0] - learned) > PILOT_TOL_HZ)
        self._pil_miss = (self._pil_miss or now) if bad else None
        self.pil_v = pilot_verdict(learned, pilot, carrier, now - self._pil_miss if self._pil_miss else 0.0, TR)
        if self.pil_v[0] == "other" and now - (self._pil_miss or now) < PILOT_MISS_S:
            self.pil_v = ("wait", TR("pilote attendu ({} kHz)…").format(f"{learned / 1000.0:.1f}"), "warn")

    def pilot_accept(self):
        """✔ C'est bien mon émetteur : le pilote vu est retenu pour ce micro."""
        p, self.pil_pending = getattr(self, "pil_pending", None), None
        if p is not None:
            w, hz = p
            w["pilot"] = hz
            self._say(TR("🔊 Pilote de {} retenu : {} kHz (il sert à reconnaître TON émetteur).").format(
                w["name"] or f"{w['freq']:.3f}", f"{hz / 1000.0:.1f}"))
        self.changed.emit()

    def pilot_reject(self):
        """✖ Ce n'est pas mon émetteur : ce pilote n'est plus proposé pour ce micro (jusqu'à la fermeture)."""
        p, self.pil_pending = getattr(self, "pil_pending", None), None
        if p is not None:
            p[0].setdefault("_pil_rej", []).append(p[1])
            self._pil_hist = None
        self.changed.emit()

    def forget_pilot(self):
        w = self.cur_mic
        if w is not None:
            w.pop("pilot", None)
            self._pil_hist, self._pil_miss, self.pil_v = None, None, None
            self._pilot_alarm(None)
            self.changed.emit()

    def _pilot_tick(self, now):
        v = self.pil_v
        w = self.cur_mic
        on = self.auto()["pilot_alarm"] and v is not None and v[0] in ("missing", "other") and w is not None
        if on:
            self._pil_ok_t = None
            self._pilot_alarm(w, v[1])
            return
        cur = getattr(self, "_pil_key", None)
        same_mic = cur is not None and w is not None and cur[1] == int(round(w["freq"] * 1000))
        if same_mic and self.auto()["pilot_alarm"] and v is not None and v[0] != "off":
            if v[0] == "same":                         # audit : retombée seulement après 3 s de pilote retrouvé
                self._pil_ok_t = getattr(self, "_pil_ok_t", None) or now
                if now - self._pil_ok_t >= 3.0:
                    self._pilot_alarm(None)
            else:
                self._pil_ok_t = None
            return
        self._pil_ok_t = None
        self._pilot_alarm(None)

    def _pilot_alarm(self, w, info=""):
        """Alarme « PILOTE » (porteuse là, mais pas le pilote de ton émetteur) : levée / effacée."""
        o = self.owner
        key_on = ("PILOTE", int(round(w["freq"] * 1000))) if w is not None else None
        old = getattr(self, "_pil_key", None)
        if old is not None and old != key_on:
            o.alarms.clear(old, time.time())
            self._pil_key = None
            try:
                o.refresh_alarms()
            except Exception:  # noqa: BLE001
                pass
        if key_on is None:
            return
        self._pil_key = key_on
        prio = o.freq_prio(w) if hasattr(o, "freq_prio") else 1
        lv = self.level_at(w["freq"])
        if o.alarms.raise_(key_on, "PILOTE", w["name"], w["freq"], prio, time.time(), lv,
                           o.layer_text(w) if hasattr(o, "layer_text") else "", info):
            o.log_event(dict(w, note=info), lv or 0.0, "PILOTE")
            o._alarm_sound(prio)
            o.refresh_alarms()

    def info_text(self):
        """Ligne d'info du poste : c'est quoi sur A, verdict du pilote. -> (texte, ton)."""
        parts, tone = [], "none"
        if self.running() and self.what is not None:
            parts.append(what_is_text(self.what, TR))
        if self.pil_v is not None:
            parts.append("🔊 " + self.pil_v[1])
            tone = self.pil_v[2]
        return "  ·  ".join(parts), tone

    # ---- enregistrements (accord vie privée)
    def rec_audio(self, on):
        import wave
        if not on:
            r, self.wav = self.wav, None
            if r is not None:
                try:
                    r["wv"].close()
                except Exception:  # noqa: BLE001
                    pass
                self._say(TR("⏺ Son enregistré : {}").format(r["path"]))
            self.changed.emit()
            return True
        if self.worker is None or not self.owner.privacy_ok(self.owner):
            return False
        d = Path(self.owner.log_dir) / "enregistrements_audio" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"sdr_{datetime.now():%H%M%S}_{self.a:.3f}MHz.wav"
            wv = wave.open(str(p), "wb")
            wv.setnchannels(2)
            wv.setsampwidth(2)
            wv.setframerate(LISTEN_RATE)
        except Exception as e:  # noqa: BLE001
            self._say(TR("⚠ Enregistrement impossible : {}").format(e))
            return False
        self.wav = dict(wv=wv, path=p, t0=time.time())
        self.changed.emit()
        return True

    def rec_iq(self, on):
        w = self.worker
        if w is None:
            return False
        if not on:
            w.stop_rec()
            self.changed.emit()
            return True
        if not self.owner.privacy_ok(self.owner):
            return False
        d = Path(self.owner.log_dir) / "enregistrements_iq" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        w.start_rec(str(d / f"iq_{datetime.now():%H%M%S}_{self.center / 1e6:.3f}MHz"))
        self.changed.emit()
        return True


def sdr_light_axes(plot, dens=(1.6, 2.6)):
    """Graphes SDR : grands carreaux seulement (comme le spectre principal depuis 7.54.2). Les sous-graduations de la grille
    coûtaient la moitié du temps de l'interface avec 2 SDR (QPicture.play, mesuré hors écran)."""
    for ax, d in (("bottom", dens[0]), ("left", dens[1])):
        try:
            a_ = plot.getPlotItem().getAxis(ax)
            a_.setStyle(maxTickLevel=0, maxTextLevel=0)
            a_.setTickDensity(d)
        except Exception:  # noqa: BLE001
            pass


class SdrPanelBase(QtWidgets.QWidget):
    """Base des panneaux SDR : le moteur commun, le niveau d'affichage (Simple / Plus / Expert)."""

    def __init__(self, owner, eng=None):
        super().__init__(owner)
        self.owner, self.eng = owner, eng or owner.sdr_eng

    def lvl(self):
        return sdr_level(getattr(self.owner, "ui_level", "simple"))

    def apply_level(self):
        pass

    @staticmethod
    def _wrap(*ws):
        """Rangée qui se replie (8.0.1) : un texte reste collé au contrôle qui le suit ; None (ressort) ignoré.
        Avant : rangées fixes -> le Récepteur imposait 925 px de large et agrandissait la fenêtre."""
        fl, i, ws = FlowLayout(), 0, [w for w in ws if w is not None]
        while i < len(ws):
            w = ws[i]
            if isinstance(w, str):
                box = QtWidgets.QWidget()
                h = QtWidgets.QHBoxLayout(box)
                h.setContentsMargins(0, 0, 0, 0)
                h.addWidget(QtWidgets.QLabel(w))
                if i + 1 < len(ws) and not isinstance(ws[i + 1], str):
                    h.addWidget(ws[i + 1])
                    i += 1
                fl.addWidget(box)
            else:
                fl.addWidget(w)
            i += 1
        return fl


def idle_sdr_view(plot, e, yr):
    """8.0.1 : SDR pas encore démarré -> on montre déjà la fenêtre qu'il recevra (avant : axes 0-1 et 0-600 MHz)."""
    try:
        a = e.a if e.a is not None else 600.0
        sp = max(0.2, float(e.span() or 2.0))
        c = vfo_center(a, sp) / 1e6
        plot.setXRange(c - sp / 2.0, c + sp / 2.0, padding=0.0)
        plot.setYRange(*yr, padding=0.0)
    except Exception:  # noqa: BLE001
        pass


class SdrScroll(QtWidgets.QScrollArea):
    """Panneau SDR qui défile quand on le rétrécit (8.0.1). Le reste du programme parle au panneau à travers lui :
    les attributs inconnus (apply_level, refresh, go_btn…) sont ceux du panneau."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidget(panel)

    def __getattr__(self, name):
        p = self.__dict__.get("panel")
        if p is None:
            up = getattr(super(), "__getattr__", None)
            if up is not None:
                return up(name)
            raise AttributeError(name)
        return getattr(p, name)

    def sizeHint(self):
        h = self.panel.sizeHint()
        return QtCore.QSize(h.width() + 18, h.height() + 4)

    def minimumSizeHint(self):
        return QtCore.QSize(220, 140)


class SdrReceiverPanel(SdrPanelBase):
    """📡 SDR · Récepteur (façon poste SDR) : ▶ / ■, son, grande fréquence A réglable chiffre par chiffre, S-mètre à
    aiguille ; Plus : démodulation, pas, squelch, récepteur B, zoom du canal écouté (IF) et spectre du son (AF),
    enregistrements ; Expert : FFT, réglages de l'appareil, charge / saturation."""

    def __init__(self, owner, eng=None):
        super().__init__(owner, eng)
        e, o = self.eng, owner
        acc = o.theme.get("accent", "#64d2ff")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(4)
        self.go_btn = QtWidgets.QPushButton("▶ Démarrer le SDR")
        self.go_btn.setToolTip("Lance / arrête le SDR : spectre sans trou, écoute de A (et B), surveillance de la fenêtre.")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        self.mute = QtWidgets.QToolButton()
        self.mute.setCheckable(True)
        self.mute.setText("🔊")
        self.mute.setToolTip("Couper / remettre le son.")
        self.mute.toggled.connect(lambda on: (self.mute.setText("🔇" if on else "🔊"),
                                              e.set_opts(vol=0.0 if on else self.vol.value() / 100.0)))
        self.vol = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 200)
        self.vol.setValue(int((e.vol or 0.8) * 100))
        self.vol.setMaximumWidth(140)
        self.vol.setTickPosition(QtWidgets.QSlider.TickPosition.TicksBelow)   # 8.1 : graduations (0, 50, 100, 150, 200 %)
        self.vol.setTickInterval(50)
        self.vol.setPageStep(10)
        self.vol.setToolTip("Volume.")
        self.vol.valueChanged.connect(lambda v: None if self.mute.isChecked() else e.set_opts(vol=v / 100.0))
        self.vol_lbl = QtWidgets.QLabel("")              # 8.1 : la valeur du volume (le vu-mètre, lui, ne la compte pas)
        self.vol_lbl.setMinimumWidth(78)
        self.vol_lbl.setToolTip(TR("Volume de l'écoute sur ton PC (100 % = 0 dB). N'influence PAS le vu-mètre du son : "
                                   "il mesure le niveau reçu, avant le volume."))
        self.vol.valueChanged.connect(self._vol_txt)
        self._vol_txt(self.vol.value())
        self.vol.installEventFilter(self)                 # 8.1 : double-clic = 100 % (0 dB)
        self.vol_lbl.installEventFilter(self)
        self.vol.setToolTip(TR("Volume. Double-clic = 100 % (0 dB)."))
        self.dev_lbl = QtWidgets.QLabel("")
        self.dev_lbl.setToolTip(TR(DEVICE_HELP["sdr"]) + "\n\n" + TR("Ton SDR : 📡 Réglages SDR pour le changer."))
        lay.addLayout(self._wrap(self.go_btn, self.mute, self.vol, self.vol_lbl, o._elastic(self.dev_lbl)))
        self.a_disp = FreqDisplay(self, 24, acc)
        self.a_disp.changed.connect(lambda v: e.set_a(v))
        self.a_meter = SMeterGauge(self, owner=o)
        top = QtWidgets.QHBoxLayout()
        lab_a = QtWidgets.QLabel("A")
        lab_a.setStyleSheet(f"color: {acc}; font-weight: bold; font-size: 18px;")
        top.addWidget(lab_a)
        top.addWidget(self.a_disp, 1)
        top.addWidget(self.a_meter)
        lay.addLayout(top)
        self.af_meter = AudioMeterBar(o, self)           # 8.1 : niveau du son démodulé (+ déviation mesurée)
        self.dev_txt = QtWidgets.QLabel("")
        self.dev_txt.setToolTip(TR("Déviation FM mesurée sur A (crête), comparée à la déviation max du réglage d'écoute :\n"
                                   "0 dB = pile la nominale ; au-dessus = pack trop chaud (gain à baisser)."))
        self.row_af = QtWidgets.QWidget()
        ra_ = QtWidgets.QHBoxLayout(self.row_af)
        ra_.setContentsMargins(0, 0, 0, 0)
        lab_s = QtWidgets.QLabel("🔊")
        lab_s.setToolTip(TR("Niveau du son que tu entends (A démodulé)."))
        ra_.addWidget(lab_s)
        ra_.addWidget(self.af_meter, 1)
        self.af_post = QtWidgets.QToolButton()            # 8.1 : vu-mètre AVANT (pré) ou APRÈS (post) le volume
        self.af_post.setCheckable(True)
        self.af_post.setChecked(bool(o.sdr_cfg.get("af_post")))
        self.af_post.setToolTip(TR("PRÉ : le vu-mètre mesure le son reçu, avant ton volume (pour caler un récepteur).\n"
                                   "POST : il mesure ce que tu entends, après le volume et le mélange A + B."))
        self.af_post.toggled.connect(self._af_post_set)
        self._af_post_set(self.af_post.isChecked())
        ra_.addWidget(self.af_post)
        ra_.addWidget(o._elastic(self.dev_txt), 1)
        lay.addWidget(self.row_af)
        self.favs = []                                   # étape 18 : favoris du pavé numérique (1…9)
        fr_ = QtWidgets.QHBoxLayout()
        fr_.setSpacing(3)
        lab_f = QtWidgets.QLabel("⭐")
        lab_f.setToolTip("Tes micros les plus importants sur les touches 1 à 9 du PAVÉ NUMÉRIQUE : un appui = le SDR se cale\n"
                         "dessus et tu l'entends. Clic droit sur un bouton = y mettre le micro écouté (A).")
        fr_.addWidget(lab_f)
        for k in range(1, FAV_KEYS + 1):
            b = QtWidgets.QToolButton()
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.setMinimumWidth(36)
            b.clicked.connect(lambda *_, k=k: o.sdr_fav(k))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p, k=k: self._fav_menu(k))
            fr_.addWidget(b)
            self.favs.append(b)
        fr_.addStretch(1)
        lay.addLayout(fr_)
        # ---- étape 20 : patrouille, alarme -> calage, retour, « c'est quoi » et pilote
        au = e.auto()
        self.pat_btn = QtWidgets.QPushButton("🔁 Patrouille")
        self.pat_btn.setCheckable(True)
        self.pat_btn.setToolTip("Le SDR passe tout seul d'un micro à l'autre (tes favoris ⭐, sinon tous), avec la bonne\n"
                                "écoute pour chacun. Une touche du pavé numérique ou un clic sur une fréquence l'arrête.")
        self.pat_btn.toggled.connect(lambda on: self._patrol(on))
        self.dwell = QtWidgets.QComboBox()
        for d_ in PATROL_DWELLS:
            self.dwell.addItem(TR("{} s par micro").format(d_), d_)
        self.dwell.setCurrentIndex(max(0, self.dwell.findData(au["dwell"])))
        self.dwell.setToolTip("Temps passé sur chaque micro pendant la patrouille.")
        self.dwell.currentIndexChanged.connect(lambda *_: e.set_auto(dwell=int(self.dwell.currentData() or 8)))
        self.psrc = QtWidgets.QComboBox()
        for k_, t_ in PATROL_SRCS:
            self.psrc.addItem(t_, k_)
        self.psrc.setCurrentIndex(max(0, self.psrc.findData(au["src"])))
        self.psrc.setToolTip("Quels micros la patrouille parcourt (les éteints 💤 et ceux en pause sont sautés).")
        self.psrc.currentIndexChanged.connect(lambda *_: e.set_auto(src=self.psrc.currentData() or "favs"))
        self.al_chk = QtWidgets.QCheckBox("🚨 Se caler sur les alarmes")
        self.al_chk.setChecked(au["tune"])
        self.al_chk.setToolTip("Une nouvelle alarme (conflit, intermod, absent, trop fort, pilote) sur un micro de ce SDR :\n"
                               "le SDR s'y cale tout seul, tu entends ce qui se passe, et le journal dit ce que c'est.")
        self.al_chk.toggled.connect(lambda on: e.set_auto(tune=bool(on)))
        self.alrec_chk = QtWidgets.QCheckBox("⏺ et enregistrer le son")
        self.alrec_chk.setChecked(au["rec"])
        self.alrec_chk.setToolTip("Enregistre le son de l'alarme : 10 s avant (si le SDR écoutait déjà ce micro) et 20 s\n"
                                  "après, en WAV. Demande ton accord la 1re fois (voix).")
        self.alrec_chk.toggled.connect(lambda on: self._alrec(on))
        self.back_btn = QtWidgets.QPushButton("↩ Revenir")
        self.back_btn.setToolTip("Revenir où tu étais avant l'alarme (fréquence, écoute, patrouille).")
        self.back_btn.clicked.connect(lambda *_: e.go_back())
        self.pat_lbl = QtWidgets.QLabel("")
        self.row_auto = QtWidgets.QWidget()
        self.rew_btn = QtWidgets.QPushButton("⏪ Remonter le temps")
        self.rew_btn.setToolTip("Les dernières minutes de ce poste : waterfall, réécouter un passage, le garder.")
        self.rew_btn.clicked.connect(lambda *_: o.open_rewind(e))
        ra = self._wrap(self.pat_btn, self.dwell, self.psrc, self.al_chk, self.alrec_chk, self.back_btn, self.pat_lbl, None,
                    self.rew_btn)
        ra.setContentsMargins(0, 0, 0, 0)
        self.row_auto.setLayout(ra)
        lay.addWidget(self.row_auto)
        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setToolTip("C'est quoi sur A (d'après la forme du spectre : une supposition, pas une certitude) et ce que\n"
                             "dit le PILOTE : la tonalité inaudible de ton émetteur, retenue la 1re fois qu'on l'entend.\n"
                             "Porteuse sans son pilote = ce n'est peut-être pas ton émetteur. Clic droit = oublier le pilote.")
        self.info.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.info.customContextMenuRequested.connect(lambda _p: self._info_menu())
        lay.addWidget(self.info)
        self.pil_ask = QtWidgets.QLabel("")
        self.pil_ask.setWordWrap(True)
        self.pil_yes = QtWidgets.QPushButton("✔ Oui, le retenir")
        self.pil_yes.setToolTip("Ce pilote sert ensuite à reconnaître ton émetteur (alarme PILOTE s'il manque).")
        self.pil_yes.clicked.connect(lambda *_: e.pilot_accept())
        self.pil_no = QtWidgets.QPushButton("✖ Non")
        self.pil_no.setToolTip("Ce n'est pas ton émetteur (brouilleur ?) : ce pilote n'est pas retenu.")
        self.pil_no.clicked.connect(lambda *_: e.pilot_reject())
        self.go_al_btn = QtWidgets.QPushButton("🚨 Aller à l'alarme")
        self.go_al_btn.setToolTip("L'alarme est hors de la fenêtre du SDR : y aller (les autres micros ne sont plus mesurés\n"
                                  "par le SDR pendant ce temps ; « ↩ Revenir » pour revenir).")
        self.go_al_btn.clicked.connect(lambda *_: e.go_alarm())
        self.row_pil = QtWidgets.QWidget()
        rp = self._wrap(self.pil_ask, self.pil_yes, self.pil_no, self.go_al_btn, None)
        rp.setContentsMargins(0, 0, 0, 0)
        self.row_pil.setLayout(rp)
        lay.addWidget(self.row_pil)
        # ---- Plus : démodulation, pas, squelch
        self._sync = False
        self.dp = DemodPick(lambda: hasattr(self, "dp") and not self._sync and self._dp_changed())
        self.step = QtWidgets.QComboBox()
        for s_ in SDR_STEPS_KHZ:
            self.step.addItem(f"{s_:g} kHz", s_)
        self.step.setCurrentIndex(max(0, self.step.findData(e.step)))
        self.step.setToolTip("Pas : clic sur le spectre et micro suivant arrondis à ce pas.")
        self.step.currentIndexChanged.connect(lambda *_: e.set_opts(step=float(self.step.currentData() or 25.0)))
        self.sq = QtWidgets.QSpinBox()
        self.sq.setRange(-121, 0)
        self.sq.setSpecialValueText("aucun")
        self.sq.setSuffix(" dBFS")
        self.sq.setValue(-121 if e.sq is None else int(e.sq))
        self.sq.setToolTip("Squelch : en dessous de ce niveau, le son est coupé (pas de souffle entre deux phrases).")
        self.sq.valueChanged.connect(lambda v: e.set_opts(sq=None if v <= -121 else float(v)))
        self.dp.pre.setToolTip("Le type d'appareil que tu écoutes : règle tout seul la démodulation, le compander et la "
                               "désaccentuation\n(Sennheiser evolution, Shure, Wisycom, ears, talkies…).")
        self.row_listen = QtWidgets.QWidget()                # étape 16 ter : l'écoute, à tous les niveaux
        self.dem_lbl = QtWidgets.QLabel("")
        self.dem_lbl.setToolTip("« auto » : réglage déduit du micro (son appareil dans le plan importé, son groupe, son nom).\n"
                                "Change-le ici : il est retenu pour CE micro (liste et shows).")
        rl = self._wrap("🎧 Écoute :", self.dp.pre, "Compander :", self.dp.comp, self.dem_lbl, None)
        rl.setContentsMargins(0, 0, 0, 0)
        self.row_listen.setLayout(rl)
        lay.addWidget(self.row_listen)
        self.row_dem = QtWidgets.QWidget()
        rd = self._wrap("Mode :", self.dp.mode, self.dp.de, "Pas :", self.step, "Squelch :", self.sq, None)
        rd.setContentsMargins(0, 0, 0, 0)
        self.row_dem.setLayout(rd)
        lay.addWidget(self.row_dem)
        # ---- Plus : récepteur B
        self.b_chk = QtWidgets.QCheckBox("B")
        self.b_chk.setToolTip("Deuxième récepteur, écouté en même temps que A (dans la même fenêtre du SDR).")
        self.b_chk.setChecked(e.b_on)
        self.b_chk.toggled.connect(lambda on: e.set_b(on=on))
        self.b_disp = FreqDisplay(self, 13, "#ff9f0a")
        self.b_disp.setToolTip("Fréquence du récepteur B (clic droit sur le spectre ou un micro pour y aller).")
        self.b_disp.changed.connect(lambda v: e.set_b(f=v))
        self.b_meter = SMeterGauge(self, small=True, owner=o)
        self.split_chk = QtWidgets.QCheckBox("A gauche / B droite")
        self.split_chk.setToolTip("Au casque : A dans l'oreille gauche, B dans la droite (sinon mélangés).")
        self.split_chk.setChecked(e.split)
        self.split_chk.toggled.connect(lambda on: e.set_opts(split=bool(on)))
        self.row_b = QtWidgets.QWidget()
        rb = QtWidgets.QHBoxLayout(self.row_b)
        rb.setContentsMargins(0, 0, 0, 0)
        for w_ in (self.b_chk, self.b_disp, self.b_meter, self.split_chk):
            rb.addWidget(w_)
        rb.addStretch(1)
        lay.addWidget(self.row_b)
        # ---- Plus : zoom du canal (IF) et spectre du son (AF)
        self.if_plot = pg.PlotWidget()
        self.if_plot.setMinimumHeight(90)
        self.if_plot.setMaximumHeight(140)
        self.if_plot.setToolTip("Zoom du canal écouté (A) : la porteuse, sa largeur, les voisins proches.")
        self.if_plot.setLabel("bottom", "kHz autour de A")
        self.if_plot.hideAxis("left")
        sdr_light_axes(self.if_plot)
        self.if_curve = self.if_plot.plot(pen=pg.mkPen(acc, width=1.3), fillLevel=0.0,
                                          brush=pg.mkBrush(QtGui.QColor(acc).red(), QtGui.QColor(acc).green(),
                                                           QtGui.QColor(acc).blue(), 60))
        self.if_band = pg.LinearRegionItem(movable=False, brush=pg.mkBrush(255, 255, 255, 25))
        self.if_plot.addItem(self.if_band)
        self.af_plot = pg.PlotWidget()
        self.af_plot.setMinimumHeight(90)
        self.af_plot.setMaximumHeight(140)
        self.af_plot.setToolTip("Spectre du son entendu (0 – 15 kHz) : voix, souffle, sifflement, ronflette.")
        self.af_plot.setLabel("bottom", "kHz (son)")
        self.af_plot.hideAxis("left")
        sdr_light_axes(self.af_plot)
        self.af_plot.setYRange(-100, 0)
        self.af_curve = self.af_plot.plot(pen=pg.mkPen("#30d158", width=1.2))
        # 8.1 : chaque petite fenêtre peut montrer autre chose que le spectre (phase, constellation, oscilloscope…)
        self.if_scat = pg.ScatterPlotItem(size=2, pen=None, brush=pg.mkBrush(QtGui.QColor(acc).red(),
                                                                             QtGui.QColor(acc).green(),
                                                                             QtGui.QColor(acc).blue(), 140))
        self.if_plot.addItem(self.if_scat)
        self.af_scat = pg.ScatterPlotItem(size=2, pen=None, brush=pg.mkBrush(48, 209, 88, 140))
        self.af_plot.addItem(self.af_scat)
        self.af_curve2 = self.af_plot.plot(pen=pg.mkPen("#ff9f0a", width=1.0))
        self.if_curve2 = self.if_plot.plot(pen=pg.mkPen("#bf5af2", width=1.0))        # 8.2 : Q (vue « I et Q »)
        rvw = (o.sdr_cfg.get("rx_views") or {})
        self.if_view = QtWidgets.QComboBox()
        for k_, t_ in RX_IF_VIEWS:
            self.if_view.addItem(TR(t_), k_)
        self.if_view.setToolTip(TR("Ce que montre la fenêtre du canal écouté (A) :\n"
                                   "spectre = la porteuse et ses voisins ; constellation = le signal I/Q (un FM fait un "
                                   "cercle) ;\nphase = comment la phase bouge dans le temps ; fréquence instantanée = "
                                   "ce que le démodulateur FM entend (la modulation)."))
        self.af_view = QtWidgets.QComboBox()
        for k_, t_ in RX_AF_VIEWS:
            self.af_view.addItem(TR(t_), k_)
        self.af_view.setToolTip(TR("Ce que montre la fenêtre du son :\n"
                                   "spectre = les fréquences du son ; oscilloscope = la forme d'onde (G en vert, D en "
                                   "orange) ;\ngoniomètre = la phase entre gauche et droite (trait vertical = mono, "
                                   "horizontal = hors phase)."))
        self.if_view.setCurrentIndex(max(0, self.if_view.findData(rvw.get("iff", "spec"))))
        self.af_view.setCurrentIndex(max(0, self.af_view.findData(rvw.get("af", "spec"))))
        self.if_view.currentIndexChanged.connect(lambda *_: self._views())
        self.af_view.currentIndexChanged.connect(lambda *_: self._views())
        self.row_zoom = QtWidgets.QWidget()
        rz = QtWidgets.QHBoxLayout(self.row_zoom)
        rz.setContentsMargins(0, 0, 0, 0)
        for cb_, pl_ in ((self.if_view, self.if_plot), (self.af_view, self.af_plot)):
            col_ = QtWidgets.QVBoxLayout()
            col_.setSpacing(2)
            col_.addWidget(cb_)
            col_.addWidget(pl_)
            rz.addLayout(col_, 1)
        lay.addWidget(self.row_zoom)
        self._views()
        # ---- outils
        self.rec_btn = QtWidgets.QPushButton("⏺ Son")
        self.rec_btn.setCheckable(True)
        self.rec_btn.setToolTip("Enregistre ce que tu entends (WAV). Demande ton accord la 1re fois (voix).")
        self.rec_btn.toggled.connect(lambda on: self._rec(on, "audio"))
        self.iq_btn = QtWidgets.QPushButton("⏺ IQ")
        self.iq_btn.setCheckable(True)
        self.iq_btn.setToolTip("Enregistre le signal brut de toute la fenêtre (gros fichiers), à relire dans le Temps réel.")
        self.iq_btn.toggled.connect(lambda on: self._rec(on, "iq"))
        self.nfft = QtWidgets.QComboBox()
        for n_ in SDR_NFFT:
            self.nfft.addItem(f"FFT {n_}", n_)
        self.nfft.setCurrentIndex(max(0, self.nfft.findData(e.nfft)))
        self.nfft.setToolTip("Finesse du spectre (plus grand = plus fin, plus de calcul).")
        self.nfft.currentIndexChanged.connect(lambda *_: e.set_opts(nfft=self.nfft.currentData()))
        self.set_btn = QtWidgets.QPushButton("⚙ Réglages SDR")
        self.set_btn.setToolTip("Choisir le SDR, sa sensibilité, le tester.")
        self.set_btn.clicked.connect(lambda *_: o.open_sdr())
        self.stats = QtWidgets.QLabel("")
        self.stats.setToolTip("Charge du calcul et saturation de l'entrée du SDR.")
        self.row_tools = QtWidgets.QWidget()
        rt = o._row(self.rec_btn, self.iq_btn, None, self.nfft, self.set_btn, self.stats)
        rt.setContentsMargins(0, 0, 0, 0)
        self.row_tools.setLayout(rt)
        lay.addWidget(self.row_tools)
        self.flux = QtWidgets.QLabel("")              # 8.2 : qualité du flux IQ (pertes, coupures, saturation)
        self.flux.setWordWrap(True)
        self.flux.setToolTip("Qualité du flux du SDR : échantillons perdus (USB ou PC qui ne suit pas), coupures,\n"
                             "saturation de l'entrée, reconnexions. Orange / rouge = ce que tu entends et vois n'est\n"
                             "pas complet.")
        lay.addWidget(self.flux)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch(1)
        e.changed.connect(self.refresh)
        e.frame.connect(self._frame)
        e.status.connect(self.msg.setText)
        self._t_af = 0.0
        self.refresh()
        self.apply_level()

    def toggle(self):
        if self.eng.running():
            self.eng.stop()
        else:
            self.eng.start()

    def _patrol(self, on):
        e = self.eng
        if on and e.patrol is None:
            if not e.patrol_start():
                self._set_chk(self.pat_btn, False)
        elif not on and e.patrol is not None:
            e.patrol_stop()

    def _alrec(self, on):
        if on and not self.owner.privacy_ok(self.owner):
            self._set_chk(self.alrec_chk, False)
            return
        self.eng.set_auto(rec=bool(on))

    @staticmethod
    def _set_chk(b, on):
        if b.isChecked() != bool(on):
            b.blockSignals(True)
            b.setChecked(bool(on))
            b.blockSignals(False)

    def _info_menu(self):
        e = self.eng
        m = QtWidgets.QMenu(self)
        w = e.cur_mic
        a1 = m.addAction(TR("Oublier le pilote de {}").format(w["name"] or f"{w['freq']:.3f}") if w and w.get("pilot")
                         else TR("Oublier le pilote (aucun retenu pour ce micro)"))
        a1.setEnabled(bool(w and w.get("pilot")))
        a1.triggered.connect(lambda *_: e.forget_pilot())
        a2 = m.addAction(TR("Alarme si la porteuse n'a pas son pilote"))
        a2.setCheckable(True)
        a2.setChecked(e.auto()["pilot_alarm"])
        a2.triggered.connect(lambda *_, a=a2: e.set_auto(pilot_alarm=a.isChecked()))
        m.exec(QtGui.QCursor.pos())

    def _views(self):
        """8.1 : met en place les axes et les tracés de la vue choisie dans chaque petite fenêtre, et la retient."""
        iv, av = self.if_view.currentData(), self.af_view.currentData()
        self.owner.sdr_cfg["rx_views"] = dict(iff=iv, af=av)
        pi, pa = self.if_plot.getPlotItem(), self.af_plot.getPlotItem()
        self.if_curve.setData([], [])
        self.if_curve2.setData([], [])
        self.if_curve2.setVisible(iv == "iq")
        self.if_scat.setData([], [])
        self.if_band.setVisible(iv == "spec")
        self.if_scat.setVisible(iv in ("const", "phase"))
        self.if_curve.setVisible(iv not in ("const", "phase"))
        self.if_curve.setFillLevel(None if iv != "spec" else 0.0)
        pi.setAspectLocked(iv == "const")
        pi.enableAutoRange(axis="y", enable=True)
        pi.enableAutoRange(axis="x", enable=True)
        if iv == "const":
            pi.setXRange(-2, 2, padding=0)
            pi.setYRange(-2, 2, padding=0)
            pi.disableAutoRange()
        elif iv == "phase":
            pi.setYRange(-180, 180, padding=0.02)
            pi.enableAutoRange(axis="y", enable=False)
        elif iv == "iq":
            pi.setYRange(-2, 2, padding=0)
            pi.enableAutoRange(axis="y", enable=False)
        self.if_plot.setLabel("bottom", TR({"spec": "kHz autour de A", "const": "I / Q (normalisés)",
                                            "iq": "ms (bleu = I, violet = Q)",
                                            "phase": "ms · phase (degrés)", "finst": "ms · kHz (écart de fréquence)"}[iv]))
        self.af_curve.setData([], [])
        self.af_curve2.setData([], [])
        self.af_scat.setData([], [])
        self.af_scat.setVisible(av == "gonio")
        self.af_curve.setVisible(av != "gonio")
        self.af_curve2.setVisible(av == "scope")
        pa.setAspectLocked(av == "gonio")
        if av == "spec":
            pa.enableAutoRange(axis="x", enable=True)
            pa.setYRange(-100, 0)
            self.af_plot.setLabel("bottom", TR("kHz (son)"))
        elif av == "scope":
            pa.enableAutoRange(axis="x", enable=True)
            pa.setYRange(-1, 1)
            self.af_plot.setLabel("bottom", TR("ms (vert = G, orange = D)"))
        else:
            pa.setXRange(-1, 1, padding=0)
            pa.setYRange(-1, 1, padding=0)
            pa.disableAutoRange()
            self.af_plot.setLabel("bottom", TR("goniomètre G/D"))

    def _af_post_set(self, on):
        self.af_post.setText("POST" if on else "PRÉ")
        self.owner.sdr_cfg["af_post"] = bool(on)

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Type.MouseButtonDblClick and obj in (getattr(self, "vol", None),
                                                                          getattr(self, "vol_lbl", None)):
            self.vol.setValue(100)
            return True
        return super().eventFilter(obj, ev)

    def _vol_txt(self, v):
        v = int(v)
        db = "−∞" if v <= 0 else f"{20 * math.log10(v / 100.0):+.1f}".replace(".", ",").replace("-", "−")
        self.vol_lbl.setText(f"{v} % · {db} dB")

    def _af_meter(self, fr):
        """8.1 : vu-mètre du son de A (derniers ~0,3 s) et déviation mesurée par rapport à la nominale (5 fois / s)."""
        now = time.monotonic()
        if now - getattr(self, "_t_afm", 0.0) < 0.2:
            return
        self._t_afm = now
        e, o = self.eng, self.owner
        try:
            raw = getattr(e.worker, "a_raw", None) if e.worker is not None else None
            if raw is not None and not self.af_post.isChecked():            # 8.1 : le son de A AVANT ton volume et le mélange avec B (sinon le curseur
                bs = list(raw)[-6:]        # de volume à 200 % ajoutait 6 dB à la mesure)
                x = np.concatenate(bs) if bs else np.zeros(0, dtype=np.float32)
            else:
                bs = list(e.af)[-3:]
                x = np.frombuffer(b"".join(bs), dtype="<i2").astype(np.float32) / 32768.0 if bs else np.zeros(0)
                x = x[0::2] if len(x) else x
            self.af_meter.set_meter(audio_meter(x), o.audio_ref["target"])
        except Exception:  # noqa: BLE001
            pass
        h = fr.get("health") or {}
        nom = float(e.demod.get("dev") or (LISTEN_MODES.get(e.demod.get("mode", ""), {}).get("dev")) or 0) / 1000.0
        if h.get("dev") and nom > 0 and e.demod.get("mode", "") in ("wfm", "wfm_st", "nfm"):
            ddb = deviation_db(h["dev"], nom)
            self.dev_txt.setText(TR("déviation {} kHz · {} dB / nominale {} kHz").format(
                f"{h['dev']:.1f}".replace(".", ","), f"{ddb:+.1f}".replace(".", ","), f"{nom:g}"))
        else:
            self.dev_txt.setText("")

    def _auto_refresh(self):
        e = self.eng
        self._set_chk(self.pat_btn, e.patrol is not None)
        self.pat_lbl.setText(e.patrol_text())
        bt = e.back_text()
        self.back_btn.setVisible(bool(bt))
        if bt and getattr(self, "_bt", None) != bt:
            self._bt = bt
            self.back_btn.setText(bt)
        au = e.auto()
        self._set_chk(self.al_chk, au["tune"])
        self._set_chk(self.alrec_chk, au["rec"])
        pp = getattr(e, "pil_pending", None)
        ofr = e.alarm_offer()
        ask = (TR("🔊 Pilote {} kHz entendu sur {} : c'est bien ton émetteur ?").format(
            f"{pp[1] / 1000.0:.1f}", pp[0]["name"] or f"{pp[0]['freq']:.3f}") if pp else
            TR("🚨 {} sur {} : hors de la fenêtre du SDR.").format(ofr.get("kind", ""), ofr.get("name", "")) if ofr else "")
        if self.pil_ask.text() != ask:
            self.pil_ask.setText(ask)
        for w_, on_ in ((self.pil_yes, bool(pp)), (self.pil_no, bool(pp)), (self.go_al_btn, bool(ofr) and not pp)):
            w_.setVisible(on_)
        self.row_pil.setVisible(bool(pp or ofr))
        t, tone = e.info_text()
        if self.info.text() != t:
            self.info.setText(t)
        st = f"color: {self.owner.tone_color(tone)};" if tone in ("ok", "warn", "bad") else ""
        if self.info.styleSheet() != st:
            self.info.setStyleSheet(st)

    def _dp_changed(self):
        """Réglage d'écoute changé à la main : appliqué, et retenu pour le micro écouté (s'il y en a un)."""
        e = self.eng
        e.demod_key = self.dp.pre.currentData() or None
        e.set_opts(demod=self.dp.params())
        if e.cur_mic is not None and e.demod_key:
            self.owner.mic_demod_set(e.cur_mic, e.demod_key)
            e.demod_how = self.owner.mic_demod(e.cur_mic)[1]
        self._dem_txt()

    def _dem_txt(self):
        e = self.eng
        how = e.demod_how if e.cur_mic is not None else None
        t = {"auto": TR("auto (d'après le micro)"), "manual": TR("✋ choisi pour ce micro")}.get(how, "")
        if self.dem_lbl.text() != t:
            self.dem_lbl.setText(t)

    def _fav_menu(self, k):
        o, e = self.owner, self.eng
        m = QtWidgets.QMenu(self)
        w = min((w for w in e.ws() if e.a is not None and abs(w["freq"] - e.a) < 0.0005), default=None,
                key=lambda w: abs(w["freq"] - e.a))
        a1 = m.addAction(TR("⭐ Mettre ici : {}").format(w["name"] or f"{w['freq']:.3f}") if w else
                         TR("⭐ Mettre ici le micro écouté (règle A sur un micro d'abord)"))
        a1.setEnabled(w is not None)
        a1.triggered.connect(lambda *_: o.sdr_set_fav(k, w))
        m.addAction(TR("Vider la touche {}").format(k)).triggered.connect(lambda *_: o.sdr_set_fav(k, None))
        m.exec(QtGui.QCursor.pos())

    def _favs_refresh(self):
        o, e = self.owner, self.eng
        favs = favs_norm(o.sdr_cfg.get("favs"))
        for k, b in zip(range(1, FAV_KEYS + 1), self.favs):
            w = o.watch_by_key(favs[k]) if k in favs else None
            nm = (w["name"] or f"{w['freq']:.3f}") if w else ""
            t = f"{k} {nm[:10]}" if nm else f"{k}"
            if b.text() != t:
                b.setText(t)
            b.setToolTip(TR("Touche {} du pavé numérique : {}").format(k, f"{nm} ({w['freq']:.3f} MHz)") if w else
                         TR("Touche {} du pavé numérique : libre (clic droit = y mettre le micro écouté)").format(k))
            on = bool(w and e.a is not None and abs(w["freq"] - e.a) < 0.0005)
            if b.isChecked() != on:
                b.setChecked(on)

    def _rec(self, on, what):
        ok = self.eng.rec_audio(on) if what == "audio" else self.eng.rec_iq(on)
        if on and not ok:
            b = self.rec_btn if what == "audio" else self.iq_btn
            b.blockSignals(True)
            b.setChecked(False)
            b.blockSignals(False)

    def refresh(self):
        e = self.eng
        m = e.model()
        run = e.running()
        self._favs_refresh()
        self._auto_refresh()
        if e.demod_key and self.dp.pre.currentData() != e.demod_key:   # le moteur a changé d'écoute (micro, pavé…)
            i = self.dp.pre.findData(e.demod_key)
            if i >= 0:
                self._sync = True
                self.dp.pre.setCurrentIndex(i)
                self._sync = False
        self._dem_txt()
        self.go_btn.setText("■ Arrêter le SDR" if run else "▶ Démarrer le SDR")
        self.dev_lbl.setText(TR("📡 {} · fenêtre {} MHz").format(m["name"], f"{e.span():.1f}") if m else "")
        for dsp, v in ((self.a_disp, e.a), (self.b_disp, e.b)):
            if m:
                dsp.setRange(m["fmin"], m["fmax"])
            if v is not None:
                dsp.setValue(v)
        self.b_disp.setEnabled(e.b_on)
        if self.b_chk.isChecked() != bool(e.b_on):
            self.b_chk.blockSignals(True)
            self.b_chk.setChecked(bool(e.b_on))
            self.b_chk.blockSignals(False)
        for b, on in ((self.rec_btn, e.wav is not None),
                      (self.iq_btn, run and (e.worker.rec_req is not None or e.worker.rec is not None))):
            if b.isChecked() != bool(on):
                b.blockSignals(True)
                b.setChecked(bool(on))
                b.blockSignals(False)
        self.rec_btn.setEnabled(run)
        self.iq_btn.setEnabled(run)
        if not run:
            self.a_meter.set_dbm(None)
            self.b_meter.set_dbm(None)
            self.flux.setText("")

    def _frame(self, fr):
        e = self.eng
        now = time.time()
        if now - getattr(self, "_t_auto", 0.0) >= 0.5:          # étape 20 : patrouille, pilote, « c'est quoi »
            self._t_auto = now
            self._auto_refresh()
        self.a_meter.set_dbm(e.dbm(fr.get("lv_a")))
        self.b_meter.set_dbm(e.dbm(fr.get("lv_b")))
        self._af_meter(fr)
        if now - getattr(self, "_t_flux", 0.0) >= 0.5:          # 8.2 : qualité du flux
            self._t_flux = now
            q = e.quality()
            if q:
                self.flux.setText(TR("Flux : {}").format(q[0]))
                self.flux.setStyleSheet("" if q[1] == "ok" else f"color: {self.owner.tone_color(q[1])}; font-weight: 600;")
        self.stats.setText(TR("charge {} % · saturation {} %").format(f"{100 * fr.get('load', 0):.0f}",
                                                                      f"{100 * fr.get('ovf', 0):.1f}"))
        if fr.get("load", 0) > 1.0:                     # 8.1 : le PC ne suit pas -> calcul ou attente ?
            self.stats.setText(self.stats.text() + " · " + TR("calcul {} %, attente {} %").format(
                f"{100 * fr.get('load_cpu', 0):.0f}", f"{100 * max(0.0, fr.get('load', 0) - fr.get('load_cpu', 0)):.0f}"))
            self.stats.setToolTip(TR("Le PC ne suit pas le débit du SDR : le son aura des trous.\n"
                                     "« Calcul » = le temps que le traitement prend vraiment ; « attente » = le temps où il "
                                     "attend le processeur\n(l'affichage ou un autre programme l'occupe). Beaucoup "
                                     "d'attente : ferme des panneaux SDR,\nbaisse la FFT, ou passe en mode Simple."))
        pr = fr.get("prof") or {}
        if pr and fr.get("load", 0) > 0.6:              # 8.1 : détail du calcul (ms pour 50 ms de signal)
            self.stats.setText(self.stats.text() + " · " + TR("spectre {} · démod {} · reste {} ms/50").format(
                f"{pr.get('fft', 0):.0f}", f"{pr.get('dem', 0):.0f}", f"{pr.get('rest', 0):.0f}"))
            dp = fr.get("dprof") or {}
            if dp:                                      # étapes de la démodulation, pour le diagnostic
                self.stats.setText(self.stats.text() + " (" + " · ".join(
                    f"{TR(k)} {v:.0f}" for k, v in dp.items()) + ")")
        if fr.get("fft_frac", 1.0) < 1.0:
            self.stats.setText(self.stats.text() + " · " + TR("spectre allégé (PC à la peine), son prioritaire"))
        self.stats.setStyleSheet(f"color: {self.owner.tone_color('bad')};" if fr.get("ovf", 0) > 0.001 or
                                 fr.get("load", 0) > 1.0 else "")
        if not self.row_zoom.isVisible() or e.a is None:
            return
        if time.monotonic() - getattr(self, "_t_zoom", 0.0) < 0.16:   # 8.1 : zoom du canal et spectre du son à 6 / s
            return
        self._t_zoom = time.monotonic()
        F, L = np.asarray(fr["F"]), np.asarray(fr["avg"])
        bw = max(0.012, expected_obw_khz(e.demod.get("mode", "wfm")) / 1000.0)
        sel = np.abs(F - e.a) <= 1.5 * bw
        iv, av = self.if_view.currentData(), self.af_view.currentData()
        if iv != "spec":                                   # 8.1 : vues de phase du canal
            v = bb_views(fr.get("bb") if fr.get("bb") is not None else [], fr.get("bb_fs") or 0)
            if v is not None:
                if iv == "const":
                    self.if_scat.setData(v["I"], v["Q"])
                elif iv == "phase":
                    self.if_scat.setData(v["tp"], v["phase"])
                elif iv == "iq":                           # 8.2 : I et Q dans le temps (les 2 ms les plus récentes)
                    k_ = max(1, int(len(v["ti"]) * 0.25))
                    self.if_curve.setData(v["ti"][-k_:], v["I"][-k_:])
                    self.if_curve2.setData(v["ti"][-k_:], v["Q"][-k_:])
                else:
                    self.if_curve.setData(v["tf"], v["finst"])
            sel = np.zeros(0, dtype=bool)
        if sel.sum() > 3:
            x = (F[sel] - e.a) * 1000.0
            self.if_curve.setFillLevel(float(np.min(L[sel])))      # remplissage depuis le bruit, pas depuis −160
            self.if_curve.setData(x, L[sel])
            self.if_band.setRegion((-bw * 500.0, bw * 500.0))
        now = time.time()
        if now - self._t_af >= 0.2 and e.af and av != "spec":  # 8.1 : oscilloscope / goniomètre du son
            self._t_af = now
            a = np.frombuffer(b"".join(list(e.af)[-3:]), dtype="<i2").astype(np.float32) / 32768.0
            if len(a) >= 2048:
                st_ = a.reshape(-1, 2)
                if av == "scope":
                    seg = st_[-960:]                           # 20 ms
                    tt = np.arange(len(seg)) / LISTEN_RATE * 1000.0
                    self.af_curve.setData(tt, seg[:, 0])
                    self.af_curve2.setData(tt, seg[:, 1])
                else:
                    g = gonio_points(st_[-4800:, 0], st_[-4800:, 1])
                    if g is not None:
                        self.af_scat.setData(g["x"], g["y"])
                        self.af_plot.setLabel("bottom", TR("corrélation G/D {}").format(
                            f"{g['corr']:+.2f}".replace(".", ",")))
        elif now - self._t_af >= 0.2 and e.af:                 # spectre du son (dernier ~0,1 s)
            self._t_af = now
            a = np.frombuffer(b"".join(list(e.af)[-3:]), dtype="<i2").astype(np.float32)
            if len(a) >= 1024:
                mono = a.reshape(-1, 2).mean(axis=1)[-4096:] / 32768.0
                sp = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) / max(1.0, len(mono) / 4)
                fk = np.fft.rfftfreq(len(mono), 1.0 / LISTEN_RATE) / 1000.0
                keep = fk <= 15.0
                self.af_curve.setData(fk[keep], 20 * np.log10(sp[keep] + 1e-7))

    def apply_level(self):
        lv = self.lvl()
        for w_ in (self.row_b, self.row_dem, self.row_tools):
            w_.setVisible(lv != "simple")
        for w_ in (self.dwell, self.psrc, self.alrec_chk):     # étape 20 : en Simple, patrouille + alarme seulement
            w_.setVisible(lv != "simple")
        self.row_zoom.setVisible(True)                  # étape 18 : le canal et le son se voient aussi en Simple
        if lv == "simple" and self.eng.b_on:            # Simple : un seul récepteur (B n'a pas ses réglages ici)
            self.eng.set_b(on=False)
        for w_ in (self.nfft, self.set_btn, self.stats):
            w_.setVisible(lv == "expert")


class SdrSpectrumPanel(SdrPanelBase):
    """📡 SDR · Spectre (façon WiNRADiO / SDR#) : la fenêtre du SDR sans trou ; tes micros étiquetés (nom + fréquence,
    couleur de leur état) ; canaux TNT à éviter grisés ; A et B en bandes à faire glisser ; clic = A, clic droit = B ;
    Plus : pics gardés, ◀ ▶ micro précédent / suivant, zoom ; Expert : barre d'état (RBW, FFT…) et curseur."""

    def __init__(self, owner, eng=None):
        super().__init__(owner, eng)
        e, o = self.eng, owner
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.mh_chk = QtWidgets.QCheckBox("Pics gardés")
        self.mh_chk.setChecked(e.maxhold)
        self.mh_chk.setToolTip("Garde le plus haut niveau vu à chaque fréquence (repérer un signal bref).")
        self.mh_chk.toggled.connect(lambda on: (e.set_opts(maxhold=bool(on)), self._reset_mh()))
        self.prev_btn = QtWidgets.QToolButton()
        self.prev_btn.setText("Micro préc.")
        self.prev_btn.setToolTip("Écouter le micro précédent (A).")
        self.prev_btn.clicked.connect(lambda *_: self._jump(-1))
        self.next_btn = QtWidgets.QToolButton()
        self.next_btn.setText("Micro suiv.")
        self.next_btn.setToolTip("Écouter le micro suivant (A).")
        self.next_btn.clicked.connect(lambda *_: self._jump(1))
        self.zin = QtWidgets.QToolButton()
        self.zin.setText("＋")
        self.zin.setToolTip("Zoomer autour de A.")
        self.zin.clicked.connect(lambda *_: self._zoom(0.5))
        self.zout = QtWidgets.QToolButton()
        self.zout.setText("−")
        self.zout.setToolTip("Dézoomer.")
        self.zout.clicked.connect(lambda *_: self._zoom(2.0))
        self.zall = QtWidgets.QToolButton()
        self.zall.setText("⤢")
        self.zall.setToolTip("Toute la fenêtre du SDR.")
        self.zall.clicked.connect(lambda *_: self._zoom(None))
        self.span_lbl = QtWidgets.QLabel("")
        self.span_lbl.setToolTip("Début · centre · fin de la fenêtre du SDR, et sa largeur.")
        self.hint = QtWidgets.QLabel("Clic = écouter (A) · clic droit = B")
        self.hint.setToolTip("Tu peux aussi faire glisser les bandes A et B.")
        self.pers_chk = QtWidgets.QCheckBox("Rémanence")            # 8.2 : densité des derniers spectres
        self.pers_chk.setToolTip("Rémanence : les derniers spectres restent visibles et s'effacent doucement ;\n"
                                 "ce qui revient souvent brille (signal intermittent, saut de fréquence).")
        self.pers_chk.toggled.connect(lambda on: self._pers_clear())
        self.ref_btn = QtWidgets.QToolButton()                       # 8.2 : courbe de référence
        self.ref_btn.setText("📌 Référence")
        self.ref_btn.setCheckable(True)
        self.ref_btn.setToolTip("Fige le spectre actuel (ou les pics gardés) en pointillés, pour comparer plus tard :\n"
                                "« avant / après », antenne A contre antenne B… Re-clic = l'effacer.")
        self.ref_btn.toggled.connect(self._ref_toggle)
        self.ref_lbl = QtWidgets.QLabel("")
        self.ref_lbl.setToolTip("Écart entre maintenant et la référence, à la fréquence de A et au plus fort changement.\n"
                                "« Notable » seulement s'il dépasse la variation normale du spectre (6 dB ou 3 écarts-types) :\n"
                                "une différence n'est pas forcément une anomalie.")
        self.bar = QtWidgets.QWidget()
        bl = self._wrap(self.prev_btn, self.next_btn, self.zin, self.zout, self.zall, self.mh_chk, self.pers_chk,
                        self.ref_btn, self.ref_lbl, self.span_lbl, self.hint)
        bl.setContentsMargins(0, 0, 0, 0)
        self.bar.setLayout(bl)
        lay.addWidget(self.bar)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("left", "dBFS")
        self.plot.showGrid(x=True, y=True, alpha=0.22)
        sdr_light_axes(self.plot)
        self.plot.setToolTip(TR("Le spectre du SDR : la fenêtre de quelques MHz qu'il reçoit en entier, sans trou (ce n'est "
                                "pas le balayage du tinySA, qui couvre toute la bande).") + "\n" +
                             TR("Clic = écouter (A) · clic droit = B · molette = zoom."))
        acc = o.theme.get("accent", "#64d2ff")
        self.curve = self.plot.plot(pen=pg.mkPen(o.theme.get("curve", acc), width=1.2))
        self.mh = self.plot.plot(pen=pg.mkPen(o.theme.get("maxhold", "#ff9f0a"), width=1))
        self.refc = self.plot.plot(pen=pg.mkPen("#bf5af2", width=1.2, style=Qt.PenStyle.DashLine))
        self.refc.setZValue(5)
        self._ref, self._pers, self._pers_t, self._pers_img = None, deque(maxlen=30), 0.0, None
        self.reg_a = pg.LinearRegionItem(brush=pg.mkBrush(100, 210, 255, 55), movable=True)
        self.reg_b = pg.LinearRegionItem(brush=pg.mkBrush(255, 159, 10, 45), movable=True)
        self.lab_a = pg.InfiniteLine(angle=90, pen=pg.mkPen(None), label="A",
                                     labelOpts=dict(position=0.06, color="#000000", fill=pg.mkBrush(100, 210, 255, 230)))
        self.lab_b = pg.InfiniteLine(angle=90, pen=pg.mkPen(None), label="B",
                                     labelOpts=dict(position=0.06, color="#000000", fill=pg.mkBrush(255, 159, 10, 230)))
        for r_, nm in ((self.reg_a, "A"), (self.reg_b, "B")):
            r_.setZValue(10)
            self.plot.addItem(r_)
            r_.sigRegionChangeFinished.connect(lambda reg, nm=nm: self._dragged(nm, reg))
        for it in (self.lab_a, self.lab_b):
            it.setZValue(12)
            self.plot.addItem(it)
        self.marks, self.zones, self._mh, self._range = [], [], None, None
        self.plot.scene().sigMouseClicked.connect(self._click)
        self.plot.scene().sigMouseMoved.connect(self._moved)
        lay.addWidget(self.plot, 1)
        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color: #8e8e93; font-family: monospace;")
        self.status.setToolTip("RBW (finesse) · taille de FFT · fenêtre · détecteur · charge · échelle ; et le curseur.")
        self.cursor_lbl = QtWidgets.QLabel("")
        self.cursor_lbl.setStyleSheet("color: #8e8e93; font-family: monospace;")
        self.sbar = QtWidgets.QWidget()
        sb = QtWidgets.QHBoxLayout(self.sbar)
        sb.setContentsMargins(4, 0, 4, 0)
        sb.addWidget(self.status, 1)
        sb.addWidget(self.cursor_lbl)
        lay.addWidget(self.sbar)
        e.frame.connect(self._frame)
        e.changed.connect(self._vfo)
        self.tm = QtCore.QTimer(self)
        self.tm.timeout.connect(self._marks)
        self.tm.start(2000)
        self._vfo()
        self.apply_level()

    def _bw(self):
        return max(0.012, expected_obw_khz(self.eng.demod.get("mode", "wfm")) / 1000.0)

    def _vfo(self):
        e = self.eng
        b_on = bool(e.b_on and e.b is not None and self.lvl() != "simple")
        for r_, lab, f, on, nm in ((self.reg_a, self.lab_a, e.a, e.a is not None, "A"),
                                   (self.reg_b, self.lab_b, e.b, b_on, "B")):
            r_.setVisible(on)
            lab.setVisible(on)
            if on:
                r_.blockSignals(True)
                r_.setRegion((f - self._bw() / 2.0, f + self._bw() / 2.0))
                r_.blockSignals(False)
                lab.setValue(f)
                lab.label.setFormat(f"{nm} · {f:.4f}")
        if self._range is None:
            idle_sdr_view(self.plot, e, (-120.0, 0.0))
        self._marks()

    def _dragged(self, nm, reg):
        lo, hi = reg.getRegion()
        f = (lo + hi) / 2.0
        if nm == "A":
            self.eng.set_a(f)
        else:
            self.eng.set_b(f=f)

    def _click(self, ev):
        vb = self.plot.getPlotItem().vb
        if not vb.sceneBoundingRect().contains(ev.scenePos()) or ev.double():
            return
        f = float(vb.mapSceneToView(ev.scenePos()).x())
        st = self.eng.step / 1000.0
        f = round(f / st) * st
        if ev.button() == Qt.MouseButton.RightButton and self.lvl() != "simple":
            self.eng.set_b(f=f, on=True)
        elif ev.button() == Qt.MouseButton.LeftButton:
            self.eng.set_a(f)

    def _moved(self, pos):
        vb = self.plot.getPlotItem().vb
        fr = self.eng.last
        if fr is None or not vb.sceneBoundingRect().contains(pos):
            self.cursor_lbl.setText("")
            return
        f = float(vb.mapSceneToView(pos).x())
        F, L = np.asarray(fr["F"]), np.asarray(fr["avg"])
        i = int(np.argmin(np.abs(F - f)))
        self.cursor_lbl.setText(f"⌖ {f:.4f} MHz · {L[i]:.1f} dBFS")

    def _jump(self, d):
        e = self.eng
        m = e.model()
        fs = [w["freq"] for w in self.owner.watch if not m or sdr_in_range(m, w["freq"])]
        f = next_mic(fs, e.a if e.a is not None else 0.0, d)
        if f is not None:
            e.set_a(f)

    def _zoom(self, k):
        if self._range is None:
            return
        if k is None:
            self.plot.setXRange(*self._range, padding=0.0)
            return
        lo, hi = self.plot.getPlotItem().vb.viewRange()[0]
        c = self.eng.a if self.eng.a is not None else (lo + hi) / 2.0
        h = max(0.01, (hi - lo) * k / 2.0)
        self.plot.setXRange(max(self._range[0], c - h), min(self._range[1], c + h), padding=0.0)

    def _reset_mh(self):
        self._mh = None
        self.mh.setData([], [])

    # ---- 8.2 : rémanence et référence
    def _pers_clear(self):
        self._pers.clear()
        if self._pers_img is not None:
            self._pers_img.setVisible(False)

    def _pers_draw(self, F, avg):
        self._pers.appendleft((np.asarray(F, dtype=float), np.asarray(avg, dtype=float)))
        now = time.monotonic()
        if now - self._pers_t < 0.25:
            return
        self._pers_t = now
        vb = self.plot.getPlotItem().vb
        (x0, x1), (y0, y1) = vb.viewRange()
        W, H = int(min(1400, max(64, vb.width()))), int(min(600, max(48, vb.height())))
        n = len(self._pers)
        try:
            arr = density_glow(density_raster(list(self._pers), x0, x1, y0, y1, W, H,
                                              [1.0 - i / (n + 1.0) for i in range(n)]))
        except Exception:  # noqa: BLE001
            return
        if self._pers_img is None:
            self._pers_img = pg.ImageItem()
            self._pers_img.setZValue(-5)
            self._pers_img.setLookupTable(density_lut(self.owner.theme.get("curve", "#64d2ff")))
            self.plot.addItem(self._pers_img)
        self._pers_img.setImage(arr, autoLevels=False, levels=(0.0, 1.0))
        self._pers_img.setRect(QtCore.QRectF(x0, y0, x1 - x0, y1 - y0))
        self._pers_img.setVisible(True)

    def _ref_toggle(self, on):
        fr = self.eng.last
        self._refc = None
        if on and fr is not None:
            F = np.asarray(fr["F"], dtype=float)
            L = np.asarray(self._mh if self._mh is not None and self.mh_chk.isChecked() else fr["avg"], dtype=float)
            if len(F) != len(L):
                F = np.linspace(F[0], F[-1], len(L))
            self._ref = (F, L.copy(), time.strftime("%H:%M:%S"))
            self.refc.setData(F, L)
        else:
            self._ref = None
            self.refc.setData([], [])
            self.ref_lbl.setText("")
            if on:
                self.ref_btn.blockSignals(True)
                self.ref_btn.setChecked(False)
                self.ref_btn.blockSignals(False)

    def _ref_cmp(self, F, avg):
        if self._ref is None:
            return
        rF, rL, t = self._ref
        if len(rF) < 2 or rF[0] > F[-1] or rF[-1] < F[0]:
            self.ref_lbl.setText(TR("Réf. {} : autre fenêtre").format(t))
            return
        d = np.asarray(avg, dtype=float) - np.interp(F, rF, rL, left=np.nan, right=np.nan)
        txt = TR("Réf. {}").format(t)
        a = self.eng.a
        if a is not None and F[0] <= a <= F[-1]:
            m = np.abs(F - a) <= 0.05
            if m.any():
                txt += " · " + TR("A : {} dB").format(f"{float(np.nanmax(d[m])):+.1f}")
        rc = getattr(self, "_refc", None)               # 8.2 : écart jugé par rapport à la variation NORMALE
        if rc is None:
            rc = self._refc = RefCompare()
        rc.feed(avg)
        j = rc.judge(F, avg, rF, rL)
        if j is not None:
            if j["notable"]:
                txt += " · " + TR("⚠ écart notable {} dB à {} MHz").format(f"{j['d']:+.1f}", f"{j['f']:.3f}")
                self.ref_lbl.setStyleSheet(f"color: {self.owner.tone_color('warn')};")
            else:
                txt += " · " + TR("dans la variation normale (± {} dB)").format(f"{max(6.0, 3 * j['sigma']):.0f}")
                self.ref_lbl.setStyleSheet("")
        self.ref_lbl.setText(txt)

    def _frame(self, fr):
        F, avg, mx = fr["F"], fr["avg"], fr["mx"]
        if len(F) != len(avg):
            F = np.linspace(F[0], F[-1], len(avg))
        self.curve.setData(F, avg)
        if self.pers_chk.isChecked() and self.lvl() != "simple":
            self._pers_draw(F, avg)
        if self._ref is not None and self.lvl() != "simple":
            self._ref_cmp(np.asarray(F, dtype=float), avg)
        if self.eng.maxhold and self.lvl() != "simple":
            self._mh = mx.copy() if self._mh is None or len(self._mh) != len(mx) else np.maximum(self._mh, mx)
            self.mh.setData(F, self._mh)
        rng = (float(F[0]), float(F[-1]))
        if rng != self._range:                            # nouvelle fenêtre du SDR : on la montre en entier
            self._range = rng
            self.plot.setXRange(*rng, padding=0.0)
            self._reset_mh()
            self._pers_clear()
            self._marks()
            self.span_lbl.setText(f"{rng[0]:.3f} · {(rng[0] + rng[1]) / 2:.3f} · {rng[1]:.3f} MHz "
                                  f"({rng[1] - rng[0]:.2f} MHz)")
        e = self.eng
        cal = bool((e.model() or {}).get("cal")) or bool(self.owner.sdr_offset(e.kind()))
        self.status.setText(spectrum_status(e.rate or 0, e.nfft, fr.get("load", 0), fr.get("ovf", 0), cal, TR))

    def _marks(self):
        """Tes micros de la fenêtre, étiquetés (nom + fréquence, couleur de leur état), et les canaux TNT à éviter."""
        o = self.owner
        for it in self.marks + self.zones:
            self.plot.removeItem(it)
        self.marks, self.zones = [], []
        if self._range is None:
            return
        lo, hi = self._range
        tc = getattr(o, "tnt_cfg", {}) or {}
        try:
            code = o.country_code()
        except Exception:  # noqa: BLE001
            code = "FR"
        for a, b, lab in sdr_zones(code, tc.get("manual"), tc.get("plan"), lo, hi):
            z = pg.LinearRegionItem((a, b), movable=False, brush=pg.mkBrush(120, 130, 160, 70),
                                    pen=pg.mkPen(120, 130, 160, 160))
            z.setZValue(-5)
            t = pg.InfiniteLine(pos=(max(a, lo) + min(b, hi)) / 2.0, angle=90, pen=pg.mkPen(None),
                                label=TR("{} — à éviter").format(lab),
                                labelOpts=dict(position=0.5, color="#ffffff", fill=pg.mkBrush(60, 70, 95, 200)))
            for it in (z, t):
                self.plot.addItem(it)
                self.zones.append(it)
        ws = sorted((w for w in o.watch if lo <= w["freq"] <= hi), key=lambda w: w["freq"])[:40]
        for i, w in enumerate(ws):
            col = QtGui.QColor(o.sig_view(w)[2])
            fill = QtGui.QColor(col)
            fill.setAlpha(215)
            ln = pg.InfiniteLine(pos=w["freq"], angle=90, movable=False,
                                 pen=pg.mkPen(col, width=1, style=Qt.PenStyle.DashLine),
                                 label=f"{w['name'] or '—'}\n{w['freq']:.3f}",
                                 labelOpts=dict(position=0.92 - (i % 3) * 0.11, color="#000000", fill=pg.mkBrush(fill)))
            ln.setZValue(5)
            self.plot.addItem(ln)
            self.marks.append(ln)

    def apply_level(self):
        lv = self.lvl()
        for w_ in (self.prev_btn, self.next_btn, self.zin, self.zout, self.zall, self.mh_chk, self.span_lbl,
                   self.pers_chk, self.ref_btn, self.ref_lbl):
            w_.setVisible(lv != "simple")
        self.sbar.setVisible(lv == "expert")
        self.hint.setText(TR("Clic = écouter") if lv == "simple" else TR("Clic = écouter (A) · clic droit = B"))
        if lv == "simple":
            self.mh.setData([], [])
            self._pers_clear()


class SdrWaterfallPanel(SdrPanelBase):
    """📡 SDR · Waterfall de la fenêtre du SDR (le temps descend), A et B en traits."""
    ROWS = 240

    def __init__(self, owner, eng=None):
        super().__init__(owner, eng)
        e, o = self.eng, owner
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.plot = pg.PlotWidget()
        self.plot.hideAxis("left")
        self.plot.setLabel("bottom", "MHz")
        sdr_light_axes(self.plot)
        self.img = pg.ImageItem()
        self.img.setLookupTable(make_lut(o.theme.get("wf", "Inferno")))
        self.plot.addItem(self.img)
        self.la = pg.InfiniteLine(angle=90, pen=pg.mkPen("#0a84ff", width=1))
        self.lb = pg.InfiniteLine(angle=90, pen=pg.mkPen("#ff9f0a", width=1))
        for ln in (self.la, self.lb):
            self.plot.addItem(ln)
        lay.addWidget(self.plot, 1)
        self.q, self._rng = None, None
        e.frame.connect(self._frame)
        e.changed.connect(self._vfo)
        self._vfo()

    def _vfo(self):
        e = self.eng
        if self._rng is None:
            idle_sdr_view(self.plot, e, (0.0, float(self.ROWS)))
        self.la.setVisible(e.a is not None)
        self.lb.setVisible(bool(e.b_on and e.b is not None))
        if e.a is not None:
            self.la.setValue(e.a)
        if e.b is not None:
            self.lb.setValue(e.b)

    def _frame(self, fr):
        F, avg = fr["F"], np.asarray(fr["avg"], dtype=np.float32)
        if self.q is None or self.q.shape[1] != len(avg) or self._rng != (float(F[0]), float(F[-1])):
            self.q = np.full((self.ROWS, len(avg)), np.nan, dtype=np.float32)
            self._rng = (float(F[0]), float(F[-1]))
        self.q[:-1] = self.q[1:]                         # 8.1 : décalage sur place (pas de copie complète)
        self.q[-1] = avg
        now = time.monotonic()
        if now - getattr(self, "_t_lv", 0.0) > 1.0 or getattr(self, "_lv", None) is None:
            fin = self.q[np.isfinite(self.q)]                # niveaux recalculés une fois par seconde seulement
            if fin.size:
                lo = float(np.percentile(fin[:: max(1, fin.size // 20000)], 5))
                self._lv, self._t_lv = (lo, max(lo + 10.0, float(fin.max()))), now
        if now - getattr(self, "_t_img", 0.0) < 0.12 or getattr(self, "_lv", None) is None:
            return                                       # 8 images / s au plus
        self._t_img = now
        self.img.setImage(self.q.T, autoLevels=False, levels=self._lv)   # vide (NaN) = transparent
        self.img.setRect(QtCore.QRectF(self._rng[0], 0.0, self._rng[1] - self._rng[0], float(self.ROWS)))


def proc_usage():
    """8.2 : mémoire du processus (Mo) et temps de calcul cumulé (s) de l'appli, sans dépendance de plus."""
    mem = None
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            c = _PMC()
            c.cb = ctypes.sizeof(c)
            if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c),
                                                        c.cb):
                mem = c.WorkingSetSize / 1e6
        else:
            with open("/proc/self/statm") as f:
                mem = int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e6
    except Exception:  # noqa: BLE001
        mem = None
    return mem, time.process_time()


class SdrDiagPanel(SdrPanelBase):
    """📡 SDR · Diagnostic (8.2, propositions « SDR réel » : historique, qualité, fiche appareil, système, sessions) :
    ce qui s'est passé sur le poste (horodaté, avec le contexte), l'état du matériel, la santé du PC, et la session
    enregistrée (CSV, rapport HTML / PDF). Données du SDR démo marquées 🧪 simulé."""

    def __init__(self, owner, eng=None):
        super().__init__(owner, eng)
        e, o = self.eng, owner
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.head = QtWidgets.QLabel("")
        self.head.setWordWrap(True)
        self.head.setToolTip("D'où viennent ces données (SDR réel ou simulé) et la qualité du flux en ce moment.")
        lay.addWidget(self.head)
        self.tabs = QtWidgets.QTabWidget()
        lay.addWidget(self.tabs, 1)
        # événements
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self.filt = QtWidgets.QComboBox()
        self.filt.addItem(TR("Tout"), "all")
        self.filt.addItem(TR("Problèmes seulement"), "bad")
        self.filt.setToolTip("Tout l'historique, ou seulement ce qui demande de l'attention (orange / rouge).")
        self.filt.currentIndexChanged.connect(lambda *_: self._fill(force=True))
        self.csv_btn = QtWidgets.QPushButton("💾 CSV…")
        self.csv_btn.setToolTip("Enregistre l'historique des événements en CSV (tableur).")
        self.csv_btn.clicked.connect(lambda *_: self.export_csv())
        self.rep_btn = QtWidgets.QPushButton("📄 Rapport…")
        self.rep_btn.setToolTip("Rapport de la session : courbes (niveau de A, pertes, charge) et événements, en HTML ou PDF.")
        self.rep_btn.clicked.connect(lambda *_: self.export_report())
        self.clr_btn = QtWidgets.QPushButton("Effacer")
        self.clr_btn.setToolTip("Vide l'historique affiché (la session enregistrée sur le disque reste).")
        self.clr_btn.clicked.connect(lambda *_: self.clear())
        v.addLayout(o._row(self.filt, None, self.csv_btn, self.rep_btn, self.clr_btn))
        self.tbl = QtWidgets.QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels([TR(x) for x in ("Heure", "Événement", "Détail", "A (MHz)", "Niveau A")])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setToolTip("Ce qui s'est passé sur ce poste SDR, le plus récent en haut. Une ligne n'est pas forcément "
                            "une panne :\nà recouper avec ce que tu entendais.")
        v.addWidget(self.tbl, 1)
        self.tabs.addTab(w, TR("Événements"))
        # appareil
        self.dev = QtWidgets.QLabel("")
        self.dev.setWordWrap(True)
        self.dev.setTextFormat(Qt.TextFormat.RichText)
        self.dev.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dev.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sa = QtWidgets.QScrollArea()
        sa.setWidgetResizable(True)
        sa.setWidget(self.dev)
        self.tabs.addTab(sa, TR("Appareil"))
        # système
        self.sys = QtWidgets.QLabel("")
        self.sys.setWordWrap(True)
        self.sys.setTextFormat(Qt.TextFormat.RichText)
        self.sys.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.tabs.addTab(self.sys, TR("Système"))
        # session
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        self.sess_chk = QtWidgets.QCheckBox("Enregistrer chaque session (CSV : mesures toutes les 2 s + événements)")
        self.sess_chk.setChecked(bool(o.sdr_cfg.get("sdr_session", True)))
        self.sess_chk.setToolTip("À chaque ▶ du poste, deux fichiers CSV dans <journaux>/sessions_sdr/<date>/ : rien du son, "
                                 "seulement des niveaux et des événements (quelques Ko par heure).")
        self.sess_chk.toggled.connect(lambda on: o.sdr_cfg.__setitem__("sdr_session", bool(on)))
        v.addWidget(self.sess_chk)
        self.sess_lbl = QtWidgets.QLabel("")
        self.sess_lbl.setWordWrap(True)
        self.sess_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.sess_lbl)
        b = QtWidgets.QPushButton("📁 Ouvrir le dossier des sessions")
        b.setToolTip("Les sessions SDR enregistrées (un dossier par jour).")
        b.clicked.connect(lambda *_: self._open_dir())
        v.addWidget(b)
        v.addStretch(1)
        self.tabs.addTab(w, TR("Session"))
        self._n_shown, self._cpu = -1, None
        self.tm = QtCore.QTimer(self)
        self.tm.timeout.connect(self.refresh)
        self.tm.start(1000)

    def _sev_color(self, sev):
        return self.owner.tone_color(sev) if sev in ("warn", "bad") else (
            self.owner.tone_color("ok") if sev == "ok" else "")

    def _fill(self, force=False):
        h = list(getattr(self.eng, "hist", []))
        key = (len(h), h[-1]["t"] if h else 0, self.filt.currentData())
        if not force and key == getattr(self, "_fkey", None):
            return
        self._fkey = key
        if self.filt.currentData() == "bad":
            h = [x for x in h if x["sev"] in ("warn", "bad")]
        h = h[-400:][::-1]
        t = self.tbl
        t.setRowCount(len(h))
        for i, ev in enumerate(h):
            r = sdr_event_row(ev)
            vals = [r[0], ("🧪 " if ev.get("sim") else "") + TR(r[1]), TR(r[2]) if r[2] else "", r[3], r[4]]
            col = self._sev_color(ev["sev"])
            for j, x in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(x)
                if col and j == 1:
                    it.setForeground(QtGui.QColor(col))
                t.setItem(i, j, it)

    def refresh(self):
        if self.isVisible() is not True:
            return
        e, o = self.eng, self.owner
        demo = e.kind() == "demo"
        prov = TR(PROVENANCE["sim" if demo else "obs"])
        q = e.quality()
        self.head.setText(f"<b>{_hesc(e.name())}</b> · {_hesc(prov)} · " +
                          (_hesc(TR("Flux : {}").format(q[0])) if q else _hesc(TR("poste arrêté"))))
        self._fill()
        m = e.model() or {}
        w = e.worker
        fr = e.last if w is not None else None
        rows = [(TR("Appareil"), m.get("name", "—")), (TR("Genre"), e.kind()),
                (TR("N° de série"), e.post().get("serial") or "—"),
                (TR("État"), TR("en marche") if w is not None else (
                    TR("reconnexion en cours") if getattr(e, "_recovering", False) else TR("arrêté"))),
                (TR("Capacités"), caps_text(device_caps(e.kind(), m), TR)),
                (TR("Débit réglé"), f"{(e.rate or 0) / 1e6:g} MS/s" if e.rate else "—")]
        if fr is not None:
            qd = fr.get("q") or {}
            rows.append((TR("Dernière communication"), TR("il y a {} s").format(f"{max(0.0, time.time() - fr.get('t', time.time())):.1f}")))
            if qd.get("rate"):
                rows.append((TR("Débit reçu"), f"{qd['rate'] / 1e6:.3f} MS/s ({100 * qd['rate'] / (e.rate or 1):.1f} %)"))
            rows.append((TR("Échantillons reçus"), f"{qd.get('total', 0):,}".replace(",", " ")))
        rows.append((TR("Reconnexions"), str(getattr(e, "recon", 0))))
        errs = list(getattr(w, "err", []) if w is not None else [])[-5:]
        rows.append((TR("Dernières erreurs de l'outil"), " | ".join(errs) if errs else "—"))
        if demo:
            rows.append((TR("Note"), TR("SDR démo : appareil simulé par l'appli, aucune mesure réelle.")))
        self.dev.setText("<table>" + "".join(f"<tr><td style='color:#8e8e93;padding-right:10px'>{_hesc(a)}</td>"
                                             f"<td>{_hesc(str(b))}</td></tr>"
                                             for a, b in rows) + "</table>")
        mem, cpu_t = proc_usage()
        now = time.monotonic()
        cpu = None
        if self._cpu is not None and now - self._cpu[0] > 0.2:
            cpu = 100.0 * (cpu_t - self._cpu[1]) / (now - self._cpu[0])
        self._cpu = (now, cpu_t)
        srows = [(TR("Processeur (toute l'appli)"), "—" if cpu is None else f"{cpu:.0f} % " + TR("d'un cœur")),
                 (TR("Mémoire (toute l'appli)"), "—" if mem is None else f"{mem:.0f} Mo")]
        if fr is not None:
            srows += [(TR("Charge du poste"), f"{100 * fr.get('load', 0):.0f} %"),
                      (TR("dont calcul"), f"{100 * fr.get('load_cpu', 0):.0f} %"),
                      (TR("Débit traité"), f"{(e.rate or 0) * (1 - ((fr.get('q') or {}).get('lost') or 0) / 100) / 1e6:.2f} MS/s"),
                      (TR("Spectre calculé sur"), f"{100 * fr.get('fft_frac', 1.0):.0f} %")]
            pr = fr.get("prof") or {}
            if pr:
                srows.append((TR("Temps par morceau de 50 ms"), TR("spectre {} · démod {} · reste {} ms").format(
                    f"{pr.get('fft', 0):.1f}", f"{pr.get('dem', 0):.1f}", f"{pr.get('rest', 0):.1f}")))
            srows.append((TR("Son en attente"), f"{len(e.q)}"))
        self.sys.setText("<table>" + "".join(f"<tr><td style='color:#8e8e93;padding-right:10px'>{_hesc(a)}</td>"
                                             f"<td>{_hesc(b)}</td></tr>" for a, b in srows) + "</table>")
        f = getattr(e, "_sess", None)
        self.sess_lbl.setText(TR("Session en cours : {}").format(f["base"] + "_*.csv") if f else
                              TR("Pas de session en cours (poste arrêté, ou enregistrement coupé)."))

    def _dir(self):
        return Path(self.owner.log_dir) / "sessions_sdr"

    def _open_dir(self):
        d = self._dir()
        d.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(d)))

    def export_csv(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, TR("Historique du poste SDR"),
                                                            str(self._dir() / f"evenements_{datetime.now():%Y%m%d_%H%M%S}.csv"),
                                                            "CSV (*.csv)")
            if not path:
                return None
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(SDR_EVENTS_HEAD)
            for ev in getattr(self.eng, "hist", []):
                w.writerow(sdr_event_row(ev))
        return path

    def export_report(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, TR("Rapport de la session SDR"), str(Path(self.owner.log_dir) / "rapports" /
                                                          f"session_sdr_{datetime.now():%Y%m%d_%H%M%S}.html"),
                "HTML (*.html);;PDF (*.pdf)")
            if not path:
                return None
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.eng.session_report(path)
        if not os.environ.get("TSM_NO_BROWSER") and path.lower().endswith(".html"):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        return path

    def clear(self):
        if hasattr(self.eng, "hist"):
            self.eng.hist.clear()
        self._fill(force=True)


class SdrMicsPanel(SdrPanelBase):
    """📡 SDR · Mes micros : tes fréquences dans la fenêtre du SDR (niveau mesuré par le SDR, état), clic = écouter
    (A), clic droit = écouter en B. Celles hors de la fenêtre sont dites."""
    COLS = ["Nom", "MHz", "Niveau SDR", "État"]

    def __init__(self, owner, eng=None):
        super().__init__(owner, eng)
        e, o = self.eng, owner
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        hh = self.table.horizontalHeader()
        for c in range(3):
            hh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("Tes fréquences dans la fenêtre du SDR. Clic = l'écouter (A) ; clic droit = en B, ou la mettre "
                              "sur une touche du pavé numérique.")
        self.table.cellClicked.connect(lambda r, c: self._pick(r, "a"))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(lambda p: self._menu(self.table.rowAt(p.y())))
        self.add_btn = QtWidgets.QPushButton(TR("＋ Ajouter ma sélection"))           # 8.0.2 : micros choisis
        self.add_btn.setToolTip(TR("Ajoute les lignes choisies dans « Mes fréquences » aux micros suivis par ce SDR "
                                   "(aussi : clic droit dans Mes fréquences › 📡, ou Ctrl+Maj+F)."))
        self.add_btn.clicked.connect(lambda *_: self.owner.sdr_follow(self.owner.watch_selected(), True, self.eng.pid))
        self.del_btn = QtWidgets.QPushButton(TR("Retirer"))
        self.del_btn.setToolTip(TR("Retire les micros choisis ici de ceux que suit ce SDR (Suppr)."))
        self.del_btn.clicked.connect(lambda *_: self._remove())
        self.all_btn = QtWidgets.QPushButton(TR("↺ Tous"))
        self.all_btn.setToolTip(TR("Le SDR suit de nouveau tous les micros (de ses scènes)."))
        self.all_btn.clicked.connect(lambda *_: self.owner.sdr_follow_clear(self.eng.pid))
        self.mode_lbl = QtWidgets.QLabel("")
        self.mode_lbl.setToolTip(TR("Ce que suit ce SDR : les micros que tu as choisis, ou tous ceux de ses scènes."))
        lay.addLayout(self._wrap(self.mode_lbl, self.add_btn, self.del_btn, self.all_btn))
        try:
            del_key(self.table, self._remove)
        except Exception:  # noqa: BLE001
            pass
        lay.addWidget(self.table, 1)
        self.note = QtWidgets.QLabel("")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        self.ws = []
        self.tm = QtCore.QTimer(self)
        self.tm.timeout.connect(self.refresh)
        self.tm.start(500)
        e.changed.connect(self.refresh)
        self.refresh()

    def _menu(self, r):
        """Clic droit sur un micro : écouter en A / en B, le mettre sur une touche du pavé numérique."""
        if not 0 <= r < len(self.ws):
            return
        o, w = self.owner, self.ws[r]
        m = QtWidgets.QMenu(self)
        m.addAction(TR("🎧 Écouter (A)")).triggered.connect(lambda *_: self._pick(r, "a"))
        if self.lvl() != "simple":
            m.addAction(TR("🎧 Écouter en B")).triggered.connect(lambda *_: self._pick(r, "b"))
        sm = m.addMenu(TR("⭐ Touche du pavé numérique"))
        favs = favs_norm(o.sdr_cfg.get("favs"))
        for k in range(1, FAV_KEYS + 1):
            cur = o.watch_by_key(favs[k]) if k in favs else None
            sm.addAction(f"{k} · " + ((cur["name"] or f"{cur['freq']:.3f}") if cur else TR("libre"))).triggered.connect(
                lambda *_, k=k: o.sdr_set_fav(k, w))
        if o.sdr_cfg.get("demo"):                         # étape 21 : le son de ce micro dans le SDR démo
            m.addAction(TR("🎵 Son de ce micro dans le SDR démo…")).triggered.connect(lambda *_: o.pick_demo_sound(w))
        m.exec(QtGui.QCursor.pos())

    def _remove(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        ws = [self.ws[r] for r in rows if 0 <= r < len(self.ws)]
        if ws:
            self.owner.sdr_follow(ws, False, self.eng.pid)

    def _pick(self, r, slot):
        if not 0 <= r < len(self.ws):
            return
        f = self.ws[r]["freq"]
        if slot == "a":
            self.eng.set_a(f)                            # set_a applique le réglage d'écoute du micro
        elif self.lvl() != "simple":
            self.eng.set_b(f=f, on=True)

    def refresh(self):
        if not self.isVisible() and self.ws:
            return
        o, e = self.owner, self.eng
        m = e.model()
        allw = [w for w in e.ws() if not m or sdr_in_range(m, w["freq"])]       # les micros de SES scènes
        chosen = bool(e.post().get("mics"))
        if e.center is not None:
            inside = [w for w in allw if vfo_inside(e.center, e.span(), w["freq"], 0.0)]
        else:
            inside = list(allw)
        n_out = len(allw) - len(inside)
        out_ws = [w for w in allw if w not in inside] if chosen else []     # choisis : tous listés (hors fenêtre grisés)
        self.ws = inside + out_ws
        n_mine = len(e.post().get("mics") or [])
        self.mode_lbl.setText(TR("📡 Suit {} micro(s) choisi(s)").format(n_mine) if chosen
                              else TR("📡 Suit tous les micros") + (" " + TR("de ses scènes") if e.post()["scenes"] else ""))
        self.del_btn.setEnabled(chosen)
        self.all_btn.setEnabled(chosen)
        if self.table.rowCount() != len(self.ws):
            self.table.setRowCount(len(self.ws))
        for r, w in enumerate(self.ws):
            lv = e.level_at(w["freq"]) if e.running() else None
            txt, tone, col = o.sig_view(w)
            here = (" 🎧A" if e.a is not None and abs(e.a - w["freq"]) < 1e-4 else "") + \
                   (" 🎧B" if e.b_on and e.b is not None and abs(e.b - w["freq"]) < 1e-4 else "")
            outside = w in out_ws
            if outside:
                lv, txt, col = None, TR("↪ hors de la fenêtre (clic = y aller)"), "#8e8e93"
            for c, v in enumerate((w["name"] + here, f"{w['freq']:.3f}", "—" if lv is None else f"{lv:.0f} dBm", txt)):
                it = self.table.item(r, c)
                if it is None:
                    it = QtWidgets.QTableWidgetItem(v)
                    self.table.setItem(r, c, it)
                elif it.text() != v:
                    it.setText(v)
            self.table.item(r, 3).setForeground(QtGui.QColor(col))
        if chosen:
            self.note.setText("" if self.ws else TR("Aucun de tes micros choisis n'est dans la plage de ce SDR."))
        else:
            self.note.setText(TR("Pour n'en suivre que quelques-uns : choisis-les dans « Mes fréquences » puis « ＋ Ajouter "
                                 "ma sélection » (ou clic droit › 📡).") + ("" if not n_out else "\n" + TR(
                "{} autre(s) fréquence(s) hors de la fenêtre du SDR : clique un micro ou tape sa fréquence en A pour y "
                "aller.").format(n_out)))


class SdrPostsDialog(QtWidgets.QDialog):
    """📡 Mes SDR (étape 17) : un ou plusieurs SDR qui écoutent / surveillent en même temps que les tinySA. Pour chacun :
    nom, modèle, n° de série (pour distinguer deux SDR du même modèle), scènes qu'il surveille ; ▶ / ■ ; place sur la
    carte. Tout s'applique tout de suite."""
    COLS = ["Nom", "Modèle", "N° de série", "Scènes", "État"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = o = owner
        self.setWindowTitle("Mes SDR")
        self.setModal(False)
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Plusieurs SDR peuvent tourner en même temps que tes tinySA : chacun surveille et écoute "
                                "les micros de SES scènes (aucune scène = tout le site), avec ses propres panneaux. "
                                "Place-les sur la 🗺 carte comme les tinySA.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 3)
        lay.addWidget(info)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Nom et n° de série se tapent ; Modèle et Scènes se choisissent dans leur liste.")
        lay.addWidget(self.table, 1)
        self.add_btn = QtWidgets.QPushButton("＋ Ajouter un SDR")
        self.add_btn.setToolTip("Un poste SDR de plus (4 au plus) : ses panneaux apparaissent en onglets, déplace-les où tu veux.")
        self.add_btn.clicked.connect(lambda *_: self.add())
        self.del_btn = QtWidgets.QPushButton("Retirer")
        self.del_btn.setToolTip("Retire le poste choisi (le 1er reste).")
        self.del_btn.clicked.connect(lambda *_: self.remove())
        self.go_btn = QtWidgets.QPushButton("Démarrer / arrêter")
        self.go_btn.setToolTip("Démarre ou arrête le poste choisi.")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        self.map_btn = QtWidgets.QPushButton("🗺 Carte")
        self.map_btn.setToolTip("Ouvre la carte : fais glisser un SDR sur une scène pour qu'il la surveille.")
        self.map_btn.clicked.connect(lambda *_: o.open_map())
        lay.addLayout(o._row(self.add_btn, self.del_btn, self.go_btn, None, self.map_btn))
        self.st = QtWidgets.QLabel("")
        self.st.setWordWrap(True)
        lay.addWidget(self.st)
        self._busy = False
        self.fill()
        self.tm = QtCore.QTimer(self)
        self.tm.timeout.connect(self._states)
        self.tm.start(1000)
        fit_dialog(self, 860, 420)

    def posts(self):
        return sdr_posts_norm(self.owner.sdr_cfg.get("posts"))

    def _save(self, posts):
        self.owner.sdr_cfg["posts"] = sdr_posts_norm(posts)
        self.owner._sdr_posts_sync()
        try:
            self.owner.map_scene().sync()
        except Exception:  # noqa: BLE001
            pass

    def fill(self):
        o = self.owner
        self._busy = True
        ps = self.posts()
        self.table.setRowCount(len(ps))
        for r, p in enumerate(ps):
            it = QtWidgets.QTableWidgetItem(p["name"])
            it.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.table.setItem(r, 0, it)
            cb = QtWidgets.QComboBox()
            cb.addItem(TR("(celui des Réglages SDR)"), "")
            for m in SDR_MODELS:
                if m.get("kind"):
                    cb.addItem(m["name"], m["key"])
            cb.setCurrentIndex(max(0, cb.findData(p["model"])))
            cb.currentIndexChanged.connect(lambda *_, r=r: self._edit(r))
            self.table.setCellWidget(r, 1, cb)
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(p["serial"]))
            sb = QtWidgets.QToolButton()
            sb.setText(", ".join(p["scenes"]) or TR("tout le site"))
            sb.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            mn = QtWidgets.QMenu(sb)
            for sc in o.scenes:
                a_ = mn.addAction(sc["name"])
                a_.setCheckable(True)
                a_.setChecked(sc["name"] in p["scenes"])
                a_.toggled.connect(lambda on, r=r, n=sc["name"]: self._scene(r, n, on))
            sb.setMenu(mn)
            self.table.setCellWidget(r, 3, sb)
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(""))
        self._busy = False
        self.table.itemChanged.connect(self._item) if not getattr(self, "_conn", False) else None
        self._conn = True
        self._states()

    def _row_post(self, r):
        it = self.table.item(r, 0)
        pid = it.data(Qt.ItemDataRole.UserRole) if it else None
        ps = self.posts()
        return ps, next((p for p in ps if p["id"] == pid), None)

    def _item(self, it):
        if self._busy or it.column() not in (0, 2):
            return
        self._edit(it.row())

    def _edit(self, r):
        if self._busy:
            return
        ps, p = self._row_post(r)
        if p is None:
            return
        p["name"] = (self.table.item(r, 0).text() if self.table.item(r, 0) else p["name"]).strip() or p["name"]
        p["serial"] = (self.table.item(r, 2).text() if self.table.item(r, 2) else "").strip()
        p["model"] = self.table.cellWidget(r, 1).currentData() or ""
        self._save(ps)

    def _scene(self, r, name, on):
        ps, p = self._row_post(r)
        if p is None:
            return
        p["scenes"] = sorted(set(p["scenes"]) | {name}) if on else [s for s in p["scenes"] if s != name]
        self._save(ps)
        self.table.cellWidget(r, 3).setText(", ".join(p["scenes"]) or TR("tout le site"))

    def add(self):
        ps = self.posts()
        free = [i for i in range(1, SDR_POSTS_MAX + 1) if i not in {p["id"] for p in ps}]
        if not free:
            self.st.setText(TR("4 SDR au plus."))
            return None
        ps.append(dict(id=free[0], name=f"SDR {free[0]}", model="", serial="", scenes=[]))
        self._save(ps)
        self.fill()
        return free[0]

    def remove(self):
        r = self.table.currentRow()
        ps, p = self._row_post(r)
        if p is None or p["id"] == 1:
            self.st.setText(TR("Le 1er SDR reste (il suffit de ne pas le démarrer)."))
            return
        self._save([x for x in ps if x["id"] != p["id"]])
        self.fill()

    def toggle(self):
        r = max(0, self.table.currentRow())
        _ps, p = self._row_post(r)
        e = self.owner.sdr_engs.get((p or {}).get("id"))
        if e is None:
            return
        if e.running():
            e.stop()
        else:
            if self.owner.rf_mode == "tiny":
                self.owner.set_rf_mode("sdr")
            e.start()
        self._states()

    def _states(self):
        for r in range(self.table.rowCount()):
            _ps, p = self._row_post(r)
            e = self.owner.sdr_engs.get((p or {}).get("id"))
            if e is None or self.table.item(r, 4) is None:
                continue
            txt = (TR("▶ en marche") if e.running() else TR("■ arrêté")) + (f" · {e.msg}" if e.msg and not e.running()
                                                                            else "")
            if self.table.item(r, 4).text() != txt:
                self.table.item(r, 4).setText(txt)


def write_atomic(path, text):
    """Étape 14 : écrit un fichier texte d'un coup (fichier « .part » puis renommé) : une coupure ne laisse jamais un
    fichier à moitié écrit sous le vrai nom."""
    tmp = str(path) + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def open_incident(owner, folder, parent=None):
    """9. Ouvre un dossier d'incident : rapport.html dans le navigateur, IQ rejoué dans la fenêtre Temps réel."""
    rep = os.path.join(folder, "rapport.html")
    if os.path.isfile(rep):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(rep))
    iq = os.path.join(folder, "iq.sigmf-meta")
    if os.path.isfile(iq):
        owner.open_realtime()
        rt = getattr(owner, "_rt", None)
        if rt is not None:
            rt.open_file(iq)
            try:                                       # 9. chronologie synchronisée avec la lecture
                with open(os.path.join(folder, "mesures.json"), encoding="utf-8") as f_:
                    doc = json.load(f_)
                rt.show_incident(doc, float((doc.get("iq") or {}).get("t0") or doc.get("t") or 0.0))
            except (OSError, ValueError, TypeError):
                pass
            return True
    elif parent is not None and hasattr(parent, "sel_lbl"):
        parent.sel_lbl.setText(TR("Pas d'IQ dans ce dossier : seul le rapport s'ouvre."))
    return False


class RealtimeWorker(QtCore.QThread):
    """V8 : mode temps réel. Source = l'outil d'IQ du SDR (direct) ou un fichier SigMF (relecture, au rythme réel,
    ×2, ×4, pause, déplacement). Tous les échantillons passent dans des FFT jointives (rt_frames) → spectre moyen
    + max de chaque bloc de 50 ms (rien n'échappe), détecteur de signaux brefs (BurstDetector), démodulation à la
    demande (`listen`), et enregistrement IQ brut (SigMF, signaux détectés en annotations) en direct."""
    frame = Signal(object)           # dict(F MHz, avg, mx, t, ovf, load, pos, dur, rec)
    events = Signal(object)          # [événement BurstDetector] (signaux disparus)
    stopped = Signal(str)
    status = Signal(str)
    DISPLAY = 4096

    def __init__(self, kind, center_hz, rate, nfft=4096, gains=None, serial="", tool=None, tool_dir="", src=None):
        super().__init__()
        self.kind, self.center, self.rate, self.nfft, self.serial = kind, float(center_hz), int(rate), int(nfft), serial
        self.gains = dict(lna=24, vga=20, amp=False)
        self.gains.update(gains or {})
        self.tool, self.tool_dir = tool, tool_dir
        self.src = src                   # relecture : dict(path, dtype, rate, center, t0, hw) ; None = direct
        self.dtype = src["dtype"] if src else SDR_DTYPE.get(kind, "cf32_le")      # étape 21 : « demo » = cf32
        if src:                          # relecture : le débit et le centre sont ceux du fichier
            self.rate, self.center = int(src["rate"]), float(src["center"])
        self.thr = -60.0                 # seuil du détecteur (dBFS)
        self.listen = None               # dict(f MHz, mode, compander, deemph, volume, dev, cut, audio) ou None
        self.listen_b = None             # V8 étape 16 (poste SDR) : 2ᵉ récepteur B, mêmes clés (+ sq : squelch dBFS)
        self.split = False               # A à gauche, B à droite (sinon mélangés)
        self.audio = deque(maxlen=200)
        self.a_raw = deque(maxlen=12)    # 8.1 : son de A tel qu'il sort du démodulateur (vu-mètre : sans volume ni B)
        self.a_pre = deque(maxlen=400)   # 8.2 : son de A démodulé BRUT (avant désaccentuation / expanseur) : Compander Lab
        self.lab_tap = False             # 8.2 : rempli seulement quand le Compander Lab regarde
        self.iq_grab = None              # 8.2 : capture d'IQ brut demandée par le labo (dict parts, n, want, done)
        self.prof = dict(fft=0.0, dem=0.0, rest=0.0)   # 8.1 : temps de calcul (ms par morceau de 50 ms) par étape
        self.fft_frac = 1.0              # 8.1 : part des échantillons mise dans le spectre (allégé si le PC ne suit pas)
        self.proc = None
        self.err = deque(maxlen=20)
        self.det = BurstDetector(gap=3)
        self.load = 0.0                  # part du temps passée à calculer (1 = le PC ne suit plus)
        self.load_cpu = 0.0              # 8.1 : la part VRAIMENT calculée par ce fil (le reste = attente du processeur)
        self.speed, self.playing, self.seek_to = 1, True, None      # relecture
        self.rec_req, self.rec = None, None                          # enregistrement : demande / en cours
        self.rec_max = 20e9              # octets ; et arrêt si moins de 2 Go libres

    # ------------------------------------------------------------ enregistrement (appelé depuis l'interface)
    def start_rec(self, base):
        """base = chemin sans extension : écrit base.sigmf-data (+ base.sigmf-meta à l'arrêt et toutes les 10 s)."""
        self.rec_req = ("start", str(base))

    def stop_rec(self):
        self.rec_req = ("stop", "")

    def _rec_open(self, base, t0):
        try:
            f = open(base + ".sigmf-data", "wb")
        except OSError as e:
            self.status.emit(f"⚠ Enregistrement impossible : {e}")
            return
        self.rec = dict(base=base, f=f, t0=t0, n=0, ann=[], t_meta=0.0)
        self._rec_meta()
        self.status.emit(f"⏺ Enregistrement IQ : {base}.sigmf-data")

    def _rec_meta(self):
        r = self.rec
        meta = sigmf_meta(self.dtype, self.rate, self.center, r["t0"], SDR_KINDS.get(self.kind, SDR_DEMO_KIND)["name"],
                          r["ann"])
        try:
            with open(r["base"] + ".sigmf-meta", "w", encoding="utf-8") as fm:
                json.dump(meta, fm, indent=1)
        except OSError:
            pass

    def _rec_close(self, why=""):
        r, self.rec = self.rec, None
        if r is None:
            return
        try:
            r["f"].close()
        except OSError:
            pass
        self.rec = r
        self._rec_meta()
        self.rec = None
        self.status.emit(f"⏹ Enregistrement arrêté{(' : ' + why) if why else ''} — {rec_size_text(r['n'])} dans "
                         f"{os.path.basename(r['base'])}.sigmf-data")

    # ------------------------------------------------------------ boucle
    def run(self):
        sp = SDR_KINDS.get(self.kind, SDR_DEMO_KIND)
        nb = IQ_BYTES[self.dtype]
        fh = None
        if self.src is not None:
            try:
                fh = open(self.src["path"], "rb")
            except OSError as e:
                self.stopped.emit(f"Fichier illisible : {e}")
                return
            total = os.path.getsize(self.src["path"]) // nb
            t_base = self.src.get("t0") or os.path.getmtime(self.src["path"])
            self.status.emit(f"📂 Relecture : {os.path.basename(self.src['path'])} · {self.center / 1e6:.3f} MHz · "
                             f"{self.rate / 1e6:g} MS/s · {total / self.rate:.0f} s")
            read = fh.read
        else:
            try:                                # étape 7 : outil (HackRF, RTL, SoapySDR) ou DLL WiNRADiO
                self.isrc = open_iq_source(self.kind, self.center, self.rate, self.gains, self.serial, self.tool,
                                           self.tool_dir, wr_lib=WINRADIO_LIB)
            except RuntimeError as e:
                self.stopped.emit(str(e))
                return
            self.rate, self.dtype, self.err = self.isrc.rate, self.isrc.dtype, self.isrc.err
            nb = IQ_BYTES[self.dtype]
            self.status.emit(f"⏱ {sp['name']} : temps réel {self.center / 1e6:.3f} MHz ± {0.4 * self.rate / 1e6:.1f} MHz")
            read = self.isrc.read
            total = 0
        Fb = rt_freqs(self.center, self.rate, self.nfft)
        sst = self.sstat = StreamStats(self.rate)
        n_s = int(self.rate * 0.05)
        chunk = n_s * nb
        buf, why, dem, dem_key = b"", "", None, None
        dem_b = dem_b_key = None
        lv_a = lv_b = None
        pos, t_play, t_disk = 0, time.time(), 0.0
        try:
            while not self.isInterruptionRequested():
                if fh is not None:                               # relecture : pause, déplacement, rythme
                    if self.seek_to is not None:
                        pos = max(0, min(total - 1, int(self.seek_to * self.rate)))
                        fh.seek(pos * nb)
                        self.seek_to, buf, dem_key = None, b"", None
                        self.det = BurstDetector(gap=3)
                        t_play = time.time()
                    if not self.playing:
                        self.msleep(50)
                        t_play = time.time()
                        continue
                elif self.rec_req is not None:                   # direct : enregistrement demandé / arrêté
                    req, self.rec_req = self.rec_req, None
                    if req[0] == "start" and self.rec is None:
                        self._rec_open(req[1], time.time())
                    elif req[0] == "stop":
                        self._rec_close()
                data = read(chunk - len(buf))
                if fh is None and data:                          # 8.2 : ce que le SDR livre vraiment
                    sst.feed(time.time() + float(getattr(self.isrc, "ts_off", 0.0) or 0.0), len(data) // nb)
                if not data:
                    if fh is not None:
                        why = ""
                        self.status.emit("📂 Fin de l'enregistrement.")
                    else:
                        time.sleep(0.1)
                        why = (self.err[-1] if self.err else "flux coupé") + f" — {sp['name']} débranché ou occupé ?"
                    break
                buf += data
                if len(buf) < chunk:
                    continue
                if self.rec is not None:
                    try:
                        self.rec["f"].write(buf)
                        self.rec["n"] += len(buf)
                    except OSError as e:
                        self._rec_close(f"erreur d'écriture ({e})")
                t_c = (t_base + pos / self.rate) if fh is not None else time.time()
                t_work = time.time()
                c_work = time.thread_time()
                iq, buf = iq_decode(self.dtype, buf), b""
                bad_ = ~np.isfinite(iq)                          # 8.2 : échantillons invalides (NaN / inf) comptés,
                if bad_.any():                                   # remplacés par 0 (ils casseraient FFT et son)
                    sst.invalid += int(np.count_nonzero(bad_))
                    iq = np.where(bad_, 0, iq).astype(iq.dtype)
                pos += len(iq)
                g_ = self.iq_grab
                if g_ is not None and not g_["done"]:            # 8.2 : labo, chaîne complète sur le vrai signal
                    g_["parts"].append(iq.copy())
                    g_["n"] += len(iq)
                    if g_["n"] >= g_["want"]:
                        g_["done"] = True
                        self.iq_grab = None
                t_s0 = time.perf_counter()
                if self.fft_frac < 1.0:          # 8.1 : PC à la peine -> spectre sur une partie du morceau, le son reste
                    avg, mx = rt_frames(iq[:max(self.nfft, int(len(iq) * self.fft_frac))], self.nfft)
                else:
                    avg, mx = rt_frames(iq, self.nfft)
                if avg is None:
                    continue
                done = self.det.feed(t_c, Fb, mx, self.thr)
                if done:
                    self.events.emit(done)
                    if self.rec is not None:
                        self.rec["ann"] += [sigmf_annot(ev, self.rec["t0"], self.rate) for ev in done
                                            if ev["t0"] >= self.rec["t0"]]
                t_s1 = time.perf_counter()
                L, LB = self.listen, self.listen_b
                lv_a = lv_b = a_same = None
                outs = []
                for slot, Lx in (("a", L), ("b", LB)):          # étape 16 : récepteurs A et B en même temps
                    if Lx is None or not (fh is None or self.speed == 1):
                        if slot == "a":
                            dem = dem_key = None
                        else:
                            dem_b = dem_b_key = None
                        continue
                    key = tuple(sorted((k_, v_) for k_, v_ in Lx.items() if k_ not in ("volume", "sq")))
                    if slot == "b" and key == dem_key and a_same is not None:    # 8.1 : B = A (même fréquence,
                        a_, lv_b = a_same                                         # mêmes réglages) : pas 2 calculs
                        if Lx.get("sq") is not None and lv_b is not None and lv_b < Lx["sq"]:
                            a_ = a_ * 0.0
                        if len(a_):
                            outs.append((slot, to_stereo(a_) * float(Lx.get("volume", 1.0))))
                        continue
                    cur, cur_key = (dem, dem_key) if slot == "a" else (dem_b, dem_b_key)
                    if key != cur_key:
                        cur = ChannelDemod(self.rate, Lx["f"] * 1e6 - self.center, Lx["mode"], Lx["deemph"], None,
                                           Lx["compander"], Lx.get("dev"), Lx.get("cut"), Lx.get("audio"))
                        cur_key = key
                    if slot == "a":
                        dem, dem_key = cur, cur_key
                    else:
                        dem_b, dem_b_key = cur, cur_key
                    a_, lv_ = cur.process(iq)
                    lv_ = None if lv_ is None else float(np.max(lv_) if np.ndim(lv_) else lv_)
                    if slot == "a":
                        lv_a, a_same = lv_, (a_, lv_)
                        if len(a_):
                            self.a_raw.append(np.asarray(a_[:, 0] if np.ndim(a_) == 2 else a_, dtype=np.float32))
                        pr_ = getattr(cur, "pre_raw", None)
                        if self.lab_tap and pr_ is not None:
                            self.a_pre.append((time.time(), pr_.copy()))
                        cur.pre_raw = None
                    else:
                        lv_b = lv_
                    if len(a_):
                        sq = Lx.get("sq")
                        if sq is not None and lv_ is not None and lv_ < sq:
                            a_ = a_ * 0.0                          # squelch fermé
                        outs.append((slot, to_stereo(a_) * float(Lx.get("volume", 1.0))))
                if outs:
                    n_ = min(len(x[1]) for x in outs)
                    if len(outs) == 2 and self.split:            # A à gauche, B à droite
                        mix = np.stack([outs[0][1][:n_].mean(axis=1), outs[1][1][:n_].mean(axis=1)], axis=1)
                    else:
                        mix = sum(x[1][:n_] for x in outs) / (1.0 if len(outs) == 1 else 1.6)
                    self.audio.append(audio_int16(mix, 1.0))
                t_s2 = time.perf_counter()
                ovf = float(np.mean(np.abs(iq.real) > 0.98))         # échantillons à pleine échelle : saturation
                self.load = 0.8 * self.load + 0.2 * (time.time() - t_work) / 0.05
                self.load_cpu = 0.8 * self.load_cpu + 0.2 * (time.thread_time() - c_work) / 0.05
                t_s3 = time.perf_counter()
                for k_, v_ in (("fft", t_s1 - t_s0), ("dem", t_s2 - t_s1), ("rest", t_s3 - t_s2)):
                    self.prof[k_] = 0.9 * self.prof[k_] + 0.1 * v_ * 1000.0
                if self.load > 0.9 and self.fft_frac > 0.25:
                    self.fft_frac /= 2.0
                elif self.load < 0.4 and self.fft_frac < 1.0:
                    self.fft_frac = min(1.0, self.fft_frac * 2.0)
                if self.rec is not None and time.time() - t_disk > 1.0:
                    t_disk = time.time()
                    try:
                        free = shutil.disk_usage(os.path.dirname(self.rec["base"]) or ".").free
                    except OSError:
                        free = 1e12
                    if free < 2e9 or self.rec["n"] >= self.rec_max:
                        self._rec_close("disque presque plein" if free < 2e9 else "taille maximale atteinte")
                    elif time.time() - self.rec["t_meta"] > 10:
                        self.rec["t_meta"] = time.time()
                        self._rec_meta()
                self.frame.emit(dict(F=decimate_max(Fb, self.DISPLAY) if len(Fb) > self.DISPLAY else Fb,
                                     avg=decimate_max(avg, self.DISPLAY), mx=decimate_max(mx, self.DISPLAY),
                                     t=t_c, ovf=ovf, load=self.load, load_cpu=self.load_cpu, pos=pos / self.rate,
                                     prof=dict(self.prof), fft_frac=self.fft_frac,
                                     dprof=dict(getattr(dem, "prof", None) or {}),
                                     dur=total / self.rate if fh is not None else 0.0,
                                     pilot=None if dem is None else dem.pilot, lv_a=lv_a, lv_b=lv_b,
                                     bb=None if dem is None or getattr(dem, "last_bb", None) is None
                                     else dem.last_bb.copy(), bb_fs=None if dem is None else dem.fs1,
                                     health=None if dem is None else dem.health,
                                     q=sst.view() if fh is None else None,
                                     rec=None if self.rec is None else (self.rec["n"], time.time() - self.rec["t0"])))
                if fh is not None:                               # au rythme réel (× vitesse)
                    t_play += 0.05 / max(1, self.speed)
                    dt = t_play - time.time()
                    if dt > 0:
                        time.sleep(dt)
                    elif dt < -1.0:
                        t_play = time.time()                     # le PC ne suit pas : on n'accumule pas de retard
        finally:
            self._rec_close()
            if fh is not None:
                fh.close()
            s_, self.isrc = getattr(self, "isrc", None), None
            if s_ is not None:
                s_.close()
        self.stopped.emit(why)

    def _read_err(self):
        try:
            for line in self.proc.stderr:
                t = line.decode(errors="ignore").strip()
                if t:
                    self.err.append(t)
        except Exception:  # noqa: BLE001
            pass


class RealtimeDialog(QtWidgets.QDialog):
    """V8 : ⏱ Temps réel — une fenêtre fixe vue SANS TROU par le SDR : spectre, max-hold, persistance, waterfall,
    journal des signaux qui apparaissent / disparaissent (avec leur durée), clic sur le spectre = écouter."""
    WF_ROWS = 200

    def __init__(self, owner, center_mhz=None):
        super().__init__(owner)
        self._aq = deque(maxlen=200)                      # 8.1 : file de la carte son (AudioPump)
        self.owner = owner
        self.setWindowTitle("⏱ Temps réel (SDR)")
        self.resize(1240, 800)
        th = owner.theme
        self.worker, self.audio, self.paused = None, None, []
        self.maxh, self.wf, self.pers = None, None, None
        self.n_ev = 0
        lay = QtWidgets.QVBoxLayout(self)
        R = owner._row
        self.dev_combo = QtWidgets.QComboBox()
        for k, sp in SDR_KINDS.items():
            self.dev_combo.addItem(f"📡 {sp['name']}", k)
        pk = parse_sdr_addr(owner.port_combo.currentData() or "") or parse_sdr_addr(owner.dev2.get("addr", ""))
        if pk:
            self.dev_combo.setCurrentIndex(max(0, self.dev_combo.findData(pk[0])))
        self.dev_combo.setToolTip("Le SDR utilisé (outil d'IQ : hackrf_transfer / rtl_sdr).")
        self.center_spin = QtWidgets.QDoubleSpinBox()
        self.center_spin.setDecimals(3)
        self.center_spin.setRange(1.0, 6000.0)
        self.center_spin.setSuffix(" MHz")
        self.center_spin.setValue(center_mhz or 600.0)
        self.center_spin.setToolTip("Centre de la fenêtre. Astuce : clic droit sur le spectre principal ou sur une "
                                    "fréquence de la liste.")
        self.rate_combo = QtWidgets.QComboBox()
        self.rate_combo.setToolTip("Largeur de la fenêtre vue en permanence. Plus large = plus de calcul : 19,2 MS/s "
                                   "demande un PC costaud\n(regarde la charge en bas : au-delà de 100 %, des "
                                   "échantillons sont perdus).")
        self.nfft_combo = QtWidgets.QComboBox()
        self.nfft_combo.setToolTip("Résolution (taille de FFT) : plus fin = sépare mieux deux porteuses proches, "
                                   "mais moins de mises à jour par seconde dans chaque FFT.")
        self.go_btn = QtWidgets.QPushButton("▶ Démarrer")
        self.go_btn.setToolTip("Lance / arrête le temps réel (le balayage de ce SDR est mis en pause).")
        self.go_btn.clicked.connect(lambda *_: self.toggle())
        lay.addLayout(R("SDR :", self.dev_combo, "Centre :", self.center_spin, "Largeur :", self.rate_combo,
                        "Résolution :", self.nfft_combo, None, self.go_btn))
        self.thr_spin = QtWidgets.QSpinBox()
        self.thr_spin.setRange(-120, 0)
        self.thr_spin.setValue(-60)
        self.thr_spin.setSuffix(" dBFS")
        self.thr_spin.setToolTip("Seuil du journal : tout signal qui passe au-dessus est noté (début, fin, durée, "
                                 "niveau max).\nLes niveaux d'un SDR sont relatifs (dBFS), pas des dBm.")
        self.thr_spin.valueChanged.connect(lambda v: self._thr(v))
        self.max_chk = QtWidgets.QCheckBox("Max-hold")
        self.max_chk.setChecked(True)
        self.max_chk.setToolTip("Garde le plus haut niveau vu à chaque fréquence depuis le début (ou « Effacer »).")
        clr = QtWidgets.QPushButton("Effacer")
        clr.setToolTip("Remet à zéro le max-hold, la persistance et le waterfall.")
        clr.clicked.connect(lambda *_: self.clear())
        self.pers_chk = QtWidgets.QCheckBox("Persistance")
        self.pers_chk.setChecked(True)
        self.pers_chk.setToolTip("Densité des signaux sur quelques secondes : un signal bref laisse une trace pâle.")
        self.known_chk = QtWidgets.QCheckBox("Journal : ignorer mes fréquences")
        self.known_chk.setChecked(True)
        self.known_chk.setToolTip("Ne note pas les signaux à moins de 100 kHz d'une fréquence de ta liste "
                                  "(tes propres émetteurs).")
        self.log_chk = QtWidgets.QCheckBox("Aussi dans le journal")
        self.log_chk.setToolTip("Note aussi chaque signal détecté dans le journal principal (et son export CSV).")
        lay.addLayout(R("Seuil du journal :", self.thr_spin, self.max_chk, self.pers_chk, clr, self.known_chk,
                        self.log_chk, None))
        # étape 8 : signal bref sur une « doit rester libre » = alarme ; IQ enregistré sur alarme
        self.burst_chk = QtWidgets.QCheckBox("⚡ Signal bref sur une fréquence « doit rester libre » = alarme")
        self.burst_chk.setChecked(True)
        self.burst_chk.setToolTip("Le temps réel voit des signaux de quelques millisecondes, que le balayage rate. Sur une\n"
                                  "fréquence « doit rester libre » de la fenêtre, il lève une alarme CONFLIT (signal bref),\n"
                                  "notée au journal, qui se termine seule après 1 minute.")
        self.autorec_chk = QtWidgets.QCheckBox("⏺ Sur alarme : enregistrer l'IQ 15 s")
        self.autorec_chk.setToolTip("Quand une alarme part sur une fréquence de la fenêtre, enregistre 15 s d'IQ (toute la\n"
                                    "fenêtre, pour réécouter et analyser après). Gros fichiers : décoché d'office.")
        self.autorec_chk.toggled.connect(lambda on: on and not self.owner.privacy_ok(self)
                                         and self.autorec_chk.setChecked(False))       # audit V8 : accord
        lay.addLayout(R(self.burst_chk, self.autorec_chk, None))
        self.plot = pg.PlotWidget()
        pi = self.plot.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "Fréquence", units="MHz")
        pi.setLabel("left", "Niveau", units="dBFS")
        pi.getAxis("bottom").enableAutoSIPrefix(False)
        pi.setYRange(-120, 0, padding=0)
        pi.setMouseEnabled(x=True, y=False)
        self.pers_img = pg.ImageItem()
        self.pers_img.setLookupTable(make_lut(th.get("wf", "Inferno")))
        self.pers_img.setOpacity(0.75)
        pi.addItem(self.pers_img)
        self.maxcurve = pi.plot(pen=pg.mkPen(th["maxhold"], width=1))
        self.curve = pi.plot(pen=pg.mkPen(th["curve"], width=1.4))
        self.thr_line = pg.InfiniteLine(pos=-60, angle=0, pen=pg.mkPen(th["thr"], width=1.2, style=Qt.PenStyle.DashLine))
        pi.addItem(self.thr_line)
        self.lis_line = pg.InfiniteLine(angle=90, pen=pg.mkPen("#22d3ee", width=2))
        self.lis_line.setVisible(False)
        pi.addItem(self.lis_line)
        self.marks = []
        self.plot.scene().sigMouseClicked.connect(self._click)
        self.plot.setToolTip("Clic sur une porteuse : l'écouter (FM / AM ci-dessous). Molette : zoom horizontal.")
        self.wfw = pg.PlotWidget()
        wi = self.wfw.getPlotItem()
        wi.hideAxis("left")
        wi.getAxis("bottom").enableAutoSIPrefix(False)
        wi.setXLink(pi)
        wi.setMouseEnabled(x=True, y=False)
        self.wf_img = pg.ImageItem()
        self.wf_img.setLookupTable(make_lut(th.get("wf", "Inferno")))
        wi.addItem(self.wf_img)
        self.wfw.setToolTip("Waterfall : le temps descend (≈ 20 lignes par seconde).")
        self.ev_table = QtWidgets.QTableWidget(0, 6)
        self.ev_table.setHorizontalHeaderLabels(["Heure", "MHz", "Max dBFS", "Durée", "Près de", "Type"])
        self.ev_table.verticalHeader().setVisible(False)
        self.ev_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ev_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.ev_table.horizontalHeader().setStretchLastSection(True)
        self.ev_table.setWordWrap(False)
        for c, w_ in enumerate((70, 80, 70, 70)):
            self.ev_table.setColumnWidth(c, w_)
        self.ev_table.setMinimumWidth(380)
        self.ev_table.setToolTip("Journal des signaux apparus puis disparus (les plus récents en haut).\n"
                                 "Double-clic : écouter cette fréquence.")
        self.ev_table.cellDoubleClicked.connect(lambda r, c: self._listen_row(r))
        sp_ = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        sp_.addWidget(self.plot)
        sp_.addWidget(self.wfw)
        sp_.setSizes([480, 220])
        h_ = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        h_.addWidget(sp_)
        h_.addWidget(self.ev_table)
        h_.setSizes([860, 380])
        lay.addWidget(h_, 1)
        self.dp = DemodPick(on_change=lambda: self._listen(self._lis_f) if hasattr(self, "_lis_f") else None)
        self.pre_combo, self.mode_combo, self.comp_combo, self.de_combo = self.dp.widgets()
        self.vol = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 200)
        self.vol.setValue(100)
        self.vol.setMaximumWidth(160)
        self.vol.setToolTip("Volume.")
        self.mute_btn = QtWidgets.QPushButton("🔇 Couper l'écoute")
        self.mute_btn.setToolTip("Arrête la démodulation (le temps réel continue).")
        self.mute_btn.clicked.connect(lambda *_: self._listen(None))
        self.lis_lbl = QtWidgets.QLabel("🎧 Clic sur le spectre pour écouter")
        self.lis_lbl.setMinimumWidth(230)
        self.vol.valueChanged.connect(lambda *_: self._listen(self._lis_f))
        lay.addLayout(R(self.lis_lbl, "Préréglage :", self.pre_combo, "Volume :", self.vol, self.mute_btn, None))
        self.ana_lbl = QtWidgets.QLabel("")              # étape 8 : « c'est quoi ce signal ? » + mesures
        self.ana_lbl.setWordWrap(True)
        self.ana_lbl.setToolTip("Analyse du signal écouté (ou cliqué) : type probable, largeur occupée (99 % de la\n"
                                "puissance), écart au bruit, tient-il dans un canal de 200 kHz. Repères calculés sur le\n"
                                "spectre : à confirmer à l'oreille.")
        lay.addWidget(self.ana_lbl)
        self._ana_f, self._t_ana, self._seen_al, self._t_al, self._auto_rec = None, 0.0, set(), 0.0, False
        lay.addLayout(R("Mode :", self.mode_combo, "Compander :", self.comp_combo, "Désaccentuation :", self.de_combo,
                        None))
        # enregistrement IQ / relecture
        self.rec_btn = QtWidgets.QPushButton("⏺ Enregistrer l'IQ")
        self.rec_btn.setToolTip("Enregistre TOUTE la fenêtre (IQ brut, format SigMF) pour la rejouer plus tard : réécouter "
                                "n'importe quel micro,\nretrouver un brouilleur… Attention à la place : ≈ 38 Mo/s à "
                                "19,2 MS/s, 19 Mo/s à 9,6 MS/s, 5 Mo/s à 2,4 MS/s.\nArrêt automatique sous 2 Go libres "
                                "ou à la taille maximale (Outils › 📡 Réglages SDR).")
        self.rec_btn.clicked.connect(lambda *_: self.toggle_rec())
        self.rec_lbl = QtWidgets.QLabel("")
        self.open_btn = QtWidgets.QPushButton("📂 Relire un enregistrement…")
        self.open_btn.setToolTip("Rejoue un enregistrement IQ (.sigmf-meta / .sigmf-data, aussi ceux d'autres logiciels "
                                 "en ci8 / cu8 / ci16 / cf32) :\nspectre, journal des signaux et écoute comme en direct, "
                                 "sans SDR branché.")
        self.open_btn.clicked.connect(lambda *_: self.open_file())
        dir_btn = QtWidgets.QPushButton("📁")
        dir_btn.setToolTip("Ouvre le dossier des enregistrements IQ.")
        dir_btn.clicked.connect(lambda *_: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self._rec_dir()))))
        lay.addLayout(R(self.rec_btn, self.rec_lbl, None, self.open_btn, dir_btn))
        self.play_bar = QtWidgets.QWidget()
        pb = QtWidgets.QHBoxLayout(self.play_bar)
        pb.setContentsMargins(0, 0, 0, 0)
        self.pause_btn = QtWidgets.QPushButton("⏸")
        self.pause_btn.setToolTip("Pause / lecture.")
        self.pause_btn.clicked.connect(lambda *_: self._pause())
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setToolTip("Position dans l'enregistrement : glisse pour t'y déplacer.")
        self.slider.sliderReleased.connect(lambda: self.worker is not None and
                                           setattr(self.worker, "seek_to", self.slider.value() / 10.0))
        self.pos_lbl = QtWidgets.QLabel("")
        self.pos_lbl.setMinimumWidth(200)
        self.speed_combo = QtWidgets.QComboBox()
        for t, v in (("×1", 1), ("×2 (sans son)", 2), ("×4 (sans son)", 4)):
            self.speed_combo.addItem(t, v)
        self.speed_combo.setToolTip("Vitesse de relecture (le son n'est rendu qu'en ×1).")
        self.speed_combo.currentIndexChanged.connect(lambda *_: self.worker is not None and
                                                     setattr(self.worker, "speed", self.speed_combo.currentData()))
        live = QtWidgets.QPushButton("⏹ Revenir au direct")
        live.setToolTip("Quitte la relecture.")
        live.clicked.connect(lambda *_: self.leave_file())
        for wd in (self.pause_btn, self.slider, self.pos_lbl, self.speed_combo, live):
            pb.addWidget(wd, 1 if wd is self.slider else 0)
        self.play_bar.setVisible(False)
        lay.addWidget(self.play_bar)
        self._src = None
        self.st_lbl = QtWidgets.QLabel("Pas encore testé avec un vrai SDR : dis-moi ce que ça donne !")
        self.st_lbl.setWordWrap(True)
        lay.addWidget(self.st_lbl)
        self._lis_f = None
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._feed)
        self.dev_combo.currentIndexChanged.connect(lambda *_: self._fill_rates())
        self._fill_rates()
        for n in RT_FFT:
            self.nfft_combo.addItem(str(n), n)
        self.nfft_combo.setCurrentIndex(RT_FFT.index(4096))
        self.nfft_combo.currentIndexChanged.connect(lambda *_: self._res_text())
        self.rate_combo.currentIndexChanged.connect(lambda *_: self._res_text())
        self._res_text()

    def _fill_rates(self):
        self.rate_combo.clear()
        k_ = self.dev_combo.currentData()
        m_ = self.owner.sdr_model_for(k_)           # étape 7 : débits et part utile du modèle choisi
        for r in sorted((m_ or {}).get("rates") or RT_RATES.get(k_, [2400000]), reverse=True):
            self.rate_combo.addItem(f"≈ {sdr_span_mhz(m_, r):.1f} MHz ({r / 1e6:g} MS/s)", r)
        if self.rate_combo.count() > 1:
            self.rate_combo.setCurrentIndex(1)                # 9,6 MS/s par défaut sur un HackRF

    def _res_text(self):
        r, n = self.rate_combo.currentData(), self.nfft_combo.currentData()
        if r and n:
            for i in range(self.nfft_combo.count()):
                k = self.nfft_combo.itemData(i)
                self.nfft_combo.setItemText(i, f"{r / k / 1e3:.1f} kHz")

    def _thr(self, v):
        self.thr_line.setValue(v)
        if self.worker is not None:
            self.worker.thr = float(v)

    def clear(self):
        self.maxh, self.wf, self.pers = None, None, None

    def _marks(self, lo, hi):
        pi = self.plot.getPlotItem()
        for m_ in self.marks:
            pi.removeItem(m_)
        self.marks = []
        for w in self.owner.watch:
            if lo <= w["freq"] <= hi:
                ln = pg.InfiniteLine(pos=w["freq"], angle=90, label=w["name"] or f"{w['freq']:.3f}",
                                     labelOpts=dict(position=0.95, color="#cbd5e1"),
                                     pen=pg.mkPen("#64748b", width=1, style=Qt.PenStyle.DotLine))
                pi.addItem(ln)
                self.marks.append(ln)

    def toggle(self):
        if self.worker is not None:
            self.stop()
            return
        o = self.owner
        kind = self.dev_combo.currentData()
        other = getattr(o, "_listen", None)
        if other is not None and other.worker is not None:
            self.st_lbl.setText("⚠ L'écoute 🎧 utilise déjà le SDR : arrête-la d'abord.")
            return
        rate, nfft = self.rate_combo.currentData(), self.nfft_combo.currentData()
        c = self.center_spin.value() * 1e6
        src = self._src
        if src is not None:
            rate, c = int(src["rate"]), float(src["center"])
            self.paused = []
        else:
            self.paused = [w for w in o.workers if w.isRunning() and w.sdr and parse_sdr_addr(w.port)[0] == kind]
        for w in self.paused:
            w.paused = True
        self.worker = RealtimeWorker(kind, c, rate, nfft, o.sdr_gains(kind), tool=getattr(o, "_listen_tool", None),
                                     tool_dir=o.sdr_cfg.get("dir", ""), src=src)
        self.worker.rec_max = float(o.sdr_cfg.get("rec_max_gb", 20)) * 1e9
        self.worker.speed = self.speed_combo.currentData()
        self.worker.thr = float(self.thr_spin.value())
        self.worker.frame.connect(self._frame)
        self.worker.events.connect(self._events)
        self.worker.status.connect(self.st_lbl.setText)
        self.worker.stopped.connect(self._stopped)
        self.clear()
        lo, hi = rt_useful(c, rate)
        self.plot.getPlotItem().setXRange(lo, hi, padding=0)
        self._marks(lo, hi)
        QtCore.QTimer.singleShot(300 if self.paused else 0, self.worker.start)
        self.timer.start(10)                             # 8.1 : son nourri plus souvent (moins de trous)
        self.go_btn.setText("■ Arrêter")
        for wd in (self.dev_combo, self.center_spin, self.rate_combo, self.nfft_combo, self.open_btn):
            wd.setEnabled(False)
        self.rec_btn.setEnabled(src is None)
        self.play_bar.setVisible(src is not None)
        self.pause_btn.setText("⏸")
        if self._lis_f is not None:
            self._listen(self._lis_f)

    def show_incident(self, doc, t0_file):
        """9. Relecture d'un incident : la chronologie du micro suit la lecture de l'IQ (ce qui se passe à l'instant
        lu est surligné) ; double-clic = aller à ce moment."""
        evs = [dict(e_) for e_ in doc.get("events") or []]
        tg = dict(doc.get("trigger") or {}, t=doc.get("t"))
        if tg.get("t") is not None and not any(abs(e_.get("t", 0) - tg["t"]) < 0.01 for e_ in evs):
            evs.append(tg)
        evs = sorted((e_ for e_ in evs if e_.get("t") is not None), key=lambda e_: e_["t"])
        self._inc = dict(doc=doc, t0=float(t0_file), evs=evs)
        if getattr(self, "inc_box", None) is None:
            self.inc_box = QtWidgets.QGroupBox("")
            ib = QtWidgets.QVBoxLayout(self.inc_box)
            self.inc_lbl = QtWidgets.QLabel("")
            self.inc_lbl.setWordWrap(True)
            self.inc_list = QtWidgets.QListWidget()
            self.inc_list.setMaximumHeight(110)
            self.inc_list.setToolTip("Ce qui est arrivé au micro, dans l'ordre. Double-clic = aller à ce moment dans l'IQ.")
            self.inc_list.itemDoubleClicked.connect(lambda it: self._inc_goto(self.inc_list.row(it)))
            ib.addWidget(self.inc_lbl)
            ib.addWidget(self.inc_list)
            self.layout().insertWidget(1, self.inc_box)
        self.inc_box.setTitle(TR("📦 Incident : {} · {} MHz").format(doc.get("name", ""), f"{float(doc.get('freq') or 0):.3f}"))
        self.inc_list.clear()
        for e_ in evs:
            self.inc_list.addItem(f"{datetime.fromtimestamp(e_['t']):%H:%M:%S} · {anomaly_text(e_, TR)}")
        self.inc_box.show()
        try:
            self._lis_f = float(doc.get("freq"))
        except (TypeError, ValueError):
            pass

    def _inc_goto(self, r):
        inc = getattr(self, "_inc", None)
        if inc and 0 <= r < len(inc["evs"]) and self.worker is not None:
            self.worker.seek_to = max(0.0, inc["evs"][r]["t"] - inc["t0"] - 2.0)    # 2 s avant, pour voir arriver

    def _inc_sync(self, t):
        inc = self._inc
        past = [i for i, e_ in enumerate(inc["evs"]) if e_["t"] <= t]
        nxt = next((e_ for e_ in inc["evs"] if e_["t"] > t), None)
        i = past[-1] if past else -1
        if self.inc_list.currentRow() != i and i >= 0:
            self.inc_list.setCurrentRow(i)
        txt = f"▶ {datetime.fromtimestamp(t):%H:%M:%S}"
        if i >= 0:
            txt += " · " + TR("il y a {} s : {}").format(f"{t - inc['evs'][i]['t']:.0f}", anomaly_text(inc["evs"][i], TR))
        if nxt:
            txt += " · " + TR("dans {} s : {}").format(f"{nxt['t'] - t:.0f}", anomaly_text(nxt, TR))
        self.inc_lbl.setText(txt)

    def _frame(self, fr):
        F, avg, mx = fr["F"], fr["avg"], fr["mx"]
        self.last = fr
        now_ = time.time()
        tgt = getattr(self, "_lis_f", None) or self._ana_f
        if tgt is not None and now_ - self._t_ana >= 1.0 and len(F) == len(avg):
            self._t_ana = now_                      # étape 8 : type + mesures du signal visé
            c_ = classify_signal(F, avg, tgt, fr.get("pilot"))
            self.ana_lbl.setText(f"🔎 {tgt:.3f} MHz : " + signal_report(c_, TR))
            self.ana_lbl.setToolTip(TR(c_["why"]))
            self.last_class = (tgt, c_)
        if now_ - self._t_al >= 0.5 and len(F):
            self._t_al = now_
            self._alarm_check(float(np.min(F)), float(np.max(F)))
        if not fr.get("dur") and now_ - getattr(self, "_t_feed", 0.0) >= 0.5 and len(F) == len(avg):
            self._t_feed = now_                     # étape 7 : la fenêtre du temps réel surveille aussi
            self.owner.sdr_listen_feed(self.dev_combo.currentData(), F, avg)
        if len(F) != len(avg):
            F = np.linspace(F[0], F[-1], len(avg))
        self.curve.setData(F, avg)
        if self.maxh is None or len(self.maxh) != len(mx):
            self.maxh = mx.copy()
        else:
            np.maximum(self.maxh, mx, out=self.maxh)
        self.maxcurve.setData(F, self.maxh) if self.max_chk.isChecked() else self.maxcurve.setData([], [])
        if self.pers is None or self.pers.nx != len(mx):
            self.pers = Persist(len(mx), -120.0, 0.0, 120, 0.97)
        img = self.pers.add(mx)
        if self.pers_chk.isChecked():
            self.pers_img.setImage(img, autoLevels=False, levels=(0.0, 6.0))
            self.pers_img.setRect(QtCore.QRectF(float(F[0]), -120.0, float(F[-1] - F[0]), 120.0))
            self.pers_img.setVisible(True)
        else:
            self.pers_img.setVisible(False)
        if self.wf is None or self.wf.shape[0] != len(mx):
            self.wf = np.full((len(mx), self.WF_ROWS), -120.0, dtype=np.float32)
        self.wf = np.roll(self.wf, 1, axis=1)
        self.wf[:, 0] = mx
        self.wf_img.setImage(self.wf, autoLevels=False, levels=(float(np.median(avg)) - 5, float(np.median(avg)) + 50))
        self.wf_img.setRect(QtCore.QRectF(float(F[0]), 0.0, float(F[-1] - F[0]), float(self.WF_ROWS)))
        if self._lis_f is not None:
            k = self._known(self._lis_f)
            pil = fr.get("pilot")
            self.lis_lbl.setText(f"🎧 {self._lis_f:.3f} MHz" + (f" ({k['name']})" if k else "")
                                 + (f" · pilote {pil[0] / 1000:.1f} kHz" if pil else ""))
        rec = fr.get("rec")
        if rec is not None:
            self.rec_lbl.setText(f"⏺ {int(rec[1]) // 60:02d}:{int(rec[1]) % 60:02d} · {rec_size_text(rec[0])}")
            self.rec_btn.setText("⏹ Arrêter l'enregistrement")
        elif self.rec_btn.text().startswith("⏹"):
            self.rec_btn.setText("⏺ Enregistrer l'IQ")
        if fr.get("dur"):
            if not self.slider.isSliderDown():
                self.slider.blockSignals(True)
                self.slider.setRange(0, int(fr["dur"] * 10))
                self.slider.setValue(int(fr["pos"] * 10))
                self.slider.blockSignals(False)
            self.pos_lbl.setText(f"{datetime.fromtimestamp(fr['t']):%H:%M:%S} · {fr['pos']:.0f} / {fr['dur']:.0f} s")
            if getattr(self, "_inc", None):
                self._inc_sync(float(fr["t"]))
        warn = []
        if fr.get("ovf", 0) > 0.001:
            warn.append("⚠ SATURATION : baisse le gain (Outils › 📡) ou retire l'ampli")
        if fr.get("load", 0) > 1.0:
            warn.append(f"⚠ le PC ne suit pas ({fr['load'] * 100:.0f} %) : réduis la largeur")
        self.st_lbl.setText(" · ".join(warn) if warn else f"Temps réel · charge {fr.get('load', 0) * 100:.0f} % · "
                            f"crête {float(mx.max()):.0f} dBFS")

    def _rec_dir(self):
        d = Path(self.owner.log_dir) / "enregistrements_iq" / datetime.now().strftime("%Y-%m-%d")
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return d

    def toggle_rec(self):
        w = self.worker
        if w is None or self._src is not None:
            self.st_lbl.setText("Lance d'abord le temps réel en direct (▶ Démarrer), puis ⏺ Enregistrer.")
            return
        if w.rec is not None or self.rec_btn.text().startswith("⏹"):
            w.stop_rec()
            self.rec_btn.setText("⏺ Enregistrer l'IQ")
            self.rec_lbl.setText("")
            return
        if not self.owner.privacy_ok(self):            # audit V8 : l'IQ contient le son, accord comme partout ailleurs
            return
        base = self._rec_dir() / f"iq_{datetime.now():%H%M%S}_{w.center / 1e6:.3f}MHz"
        w.start_rec(str(base))
        self.rec_btn.setText("⏹ Arrêter l'enregistrement")
        self.rec_lbl.setText(f"⏺ … ({w.rate * IQ_BYTES[w.dtype] / 1e6:.0f} Mo/s)")

    def open_file(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Relire un enregistrement IQ", str(self._rec_dir().parent),
                                                            "Enregistrement SigMF (*.sigmf-meta *.sigmf-data)")
        if not path:
            return
        base = re.sub(r"\.sigmf-(meta|data)(\.part)?$", "", path)
        try:
            if os.path.isfile(base + ".sigmf-data.part") and not os.path.isfile(base + ".sigmf-data"):
                raise ValueError(TR("enregistrement interrompu pendant l'écriture (fichier .part) : IQ incomplet"))
            with open(base + ".sigmf-meta", encoding="utf-8") as fm:
                info = sigmf_info(json.load(fm))
            if not os.path.isfile(base + ".sigmf-data"):
                raise ValueError("fichier .sigmf-data introuvable à côté")
            if os.path.getsize(base + ".sigmf-data") < IQ_BYTES[info["dtype"]] * info["rate"] * 0.05:
                raise ValueError(TR("fichier IQ vide ou presque (moins de 0,05 s)"))
        except (OSError, ValueError, json.JSONDecodeError) as e:
            self.st_lbl.setText(f"⚠ Enregistrement illisible : {e}")
            return
        self.stop()
        self._inc = None                              # 9. un autre fichier : plus la chronologie d'un incident
        if getattr(self, "inc_box", None) is not None:
            self.inc_box.hide()
        info["path"] = base + ".sigmf-data"
        self._src = info
        self.rec_lbl.setText("")
        dur = os.path.getsize(info["path"]) / IQ_BYTES[info["dtype"]] / info["rate"]
        t0_ = info.get("t0") or os.path.getmtime(info["path"])
        self.pos_lbl.setText(f"{datetime.fromtimestamp(t0_):%d/%m %H:%M:%S} · 0 / {dur:.0f} s")
        self.slider.setRange(0, int(dur * 10))
        self.slider.setValue(0)
        self.center_spin.setValue(info["center"] / 1e6)
        self.clear()
        self.ev_table.setRowCount(0)
        self.toggle()

    def leave_file(self):
        self._src = None
        self.stop()
        self.play_bar.setVisible(False)

    def _pause(self):
        w = self.worker
        if w is not None:
            w.playing = not w.playing
            self.pause_btn.setText("⏸" if w.playing else "▶")

    def _known(self, f):
        w = min(self.owner.watch, key=lambda w: abs(w["freq"] - f), default=None)
        return w if w is not None and abs(w["freq"] - f) <= 0.1 else None

    def _alarm_check(self, lo, hi):
        """Étape 8 : nouvelle alarme dans la fenêtre -> 15 s d'IQ enregistrées (si coché)."""
        new = alarms_in_window(list(self.owner.alarms.active.values()), lo, hi, self._seen_al)
        for a in new:
            self._seen_al.add(a.get("key"))
        if not new or not self.autorec_chk.isChecked() or self.worker is None or self._src is not None \
                or self.worker.rec is not None or self._auto_rec:
            return
        self._auto_rec = True
        self.toggle_rec()
        a = new[0]
        self.owner.log_event(dict(name=a.get("name", ""), freq=float(a.get("freq") or 0.0),
                                  note=TR("IQ enregistré 15 s (temps réel)")), 0.0, "ENREGISTRÉ (alarme)")

        def _stop_auto():
            if self._auto_rec and self.worker is not None and self.worker.rec is not None:
                self.toggle_rec()
            self._auto_rec = False
        QtCore.QTimer.singleShot(15000, _stop_auto)

    def _events(self, evs):
        fr_ = getattr(self, "last", None)
        for ev in evs:
            k = self._known(ev["f"])
            if k is not None and self.burst_chk.isChecked() and self._src is None:
                self.owner.sdr_burst_conflict(self.dev_combo.currentData(), k, ev)   # étape 8
            if k is not None and self.known_chk.isChecked():
                continue
            self.n_ev += 1
            self.ev_table.insertRow(0)
            dur = ev["t1"] - ev["t0"]
            c_ = classify_signal(fr_["F"], fr_["mx"], ev["f"]) if fr_ is not None and len(fr_["F"]) == len(fr_["mx"]) \
                else None
            vals = [datetime.fromtimestamp(ev["t0"]).strftime("%H:%M:%S"), f"{ev['f']:.3f}", f"{ev['peak']:.0f}",
                    f"{dur:.1f} s" if dur >= 0.1 else "< 0,1 s", (k["name"] if k else "—"),
                    TR(c_["name"]) if c_ else ""]
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c == 1:
                    it.setData(Qt.ItemDataRole.UserRole, ev["f"])
                self.ev_table.setItem(0, c, it)
            if self.ev_table.rowCount() > 500:
                self.ev_table.removeRow(self.ev_table.rowCount() - 1)
            if self.log_chk.isChecked():
                self.owner.log_event(dict(name="Temps réel", freq=0.0,
                                          note=f"signal {ev['f']:.3f} MHz, {ev['peak']:.0f} dBFS, {dur:.1f} s"),
                                     0.0, "SIGNAL (TEMPS RÉEL)")

    def _listen_row(self, r):
        it = self.ev_table.item(r, 1)
        if it is not None:
            self._listen(float(it.data(Qt.ItemDataRole.UserRole)))

    def _click(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        pt = self.plot.getPlotItem().vb.mapSceneToView(ev.scenePos())
        if not self.plot.sceneBoundingRect().contains(ev.scenePos()):
            return
        f = float(pt.x())
        fr = getattr(self, "last", None)
        if fr is not None:                                    # accroche le pic le plus proche (± 100 kHz)
            F, mx = np.asarray(fr["F"]), np.asarray(fr["mx"])
            if len(F) == len(mx):
                m = np.abs(F - f) <= 0.1
                if m.any():
                    f = float(F[m][int(np.argmax(mx[m]))])
        self._listen(round(f, 4))

    def _listen(self, f):
        self._lis_f = f
        if f is None:
            self.lis_line.setVisible(False)
            self.lis_lbl.setText("🎧 Clic sur le spectre pour écouter")
            if self.worker is not None:
                self.worker.listen = None
            if self.audio is not None:
                self.audio.close()
                self.audio = None
            return
        self.lis_line.setValue(f)
        self.lis_line.setVisible(True)
        k = self._known(f)
        self.lis_lbl.setText(f"🎧 {f:.3f} MHz" + (f" ({k['name']})" if k else ""))
        if self.worker is not None:
            self.worker.listen = dict(f=f, volume=self.vol.value() / 100.0, **self.dp.params())
            if self.audio is None:
                self.audio = AudioPump(self._aq, sdr_audio_device(self.owner))        # 8.1 : son nourri par son propre fil
                self.audio.start()

    def _feed(self):
        if self.worker is not None and self.audio is not None:
            pump_move(self.worker.audio, self._aq)

    def _stopped(self, why):
        if why:
            self.st_lbl.setText(f"⚠ Temps réel arrêté : {why}")
        self.stop()

    def stop(self):
        self.timer.stop()
        w, self.worker = self.worker, None
        if w is not None:
            w.requestInterruption()
            w.wait(5000)
        if self.audio is not None:
            self.audio.close()
            self.audio = None
        for w in self.paused:
            w.paused = False
        self.paused = []
        self.owner.sdr_listen_clear()
        self.go_btn.setText("▶ Démarrer" if self._src is None else "▶ Relire")
        for wd in (self.dev_combo, self.center_spin, self.rate_combo, self.nfft_combo, self.open_btn):
            wd.setEnabled(self._src is None or wd is self.open_btn)
        self.rec_btn.setText("⏺ Enregistrer l'IQ")
        self.rec_btn.setEnabled(self._src is None)              # pas d'enregistrement d'une relecture

    def closeEvent(self, ev):
        self.stop()
        super().closeEvent(ev)
