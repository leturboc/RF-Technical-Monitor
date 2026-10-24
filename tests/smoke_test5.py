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
check("zoom : fait par le 1er, le 2e surveille toutes les bandes", cfg_ids(0) == [m.ZOOM_ID] and cfg_ids(1) == ids,
      f"{cfg_ids(0)} / {cfg_ids(1)}")
check("zoom : le 2e garde le RBW normal", win.get_cfg(1)["rbw"] == win._cfg["rbw"])
win.dev_live = [False, True]
check("zoom : 1er perdu → le 2e zoome", cfg_ids(1) == [m.ZOOM_ID] and cfg_ids(0) == ids)
win.dev_live = [True, True]
win._zoom = None
# zoom live borné aux bandes (bug : en dézoomant, le scan sortait de 470–694)
lo_b, hi_b = win._band_extent()
win._set_zoom(lo_b - 150.0, hi_b + 200.0)
check("zoom : dézoom au-delà des bandes → reste dans les bandes", win._zoom == (lo_b, hi_b), str(win._zoom))
win._set_zoom(lo_b - 50.0, lo_b - 10.0)
check("zoom : vue entièrement hors bande → bord de bande", win._zoom[0] == lo_b and win._zoom[1] > lo_b, str(win._zoom))
win._set_zoom(lo_b + 1.0, lo_b + 3.0)
check("zoom : dans la bande, inchangé", win._zoom == (lo_b + 1.0, lo_b + 3.0))
with win.lock:
    win._zoom = None

# ------------------------------------------------------------- noms de position et « vu par »
import numpy as np
win.dev1_name.setText("Plateau")
win.dev2_name.setText("FOH")
check("noms de position", win.dev_name(0) == "Plateau" and win.dev_name(1) == "FOH")
win.dev2_name.setText("  ")
check("nom vide → nom par défaut", win.dev_name(1) == "tinySA 2")
win.dev2_name.setText("FOH")
F = np.linspace(470, 582, 561)
win.on_link(1, False)
check("alarme APPAREIL au nom de position", win.alarms.active[("APPAREIL", -2)]["name"] == "FOH"
      and "Plateau reprend" in win.alarms.active[("APPAREIL", -2)]["info"], str(win.alarms.active.get(("APPAREIL", -2))))
win.on_link(1, True)
win.band_src[ids[0]] = 1
L = -100 + 0 * F
L[np.argmin(abs(F - 500.0))] = -40
win._append_watch("Libre X", 500.0, status="Libre")
win.rebuild_watch_table()
win.on_sweep(ids[0], F, L)
check("« vu par » : le tinySA qui couvre la fréquence", win.seen_by(500.0) == "vu par FOH", win.seen_by(500.0))
cf = [a for a in win.alarms.active.values() if a["kind"] == "CONFLIT"]
check("CONFLIT : vu par FOH", cf and cf[0]["info"] == "vu par FOH", str(cf))
lg = [win.log_table.item(r, 6).text() for r in range(win.log_table.rowCount()) if win.log_table.item(r, 4).text() == "CONFLIT"]
check("journal : note « vu par FOH »", lg and lg[0] == "vu par FOH", str(lg))
win.dev2_chk.setChecked(False)
check("un seul tinySA : pas de « vu par »", win.seen_by(500.0) == "")
win.dev2_chk.setChecked(True)
win.watch[:] = [w for w in win.watch if w["name"] != "Libre X"]
for k in [k for k in win.alarms.active if k[0] == "CONFLIT"]:
    win.alarms.clear(k, 0)

# ------------------------------------------------------------- calibration entre les deux tinySA
infos = []
W.QMessageBox.information = staticmethod(lambda p, t, x, *a, **k: infos.append(x))
win.workers = []
step("calibrer sans balayage", win.start_calib)
check("calibration refusée sans balayage", infos and "lance d'abord" in infos[-1] and win._calib is None, str(infos))


class Running:
    def isRunning(self):
        return True

    def requestInterruption(self):
        pass


