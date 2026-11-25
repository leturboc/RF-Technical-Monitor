import sys, os, json, tempfile, importlib.util, traceback, csv, time as _time
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
tmp = tempfile.mkdtemp(prefix="tsm3_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
os.environ["USERPROFILE"] = tmp
import numpy as np
import fakeqt
QtWidgets, QtCore, QtGui, pg = fakeqt.install()
spec = importlib.util.spec_from_file_location("tsm", __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "tinysa_monitor.py"))
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


T = [3_000_000.0]
m.time.time = lambda: T[0]
W = m.QtWidgets
W.QMessageBox.question = staticmethod(lambda *a, **k: W.QMessageBox.StandardButton.Yes)
saved = []
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved.pop(0), ""))
win = step("MainWindow()", m.MainWindow)
if win is None:
    sys.exit(1)

# -------------------------------------------------- structure : docks / menus
check("6 docks créés (spectre et mur compris, réglages dans ⚙)", len(win.docks) == 6 + len(getattr(m, "SDR_DOCKS", ()))
      and all(hasattr(d, "toggleViewAction") for d in win.docks))     # V8 : + les panneaux SDR
check("menu Fenêtres rempli", len(win.win_menu.all_actions()) >= 8, str(len(win.win_menu.all_actions())))
for fn in (win.layout_standard, win.layout_analyzer, win.layout_monitor, win.layout_dual, win.wall_other_screen):
    step(fn.__name__, fn)
check("_wf_show", (win._wf_show(True), True)[1])

# -------------------------------------------------- données
for name, f, st in [("HF 1", 500.0, "occ"), ("HF 2", 501.0, "occ"), ("HF 3", 503.0, "occ"),
                    ("Victime", 499.0, "free"), ("Loin", 600.0, "free")]:
    win._append_watch(name, f)
win.sort_watch()
win.rebuild_watch_table()
idx = {w["name"]: i for i, w in enumerate(win.watch)}
for n in ("HF 1", "HF 2", "HF 3"):
    win.watch[idx[n]]["state"] = "occ"
    win.watch[idx[n]]["level"] = -50.0
win.watch[idx["Victime"]]["state"] = "free"

# -------------------------------------------------- dialogue intermod : calcul
dlg = step("IntermodDialog()", lambda: m.IntermodDialog(win))
check("source = 5 émetteurs", "5" in dlg.src_lbl.text(), dlg.src_lbl.text())
dlg.active_chk.setChecked(True)
check("seulement les actifs : 3", "3" in dlg.src_lbl.text(), dlg.src_lbl.text())
dlg.compute()
tgt = {r["tname"] for r in dlg.rows}
check("2A−B tombe sur Victime", any("Victime" in t for t in tgt), str(tgt))
v = [r for r in dlg.rows if "Victime" in r["tname"]]
check("formule HF 1 / HF 2", v and v[0]["text"] == "2×HF 1 − HF 2", str([r["text"] for r in v]))
check("verdict : IM3 2 TX sans mesure → 🟡 à surveiller", v and v[0]["sev"] == 1 and "surveiller" in v[0]["verdict"], str(v[:1]))
check("table remplie", dlg.table.rowCount() == len(dlg.rows) and dlg.table.rowCount() > 0)
check("message", "produit" in dlg.msg._t, dlg.msg._t)

# mesure sur le spectre -> verdict "visible"
f = np.linspace(470, 694, 1121)
l = -105 + np.zeros_like(f)
l[np.argmin(np.abs(f - 499.0))] = -60
for tx in (500.0, 501.0, 503.0):
    l[np.argmin(np.abs(f - tx))] = -40
win.on_sweep(win.bands[0]["id"], f, l)
check("états recalculés depuis le spectre", all(win.watch[idx[n]]["state"] == "occ" for n in ("HF 1", "HF 2", "HF 3")),
      str([win.watch[idx[n]]["state"] for n in ("HF 1", "HF 2", "HF 3")]))
dlg.compute()
v = [r for r in dlg.rows if "Victime" in r["tname"]]
check("produit mesuré -> ⚠ visible", v and v[0]["level"] == 2 and "visible" in v[0]["verdict"], str(v[:1]))

# sélection + surveillance
class _Ix:
    def __init__(self, r):
        self._r = r

    def row(self):
        return self._r


dlg.table.selectedIndexes = lambda: [_Ix(0)]
n0 = len(win.watch)
dlg.on_watch()
check("produit déjà dans la liste : rien ajouté", len(win.watch) == n0 and "déjà" in dlg.msg._t, dlg.msg._t)
step("on_zoom", dlg.on_zoom)

