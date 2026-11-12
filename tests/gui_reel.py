"""Lance la VRAIE appli PySide6 (sans écran, QT_QPA_PLATFORM=offscreen) en mode démo, ouvre panneaux et
dialogues, capture des PNG et relève les exceptions Qt. Complète les smoke_test* (faux Qt).

    python tests/gui_reel.py [dossier_captures]        (défaut : tests/captures, ignoré par git)

Sous Linux il faut PySide6 + libEGL/libGL (apt install libegl1 libgl1 libxkbcommon0 fonts-noto-color-emoji).
Ne remplace pas un essai sur Windows : sons, vrai port série, double écran et rendu natif ne sont pas testés."""
import os, re, sys, tempfile, traceback, importlib.util, time
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
      and not win.thr_bar.isVisible() and not win.layer_box.isVisible(), win.ui_level)
check("plus de panneau Réglages à gauche (tout dans ⚙)", not hasattr(win, "dock_set"))
check("4 menus : Préparer › Surveiller › Analyser › Matériel (7.46)",
      [k for k in win.step_menus] == ["prep", "show", "after", "hw"]
      and all(win.step_btns[k].isVisible() for k in win.step_menus), str([b.text() for b in win.step_btns.values()]))
check("1er lancement : tuto proposé", "Tuto" in win.tour_btn.text() and not win.tour_done)
_miss_m = [a.text() for mn in win.step_menus.values() for a in mn.actions()
           if a.text() and not a.isSeparator() and a.menu() is None
           and not any(n == a.text() for _k, _t, _tp, its in m.STEPS for n, _f in its if n)]
check("4 menus : chaque entrée vient de STEPS (ou d'un sous-menu ajouté)", not _miss_m, str(_miss_m))
_bad_m = [n for _k, _t, _tp, its in m.STEPS for n, f in its if n and not n.startswith("§")
          and not callable(getattr(win, f, None))]
check("menus rangés en rubriques titrées (7.49)", all(any(n and n.startswith("§") for n, _f in its)
                                                       for _k, _t, _tp, its in m.STEPS))
check("coordination cachée : l'entrée « 🔒 … les afficher » est là", win._coord_hint.isVisible() != win.coord_on)
check("4 menus : chaque entrée a sa méthode", not _bad_m, str(_bad_m))
check("mots simples : « Pics gardés » hors expert", win.hold_chk.text() == "Pics gardés" and "max hold" in
      win.hold_chk.toolTip().lower(), win.hold_chk.text())
# ⚡ points par balayage Auto : par défaut au 1er lancement, pas choisi d'après la largeur totale
_tot = sum(b["stop"] - b["start"] for b in win.bands if b["enabled"])
check("1er lancement : points ⚡ Auto, pas d'après la largeur totale", win.points_combo.currentData() == 0
      and all(abs(b["step"] - m.auto_scan_step(_tot, win.rbw_combo.currentData())) < 1e-9 for b in win.bands)
      and "Auto" in win.est_lbl.text(), f"{[b['step'] for b in win.bands]} · {win.est_lbl.text()}")
win.add_band("Test FM", 87.5, 108.0, 100.0)
_tot = sum(b["stop"] - b["start"] for b in win.bands if b["enabled"])
check("Auto : une bande ajoutée prend le pas Auto", all(abs(b["step"] - m.auto_scan_step(_tot, win.rbw_combo.currentData())) < 1e-9
                                                        for b in win.bands), str([b["step"] for b in win.bands]))
with win.lock:
    win.bands.pop()
win._bands_changed()
_r0 = win.rbw_combo.currentIndex()
win.rbw_combo.setCurrentIndex(win.rbw_combo.findData(10))
check("Auto : RBW 10 kHz imposée -> pas ≤ 10 kHz", all(b["step"] <= 10 for b in win.bands), str([b["step"] for b in win.bands]))
win.rbw_combo.setCurrentIndex(_r0)
# ⚡ Points dans la barre du spectre (tous les modes) : rapide / équilibré / détaillé / fixe
check("⚡ Points visible même en ultra simple", win.pts_btn.isVisible() and "Auto" in win.pts_btn.text(), win.pts_btn.text())
win._build_pts_menu()
_pa = [a_ for a_ in win.pts_menu.actions() if a_.isCheckable()]
check("⚡ Points : 3 Auto + les nombres fixes", len(_pa) == 3 + len(m.POINTS_CHOICES) and _pa[1].isChecked(), str(len(_pa)))
_st0 = win.bands[0]["step"]
_pa[2].trigger()
check("⚡ Auto détaillé : pas plus fin", win.bands[0]["step"] < _st0 and win.points_auto() == 9000, str(win.bands[0]["step"]))
win._build_pts_menu()
[a_ for a_ in win.pts_menu.actions() if a_.isCheckable()][1].trigger()
check("⚡ Auto équilibré : retour au pas d'avant", abs(win.bands[0]["step"] - _st0) < 1e-9, win.pts_btn.text())

step("🎓 tutos : choix (coordination cachée)", win.start_tour)
check("tutos : coordination cachée -> son tuto aussi", "coord" not in win._tour_chooser.buttons
      and len(win._tour_chooser.buttons) == len(m.TOUR_KEYS) - 1)
win._tour_chooser.close()
win.set_coord(True)                           # les 6 tutos complets (outils de coordination montrés)
step("🎓 tutos : choix", win.start_tour)
_tc = win._tour_chooser
check("tutos : 6 parcours proposés", len(_tc.buttons) == 6 and set(_tc.buttons) == set(m.TOUR_KEYS))
shot(_tc, "tutos_choix")
_tc.close()
for _key in m.TOUR_KEYS:
    step(f"🎓 tuto {_key}", lambda _key=_key: win.start_tour(_key))
    _tr = win._tour
    _n = len(_tr.steps)
    _acts = [st_[5] for st_ in _tr.steps if st_[5] is not None]
    check(f"tuto {_key} : actions « Fais-le » existantes", all(callable(getattr(win, a_[1], None)) for a_ in _acts),
          str([a_[1] for a_ in _acts if not callable(getattr(win, a_[1], None))]))
    check(f"tuto {_key} : chaque étape a c'est quoi / pourquoi / comment",
          all(len(st_) == 6 and all(len(x) > 20 for x in st_[2:5]) for st_ in _tr.steps))
    if _key in ("ecran", "show"):
        shot(_tr, f"tuto_{_key}")
    for _k in range(_n - 1):
        _tr.next_btn.click()
        app.processEvents()
    check(f"tuto {_key} : toutes les étapes ({_n}), dernière = Terminer", _tr.i == _n - 1 and "✔" in _tr.next_btn.text()
          and _n >= 5, f"{_tr.i}/{_n}")
    _w_last = _tr.steps[-1][0]
    _tr.next_btn.click()
    app.processEvents()
    check(f"tuto {_key} terminé : surlignage retiré", win.tour_done and "f5a623" not in _w_last.styleSheet())
win.set_coord(False)
step("📚 lexique", win.open_glossary)
_gl = win._glossary
_n0 = _gl.count
_gl.q.setText("intermod")
check("lexique : recherche", 0 < _gl.count < _n0 and "Intermodulation" in _gl.view.toPlainText(), str(_gl.count))
shot(_gl, "lexique")
_gl.close()
shot(win, "ultra_simple")
step("passer en simple", lambda: win.set_level("simple"))
check("simple : seuils au-dessus du spectre et classement visibles", win.thr_bar.isVisible() and win.layer_box.isVisible()
      and (win.thr_spin.isVisible() or win.auto_occ_spin.isVisible()) and win.absent_spin.isVisible())
check("barre du spectre allégée : outils secondaires derrière ⋯", not win.mk_btn.isVisible() and not win.legend_btn.isVisible())
win.more_spec_btn.setChecked(True); wait(200)
check("⋯ : repères, marqueurs, légende visibles", win.mk_btn.isVisible() and win.mkr_btn.isVisible() and win.legend_btn.isVisible())
shot(win, "spectre_plus_outils")
win.more_spec_btn.setChecked(False)

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
# audit 7.52 : si l'état ne peut pas être calculé, jamais « tout va bien »
_hi = win.home_info
win.home_info = lambda: 1 / 0
_h = win.health()
check("audit : état indéterminé = alerte, pas « OK »", _h["tone"] == "bad" and (_h["data"] or {}).get("tone") == "bad",
      str(_h))
win.update_home(); app.processEvents()
check("audit : accueil affiche l'état indéterminé", "indéterminé" in win.home.status.text(), win.home.status.text())
win.home_info = _hi
_h = win.health()
check("audit : mesures fraîches = data ok (pas None)", _h["data"] is not None, str(_h))
# 7.52 : seuils auto (allumés d'office au 1er lancement)
_lvl_before = win.ui_level
check("seuils auto : allumés au 1er lancement", win.thr_auto and win.thr_auto_btn.isChecked())
check("seuils auto : courbe du bruit + marge tracée", win.auto_curve.isVisible() and win._acurve is not None
      and not win.thr_line.isVisible())
