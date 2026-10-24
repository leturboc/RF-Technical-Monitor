"""2e tinySA dans MainWindow (faux Qt) : répartition des bandes, bascule quand un appareil décroche,
alarme APPAREIL, zoom, coupe de bande, config, démarrage des deux workers."""
import sys, os, tempfile, importlib.util, traceback
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
tmp = tempfile.mkdtemp(prefix="tsm5_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
os.environ["USERPROFILE"] = tmp
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
msgs = []
W.QMessageBox.warning = staticmethod(lambda p, t, x, *a, **k: msgs.append(x))
W.QMessageBox.critical = staticmethod(lambda p, t, x, *a, **k: msgs.append(x))
win = step("MainWindow()", m.MainWindow)
if win is None:
    sys.exit(1)
win.log_dir = m.Path(tmp) / "journaux"
sounds = []
win._alarm_sound = lambda prio: sounds.append(prio)

# ------------------------------------------------------------- bandes
with win.lock:
    win.bands.clear()
win._append_band("UHF bas", 470.0, 582.0, 200.0)
win._append_band("UHF haut", 582.0, 694.0, 200.0)
win._append_band("VHF", 174.0, 223.0, 100.0)
win._bands_changed()
ids = [b["id"] for b in win.bands]


def cfg_ids(d):
    return [b["id"] for b in win.get_cfg(d)["bands"]]


check("1 seul tinySA : tout sur le 1er", cfg_ids(0) == ids and cfg_ids(1) == [], f"{cfg_ids(0)} / {cfg_ids(1)}")
check("colonne tinySA = 1", win.band_table.item(0, 5).text() == "1", win.band_table.item(0, 5).text())

# ------------------------------------------------------------- activation du 2e
win.dev2_chk.setChecked(True)
win.dev2_addr.setEditText("192.168.1.20")
check("dev2 lu", win.dev2["on"] and win.dev2["addr"] == "192.168.1.20", str(win.dev2))
a, b = cfg_ids(0), cfg_ids(1)
check("2 tinySA : chaque bande sur un seul appareil", sorted(a + b) == sorted(ids) and not set(a) & set(b), f"{a} / {b}")
check("2 tinySA : les deux travaillent", a and b, f"{a} / {b}")
txt = [win.band_table.item(r, 5).text() for r in range(3)]
check("colonne : « Auto → n »", all(t.startswith("Auto → ") for t in txt), str(txt))

# offset propre au 2e
win.dev2_off.setValue(2.5)
win._cfg["offset"] = 1.0
check("offset du 2e = général + le sien", win.get_cfg(1)["offset"] == 3.5 and win.get_cfg(0)["offset"] == 1.0,
      f'{win.get_cfg(0)["offset"]} / {win.get_cfg(1)["offset"]}')
win._cfg["offset"] = 0.0

# choix manuel par double-clic : Auto → 1 → 2 → Auto
step("double-clic colonne", lambda: win.on_band_dbl(2, 5))
check("VHF fixée sur le 1", win.bands[2]["dev"] == 0 and 3 in cfg_ids(0) or ids[2] in cfg_ids(0), str(win.bands[2]))
win.on_band_dbl(2, 5)
check("VHF fixée sur le 2", win.bands[2]["dev"] == 1 and ids[2] in cfg_ids(1))
check("colonne affiche 2", win.band_table.item(2, 5).text() == "2", win.band_table.item(2, 5).text())
win.on_band_dbl(2, 5)
check("retour en Auto", win.bands[2]["dev"] is None)
win.on_band_dbl(0, 1)
check("double-clic hors colonne : rien", win.bands[0].get("dev") is None)

# ------------------------------------------------------------- un appareil décroche
v0 = win.get_ver()
step("tinySA 2 perdu", lambda: win.on_link(1, False))
check("2 perdu : tout passe sur le 1", cfg_ids(0) == ids and cfg_ids(1) == [], f"{cfg_ids(0)} / {cfg_ids(1)}")
check("2 perdu : config relancée", win.get_ver() > v0)
al = win.alarms.active.get(("APPAREIL", -2))
check("alarme APPAREIL critique", al is not None and al["prio"] == 2 and al["name"] == "tinySA 2", str(win.alarms.active))
check("alarme : son critique", sounds == [2], str(sounds))
check("journal : APPAREIL PERDU", win.log_table.item(0, 4).text() == "APPAREIL PERDU" and win.log_table.item(0, 2).text() == "—",
      str([win.log_table.item(0, c).text() for c in range(5)]))
check("colonne : « Auto → 1 » partout", all(win.band_table.item(r, 5).text() == "Auto → 1" for r in range(3)))
step("_alarm_tick", win._alarm_tick)
check("le tick ne nettoie pas l'alarme APPAREIL", ("APPAREIL", -2) in win.alarms.active)
step("refresh_alarms", win.refresh_alarms)
step("alarm_jump sur APPAREIL", lambda: win.alarm_jump(0, 0))
step("tinySA 2 retrouvé", lambda: win.on_link(1, True))
check("retrouvé : alarme terminée", ("APPAREIL", -2) not in win.alarms.active)
check("retrouvé : répartition rétablie", cfg_ids(1) != [], f"{cfg_ids(0)} / {cfg_ids(1)}")
step("tinySA 1 perdu", lambda: win.on_link(0, False))
check("1 perdu : tout passe sur le 2", cfg_ids(1) == ids and cfg_ids(0) == [], f"{cfg_ids(0)} / {cfg_ids(1)}")
win.on_link(0, True)

# ------------------------------------------------------------- cycles
win.on_cycle(1.0, 2, 0)
win.on_cycle(2.0, 1, 1)
check("rythme = le plus lent des deux", win.last_cycle == 2.0, str(win.last_cycle))
check("libellé cycle : nb total de bandes", "3 bande(s)" in win.cycle_lbl.text(), win.cycle_lbl.text())

# ------------------------------------------------------------- zoom live
win._zoom = (500.0, 510.0)
check("zoom : fait par le 1er seulement", cfg_ids(0) == [m.ZOOM_ID] and cfg_ids(1) == [])
win.dev_live = [False, True]
check("zoom : 1er perdu → le 2e zoome", cfg_ids(1) == [m.ZOOM_ID] and cfg_ids(0) == [])
win.dev_live = [True, True]
win._zoom = None

# ------------------------------------------------------------- coupe de bande
win.band_table.currentRow = lambda: 0
step("cut_band", win.cut_band)
check("coupe : 4 bandes", len(win.bands) == 4 and win.bands[0]["stop"] == win.bands[1]["start"] == 526.0,
      str([(b["name"], b["start"], b["stop"]) for b in win.bands]))
check("coupe : noms bas / haut", win.bands[0]["name"].endswith("(bas)") and win.bands[1]["name"].endswith("(haut)"))
a, b = cfg_ids(0), cfg_ids(1)
check("coupe : les moitiés se partagent", len(a) == 2 and len(b) == 2, f"{a} / {b}")
win.band_table.currentRow = lambda: -1
step("cut_band sans sélection", win.cut_band)
check("sans sélection : rien", len(win.bands) == 4)

# ------------------------------------------------------------- config
win.bands[3]["dev"] = 1
data = win._collect_config(full=False)
check("config : dev2 enregistré", data["dev2"] == dict(on=True, addr="192.168.1.20", offset=2.5), str(data["dev2"]))
check("config : appareil de la bande", data["bands"][3]["dev"] == 1)
win2 = step("MainWindow() #2", m.MainWindow)
step("apply_config", lambda: win2._apply_config(data))
check("config relue : 2e tinySA", win2.dev2 == dict(on=True, addr="192.168.1.20", offset=2.5), str(win2.dev2))
check("config relue : bande fixée", win2.bands[3]["dev"] == 1 and win2.bands[0]["dev"] is None,
      str([b.get("dev") for b in win2.bands]))
old = dict(data)
old.pop("dev2")
for bb in old["bands"]:
    bb.pop("dev", None)
win3 = step("MainWindow() #3", m.MainWindow)
step("ancienne config sans 2e tinySA", lambda: win3._apply_config(old))
check("ancienne config : un seul tinySA", not win3.dev2["on"] and all(b["dev"] is None for b in win3.bands))

# ------------------------------------------------------------- port proposé dans la liste
win.dev2_addr.clear()
win.dev2_addr.addItem("COM7  ✔ tinySA", "COM7")
win.dev2_addr._edit = None
win._read_dev2()
check("port de la liste → « COM7 »", win.dev2["addr"] == "COM7", win.dev2["addr"])
win.dev2_addr.setEditText("10.0.0.8:6000")

# ------------------------------------------------------------- démarrage
win.port_combo.addItem("COM3", "COM3")
win.port_combo.setCurrentIndex(win.port_combo.count() - 1)
win.demo_chk.setChecked(False)
win.dev2_addr.setEditText("pc scène")
msgs.clear()
step("toggle_run adresse illisible", win.toggle_run)
check("adresse illisible : refus", msgs and "illisible" in msgs[-1] and not win.workers, str(msgs))
win.dev2_addr.setEditText("COM3")
msgs.clear()
step("toggle_run même port", win.toggle_run)
check("même port : refus", msgs and "même port" in msgs[-1], str(msgs))
win.dev2_addr.setEditText("192.168.1.20:5025")
created = []
real = m.ScanWorker


class Rec(real):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        created.append(self)

    def start(self):
        pass

    def isRunning(self):
        return True


m.ScanWorker = Rec
step("toggle_run 2 appareils", win.toggle_run)
m.ScanWorker = real
check("2 workers", len(created) == 2 and win.workers == created, str(len(created)))
if len(created) == 2:
    check("ports", created[0].port == "COM3" and created[1].port == "socket://192.168.1.20:5025",
          f"{created[0].port} / {created[1].port}")
    check("étiquettes", created[0].label == "tinySA 1" and created[1].label == "tinySA 2")
    check("le 2e attend son relais", created[1].retry_first and not created[0].retry_first)
    check("chacun sa config", created[1].get_cfg()["bands"] == win.get_cfg(1)["bands"])
    check("réglages du 2e verrouillés pendant le scan", win.is_running())
step("update_dev2_label en marche", win.update_dev2_label)
check("libellé 2e : réseau", "réseau 192.168.1.20:5025" in win.dev2_lbl.text(), win.dev2_lbl.text())
step("on_error du 2e : n'arrête pas le 1er", lambda: win.on_error("x", 1))
step("on_info du 2e", lambda: win.on_info("tinySA4_v1.4", 1))
check("info du 2e dans son libellé", "tinySA4_v1.4" in win.dev2_lbl.text(), win.dev2_lbl.text())

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
