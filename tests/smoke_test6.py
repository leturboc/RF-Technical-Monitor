"""Shows (faux Qt) : enregistrer, rouvrir l'an d'après sans toucher aux préférences, courbe de référence du lieu,
ancien profil .json, nouveau show, récents, titre, config."""
import sys, os, json, tempfile, importlib.util, traceback
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
tmp = tempfile.mkdtemp(prefix="tsm6_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
os.environ["USERPROFILE"] = tmp
import numpy as np
import fakeqt
QtWidgets, QtCore, QtGui, pg = fakeqt.install()
spec = importlib.util.spec_from_file_location("tsm", os.path.join(SP, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
fails = 0


def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra)


def step(label, fn):
    global fails
    try:
        return fn()
    except Exception:
        fails += 1
        print("FAIL (exception)", label)
        traceback.print_exc()
        return None


W = m.QtWidgets
answers = {"q": W.QMessageBox.StandardButton.Yes}
msgs = []
W.QMessageBox.question = staticmethod(lambda *a, **k: answers["q"])
W.QMessageBox.warning = staticmethod(lambda p, t, x, *a, **k: msgs.append(x))
saved = []
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved.pop(0) if saved else "", ""))
info = {"meta": None}


class FakeInfo:
    def __init__(self, parent, meta, title=""):
        self.meta = dict(meta)

    def exec(self):
        return info["meta"] is not None

    def values(self):
        return dict(info["meta"])


m.ShowInfoDialog = FakeInfo
m.SHOW_DIR = m.Path(tmp) / "Shows"
win = step("MainWindow()", m.MainWindow)
if win is None:
    sys.exit(1)
win.apply_web = lambda: None

# ------------------------------------------------------------- un show
win.ensure_group("Grande scène", "Micros HF")
win.set_prio(("Grande scène", "Micros HF"), 2)
win._append_watch("HF 1", 500.0, status="En service", scene="Grande scène", group="Micros HF")
win._append_watch("Spectera ch 38", 610.0, status="En service", bw=8.0)
win.thr_spin.setValue(-77)
win.dev1_name.setText("Plateau")
win._set_ref([(np.linspace(470, 694, 50), np.full(50, -101.0))])
win.rebuild_watch_table()
info["meta"] = dict(name="Fest", venue="Grande scène", date_from="2025-07-17", date_to="2025-07-20", notes="câble FOH")
p1 = str(m.SHOW_DIR / "2025 Fest - Grande scène.tsashow")
saved[:] = [p1]
step("save_show", win.save_show)
check("fichier show écrit", os.path.exists(p1), str(os.listdir(tmp)))
check("pas de fichier temporaire oublié", not os.path.exists(p1 + ".tmp"))
doc = json.loads(open(p1, encoding="utf-8").read())
check("show : 2 fréquences, bloc, priorité, seuil, noms, référence",
      len(doc["show"]["watch"]) == 2 and doc["show"]["watch"][1]["bw"] == 8.0
      and doc["show"]["scenes"][0]["groups"][0]["prio"] == 2 and doc["show"]["thr"] == -77
      and doc["show"]["dev_names"][0] == "Plateau" and len(doc["ref"]) == 1, str(doc["show"].keys()))
check("show : pas de préférences", not any(k in doc["show"] for k in ("theme", "web", "dev2", "markers", "log_dir")))
check("récents", win.recent_shows == [p1])
# Ctrl+S : réenregistre au même endroit sans redemander
win.thr_spin.setValue(-78)
step("save_show (2e fois)", win.save_show)
check("Ctrl+S : même fichier, pas de dialogue", json.loads(open(p1, encoding="utf-8").read())["show"]["thr"] == -78
      and not saved)

