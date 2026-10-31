import sys, os, json, tempfile, importlib.util, traceback, csv, time as _time
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
tmp = tempfile.mkdtemp(prefix="tsm4_")
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


T = [4_000_000.0]
m.time.time = lambda: T[0]
W = m.QtWidgets
W.QMessageBox.question = staticmethod(lambda *a, **k: W.QMessageBox.StandardButton.Yes)
saved, opened, dirs = [], [], []
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (saved.pop(0), ""))
W.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (opened.pop(0), ""))
W.QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: (list(opened), ""))
W.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: dirs.pop(0))
W.QInputDialog.getItem = staticmethod(lambda *a, **k: ("Max hold (recommandé)", True))
win = step("MainWindow()", m.MainWindow)
win.sound.cfg.update(confirm=0, repeat=10)          # ces tests vérifient le CONFLIT immédiat et la répétition 10 s
win.alarms.repeat_s = 10.0
if win is None:
    sys.exit(1)
win.log_dir = m.Path(tmp) / "journaux"
class FakeBtn:
    def __init__(self):
        self._t, self._s = "🔔", ""

    def setText(self, x):
        self._t = x

    def text(self):
        return self._t

    def setStyleSheet(self, s):
        self._s = s


win.alarm_btn = FakeBtn()
sounds = []
win._alarm_sound = lambda prio: sounds.append(prio)        # on compte les sons au lieu de biper

# ------------------------------------------------------------- statuts
names = [s["name"] for s in win.statuses]
check("statut « En service » par défaut", "En service" in names)
check("is_keep_on", win.is_keep_on("En service") and not win.is_keep_on("Libre") and not win.is_keep_on(""))
check("Libre n'est pas « doit émettre »", not any(s.get("on") for s in win.statuses if s["name"] == "Libre"))

# ------------------------------------------------------------- scène / groupes / fréquences
win.ensure_group("Show", "Micros")
win.ensure_group("Show", "Libres")
sc = win.scene_by_name("Show")
check("scène + 2 groupes", sc is not None and {g["name"] for g in sc["groups"]} == {"Micros", "Libres"})
check("priorité par défaut = normale", all(g.get("prio", 1) == 1 for g in sc["groups"]))
win.set_prio(("Show", "Micros"), 2)
check("priorité critique posée", win.freq_prio(dict(scene="Show", group="Micros")) == 2)
check("prio_mark critique", "❗" in win.prio_mark(next(g for g in sc["groups"] if g["name"] == "Micros")))
check("priorité d'une fréquence sans groupe = normale", win.freq_prio(dict(scene="", group="")) == 1)
win._append_watch("HF 1", 500.0, status="En service", scene="Show", group="Micros")
win._append_watch("HF 2", 502.0, status="En service", scene="Show", group="Micros")
win._append_watch("Libre 1", 499.0, status="Libre", scene="Show", group="Libres")
win.sort_watch()
win.rebuild_watch_table()
idx = {w["name"]: i for i, w in enumerate(win.watch)}
bid = win.bands[0]["id"]
f = np.linspace(470, 530, 2401)


def sweep(tx=(), extra=()):
    l = -105 + np.zeros_like(f)
    for x in tx:
        l[np.argmin(np.abs(f - x))] = -40
    for x in extra:
        l[np.argmin(np.abs(f - x))] = -50
    win.on_sweep(bid, f, l)


win.absent_spin.setValue(20)
win.last_cycle = 1.0
win.ref_chk.setChecked(False)
# --- tout émet : aucune alarme
sweep(tx=(500.0, 502.0))
check("TX présents : pas d'alarme", not win.alarms.active and all(win.watch[idx[n]]["state"] == "occ" for n in ("HF 1", "HF 2")),
      str([win.watch[idx[n]]["state"] for n in ("HF 1", "HF 2")]))
