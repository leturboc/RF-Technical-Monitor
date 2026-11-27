# Thèmes, mises en page, dialogues de la liste, intermod, secours, relecture, plans.
# Partie de l'interface de RF Technical Monitor (8.1 étape 3). PAS un module à importer : exécutée dans l'espace
# de noms de tinysa_monitor.py, dans l'ordre de tsm_ui.PARTS (voir tsm_ui/__init__.py). Les noms viennent de là.


# --------------------------------------------------------------------------
# Aides graphiques
# --------------------------------------------------------------------------
def qss_icons(t):
    """Petites images du look « pro » (7.54) dessinées à la volée aux couleurs du thème (flèche de menu, coche) ->
    morceau de feuille de style. Les styler sans image faisait disparaître la flèche / la coche."""
    try:
        d = Path(tempfile.gettempdir()) / "tinysa_monitor_qss"
        d.mkdir(parents=True, exist_ok=True)
        sub = blend(t["ui_text"], t["ui_bg"], 0.70)
        on = contrast_text(t["ui_accent"])
        key = (sub + on).replace("#", "")

        def draw(name, col, pts, w=2.0, size=24):
            path = d / f"{name}_{key}.png"
            if not path.exists():
                pm = QtGui.QPixmap(size, size)
                pm.fill(Qt.GlobalColor.transparent)
                pa = QtGui.QPainter(pm)
                pa.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                pen = QtGui.QPen(QtGui.QColor(col), w * size / 12)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pa.setPen(pen)
                pa.drawPolyline(QtGui.QPolygonF([QtCore.QPointF(x * size, y * size) for x, y in pts]))
                pa.end()
                pm.save(str(path), "PNG")
            return path.as_posix()

        chev = draw("chev", sub, [(0.25, 0.38), (0.5, 0.63), (0.75, 0.38)], 1.4)
        chk = draw("check", on, [(0.24, 0.52), (0.42, 0.70), (0.76, 0.32)], 1.6)
        bd = blend(t["ui_text"], t["ui_bg"], 0.32)
        acc, base = t["ui_accent"], t["ui_base"]
        return f"""
QToolButton::menu-indicator {{ image:url({chev}); subcontrol-origin:padding; subcontrol-position:right center;
    right:5px; width:10px; height:10px; }}
QToolButton::menu-button {{ border:0; border-left:1px solid {bd}; width:16px; }}
QToolButton::menu-arrow {{ image:url({chev}); width:10px; height:10px; }}
QPushButton::menu-indicator {{ image:url({chev}); subcontrol-origin:padding; subcontrol-position:right center;
    right:5px; width:10px; height:10px; }}
QComboBox {{ background:{base}; border:1px solid {blend(t["ui_text"], t["ui_bg"], 0.16)}; border-radius:6px;
    padding:2px 22px 2px 8px; }}
QComboBox:hover {{ border-color:{bd}; }}
QComboBox:focus {{ border-color:{acc}; }}
QComboBox::drop-down {{ border:0; width:22px; }}
QComboBox::down-arrow {{ image:url({chev}); width:10px; height:10px; }}
QComboBox QAbstractItemView {{ border:1px solid {bd}; border-radius:8px; padding:4px; outline:0; }}
QCheckBox::indicator, QGroupBox::indicator {{ width:15px; height:15px; border-radius:4px;
    border:1px solid {bd}; background:{base}; }}
QCheckBox::indicator:hover {{ border-color:{acc}; }}
QCheckBox::indicator:checked, QGroupBox::indicator:checked {{ background:{acc}; border-color:{acc}; image:url({chk}); }}
QCheckBox::indicator:disabled {{ background:{t["ui_bg"]}; }}
"""
    except Exception:  # noqa: BLE001  — pas d'image : on garde les flèches / coches de Qt
        return ""


def build_palette(t):
    C = QtGui.QColor
    R, G = QtGui.QPalette.ColorRole, QtGui.QPalette.ColorGroup
    p = QtGui.QPalette()
    p.setColor(R.Window, C(t["ui_bg"]))
    p.setColor(R.WindowText, C(t["ui_text"]))
    p.setColor(R.Base, C(t["ui_base"]))
    p.setColor(R.AlternateBase, C(t["ui_bg"]))
    p.setColor(R.Text, C(t["ui_text"]))
    p.setColor(R.Button, C(t["ui_button"]))
    p.setColor(R.ButtonText, C(t["ui_text"]))
    p.setColor(R.ToolTipBase, C(t["ui_button"]))
    p.setColor(R.ToolTipText, C(t["ui_text"]))
    p.setColor(R.Highlight, C(t["ui_accent"]))
    p.setColor(R.HighlightedText, C(contrast_text(t["ui_accent"])))
    p.setColor(R.PlaceholderText, C(blend(t["ui_text"], t["ui_bg"], 0.5)))
    dis = C(blend(t["ui_text"], t["ui_bg"], 0.4))
    p.setColor(G.Disabled, R.Text, dis)
    p.setColor(G.Disabled, R.ButtonText, dis)
    p.setColor(G.Disabled, R.WindowText, dis)
    return p


def make_lut(name):
    stops = WF_MAPS.get(name) or WF_MAPS["Inferno"]
    cmap = pg.ColorMap([s[0] for s in stops], [s[1] for s in stops])
    return cmap.getLookupTable(0.0, 1.0, 256)


def color_icon(color, size=12):
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtGui.QColor(color))
    return QtGui.QIcon(pm)


class FlowLayout(QtWidgets.QLayout):
    """Rangée de widgets qui passe à la ligne quand la fenêtre est trop étroite (barres d'outils)."""

    def __init__(self, parent=None, hspace=6, vspace=4):
        super().__init__(parent)
        self._items, self._hs, self._vs = [], hspace, vspace
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._place(QtCore.QRect(0, 0, w, 0), False)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._place(r, True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        sz = QtCore.QSize()
        for it in self._items:
            sz = sz.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return sz + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, r, apply):
        m = self.contentsMargins()
        r = r.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = r.x(), r.y(), 0
        for it in self._items:
            if it.isEmpty():
                continue
            sh = it.sizeHint()
            if x + sh.width() > r.right() + 1 and line_h > 0:
                x, y, line_h = r.x(), y + line_h + self._vs, 0
            if apply:
                it.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), sh))
            x += sh.width() + self._hs
            line_h = max(line_h, sh.height())
        return y + line_h - r.y() + m.top() + m.bottom()


def swatch_style(color):
    return ("QPushButton{background:%s;color:%s;border:1px solid #888;border-radius:4px;padding:3px 10px;}"
            % (color, contrast_text(color)))


# --------------------------------------------------------------------------
# Dialogue : couleurs
# --------------------------------------------------------------------------
class ColorsDialog(QtWidgets.QDialog):
    def __init__(self, parent, theme, preview_cb):
        super().__init__(parent)
        self.setWindowTitle("Couleurs")
        self.resize(460, 640)
        self.original = dict(theme)
        self.theme = dict(theme)
        self.preview_cb = preview_cb
        self.buttons = {}

        lay = QtWidgets.QVBoxLayout(self)
        self.preset = QtWidgets.QComboBox()
        self.preset.addItem("Personnalisé")
        for n in THEMES:
            self.preset.addItem(n, n)                    # nom affiché (traduit) / clé (data)
        self.preset.activated.connect(self.on_preset)
        self.wf_combo = QtWidgets.QComboBox()
        for n in WF_MAPS:
            self.wf_combo.addItem(n, n)
        self.wf_combo.setCurrentIndex(max(0, self.wf_combo.findData(self.theme.get("wf", "Inferno"))))
        self.wf_combo.activated.connect(self.on_wf)
        top = QtWidgets.QFormLayout()
        top.addRow("Thème prédéfini :", self.preset)
        top.addRow("Palette du waterfall :", self.wf_combo)
        lay.addLayout(top)

        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        iv = QtWidgets.QVBoxLayout(inner)
        for group in ("Interface", "Graphique", "Etats du signal", "Bandes du spectre"):
            box = QtWidgets.QGroupBox(group)
            form = QtWidgets.QFormLayout(box)
            for key, label, g in THEME_KEYS:
                if g != group:
                    continue
                b = QtWidgets.QPushButton(self.theme[key])
                b.clicked.connect(lambda _=False, k=key: self.pick(k))
                self.buttons[key] = b
                form.addRow(label + " :", b)
            iv.addWidget(box)
        iv.addStretch(1)
        area.setWidget(inner)
        lay.addWidget(area, 1)
        hint = QtWidgets.QLabel("Les couleurs des statuts manuels se règlent dans « Statuts ».\n"
                                "Les changements s'appliquent en direct.")
        lay.addWidget(hint)
        # 7.54.1 : scènes / groupes / statuts aux couleurs du thème (nuances du phosphore en « analyseur »)
        self.recolor_chk = QtWidgets.QCheckBox("Recolorer aussi mes scènes, groupes et statuts avec ce thème")
        self.recolor_chk.setToolTip("Chaque thème a sa palette (nuances du phosphore pour les thèmes « Analyseur »).\n"
                                    "Coché : à OK, tes scènes, groupes et statuts prennent ces couleurs ; les statuts\n"
                                    "« doit rester libre » / « doit émettre » gardent leur sens. Annulable (Ctrl+Z).\n"
                                    "Les nouvelles scènes et nouveaux groupes prennent toujours la palette du thème.")
        lay.addWidget(self.recolor_chk)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.refresh_buttons()

    def refresh_buttons(self):
        for k, b in self.buttons.items():
            b.setText(self.theme[k])
            b.setStyleSheet(swatch_style(self.theme[k]))

    def pick(self, key):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.theme[key]), self, "Choisir une couleur")
        if c.isValid():
            self.theme[key] = c.name()
            self.preset.setCurrentIndex(0)
            self.refresh_buttons()
            self.preview_cb(self.theme)

    def on_preset(self, idx):
        if idx <= 0:
            return
        self.theme = dict(THEMES[self.preset.currentData()])
        self.wf_combo.setCurrentIndex(max(0, self.wf_combo.findData(self.theme["wf"])))
        self.refresh_buttons()
        self.preview_cb(self.theme)

    def on_wf(self, _):
        self.theme["wf"] = self.wf_combo.currentData()
        self.preset.setCurrentIndex(0)
        self.preview_cb(self.theme)

    def reject(self):
        self.preview_cb(self.original)
        super().reject()


# --------------------------------------------------------------------------
# Dialogue : statuts manuels
# --------------------------------------------------------------------------
class StatusDialog(QtWidgets.QDialog):
    def __init__(self, parent, statuses):
        super().__init__(parent)
        self.setWindowTitle("Statuts des fréquences")
        self.resize(520, 420)
        self.rows = [dict(name=s["name"], color=s["color"], orig=s["name"], free=bool(s.get("free", False)),
                          on=bool(s.get("on", False))) for s in statuses]
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel("Crée tes propres statuts (libre, occupé, réservé, en test…)\n"
                                       "et choisis leur couleur. Ils s'affectent dans la liste des fréquences.\n"
                                       "Coche « Doit rester libre » : si un signal apparaît sur une fréquence "
                                       "ayant ce statut, tu as une alerte CONFLIT.\n"
                                       "Coche « Doit émettre » : si la fréquence reste sans signal, tu as une alerte "
                                       "ABSENT (micro HF éteint, pile morte, TX coupé…)."))
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nom du statut", "Couleur", "Doit rester libre", "Doit émettre"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self.on_item)
        lay.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("＋ Ajouter")
        add.clicked.connect(self.add_row)
        rem = QtWidgets.QPushButton("Supprimer")
        rem.clicked.connect(self.del_row)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.rebuild()

    def rebuild(self):
        self._busy = True
        self.table.setRowCount(len(self.rows))
        for r, s in enumerate(self.rows):
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(s["name"]))
            b = QtWidgets.QPushButton(s["color"])
            b.setStyleSheet(swatch_style(s["color"]))
            b.clicked.connect(lambda _=False, i=r: self.pick(i))
            self.table.setCellWidget(r, 1, b)
            ck = QtWidgets.QTableWidgetItem("")
            ck.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            ck.setCheckState(Qt.CheckState.Checked if s.get("free") else Qt.CheckState.Unchecked)
            self.table.setItem(r, 2, ck)
            ck2 = QtWidgets.QTableWidgetItem("")
            ck2.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            ck2.setCheckState(Qt.CheckState.Checked if s.get("on") else Qt.CheckState.Unchecked)
            self.table.setItem(r, 3, ck2)
        self._busy = False

    def on_item(self, item):
        if getattr(self, "_busy", False) or item.row() >= len(self.rows):
            return
        if item.column() == 0:
            self.rows[item.row()]["name"] = item.text().strip()
        elif item.column() == 2:
            self.rows[item.row()]["free"] = item.checkState() == Qt.CheckState.Checked
            if self.rows[item.row()]["free"] and self.rows[item.row()].get("on"):
                self.rows[item.row()]["on"] = False         # « libre » et « doit émettre » s'excluent
                QtCore.QTimer.singleShot(0, self.rebuild)
        elif item.column() == 3:
            self.rows[item.row()]["on"] = item.checkState() == Qt.CheckState.Checked
            if self.rows[item.row()]["on"] and self.rows[item.row()].get("free"):
                self.rows[item.row()]["free"] = False
                QtCore.QTimer.singleShot(0, self.rebuild)

    def pick(self, i):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.rows[i]["color"]), self, "Couleur du statut")
        if c.isValid():
            self.rows[i]["color"] = c.name()
            self.rebuild()

    def add_row(self):
        pal = theme_pal(getattr(self.parent(), "theme", None) or {})       # 7.54.1 : palette du thème
        col = pal[(len(self.rows) + 3) % len(pal)]
        self.rows.append(dict(name="Nouveau statut", color=col, orig=None, free=False, on=False))
        self.rebuild()

    def del_row(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.rows):
            self.rows.pop(r)
            self.rebuild()

    def result_rows(self):
        out, seen = [], set()
        for s in self.rows:
            n = s["name"].strip()
            if n and n.lower() not in seen:
                seen.add(n.lower())
                out.append(dict(name=n, color=s["color"], orig=s["orig"], free=bool(s.get("free")),
                                on=bool(s.get("on")) and not bool(s.get("free"))))
        return out


# --------------------------------------------------------------------------
# Dialogue : import CSV intelligent
# --------------------------------------------------------------------------
class ImportDialog(QtWidgets.QDialog):
    def __init__(self, parent, text, source, scenes=None, preset=("", "")):
        super().__init__(parent)
        self.setWindowTitle("Importer des fréquences")
        self.resize(760, 720)
        self.an = analyze_csv(text)
        self.scenes = scenes or []
        self._preset_group = preset[1]
        an = self.an
        lay = QtWidgets.QVBoxLayout(self)
        delim = {";": "point-virgule", "\t": "tabulation", ",": "virgule", None: "lignes libres"}[an["delim"]]
        info = QtWidgets.QLabel(f"<b>{source}</b><br>Format détecté : <b>{an['brand']}</b> · séparateur : {delim} · "
                                f"{len(an['data'])} ligne(s) · en-tête : {'oui' if an['hdr'] is not None else 'non'}")
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.name_combo = QtWidgets.QComboBox()
        self.name_combo.addItem("(aucune : la fréquence sert de nom)", None)
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItem("(aucune)", None)
        self.scene_col_combo = QtWidgets.QComboBox()
        self.scene_col_combo.addItem("(aucune)", None)
        self.group_col_combo = QtWidgets.QComboBox()
        self.group_col_combo.addItem("(aucune)", None)
        for c in range(an["ncol"]):
            lab = f"{c + 1}. {an['headers'][c]}   (ex. {an['samples'][c][:22]})"
            for cb in (self.name_combo, self.status_combo, self.scene_col_combo, self.group_col_combo):
                cb.addItem(lab, c)
        self.name_combo.setCurrentIndex(max(0, self.name_combo.findData(an["name_col"])))
        self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(an["status_col"])))
        self.scene_col_combo.setCurrentIndex(max(0, self.scene_col_combo.findData(an["scene_col"])))
        self.group_col_combo.setCurrentIndex(max(0, self.group_col_combo.findData(an["group_col"])))
        form.addRow("Colonne des noms :", self.name_combo)
        form.addRow("Colonne du statut :", self.status_combo)
        form.addRow("Colonne de la scène :", self.scene_col_combo)
        form.addRow("Colonne du groupe / artiste :", self.group_col_combo)

        self.scene_edit = QtWidgets.QComboBox()
        self.scene_edit.setEditable(True)
        self.scene_edit.addItem("")
        for s in self.scenes:
            self.scene_edit.addItem(s["name"])
        self.scene_edit.setEditText(preset[0])
        self.group_edit = QtWidgets.QComboBox()
        self.group_edit.setEditable(True)
        self.scene_edit.currentTextChanged.connect(self._fill_groups)
        self._fill_groups()
        form.addRow("Affecter tout le fichier à la scène :", self.scene_edit)
        form.addRow("… et au groupe :", self.group_edit)
        lay.addLayout(form)
        tip = QtWidgets.QLabel("Astuce : un fichier par groupe ? Choisis ici sa scène et son groupe (ou tape-les : "
                               "ils seront créés). Les colonnes du fichier, si elles existent, ont priorité.")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        lay.addWidget(QtWidgets.QLabel("Colonnes de fréquence (coche toutes celles à importer) :"))
        self.freq_list = QtWidgets.QListWidget()
        self.freq_list.setMaximumHeight(110)
        for c in range(an["ncol"]):
            it = QtWidgets.QListWidgetItem(f"{c + 1}. {an['headers'][c]}   (ex. {an['samples'][c][:22]})")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if c in an["freq_cols"] else Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, c)
            self.freq_list.addItem(it)
        lay.addWidget(self.freq_list)

        mode = QtWidgets.QHBoxLayout()
        self.r_add = QtWidgets.QRadioButton("Ajouter à ma liste")
        self.r_rep = QtWidgets.QRadioButton("Remplacer ma liste")
        self.r_add.setChecked(True)
        mode.addWidget(self.r_add)
        mode.addWidget(self.r_rep)
        mode.addStretch(1)
        lay.addLayout(mode)

        self.count_lbl = QtWidgets.QLabel("")
        lay.addWidget(self.count_lbl)
        self.prev = QtWidgets.QTableWidget(0, 5)
        self.prev.setHorizontalHeaderLabels(["Nom", "MHz", "Statut", "Scène", "Groupe"])
        self.prev.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.prev.verticalHeader().setVisible(False)
        self.prev.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.prev, 1)

        self.bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)
        for cb in (self.name_combo, self.status_combo, self.scene_col_combo, self.group_col_combo):
            cb.currentIndexChanged.connect(self.refresh)
        self.scene_edit.currentTextChanged.connect(self.refresh)
        self.group_edit.currentTextChanged.connect(self.refresh)
        self.freq_list.itemChanged.connect(self.refresh)
        self.refresh()

    def _fill_groups(self, *_):
        cur = self.group_edit.currentText().strip() or self._preset_group
        self.group_edit.blockSignals(True)
        self.group_edit.clear()
        self.group_edit.addItem("")
        sc = self.scene_edit.currentText().strip()
        for s in self.scenes:
            if s["name"] == sc:
                for g in s["groups"]:
                    self.group_edit.addItem(g["name"])
        self.group_edit.setEditText(cur)
        self.group_edit.blockSignals(False)

    def selection(self):
        fcols = [self.freq_list.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.freq_list.count())
                 if self.freq_list.item(i).checkState() == Qt.CheckState.Checked]
        return self.name_combo.currentData(), fcols, self.status_combo.currentData()

    def entries(self):
        """-> [(nom, MHz, statut, scène, groupe)]"""
        n, f, s = self.selection()
        ent = build_entries_ex(self.an, n, f, s, self.scene_col_combo.currentData(),
                               self.group_col_combo.currentData())
        fs, fg = self.scene_edit.currentText().strip(), self.group_edit.currentText().strip()
        out = []
        for (nm, fr, st, sc, gr) in ent:
            sc, gr = sc or fs, gr or fg
            if gr and not sc:
                sc = DEFAULT_SCENE
            out.append((nm, fr, st, sc, gr))
        return out

    def replace(self):
        return self.r_rep.isChecked()

    def refresh(self, *_):
        e = self.entries()
        self.count_lbl.setText(f"{len(e)} fréquence(s) trouvée(s). Aperçu :")
        self.prev.setRowCount(min(len(e), 40))
        for r, (n, f, s, sc, gr) in enumerate(e[:40]):
            self.prev.setItem(r, 0, QtWidgets.QTableWidgetItem(n))
            it = QtWidgets.QTableWidgetItem(f"{f:.3f}")
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.prev.setItem(r, 1, it)
            self.prev.setItem(r, 2, QtWidgets.QTableWidgetItem(s))
            self.prev.setItem(r, 3, QtWidgets.QTableWidgetItem(sc))
            self.prev.setItem(r, 4, QtWidgets.QTableWidgetItem(gr))
        self.bb.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(len(e) > 0)


