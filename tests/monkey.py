"""Test du singe : la VRAIE appli (hors écran, mode démo) pendant que le script clique au hasard sur tout ce qui est
cliquable (boutons, menus, menus du clic droit, fenêtres qui s'ouvrent…), des milliers de fois. Chaque exception est
notée avec l'endroit du code : c'est la façon la plus rapide de trouver des bugs qu'aucun test écrit à la main ne
prévoit (enchaînements bizarres, listes vides, fenêtre ouverte deux fois…).

    python tests/monkey.py [nombre_d_actions] [graine]        (défaut 1500 actions, graine 1)

Les fichiers, les boîtes de saisie, les relances de l'appli et le navigateur sont neutralisés."""
import faulthandler
import os
import random
import sys
import tempfile
import time
import traceback

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="tsm_monkey_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
rnd = random.Random(SEED)
faulthandler.enable()
faulthandler.dump_traceback_later(90, repeat=True)       # bloqué ? on voit où

errors = {}
current = [""]


def hook(t, v, tb):
    frames = traceback.extract_tb(tb)
    where = next((f"{f.name}:{f.lineno}" for f in reversed(frames) if f.filename.endswith("tinysa_monitor.py")),
                 frames[-1].name if frames else "?")
    key = (t.__name__, where)
    if key not in errors:
        errors[key] = (str(v), current[0], "".join(traceback.format_exception(t, v, tb))[-1800:])
        print(f"!!! {t.__name__} @ {where} : {v}   (après : {current[0]})", flush=True)


