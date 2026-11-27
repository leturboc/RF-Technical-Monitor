"""8.1 étape 3 : lance toute la batterie de tests, plus vite qu'à la main, et note la durée de chacun.

    python tests/run_all.py              tout (tests rapides en parallèle, puis gui_reel et gui_en)
    python tests/run_all.py --fast       sans gui_reel ni gui_en (≈ quelques minutes)
    python tests/run_all.py --jobs 2     nombre de tests rapides lancés en même temps (défaut : processeurs − 1)

Les tests sensibles au temps (vrais fils, réseau, processus surveillés, interface réelle) tournent seuls, après les
autres, pour ne pas échouer à cause d'un processeur chargé. Résumé à la fin ; code de sortie 1 si un test échoue.
Les sorties complètes sont dans tests/sorties/<test>.log."""
import os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "sorties")
PARALLEL = ["test_v7", "test_im", "test_plan", "smoke_test", "smoke_test2", "smoke_test3", "smoke_test4",
            "smoke_test5", "smoke_test6", "test_alertes", "test_i18n", "test_relais_pi", "test_sdr", "check_names"]
SERIAL = ["test_garde", "test_sdr_qt", "test_reseau", "test_reseau_qt", "test_instance"]   # sensibles au temps
GUI = [("gui_reel", ["tests/captures"]), ("gui_en", ["tests/captures/en"])]


def run(name, args=(), timeout=2400):
    path = os.path.join(HERE, name + ".py")
    if not os.path.isfile(path):
        return name, None, 0.0, "absent"
    env = dict(os.environ, TSM_NO_BROWSER="1")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-u", path] + list(args), cwd=ROOT, env=env, capture_output=True,
                           text=True, timeout=timeout)
        out, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, code = (e.stdout or "") if isinstance(e.stdout, str) else "", "temps dépassé"
    dt = time.time() - t0
    with open(os.path.join(OUT, name + ".log"), "w", encoding="utf-8") as f:
        f.write(out)
    last = [ln for ln in out.splitlines() if "ÉCHECS" in ln or "FAILS" in ln]
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL ")]
    ok = code == 0 and (not last or last[-1].strip().endswith(" 0")) and not fails and "EXCEPTION" not in out
    return name, ok, dt, (last[-1].strip() if last else f"code {code}") + (f" · {len(fails)} FAIL" if fails else "")


def main():
    os.makedirs(OUT, exist_ok=True)
    fast = "--fast" in sys.argv
    jobs = max(1, (os.cpu_count() or 2) - 1)
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
    t0 = time.time()
    res = []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for r in ex.map(run, PARALLEL):
            res.append(r)
            print(f"{'OK  ' if r[1] else 'FAIL'} {r[0]:<16} {r[2]:6.1f} s  {r[3]}", flush=True)
    for name in SERIAL:
        r = run(name)
        res.append(r)
        print(f"{'OK  ' if r[1] else 'FAIL'} {r[0]:<16} {r[2]:6.1f} s  {r[3]}", flush=True)
    if not fast:
        for name, args in GUI:
            r = run(name, args)
            res.append(r)
            print(f"{'OK  ' if r[1] else 'FAIL'} {r[0]:<16} {r[2]:6.1f} s  {r[3]}", flush=True)
    bad = [r for r in res if r[1] is False]
    print(f"\n{len(res)} tests en {time.time() - t0:.0f} s · {len(bad)} en échec" + (
        " : " + ", ".join(r[0] for r in bad) if bad else ""))
    print("ÉCHECS:", len(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