# ------------------------------------------------------------- l'année suivante : autres préférences, show rouvert
win.theme["ui_base"] = "#abcdef"
win.dev2_chk.setChecked(True)
win.dev2_addr.setEditText("10.0.0.9:5025")
win.log_dir = m.Path(tmp) / "journaux2026"
win.watch.clear()
win.scenes.clear()
win._set_ref([])
win.thr_spin.setValue(-90)
step("open_show", lambda: win.open_show(p1))
ws = {w["name"]: w for w in win.watch}
check("rouvert : fréquences et bloc", set(ws) == {"HF 1", "Spectera ch 38"} and ws["Spectera ch 38"]["bw"] == 8.0)
check("rouvert : scène, groupe, priorité", win.freq_prio(ws["HF 1"]) == 2)
check("rouvert : seuil", win.thr_spin.value() == -78)
check("rouvert : courbe de référence du lieu", win._ref_F is not None and len(win._ref_F) == 50)
check("rouvert : préférences intactes (couleurs, 2e tinySA, journaux)",
      win.theme["ui_base"] == "#abcdef" and win.dev2["addr"] == "10.0.0.9:5025" and win.dev2["on"]
      and str(win.log_dir).endswith("journaux2026"), f'{win.theme["ui_base"]} {win.dev2} {win.log_dir}')
check("rouvert : infos du show", win.show_meta["name"] == "Fest" and win.show_meta["notes"] == "câble FOH")
answers["q"] = W.QMessageBox.StandardButton.No
win.watch.clear()
win.open_show(p1)
check("ouverture refusée : rien ne change", win.watch == [])
answers["q"] = W.QMessageBox.StandardButton.Yes
win.open_show(p1)
# « Enregistrer sous » : édition 2026
info["meta"] = dict(win.show_meta, date_from="2026-07-16", date_to="2026-07-19")
win.show_meta = info["meta"]
p2 = str(m.SHOW_DIR / "2026 Fest - Grande scène.tsashow")
saved[:] = [p2]
step("save_show as_new", lambda: win.save_show(as_new=True))
check("nouvelle édition à côté de l'ancienne", os.path.exists(p1) and os.path.exists(p2) and win.show_path == p2)
check("récents : plus récent en tête", win.recent_shows[:2] == [p2, p1], str(win.recent_shows))

# ------------------------------------------------------------- liste des shows (dialogue réel, faux Qt)
rows = []
dlg = step("ShowOpenDialog", lambda: m.ShowOpenDialog(win, [(m.SHOW_DIR, "*" + m.SHOW_EXT)]))
if dlg is not None:
    check("liste : 2 shows, le plus récent en tête", len(dlg.rows) == 2 and dlg.rows[0][1]["meta"]["date_from"] == "2026-07-16",
          str([r[1]["meta"]["date_from"] for r in dlg.rows]))

# ------------------------------------------------------------- ancien profil .json
oldp = os.path.join(tmp, "evenement.json")
cfg_old = win._collect_config(False)
cfg_old["watch"] = [dict(name="Vieux HF", freq=520.0, status="", thr=None, scene="", group="")]
cfg_old["theme"] = dict(cfg_old["theme"], ui_base="#000000")
open(oldp, "w", encoding="utf-8").write(json.dumps(cfg_old))
step("open ancien profil", lambda: win.open_show(oldp))
check("ancien profil : fréquences chargées, thème gardé", [w["name"] for w in win.watch] == ["Vieux HF"]
      and win.theme["ui_base"] == "#abcdef", win.theme["ui_base"])
check("ancien profil : sera enregistré en .tsashow (pas de chemin)", win.show_path == "" and win.show_meta["name"] == "evenement")
open(os.path.join(tmp, "nimporte.json"), "w").write('{"x": 1}')
msgs.clear()
win.open_show(os.path.join(tmp, "nimporte.json"))
check("fichier quelconque : message clair", msgs and "illisible" in msgs[-1], str(msgs))

