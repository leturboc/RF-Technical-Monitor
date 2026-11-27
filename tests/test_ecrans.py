"""8.1 : vraie appli hors écran avec DEUX écrans virtuels (Linux) : le labo sur 2 écrans puis changement de mode ne doit
détruire aucun panneau (crash.log de Clément 27/11/2026 : « Internal C++ object already deleted » en boucle), et le
bouton « 🧪 Simuler » lance bien tinySA démo + SDR démo. Sauté sous Windows (pas de plateforme offscreen à 2 écrans)."""
import os, sys, json, tempfile, importlib.util, traceback
if sys.platform == "win32":
    print("sauté sous Windows\nÉCHECS: 0")
    sys.exit(0)
tmp = tempfile.mkdtemp(prefix="tsm_ecrans_")
cfgf = os.path.join(tmp, "ecrans.json")
json.dump({"synchronousWindowSystemEvents": False, "windowFrameMargins": False, "screens": [
    {"name": "S1", "x": 0, "y": 0, "width": 1920, "height": 1080, "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1},
    {"name": "S2", "x": 1920, "y": 0, "width": 1920, "height": 1080, "logicalDpi": 96, "logicalBaseDpi": 96, "dpr": 1}]},
    open(cfgf, "w"))
os.environ["QT_QPA_PLATFORM"] = "offscreen:configfile=" + cfgf
os.environ["APPDATA"] = tmp
os.environ["TSM_NO_BROWSER"] = "1"
errs = []
sys.excepthook = lambda t, v, tb: errs.append("".join(traceback.format_exception(t, v, tb)))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
spec = importlib.util.spec_from_file_location("tsm", os.path.join(ROOT, "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
from PySide6 import QtWidgets, QtCore  # noqa: E402
import shiboken6  # noqa: E402
app = QtWidgets.QApplication(sys.argv)
m.install_gc_main_thread(app)
win = m.MainWindow()
win.show()
fails = 0


def wait(ms):
    lp = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, lp.quit)
    lp.exec()


def check(label, cond, extra=""):
    global fails
    fails += not cond
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra, flush=True)


def dead():
    return [k for k, w in win._sdrlab.panels.items() if not shiboken6.isValid(w)]


wait(800)
check("deux écrans vus", len(QtWidgets.QApplication.screens()) == 2)
win.open_sdr_lab(0)
wait(300)
for seq in (("dual", "mode:tiny"), ("dual", "close"), ("dual", "grid", "mode:sdr"), ("dual", "off", "dual", "tabs"),
            ("dual", "mode:both", "dual", "viewoff")):
    for st in seq:
        if st in ("dual", "grid", "tabs"):
            win.lab_view(True, st)
        elif st == "viewoff":
            win.lab_view(False)
        elif st.startswith("mode:"):
            getattr(win, "rf_mode_" + st[5:])()
        elif st == "close":
            for h in list(win.screen_hosts.values()):
                h.close()
        elif st == "off":
            win.screens_off()
        wait(500)
    check("labo sur 2 écrans : " + " → ".join(seq) + " : aucun panneau détruit", not dead() and not errs,
          f"{dead()} {errs[:1]}")
check("labo : 2ᵉ fenêtre d'écran refermée à la fin", not win.screen_hosts or win.lab_view_on)
win.screens_off()
win.lab_view(False)
win.simulate(True)
wait(4000)
e = win.sdr_eng
check("🧪 Simuler : tinySA démo + SDR démo, surveillance lancée, mode combiné", win.simulating() and win.is_running()
      and e.running() and win.rf_mode == "both", f"sim={win.simulating()} run={win.is_running()} sdr={e.running()} "
      f"mode={win.rf_mode}")
check("🧪 Simuler : marqué simulé", win.simulated())
win.home.refresh(win.home_info())
check("🧪 Simuler : le bouton de l'accueil suit", win.home.sim_btn.isChecked())
win.simulate(False)
wait(2500)
check("🧪 Simuler encore : simulation coupée", not win.simulating() and not win.sdr_cfg.get("demo"))
check("aucune exception", not errs, errs[:1])
win._closing = True
try:
    win.close()
except Exception:  # noqa: BLE001
    pass
print("ÉCHECS:", fails)
os._exit(1 if fails else 0)