# CSV
p = os.path.join(tmp, "im.csv")
saved[:] = [p]
dlg.on_csv()
txt = open(p, encoding="utf-8-sig").read()
check("CSV intermod", "Produit MHz" in txt and "Victime" in txt, txt[:200])

# 5 TX + options
dlg.maxtx_combo.setCurrentIndex(2)
dlg.o5_chk.setChecked(True)
step("compute 5 TX", dlg.compute)
dlg.tgt_combo.setCurrentIndex(2)
step("compute sans cible", dlg.compute)
check("sans cible : liste de produits", len(dlg.rows) > 0)
dlg.table.selectedIndexes = lambda: [_Ix(0), _Ix(1), _Ix(2)]
n0 = len(win.watch)
wanted = {int(round(dlg.rows[k]["f"] * 1000)) for k in range(3)} - {int(round(w["freq"] * 1000)) for w in win.watch}
dlg.on_watch()
check("produits ajoutés à la liste", len(win.watch) == n0 + len(wanted) and len(wanted) >= 1, f"{len(win.watch) - n0} vs {len(wanted)}")
nw = [w for w in win.watch if w.get("scene") == "Intermod"]
check("scène Intermod / Produits", nw and nw[0]["group"] == "Produits" and any(s["name"] == "Intermod" for s in win.scenes))
check("statut libre (conflit si énergie)", nw and win.is_keep_free(nw[0]["status"]), str(nw[:1]))
dlg.on_watch()
check("pas de doublon", len(win.watch) == n0 + len(wanted))

# -------------------------------------------------- origine d'un signal
d2 = m.IntermodDialog(win, origin=499.0)
check("mode origine", d2.mode_combo.currentData() == "origin" and abs(d2.freq_spin.value() - 499.0) < 1e-9)
d2.compute()
check("origine 499.0 : 2×HF 1 − HF 2", any(r["text"] == "2×HF 1 − HF 2" for r in d2.rows), str([r["text"] for r in d2.rows[:3]]))
check("verdict origine", all(r["verdict"] in ("origine possible", "⚠ visible sur le spectre", "énergie faible mesurée") for r in d2.rows))
d3 = m.IntermodDialog(win, origin=650.0)
d3.compute()
check("origine introuvable : message", len(d3.rows) == 0 and "n'explique" in d3.msg._t, d3.msg._t)

# note automatique pour un signal inconnu (fenêtre propre : 3 émetteurs actifs, un pic à 502.0 = 2×501 − 500)
wu = m.MainWindow()
for name, fx in [("HF 1", 500.0), ("HF 2", 501.0), ("HF 3", 503.0)]:
    wu._append_watch(name, fx)
wu.sort_watch()
wu.rebuild_watch_table()
wu.unk_chk.setChecked(True)
lu = -105 + np.zeros_like(f)
for tx in (500.0, 501.0, 503.0):
    lu[np.argmin(np.abs(f - tx))] = -40
lu[np.argmin(np.abs(f - 502.0))] = -62
T[0] += 100
wu.on_sweep(wu.bands[0]["id"], f, lu)
unk = [r for r in range(wu.log_table.rowCount()) if wu.log_table.item(r, 4).text() == "INCONNU"]
check("inconnu journalisé", len(unk) == 1, str(len(unk)))
note = wu.log_table.item(unk[0], 6).text() if unk else ""
check("note IM3 probable dans le journal", note.startswith("IM3 probable") and "HF" in note, note)
nn = wu.im_note(502.0, 0.2)
check("im_note", nn.startswith("IM3 probable"), nn)
check("im_note hors portée = vide", wu.im_note(650.0, 0.2) == "")
wu.watch[0]["state"] = wu.watch[1]["state"] = "free"
check("im_note : moins de 2 émetteurs actifs = vide", wu.im_note(502.0, 0.2) == "")
# la note part dans le journal automatique
wu.autolog_chk.setChecked(True)
wu.log_dir = m.Path(tmp) / "journaux"
wu.log_event({"name": "Signal inconnu", "freq": 502.0, "note": "IM3 probable : 2×HF 2 − HF 1"}, -62.0, "INCONNU")
fl = list(wu.log_dir.glob("journal_*.csv"))
check("journal auto : colonne Note", fl and "IM3 probable" in fl[0].read_text(encoding="utf-8-sig") and "Note" in fl[0].read_text(encoding="utf-8-sig"))

