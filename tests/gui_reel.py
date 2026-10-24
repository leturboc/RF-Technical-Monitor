"""Lance la VRAIE appli PySide6 (sans écran, QT_QPA_PLATFORM=offscreen) en mode démo, ouvre panneaux et
dialogues, capture des PNG et relève les exceptions Qt. Complète les smoke_test* (faux Qt).

    python tests/gui_reel.py [dossier_captures]        (défaut : tests/captures, ignoré par git)

Sous Linux il faut PySide6 + libEGL/libGL (apt install libegl1 libgl1 libxkbcommon0 fonts-noto-color-emoji).
Ne remplace pas un essai sur Windows : sons, vrai port série, double écran et rendu natif ne sont pas testés."""
import os, sys, tempfile, traceback, importlib.util, time
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
        act(self)
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
step("Démarrer", win.toggle_run)
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
vis = {t: b.isVisible() and b.visibleRegion().boundingRect().width() >= b.width() - 2
       for t, b in (("Démarrer", win.start_btn), ("🔔", win.alarm_btn))}
vis["Shows / Plus"] = all(a.isVisible() for a in win.cmd_bar.findChildren(W.QPushButton) if a.text() in ("🎪 Shows", "☰ Plus"))
check("1280×720 : boutons du haut visibles en entier", all(vis.values()), str(vis))
win.resize(1700, 980); wait(800)

# dialogues modaux
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

# dialogues non modaux
step("open_intermod", win.open_intermod); wait(1500)
if win._im_dlg: shot(win._im_dlg, "intermod")
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
    check("page web : état réel", len(js["rows"]) == len(win.watch) and js["running"], str(js.get("running")))
    check("page web : page HTML", b"TinySA Monitor" in _ur.urlopen(base + "/", timeout=5).read())
    win.web_cfg["on"] = False
    step("web off", win.apply_web)
    check("page web arrêtée", win.web is None)
DLG_ACTION[0] = "reject"
step("dialogue alertes", win.open_alerts)
step("Arrêter x2", win.toggle_run)
wait(3000)
check("arrêt des deux", not win.is_running())
win.dev2_chk.setChecked(False)
step("open_relay", win.open_relay)
wait(600)
shot(win._relay_win, "relais")
win._relay_win.close()
step("close", win.close); wait(500)
print("config écrite:", os.path.exists(m.CFG_PATH), flush=True)

# relance : config relue + état des docks restauré
win2 = step("MainWindow() #2", m.MainWindow)
if win2:
    win2.show(); wait(800); shot(win2, "relance")
    print("relance: fréquences", len(win2.watch), "scènes", len(win2.scenes), flush=True)
    win2.close()

check("aucune exception Qt", not errors, f"{len(errors)} exception(s)")
check("aucun message d'erreur", not [k for k, _ in msgs if k in ("warning", "critical")], str(msgs))
for k, t in msgs:
    print("  message", k, ":", t[:140].replace("\n", " | "), flush=True)
print(f"\n{len(shots)} captures dans {OUT}")
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