check("bouton 🔔 au repos", win.alarm_btn.text() == "🔔", win.alarm_btn.text())
# --- HF 1 se tait
T[0] += 1
sweep(tx=(502.0,))
check("HF 1 libre mais délai pas écoulé : pas d'alarme", not win.alarms.active, str(win.alarms.active))
T[0] += 10
sweep(tx=(502.0,))
check("10 s : toujours pas d'alarme", not win.alarms.active)
T[0] += 12
sweep(tx=(502.0,))
ab = [a for a in win.alarms.active.values() if a["kind"] == "ABSENT"]
check("22 s de silence : ABSENT levée", len(ab) == 1 and ab[0]["name"] == "HF 1", str(win.alarms.active))
check("ABSENT : priorité du groupe (critique)", ab and ab[0]["prio"] == 2)
check("ABSENT : son déclenché (prio 2)", sounds == [2], str(sounds))
check("ABSENT : drapeau sur la fréquence", win.watch[idx["HF 1"]]["absent"] is True)
win.refresh_alarms()
check("ABSENT : bouton 🔔 1 en rouge", win.alarm_btn.text() == "🔔 1" and "font-weight" in win.alarm_btn._s, win.alarm_btn.text())
lg = [win.log_table.item(r, 4).text() for r in range(win.log_table.rowCount())]
check("ABSENT dans le journal", "ABSENT" in lg, str(lg))
check("la fréquence encore en silence : pas de 2e alarme", (sweep(tx=(502.0,)), len(win.alarms.active))[1] == 1)
check("pas de re-son tant que < 10 s", sounds == [2])
# --- critique : répétition toutes les 10 s
T[0] += 11
win._alarm_sound = lambda prio: sounds.append(prio)
win.alarms.due_repeat  # existe
win._alarm_tick()
check("critique non acquittée : son rejoué après 10 s", sounds == [2, 2], str(sounds))
# --- acquittement
win.ack_all_alarms()
T[0] += 15
win._alarm_tick()
check("acquittée : plus de son", sounds == [2, 2], str(sounds))
check("acquittée : alarme toujours en cours", len(win.alarms.active) == 1 and list(win.alarms.active.values())[0]["acked"])
check("bouton 🔕 après acquittement", win.alarm_btn.text() == "🔕 1", win.alarm_btn.text())
# --- retour du TX
T[0] += 2
sweep(tx=(500.0, 502.0))
check("retour du TX : alarme terminée", not win.alarms.active and len(win.alarms.done) == 1)
check("drapeau absent retiré", win.watch[idx["HF 1"]]["absent"] is False)
lg = [win.log_table.item(r, 4).text() for r in range(win.log_table.rowCount())]
check("« Retour » dans le journal", any(x.startswith("Retour") for x in lg), str(lg))
win._alarm_tick()          # le bouton est tenu à jour chaque seconde
check("bouton 🔔 de nouveau neutre", win.alarm_btn.text() == "🔔", win.alarm_btn.text())
# --- CONFLIT confirmé : un signal bref ne sonne pas, un signal qui dure (≥ 3 s) oui
win.sound.cfg["confirm"] = 3
sounds.clear()
T[0] += 1
sweep(tx=(500.0, 502.0), extra=(499.0,))
check("CONFLIT : pas d'alarme au 1er balayage (en attente de confirmation)",
      not any(a["kind"] == "CONFLIT" for a in win.alarms.active.values()) and not sounds, str(sounds))