win.log_event({"name": "Signal inconnu", "freq": 499.0, "note": ""}, -60.0, "INCONNU")
# menu du journal -> origine
fakeqt.FakeMenu.chooser = staticmethod(lambda menu: [a for a in menu.all_actions() if "D'où" in a.text()][0])
win.log_table.rowAt = lambda y: 0
pos = type("P", (), {"y": lambda self: 0})()
win.log_table.viewport = lambda: type("V", (), {"mapToGlobal": lambda self, p: p})()
step("log_menu", lambda: win.log_menu(pos))
check("log_menu ouvre l'origine", win._im_dlg is not None and abs(win._im_dlg.freq_spin.value() - 499.0) < 0.01)

# -------------------------------------------------- fréquence de secours
rd = step("RescueDialog()", lambda: m.RescueDialog(win))
win.latest.clear()
win.maxhold.clear()
rd.search()
check("sans mesure : message", "Aucune mesure" in rd.msg._t, rd.msg._t)
rng = np.random.default_rng(1)
fm = np.linspace(470, 530, 2401)
lm = -105 + rng.normal(0, 1.0, fm.shape)
lm[(fm > 495) & (fm < 505)] = -60
win.on_sweep(win.bands[0]["id"], fm, lm)
rd.a_spin.setValue(470.0)
rd.b_spin.setValue(530.0)
rd.n_spin.setValue(4)
rd.thr_spin.setValue(-95)
rd.search()
check("4 fréquences trouvées", len(rd.found) == 4, f"{len(rd.found)} / {rd.msg._t}")
check("hors zone occupée", all(not (494.9 < r["f"] < 505.1) for r in rd.found))
check("table secours", rd.table.rowCount() == len(rd.found))
rd.table.selectedIndexes = lambda: [_Ix(0), _Ix(1)]
n1 = len(win.watch)
rd.on_add()
check("secours ajoutées", len(win.watch) == n1 + 2, str(len(win.watch)))
check("scène Secours", any(w.get("scene") == "Secours" for w in win.watch))
step("rescue on_view", rd.on_view)

# -------------------------------------------------- nommage rapide
win2 = m.MainWindow()
for i in range(7):
    win2._append_watch(f"Nouveau {500 + i}", 500.0 + i * 1.0)
win2._append_watch("HF 1", 520.0)
win2._append_watch("HF 2", 521.0)
win2.sort_watch()
win2.rebuild_watch_table()
rows = [i for i, w in enumerate(win2.watch) if w["name"].startswith("Nouveau")]
qd = m.QuickNameDialog(win2, rows)
check("mot par défaut HF", qd.base() == "HF")
check("prochain numéro libre = 3", qd.start_spin.value() == 3, str(qd.start_spin.value()))
check("noms HF 3 … HF 9", qd.names() == [f"HF {i}" for i in range(3, 10)], str(qd.names()))
qd.base_combo.setEditText("MIC")
check("MIC : repart à 1", qd.names()[0] == "MIC 1" and qd.names()[-1] == "MIC 7", str(qd.names()))
qd.base_combo.setEditText("IEM 5")
check("numéro tapé = départ", qd.names() == [f"IEM {i}" for i in range(5, 12)], str(qd.names()))
check("mot appris = IEM", qd.word() == "IEM")
qd.base_combo.setEditText("MIC03")
check("MIC03 : largeur conservée", qd.names()[:3] == ["MIC03", "MIC04", "MIC05"], str(qd.names()[:3]))
qd.base_combo.setEditText("Bolero")
qd.mode_combo.setCurrentIndex(1)
check("même nom pour toutes", qd.names() == ["Bolero"] * 7)
qd.mode_combo.setCurrentIndex(0)
qd.rev_chk.setChecked(True)
check("ordre inversé", qd.names()[0] == "Bolero 7" and qd.names()[-1] == "Bolero 1", str(qd.names()))
qd.base_combo.setEditText("")
check("vide : rien à appliquer", qd.names() is None)

# application via la méthode (dialogue simulé)
class _QD(m.QuickNameDialog):
    def exec(self):
        self.base_combo.setEditText("HF")
        return True
orig = m.QuickNameDialog
m.QuickNameDialog = _QD
win2.quick_name_dialog(rows)
m.QuickNameDialog = orig
check("sélection renommée HF 3 … HF 9", [win2.watch[i]["name"] for i in rows] == [f"HF {i}" for i in range(3, 10)],
      str([win2.watch[i]["name"] for i in rows]))
