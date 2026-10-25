import io, csv, json, math, os, re, sys, unicodedata, itertools, time, random
import numpy as np

src = open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "tinysa_monitor.py"), encoding="utf-8").read()
a = src.index("# ===== PURE-BEGIN")
b = src.index("# ===== PURE-END")
ns = dict(itertools=itertools, re=re, csv=csv, io=io, math=math, np=np, unicodedata=unicodedata,
          deque=__import__('collections').deque, MIN_PTS=51, HYST=3.0, RBW_LIST=[0.3, 1, 3, 10, 30, 100, 300, 600, 850])
exec(src[a:b], ns)
fails = 0


def check(label, got, exp):
    global fails
    ok = got == exp
    fails += (not ok)
    print(("OK  " if ok else "FAIL"), label, "" if ok else f"-> {got!r} != {exp!r}")


def ok(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra)


im_scan, im_formula, im_pairs, im3_clash, find_free = ns["im_scan"], ns["im_formula"], ns["im_pairs"], ns["im3_clash"], ns["find_free"]

# ---- 2 TX
rows, info = im_scan([500.0, 501.0], (3,), 2)
check("2 TX IM3 : 2 produits", sorted(round(r["f"], 3) for r in rows), [499.0, 502.0])
check("2 TX : ntx=2", {r["ntx"] for r in rows}, {2})
rows, _ = im_scan([500.0, 501.0], (3, 5), 2)
check("2 TX IM3+IM5", sorted((r["order"], round(r["f"], 3)) for r in rows), [(3, 499.0), (3, 502.0), (5, 498.0), (5, 503.0)])
# ---- 3 TX
F3 = [500.0, 503.0, 507.0]
rows, _ = im_scan(F3, (3,), 3)
check("3 TX IM3 : 9 produits", len(rows), 9)
check("3 TX : A+B−C présent", sorted(round(r["f"], 3) for r in rows if r["ntx"] == 3), [496.0, 504.0, 510.0])
rows2, _ = im_scan(F3, (3,), 2)
check("max_tx=2 exclut A+B−C", len(rows2), 6)

# ---- chemin rapide 2 TX == énumération générale (en forçant max_tx=3 puis en filtrant ntx==2)
for n in (4, 7, 12):
    for order in (3, 5, 7):
        F = sorted({round(470 + 7.13 * i * (i + 2) / 3.0 + 0.07 * i, 3) for i in range(n)})
        r2, _ = im_scan(F, (order,), 2, fmin=-1e9, fmax=1e9, limit=10 ** 7)
        rg, _ = im_scan(F, (order,), 3, fmin=-1e9, fmax=1e9, limit=10 ** 7)
        a = sorted((round(r["f"], 6), tuple(r["terms"])) for r in r2)
        b = sorted((round(r["f"], 6), tuple(r["terms"])) for r in rg if r["ntx"] == 2)
        ok(f"2 TX rapide == général (n={n}, ordre {order}, {len(a)} produits)", a == b, f"{len(a)} vs {len(b)}")
tg = [round(470 + 0.37 * i, 3) for i in range(60)]
F = sorted({round(470 + 7.13 * i * (i + 2) / 3.0 + 0.07 * i, 3) for i in range(12)})
r2, _ = im_scan(F, (3, 5), 2, targets=tg, guard=0.2)
rg, _ = im_scan(F, (3, 5), 3, targets=tg, guard=0.2)
a = sorted((round(r["f"], 6), tuple(r["terms"]), r["target"]) for r in r2)
b = sorted((round(r["f"], 6), tuple(r["terms"]), r["target"]) for r in rg if r["ntx"] == 2)
ok(f"2 TX rapide avec cibles == général ({len(a)})", a == b, f"{len(a)} vs {len(b)}")
t0 = time.time()
tx1000 = sorted(set(np.round(np.random.default_rng(4).uniform(470, 694, 1000), 3)))
rr, inf = im_scan(tx1000, (3,), 2, targets=tx1000, guard=0.2)
ok(f"1000 TX en 2 TX (IM3) : {time.time() - t0:.1f} s, {len(rr)} lignes", time.time() - t0 < 10 and not inf["too_big"] and len(rr) > 0, str(inf))
check("im_pairs max_tx=2", im_pairs(1000, 3, 2), 999000)