# --------------------------------------------------------------------------
# Dialogue : guide des bandes (que contient chaque bande du spectre ?)
# --------------------------------------------------------------------------
class BandGuideDialog(QtWidgets.QDialog):
    def __init__(self, parent, country, plan, tv, theme, add_cb, view_cb):
        super().__init__(parent)
        self.setWindowTitle(f"Guide des bandes – {country}")
        self.resize(1000, 660)
        self.plan, self.tv, self.theme = plan, tv, theme
        self.add_cb, self.view_cb = add_cb, view_cb
        self.shown = []
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Ce qui est attribué dans le spectre que ton tinySA peut balayer (100 kHz – 5,9 GHz), pays par pays. "
            "Plan <b>indicatif</b> : le Tableau national de répartition des fréquences (ANFR, Ofcom, BNetzA, FCC…) "
            "fait foi. Ici on ne fait que <b>mesurer des niveaux</b> : rien n'est décodé.")
        info.setWordWrap(True)
        lay.addWidget(info)
        top = QtWidgets.QHBoxLayout()
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Attributions du spectre", "plan")
        self.src_combo.addItem("Canaux TV", "tv")
        self.cat_combo = QtWidgets.QComboBox()
        self.cat_combo.addItem("Toutes les catégories", None)
        for k, (lab, _c) in CATEGORIES.items():
            self.cat_combo.addItem(lab, k)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("🔎 Un usage ou une fréquence : police, 4G, CB, ADS-B, 868, 446…")
        self.search.setClearButtonEnabled(True)
        top.addWidget(self.src_combo)
        top.addWidget(self.cat_combo)
        top.addWidget(self.search, 1)
        lay.addLayout(top)
        self.count_lbl = QtWidgets.QLabel("")
        lay.addWidget(self.count_lbl)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Début", "Fin", "Catégorie", "Usage", "Note"])
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 95)
        self.table.setColumnWidth(1, 95)
        self.table.setColumnWidth(2, 190)
        self.table.setColumnWidth(4, 260)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_view())
        lay.addWidget(self.table, 1)
        self.msg = QtWidgets.QLabel("Sélectionne une ligne : « Voir » zoome dessus, « Ajouter » l'ajoute à tes bandes à balayer.")
        lay.addWidget(self.msg)
        row = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("＋ Ajouter aux bandes à balayer")
        b_add.clicked.connect(self.on_add)
        b_view = QtWidgets.QPushButton("🔍 Voir sur le spectre")
        b_view.clicked.connect(self.on_view)
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        row.addWidget(b_add)
        row.addWidget(b_view)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.src_combo.currentIndexChanged.connect(self.refresh)
        self.cat_combo.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        entries = self.plan if self.src_combo.currentData() == "plan" else self.tv
        cat = self.cat_combo.currentData()
        txt = self.search.text().strip().lower()
        try:
            fnum = float(txt.replace(",", "."))
        except ValueError:
            fnum = None
        self.shown = []
        for e in entries:
            a, b, lab, c, note = e
            if cat and c != cat:
                continue
            if txt:
                hay = f"{lab} {note} {CATEGORIES.get(c, ('',))[0]}".lower()
                if not (txt in hay or (fnum is not None and a <= fnum < b)):
                    continue
            self.shown.append(e)
        t, th = self.table, self.theme
        t.setRowCount(len(self.shown))
        for r, (a, b, lab, c, note) in enumerate(self.shown):
            col = th.get("bp_" + c, "#64748b")
            vals = (fmt_freq_mhz(a), fmt_freq_mhz(b), CATEGORIES.get(c, ("?",))[0], lab, note)
            for k, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if k == 2:
                    it.setBackground(QtGui.QColor(col))
                    it.setForeground(QtGui.QColor(contrast_text(col)))
                it.setToolTip(f"{a:g} – {b:g} MHz\n{lab}" + (f"\n{note}" if note else ""))
                t.setItem(r, k, it)
        self.count_lbl.setText(f"{len(self.shown)} ligne(s)")

    def _current(self):
        r = self.table.currentRow()
        return self.shown[r] if 0 <= r < len(self.shown) else None

    def on_add(self):
        e = self._current()
        if e is None:
            self.msg.setText("Sélectionne d'abord une ligne.")
            return
        self.add_cb(e[2], e[0], e[1])
        self.msg.setText(f"« {e[2]} » ajoutée aux bandes à balayer.")

    def on_view(self):
        e = self._current()
        if e is not None:
            self.view_cb(e[0], e[1])


# --------------------------------------------------------------------------
# Dialogue : plan de fréquences personnalisé
# --------------------------------------------------------------------------
class PlanDialog(QtWidgets.QDialog):
    def __init__(self, parent, country, text):
        super().__init__(parent)
        self.setWindowTitle(f"Plan de fréquences : {country}")
        self.resize(780, 560)
        self.reset = False
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Une ligne par attribution :   début-fin (MHz) | catégorie | libellé | note (facultative)\n"
            "Catégories : " + ", ".join(CATEGORIES) + "\n"
            "Les plans fournis sont indicatifs : corrige-les avec les infos de ton régulateur "
            "(ANFR, Ofcom, BNetzA, FCC…). Les plages les plus étroites sont prioritaires à l'affichage.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.edit = QtWidgets.QPlainTextEdit(text)
        self.edit.setStyleSheet("font-family:Consolas,monospace;")
        self.edit.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.edit, 1)
        row = QtWidgets.QHBoxLayout()
        b_reset = QtWidgets.QPushButton("Rétablir le plan d'origine")
        b_reset.clicked.connect(self.on_reset)
        row.addWidget(b_reset)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def on_reset(self):
        self.reset = True
        super().accept()

    def accept(self):
        if not parse_plan_text(self.edit.toPlainText()):
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Aucune ligne valide.\nExemple :  470-694|tv|TNT|ma note")
            return
        super().accept()

    def result_text(self):
        return "" if self.reset else self.edit.toPlainText()


# --------------------------------------------------------------------------
# Dialogue : export du scan en CSV
# --------------------------------------------------------------------------
class _DelKeyFilter(QtCore.QObject):
    """Suppr (ou Retour arrière) sur une liste / un tableau, hors saisie dans une cellule : appelle fn. Un filtre plutôt
    qu'un QShortcut : les vues d'éléments gardent la touche pour elles (raccourci jamais déclenché)."""

    def __init__(self, view, fn):
        super().__init__(view)
        self.view, self.fn = view, fn

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Type.KeyPress and ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) \
                and not ev.modifiers() & ~Qt.KeyboardModifier.KeypadModifier:
            st = getattr(self.view, "state", None)
            if st is None or st() != QtWidgets.QAbstractItemView.State.EditingState:
                self.fn()
                return True
        return False


def del_key(widget, fn):
    """Touche Suppr sur une liste / un tableau : appelle fn (seulement quand ce widget a le focus)."""
    f = _DelKeyFilter(widget, fn)
    widget.installEventFilter(f)
    widget._del_filter = f                       # gardé en vie avec le widget
    return f


class RangeBox(QtWidgets.QWidget):
    """Plage de fréquences à exporter (vers le logiciel de coord, WWB, WSM…) : tout, la zone affichée, une de mes bandes, la plage
    d'un appareil de la bibliothèque, ou « de … à … » à la main. values() -> (lo, hi) en MHz, ou (None, None) = tout."""

    def __init__(self, owner, extent=None):
        super().__init__()
        self.owner = owner
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.preset = QtWidgets.QComboBox()
        self.preset.setToolTip("Quelle partie du scan exporter. Une bande, la zone affichée sur le spectre, la plage d'un\n"
                               "appareil, ou des valeurs à la main.")
        self.preset.addItem("Tout le scan", None)
        try:
            vr = owner.spec.getPlotItem().vb.viewRange()[0]
            self.preset.addItem(f"Zone affichée sur le spectre ({vr[0]:.1f}–{vr[1]:.1f} MHz)", (float(vr[0]), float(vr[1])))
        except Exception:  # noqa: BLE001 — pas de spectre (tests)
            pass
        for b in getattr(owner, "bands", []):
            self.preset.addItem(f"Bande « {b['name']} » ({b['start']:g}–{b['stop']:g} MHz)",
                                (float(b["start"]), float(b["stop"])))
        for k, n, d, _w in rx_all():
            if d.get("hi", 0) > d.get("lo", 0) > 0:
                self.preset.addItem(f"Appareil {n} ({d['lo']:g}–{d['hi']:g} MHz)", (float(d["lo"]), float(d["hi"])))
        self.preset.addItem("À la main…", "custom")
        self.lo, self.hi = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        ext = extent or (470.0, 694.0)
        for sp_, v in ((self.lo, ext[0]), (self.hi, ext[1])):
            sp_.setDecimals(3)
            sp_.setRange(0.0, 7000.0)
            sp_.setSuffix(" MHz")
            sp_.setValue(v)
            sp_.setToolTip("Début et fin de la plage exportée.")
        self.preset.currentIndexChanged.connect(lambda *_: self._sync())
        for sp_ in (self.lo, self.hi):
            sp_.valueChanged.connect(lambda *_: self._manual())
        lay.addWidget(self.preset, 1)
        lay.addWidget(self.lo)
        lay.addWidget(QtWidgets.QLabel("à"))
        lay.addWidget(self.hi)
        self._sync()

    def _sync(self):
        d = self.preset.currentData()
        if isinstance(d, tuple):
            for sp_, v in ((self.lo, d[0]), (self.hi, d[1])):
                sp_.blockSignals(True)
                sp_.setValue(v)
                sp_.blockSignals(False)
        for sp_ in (self.lo, self.hi):
            sp_.setEnabled(d is not None)

    def _manual(self):
        ix = self.preset.findData("custom")
        if self.preset.currentIndex() != ix:
            self.preset.blockSignals(True)
            self.preset.setCurrentIndex(ix)
            self.preset.blockSignals(False)

    def values(self):
        if self.preset.currentData() is None:
            return None, None
        return self.lo.value(), self.hi.value()

    def select(self, lo, hi):
        """Choisit une plage à la main (tests, préférences)."""
        self.preset.setCurrentIndex(self.preset.findData("custom"))
        self.lo.setValue(lo)
        self.hi.setValue(hi)


class ExportScanDialog(QtWidgets.QDialog):
    def __init__(self, parent, prefs):
        super().__init__(parent)
        self.setWindowTitle("Exporter le scan en CSV")
        self.resize(560, 320)
        p = prefs or {}
        form = QtWidgets.QFormLayout(self)

        def combo(items, cur):
            c = QtWidgets.QComboBox()
            for txt, data in items:
                c.addItem(txt, data)
            c.setCurrentIndex(max(0, c.findData(cur)))
            return c

        self.src = combo([("Balayage actuel", "live"), ("Max hold", "max"),
                          ("Les deux (2 colonnes)", "both")], p.get("src", "live"))
        self.scope = combo([("Bande affichée", "view"), ("Toutes les bandes activées", "all")],
                           p.get("scope", "view"))
        self.unit = combo([("MHz", "MHz"), ("kHz", "kHz"), ("Hz", "Hz")], p.get("unit", "MHz"))
        self.delim = combo([(k, v) for k, v in DELIMS.items()], p.get("delim", ";"))
        self.dec = combo([(". (point)", "."), (", (virgule)", ",")], p.get("dec", ","))
        self.header = QtWidgets.QCheckBox("Ligne d'en-tête")
        self.header.setChecked(p.get("header", True))
        self.range = RangeBox(parent)
        form.addRow("Contenu :", self.src)
        form.addRow("Bandes :", self.scope)
        form.addRow("Plage :", self.range)
        form.addRow("Unité des fréquences :", self.unit)
        form.addRow("Séparateur de colonnes :", self.delim)
        form.addRow("Séparateur décimal :", self.dec)
        form.addRow("", self.header)
        note = QtWidgets.QLabel("Excel français : MHz, « ; » et virgule. Autres logiciels : essaie kHz ou Hz avec "
                                "point décimal. Le format exact attendu par WWB / WSM dépend de ta version : "
                                "envoie-moi un exemple et je l'ajoute en un clic.")
        note.setWordWrap(True)
        form.addRow(note)
        if hasattr(parent, "live_rbw"):              # 📏 scan pour la coordination : RBW fine
            rb, est = parent.live_rbw()
            txt, ok = rbw_coord_line(rb, est, TR, step=max((scan_step_khz(v[0]) or 0.0
                                                             for v in parent.latest.values()), default=None))
            rbl = QtWidgets.QLabel(txt)
            rbl.setWordWrap(True)
            rbl.setToolTip(COORD_RBW_TIP)
            if not ok:
                rbl.setStyleSheet(f"color: {parent.theme.get('st_weak', '#f59e0b')};")
            form.addRow(rbl)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self):
        lo, hi = self.range.values()
        return dict(src=self.src.currentData(), scope=self.scope.currentData(), unit=self.unit.currentData(),
                    delim=self.delim.currentData(), dec=self.dec.currentData(),
                    header=self.header.isChecked(), lo=lo, hi=hi)


# --------------------------------------------------------------------------
# Saisie assistée : nom avec auto-complétion
# --------------------------------------------------------------------------
def make_completer(words, parent):
    comp = QtWidgets.QCompleter(list(words), parent)
    comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    comp.setFilterMode(Qt.MatchFlag.MatchContains)
    comp.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
    return comp


class NameDialog(QtWidgets.QDialog):
    """Saisie d'un nom (scène, groupe, fréquence) avec propositions pendant la frappe."""
    def __init__(self, parent, title, label, words, text=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(430, 130)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(label))
        self.edit = QtWidgets.QLineEdit()
        self.edit.setText(text)
        self.edit.setCompleter(make_completer(words, self.edit))
        lay.addWidget(self.edit)
        lay.addWidget(QtWidgets.QLabel("Tape les premières lettres : des propositions apparaissent."))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def value(self):
        return self.edit.text().strip()


class NameDelegate(QtWidgets.QStyledItemDelegate):
    """Éditeur de la colonne « Nom » : propose les mots de base, le prochain numéro libre (HF 5…) et les noms déjà utilisés."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def createEditor(self, parent, option, index):
        ed = QtWidgets.QLineEdit(parent)
        ed.setCompleter(make_completer(self.owner.name_suggestions(), ed))
        return ed


class QuickNameDialog(QtWidgets.QDialog):
    """Nommer toute la sélection d'un coup : un mot de base + numérotation automatique (HF 1, HF 2, HF 3…)."""
    def __init__(self, owner, rows):
        super().__init__(owner)
        self.owner, self.rows = owner, list(rows)
        self.setWindowTitle("Nommer la sélection")
        self.resize(560, 640)
        rs = set(self.rows)
        self._others = [w["name"] for i, w in enumerate(owner.watch) if i not in rs]
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(f"<b>{len(self.rows)}</b> fréquence(s) à nommer, dans l'ordre des fréquences."))
        form = QtWidgets.QFormLayout()
        self.base_combo = QtWidgets.QComboBox()
        self.base_combo.setEditable(True)
        self.base_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        words = owner.vocab_all("name")
        for w in words:
            self.base_combo.addItem(w)
        self.base_combo.setCompleter(make_completer(words, self.base_combo))
        self.base_combo.setEditText("HF")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Numéroter : HF 1, HF 2, HF 3…", "num")
        self.mode_combo.addItem("Même nom pour toutes : HF", "same")
        self.auto_chk = QtWidgets.QCheckBox("Commencer au prochain numéro libre pour ce mot")
        self.auto_chk.setChecked(True)
        self.start_spin = QtWidgets.QSpinBox()
        self.start_spin.setRange(0, 9999)
        self.start_spin.setValue(1)
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(0, 4)
        self.width_spin.setToolTip("0 : HF 1   ·   2 : HF 01")
        self.sep_combo = QtWidgets.QComboBox()
        for lab, v in (("espace  (HF 1)", " "), ("rien  (HF1)", ""), ("tiret  (HF-1)", "-"), ("souligné  (HF_1)", "_")):
            self.sep_combo.addItem(lab, v)
        self.rev_chk = QtWidgets.QCheckBox("Du plus haut au plus bas en fréquence")
        self.learn_chk = QtWidgets.QCheckBox("Retenir ce mot dans mon vocabulaire")
        self.base_combo.setToolTip("Tape un mot (HF, MIC, IEM, Bolero…) : il est numéroté tout seul.\n"
                                   "Tape « HF 5 » pour démarrer à 5.")
        self.learn_chk.setChecked(True)
        form.addRow("Mot :", self.base_combo)
        form.addRow("Mode :", self.mode_combo)
        form.addRow(self.auto_chk)
        form.addRow("Premier numéro :", self.start_spin)
        form.addRow("Zéros de remplissage :", self.width_spin)
        form.addRow("Séparateur :", self.sep_combo)
        form.addRow(self.rev_chk)
        form.addRow(self.learn_chk)
        lay.addLayout(form)
        lay.addWidget(QtWidgets.QLabel("Aperçu :"))
        self.prev = QtWidgets.QTableWidget(0, 3)
        self.prev.setHorizontalHeaderLabels(["MHz", "Avant", "Après"])
        self.prev.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.prev.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.prev.verticalHeader().setVisible(False)
        self.prev.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.prev, 1)
        self.bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)
        self.base_combo.currentTextChanged.connect(self._on_base)
        self.auto_chk.toggled.connect(self._on_base)
        for w in (self.mode_combo, self.sep_combo):
            w.currentIndexChanged.connect(self.refresh)
        self.start_spin.valueChanged.connect(self.refresh)
        self.width_spin.valueChanged.connect(self.refresh)
        self.rev_chk.toggled.connect(self.refresh)
        self._on_base()

    def base(self):
        return self.base_combo.currentText().strip()

    def _split(self):
        """Ce qui est tapé dans « Mot » : « HF » ou « HF 5 » (le numéro tapé devient le point de départ)."""
        b = self.base()
        return parse_label(b) if b else ("", " ", None, 0)

    def word(self):
        return self._split()[0]

    def _on_base(self, *_):
        b, _sep, n0, _wd = self._split()
        if n0 is not None:
            self.auto_chk.setEnabled(False)
            self.start_spin.setEnabled(False)
            self.start_spin.setValue(n0)
        else:
            self.auto_chk.setEnabled(True)
            self.start_spin.setEnabled(not self.auto_chk.isChecked())
            if self.auto_chk.isChecked() and b:
                self.start_spin.setValue(next_free_number(b, self._others))
        self.refresh()

    def names(self):
        base, n = self.base(), len(self.rows)
        if not base:
            return None
        if self.mode_combo.currentData() == "same":
            return [base] * n
        b, sep0, n0, wd0 = self._split()
        if n0 is not None:
            base, start, wd, sep = b, n0, (wd0 or self.width_spin.value()), sep0
        else:
            start, wd, sep = self.start_spin.value(), self.width_spin.value(), self.sep_combo.currentData()
        labs = [make_label(base, start + i, wd, sep) for i in range(n)]
        if self.rev_chk.isChecked():
            labs.reverse()
        return labs

    def refresh(self, *_):
        new = self.names()
        ok = new is not None
        self.bb.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(ok)
        shown = list(range(len(self.rows)))
        if len(shown) > 14:
            shown = shown[:7] + shown[-7:]
        self.prev.setRowCount(len(shown))
        for r, k in enumerate(shown):
            w = self.owner.watch[self.rows[k]]
            self.prev.setItem(r, 0, QtWidgets.QTableWidgetItem(f'{w["freq"]:.3f}'))
            self.prev.setItem(r, 1, QtWidgets.QTableWidgetItem(w["name"]))
            self.prev.setItem(r, 2, QtWidgets.QTableWidgetItem(new[k] if ok else ""))


