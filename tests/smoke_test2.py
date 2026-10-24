import sys, os, json, tempfile, importlib.util, traceback, csv
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
tmp = tempfile.mkdtemp(prefix="tsm2_")
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


T = [2_000_000.0]
m.time.time = lambda: T[0]
W = m.QtWidgets
W.QMessageBox.question = staticmethod(lambda *a, **k: W.QMessageBox.StandardButton.Yes)
saved = []
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved.pop(0), ""))
W.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (saved.pop(0), ""))
answers = []          # réponses successives de QInputDialog.getText
W.QInputDialog.getText = staticmethod(lambda *a, **k: answers.pop(0))
W.QInputDialog.getItem = staticmethod(lambda *a, **k: answers.pop(0))
m.ImportDialog.exec = lambda self: True

win = step("MainWindow()", m.MainWindow)
if win is None:
    sys.exit(1)
win.ask_name = lambda *a, **k: answers.pop(0)
titles = []
win.setWindowTitle = lambda t: titles.append(t)
tree = win.layer_tree


def click(scene, group=None, add=False):
    """Simule un clic (ou Ctrl+clic) sur un noeud de l'arbre."""
    it = win._tree_items[(scene, group)][0]
    if not add:
        for i in tree.all_items():
            i._sel = False
    it._sel = True
    tree.itemSelectionChanged.emit()


def menu_pick(label_part):
    def chooser(menu):
        for a in menu.all_actions():
            if label_part in a.text():
                return a
        raise AssertionError(f"action introuvable : {label_part} dans {[a.text() for a in menu.all_actions()]}")
    fakeqt.FakeMenu.chooser = staticmethod(chooser)


# ---------------------------------------------------------------- données
for name, f in [("Chant A", 506.0), ("Basse A", 507.5), ("Gtr A", 509.0), ("Chant B", 560.0),
                ("Basse B", 561.5), ("IEM", 863.5)]:
    win._append_watch(name, f)
win.sort_watch()
win.rebuild_watch_table()
check("aucune scène au départ", win.scenes == [] and win.scope is None)
check("arbre vide", len(tree.top) == 0)
check("tout visible en global", all(not win.watch_table.isRowHidden(r) for r in range(6)))

# ---------------------------------------------------------------- création scènes / groupes
answers[:] = [("Main Stage", True)]
step("add_scene", win.add_scene)
check("scène créée", [s["name"] for s in win.scenes] == ["Main Stage"])
answers[:] = [("Groupe A", True)]
r = step("add_group (1 seule scène, pas de question)", win.add_group)
check("groupe créé", r == ("Main Stage", "Groupe A"), str(r))
answers[:] = [("Groupe B", True)]
step("add_group B", win.add_group)
answers[:] = [("Side Stage", True)]
step("add_scene 2", win.add_scene)
answers[:] = [("Side Stage", True), ("Duo", True)]     # choix de la scène puis nom
step("add_group sur 2 scènes", win.add_group)
check("2 scènes", [s["name"] for s in win.scenes] == ["Main Stage", "Side Stage"])
check("groupes", [g["name"] for g in win.scenes[0]["groups"]] == ["Groupe A", "Groupe B"] and
      [g["name"] for g in win.scenes[1]["groups"]] == ["Duo"], str(win.scenes))
check("couleurs distinctes", len({g["color"] for s in win.scenes for g in s["groups"]}) == 3)
check("arbre: 2 scènes + 3 groupes + « Sans scène »", len(tree.top) == 3 and len(tree.all_items()) == 6,
      str(len(tree.all_items())))

idx = {w["name"]: i for i, w in enumerate(win.watch)}
win.assign_rows([idx["Chant A"], idx["Basse A"], idx["Gtr A"]], "Main Stage", "Groupe A")
win.assign_rows([idx["Chant B"], idx["Basse B"]], "Main Stage", "Groupe B")
win.assign_rows([idx["IEM"]], "Side Stage", "Duo")
check("affectation", win.watch[idx["Chant A"]]["group"] == "Groupe A" and win.watch[idx["IEM"]]["scene"] == "Side Stage")
check("colonne Scène › Groupe", win.watch_table.item(idx["Chant A"], m.C_LAYER).text() == "Main Stage › Groupe A",
      win.watch_table.item(idx["Chant A"], m.C_LAYER).text())