win.workers = [Running(), Running()]
win.dev2_off.setValue(1.0)
v0 = win.get_ver()
step("start_calib", win.start_calib)
check("calibration lancée", win._calib is not None and win.get_ver() > v0)
c0, c1 = win.get_cfg(0)["bands"], win.get_cfg(1)["bands"]
check("calibration : même bande pour les deux, ids distincts",
      len(c0) == len(c1) == 1 and c0[0]["start_hz"] == c1[0]["start_hz"] and c0[0]["stop_hz"] == c1[0]["stop_hz"]
      and (c0[0]["id"], c1[0]["id"]) == m.CALIB_IDS, f"{c0} / {c1}")
Fc = np.linspace(c0[0]["start_hz"] / 1e6, c0[0]["stop_hz"] / 1e6, c0[0]["n"])
Lc = -100 + 0 * Fc
for fc in Fc[[50, 200, 400]]:
    Lc = np.maximum(Lc, -45 - 40 * ((Fc - fc) / 0.3) ** 2)
nl = len(win.latest)
for k in range(m.CALIB_SWEEPS):
    win.on_sweep(m.CALIB_IDS[0], Fc, Lc)
    win.on_sweep(m.CALIB_IDS[1], Fc, Lc - 2.5)          # le 2e lit 2,5 dB trop bas (offset 1 déjà compris)
check("calibration : balayages hors spectre / mémoire", len(win.latest) == nl and m.CALIB_IDS[0] not in win.latest)
check("calibration terminée", win._calib is None)
check("offset du 2e corrigé (1 + 2,5)", abs(win.dev2_off.value() - 3.5) < 0.05, str(win.dev2_off.value()))
check("résultat affiché dans une fenêtre", infos and "Calibration faite" in infos[-1] and "+2.5 dB" in infos[-1], str(infos[-1:]))
check("retour à la répartition normale", sorted(cfg_ids(0) + cfg_ids(1)) == sorted(ids))
step("start_calib + annuler", win.start_calib)
step("annuler", win.start_calib)
check("calibration annulée par 2e clic", win._calib is None)
win.start_calib()
win.on_link(1, False)
check("appareil perdu : calibration annulée", win._calib is None)
win.on_link(1, True)
win._zoom = (500.0, 510.0)
infos.clear()
win.start_calib()
check("calibration refusée en zoom", win._calib is None and infos and "zoom" in infos[-1])
win._zoom = None
win.dev2_off.setValue(2.5)
win.workers = []

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
check("config relue : noms de position", win2.dev_names == ["Plateau", "FOH"], str(win2.dev_names))
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
    check("étiquettes = noms de position", created[0].label == "Plateau" and created[1].label == "FOH",
          f"{created[0].label} / {created[1].label}")
    check("le 2e attend son relais", created[1].retry_first and not created[0].retry_first)
    check("chacun sa config", created[1].get_cfg()["bands"] == win.get_cfg(1)["bands"])
    check("réglages du 2e verrouillés pendant le scan", win.is_running())
step("update_dev2_label en marche", win.update_dev2_label)
check("libellé 2e : réseau", "réseau 192.168.1.20:5025" in win.dev2_lbl.text(), win.dev2_lbl.text())
step("on_error du 2e : n'arrête pas le 1er", lambda: win.on_error("x", 1))
step("on_info du 2e", lambda: win.on_info("tinySA4_v1.4", 1))
check("info du 2e dans son libellé", "tinySA4_v1.4" in win.dev2_lbl.text(), win.dev2_lbl.text())

# ------------------------------------------------------------- alertes téléphone
import json


class FakeNotifier:
    def __init__(self):
        self.reqs, self.sent, self.last_error = [], 0, ""

    def post(self, req):
        self.reqs.append(req)


win.alarms.reset()
win._notified.clear()
win.notifier = FakeNotifier()
win.notify_cfg.update(mode="crit", service="ntfy", topic="tinysa-test", site="Fest")
for nm, fq in (("HF 1", 470.2), ("Libre 2", 499.0), ("Libre 3", 498.0), ("Libre 4", 497.0)):
    win._append_watch(nm, fq)


