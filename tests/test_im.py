import io, csv, json, math, os, re, sys, unicodedata, itertools, time, random
import numpy as np

src = __import__("_src").source()
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
# cas de Clément (7.14) : bande FM pleine, 30 stations déclarées « en service »
fm = [87.9, 88.6, 89.1, 89.9, 90.6, 91.3, 91.8, 92.5, 93.2, 93.7, 94.3, 95.0, 95.6, 96.4, 96.9, 97.975, 98.425,
      98.9, 99.825, 100.275, 101.5, 102.2, 102.625, 103.075, 103.4, 104.125, 104.6, 104.95, 105.4, 106.7]
Ff = np.linspace(87.5, 108.0, 1401)
Lf = -100 + rng.normal(0, 1.0, Ff.shape)
for f0 in fm:
    Lf[np.abs(Ff - f0) < 0.09] = -70
rf, df = find_free(Ff, Lf, 87.5, 108.0, fm, n=2, width=0.2, min_sep=0.3, thr=-85, guard=0.2, guard3=0.1)
ok("secours FM (30 émetteurs, 3 TX) : des « moins mauvaises » proposées au lieu de rien",
   len(rf) == 2 and df["intermod"] > 0, str((rf, df)))
ok("secours : les moins mauvaises disent ce qui cloche", all(r.get("warn") for r in rf[len(rf) - df["alternatives"]:]), str(rf))
ok("secours FM : avec 30 émetteurs même le 2 TX recouvre tout -> moins mauvaises",
   find_free(Ff, Lf, 87.5, 108.0, fm, n=2, width=0.2, min_sep=0.3, thr=-85, guard=0.1, im3=False)[1]["alternatives"] == 2)
rf2, df2 = find_free(Ff, Lf, 87.5, 108.0, fm, n=2, width=0.2, min_sep=0.3, thr=-85, guard=0.1, emitters=fm[::4])
ok("secours FM, 8 émetteurs (plan réaliste) : de vraies fréquences libres", len(rf2) == 2 and df2["alternatives"] == 0,
   str((rf2, df2)))
rf3, df3 = find_free(Ff, Lf, 87.5, 108.0, fm, n=2, width=0.2, min_sep=0.3, thr=-85, guard=0.2, emitters=[])
ok("secours : réserves libres = pas des émetteurs (aucun IM compté)", df3["intermod"] == 0 and len(rf3) == 2
   and df3["alternatives"] == 0, str(df3))
for r in rf2:
    ok(f"secours FM {r['f']:.3f} : à ≥ 300 kHz des stations", min(abs(r["f"] - e) for e in fm) >= 0.3 - 1e-9)
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

# ---- tolérances par type de produit (façon EazyRF)
ok("classes de produits", [ns["im_class"](3, 2), ns["im_class"](3, 3), ns["im_class"](5, 2), ns["im_class"](5, 4)]
   == ["2tx3", "3tx3", "5", "5"])
EZ = {"2tx3": 0.100, "3tx3": 0.050, "5": 0.050, "7": 0.050}      # tolérances EazyRF complètes (2 / 3 TX + 5ᵉ)
_P = ns["IM_TOL_PRESETS"]
ok("règles : « Standard » d'abord = 2 TX 100 / 3 TX 50 kHz", _P[0][0].startswith("🟢 Standard")
   and _P[0][1]["3tx3"] == 0.05 and _P[0][1]["5"] == 0 and _P[0][1]["2tx3"] == 0.1)
ok("règles : « Simple » = 2A − B seulement", _P[1][1]["3tx3"] == 0 and _P[1][1]["5"] == 0 and _P[1][1]["2tx3"] == 0.1)
ok("règles : chaque niveau est expliqué", all(len(w_) > 40 for _t, _d, w_ in _P))
ok("règles : phrase « on vérifie »", ns["im_rules_text"](_P[1][1], 0.3) ==
   "On vérifie : écart d'au moins 300 kHz entre deux porteuses · 2A − B (2 émetteurs) à moins de 100 kHz d'une "
   "fréquence · A + B − C (3 émetteurs) : non vérifié · 5ᵉ ordre : non vérifié")