# --------------------------------------------------------------------------
# Dialogue : intermodulation (2 / 3 / 5 TX) et origine d'un signal
# --------------------------------------------------------------------------
def fill_rules_combo(combo):
    """Règles d'intermod dans une liste : nom + explication en bulle, et « Personnalisé » à la fin."""
    for txt, d, why in IM_TOL_PRESETS:
        combo.addItem(txt, d)
        combo.setItemData(combo.count() - 1, why, Qt.ItemDataRole.ToolTipRole)
    combo.addItem(IM_TOL_CUSTOM, None)
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(max(len(t) for t, _d, _w in IM_TOL_PRESETS) + 2)
    combo.setItemData(combo.count() - 1, "Tes tolérances à toi (0 = type ignoré).", Qt.ItemDataRole.ToolTipRole)


class IntermodDialog(QtWidgets.QDialog):
    def __init__(self, owner, origin=None):
        super().__init__(owner)
        self.owner = owner
        self.rows = []
        self.setWindowTitle("Intermodulation : d'où ça peut venir ?")
        self.resize(1040, 720)
        R = owner._row
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(coord_note())
        info = QtWidgets.QLabel(
            "Calcule les produits d'intermodulation de tes émetteurs (les fréquences de la liste) : 2 TX → 2A − B ; "
            "3 TX → A + B − C ; 5 TX → A + B + C − D − E… Tu vois quelle combinaison peut retomber sur une de tes "
            "fréquences, ou expliquer un signal inconnu vu sur le spectre. C'est un calcul théorique : il ne dit "
            "pas quel appareil (émetteur, ampli d'antenne, combiner…) le fabrique vraiment. Blocs larges "
            "(Spectera / WMAS) : leurs produits sont des bandes (« 540.000 ± 8.0 »), comptées bord à bord.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Calculer les produits : qui tombe sur quoi ?", "calc")
        self.mode_combo.addItem("Chercher l'origine d'un signal à…", "origin")
        self.freq_spin = QtWidgets.QDoubleSpinBox()
        self.freq_spin.setDecimals(3)
        self.freq_spin.setRange(0.1, 6000.0)
        self.freq_spin.setValue(origin if origin else 500.0)
        self.freq_spin.setSuffix(" MHz")
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Émetteurs : toute la liste (sauf « doit rester libre »)", "all")
        self.src_combo.addItem("Émetteurs : la couche active", "scope")
        self.src_combo.addItem("Émetteurs : les lignes sélectionnées", "sel")
        self.src_combo.addItem("Émetteurs : les signaux VUS sur le spectre (pics mesurés)", "spectrum")
        self.src_combo.setItemData(3, "Pas besoin que les émetteurs soient déclarés : on prend les pics réellement "
                                      "mesurés\n(max hold, au-dessus du seuil « faible »), y compris ceux qui ne sont "
                                      "pas dans ta liste.", Qt.ItemDataRole.ToolTipRole)
        self.active_chk = QtWidgets.QCheckBox("Seulement ceux qui émettent (vus sur le spectre)")
        self.active_chk.setToolTip("Un produit n'existe que si les émetteurs sont allumés : on ne garde que ceux "
                                   "dont l'état est « occupé » ou « faible ».")
        self.src_lbl = QtWidgets.QLabel("")
        self.maxtx_combo = QtWidgets.QComboBox()
        self.maxtx_combo.addItem("2 TX  (2A − B)", 2)
        self.maxtx_combo.addItem("jusqu'à 3 TX  (2A − B, A + B − C)", 3)
        self.maxtx_combo.addItem("jusqu'à 5 TX  (… A + B + C − D − E)", 5)
        self.maxtx_combo.setCurrentIndex(1)
        self.o3_chk = QtWidgets.QCheckBox("3ᵉ ordre")
        self.o3_chk.setChecked(True)
        self.o5_chk = QtWidgets.QCheckBox("5ᵉ ordre")
        self.o7_chk = QtWidgets.QCheckBox("7ᵉ ordre")
        self.tgt_combo = QtWidgets.QComboBox()
        self.tgt_combo.addItem("Protéger : toutes les fréquences de la liste", "all")
        self.tgt_combo.addItem("Protéger : la couche active seulement", "scope")
        self.tgt_combo.addItem("Aucune cible : lister tous les produits dans la plage", "none")
        # tolérances par type de produit (un 2A − B est bien plus fort qu'un A + B − C)
        self.tol_spins = {}
        for key, tip in (("2tx3", "2 TX, 3ᵉ ordre (2A − B) : le produit le plus fort."),
                         ("3tx3", "3 TX, 3ᵉ ordre (A + B − C) : plus faible, tolérance plus serrée."),
                         ("5", "5ᵉ ordre et au-delà (3A − 2B, 2A + B − 2C…) : faibles.")):
            sp = QtWidgets.QSpinBox()
            sp.setRange(0, 2000)
            sp.setSingleStep(10)
            sp.setSuffix(" kHz")
            sp.setPrefix("± ")
            sp.setSpecialValueText("ignoré")            # 0 = ce type de produit n'est pas compté
            sp.setToolTip(tip + "\nUn produit plus loin que ça de ta fréquence est accepté (comme les tolérances "
                                "des logiciels de coordination).\n0 = « ignoré » : ce type de produit n'est pas compté du tout.")
            self.tol_spins[key] = sp
        self.tol_combo = QtWidgets.QComboBox()
        fill_rules_combo(self.tol_combo)
        self.tol_combo.setToolTip("Quels produits comptent, et à quelle distance de ta fréquence (survole chaque choix).\n"
                                  "Standard = les tolérances les plus courantes (2 TX 100 kHz, 3 TX 50 kHz).")
        self.tol_combo.currentIndexChanged.connect(lambda *_: self._tol_preset())
        self.filt_spin = QtWidgets.QDoubleSpinBox()
        self.filt_spin.setRange(0, 400)
        self.filt_spin.setDecimals(0)
        self.filt_spin.setSingleStep(4)
        self.filt_spin.setSuffix(" MHz")
        self.filt_spin.setSpecialValueText("aucun")
        self.filt_spin.setValue(float(owner.plan_opts["filt"]))
        self.filt_spin.setToolTip("Filtre d'entrée du récepteur (32 MHz pour un Wisycom) : un "
                                  "produit ne compte sur une fréquence\nque si tous ses émetteurs sont à ± la valeur du "
                                  "filtre autour d'elle. aucun = tous comptent.\nSans effet en « aucune cible ».")
        self._tol_preset()
        for sp in self.tol_spins.values():
            sp.valueChanged.connect(lambda *_: self._tol_custom())
        bands = [b for b in owner.bands if b["enabled"]]
        self.fmin_spin = QtWidgets.QDoubleSpinBox()
        self.fmax_spin = QtWidgets.QDoubleSpinBox()
        for sp in (self.fmin_spin, self.fmax_spin):
            sp.setDecimals(3)
            sp.setRange(0.1, 6000.0)
            sp.setSuffix(" MHz")
        self.fmin_spin.setValue(min((b["start"] for b in bands), default=470.0))
        self.fmax_spin.setValue(max((b["stop"] for b in bands), default=694.0))
        self.go_btn = QtWidgets.QPushButton("⚡ Calculer")
        self.go_btn.clicked.connect(lambda *_: self.compute())
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addLayout(R("Mode :", self.mode_combo, self.freq_spin, None))
        lay.addLayout(R(self.src_combo, self.active_chk, self.src_lbl, None))
        lay.addLayout(R("Combinaisons :", self.maxtx_combo, self.o3_chk, self.o5_chk, self.o7_chk, None))
        lay.addLayout(R(self.tgt_combo, "Règles :", self.tol_combo, None))
        lay.addLayout(R("2 TX :", self.tol_spins["2tx3"], "3 TX :", self.tol_spins["3tx3"],
                        "5ᵉ / 7ᵉ ordre :", self.tol_spins["5"], "Filtre :", self.filt_spin, filter_help_btn(self), None))
        lay.addLayout(R("Plage (liste complète) :", self.fmin_spin, "à", self.fmax_spin, None, self.go_btn))
        lay.addWidget(self.msg)
        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Produit MHz", "Ordre", "Origine (émetteurs)", "Tombe sur", "Écart kHz",
                                              "Mesuré dBm", "Verdict"])
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for c, w in ((0, 96), (1, 92), (3, 190), (4, 76), (5, 88), (6, 240)):
            self.table.setColumnWidth(c, w)
        for c, tip in ((1, "IM3 = 3ᵉ ordre, IM5 = 5ᵉ ordre ; « 2 TX » = 2 émetteurs (2A − B : le plus fort),\n"
                           "« 3 TX » = A + B − C (plus faible), etc."),
                       (4, "Écart entre le produit calculé et ta fréquence (0 = pile dessus)."),
                       (5, "Ce que le tinySA mesure EN CE MOMENT à cet endroit (pas la force du produit)."),
                       (6, "🔴 problème : on mesure un signal au-dessus de ton seuil « occupé » là où le produit tombe.\n"
                           "🟠 à vérifier : on mesure de l'énergie (au-dessus du seuil « faible »).\n"
                           "🟡 à surveiller : rien de mesuré, mais c'est un IM3 à 2 émetteurs (2A − B, le plus fort).\n"
                           "⚪ faible risque : rien de mesuré, produit plus faible (A + B − C, 5ᵉ ordre…).\n"
                           "Le calcul ne dit pas si c'est audible : ça dépend de la puissance, des distances et des\n"
                           "récepteurs. « cible en émission » : on ne peut pas mesurer sous sa propre porteuse.")):
            self.table.horizontalHeaderItem(c).setToolTip(tip)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_zoom())
        lay.addWidget(self.table, 1)
        b_zoom = QtWidgets.QPushButton("🔍 Voir le produit sur le spectre")
        b_zoom.clicked.connect(lambda *_: self.on_zoom())
        b_watch = QtWidgets.QPushButton("👁 Surveiller les produits sélectionnés")
        b_watch.setToolTip("Ajoute les lignes sélectionnées à ta liste (scène « Intermod »), statut « Libre » :\n"
                           "si de l'énergie apparaît dessus, ça déclenche ⚠ CONFLIT.")
        b_watch.clicked.connect(lambda *_: self.on_watch())
        b_csv = QtWidgets.QPushButton("💾 Exporter CSV…")
        b_csv.clicked.connect(lambda *_: self.on_csv())
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        lay.addLayout(R(b_zoom, b_watch, b_csv, None, b_close))
        for w in (self.src_combo,):
            w.currentIndexChanged.connect(self.update_src)
        self.active_chk.toggled.connect(self.update_src)
        self.mode_combo.currentIndexChanged.connect(self.on_mode)
        if origin:
            self.mode_combo.setCurrentIndex(1)
        else:
            self.on_mode()
        self.update_src()

    def on_mode(self, *_):
        origin = self.mode_combo.currentData() == "origin"
        self.freq_spin.setEnabled(origin)
        self.tgt_combo.setEnabled(not origin)
        if origin:
            self.o5_chk.setChecked(True)
            self.maxtx_combo.setCurrentIndex(2)
            n_act = sum(1 for w in self.owner.watch if w["state"] in ("occ", "weak"))
            self.active_chk.setChecked(n_act >= 2)
            if len(self.spectrum_sources()) >= 2:   # chercher dans ce qui est VRAIMENT là, déclaré ou pas
                self.src_combo.setCurrentIndex(self.src_combo.findData("spectrum"))
        self.update_src()

    def spectrum_sources(self):
        """Pics réellement mesurés (max hold, au-dessus du seuil « faible » ou « occupé ») -> [(MHz, dBm, nom)].
        Un pic à ±100 kHz d'une fréquence de la liste prend son nom ; en recherche d'origine, le signal cherché
        lui-même est écarté."""
        o = self.owner
        F, L = o.fresh_FL(use_max=True, any_age=True)
        if F is None:
            return []
        thr = o.weak_spin.value() if o.weak_chk.isChecked() else o.thr_spin.value()
        pk = strong_peaks(F, L, thr, merge=0.2, limit=80)
        if self.mode_combo.currentData() == "origin":
            f0 = self.freq_spin.value()
            pk = [(f, l) for f, l in pk if abs(f - f0) > 0.1]
            pk.sort(key=lambda p_: (abs(p_[0] - f0) > 50.0, -p_[1]))     # d'abord les voisins (±50 MHz)
        pk = pk[:24]                                # les plus forts : ce sont eux qui intermodulent
        out = []
        for f, l in sorted(pk):
            near_ = (np.abs(F - f) <= 0.1) & (L >= l - 3.0)     # centre du pic (plateau de quelques points)
            if near_.any():
                f = float(np.mean(F[near_]))
            near = min(o.watch, key=lambda w: abs(w["freq"] - f), default=None)
            nm = near["name"] if near is not None and abs(near["freq"] - f) <= 0.1 else f"pic {f:.3f}"
            out.append((f, l, nm))
        return out

    def source_indices(self):
        o = self.owner
        kind = self.src_combo.currentData()
        if kind == "spectrum":
            return []
        if kind == "sel":
            idx = o._sel_rows()
        elif kind == "scope":
            idx = [i for i, w in enumerate(o.watch) if o.in_scope(w)]
        else:
            idx = list(range(len(o.watch)))
        if kind != "sel":                   # une réserve « doit rester libre » n'émet pas : pas un émetteur
            idx = [i for i in idx if not o.is_keep_free(o.watch[i]["status"])]
        if self.active_chk.isChecked():
            idx = [i for i in idx if o.watch[i]["state"] in ("occ", "weak")]
        return idx

    def update_src(self, *_):
        sp = self.src_combo.currentData() == "spectrum"
        self.active_chk.setEnabled(not sp)
        n = len(self.spectrum_sources()) if sp else len(self.source_indices())
        self.src_lbl.setText(f"→ {n} " + ("signal(aux) mesuré(s)" if sp else "émetteur(s)"))

    def _tol_preset(self):
        d = self.tol_combo.currentData()
        if d is None:
            return
        self._applying = True
        for k, sp in self.tol_spins.items():
            sp.setValue(int(round(d[k] * 1000)))
        self._applying = False

    def _tol_custom(self):
        if getattr(self, "_applying", False):
            return
        self.tol_combo.blockSignals(True)
        self.tol_combo.setCurrentIndex(self.tol_combo.count() - 1)
        self.tol_combo.blockSignals(False)

    def tolerances(self):
        """-> dict pour im_scan (MHz) : 2 TX, 3 TX, 5ᵉ et 7ᵉ ordre."""
        t5 = self.tol_spins["5"].value() / 1000.0
        return {"2tx3": self.tol_spins["2tx3"].value() / 1000.0, "3tx3": self.tol_spins["3tx3"].value() / 1000.0,
                "5": t5, "7": t5}

    def orders(self):
        out = tuple(x for x, c in ((3, self.o3_chk), (5, self.o5_chk), (7, self.o7_chk)) if c.isChecked())
        return out or (3,)

    def compute(self):
        o = self.owner
        if self.src_combo.currentData() == "spectrum":
            src = self.spectrum_sources()
            freqs, names, bws = [x[0] for x in src], [x[2] for x in src], [0.0] * len(src)
            if len(freqs) < 2:
                self.msg.setText("Moins de 2 signaux mesurés au-dessus du seuil « faible » : lance un balayage et "
                                 "laisse tourner un moment (le max hold garde les signaux intermittents).")
                return
        else:
            idx = self.source_indices()
            freqs = [o.watch[i]["freq"] for i in idx]
            names = [o.watch[i]["name"] for i in idx]
            bws = [float(o.watch[i].get("bw") or 0.0) for i in idx]    # blocs Spectera / WMAS : produits en bandes
        orders, max_tx, guard = self.orders(), self.maxtx_combo.currentData(), self.tolerances()
        if len(freqs) < 2:
            self.msg.setText("Il faut au moins 2 émetteurs (change la source ou décoche « seulement ceux qui émettent »).")
            return
        pairs = sum(im_pairs(len(freqs), x, max_tx) for x in orders)
        if pairs > IM_MAX_PAIRS:
            self.msg.setText((f"Trop de combinaisons ({pairs:,}) pour {len(freqs)} émetteurs. Essaie : « 2 TX » (rapide "
                              f"même avec des centaines de fréquences), « seulement ceux qui émettent », une couche plus "
                              f"petite, ou retire les ordres 5 / 7 qui sont les plus gourmands.").replace(",", " "))
            return
        origin = self.mode_combo.currentData() == "origin"
        tbws = None
        if origin:
            targets, fmin, fmax = [self.freq_spin.value()], 0.1, 6000.0
        else:
            tm = self.tgt_combo.currentData()
            fmin, fmax = self.fmin_spin.value(), self.fmax_spin.value()
            tw = o.watch if tm == "all" else (o.scope_ws() if tm == "scope" else None)
            if tw is not None:
                targets, fmin, fmax = [w["freq"] for w in tw], 0.1, 6000.0
                tbws = [float(w.get("bw") or 0.0) for w in tw]
            else:
                targets = None
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rows, info = im_scan(freqs, orders, max_tx, targets, guard, fmin, fmax, limit=5000, bws=bws, tbws=tbws)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        filt = self.filt_spin.value()
        o.plan_opts["filt"] = filt
        if filt > 0:                    # émetteurs hors du filtre du récepteur visé : produit coupé
            rows = [r for r in rows if r["target"] is None
                    or all(abs(freqs[i] - r["target"]) <= filt + 1e-9 for i, _c in r["terms"])]
        F, L = o.fresh_FL()
        win = max(0.05, o.win_spin.value() / 1000.0)
        thr, weak = o.thr_spin.value(), o.weak_spin.value()
        by_freq = {int(round(w["freq"] * 1000)): w["name"] for w in o.watch}
        by_w = {int(round(w["freq"] * 1000)): w for w in o.watch}
        for r in rows:
            r["text"] = im_formula(r["terms"], names)
            r["numtext"] = im_formula(r["terms"], freqs=freqs, numeric=True)
            tw_ = None if (r["target"] is None or origin) else by_w.get(int(round(r["target"] * 1000)))
            masked = tw_ is not None and tw_["state"] in ("occ", "weak") and o.is_keep_on(tw_["status"])
            if F is None or masked:     # la cible émet : on mesurerait sa propre porteuse, pas le produit
                r["meas"] = None
            elif tw_ is not None:       # niveau là où ça gêne : sur la fréquence (ou le bloc) protégée
                tb_ = float(tw_.get("bw") or 0.0)
                r["meas"] = (level_block(F, L, tw_["freq"], tb_, "max") if tb_ else level_at(F, L, tw_["freq"], win))
            elif r["hw"] > 0.05:        # produit large sans cible : son « plateau »
                r["meas"] = level_block(F, L, r["f"], 2 * r["hw"], "median")
            else:
                r["meas"] = level_at(F, L, r["f"], win)
            r["masked"] = masked
            if r["target"] is None:
                r["tname"] = ""
            elif origin:
                r["tname"] = f"signal à {r['target']:.3f}"
            else:
                r["tname"] = f"{by_freq.get(int(round(r['target'] * 1000)), '?')} ({r['target']:.3f})"
            if r["target"] is not None and not origin:
                r["sev"], r["verdict"] = im_verdict(r["meas"], thr, weak, o.weak_chk.isChecked(), r["order"],
                                                    r["ntx"], r.get("masked", False))
            elif origin:
                r["sev"], r["verdict"] = 1, "origine possible"
            elif r["meas"] is not None and r["meas"] >= thr:
                r["sev"], r["verdict"] = 3, "⚠ visible sur le spectre"
            elif r["meas"] is not None and o.weak_chk.isChecked() and r["meas"] >= weak:
                r["sev"], r["verdict"] = 2, "énergie faible mesurée"
            else:
                r["sev"], r["verdict"] = 0, ""
            r["level"] = 2 if r["sev"] == 3 else (1 if r["sev"] else 0)
        if targets is not None and not origin:
            rows.sort(key=lambda r: -r["sev"])                # le plus grave en haut
        if origin:                                        # le plus probable en haut : ordre bas, pile dessus
            rows.sort(key=lambda r: (r["order"], r["ntx"], abs(r["delta"] or 0.0)))
        self.rows = rows
        self.cur_freqs, self.cur_names = freqs, names
        self.fill()
        if targets is not None and not origin:
            npairs = f"{info['pairs']:,}".replace(",", " ")
            txt = (f"{npairs} combinaisons calculées ({len(freqs)} émetteurs, ordres "
                   f"{', '.join(str(x) for x in orders)}) · seules celles qui tombent sur une de tes fréquences "
                   f"(dans la tolérance) sont listées : {len(rows)} produit(s)")
            txt += " (liste tronquée)" if info["truncated"] else ""
        else:
            txt = f"{len(rows)} produit(s)" + (" (liste tronquée)" if info["truncated"] else "")
            txt += f" · {len(freqs)} émetteur(s) · ordres {', '.join(str(x) for x in orders)} · {info['pairs']:,} combinaisons examinées".replace(",", " ")
        cnt = [sum(1 for r in rows if r["sev"] == k) for k in range(4)]
        if targets is not None and not origin and rows:
            txt += (f"\n🔴 {cnt[3]} problème(s) mesuré(s) · 🟠 {cnt[2]} à vérifier · 🟡 {cnt[1]} à surveiller (IM3 2 TX) · "
                    f"⚪ {cnt[0]} faible risque — survole « Verdict » pour le détail")
        n_vis = cnt[3]
        if n_vis:
            txt += f"\n⚠ {n_vis} produit(s) retombent sur un niveau mesuré au-dessus du seuil : à regarder en priorité."
        elif not origin and targets is not None and not rows:
            txt += "\n✔ Aucun produit ne tombe à moins de la marge d'une de tes fréquences (pour ces combinaisons)."
        elif origin and not rows:
            txt += "\nAucune combinaison de ces émetteurs n'explique ce signal : il vient peut-être d'ailleurs " \
                   "(émetteur absent de la liste, intermod dans un ampli, source extérieure…)."
        self.msg.setText(txt)

    def fill(self):
        t, th = self.table, self.owner.theme
        t.setRowCount(len(self.rows))
        base = th["ui_base"]
        for r, row in enumerate(self.rows):
            wide = row["hw"] > 0.05 or (row["gap"] is not None and row["delta"] is not None
                                        and abs(abs(row["delta"]) - row["gap"]) > 1e-6)
            if row["delta"] is None:
                d_txt = ""
            elif wide:
                d_txt = "dans la bande" if row["gap"] <= 0 else f"bord à {row['gap'] * 1000:.0f}"
            else:
                d_txt = f"{row['delta'] * 1000:+.0f}"
            vals = (f"{row['f']:.3f}" + (f" ± {row['hw']:.1f}" if row["hw"] > 0.05 else ""),
                    f'{IM_NAMES.get(row["order"], str(row["order"]))} · {row["ntx"]} TX',
                    f'{row["text"]}   =   {row["numtext"]}', row["tname"], d_txt,
                    "—" if row["meas"] is None else f"{row['meas']:.1f}", row["verdict"])
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (0, 4, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 2:
                    it.setToolTip(row["numtext"])
                sev = row.get("sev", 0)
                if sev == 3:
                    bg = blend(th["st_occ"], base, 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif c == 6 and row["verdict"]:
                    col_ = {2: "#f97316", 1: th["st_weak"]}.get(sev, th["st_none"])
                    bg = blend(col_, base, 0.55 if sev else 0.35)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                t.setItem(r, c, it)

    def selected(self):
        rs = sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.rows)})
        return [self.rows[r] for r in rs]

    def on_zoom(self):
        sel = self.selected()
        if sel:
            f = sel[0]["f"]
            self.owner.view_range(f - 1.0, f + 1.0, f"Produit {IM_NAMES.get(sel[0]['order'], '')} à {f:.3f} MHz")

    def on_watch(self):
        sel = self.selected()
        if not sel:
            self.msg.setText("Sélectionne d'abord des lignes (Ctrl+A pour tout prendre).")
            return
        n = self.owner.add_im_watches([(r["f"], f"{IM_NAMES.get(r['order'], 'IM')} {r['text']}") for r in sel])
        self.msg.setText(f"{n} fréquence(s) ajoutée(s) à la scène « Intermod » (statut Libre)." if n else
                         "Ces fréquences sont déjà dans ta liste.")

    def on_csv(self):
        if not self.rows:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter les produits", "intermod.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                wr = csv.writer(fh, delimiter=";")
                wr.writerow(["Produit MHz", "Ordre", "Origine", "Origine (MHz)", "Tombe sur", "Écart kHz", "Mesuré dBm",
                             "Verdict"])
                for r in self.rows:
                    wr.writerow([fmt_comma(r["f"]), r["order"], r["text"], r["numtext"].replace(".", ","), r["tname"],
                                 "" if r["delta"] is None else fmt_comma(r["delta"] * 1000, 0),
                                 "" if r["meas"] is None else fmt_comma(r["meas"], 1), r["verdict"]])
            self.msg.setText(f"Exporté : {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")