sys.excepthook = hook
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("tsm", os.path.join(HERE, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
W = QtWidgets
app = W.QApplication(sys.argv)
_gct = m.install_gc_main_thread(app, 500)


def wait(ms):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()


# ---- tout ce qui bloquerait ou sortirait de la sandbox est neutralisé
for k in ("warning", "information", "critical", "question"):
    setattr(W.QMessageBox, k, staticmethod(lambda *a, **k_: rnd.choice(
        [W.QMessageBox.StandardButton.Yes, W.QMessageBox.StandardButton.No, W.QMessageBox.StandardButton.Cancel])))
W.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
W.QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
W.QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
W.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
W.QInputDialog.getText = staticmethod(lambda *a, **k: (rnd.choice(["Test", "", "Scène 9"]), rnd.random() < 0.6))
W.QInputDialog.getDouble = staticmethod(lambda *a, **k: (rnd.choice([606.5, 0.0, 470.0, 1e9]), rnd.random() < 0.6))
W.QInputDialog.getInt = staticmethod(lambda *a, **k: (rnd.choice([1, 0, 5]), rnd.random() < 0.6))
W.QInputDialog.getItem = staticmethod(lambda p, t, l, items, *a, **k: (rnd.choice(list(items) or [""]),
                                                                        rnd.random() < 0.6))
W.QInputDialog.getMultiLineText = staticmethod(lambda *a, **k: ("HF X;620.125\nHF Y;621.250", rnd.random() < 0.5))
W.QColorDialog.getColor = staticmethod(lambda *a, **k: QtGui.QColor("#ff8800"))
QtGui.QDesktopServices.openUrl = staticmethod(lambda *a, **k: True)
m.restart_app = lambda: False
m.MainWindow.relaunch_guarded = lambda self: False
m.MainWindow.set_windows_startup = lambda self, on: ""
depth = [0]


def fake_exec(self, *a, **k):
    """Fenêtre modale : on l'affiche, on clique 0 à 3 boutons au hasard dedans, puis on la ferme (OK ou Annuler)."""
    if depth[0] > 2:
        return 0
    depth[0] += 1
    try:
        self.show()
        wait(30)
        for _ in range(rnd.randint(0, 3)):
            bs = [b for b in self.findChildren(W.QAbstractButton) if b.isVisible() and b.isEnabled()
                  and getattr(b, "menu", lambda: None)() is None]
            if not bs or not self.isVisible():
                break
            b = rnd.choice(bs)
            current[0] = f"{type(self).__name__} › {b.text()[:40]!r}"
            b.click()
            wait(20)
        if self.isVisible():
            if rnd.random() < 0.3:
                self.accept()
                return 1
            self.reject()
        return 0
    finally:
        depth[0] -= 1


W.QDialog.exec = fake_exec


class _Box(W.QMessageBox):                 # QMessageBox(...).exec() : l'affectation sur la classe C++ ne suffit pas
    def exec(self, *a, **k):
        return fake_exec(self)


for k in ("warning", "information", "critical", "question"):
    setattr(_Box, k, getattr(W.QMessageBox, k))
W.QMessageBox = _Box


def pick_action(menu, d=0):
    acts = [a for a in menu.actions() if a.isEnabled() and not a.isSeparator() and a.isVisible()]
    if not acts or d > 3:
        return None
    a = rnd.choice(acts)
    if a.menu() is not None:
        a.menu().aboutToShow.emit()
        return pick_action(a.menu(), d + 1)
    return a


def fake_menu_exec(self, *a, **k):
    self.aboutToShow.emit()
    return pick_action(self)


class _Menu(W.QMenu):                      # idem pour QMenu(...).exec(pos) : sinon ça bloque hors écran
    def exec(self, *a, **k):
        return fake_menu_exec(self)


W.QMenu = _Menu

# ---- l'appli, avec de quoi faire
win = m.MainWindow()
win.log_dir = m.Path(tmp) / "journaux"
win.resize(1500, 900)
win.show()
wait(500)


def seed():
    if len(win.watch) >= 6:
        return
    for i, f in enumerate([470.2 + 3.7 * k for k in range(14)]):
        st = "Libre" if i % 5 == 4 else "En service"
        win._append_watch(f"HF {i + 1}", f, status=st, scene=("Grande scène" if i < 7 else "Club"),
                          group=("Micros" if i % 2 else "IEM"))
    win.sort_watch()
    win.rebuild_tree()
    win.rebuild_watch_table()


seed()
win.demo_chk.setChecked(True)
win.session_cfg.update(ask=False, rec=False)
win.toggle_run()
wait(2500)
SKIP = ("Quitter", "Exit", "Fermer l'appli")


def targets():
    out = []
    for tl in app.topLevelWidgets():
        if not tl.isVisible():
            continue
        for b in tl.findChildren(W.QAbstractButton):
            if not (b.isVisible() and b.isEnabled()) or any(s in b.text() for s in SKIP):
                continue
            mn = b.menu() if hasattr(b, "menu") else None
            out.append(("menu", mn, b) if mn is not None else ("btn", b, None))
    for mn in (win.more_menu,):
        out.append(("menu", mn, None))
    for _ in range(4):                        # clics droits (liste, arbre, journal)
        out.append(("ctx", None, None))
    for name in ("step_monitor", "toggle_run", "open_show_mode", "open_ready", "undo", "redo", "toggle_muted_sel",
                 "open_wall", "ack_all_alarms"):
        out.append(("call", name, None))
    return out


t0 = time.time()
for i in range(N):
    if i % 200 == 0:
        seed()
        print(f"… {i}/{N} actions, {len(errors)} bug(s) distinct(s), {time.time() - t0:.0f} s", flush=True)
    ts = targets()
    kind, a, b = rnd.choice(ts)
    try:
        if kind == "btn":
            current[0] = f"bouton {a.text()[:40]!r} ({type(a.window()).__name__})"
            a.click()
        elif kind == "menu":
            a.aboutToShow.emit()
            act = pick_action(a)
            if act is not None:
                current[0] = f"menu {act.text()[:50]!r}"
                act.trigger()
        elif kind == "ctx":
            which = rnd.choice(["watch", "tree", "log"])
            if which == "watch" and win.watch_table.rowCount():
                r = rnd.randrange(win.watch_table.rowCount())
                win.watch_table.selectRow(r)
                current[0] = f"clic droit liste ligne {r}"
                win.watch_menu(win.watch_table.visualItemRect(win.watch_table.item(r, 0)).center())
            elif which == "tree" and win.layer_tree.topLevelItemCount():
                it = win.layer_tree.topLevelItem(rnd.randrange(win.layer_tree.topLevelItemCount()))
                win.layer_tree.setCurrentItem(it)
                current[0] = "clic droit arbre"
                win.layer_menu(win.layer_tree.visualItemRect(it).center())
            elif which == "log" and win.log_table.rowCount():
                r = rnd.randrange(win.log_table.rowCount())
                win.log_table.selectRow(r)
                current[0] = "clic droit journal"
                win.log_menu(win.log_table.visualItemRect(win.log_table.item(r, 0)).center())
        elif kind == "call":
            current[0] = f"appel {a}()"
            getattr(win, a)()
    except Exception:  # noqa: BLE001
        hook(*sys.exc_info())
    wait(rnd.choice([5, 20, 60]))
    for tl in app.topLevelWidgets():          # pas plus de 6 fenêtres ouvertes à la fois
        if tl is not win and tl.isVisible() and rnd.random() < 0.15:
            tl.close()

faulthandler.cancel_dump_traceback_later()
print(f"\n{N} actions en {time.time() - t0:.0f} s · {len(errors)} bug(s) distinct(s)")
for (t, where), (msg, after, tb) in errors.items():
    print(f"\n=== {t} @ {where} : {msg}\n    après : {after}\n{tb}")
print("\nÉCHECS:", len(errors))
os._exit(1 if errors else 0)
