"""8.1 : vraie appli hors écran avec DEUX écrans virtuels (Linux) : le labo sur 2 écrans puis changement de mode ne doit
détruire aucun panneau (crash.log de Clément 27/11/2026 : « Internal C++ object already deleted » en boucle), et le
bouton « 🧪 Simuler » lance bien tinySA démo + SDR démo. Sauté sous Windows (pas de plateforme offscreen à 2 écrans)."""
import os, sys, json, tempfile, importlib.util, traceback, time
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
import faulthandler, threading  # noqa: E401,E402


def _stuck():
    """CI : test bloqué -> dire OÙ (pile de chaque fil) et sortir, au lieu d'attendre la limite de 15 min."""
    import traceback as _tb
    main_ = sys._current_frames().get(threading.main_thread().ident)
    where = " > ".join(f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in _tb.extract_stack(main_)[-7:]) \
        if main_ is not None else "?"
    print("Error: test_ecrans bloqué depuis 240 s dans : " + where, flush=True)
    faulthandler.dump_traceback(all_threads=True)
    sys.stdout.flush()
    os._exit(1)


_wd = threading.Timer(240, _stuck)
_wd.daemon = True
_wd.start()
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
problems = []
m.ProblemDialog.exec = lambda self, *a: problems.append(self.windowTitle()) or 0   # jamais de fenêtre bloquante
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
    sys.stdout.flush()


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

# ---- focus, graphe masqué, rien ne bouge en direct (retours de Clément 27/11)
lab = win.open_sdr_lab("cmp")
wait(400)
ps_ = [q for q in lab.panels["cmp"].findChildren(m.pg.PlotWidget) if not q.isHidden()]
g0_ = [q.size().toTuple() for q in ps_]
lab.plot_focus(lab.p_eq)
wait(300)
big_ = lab.p_eq.size().toTuple()
lab.plot_focus(lab.p_eq)
wait(300)
check("focus : le graphe s'agrandit, puis chacun reprend SA place", big_[0] > g0_[ps_.index(lab.p_eq)][0]
      and [q.size().toTuple() for q in ps_] == g0_, f"{g0_} {big_} {[q.size().toTuple() for q in ps_]}")
lab.plot_hide(lab.p_ph)
wait(200)
rb_ = lab.restore_btns["cmp"]
check("graphe masqué : bouton « ↺ 1 graphe(s) masqué(s) » visible dans son panneau", not rb_.isHidden() and "1" in rb_.text(),
      rb_.text())
rb_.click()
wait(300)
check("… et un clic le remet", not lab.p_ph.isHidden() and rb_.isHidden() and not win.sdr_cfg.get("lab_hidden")
      and [q.size().toTuple() for q in ps_] == g0_)
win.screens_off()
win.lab_view(False)
win.simulate(True)
wait(4000)
e = win.sdr_eng
check("🧪 Simuler : tinySA démo + SDR démo, surveillance lancée, mode combiné", win.simulating() and win.is_running()
      and e.running() and win.rf_mode == "both", f"sim={win.simulating()} run={win.is_running()} sdr={e.running()} "
      f"mode={win.rf_mode}")
check("🧪 Simuler : marqué simulé", win.simulated())
e_ = win.sdr_eng
wait(1500)
if e_.audio is not None:
    e_.side.clear()
    time.sleep(1.5)                     # l'interface est bloquée 1,5 s (labo, graphes, 2ᵉ écran…)
    got_ = sum(len(b_) for b_ in list(e_.side)) / (m.LISTEN_RATE * 4.0)
    check("son du SDR : continue d'arriver à la carte son pendant que l'interface est bloquée (vidéo de Clément)",
          got_ >= 1.0, f"{got_:.2f} s de son en 1,5 s")
else:
    check("son du SDR : fil du son démarré", False, "pas de AudioPump")