ok("règles : phrase avec le filtre", "à ±32 MHz de la fréquence touchée (filtre 32 MHz)"
   in ns["im_rules_text"](_P[0][1], 0.5, 32.0))
ok("plan Wisycom de Clément : compatible en 2A − B seul",
   not any(ns["pf_check"]([558.0, 574.0, 606.0, 614.0, 646.0, 478.0], tol=_P[1][1])[0]))
# le vrai plan de Clément dans EazyRF (MRK980 + MTK952) : profil 2 TX 100, 3 TX 50, séparation 500, filtre 32 → 0 IM
WIS = [470.2, 471.3, 478.0, 558.0, 574.0, 606.0, 614.0, 646.0, 660.95, 661.45]
_w0 = ns["pf_check"](WIS, sep=0.5, tol=_P[0][1], filt=32.0)[0]
ok("plan Wisycom complet, profil EazyRF (filtre 32 MHz) : 0 problème, comme EazyRF", not any(_w0), str(_w0))
_w1 = ns["pf_check"](WIS, sep=0.5, tol=_P[0][1])[0]
ok("même plan sans filtre : des A + B − C (émetteurs loin les uns des autres)",
   any(it["kind"] == "im" and it["ntx"] == 3 for x in _w1 for it in x), str(_w1))
ok("même plan, écart 500 kHz pile (661.45 − 660.95) : accepté", not any(it["kind"] == "sep" for x in _w0 for it in x))
_w2 = ns["pf_check"](WIS, sep=0.6, tol=_P[0][1], filt=32.0)[0]
ok("écart 600 kHz : 660.95 / 661.45 trop près", _w2[8] and _w2[8][0]["kind"] == "sep")
# filtre (doc EazyRF 2.4.5 : 16 MHz -> porteuse à 500 MHz, émetteurs de 484 à 516) : ± la valeur du filtre
ok("filtre 16 : émetteurs à 7 et 14 MHz comptés (2×507 − 514)", ns["pf_check"]([500.0, 507.0, 514.0], sep=0.3, tol=_P[0][1], filt=16.0)[0][0])
ok("filtre 16 : émetteur à 18 MHz coupé (2×509 − 518)", not ns["pf_check"]([500.0, 509.0, 518.0], sep=0.3, tol=_P[0][1], filt=16.0)[0][0])
# tolérance « au-delà de laquelle les IM sont acceptées » : pile 50 kHz = accepté, 45 kHz = gênant
ok("3 TX pile à 50 kHz : accepté", not ns["pf_check"]([500.0, 503.0, 510.0, 493.05], sep=0.3, tol=_P[0][1])[0][3])
ok("3 TX à 45 kHz : gênant", ns["pf_check"]([500.0, 503.0, 510.0, 493.045], sep=0.3, tol=_P[0][1])[0][3])
# 2ᵉ vrai plan de Clément (Roc d'Azur 2026, EazyRF 4.81 : « Nbre Intermodulation: 0 ») : réglages PAR APPAREIL
# (MRK980 / MTK952 filtre 32, AKG DMS700 filtre 16 ; séparations 2000 / 4000 / 1000 / 300 kHz ; 5ᵉ ordre coupé)
_RA = [(558.2, 2.0, 32), (578.05, 2.0, 32), (602.8, 2.0, 32), (612.85, 2.0, 32), (522.85, 2.0, 32), (681.45, 2.0, 32),
       (610.3, 2.0, 32), (575.8, 2.0, 32), (645.65, 2.0, 32), (671.25, 2.0, 32), (566.0, 2.0, 32), (597.65, 2.0, 32),
       (684.2, 2.0, 32), (534.85, 2.0, 32), (538.25, 2.0, 32), (527.45, 2.0, 32), (529.65, 2.0, 32), (627.05, 1.0, 16),
       (679.45, 1.0, 16), (554.2, 4.0, 32), (570.6, 4.0, 32), (491.55, 4.0, 32), (497.15, 4.0, 32), (624.0, 0.3, 16),
       (635.85, 0.3, 16), (629.2, 0.3, 16), (640.3, 0.3, 16), (608.2, 2.0, 32), (658.5, 2.0, 32)]
