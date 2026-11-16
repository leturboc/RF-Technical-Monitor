import sys, os, json, tempfile, importlib.util, types, traceback, csv
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
tmp = tempfile.mkdtemp(prefix="tsm_")
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
m.OCC_LOG_S = 0      # anciens tests : occupation notée tout de suite (7.66.1 : seulement si elle dure)

fails = 0
def check(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra)

def step(label, fn):
    global fails
    try:
        r = fn()
        return r
    except Exception:
        fails += 1
        print("FAIL (exception)", label)
        traceback.print_exc()
        return None

T = [1_000_000.0]
m.time.time = lambda: T[0]

W = m.QtWidgets
W.QMessageBox.question = staticmethod(lambda *a, **k: W.QMessageBox.StandardButton.Yes)
saved_paths = []
def fake_save(*a, **k):
    return (saved_paths.pop(0), "")
W.QFileDialog.getSaveFileName = staticmethod(fake_save)
W.QFileDialog.getOpenFileName = staticmethod(fake_save)

win = step("MainWindow()", m.MainWindow)
check("fenêtre créée", win is not None)
if win is None:
    sys.exit(1)

check("plan FR chargé", len(win.plan) > 20 and len(win.tv) > 40, f"{len(win.plan)} {len(win.tv)}")
check("pays par défaut", win.country == "FR")
check("statuts: Libre = doit rester libre", win.is_keep_free("Libre") and not win.is_keep_free("Occupé"))

# --- fréquences surveillées
for name, f, st in [("Chant", 506.0, "Libre"), ("Basse", 520.25, "Occupé"), ("Guitare", 760.0, ""), ("IEM", 863.5, "")]:
    win._append_watch(name, f, st)
win.sort_watch()
win.rebuild_watch_table()
t = win.watch_table
check("tableau: 10 colonnes remplies", all(t.item(0, c) is not None for c in range(10)))
bands = {w["name"]: w["band"] for w in win.watch}
check("Spectre Chant = CH 25", bands["Chant"].startswith("CH 25"), bands["Chant"])
check("Spectre Guitare = 4G/5G 700", "700" in bands["Guitare"], bands["Guitare"])
check("Spectre IEM = micros HF 863", "863" in bands["IEM"] or "micros" in bands["IEM"].lower(), bands["IEM"])

# --- balayage simulé
b0 = win.bands[0]
f = np.linspace(470, 694, 1121)
rng = np.random.default_rng(1)
base = -100 + rng.normal(0, 1.0, f.shape)
def sweep(extra=None):
    l = base.copy()
    if extra:
        for fr, lv in extra:
            l[np.argmin(np.abs(f - fr))] = lv
    return f, l
T[0] += 10
step("on_sweep (calme)", lambda: win.on_sweep(b0["id"], *sweep()))
check("niveau mesuré", all(w["level"] is not None for w in win.watch if w["freq"] < 694))
check("tous libres", all(w["state"] == "free" for w in win.watch if w["freq"] < 694), str([w["state"] for w in win.watch]))
check("rien de signalé", win.log_table.rowCount() == 0)

T[0] += 10
step("on_sweep (signal sur Chant 'Libre')", lambda: win.on_sweep(b0["id"], *sweep([(506.0, -55.0), (520.25, -50.0)])))
chant = next(w for w in win.watch if w["name"] == "Chant")
basse = next(w for w in win.watch if w["name"] == "Basse")
check("Chant occupé", chant["state"] == "occ")
events = [win.log_table.item(r, 4).text() for r in range(win.log_table.rowCount())]
check("CONFLIT journalisé pour Chant", "CONFLIT" in events, str(events))
check("OCCUPÉ journalisé pour Basse", "OCCUPÉ" in events, str(events))
r_chant = win.watch.index(chant)
check("cellule Signal = CONFLIT", win.watch_table.item(r_chant, m.C_SIG).text() == m.CONFLICT_TEXT,
      win.watch_table.item(r_chant, m.C_SIG).text())