T[0] += 1
sweep(tx=(500.0, 502.0))
T[0] += 5
sweep(tx=(500.0, 502.0))
check("CONFLIT : signal de 1 s puis parti → jamais d'alarme", not any(a["kind"] == "CONFLIT" for a in win.alarms.active.values()))
sweep(tx=(500.0, 502.0), extra=(499.0,))
T[0] += 4
sweep(tx=(500.0, 502.0), extra=(499.0,))
check("CONFLIT : signal qui dure 4 s → alarme", any(a["kind"] == "CONFLIT" for a in win.alarms.active.values()))
win.alarms.clear(("CONFLIT", int(round(499.0 * 1000))), T[0])
win.alarms.done.clear()
T[0] += 1
sweep(tx=(500.0, 502.0))
win.sound.cfg["confirm"] = 0
# --- CONFLIT sur fréquence libre (prio normale)
sounds.clear()
T[0] += 1
sweep(tx=(500.0, 502.0), extra=(499.0,))
cf = [a for a in win.alarms.active.values() if a["kind"] == "CONFLIT"]
check("CONFLIT levé sur 'Libre 1'", len(cf) == 1 and cf[0]["name"] == "Libre 1" and cf[0]["prio"] == 1, str(win.alarms.active))
check("CONFLIT : un seul son (prio 1)", sounds == [1], str(sounds))
T[0] += 5
sweep(tx=(500.0, 502.0))
check("CONFLIT terminé quand le signal disparaît", not win.alarms.active)
# --- priorité Info : pas de son
sounds.clear()
win.set_prio(("Show", "Libres"), 0)
T[0] += 1
sweep(tx=(500.0, 502.0), extra=(499.0,))
check("prio Info : alarme levée sans son", len(win.alarms.active) == 1 and sounds == [0], str(sounds))
sweep(tx=(500.0, 502.0))
# --- portée : une alarme disparaît si la fréquence sort de la couche
sounds.clear()
T[0] += 40
sweep(tx=(502.0,))
T[0] += 25
sweep(tx=(502.0,))
check("2e ABSENT levée", any(a["kind"] == "ABSENT" for a in win.alarms.active.values()), str(win.alarms.active))
win.scope = [("Show", "Libres")]
sweep(tx=(502.0,))
check("fréquence hors couche : alarme arrêtée", not win.alarms.active and not win.watch[idx["HF 1"]]["absent"],
      str(win.alarms.active))
win.scope = None
# --- statut qui n'est plus « doit émettre »
T[0] += 1
sweep(tx=(502.0,))
T[0] += 25
sweep(tx=(502.0,))
check("ABSENT à nouveau", any(a["kind"] == "ABSENT" for a in win.alarms.active.values()))
win.watch[idx["HF 1"]]["status"] = "Réservé"
sweep(tx=(502.0,))
check("statut changé : ABSENT s'arrête", not win.alarms.active)
win.watch[idx["HF 1"]]["status"] = "En service"
# --- suppression d'une fréquence avec alarme en cours
T[0] += 1
sweep(tx=(502.0,))
T[0] += 25
sweep(tx=(502.0,))
check("ABSENT avant suppression", len(win.alarms.active) == 1)
w1 = win.watch.pop(idx["HF 1"])
win._alarm_tick()
check("fréquence supprimée : alarme nettoyée par le tick", not win.alarms.active)
win.watch.insert(idx["HF 1"], w1)
w1["absent"] = False
w1["free_since"] = None
# --- délai minimum : jamais moins de 2 cycles
win.absent_spin.setValue(3)
win.last_cycle = 10.0
T[0] += 1
sweep(tx=(502.0,))
T[0] += 12
sweep(tx=(502.0,))
check("délai ≥ 2 cycles (10 s de cycle → 20 s)", not win.alarms.active, str(win.alarms.active))
T[0] += 10
sweep(tx=(502.0,))
check("… puis ABSENT après 22 s", any(a["kind"] == "ABSENT" for a in win.alarms.active.values()))
win.last_cycle = 1.0
win.absent_spin.setValue(20)
sweep(tx=(500.0, 502.0))

# ------------------------------------------------------------- tableau d'alarmes
win.alarm_table.isVisible = lambda: True
T[0] += 1
sweep(tx=(502.0,))
T[0] += 25
sweep(tx=(502.0,))
step("refresh_alarms", win.refresh_alarms)
check("tableau d'alarmes rempli", win.alarm_table.rowCount() == len(win.alarms.listing()) and win.alarm_table.rowCount() >= 2,
      str(win.alarm_table.rowCount()))
check("bandeau d'alarmes", "à acquitter" in win.alarm_lbl._t, win.alarm_lbl._t)
class _Ix:
    def __init__(self, r):
        self._r = r

    def row(self):
        return self._r
win.alarm_table.selectedIndexes = lambda: [_Ix(0)]
check("id d'alarme sélectionnée", len(win._alarm_selected_ids()) == 1)
win.ack_selected()
check("acquittement de la sélection", all(a["acked"] for a in win.alarms.active.values()))
n_done = len(win.alarms.done)
win.purge_alarms()
check("effacer les terminées", len(win.alarms.done) == 0 and n_done >= 1)
step("toggle_alarm_dock", win.toggle_alarm_dock)
step("alarm_jump", lambda: win.alarm_jump(0, 3))