_T0 = {"2tx3": 0.1, "3tx3": 0.05, "5": 0.0, "7": 0.0}
_ra = ns["pf_check"]([x[0] for x in _RA], sep=[0.3] * len(_RA), tol=_T0, filt=[x[2] for x in _RA])[0]
ok("plan Roc d'Azur (filtres par appareil) : 0 problème, comme EazyRF", not any(_ra), str([x for x in _ra if x]))
_ra2 = ns["pf_check"]([x[0] for x in _RA], tol={"2tx3": 0.1, "3tx3": 0.0501, "5": 0.0, "7": 0.0},
                      filt=[x[2] for x in _RA])[0]
_g2 = [it["gap"] for x in _ra2 for it in x]
ok("plan Roc d'Azur : des produits pile à 50 kHz (d'où la limite stricte)",
   _g2 and all(abs(g - 0.05) < 1e-6 for g in _g2), str(_g2))
# filtre : 2A − B avec un émetteur à 40 MHz de la victime → coupé par un filtre de 32 MHz (±32), pas par 100
_fx = [500.0, 520.0, 540.0]                    # 2×520 − 500 = 540 : A = 520 (20 MHz), B = 500 (40 MHz)
ok("filtre 32 : produit coupé", not ns["pf_check"](_fx, sep=0.3, tol=_P[0][1], filt=32.0)[0][2])
ok("filtre 100 : produit compté", ns["pf_check"](_fx, sep=0.3, tol=_P[0][1], filt=100.0)[0][2])
ok("sans filtre : produit compté", ns["pf_check"](_fx, sep=0.3, tol=_P[0][1])[0][2])
# 2A − B à 80 kHz d'une cible : gênant (2 TX, < 100) ; A + B − C à 80 kHz : accepté (3 TX, > 50)
rows, _ = im_scan([500.0, 501.0], (3,), 2, targets=[499.08], guard=EZ)
ok("2 TX à 80 kHz : gênant", len(rows) == 1 and rows[0]["ntx"] == 2, str(rows))
rows, _ = im_scan([500.0, 503.0, 510.0], (3,), 3, targets=[493.08], guard=EZ)
ok("3 TX à 80 kHz : accepté", not [r for r in rows if r["ntx"] == 3], str(rows))
rows, _ = im_scan([500.0, 503.0, 510.0], (3,), 3, targets=[493.03], guard=EZ)
ok("3 TX à 30 kHz : gênant", [r for r in rows if r["ntx"] == 3], str(rows))
rows, _ = im_scan([500.0, 503.0, 510.0], (3,), 3, targets=[493.08], guard=0.1)
ok("une seule tolérance (ancien appel) : 3 TX à 80 kHz gênant", [r for r in rows if r["ntx"] == 3])
# im3_clash : tolérance 3 TX séparée
ok("im3_clash : 3 TX séparé", im3_clash(493.08, [500.0, 503.0, 510.0], 0.1, 0.05) == []
   and im3_clash(493.08, [500.0, 503.0, 510.0], 0.1) != [])

# ---- tolérance 0 = type ignoré (comme EazyRF)
TXc = [558.0, 574.0, 606.0, 614.0, 646.0, 478.0]       # le plan de Clément : 606 + 614 − 646 = 574 pile
rows, _ = im_scan(TXc, (3,), 3, targets=TXc, guard=dict(EZ))
ok("plan de Clément : A + B − C pile dessus trouvé", any(r["ntx"] == 3 and r["gap"] <= 1e-9 for r in rows))
rows, _ = im_scan(TXc, (3,), 3, targets=TXc, guard=dict(EZ, **{"3tx3": 0.0}))
ok("tolérance 3 TX = 0 → les A + B − C ne sont plus comptés", not [r for r in rows if r["ntx"] == 3], str(rows[:2]))
rows, _ = im_scan(TXc, (3, 5), 3, targets=TXc, guard={"2tx3": 0.1, "3tx3": 0.0, "5": 0.0, "7": 0.0})
ok("seulement 2A − B : plan propre", not rows, str([(r["f"], r["terms"]) for r in rows[:3]]))
rows, _ = im_scan(TXc, (3,), 2, targets=TXc, guard={"2tx3": 0.0, "3tx3": 0.05})
ok("tolérance 2 TX = 0 (chemin rapide) → rien", not rows)