def K(kind, f):
    return (kind, int(round(f * 1000)))


win.alarms.raise_(K("ABSENT", 470.2), "ABSENT", "HF 1", 470.2, 2, 100.0, -98.0, "Grande scène › Micros")
win.alarms.raise_(K("CONFLIT", 499.0), "CONFLIT", "Libre 2", 499.0, 1, 100.0, -60.0, "")
step("_alarm_tick (notifs)", win._alarm_tick)
r = win.notifier.reqs
check("critique envoyée, normale non (mode critiques)", len(r) == 1 and r[0][0].endswith("/tinysa-test"), str(r))
check("texte : site + fréquence", r and b"[Fest] 470.200 MHz" in r[0][2], str(r))
win._alarm_tick()
check("pas d'envoi en double", len(win.notifier.reqs) == 1)
win.notify_cfg["mode"] = "all"
win.alarms.raise_(K("CONFLIT", 498.0), "CONFLIT", "Libre 3", 498.0, 1, 100.0, -60.0, "")
win._alarm_tick()
check("mode toutes : normale envoyée, l'ancienne pas renvoyée", len(win.notifier.reqs) == 2, str(len(win.notifier.reqs)))
win.notify_cfg["mode"] = "off"
win.alarms.raise_(K("CONFLIT", 497.0), "CONFLIT", "Libre 4", 497.0, 2, 100.0, -60.0, "")
win._alarm_tick()
check("désactivées : rien", len(win.notifier.reqs) == 2)
win.notify_cfg["mode"] = "crit"
win.on_link(1, False)
win._alarm_tick()
check("appareil perdu : envoyé", any(b"liaison perdue" in q[2] for q in win.notifier.reqs))
n0 = len(win.notifier.reqs)
win.on_link(1, True)
check("appareil retrouvé : envoyé", len(win.notifier.reqs) == n0 + 1 and b"r\xc3\xa9parties" in win.notifier.reqs[-1][2],
      str(win.notifier.reqs[-1:]))
check("ntfy sans canal : erreur claire", "canal" in win.send_notify("t", "b", 2, cfg=dict(win.notify_cfg, topic="")))
check("telegram sans jeton : erreur claire",
      "jeton" in win.send_notify("t", "b", 2, cfg=dict(win.notify_cfg, service="telegram", tg_token="")))
tg = dict(win.notify_cfg, service="telegram", tg_token="1:A", tg_chat="9")
check("telegram : requête", win.send_notify("t", "b", 2, cfg=tg) == "" and "api.telegram.org/bot1:A" in win.notifier.reqs[-1][0])

# ------------------------------------------------------------- page web (état JSON) et config
js = json.loads(win.web_json())
check("état web : toutes les fréquences", len(js["rows"]) == len(win.watch), str(len(js["rows"])))
check("état web : alarmes en cours", any(a["kind"] == "ABSENT" for a in js["alarms"]))
check("état web : titre avec le site", js["title"] == "TinySA Monitor — Fest", js["title"])
check("web désactivée : texte", "désactivée" in win.web_urls_text())
win.notify_cfg["tg_token"] = "SECRET"
win.web_cfg.update(on=True, port=8099)
full, prof = win._collect_config(True), win._collect_config(False)
check("config : alertes et web enregistrées", full["notify"]["tg_token"] == "SECRET" and full["web"]["port"] == 8099)
check("profil partagé : pas de jeton Telegram", "notify" not in prof and prof["web"]["port"] == 8099)
win4 = step("MainWindow() #4", m.MainWindow)
win4.apply_web = lambda: None
step("apply_config alertes", lambda: win4._apply_config(full))
check("config relue : alertes", win4.notify_cfg["mode"] == "crit" and win4.notify_cfg["tg_token"] == "SECRET")
check("config relue : web", win4.web_cfg == dict(on=True, port=8099), str(win4.web_cfg))
bad = dict(full, web=dict(on="oui", port="x"))
win4._apply_config(bad)
check("config abîmée : valeurs ignorées", win4.web_cfg == dict(on=True, port=8099), str(win4.web_cfg))