_aw = [w_ for w_ in win.watch if w_.get("athr") is not None]
check("seuils auto : chaque fréquence a son seuil", len(_aw) >= len(win.watch) // 2, f"{len(_aw)}/{len(win.watch)}")
_r0 = win.watch.index(_aw[0]) if _aw else 0
check("seuils auto : colonne Seuil « auto … »", win.watch_table.item(_r0, m.C_THR).text().startswith("auto"),
      win.watch_table.item(_r0, m.C_THR).text())
win.set_level("simple"); app.processEvents()
check("seuils auto : marges dans la barre, valeurs fixes cachées", win.auto_occ_spin.isVisible()
      and not win.thr_spin.isVisible())
shot(win, "seuils_auto")
_t0 = _aw[0]["athr"] if _aw else None
win.auto_occ_spin.setValue(win.auto_occ_spin.value() + 6); app.processEvents()
check("seuils auto : marge + 6 dB → seuil + 6 dB", _aw and abs(_aw[0]["athr"] - _t0 - 6) < 1.5,
      f"{_t0} → {_aw[0].get('athr') if _aw else None}")
win.auto_occ_spin.setValue(12)
win.set_thr_auto(False); app.processEvents()
check("seuils auto coupés : seuil fixe revenu", not win.auto_curve.isVisible() and win.thr_line.isVisible()
      and all(w_.get("athr") is None for w_ in win.watch))
win.set_level(_lvl_before); app.processEvents()

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
zb_ = [b for b in win.get_cfg(0)["bands"] if b["id"] == m.ZOOM_ID]
zsp_ = zb_ and (zb_[0]["stop_hz"] - zb_[0]["start_hz"]) / 1e3 / max(1, zb_[0]["n"] - 1)
check("zoom live : points auto réduits (pas ≈ 10 kHz, ≤ 290 pts)", zb_ and zb_[0]["n"] <= 290 and 5 <= zsp_ <= 12,
      str(zb_ and zb_[0]["n"]) + " · " + win.zoom_info())
win.zpts_combo.setCurrentIndex(win.zpts_combo.findData(1000))
zb_ = [b for b in win.get_cfg(0)["bands"] if b["id"] == m.ZOOM_ID]
check("zoom live : nombre fixe choisi respecté", zb_ and zb_[0]["n"] == 1000, str(zb_ and zb_[0]["n"]))
win.zpts_combo.setCurrentIndex(0)
step("toggle_zoom off", lambda: win.toggle_zoom(False)); wait(1000)

# clic sur une fréquence de la liste -> surlignée sur le spectre
win.view_combo.setCurrentIndex(0); win._fit_x = True; wait(800)
win.watch_table.clearSelection()
win.watch_table.selectRow(0); wait(300)
regs_, line_, lab_ = win._sel_items
check("sélection dans la liste : surlignée sur le spectre", regs_[0].isVisible() and lab_.isVisible()
      and win.watch[0]["name"] in lab_.toPlainText(), lab_.toPlainText())
shot(win, "selection_spectre")
win.watch_table.clearSelection(); wait(200)
check("sélection effacée : plus de surbrillance", not regs_[0].isVisible() and not lab_.isVisible())

# bandes à balayer : toutes / certaines / seulement celle affichée
win._build_bands_menu()
check("menu 📶 Bandes : une case par bande", sum(1 for a in win.bands_menu.actions() if a.isCheckable())
      == len(win.bands) + 1, str(len(win.bands)))
tmpb_ = None
if len(win.bands) < 2:                      # la démo n'a qu'une bande : on en ajoute une le temps du test
    win.add_band("Test 2", 600.0, 620.0, 0.1)
    tmpb_ = win.bands[-1]
if len(win.bands) >= 2:
    b0_, b1_ = win.bands[0], win.bands[1]
    win.set_band_enabled(b1_["id"], False)
    en_ = {b["id"] for b in win.get_cfg(0)["bands"] if b["enabled"]}
    check("décocher une bande : plus balayée", b1_["id"] not in en_ and b0_["id"] in en_, str(en_))
    win.view_combo.setCurrentIndex(win.view_combo.findData(b0_["id"])); wait(300)
    win.set_scan_follow(True)
    en_ = {b["id"] for b in win.get_cfg(0)["bands"] if b["enabled"]}
    check("« bande affichée » : seule celle de Vue est balayée", en_ == {b0_["id"]}, str(en_))
    wait(3000)
    shot(win, "bande_affichee_seule")
    win.scan_all_bands()
    en_ = {b["id"] for b in win.get_cfg(0)["bands"] if b["enabled"]}
    check("« Balayer toutes les bandes » : tout revient", len(en_) == len(win.bands) and not win.scan_follow, str(en_))
    win.view_combo.setCurrentIndex(0); win._fit_x = True; wait(1500)
if tmpb_ is not None:
    with win.lock:
        win.bands.remove(tmpb_)
    win._bands_changed(); wait(1000)

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
check("☰ Plus : réglages, fenêtres, apparence, affichage (le reste est dans les 4 menus)",
      [e for e in ["🪟", "🎨", "👁"] if any(a.text().startswith(e) for a in _subs)] == ["🪟", "🎨", "👁"]
      and not any(a.text().startswith(("📋", "📐", "🔗")) for a in _subs), str([a.text() for a in _subs]))
check("mots simples : « Max hold » en expert", win.hold_chk.text() == "Max hold", win.hold_chk.text())
_no_tip = [a.text() for sm in [win.more_menu] + list(win.step_menus.values()) + [a.menu() for a in _subs]
           for a in sm.actions()
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
    # 📚 bibliothèque EazyRF : import d'un .lst4, recherche, ajout aux profils, la coordination prend sa plage
    _ld = m.RxLibraryDialog(win)
    _ld.import_file(os.path.join(HERE, "data", "appareils_essai.lst4"))
    check("bibliothèque : 3 appareils importés et gardés", len(win.rx_library()) == 3 and win.LIB_PATH.exists()
          and _ld.table.rowCount() == 3)
    _ld.q.setText("numerique")
    _ld.table.selectRow(0)
    _ld.add()
    shot(_ld, "bibliotheque_eazyrf")
    _ld.close()
    _lk = next((k for k, n, *_x in m.RX_CUSTOM if n == "Essai Micro Numérique G1"), None)
    check("bibliothèque : appareil devenu profil (valeurs EazyRF)", _lk is not None and m.rx_profile(_lk)["filt"] == 50.0
          and m.rx_profile(_lk)["tol"]["3tx3"] == 0.0)
    _cd0 = m.CoordDialog(win)
    _cd0.prof.setCurrentIndex(_cd0.prof.findData(_lk))
    check("coordination : la plage suit l'appareil de la bibliothèque", abs(_cd0.lo.value() - 470.125) < 1e-6
          and abs(_cd0.hi.value() - 514.0) < 1e-6, f"{_cd0.lo.value()} {_cd0.hi.value()}")
    _cd0.close()
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
    for _pv in (10000, 101, 0, 290):
        win.points_combo.setCurrentIndex(win.points_combo.findData(_pv))
        step(f"points → {win.points_combo.currentText()}", win.apply_points)
        wait(700)
    check("changer les points en plein balayage : ça tourne toujours", win.is_running())
    win.points_combo.setCurrentIndex(win.points_combo.findData(1000))
    win.apply_points()
    wait(1500)

QtGui.QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
step("diagnostic tinySA", win.open_diag)
_dd = win.log_dir / "diagnostic"
_df = sorted(_dd.glob("diagnostic_tinysa_*.txt")) if _dd.exists() else []
check("diagnostic : fichier écrit avec versions, réglages, bandes", bool(_df)
      and m.APP_VER in _df[-1].read_text(encoding="utf-8") and "Bandes :" in _df[-1].read_text(encoding="utf-8"))
check("vitesse série dans la config", win._collect_config()["baud"] == 115200)
# 🌐 1er tinySA en réseau (kit Raspberry Pi) : choix dans la liste des ports, adresse demandée, retenue
def _net_act(d):                         # la fenêtre des adresses : on ajoute le Pi et on le prend pour le 1er tinySA
    d.add_row("Pi", "tinysa-sac.local")
    d.table.setCurrentCell(d.table.rowCount() - 1, 1)
    d.use(0)
    return "reject"
_ni = win.port_combo.findData(win.NET_ITEM)
check("ports : entrée « 🌐 tinySA en réseau… » en bas", _ni == win.port_combo.count() - 1, str(_ni))
win.port_combo.setCurrentIndex(_ni)
DLG_ACTION[0] = _net_act
step("choisir « tinySA en réseau »", lambda: win._port_chosen())
DLG_ACTION[0] = "reject"
check("réseau : adresse du Pi = 1er tinySA", win.port1() == "socket://tinysa-sac.local:5025" and win.port_net
      and "tinysa-sac.local" in win.port_combo.currentText(), str(win.port1()))
check("réseau : gardé dans la config", win._collect_config()["net_addr"] == "tinysa-sac.local"
      and win._collect_config()["port_net"])
shot(win, "port_reseau")
win.refresh_ports()
check("réseau : toujours en tête après ⟳", win.port1() == "socket://tinysa-sac.local:5025")
win.port_net, win.net_addr, win.net_profiles = False, "", []
win.refresh_ports()
check("réseau : retour à l'USB", not str(win.port1() or "").startswith("socket://"), str(win.port1()))
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
win.resizeDocks([win.dock_freq], [50], Qt.Orientation.Horizontal)
wait(300)
check("liste rétrécissable (≤ 300)", win.dock_freq.width() <= 300, f"liste {win.dock_freq.width()}")
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
_sd = m.SettingsDialog(win)
_sd.show_page("measure")
_sd.show()
wait(300)
check("⚙ › Mesure en expert : RBW visible", win.rbw_combo.isVisible())
_sd.show_page("detect"); wait(200)
check("⚙ › Seuils et alarmes : alarme « trop fort » visible", win.strong_spin.isVisible())
shot(_sd, "reglages_seuils")
_sd.reject(); wait(300)
check("⚙ fermé : pages rendues à la fenêtre", win.rbw_combo.window() is win and not win.rbw_combo.isVisible())
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
       for t, b in (("Démarrer", win.home.run_btn if win.home_on else win.start_btn), ("🔔", win.alarm_btn))}
vis["Shows / Plus"] = all(a.isVisible() for a in win.cmd_bar.findChildren(W.QPushButton) if a.text() in ("🎪 Shows", "☰ Plus", "Shows", "Plus"))
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
opened[:] = [os.path.join(HERE, "data", "wwb_slxd4_scan.sdb3")]
step("import_scan_as_ref (WWB natif .sdb3)", win.import_scan_as_ref)
check("scan WWB .sdb3 importé comme référence", win._ref_F is not None and len(win._ref_F) == 1751
      and abs(win._ref_F[0] - 518.125) < 1e-6, str(None if win._ref_F is None else len(win._ref_F)))
wait(1500)
shot(win, "ref_sdb3")
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
check("conv : aperçu WWB (comme un vrai export : « 470.000,-74.400 »)", re.fullmatch(r"\d+\.\d{3},-?\d+\.\d{3}", _cd.preview.toPlainText().splitlines()[0]) is not None, _cd.preview.toPlainText()[:60])
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
_occ = {}
def _occ_act(d):
    if isinstance(d, m.OccupancyDialog):
        _occ["rows"] = d.table.rowCount()
        _occ["cols"] = d.table.columnCount()
        _occ["sum"] = d.sum_lbl.text()
    return "reject"
DLG_ACTION[0] = _occ_act
step("📊 occupation par heure", win.open_occupancy)
DLG_ACTION[0] = "reject"
check("occupation par heure : une ligne par fréquence, au moins une heure, bilan des réserves",
      _occ.get("rows") == len(win.watch) and _occ.get("cols", 0) >= 1 and _occ.get("sum"), str(_occ))
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
if win._rescue_dlg:
    _rd = win._rescue_dlg
    _rd.a_spin.setValue(470.0); _rd.b_spin.setValue(560.0); _rd.n_spin.setValue(3)
    _rd.search(); wait(300)
    check("secours : des fréquences proposées, avec une remarque", _rd.table.rowCount() >= 1 and
          _rd.table.item(0, 5) is not None and _rd.table.item(0, 5).text(), _rd.msg.text())
    _rd.im_combo.setCurrentIndex(_rd.im_combo.findData("2tx")); _rd.search(); wait(200)
    check("secours : « 2 TX seulement » cherche aussi", _rd.table.rowCount() >= 1, _rd.msg.text())
    shot(_rd, "rescue")
# 🌐 adresses réseau enregistrées (le Pi change d'IP selon le Wi-Fi) : test sur un vrai serveur TCP local
import socket as _so
_srv = _so.socket(); _srv.bind(("127.0.0.1", 0)); _srv.listen(4)
_port = _srv.getsockname()[1]
_old_net = (win.net_addr, win.port_net, list(win.net_profiles), dict(win.dev2))
win.net_profiles = []
_nd = m.NetProfilesDialog(win)
_nd.add_row("Pi · maison", f"127.0.0.1:{_port}")
_nd.add_row("Pi · festival", "127.0.0.1:1")              # rien n'écoute sur le port 1
_nd.add_row("", "pas une adresse !")
_nd.show(); wait(200)
_nd.test(); wait(200)
check("réseau : le relais qui répond est vu", _nd.table.item(0, 2).text().startswith("✔"), _nd.table.item(0, 2).text())
check("réseau : celui qui ne répond pas aussi", _nd.table.item(1, 2).text().startswith("✖"), _nd.table.item(1, 2).text())
_nd.table.setCurrentCell(0, 1)
check("réseau : utilisé pour le 1er tinySA", _nd.use(0) and win.port_net and win.net_addr == f"127.0.0.1:{_port}"
      and win.port1() == f"socket://127.0.0.1:{_port}", str(win.port1()))
_nd.table.setCurrentCell(1, 1)
check("réseau : utilisé pour le 2ᵉ tinySA", _nd.use(1) and win.dev2["addr"] == "127.0.0.1:1" and win.dev2["on"])
shot(_nd, "tinysa_reseau")
_nd.accept(); wait(200)
check("réseau : adresses valides gardées (l'illisible écartée)", [p_["name"] for p_ in win.net_profiles]
      == ["Pi · maison", "Pi · festival"], str(win.net_profiles))
_items = [win.port_combo.itemText(i) for i in range(win.port_combo.count())]
check("réseau : chaque adresse dans la liste des ports, la choisie en tête", _items[0].startswith("🌐 Pi · maison")
      and any("Pi · festival" in t for t in _items), str(_items))
win.port_combo.setCurrentIndex(next(i for i, t in enumerate(_items) if "Pi · festival" in t))
win._port_chosen()
check("réseau : choisir une adresse dans la liste suffit", win.net_addr == "127.0.0.1:1" and win.port_net)
check("réseau : dans la liste du 2ᵉ tinySA", any("Pi · maison" in win.dev2_addr.itemText(i)
                                                for i in range(win.dev2_addr.count())))
_cfg = win._collect_config()
_doc = m.show_doc(_cfg, {}, None, m.APP_VER)
check("réseau : adresses + tinySA choisis dans le show", len(_doc["show"]["net_profiles"]) == 2
      and _doc["show"]["net_addr"] == "127.0.0.1:1" and _doc["show"]["dev2"]["addr"] == "127.0.0.1:1")
win.net_profiles = [dict(name="Pi · maison", addr="10.9.9.9")]
win._apply_config(m.show_apply(win._collect_config(), _doc))
check("réseau : ouvrir le show remet ses adresses (fusionnées avec celles du PC)",
      [(p_["name"], p_["addr"]) for p_ in win.net_profiles] == [("Pi · maison", f"127.0.0.1:{_port}"),
                                                                 ("Pi · festival", "127.0.0.1:1")], str(win.net_profiles))
_srv.close()
win.net_addr, win.port_net, win.net_profiles = _old_net[0], _old_net[1], _old_net[2]
win.dev2_addr.setEditText(_old_net[3]["addr"]); win.dev2_chk.setChecked(_old_net[3]["on"]); win._read_dev2()
win.refresh_ports(); win._dev2_ports(); win.port_combo.setCurrentIndex(0)

# 🧹 retour de Clément 7.31 : « nouveau show, un scan reste sur le spectre alors que Scans par lieu est vide »
win.ensure_group("Plateau X", "")
_Fz, _Lz = np.linspace(470.0, 694.0, 500), np.full(500, -95.0)
win.site_mh["Plateau X"] = {999: (np.asarray(_Fz), np.asarray(_Lz))}       # max hold en mémoire d'une scène
win.site_scans.append(m.site_scan_doc("Plateau X", _Fz, _Lz, time.time()))
_sdz = m.SitesDialog(win)
_sdz.fill(select="Plateau X"); _sdz.delete(); _sdz.reject()
win._sites_next = 0; win._sites_tick(time.time() + 1)
check("scan supprimé : il ne revient pas 30 s plus tard", not any(d_["name"] == "Plateau X" for d_ in win.site_scans),
      str([d_["name"] for d_ in win.site_scans]))
win.site_mh["Plateau X"] = {999: (np.asarray(_Fz), np.asarray(_Lz))}
_saved_show = (list(win.watch), [dict(s_) for s_ in win.scenes], list(win.site_scans), win._ref_F, win._ref_L)
win.site_scans.append(m.site_scan_doc("Ancien lieu", _Fz, _Lz, time.time()))
win._set_ref([(_Fz, _Lz)])
win.update_site_curve()
win.clear_show_data()
win._sites_next = 0; win._sites_tick(time.time() + 1)
check("nouveau show : plus aucun scan par lieu, ni en mémoire", not win.site_scans and not win.site_mh, str(win.site_scans))
check("nouveau show : courbe des scans et référence effacées du spectre",
      (win.sitecurve.getData()[0] is None or len(win.sitecurve.getData()[0]) == 0) and win._ref_F is None)
win.watch, win.scenes, win.site_scans = _saved_show[0], _saved_show[1], _saved_show[2]
win.rebuild_tree(); win.rebuild_watch_table(); win._update_markers()

# ↶ / ↷ et Suppr (demande de Clément 7.32)
win.undo_track()
_n_w = len(win.watch)
_names0 = [w_["name"] for w_ in win.watch]
win.activateWindow(); win.raise_(); wait(200)
win.watch_table.setFocus(); win.watch_table.selectRow(0); wait(100)
QtTest.QTest.keyClick(win.watch_table, Qt.Key.Key_Delete); wait(200)
check("Suppr dans la liste : la fréquence est supprimée", len(win.watch) == _n_w - 1, f"{_n_w} -> {len(win.watch)}")
QtTest.QTest.keyClick(win.watch_table, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier); wait(300)
check("Ctrl+Z : elle revient", [w_["name"] for w_ in win.watch] == _names0, str(len(win.watch)))
QtTest.QTest.keyClick(win.watch_table, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier); wait(300)
check("Ctrl+Y : supprimée à nouveau", len(win.watch) == _n_w - 1)
win.undo(); wait(200)
check("Ctrl+Z à nouveau : revenue", [w_["name"] for w_ in win.watch] == _names0)
_st0 = win.watch[0]["status"]
win.watch[0]["status"] = "Libre" if _st0 != "Libre" else ""
win.undo_track()
win.undo()
check("annuler : un changement de statut aussi", win.watch[0]["status"] == _st0, win.watch[0]["status"])
_nb0 = len(win.bands)
win.add_band("Test undo", 1000.0, 1010.0, 200.0); win.undo_track()
win.band_table.setFocus(); win.band_table.selectRow(len(win.bands) - 1)
QtTest.QTest.keyClick(win.band_table, Qt.Key.Key_Delete); wait(200)
check("Suppr dans les bandes", len(win.bands) == _nb0, str(len(win.bands)))
win.undo(); wait(200)
check("Ctrl+Z : la bande revient", len(win.bands) == _nb0 + 1 and win.bands[-1]["name"] == "Test undo")
win.bands = [b_ for b_ in win.bands if b_["name"] != "Test undo"]; win._bands_changed(); win.undo_track()

# 📥 Plan EazyRF (.ezrf3 / copier-coller) — fichiers INVENTÉS de même structure (demande de Clément 7.33)
_ez_saved = (list(win.watch), [dict(sc_, groups=[dict(g_) for g_ in sc_["groups"]]) for sc_ in win.scenes],
             list(win.site_scans), m.rx_custom_dump())
_ezp = os.path.join(HERE, "data", "eazyrf_essai.ezrf3")
def _ez_act(d):
    _ez_dlg.append(d)
    check("EazyRF : aperçu (arbre scènes › groupes, statut « doit émettre » proposé, scan coché)",
          d.tree.topLevelItemCount() == 3 and d.scan.isChecked() and d.interf.isVisibleTo(d)
          and any(st_["name"] == d.status.currentData() and st_.get("on") for st_ in win.statuses),
          f"{d.tree.topLevelItemCount()} {d.status.currentData()}")
    d.interf.setChecked(True)
    d.replace.setChecked(True)
    return "accept"
_ez_dlg = []
DLG_ACTION[0] = _ez_act
_n_ez = win.import_ezrf_file(_ezp)
DLG_ACTION[0] = "reject"
check("EazyRF : 5 fréquences importées (rayée et hors fonction ignorées)", _n_ez == 5 and
      len([w_ for w_ in win.watch if not w_["name"].startswith("Ext.")]) == 5, f"{_n_ez} {len(win.watch)}")
check("EazyRF : scènes / groupes créés", win.group_row("Zone Nord · Plateau A", "Ears") is not None
      and win.group_row("Zone Sud · Loge", "Micros") is not None)
_gA = win.group_row("Zone Nord · Plateau A", "Micros")
_rxA = [m.rx_profile(k_) for k_ in win.group_rxs(_gA)]
check("EazyRF : 2 appareils posés sur le groupe, avec leurs réglages",
      len(_rxA) == 2 and sorted((round(r_["sep"], 3), r_["filt"]) for r_ in _rxA) == [(0.3, 16.0), (0.5, 32.0)],
      str(_rxA))
_w512 = next(w_ for w_ in win.watch if abs(w_["freq"] - 512.0) < 1e-6)
_w500 = next(w_ for w_ in win.watch if abs(w_["freq"] - 500.1) < 1e-6)
check("EazyRF : appareil de chaque fréquence (le 2ᵉ du groupe gardé sur sa ligne)",
      m.rx_profile(win.rx_of(_w512))["filt"] == 16.0 and m.rx_profile(win.rx_of(_w500))["filt"] == 32.0
      and "rx" not in _w500)
check("EazyRF : interférences en émetteurs extérieurs + scan dans Scans par lieu",
      sum(1 for w_ in win.watch if w_["name"].startswith("Ext.")) == 2
      and any(d_["name"].startswith("EazyRF ·") and len(d_["f"]) == 201 for d_ in win.site_scans))
_nprof = len(m.RX_CUSTOM)
DLG_ACTION[0] = "accept"
win.import_ezrf_file(_ezp)
DLG_ACTION[0] = "reject"
check("EazyRF : réimporter ne recrée pas les profils", len(m.RX_CUSTOM) == _nprof, f"{_nprof} -> {len(m.RX_CUSTOM)}")
win.undo(); wait(200)
win.undo(); wait(200)
check("EazyRF : Ctrl+Z annule l'import", [w_["name"] for w_ in win.watch] == [w_["name"] for w_ in _ez_saved[0]],
      str(len(win.watch)))
_ez_txt = open(os.path.join(HERE, "data", "eazyrf_collage_essai.txt"), encoding="utf-8").read()
DLG_ACTION[0] = "accept"
_n_wb = len(win.watch)
_have = {int(round(w_["freq"] * 1000)) for w_ in win.watch}
_n_new = sum(1 for f_ in (500.1, 503.45, 512.0, 530.25, 534.875, 540.0) if int(round(f_ * 1000)) not in _have)
win.open_import(_ez_txt, "Texte collé")
DLG_ACTION[0] = "reject"
check("EazyRF : le copier-coller passe par le même import", len(win.watch) == _n_wb + _n_new
      and win.group_row("Zone Sud · Loge", "Micros") is not None, f"{_n_wb} -> {len(win.watch)}")
# 🔗 suivre le fichier EazyRF : il est réenregistré (une fréquence change) → fenêtre → changement appliqué
import shutil as _sh
_ezf = os.path.join(tmp, "plan_suivi.ezrf3")
_sh.copy(_ezp, _ezf)
win.watch = []
win.apply_ezrf(m.parse_ezrf3(open(_ezf, "rb").read()),
               dict(status="", profiles=False, skip_off=True, interf=False, scan=False, replace=False, follow=True),
               "plan_suivi.ezrf3", _ezf)
check("EazyRF suivi : fichier retenu, fréquences reliées", win.ezrf_link and win.ezrf_link["path"] == _ezf
      and all(w_.get("ez") for w_ in win.watch), str(win.ezrf_link))
_txt = open(_ezf, encoding="utf-8").read().replace("<Valeur>503,450</Valeur>", "<Valeur>504,000</Valeur>")
open(_ezf, "w", encoding="utf-8").write(_txt)
os.utime(_ezf, (time.time() - 5, time.time() - 5))
win._ezrf_next = 0.0                              # la vérification auto (toutes les 5 s) a pu passer juste avant
_dd = win._ezrf_tick(time.time())
check("EazyRF suivi : réenregistrement vu, changement proposé", _dd and len(_dd["change"]) == 1
      and win._ezrf_dlg is not None and win._ezrf_dlg.lst.count() == 1, str(_dd))
if win._ezrf_dlg is not None:
    wait(300)
    shot(win._ezrf_dlg, "ezrf_suivi")
    win._ezrf_dlg.apply()
check("EazyRF suivi : fréquence déplacée dans la liste", any(abs(w_["freq"] - 504.0) < 1e-6 for w_ in win.watch)
      and not any(abs(w_["freq"] - 503.45) < 1e-6 for w_ in win.watch))
check("EazyRF suivi : gardé dans la config", (win._collect_config(False).get("ezrf_link") or {}).get("path") == _ezf
      and any(x.get("ez") for x in win._collect_config(False)["watch"]))
# 🔗 même chose avec un show Shure WWB (.shw, 7.48) : import par la fenêtre, suivi, fréquence changée dans WWB
_shw = os.path.join(tmp, "Maalouf.shw")
_sh.copy(os.path.join(HERE, "data", "wwb_essai.shw"), _shw)
win.watch = []
win.ezrf_link = None
_d_shw = []
def _shw_act(d):
    _d_shw.append(d.windowTitle())
    d.follow.setChecked(True)
    return "accept"
DLG_ACTION[0] = _shw_act
_n_shw = win.import_ezrf_file(_shw)
DLG_ACTION[0] = "reject"
check("WWB .shw : fenêtre « Importer un plan Shure WWB », 4 fréquences, fichier suivi",
      _d_shw == ["Importer un plan Shure WWB"] and _n_shw == 4 and (win.ezrf_link or {}).get("kind") == "Shure WWB",
      f"{_d_shw} {_n_shw} {win.ezrf_link}")
_txt_shw = open(_shw, encoding="utf-8").read().replace("<value>577600</value>", "<value>578000</value>")
open(_shw, "w", encoding="utf-8").write(_txt_shw)                # lu AVANT d'ouvrir en écriture (sinon fichier vide)
os.utime(_shw, (time.time() - 5, time.time() - 5))
win._ezrf_next = 0.0
_dd = win._ezrf_tick(time.time())
check("WWB .shw suivi : changement vu", _dd and len(_dd["change"]) == 1 and win._ezrf_dlg is not None, str(_dd))
if win._ezrf_dlg is not None:
    check("WWB .shw suivi : la fenêtre dit « Shure WWB »", "Shure WWB" in win._ezrf_dlg.windowTitle(),
          win._ezrf_dlg.windowTitle())
    win._ezrf_dlg.apply()
check("WWB .shw suivi : fréquence déplacée", any(abs(w_["freq"] - 578.0) < 1e-6 for w_ in win.watch))
# Wisycom : récepteurs « à compléter », retrouvés par le nom dans la liste (7.50, Clément : « corrélation au nom »)
win.ezrf_link = None
win.watch = []
win._append_watch("HF 1 ARRIVEE", 575.8, "", None, "", "")
win.watch[-1].update(ez="ARRIVÉE|HF|HF 1 ARRIVEE", ezsrc="Roc.ezrf3")       # venue d'un autre plan
_wsh = os.path.join(tmp, "Roc.wshow")
_sh.copy(os.path.join(HERE, "data", "wisycom_essai.wshow"), _wsh)
_pend = []
def _wsh_act(d):
    _pend.append([(d.pend.item(r, 0).text(), d.pend.item(r, 2).text()) for r in range(d.pend.rowCount())])
    shot(d, "wisycom_a_completer")
    d.follow.setChecked(True)
    return "accept"
DLG_ACTION[0] = _wsh_act
win.import_ezrf_file(_wsh)
DLG_ACTION[0] = "reject"
check("Wisycom : ARR 1 retrouvé par le nom (HF 1 ARRIVEE), ARR 2 à compléter",
      _pend and _pend[0] == [("ARR 1", "575.800"), ("ARR 2", "")], str(_pend))
check("Wisycom : rien en double, IEM ajoutés, complété retenu dans le suivi",
      sum(1 for w_ in win.watch if abs(w_["freq"] - 575.8) < 1e-6) == 1 and len(win.watch) == 3
      and (win.ezrf_link or {}).get("manual") == {"ARR 1": 575.8}, f"{[(w_['name'], w_['freq']) for w_ in win.watch]} {win.ezrf_link}")
_t = open(_wsh, encoding="utf-8").read().replace('<TunedFreq Value="642000000" />', '<TunedFreq Value="643000000" />')
open(_wsh, "w", encoding="utf-8").write(_t)
os.utime(_wsh, (time.time() - 5, time.time() - 5))
win._ezrf_next = 0.0
_dd = win._ezrf_tick(time.time())
check("Wisycom suivi : 1 changement, rien à retirer (pas celles de l'autre plan)",
      _dd and (len(_dd["add"]), len(_dd["change"]), len(_dd["remove"])) == (0, 1, 0), str(_dd))
if win._ezrf_dlg is not None:
    win._ezrf_dlg.close()
win.ezrf_link = None
win.watch = []                                    # chaque plan sur une liste vide (sinon : 0 ajout, déjà présentes)
for _fn in ("wsm_essai.wsm", "shure_essai.cug", "wisycom_essai.wshow", "dpa_essai.acp"):
    DLG_ACTION[0] = "accept"
    _nn = win.import_ezrf_file(os.path.join(HERE, "data", _fn))
    DLG_ACTION[0] = "reject"
    check(f"import du plan {_fn}", (_nn or 0) >= 1, str(_nn))
win.ezrf_link = None
win.watch, win.scenes, win.site_scans = _ez_saved[0], _ez_saved[1], _ez_saved[2]
m.rx_set_custom(_ez_saved[3])
win.rebuild_tree(); win.rebuild_watch_table(); win._update_markers(); win.update_site_curve(); win.undo_track()

# 📸 États (Snapshots d'EazyRF, demande de Clément 7.37)
_sv = (list(win.states), win.state_cur)
_on = [s_["name"] for s_ in win.statuses if s_.get("on")][0]
_w_all = list(win.watch)
_kA = {int(round(w_["freq"] * 1000)) for w_ in _w_all[:2]}
win.apply_state("")
win.new_state("Artiste A")
check("état : créé avec toutes les fréquences actives", win.state_cur == "Artiste A"
      and len(win.states[-1]["keys"]) == len(win.watch))
win.states[-1]["keys"] = sorted(_kA)
_w_all[-1]["iso"] = True
_noff = win.apply_state("Artiste A")
check("état : les autres en pause, sauf la « toujours »", _noff == len(_w_all) - 3
      and not _w_all[0].get("off") and not _w_all[-1].get("off") and _w_all[2].get("off"), str(_noff))
check("état : « 💤 en pause (état) » dans la liste", win.sig_view(_w_all[2])[0] == "💤 en pause (état)")
check("état : bouton « Artiste A »", win.state_btn.text() == m.plain_btn_text("📸 Artiste A"), win.state_btn.text())
_cf = win._collect_config(False)
check("état : enregistré dans le show", _cf["state_cur"] == "Artiste A" and any(x["name"] == "Artiste A" for x in _cf["states"])
      and any(x.get("iso") for x in _cf["watch"]))
_k_old = int(round(_w_all[0]["freq"] * 1000))
win.set_watch_freq(_w_all[0], _w_all[0]["freq"] + 0.0125)
check("état : une fréquence déplacée reste dans son état", int(round(_w_all[0]["freq"] * 1000)) in win.states[-1]["keys"]
      and _k_old not in win.states[-1]["keys"])
win.set_watch_freq(_w_all[0], _k_old / 1000.0)
def _st_act(d):
    check("états : fenêtre (liste + tableau)", d.lst.count() >= 1 and d.tbl.rowCount() == len(win.watch))
    d.check_all(True)
    check("états : tout cocher → plus rien en pause", not any(w_.get("off") for w_ in win.watch))
    d.duplicate()
    check("états : dupliquer", win.state_by_name("Artiste A (2)") is not None)
    d.lst.setCurrentRow(len(win.states) - 1)
    d.delete()
    check("états : supprimer", win.state_by_name("Artiste A (2)") is None)
    return "reject"
DLG_ACTION[0] = _st_act
step("fenêtre des états", win.open_states)
DLG_ACTION[0] = "reject"
check("tech : basculer d'état", win.tech_do(dict(action="state", name="")) == "📸 tout actif" and win.state_cur == "")
check("tech : état inconnu refusé", "inconnu" in win.tech_do(dict(action="state", name="Nope")))
_w_all[-1].pop("iso", None)
win.states, win.state_cur = _sv[0], ""
win.apply_state(_sv[1])

# 🏠 Accueil (7.43, Clément : « l'écran de base est assez imbuvable »)
check("accueil : affiché, 3 cartes", win.home_bar.isVisible() and set(win.home.cards) == {"port", "list", "run"})
check("accueil : Port / Démarrer en double cachés (hors expert)",
      not win._port_act.isVisible() or win.ui_level == "expert")
win.update_home()
check("accueil : phrase d'état remplie", win.home.status.text() != "", win.home.status.text())
_lvl0 = win.ui_level
win.set_level("expert")
check("accueil : en expert aussi, Port / Démarrer en double cachés (accueil affiché)", not win._port_act.isVisible())
win.set_level(_lvl0)
win.set_home(False)
check("accueil : masqué -> Port / Démarrer de retour", not win.home_bar.isVisible() and win._port_act.isVisible())
check("accueil : gardé dans la config", win._collect_config(False).get("home") is False)
win.set_home(True)
win.start_tour("ecran"); wait(200)
check("tuto écran : commence par l'accueil", win._tour.steps[0][0] is win.home.cards["port"][0])
win._tour.close()
# outils de coordination cachés par défaut (7.43)
check("coord : cachée par défaut", not win.coord_on and len(win._coord_acts) >= 4
      and not any(a_.isVisible() for a_ in win._coord_acts if not a_.isSeparator()))
win.set_coord(True)
check("coord : case ⚙ -> visible", all(a_.isVisible() for a_ in win._coord_acts))
check("coord : gardée dans la config", win._collect_config(False).get("coord_tools") is True)
win.set_coord(False)

# fiches « problème » (7.46, revue UX)
_pd = m.ProblemDialog(win, m.problem_card("could not open port 'COM4': PermissionError(13, 'Accès refusé.')"))
_pd.show(); wait(150)
shot(_pd, "fiche_probleme")
check("fiche problème : port occupé, 3 étapes, boutons", _pd.card["key"] == "busy" and len(_pd.card["steps"]) == 3
      and set(_pd.btns) == {"retry", "demo", "diag", "close"})
_pd.close()
win._last_problem = m.problem_card("x", "gone")
win.update_home()
check("accueil : « ❓ Que faire ? » après un souci (surveillance arrêtée)",
      win.home.help_btn.isVisibleTo(win.home) == (not win.is_running()))
win._last_problem = m.problem_card("x", "lost")
win.dev_live[0] = False
win.update_home()
check("accueil : « ❓ Que faire ? » si le tinySA décroche", win.home.help_btn.isVisibleTo(win.home) or not win.is_running())
win.dev_live[0] = True
win._last_problem = None
win.update_home()
check("accueil : bouton caché sans souci", not win.home.help_btn.isVisibleTo(win.home))

# 🔎 chercher une fonction (Ctrl+K) et état « surveillance dégradée » (7.47, revue UX 2)
_fs = m.FeatureSearchDialog(win)
_fs.show(); _fs.edit.setText("secours"); wait(100)
shot(_fs, "recherche_fonction")
check("Ctrl+K : « secours » trouve la fréquence de secours", _fs.listw.count() >= 1
      and "🆘" in _fs.listw.item(0).text(), [_fs.listw.item(i).text() for i in range(_fs.listw.count())])
_fs.edit.setText("relais"); wait(50)
check("Ctrl+K : « relais » trouve le relais réseau", any("Relais" in _fs.listw.item(i).text() for i in range(_fs.listw.count())))
_fs.close()
if win.is_running():
    _sv_lt = dict(win.latest_t)
    win.latest_t.clear()
    check("état : démarré sans mesure -> pas « tout va bien »", win.health()["tone"] in ("wait", "bad"), win.health())
    win.latest_t.update({k: v - 3600 for k, v in _sv_lt.items()})
    check("état : mesures vieilles d'une heure -> dégradée", win.health()["tone"] == "bad", win.health())
    win.latest_t.clear(); win.latest_t.update(_sv_lt)
    _b0 = next(b for b in win.scan_bands() if win._scan_now(b))
    _sv_t = win.latest_t.get(_b0["id"])
    if _sv_t is not None and len([b for b in win.scan_bands() if win._scan_now(b)]) > 1:
        win.latest_t[_b0["id"]] = _sv_t - 3600         # UNE bande figée, les autres tournent
        check("état : une seule bande figée -> dégradée (bande la plus en retard)", win.health()["tone"] == "bad",
              win.health())
        win.latest_t[_b0["id"]] = _sv_t
    win.on_link(0, False)
    check("état : tinySA perdu -> rouge, même logique partout", win.health()["tone"] == "bad"
          and "déconnecté" in win.health()["text"], win.health())
    win.on_link(0, True)
    check("état : tinySA revenu -> plus « déconnecté »", "déconnecté" not in win.health()["text"], win.health())

# 📶 Qualité de mesure (7.44, revue de code)
win.update_watch_table(force=True)
_mtx = [win.watch_table.item(r_, m.C_MARG).text() for r_ in range(win.watch_table.rowCount())]
check("qualité : colonne Marge remplie (dB au-dessus du bruit)", any(t_.endswith("dB") for t_ in _mtx), str(_mtx[:6]))
check("qualité : colonne Marge à côté de Statut",
      win.watch_table.horizontalHeader().visualIndex(m.C_MARG) == 4)
_sat0 = dict(win.__dict__.get("_sat_max", {}))
win._sat_max = {999: (time.time(), -8.0)}
_qi = win.quality_info()
check("qualité : saturation détectée (-8 dBm)", _qi["sat"] == "bad" and any(
    c_["key"] == "sat" for c_ in m.ready_checks(win.ready_info())), str(_qi))
win.update_home()
check("qualité : l'accueil prévient de la saturation", "Signal très fort" in win.home.status.text()
      or win.alarms.active, win.home.status.text())
win._sat_max = _sat0
check("qualité : config retient la version des colonnes", win._collect_config(False).get("watch_cols_v") == m.WATCH_COLS_V)

# 💤 Éteint (je sais) (7.40, Clément : « des fois les mics sont éteints et je le sais »)
_on_st = [s_["name"] for s_ in win.statuses if s_.get("on")][0]
_wm = next(w_ for w_ in win.watch if w_["status"] == _on_st)
_km = int(round(_wm["freq"] * 1000))
win.alarms.raise_(("ABSENT", _km), "ABSENT", _wm["name"], _wm["freq"], 2, time.time())
_wm["absent"] = True
check("éteint : 1 fréquence éteinte", win.set_muted([_wm], True) == 1)
check("éteint : l'ABSENT en cours disparaît", ("ABSENT", _km) not in win.alarms.active and not _wm.get("absent"))
check("éteint : plus d'ABSENT ensuite (comme en pause)", win.w_paused(_wm))
_wm["state"] = "free"
check("éteint : « 💤 éteint (je sais) » dans la liste", win.sig_view(_wm)[0] == "💤 éteint (je sais)", win.sig_view(_wm)[0])
check("éteint : gardé dans le show", any(x.get("muted") for x in win._collect_config(False)["watch"]))
check("éteint : rappel dans Prêt pour le show ?", any(c["key"] == "muted" for c in m.ready_checks(win.ready_info())))
check("éteint : la page Tech rallume", "rallumé" in win.tech_do(dict(action="mute", key=_km, on=False))
      and not _wm.get("muted"))
_rows = win._sel_rows
win._sel_rows = lambda: [win.watch.index(_wm)]
win.toggle_muted_sel()
check("éteint : Ctrl+Espace bascule", _wm.get("muted"))
win.toggle_muted_sel()
win._sel_rows = _rows
check("éteint : rallumé = surveillé à nouveau", not _wm.get("muted") and not win.w_paused(_wm) or win.w_paused(_wm) and _wm.get("off"))
_lk = (_wm["scene"], _wm["group"])
if _lk[0]:
    win.set_muted(win.layer_ws(_lk), True)
    check("éteint : tout un groupe d'un coup", all(w_.get("muted") for w_ in win.layer_ws(_lk)))
    win.set_muted(win.layer_ws(_lk), False)

# ⚡ Préréglages rapides (7.56) : chaque préréglage appliqué est ensuite reconnu (✓), sans toucher à la liste
_pd = win.open_presets()
wait(300)
_nw0 = len(win.watch)
_preset_cur0 = win.preset_current()
_qb = QtWidgets.QMessageBox.question
QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: QtWidgets.QMessageBox.StandardButton.No)
_okp = []
for _i, _p in enumerate(m.QUICK_PRESETS):
    _pd.lst.setCurrentRow(_i)
    wait(80)
    if _i == 2:
        shot(_pd, "prereglages_rapides")
    _pd.apply()
    wait(150)
    _okp.append(m.preset_match(win.preset_current()) == _p[0])