# ---- vérification d'un plan (façon EazyRF)
pfc, pfs, pft = ns["pf_check"], ns["pf_suggest"], ns["pf_issue_text"]
NM = ["HF1", "HF2", "HF3", "DJL", "DJR", "SAX"]
iss, _ = pfc(TXc, tol=dict(EZ))
ok("plan : HF2 (574) a un problème A + B − C", any(it["kind"] == "im" and it["ntx"] == 3 for it in iss[1]), str(iss[1]))
txt_ = pft(next(it for it in iss[1] if it["kind"] == "im"), NM, TXc)
ok("plan : texte lisible", "pile dessus" in txt_ and "TX" in txt_, txt_)
iss2, _ = pfc(TXc, tol={"2tx3": 0.1, "3tx3": 0.0, "5": 0.0, "7": 0.0})
ok("plan : en 2A − B seulement, tout est compatible", not any(iss2), str(iss2))
iss3, _ = pfc([500.0, 500.2, 510.0], tol=dict(EZ))
ok("plan : écart entre porteuses (200 kHz < 300)", iss3[0] and iss3[0][0]["kind"] == "sep" and iss3[1] and not iss3[2])
ok("plan : texte écart", "trop près de" in pft(iss3[0][0], ["A", "B", "C"], [500.0, 500.2, 510.0]))
ok("plan : bloc large compté bord à bord", pfc([500.0, 504.2], bws=[8.0, 0.0], tol=dict(EZ))[0][0][0]["kind"] == "sep")
# une réserve (doit rester libre) est protégée mais n'émet pas
F_ = [500.0, 501.0, 499.0]                     # 2×500 − 501 = 499
ok("plan : réserve touchée par 2A − B", pfc(F_, is_tx=[True, True, False], tol=dict(EZ))[0][2])
ok("plan : réserve qui n'émet pas → ne crée pas de produit", not pfc([500.0, 499.0, 501.0], is_tx=[True, False, True],
                                                                      tol=dict(EZ))[0][0])
sg = pfs(1, TXc, tol=dict(EZ), n=3)
ok("suggestion : 3 fréquences proposées, les plus proches d'abord", len(sg) == 3
   and abs(sg[0][1]) <= abs(sg[-1][1]), str(sg))
for c_, d_ in sg:
    Fn = list(TXc)
    Fn[1] = c_
    iss_n, _ = pfc(Fn, tol=dict(EZ))
    ok(f"suggestion {c_:.3f} : compatible pour elle, rien de nouveau ailleurs",
       not iss_n[1] and sum(map(len, iss_n)) <= sum(map(len, pfc([f for k, f in enumerate(TXc) if k != 1], tol=dict(EZ))[0])),
       str(iss_n))
sg2 = pfs(1, TXc, tol=dict(EZ), n=2, busy=lambda c: abs(c - sg[0][0]) < 1e-6)
ok("suggestion : évite une fréquence occupée sur le spectre", all(abs(c - sg[0][0]) > 1e-6 for c, _ in sg2))

# suggestion rapide (pré-filtre) = recherche brute, sur des plans aléatoires avec blocs larges
def _brute(i, F, T, B, sep, tol, lo, hi, n, filt=0.0, step=0.025):
    Fo = [f for k, f in enumerate(F) if k != i]
    To = [t for k, t in enumerate(T) if k != i]
    Bo = [b for k, b in enumerate(B) if k != i]
    base = sum(map(len, pfc(Fo, To, Bo, sep, tol, None, filt)[0]))
    out = []
    g = np.arange(np.ceil(lo / step - 1e-9) * step, hi + 1e-9, step)
    for c in g[np.lexsort((g, np.round(np.abs(g - F[i]), 6)))]:
        c = round(float(c), 6)
        if abs(c - F[i]) < 1e-9:
            continue
        iss = pfc(Fo + [c], To + [T[i]], Bo + [B[i]], sep, tol, None, filt)[0]
        if not iss[-1] and sum(map(len, iss[:-1])) <= base:
            out.append(c)
            if len(out) >= n:
                break
    return out