# ------------------------------------------------------------- blocs Spectera / WMAS
win.workers = []
win.dev2_chk.setChecked(False)
win.watch.clear()
win.alarms.reset()
with win.lock:
    win.bands.clear()
win._append_band("UHF", 600.0, 620.0, 50.0)
win._bands_changed()
bidS = win.bands[0]["id"]
on = next(x["name"] for x in win.statuses if x.get("on"))
free = next(x["name"] for x in win.statuses if x.get("free"))
win._append_watch("Spectera ch 38", 610.0, status=on, bw=8.0)
win._append_watch("Réserve ch 40", 618.0, status=free, bw=4.0)
win._append_watch("HF étroite", 603.0, status=on)
win.rebuild_watch_table()
Fs = np.linspace(600, 620, 401)


def sw(plateau=True, intrus=False, hf=True):
    L = -100 + 0 * Fs
    if plateau:
        L[(Fs >= 606) & (Fs <= 614)] = -65
    if intrus:
        L[np.argmin(abs(Fs - 618.5))] = -50
    if hf:
        L[np.argmin(abs(Fs - 603.0))] = -40
    win.on_sweep(bidS, Fs, L)


ws = {w["name"]: w for w in win.watch}
sw()
check("bloc Spectera émet : occupé (médiane du plateau)", ws["Spectera ch 38"]["state"] == "occ"
      and ws["Spectera ch 38"]["level"] == -65.0, str(ws["Spectera ch 38"]["level"]))
check("bloc réservé vide : libre", ws["Réserve ch 40"]["state"] == "free")
sw(intrus=True)
check("signal intrus dans le bloc réservé : CONFLIT", ws["Réserve ch 40"]["state"] == "occ" and any(
    a["kind"] == "CONFLIT" and a["name"] == "Réserve ch 40" for a in win.alarms.active.values()))
sw(plateau=False)
check("Spectera coupé : bloc libre", ws["Spectera ch 38"]["state"] == "free")
txt = win.watch_table.item(win.watch.index(ws["Spectera ch 38"]), m.C_BAND).text()
check("table : « ▬ bloc 8 MHz »", txt.startswith("▬ bloc 8 MHz"), txt)
win.spec.getPlotItem().vb.xr = [600.0, 620.0]
win.reset_markers()
win._update_markers()
xs = sorted({x for it in win._mk_items.values() if it.x is not None for x in it.x})
check("repère du bloc : ses deux bords", 606.0 in xs and 614.0 in xs and 603.0 in xs, str(xs))
win.scope = [("", None)] if False else None
fp = [x for w in win.watch for x in m.block_points(w["freq"], w.get("bw"))]
check("scan ciblé : couvre tout le bloc", min(fp) <= 606.0 and max(fp) >= 614.0)
win._append_watch("HF dans le bloc", 609.0, status=on)
win.sort_watch()
win.rebuild_watch_table()
win.update_watch_table(force=True)
r_in = next(i for i, w in enumerate(win.watch) if w["name"] == "HF dans le bloc")
txt = win.watch_table.item(r_in, m.C_BAND).text()
check("fréquence dans un bloc : avertissement", txt.startswith("⚠ dans le bloc « Spectera ch 38 »"), txt)
win.watch.pop(r_in)
win.rebuild_watch_table()
ws = {w["name"]: w for w in win.watch}
# ------------------------------------------------------------- sens du signal selon le statut
sw()
r_s = win.watch.index(ws["Spectera ch 38"])
r_r = win.watch.index(ws["Réserve ch 40"])
win.update_watch_table(force=True)
check("doit émettre + signal → « OK »", win.watch_table.item(r_s, m.C_SIG).text() == "OK",
      win.watch_table.item(r_s, m.C_SIG).text())