# ------------------------------------------------------------- statistiques de l'arbre / mur / titre
cnt = win._tree_counts()
check("arbre : alarme comptée", any(c[2] >= 1 for c in cnt.values()), str(cnt))
wall = step("WallWindow", lambda: m.WallWindow(win))
if wall is not None:
    wall.isVisible = lambda: True
    wall.rebuild()
    check("mur : tuile ABSENT", any("ABSENT" in t._t for t in wall.tiles), str([t._t[:60] for t in wall.tiles]))

# ------------------------------------------------------------- configuration aller-retour
cfg = win._collect_config(True)
check("config : statuts avec 'on'", any(s.get("on") for s in cfg["statuses"]))
check("config : priorité du groupe", any(g.get("prio") == 2 for s in cfg["scenes"] for g in s["groups"]), str(cfg["scenes"]))
check("config : délai TX absent", cfg.get("absent_s") == 20)
cfg["absent_s"] = 45
win._apply_config(json.loads(json.dumps(cfg)))
check("config rechargée : délai", win.absent_spin.value() == 45)
check("config rechargée : priorité", win.freq_prio(dict(scene="Show", group="Micros")) == 2 and
      win.freq_prio(dict(scene="Show", group="Libres")) == 0)
check("config rechargée : 'doit émettre' restauré", win.is_keep_on("En service"))
check("config rechargée : alarmes remises à zéro", not win.alarms.active and not win.alarms.done)
old = json.loads(json.dumps(cfg))
for s in old["statuses"]:
    s.pop("on", None)
old["statuses"] = [s for s in old["statuses"] if s["name"] != "En service"]
win._apply_config(old)
check("ancienne config : statut « En service » ajouté", win.is_keep_on("En service"))
for g in old["scenes"][0]["groups"]:
    g.pop("prio", None)
win._apply_config(old)
check("ancienne config : priorité normale", win.freq_prio(dict(scene="Show", group="Micros")) == 1)
idx = {w["name"]: i for i, w in enumerate(win.watch)}

# ------------------------------------------------------------- boîte des statuts
sd = m.StatusDialog(win, win.statuses)
en = next(r for r in sd.rows if r["name"] == "En service")
check("StatusDialog : 'En service' est 'doit émettre'", en["on"] is True)
res = sd.result_statuses() if hasattr(sd, "result_statuses") else None

# ------------------------------------------------------------- enregistrement + relecture
win.log_dir = m.Path(tmp) / "journaux"
win.rec_chk.setChecked(True)
check("enregistrement démarré", win.recorder is not None and "Enregistrement" in win.rec_lbl._t, win.rec_lbl._t)
for k in range(6):
    T[0] += 5
    sweep(tx=(500.0, 502.0) if k % 2 == 0 else (502.0,))
win.recorder.flush(T[0])
chunks = sorted(win.recorder.folder.glob("chunk_*.npz"))
check("tranche écrite sur disque", len(chunks) >= 1 and win.recorder.n_sweeps >= 6, f"{chunks} {win.recorder.n_sweeps}")
st2 = m.SweepStore(1800, 300)
n, nf = m.load_recording(win.recorder.folder, st2)
check("relecture du disque : 6 balayages", n >= 6, f"{n}")
rec_folder = win.recorder.folder
win.rec_chk.setChecked(False)
check("enregistrement arrêté", win.recorder is None and "terminé" in win.rec_lbl._t, win.rec_lbl._t)
check("mémoire tampon alimentée", sum(len(v) for v in win.store.t.values()) >= 6, str({k: len(v) for k, v in win.store.t.items()}))
rd = step("ReplayDialog()", lambda: m.ReplayDialog(win))
if rd is not None:
    step("replay.use_memory", rd.use_memory)
    check("replay : instants chargés", len(rd.times) >= 6, str(len(rd.times)))
    step("replay.seek", lambda: rd.seek(2))
    step("replay.step", lambda: rd.step(1))
    step("replay.toggle_play", rd.toggle_play)
    step("replay._tick", rd._tick)
    step("replay.toggle_play (stop)", rd.toggle_play)
    step("replay.fill_events", rd.fill_events)
    opened[:] = [str(rec_folder)]
    W.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(rec_folder))
    step("replay.open_rec", rd.open_rec)
    check("replay : enregistrement disque chargé", len(rd.times) >= 6, str(len(rd.times)))
