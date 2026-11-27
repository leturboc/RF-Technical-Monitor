# Carte du site et carte de chaleur.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


class MapNode(QtWidgets.QGraphicsObject):
    """🗺 Une carte de la vue Carte : une scène (état de ses micros) ou un tinySA (en ligne / perdu). Glissable,
    aimantée à la grille ; déposer un tinySA sur une scène = la lui rattacher."""

    def __init__(self, owner, key):
        super().__init__()
        self.owner, self.key = owner, key
        self.kind, self.name = key.split(":", 1)
        self.w, self.h = (260.0, 100.0) if self.kind == "scene" else (230.0, 84.0)
        self.title, self.sub, self.col, self.stripe = self.name, "", "#888888", "#888888"
        self.pill, self.dots, self.extra = "", [], ""  # pastille d'état, un point par micro, ligne du bas
        sh = QtWidgets.QGraphicsDropShadowEffect()
        sh.setBlurRadius(18)
        sh.setOffset(0, 3)
        sh.setColor(QtGui.QColor(0, 0, 0, 110))
        self.setGraphicsEffect(sh)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setZValue(10)
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        return QtCore.QRectF(-8, -8, self.w + 16, self.h + 16)

    def center(self):
        return self.pos() + QtCore.QPointF(self.w / 2, self.h / 2)

    def port(self, top):
        """Point d'accroche des liens : haut (scène) ou bas (tinySA) de la tuile."""
        return self.pos() + QtCore.QPointF(self.w / 2, 0.0 if top else self.h)

    def paint(self, p, opt, widget=None):
        th = self.owner.theme
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing, True)
        r = QtCore.QRectF(0, 0, self.w, self.h)
        sel = self.isSelected()
        card = blend(th["ui_text"], th["ui_base"], 0.05)
        edge = th["ui_accent"] if sel else blend(self.col, card, 0.55)
        p.setPen(QtGui.QPen(QtGui.QColor(edge), 2.5 if sel else 1.2))
        p.setBrush(QtGui.QColor(card))
        p.drawRoundedRect(r, 12, 12)
        p.setPen(Qt.PenStyle.NoPen)                    # bande de couleur de la scène / du tinySA
        p.setBrush(QtGui.QColor(self.stripe))
        path = QtGui.QPainterPath()
        path.addRoundedRect(QtCore.QRectF(0, 0, 14, self.h), 12, 12)
        clip = QtGui.QPainterPath()
        clip.addRect(QtCore.QRectF(0, 0, 6, self.h))
        p.drawPath(path.intersected(clip))
        base = QtGui.QFont(p.font())
        fp = QtGui.QFont(base)                         # pastille d'état (en haut à droite)
        fp.setBold(True)
        fp.setPointSizeF(8.0)
        fmp = QtGui.QFontMetrics(fp)
        pw = fmp.horizontalAdvance(self.pill) + 24
        pr = QtCore.QRectF(self.w - pw - 10, 10, pw, 20)
        p.setBrush(QtGui.QColor(blend(self.col, card, 0.22)))
        p.setPen(QtGui.QPen(QtGui.QColor(self.col), 1.0))
        p.drawRoundedRect(pr, 10, 10)
        p.setBrush(QtGui.QColor(self.col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QtCore.QPointF(pr.left() + 9, pr.center().y()), 3.2, 3.2)
        p.setFont(fp)
        p.setPen(QtGui.QColor(self.col))
        p.drawText(pr.adjusted(18, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, self.pill)
        ft = QtGui.QFont(base)                         # titre
        ft.setBold(True)
        ft.setPointSizeF(12.5)
        p.setFont(ft)
        p.setPen(QtGui.QColor(th["ui_text"]))
        tw = int(self.w - pw - 34)
        p.drawText(QtCore.QRectF(18, 8, tw, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QtGui.QFontMetrics(ft).elidedText(self.title, Qt.TextElideMode.ElideRight, tw))
        fs = QtGui.QFont(base)                         # sous-titre (texte secondaire)
        fs.setPointSizeF(9.5)
        p.setFont(fs)
        p.setPen(QtGui.QColor(blend(th["ui_text"], card, 0.62)))
        p.drawText(QtCore.QRectF(18, 36, self.w - 30, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QtGui.QFontMetrics(fs).elidedText(self.sub, Qt.TextElideMode.ElideRight, int(self.w - 30)))
        if self.kind == "scene":                       # un point par micro, à sa couleur d'état
            x, y = 22.0, self.h - 22.0
            for c in self.dots[:20]:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QtGui.QColor(c))
                p.drawEllipse(QtCore.QPointF(x, y), 5.0, 5.0)
                x += 13.0
            if len(self.dots) > 20:
                p.setPen(QtGui.QColor(blend(th["ui_text"], card, 0.62)))
                p.drawText(QtCore.QRectF(x - 4, y - 9, 40, 18), Qt.AlignmentFlag.AlignVCenter, f"+{len(self.dots) - 20}")
            if not self.dots:
                p.setPen(QtGui.QColor(blend(th["ui_text"], card, 0.45)))
                p.drawText(QtCore.QRectF(18, self.h - 32, self.w - 30, 20), Qt.AlignmentFlag.AlignVCenter,
                           TR("aucun micro dans cette scène"))
        else:
            p.setPen(QtGui.QColor(blend(th["ui_text"], card, 0.62)))
            p.drawText(QtCore.QRectF(18, self.h - 30, self.w - 30, 20), Qt.AlignmentFlag.AlignVCenter,
                       QtGui.QFontMetrics(fs).elidedText(self.extra, Qt.TextElideMode.ElideRight, int(self.w - 30)))


    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() is not None:
            self.scene().update_links()
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        sc = self.scene()
        if sc is not None:
            sc.node_dropped(self)

    def mouseDoubleClickEvent(self, e):
        sc = self.scene()
        if sc is not None:
            sc.node_open(self)


class MapScene(QtWidgets.QGraphicsScene):
    """🗺 7.64 : la carte du site (façon canevas réseau) : grille, scènes et tinySA en cartes glissables, liens tinySA →
    scènes surveillées, plan du site en fond (facultatif), points de la carte de chaleur. Modèle = owner.map_cfg."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.nodes, self.links, self.heat_items, self.hot_item = {}, [], [], None
        self.arrow_info = None
        self.bg_item = None
        self.heat_f = None                    # fréquence affichée en chaleur (None = toutes)
        self.show_heat = True
        self.setSceneRect(-2000, -2000, 6000, 4000)

    # --- contenu
    def _keys_all_base(self):
        o = self.owner
        return [map_key("scene", sc["name"]) for sc in o.scenes] + [map_key("dev", d) for d in o.dev_list()]

    def keys_all(self):
        if rf_mode_norm(getattr(self.owner, "rf_mode", "tiny")) == "tiny":      # mode tinySA seul : pas de SDR sur la carte
            return self._keys_all_base()
        return self._keys_all_base() + [map_key("sdr", p["id"]) for p in sdr_posts_norm(self.owner.sdr_cfg.get("posts"))]

    def _label_base(self, key):
        kind, name = key.split(":", 1)
        o = self.owner
        return name if kind == "scene" else f"{dev_ord(int(name))} tinySA · {o.dev_name(int(name))}"

    def label(self, key):
        kind, name = key.split(":", 1)
        if kind != "sdr":
            return self._label_base(key)
        e = (getattr(self.owner, "sdr_engs", None) or {}).get(int(name))
        return f"📡 {e.name() if e else 'SDR ' + name}"

    def sync(self):
        """Ajoute / retire les cartes selon les scènes / tinySA et les positions enregistrées."""
        o = self.owner
        pos = o.map_cfg["pos"]
        want = [k for k in self.keys_all() if k in pos]
        for k in list(self.nodes):
            if k not in want:
                self.removeItem(self.nodes.pop(k))
        for k in want:
            n = self.nodes.get(k)
            if n is None:
                n = MapNode(o, k)
                self.nodes[k] = n
                self.addItem(n)
            n.setPos(QtCore.QPointF(*pos[k]))
        self.sync_bg()
        self.refresh()
        self.sync_heat()

    def unplaced(self):
        pos = self.owner.map_cfg["pos"]
        return [k for k in self.keys_all() if k not in pos]

    def place(self, key, x, y):
        self.owner.map_cfg["pos"][key] = map_snap(x, y)
        self.sync()

    def auto_place(self):
        cfg = self.owner.map_cfg
        cfg["pos"].update(map_auto_place(self.keys_all(), cfg["pos"]))
        self.sync()

    def remove(self, key):
        self.owner.map_cfg["pos"].pop(key, None)
        self.sync()

    # --- état en direct
    def _scene_state_base(self, name):
        o = self.owner
        ws = [w for w in o.watch if w.get("scene") == name and not w.get("off")]
        tones = [o.sig_view(w)[1] for w in ws]
        al = sum(1 for a in o.alarms.active.values() if any(abs((a.get("freq") or -1) - w["freq"]) < 0.0015 for w in ws))
        if not o.is_running():
            tone = "none"
        elif al or "bad" in tones:
            tone = "bad"
        elif "warn" in tones:
            tone = "warn"
        else:
            tone = "ok"
        sub = TR("{} micro(s)").format(len(ws))
        pill = (TR("Arrêté") if not o.is_running() else TR("{} alarme(s)").format(al) if al
                else TR("À surveiller") if tone in ("bad", "warn") else TR("OK"))
        dots = [o.tone_color(t) if o.is_running() else o.theme["st_none"] for t in tones]
        # 7.65 (audit) : état de la SURVEILLANCE de la scène, séparé de l'état RF de ses micros : un vieil état vert ne
        # doit jamais passer pour une surveillance qui marche (tinySA perdus, mesures périmées)
        mon = map_scene_monitor(o.is_running(), self.scene_devs(name), [w.get("state") for w in ws])
        if mon == "lost":
            tone, pill = "warn", TR("Surveillance perdue")
            dots = [o.theme["st_none"]] * len(tones)
        elif mon == "nodata":
            tone, pill = "warn", TR("Pas de mesure")
            dots = [o.theme["st_none"]] * len(tones)
        elif mon == "partial":
            n_ = sum(1 for w in ws if w.get("state") is None)
            sub = TR("{} micro(s)").format(len(ws)) + " · " + TR("{} sans mesure").format(n_)
            if tone == "ok":
                tone, pill = "warn", TR("Mesure partielle")
            dots = [o.theme["st_none"] if w.get("state") is None else c_ for w, c_ in zip(ws, dots)]
        return tone, sub, pill, dots

    def scene_state(self, name):
        """Une scène surveillée par un SDR en marche n'est pas « Arrêtée », même si les tinySA ne tournent pas."""
        o = self.owner
        live = [e for e in (getattr(o, "sdr_engs", None) or {}).values()
                if _v8_post_live(e) and (not e.post()["scenes"] or name in e.post()["scenes"])]
        if o.is_running() or not live:
            return self._scene_state_base(name)
        ws = [w for w in o.watch if w.get("scene") == name and not w.get("off")]
        tones = [o.sig_view(w)[1] for w in ws]
        al = sum(1 for a in o.alarms.active.values() if any(abs((a.get("freq") or -1) - w["freq"]) < 0.0015 for w in ws))
        tone = "bad" if (al or "bad" in tones) else ("warn" if "warn" in tones else "ok")
        pill = (TR("{} alarme(s)").format(al) if al else TR("À surveiller") if tone in ("bad", "warn") else TR("OK"))
        sub = TR("{} micro(s)").format(len(ws)) + " · 📡 " + ", ".join(e.name() for e in live)
        return tone, sub, pill, [o.tone_color(t) for t in tones]

    def scene_devs(self, name):
        """[(n° du tinySA, en ligne ?)] qui surveillent cette scène : ceux qui lui sont rattachés, sinon tous."""
        o = self.owner
        devs = o.dev_list()
        att = [d for d in devs if name in o.dev_scenes.get(d, [])]
        return [(d, d < len(o.dev_live) and bool(o.dev_live[d])) for d in (att or devs)]

    def _refresh_base(self):
        o = self.owner
        th = o.theme
        for k, n in self.nodes.items():
            if n.kind == "scene":
                tone, sub, n.pill, n.dots = self.scene_state(n.name)
                sc = o.scene_by_name(n.name)
                n.col, n.sub = o.tone_color(tone), sub
                n.stripe = sc["color"] if sc else th["st_none"]
                n.title = n.name
            else:
                d = int(n.name)
                live = o.is_running() and d < len(o.dev_live) and bool(o.dev_live[d])
                n.title = o.dev_name(d)
                n.col = th["st_free"] if live else (th["st_occ"] if o.is_running() else th["st_none"])
                scs = o.dev_scenes.get(d, [])
                n.pill = TR("En ligne") if live else (TR("Perdu") if o.is_running() else TR("Arrêté"))
                cyc = o.dev_cycle.get(d) if live else None
                n.sub = f"{dev_ord(d)} tinySA" + (f" · {TR('tour de')} {cyc:.1f} s" if cyc and cyc >= 0.1 else "")
                n.extra = TR("Surveille : {}").format(", ".join(scs) if scs else TR("tout le site"))
                n.stripe = th["ui_accent"]
            n.update()
        self.update_links()

    def refresh(self):
        self._refresh_base()
        o, th = self.owner, self.owner.theme
        for k, n in self.nodes.items():
            if n.kind != "sdr":
                continue
            e = (getattr(o, "sdr_engs", None) or {}).get(int(n.name))
            live = _v8_post_live(e)
            n.title = f"📡 {e.name()}" if e else n.name
            n.col = th["st_free"] if live else (th["st_occ"] if e is not None and e.running() else th["st_none"])
            n.pill = TR("En ligne") if live else (TR("Pas de flux") if e is not None and e.running() else TR("Arrêté"))
            m = e.model() if e else None
            n.sub = (m["name"] if m else "SDR") + (f" · A {e.a:.3f}" if e is not None and e.a is not None else "")
            scs = e.post()["scenes"] if e else []
            n.extra = TR("Surveille : {}").format(", ".join(scs) if scs else TR("tout le site"))
            n.stripe = "#64d2ff"
            n.update()
        self._sdr_links()

    def _update_links_base(self):
        for it in self.links:
            self.removeItem(it)
        self.links = []
        o = self.owner
        for d in o.dev_list():
            a = self.nodes.get(map_key("dev", d))
            if a is None:
                continue
            live = o.is_running() and d < len(o.dev_live) and bool(o.dev_live[d])
            for scn in o.dev_scenes.get(d, []):
                b = self.nodes.get(map_key("scene", scn))
                if b is None:
                    continue
                pa = a.port(False) if b.pos().y() >= a.pos().y() + a.h else a.port(True)
                pb = b.port(True) if b.pos().y() >= a.pos().y() + a.h else b.port(False)
                path = QtGui.QPainterPath(pa)
                dy = max(40.0, abs(pb.y() - pa.y()) / 2) * (1 if pb.y() >= pa.y() else -1)
                path.cubicTo(QtCore.QPointF(pa.x(), pa.y() + dy), QtCore.QPointF(pb.x(), pb.y() - dy), pb)
                pen = QtGui.QPen(QtGui.QColor(o.theme["ui_accent"]), 2.6)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                if not live:
                    pen.setStyle(Qt.PenStyle.DashLine)
                it = self.addPath(path, pen)
                it.setZValue(5)
                self.links.append(it)
                for q in (pa, pb):                     # points d'accroche
                    dot = self.addEllipse(QtCore.QRectF(q.x() - 5, q.y() - 5, 10, 10),
                                          QtGui.QPen(QtGui.QColor(o.theme["ui_bg"]), 2.0),
                                          QtGui.QBrush(QtGui.QColor(o.theme["ui_accent"])))
                    dot.setZValue(12)
                    self.links.append(dot)

    def update_links(self):
        self._update_links_base()
        self._sdr_links()

    # --- plan de fond (facultatif)
    def sync_bg(self):
        cfg = self.owner.map_cfg
        if self.bg_item is not None:
            self.removeItem(self.bg_item)
            self.bg_item = None
        if not cfg["bg"]:
            return
        pm = QtGui.QPixmap(cfg["bg"])
        if pm.isNull():
            return
        self.bg_item = self.addPixmap(pm)
        self.bg_item.setZValue(-10)
        self.bg_item.setOpacity(cfg["bg_op"])
        self.bg_item.setScale(cfg["bg_scale"])
        self.bg_item.setPos(QtCore.QPointF(*cfg["bg_pos"]))
        self.bg_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    # --- carte de chaleur
    def sync_heat(self):
        for it in self.heat_items:
            self.removeItem(it)
        self.heat_items = []
        if self.hot_item is not None:
            self.removeItem(self.hot_item)
            self.hot_item = None
        if not self.show_heat:
            return
        o = self.owner
        pts = heat_for(o.map_cfg["heat"], self.heat_f, 0.05)
        if not pts:
            return
        lo, hi = heat_scale([p["level"] for p in pts])
        # 1) le dégradé continu, calculé entre les points (une seule image lissée, sous les tuiles)
        cell = 8.0
        reach = float(o.map_cfg.get("heat_reach", HEAT_REACH))
        x0 = min(p["x"] for p in pts) - reach
        y0 = min(p["y"] for p in pts) - reach
        w = max(p["x"] for p in pts) + reach - x0
        h = max(p["y"] for p in pts) + reach - y0
        field, alpha = heat_field(pts, x0, y0, w, h, cell, reach)
        st = heat_stops(o.map_cfg.get("heat_pal", HEAT_PAL_DEFAULT), o.theme["ui_accent"])
        rgba = np.ascontiguousarray(heat_rgba(field, alpha, lo, hi, float(o.map_cfg.get("heat_op", 0.55)), st))
        img = QtGui.QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.shape[1] * 4,
                           QtGui.QImage.Format.Format_RGBA8888).copy()
        pm = QtGui.QPixmap.fromImage(img.scaled(img.width() * 4, img.height() * 4,
                                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation))
        it = self.addPixmap(pm)
        it.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        it.setScale(cell / 4.0)
        it.setPos(x0, y0)
        it.setZValue(-5)
        self.heat_items.append(it)
        th = o.theme
        # 1 bis) courbes de niveau tous les 5 dB (facultatif)
        if o.map_cfg.get("heat_iso", True) and len(pts) >= 2:
            ink = QtGui.QColor(th["ui_text"])
            for lev, segs in heat_isolines(field, alpha, x0, y0, cell, 5.0):
                path = QtGui.QPainterPath()
                for xa, ya, xb, yb in segs:
                    path.moveTo(xa, ya)
                    path.lineTo(xb, yb)
                c = QtGui.QColor(ink)
                c.setAlphaF(0.30)
                pen = QtGui.QPen(c, 1.1)
                pen.setCosmetic(True)
                li = self.addPath(path, pen)
                li.setZValue(-4.6)
                li.setToolTip(TR("Courbe de niveau : {}").format(o.lvl(lev, suffix=True)))
                self.heat_items.append(li)
        # 1 ter) parcours de la chasse (facultatif) : trace fine et lissée, plus nette vers les derniers points
        if o.map_cfg.get("heat_path", False) and len(pts) >= 2:
            route = heat_path(pts)
            n = len(route)
            for k in range(n - 1):
                p0 = route[max(0, k - 1)]
                p1, p2 = route[k], route[k + 1]
                p3 = route[min(n - 1, k + 2)]
                path = QtGui.QPainterPath(QtCore.QPointF(*p1))
                path.cubicTo(QtCore.QPointF(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6),
                             QtCore.QPointF(p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6),
                             QtCore.QPointF(*p2))
                c = QtGui.QColor(th["ui_text"])
                c.setAlphaF(0.12 + 0.43 * (k + 1) / (n - 1))
                pen = QtGui.QPen(c, float(o.map_cfg.get("heat_trail", 2.0)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                pen.setCosmetic(True)
                li = self.addPath(path, pen)
                li.setZValue(-4.5)
                li.setToolTip(TR("Parcours de la chasse (dans l'ordre des points)"))
                self.heat_items.append(li)
        # 2) les points de mesure : petits, nets, avec leur niveau
        hot = heat_hot(pts)
        font = QtGui.QFont(self.font())
        font.setPointSizeF(8.5)
        font.setBold(True)
        fm = QtGui.QFontMetricsF(font)
        for p in pts:
            r_, g_, b_ = heat_rgb(p["level"], lo, hi, st)
            is_hot = p is hot
            rad = (6.5 if is_hot else 4.5) * float(o.map_cfg.get("heat_dot", 1.0))
            dot = self.addEllipse(QtCore.QRectF(p["x"] - rad, p["y"] - rad, 2 * rad, 2 * rad),
                                  QtGui.QPen(QtGui.QColor(blend(th["ui_text"], th["ui_bg"], 0.65)), 1.4),
                                  QtGui.QBrush(QtGui.QColor(r_, g_, b_)))
            dot.setZValue(-4)
            when = datetime.fromtimestamp(p["t"]).strftime("%H:%M:%S") if p.get("t") else ""
            dot.setToolTip(f"{o.lvl(p['level'], suffix=True)} · {p['f']:.3f} MHz · {when}")
            self.heat_items.append(dot)
            if not (is_hot or o.map_cfg.get("heat_labels", True)):
                continue                       # niveaux écrits : le plus fort seulement
            txt = fmt_level(p["level"], o.unit, 0, False)
            tw = fm.horizontalAdvance(txt) + 10
            box = QtCore.QRectF(p["x"] - tw / 2, p["y"] + (rad * 2.3 if is_hot else rad + 3), tw, fm.height() + 2)
            path = QtGui.QPainterPath()
            path.addRoundedRect(box, 6, 6)
            bg = self.addPath(path, QtGui.QPen(Qt.PenStyle.NoPen),
                              QtGui.QBrush(QtGui.QColor(r_, g_, b_) if is_hot else QtGui.QColor(th["ui_base"])))
            bg.setOpacity(0.92)
            bg.setZValue(-3.9)
            lab = self.addSimpleText(txt, font)
            lab.setBrush(QtGui.QColor("#111111" if is_hot else th["ui_text"]))
            lab.setPos(box.left() + 5, box.top() + 1)
            lab.setZValue(-3.8)
            self.heat_items += [bg, lab]
        if hot is not None:
            hr = 13 * float(o.map_cfg.get("heat_dot", 1.0))
            self.hot_item = self.addEllipse(QtCore.QRectF(hot["x"] - hr, hot["y"] - hr, 2 * hr, 2 * hr),
                                            QtGui.QPen(QtGui.QColor(*heat_rgb(hot["level"], lo, hi, st)), 2.0))
            self.hot_item.setZValue(-3)
            self.hot_item.setToolTip(TR("Le plus fort : {} dBm").format(f"{hot['level']:.1f}"))
        # 3) « par là » (facultatif) : « tu es ici » sur le dernier point + chevrons ››› vers le plus fort + « +N dB »
        self.arrow_info = heat_arrow(pts) if o.map_cfg.get("heat_arrow", True) else None
        ar = self.arrow_info
        if ar:
            acc = QtGui.QColor(heat_dir_color(o.map_cfg.get("heat_dir", "accent"), th["ui_accent"],
                                              heat_rgb(hot["level"], lo, hi, st) if hot else None))
            last = max(pts, key=lambda p_: float(p_.get("t") or 0.0))
            lx, ly = float(last["x"]), float(last["y"])
            halo = QtGui.QRadialGradient(QtCore.QPointF(lx, ly), 22)
            c0, c1 = QtGui.QColor(acc), QtGui.QColor(acc)
            c0.setAlphaF(0.32)
            c1.setAlphaF(0.0)
            halo.setColorAt(0.0, c0)
            halo.setColorAt(1.0, c1)
            items = [self.addEllipse(QtCore.QRectF(lx - 22, ly - 22, 44, 44), QtGui.QPen(Qt.PenStyle.NoPen),
                                     QtGui.QBrush(halo)),
                     self.addEllipse(QtCore.QRectF(lx - 9, ly - 9, 18, 18), QtGui.QPen(acc, 2.0))]
            if ar.get("here"):
                tip = TR("📍 Ta dernière mesure est la plus forte : cherche autour d'ici")
            else:
                ang = math.atan2(ar["y1"] - ar["y0"], ar["x1"] - ar["x0"])
                ux, uy = math.cos(ang), math.sin(ang)
                for k, (d, a_) in enumerate(((27, 0.95), (42, 0.65), (57, 0.35))):
                    cx, cy = lx + ux * d, ly + uy * d
                    path = QtGui.QPainterPath(QtCore.QPointF(cx - ux * 6 - uy * 8, cy - uy * 6 + ux * 8))
                    path.lineTo(cx + ux * 2, cy + uy * 2)
                    path.lineTo(cx - ux * 6 + uy * 8, cy - uy * 6 - ux * 8)
                    c = QtGui.QColor(acc)
                    c.setAlphaF(a_)
                    pen = QtGui.QPen(c, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                    items.append(self.addPath(path, pen))
                txt = f"+{ar['gain']:.0f} dB"
                fnt = QtGui.QFont(self.font())
                fnt.setPointSizeF(8.5)
                fnt.setBold(True)
                fm2 = QtGui.QFontMetricsF(fnt)
                tw, tht = fm2.horizontalAdvance(txt) + 12, fm2.height() + 3
                cx, cy = lx + ux * 80, ly + uy * 80
                box = QtCore.QRectF(cx - tw / 2, cy - tht / 2, tw, tht)
                pp = QtGui.QPainterPath()
                pp.addRoundedRect(box, tht / 2, tht / 2)
                items.append(self.addPath(pp, QtGui.QPen(Qt.PenStyle.NoPen), QtGui.QBrush(acc)))
                lab = self.addSimpleText(txt, fnt)
                lab.setBrush(QtGui.QColor("#111111" if acc.lightnessF() > 0.62 else "#ffffff"))
                lab.setPos(box.left() + 6, box.top() + 1.5)
                items.append(lab)
                tip = TR("Par là : le point le plus fort est {} dB au-dessus de ta dernière mesure").format(f"{ar['gain']:.0f}")
            for it in items:
                it.setZValue(-3.5)
                it.setToolTip(tip)
                self.heat_items.append(it)

    # --- glisser-déposer
    def _node_dropped_base(self, n):
        o = self.owner
        p = map_snap(n.pos().x(), n.pos().y())
        n.setPos(QtCore.QPointF(*p))
        o.map_cfg["pos"][n.key] = p
        if n.kind == "dev":                    # tinySA posé SUR une scène = rattaché à elle
            for k, m in self.nodes.items():
                if m.kind == "scene" and m.sceneBoundingRect().intersects(n.sceneBoundingRect()):
                    d = int(n.name)
                    if m.name not in o.dev_scenes.get(d, []):
                        o.toggle_dev_scene(d, m.name, True)
                        o.set_status(TR("📡 {} surveille maintenant « {} » (glissé sur la carte).").format(
                            self.label(n.key), m.name))
                    n.setPos(QtCore.QPointF(p[0], m.pos().y() + m.h + MAP_STEP))
                    o.map_cfg["pos"][n.key] = [n.pos().x(), n.pos().y()]
                    break
        self.refresh()

    def node_dropped(self, n):
        if n.kind != "sdr":
            return self._node_dropped_base(n)
        o = self.owner
        p = map_snap(n.pos().x(), n.pos().y())
        n.setPos(QtCore.QPointF(*p))
        o.map_cfg["pos"][n.key] = p
        for _k, m in self.nodes.items():                   # SDR posé SUR une scène = il la surveille
            if m.kind == "scene" and m.sceneBoundingRect().intersects(n.sceneBoundingRect()):
                ps = sdr_posts_norm(o.sdr_cfg.get("posts"))
                for pp in ps:
                    if pp["id"] == int(n.name) and m.name not in pp["scenes"]:
                        pp["scenes"].append(m.name)
                        o.sdr_cfg["posts"] = ps
                        o._sdr_posts_sync()
                        o.set_status(TR("📡 {} surveille maintenant « {} » (glissé sur la carte).").format(
                            self.label(n.key), m.name))
                n.setPos(QtCore.QPointF(p[0], m.pos().y() + m.h + MAP_STEP))
                o.map_cfg["pos"][n.key] = [n.pos().x(), n.pos().y()]
                break
        self.refresh()

    def _node_open_base(self, n):
        o = self.owner
        if n.kind == "scene":
            o.set_scope([(n.name, None)])
            o.set_status(TR("🗺 Vue sur « {} » (liste et spectre).").format(n.name))
        else:
            o.open_devices()

    def node_open(self, n):
        if n.kind != "sdr":
            return self._node_open_base(n)
        o = self.owner
        pid = int(n.name)
        if o.rf_mode == "tiny":
            o.set_rf_mode("sdr")
        for d in o.post_docks.get(pid, {}).values():
            if d.isHidden() and d is not o.post_docks[pid].get("wf"):
                d.show()
            d.raise_()
        e = o.sdr_engs.get(pid)
        if e is not None and not e.running():
            e.start()

    def mark(self, x, y, who=""):
        """📍 Point de chaleur à (x, y) avec le niveau actuel de la chasse. -> point, ou None (pas de chasse en cours)."""
        o = self.owner
        h = o._hunt
        if h is None or not h.go_btn.isChecked() or h.level is None:
            return None
        pt = dict(x=round(float(x), 1), y=round(float(y), 1), level=round(float(h.level), 1),
                  f=round(float(h.f_spin.value()), 4), t=time.time())
        o.map_cfg["heat"].append(pt)
        del o.map_cfg["heat"][:-HEAT_MAX]
        self.heat_f = pt["f"]
        self.sync_heat()
        return pt

    def _sdr_links(self):
        o = self.owner
        for it in getattr(self, "sdr_links", []):
            if it.scene() is self:
                self.removeItem(it)
        self.sdr_links = []
        for pid, e in (getattr(o, "sdr_engs", None) or {}).items():
            a = self.nodes.get(map_key("sdr", pid))
            if a is None:
                continue
            for scn in e.post()["scenes"]:
                b = self.nodes.get(map_key("scene", scn))
                if b is None:
                    continue
                pa, pb = a.port(b.pos().y() < a.pos().y()), b.port(b.pos().y() >= a.pos().y())
                path = QtGui.QPainterPath(pa)
                dy = max(40.0, abs(pb.y() - pa.y()) / 2) * (1 if pb.y() >= pa.y() else -1)
                path.cubicTo(QtCore.QPointF(pa.x(), pa.y() + dy), QtCore.QPointF(pb.x(), pb.y() - dy), pb)
                pen = QtGui.QPen(QtGui.QColor("#64d2ff"), 2.4)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                if not _v8_post_live(e):
                    pen.setStyle(Qt.PenStyle.DashLine)
                it = self.addPath(path, pen)
                it.setZValue(5)
                self.sdr_links.append(it)


class MapView(QtWidgets.QGraphicsView):
    """Vue de la carte : grille en points, molette = zoom, glisser le fond = se déplacer, clic pendant une chasse = point noté."""

    def __init__(self, sc, win):
        super().__init__(sc)
        self.win = win
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        for pol in (self.setHorizontalScrollBarPolicy, self.setVerticalScrollBarPolicy):
            pol(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)      # on se déplace en glissant le fond
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setToolTip("Glisse les tuiles pour les placer · dépose un tinySA sur une scène pour la lui rattacher ·\n"
                        "molette = zoom · glisser le fond = se déplacer · double-clic sur une scène = la voir · clic droit = options")

    def drawBackground(self, p, rect):
        th = self.win.owner.theme
        p.fillRect(rect, QtGui.QColor(th["ui_bg"]))
        if not self.win.owner.map_cfg.get("grid", True):
            return
        step = MAP_STEP if self.transform().m11() >= 0.45 else MAP_STEP * 3
        p.setPen(QtGui.QPen(QtGui.QColor(blend(th["ui_text"], th["ui_bg"], 0.22)), 2.2))
        pts = []
        x0 = math.floor(rect.left() / step) * step
        y = math.floor(rect.top() / step) * step
        while y < rect.bottom():
            x = x0
            while x < rect.right():
                pts.append(QtCore.QPointF(x, y))
                x += step
            y += step
        if len(pts) < 40000:                   # grille en points discrets (façon canevas)
            p.drawPoints(pts)

    def wheelEvent(self, e):
        k = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        if self.win.bg_move.isChecked() and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.win.wheel_bg(k)                   # Ctrl + molette : agrandir / réduire le plan
            return
        sc = self.transform().m11() * k
        if 0.15 <= sc <= 4.0:
            self.scale(k, k)

    def mousePressEvent(self, e):
        self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        p0 = getattr(self, "_press", None)
        pos = e.position().toPoint()
        if (p0 is not None and e.button() == Qt.MouseButton.LeftButton and self.win.marking()
                and (pos - p0).manhattanLength() < 6 and not isinstance(self.itemAt(pos), MapNode)):
            pt = self.mapToScene(pos)          # un simple clic (pas un glisser) pendant la chasse = point noté
            self.win.mark_at(pt.x(), pt.y())
        self._press = None

    def contextMenuEvent(self, e):
        it = self.itemAt(e.pos())
        self.win.context_menu(it if isinstance(it, MapNode) else None, self.mapToScene(e.pos()), e.globalPos())


class MapHeatLegend(QtWidgets.QWidget):
    """Légende de la carte de chaleur (posée sur la carte, en bas à gauche) : dégradé bleu → rouge + niveaux."""

    def __init__(self, parent, owner):
        super().__init__(parent)
        self.owner, self.lo, self.hi, self.n = owner, -100.0, -40.0, 0
        self.setFixedSize(230, 54)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_range(self, lo, hi, n):
        self.lo, self.hi, self.n = lo, hi, n
        self.setVisible(n > 0)
        self.update()

    def paintEvent(self, e):
        th = self.owner.theme
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        card = blend(th["ui_text"], th["ui_base"], 0.05)
        p.setPen(QtGui.QPen(QtGui.QColor(blend(th["ui_text"], card, 0.18)), 1.0))
        p.setBrush(QtGui.QColor(card))
        p.drawRoundedRect(QtCore.QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 10, 10)
        g = QtGui.QLinearGradient(12, 0, self.width() - 12, 0)
        st = heat_stops(self.owner.map_cfg.get("heat_pal", HEAT_PAL_DEFAULT), th["ui_accent"])
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            g.setColorAt(t, QtGui.QColor(*heat_rgb(self.lo + t * (self.hi - self.lo), self.lo, self.hi, st)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QBrush(g))
        p.drawRoundedRect(QtCore.QRectF(12, 26, self.width() - 24, 10), 5, 5)
        f = QtGui.QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        p.setPen(QtGui.QColor(th["ui_text"]))
        p.drawText(QtCore.QRectF(12, 4, self.width() - 24, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   TR("🔥 Chaleur · {} point(s)").format(self.n))
        sub = QtGui.QColor(blend(th["ui_text"], card, 0.62))
        p.setPen(sub)
        p.drawText(QtCore.QRectF(12, 36, 90, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{self.lo:.0f} dBm")
        p.drawText(QtCore.QRectF(self.width() - 102, 36, 90, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"{self.hi:.0f} dBm")


class MapWindow(QtWidgets.QWidget):
    """🗺 7.64 Carte du site, vraie fenêtre épurée : la carte prend toute la place ; scènes et tinySA posés tout seuls
    (on les déplace ensuite), barre fine (🖼 Plan, 🔥 Chaleur, ⋯), bulle d'aide flottante, zoom et légende sur la carte.
    Pendant une 🔎 chasse, un simple clic sur la carte note le niveau à cet endroit (carte de chaleur)."""

    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Window)
        self.owner = o = owner
        self.setWindowTitle("Carte du site")
        self.heat_on, self._hint, self._hint_t = True, "", 0.0
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        # --- 🖼 Plan (facultatif)
        self.plan_btn = QtWidgets.QToolButton()
        self.plan_btn.setText("🖼 Plan")
        self.plan_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.plan_btn.setToolTip("Facultatif : une image du plan du site sous les tuiles. Sans plan, la grille suffit.")
        pm = QtWidgets.QMenu(self.plan_btn)
        pm.addAction("Choisir une image…").triggered.connect(lambda *_: self.pick_bg())
        ow = QtWidgets.QWidget()
        ol = QtWidgets.QHBoxLayout(ow)
        ol.setContentsMargins(12, 4, 12, 4)
        ol.addWidget(QtWidgets.QLabel("Opacité"))
        self.op = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.op.setRange(5, 100)
        self.op.setValue(int(o.map_cfg["bg_op"] * 100))
        self.op.setMinimumWidth(140)
        self.op.setToolTip("Transparence du plan de fond.")
        self.op.valueChanged.connect(lambda v: self._bg_param(bg_op=v / 100.0))
        ol.addWidget(self.op)
        wa = QtWidgets.QWidgetAction(pm)
        wa.setDefaultWidget(ow)
        pm.addAction(wa)
        self.bg_move = pm.addAction("Caler le plan (déplacer, Ctrl + molette = taille)")
        self.bg_move.setCheckable(True)
        self.bg_move.triggered.connect(lambda *_: self._bg_movable())
        pm.addSeparator()
        pm.addAction("Retirer le plan").triggered.connect(lambda *_: self.set_bg(""))
        self.plan_btn.setMenu(pm)
        # --- 🔥 Chaleur
        self.heat_btn = QtWidgets.QToolButton()
        self.heat_btn.setText("🔥 Chaleur")
        self.heat_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self.heat_btn.setToolTip("Carte de chaleur de la chasse au brouilleur : bleu = faible, rouge = là où ça crie le plus.")
        self.heat_menu = QtWidgets.QMenu(self.heat_btn)
        self.heat_menu.aboutToShow.connect(self._build_heat_menu)
        self.heat_btn.setMenu(self.heat_menu)
        # --- infos, tout voir, ⋯
        self.count_lbl = QtWidgets.QLabel("")
        self.count_lbl.setStyleSheet(f"color:{blend(o.theme['ui_text'], o.theme['ui_bg'], 0.6)}")
        fit = QtWidgets.QPushButton("⤢ Tout voir")
        fit.setToolTip("Recadre la vue sur toutes les tuiles.")
        fit.clicked.connect(lambda *_: self.fit())
        more = QtWidgets.QToolButton()
        more.setText("⋯")
        more.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        more.setToolTip("Plus d'options : grille, réorganiser, exporter.")
        mm = QtWidgets.QMenu(more)
        self.grid_act = mm.addAction("Grille")
        self.grid_act.setCheckable(True)
        self.grid_act.setChecked(o.map_cfg.get("grid", True))
        self.grid_act.triggered.connect(lambda *_: (o.map_cfg.__setitem__("grid", self.grid_act.isChecked()),
                                                    self.view.viewport().update()))
        mm.addAction("Réorganiser automatiquement").triggered.connect(lambda *_: self.relayout())
        mm.addSeparator()
        mm.addAction("Exporter en PNG…").triggered.connect(lambda *_: self.export_png())
        more.setMenu(mm)
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(6)
        for w_ in (self.plan_btn, self.heat_btn):
            bar.addWidget(w_)
        bar.addStretch(1)
        bar.addWidget(self.count_lbl)
        bar.addWidget(fit)
        bar.addWidget(more)
        lay.addLayout(bar)
        # --- la carte
        self.view = MapView(o.map_scene(), self)
        lay.addWidget(self.view, 1)
        self.zoom_box = QtWidgets.QWidget(self.view)     # zoom (en haut à droite)
        zb = QtWidgets.QVBoxLayout(self.zoom_box)
        zb.setContentsMargins(0, 0, 0, 0)
        zb.setSpacing(4)
        for txt, tip, k in (("+", "Zoomer", 1.2), ("−", "Dézoomer", 1 / 1.2)):
            b = QtWidgets.QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.setFixedSize(32, 32)
            b.clicked.connect(lambda *_, k=k: self.view.scale(k, k))
            zb.addWidget(b)
        self.legend = MapHeatLegend(self.view, o)       # légende de chaleur (en bas à gauche)
        self.banner = QtWidgets.QLabel("", self.view)   # bulle d'aide (en haut, au centre)
        self.banner.setWordWrap(True)
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.banner.hide()
        self.view.installEventFilter(self)
        self.resize(1100, 720)
        fit_dialog(self, 1100, 720)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        o.map_scene().sync()
        self.fill_heat()
        self.tick()
        QtCore.QTimer.singleShot(50, lambda: (self.fit(), self._place_overlays()))

    # --- aide flottante
    def hint(self, txt, secs=6.0):
        self._hint, self._hint_t = txt, time.time() + secs
        self._show_banner()

    def _show_banner(self):
        o = self.owner
        th = o.theme
        if self.marking():
            h = o._hunt
            txt = TR("🔎 Chasse en cours sur {} MHz · clique sur la carte là où tu es : le niveau y est noté").format(
                f"{h.f_spin.value():.3f}")
            ar = o.map_scene().arrow_info
            if ar and ar.get("here"):
                txt += "\n" + TR("📍 Ta dernière mesure est la plus forte : cherche autour d'ici")
            elif ar:
                txt += "\n" + TR("››› Va dans la direction des chevrons : environ {} dB de plus vers le point le plus fort").format(f"{ar['gain']:.0f}")
            col = th["ui_accent"]
        elif self._hint and time.time() < self._hint_t:
            txt, col = self._hint, th["ui_text"]
        else:
            self.banner.hide()
            return
        self.banner.setText(txt)
        self.banner.setStyleSheet(soft_style(col, th["ui_base"], th["ui_text"]) + "; padding:8px 14px; border-radius:14px")
        fm = self.banner.fontMetrics()
        tw = max(fm.horizontalAdvance(l_) for l_ in txt.split("\n")) + 40
        self.banner.setFixedWidth(max(200, min(tw, self.view.width() - 120)))
        self.banner.adjustSize()
        self.banner.show()
        self._place_overlays()

    def marking(self):
        h = self.owner._hunt
        try:
            return h is not None and h.go_btn.isChecked()
        except RuntimeError:
            return False

    # --- placement
    def relayout(self):
        o = self.owner
        o.map_cfg["pos"] = {}
        o.map_scene().auto_place()
        self.fit()

    def fit(self):
        """Cadre sur les tuiles (pas sur le plan de fond, souvent bien plus grand), zoom 1:1 au plus."""
        sc = self.owner.map_scene()
        r = QtCore.QRectF()
        for n in sc.nodes.values():
            r = r.united(n.sceneBoundingRect())
        for it in sc.heat_items:
            r = r.united(it.sceneBoundingRect())
        if r.isEmpty():
            r = sc.itemsBoundingRect()
        if r.isEmpty():
            r = QtCore.QRectF(-200, -150, 800, 500)
        self.view.resetTransform()
        self.view.fitInView(r.adjusted(-80, -150, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)   # place pour la bulle
        if self.view.transform().m11() > 1.0:
            self.view.resetTransform()
            self.view.centerOn(r.center())

    def eventFilter(self, obj, e):
        if obj is self.view and e.type() == QtCore.QEvent.Type.Resize:
            self._place_overlays()
        return super().eventFilter(obj, e)

    def _place_overlays(self):
        vw = self.view.viewport().geometry()
        self.zoom_box.adjustSize()
        self.zoom_box.move(vw.right() - self.zoom_box.width() - 10, vw.top() + 10)
        self.legend.move(vw.left() + 10, vw.bottom() - self.legend.height() - 10)
        if self.banner.isVisible():
            self.banner.move(vw.left() + (vw.width() - self.banner.width()) // 2, vw.top() + 10)
        for w_ in (self.zoom_box, self.legend, self.banner):
            w_.raise_()

    # --- plan de fond
    def pick_bg(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Plan du site (image)", "",
                                                            "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
            if not path:
                return False
        if QtGui.QPixmap(path).isNull():
            self.hint(TR("Image illisible."))
            return False
        self.set_bg(path)
        return True

    def set_bg(self, path):
        o = self.owner
        o.map_cfg["bg"] = path
        if path:
            pm = QtGui.QPixmap(path)
            r = QtCore.QRectF()
            for n in o.map_scene().nodes.values():
                r = r.united(n.sceneBoundingRect())
            w0 = max(r.width() + 200, 1200.0)
            o.map_cfg["bg_scale"] = round(w0 / max(1, pm.width()), 3)
            o.map_cfg["bg_pos"] = [r.left() - 100 if not r.isEmpty() else -200.0, r.top() - 100 if not r.isEmpty() else -150.0]
        o.map_scene().sync_bg()
        self._bg_movable()
        if path:
            self.hint(TR("Plan posé. 🖼 Plan › « Caler le plan » pour l'ajuster sous tes tuiles."))
        self.fit()

    def _bg_param(self, **kw):
        self.owner.map_cfg.update(kw)
        it = self.owner.map_scene().bg_item
        if it is not None and "bg_op" in kw:
            it.setOpacity(kw["bg_op"])

    def _bg_movable(self):
        it = self.owner.map_scene().bg_item
        if it is None:
            return
        on = self.bg_move.isChecked()
        it.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, on)
        it.setZValue(20 if on else -10)
        if on:
            self.hint(TR("Glisse le plan, Ctrl + molette pour l'agrandir. Décoche « Caler le plan » pour le figer."), 10.0)

    def wheel_bg(self, k):
        o = self.owner
        it = o.map_scene().bg_item
        if it is not None:
            o.map_cfg["bg_scale"] = min(20.0, max(0.02, o.map_cfg["bg_scale"] * k))
            it.setScale(o.map_cfg["bg_scale"])

    # --- chaleur
    def _build_heat_menu(self):
        o = self.owner
        m = self.heat_menu
        m.clear()
        a = m.addAction("Afficher la carte de chaleur")
        a.setCheckable(True)
        a.setChecked(self.heat_on)
        a.triggered.connect(lambda *_, a=a: self._heat(a.isChecked()))
        m.addSection(TR("Apparence"))
        cm = m.addMenu(TR("🎨 Couleurs"))
        for k, name, _st in HEAT_PALETTES:
            b = cm.addAction(name)
            b.setCheckable(True)
            b.setChecked(o.map_cfg.get("heat_pal", HEAT_PAL_DEFAULT) == k)
            b.triggered.connect(lambda *_, k=k: self.set_heat_opt("heat_pal", k))
        ow = QtWidgets.QWidget()
        ol = QtWidgets.QHBoxLayout(ow)
        ol.setContentsMargins(12, 4, 12, 4)
        ol.addWidget(QtWidgets.QLabel(TR("Intensité")))
        sl = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        sl.setRange(10, 95)
        sl.setValue(int(round(float(o.map_cfg.get("heat_op", 0.55)) * 100)))
        sl.setMinimumWidth(150)
        sl.setToolTip(TR("Plus ou moins opaque : à baisser pour bien voir le plan de fond sous la chaleur."))
        sl.valueChanged.connect(lambda v: self.set_heat_opt("heat_op", v / 100.0))
        ol.addWidget(sl)
        wa = QtWidgets.QWidgetAction(m)
        wa.setDefaultWidget(ow)
        m.addAction(wa)
        self.heat_slider = sl
        for title, key, opts in (("Taille des points", "heat_dot", HEAT_DOT_SIZES),
                                 ("Épaisseur du parcours", "heat_trail", HEAT_TRAIL_WIDTHS),
                                 ("Couleur de la direction", "heat_dir", tuple((v, t) for v, t in HEAT_DIR_COLORS))):
            sub = m.addMenu(TR(title))
            cur = o.map_cfg.get(key, MAP_DEFAULT[key])
            for v, txt in opts:
                b = sub.addAction(TR(txt))
                if isinstance(v, str) and v.startswith("#"):
                    pm = QtGui.QPixmap(12, 12)
                    pm.fill(QtGui.QColor(v))
                    b.setIcon(QtGui.QIcon(pm))
                b.setCheckable(True)
                b.setChecked(cur == v if isinstance(v, str) else abs(float(cur) - v) < 1e-6)
                b.triggered.connect(lambda *_, key=key, v=v: self.set_heat_opt(key, v))
        m.addSection(TR("Sur la carte"))
        for key, txt in (("heat_labels", "Niveaux écrits sur les points"),
                         ("heat_iso", "Courbes de niveau (tous les 5 dB)"),
                         ("heat_arrow", "Direction « par là » (vers le plus fort)"),
                         ("heat_path", "Parcours de la chasse")):
            b = m.addAction(txt)
            b.setCheckable(True)
            b.setChecked(bool(o.map_cfg.get(key, MAP_DEFAULT[key])))
            b.triggered.connect(lambda *_, key=key, b=b: self.set_heat_opt(key, b.isChecked()))
        sub = m.addMenu(TR("Étalement du dégradé"))
        for r, txt in zip(HEAT_REACHES, ("Serré (points rapprochés)", "Normal", "Large (points espacés)")):
            b = sub.addAction(txt)
            b.setCheckable(True)
            b.setChecked(abs(float(o.map_cfg.get("heat_reach", HEAT_REACH)) - r) < 1)
            b.triggered.connect(lambda *_, r=r: self.set_heat_opt("heat_reach", r))
        fs = heat_freqs(o.map_cfg["heat"])
        if fs:
            m.addSection(TR("Fréquence chassée"))
            cur = o.map_scene().heat_f
            for f in [None] + fs:
                b = m.addAction(TR("Toutes les fréquences") if f is None else f"{f:.3f} MHz")
                b.setCheckable(True)
                b.setChecked(cur == f)
                b.triggered.connect(lambda *_, f=f: self._set_heat_f(f))
            m.addSeparator()
            m.addAction("Effacer les points affichés").triggered.connect(lambda *_: self.clear_heat())
        m.addSeparator()
        m.addAction("Comment noter des points ?").triggered.connect(lambda *_: self.hint(TR(
            "Lance une 🔎 chasse au brouilleur, puis clique sur la carte là où tu es (PC portable), ou sur le téléphone : "
            "vue 🔎 Chasse › « Où suis-je ? »."), 12.0))

    def set_heat_opt(self, key, val):
        """Affichages de la chaleur (couleurs, intensité, niveaux, courbes, direction, parcours, étalement) : chacun se
        règle / se coupe à part ; gardé avec le show, et l'image du téléphone suit."""
        self.owner.map_cfg[key] = val
        self._heat(self.heat_on)
        self.legend.update()

    def _set_heat_f(self, f):
        self.owner.map_scene().heat_f = f
        self._heat(True)

    def fill_heat(self):
        """Après un nouveau point : on montre la fréquence chassée."""
        sc = self.owner.map_scene()
        fs = heat_freqs(self.owner.map_cfg["heat"])
        if sc.heat_f is not None and round(sc.heat_f, 3) not in fs:
            sc.heat_f = fs[0] if fs else None
        self._heat(self.heat_on)

    def _heat(self, on):
        self.heat_on = bool(on)
        sc = self.owner.map_scene()
        sc.show_heat = self.heat_on
        sc.sync_heat()
        pts = heat_for(self.owner.map_cfg["heat"], sc.heat_f, 0.05)
        lo, hi = heat_scale([p_["level"] for p_ in pts])
        self.legend.set_range(lo, hi, len(pts) if self.heat_on else 0)
        self._place_overlays()

    def mark_at(self, x, y):
        pt = self.owner.map_scene().mark(x, y)
        if pt is None:
            self.hint(TR("📍 Lance d'abord la chasse au brouilleur (🎚 Surveiller › 🔎) : le point note son niveau."))
            return None
        self.fill_heat()
        self.hint(TR("📍 Point noté : {} à {} MHz.").format(self.owner.lvl(pt["level"], suffix=True), f"{pt['f']:.3f}"), 3.0)
        return pt

    def clear_heat(self):
        o = self.owner
        f = o.map_scene().heat_f
        o.map_cfg["heat"] = [p for p in o.map_cfg["heat"] if f is not None and abs(p["f"] - f) > 0.05]
        o.map_scene().heat_f = None
        self.fill_heat()

    # --- menu des tuiles
    def context_menu(self, node, pt, gpos):
        o = self.owner
        m = QtWidgets.QMenu(self)
        acts = {}
        if node is not None and node.kind == "dev":
            d = int(node.name)
            sub = m.addMenu("📡 Surveille…")
            for sc in o.scenes:
                a = sub.addAction(sc["name"])
                a.setCheckable(True)
                a.setChecked(sc["name"] in o.dev_scenes.get(d, []))
                a.triggered.connect(lambda *_, n=sc["name"], a=a: (o.toggle_dev_scene(d, n, a.isChecked()),
                                                                   o.map_scene().refresh()))
            acts[m.addAction("🌐 Tout le site (aucune scène)")] = lambda: (o.set_dev_scenes(d, []), o.map_scene().refresh())
            acts[m.addAction("👋 Identifier ce tinySA")] = lambda: o.identify_device(d)
        if node is not None and node.kind == "scene":
            acts[m.addAction("🔍 Voir cette scène (liste et spectre)")] = lambda: o.map_scene().node_open(node)
        if node is None:
            acts[m.addAction("📍 Noter le niveau de la chasse ici")] = lambda: self.mark_at(pt.x(), pt.y())
            acts[m.addAction("⤢ Tout voir")] = lambda: self.fit()
        act = m.exec(gpos)
        if act in acts:
            acts[act]()

    def tick(self):
        if not self.isVisible():
            return
        o = self.owner
        sc = o.map_scene()
        if sc.unplaced():                      # nouvelle scène / nouveau tinySA : posé tout seul
            sc.auto_place()
        elif set(sc.keys_all()) != set(sc.nodes):
            sc.sync()
        else:
            sc.refresh()
        ns = sum(1 for n in sc.nodes.values() if n.kind == "scene")
        self.count_lbl.setText(TR("{} scène(s) · {} tinySA").format(ns, len(sc.nodes) - ns))
        self.view.setCursor(Qt.CursorShape.CrossCursor if self.marking() else Qt.CursorShape.ArrowCursor)
        self._show_banner()

    def export_png(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter la carte", "carte_site.png", "Image PNG (*.png)")
            if not path:
                return False
        data, _r = self.owner.map_png(1800)
        if not data:
            return False
        Path(path).write_bytes(data)
        return True

    def closeEvent(self, e):
        bg = self.owner.map_scene().bg_item
        if bg is not None:                    # position du plan déplacé gardée
            self.owner.map_cfg["bg_pos"] = [bg.pos().x(), bg.pos().y()]
        super().closeEvent(e)