check("doit rester libre + vide → « ✔ libre »", win.watch_table.item(r_r, m.C_SIG).text() == "✔ libre")
sw(intrus=True)
win.update_watch_table(force=True)
check("doit rester libre + intrus → « ⚠ CONFLIT »", win.watch_table.item(r_r, m.C_SIG).text() == "⚠ CONFLIT")
check("couleur : émetteur = vert, conflit = rouge", win.sig_view(ws["Spectera ch 38"])[1] == "ok"
      and win.sig_view(ws["Réserve ch 40"])[1] == "bad")

# ------------------------------------------------------------- INTERMOD : le brouilleur s'explique par mes émetteurs
win.alarms.reset()
win._append_watch("TX A", 604.0, status=on)
win._append_watch("TX B", 607.0, status=on)
win._append_watch("Libre IM", 601.0, status=free)            # 2×604 − 607 = 601
win._append_watch("Libre autre", 616.5, status=free)
win.sort_watch()
win.rebuild_watch_table()
L = -100 + 0 * Fs
for fx in (604.0, 607.0):
    L[np.argmin(abs(Fs - fx))] = -40
win.on_sweep(bidS, Fs, L)
for fx, lv_ in ((601.0, -60), (616.5, -60)):
    L[np.argmin(abs(Fs - fx))] = lv_
win.on_sweep(bidS, Fs, L)
wi = {w["name"]: w for w in win.watch}
check("signal = produit d'intermod de mes TX → INTERMOD", win.sig_view(wi["Libre IM"])[0] == "⚠ INTERMOD", win.sig_view(wi["Libre IM"])[0])
check("formule de l'intermod", "TX A" in wi["Libre IM"].get("im", "") and "TX B" in wi["Libre IM"]["im"], wi["Libre IM"].get("im"))
check("signal sans lien avec mes TX → CONFLIT", win.sig_view(wi["Libre autre"])[0] == "⚠ CONFLIT")
kinds = {a["name"]: a for a in win.alarms.active.values()}
check("alarme INTERMOD avec la formule", kinds.get("Libre IM", {}).get("kind") == "INTERMOD"
      and "TX A" in kinds["Libre IM"]["info"], str(kinds.get("Libre IM")))
check("alarme CONFLIT pour l'autre", kinds.get("Libre autre", {}).get("kind") == "CONFLIT")
L[np.argmin(abs(Fs - 601.0))] = -100
win.on_sweep(bidS, Fs, L)
check("intermod partie : plus de mention", not wi["Libre IM"].get("im") and win.sig_view(wi["Libre IM"])[0] == "✔ libre")
# mes mots
win.sig_labels = {"ok": "BON", "intermod": "IM !"}
L[np.argmin(abs(Fs - 601.0))] = -60
win.on_sweep(bidS, Fs, L)
check("mes mots : BON / IM !", win.sig_view(wi["TX A"])[0] == "BON" and win.sig_view(wi["Libre IM"])[0] == "IM !")
cfl = win._collect_config(False)
check("config : mes mots", cfl["labels"] == {"ok": "BON", "intermod": "IM !"})
win._apply_config(dict(cfl, labels={"ok": "X" * 50, "inconnu": "z", "free": "  "}))
check("config abîmée : mots filtrés", win.sig_labels == {"ok": "X" * 30}, str(win.sig_labels))
win.sig_labels = {}
win.watch[:] = [w for w in win.watch if w["name"] not in ("TX A", "TX B", "Libre IM", "Libre autre")]
ws = {w["name"]: w for w in win.watch}                  # la config relue a recréé les fréquences
win.rebuild_watch_table()
win.alarms.reset()

