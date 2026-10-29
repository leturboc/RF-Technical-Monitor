"""Lance la VRAIE appli PySide6 (sans écran, QT_QPA_PLATFORM=offscreen) en mode démo, ouvre panneaux et
dialogues, capture des PNG et relève les exceptions Qt. Complète les smoke_test* (faux Qt).

    python tests/gui_reel.py [dossier_captures]        (défaut : tests/captures, ignoré par git)

Sous Linux il faut PySide6 + libEGL/libGL (apt install libegl1 libgl1 libxkbcommon0 fonts-noto-color-emoji).
Ne remplace pas un essai sur Windows : sons, vrai port série, double écran et rendu natif ne sont pas testés."""
import os, sys, tempfile, traceback, importlib.util, time
import numpy as np
if sys.platform != "win32":       # Windows : vrai rendu (le mode offscreen n'y a aucune police)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="tsm_real_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "captures")
SRC = os.path.join(HERE, "..", "tinysa_monitor.py")
os.makedirs(OUT, exist_ok=True)

errors = []
def hook(t, v, tb):
    s = "".join(traceback.format_exception(t, v, tb))
    errors.append(s)
    print("!!! EXCEPTION\n" + s, flush=True)
sys.excepthook = hook

spec = importlib.util.spec_from_file_location("tsm", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
W = QtWidgets

app = W.QApplication(sys.argv)
if sys.platform != "win32":
    app.setFont(QtGui.QFont("DejaVu Sans", 9))
_f = app.font()
print(f"OK   police : {QtGui.QFontInfo(_f).family()} {_f.pointSize()} pt · "
      f"{QtGui.QFontMetrics(_f).averageCharWidth()} px/car · dpi {app.primaryScreen().logicalDotsPerInch():.0f}",
      flush=True)

def wait(ms):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()

shots = []
def shot(widget, name):
    app.processEvents()
    p = os.path.join(OUT, f"{len(shots):02d}_{name}.png")
    widget.grab().save(p)
    shots.append(p)
    print("capture", p, widget.size().width(), "x", widget.size().height(), flush=True)

msgs = []
def fake_box(kind):
    def f(parent, title, text, *a, **k):
        msgs.append((kind, text))
        print(f"[QMessageBox.{kind}] {text!r}", flush=True)
        return W.QMessageBox.StandardButton.Yes
    return staticmethod(f)
for k in ("warning", "information", "critical", "question"):
    setattr(W.QMessageBox, k, fake_box(k))

opened, saved = [], []
W.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (opened.pop(0) if opened else "", ""))
W.QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: (list(opened), ""))
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved.pop(0) if saved else "", ""))

W.QInputDialog.getDouble = staticmethod(lambda *a, **k: (606.5, True))
W.QInputDialog.getItem = staticmethod(lambda p, t, l, items, *a, **k: (items[0], True))
W.QInputDialog.getMultiLineText = staticmethod(lambda *a, **k: ("HF X;620.125\nHF Y;621.250", True))
W.QInputDialog.getText = staticmethod(lambda *a, **k: ("Test", True))
# exec() modal -> on affiche, on capture, puis action (accept / reject)
DLG_ACTION = ["reject"]
_orig_exec = W.QDialog.exec
def fake_exec(self):
    self.show()
    wait(300)
    shot(self, "dlg_" + type(self).__name__)
    act = DLG_ACTION[0]
    if callable(act):
        act = act(self)                  # une action perso peut renvoyer "accept" pour valider (OK)
    if act == "accept":
        self.accept()
        return 1
    self.reject()
    return 0
W.QDialog.exec = fake_exec

def step(label, fn):
    print(f"--- {label}", flush=True)
    try:
        r = fn()
        app.processEvents()
        return r
    except Exception:
        hook(*sys.exc_info())
        return None

fails = 0
def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra, flush=True)

import gc as _gc
_gct = m.install_gc_main_thread(app, 100)        # comme dans main() : ramasse-miettes dans le fil de l'interface
check("ramasse-miettes : automatique coupé (fil de l'interface seulement)", not _gc.isenabled())
class _Cyc:
    pass
_c = _Cyc(); _c.me = _c
import weakref as _wr
_ref = _wr.ref(_c)
del _c
for _ in range(_gc.get_threshold()[0] + 50):        # des déchets en cycle, comme l'interface en produit
    _x = _Cyc()
    _x.me = _x
del _x
_l = QtCore.QEventLoop(); QtCore.QTimer.singleShot(400, _l.quit); _l.exec()
check("ramasse-miettes : les cycles sont quand même nettoyés (par le minuteur)", _ref() is None)
check("traductions Qt en français chargées", m.install_french(app))
_bb = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Yes | W.QDialogButtonBox.StandardButton.Cancel)
_txt = (_bb.button(W.QDialogButtonBox.StandardButton.Yes).text(), _bb.button(W.QDialogButtonBox.StandardButton.Cancel).text())
check("boutons standard en français", _txt == ("&Oui", "&Annuler") or "Oui" in _txt[0], str(_txt))

win = m.MainWindow()
win.log_dir = m.Path(tmp) / "journaux"
win.resize(1700, 980)
win.show()
wait(600)
shot(win, "demarrage")
# 1er lancement : mode ULTRA SIMPLE (spectre + liste + alarmes), parcours dans l'ordre, tuto proposé
check("1er lancement : ultra simple (réglages et classement cachés)", win.ui_level == "ultra"
      and not win.dock_set.isVisible() and not win.layer_box.isVisible(), win.ui_level)
check("parcours : ① scan › ② liste › ③ plan › ④ intermod › ⑤ show › ⑥ après",
      [b.text()[:1] for b in win.step_btns.values()] == ["①", "②", "③", "④", "⑤", "⑥"],
      str([b.text() for b in win.step_btns.values()]))
check("1er lancement : tuto proposé", "Tuto" in win.tour_btn.text() and not win.tour_done)
step("🎓 tuto", win.start_tour)
_tr = win._tour
if _tr is not None:
    _n = len(_tr.steps)
    shot(_tr, "tuto_1")
    for _k in range(_n - 1):
        _tr.next_btn.click()
        app.processEvents()
    check("tuto : toutes les étapes, dernière = Terminer", _tr.i == _n - 1 and "✔" in _tr.next_btn.text()
          and _n >= 10, f"{_tr.i}/{_n}")
    _w_last = _tr.steps[-1][0]
    _tr.next_btn.click()
    app.processEvents()
    check("tuto terminé : retenu, surlignage retiré", win.tour_done and "f5a623" not in _w_last.styleSheet())
shot(win, "ultra_simple")
step("passer en simple", lambda: win.set_level("simple"))
check("simple : réglages et classement visibles", win.dock_set.isVisible() and win.layer_box.isVisible())

# fréquences + couches
win.ensure_group("Grande scène", "Micros HF")
win.ensure_group("Grande scène", "IEM")
win.ensure_group("Grande scène", "Libres")
win.set_prio(("Grande scène", "Micros HF"), 2)
F0 = [470.2, 471.8, 474.4, 477.9, 480.3, 483.6, 488.1, 492.5, 503.5, 512.0, 525.25, 538.9, 552.4, 566.1, 580.0]
for i, f in enumerate(F0):
    grp = "Micros HF" if i < 6 else ("IEM" if i < 12 else "Libres")
    st = "Libre" if grp == "Libres" else "En service"
    win._append_watch(f"{'HF' if i < 6 else ('IEM' if i < 12 else 'Libre')} {i+1}", f, status=st,
                      scene="Grande scène", group=grp)
win.sort_watch(); win.rebuild_tree(); win.rebuild_watch_table()
win.absent_spin.setValue(5) if hasattr(win, "absent_spin") else None

win.demo_chk.setChecked(True)
_sess_dir = os.path.join(tmp, "sessions")
win.session_cfg.update(dir=_sess_dir, ask=True, rec=True)
DLG_ACTION[0] = "reject"
step("Démarrer → « Enregistrer la session ? » › Annuler", win.toggle_run)
check("session : Annuler ne démarre pas", not win.is_running() and win._session is None)
DLG_ACTION[0] = "accept"                 # « 💾 Enregistrer et démarrer » (bouton par défaut)
step("Démarrer", win.toggle_run)
DLG_ACTION[0] = "reject"
check("session : enregistrement lancé dans le dossier choisi", win._session is not None
      and str(win._session).startswith(_sess_dir) and win.recorder is not None, str(win._session))