# --------------------------------------------------------------------------
# Dialogue : fréquence de secours
# --------------------------------------------------------------------------
class RescueDialog(QtWidgets.QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.found = []
        self.setWindowTitle("Fréquence de secours")
        self.resize(900, 640)
        R = owner._row
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(coord_note())
        info = QtWidgets.QLabel(
            "Cherche des fréquences libres d'après ce que le tinySA a mesuré (max hold), à bonne distance de tes "
            "émetteurs et sans intermodulation de 3ᵉ ordre avec eux. Aide de dépannage : ça ne remplace pas ta "
            "coordination (logiciel dédié). Vérifie que la fréquence est autorisée et compatible avec ton matériel "
            "avant de l'utiliser. Scanne bien la zone un moment avant de chercher.")
        info.setWordWrap(True)
        lay.addWidget(info)
        vr = owner.spec.getPlotItem().vb.viewRange()[0]
        a0, b0 = (vr[0], vr[1]) if 0.1 <= vr[0] < vr[1] <= 6000 and (vr[1] - vr[0]) <= 400 else (470.0, 694.0)
        self.a_spin, self.b_spin = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for sp in (self.a_spin, self.b_spin):
            sp.setDecimals(3)
            sp.setRange(0.1, 6000.0)
            sp.setSuffix(" MHz")
        self.a_spin.setValue(round(a0, 3))
        self.b_spin.setValue(round(b0, 3))
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1, 30)
        self.n_spin.setValue(3)
        self.width_spin = QtWidgets.QDoubleSpinBox()
        self.width_spin.setDecimals(3)
        self.width_spin.setRange(0.025, 2.0)
        self.width_spin.setValue(0.2)
        self.width_spin.setSuffix(" MHz")
        self.width_spin.setToolTip("Largeur à garder libre autour de la fréquence (canal du micro / de l'IEM).")
        self.sep_spin = QtWidgets.QDoubleSpinBox()
        self.sep_spin.setDecimals(3)
        self.sep_spin.setRange(0.0, 5.0)
        self.sep_spin.setSingleStep(0.05)
        self.sep_spin.setValue(0.30)
        self.sep_spin.setSuffix(" MHz")
        self.sep_spin.setToolTip("Écart minimal avec tes autres fréquences (souvent 300 à 500 kHz selon l'appareil).")
        self.guard_spin = QtWidgets.QDoubleSpinBox()
        self.guard_spin.setDecimals(3)
        self.guard_spin.setRange(0.005, 5.0)
        self.guard_spin.setSingleStep(0.05)
        self.guard_spin.setValue(0.10)
        self.guard_spin.setPrefix("± ")
        self.guard_spin.setSuffix(" MHz")
        self.guard_spin.setToolTip("Tolérance d'intermodulation 3ᵉ ordre 2 TX (2A − B) avec tes fréquences ;\n"
                                   "la moitié pour les 3 TX (A + B − C). 100 kHz = valeur courante pour les 2 TX.")
        self.thr_spin = QtWidgets.QDoubleSpinBox()
        self.thr_spin.setRange(-130, 0)
        _Fm, _Lm = owner.fresh_FL(use_max=True, any_age=True)
        if owner.thr_auto and _Fm is not None:      # 7.66.3 : max hold comparé à son propre bruit, pas au bruit du moment
            self.thr_spin.setValue(round(owner.busy_limit(_Lm)))
        else:
            self.thr_spin.setValue(owner.weak_spin.value() if owner.weak_chk.isChecked() else owner.thr_spin.value() - 10)
        self.thr_spin.setSuffix(" dBm")
        self.thr_spin.setToolTip("Niveau maximum mesuré toléré sur le canal (max hold).")
        self.im_combo = QtWidgets.QComboBox()
        self.im_combo.addItem("Intermod : 2 TX + 3 TX", "full")
        self.im_combo.addItem("Intermod : 2 TX seulement (2A − B)", "2tx")
        self.im_combo.addItem("Intermod : ignorée", "none")
        self.im_combo.setToolTip("Quels produits d'intermodulation compter. Avec beaucoup d'émetteurs, les 3 TX\n"
                                 "(A + B − C) recouvrent vite toute la bande : « 2 TX seulement » = règle « Simple ».")
        self.filt_spin = QtWidgets.QDoubleSpinBox()
        self.filt_spin.setDecimals(0)
        self.filt_spin.setRange(0, 200)
        self.filt_spin.setValue(float(owner.plan_opts.get("filt", 32.0)))
        self.filt_spin.setSuffix(" MHz")
        self.filt_spin.setSpecialValueText("aucun")
        self.filt_spin.setToolTip("Filtre du récepteur : seuls les émetteurs à ± la valeur du filtre\nautour de la "
                                  "fréquence comptent pour l'intermod. 0 = aucun filtre (tous comptent).")
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Éviter : toute la liste", "all")
        self.src_combo.addItem("Éviter : la couche active seulement", "scope")
        self.go_btn = QtWidgets.QPushButton("🔎 Chercher")
        self.go_btn.clicked.connect(lambda *_: self.search())
        self.spec_combo = QtWidgets.QComboBox()
        owner.fill_coord_combo(self.spec_combo)
        self.rx_combo = QtWidgets.QComboBox()             # 7.61 : appareil -> réglages + sa bande
        fill_rx_combo(self.rx_combo, "Appareil : réglages ci-dessous")
        self.rx_combo.setToolTip("Pour quel appareil chercher : ses réglages (écart, tolérance, filtre, pas) sont\n"
                                 "repris, et s'il a une bande (bibliothèque, plan importé), la recherche y reste.")
        rows = owner._sel_rows() if hasattr(owner, "_sel_rows") else []
        rx0 = owner.rx_of(owner.watch[rows[0]]) if rows and rows[0] < len(owner.watch) else ""
        if rx0:
            self.rx_combo.setCurrentIndex(max(0, self.rx_combo.findData(rx0)))
        self.rx_combo.currentIndexChanged.connect(lambda *_: self._from_rx())
        self.band_lbl = QtWidgets.QLabel("")
        lay.addLayout(R("De", self.a_spin, "à", self.b_spin, "Nombre :", self.n_spin, None))
        lay.addLayout(R(self.rx_combo, self.band_lbl, None))
        lay.addLayout(R("Canal :", self.width_spin, "Écart mini :", self.sep_spin, "Tolérance :", self.guard_spin,
                        self.im_combo, "Filtre :", self.filt_spin, None))
        lay.addLayout(R("Niveau max toléré :", self.thr_spin, self.src_combo, None, self.go_btn))
        lay.addLayout(R(self.spec_combo, None))
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Fréquence MHz", "Niveau max dBm", "Voisine la plus proche", "Écart kHz",
                                              "Spectre", "Remarque"])
        self.table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for c, w in ((0, 110), (1, 110), (2, 200), (3, 76), (4, 160)):
            self.table.setColumnWidth(c, w)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_view())
        lay.addWidget(self.table, 1)
        self.layer_combo = QtWidgets.QComboBox()
        self.layer_combo.addItem("Ajouter dans : (sans scène)", ("", ""))
        for sc in owner.scenes:
            for g in sc["groups"]:
                self.layer_combo.addItem(f"Ajouter dans : {sc['name']} › {g['name']}", (sc["name"], g["name"]))
        self.layer_combo.addItem("Ajouter dans : Secours › Fréquences de secours (nouveau)", ("Secours", "Fréquences de secours"))
        self.layer_combo.setCurrentIndex(self.layer_combo.count() - 1)
        b_view = QtWidgets.QPushButton("🔍 Voir")
        b_view.clicked.connect(lambda *_: self.on_view())
        b_add = QtWidgets.QPushButton("＋ Ajouter la sélection à ma liste")
        b_add.clicked.connect(lambda *_: self.on_add())
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        lay.addLayout(R(self.layer_combo, b_view, b_add, None, b_close))
        if rx0:
            self._from_rx()

    def _rx(self):
        return rx_profile(self.rx_combo.currentData()) if self.rx_combo.currentData() else None

    def _from_rx(self):
        """Appareil choisi : ses réglages remplissent la fenêtre, et la plage se cale sur sa bande s'il en a une."""
        d = self._rx()
        if d is None:
            self.band_lbl.setText("")
            return
        self.sep_spin.setValue(d["sep"])
        if d["tol"].get("2tx3"):
            self.guard_spin.setValue(d["tol"]["2tx3"])
        self.filt_spin.setValue(d["filt"])
        bd = rx_band(d)
        if bd:
            cl = band_clip(self.a_spin.value(), self.b_spin.value(), bd) or bd
            self.a_spin.setValue(round(cl[0], 3))
            self.b_spin.setValue(round(cl[1], 3))
            self.band_lbl.setText(f"Bande de l'appareil : {bd[0]:g}–{bd[1]:g} MHz (la recherche y reste)")
        else:
            self.band_lbl.setText("Pas de bande connue pour cet appareil (profil intégré) : vérifie que la plage "
                                  "correspond à ton matériel.")

    def search(self):
        o = self.owner
        F, L = o.coord_FL(self.spec_combo.currentData())
        if F is None:
            self.msg.setText("Aucune mesure : lance un balayage (▶ Démarrer) sur cette zone, laisse tourner un moment, "
                             "puis relance la recherche.")
            return
        a, b = self.a_spin.value(), self.b_spin.value()
        if b <= a:
            self.msg.setText("La plage est à l'envers.")
            return
        d_rx = self._rx()
        bd = rx_band(d_rx) if d_rx else None
        if bd:                                      # 7.61 : jamais hors de la bande de l'appareil choisi
            cl = band_clip(a, b, bd, self.width_spin.value())
            if cl is None:
                self.msg.setText(f"La plage {a:g}–{b:g} MHz est hors de la bande de l'appareil ({bd[0]:g}–{bd[1]:g} MHz).")
                return
            a, b = cl
        grid = max(0.025, d_rx["step"]) if d_rx else 0.025   # pas de l'appareil (au moins 25 kHz : assez fin)
        a = math.ceil(a / grid - 1e-9) * grid                 # grille calée sur le pas (fréquences réglables)
        ws = o.scope_ws() if self.src_combo.currentData() == "scope" else o.watch
        ex = [w["freq"] for w in ws]
        em = [w["freq"] for w in ws if not o.is_keep_free(w["status"])]      # une réserve libre n'émet pas
        im = self.im_combo.currentData()
        res, d = find_free(F, L, a, b, ex, self.n_spin.value(), self.width_spin.value(), self.sep_spin.value(),
                           self.thr_spin.value(), None if im == "none" else self.guard_spin.value(),
                           guard3=self.guard_spin.value() / 2.0, emitters=em, filt=self.filt_spin.value(),
                           im3=im == "full", allowed=o.reg_pred(), grid=grid)
        self.found = res
        exa = sorted(w["freq"] for w in o.watch)
        t = self.table
        t.setRowCount(len(res))
        for r, x in enumerate(res):
            near = min(o.watch, key=lambda w: abs(w["freq"] - x["f"]), default=None)
            nn = "—" if near is None else f'{near["name"]} ({near["freq"]:.3f})'
            dk = "" if near is None else f'{abs(near["freq"] - x["f"]) * 1000:.0f}'
            warn = x.get("warn")
            rt = o.reg_tag(x["f"], self.width_spin.value())   # 7.60.1 : licence / inconnue = dit tout de suite
            if rt:
                warn = f"{warn} · {rt}" if warn else rt
            vals = (f'{x["f"]:.3f}', f'{x["level"]:.1f}', nn, dk, spectrum_info(x["f"], o.plan, o.tv)[0] or "—",
                    "⚠ " + warn if warn else "✔ libre, sans intermod")
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (0, 1, 3):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if warn:
                    it.setForeground(QtGui.QColor("#e0a040"))
                t.setItem(r, c, it)
        cover = f"{F.min():.1f}–{F.max():.1f} MHz"
        n_ok = len(res) - d["alternatives"]
        txt = (f"{n_ok} fréquence(s) trouvée(s) sur {self.n_spin.value()} demandée(s). "
               f"Grille : {d['grille']} points · trop bruyants : {d['bruyantes']} · hors mesure : {d['sans_mesure']} · "
               f"trop proches : {d['trop_proches']} · rejetés pour intermod : {d['intermod']}. Mesures disponibles : {cover}.")
        if n_ok < self.n_spin.value():
            if d["intermod"] >= max(d["trop_proches"], 1) and im == "full":
                txt += ("\nC'est surtout l'intermod qui bloque : avec beaucoup d'émetteurs, les produits 3 TX (A + B − C) "
                        "recouvrent toute la bande. Essaie « 2 TX seulement », un filtre récepteur, ou « la couche "
                        "active seulement ».")
            elif d["bruyantes"] > d["grille"] // 2:
                txt += "\nLa zone est très chargée : accepte un niveau plus haut ou élargis la plage."
            else:
                txt += "\nPas assez de place avec ces réglages : élargis la plage, baisse l'écart ou la tolérance."
            if d["alternatives"]:
                txt += (f"\n⚠ {d['alternatives']} « moins mauvaise(s) » proposée(s) en orange : regarde la "
                        "remarque avant de t'en servir.")
        if bd:
            txt += f"\nRecherche limitée à la bande de l'appareil : {a:.3f}–{b:.3f} MHz."
        if o.reg_note():
            txt += "\n" + o.reg_note()
        self.msg.setText(txt)

    def _sel(self):
        rs = sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.found)})
        return [self.found[r] for r in rs]

    def on_view(self):
        s = self._sel()
        if s:
            self.owner.view_range(s[0]["f"] - 1.0, s[0]["f"] + 1.0, f"Fréquence candidate {s[0]['f']:.3f} MHz")

    def on_add(self):
        s = self._sel() or self.found
        if not s:
            return
        sc, gr = self.layer_combo.currentData() or ("", "")
        n = self.owner.add_free_freqs([x["f"] for x in s], sc, gr, self.rx_combo.currentData() or "")
        self.msg.setText(f"{n} fréquence(s) ajoutée(s) à ta liste.")


