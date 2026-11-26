"""8.0.3 : une seule instance. Vrais processus (Qt hors écran) : A s'ouvre, B (2ᵉ copie) doit se fermer tout de suite en
réveillant A ; A fermée de force (verrou d'une appli plantée) : C s'ouvre quand même."""
import os, sys, subprocess, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def ok(label, cond, extra=""):
    global fails
    print(("OK   " if cond else "FAIL ") + label, extra, flush=True)
    fails += 0 if cond else 1


tmp = tempfile.mkdtemp()
env = dict(os.environ, APPDATA=tmp, QT_QPA_PLATFORM="offscreen", TSM_LANG="fr")   # pas HOME : paquets « --user »
env.pop("TSM_MULTI", None)
cmd = [sys.executable, str(ROOT / "tinysa_monitor.py")]
lock = None


def find_lock():
    for p in Path(tmp).rglob("instance.lock"):
        return p
    return None


_errf = open(os.path.join(tmp, "a_stderr.txt"), "w+b")      # fichier, pas un tube (un tube plein bloquerait l'appli)
a = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=_errf)
t0 = time.time()
while time.time() - t0 < 60 and find_lock() is None and a.poll() is None:
    time.sleep(0.5)
if a.poll() is not None:            # l'appli n'a même pas démarré (ex. pyqtgraph / PySide6 absents) : le dire tout de suite
    _errf.seek(0)
    err = (_errf.read() or b"").decode("utf-8", "replace").strip().splitlines()[-6:]
    print("SAUTÉ : l'appli ne démarre pas dans cet environnement (dépendance manquante ?) :\n  " + "\n  ".join(err))
    sys.exit(2)
time.sleep(3)
ok("1re copie ouverte (verrou posé)", find_lock() is not None and a.poll() is None)
t1 = time.time()
b = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    rb = b.wait(timeout=45)
except subprocess.TimeoutExpired:
    b.kill()
    rb = None
ok("2ᵉ copie : se ferme tout de suite (code 0)", rb == 0, f"code {rb} en {time.time() - t1:.1f} s")
ok("1re copie toujours ouverte", a.poll() is None)
a.kill()
a.wait()
time.sleep(0.5)
c = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(12)
ok("après un plantage (verrou d'un processus mort) : l'appli se rouvre", c.poll() is None)
c.kill()
c.wait()
envm = dict(env, TSM_MULTI="1")
d1 = subprocess.Popen(cmd, env=envm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d2 = subprocess.Popen(cmd, env=envm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(12)
ok("TSM_MULTI=1 : plusieurs copies permises (dépannage)", d1.poll() is None and d2.poll() is None)
for p in (d1, d2):
    p.kill()
    p.wait()
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
