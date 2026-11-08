"""Test d'endurance : la VRAIE appli (PySide6 hors écran) tourne longtemps en démo, comme une nuit de festival, et on
relève la mémoire, le processeur et la taille des réserves internes. Sert à trouver les fuites (ce qui grossit sans
s'arrêter) avant qu'elles ne fassent tomber l'appli à 3 h du matin.

    python tests/endurance.py [minutes]          (défaut 60 ; relevés toutes les 30 s dans endurance.csv)

Charge : 4 tinySA simulés, session enregistrée, page web avec 3 « téléphones » (liste, spectre, page Tech) qui
interrogent le PC chaque seconde, changement d'état 📸 toutes les 2 min, acquittement des alarmes, zoom de temps en
temps. Verdict à la fin : la mémoire doit se stabiliser (croissance < 15 Mo / h après la mise en route)."""
import csv
import gc
import http.cookiejar
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
tmp = tempfile.mkdtemp(prefix="tsm_endu_")
os.environ["APPDATA"] = tmp
os.environ["HOME"] = tmp
HERE = os.path.dirname(os.path.abspath(__file__))
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
OUT = os.environ.get("ENDURANCE_CSV", os.path.join(HERE, "endurance.csv"))

import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("tsm", os.path.join(HERE, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
sys.modules["tsm"] = m
spec.loader.exec_module(m)
from PySide6 import QtCore, QtWidgets  # noqa: E402

errors = []
sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
app = QtWidgets.QApplication(sys.argv)
_gct = m.install_gc_main_thread(app, 500)
for k in ("warning", "information", "critical", "question"):
    setattr(QtWidgets.QMessageBox, k, staticmethod(lambda *a, **k_: QtWidgets.QMessageBox.StandardButton.Yes))


def wait(ms):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec()


def rss_mb():
    try:
        with open("/proc/self/status") as f:
            for ln in f:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) / 1024.0
    except OSError:
        pass
    try:                                           # Windows
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = PMC()
        c.cb = ctypes.sizeof(c)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 1048576.0
    except Exception:  # noqa: BLE001
        return float("nan")


win = m.MainWindow()
win.log_dir = m.Path(tmp) / "journaux"
win.resize(1600, 950)
win.show()
wait(800)
for i, f in enumerate([470.2 + 4.1 * k for k in range(24)]):
    st = "Libre" if i % 6 == 5 else "En service"
    win._append_watch(f"HF {i + 1}", f, status=st, scene=("Grande scène" if i < 12 else "Club"),
                      group=("Micros" if i % 2 else "IEM"))
win.sort_watch()
win.rebuild_tree()
win.rebuild_watch_table()
win.add_band("UHF bas", 470.0, 560.0, 50.0)
win.add_band("UHF haut", 560.0, 694.0, 50.0)
win.demo_chk.setChecked(True)
win.dev2_chk.setChecked(True)
win.dev2_addr.setEditText("192.168.1.20:5025")
win.devx = m.devx_norm([dict(addr="COM8", name="Club"), dict(addr="COM9", name="Volant")])
win._devx_fill()
win._dev2_changed()
win.session_cfg.update(dir=os.path.join(tmp, "sessions"), ask=False, rec=True)
win.new_state("Tout le monde")
win.states.append(dict(name="Grande scène", keys=[int(round(w["freq"] * 1000)) for w in win.watch
                                                  if w["scene"] == "Grande scène"]))
win.web_cfg.update(on=True, port=0, pin="2468", tech="endurance!", tech_approve=False)
win.web_cfg["views"] = m.web_views_norm({"tech": True, "terrain": True})
win.apply_web()
wait(500)
win.toggle_run()
wait(3000)
base = f"http://127.0.0.1:{win.web.port}" if win.web else None
stop = threading.Event()
web_n, web_err = [0], [0]


def phone(name, view, extra=()):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def post(path, obj):
        return op.open(urllib.request.Request(base + path, data=json.dumps(obj).encode(),
                                              headers={"Content-Type": "application/json"}, method="POST"), timeout=5)
    try:
        post("/connexion", dict(name=name, password=""))
        if view == "tech":
            post("/tech/login", dict(password="endurance!"))
    except Exception:  # noqa: BLE001
        web_err[0] += 1
    while not stop.is_set():
        try:
            op.open(f"{base}/etat.json?v={view}", timeout=5).read()
            for p in extra:
                op.open(base + p, timeout=5).read()
            web_n[0] += 1
        except Exception:  # noqa: BLE001
            web_err[0] += 1
        stop.wait(1.0)


if base:
    for n, v, ex in (("Régie", "liste", ()), ("Plateau", "spectre", ("/spectre.json",)), ("Tech", "tech", ("/tech.json",))):
        threading.Thread(target=phone, args=(n, v, ex), daemon=True).start()

rows, t0 = [], time.time()
cpu0, wall0 = time.process_time(), time.time()
end = t0 + MINUTES * 60.0
k, next_state, next_zoom = 0, t0 + 120, t0 + 300
print(f"Endurance : {MINUTES:g} min, 4 tinySA simulés, page web, relevés toutes les 30 s", flush=True)
while time.time() < end:
    wait(30000)
    k += 1
    now = time.time()
    if now >= next_state:
        win.apply_state("Grande scène" if win.state_cur != "Grande scène" else "Tout le monde")
        win.alarms.ack_all()
        next_state = now + 120
    if now >= next_zoom:
        try:
            win.zoom_on(0)
            wait(8000)
            win.toggle_zoom(False)
            win.zoom_btn.setChecked(False)
        except Exception as e:  # noqa: BLE001
            errors.append(f"zoom : {e}")
        next_zoom = now + 600
    cpu = time.process_time()
    pct = 100.0 * (cpu - cpu0) / max(1e-6, now - wall0)
    cpu0, wall0 = cpu, now
    r = dict(minute=round((now - t0) / 60.0, 1), rss_mb=round(rss_mb(), 1), cpu_pct=round(pct, 1),
             objets=len(gc.get_objects()), journal=win.log_table.rowCount(), alarmes_finies=len(win.alarms.done),
             historique=sum(len(v) for v in win.history.values()), store_mo=round(win.store.bytes / 1e6, 1),
             div=len(win.div_buf), sites=len(win.site_mh), clients=len(win.web.client_list()) if win.web else 0,
             web=web_n[0], web_err=web_err[0], running=int(win.is_running()), erreurs=len(errors))
    rows.append(r)
    print(" · ".join(f"{a}={b}" for a, b in r.items()), flush=True)
    with open(OUT, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(r))
        wr.writeheader()
        wr.writerows(rows)
stop.set()
win.toggle_run()
wait(3000)
# verdict : pente de la mémoire après la mise en route. La relecture garde 30 min de balayages en mémoire
# (SweepStore, voulu) : on juge la mémoire HORS relecture (rss − store), et la mémoire brute après 35 min.


def pente(pts):
    if len(pts) < 3:
        return 0.0
    xs, ys = [p[0] / 60.0 for p in pts], [p[1] for p in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(1e-9, sum((x - mx) ** 2 for x in xs))


warm = min(5.0, MINUTES / 3)
slope = pente([(r["minute"], r["rss_mb"] - r["store_mo"]) for r in rows if r["minute"] >= warm])
raw = pente([(r["minute"], r["rss_mb"]) for r in rows if r["minute"] >= 35.0])
fails = 0
checks = [(f"mémoire hors relecture stable (pente {slope:+.1f} Mo/h < 15)", slope < 15.0)]
if MINUTES >= 60:
    checks.append((f"mémoire totale stable après 35 min (pente {raw:+.1f} Mo/h < 15)", raw < 15.0))
for lbl, ok in checks + [
                (f"toujours en surveillance ({sum(r['running'] for r in rows)}/{len(rows)} relevés)",
                 all(r["running"] for r in rows)),
                (f"page web : {web_n[0]} réponses, {web_err[0]} erreurs", web_err[0] <= max(3, web_n[0] // 200)),
                (f"aucune exception ({len(errors)})", not errors)]:
    fails += not ok
    print(("OK  " if ok else "FAIL"), lbl, flush=True)
for e in errors[:10]:
    print("   ", e)
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
