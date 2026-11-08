"""Lance la VRAIE appli en anglais (TSM_LANG=en, sans écran), mode démo, ouvre menus et dialogues et relève tout
texte visible qui ressemble encore à du français (accents, mots courants). Affiche ÉCHECS: 0 si rien ne reste.

    python tests/gui_en.py [dossier_captures]     (défaut : tests/captures_en)"""
import os, sys, tempfile, traceback, importlib.util, re
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["TSM_LANG"] = "en"
tmp = tempfile.mkdtemp(prefix="tsm_en_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "captures_en")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, ".."))
errors = []
def hook(t, v, tb):
    s = "".join(traceback.format_exception(t, v, tb))
    errors.append(s)
    print("!!! EXCEPTION\n" + s, flush=True)
sys.excepthook = hook
spec = importlib.util.spec_from_file_location("tsm", os.path.join(HERE, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
from PySide6 import QtWidgets as W, QtCore, QtGui
app = W.QApplication(sys.argv)
if sys.platform != "win32":
    app.setFont(QtGui.QFont("DejaVu Sans", 9))
m.install_gc_main_thread(app, 100)

FR = re.compile(r"[éèêàùçôîûœÉÈÀÇ]|\b(le|la|les|des|du|une|pour|avec|sans|dans|sur|est|pas|ou|aux|cette|ce|ces|"
                r"fréquences?|appareil|bande|réglages?|libre|occupée?s?|fenêtre|écran|liste|niveau|seuil|"
                r"Ajouter|Supprimer|Enregistrer|Ouvrir|Fermer|Annuler|Démarrer|Arrêter|Afficher|Masquer|Liste|Spectre|Alarmes|Mur|muet|faible|Seuil|Nom|Statut|Groupe|Couleur|Mots)\b")
OK_WORDS = re.compile(r"Sennheiser|Wisycom|Shure|EazyRF|Français|tinySA|Spectera|Sémaphore")
import lang_en
FRS = lang_en.EXACT                       # un texte affiché tel quel en français alors qu'il a sa traduction
try:
    import lang_en_v8
    FRS = {**FRS, **lang_en_v8.EXACT}
except ImportError:
    pass
found = {}
def look(txt, where):
    if not isinstance(txt, str) or not txt.strip():
        return
    for line in txt.split("\n"):
        t = re.sub(r"<[^>]+>", " ", line).replace("Clément", "").replace("Français", "")
        st = t.strip()
        if (FR.search(t) and not OK_WORDS.fullmatch(st)) or (FRS.get(st, st) != st):
            found.setdefault(line.strip()[:400], where)

def scan(w, where):
    objs = [w] + w.findChildren(QtCore.QObject)
    for o in objs:
        try:
            _scan1(o, where)
        except RuntimeError:          # menu reconstruit par aboutToShow : ses anciennes actions sont détruites
            pass

def _scan1(o, where):
    if True:
        if isinstance(o, W.QWidget):
            look(o.toolTip(), where + ":tip")
            look(o.windowTitle(), where + ":title")
        for attr in ("text", "title", "placeholderText", "suffix", "prefix", "specialValueText"):
            f = getattr(o, attr, None)
            if callable(f) and not isinstance(o, (W.QLineEdit, W.QPlainTextEdit, W.QTextEdit)) or attr == "placeholderText":
                try:
                    look(f(), f"{where}:{type(o).__name__}.{attr}")
                except Exception:
                    pass
        if isinstance(o, QtGui.QAction):
            look(o.text(), where + ":action"); look(o.toolTip(), where + ":action-tip")
        if isinstance(o, W.QMenu):
            o.aboutToShow.emit()
            for a in o.actions():
                look(a.text(), where + ":menu"); look(a.toolTip(), where + ":menu-tip")
        if isinstance(o, W.QComboBox):
            for i in range(o.count()):
                look(o.itemText(i), where + ":combo")
                look(o.itemData(i, QtCore.Qt.ItemDataRole.ToolTipRole), where + ":combo-tip")
        if isinstance(o, W.QTabWidget):
            for i in range(o.count()):
                look(o.tabText(i), where + ":tab")
        if isinstance(o, W.QTableWidget):
            for c in range(o.columnCount()):
                h = o.horizontalHeaderItem(c)
                h and look(h.text(), where + ":head")
            for r in range(min(o.rowCount(), 60)):
                for c in range(o.columnCount()):
                    it = o.item(r, c)
                    if it:
                        look(it.text(), where + ":cell"); look(it.toolTip(), where + ":cell-tip")
        if isinstance(o, W.QTreeWidget):
            it = W.QTreeWidgetItemIterator(o)
            while it.value():
                for c in range(o.columnCount()):
                    look(it.value().text(c), where + ":tree")
                it += 1
        if isinstance(o, W.QListWidget):
            for i in range(o.count()):
                look(o.item(i).text(), where + ":list")
        if isinstance(o, W.QTextEdit):
            look(o.toPlainText(), where + ":textedit")

def wait(ms):
    loop = QtCore.QEventLoop(); QtCore.QTimer.singleShot(ms, loop.quit); loop.exec()

msgs = []
def fake_box(kind):
    def f(parent, title, text, *a, **k):
        look(title, "msgbox-title"); look(text, "msgbox:" + kind)
        return W.QMessageBox.StandardButton.No
    return staticmethod(f)
for k in ("warning", "information", "critical", "question"):
    setattr(W.QMessageBox, k, fake_box(k))
W.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
W.QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
W.QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
W.QInputDialog.getDouble = staticmethod(lambda *a, **k: (0, False))
W.QInputDialog.getItem = staticmethod(lambda *a, **k: ("", False))
W.QInputDialog.getMultiLineText = staticmethod(lambda *a, **k: ("", False))
n_shot = [0]
def fake_exec(self):
    self.show(); wait(250)
    scan(self, type(self).__name__)
    self.grab().save(os.path.join(OUT, f"{n_shot[0]:02d}_{type(self).__name__}.png")); n_shot[0] += 1
    self.reject()
    return 0
W.QDialog.exec = fake_exec
assert m.read_language() == "en"
assert m.install_language("en")
W.QMenu.exec = lambda self, *a, **k: (scan(self, "popup"), None)[1]

win = m.MainWindow()
win.log_dir = m.Path(tmp) / "journaux"
win.resize(1600, 950); win.show(); wait(500)
win.ensure_group("Main stage", "Mics")
for i, f in enumerate([470.2, 474.4, 480.3, 503.5, 525.25, 552.4]):
    win._append_watch(f"HF {i+1}", f, status="En service" if i < 4 else "Libre", scene="Main stage", group="Mics")
win.rebuild_tree(); win.rebuild_watch_table()
win.demo_chk.setChecked(True)
win.toggle_run(); wait(300)             # 1er démarrage : la question « enregistrer la session ? » (scannée puis refusée)
win.session_cfg.update(ask=False, rec=False)
win.set_level("simple")
win.toggle_run(); wait(6000)
win.grab().save(os.path.join(OUT, "main.png"))
win.grab().save(os.path.join(OUT, "90_mode_simple.png"))          # captures du manuel anglais (make_manual --shots)
scan(win, "main")
win.more_spec_btn.setChecked(True); wait(300)
scan(win.spec_more, "main-more"); win.grab().save(os.path.join(OUT, "91_spectre_plus_outils.png"))
win.more_spec_btn.setChecked(False)
# ⚙ Réglages : chaque rubrique (dont les pages empruntées à la fenêtre principale)
_sd = m.SettingsDialog(win); _sd.show(); wait(300)
for _k in _sd.keys:
    _sd.show_page(_k); wait(120); scan(_sd, f"Settings-{_k}")
    if _k == "detect":
        _sd.grab().save(os.path.join(OUT, "92_reglages_seuils.png"))
_sd.reject(); wait(200)
win.open_wall(); wait(800)
win.dock_wall.grab().save(os.path.join(OUT, "93_mur_en.png"))
# 🎓 tutos (chaque étape) et lexique
win.start_tour(); wait(200); scan(win._tour_chooser, "TourChooser"); win._tour_chooser.close()
for _k in m.TOUR_KEYS:
    win.start_tour(_k); wait(100)
    for _i in range(len(win._tour.steps)):
        win._tour.go(_i); scan(win._tour, f"tour-{_k}-{_i}")
    win._tour.grab().save(os.path.join(OUT, f"tour_{_k}.png"))
    win._tour.close()
win.open_glossary(); wait(200); scan(win._glossary, "Glossary")
look(win._glossary.view.toPlainText(), "Glossary-text"); win._glossary.close()
for name in ("edit_labels", "edit_statuses", "edit_colors", "edit_plan", "add_watch_dialog", "edit_vocab",
             "open_intermod", "open_rescue", "open_guide", "open_replay", "open_wall", "open_plan_check", "open_diag",
             "show_about", "open_linecheck", "open_scan_convert", "open_alerts", "edit_show_info", "open_show_dialog",
             "make_report", "export_by_scene", "open_sites", "open_coord", "open_net_profiles", "pick_wall", "open_relay", "add_block_dialog",
             "open_festival", "open_ready", "open_show_mode",
             "open_sdr", "open_listen", "open_realtime"):          # les 3 derniers : V8 (SDR) seulement
    fn = getattr(win, name, None)
    if fn is None:
        continue
    try:
        fn(); wait(600)
    except Exception:
        hook(*sys.exc_info())
for tl in app.topLevelWidgets():
    if tl.isVisible() and tl is not win:
        scan(tl, type(tl).__name__)
        tl.grab().save(os.path.join(OUT, f"{n_shot[0]:02d}_{type(tl).__name__}.png")); n_shot[0] += 1
win.toggle_run(); wait(1500)
for k, v in sorted(found.items(), key=lambda x: x[1]):
    print(f"FR   [{v}] {k}")
print(f"textes encore en français : {len(found)} · exceptions : {len(errors)}")
lm = [a.text() for a in win.lang_menu.actions()]
ok_menu = lm == ["Français", "English"] and win.lang_menu.actions()[1].isChecked() and win.lang == "en"
print(("OK  " if ok_menu else "FAIL"), "menu des langues :", lm)
man = win.manual_path()
ok_man = man is not None and man.name == "manual_en.html"
print(("OK  " if ok_man else "FAIL"), "manuel anglais :", man)
n = len(found) + len(errors) + (not ok_menu) + (not ok_man)
print(f"ÉCHECS: {n}")
win.close()
sys.exit(1 if n else 0)