check("compte dans l'arbre", "3 fréq." in win._tree_items[("Main Stage", "Groupe A")][0].text(0) and
      "5 fréq." in win._tree_items[("Main Stage", None)][0].text(0),
      win._tree_items[("Main Stage", None)][0].text(0))

# ---------------------------------------------------------------- balayage global
b0 = win.bands[0]
f = np.linspace(470, 694, 1121)
rng = np.random.default_rng(2)
base = -100 + rng.normal(0, 1.0, f.shape)


def sweep(extra=None, ff=f, bb=base):
    l = bb.copy()
    for fr, lv in (extra or []):
        l[np.argmin(np.abs(ff - fr))] = lv
    return ff, l


T[0] += 10
win.on_sweep(b0["id"], *sweep())
check("global : tout évalué", all(w["state"] == "free" for w in win.watch if w["freq"] < 694))

# ---------------------------------------------------------------- clic sur un groupe
click("Main Stage", "Groupe A")
check("scope = groupe A", win.scope == [("Main Stage", "Groupe A")], str(win.scope))
check("3 fréquences dans la couche", len(win.scope_ws()) == 3)
hidden = [win.watch_table.isRowHidden(r) for r in range(6)]
check("lignes hors couche masquées", sum(hidden) == 3 and not hidden[idx["Chant A"]] and hidden[idx["Chant B"]], str(hidden))
check("titre de fenêtre", titles and "Main Stage › Groupe A" in titles[-1], str(titles[-2:]))
check("étiquette de couche", "Groupe A" in win.layer_lbl.text() and "3" in win.layer_lbl.text(), win.layer_lbl.text())
check("compteur du tableau", "3 fréquences (sur 6)" in win.count_lbl.text(), win.count_lbl.text())
check("scan ciblé activable", win.focus_chk.isEnabled() is True)

n_log0 = win.log_table.rowCount()
T[0] += 10
win.on_sweep(b0["id"], *sweep([(560.0, -50.0), (506.0, -50.0)]))     # Chant B (hors couche) + Chant A (dans)
ev = [(win.log_table.item(r, 1).text(), win.log_table.item(r, 4).text(), win.log_table.item(r, 5).text())
      for r in range(win.log_table.rowCount())]
check("événement dans la couche journalisé", any(n == "Chant A" and e == "OCCUPÉ" for n, e, _l in ev), str(ev))
check("rien pour le hors-couche", not any(n == "Chant B" for n, e, _l in ev), str(ev))
check("journal: colonne couche", any(l == "Main Stage › Groupe A" for _n, _e, l in ev), str(ev))
check("tuile/arbre: groupe A occupé", "occupée" in win._tree_items[("Main Stage", "Groupe A")][0].text(0),
      win._tree_items[("Main Stage", "Groupe A")][0].text(0))
check("couleur arbre = occupé", win._tree_items[("Main Stage", "Groupe A")][0]._fg is not None)