rgs = random.Random(7)
same = tot_ = 0
for _ in range(12):
    nf = rgs.randint(4, 9)
    Fr = sorted({round(rgs.uniform(500, 530), 3) for _ in range(nf)})
    Br = [8.0 if rgs.random() < 0.15 else 0.0 for _ in Fr]
    Tr = [rgs.random() > 0.2 for _ in Fr]
    i_ = rgs.randrange(len(Fr))
    fast = [c for c, _d in pfs(i_, Fr, Tr, Br, 0.3, dict(EZ), 3, lo=Fr[i_] - 3, hi=Fr[i_] + 3, n=3)]
    slow = _brute(i_, Fr, Tr, Br, 0.3, dict(EZ), Fr[i_] - 3, Fr[i_] + 3, 3)
    tot_ += 1
    same += fast == slow
ok(f"suggestion rapide = recherche brute ({same}/{tot_})", same == tot_)
same = tot_ = 0
for _ in range(14):                            # avec filtre récepteur et pas de 5 kHz, plans plus étalés
    nf = rgs.randint(4, 9)
    Fr = sorted({round(rgs.uniform(490, 560), 3) for _ in range(nf)})
    Br = [8.0 if rgs.random() < 0.1 else 0.0 for _ in Fr]
    Tr = [rgs.random() > 0.2 for _ in Fr]
    i_ = rgs.randrange(len(Fr))
    fl_ = rgs.choice([8.0, 20.0, 32.0])
    fast = [c for c, _d in pfs(i_, Fr, Tr, Br, 0.3, dict(EZ), 3, lo=Fr[i_] - 1.5, hi=Fr[i_] + 1.5, n=3, step=0.005,
                               filt=fl_)]
    slow = _brute(i_, Fr, Tr, Br, 0.3, dict(EZ), Fr[i_] - 1.5, Fr[i_] + 1.5, 3, filt=fl_, step=0.005)
    tot_ += 1
    same += fast == slow
ok(f"suggestion rapide = brute, avec filtre et pas 5 kHz ({same}/{tot_})", same == tot_)

# ---- profils d'appareil (un par fréquence, comme EazyRF)
rxp = ns["rx_profile"]
ok("profils : Wisycom = profil EazyRF de Clément", rxp("wisycom")["filt"] == 32.0 and rxp("wisycom")["sep"] == 0.5
   and rxp("wisycom")["step"] == 0.005 and rxp("inconnu") is None)
ok("profils : chacun expliqué, clés uniques", all(len(w_) > 30 for *_x, w_ in ns["RX_PROFILES"])
   and len({k for k, *_x in ns["RX_PROFILES"]}) == len(ns["RX_PROFILES"]))
def _prof(keys):
    P = [rxp(k) for k in keys]
    return dict(sep=[q["sep"] for q in P], tol=[q["tol"] for q in P], filt=[q["filt"] for q in P])
_pw = _prof(["wisycom"] * len(WIS))
ok("profils : plan Wisycom tout en Wisycom → 0 problème", not any(pfc(WIS, **_pw)[0]))
_ps = _prof(["shure_ana"] * len(WIS))
ok("profils : même plan en Shure analogique (peu sélectif) → des problèmes", any(pfc(WIS, **_ps)[0]))
_im = pfc(WIS, **_prof(["wisycom"] * 3 + ["shure_ana"] * 5 + ["wisycom"] * 2))[0]
ok("profils : mélange → seuls les récepteurs peu sélectifs (Shure 558…646) sont touchés",
   all(len(_im[i]) == 0 for i in (0, 1, 2, 8, 9)) and all(len(_im[i]) > 0 for i in (4, 5, 6, 7)),
   str([len(x) for x in _im]))
# écart par paire = le plus grand des deux
ok("profils : écart = le plus grand des deux", pfc([500.0, 500.45], sep=[0.3, 0.5])[0][0]
   and not pfc([500.0, 500.45], sep=[0.3, 0.4])[0][0])
# tolérance de la fréquence TOUCHÉE : 2×500 − 501 = 499 à 120 kHz de 499.12
ok("profils : tolérance de la victime (150 kHz → touchée)",
   pfc([500.0, 501.0, 499.12], tol=[None, None, {"2tx3": 0.15, "3tx3": 0, "5": 0, "7": 0}])[0][2])
ok("profils : tolérance de la victime (100 kHz → non)",
   not pfc([500.0, 501.0, 499.12], tol=[None, None, {"2tx3": 0.1, "3tx3": 0, "5": 0, "7": 0}])[0][2])