_lv0 = win.ui_level
win.set_level("expert")
rxd_ = [d_ for d_ in win.docks if d_.objectName() == "dock_sdr_rx"][0]
win.resizeDocks([rxd_], [260], QtCore.Qt.Orientation.Vertical)
win.resizeDocks([rxd_], [420], QtCore.Qt.Orientation.Horizontal)
wait(1200)
sc_ = rxd_.widget()
hs_ = []
long_ = "charge 65 % · saturation 0.0 % · spectre 7 · démod 24 · reste 0 ms/50 (mix 0 · filtre 8 · FM) " * 3
for i_ in range(10):                     # texte d'état qui s'allonge / raccourcit à chaque image (vidéo de Clément)
    sc_.panel.stats.setText(long_ if i_ % 2 else "charge 61 %")
    sc_.panel.row_pil.setVisible(bool(i_ % 3 == 1))
    wait(350)
    hs_.append((sc_.horizontalScrollBar().isVisible(), sc_.verticalScrollBar().value(), sc_.widget().height()))
check("Récepteur : un texte qui s'allonge ne fait plus apparaître de barre horizontale ni sauter le panneau",
      not any(h_[0] for h_ in hs_) and len({h_[1] for h_ in hs_}) == 1
      and all(b_[2] >= a_[2] for a_, b_ in zip(hs_, hs_[1:])), str(hs_))
win.set_level(_lv0)
win.home.refresh(win.home_info())
check("🧪 Simuler : le bouton de l'accueil suit", win.home.sim_btn.isChecked())
win.simulate(False)
wait(2500)
win.lab_view(True, "grid")
wait(500)
win.simulate(True)
wait(2500)
check("🧪 Simuler depuis l'affichage Labo : le labo reste affiché", win.lab_view_on and lab._shown("chain"))
lab.live_frames = 0
lab.chain_live(True)
wait(7000)
check("labo : chaîne complète EN DIRECT sur le SDR démo (graphes mis à jour en continu, marqué simulé)",
      lab.live_frames >= 3 and lab.res_chain.get("real") and lab.badges["chain"].property("prov") == "sim"
      and len(lab.p_const.getPlotItem().listDataItems()) > 0, f"images={lab.live_frames} {lab.ch_res.text()[:120]}")
print("images en direct :", lab.live_frames, "en 7 s", flush=True)
geo_ = lambda: [q.geometry().getRect() for q in lab.panels["chain"].findChildren(m.pg.PlotWidget)]
g_, moved_ = geo_(), 0
for _i in range(8):
    wait(500)
    moved_ += geo_() != g_
    g_ = geo_()
check("en direct : les graphes ne bougent pas d'une image à l'autre", moved_ == 0, f"{moved_} déplacements sur 8")
if os.environ.get("CAPTURE"):
    lab.panels["chain"].grab().save(os.environ["CAPTURE"])
lab.chain_live(False)
n_ = lab.live_frames
wait(1500)
check("labo : en direct arrêté = plus de mise à jour", lab.live_frames == n_)
win.simulate(False)
wait(2500)
check("🧪 Simuler encore : simulation coupée, surveillance arrêtée sans relance ni fenêtre d'erreur",
      not win.simulating() and not win.sdr_cfg.get("demo") and not win.is_running() and not problems, str(problems))
# 8.1 : démarrage précédent planté en rouvrant les autres écrans (crash.log de Clément 27/11) -> pas de 2ᵉ essai
mk_ = m.CFG_PATH.parent / "ecrans_en_cours.txt"
win.screens_cfg = {"on": True, "plan": {"dock_sdr_rx": 1, "dock_sdr_spec": 1}, "full": False, "hosts": {}}
mk_.parent.mkdir(parents=True, exist_ok=True); mk_.write_text("x")
win.screens_restore(); wait(200)
check("témoin de plantage : les autres écrans ne sont pas rouverts, témoin effacé, plan coupé",
      not win.screen_hosts and not mk_.exists() and not win.screens_cfg.get("on"))
win.screens_cfg = {"on": True, "plan": {"dock_sdr_rx": 1, "dock_sdr_spec": 1}, "full": False, "hosts": {}}
win.screens_restore(); wait(300)
check("sans témoin : les écrans sont rouverts et le témoin retiré à la fin", bool(win.screen_hosts) and not mk_.exists())
win.screens_off(); wait(200)
check("aucune exception", not errs, errs[:1])
win._closing = True
try:
    win.close()
except Exception:  # noqa: BLE001
    pass
_wd.cancel()
print("ÉCHECS:", fails)
os._exit(1 if fails else 0)