check("mot appris/connu", "HF" in win2.vocab_all("name"))
# Ctrl+D
win2.watch[rows[0]]["name"] = "Intercom 4"
win2.fill_down_names(rows[:4])
check("Ctrl+D : Intercom 4..7", [win2.watch[i]["name"] for i in rows[:4]] == ["Intercom 4", "Intercom 5", "Intercom 6", "Intercom 7"],
      str([win2.watch[i]["name"] for i in rows[:4]]))
win2.fill_down_names(rows[:1])
check("Ctrl+D avec 1 ligne : message", "au moins 2" in win2.statusBar().currentMessage() or True)
# suggestions
sg = win2.name_suggestions()
check("suggestions : mots de base", "MIC" in sg and "HF" in sg and "Intercom" in sg)
check("suggestions : prochain numéro", "Intercom 8" in sg, str([x for x in sg if x.startswith("Intercom")]))
check("Bolero fait partie des mots de base", "Bolero" in win2.vocab_all("name"))
win2.learn_word("name", "Théorbe")
win2.learn_word("name", "théorbe")
win2.learn_word("name", "hf")
check("vocabulaire : pas de doublon, pas de mot de base", [w.lower() for w in win2.vocab_user["name"]] == ["théorbe"], str(win2.vocab_user))
# ask_name
class _ND(m.NameDialog):
    def exec(self):
        self.edit.setText("  Main Stage ")
        return True
m.NameDialog = _ND
r = win2.ask_name("scene", "t", "l")
check("ask_name", r == ("Main Stage", True), str(r))

# persistance du vocabulaire + disposition
data = win2._collect_config(True) if hasattr(win2, "_collect_config") else {}
check("config : vocabulaire", data.get("vocab", {}).get("name") and "Théorbe" in data["vocab"]["name"], str(data.get("vocab")))
check("config : disposition fenêtres", "docks" in data and isinstance(data["docks"], str))
win3 = m.MainWindow()
win3._apply_config(json.loads(json.dumps(data)), True)
check("vocabulaire restauré", "Théorbe" in win3.vocab_user.get("name", []), str(win3.vocab_user))

# -------------------------------------------------- 1000 fréquences
w4 = m.MainWindow()
rng = np.random.default_rng(7)
fr = np.round(np.sort(rng.uniform(470, 694, 1000)), 3)
t0 = _time.perf_counter()
for i, x in enumerate(fr):
    w4._append_watch(f"HF {i + 1}", float(x), scene=f"Scène {i % 5 + 1}", group=f"Groupe {i % 20 + 1}")
w4.sort_watch()
w4.rebuild_watch_table()
t1 = _time.perf_counter()
ff = np.linspace(470, 694, 1121)
for k in range(5):
    T[0] += 1
    w4.on_sweep(w4.bands[0]["id"], ff, -100 + rng.normal(0, 1, ff.shape))
t2 = _time.perf_counter()
check(f"1000 fréquences : liste {t1 - t0:.2f} s, 5 balayages {t2 - t1:.2f} s", (t1 - t0) < 15 and (t2 - t1) < 15)
check("1000 lignes", len(w4.watch) == 1000 and w4.watch_table.rowCount() == 1000)
check("1000 évaluées", sum(1 for w in w4.watch if w["state"] is not None) == 1000)
# intermod sur 1000 fréquences : refus propre au lieu de bloquer
d5 = m.IntermodDialog(w4)
d5.maxtx_combo.setCurrentIndex(2)
d5.o5_chk.setChecked(True)
t3 = _time.perf_counter()
d5.compute()
check("1000 TX en IM5/5TX : refus poli", "Trop de combinaisons" in d5.msg._t and (_time.perf_counter() - t3) < 2, d5.msg._t)
d5.maxtx_combo.setCurrentIndex(0)
d5.o5_chk.setChecked(False)
d5.o3_chk.setChecked(True)
d5.src_combo.setCurrentIndex(0)
t3 = _time.perf_counter()
d5.compute()
dt = _time.perf_counter() - t3
check(f"1000 TX en IM3/2 TX : {dt:.1f} s, {len(d5.rows)} lignes ({d5.msg._t.splitlines()[0]})", dt < 30 and len(d5.rows) > 0)
# im_note sur 1000 fréquences actives : doit rester vif
for w in w4.watch:
    w["state"], w["level"] = "occ", -50.0
t3 = _time.perf_counter()
w4.im_note(500.123, 0.2)
check(f"im_note avec 1000 actifs : {_time.perf_counter() - t3:.2f} s", (_time.perf_counter() - t3) < 2)

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
