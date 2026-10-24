"""Lance la VRAIE appli PySide6 (sans écran, QT_QPA_PLATFORM=offscreen) en mode démo, ouvre panneaux et
dialogues, capture des PNG et relève les exceptions Qt. Complète les smoke_test* (faux Qt).

    python tests/gui_reel.py [dossier_captures]        (défaut : tests/captures, ignoré par git)

Sous Linux il faut PySide6 + libEGL/libGL (apt install libegl1 libgl1 libxkbcommon0 fonts-noto-color-emoji).
Ne remplace pas un essai sur Windows : sons, vrai port série, double écran et rendu natif ne sont pas testés."""
import os, sys, tempfile, traceback, importlib.util, time
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
# police d'un vrai bureau : Segoe UI 9 pt sous Windows (le mode offscreen ne la fournit pas tout seul)
app.setFont(QtGui.QFont("Segoe UI" if sys.platform == "win32" else "DejaVu Sans", 9))
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

step("zoom sur ligne 0", lambda: win.zoom_on(0)); wait(4000); shot(win, "zoom_live")
step("toggle_zoom off", lambda: win.toggle_zoom(False)); wait(1000)

# dispositions
for name in ("layout_analyzer", "layout_monitor", "layout_dual", "layout_standard"):
    step(name, getattr(win, name)); wait(1200); shot(win, name)

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
check("hauteur mini ≤ 720 px", win.minimumSizeHint().height() <= 720, str(win.minimumSizeHint()))
win.resize(1280, 720); wait(1200); shot(win, "taille_1280x720")
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

step("Arrêter", win.toggle_run); wait(2500)
print("worker running après arrêt:", win.worker.isRunning() if win.worker else None, flush=True)
shot(win, "arrete")
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
print(f"\n{len(shots)} captures dans {OUT}")
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