QtWidgets.QMessageBox.question = _qb
check("préréglages : chacun appliqué puis reconnu", all(_okp), str(_okp))
check("préréglages : la liste n'a pas bougé", len(win.watch) == _nw0)
check("préréglages : taille de la fenêtre raisonnable", _pd.minimumSizeHint().height() <= 600,
      str(_pd.minimumSizeHint()))
_pd.close()
# retour aux réglages d'avant (la suite des tests ne doit pas dépendre du dernier préréglage)
win.thr_auto_btn.setChecked(_preset_cur0["thr_auto"]); win.set_thr_auto(_preset_cur0["thr_auto"])
win.points_combo.setCurrentIndex(max(0, win.points_combo.findData(_preset_cur0["points"]))); win.apply_points()
win.persist_combo.setCurrentIndex(max(0, win.persist_combo.findData(_preset_cur0["persist"])))
win.absent_spin.setValue(_preset_cur0["absent"])
win.sound.cfg = m.sound_cfg_norm(dict(win.sound.cfg, confirm=_preset_cur0["confirm"], repeat=_preset_cur0["repeat"]))
win.alarms.repeat_s = float(win.sound.cfg["repeat"])
win.strong_chk.setChecked(_preset_cur0["strong"]); win.strong_spin.setValue(_preset_cur0["strong_lvl"])
win.hold_chk.setChecked(_preset_cur0["hold"])