# suggestion rapide = brute avec des profils mélangés
def _brute2(i, F, T, B, pp, lo, hi, n, step):
    ot = [k for k in range(len(F)) if k != i]
    sub = lambda key, ks: [pp[key][k] for k in ks]
    mt = 3
    base = sum(map(len, pfc([F[k] for k in ot], [T[k] for k in ot], [B[k] for k in ot], sub("sep", ot),
                            sub("tol", ot), mt, sub("filt", ot))[0]))
    out = []
    g = np.arange(np.ceil(lo / step - 1e-9) * step, hi + 1e-9, step)
    for c in g[np.lexsort((g, np.round(np.abs(g - F[i]), 6)))]:
        c = round(float(c), 6)
        if abs(c - F[i]) < 1e-9:
            continue
        ks = ot + [i]
        iss = pfc([F[k] for k in ot] + [c], [T[k] for k in ks], [B[k] for k in ks], sub("sep", ks), sub("tol", ks),
                  mt, sub("filt", ks))[0]
        if not iss[-1] and sum(map(len, iss[:-1])) <= base:
            out.append(c)
            if len(out) >= n:
                break
    return out
same = tot_ = 0
keys_ = [k for k, *_x in ns["RX_PROFILES"]]
for _ in range(14):
    nf = rgs.randint(4, 8)
    Fr = sorted({round(rgs.uniform(490, 540), 3) for _ in range(nf)})
    Br = [8.0 if rgs.random() < 0.1 else 0.0 for _ in Fr]
    Tr = [rgs.random() > 0.2 for _ in Fr]
    pp = _prof([rgs.choice(keys_) for _ in Fr])
    i_ = rgs.randrange(len(Fr))
    fast = [c for c, _d in pfs(i_, Fr, Tr, Br, pp["sep"], pp["tol"], 3, lo=Fr[i_] - 1.5, hi=Fr[i_] + 1.5, n=3,
                               step=0.025, filt=pp["filt"])]
    slow = _brute2(i_, Fr, Tr, Br, pp, Fr[i_] - 1.5, Fr[i_] + 1.5, 3, 0.025)
    tot_ += 1
    same += fast == slow
    if fast != slow:
        print("   diff", i_, Fr, pp, fast, slow)
ok(f"suggestion rapide = brute, profils mélangés ({same}/{tot_})", same == tot_)
rgb = np.random.default_rng(1)
F30 = sorted(470 + rgb.uniform(0, 224, 30).round(3))
_iss30, _inf30 = pfc(F30, tol=dict(EZ))
ok("plan de 30 émetteurs, ordres 3 + 5 : calculable (pas « trop gros »)", not _inf30["too_big"], str(_inf30))
ok("le 7ᵉ ordre n'est pas compté dans le plan", ns["pf_orders"](dict(EZ)) == (3, 5))

# ---- verdict : gravité en couleurs
iv = ns["im_verdict"]
ok("verdict : mesuré au-dessus du seuil occupé → 🔴", iv(-60.0, -80.0, -90.0, True, 3, 3)[0] == 3)
ok("verdict : au-dessus du seuil faible → 🟠", iv(-85.0, -80.0, -90.0, True, 5, 3)[0] == 2)
ok("verdict : faible ignoré si la case est décochée", iv(-85.0, -80.0, -90.0, False, 5, 3)[0] == 0)
ok("verdict : rien mesuré, IM3 2 TX → 🟡", iv(-98.0, -80.0, -90.0, True, 3, 2)[0] == 1)
ok("verdict : rien mesuré, A + B − C → ⚪", iv(-98.0, -80.0, -90.0, True, 3, 3)[0] == 0)
ok("verdict : rien mesuré, IM5 → ⚪", iv(-98.0, -80.0, -90.0, True, 5, 2)[0] == 0)
s_, t_ = iv(-50.0, -80.0, -90.0, True, 3, 2, masked=True)
ok("verdict : cible en émission → pas de mesure, calcul seul", s_ == 1 and "cible émet" in t_, t_)
ok("verdict : pas de scan", "pas de mesure" in iv(None, -80.0, -90.0, True, 3, 3)[1])

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