win.session_cfg["ask"] = False           # les démarrages suivants du test : sans question (même choix)
_dj = [x for x in win.findChildren(W.QDockWidget) if x.objectName() == "dock_journal"][0]
win._set_rec_lbl("💾 Session → C:\\Users\\runneradmin\\AppData\\Local\\Temp\\tsm_real_abcdefgh\\sessions\\2026-10-29_1045")
app.processEvents()
check("journal : un long chemin de session n'élargit pas la colonne (vu sous Windows)",
      _dj.minimumSizeHint().width() <= 300, str(_dj.minimumSizeHint().width()))
wait(8000)
shot(win, "demo_tout_spectre")

# vues par bande
for i in range(1, min(win.view_combo.count(), 3)):
    step(f"vue {i}", lambda i=i: win.view_combo.setCurrentIndex(i))
    wait(3500)
    shot(win, f"vue_bande_{i}")
step("vue globale", lambda: win.view_combo.setCurrentIndex(0)); wait(1500)

# repères : menu réel, filtres, style discret, tout masquer
win.mk_menu.aboutToShow.emit()
acts = {a.text(): a for a in win.mk_menu.actions() if a.text()}
for sub in [a.menu() for a in win.mk_menu.actions() if a.menu() is not None]:
    acts.update({a.text(): a for a in sub.actions() if a.text()})
check("menu repères (vrai Qt) : complet", {"Occupées", "Libres", "Noms des fréquences", "Petit repère discret en haut",
                                          "Grande scène › IEM", "(sans statut)"} <= set(acts), str(sorted(acts)))
win.mk_menu.popup(win.mk_btn.mapToGlobal(win.mk_btn.rect().bottomLeft()))
wait(500)
shot(win.mk_menu, "menu_reperes")
win.mk_menu.hide()
win.mk_menu.aboutToShow.emit()          # l'ouverture a reconstruit le menu : on relit les actions
acts = {a.text(): a for a in win.mk_menu.actions() if a.text()}
for sub in [a.menu() for a in win.mk_menu.actions() if a.menu() is not None]:
    acts.update({a.text(): a for a in sub.actions() if a.text()})
acts["Grande scène › IEM"].trigger()
acts["Libres"].trigger()
wait(600)
check("filtres appliqués (vrai Qt)", "IEM" in "".join(win.mk["hide_layers"]) and "free" not in win.mk["states"]
      and win.mk_btn.text().endswith("(filtrés)"), str(win.mk) + win.mk_btn.text())
win.set_markers(style="top")
wait(800)
shot(win, "reperes_filtres_discrets")
win.reset_markers()


def click(txt):
    """Comme à la souris : le menu est reconstruit à chaque ouverture, puis on clique l'entrée."""
    win.mk_menu.aboutToShow.emit()
    acts_ = {a.text(): a for a in win.mk_menu.actions() if a.text()}
    for sub_ in [a.menu() for a in win.mk_menu.actions() if a.menu() is not None]:
        acts_.update({a.text(): a for a in sub_.actions() if a.text()})
    acts_[txt].trigger()
    app.processEvents()


# chaque case doit marcher dans LES DEUX sens (bug v7.1 : impossible de recocher à la souris)
for txt, get in (("Masquer tous les repères  (Ctrl+M)", lambda: not win.mk["on"]),
                 ("Signaux inconnus (pointillés)", lambda: win.mk["unk"]),
                 ("Libres", lambda: "free" in win.mk["states"]),
                 ("Toujours montrer les fréquences en alarme", lambda: win.mk["alarms"]),
                 ("Noms des fréquences", lambda: win.names_chk.isChecked()),
                 ("Grande scène › IEM", lambda: not any("IEM" in k for k in win.mk["hide_layers"]))):
    v0 = get()
    click(txt)
    v1 = get()
    click(txt)
    v2 = get()
    check(f"souris, « {txt} » : {v0} → {v1} → {v2}", v1 != v0 and v2 == v0)
win.unk_chk.setChecked(False)
click("Signaux inconnus (pointillés)")         # affiché décoché quand la détection est coupée
check("souris : inconnus → la détection s'active aussi", win.unk_chk.isChecked() and win.mk["unk"])
click("Petit repère discret en haut")
check("souris : style discret", win.mk["style"] == "top")
click("Trait sur toute la hauteur")
check("souris : style plein", win.mk["style"] == "full")
click("couleur du groupe")
check("souris : couleur du groupe", win.mark_combo.currentData() == "group")
click("état du signal")
check("souris : couleur état", win.mark_combo.currentData() == "signal")
win.reset_markers()
win.reset_markers()
win.set_markers(style="full")
win.toggle_markers()
wait(600)
shot(win, "reperes_masques")
check("Ctrl+M : masqués", not win.mk["on"])
win.toggle_markers()

# bloc Spectera / WMAS (canal 21 en démo : plateau simulé)
step("ajout bloc Spectera", win.add_block_dialog)
blk = next((w for w in win.watch if w.get("bw")), None)
check("bloc ajouté", blk is not None and blk["bw"] == 8.0, str(blk and (blk["name"], blk["freq"])))
wait(5000)
check("bloc Spectera (démo) : vu en émission", blk is not None and blk["state"] == "occ", str(blk and blk["level"]))
win.view_range(462.0, 486.0)
wait(1500)
shot(win, "bloc_spectera")
win.view_combo.setCurrentIndex(0)
win._fit_x = True
wait(800)

step("zoom sur ligne 0", lambda: win.zoom_on(0)); wait(4000); shot(win, "zoom_live")
step("toggle_zoom off", lambda: win.toggle_zoom(False)); wait(1000)

# dispositions
for name in ("layout_analyzer", "layout_monitor", "layout_dual", "layout_standard"):
    step(name, getattr(win, name)); wait(1200); shot(win, name)

# vraies fenêtres (double écran) : un panneau sort dans une fenêtre Windows normale, plein écran, raccroché
_scr = QtGui.QGuiApplication.primaryScreen()
step("spectre en vraie fenêtre (écran 1, agrandie)", lambda: win.panel_window(win.dock_spec, True, _scr, "max"))
wait(800)
_pw = win.panel_wins.get("dock_spectre")
check("vraie fenêtre : ouverte, vrai type Window (pas « outil »)", _pw is not None and _pw.isVisible()
      and (_pw.windowFlags() & Qt.WindowType.WindowType_Mask) == Qt.WindowType.Window)
check("vraie fenêtre : le spectre est dedans", _pw is not None and win.spec.window() is _pw)
check("vraie fenêtre : le panneau d'origine est caché", not win.dock_spec.isVisible())
shot(_pw, "spectre_vraie_fenetre")
step("plein écran", _pw.toggle_full)
wait(400)
check("plein écran : barre masquée", _pw.isFullScreen() and not _pw.bar.isVisible())
step("sortir du plein écran", _pw.toggle_full)
wait(300)
step("fermer la fenêtre = raccrocher", _pw.close)
wait(600)
check("raccroché : le spectre est revenu", "dock_spectre" not in win.panel_wins and win.spec.window() is win
      and win.dock_spec.isVisible())
step("menu 🗗 Vraies fenêtres", win._fill_panel_menu)
check("menu : un sous-menu par panneau", len([a for a in win.panel_menu.actions() if a.menu()]) == len(win.panel_docks()))

# unités : saisie d'un seuil en % / dBµV dans la vraie case Qt, axe du spectre
win.thr_spin.setValue(-80.0)
win.set_unit("dbuv")
app.processEvents()
check("unité dBµV : la case affiche 27.0 dBµV", win.thr_spin.text() == "27.0 dBµV", win.thr_spin.text())
check("unité dBµV : axe gradué", win.spec.getPlotItem().getAxis("left").tickStrings([-80.0], 1.0, 10) == ["27"])
win.set_unit("pct")
win.thr_spin.lineEdit().setText("50 %")
win.thr_spin.interpretText()
check("unité % : taper « 50 % » → seuil à -60 dBm", abs(win.thr_spin.value() + 60.0) < 0.01, str(win.thr_spin.value()))
check("unité % : en-tête de la liste", win.watch_table.horizontalHeaderItem(m.C_LVL).text() == "Niveau (%)")
win.thr_spin.setValue(-80.0)
win.set_unit("dbm")
app.processEvents()
check("retour dBm", win.thr_spin.text() == "-80.0 dBm", win.thr_spin.text())