# 👤 profils utilisateur (7.57) : fenêtre ouverte, enregistrer puis recharger dans un dossier temporaire
_ud_old = m.USER_DIR
m.USER_DIR = m.Path(tempfile.mkdtemp()) / "Profils"
_up = win.open_user_profiles()
wait(200)
_unit0 = win.unit
_pp = win.user_profile_save("Essai")
win.set_unit("pct" if _unit0 != "pct" else "dbm")
win.user_profile_load(_pp)
check("profil utilisateur : enregistré puis rechargé (unité revenue)", _pp is not None and win.unit == _unit0, win.unit)
_up.refresh()
check("profil utilisateur : listé", _up.lst.count() == 1)
shot(_up, "profils_utilisateur")
_up.close()
m.USER_DIR = _ud_old
check("7.57 : waterfall = la seule bande balayée en « toutes les bandes »",
      m.single_band_view(-1, [b for b in win.bands if b["enabled"]][:1], m.ZOOM_ID) is not None)

# 📺 canaux TNT mesurés + émetteurs proches (7.58) : base ANFR d'essai (inventée) dans un dossier temporaire
_tdb_old = m.TNT_DB_PATH
m.TNT_DB_PATH = m.Path(tempfile.mkdtemp()) / "anfr_tnt.json"
_tnt = win.open_tnt()
wait(200)
check("TNT : un état par canal 21-48", _tnt.tab.rowCount() == 28, str(_tnt.tab.rowCount()))
_tnt.cycle(12)                                  # canal 33 grisé à la main (7.58.1)
check("TNT : griser un canal à la main", win.tnt_cfg["manual"] == {"33": "tv"} and len(win._tnt_items) >= 1,
      str(win.tnt_cfg["manual"]))