# marqueurs : seulement la couche
win.spec.getPlotItem().vb.xr = [470.0, 694.0]
win._update_markers()
n_mark = sum(len(it.x) // 2 for it in win._mk_items.values() if it.x is not None and len(it.x))
check("repères limités à la couche (3)", n_mark == 3, str(n_mark))
win.mark_combo.setCurrentIndex(win.mark_combo.findData("group"))
win._update_markers()
gcol = win.group_color("Main Stage", "Groupe A")
check("repères en couleur de groupe", (gcol, False) in win._mk_items and len(win._mk_items[(gcol, False)].x) == 6,
      str(list(win._mk_items)))
win.mark_combo.setCurrentIndex(0)

# mur
step("open_wall", win.open_wall)
wall = win.wall
wall.host.width = lambda: 1200
wall.host.height = lambda: 700
wall.rebuild()
check("mur: 3 tuiles visibles", len(wall._visible_idx()) == 3, str(wall._visible_idx()))
check("mur: résumé avec couche", "Groupe A" in wall.sum_lbl.text() and "3 fréquences" in wall.sum_lbl.text(), wall.sum_lbl.text())

# ---------------------------------------------------------------- scène entière + multi-sélection
click("Main Stage")
check("scène entière = 5 fréquences", len(win.scope_ws()) == 5, str(len(win.scope_ws())))
click("Main Stage", "Groupe A")
click("Side Stage", "Duo", add=True)
check("multi-sélection", len(win.scope) == 2 and len(win.scope_ws()) == 4, str(win.scope))
check("texte de couche multiple", "+" in win.scope_text(), win.scope_text())

# ---------------------------------------------------------------- scan ciblé
click("Main Stage", "Groupe A")
v0 = win.get_ver()
win.focus_chk.setChecked(True)
check("scan ciblé : bandes créées", len(win._focus_bands) >= 1 and all(b["id"] <= -100 for b in win._focus_bands),
      str(win._focus_bands))
cfg = win.get_cfg()
check("config du worker = zones ciblées", [b["id"] for b in cfg["bands"]] == [b["id"] for b in win._focus_bands])
fb = win._focus_bands[0]
check("zone couvre les 3 fréquences", fb["start"] <= 506.0 and fb["stop"] >= 509.0, str(fb))
check("zone étroite", (fb["stop"] - fb["start"]) < 10, str(fb))
check("version incrémentée (le cycle en cours s'arrête)", win.get_ver() > v0)
check("estimation ciblée", "Scan ciblé" in win.est_lbl.text(), win.est_lbl.text())
check("vue = zones ciblées", win.view_combo.count() == 1 + len(win._focus_bands))
check("anciennes données purgées", b0["id"] not in win.latest, str(list(win.latest)))
# balayage d'une zone ciblée
ff = np.linspace(fb["start"], fb["stop"], m.MainWindow._npts(fb))
bb = -100 + rng.normal(0, 1.0, ff.shape)
T[0] += 3
win.on_sweep(fb["id"], *sweep([(507.5, -45.0)], ff, bb))
basse = win.watch[idx["Basse A"]]
check("niveau mesuré dans la zone ciblée", basse["state"] == "occ", str(basse["state"]))
win.on_cycle(0.4, 1)
check("étiquette de cycle ciblée", "🎯" in win.cycle_lbl.text() and "3 fréq." in win.cycle_lbl.text(), win.cycle_lbl.text())
check("plage de vue ajustée", (lambda r: r is not None and r[0] >= 500)(win._fit_range()), str(win._fit_range()))
# changement de points -> zones recalculées
win.points_combo.setCurrentIndex(win.points_combo.findData(3000))
win._sync_cfg()
check("points 3000 : au plus 3000 pts/zone", all(m.MainWindow._npts(b) <= 3000 for b in win._focus_bands))
# global : retour au balayage complet
v1 = win.get_ver()
win.go_global()
check("global : plus de scan ciblé", win._focus_bands == [] and win.scan_bands() is win.bands)
check("global : bandes d'origine envoyées au worker", [b["id"] for b in win.get_cfg()["bands"]] == [b["id"] for b in win.bands])
check("global : version incrémentée", win.get_ver() > v1)
check("global : tout visible", not any(win.watch_table.isRowHidden(r) for r in range(6)))
check("global : bouton ciblé grisé", win.focus_chk.isEnabled() is False)
# groupe sans fréquence -> repli sur le balayage complet
answers[:] = [("Vide", True)]
win.add_group("Main Stage")
click("Main Stage", "Vide")
win.focus_chk.setChecked(True)
check("couche vide : repli sur les bandes normales", win.scan_bands() is win.bands)
win.focus_chk.setChecked(False)
win.go_global()

# ---------------------------------------------------------------- menu clic droit : affecter
win._sel_rows = lambda: [idx["Gtr A"]]
menu_pick("Groupe B")
win.watch_table.rowAt = lambda y: 0
step("watch_menu → affecter", lambda: win.watch_menu(fakeqt.Poly()))
check("affectation via menu", win.watch[idx["Gtr A"]]["group"] == "Groupe B", str(win.watch[idx["Gtr A"]]))
menu_pick("Nouvelle scène + groupe")
answers[:] = [("Backline", True), ("Techs", True)]
step("watch_menu → nouvelle scène + groupe", lambda: win.watch_menu(fakeqt.Poly()))
check("nouvelle scène/groupe via menu", win.watch[idx["Gtr A"]]["scene"] == "Backline" and
      win.watch[idx["Gtr A"]]["group"] == "Techs")
menu_pick("Aucune scène")
step("watch_menu → aucune", lambda: win.watch_menu(fakeqt.Poly()))
check("retrait via menu", win.watch[idx["Gtr A"]]["scene"] == "" and win.watch[idx["Gtr A"]]["group"] == "")
check("noeud « Sans scène »", ("", None) in win._tree_items)
win.assign_rows([idx["Gtr A"]], "Main Stage", "Groupe A")
win._sel_rows = type(win)._sel_rows.__get__(win)
fakeqt.FakeMenu.chooser = None

# menu de l'arbre
tree._at = win._tree_items[("Main Stage", "Groupe B")][0]
click("Main Stage", "Groupe B")
win._sel_rows = lambda: [idx["Chant A"]]
menu_pick("Affecter les 1")
step("layer_menu → affecter ici", lambda: win.layer_menu(fakeqt.Poly()))
check("affecter depuis l'arbre", win.watch[idx["Chant A"]]["group"] == "Groupe B")
win.assign_rows([idx["Chant A"]], "Main Stage", "Groupe A")
win._sel_rows = type(win)._sel_rows.__get__(win)
fakeqt.FakeMenu.chooser = None

# ---------------------------------------------------------------- renommer / couleur / supprimer
click("Main Stage", "Groupe A")
answers[:] = [("Les Fleurs", True)]
step("rename groupe", lambda: win.rename_layer(("Main Stage", "Groupe A")))
check("renommage répercuté", win.watch[idx["Chant A"]]["group"] == "Les Fleurs" and
      win.scope == [("Main Stage", "Les Fleurs")], str(win.scope))
check("scope toujours actif après renommage", len(win.scope_ws()) == 3, str(len(win.scope_ws())))
answers[:] = [("Groupe B", True)]
step("rename vers un nom existant refusé", lambda: win.rename_layer(("Main Stage", "Les Fleurs")))
check("doublon refusé", any(g["name"] == "Les Fleurs" for g in win.scenes[0]["groups"]))
answers[:] = [("Main Stage 2", True)]
step("rename scène", lambda: win.rename_layer(("Main Stage", None)))
check("scène renommée", win.watch[idx["Chant A"]]["scene"] == "Main Stage 2" and win.scope[0][0] == "Main Stage 2")
W.QColorDialog.getColor = staticmethod(lambda *a, **k: type("C", (), {"isValid": lambda s: True, "name": lambda s: "#123456"})())
step("couleur", lambda: win.pick_layer_color(("Main Stage 2", "Les Fleurs")))
check("couleur changée", win.group_color("Main Stage 2", "Les Fleurs") == "#123456")
step("supprimer groupe", lambda: win.delete_layer(("Main Stage 2", "Groupe B")))
check("groupe supprimé, fréquences conservées", all(g["name"] != "Groupe B" for g in win.scenes[0]["groups"]) and
      win.watch[idx["Chant B"]]["group"] == "" and win.watch[idx["Chant B"]]["scene"] == "Main Stage 2" and len(win.watch) == 6)
step("supprimer scène", lambda: win.delete_layer(("Side Stage", None)))
check("scène supprimée", win.scene_by_name("Side Stage") is None and win.watch[idx["IEM"]]["scene"] == "")
win.go_global()

# ---------------------------------------------------------------- import CSV avec scène / groupe
csv_txt = ("Scène;Groupe;Nom;Fréquence MHz\n"
           "Stage 3;Les Zéro;Chant;470,125\n"
           "Stage 3;Les Zéro;Basse;470,500\n"
           "Stage 3;Duo Jazz;Sax;471,250\n"
           "Stage 3;Duo Jazz;Piano;506,000\n")        # 506,000 existe déjà (Chant A)
dlg = m.ImportDialog(win, csv_txt, "scenes.csv", win.scenes)
check("import: colonne scène détectée", dlg.scene_col_combo.currentData() is not None and dlg.group_col_combo.currentData() is not None,
      str((dlg.scene_col_combo.currentData(), dlg.group_col_combo.currentData(), dlg.an["scene_col"])))
ents = dlg.entries()
check("import: 5-uplets", len(ents) == 4 and ents[0][3] == "Stage 3" and ents[0][4] == "Les Zéro", str(ents))
n0 = len(win.watch)
win.open_import(csv_txt, "scenes.csv")
check("import: 3 ajoutées + 1 doublon", len(win.watch) == n0 + 3, str(len(win.watch) - n0))
check("import: scène et groupes créés", win.scene_by_name("Stage 3") is not None and
      {g["name"] for g in win.scene_by_name("Stage 3")["groups"]} == {"Les Zéro", "Duo Jazz"})
sax = next(w for w in win.watch if w["name"] == "Sax")
check("import: affectation", sax["scene"] == "Stage 3" and sax["group"] == "Duo Jazz")
chantA = next(w for w in win.watch if w["name"] == "Chant A")
check("import: doublon déjà rangé conservé", chantA["group"] == "Les Fleurs")
# fichier sans colonnes scène/groupe + preset
plain = "Nom;MHz\nM1;600,000\nM2;601,000\n"
dlg2 = m.ImportDialog(win, plain, "plain.csv", win.scenes, ("Stage 4", "Les Autres"))
e2 = dlg2.entries()
check("import preset: scène/groupe du fichier entier", all(x[3] == "Stage 4" and x[4] == "Les Autres" for x in e2), str(e2))
dlg3 = m.ImportDialog(win, plain, "plain.csv", win.scenes, ("", "Solo"))
check("import: groupe sans scène -> scène par défaut", all(x[3] == m.DEFAULT_SCENE for x in dlg3.entries()), str(dlg3.entries()))
win.open_import(plain, "plain.csv", preset=("Stage 4", "Les Autres"))
m1 = next(w for w in win.watch if w["name"] == "M1")
check("import avec preset appliqué", m1["scene"] == "Stage 4" and m1["group"] == "Les Autres")
# doublon sans couche -> prend la couche de l'import
extra = "Nom;MHz\nIEM;863,500\n"
win.open_import(extra, "iem.csv", preset=("Stage 4", "Les Autres"))
iem = next(w for w in win.watch if w["name"] == "IEM")
check("doublon sans couche rangé par l'import", iem["scene"] == "Stage 4" and iem["group"] == "Les Autres", str(iem["scene"]))
# dépôt avec un groupe actif -> préréglage
click("Stage 4", "Les Autres")
check("préréglage = groupe actif", win._scope_preset() == ("Stage 4", "Les Autres"))
win.go_global()
check("préréglage vide en global", win._scope_preset() == ("", ""))

# export puis ré-import (aller-retour)
out = os.path.join(tmp, "liste.csv")
saved.append(out)
step("export_watch", win.export_watch)
txt = open(out, encoding="utf-8-sig").read()
hdr = txt.splitlines()[0]
check("export: colonnes Scène et Groupe", "Scène" in hdr and "Groupe" in hdr, hdr)
an = m.analyze_csv(txt)
check("export: ré-importable (scène/groupe détectés)", an["scene_col"] is not None and an["group_col"] is not None,
      str((an["scene_col"], an["group_col"])))

# ---------------------------------------------------------------- guide des bandes
step("open_guide", win.open_guide)
g = win._guide
check("guide créé", g is not None and len(g.shown) > 30, str(len(g.shown)) if g else "None")
g.search.setText("police")
g.refresh()
check("guide: recherche « police »", len(g.shown) >= 1 and all("polic" in (e[2] + e[4]).lower() or "polic" in m.CATEGORIES.get(e[3], ("",))[0].lower() for e in g.shown),
      str([e[2] for e in g.shown]))
g.search.setText("446.1")
g.refresh()
check("guide: recherche par fréquence", any("PMR446" in e[2] for e in g.shown), str([e[2] for e in g.shown]))
g.search.setText("ads-b")
g.refresh()
check("guide: recherche ADS-B", len(g.shown) >= 1, str(len(g.shown)))
g.search.setText("")
ci = g.cat_combo.findData("safety")
g.cat_combo.setCurrentIndex(ci)
g.refresh()
check("guide: filtre catégorie", len(g.shown) >= 1 and all(e[3] == "safety" for e in g.shown), str(len(g.shown)))
g.src_combo.setCurrentIndex(1)
g.cat_combo.setCurrentIndex(0)
g.refresh()
check("guide: onglet canaux TV", len(g.shown) > 40 and all(e[3] in ("tv", "tv_off") for e in g.shown), str(len(g.shown)))
g.src_combo.setCurrentIndex(0)
g.search.setText("police")
g.refresh()
g.table.currentRow = lambda: 0
nb = len(win.bands)
g.on_add()
nb2 = len(win.bands)
check("guide: ajout aux bandes", nb2 == nb + 1)
nbnd = win.bands[-1]
check("guide: bande ajoutée cohérente", nbnd["start"] >= 0.1 and nbnd["stop"] > nbnd["start"] and nbnd["step"] > 0,
      str(nbnd))
g.on_view()
vr = win.spec.getPlotItem().vb.xr
check("guide: zoom sur la bande", vr[0] < g.shown[0][0] + 1 and vr[1] > g.shown[0][1] - 1, str((vr, g.shown[0])))
for bnd in list(win.bands[1:]):
    win.bands.remove(bnd)
win._bands_changed()

# ---------------------------------------------------------------- profils / config
click("Stage 3", "Duo Jazz")
win.focus_chk.setChecked(True)
prof = os.path.join(tmp, "p.json")
saved.append(prof)
step("save_profile", win.save_profile)
pd = json.load(open(prof, encoding="utf-8"))
check("profil: scènes", any(s["name"] == "Stage 3" and {g["name"] for g in s["groups"]} == {"Les Zéro", "Duo Jazz"} for s in pd["scenes"]), str(pd.get("scenes")))
check("profil: scope et focus", pd["scope"] == [["Stage 3", "Duo Jazz"]] and pd["focus"] is True, str((pd.get("scope"), pd.get("focus"))))
check("profil: scène/groupe par fréquence", any(w["name"] == "Sax" and w["scene"] == "Stage 3" and w["group"] == "Duo Jazz" for w in pd["watch"]))
win.go_global()
win.focus_chk.setChecked(False)
win.scenes.clear()
for w in win.watch:
    w["scene"] = w["group"] = ""
saved.append(prof)
step("load_profile", win.load_profile)
check("profil rechargé: scènes", win.scene_by_name("Stage 3") is not None and len(win.scenes) >= 3)
check("profil rechargé: affectations", next(w for w in win.watch if w["name"] == "Sax")["group"] == "Duo Jazz")
check("profil rechargé: scope", win.scope == [("Stage 3", "Duo Jazz")], str(win.scope))
check("profil rechargé: scan ciblé actif", win.focus_chk.isChecked() and len(win._focus_bands) >= 1, str(win._focus_bands))
check("profil rechargé: 1 fréquence en couche", len(win.scope_ws()) == 1, str(len(win.scope_ws())))

win.closeEvent(fakeqt.Poly())
win2 = step("relance", m.MainWindow)
check("relance: scènes restaurées", win2 is not None and win2.scene_by_name("Stage 3") is not None)
check("relance: couche et ciblage restaurés", win2 is not None and win2.scope == [("Stage 3", "Duo Jazz")] and
      win2.focus_chk.isChecked() and len(win2._focus_bands) >= 1, str(win2.scope if win2 else None))
check("relance: arbre sélectionné", win2 is not None and win2._tree_items[("Stage 3", "Duo Jazz")][0].isSelected())

# ancienne config (sans scènes) : tout continue de marcher
old = {"bands": [{"name": "UHF", "start": 470.0, "stop": 694.0, "step": 200.0, "enabled": True}],
       "watch": [{"name": "A", "freq": 500.0, "status": "Libre"}]}
json.dump(old, open(m.CFG_PATH, "w", encoding="utf-8"))
win3 = step("ancienne config", m.MainWindow)
check("ancienne config: global, sans scène", win3 is not None and win3.scope is None and win3.scenes == [] and
      win3.watch[0]["scene"] == "")

# scope fantôme dans un profil (groupe supprimé entre-temps) -> retombe en global
bad = dict(old)
bad["scope"] = [["Fantôme", "Nulle part"]]
bad["focus"] = True
json.dump(bad, open(m.CFG_PATH, "w", encoding="utf-8"))
win4 = step("scope fantôme", m.MainWindow)
check("scope fantôme ignoré", win4 is not None and win4.scope is None and win4._focus_bands == [], str(win4.scope if win4 else None))

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