# --------------------------------------------------------------------------
# Enregistrement disque des balayages + relecture
# --------------------------------------------------------------------------
REC_SESSION_MB = 2000          # taille maximale d'un enregistrement (les plus anciennes tranches sont supprimées)


class SweepRecorder:
    """Enregistre les balayages sur disque : une tranche .npz compressée toutes les ~30 s
    (niveaux en float16 : précision de 0,06 dB)."""

    def __init__(self, folder, flush_s=30.0, max_mb=REC_SESSION_MB):
        self.folder = Path(folder)
        self.flush_s, self.max_bytes = float(flush_s), int(max_mb * 1e6)
        self.pending, self.n_chunk, self.n_sweeps, self.error = [], 0, 0, ""
        self.t_flush = time.time()

    def add(self, bid, t, f, l):
        if not self.error:
            self.pending.append((int(bid), float(t), np.asarray(f, dtype=np.float64), np.asarray(l, dtype=np.float16)))

    def maybe_flush(self, now):
        if self.pending and now - self.t_flush >= self.flush_s:
            self.flush(now)

    def flush(self, now=None):
        if not self.pending or self.error:
            return
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            segs, cur = [], None
            for bid, t, f, l in self.pending:
                key = (bid, len(f), float(f[0]), float(f[-1]))
                if cur is None or cur[0] != key:
                    cur = [key, [], f, []]
                    segs.append(cur)
                cur[1].append(t)
                cur[3].append(l)
            arrs = {"n": np.array(len(segs))}
            for i, (key, ts, f, ls) in enumerate(segs):
                arrs[f"b{i}"] = np.array(key[0])
                arrs[f"t{i}"] = np.array(ts, dtype=np.float64)
                arrs[f"f{i}"] = f
                arrs[f"l{i}"] = np.stack(ls)
            self.n_chunk += 1
            path = self.folder / f"chunk_{self.n_chunk:06d}.npz"
            part = self.folder / f"chunk_{self.n_chunk:06d}.part"
            with open(part, "wb") as fh:
                np.savez_compressed(fh, **arrs)
            os.replace(part, path)
            self.n_sweeps += len(self.pending)
            self.pending = []
            self.t_flush = now if now is not None else time.time()
            self._trim()
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    def _trim(self):
        files = sorted(self.folder.glob("chunk_*.npz"))
        sizes = [p.stat().st_size for p in files]
        total = sum(sizes)
        for p, s in zip(files[:-1], sizes[:-1]):
            if total <= self.max_bytes:
                break
            try:
                p.unlink()
                total -= s
            except OSError:
                break

    def close(self):
        self.flush()


def export_store(store, folder):
    """Écrit tout le contenu d'un SweepStore comme un enregistrement (tranches .npz). -> nombre de balayages."""
    rec = SweepRecorder(folder, max_mb=1e9)
    evs = sorted((t, b, k) for b, ts in store.t.items() for k, t in enumerate(ts))
    n = 0
    for t, b, k in evs:
        f, l = store.d[b][k]
        rec.add(b, t, f, l)
        n += 1
        if len(rec.pending) >= 2000:
            rec.flush()
    rec.flush()
    if rec.error:
        raise OSError(rec.error)
    return n


def load_recording(folder, store):
    """Relit un dossier d'enregistrement dans un SweepStore. -> (nombre de balayages, nombre de tranches)."""
    files = sorted(Path(folder).glob("chunk_*.npz"))
    n = 0
    for p in files:
        try:
            with np.load(p) as z:
                for i in range(int(z["n"])):
                    bid, ts, f, ls = int(z[f"b{i}"]), z[f"t{i}"], z[f"f{i}"], z[f"l{i}"]
                    for t, l in zip(ts, ls):
                        store.add(bid, float(t), f, l.astype(np.float32))
                        n += 1
        except Exception:  # noqa: BLE001
            continue
    return n, len(files)