# aide au survol : tout bouton / case / liste visible a une explication
win.set_expert(True)
for k_ in win.sections:
    win.open_section(k_, True)
wait(300)
miss = []
for x in win.findChildren(W.QWidget):
    if not isinstance(x, (W.QAbstractButton, W.QComboBox, W.QAbstractSpinBox, W.QLineEdit)) or not x.isVisibleTo(win):
        continue
    if x.objectName().startswith("qt_") or isinstance(x.parentWidget(), (W.QAbstractSpinBox, W.QComboBox, W.QTabBar)):
        continue
    if isinstance(x, W.QToolButton) and not x.text():
        continue
    if not x.toolTip().strip():
        miss.append((type(x).__name__, getattr(x, "text", lambda: "")() if not isinstance(x, W.QComboBox) else x.currentText()))
check("chaque bouton / case / liste a une info-bulle", not miss, str(miss))
_subs = [a for a in win.more_menu.actions() if a.menu() is not None]
check("☰ Plus dans l'ordre du travail : liste, plan, scans / rapports, connexions, fenêtres, apparence",
      [e for e in ["📋", "📐", "📊", "🔗", "🪟", "🎨"] if any(a.text().startswith(e) for a in _subs)]
      == ["📋", "📐", "📊", "🔗", "🪟", "🎨"],
      str([a.text() for a in _subs]))
_no_tip = [a.text() for sm in [win.more_menu] + [a.menu() for a in _subs] for a in sm.actions()
           if a.text() and not a.isSeparator() and not a.toolTip().strip() and a.toolTip() != a.text().replace("&", "")]
check("☰ Plus : chaque entrée a une bulle d'aide", not _no_tip, str(_no_tip))
win.set_expert(False)

# mur de fréquences = panneau
step("ouvrir le mur (panneau)", win.open_wall)
wait(1200)
check("mur : panneau visible, accroché", win.dock_wall in win.docks and win.dock_wall.isVisible()
      and not win.dock_wall.isFloating())
shot(win, "mur_en_panneau")
app.processEvents()
check("mur : taille auto, tout tient sans défiler", win.wall.host.height() <= win.wall.scroll.viewport().height() + 1,
      f"{win.wall.host.height()} / {win.wall.scroll.viewport().height()}")
n_tiles = len(win.wall._visible_idx())
win.set_wall_rows([0], False)
wait(300)
check("mur : une tuile en moins après « Masquer sur le mur »",
      len(win.wall._visible_idx()) == n_tiles - 1 or win.in_alarm(win.watch[0]), f"{n_tiles} → {len(win.wall._visible_idx())}")
win.set_wall_rows([0], True)


def _uncheck_first_group(d):
    if hasattr(d, "items") and d.items:
        d.items[0][0].parent().setCheckState(0, Qt.CheckState.Unchecked)


DLG_ACTION[0] = lambda d: (_uncheck_first_group(d), "accept")[1]
step("choisir les fréquences du mur", win.pick_wall)
DLG_ACTION[0] = "reject"
check("mur : groupe entier décoché via la fenêtre", any(w.get("hide_wall") for w in win.watch))
win.set_wall_rows(list(range(len(win.watch))), True)
step("mur plein écran (F11)", win.wall.toggle_full)
wait(600)
check("mur : plein écran dans sa propre fenêtre", win.wall_is_fullscreen() and win._wall_full.isFullScreen()
      and win.wall.window() is win._wall_full)
check("mur plein écran : tuiles visibles (pas d'écran noir)", win.wall.isVisible()
      and sum(t.isVisible() for t in win.wall.tiles) > 0, f"{sum(t.isVisible() for t in win.wall.tiles)} tuiles")
shot(win._wall_full, "mur_plein_ecran")
step("mur : Échap", win.wall.leave_full)
wait(400)
check("mur : de retour dans son panneau", not win.wall_is_fullscreen() and win.dock_wall.widget() is win.wall
      and win.wall.isVisible())
step("mur : bouton Détacher", win.wall.float_btn.click)
wait(500)
check("mur : détaché par le bouton", win.dock_wall.isFloating() and "Raccrocher" in win.wall.float_btn.text())
win.dock_wall.resize(900, 600); wait(400)
_fs_big = win.wall._fs
win.dock_wall.resize(360, 240); wait(400)
check("mur détaché : les tuiles suivent la souris (texte plus petit)", win.wall._fs < _fs_big, f"{_fs_big} → {win.wall._fs}")
win.dock_wall.resize(900, 600); wait(400)
check("mur détaché : et regrossissent", win.wall._fs == _fs_big, f"{win.wall._fs} / {_fs_big}")
step("mur : bouton Raccrocher", win.wall.float_btn.click)
wait(500)
check("mur : raccroché", not win.dock_wall.isFloating() and "Détacher" in win.wall.float_btn.text())
mh = win.dock_wall.minimumSizeHint()
check("mur : panneau réductible (largeur mini ≤ 320)", mh.width() <= 320, f"{mh.width()} px")
win.dock_wall.setFloating(True)
win.dock_wall.resize(320, 240)
win.wall.size_combo.setCurrentIndex(win.wall.size_combo.findData("s"))
wait(400)
check("mur : détaché, réduit à 320 × 240", win.dock_wall.width() <= 330 and win.dock_wall.height() <= 250,
      f"{win.dock_wall.width()} × {win.dock_wall.height()}")
vis_t = [win.wall.tiles[i] for i in win.wall._visible_idx()]
check("mur : petites tuiles de hauteur fixe, on fait défiler",
      vis_t and all(t.height() == m.WALL_TILE["s"][1] for t in vis_t)
      and win.wall.host.height() > win.wall.scroll.viewport().height())
shot(win.dock_wall, "mur_petit")
win.wall.size_combo.setCurrentIndex(0)
win.dock_wall.setFloating(False)
win.dock_wall.hide()
wait(300)

# statut au clavier : sélection + Ctrl+E / Ctrl+0
_t = win.watch_table
_t.clearSelection()
win.activateWindow()
_t.setFocus()
wait(300)
for _r in (0, 1):
    _t.selectionModel().select(_t.model().index(_r, 0), QtCore.QItemSelectionModel.SelectionFlag.Select
                               | QtCore.QItemSelectionModel.SelectionFlag.Rows)