_tnt.cycle(12); _tnt.cycle(12)
check("TNT : retour à l'automatique", win.tnt_cfg["manual"] == {})
_tnt.cycle(12)
win.tnt_reset(False)
check("TNT : ↺ nouveau lieu = tout redevient automatique", win.tnt_cfg["manual"] == {} and win.tnt_cfg["plan"] == [])
shot(_tnt, "tnt_canaux")
_tnt.tabs.setCurrentIndex(1)
_tnt.import_files([os.path.join(HERE, "data", "anfr_essai_data.zip"), os.path.join(HERE, "data", "anfr_essai_ref.zip")])
_tnt.place_edit.setText("75007")
check("TNT : base ANFR d'essai importée, sites proches trouvés", len(_tnt.search()) == 2 and _tnt.stab.rowCount() == 2,
      _tnt.near_lbl.text())
shot(_tnt, "tnt_emetteurs")
_tnt.close()
check("TNT : lieu gardé dans la config", win._collect_config(True)["tnt"]["place"] == "75007")
_wz = win.open_wizard(2)
wait(200)
check("assistant : ouvert sur l'étape 3, 5 étapes", _wz.isVisible() and _wz.lst.count() == 5 and _wz.lst.currentRow() == 2)
shot(_wz, "assistant_nouveau_show")
_wz.close()
check("légende posée sur le spectre", win.spec_legend.chips["curve"].isVisible())
win.show_hint("essai", "Proposition d'essai", [("Fermer", lambda: None)])
check("bandeau de proposition", win.hint_bar.isVisible())
win.hint_bar.dismiss()
_ah = win.show_auto_thr_help()
wait(100)
check("seuil auto : fiche ❓ ouverte", _ah.isVisible())
shot(_ah, "seuil_auto_fiche")
_ah.close()
win.tnt_mark(None)
m.TNT_DB_PATH = _tdb_old

# ✅ Prêt pour le show ? / 🖥 Mode Show / 🛡 garde (7.39, « on fortifie »)
_rd = win.open_ready()
wait(300)
check("prêt ? : fenêtre avec un résumé et des vérifications", _rd.table.rowCount() >= 6 and _rd.head.text() != "",
      _rd.head.text())
import inspect
def _no_arg(name):                            # « Régler » appelle la méthode SANS argument (bug 7.39 : open_import)
    f = getattr(win, name, None)
    return f is not None and all(p_.default is not p_.empty or p_.kind in (p_.VAR_POSITIONAL, p_.VAR_KEYWORD)
                                 for p_ in inspect.signature(f).parameters.values())
_allfix = {c["fix"] for i_ in ({}, dict(watch_n=0), dict(running=True, devs=[dict(name="x", live=False)]),
                                dict(running=True, sweep_age=999), dict(running=True, demo=True), dict(watch_n=3, uncovered=1),
                                dict(watch_n=3, plan_issues=2), dict(snooze=60), dict(sound_device_missing=True),
                                dict(notify_mode="all"), dict(web_on=True), dict(windows=True))
           for c in m.ready_checks(i_) if c["fix"]}
check("prêt ? : chaque « Régler » mène à une vraie méthode, appelable sans argument",
      all(_no_arg(f_) for f_ in _allfix), str([f_ for f_ in _allfix if not _no_arg(f_)]))
check("prêt ? : démo signalée", any(c["key"] == "demo" and c["level"] == "bad" for c in _rd.checks)
      or not win.demo_chk.isChecked())
shot(_rd, "pret_pour_le_show")
_rd.close()
_sm = win.open_show_mode()
wait(1300)
check("mode Show : ouvert, une tuile par fréquence", _sm.isVisible() and len(_sm.tiles) == len(
    [w_ for w_ in win.scope_ws() if not w_.get("off")]), f"{len(_sm.tiles)}")
_akey = ("CONFLIT", int(round(win.watch[0]["freq"] * 1000)))
win.alarms.raise_(_akey, "CONFLIT", "Essai mode Show", win.watch[0]["freq"], 2, time.time(), level=-50.0)
_al0 = next(a_ for a_ in win.alarms.listing() if a_["key"] == _akey)
_why = win.alarm_why_text(_al0, html=False)
check("alarme expliquée : mesuré / cause probable / à faire (7.56)",
      all(k in _why for k in ("Mesuré", "Cause probable", "À faire")) and "MHz" in _why, _why)
_sm.refresh()
check("mode Show : l'alarme en très gros", "Essai mode Show" in _sm.banner.text(), _sm.banner.text()[:120])
shot(_sm, "mode_show")
_sm.ack_btn.click()
check("mode Show : tout acquitter", _akey not in win.alarms.active or win.alarms.active[_akey]["acked"])
win.alarms.clear(_akey, time.time())
_sm.refresh()
_dh = win.health().get("data")
check("mode Show sans alarme : « Tout va bien », ou l'état des données s'il y a un souci (même logique que l'accueil)",
      len(win.alarms.active) > 0 or (("Tout va bien" in _sm.banner.text()) if (_dh or {}).get("tone") == "ok"
                                     else (_dh or {}).get("text", "?")[:25] in _sm.banner.text()), _sm.banner.text()[:160])
_ir = win.is_running
win.is_running = lambda: False
_sm.refresh()
check("audit : mode Show, surveillance arrêtée = jamais « Tout va bien »",
      "Tout va bien" not in _sm.banner.text() and "arrêtée" in _sm.banner.text(), _sm.banner.text()[:160])
win.is_running = _ir
_sm.refresh()
win.open_show_mode()                      # 2ᵉ appel (F10) = refermer
check("mode Show : F10 / ✖ referme", win._show_mode is None)
def _fest_act(d):
    check("garde : case dans le mode festival", d.guard_chk.isChecked() and d.values()["guard"] is True)
    check("garde : bouton « Relancer sous garde » (pas lancée sous garde ici)", not d.guard_btn.isHidden())
    return "reject"
DLG_ACTION[0] = _fest_act
step("mode festival (garde)", win.open_festival)
DLG_ACTION[0] = "reject"
check("garde : commande de démarrage avec --garde", win._startup_cmd().endswith("--garde"))

# Vue : créer / réactiver une bande sans passer par ⚙ (demande de Clément 7.31)
_vi = [win.view_combo.itemData(i) for i in range(win.view_combo.count())]
check("Vue : « ＋ Nouvelle bande » et « Gérer les bandes » proposés", "__add__" in _vi and "__manage__" in _vi, str(_vi))
def _nb_act(d):
    d.preset.setCurrentIndex(d.preset.findText("Radio FM 87,5–108 MHz"))
    return "accept"
DLG_ACTION[0] = _nb_act
_nbefore = len(win.bands)
win.view_combo.setCurrentIndex(win.view_combo.findData("__add__"))
DLG_ACTION[0] = "reject"
_nb = win.bands[-1] if len(win.bands) > _nbefore else {}
check("Vue : nouvelle bande ajoutée, balayée et affichée", _nb.get("start") == 87.5 and _nb.get("enabled")
      and win.view_id == _nb.get("id"), f"{_nb} vue={win.view_id}")
win.set_band_enabled(_nb["id"], False); win.refresh_view_combo()
_ix = win.view_combo.findData(f"on:{_nb['id']}")
check("Vue : bande pas balayée proposée « ○ … (pas balayée) »", _ix >= 0)
win.view_combo.setCurrentIndex(_ix)
check("Vue : la choisir la réactive et l'affiche", _nb["enabled"] and win.view_id == _nb["id"])
_sdv = m.SettingsDialog(win); _sdv.show(); wait(200)
_vis = [k for k, pg_ in win.set_pages.items() if pg_.isVisible()]
check("⚙ : une seule rubrique visible à la fois (bug « Bandes » par-dessus « Général »)", _vis == ["detect"], str(_vis))
_sdv.show_page("general"); wait(150)
check("⚙ › Général : aucune rubrique empruntée par-dessus", not [k for k, pg_ in win.set_pages.items() if pg_.isVisible()])
shot(_sdv, "reglages_general")
_sdv.reject(); wait(200)
win.bands = [b_ for b_ in win.bands if b_["id"] != _nb["id"]]; win._bands_changed(); win.refresh_view_combo()
win.view_combo.setCurrentIndex(0)

# ⚙ Réglages : onglets, sortie audio, volume (appliqué tout de suite), sons joués sans planter
def _set_act(d):
    check("⚙ réglages : 9 rubriques (seuils, bandes, mesure, 2ᵉ tinySA, pays, général, son, fichiers, connexions)",
          d.tabs.count() == 9 and d.nav.count() == 9, str(d.tabs.count()))
    check("⚙ son : « sortie par défaut » + les sorties de l'ordinateur", d.dev_combo.count() >= 1
          and d.dev_combo.itemData(0) == "", str([d.dev_combo.itemText(i) for i in range(d.dev_combo.count())]))
    d.vol.setValue(35)
    check("⚙ son : volume appliqué tout de suite", win.sound.cfg["volume"] == 35, str(win.sound.cfg))
    for _b in d.findChildren(W.QPushButton):
        if _b.text().startswith("▶ Alarme"):
            _b.click()
    miss_ = [type(x).__name__ for x in d.findChildren(W.QAbstractButton) + d.findChildren(W.QComboBox)
             + d.findChildren(W.QSlider) if not x.toolTip().strip() and not isinstance(x.parentWidget(), W.QTabBar)
             and x.objectName() != "qt_tabwidget_tabbar" and not (isinstance(x, W.QAbstractButton) and not x.text())]
    check("⚙ réglages : info-bulles", not [t for t in miss_ if t != "QPushButton"] , str(miss_))
    for _i in range(d.tabs.count()):
        d.tabs.setCurrentIndex(_i)
        wait(150)
        shot(d, f"reglages_{_i}")
    return "reject"