# ------------------------------------------------------------- nouveau show
nb = len(win.bands)
info["meta"] = dict(name="Autre", venue="", date_from="2026-08-01", date_to="2026-08-01", notes="")
step("new_show", win.new_show)
check("nouveau show : liste vide, bandes gardées", win.watch == [] and win.scenes == [] and len(win.bands) == nb)
check("nouveau show : infos saisies, pas encore de fichier", win.show_meta["name"] == "Autre" and win.show_path == "")
info["meta"] = None
win.show_meta = {k: "" for k in m.SHOW_META}
saved[:] = []
step("save_show sans nom (annulé)", win.save_show)
check("sans nom : rien d'enregistré", win.show_path == "")

# ------------------------------------------------------------- config : show en cours et récents gardés
win.show_meta = dict(name="Fest", venue="", date_from="2026-07-16", date_to="", notes="")
win.show_path = p2
full = win._collect_config(True)
check("config : show en cours", full["show_meta"]["name"] == "Fest" and full["show_path"] == p2)
check("profil / show : pas de chemin de show", "show_path" not in win._collect_config(False))
win2 = step("MainWindow() #2", m.MainWindow)
win2.apply_web = lambda: None
step("apply startup", lambda: win2._apply_config(full, startup=True))
check("relance : show en cours et récents", win2.show_meta["name"] == "Fest" and win2.show_path == p2
      and win2.recent_shows[:1] == [p2])
step("menu shows", win2._build_show_menu)
acts = [a.text() for a in win2.show_menu.all_actions()]
check("menu : enregistrer le show nommé, récents", any("Enregistrer « Fest »" in t for t in acts)
      and any(t.startswith("2026 Fest") for t in acts), str(acts))

# ------------------------------------------------------------- config : écriture sûre, copie de secours
check("sauvegarde auto prévue", m.AUTOSAVE_MS <= 60_000 and hasattr(win, "_autosave"))
win.show_meta["name"] = "Sauvé 1"
check("_save_config 1", win._save_config() and m.CFG_PATH.exists())
win.show_meta["name"] = "Sauvé 2"
win._save_config()
check("copie de secours = version d'avant", json.loads(m.CFG_BAK.read_text(encoding="utf-8"))["show_meta"]["name"] == "Sauvé 1")
check("pas de fichier temporaire oublié", not m.CFG_PATH.with_suffix(".json.tmp").exists())
m.CFG_PATH.write_text('{"watch": [ {"name": "coupé en plein', encoding="utf-8")       # coupure pendant l'écriture
win3 = step("MainWindow() sur config abîmée", m.MainWindow)
check("config abîmée : copie de secours rechargée", win3 is not None and win3.show_meta["name"] == "Sauvé 1",
      str(win3 and win3.show_meta))
m.CFG_PATH.unlink()
m.CFG_BAK.unlink()
win4 = step("MainWindow() sans config", m.MainWindow)
check("sans config : démarrage normal", win4 is not None and win4.show_meta["name"] == "")

# ------------------------------------------------------------- journal de plantage
cl = os.path.join(tmp, "crash_test.log")
m.log_crash("erreur", "Traceback: boom", cl)
txt = open(cl, encoding="utf-8").read()
check("crash.log : horodaté, version, détail", m.APP_VER in txt and "boom" in txt and "=====" in txt)
m.CRASH_PATH = m.Path(tmp) / "crash.log"
fh = m.install_crash_log(None)
try:
    raise RuntimeError("erreur imprévue de test")
except RuntimeError:
    sys.excepthook(*sys.exc_info())
import threading as _th
t = _th.Thread(target=lambda: 1 / 0, name="fil-test")
t.start()
t.join()
txt = m.CRASH_PATH.read_text(encoding="utf-8")
check("erreur imprévue → crash.log", "erreur imprévue de test" in txt)
check("erreur dans un fil → crash.log", "fil-test" in txt and "ZeroDivisionError" in txt)
sys.excepthook = sys.__excepthook__
_th.excepthook = _th.__excepthook__
import faulthandler as _fh
_fh.disable()
if fh:
    fh.close()

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