class SessionDialog(QtWidgets.QDialog):
    """Avant ▶ Démarrer : enregistrer toute la session (spectre + journal) pour revenir dessus après le show ?"""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Enregistrer cette session ?")
        c = owner.session_cfg
        lay = QtWidgets.QVBoxLayout(self)
        est = owner.rec_estimate_txt()
        info = QtWidgets.QLabel(
            "<b>💾 Garder tout le scan sur disque</b> : le spectre de chaque balayage et le journal, pour revenir à "
            "n'importe quel moment après le show (⏪ Relecture › 📂 Ouvrir une session), même si l'appli est "
            "fermée entre-temps." + (f"<br>Place estimée : {est}." if est else ""))
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 4)
        lay.addWidget(info)
        f = QtWidgets.QFormLayout()
        self.dir_edit = QtWidgets.QLineEdit(c.get("dir") or str(owner.log_dir / "enregistrements"))
        self.dir_edit.setToolTip("Dossier où ranger les sessions (un sous-dossier par session).")
        b_dir = QtWidgets.QPushButton("Choisir…")
        b_dir.setToolTip("Dossier où ranger les sessions (disque externe, clé USB, dossier partagé…).")
        b_dir.clicked.connect(lambda *_: self.pick_dir())
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.dir_edit, 1)
        row.addWidget(b_dir)
        f.addRow("Dossier :", row)
        self.name_edit = QtWidgets.QLineEdit(owner.session_default_name())
        self.name_edit.setToolTip("Nom du sous-dossier de cette session (date + nom du show par défaut).")
        f.addRow("Nom de la session :", self.name_edit)
        lay.addLayout(f)
        self.never = QtWidgets.QCheckBox("Ne plus demander : toujours faire ce choix (réglable dans Journal)")
        self.never.setToolTip("La question ne revient plus ; la case « Demander à chaque démarrage » de "
                              "l'onglet Journal la fait revenir.")
        self.never.setChecked(not c.get("ask", True))
        lay.addWidget(self.never)
        bb = QtWidgets.QDialogButtonBox()
        self.b_rec = bb.addButton("💾 Enregistrer et démarrer", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.b_no = bb.addButton("▶ Démarrer sans enregistrer", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.b_rec.setToolTip("Démarre le scan et enregistre tout dans le dossier ci-dessus.")
        self.b_no.setToolTip("Démarre le scan sans rien garder sur disque (les 30 dernières minutes restent en mémoire).")
        bb.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.b_rec.setDefault(True)
        self.rec = True
        self.b_rec.clicked.connect(lambda *_: self._done(True))
        self.b_no.clicked.connect(lambda *_: self._done(False))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(640, 270)

    def pick_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier des sessions", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _done(self, rec):
        self.rec = rec
        self.accept()


class ReplayDialog(QtWidgets.QDialog):
    """Revoir le spectre à un instant passé : curseur de temps, lecture accélérée, qui était allumé à ce moment-là."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.store = owner.store
        self.times = np.array([])
        self.idx = 0
        self.speed = 1
        self.sess_watch = None                   # session ouverte : sa liste de fréquences et son journal
        self.sess_events = None
        self.sess_path = None
        self.setWindowTitle("Relecture : revoir le spectre")
        self.resize(1320, 780)
        th = owner.theme
        lay = QtWidgets.QVBoxLayout(self)
        self.src_lbl = QtWidgets.QLabel("")
        b_open = QtWidgets.QPushButton("📂 Ouvrir une session…")
        b_open.setToolTip("Relit une session enregistrée (proposé à ▶ Démarrer, ou « 💾 Enregistrer les balayages ») :\n"
                          "spectre, journal et liste de fréquences de ce moment-là.")
        b_open.clicked.connect(lambda *_: self.open_rec())
        b_last = QtWidgets.QPushButton("🕘 Dernière session")
        b_last.setToolTip("Rouvre la dernière session enregistrée par cette appli.")
        b_last.clicked.connect(lambda *_: self.open_rec(owner._last_session or owner._session))
        b_last.setEnabled(bool(owner._last_session or owner._session))
        b_exp = QtWidgets.QPushButton("💾 Exporter…")
        b_exp.setToolTip("Enregistre ce qui est relu (par ex. les 30 dernières minutes en mémoire) comme une session,\n"
                         "dans le dossier de ton choix : à garder, envoyer, ou rouvrir plus tard.")
        b_exp.clicked.connect(lambda *_: self.export_session())
        b_mem = QtWidgets.QPushButton("↩ Mémoire en cours")
        b_mem.setToolTip("Les 30 dernières minutes gardées en mémoire par le logiciel.")
        b_mem.clicked.connect(lambda *_: self.use_memory())
        self.ev_combo = QtWidgets.QComboBox()
        self.ev_combo.setMinimumWidth(380)
        self.ev_combo.currentIndexChanged.connect(self.on_event_pick)
        lay.addLayout(owner._row(self.src_lbl, None, "Aller à :", self.ev_combo, b_open, b_last, b_mem, b_exp))
        self.plot = pg.PlotWidget()
        pi = self.plot.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "Fréquence", units="MHz")
        pi.setLabel("left", "Niveau", units="dBm")
        pi.setYRange(-120, -10, padding=0)
        pi.getAxis("bottom").enableAutoSIPrefix(False)
        self.cmpcurve = pi.plot(pen=pg.mkPen("#c678dd", width=1.3, style=Qt.PenStyle.DashLine), connect="finite")
        self.cmp = None                          # session de comparaison : (nom, F, L max hold)
        self.maxcurve = pi.plot(pen=pg.mkPen(th["maxhold"], width=1), connect="finite")
        self.curve = pi.plot(pen=pg.mkPen(th["curve"], width=1.6), connect="finite")
        self.thr_line = pg.InfiniteLine(pos=owner.thr_spin.value(), angle=0,
                                        pen=pg.mkPen(th["thr"], width=1.3, style=Qt.PenStyle.DashLine))
        pi.addItem(self.thr_line)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nom", "MHz", "Niveau", "Max", "À ce moment"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumWidth(430)
        self.table.setMaximumWidth(520)
        mid = QtWidgets.QHBoxLayout()
        mid.addWidget(self.plot, 1)
        mid.addWidget(self.table)
        lay.addLayout(mid, 1)
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self.seek)
        self.time_lbl = QtWidgets.QLabel("")
        self.time_lbl.setMinimumWidth(260)
        self.play_btn = QtWidgets.QPushButton("▶ Lecture")
        self.play_btn.clicked.connect(lambda *_: self.toggle_play())
        b_prev = QtWidgets.QPushButton("◀")
        b_prev.setToolTip("Balayage précédent")
        b_prev.clicked.connect(lambda *_: self.step(-1))
        b_next = QtWidgets.QPushButton("▶")
        b_next.setToolTip("Balayage suivant")
        b_next.clicked.connect(lambda *_: self.step(1))
        self.speed_combo = QtWidgets.QComboBox()
        for lab, v in (("×1", 1), ("×4", 4), ("×16", 16), ("×64", 64)):
            self.speed_combo.addItem(lab, v)
        self.speed_combo.currentIndexChanged.connect(self._on_speed)
        self.mh_chk = QtWidgets.QCheckBox("Max hold depuis le début")
        self.mh_chk.setChecked(True)
        self.mh_chk.toggled.connect(lambda *_: self.seek(self.idx))
        lay.addWidget(self.slider)
        b_cmp = QtWidgets.QPushButton("⚖ Comparer avec une session…")
        b_cmp.setToolTip("Superpose le max hold d'une autre session (ex. la balance, ou hier) en pointillés violets,\n"
                         "et liste les signaux en plus ou en moins par rapport à elle.")
        b_cmp.clicked.connect(lambda *_: self.open_compare())
        b_occ = QtWidgets.QPushButton("📊 Occupation par heure")
        b_occ.setToolTip("% du temps où chaque fréquence était occupée, heure par heure, sur ce qui est relu.")
        b_occ.clicked.connect(lambda *_: OccupancyDialog(self.owner, self.store, self.sess_watch,
                                                          self.sess_path.name if self.sess_path else "").exec())
        self.cmp_lbl = QtWidgets.QLabel("")
        self.cmp_lbl.setWordWrap(True)
        lay.addLayout(owner._row(b_prev, self.play_btn, b_next, self.speed_combo, self.mh_chk, b_cmp, b_occ, None,
                                 self.time_lbl))
        lay.addWidget(self.cmp_lbl)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._tick)
        self._fit = True
        self.reload()

    # ------------------------------------------------------------- source
    def reload(self):
        self.times = self.store.times()
        n = len(self.times)
        self.slider.setRange(0, max(0, n - 1))
        sp = self.store.span()
        if n == 0:
            self.src_lbl.setText("Aucun balayage en mémoire : lance un balayage (▶ Démarrer) ou ouvre un enregistrement.")
            self.curve.setData([], [])
            self.maxcurve.setData([], [])
            self.table.setRowCount(0)
            self.time_lbl.setText("—")
            return
        self.src_lbl.setText(f"{n} instants · {fmt_clock(sp[0])} → {fmt_clock(sp[1])} ({fmt_dur(sp[1] - sp[0])})")
        self.fill_events()
        self._fit = True
        self.slider.setValue(n - 1)
        self.seek(n - 1)

    def use_memory(self):
        self.store = self.owner.store
        self.sess_watch = self.sess_events = self.sess_path = None
        self.reload()

    def open_rec(self, d=None):
        if not d:
            o = self.owner
            start = o.session_cfg.get("dir") or str(o.log_dir / "enregistrements")
            d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier d'une session", str(start))
        if not d:
            return
        st = SweepStore(seconds=1e12, max_mb=2500)
        n, nf = load_recording(d, st)
        if n == 0:
            self.msg.setText(f"Aucun balayage lisible dans « {d} » ({nf} fichier(s) trouvé(s)).")
            return
        self.store = st
        self.sess_path, self.sess_watch, self.sess_events = Path(d), None, None
        extra = ""
        try:
            meta = json.loads((Path(d) / "session.json").read_text(encoding="utf-8"))
            if isinstance(meta.get("watch"), list) and meta["watch"]:
                self.sess_watch = [dict(name=str(w.get("name", "")), freq=float(w["freq"]), thr=w.get("thr"),
                                        status=w.get("status", "")) for w in meta["watch"] if "freq" in w]
            show = (meta.get("show") or {}).get("name") or ""
            extra = f" · {show}" if show else ""
        except Exception:  # noqa: BLE001
            pass
        try:
            rows = session_journal_rows((Path(d) / "journal.csv").read_text(encoding="utf-8-sig"))
            self.sess_events = [(datetime.strptime(f"{a} {b}", "%Y-%m-%d %H:%M:%S").timestamp(), lab)
                                for a, b, lab in rows]
        except Exception:  # noqa: BLE001
            pass
        self.msg.setText(f"Session chargée{extra} : {n} balayages ({nf} tranche(s))"
                         + (f", {len(self.sess_watch)} fréquences" if self.sess_watch else "")
                         + (f", {len(self.sess_events)} événements du journal" if self.sess_events else "") + ".")
        self.reload()

    def open_compare(self, d=None):
        """Charge une autre session : son max hold (toute sa durée) est superposé et comparé."""
        if not d:
            o = self.owner
            start = o.session_cfg.get("dir") or str(o.log_dir / "enregistrements")
            d = QtWidgets.QFileDialog.getExistingDirectory(self, "Session à comparer", str(start))
        if not d:
            return
        st = SweepStore(seconds=1e12, max_mb=2500)
        n, _nf = load_recording(d, st)
        sp = st.span()
        if not n or sp is None:
            self.cmp_lbl.setText(f"Aucun balayage lisible dans « {d} ».")
            return
        F2, L2 = st.maxhold(sp[0], sp[1])
        self.cmp = (Path(d).name, F2, L2)
        self.cmpcurve.setData(F2, L2)
        self.seek(self.idx)

    def _compare_text(self, F1, L1):
        if self.cmp is None or F1 is None:
            return
        name, F2, L2 = self.cmp
        new, gone = compare_spectra(F1, L1, F2, L2, self.owner.thr_spin.value())

        def fl(p_):
            return ", ".join(f"{x['f']:.3f}" for x in p_[:8]) + (" …" if len(p_) > 8 else "")
        self.cmp_lbl.setText(f"⚖ Comparé à « {name} » (pointillés violets) : {len(new)} signal(aux) en plus ici"
                             + (f" ({fl(new)} MHz)" if new else "") + f" · {len(gone)} en moins"
                             + (f" ({fl(gone)} MHz)" if gone else "") + ".")

    def export_session(self):
        """Enregistre le contenu relu (mémoire ou session ouverte) comme une session, dans le dossier choisi."""
        sp = self.store.span()
        if sp is None:
            self.msg.setText("Rien à exporter : aucun balayage.")
            return
        o = self.owner
        start = o.session_cfg.get("dir") or str(o.log_dir / "enregistrements")
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Exporter la session dans…", str(start))
        if not d:
            return
        name = session_name(datetime.fromtimestamp(sp[0]).strftime("%Y-%m-%d_%H%M") + "_export",
                            o.show_meta.get("name", ""))
        try:
            n = export_store(self.store, Path(d) / name)
            dst = Path(d) / name
            if self.sess_path is not None:          # session déjà sur disque : on garde aussi son journal / sa liste
                import shutil                       # (import local : la V8 l'importe aussi en tête)
                for fn in ("session.json", "journal.csv"):
                    if (self.sess_path / fn).exists():
                        shutil.copy2(self.sess_path / fn, dst / fn)
            else:
                o._write_session_json(dst)
                self._export_journal(dst, sp)
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")
            return
        self.msg.setText(f"💾 {n} balayages exportés dans {dst}")

    def _export_journal(self, dst, sp):
        t = self.owner.log_table
        day = datetime.fromtimestamp(sp[0]).strftime("%Y-%m-%d")
        with open(dst / "journal.csv", "w", newline="", encoding="utf-8-sig") as fh:
            wr = csv.writer(fh, delimiter=";")
            wr.writerow(SESSION_JOURNAL_HEAD)
            for r in range(t.rowCount() - 1, -1, -1):
                v = [(t.item(r, c).text() if t.item(r, c) else "") for c in range(7)]
                wr.writerow([day, v[0], v[1], v[2].replace(".", ","), v[3].replace(".", ","), v[4], "", "", "", "",
                             v[6]])

    def fill_events(self):
        """Événements du journal qui tombent dans la période relue (le journal ne garde que l'heure du jour)."""
        self.ev_combo.blockSignals(True)
        self.ev_combo.clear()
        self.ev_combo.addItem("— événement du journal —", None)
        sp = self.store.span()
        if self.sess_events is not None:
            for ep, lab in self.sess_events:
                if sp[0] - 60 <= ep <= sp[1] + 60:
                    self.ev_combo.addItem(lab, ep)
            self.ev_combo.blockSignals(False)
            return
        t = self.owner.log_table
        day = datetime.fromtimestamp(sp[0]).replace(hour=0, minute=0, second=0, microsecond=0)
        for r in range(t.rowCount() - 1, -1, -1):
            try:
                hh, mm, ss = (int(x) for x in t.item(r, 0).text().split(":"))
            except Exception:  # noqa: BLE001
                continue
            ep = day.replace(hour=hh, minute=mm, second=ss).timestamp()
            if ep < sp[0] - 60:
                ep += 86400.0
            if sp[0] - 60 <= ep <= sp[1] + 60:
                self.ev_combo.addItem(f'{t.item(r, 0).text()}  {t.item(r, 4).text()}  {t.item(r, 1).text()}  '
                                      f'{t.item(r, 2).text()} MHz', ep)
        self.ev_combo.blockSignals(False)

    def on_event_pick(self, *_):
        ep = self.ev_combo.currentData()
        if ep is not None and len(self.times):
            i = int(np.searchsorted(self.times, ep - 1.0))
            i = min(max(i, 0), len(self.times) - 1)
            self.slider.setValue(i)
            self.seek(i)

    # ------------------------------------------------------------- lecture
    def _on_speed(self, *_):
        self.speed = int(self.speed_combo.currentData() or 1)

    def toggle_play(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("▶ Lecture")
        else:
            if len(self.times) and self.idx >= len(self.times) - 1:
                self.slider.setValue(0)
                self.seek(0)
            self.timer.start()
            self.play_btn.setText("💤 Pause")

    def _tick(self):
        if self.idx >= len(self.times) - 1:
            self.timer.stop()
            self.play_btn.setText("▶ Lecture")
            return
        i = min(len(self.times) - 1, self.idx + self.speed)
        self.slider.setValue(i)
        self.seek(i)

    def step(self, d):
        if len(self.times):
            i = min(max(self.idx + d, 0), len(self.times) - 1)
            self.slider.setValue(i)
            self.seek(i)

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)

    # ------------------------------------------------------------- affichage
    def seek(self, i):
        i = int(i)
        if not len(self.times):
            return
        i = min(max(i, 0), len(self.times) - 1)
        self.idx = i
        o = self.owner
        t = float(self.times[i])
        t0 = float(self.times[0])
        F, L = self.store.snapshot(t)
        if F is None:
            return
        self.curve.setData(F, L)
        if self.mh_chk.isChecked():
            Fm, Lm = self.store.maxhold(t0, t)
        else:
            Fm, Lm = None, None
        if Fm is not None:
            self.maxcurve.setData(Fm, Lm)
        else:
            self.maxcurve.setData([], [])
        if self.cmp is not None:                     # comparaison : max hold jusqu'à cet instant vs l'autre session
            self._compare_text(*((Fm, Lm) if Fm is not None else self.store.maxhold(t0, t)))
        if self._fit:
            self._fit = False
            self.plot.getPlotItem().setXRange(float(F[0]), float(F[-1]), padding=0.01)
        self.time_lbl.setText(f"{fmt_clock(t)}   ({fmt_dur(t - float(self.times[-1]), signed=True)} · "
                              f"{i + 1}/{len(self.times)})")
        win = max(0.05, o.win_spin.value() / 1000.0)
        gthr, gweak, weak_on = o.thr_spin.value(), o.weak_spin.value(), o.weak_chk.isChecked()
        rows = []
        src = self.sess_watch if self.sess_watch is not None else [w for w in o.watch if o.in_scope(w)]
        for w in src:
            lv = level_at(F, L, w["freq"], win)
            mx = level_at(Fm, Lm, w["freq"], win) if Fm is not None else None
            thr = w["thr"] if w.get("thr") is not None else gthr
            if lv is None:
                st = "—"
            elif lv >= thr:
                st = "OCCUPÉ"
            elif weak_on and lv >= (thr - (gthr - gweak)):
                st = "faible"
            else:
                st = "libre"
            rows.append((lv if lv is not None else -999.0, w["name"], w["freq"], lv, mx, st))
        rows.sort(key=lambda r: -r[0])
        rows = rows[:300]
        th = o.theme
        base = th["ui_base"]
        self.table.setRowCount(len(rows))
        for r, (_k, nm, fr, lv, mx, st) in enumerate(rows):
            vals = (nm, f"{fr:.3f}", "—" if lv is None else f"{lv:.1f}", "—" if mx is None else f"{mx:.1f}", st)
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (1, 2, 3):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if st == "OCCUPÉ":
                    bg = blend(th["st_occ"], base, 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif st == "faible" and c == 4:
                    bg = blend(th["st_weak"], base, 0.5)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                self.table.setItem(r, c, it)


def fmt_clock(t):
    return datetime.fromtimestamp(float(t)).strftime("%H:%M:%S")


def fmt_dur(s, signed=False):
    s = float(s)
    sign = "-" if (signed and s < -0.5) else ""
    s = int(round(abs(s)))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    txt = f"{h} h {m:02d} min {sec:02d} s" if h else (f"{m} min {sec:02d} s" if m else f"{sec} s")
    return sign + txt


# --------------------------------------------------------------------------
# Dialogue : rapport de fin de show
# --------------------------------------------------------------------------
def rx_short(key):
    """Nom court d'un profil d'appareil (colonne « Appareil »)."""
    for k, n, _d, _w in rx_all():
        if k == key:
            return n.split(" (")[0].split(" ·")[0]
    return "par défaut"


def fill_rx_combo(combo, default_txt):
    """Profils d'appareil dans une liste : 1er choix = default_txt (donnée ""), explication en bulle, puis les
    profils perso (« ✏ … »)."""
    cur = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(default_txt, "")
    for k, n, _d, why in rx_all():
        combo.addItem(("✏ " + n) if k.startswith("perso_") else n, k)
        combo.setItemData(combo.count() - 1, why, Qt.ItemDataRole.ToolTipRole)
    ix = combo.findData(cur) if cur else -1
    combo.setCurrentIndex(max(0, ix))
    combo.blockSignals(False)
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)


def show_filter_help(parent):
    """Fenêtre « ❓ Le filtre récepteur, c'est quoi ? » (texte + tableau des profils)."""
    d = QtWidgets.QDialog(parent)
    d.setWindowTitle("Filtre récepteur et profils d'appareil")
    v = QtWidgets.QVBoxLayout(d)
    tb = QtWidgets.QTextBrowser()
    tb.setHtml(rx_help_html())
    v.addWidget(tb)
    b = QtWidgets.QPushButton("Fermer")
    b.setToolTip("Ferme l'explication.")
    b.clicked.connect(d.accept)
    v.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
    d.resize(760, 640)
    d.exec()


def filter_help_btn(parent):
    b = QtWidgets.QPushButton("❓")
    b.setToolTip("Le filtre récepteur, c'est quoi ? (explication et profils)")
    b.setMaximumWidth(36)
    b.clicked.connect(lambda *_: show_filter_help(parent))
    return b


class EzrfImportDialog(QtWidgets.QDialog):
    """📥 Plan (document .ezrf3 ou copier-coller du plan de fréquences) -> Mes fréquences : scènes (groupes
    du document), groupes (sections), appareils (profils perso avec les réglages du document), interférences notées,
    scan de fond."""

    def __init__(self, owner, doc, source, path=None, kind="EazyRF"):
        super().__init__(owner)
        self.owner, self.doc, self.path, self.kind = owner, doc, path, kind
        self.setWindowTitle(f"Importer un plan {kind}")
        fit_dialog(self, 820, 760)
        lay = QtWidgets.QVBoxLayout(self)
        ent = ezrf_entries(doc, False)
        n_off = sum(1 for r in doc["rows"] if r["off"])
        head = f"<b>{source}</b>"
        if doc["title"]:
            head += f"<br>« {doc['title']} »" + (f" · {doc['date']}" if doc["date"] else "") + (
                f" · EazyRF {doc['version'].replace('Version', '').strip()}" if doc["version"] else "")
        scenes = []
        for _n, _f, sc, gr, _d, _x in ent:
            if sc not in scenes:
                scenes.append(sc)
        head += (f"<br>{len(ent)} fréquence(s) · {len([x for x in scenes if x])} scène(s) · "
                 f"{len(doc['devices'])} appareil(s)")
        info = QtWidgets.QLabel(head)
        info.setWordWrap(True)
        lay.addWidget(info)
        if doc["warn"]:
            w = QtWidgets.QLabel("⚠ " + doc["warn"])
            w.setWordWrap(True)
            lay.addWidget(w)
        self.pend = None
        if doc.get("pending"):
            self._build_pending(lay)
        self._ent0 = ent
        self._build_map(lay, [x for x in scenes if x])
        self.naming = None
        if kind == "EazyRF" and any(not r["name"] and r["dev"] for r in doc["rows"]):
            nrow = QtWidgets.QHBoxLayout()
            nrow.addWidget(QtWidgets.QLabel("Noms des fréquences sans nom :"))
            self.naming = QtWidgets.QComboBox()
            for k_, lab_ in EZRF_NAMINGS:
                self.naming.addItem(lab_, k_)
            self.naming.setToolTip("Les fréquences qui n'ont pas de nom dans le plan prennent le nom de leur appareil\n"
                                   "(par défaut) ou celui de leur groupe : « THE BROWNING · MICS 1 » se lit mieux en régie.\n"
                                   "Le modèle de l'appareil reste dans la note. Un nom écrit dans le plan est toujours gardé.")
            self.naming.currentIndexChanged.connect(lambda *_: self._naming_changed())
            nrow.addWidget(self.naming, 1)
            lay.addLayout(nrow)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Scène › groupe › fréquence", "MHz", "Appareil"])
        self.tree.setToolTip("Ce qui va arriver dans Mes fréquences : groupe EazyRF = scène, section = groupe."
                             if kind == "EazyRF" else "Ce qui va arriver dans Mes fréquences : scène › groupe › fréquence.")
        self._names = ezrf_profile_names(doc["devices"])
        self.tree.setMinimumHeight(150)
        lay.addWidget(self.tree, 1)
        self._fill_tree()

        form = QtWidgets.QFormLayout()
        self.status = QtWidgets.QComboBox()
        self.status.addItem("(aucun)", "")
        for st in owner.statuses:
            self.status.addItem(st["name"], st["name"])
        on = next((st["name"] for st in owner.statuses if st.get("on")), "")
        self.status.setCurrentIndex(max(0, self.status.findData(on)))
        self.status.setToolTip("Statut donné à chaque fréquence du plan. « Doit émettre » : alarme ABSENT si elle "
                               "disparaît, et c'est un émetteur pour Vérifier le plan.")
        form.addRow("Statut :", self.status)
        lay.addLayout(form)
        self.prof = QtWidgets.QCheckBox("Créer les profils d'appareil avec les réglages du plan (écart, filtre, "
                                        "tolérances, pas)")
        self.prof.setChecked(True)
        self.prof.setToolTip("Chaque appareil du plan devient un profil perso, posé sur son groupe : Vérifier le "
                             "plan et Coordonner utilisent alors ses réglages (écart, filtre, tolérances).")
        if not any("sep" in p for p in doc["devices"].values()):
            self.prof.setText("Relier les appareils à mes profils (même nom)")
        lay.addWidget(self.prof)
        self.skip = QtWidgets.QCheckBox(f"Ignorer les fréquences rayées / hors fonction ({n_off})")
        self.skip.setChecked(True)
        self.skip.setToolTip("Fréquences barrées, libérées ou dont l'appareil / la section est hors fonction "
                             "dans EazyRF.")
        self.skip.setVisible(n_off > 0)
        lay.addWidget(self.skip)
        self.interf = QtWidgets.QCheckBox(f"Ajouter les interférences notées dans EazyRF ({len(doc['interf'])}) "
                                          "comme émetteurs extérieurs")
        self.interf.setToolTip("Sans statut ni alarme, nommées « Ext. … » : Vérifier le plan et Coordonner en "
                               "tiennent compte.")
        self.interf.setVisible(bool(doc["interf"]))
        lay.addWidget(self.interf)
        sc_n = len(doc["scan"][0]) if doc["scan"] else 0
        self.scan = QtWidgets.QCheckBox(f"Garder le scan du document dans Scans par lieu ({sc_n} points)")
        self.scan.setChecked(bool(sc_n))
        self.scan.setToolTip("Le scan de fond enregistré dans le document EazyRF : affiché en pointillés sur le "
                             "spectre, utilisable par Coordonner.")
        self.scan.setVisible(bool(sc_n))
        lay.addWidget(self.scan)
        self.plan_chk = QtWidgets.QCheckBox("🎬 Créer le planning d'après les horaires des noms (« 15:00 - 15:40 »)")
        self.plan_chk.setToolTip("Chaque groupe dont le nom contient un horaire devient un créneau de 🎬 Planning : en dehors\n"
                                 "de son passage (avec les marges du planning), ses micros éteints ne déclenchent pas\n"
                                 "d'alarme ABSENT. Tu peux tout modifier ensuite dans 🎚 Surveiller › 🎬 Planning.")
        lay.addWidget(self.plan_chk)
        self._upd_plan_chk()
        self.follow = QtWidgets.QCheckBox(f"🔗 Suivre ce fichier : quand tu le réenregistres dans {kind}, proposer les "
                                          f"changements")
        self.follow.setToolTip(f"L'appli regarde le fichier toutes les 5 s ; s'il change, elle liste les fréquences "
                               f"ajoutées,\nmodifiées ou retirées dans {kind} et tu choisis ce que tu reprends.")
        self.follow.setChecked(bool(path))
        self.follow.setVisible(bool(path))
        lay.addWidget(self.follow)
        self.replace = QtWidgets.QCheckBox("Remplacer ma liste (sinon : ajouter)")
        self.replace.setToolTip("Coché : la liste actuelle est vidée avant l'import (Ctrl+Z pour revenir).")
        lay.addWidget(self.replace)
        if doc["tv"]:
            tv = QtWidgets.QLabel("Canaux TV actifs dans le document : " + ", ".join(map(str, doc["tv"]))
                                  + " (grisés sur le spectre et dans 📺 Canaux TNT ; suivis si tu suis le fichier).")
            tv.setWordWrap(True)
            lay.addWidget(tv)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Importer")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _build_map(self, lay, scenes):
        """🗂 Ranger les scènes du plan : chaque scène du document peut aller dans une autre scène (la vraie scène),
        son nom devenant un groupe. Proposé tout seul pour « T2 - … » -> « TERMINAL 2 »."""
        self.map_tbl = None
        if len(scenes) < 2:
            return
        auto = ezrf_auto_map(scenes, [s_["name"] for s_ in self.owner.scenes])
        box = QtWidgets.QGroupBox("🗂 Ranger les scènes du plan")
        v = QtWidgets.QVBoxLayout(box)
        hint = QtWidgets.QLabel(
            TR("{} scène(s) rangée(s) toute(s) seule(s) (« T2 - … » va dans « TERMINAL 2 »). Change la scène d'arrivée ou "
               "le groupe ligne par ligne ; l'aperçu en dessous suit.").format(len(auto)) if auto else
            "Choisis pour chaque scène du plan la scène où elle arrive (ex. un passage dans sa vraie scène).")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.map_tbl = QtWidgets.QTableWidget(len(scenes), 3)
        self.map_tbl.setHorizontalHeaderLabels(["Scène du plan", "Arrive dans la scène", "Groupe"])
        self.map_tbl.verticalHeader().setVisible(False)
        self.map_tbl.setToolTip("Scène d'arrivée : tape un nom ou choisis-en une (scènes du plan et de ta liste).\n"
                                "Groupe : garder les sections du plan (MICS / IEMS), prendre le nom d'origine (le passage),\n"
                                "ou les deux (« passage · MICS »).")
        choices = list(dict.fromkeys(scenes + [s_["name"] for s_ in self.owner.scenes]))
        for r, sc in enumerate(scenes):
            it = QtWidgets.QTableWidgetItem(sc)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.map_tbl.setItem(r, 0, it)
            dst = QtWidgets.QComboBox()
            dst.setEditable(True)
            dst.addItems(choices)
            mp = auto.get(sc)
            dst.setCurrentText(mp["scene"] if mp else sc)
            dst.currentTextChanged.connect(lambda *_: self._map_changed())
            self.map_tbl.setCellWidget(r, 1, dst)
            gm = QtWidgets.QComboBox()
            for k, t_ in EZRF_GROUP_MODES:
                gm.addItem(TR(t_), k)
            gm.setCurrentIndex(max(0, gm.findData(mp["group"] if mp else "keep")))
            gm.currentIndexChanged.connect(lambda *_: self._map_changed())
            self.map_tbl.setCellWidget(r, 2, gm)
        hh = self.map_tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c_, w_ in ((1, 190), (2, 210)):
            hh.setSectionResizeMode(c_, QtWidgets.QHeaderView.ResizeMode.Interactive)
            self.map_tbl.setColumnWidth(c_, w_)
        self.map_tbl.verticalHeader().setDefaultSectionSize(30)
        self.map_tbl.setMinimumHeight(min(4, len(scenes)) * 30 + 32)
        self.map_tbl.setMaximumHeight(min(300, 34 + 30 * len(scenes)))
        v.addWidget(self.map_tbl)
        h = QtWidgets.QHBoxLayout()
        b_auto = QtWidgets.QPushButton("Ranger automatiquement")
        b_auto.setToolTip("Reprend le rangement proposé (préfixe « T2 » = initiales de « TERMINAL 2 »).")
        b_auto.clicked.connect(lambda *_: self._map_set(auto))
        b_none = QtWidgets.QPushButton("Tout laisser comme dans le plan")
        b_none.setToolTip("Une scène par scène du plan, sections en groupes (comme avant).")
        b_none.clicked.connect(lambda *_: self._map_set({}))
        h.addWidget(b_auto)
        h.addWidget(b_none)
        h.addStretch(1)
        v.addLayout(h)
        lay.addWidget(box)

    def _map_set(self, mapping):
        if self.map_tbl is None:
            return
        for r in range(self.map_tbl.rowCount()):
            sc = self.map_tbl.item(r, 0).text()
            mp = mapping.get(sc)
            dst, gm = self.map_tbl.cellWidget(r, 1), self.map_tbl.cellWidget(r, 2)
            for w_ in (dst, gm):
                w_.blockSignals(True)
            dst.setCurrentText(mp["scene"] if mp else sc)
            gm.setCurrentIndex(max(0, gm.findData(mp["group"] if mp else "keep")))
            for w_ in (dst, gm):
                w_.blockSignals(False)
        self._map_changed()

    def mapping(self):
        """Rangement choisi -> {scène du plan: {scene, group, label}} (seulement ce qui change)."""
        out = {}
        if getattr(self, "map_tbl", None) is None:
            return out
        for r in range(self.map_tbl.rowCount()):
            sc = self.map_tbl.item(r, 0).text()
            dst = self.map_tbl.cellWidget(r, 1).currentText().strip() or sc
            mode = self.map_tbl.cellWidget(r, 2).currentData() or "keep"
            g = ezrf_scene_guess(sc, [dst])
            lab = g[1] if g else sc
            if dst != sc or mode != "keep":
                out[sc] = dict(scene=dst, group=mode, label=lab)
        return ezrf_map_norm(out)

    def entries(self):
        return ezrf_remap(self._ent0, self.mapping())

    def naming_key(self):
        return (self.naming.currentData() or "dev") if self.naming is not None else "dev"

    def _naming_changed(self):
        self._ent0 = ezrf_entries(self.doc, False, self.naming_key())
        self._map_changed()

    def _map_changed(self):
        self._fill_tree()
        self._upd_plan_chk()

    def _upd_plan_chk(self):
        if hasattr(self, "plan_chk"):
            n_ = len(ezrf_planning(self.entries()))
            self.plan_chk.setVisible(n_ > 0)
            self.plan_chk.setText(TR("🎬 Créer le planning d'après les horaires des noms ({} créneau(x))").format(n_))

    def _fill_tree(self):
        self.tree.clear()
        nodes = {}
        for name, f, sc, gr, dk, _note in self.entries():
            top = nodes.get((sc,))
            if top is None:
                top = nodes[(sc,)] = QtWidgets.QTreeWidgetItem(self.tree, [sc or "Sans scène", "", ""])
                top.setExpanded(True)
            par = top
            if gr:
                par = nodes.get((sc, gr))
                if par is None:
                    par = nodes[(sc, gr)] = QtWidgets.QTreeWidgetItem(top, [gr, "", ""])
                    par.setExpanded(True)
            QtWidgets.QTreeWidgetItem(par, [name, f"{f:.3f}", self._names.get(dk, "")])
        self.tree.resizeColumnToContents(0)

    def _build_pending(self, lay):
        """« À compléter » : canaux de récepteurs sans fréquence dans le fichier (Wisycom). Fréquence retrouvée par le
        nom dans ta liste (ou un autre plan) quand c'est possible ; sinon à taper."""
        box = QtWidgets.QGroupBox("À compléter : récepteurs sans fréquence dans le fichier")
        v = QtWidgets.QVBoxLayout(box)
        self.pend = QtWidgets.QTableWidget(len(self.doc["pending"]), 4)
        self.pend.setHorizontalHeaderLabels(["Canal", "Appareil", "MHz", "Trouvé (par le nom)"])
        self.pend.setToolTip("Tape la fréquence en MHz (ex. 578,050). Vide = pas importé. Retenu avec le suivi du "
                             "fichier : un nouvel enregistrement dans Wisycom Manager ne l'efface pas.")
        self.pend.verticalHeader().setVisible(False)
        for r, p_ in enumerate(self.doc["pending"]):
            for c, txt in enumerate((p_["name"], p_["model"])):
                it = QtWidgets.QTableWidgetItem(txt)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.pend.setItem(r, c, it)
            self.pend.setItem(r, 2, QtWidgets.QTableWidgetItem(""))
            it = QtWidgets.QTableWidgetItem("")
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.pend.setItem(r, 3, it)
        self.pend.horizontalHeader().setStretchLastSection(True)
        self.pend.setMinimumHeight(140)
        v.addWidget(self.pend)
        h = QtWidgets.QHBoxLayout()
        b = QtWidgets.QPushButton("📂 Chercher les noms dans un autre plan…")
        b.setToolTip("Un plan EazyRF, WWB, WSM… où ces canaux ont leur fréquence (par ex. « HF 1 DEPART » pour « DEP 1 ») :\n"
                     "les fréquences trouvées par le nom remplissent les cases vides.")
        b.clicked.connect(lambda *_: self._pend_from_file())
        self.pend_lbl = QtWidgets.QLabel("")
        h.addWidget(b)
        h.addWidget(self.pend_lbl, 1)
        v.addLayout(h)
        lay.addWidget(box)
        self._pend_match([(w["name"], w["freq"]) for w in self.owner.watch], "ta liste")

    def _pend_match(self, pool, where):
        names = [n for n, _f in pool]
        n = 0
        for r, p_ in enumerate(self.doc["pending"]):
            if self.pend.item(r, 2).text().strip():
                continue
            avoid = ("IEM",) if p_["model"].upper().startswith(("MRK", "MCR")) else ()
            i = name_match(p_["name"], names, avoid)
            if i is not None:
                self.pend.item(r, 2).setText(f"{pool[i][1]:.3f}")
                self.pend.item(r, 3).setText(f"{pool[i][0]} ({where})")
                n += 1
        left = sum(1 for r in range(self.pend.rowCount()) if not self.pend.item(r, 2).text().strip())
        self.pend_lbl.setText(f"{n} trouvée(s) dans {where} · {left} à compléter")
        return n

    def _pend_from_file(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Plan où chercher les noms", "", "Plans (*.ezrf3 *.shw *.cug *.wsm *.wshow *.acp);;Tous (*)")
            if not path:
                return 0
        try:
            doc, _k = parse_plan_file(Path(path).read_bytes(), os.path.basename(path))
        except (OSError, ValueError) as e:
            self.pend_lbl.setText(f"Illisible : {e}")
            return 0
        return self._pend_match([(e[0], e[1]) for e in ezrf_entries(doc, False)], os.path.basename(path))

    def manual(self):
        out = {}
        if self.pend is None:
            return out
        for r, p_ in enumerate(self.doc["pending"]):
            try:
                f = float(self.pend.item(r, 2).text().strip().replace(",", "."))
            except ValueError:
                continue
            if 1.0 <= f <= 7000.0:
                out[p_["name"]] = round(f, 5)
        return out

    def options(self):
        return dict(status=self.status.currentData() or "", profiles=self.prof.isChecked(), manual=self.manual(),
                    skip_off=self.skip.isChecked(), interf=self.interf.isChecked() and self.interf.isVisibleTo(self),
                    scan=self.scan.isChecked() and self.scan.isVisibleTo(self), replace=self.replace.isChecked(),
                    follow=self.follow.isChecked() and bool(self.path), kind=self.kind, map=self.mapping(),
                    naming=self.naming_key(), planning=self.plan_chk.isChecked() and self.plan_chk.isVisibleTo(self))


class RxProfileEdit(QtWidgets.QDialog):
    """Un profil perso : nom, filtre, écart, pas, tolérances, note."""

    def __init__(self, parent, prof):
        super().__init__(parent)
        self.setWindowTitle("Profil d'appareil perso")
        f = QtWidgets.QFormLayout(self)
        self.name = QtWidgets.QLineEdit(prof.get("name", ""))
        self.name.setPlaceholderText("ex. Sennheiser EW G4 groupe A")
        self.name.setToolTip("Nom affiché dans les listes d'appareils.")
        f.addRow("Nom :", self.name)

        def spin(v, lo, hi, step, suffix, tip, special=None, dec=0):
            sp = QtWidgets.QDoubleSpinBox()
            sp.setRange(lo, hi)
            sp.setDecimals(dec)
            sp.setSingleStep(step)
            sp.setSuffix(suffix)
            if special:
                sp.setSpecialValueText(special)
            sp.setValue(v)
            sp.setToolTip(tip)
            return sp
        self.filt = spin(prof.get("filt", 16.0), 0, 400, 4, " MHz", "Filtre d'entrée du récepteur. "
                         "0 = aucun : tous les émetteurs comptent.", "aucun")
        self.sep = spin(prof.get("sep", 0.4) * 1000, 0, 10000, 25, " kHz", "Écart minimal entre deux porteuses "
                        "(« Séparation »).")
        self.step = spin(prof.get("step", 0.025) * 1000, 1, 1000, 5, " kHz", "Pas de réglage de l'appareil "
                         "(« Incrément »).")
        t = prof.get("tol") or _TOL_EZ
        self.tol = {k: spin(t.get(k, 0.0) * 1000, 0, 2000, 10, " kHz", tip, "ignoré")
                    for k, tip in (("2tx3", "Tolérance 2 TX (2A − B). 0 = ignoré."),
                                   ("3tx3", "Tolérance 3 TX (A + B − C). 0 = ignoré."),
                                   ("5", "Tolérance 5ᵉ ordre. 0 = ignoré."))}
        f.addRow("Filtre récepteur :", self.filt)
        f.addRow("Écart mini :", self.sep)
        f.addRow("Pas :", self.step)
        f.addRow("2A − B :", self.tol["2tx3"])
        f.addRow("A + B − C :", self.tol["3tx3"])
        f.addRow("5ᵉ ordre :", self.tol["5"])
        self.img = spin(prof.get("img", 0.0), 0, 200, 0.1, " MHz", "Fréquence intermédiaire (FI) des récepteurs "
                        "analogiques, souvent 10,7 MHz :\nun émetteur à ± FI de la fréquence tombe sur sa fréquence "
                        "image. 0 = pas vérifié (récepteurs numériques).", "non vérifiée", 3)
        f.addRow("FI (fréquence image) :", self.img)
        self.note = QtWidgets.QLineEdit(prof.get("note", ""))
        self.note.setPlaceholderText("ex. valeurs de mon logiciel de coordination")
        self.note.setToolTip("Note affichée en bulle dans les listes.")
        f.addRow("Note :", self.note)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def value(self, key=""):
        return dict(key=key, name=self.name.text().strip() or "Mon appareil", filt=self.filt.value(),
                    sep=self.sep.value() / 1000.0, step=self.step.value() / 1000.0,
                    tol={k: sp.value() / 1000.0 for k, sp in self.tol.items()},
                    **({"img": self.img.value()} if self.img.value() > 0 else {}),
                    note=self.note.text().strip() or "Profil perso.")


COORD_NOTE = ("⚠ Coordination BASIQUE, pour vérifier et dépanner sur place à partir du spectre mesuré : elle ne "
              "remplace pas un logiciel de coordination. Pour construire ton plan, utilise un outil dédié, bien plus "
              "complet (EazyRF, Shure WWB, Sennheiser WSM, Soundbase…), puis importe-le ici pour le surveiller.")
TRADEMARKS = ("RF Technical Monitor n'est ni affilié ni approuvé par les éditeurs de ces logiciels ; leurs noms (marques de "
              "leurs propriétaires) servent seulement à dire avec quels fichiers il est compatible.")


def coord_note():
    """Rappel en tête des outils de coordination : RF Technical Monitor fait une coordination SIMPLE (vérifier, dépanner sur
    place) ; un vrai plan complet se construit dans un logiciel dédié (demande de Clément)."""
    lab = QtWidgets.QLabel(COORD_NOTE)
    lab.setWordWrap(True)
    lab.setStyleSheet("color:#d29922; font-size: 90%;")
    lab.setToolTip("RF Technical Monitor reste un moniteur : ses calculs reprennent les règles de base (écart, intermod "
                   "3ᵉ / 5ᵉ ordre,\nfiltre du récepteur), pas tout ce que fait un logiciel de coordination.\n"
                   + TRADEMARKS)
    return lab


class RxLibraryDialog(QtWidgets.QDialog):
    """📚 Bibliothèque d'appareils (.lst4) : importer « Appareils.lst4 », chercher un modèle, l'ajouter à mes profils
    (il garde ses valeurs : écart, filtre, pas, tolérances, plage)."""
    COLS = ["Appareil", "Type", "Plage MHz", "Écart", "Filtre", "2 TX", "3 TX", "5ᵉ", "Pas"]

    def __init__(self, owner, pick=False):
        super().__init__(owner)
        self.owner, self.pick = owner, pick
        self.setWindowTitle("Bibliothèque d'appareils (.lst4)")
        lay = QtWidgets.QVBoxLayout(self)
        self.head = QtWidgets.QLabel("")
        self.head.setWordWrap(True)
        b_imp = QtWidgets.QPushButton("📥 Importer Appareils.lst4…")
        b_imp.setToolTip("Un fichier de bibliothèque d'appareils (.lst4) déjà présent sur ce PC.")
        b_imp.clicked.connect(lambda *_: self.import_file())
        lay.addLayout(owner._row(self.head, None, b_imp))
        self.q = QtWidgets.QLineEdit()
        self.q.setPlaceholderText("🔎 Chercher : marque, modèle, gamme (ex. « slx-d g58 », « mrk980 », « psm 1000 »)…")
        self.q.setToolTip("Tous les mots tapés doivent apparaître dans le nom ou le type.")
        self.q.setClearButtonEnabled(True)
        self.q.textChanged.connect(lambda *_: self.fill())
        lay.addWidget(self.q)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setToolTip("Choisis un ou plusieurs appareils (Ctrl+clic), puis « Ajouter à mes profils ».")
        self.table.cellDoubleClicked.connect(lambda *_: self.add())
        lay.addWidget(self.table, 1)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        b_add = QtWidgets.QPushButton("＋ Ajouter à ce groupe" if pick else "＋ Ajouter à mes profils")
        b_add.setToolTip("Les appareils choisis deviennent des profils utilisables partout (vérifier le plan,\n"
                         "trouver N fréquences, fréquence de secours), gardés dans ta config et tes shows.")
        b_add.clicked.connect(lambda *_: self.add())
        close = QtWidgets.QPushButton("Fermer")
        close.clicked.connect(self.accept)
        lay.addLayout(owner._row(self.msg, None, b_add, close))
        self.resize(980, 600)
        self.rows = []
        self.fill()

    def fill(self):
        lib = self.owner.rx_library()
        self.head.setText(f"{len(lib)} appareils dans la bibliothèque." if lib else
                          "Pas encore de bibliothèque : importe un fichier .lst4.")
        self.rows = rx_library_find(lib, self.q.text())
        self.table.setRowCount(len(self.rows))
        for r, d in enumerate(self.rows):
            vals = (d["name"], d["type"], f"{d['lo']:g} – {d['hi']:g}" if d["hi"] else "",
                    f"{d['sep'] * 1000:.0f} kHz", f"{d['filt']:g} MHz" if d["filt"] else "aucun",
                    *[(f"±{d['tol'][t] * 1000:.0f}" if d["tol"][t] else "ignoré") for t in ("2tx3", "3tx3", "5")],
                    f"{d['step'] * 1000:g} kHz")
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QtWidgets.QTableWidgetItem(v))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def import_file(self, path=None):
        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Bibliothèque d'appareils (.lst4)", "",
                                                            "Bibliothèque (*.lst4 *.xml);;Tous les fichiers (*)")
            if not path:
                return
        try:
            lib = parse_lst4(Path(path).read_bytes())
        except Exception as e:  # noqa: BLE001
            self.msg.setText(f"Import impossible : {e}")
            return
        self.owner.set_rx_library(lib)
        self.fill()
        self.msg.setText(f"📚 {len(lib)} appareils importés.")

    def add(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        devs = [self.rows[r] for r in rows if r < len(self.rows)]
        if not devs:
            self.msg.setText("Choisis d'abord un appareil dans la liste.")
            return
        have = {n for _k, n, _d, _w in RX_CUSTOM}
        new = [rx_from_library(d) for d in devs if d["name"] not in have]
        if new:
            rx_set_custom(rx_custom_dump() + new)
            self.owner.rx_profiles_changed()
        self.msg.setText(f"✔ {len(new)} profil(s) ajouté(s)" + (f", {len(devs) - len(new)} déjà là" if len(devs) > len(new)
                                                                   else "") + ".")
        self.added = [d["name"] for d in devs]
        if self.pick:
            self.accept()


class RxProfilesDialog(QtWidgets.QDialog):
    """Tous les profils d'appareil : intégrés (lecture seule) et perso (créer, copier, modifier, supprimer)."""
    COLS = ["Appareil", "Filtre", "Écart", "Pas", "2A − B", "A + B − C", "5ᵉ", "Source"]

    def __init__(self, owner, current=None):
        super().__init__(owner)
        self.owner, self.current = owner, current
        self.setWindowTitle("Profils d'appareil (filtre, écart, pas, tolérances)")
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Profils intégrés en lecture seule ; « ＋ Nouveau » copie la ligne choisie (ou tes "
                                "réglages actuels) dans un profil perso modifiable. Les profils perso sont gardés "
                                "dans ta config et dans tes shows.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 2)
        lay.addWidget(info)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setToolTip("Double-clic sur un profil perso : le modifier.")
        self.table.cellDoubleClicked.connect(lambda *_: self.edit())
        lay.addWidget(self.table, 1)
        b_new = QtWidgets.QPushButton("＋ Nouveau (copie de la ligne)")
        b_new.setToolTip("Crée un profil perso à partir du profil choisi (ou d'une base 16 MHz si rien n'est choisi).")
        b_new.clicked.connect(lambda *_: self.new())
        b_cur = QtWidgets.QPushButton("＋ Depuis les réglages actuels")
        b_cur.setToolTip("Crée un profil perso avec l'écart, le filtre, le pas et les tolérances de la fenêtre "
                         "« Vérifier le plan ».")
        b_cur.clicked.connect(lambda *_: self.new(self.current))
        b_cur.setEnabled(current is not None)
        b_edit = QtWidgets.QPushButton("✏ Modifier")
        b_edit.setToolTip("Modifie le profil perso choisi.")
        b_edit.clicked.connect(lambda *_: self.edit())
        b_del = QtWidgets.QPushButton("🗑 Supprimer")
        b_del.setToolTip("Supprime le profil perso choisi (les fréquences qui l'utilisaient repassent « par défaut »).")
        b_del.clicked.connect(lambda *_: self.delete())
        b_help = QtWidgets.QPushButton("❓ Le filtre, c'est quoi ?")
        b_help.setToolTip("Explication du filtre récepteur et de chaque réglage.")
        b_help.clicked.connect(lambda *_: show_filter_help(self))
        b_lib = QtWidgets.QPushButton("📚 Bibliothèque (.lst4)…")
        b_lib.setToolTip("Mode expert : lire un fichier de bibliothèque d'appareils (.lst4) déjà présent sur ce PC.")
        b_lib.setVisible(bool(getattr(owner, "expert", False)))          # caché sauf en mode expert
        b_lib.clicked.connect(lambda *_: (RxLibraryDialog(owner).exec(), self.refresh()))
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.accept)
        lay.addLayout(owner._row(b_lib, b_new, b_cur, b_edit, b_del, None, b_help, close))
        self.resize(900, 520)
        self.refresh()

    def refresh(self):
        allp = rx_all()
        self.table.setRowCount(len(allp))
        for r, (k, n, d, why) in enumerate(allp):
            vals = (("✏ " + n) if k.startswith("perso_") else n, f"{d['filt']:g} MHz" if d["filt"] else "aucun",
                    f"{d['sep'] * 1000:.0f} kHz", f"{d['step'] * 1000:g} kHz",
                    *[(f"±{d['tol'][t] * 1000:.0f}" if d["tol"].get(t) else "ignoré") for t in ("2tx3", "3tx3", "5")],
                    RX_SRC_TXT.get(d.get("src"), ""))
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                it.setToolTip(why)
                it.setData(Qt.ItemDataRole.UserRole, k)
                self.table.setItem(r, c, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def _key(self):
        r = self.table.currentRow()
        it = self.table.item(r, 0) if r >= 0 else None
        return it.data(Qt.ItemDataRole.UserRole) if it is not None else None

    def _save(self, lst):
        rx_set_custom(lst)
        self.refresh()
        self.owner.rx_profiles_changed()

    def new(self, base=None):
        if base is None:
            d = rx_profile(self._key()) or dict(filt=16.0, sep=0.4, step=0.025, tol=dict(_TOL_EZ))
            name = rx_short(self._key()) + " (perso)" if self._key() else ""
            base = dict(d, name=name)
        dlg = RxProfileEdit(self, base)
        if dlg.exec():
            lst = rx_custom_dump()
            lst.append(dlg.value(""))
            self._save(lst)

    def edit(self):
        k = self._key()
        lst = rx_custom_dump()
        i = next((i for i, p in enumerate(lst) if p["key"] == k), None)
        if i is None:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Les profils intégrés ne se modifient pas : "
                                              "« ＋ Nouveau » en fait une copie perso modifiable.")
            return
        dlg = RxProfileEdit(self, lst[i])
        if dlg.exec():
            lst[i] = dlg.value(k)
            self._save(lst)

    def delete(self):
        k = self._key()
        lst = rx_custom_dump()
        if not any(p["key"] == k for p in lst):
            QtWidgets.QMessageBox.information(self, APP_NAME, "Seuls les profils perso se suppriment.")
            return
        self._save([p for p in lst if p["key"] != k])


class PlanCheckDialog(QtWidgets.QDialog):
    """Vérifie un plan de fréquences comme un logiciel de coordination : écart entre porteuses et
    intermod selon des tolérances, un verdict par fréquence, et une fréquence de remplacement compatible.
    Chaque fréquence peut avoir son profil d'appareil (w["rx"] : Wisycom très sélectif, Shure, Sennheiser…)."""
    COLS = ["État", "Nom", "MHz", "Appareil", "Problèmes"]

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Vérifier le plan de fréquences")
        self.resize(940, 660)
        self.ws, self.issues = [], []
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(coord_note())
        info = QtWidgets.QLabel(
            "Coordination simple : pour chaque fréquence, est-elle trop près d'une autre (écart entre "
            "porteuses), et un produit d'intermod de tes émetteurs tombe-t-il dessus (selon les tolérances) ? C'est un "
            "calcul, sans mesure. Les « doit rester libre » (réserves) sont protégées mais ne comptent pas comme "
            "émetteurs. Choisis une fréquence ✗ puis « Proposer » pour une remplaçante compatible.")
        info.setWordWrap(True)
        info.setMinimumHeight(info.fontMetrics().height() * 4)
        lay.addWidget(info)
        R = owner._row
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Plan : toute la liste", "all")
        self.src_combo.addItem("Plan : la couche active", "scope")
        self.src_combo.setToolTip("Les fréquences vérifiées ensemble (celles qui émettent en même temps au même endroit).")
        self.sep_spin = QtWidgets.QSpinBox()
        self.sep_spin.setRange(0, 10000)
        self.sep_spin.setSingleStep(25)
        po = owner.plan_opts
        self.sep_spin.setValue(int(po["sep"]))
        self.sep_spin.setSuffix(" kHz")
        self.sep_spin.setToolTip("Écart minimal entre deux porteuses (bord à bord pour un bloc large).\n"
                                 "« Séparation » d'un profil d'appareil (500 kHz pour un Wisycom MRK980).")
        self.filt_spin = QtWidgets.QDoubleSpinBox()
        self.filt_spin.setRange(0, 400)
        self.filt_spin.setDecimals(0)
        self.filt_spin.setSingleStep(4)
        self.filt_spin.setSuffix(" MHz")
        self.filt_spin.setSpecialValueText("aucun")
        self.filt_spin.setValue(float(po["filt"]))
        self.filt_spin.setToolTip("Largeur du filtre d'entrée du récepteur (« Filtre » d'un profil d'appareil : 32 MHz "
                                  "pour un Wisycom MRK980).\nUn produit d'intermod ne gêne une fréquence que si TOUS ses "
                                  "émetteurs sont à ± la valeur du filtre\nautour d'elle : les émetteurs plus loin sont "
                                  "coupés par le filtre du récepteur.\naucun (0) = tous les émetteurs comptent (plus strict).")
        self.step_spin = QtWidgets.QSpinBox()
        self.step_spin.setRange(1, 1000)
        self.step_spin.setSuffix(" kHz")
        self.step_spin.setValue(int(po["step"]))
        self.step_spin.setToolTip("Pas des fréquences proposées (« Incrément ») : le pas réglable de tes "
                                  "appareils.\n5 kHz pour un Wisycom MRK980, 25 kHz pour un MTK952.")
        self.prof_combo = QtWidgets.QComboBox()
        fill_rx_combo(self.prof_combo, "✏ Réglages ci-dessous")
        self.prof_combo.setToolTip("Appareil par défaut : remplit écart, filtre, pas et tolérances.\nLes fréquences "
                                   "avec leur propre appareil (colonne « Appareil ») gardent le leur.\nTous tes "
                                   "modèles : 🎛 Profils d'appareil.")
        self.tol_combo = QtWidgets.QComboBox()
        fill_rules_combo(self.tol_combo)
        self.tol_combo.setToolTip("Quelle sévérité ? Survole chaque choix pour l'explication.\n"
                                  "Standard = les tolérances les plus courantes (2 TX 100 kHz, 3 TX 50 kHz).")
        self.tol_spins = {}
        for key in ("2tx3", "3tx3", "5"):
            sp = QtWidgets.QSpinBox()
            sp.setRange(0, 2000)
            sp.setSingleStep(10)
            sp.setPrefix("± ")
            sp.setSuffix(" kHz")
            sp.setSpecialValueText("ignoré")
            sp.setToolTip({"2tx3": "2 TX, 3ᵉ ordre (2A − B).", "3tx3": "3 TX, 3ᵉ ordre (A + B − C).",
                           "5": "5ᵉ ordre et plus."}[key] + "\n0 = ignoré.")
            self.tol_spins[key] = sp
        self.rule_lbl = QtWidgets.QLabel("")
        self.rule_lbl.setWordWrap(True)
        self.rule_lbl.setMinimumHeight(self.rule_lbl.fontMetrics().height() * 3)
        self.tol_combo.currentIndexChanged.connect(lambda *_: (self._prof_touched(), self._preset()))
        for sp in self.tol_spins.values():
            sp.valueChanged.connect(lambda *_: self._custom())
        self.sep_spin.valueChanged.connect(lambda *_: self._explain())
        self.filt_spin.valueChanged.connect(lambda *_: self._explain())
        self._preset()
        ix = self.prof_combo.findData(po.get("prof", ""))
        self.prof_combo.setCurrentIndex(max(0, ix))
        self._prof_default()
        self.prof_combo.currentIndexChanged.connect(lambda *_: self._prof_default())
        for sp in (self.sep_spin, self.filt_spin, self.step_spin):
            sp.valueChanged.connect(lambda *_: self._prof_touched())
        self.go_btn = QtWidgets.QPushButton("🧮 Vérifier")
        self.go_btn.setToolTip("Calcule la compatibilité de tout le plan.")
        self.go_btn.clicked.connect(lambda *_: self.compute())
        b_prof = QtWidgets.QPushButton("✏ Mes profils…")
        b_prof.setToolTip("Tous les profils d'appareil, et tes profils perso (ton filtre, ton écart, tes tolérances).")
        b_prof.clicked.connect(lambda *_: self.edit_profiles())
        b_help = QtWidgets.QPushButton("❓ Le filtre ?")
        b_help.setToolTip("Le filtre récepteur, c'est quoi, et pourquoi il change le calcul d'intermod.")
        b_help.clicked.connect(lambda *_: show_filter_help(self))
        lay.addLayout(R(self.src_combo, "Appareil par défaut :", self.prof_combo, b_prof, b_help, None, self.go_btn))
        lay.addLayout(R("Règles :", self.tol_combo, None))
        lay.addLayout(R("Écart mini :", self.sep_spin, "Filtre récepteur :", self.filt_spin, "Pas :", self.step_spin,
                        None))
        lay.addLayout(R("2A − B :", self.tol_spins["2tx3"], "A + B − C :", self.tol_spins["3tx3"], "5ᵉ ordre :",
                        self.tol_spins["5"], None))
        lay.addWidget(self.rule_lbl)
        self.sum_lbl = QtWidgets.QLabel("")
        f_ = self.sum_lbl.font()
        f_.setPointSize(f_.pointSize() + 3)
        f_.setBold(True)
        self.sum_lbl.setFont(f_)
        self.sum_lbl.setWordWrap(True)
        lay.addWidget(self.sum_lbl)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        for c, w_ in enumerate((120, 140, 80, 130)):
            self.table.setColumnWidth(c, w_)
        self.table.setToolTip("Survole « Problèmes » pour le détail complet. Double-clic : proposer une remplaçante.\n"
                              "Sélection multiple (Maj / Ctrl) pour donner un appareil à plusieurs fréquences.")
        self.table.cellDoubleClicked.connect(lambda r, c: self.suggest())
        lay.addWidget(self.table, 1)
        self.rx_combo = QtWidgets.QComboBox()
        fill_rx_combo(self.rx_combo, "par défaut (appareil ci-dessus)")
        self.rx_combo.setToolTip("L'appareil (récepteur) des fréquences choisies dans le tableau : son filtre, son écart, "
                                 "ses tolérances\net son pas comptent pour ELLES. Enregistré dans ta liste (et tes shows).")
        self.rx_btn = QtWidgets.QPushButton("Appliquer aux lignes choisies")
        self.rx_btn.setToolTip("Donne cet appareil aux fréquences sélectionnées, puis recalcule.")
        self.rx_btn.clicked.connect(lambda *_: self.set_rx())
        lay.addLayout(R("Appareil des lignes choisies :", self.rx_combo, self.rx_btn, None))
        self.sug_list = QtWidgets.QListWidget()
        self.sug_list.setMaximumHeight(110)
        self.sug_list.setToolTip("Fréquences compatibles avec tout le reste du plan, les plus proches d'abord.")
        self.avoid_chk = QtWidgets.QCheckBox("Éviter ce que le tinySA voit occupé")
        self.avoid_chk.setChecked(True)
        self.avoid_chk.setToolTip("Écarte les fréquences où le spectre mesuré dépasse ton seuil « faible »\n"
                                  "(ou « occupé » si le niveau faible est désactivé).")
        self.sug_btn = QtWidgets.QPushButton("🔍 Proposer une fréquence compatible")
        self.sug_btn.setToolTip("Pour la fréquence choisie : cherche à ± 10 MHz une fréquence sans aucun problème,\n"
                                "qui n'en crée pas de nouveau pour les autres.")
        self.sug_btn.clicked.connect(lambda *_: self.suggest())
        self.rep_btn = QtWidgets.QPushButton("✔ Remplacer")
        self.rep_btn.setToolTip("Remplace la fréquence choisie par la proposition sélectionnée (dans ta liste).")
        self.rep_btn.clicked.connect(lambda *_: self.replace())
        close = QtWidgets.QPushButton("Fermer")
        close.setToolTip("Ferme la fenêtre.")
        close.clicked.connect(self.close)
        lay.addLayout(R(self.sug_btn, self.avoid_chk, None))
        lay.addWidget(self.sug_list)
        lay.addLayout(R(self.rep_btn, None, close))
        self._target = None
        self.compute()

    def _prof_default(self):
        """Profil par défaut choisi : remplit écart, filtre, pas et tolérances."""
        d = rx_profile(self.prof_combo.currentData())
        self.owner.plan_opts["prof"] = self.prof_combo.currentData() or ""
        if d is None:
            return
        self._filling = True
        self.sep_spin.setValue(int(round(d["sep"] * 1000)))
        self.filt_spin.setValue(d["filt"])
        self.step_spin.setValue(int(round(d["step"] * 1000)))
        ix = next((k for k in range(self.tol_combo.count() - 1) if self.tol_combo.itemData(k) == d["tol"]),
                  self.tol_combo.count() - 1)
        self.tol_combo.setCurrentIndex(ix)
        if ix == self.tol_combo.count() - 1:
            self._applying = True
            for k, sp in self.tol_spins.items():
                sp.setValue(int(round(d["tol"][k] * 1000)))
            self._applying = False
        self._filling = False
        self._explain()

    def edit_profiles(self):
        cur = dict(name="", sep=self.sep_spin.value() / 1000.0, filt=self.filt_spin.value(),
                   step=self.step_spin.value() / 1000.0, tol=self.tolerances())
        RxProfilesDialog(self.owner, cur).exec()

    def refill_profiles(self):
        fill_rx_combo(self.prof_combo, "✏ Réglages ci-dessous")
        fill_rx_combo(self.rx_combo, "par défaut (appareil ci-dessus)")
        self.compute()

    def _prof_touched(self):
        if not getattr(self, "_filling", False) and self.prof_combo.currentData():
            self.prof_combo.blockSignals(True)
            self.prof_combo.setCurrentIndex(0)                 # on a touché un réglage : « ✏ Réglages ci-dessous »
            self.prof_combo.blockSignals(False)
            self.owner.plan_opts["prof"] = ""

    def set_rx(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.ws)})
        if not rows:
            self.sum_lbl.setText("Choisis d'abord une ou plusieurs fréquences dans le tableau.")
            return
        key = self.rx_combo.currentData()
        for r in rows:
            if key:
                self.ws[r]["rx"] = key
            else:
                self.ws[r].pop("rx", None)
        self._explain()
        self.compute()
        self.owner.set_status(f"{len(rows)} fréquence(s) : appareil « {rx_short(key)} ».")

    def _preset(self):
        d = self.tol_combo.currentData()
        if d is not None:
            self._applying = True
            for k, sp in self.tol_spins.items():
                sp.setValue(int(round(d[k] * 1000)))
            self._applying = False
        self._explain()

    def _custom(self):
        self._prof_touched()
        if not getattr(self, "_applying", False):
            self.tol_combo.blockSignals(True)
            self.tol_combo.setCurrentIndex(self.tol_combo.count() - 1)
            self.tol_combo.blockSignals(False)
        self._explain()

    def _explain(self):
        why = self.tol_combo.itemData(self.tol_combo.currentIndex(), Qt.ItemDataRole.ToolTipRole) or ""
        own = sum(1 for w in self.owner.watch if self.owner.rx_of(w))
        self.rule_lbl.setText(f"<b>{self.tol_combo.currentText()}</b> — {why}<br>"
                              + im_rules_text(self.tolerances(), self.sep_spin.value() / 1000.0,
                                              self.filt_spin.value()) + "."
                              + (f"<br>{own} fréquence(s) ont leur propre appareil (colonne « Appareil ») : ce sont "
                                 "ses réglages qui comptent pour elles." if own else ""))

    def tolerances(self):
        t5 = self.tol_spins["5"].value() / 1000.0
        return {"2tx3": self.tol_spins["2tx3"].value() / 1000.0, "3tx3": self.tol_spins["3tx3"].value() / 1000.0,
                "5": t5, "7": t5}

    def _params(self):
        o = self.owner
        o.plan_opts.update(sep=self.sep_spin.value(), filt=self.filt_spin.value(), step=self.step_spin.value())
        ws = [w for w in o.watch if (self.src_combo.currentData() == "all" or o.in_scope(w))
              and not w.get("off")]                  # 📸 en pause dans l'état actif : n'émet pas
        dflt = dict(sep=self.sep_spin.value() / 1000.0, filt=self.filt_spin.value(), tol=self.tolerances(),
                    step=self.step_spin.value() / 1000.0)
        P = [rx_profile(o.rx_of(w)) or dflt for w in ws]            # appareil de chaque fréquence (ou de son groupe)
        self._steps = [q["step"] for q in P]
        self._imgs = [float(q.get("img") or 0.0) for q in P]       # FI : fréquence image (analogiques)
        self._bands = [rx_band(q) for q in P]                        # 7.61 : bande de l'appareil (bibliothèque, plan)
        return (ws, [w["freq"] for w in ws], [not o.is_keep_free(w["status"]) for w in ws],
                [float(w.get("bw") or 0.0) for w in ws], [q["sep"] for q in P], [q["tol"] for q in P], None,
                [q["filt"] for q in P])

    def compute(self):
        ws, F, T, B, sep, tol, mx, filt = self._params()
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.issues, info = pf_check(F, T, B, sep, tol, mx, filt, self._imgs)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        for r, bd in enumerate(self._bands):         # 7.61 : réglée hors de la bande de son appareil
            it = band_issue(F[r], B[r], bd)
            if it:
                self.issues[r].insert(0, it)
        self.ws = ws
        names = [w["name"] or f"{w['freq']:.3f}" for w in ws]
        th, base = self.owner.theme, self.owner.theme["ui_base"]
        t = self.table
        t.setRowCount(len(ws))
        bad = 0
        for r, (w, iss) in enumerate(zip(ws, self.issues)):
            bad += bool(iss)
            txts = [pf_issue_text(it, names, F) for it in iss]
            state = "✔ compatible" if not iss else f"✗ {len(iss)} problème{'s' if len(iss) > 1 else ''}"
            if not T[r] and not iss:
                state = "✔ réserve libre"
            vals = [state, names[r], f"{w['freq']:.3f}", rx_short(self.owner.rx_of(w)),
                    " · ".join(txts[:3]) + (" …" if len(txts) > 3 else "")]
            col = th["st_occ"] if iss else th["st_free"]
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c == 0:
                    bg = blend(col, base, 0.7)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                if c == 4 and txts:
                    it.setToolTip("\n".join(txts))
                t.setItem(r, c, it)
        n = len(ws)
        self.too_big = bool(info.get("too_big"))
        if self.too_big:
            self.sum_lbl.setText("⚠ Trop de combinaisons pour calculer l'intermod (seuls les écarts sont vérifiés) : "
                                 "passe en « 2 TX seulement », ignore le 5ᵉ ordre, ou vérifie une couche à la fois.")
        elif not n:
            self.sum_lbl.setText("Aucune fréquence à vérifier.")
        elif info.get("reduced") and not bad:
            self.sum_lbl.setText(f"✔ {n} / {n} sans problème au 3ᵉ ordre. ⚠ 5ᵉ ordre NON vérifié : trop de combinaisons "
                                 "avec autant d'émetteurs (vérifie une couche à la fois pour l'avoir).")
        elif not bad:
            self.sum_lbl.setText(f"✔ Plan compatible : {n} / {n} fréquences sans problème (pour ces règles).")
        else:
            kinds = {"sep": 0, "img": 0, "band": 0, "2tx3": 0, "3tx3": 0, "5": 0}
            for iss in self.issues:
                for it in iss:
                    k_ = it["kind"] if it["kind"] in ("sep", "img", "band") else im_class(it["order"], it["ntx"])
                    kinds[k_ if k_ in kinds else "5"] += 1
            det = " · ".join(f"{v} {lab}" for lab, v in (("écart trop faible", kinds["sep"]), ("2A − B", kinds["2tx3"]),
                                                          ("A + B − C", kinds["3tx3"]), ("5ᵉ ordre", kinds["5"]),
                                                          ("fréquence image", kinds["img"]),
                                                          ("hors de la bande de l'appareil", kinds["band"])) if v)
            self.sum_lbl.setText(f"✗ {bad} fréquence(s) à revoir sur {n} · ✔ {n - bad} compatibles ({det}). "
                                 "Choisis une ligne ✗ puis « Proposer »."
                                 + ("\n⚠ 5ᵉ ordre NON vérifié (trop de combinaisons) : seul le 3ᵉ ordre l'est."
                                    if info.get("reduced") else ""))
        self.sum_lbl.setStyleSheet(f"color:{th['st_free'] if n and not bad else th['st_occ'] if bad else th['ui_text']}")
        self.sug_list.clear()
        self._target = None

    def _sel(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return rows[0] if rows and rows[0] < len(self.ws) else None

    def suggest(self):
        r = self._sel()
        self.sug_list.clear()
        if getattr(self, "too_big", False):
            self.sum_lbl.setText("⚠ Calcul trop gros : passe en « 2 TX seulement » ou ignore le 5ᵉ ordre, puis Vérifier.")
            return
        if r is None:
            self.sum_lbl.setText("Choisis d'abord une fréquence dans le tableau.")
            return
        ws, F, T, B, sep, tol, mx, filt = self._params()
        busy = None
        if self.avoid_chk.isChecked():
            o = self.owner
            Fm, Lm = o.fresh_FL(use_max=True)
            if Fm is not None:
                lim = o.busy_limit(Lm, weak=True)
                win = max(0.05, o.win_spin.value() / 1000.0)
                busy = busy_pred(Fm, Lm, lim, win)
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            kw = dict(n=6, busy=self.owner.reg_busy(busy), step=self._steps[r], filt=filt, img=self._imgs)   # pas de l'appareil de cette fréquence
            bd = self._bands[r]                          # 7.61 : jamais hors de la bande de son appareil
            near = band_clip(F[r] - 10.0, F[r] + 10.0, bd, B[r])
            sg = pf_suggest(r, F, T, B, sep, tol, mx, lo=near[0], hi=near[1], **kw) if near else []
            if not sg:                                  # rien tout près : on cherche dans toutes les bandes
                ext = self.owner._band_extent()
                ext = band_clip(ext[0], ext[1], bd, B[r]) if ext else (band_clip(bd[0], bd[1], bd, B[r]) if bd else None)
                if ext:
                    sg = pf_suggest(r, F, T, B, sep, tol, mx, lo=ext[0], hi=ext[1], max_check=1500, **kw)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self._target = ws[r]
        name = ws[r]["name"] or f"{ws[r]['freq']:.3f}"
        if not sg:
            self.sug_list.addItem(f"Rien de compatible pour {name} dans tes bandes : élargis les tolérances, baisse "
                                  "l'écart mini ou décoche « Éviter ce que le tinySA voit occupé ».")
            if bd:
                self.sug_list.addItem(f"Recherche limitée à la bande de son appareil : {bd[0]:g}–{bd[1]:g} MHz.")
            return
        for c, d in sg:
            rt = self.owner.reg_tag(c)
            it = QtWidgets.QListWidgetItem(f"{c:.3f} MHz   ({d * 1000:+.0f} kHz)   pour {name}"
                                           + (f"   ⚠ {TR(rt)}" if rt else ""))
            it.setData(Qt.ItemDataRole.UserRole, c)
            self.sug_list.addItem(it)
        self.sug_list.setCurrentRow(0)

    def replace(self):
        it = self.sug_list.currentItem()
        c = it.data(Qt.ItemDataRole.UserRole) if it is not None else None
        w = self._target
        if c is None or w is None or not any(x is w for x in self.owner.watch):
            self.sum_lbl.setText("Propose d'abord une fréquence, puis choisis-la dans la liste.")
            return
        old = w["freq"]
        self.owner.set_watch_freq(w, c)
        self.owner.log_event(dict(name=w["name"], freq=0.0, note=f"{old:.3f} → {c:.3f} MHz (vérification du plan)"),
                             0.0, "NOUVELLE FRÉQUENCE")
        self.compute()
        self.owner.set_status(f"{w['name']} : {old:.3f} → {c:.3f} MHz (plan vérifié).")