_rows = win._sel_rows()
_old = [win.watch[r]["status"] for r in _rows]
from PySide6 import QtTest
QtTest.QTest.keyClick(_t, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
app.processEvents()
check("Ctrl+0 : statut retiré de la sélection", len(_rows) == 2 and all(win.watch[r]["status"] == "" for r in _rows),
      str([win.watch[r]["status"] for r in _rows]))
QtTest.QTest.keyClick(_t, Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier)
app.processEvents()
_on = next(x["name"] for x in win.statuses if x.get("on"))
check("Ctrl+E : sélection « en service »", all(win.watch[r]["status"] == _on for r in _rows),
      str([win.watch[r]["status"] for r in _rows]))
for r, st in zip(_rows, _old):
    win.watch[r]["status"] = st
win.update_watch_table(force=True)
_t.clearSelection()

# changer de bande en plein balayage, vue « Toutes les bandes » (retour de Clément : spectre bugué)
if win.is_running():
    win.view_combo.setCurrentIndex(0)
    _old_en = [b["enabled"] for b in win.bands]
    for _b in win.bands:
        _b["enabled"] = False
    _ix = next(i for i in range(win.preset_combo.count()) if win.preset_combo.itemText(i).startswith("2,4 GHz"))
    step("bande 2,4 GHz à la place des autres", lambda: win.on_preset(_ix))
    wait(4000)
    _nb = win.bands[-1]
    _x = win.curve.getData()[0]
    _x = _x[~np.isnan(_x)] if _x is not None else _x
    check("changement de bande : seule la nouvelle bande est tracée", _x is not None and len(_x) > 0
          and _x.min() >= _nb["start"] - 1 and _x.max() <= _nb["stop"] + 1,
          f"{None if _x is None or not len(_x) else (_x.min(), _x.max())}")
    _xr = win.spec.getPlotItem().vb.viewRange()[0]
    check("changement de bande : l'axe suit", _xr[0] < _nb["start"] + 5 and _xr[1] > _nb["stop"] - 5, str(_xr))
    shot(win, "bande_2g4")
    with win.lock:
        win.bands.pop()
    for _b, _e in zip(win.bands, _old_en):
        _b["enabled"] = _e
    win._bands_changed()
    wait(3000)

# vérification du plan de fréquences (façon EazyRF)
step("vérifier le plan", win.open_plan_check)
_pd = win._plan_dlg
wait(500)
if _pd is not None:
    check("plan : une ligne par fréquence", _pd.table.rowCount() == len(win.watch))
    shot(_pd, "plan_frequences")
    _bad = [r for r, iss in enumerate(_pd.issues) if iss]
    if not _bad:                                   # la démo n'a peut-être pas de conflit : on en fabrique un
        win._append_watch("Trop près", win.watch[0]["freq"] + 0.1, status=next(x["name"] for x in win.statuses if x.get("on")))
        win.rebuild_watch_table()
        _pd.compute()
        _bad = [r for r, iss in enumerate(_pd.issues) if iss]
    check("plan : au moins un problème trouvé", bool(_bad))
    _r = _bad[0]
    _w = _pd.ws[_r]
    _pd.table.selectRow(_r)
    step("plan : proposer", _pd.suggest)
    _c = _pd.sug_list.currentItem().data(Qt.ItemDataRole.UserRole) if _pd.sug_list.currentItem() else None
    check("plan : proposition trouvée", _c is not None, _pd.sug_list.item(0).text() if _pd.sug_list.count() else "")
    shot(_pd, "plan_proposition")
    if _c is not None:
        _n0 = sum(map(len, _pd.issues))
        step("plan : remplacer", _pd.replace)
        app.processEvents()
        check("plan : fréquence remplacée dans la liste", abs(_w["freq"] - _c) < 1e-9)
        check("plan : moins de problèmes après", sum(map(len, _pd.issues)) < _n0, f"{_n0} → {sum(map(len, _pd.issues))}")
    # profils d'appareil : défaut Wisycom (remplit les réglages), puis Shure sur 2 lignes
    _pd.prof_combo.setCurrentIndex(_pd.prof_combo.findData("wisycom"))
    app.processEvents()
    check("plan : profil Wisycom → filtre 32 MHz, écart 500, pas 5", _pd.filt_spin.value() == 32
          and _pd.sep_spin.value() == 500 and _pd.step_spin.value() == 5)
    _pd.sep_spin.setValue(450)
    check("plan : toucher un réglage → « Réglages ci-dessous »", _pd.prof_combo.currentData() == "")
    _pd.table.clearSelection()
    _pd.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
    _pd.table.selectRow(0)
    _pd.table.selectRow(1)
    _pd.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
    _pd.rx_combo.setCurrentIndex(_pd.rx_combo.findData("shure_ana"))
    _w0, _w1 = _pd.ws[0], _pd.ws[1]
    step("plan : appareil Shure sur 2 lignes", _pd.set_rx)
    check("plan : appareil enregistré sur les fréquences", _w0.get("rx") == "shure_ana" and _w1.get("rx") == "shure_ana")
    check("plan : colonne Appareil", "Shure" in (_pd.table.item(_pd.ws.index(_w0), 3).text()))
    check("plan : appareil gardé dans la config", any(x.get("rx") == "shure_ana" for x in win._collect_config()["watch"]))
    shot(_pd, "plan_appareils")
    # profils perso : « ＋ Depuis les réglages actuels » → OK → la liste des appareils le propose
    def _prof_act(d):
        if isinstance(d, m.RxProfilesDialog):
            d.new(d.current)
            return "reject"
        if isinstance(d, m.RxProfileEdit):
            d.name.setText("EW G4 bande A")
            d.filt.setValue(16)
        return "accept"
    DLG_ACTION[0] = _prof_act
    step("plan : ✏ Mes profils › nouveau profil perso", _pd.edit_profiles)
    DLG_ACTION[0] = "reject"
    check("profil perso créé et proposé dans la liste", _pd.rx_combo.findText("✏ EW G4 bande A") >= 0
          and m.rx_profile("perso_1") is not None and m.rx_profile("perso_1")["filt"] == 16.0,
          str([_pd.rx_combo.itemText(i) for i in range(_pd.rx_combo.count())]))
    check("profil perso gardé dans la config et les shows", win._collect_config()["rx_custom"][0]["name"] == "EW G4 bande A"
          and "rx_custom" in m.SHOW_KEYS)
    step("plan : ❓ le filtre", lambda: m.show_filter_help(_pd))
    _pd.close()
else:
    check("plan : fenêtre ouverte", False)

# changer le nombre de points pendant le balayage (crash.log de Clément, 7.4.2)
if win.is_running():
    for _ix in (len(m.POINTS_CHOICES) - 2, 0, 4, 2):
        win.points_combo.setCurrentIndex(_ix)
        step(f"points → {win.points_combo.currentText()}", win.apply_points)
        wait(700)
    check("changer les points en plein balayage : ça tourne toujours", win.is_running())
    win.points_combo.setCurrentIndex(m.POINTS_CHOICES.index(1000))
    win.apply_points()
    wait(1500)

QtGui.QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
step("diagnostic tinySA", win.open_diag)
_dd = win.log_dir / "diagnostic"
_df = sorted(_dd.glob("diagnostic_tinysa_*.txt")) if _dd.exists() else []
check("diagnostic : fichier écrit avec versions, réglages, bandes", bool(_df)
      and m.APP_VER in _df[-1].read_text(encoding="utf-8") and "Bandes :" in _df[-1].read_text(encoding="utf-8"))
check("vitesse série dans la config", win._collect_config()["baud"] == 115200)
check("version affichée (barre d'état)", m.APP_VER in win.ver_lbl.text() and win.ver_lbl.isVisible())
step("à propos", win.show_about)
_lm = [a_.text() for a_ in win.lang_menu.actions()]
check("menu 🌐 Langue : Français coché, English proposé", _lm == ["Français", "English"]
      and win.lang_menu.actions()[0].isChecked() and win.lang == "fr", str(_lm))
check("manuel français par défaut", win.manual_path() is not None and win.manual_path().name == "manuel.html")
check("à propos : version et tinySA", any(m.APP_VER in t and "tinySA" in t for k, t in msgs), str(msgs[-1:]))
check("version dans l'état de la page web", m.json.loads(win.web_json()["fr"])["ver"] == m.APP_VER)

# appel des micros (line check), en mode démo
step("appel des micros (Ctrl+L)", win.open_linecheck)
lcd = win._linecheck
wait(4000)
if lcd is not None:
    sm_ = m.lc_summary(lcd.lc)
    check("appel : des fréquences validées en démo", sm_["ok"] + sm_["weak"] > 0 and sm_["n"] > 0, sm_["text"])
    check("appel : les ABSENT de la démo manquent", any(w.get("absent") for w in win.watch) <= bool(sm_["missing"]), sm_["text"])
    check("appel : tableau rempli", lcd.table.rowCount() == sm_["n"] + sm_["skipped"])
    miss_t = [type(x).__name__ for x in lcd.findChildren(W.QAbstractButton) + lcd.findChildren(W.QComboBox)
              if x.isVisibleTo(lcd) and not x.toolTip().strip()]
    check("appel : info-bulles", not miss_t, str(miss_t))
    shot(lcd, "appel_des_micros")
    lcd.table.selectRow(0)
    step("appel : ignorer la 1re ligne", lambda: lcd.mark("skip"))
    check("appel : ligne ignorée", lcd.lc[lcd.keys[0]]["res"] == "skip")
    step("appel : copier", lcd.copy)
    check("appel : résumé copié", app.clipboard().text().startswith("Appel des micros"))
    n_log = win.log_table.rowCount()
    step("appel : terminer", lcd.finish)
    check("appel : noté au journal, fenêtre fermée", win.log_table.rowCount() > n_log      # (la démo journalise aussi)
          and any(win.log_table.item(i, 4).text().startswith("APPEL") for i in range(min(5, win.log_table.rowCount())))
          and win._linecheck is None)
else:
    check("appel : fenêtre ouverte", False)

# disposition de base : le spectre a la place, les colonnes se rétrécissent
win.layout_standard()
wait(400)
check("disposition de base : spectre ≥ 45 % de la largeur", win.dock_spec.width() >= 0.45 * win.width(),
      f"spectre {win.dock_spec.width()} / fenêtre {win.width()}")
win.resizeDocks([win.dock_set, win.dock_freq], [50, 50], Qt.Orientation.Horizontal)
wait(300)
check("colonnes rétrécissables (réglages ≤ 240, liste ≤ 300)", win.dock_set.width() <= 240 and win.dock_freq.width() <= 300,
      f"réglages {win.dock_set.width()} · liste {win.dock_freq.width()}")
win.view_combo.setCurrentIndex(1)
wait(2500)
if win.dock_wf.isVisible():
    check("waterfall en bandeau (≤ 40 % de la colonne)", win.dock_wf.height() <= 0.4 * (win.dock_wf.height() + win.dock_spec.height()),
          f"waterfall {win.dock_wf.height()} / spectre {win.dock_spec.height()}")
win.view_combo.setCurrentIndex(0)
_sz = win.size()
win.resize(1024, 700)             # petit portable (et l'écran de la CI Windows)
wait(300)
win.layout_standard()
wait(400)
check("disposition de base à 1024 px : spectre ≥ 45 %", win.dock_spec.width() >= 0.45 * win.width(),
      f"spectre {win.dock_spec.width()} / fenêtre {win.width()}")
win.resize(_sz)
wait(300)
win.layout_standard()
wait(300)

# spectre détachable + mode simple / expert
check("le spectre est un panneau (détachable)", win.dock_spec in win.docks and
      bool(win.dock_spec.features() & W.QDockWidget.DockWidgetFeature.DockWidgetFloatable))
win.dock_spec.setFloating(True)
win.dock_spec.resize(900, 500)
wait(800)
check("spectre détaché : fenêtre libre", win.dock_spec.isFloating() and win.dock_spec.isVisible())
shot(win.dock_spec, "spectre_detache")
win.dock_spec.setFloating(False)
wait(500)
win.set_expert(False)
wait(300)
check("mode simple : RBW caché, seuils visibles", not win.rbw_combo.isVisible() and win.thr_spin.isVisible()
      and win.absent_spin.isVisible() and win.weak_spin.isVisible())
shot(win, "mode_simple")
win.set_expert(True)
wait(300)
win.open_section("measure", True)
wait(300)
check("mode expert : RBW visible", win.rbw_combo.isVisible())
win.open_section("measure", False)
wait(300)
check("section repliée : RBW caché", not win.rbw_combo.isVisible())
win.set_expert(False)
step("toggle_alarm_dock", win.toggle_alarm_dock); wait(1500); shot(win, "panneau_alarmes")
print("ALARMES actives:", len(win.alarms.active), "btn:", win.alarm_btn.text(), flush=True)

# petite taille d'écran
def size_report():
    """Qui impose la largeur ? (docks + widgets visibles les plus larges)"""
    out = [f"central {win.centralWidget().minimumSizeHint().width()}"]
    for d in win.docks:
        if d.isVisible():
            out.append(f"{d.objectName()} {d.minimumSizeHint().width()}{'(flottant)' if d.isFloating() else ''}")
    for d in [win.centralWidget()] + [d.widget() for d in win.docks if d.isVisible()]:
        lay = d.layout()
        items = [lay.itemAt(i) for i in range(lay.count())] if lay else []
        top = sorted(((it.minimumSize().width(), (type(it.widget()).__name__ if it.widget() else type(it).__name__))
                      for it in items), reverse=True)[:3]
        out.append(f"  [{d.objectName() or type(d).__name__}] " + ", ".join(f"{n}={v}" for v, n in top))
    wide = []
    for w in win.findChildren(QtWidgets.QWidget):
        if w.isVisible() and not isinstance(w, (QtWidgets.QDockWidget, QtWidgets.QScrollBar)):
            ign = w.sizePolicy().horizontalPolicy() == QtWidgets.QSizePolicy.Policy.Ignored
            mw = w.minimumWidth() if ign else max(w.minimumSizeHint().width(), w.minimumWidth())
            if mw > 250:
                txt = getattr(w, "text", lambda: "")() if hasattr(w, "text") else ""
                wide.append((mw, f"{type(w).__name__}:{w.objectName() or str(txt)[:30]}"))
    wide.sort(reverse=True)
    return " | ".join(out) + " || " + " ; ".join(f"{n}={v}" for v, n in wide[:12])


ok_w = win.minimumSizeHint().width() <= 1280
check("largeur mini ≤ 1280 px (portable)", ok_w, str(win.minimumSizeHint()))
print(("OK  " if ok_w else "FAIL") + " détail largeurs : " + size_report(), flush=True)
check("hauteur mini ≤ 700 px (1366×768 moins barre des tâches et titre)", win.minimumSizeHint().height() <= 700, str(win.minimumSizeHint()))
win.resize(1280, 720); wait(1200); shot(win, "taille_1280x720")
_t = win.watch_table
_sig_x = _t.columnViewportPosition(m.C_SIG) + _t.columnWidth(m.C_SIG)
check("1280×720 : colonne Signal visible sans faire défiler", 0 < _sig_x <= _t.viewport().width() + 2,
      f"{_sig_x} / {_t.viewport().width()}")
vis = {t: b.isVisible() and b.visibleRegion().boundingRect().width() >= b.width() - 2
       for t, b in (("Démarrer", win.start_btn), ("🔔", win.alarm_btn))}
vis["Shows / Plus"] = all(a.isVisible() for a in win.cmd_bar.findChildren(W.QPushButton) if a.text() in ("🎪 Shows", "☰ Plus"))
check("1280×720 : boutons du haut visibles en entier", all(vis.values()), str(vis))
win.resize(1700, 980); wait(800)

# dialogues modaux
def _labels_act(d):
    if not isinstance(d, m.LabelsDialog):
        return "reject"
    _og = W.QColorDialog.getColor
    W.QColorDialog.getColor = staticmethod(lambda *a, **k: QtGui.QColor("#a855f7"))
    try:
        d.pick_color("free_ok")
    finally:
        W.QColorDialog.getColor = _og
    check("mots et couleurs : pastille mise à jour", "#a855f7" in d.table.cellWidget(
        [k for k, *_ in m.SIGNAL_LABELS].index("free_ok"), 2).text())
    return "accept"


DLG_ACTION[0] = _labels_act
step("edit_labels", win.edit_labels)
DLG_ACTION[0] = "reject"
check("couleur « libre » choisie retenue", win.sig_colors == {"free_ok": "#a855f7"}, str(win.sig_colors))
_fr = next((w for w in win.watch if win.is_keep_free(w["status"]) and w["state"] == "free"), None)
if _fr is not None:
    check("couleur « libre » appliquée", win.sig_view(_fr)[2] == "#a855f7", str(win.sig_view(_fr)))
_ok = next((w for w in win.watch if win.is_keep_on(w["status"]) and w["state"] == "occ"), None)
if _ok is not None:
    check("OK reste vert (différent de libre)", win.sig_view(_ok)[1] == "ok" and win.sig_view(_ok)[2] != "#a855f7")
win.sig_colors = {}
step("edit_statuses", win.edit_statuses)
step("edit_colors", win.edit_colors)
step("edit_plan", win.edit_plan)
step("export_scan", win.export_scan)
step("make_report", win.make_report)
step("export_by_scene", win.export_by_scene)
step("quick_name_dialog", lambda: win.quick_name_dialog([0, 1, 2]))
step("add_watch_dialog", win.add_watch_dialog)
step("edit_vocab", win.edit_vocab)

# import CSV
csvp = os.path.join(tmp, "liste.csv")
open(csvp, "w", encoding="utf-8").write("Name;Frequency;Group\nHF A;606.125;Plateau\nHF B;607.250;Plateau\nIEM C;610.500;Retours\n")
opened[:] = [csvp]
step("import_watch", win.import_watch)

# scan WSM
rows = ["WSM scan export", "Date;2026-10-24", "Site;Test", "", "", ""]
hdr = "Frequency;RF level (%);RF level;Memory (%);Memory;Squelch (%);Squelch"
body = [f"{k};{20 + (k % 7) * 3};-96 dBm;0;0;0;0" for k in range(470000, 600001, 25)]
wsm = os.path.join(tmp, "scan_wsm.csv")
open(wsm, "w", encoding="utf-8").write("\n".join(rows + [hdr] + body + [""] * 13))
opened[:] = [wsm]
step("import_scan_as_ref (WSM)", win.import_scan_as_ref); wait(2500); shot(win, "ref_wsm")
wwb = os.path.join(tmp, "scan_wwb.txt")
open(wwb, "w").write("\n".join(f"{470 + i * 0.025:.3f}, {-98 + (i % 11)}" for i in range(4000)))
opened[:] = [wwb]
step("import_scan_as_ref (WWB)", win.import_scan_as_ref); wait(2500); shot(win, "ref_wwb")
opened[:] = [wsm]; saved[:] = [os.path.join(tmp, "conv_wwb.csv")]
step("convert_wsm_wwb", win.convert_wsm_wwb)
saved[:] = [os.path.join(tmp, "export_wwb.csv")]
step("export_scan_wwb", win.export_scan_wwb)

# convertisseur de scans
step("convertisseur de scans", win.open_scan_convert)
_cd = win._conv_dlg
opened[:] = [wsm]
step("conv : ouvrir l'export WSM", _cd.open_files)
check("conv : WSM reconnu", "export WSM" in _cd.src_lbl.text(), _cd.src_lbl.text())
check("conv : aperçu WWB", _cd.preview.toPlainText().splitlines()[0].count(", ") == 1, _cd.preview.toPlainText()[:60])
_cd.out_fmt.setCurrentIndex(_cd.out_fmt.findData("csv"))
_cd.out_sep.setCurrentIndex(_cd.out_sep.findData("\t"))
_cd.out_lunit.setCurrentIndex(_cd.out_lunit.findData("dbuv"))
check("conv : CSV personnalisé (tabulation, dBµV)", _cd.preview.toPlainText().startswith("Fréquence (MHz)\tNiveau (dBµV)"),
      _cd.preview.toPlainText()[:60])
shot(_cd, "convertisseur")
_outp = os.path.join(tmp, "conv_test.csv")
saved[:] = [_outp]
step("conv : enregistrer", _cd.save)
check("conv : fichier écrit", os.path.exists(_outp) and "\t" in open(_outp, encoding="utf-8").read())
step("conv : scan en cours", _cd.use_current)
check("conv : scan en cours chargé", "Scan en cours" in _cd.src_lbl.text(), _cd.src_lbl.text())
_cd.close()

# dialogues non modaux
step("open_intermod", win.open_intermod); wait(1500)
if win._im_dlg:
    shot(win._im_dlg, "intermod")
    _d = win._im_dlg
    _d.active_chk.setChecked(False)
    _d.src_combo.setCurrentIndex(0)
    _d.maxtx_combo.setCurrentIndex(0)
    if any(w.get("bw") for w in win.watch):
        step("intermod avec un bloc large", _d.compute)
        _wide = [r for r in _d.rows if r["hw"] > 0.05]
        check("intermod : produits du bloc en bandes (± MHz)", bool(_wide)
              and any("±" in (_d.table.item(i, 0).text()) for i in range(_d.table.rowCount())), f"{len(_d.rows)} produits")
        shot(_d, "intermod_bloc")
    else:
        print("(pas de bloc large dans la liste : IM des blocs non testée en vrai Qt)")
# origine d'un signal à partir du SPECTRE (émetteurs non déclarés) : 2 × 602 − 600 = 604
_F = np.linspace(590.0, 615.0, 2501)
_L = np.full_like(_F, -105.0)
for _f0, _l0 in ((600.0, -40.0), (602.0, -42.0), (604.0, -70.0)):
    _L[np.abs(_F - _f0) < 0.02] = _l0
def _inj():          # bande factice : un balayage démo peut l'effacer (bande inconnue) → on la remet avant chaque usage
    win.latest[9991], win.latest_t[9991] = (_F, _L), m.time.time()
    win.maxhold.pop(9991, None)
_inj()
_od = step("intermod : origine de 604 MHz (spectre)", lambda: m.IntermodDialog(win, origin=604.0))
if _od is not None:
    check("origine : source = signaux vus sur le spectre", _od.src_combo.currentData() == "spectrum",
          _od.src_lbl.text())
    step("origine : calculer", lambda: (_inj(), _od.compute()))
    _txt = [r["numtext"] for r in _od.rows]
    check("origine : 2 × 602 − 600 trouvé sans émetteur déclaré",
          any("602" in t_ and "600" in t_ for t_ in _txt[:3]), str(_txt[:5]) + _od.msg.text() + str([round(x[0], 3) for x in _od.spectrum_sources()]))
    shot(_od, "intermod_origine_spectre")
    _od.close()
# 📡 ajouter depuis le scan (idée de Clément) : les 3 signaux du faux spectre (600, 602, 604) deviennent des fréquences
_n_w = len(win.watch)
def _scan_act(d):
    if isinstance(d, m.ScanAddDialog):
        _inj()
        d.refresh()
        d.group.setText("Trouvées")
        shot(d, "ajout_depuis_scan")
        d.add()
    return "reject"
_inj()
DLG_ACTION[0] = _scan_act
step("📡 ajouter depuis le scan", win.open_scan_add)
DLG_ACTION[0] = "reject"
_new = [w for w in win.watch if w["name"].startswith("Scan ")]
check("depuis le scan : 600 / 602 / 604 ajoutées (nommées Scan n, groupe choisi)",
      {round(w["freq"]) for w in _new} >= {600, 602, 604} and all(w["group"] == "Trouvées" for w in _new),
      str([(w["name"], w["freq"], w["group"]) for w in _new]))
_inj()
_d2 = m.ScanAddDialog(win)
check("depuis le scan : déjà dans la liste → plus proposées",
      not any(abs(p_["f"] - 602.0) < 0.05 for p_ in _d2.peaks), str([p_["f"] for p_ in _d2.peaks]))
_d2.close()
for _w in _new:                                  # on les retire (la suite du test compte les fréquences)
    win.watch.remove(_w)
win.rebuild_watch_table(); win.rebuild_tree()
win.latest.pop(9991, None); win.latest_t.pop(9991, None)
# 🪄 coordination automatique : 4 fréquences compatibles ajoutées (sur un plan réaliste : celui de Clément)
_saved = list(win.watch)
win.watch.clear()
for _i, _f in enumerate((470.2, 471.3, 478.0, 558.0, 574.0, 606.0, 614.0, 646.0)):
    win._append_watch(f"W{_i}", _f, status="En service")
    win.watch[-1]["rx"] = "wisycom"
def _coord_act(d):
    if isinstance(d, m.CoordDialog):
        d.n_spin.setValue(4)
        d.lo.setValue(520.0)
        d.hi.setValue(556.0)
        d.prefix.setText("COORD")
        d.compute()
        shot(d, "coordination_auto")
        d.add()
    return "reject"
DLG_ACTION[0] = _coord_act
step("🪄 coordination auto", win.open_coord)
DLG_ACTION[0] = "reject"
_cw = [w for w in win.watch if w["name"].startswith("COORD")]
_iss, _ = m.pf_check([w["freq"] for w in win.watch], None, None, 0.5, m.rx_profile("wisycom")["tol"], None, 32.0)
check("coordination : 4 ajoutées (Wisycom, en service), plan complet sans aucun problème",
      len(_cw) == 4 and all(w.get("rx") == "wisycom" and win.is_keep_on(w["status"]) for w in _cw)
      and sum(len(x) for x in _iss) == 0, str([(w["name"], w["freq"]) for w in _cw]) + str(_iss))
win.watch[:] = _saved
win.rebuild_watch_table(); win.rebuild_tree()
# 📝 Quoi noter : un type décoché n'arrive plus au journal (les alarmes, elles, restent)
_n0 = win.log_table.rowCount()
win._logwhat_acts["unknown"].trigger()
win.log_event({"name": "Signal inconnu", "freq": 600.0, "note": ""}, -50.0, "INCONNU")
check("journal : « Signaux inconnus » décoché → pas noté", win.log_table.rowCount() == _n0 and not win.log_kinds["unknown"])
win._logwhat_acts["unknown"].trigger()
win.log_event({"name": "Signal inconnu", "freq": 600.0, "note": ""}, -50.0, "INCONNU")
check("journal : recoché → noté", win.log_table.rowCount() == _n0 + 1 and win._collect_config()["log_kinds"]["unknown"])
# 🎯 marqueurs M1 / M2 (demande de Clément : précis, déplaçables, affichables ou non)
step("🎯 marqueurs", lambda: win.mkr_btn.setChecked(True))
win.mkr2_chk.setChecked(True)
win.mkr_spins[0].setValue(503.512)
check("marqueur : la ligne M1 suit la saisie au kHz", abs(win.mkr_lines[0].value() - 503.512) < 1e-6
      and win.mkr_lines[0].isVisible())
win.mkr_lines[1].setValue(504.0)
check("marqueur : déplacer M2 à la souris met la case à jour", abs(win.mkr_spins[1].value() - 504.0) < 1e-6)
step("marqueur : ⤒ pic", lambda: win.marker_to_peak(0))
wait(300)
check("marqueur : lecture (niveau, Δ, largeur)", "M1" in win.mkr_lbl.text() and "Δ" in win.mkr_lbl.text(),
      win.mkr_lbl.text())
shot(win, "marqueurs")
win.mkr_btn.setChecked(False)
check("marqueurs masqués", not win.mkr_lines[0].isVisible() and not win.mkr_bar.isVisible())
step("❓ Courbes du spectre", win.open_spectrum_legend)
_lg = win._legend
if _lg is not None:
    _sps = _lg.findChildren(m.LevelSpin)
    _old = win.thr_spin.value()
    _sps[0].setValue(-77.0)
    check("légende : le seuil réglé dans la légende change le vrai seuil (et la ligne)",
          abs(win.thr_spin.value() + 77.0) < 0.01 and abs(win.thr_line.value() + 77.0) < 0.01)
    win.thr_spin.setValue(-75.0)
    check("légende : et inversement", abs(_sps[0].value() + 75.0) < 0.01)
    shot(_lg, "legende_spectre")
    _lg.close()
    win.thr_spin.setValue(_old)
step("open_rescue", win.open_rescue); wait(1500)
if win._rescue_dlg: shot(win._rescue_dlg, "rescue")
step("open_guide", win.open_guide); wait(800)
if win._guide: shot(win._guide, "guide_bandes")
step("open_replay", win.open_replay); wait(1500)
if win._replay:
    shot(win._replay, "relecture")
    step("relecture play", win._replay.toggle_play); wait(2500); shot(win._replay, "relecture_play")
    step("relecture stop", win._replay.toggle_play)
    win._replay.close()
step("open_wall", win.open_wall); wait(2500)
if win.wall: shot(win.wall, "mur")

# enregistrement
if hasattr(win, "rec_chk"):
    step("rec on", lambda: win.rec_chk.setChecked(True)); wait(3000)
    step("rec off", lambda: win.rec_chk.setChecked(False))

# rapport accepté
DLG_ACTION[0] = "accept"
saved[:] = [os.path.join(tmp, "rapport.html")]
step("make_report accept", win.make_report)
DLG_ACTION[0] = "reject"
print("rapport écrit:", os.path.exists(os.path.join(tmp, "rapport.html")), flush=True)

# shows : enregistrer, liste, rouvrir (vrais dialogues Qt)
m.SHOW_DIR = m.Path(tmp) / "Shows"
win.show_meta = dict(name="Festival test", venue="Grande scène", date_from="2025-07-17", date_to="2025-07-20",
                     notes="Antenne FOH sur le pont lumière.")
saved[:] = [str(m.SHOW_DIR / m.show_filename(win.show_meta))]
step("enregistrer le show", win.save_show)
check("show enregistré", os.path.exists(win.show_path), win.show_path)
check("titre avec le show", "Festival test 2025" in win.windowTitle(), win.windowTitle())
n_w = len(win.watch)
step("infos du show", win.edit_show_info)
DLG_ACTION[0] = lambda d: d.table.selectRow(0) if hasattr(d, "table") else None
step("ouvrir un show (liste)", win.open_show_dialog)
DLG_ACTION[0] = "reject"
step("rouvrir le show", lambda: win.open_show(win.show_path, ask=False))
check("show rouvert", len(win.watch) == n_w and win.show_meta["name"] == "Festival test")

step("Arrêter", win.toggle_run); wait(2500)
check("arrêt : plus aucun worker", not win.is_running())
_sp = win._last_session
check("session : close à l'arrêt (spectre + session.json + journal.csv)", _sp is not None and win._session is None
      and any(_sp.glob("chunk_*.npz")) and (_sp / "session.json").exists() and (_sp / "journal.csv").exists(),
      str(_sp) + " " + str(sorted(p_.name for p_ in _sp.iterdir())) if _sp else "")
_meta = m.json.loads((_sp / "session.json").read_text(encoding="utf-8")) if _sp else {}
check("session : liste de fréquences + fin notées", len(_meta.get("watch", [])) == len(win.watch) and _meta.get("end"))
_rp = step("relecture : ouvrir la dernière session", lambda: (win.open_replay(), win._replay)[1])
if _rp is not None:
    step("relecture : session", lambda: _rp.open_rec(_sp))
    check("relecture : session rechargée avec sa liste et son journal", _rp.sess_watch is not None
          and len(_rp.times) > 0 and _rp.ev_combo.count() > 1, _rp.msg.text())
    shot(_rp, "relecture_session")
    _exp = os.path.join(tmp, "export_sess")
    os.makedirs(_exp, exist_ok=True)
    _orig_dir = W.QFileDialog.getExistingDirectory
    W.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: _exp)
    step("relecture : mémoire → exporter", lambda: (_rp.use_memory(), _rp.export_session()))
    W.QFileDialog.getExistingDirectory = _orig_dir
    _ed = [p_ for p_ in m.Path(_exp).iterdir()]
    check("export de la mémoire : une session complète", len(_ed) == 1 and any(_ed[0].glob("chunk_*.npz"))
          and (_ed[0] / "session.json").exists(), _rp.msg.text())
    _rp.close()