r_basse = win.watch.index(basse)
check("cellule Signal Basse = OCCUPÉ", win.watch_table.item(r_basse, m.C_SIG).text() == "OCCUPÉ")
check("compteur de conflits", "CONFLIT" in win.count_lbl.text(), win.count_lbl.text())
check("occupation calculée", chant["occw"].pct() is not None and chant["occw"].pct() > 0, str(chant["occw"].pct()))
check("colonne Occ. remplie", "%" in win.watch_table.item(r_chant, m.C_OCC).text(), win.watch_table.item(r_chant, m.C_OCC).text())

# journal auto
logs = list((m.LOG_DIR).glob("journal_*.csv"))
check("journal auto créé", len(logs) == 1, str(m.LOG_DIR))
if logs:
    rows = list(csv.reader(open(logs[0], encoding="utf-8-sig"), delimiter=";"))
    check("journal auto: en-tête + >=2 événements", rows[0][0] == "Date" and len(rows) >= 3, str(rows[:3]))
    check("journal auto: statut et spectre", any(r[5] == "CONFLIT" and r[6] == "Libre" and "CH 25" in r[9] for r in rows[1:]), str(rows))

# retour au calme -> libre
T[0] += 10
win.on_sweep(b0["id"], *sweep())
check("Chant libre à nouveau", chant["state"] == "free", chant["state"])

# seuil propre
chant["thr"] = -40.0
T[0] += 10
win.on_sweep(b0["id"], *sweep([(506.0, -55.0)]))
check("seuil propre -40 : -55 dBm n'est pas occupé", chant["state"] != "occ", chant["state"])
chant["thr"] = None

# édition cellule seuil
it = win.watch_table.item(r_chant, m.C_THR)
it.setText("-72,5")
win.on_watch_edit(it)
check("seuil édité par la cellule", chant["thr"] == -72.5, str(chant["thr"]))
it.setText("")
win.on_watch_edit(it)
check("seuil effacé par cellule vide", chant["thr"] is None)

# référence
T[0] += 10
win.on_sweep(b0["id"], *sweep())          # spectre calme
step("capture_ref", lambda: win.capture_ref("live"))
check("référence en mémoire + fichier", win._ref_F is not None and m.REF_PATH.exists())
win.ref_chk.setChecked(True)
win.ref_margin.setValue(8.0)
T[0] += 10
win.on_sweep(b0["id"], *sweep([(506.0, -95.0)]))     # +5 dB au-dessus de la réf. mais sous la marge de 8
check("seuil relatif: +5 dB < marge -> pas occupé", chant["state"] != "occ", chant["state"])
T[0] += 10
win.on_sweep(b0["id"], *sweep([(506.0, -85.0)]))     # +15 dB
check("seuil relatif: +15 dB -> occupé", chant["state"] == "occ", chant["state"])
win.ref_chk.setChecked(False)
check("courbe de référence tracée", win.refcurve.x is not None and len(win.refcurve.x) > 10)
step("clear_ref", win.clear_ref)
check("référence effacée", win._ref_F is None and not m.REF_PATH.exists())
step("recharger la référence capturée", lambda: win.capture_ref("max"))
check("référence max hold", win._ref_F is not None)
check("chargement fichier", win._load_ref_file(m.REF_PATH))

# export du scan
out = os.path.join(tmp, "scan.csv")
saved_paths.append(out)
m.ExportScanDialog.exec = lambda self: True
step("export_scan", win.export_scan)
txt = open(out, encoding="utf-8-sig").read().splitlines()
check("export scan: en-tête + 1121 points", len(txt) == 1122 and txt[0].startswith("Frequence (MHz);"), f"{len(txt)} {txt[:2]}")
check("export scan: virgule décimale", "," in txt[1] and "." not in txt[1], txt[1])

# export liste
out2 = os.path.join(tmp, "freq.csv")
saved_paths.append(out2)
step("export_watch", win.export_watch)
hdr = open(out2, encoding="utf-8-sig").read().splitlines()[0]
check("export liste: colonnes occupation/spectre", "Occupation" in hdr and "Spectre" in hdr, hdr)

# pays
gb = win.country_combo.findData("GB")
win.country_combo.setCurrentIndex(gb)
check("pays GB appliqué", win.country == "GB" and any("Canal 38" in e[2] for e in win.plan))
check("bande Spectre recalculée", all(w["band"] is not None for w in win.watch))
us = win.country_combo.findData("US")
win.country_combo.setCurrentIndex(us)
check("pays US: canaux 6 MHz", any(e[1] - e[0] == 6 for e in win.tv))
win.country_combo.setCurrentIndex(win.country_combo.findData("FR"))