# ---- comparaison avec une énumération indépendante (vecteurs de coefficients entiers)
def brute(F, order, max_tx):
    n = len(F)
    res = []
    rng = range(-(order // 2 + 1), order // 2 + 2)
    for coef in itertools.product(rng, repeat=n):
        if sum(coef) != 1 or sum(abs(c) for c in coef) != order:
            continue
        if sum(1 for c in coef if c) > max_tx:
            continue
        res.append(sum(c * f for c, f in zip(coef, F)))
    return sorted(round(x, 6) for x in res)


for n, order, mx in ((4, 3, 3), (5, 3, 3), (4, 5, 4), (5, 5, 5), (5, 5, 3), (4, 7, 4)):
    F = [round(470 + random.Random(n * 10 + order).uniform(0, 200), 3) for _ in range(n)]
    F = sorted({round(470 + 9.37 * i * (i + 3) / 2.0 + 0.11 * i, 3) for i in range(n)})
    rows, _ = im_scan(F, (order,), mx, fmin=-1e9, fmax=1e9, limit=10 ** 7)
    got = sorted(round(r["f"], 6) for r in rows)
    ok(f"énumération n={n} ordre {order} max_tx={mx} == brute force ({len(got)})", got == brute(F, order, mx), f"{len(got)} vs {len(brute(F, order, mx))}")

# ---- cibles
rows, _ = im_scan([500.0, 501.0], (3,), 2, targets=[499.05, 520.0], guard=0.1)
check("cible : 1 seul produit retenu", len(rows), 1)
ok("cible : écart ≈ −0.05", abs(rows[0]["delta"] + 0.05) < 1e-9 and rows[0]["target"] == 499.05, str(rows))
check("formule", im_formula(rows[0]["terms"], ["A", "B"]), "2×A − B")
check("formule numérique", im_formula(rows[0]["terms"], freqs=[500.0, 501.0], numeric=True), "2×500.000 − 501.000")
check("formule 3 TX", im_formula([(0, 1), (1, 1), (2, -1)], ["A", "B", "C"]), "A + B − C")
# cible = un émetteur impliqué -> ignoré
rows, _ = im_scan([500.0, 500.4], (3,), 2, targets=[500.4], guard=0.05)
check("émetteur impliqué ignoré comme cible", len(rows), 0)
# origine d'un signal
rows, _ = ns["im_explain"](499.0, [500.0, 501.0, 560.0], (3, 5), 5, 0.05)
ok("origine de 499.0 : 2×500−501 en tête", rows and im_formula(rows[0]["terms"], freqs=[500.0, 501.0, 560.0], numeric=True) == "2×500.000 − 501.000", str(rows[:2]))
# garde-fous
_, info = im_scan([470 + i * 0.5 for i in range(100)], (5,), 5)
ok("trop gros : refusé", info["too_big"] and info["pairs"] == im_pairs(100, 5), str(info))
check("im_pairs", (im_pairs(5, 3), im_pairs(5, 5), im_pairs(40, 5)), (math.comb(6, 2) * 5, math.comb(7, 3) * math.comb(6, 2), math.comb(42, 3) * math.comb(41, 2)))
# charge réaliste : 40 TX, IM3+IM5, 5 TX, 150 cibles
rng = np.random.default_rng(3)
tx = sorted(set(np.round(rng.uniform(470, 600, 40), 3)))
tg = list(np.round(rng.uniform(470, 694, 150), 3))
t0 = time.time()
rows, info = im_scan(tx, (3, 5), 5, targets=tg, guard=0.2)
dt = time.time() - t0
ok(f"charge 40 TX / IM3+IM5 / 5 TX : {dt:.1f} s, {len(rows)} lignes", dt < 25 and len(rows) > 0, str(dt))
print("    ", info)
# 60 TX en IM3 seul, tous les produits
t0 = time.time()
tx60 = sorted(set(np.round(rng.uniform(470, 694, 60), 3)))
rows, info = im_scan(tx60, (3,), 3, targets=tx60, guard=0.2)
ok(f"60 TX IM3 sur lui-même : {time.time() - t0:.1f} s", time.time() - t0 < 10)

# ---- im3_clash <-> im_scan (propriété)
rg = random.Random(5)
agree = 0
tot = 0
for _ in range(60):
    n = rg.randint(2, 7)
    F = sorted({round(rg.uniform(500, 520), 2) for _ in range(n)})
    c = round(rg.uniform(500, 520), 2)
    if min(abs(c - f) for f in F) < 1e-6:
        continue
    g = 0.15
    cl = im3_clash(c, F, g)
    allf = F + [c]
    rows, _ = im_scan(allf, (3,), 3, targets=allf, guard=g)
    ci = len(allf) - 1
    inv = [r for r in rows if any(i == ci for i, _c in r["terms"]) or abs(r["target"] - c) < 1e-9]
    tot += 1
    agree += (len(cl) > 0) == (len(inv) > 0)
ok(f"im3_clash cohérent avec im_scan ({agree}/{tot})", agree == tot)

# ---- find_free
rng = np.random.default_rng(1)
Fm = np.linspace(470, 530, 2401)
Lm = -105 + rng.normal(0, 1.2, Fm.shape)
Lm[(Fm > 495) & (Fm < 505)] = -60          # bloc occupé
ex = [480.0, 483.1, 490.4]
res, diag = find_free(Fm, Lm, 470, 530, ex, n=4, width=0.2, min_sep=0.3, thr=-95, guard=0.2)
ok("find_free : 4 résultats", len(res) == 4, str((res, diag)))
ok("find_free : hors du bloc occupé", all(not (494.9 < r["f"] < 505.1) for r in res), str([r["f"] for r in res]))
ok("find_free : écart minimal respecté", all(min(abs(r["f"] - e) for e in ex) >= 0.3 - 1e-9 for r in res))
allf = ex + [r["f"] for r in res]
rows, _ = im_scan(allf, (3,), 3, targets=allf, guard=0.2)
ok("find_free : aucun IM3 sur l'ensemble final (pour les nouveaux)", not [r for r in rows if any(i >= len(ex) for i, _c in r["terms"]) or r["target"] in allf[len(ex):]], str(rows[:3]))
ok("find_free : diagnostic", diag["grille"] > 100 and diag["bruyantes"] > 100, str(diag))
res0, diag0 = find_free(None, None, 470, 530, ex)
check("find_free sans mesure", res0, [])

# ---- nommage
pl, ml, nf, nr, lw, sl = ns["parse_label"], ns["make_label"], ns["next_free_number"], ns["number_run"], ns["label_words"], ns["suggest_labels"]
check("parse 'HF 12'", pl("HF 12"), ("HF", " ", 12, 0))
check("parse 'MIC03'", pl("MIC03"), ("MIC", "", 3, 2))
check("parse sans numéro", pl("Bolero"), ("Bolero", "", None, 0))
check("parse nombre seul", pl("506"), ("506", "", None, 0))
check("parse 'IEM 0'", pl("IEM 0"), ("IEM", " ", 0, 0))
check("parse 'HF-3'", pl("HF-3"), ("HF", "-", 3, 0))
check("parse fréquence 470.125", pl("470.125"), ("470.125", "", None, 0))
check("parse 'Cor anglais 3'", pl("Cor anglais 3"), ("Cor anglais", " ", 3, 0))
check("numérote avec tiret", ns["number_run"]("HF-3", 2), ["HF-3", "HF-4"])
check("numéro libre avec tiret", nf("HF", ["HF-3"]), 4)
check("make", ml("HF", 5), "HF 5")
check("make largeur 2", ml("MIC", 3, 2, ""), "MIC03")
check("prochain numéro", nf("HF", ["HF 1", "HF 2", "hf 7", "IEM 1", "Chant"]), 8)
check("prochain numéro (aucun)", nf("Bolero", ["HF 1"]), 1)
check("numérotation HF 1 -> HF 5", nr("HF 1", 5), ["HF 1", "HF 2", "HF 3", "HF 4", "HF 5"])
check("numérotation largeur", nr("MIC 08", 3), ["MIC 08", "MIC 09", "MIC 10"])
check("numérotation sans numéro", nr("Intercom", 3), ["Intercom 1", "Intercom 2", "Intercom 3"])
check("numérotation pas 2", nr("IEM 1", 3, 2), ["IEM 1", "IEM 3", "IEM 5"])
check("mots appris", lw(["HF 1", "HF 2", "Basse", "Cor anglais 3", "506.000"]), ["HF", "Cor anglais"])
vocab = ["MIC", "HF", "IEM", "Intercom"]
names = ["HF 1", "HF 2", "IEM 1"]
s1 = sl("hf", vocab, names)
ok("suggestion « hf » : mot, prochain numéro, existants", s1[:2] == ["HF", "HF 3"] and "HF 1" in s1, str(s1))
s2 = sl("", vocab, names)
ok("suggestions vides = tout début de liste", s2[0] == "MIC" and "MIC 1" in s2, str(s2[:4]))
s3 = sl("ntercom", vocab, names)
ok("suggestion « contient »", s3 and s3[0] == "Intercom", str(s3))
cands = ns["name_candidates"](vocab, names)
ok("pas de doublons", len({c.lower() for c in cands}) == len(cands))

# ---- blocs larges (Spectera / WMAS) : les produits sont des bandes
TX, BW = [550.0, 560.0], [8.0, 0.0]          # bloc de 8 MHz centré 550 + un micro à 560
rows, _ = im_scan(TX, (3,), 2, targets=[547.0], guard=0.2)
ok("bloc : sans largeur, 2A−B = 540 ne touche pas 547", not rows)
rows, _ = im_scan(TX, (3,), 2, targets=[547.0], guard=0.2, bws=BW)
ok("bloc : 2×bloc − micro = bande 532–548, touche 547", len(rows) == 1 and abs(rows[0]["f"] - 540.0) < 1e-9
   and abs(rows[0]["hw"] - 8.0) < 1e-9 and abs(rows[0]["gap"] + 1.0) < 1e-9, str(rows))
rows, _ = im_scan(TX, (3,), 2, targets=[549.5], guard=0.2, bws=BW)
ok("bloc : 1,5 MHz au-dessus de la bande → rien", all(r["f"] != 540.0 for r in rows), str(rows))
rows, _ = im_scan(TX, (3,), 2, targets=[573.9], guard=0.2, bws=BW)
ok("bloc : 2×micro − bloc = 566–574 (demi-largeur 4)", len(rows) == 1 and abs(rows[0]["hw"] - 4.0) < 1e-9, str(rows))
rows, _ = im_scan([590.0, 596.5], (3,), 2, targets=[600.0], tbws=[8.0], guard=0.2)
ok("cible = bloc 596–604 : un produit à 603 tombe dedans", any(abs(r["f"] - 603.0) < 1e-9 and r["gap"] < 0 for r in rows), str(rows))
rows, _ = im_scan([590.0, 599.0], (3,), 2, targets=[600.0], tbws=[8.0], guard=0.2)
ok("cible = bloc : un produit à 608 reste dehors", all(abs(r["f"] - 608.0) > 1e-9 for r in rows), str(rows))
# 2 TX rapide = chemin général, avec des blocs
TXw = [520.0, 530.0, 548.0, 561.0, 575.0]
BWw = [8.0, 0.0, 6.0, 0.0, 0.2]
TG = [505.0, 512.0, 538.5, 566.0, 589.0, 600.0]
r2, _ = im_scan(TXw, (3, 5), 2, targets=TG, guard=0.3, bws=BWw, tbws=[0, 8, 0, 6, 0, 0])
rg, _ = im_scan(TXw, (3, 5), 3, targets=TG, guard=0.3, bws=BWw, tbws=[0, 8, 0, 6, 0, 0])
k2 = sorted((round(r["f"], 6), r["order"], round(r["hw"], 6)) for r in r2)
kg = sorted((round(r["f"], 6), r["order"], round(r["hw"], 6)) for r in rg if r["ntx"] == 2)
ok("blocs : 2 TX rapide = chemin général", k2 == kg and len(k2) > 0, f"{len(k2)} / {len(kg)}")
ok("blocs : A+B−C en bandes aussi (3 TX)", any(r["ntx"] == 3 for r in rg))
ok("blocs : tri du plus gênant (chevauchement) au moins gênant", all(
    (a["order"], a["ntx"], a["gap"]) <= (b["order"], b["ntx"], b["gap"]) for a, b in zip(rg, rg[1:])))

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