shot(win, "arrete")

# ---- deux tinySA (démo) : chacun ses bandes, coupure du 2e, retour, fenêtre relais
win.view_combo.setCurrentIndex(0)
win.add_band("VHF", 174.0, 223.0, 100.0)
win.dev2_chk.setChecked(True)
win.dev2_addr.setEditText("192.168.1.20:5025")
seen = {0: set(), 1: set()}
step("Démarrer x2", win.toggle_run)
check("deux workers lancés", len(win.workers) == 2 and all(w.isRunning() for w in win.workers))
for i, w in enumerate(win.workers):
    w.sweep.connect(lambda bid, f, l, i=i: seen[i].add(bid))
wait(6000)
check("les deux tinySA balayent", seen[0] and seen[1] and not (seen[0] & seen[1]), str(seen))
check("cycles des deux appareils", set(win.dev_cycle) == {0, 1}, str(win.dev_cycle))
win.dock_set.show()
win.dock_set.raise_()
wait(800)
shot(win, "deux_tinysa")
step("coupure du 2e", lambda: win.on_link(1, False))
seen[0].clear()
wait(5000)
check("2e perdu : le 1er reprend toutes les bandes",
      seen[0] >= {b["id"] for b in win.bands if b["enabled"]}, str(seen[0]))
check("2e perdu : alarme APPAREIL", ("APPAREIL", -2) in win.alarms.active)
win.dock_alarm.show()
wait(800)
shot(win, "tinysa2_perdu")
step("retour du 2e", lambda: win.on_link(1, True))
wait(1500)
# noms de position + calibration (démo : pas de porteuse commune → base « bruit de fond »)
win.dev1_name.setText("Plateau")
win.dev2_name.setText("FOH")
check("noms de position", win.dev_name(0) == "Plateau" and win.dev_name(1) == "FOH")
step("calibration", win.start_calib)
check("calibration lancée", win._calib is not None)
t_cal = time.time()
while win._calib is not None and time.time() - t_cal < 60:
    wait(500)