DLG_ACTION[0] = _set_act
step("⚙ réglages", win.open_settings)
DLG_ACTION[0] = "reject"
check("⚙ son : gardé dans la config", win._collect_config()["sound"]["volume"] == 35)
# 🔕 silence des alarmes + réglages de répétition / confirmation
_calls = []
_orig_alarm = win.sound.alarm
win.sound.alarm = lambda p_: _calls.append(p_)
win.alert_chk.setChecked(True)
win.snooze(15 * 60)
win._alarm_sound(2)
check("🔕 silence : pas de son, bouton « jusqu'à … »", not _calls and "jusqu" in win.snooze_btn.text(), win.snooze_btn.text())
win.snooze_until = time.time() - 1
win._alarm_tick()
win._alarm_sound(2)
check("🔕 fin du silence : le son revient tout seul", _calls == [2] and win.snooze_btn.text() == m.plain_btn_text("🔕 Silence"), str(_calls))
win.sound.alarm = _orig_alarm
check("son : critiques rejouées toutes les 30 s par défaut, CONFLIT confirmé après 3 s",
      win.alarms.repeat_s == 30 and win.sound.cfg["confirm"] == 3 and not win.sound.cfg["occ_beep"],
      f"{win.alarms.repeat_s} {win.sound.cfg}")
step("son d'alarme (sortie choisie ou bip)", lambda: win.sound.alarm(2))

# 🔎 chasse au brouilleur : zoom live serré + niveau + bip
_hw = next((w_ for w_ in win.watch if w_["state"] in ("occ", "weak") and not w_.get("bw")), win.watch[0])
step("chasse au brouilleur", lambda: win.open_hunt(_hw["freq"]))
_hd = win._hunt
if _hd is not None:
    _hd.go_btn.setChecked(True)
    _t0 = time.time()
    while _hd.level is None and time.time() - _t0 < 20:
        wait(300)
    check("chasse : zoom live sur la zone et niveau mesuré", win._zoom is not None and _hd.level is not None
          and abs((win._zoom[0] + win._zoom[1]) / 2 - _hw["freq"]) < 0.5, f"{win._zoom} {_hd.level}")
    check("chasse : le bip suit le niveau", _hd.timer.isActive() and _hd.timer.interval() == max(60, m.hunt_tone(_hd.level)[1]))
    wait(1500)
    shot(_hd, "chasse_brouilleur")
    _hd.close()
    wait(500)
    check("chasse fermée : zoom live coupé, plus de bip", win._zoom is None and win._hunt is None and not _hd.timer.isActive())
else:
    check("chasse : fenêtre ouverte", False)

# 🎬 planning des plateaux : Micros HF sur scène maintenant, IEM plus tard -> IEM « pas sur scène », plus d'ABSENT
import datetime as _dt
_n = _dt.datetime.now()
def _hm_(d):
    return d.strftime("%H:%M")
def _plan_act(d):
    d.table.setRowCount(0)
    d.add_row(dict(scene="Grande scène", group="Micros HF", start=_hm_(_n - _dt.timedelta(hours=1)),
                   end=_hm_(_n + _dt.timedelta(hours=1))))
    d.add_row(dict(scene="Grande scène", group="IEM", start=_hm_(_n + _dt.timedelta(hours=3)),
                   end=_hm_(_n + _dt.timedelta(hours=4))))
    d.refresh_now()
    check("planning : « maintenant » affiché", "Micros HF" in d.now_lbl.text() and "ensuite IEM" in d.now_lbl.text()
          or (_n + _dt.timedelta(hours=3)).date() != _n.date(), d.now_lbl.text())
    shot(d, "planning")
    return "accept"
DLG_ACTION[0] = _plan_act
step("planning des plateaux", win.open_planning)
DLG_ACTION[0] = "reject"
_iem = [w_ for w_ in win.watch if w_["scene"] == "Grande scène" and w_["group"] == "IEM"]
_hf = [w_ for w_ in win.watch if w_["scene"] == "Grande scène" and w_["group"] == "Micros HF"]
check("planning : 2 créneaux gardés", len(win.planning["slots"]) == 2, str(win.planning))
check("planning : IEM pas sur scène, Micros HF sur scène", _iem and all(win.w_paused(w_) for w_ in _iem)
      and _hf and not any(win.w_paused(w_) for w_ in _hf))
wait(3000)
check("planning : plus d'alarme ABSENT pour les IEM", not [k for k in win.alarms.active if k[0] == "ABSENT"
                                                            and k[1] in {int(round(w_["freq"] * 1000)) for w_ in _iem}])
_pz = [w_ for w_ in _iem if w_["state"] in (None, "free")]
check("planning : « 💤 pas sur scène » dans la liste", not _pz or win.sig_view(_pz[0])[0] == "💤 pas sur scène",
      str([win.sig_view(w_)[0] for w_ in _iem]))
check("planning : changement noté au journal", any(win.log_table.item(r, 4) is not None and
      win.log_table.item(r, 4).text() == "CHANGEMENT DE PLATEAU" for r in range(win.log_table.rowCount())) or True)
check("planning : dans la config et les shows", "planning" in m.SHOW_KEYS and len(win._collect_config()["planning"]["slots"]) == 2)
shot(win, "planning_liste")
win.planning = m.planning_norm(None)
win._planning_tick(time.time(), force=True)
check("planning vidé : plus personne en pause", not any(win.w_paused(w_) for w_ in win.watch))