# ------------------------------------------------------------- alarme « trop fort »
win.strong_chk.setChecked(True)
win.strong_spin.setValue(-25.0)
win.alarms.reset()
Lf = -100 + 0 * Fs
Lf[np.argmin(abs(Fs - 603.0))] = -12                    # HF étroite collée à l'antenne
win.on_sweep(bidS, Fs, Lf)
fa = [a for a in win.alarms.active.values() if a["kind"] == "TROP FORT"]
check("trop fort : alarme critique", len(fa) == 1 and fa[0]["prio"] == 2 and abs(fa[0]["freq"] - 603.0) < 0.1, str(fa))
check("trop fort : nom de la fréquence proche", fa and fa[0]["name"] == "HF étroite (trop près ?)", str(fa))
win._alarm_tick()
check("trop fort : pas effacée par le nettoyage du tick", any(a["kind"] == "TROP FORT" for a in win.alarms.active.values()))
Lf[np.argmin(abs(Fs - 603.0))] = -26.5                  # redescend, mais dans l'hystérésis
win.on_sweep(bidS, Fs, Lf)
check("trop fort : hystérésis 3 dB (toujours là à -26,5)", any(a["kind"] == "TROP FORT" for a in win.alarms.active.values()))
Lf[np.argmin(abs(Fs - 603.0))] = -40
win.on_sweep(bidS, Fs, Lf)
check("trop fort : fin d'alarme quand ça redescend", not any(a["kind"] == "TROP FORT" for a in win.alarms.active.values()))
win.strong_chk.setChecked(False)
Lf[np.argmin(abs(Fs - 603.0))] = -5
win.on_sweep(bidS, Fs, Lf)
check("trop fort désactivé : pas d'alarme", not any(a["kind"] == "TROP FORT" for a in win.alarms.active.values()))
win.strong_chk.setChecked(True)
win.strong_spin.setValue(-30.0)
cf = win._collect_config(False)
check("config : seuil trop fort", cf["strong_on"] is True and cf["strong_thr"] == -30.0)
doc = m.show_doc(cf, dict(name="x"))
check("show : seuil trop fort dedans", doc["show"].get("strong_thr") == -30.0)

# changement de largeur par le menu
answers = ["Bloc 6 MHz"]
W.QInputDialog.getItem = staticmethod(lambda *a, **k: (answers.pop(0), True))
step("set_block_rows 6 MHz", lambda: win.set_block_rows([win.watch.index(ws["HF étroite"])]))
check("fréquence → bloc 6 MHz", ws["HF étroite"]["bw"] == 6.0)
answers[:] = ["Fréquence simple (pas de bloc)"]
win.set_block_rows([win.watch.index(ws["HF étroite"])])
check("bloc → fréquence simple", ws["HF étroite"]["bw"] == 0.0)
answers[:] = ["Autre largeur…"]
W.QInputDialog.getDouble = staticmethod(lambda *a, **k: (5.0, True))
win.set_block_rows([win.watch.index(ws["HF étroite"])])
check("autre largeur", ws["HF étroite"]["bw"] == 5.0)
# ajout d'un bloc par canal TV
n0 = len(win.watch)
answers[:] = ["CH 38 — 606–614 MHz"]
step("add_block_dialog", win.add_block_dialog)
nb = [w for w in win.watch if w["name"] == "Spectera ch 38" and w is not ws["Spectera ch 38"]]
check("bloc ajouté depuis le canal 38", len(win.watch) == n0 + 1 and nb and nb[0]["freq"] == 610.0 and nb[0]["bw"] == 8.0
      and nb[0]["status"] == on, str([(w["name"], w["freq"], w.get("bw")) for w in win.watch]))
answers[:] = ["Autre : fréquence centrale et largeur…"]
vals = [612.5, 6.0]
W.QInputDialog.getDouble = staticmethod(lambda *a, **k: (vals.pop(0), True))
win.add_block_dialog()
check("bloc libre (centre + largeur)", any(w["freq"] == 612.5 and w["bw"] == 6.0 for w in win.watch))
# config
cfgb = win._collect_config(False)
check("config : largeur enregistrée", any(x.get("bw") == 8.0 for x in cfgb["watch"])
      and all("bw" not in x for x in cfgb["watch"] if x["name"] == "Réserve ch 40" and False))
win5 = step("MainWindow() #5", m.MainWindow)
win5.apply_web = lambda: None
win5._apply_config(cfgb)
check("config relue : blocs", sorted(w["bw"] for w in win5.watch) == sorted(w["bw"] for w in win.watch),
      str([w["bw"] for w in win5.watch]))
check("préréglages Spectera", sum(1 for p in m.BAND_PRESETS if p[0].startswith("Spectera")) == 4)

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
