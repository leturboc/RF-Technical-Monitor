"""Garde (--garde) : relance l'appli si elle plante ou se fige. Logique pure + vrai processus enfant (un petit script
Python qui joue l'appli : plante, se fige, ou se ferme normalement)."""
import os
import sys
import tempfile
import threading
import time

tmp = tempfile.mkdtemp(prefix="tsm_garde_")
os.environ["APPDATA"] = tmp
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("tsm", os.path.join(HERE, "..", "tinysa_monitor.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

fails = 0


def check(lbl, ok):
    global fails
    fails += not ok
    print(("OK  " if ok else "FAIL"), lbl)


ga = m.guard_action
check("fermée exprès -> stop", ga(0, 3.0, 50.0) == "stop")
check("plantée -> restart", ga(1, 3.0, 50.0) == "restart" and ga(-11, None, 5.0) == "restart")
check("bat encore -> wait", ga(None, 10.0, 500.0) == "wait")
check("figée -> kill", ga(None, 95.0, 500.0) == "kill")
check("démarrage : pas encore de battement -> wait", ga(None, None, 60.0) == "wait")
check("jamais de battement après le délai -> kill", ga(None, None, 200.0) == "kill")
check("relances : 3 s d'habitude", m.guard_delay([0, 100], 200) == 3.0)
check("plante en boucle -> pause 5 min", m.guard_delay([100, 110, 120, 130, 140], 150) == 300.0)
check("vieux plantages oubliés", m.guard_delay([0, 1, 2, 3, 4], 1000) == 3.0)
check("config : garde par défaut", m.festival_cfg_norm({})["guard"] is True
      and m.festival_cfg_norm({"guard": False})["guard"] is False)

# ---- vrai processus : script enfant piloté par un fichier « scénario »
child = os.path.join(tmp, "enfant.py")
runs = os.path.join(tmp, "runs.txt")
with open(child, "w") as f:
    f.write(r'''
import os, sys, time
runs = sys.argv[1]
n = (open(runs).read().count("x") if os.path.exists(runs) else 0) + 1
open(runs, "a").write("x")
open(runs + ".env", "a").write(os.environ.get("TSM_GUARD_RESTART", "?"))
beat = os.environ["TSM_HEARTBEAT"]
plan = sys.argv[2].split(",")[n - 1] if n <= len(sys.argv[2].split(",")) else "ok"
if plan == "crash":
    open(beat, "w").write("1")
    sys.exit(3)
if plan == "hang":
    open(beat, "w").write("1")
    time.sleep(60)                 # ne bat plus : figée
for _ in range(3):
    open(beat, "w").write("1")
    time.sleep(0.3)
sys.exit(0)
''')


def run(plan, **kw):
    for p in (runs, runs + ".env"):
        if os.path.exists(p):
            os.remove(p)
    log = os.path.join(tmp, "garde.log")
    t = time.time()
    n = m.run_guard(cmd=[sys.executable, child, runs, plan], beat=os.path.join(tmp, "beat.txt"), log=log,
                    poll_s=0.2, **kw)
    return n, open(runs).read().count("x"), open(runs + ".env").read(), time.time() - t, open(log, encoding="utf-8").read()


m.guard_delay = lambda starts, now: 0.2           # pas 3 s d'attente dans le test
n, k, env, dt, log = run("crash,crash,ok", hang_s=5, grace_s=10)
check(f"2 plantages -> 2 relances, 3 lancements ({n}, {k})", n == 2 and k == 3)
check(f"1er lancement normal, puis « relancée » ({env})", env == "011")
check("journal de la garde", "plantage" in log and "fermée normalement" in log)
n, k, env, dt, log = run("hang,ok", hang_s=1.5, grace_s=10)
check(f"figée -> fermée de force et relancée ({n}, {k}, {dt:.1f} s)", n == 1 and k == 2 and dt < 20)
check("journal : figée", "figée" in log)
n, k, env, dt, log = run("ok")
check("fermée normalement -> la garde s'arrête", n == 0 and k == 1)
n, k, env, dt, log = run("crash,crash,crash,crash", hang_s=5, grace_s=10, max_runs=3)
check("nombre de lancements limité (test)", k == 3)
stop = threading.Event()
th = threading.Thread(target=lambda: run("hang", hang_s=50, grace_s=50, stop=stop))
th.start()
time.sleep(1.5)
stop.set()
th.join(10)
check("garde arrêtable (l'enfant est fermé)", not th.is_alive())

# battement de cœur côté appli
bp = os.path.join(tmp, "b2.txt")
check("battement écrit", m.guard_beat(bp) and os.path.exists(bp))
os.environ.pop("TSM_HEARTBEAT", None)
check("sans garde : pas de battement", m.guard_beat() is False)

# 7.60.2 : n° de processus dans le battement + fermeture vérifiée (Clément : « l'autre s'est pas arrêtée »)
check("battement : n° de processus de l'appli", m._beat_pid(bp) == os.getpid())
import subprocess as _sp
_child = _sp.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
check("processus vivant détecté", m._pid_alive(_child.pid))
m._kill_pid(_child.pid)
_child.wait(10)
check("fermé par son n° -> plus vivant", not m._pid_alive(_child.pid))
check("_kill_tree a bien subprocess (sous Windows, taskkill ne tournait jamais : NameError avalé)",
      hasattr(m, "subprocess"))
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