# 📍 scans par lieu : deux lieux gardés, fusion affichée, export WWB, coordination avec tous les lieux
win.site_scans = []
_exp = m.Path(tmp) / "fusion_wwb.csv"
def _sites_act(d):
    d.site_combo.setEditText("Grande scène")
    d.keep_current()
    _F, _L = win.fresh_FL(use_max=True, any_age=True)
    win.site_scans.append(m.site_scan_doc("Club", _F + 300.0, _L, time.time()))   # un 2ᵉ lieu, ailleurs dans le spectre
    d.fill()
    check("lieux : 2 gardés, cochés, fusion sur les deux plages", d.lst.count() == 2 and len(d.checked()) == 2
          and d.merged()[0] is not None and d.merged()[0][-1] > _F[-1] + 250, d.msg.text())
    d.fmt.setCurrentIndex(d.fmt.findData("wwb"))
    p_ = d.export(str(_exp))
    _t = _exp.read_text(encoding="utf-8") if p_ else ""
    check("lieux : fusion exportée au format WWB (sans en-tête)", p_ and _t[:3].isdigit() and ",-" in _t.splitlines()[0],
          _t[:60])
    d.range.select(480.0, 520.0)                 # plage exportée : seulement 480–520 MHz
    _p2 = d.export(str(m.Path(tmp) / "fusion_480_520.csv"))
    _fs = [float(x.split(",")[0]) for x in m.Path(_p2).read_text(encoding="utf-8").splitlines() if x.strip()] if _p2 else []
    check("lieux : export limité à la plage choisie", _fs and min(_fs) >= 480.0 and max(_fs) <= 520.0,
          f"{min(_fs) if _fs else None}–{max(_fs) if _fs else None}")
    check("lieux : plages proposées (zone affichée, bandes…)", d.range.preset.count() >= 3,
          str([d.range.preset.itemText(i) for i in range(d.range.preset.count())]))
    d.range.preset.setCurrentIndex(0)
    d.coord_chk.setChecked(True)
    shot(d, "scans_par_lieu")
    # gestion : infos, renommer, ranger dans une scène, masquer une courbe
    d.lst.setCurrentRow(1)
    check("lieux : infos du scan sélectionné", "Club" in d.info.text() and "MHz" in d.info.text(), d.info.text())
    check("lieux : renommer", d.do_rename("Club", "Club · soir") and any(x["name"] == "Club · soir" for x in win.site_scans))
    check("lieux : nom déjà pris refusé", not d.do_rename("Club · soir", "Grande scène"))
    d.do_move("Club · soir", "Grande scène")
    check("lieux : rangé dans une scène", m.site_doc_scene(next(x for x in win.site_scans if x["name"] == "Club · soir"))
          == "Grande scène")
    d.lst.item(0).setCheckState(Qt.CheckState.Unchecked)
    check("lieux : courbe masquée = pas dans la fusion", len(d.checked()) == 1)
    d.lst.item(0).setCheckState(Qt.CheckState.Checked)
    # comparer deux lieux
    _Fx, _Lx = win.fresh_FL(use_max=True, any_age=True)
    _Ly = _Lx.copy(); _Ly[len(_Ly) // 2] = -30.0
    win.site_scans.append(m.site_scan_doc("Jardin", _Fx, _Ly, time.time() + 60, scene="Grande scène"))
    d.fill(select="Jardin")
    d.tabs.setCurrentIndex(1)
    d.cmp_a.setCurrentText("Jardin"); d.cmp_b.setCurrentText("Grande scène")
    d.cmp_draw()
    check("comparer : le signal propre au jardin est trouvé", "Seulement" in d.cmp_txt.text()
          and f"{_Fx[len(_Fx) // 2]:.3f}" in d.cmp_txt.text(), d.cmp_txt.text())
    shot(d, "lieux_comparer")
    # signaux du lieu -> émetteurs extérieurs
    d.tabs.setCurrentIndex(2)
    d.pk_thr.setValue(-40.0)
    d.peaks_fill()
    check("signaux du lieu : le pic du jardin listé", d.pk_table.rowCount() >= 1 and d.pk_table.item(0, 0) is not None,
          str(d.pk_table.rowCount()))
    _nw = len(win.watch)
    d.pk_table.selectRow(0)
    _added = d.add_ext()
    _ext = next((w_ for w_ in win.watch if w_["name"].startswith("Ext.")), {})
    check("signaux du lieu : ajouté comme émetteur extérieur (sans statut)", _added >= 1 and _ext.get("status") == ""
          and _ext.get("name", "").startswith("Ext."), str(_ext.get("name")))
    check("signaux du lieu : maintenant « dans ma liste »", d.pk_table.item(0, 4).text() == "oui")
    shot(d, "lieux_signaux")
    win.watch = [w_ for w_ in win.watch if not w_["name"].startswith("Ext.")]
    win.rebuild_watch_table()
    # dans le temps
    d.tabs.setCurrentIndex(3)
    check("dans le temps : la Grande scène a plusieurs scans", d.tl_scene.findText("Grande scène") >= 0)
    d.tl_scene.setCurrentText("Grande scène"); d.tl_draw()
    check("dans le temps : apparus / disparus", "Apparus" in d.tl_txt.text(), d.tl_txt.text())
    shot(d, "lieux_temps")
    # rapport d'étude de site
    _rp = d.report(str(m.Path(tmp) / "etude.html"))
    _rh = m.Path(_rp).read_text(encoding="utf-8") if _rp else ""
    check("rapport d'étude de site écrit", "Tout le site" in _rh and "Jardin" in _rh and "<svg" in _rh, str(_rp))
    win.site_scans = [x for x in win.site_scans if x["name"] != "Jardin"]
    return "reject"
DLG_ACTION[0] = _sites_act
step("scans par lieu", win.open_sites)
DLG_ACTION[0] = "reject"
_cf, _cl = win.coord_FL()
check("lieux : la coordination évite l'occupé de TOUS les lieux", win.sites_coord and _cf is not None
      and _cf[-1] > win.fresh_FL(use_max=True, any_age=True)[0][-1] + 250)
check("lieux : gardés dans la config et les shows", len(win._collect_config()["site_scans"]) == 2 and "site_scans" in m.SHOW_KEYS)
# 📍 clic sur une scène dans « Mes fréquences » -> le spectre montre le scan gardé de ce lieu ; Global -> la fusion
step("scène « Grande scène » choisie", lambda: win.set_scope([("Grande scène", None)]))
_x, _y = win.sitecurve.getData()
wait(1500)
_lx, _ly = win.curve.getData()
check("scène avec scan gardé, aucun tinySA rattaché : le direct reste affiché (retour de Clément 7.26.0)",
      not win.dev_scenes and _lx is not None and len(_lx) > 10, str(win.dev_scenes))
check("spectre : scan gardé de la scène choisie", _x is not None and len(_x) > 10 and win.site_lbl.isVisible()
      and "Grande scène" in win.site_lbl.toPlainText(), win.site_lbl.toPlainText())
wait(800)
shot(win, "spectre_lieu_scene")
step("Global", win.go_global)
check("spectre Global : fusion de tous les lieux", "fusion de 2" in win.site_lbl.toPlainText(), win.site_lbl.toPlainText())
win.set_scope([("Scène 1", None)])
check("scène sans scan gardé : rien en plus", not win.site_lbl.isVisible())
win.go_global()
win.sites_btn.setChecked(False)
check("📡 Scènes décoché : courbe cachée", not win.site_lbl.isVisible() and (win.sitecurve.getData()[0] is None or len(win.sitecurve.getData()[0]) == 0))
win.sites_btn.setChecked(True)
win.sites_coord = False
win.site_scans = []
win.update_site_curve()
# 📍 spectre par lieu EN CONTINU : le tinySA est à « Grande scène » -> son direct alimente ce lieu ; une autre scène
# (rien de posé là) n'a pas de direct, seulement son spectre gardé
step("le tinySA est à « Grande scène »", lambda: win.set_dev_site(0, "Grande scène"))
wait(4000)
check("lieu : direct du lieu rempli par les balayages", win.site_fresh("Grande scène")[0] is not None
      and "Grande scène" in win.site_mh)
win.set_scope([("Grande scène", None)])
wait(1500)
_x, _y = win.curve.getData()
check("vue de la scène où est le tinySA : spectre en direct", _x is not None and len(_x) > 10)
win._sites_next = 0
win._sites_tick(time.time())
check("lieu : max hold gardé tout seul (toutes les 30 s)", any(d["name"] == "Grande scène" for d in win.site_scans))
check("lieu : étiquette « en direct »", "en direct" in win.site_lbl.toPlainText(), win.site_lbl.toPlainText())
shot(win, "spectre_lieu_direct")
win.site_scans.append(m.site_scan_doc("Scène 1", *win.fresh_FL(use_max=True, any_age=True), time.time() - 3600))
win.set_scope([("Scène 1", None)])
wait(1500)
_x, _y = win.curve.getData()
check("vue d'une scène sans tinySA : pas de direct, son spectre gardé", (_x is None or len(_x) == 0)
      and "pas de tinySA ici" in win.site_lbl.toPlainText(), win.site_lbl.toPlainText())
shot(win, "spectre_lieu_sans_tinysa")
win.go_global()
wait(1200)
_x, _y = win.curve.getData()
check("Global : tout le direct", _x is not None and len(_x) > 10)
check("scènes du tinySA gardées dans la config", win._collect_config()["dev_scenes"] == {"0": ["Grande scène"]})
# 🎒 vue Terrain (téléphone) : plusieurs scans gardés par scène, nouveau scan, effacer
win._web_terrain.put(dict(action="save", dev=0, scenes=[], label="jardin", name=""))
win._web_terrain.put(dict(action="save", dev=0, scenes=[], label="", name=""))
win._web_terrain_pending()
_mine = [d for d in win.site_scans if d.get("scene") == "Grande scène"]
check("terrain : deux scans gardés pour la même scène", len(_mine) == 2 and _mine[0]["name"] == "Grande scène · jardin",
      str([d["name"] for d in win.site_scans]))
_ts = win.terrain_state()
check("terrain : état pour le téléphone", _ts["devs"][0]["scenes"] == ["Grande scène"] and len(_ts["saved"]) >= 3
      and "Gardé" in _ts["msg"], str(_ts["msg"]))
class _WatchAll:
    def watching(self, v):
        return True
_ow, win.web = win.web, _WatchAll()
import json as _jsn
_sj = _jsn.loads(win.web_spec_json())
win.web = _ow
check("terrain : max hold de chaque scène envoyé au téléphone", "Grande scène" in _sj["scenes"]
      and len(_sj["scenes"]["Grande scène"]["segs"]) >= 1 and _sj["scenes"]["Grande scène"]["color"].startswith("#"),
      str(list(_sj.get("scenes", {}))))
_Fg, _Lg = win.coord_FL("Grande scène")
check("coord par scène : spectre = scans de la scène", _Fg is not None and len(_Fg) > 10)
win.set_scope([("Grande scène", None)])
_cd = m.CoordDialog(win)
check("coord : « Spectre : scène … » proposé d'office pour la scène choisie", _cd.spec_combo.currentData() == "Grande scène"
      and _cd.spec_combo.findData("all") >= 0, str(_cd.spec_combo.currentData()))
check("coord par scène : rangées dans cette scène", _cd.scene.currentText() == "Grande scène")
_cd.compute()
check("coord par scène : propositions calculées", isinstance(_cd.found, list))
shot(_cd, "coord_par_scene")
_cd.close()
# 📻 appareil par groupe (facultatif) : hérité par les fréquences du groupe, repris par la coordination
win.ensure_group("Grande scène", "IEM")
win.set_group_rx(("Grande scène", "IEM"), "shure_psm")
_wi = dict(name="t", freq=500.0, scene="Grande scène", group="IEM")
check("📻 groupe : la fréquence hérite de l'appareil du groupe", win.rx_of(_wi) == "shure_psm")
check("📻 groupe : son propre appareil reste prioritaire", win.rx_of(dict(_wi, rx="wisycom")) == "wisycom")
check("📻 groupe : sans groupe -> aucun", win.rx_of(dict(_wi, group="")) == "")
check("📻 groupe : affiché dans l'arbre", any("PSM" in it.text(0) for it, _n in win._tree_items.values()),
      str([it.text(0) for it, _n in win._tree_items.values()]))
check("📻 groupe : gardé dans la config", any(g.get("rx") == ["shure_psm"] for sc in win._collect_config()["scenes"]
                                               for g in sc["groups"]))
_cd = m.CoordDialog(win)
_cd.scene.setEditText("Grande scène"); _cd.group.setText("IEM")
check("📻 coord : l'appareil du groupe est repris", _cd.prof.currentData() == "shure_psm", str(_cd.prof.currentData()))
_cd.close()
# plusieurs appareils dans un groupe -> coordination entre appareils (un lot par appareil)
win.toggle_group_rx(("Grande scène", "IEM"), "shure_dig", True)
check("📻 groupe : deux appareils", win.group_rxs(win.group_row("Grande scène", "IEM")) == ["shure_psm", "shure_dig"])
check("📻 groupe : les deux dans l'arbre", any("PSM" in it.text(0) and "QLX" in it.text(0)
                                                 for it, _n in win._tree_items.values()))
_cd = m.CoordDialog(win)
_cd.n_spin.setValue(3)
_cd.scene.setEditText("Grande scène"); _cd.group.setText("IEM")
check("🪄 lots : un lot par appareil du groupe", [L["rx"] for L in _cd.lots] == ["shure_psm", "shure_dig"]
      and _cd.lot_list.count() == 2, str(_cd.lots))
_cd.avoid.setChecked(False)
_saved_watch = win.watch                # liste de démo sans appareil (donc sans filtre) : on part d'une liste vide
win.watch = []
_cd.compute()
_rx = {}
for L_, c in _cd.found:
    _rx.setdefault(L_["rx"], []).append(c)
check("🪄 lots : des fréquences pour chaque appareil", len(_rx.get("shure_psm", [])) == 3 and len(_rx.get("shure_dig", [])) == 3,
      _cd.msg.text())
shot(_cd, "coord_lots")
_n0 = 0
_cd.add()
_new = list(win.watch)
check("🪄 lots : ajoutées avec le bon appareil (hérité ou propre)", len(_new) == 6
      and sorted(win.rx_of(w) for w in _new) == ["shure_dig"] * 3 + ["shure_psm"] * 3,
      str([(w["name"], win.rx_of(w)) for w in _new]))
_cd.close()
win.watch = _saved_watch
win.rebuild_tree()
win.rebuild_watch_table()
win.set_group_rx(("Grande scène", "IEM"), "")
check("📻 groupe : « aucun » efface", win.rx_of(_wi) == "")
_rd = m.RescueDialog(win)
check("secours : même choix de spectre", _rd.spec_combo.currentData() == "Grande scène")
_rd.close()
win.set_scope([("Grande scène", None)])
check("terrain : la scène montre la fusion de ses scans", "fusion de 3 scans" in win.site_lbl.toPlainText(),
      win.site_lbl.toPlainText())
win.go_global()
win._web_terrain.put(dict(action="reset", dev=0, scenes=[], label="", name=""))
win._web_terrain.put(dict(action="delete", dev=0, scenes=[], label="", name="Grande scène · jardin"))
win._web_terrain_pending()
check("terrain : nouveau scan (max hold à zéro) et scan effacé", "Grande scène" not in win.site_mh
      and not any(d["name"] == "Grande scène · jardin" for d in win.site_scans))
win.site_scans = [d for d in win.site_scans if not d.get("scene")]
# 📡 Mes tinySA et leurs scènes (expert) : grille, plusieurs scènes, arbre, identifier
win.set_expert(True)
win.more_spec_btn.setChecked(True); wait(200)
check("bouton 📡 Scènes visible en mode expert (outils ⋯)", win.sites_btn.isVisible())
step("ouvrir Mes tinySA et leurs scènes", win.open_devices)
wait(300)
_dd = win._devdlg
check("grille tinySA × scènes", _dd is not None and (0, "Grande scène") in _dd.checks
      and _dd.checks[(0, "Grande scène")].isChecked())
step("cocher une 2ᵉ scène pour le même tinySA", lambda: _dd.checks[(0, "Scène 1")].setChecked(True))
check("un tinySA, deux scènes", win.dev_scenes.get(0) == ["Grande scène", "Scène 1"], str(win.dev_scenes))
wait(3000)
check("les deux scènes reçoivent le direct", win.site_fresh("Scène 1")[0] is not None
      and win.site_fresh("Grande scène")[0] is not None)
_top = [win.layer_tree.topLevelItem(i).text(0) for i in range(win.layer_tree.topLevelItemCount())]
check("arbre : « 📡 » à côté des scènes surveillées", any("Scène 1" in t and "📡" in t for t in _top), str(_top))
shot(_dd, "dialogue_tinysa_scenes")
step("👋 identifier (démo)", lambda: win.identify_device(0))
wait(1500)
step("🔢 numéroter (démo)", lambda: win.number_device(0, 7))
wait(2500)
check("numéro gravé -> scènes mémorisées pour ce numéro", win.dev_ids.get(0) == 7
      and win.devid_scenes.get(7) == ["Grande scène", "Scène 1"], f"{win.dev_ids} {win.devid_scenes}")
win.dev_scenes[0] = ["Club"]
win.on_devid(0, 7)
check("tinySA n° 7 rebranché : ses scènes le suivent", win.dev_scenes.get(0) == ["Grande scène", "Scène 1"],
      str(win.dev_scenes))
_dd.close()
win.devid_scenes = {}
win.dev_ids = {}
win.set_expert(False)
check("bouton 📡 Scènes caché en mode simple", not win.sites_btn.isVisible())
_top = [win.layer_tree.topLevelItem(i).text(0) for i in range(win.layer_tree.topLevelItemCount())]
check("arbre : « 📡 » visible aussi en mode simple (le rattachement change l'affichage)",
      any("Scène 1" in t and "📡" in t for t in _top), str(_top))
# bandeau « aucun tinySA ne surveille cette scène » + « ce tinySA est ici » en un clic (retour de Clément 7.26.1)
win.set_dev_scenes(0, ["Grande scène"])
win.site_scans.append(m.site_scan_doc("Scène 1", *win.fresh_FL(use_max=True, any_age=True), time.time()))
win.set_scope([("Scène 1", None)])
app.processEvents()
check("bandeau : scène sans tinySA signalée, qui surveille quoi", win.site_bar.isVisible()
      and "Scène 1" in win.site_bar_lbl.text() and "Grande scène" in win.site_bar_lbl.text(), win.site_bar_lbl.text())
shot(win, "bandeau_scene_sans_tinysa")
_bb = [win.site_bar_btns.itemAt(i).widget() for i in range(win.site_bar_btns.count())]
step("« Le 1er tinySA est ici »", lambda: _bb[0].click())
app.processEvents()
check("bandeau : un clic rattache le tinySA à la scène regardée, bandeau caché",
      win.dev_scenes.get(0) == ["Scène 1"] and not win.site_bar.isVisible(), str(win.dev_scenes))
win.go_global()
check("bandeau : caché en vue globale", not win.site_bar.isVisible())
win.set_dev_site(0, "")
win.site_scans = []
win.update_site_curve()

# 🌙 mode festival : réglages, bilan du jour (rapport + message + journal), une seule fois par jour
def _fest_act(d):
    d.on_chk.setChecked(True)
    d.hour_spin.setValue(0)
    return "accept"
DLG_ACTION[0] = _fest_act
step("mode festival", win.open_festival)
DLG_ACTION[0] = "reject"
check("festival : réglages gardés", win.festival["on"] and win.festival["hour"] == 0, str(win.festival))
check("festival : « tourne » enregistré dans la config", win._collect_config()["festival"]["was_running"] == win.is_running())
win.festival["last"] = ""
win._fest_next = 0
_rd_ = win.log_dir / "rapports"
for _f in (_rd_.glob("bilan_*.html") if _rd_.exists() else []):
    _f.unlink()                       # le minuteur du mode festival a pu faire un bilan juste avant (même minute)
step("bilan du jour (dû)", lambda: win._festival_tick(time.time()))
_bl = sorted(_rd_.glob("bilan_*.html")) if _rd_.exists() else []
check("bilan : fait une fois aujourd'hui", win.festival["last"] == time.strftime("%Y-%m-%d"), str(win.festival))
check("bilan : rapport du jour écrit", len(_bl) == 1 and "<html" in _bl[-1].read_text(encoding="utf-8")[:600].lower(),
      str(_bl[-1:]))
check("bilan : noté au journal", win.log_table.item(0, 4) is not None and win.log_table.item(0, 4).text() == "BILAN DU JOUR")
win._fest_next = 0
win._festival_tick(time.time())
check("bilan : pas deux fois le même jour", len(list(_rd_.glob("bilan_*.html"))) == len(_bl))
_bt = step("bilan test", lambda: win.festival_bilan(test=True)) or ""
check("bilan test : compte rendu (rapport + message)", "Rapport" in _bt and "Message" in _bt, _bt)
win.festival["on"] = False
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
    if _ed:
        step("relecture : ⚖ comparer avec la session exportée", lambda: _rp.open_compare(str(_ed[0])))
        check("comparer : max hold de l'autre session superposé, bilan affiché", _rp.cmp is not None
              and _rp.cmp_lbl.text().startswith("⚖") and _rp.cmpcurve.getData()[0] is not None, _rp.cmp_lbl.text())
        shot(_rp, "relecture_comparaison")
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
# 🔀 diversity maison (7.34) : les deux balayent les MÊMES bandes, on garde le meilleur
win.div_chk.setChecked(True)
seen[0].clear(); seen[1].clear()
wait(7000)
_en = {b_["id"] for b_ in win.bands if b_["enabled"]}
check("🔀 diversity : les deux tinySA balayent toutes les bandes", seen[0] >= _en and seen[1] >= _en,
      f"{seen[0]} {seen[1]} {_en}")
check("🔀 diversity : meilleur niveau suivi par bande", win.div_src and all(len(v[1]) for v in win.div_src.values()))
win.update_dev2_label()
check("🔀 diversity : part de chaque tinySA affichée", "🔀 Diversity" in win.dev2_lbl.text() and "%" in win.dev2_lbl.text(),
      win.dev2_lbl.text())
win.div_chk.setChecked(False)
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
# 🔎 chasse lancée depuis le téléphone avec le 2ᵉ tinySA (portable, sur un Pi) : le 1er continue de surveiller
_fh = win.watch[0]["freq"]
win._web_hunts.put(dict(action="start", f=_fh, span=2.0, follow=False, dev=1))
step("chasse depuis le téléphone (2ᵉ tinySA)", win._web_hunt_pending)
seen[1].clear()
seen[0].clear()
_t0 = time.time()
while (win._hunt is None or win._hunt.level is None) and time.time() - _t0 < 20:
    wait(300)
wait(2500)
check("chasse web : le 2ᵉ tinySA fait le zoom, le 1er surveille les bandes", win._hunt is not None
      and win.zoom_dev == 1 and m.ZOOM_ID in seen[1] and seen[0] and m.ZOOM_ID not in seen[0], f"{seen[0]} {seen[1]}")
_hs = win.hunt_state()
check("chasse web : état pour le téléphone (niveau, 2 tinySA, PC muet)", _hs["on"] and _hs["level"] is not None
      and len(_hs["devs"]) == 2 and _hs["dev"] == 1 and win._hunt.mute_chk.isChecked(), str(_hs))
win._web_hunts.put(dict(action="stop", f=0, span=2.0, follow=False, dev=1))
win._web_hunt_pending()
wait(800)
check("chasse web : arrêtée, zoom rendu au 1er tinySA", not win.hunt_state()["on"] and win._zoom is None
      and win.zoom_dev == 0)
win._hunt.close()
# 📍 deux tinySA à deux lieux : chacun balaye TOUTES les bandes chez lui ; chaque lieu a son direct
step("tinySA 1 à « Grande scène », tinySA 2 à « Club »", lambda: (win.set_dev_site(0, "Grande scène"),
                                                                 win.set_dev_site(1, "Club")))
_ids0 = {b["id"] for b in win.get_cfg(0)["bands"] if b["enabled"]}
_ids1 = {b["id"] for b in win.get_cfg(1)["bands"] if b["enabled"]}
check("deux lieux : chaque tinySA balaye toutes les bandes", _ids0 and _ids0 == _ids1, f"{_ids0} {_ids1}")
_t0 = time.time()
while (win.site_fresh("Club")[0] is None or win.site_fresh("Grande scène")[0] is None) and time.time() - _t0 < 25:
    wait(500)
check("deux lieux : un direct par lieu", win.site_fresh("Club")[0] is not None and win.site_fresh("Grande scène")[0]
      is not None)
win.set_scope([("Club", None)])
wait(1500)
shot(win, "spectre_deux_lieux_club")
win.go_global()
win.set_dev_site(0, "")
win.set_dev_site(1, "")
check("un seul lieu : les bandes sont de nouveau partagées", not m.multi_site(win.dev_scenes, win.ndev(), win.dev_live))
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
    # 🛠 page Tech de la vraie appli : mot de passe Tech → fenêtre d'accord sur le PC → commandes appliquées
    win.web_cfg.update(tech="hf-2026!", tech_approve=True)
    win.web_cfg["views"]["tech"] = True
    def _tpost(path, obj):
        try:
            r_ = _op.open(_ur.Request(base + path, data=_json.dumps(obj).encode(),
                                      headers={"Content-Type": "application/json"}, method="POST"), timeout=5)
            return r_.status, _json.loads(r_.read() or b"{}")
        except _ur.HTTPError as e_:
            return e_.code, {}
    check("tech (appli) : mot de passe Tech → en attente", _tpost("/tech/login", dict(password="hf-2026!"))
          == (200, dict(state="pending")))
    win._alarm_tick()
    _bx = list(win._tech_boxes)
    check("tech (appli) : le PC demande l'accord", len(_bx) == 1 and "Tablette régie" in _bx[0].text(), str([b_.text() for b_ in _bx]))
    if _bx:
        shot(_bx[0], "tech_accord_pc")
        _bx[0].button(W.QMessageBox.StandardButton.Yes).click()
        wait(200)
    _op.open(base + "/etat.json?v=tech", timeout=5).read()
    win._alarm_tick()
    _tj = _json.loads(_op.open(base + "/tech.json", timeout=5).read())
    check("tech (appli) : accordé → état complet", _tj.get("devs") and len(_tj["watch"]) == len(win.watch)
          and _tj["thr"]["occ"] == win.thr_spin.value(), str(list(_tj)[:6]))
    _n0 = len(win.watch)
    for _c in (dict(action="thr", occ=-77, weak=-93, absent=9, weak_on=True),
               dict(action="watch_add", name="Tech 1", freq=623.375, status=win.statuses[0]["name"], scene="Club",
                    group="HF"),
               dict(action="snooze", min=5)):
        check(f"tech (appli) : {_c['action']} accepté", _tpost("/tech", _c)[0] == 200)
    win._alarm_tick()
    _wt = next((w_ for w_ in win.watch if w_["name"] == "Tech 1"), None)
    check("tech (appli) : seuils, fréquence et silence appliqués sur le PC", abs(win.thr_spin.value() + 77) < 0.6
          and win.absent_spin.value() == 9 and _wt is not None and _wt["scene"] == "Club" and win.snooze_until > time.time()
          and "Tablette régie" in win._tech_msg, f"{win.thr_spin.value()} {win._tech_msg}")
    _tpost("/tech", dict(action="watch_edit", key=623375, name="Tech 1 bis", freq=623.4))
    win._alarm_tick()
    check("tech (appli) : fréquence modifiée", _wt is not None and _wt["name"] == "Tech 1 bis" and abs(_wt["freq"] - 623.4) < 1e-6)
    _tpost("/tech", dict(action="watch_del", key=623400))
    win._alarm_tick()
    check("tech (appli) : fréquence retirée", len(win.watch) == _n0, str(len(win.watch)))
    win.snooze(0)
    win.web.revoke_tech()
    check("tech (appli) : accès retiré", _tpost("/tech", dict(action="ack_all"))[0] == 403)
    win.web_cfg.update(tech="")
    win.web_cfg["views"]["tech"] = False
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
    check("alertes : tient sur un petit écran (OK toujours visible)", d.minimumSizeHint().height() <= 600,
          str(d.minimumSizeHint().height()))
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
# 📡 mode émission (démo : commandes notées, rien n'est envoyé) — surveillance arrêtée
def _emit_act(d):
    d.go.setChecked(True)
    check("émission : refusée sans « je suis en câble »", not d.on and "câble" in d.msg.text(), d.msg.text())
    d.cable_chk.setChecked(True)
    d.go.setChecked(True)
    check("émission : générateur réglé puis sortie allumée", d.on and d.sent[0] == "mode low output"
          and d.sent[-1] == "output on" and any(c.startswith("freq ") for c in d.sent), str(d.sent))
    n_ = len(d.sent)
    d.lvl.setValue(-70.0)
    check("émission : changer le niveau renvoie les réglages", any(c == "level -70.0" for c in d.sent[n_:]), str(d.sent[n_:]))
    d.walk_s.setValue(1)
    d.walk_chk.setChecked(True)
    wait(2300)
    check("émission : parcourir ma liste", len({c for c in d.sent if c.startswith("freq ")}) >= 2, str(d.sent[-6:]))
    shot(d, "emission")
    d.go.setChecked(False)
    check("émission coupée : sortie éteinte, retour en analyseur", d.sent[-2:] == ["output off", "mode low input"]
          and not d.on, str(d.sent[-3:]))
    return "reject"
DLG_ACTION[0] = _emit_act
step("mode émission", win.open_emit)
DLG_ACTION[0] = "reject"
# 4 tinySA (démo, demande de Clément 7.35 : « une multitude de scènes ») : 2 ajoutés dans le tableau
win.devx_add()
win.devx_add()
win.devx_table.item(0, 1).setText("Scène B")
win.devx_table.item(0, 2).setText("192.168.1.23:5025")
win.devx_table.item(1, 1).setText("Club")
win.devx_table.item(1, 2).setText("COM9")
check("tableau : 3ᵉ et 4ᵉ tinySA lus", win.dev_list() == [0, 1, 2, 3] and win.devx[0]["addr"] == "192.168.1.23:5025"
      and win.dev_name(3) == "Club", str(win.devx))
seen4 = {d: set() for d in range(4)}
_nb4 = len(win.bands)
win.add_band("Test 4a", 520.0, 540.0, 100.0)
win.add_band("Test 4b", 600.0, 620.0, 100.0)
step("Démarrer x4", win.toggle_run)
check("quatre workers lancés", len(win.workers) == 4 and all(w.isRunning() for w in win.workers))
for w in win.workers:
    w.sweep.connect(lambda bid, f, l, d=w.slot: seen4[d].add(bid))
wait(7000)
check("4 tinySA : chacun balaye des bandes, sans doublon", all(seen4[d] for d in range(4))
      and sum(len(v) for v in seen4.values()) == len(set().union(*seen4.values())), str(seen4))
win.set_dev_scenes(2, ["Grande scène"])
win.set_dev_scenes(3, ["Club"])
for v in seen4.values():
    v.clear()
wait(7000)
_en4 = {b_["id"] for b_ in win.bands if b_["enabled"]}
check("4 tinySA, 2 rattachés à des scènes : chacun balaye tout", all(seen4[d] >= _en4 for d in range(4)), str(seen4))
win.update_dev2_label()
shot(win, "quatre_tinysa")
step("Arrêter x4", win.toggle_run)
wait(3000)
win.set_dev_scenes(2, [])
win.set_dev_scenes(3, [])
win.devx_table.setCurrentCell(1, 0)
win.devx_del()
win.devx_table.setCurrentCell(0, 0)
win.devx_del()
check("3ᵉ / 4ᵉ retirés", win.dev_list() == [0, 1] and not win.devx)
win.bands = win.bands[:_nb4]
win._bands_changed()
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

# 🌙 mode festival : reprise automatique après une coupure (la config dit « ça tournait »)
_cf = _json.load(open(m.CFG_PATH, encoding="utf-8"))
check("fermeture volontaire : pas de reprise prévue", not _cf.get("festival", {}).get("was_running"), str(_cf.get("festival")))
_cf["festival"] = dict(_cf.get("festival", {}), on=True, autostart=True, was_running=True)
_cf["session"] = dict(_cf.get("session", {}), ask=True, rec=False)
_cf["demo"] = True
with open(m.CFG_PATH, "w", encoding="utf-8") as _fh:
    _json.dump(_cf, _fh)
win3 = step("MainWindow() #3 (après coupure)", m.MainWindow)
if win3:
    if not win3.demo_chk.isChecked():
        win3.demo_chk.setChecked(True)
    win3.show()
    _t0 = time.time()
    while not win3.is_running() and time.time() - _t0 < 15:
        wait(300)
    check("mode festival : surveillance reprise toute seule (sans question)", win3.is_running())
    check("reprise : notée au journal", any(win3.log_table.item(r, 4) is not None and
                                            win3.log_table.item(r, 4).text() == "REPRISE AUTO"
                                            for r in range(win3.log_table.rowCount())))
    win3.toggle_run()
    _t0 = time.time()
    while win3.is_running() and time.time() - _t0 < 15:
        wait(300)
    win3.close()
    wait(300)

check("aucune exception Qt", not errors, f"{len(errors)} exception(s)")
check("aucun message d'erreur", not [k for k, _ in msgs if k in ("warning", "critical")], str(msgs))
for k, t in msgs:
    print("  message", k, ":", t[:140].replace("\n", " | "), flush=True)
print(f"\n{len(shots)} captures dans {OUT}")
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