# bandeaux
pi = win.bandw.getPlotItem()
check("bandeaux: rectangles", len(win._strip_rects) == len(win.plan) + len(win.tv), f"{len(win._strip_rects)}")
pi.vb.xr = [500.0, 520.0]
win.update_strip_labels()
vis = [t.txt for t in win._strip_labels if t.vis]
check("étiquettes visibles (zoom 500-520)", any("CH" in x or x.isdigit() for x in vis), str(vis))
check("positions d'étiquettes", all(t.pos is not None for t in win._strip_labels if t.vis))
pi.vb.xr = [470.0, 694.0]
win.update_strip_labels()
vis2 = [t.txt for t in win._strip_labels if t.vis]
check("étiquettes visibles (bande entière)", len(vis2) > 5, str(vis2[:8]))
win.alloc_chk.setChecked(False)
check("une seule rangée de bandeaux", len(win._strip_rows) == 1)
win.tv_chk.setChecked(False)
check("plus de bandeaux", len(win._strip_rows) == 0)
win.alloc_chk.setChecked(True); win.tv_chk.setChecked(True)

# survol
win.bandw.getPlotItem().vb.mx = 506.0
win.on_mouse_band([object()])
check("info survol bandeau", "CH 25" in win.band_lbl.text() or "Canal UHF 25" in win.band_lbl.text(), win.band_lbl.text())
win.spec.getPlotItem().vb.mx = 760.0
win.on_mouse([object()])
check("info survol spectre", "700" in win.band_lbl.text(), win.band_lbl.text())

# plan perso
class FakeDlg:
    pass
m.PlanDialog.exec = lambda self: True
m.PlanDialog.result_text = lambda self: "470-480|mil|Mon truc test|note"
step("edit_plan", win.edit_plan)
check("plan personnalisé appliqué", win.plan == m.parse_plan_text("470-480|mil|Mon truc test|note") and "FR" in win.plan_custom)
m.PlanDialog.result_text = lambda self: ""
step("edit_plan reset", win.edit_plan)
check("plan rétabli", "FR" not in win.plan_custom and len(win.plan) > 20)

# mur
step("open_wall", win.open_wall)
wall = win.wall
wall.host.width = lambda: 1200
wall.host.height = lambda: 700
step("wall.rebuild", wall.rebuild)
check("une tuile par fréquence", len(wall.tiles) == len(win.watch))
check("tuile avec nom", any("Chant" in t.text() for t in wall.tiles if hasattr(t, "text")))
wall.only_chk.setChecked(True)
step("wall filtre occupées", wall.relayout)
wall.only_chk.setChecked(False)

# statuts
sd = m.StatusDialog(win, win.statuses)
check("dialogue statuts: free conservé", [r["free"] for r in sd.rows][:2] == [True, False], str([r["free"] for r in sd.rows]))
sd.add_row()
rr = sd.result_rows()
check("dialogue statuts: nouveau non libre", rr[-1]["free"] is False and "orig" in rr[-1])
it3 = m.QtWidgets.QTableWidgetItem("")
it3._r, it3._c = 1, 2
it3.setCheckState(m.Qt.CheckState.Checked)
sd.on_item(it3)
check("dialogue statuts: case cochée prise en compte", sd.rows[1]["free"] == (m.Qt.CheckState.Checked == m.Qt.CheckState.Checked))

# couleurs
cd = step("ColorsDialog", lambda: m.ColorsDialog(win, win.theme, lambda th: None))
check("dialogue couleurs: clés bp_ présentes", cd is not None and "bp_mobile" in cd.buttons and "ref" in cd.buttons)