step("open_replay", win.open_replay)

# ------------------------------------------------------------- rapport
m.ReportDialog.exec = lambda self: True
m.ExportListDialog.exec = lambda self: True
rep_path = os.path.join(tmp, "rapport.html")
saved[:] = [rep_path]
step("make_report", win.make_report)
check("rapport écrit", os.path.exists(rep_path))
if os.path.exists(rep_path):
    html = open(rep_path, encoding="utf-8").read()
    check("rapport : contenu (ABSENT, HF 1, svg)", "ABSENT" in html and "HF 1" in html and "<svg" in html, html[:200])
    check("rapport : balises principales", html.count("<html") == 1 and html.count("</html>") == 1)

# ------------------------------------------------------------- export par scène
out_base = os.path.join(tmp, "exports")
os.makedirs(out_base)
W.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: out_base)
step("export_by_scene", win.export_by_scene)
made = list(m.Path(out_base).rglob("*.csv"))
check("export par scène : fichiers créés", len(made) >= 1, str(made))
if made:
    txt = made[0].read_text(encoding="utf-8-sig")
    check("export : contient des fréquences", "500" in txt or "502" in txt, txt[:200])

# ------------------------------------------------------------- scans WSM / WWB
rows = ["WSM scan export", "Date;2026-10-24", "Site;Test", "", "", ""]
hdr = "Frequency;RF level (%);RF level;Memory (%);Memory;Squelch (%);Squelch"
body = []
for k in range(470000, 480001, 25):
    body.append(f"{k};{20 + (k % 7) * 3};-96 dBm;0;0;0;0")
wsm_txt = "\n".join(rows + [hdr] + body + ["", "", "", "", "", "", "", "", "", "", "", "", ""])
wsm_path = os.path.join(tmp, "scan_wsm.csv")
open(wsm_path, "w", encoding="utf-8").write(wsm_txt)
opened[:] = [wsm_path]
step("import_scan_as_ref", win.import_scan_as_ref)
check("scan WSM importé comme référence", win._ref_F is not None and len(win._ref_F) > 100 and win.showref_chk.isChecked(),
      str(None if win._ref_F is None else len(win._ref_F)))
check("niveau en dBm plausible", win._ref_L is not None and -121 < float(np.min(win._ref_L)) and float(np.max(win._ref_L)) < 1, "")
out_wwb = os.path.join(tmp, "scan_wsm_WWB.csv")
opened[:] = [wsm_path]
saved[:] = [out_wwb]
step("convert_wsm_wwb", win.convert_wsm_wwb)
check("conversion WSM → WWB : fichier", os.path.exists(out_wwb))
if os.path.exists(out_wwb):
    first = open(out_wwb, encoding="utf-8").read().splitlines()[0]
    check("format WWB « 470.000, -98 »", first.count(",") == 1 and first.split(",")[0].replace(".", "").isdigit(), first)
out2 = os.path.join(tmp, "live_WWB.csv")
saved[:] = [out2]
step("export_scan_wwb", win.export_scan_wwb)
check("export du scan au format WWB", os.path.exists(out2) and len(open(out2).read().splitlines()) > 100)
opened[:] = [out2]
step("réimport du scan WWB", win.import_scan_as_ref)
check("réimport WWB comme référence", win._ref_F is not None and abs(float(win._ref_F[0]) - 470.0) < 0.5)
bad = os.path.join(tmp, "n_importe_quoi.csv")
open(bad, "w").write("bonjour;monde\n1;2\n")
opened[:] = [bad]
r_before = win._ref_F
shown = []
W.QMessageBox.warning = staticmethod(lambda *a, **k: shown.append(a[-1]))
step("import d'un fichier illisible", win.import_scan_as_ref)
check("fichier illisible : message d'erreur, référence intacte", shown and win._ref_F is r_before, str(shown))

# ------------------------------------------------------------- fermeture
win.rec_chk.setChecked(True)
sweep(tx=(500.0,))
step("closeEvent", lambda: win.closeEvent(type("E", (), {"accept": lambda self: None})()))
check("fermeture : enregistrement refermé", win.recorder is None)
print("\nÉCHECS:", fails)