check("calibration terminée", win._calib is None and "Calibration faite" in getattr(win, "calib_msg", ""),
      getattr(win, "calib_msg", ""))
check("résultat de calibration affiché", any("Calibration faite" in t for _k, t in msgs), str(msgs[-2:]))
check("offset du 2e plausible (démo)", abs(win.dev2_off.value()) < 3.0, str(win.dev2_off.value()))
# zoom : le 2e continue la surveillance
seen[1].clear()
step("zoom live", lambda: win.zoom_on(0))
wait(5000)
check("zoom : le 2e surveille toujours les bandes", seen[1] and m.ZOOM_ID not in seen[1], str(seen[1]))
step("zoom off", lambda: win.toggle_zoom(False))
win.zoom_btn.setChecked(False)
wait(1000)
# page web servie par la vraie appli
import json as _json
import urllib.request as _ur
win.web_cfg.update(on=True, port=0)
step("apply_web", win.apply_web)
check("page web démarrée", win.web is not None and win.web.port > 0)
if win.web is not None:
    wait(1500)
    base = f"http://127.0.0.1:{win.web.port}"
    js = _json.loads(_ur.urlopen(base + "/etat.json", timeout=5).read())
    check("page web : état réel", len(js["state"]["rows"]) == len(win.watch) and js["state"]["running"],
          str(js["state"].get("running")))
    # vue Spectre : un téléphone se connecte, regarde le spectre → le PC prépare le spectre allégé
    import http.cookiejar as _cj
    _op = _ur.build_opener(_ur.HTTPCookieProcessor(_cj.CookieJar()))
    _op.open(_ur.Request(base + "/connexion", data=_json.dumps(dict(name="Test", password="")).encode(),
                         headers={"Content-Type": "application/json"}, method="POST"), timeout=5)
    _op.open(base + "/etat.json?v=spectre", timeout=5).read()
    win._alarm_tick()
    _sp = _json.loads(_op.open(base + "/spectre.json", timeout=5).read())
    check("page web : spectre en direct servi", _sp["bands"] and len(_sp["bands"][0]["f"]) <= 900
          and len(_sp["bands"][0]["f"]) == len(_sp["bands"][0]["l"]), str(len(_sp["bands"])))
    check("page web : la régie voit le client", any(e["name"] == "Test" and e["view"] == "spectre"
                                                    for e in win.web.client_list()))
    def _clients_act(d):
        if not isinstance(d, m.AlertsDialog):
            return "reject"
        check("alertes : liste des connectés", any("Test" in d.clients.item(i).text() for i in range(d.clients.count())))
        d.clients.setCurrentRow(0)
        _tok0 = d._sel_tok
        d.refresh_clients()
        d.refresh_clients()
        _it = d.clients.currentItem()
        check("alertes : le choix reste après le rafraîchissement", _tok0 is not None and _it is not None and _it.isSelected()
              and _it.data(Qt.ItemDataRole.UserRole)[0] == _tok0)
        _orig_gt = W.QInputDialog.getText
        W.QInputDialog.getText = staticmethod(lambda *a, **k: ("Tablette régie", True))
        try:
            d.rename_client()
        finally:
            W.QInputDialog.getText = _orig_gt
        check("alertes : client renommé depuis le PC", any(e["name"] == "Tablette régie" for e in win.web.client_list()))
        d.refresh_clients()
        d.identify_client()
        check("alertes : identifier (clignotement demandé)", any(e.get("ident", 0) > time.time() for e in win.web.client_list()))
        return "reject"

    DLG_ACTION[0] = _clients_act
    step("dialogue alertes (connectés)", win.open_alerts)
    DLG_ACTION[0] = "reject"
    check("page web : page HTML", b"TinySA Monitor" in _ur.urlopen(base + "/", timeout=5).read())
    # acquitter depuis le téléphone (code PIN)
    import json as _js
    win.web_cfg["pin"] = "2468"
    win._alarm_tick()
    _al = [a for a in _js.loads(_ur.urlopen(base + "/etat.json", timeout=5).read())["state"]["alarms"] if not a["acked"]]
    check("page web : acquittement proposé", _js.loads(win.web_json()["fr"])["ack"] is True)
    if _al:
        _rq = _ur.Request(base + "/acquitter", data=_js.dumps(dict(pin="2468", id=_al[0]["id"])).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        check("page web : POST acquitter accepté", _ur.urlopen(_rq, timeout=5).status == 200)
        win._alarm_tick()
        a_ = next((a for a in win.alarms.active.values() if a["id"] == _al[0]["id"]), None)
        check("page web : alarme acquittée sur le PC", a_ is None or a_["acked"])
    else:
        print("(pas d'alarme en cours : acquittement web non testé)")
    win.web_cfg["pin"] = ""
    win.web_cfg["on"] = False
    step("web off", win.apply_web)
    check("page web arrêtée", win.web is None)
class _FakeResp:
    def __init__(self, b): self.b = b
    def read(self): return self.b
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _alerts_act(d):
    if not isinstance(d, m.AlertsDialog):
        return "reject"                      # le tuto (dialogue imbriqué) : on le ferme
    d.service.setCurrentIndex(d.service.findData("telegram"))
    d.tg_token.setText("123:FAUX")
    _orig = m.urllib.request.urlopen
    m.urllib.request.urlopen = lambda url, timeout=0: _FakeResp(
        b'{"ok":true,"result":[{"update_id":1,"message":{"chat":{"id":4242,"first_name":"Cl"}}}]}')
    try:
        d.fetch_chat_id()
    finally:
        m.urllib.request.urlopen = _orig
    check("alertes : chat id trouvé tout seul", d.tg_chat.text() == "4242", d.tg_chat.text())
    check("alertes : bouton visible en mode Telegram", d.find_chat.isEnabled())
    d.show_tuto()
    check("alertes : tuto ouvert sans erreur", True)
    return "reject"


DLG_ACTION[0] = _alerts_act
step("dialogue alertes", win.open_alerts)
DLG_ACTION[0] = "reject"
step("Arrêter x2", win.toggle_run)
wait(3000)
check("arrêt des deux", not win.is_running())
win.dev2_chk.setChecked(False)
step("open_relay", win.open_relay)
wait(600)
shot(win._relay_win, "relais")
win._relay_win.close()
_mp = win.manual_path()
check("manuel : fichier trouvé", _mp is not None and "Raccourcis clavier" in _mp.read_text(encoding="utf-8"), str(_mp))
step("waterfall en fenêtre libre (gardée pour la relance)", lambda: win.panel_window(win.dock_wf, True, None, "normal"))
wait(400)
step("close", win.close); wait(500)
print("config écrite:", os.path.exists(m.CFG_PATH), flush=True)

# relance : config relue + état des docks restauré
win2 = step("MainWindow() #2", m.MainWindow)
if win2:
    win2.show(); wait(800); shot(win2, "relance")
    print("relance: fréquences", len(win2.watch), "scènes", len(win2.scenes), flush=True)
    check("relance : la fenêtre du waterfall est rouverte", "dock_wf" in win2.panel_wins
          and win2.panel_wins["dock_wf"].isVisible() and win2.wf.window() is win2.panel_wins["dock_wf"],
          str(list(win2.panel_wins)))
    win2.close()
    wait(300)
    check("fermeture : plus aucune vraie fenêtre ouverte", not [w_ for w_ in app.topLevelWidgets()
                                                              if isinstance(w_, m.PanelWindow) and w_.isVisible()])

check("aucune exception Qt", not errors, f"{len(errors)} exception(s)")
check("aucun message d'erreur", not [k for k, _ in msgs if k in ("warning", "critical")], str(msgs))
for k, t in msgs:
    print("  message", k, ":", t[:140].replace("\n", " | "), flush=True)
print(f"\n{len(shots)} captures dans {OUT}")
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