# profils
prof = os.path.join(tmp, "p.json")
saved_paths.append(prof)
step("save_profile", win.save_profile)
pdat = json.load(open(prof, encoding="utf-8"))
check("profil: contenu", pdat["country"] == "FR" and len(pdat["watch"]) == 4 and "geometry" not in pdat, str(list(pdat)))
check("profil: free sauvegardé", pdat["statuses"][0]["free"] is True)
win.watch.clear()
win.rebuild_watch_table()
saved_paths.append(prof)
step("load_profile", win.load_profile)
check("profil rechargé: 4 fréquences", len(win.watch) == 4, str(len(win.watch)))
check("profil rechargé: spectre calculé", all(w["band"] for w in win.watch if w["freq"] < 880))
check("profil rechargé: bandes", len(win.bands) == 1)

# config complète + relance
win.closeEvent(fakeqt.Poly())
cfg = json.load(open(m.CFG_PATH, encoding="utf-8"))
check("config écrite", cfg["country"] == "FR" and cfg["log_auto"] is True and "demo" in cfg)
win2 = step("MainWindow() 2e lancement", m.MainWindow)
check("relance: fréquences restaurées", win2 is not None and len(win2.watch) == 4)
check("relance: statut libre restauré", win2 is not None and win2.is_keep_free("Libre"))

# ancienne config sans nouveaux champs
old = {"bands": [{"name": "UHF", "start": 470.0, "stop": 694.0, "step": 200.0, "enabled": True}],
       "watch": [{"name": "A", "freq": 500.0, "status": "Libre"}],
       "statuses": [{"name": "Libre", "color": "#2ecc71"}, {"name": "Occupé", "color": "#e74c3c"}],
       "theme": {"curve": "#ffffff"}}
json.dump(old, open(m.CFG_PATH, "w", encoding="utf-8"))
win3 = step("MainWindow() avec ancienne config", m.MainWindow)
check("ancienne config: Libre devient 'doit rester libre'", win3 is not None and win3.is_keep_free("Libre"))
check("ancienne config: thème complété", win3 is not None and "bp_tv" in win3.theme and win3.theme["curve"] == "#ffffff")

# 7.66.1 (journal de Clément) : une occupation de moins de OCC_LOG_S n'est pas notée
m.OCC_LOG_S = 3.0
def evs():
    return [(win.log_table.item(r, 1).text(), win.log_table.item(r, 4).text()) for r in range(win.log_table.rowCount())]
T[0] += 10; win.on_sweep(b0["id"], *sweep())                     # tout redevient calme
_n0 = len(evs())
for _ in range(3):                                                # 3 passages d'une seconde
    T[0] += 1; win.on_sweep(b0["id"], *sweep([(520.25, -50.0)]))
    T[0] += 1; win.on_sweep(b0["id"], *sweep())
_short = [e for e in evs()[:len(evs()) - _n0] if e[0] == "Basse"]      # le journal ajoute en tête
check("journal : passages courts non notés", _short == [], str(_short))
for _ in range(5):                                                # puis une vraie occupation de 4 s
    T[0] += 1; win.on_sweep(b0["id"], *sweep([(520.25, -50.0)]))
T[0] += 1; win.on_sweep(b0["id"], *sweep())
_long = [e[1] for e in evs()[:len(evs()) - _n0] if e[0] == "Basse"]
check("journal : occupation qui dure notée (OCCUPÉ puis Libre)", len(_long) == 2 and "OCCUPÉ" in _long
      and any(x.startswith("Libre") for x in _long), str(_long))
_note = [(win.log_table.item(r, 6).text() if win.log_table.item(r, 6) else "") for r in range(win.log_table.rowCount())
         if win.log_table.item(r, 1).text() == "Basse" and win.log_table.item(r, 4).text() == "OCCUPÉ"]
check("journal : les passages courts sont comptés dans la note", any("3 passage" in x for x in _note), str(_note))
basse = next(w for w in win.watch if w["name"] == "Basse")
basse["muted"] = True                                             # 💤 éteint (je sais) : plus rien au journal
_n1 = len(evs())
for _ in range(6):
    T[0] += 1; win.on_sweep(b0["id"], *sweep([(520.25, -50.0)]))
T[0] += 1; win.on_sweep(b0["id"], *sweep())
_mut = [e for e in evs()[:len(evs()) - _n1] if e[0] == "Basse"]
check("journal : micro éteint (je sais) = pas d'OCCUPÉ / Libre", _mut == [], str(_mut))
basse["muted"] = False

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
