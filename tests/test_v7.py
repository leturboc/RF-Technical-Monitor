import io, csv, json, math, os, re, sys, unicodedata, itertools, time, random, bisect
import numpy as np

src = open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "tinysa_monitor.py"), encoding="utf-8").read()
a = src.index("# ===== PURE-BEGIN")
b = src.index("# ===== PURE-END")
ns = dict(itertools=itertools, re=re, csv=csv, io=io, math=math, np=np, unicodedata=unicodedata, bisect=bisect,
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


parse_scan_text, wwb_scan_text, wsm_to_wwb_text = ns["parse_scan_text"], ns["wwb_scan_text"], ns["wsm_to_wwb_text"]

# ================================================================ export WSM synthétique (structure du converter nikharju)
rng = np.random.default_rng(11)
n_pts = 2721
fk = [470000 + 82 * i for i in range(n_pts)]
pct = np.round(np.clip(rng.normal(22, 6, n_pts), 0, 100), 1)
pct[100] = 71.3
meta = ["Wireless Systems Manager;Scan export", "Name;Scan 1", "Date;2023-05-02", "Start;470000", "Stop;693122", "Step;82"]
lines = list(meta)
lines.append("Frequency;RF level (%);RF level;Memory (%);Memory;Squelch (%);Squelch")
for f, p in zip(fk, pct):
    lines.append(f"{f};{p};{-120 + p * 1.2:.1f} dBm;{p / 2};{-120 + p * 0.6:.1f};0;-120")
lines += [f"Info {i};x" for i in range(13)]
wsm = "\r\n".join(lines) + "\r\n"

# portage fidèle de l'algorithme du converter (lignes 231-264 de WSM_WWB_csv_converter.py)
def original_converter(text):
    table = list(csv.reader(io.StringIO(text), delimiter=";"))
    assert table[6] == ['Frequency', 'RF level (%)', 'RF level', 'Memory (%)', 'Memory', 'Squelch (%)', 'Squelch']
    del table[2728:2741]
    del table[0:7]
    for i in table:
        del i[2:7]
        i.insert(1, i[0][:3] + "." + i[0][3:] + ",")
        del i[0]
        i.insert(2, str(int(float(i[1]) / 100 * 120 - 120)))
        del i[1]
    out = io.StringIO()
    w = csv.writer(out, delimiter=' ')
    for r in table:
        w.writerow(r)
    return out.getvalue()


ref = original_converter(wsm)
mine, info = wsm_to_wwb_text(wsm)
rl, ml = ref.split("\r\n")[:-1], mine.split("\r\n")[:-1]
check("WSM : même nombre de lignes que le converter", len(ml), len(rl))
check("WSM : 2721 points", len(ml), n_pts)
check("WSM : mêmes fréquences (texte identique)", [x.split(", ")[0] for x in ml], [x.split(", ")[0] for x in rl])
dl = [abs(int(x.split(", ")[1]) - int(y.split(", ")[1])) for x, y in zip(ml, rl)]
ok(f"WSM : niveaux à ±1 dB du converter (écart max {max(dl)})", max(dl) <= 1)
check("WSM : format de ligne", ml[0].split(", ")[0], "470.000")
ok("WSM : la ligne a bien « 470.000, -N »", re.fullmatch(r"\d{3}\.\d{3}, -?\d+", ml[0]) is not None, ml[0])
ok("WSM : info", info["fmt"] == "wsm" and info["n"] == n_pts and "dBm" in info["note"])
F, L, inf = parse_scan_text(wsm)
ok("WSM : fréquences en MHz", abs(F[0] - 470.0) < 1e-9 and abs(F[-1] - (470000 + 82 * (n_pts - 1)) / 1000.0) < 1e-9, str((F[0], F[-1])))
ok("WSM : 71.3 % = −34,4 dBm", abs(L[100] - (71.3 * 1.2 - 120)) < 1e-9, str(L[100]))
check("fin de fichier WSM ignorée (pas de ligne « Info »)", len(F), n_pts)
# virgule décimale + séparateur ; (WSM en français)
wsm_fr = wsm.replace("22.", "22,").replace(".5;", ",5;")
Ff, Lf, _ = parse_scan_text(wsm_fr)
check("WSM avec virgules décimales", len(Ff), n_pts)
# UTF-8 BOM
Fb, Lb, _ = parse_scan_text("﻿" + wsm)
check("WSM avec BOM", len(Fb), n_pts)
# autres colonnes (%) : on prend « RF level (%) » même si elle n'est pas en 2ᵉ position
cols_lines = list(meta) + ["Frequency;Memory (%);RF level (%);RF level;Squelch (%)"]
for f, p in zip(fk, pct):
    cols_lines.append(f"{f};{p / 2};{p};{-120 + p * 1.2:.1f} dBm;0")
cols_lines += [f"Info {i};x" for i in range(13)]
Fc, Lc, _ = parse_scan_text("\n".join(cols_lines))
ok("WSM : colonne « RF level (%) » choisie même en 3ᵉ position", len(Fc) == n_pts and abs(Lc[100] - (71.3 * 1.2 - 120)) < 1e-9)

# ================================================================ WWB : relecture de ce qu'on écrit
w_text = wwb_scan_text(F, L)
check("WWB : 1ʳᵉ ligne", w_text.split("\r\n")[0], f"470.000, {int(round(L[0]))}")
check("WWB : fin de ligne CRLF", w_text.endswith("\r\n") and "\n\n" not in w_text.replace("\r\n", ""), True)
F2, L2, i2 = parse_scan_text(w_text)
ok("WWB : relecture", len(F2) == n_pts and np.allclose(F2, F, atol=5e-4) and np.max(np.abs(L2 - L)) <= 0.5 + 1e-9, str(np.max(np.abs(L2 - L))))
check("WWB : format détecté simple", i2["fmt"], "simple")
Fn, Ln = wwb_scan_text([470.0, float("nan"), 471.0], [-90.4, -80.0, float("inf")]), None
check("WWB : valeurs invalides ignorées", Fn, "470.000, -90\r\n")

# ================================================================ autres variantes de fichiers
base = "\n".join(f"{470 + 0.2 * i:.3f}, {-100 + (i % 7)}" for i in range(50))
F3, L3, _ = parse_scan_text(base)
check("simple sans en-tête", (len(F3), round(float(F3[0]), 3), float(L3[1])), (50, 470.0, -99.0))
F4, L4, i4 = parse_scan_text("Frequency (MHz), Level (dBm)\n" + base)
check("simple avec en-tête", (len(F4), i4["unit"]), (50, "MHz"))
F5, L5, _ = parse_scan_text(base.replace(", ", "\t"))
check("tabulations", len(F5), 50)
F6, L6, _ = parse_scan_text("\n".join(f"{470 + 0.2 * i:.3f}".replace(".", ",") + ";" + f"{-100.5 + (i % 7)}".replace(".", ",") for i in range(50)))
check("français ; et virgule décimale", (len(F6), float(L6[0])), (50, -100.5))
# notre propre export (scan_csv) en kHz avec en-tête : l'unité est lue dans l'en-tête
ex = ns["scan_csv"](F3, [L3], "kHz", ";", ",", True, ["Niveau (dBm)"])
F7, L7, i7 = parse_scan_text(ex)
ok("round trip de notre export en kHz", np.allclose(F7, F3, atol=1e-6) and i7["unit"] == "kHz", str((F7[:2], i7)))
ex_hz = ns["scan_csv"](F3, [L3], "Hz", ";", ".", False)
F8, _, _ = parse_scan_text(ex_hz)
ok("export en Hz sans en-tête : unité déduite", np.allclose(F8, F3, atol=1e-6), str(F8[:2]))
# erreurs lisibles
for lab, txt in (("texte quelconque", "Bonjour\nceci n'est pas un scan\n"), ("vide", ""),
                 ("en-tête WSM sans données", "Frequency;RF level (%);RF level\n"),
                 ("deux lignes seulement", "470.0, -90\n470.2, -91\n")):
    try:
        parse_scan_text(txt)
        ok(f"erreur claire : {lab}", False, "pas d'exception")
    except ValueError as e:
        ok(f"erreur claire : {lab} → « {e} »", len(str(e)) > 10)
# métadonnées parasites en tête de fichier
junk = "Date;2024;05\nVenue;12;3\n" + base
F9, _, _ = parse_scan_text(junk)
check("parasites au début ignorés", len(F9), 50)
# fin de fichier parasite
F10, _, _ = parse_scan_text(base + "\nFin du scan;ok\n999;1\n")
check("pied de page ignoré", len(F10), 50)

# ================================================================ alarmes
AB = ns["AlarmBook"]
bk = AB(repeat_s=10.0)
check("nouvelle alarme", bk.raise_(("CONFLIT", 506000), "CONFLIT", "Chant", 506.0, 2, 100.0, -50.0, "Main › A"), True)
check("même alarme : pas nouvelle", bk.raise_(("CONFLIT", 506000), "CONFLIT", "Chant", 506.0, 2, 101.0, -48.0), False)
check("niveau mis à jour", bk.active[("CONFLIT", 506000)]["level"], -48.0)
bk.raise_(("ABSENT", 510000), "ABSENT", "Basse", 510.0, 1, 102.0)
bk.raise_(("ABSENT", 512000), "ABSENT", "Gtr", 512.0, 0, 103.0)
check("compteurs", bk.counts(), (3, 3, 2))
check("tri : critique d'abord", [a["name"] for a in bk.listing()], ["Chant", "Basse", "Gtr"])
check("pas de répétition avant 10 s", bk.due_repeat(105.0), [])
due = bk.due_repeat(111.0)
check("répétition critique non acquittée", [a["name"] for a in due], ["Chant"])
check("pas de double répétition", bk.due_repeat(112.0), [])
check("acquitter", bk.ack(bk.active[("CONFLIT", 506000)]["id"]), True)
check("acquittée : plus de répétition", bk.due_repeat(200.0), [])
check("compteurs après acquittement", bk.counts(), (2, 3, 1))
check("tri : acquittée en dernier", [a["name"] for a in bk.listing()][-1], "Chant")
a_ = bk.clear(("CONFLIT", 506000), 130.0)
check("terminée conservée", (a_["name"], a_["t_end"], len(bk.done)), ("Chant", 130.0, 1))
check("listing : en cours puis terminées", [a["name"] for a in bk.listing()], ["Basse", "Gtr", "Chant"])
check("re-déclenchement après fin = nouvelle", bk.raise_(("CONFLIT", 506000), "CONFLIT", "Chant", 506.0, 2, 140.0), True)
check("tout acquitter", bk.ack_all(), 3)
check("clear inconnu", bk.clear(("X", 1), 1.0), None)
check("purge", (bk.purge_done(), len(bk.done)), (1, 0))

# ================================================================ mémoire de relecture
SS = ns["SweepStore"]
st = SS(seconds=100.0, max_mb=300)
fA = np.linspace(470, 480, 101)
fB = np.linspace(500, 510, 101)
for k in range(30):
    t = 1000.0 + k * 5
    st.add(1, t, fA, np.full(101, -100.0 + k))
    st.add(2, t + 1, fB, np.full(101, -90.0 - k))
sp = st.span()
ok("fenêtre glissante 100 s", sp[1] - sp[0] <= 100.0 + 6, str(sp))
F_, L_ = st.snapshot(1140.0)
ok("snapshot : 2 bandes", F_ is not None and len(F_) == 202 and F_[0] == 470 and F_[-1] == 510)
check("snapshot : dernier balayage ≤ t (bande 1)", float(L_[0]), -100.0 + 28)
Fm, Lm = st.maxhold(1100.0, 1145.0)
check("maxhold sur la fenêtre", float(Lm[0]), -100.0 + 29)
check("maxhold bande 2 (le plus fort = le plus ancien)", float(Lm[-1]), -90.0 - 20)
check("snapshot avant le début", st.snapshot(10.0), (None, None))
F_, _ = st.snapshot(1140.0, stale=2.0)
ok("snapshot : bandes trop vieilles ignorées", F_ is not None and len(F_) == 101, str(None if F_ is None else len(F_)))
check("crans de temps triés", bool(np.all(np.diff(st.times()) > 0)), True)
big = SS(seconds=1e9, max_mb=0.05)
for k in range(200):
    big.add(1, float(k), fA, np.zeros(101))
ok("plafond mémoire respecté", big.bytes <= 0.05e6 + 101 * 4 and len(big.t[1]) < 200, str(big.bytes))
f_shared = [d[0] for d in st.d[1]]
ok("grille de fréquences partagée (pas de copie par balayage)", all(x is f_shared[0] for x in f_shared))

# ================================================================ export par scène
rows = [dict(name="HF 1", freq=506.0, status="Libre", scene="Main Stage", group="Groupe A"),
        dict(name="HF 2", freq=507.5, status="", scene="Main Stage", group="Groupe B"),
        dict(name="IEM 1", freq=863.5, status="Occupé", scene="Side/Stage", group=""),
        dict(name="Sans", freq=600.125, status="", scene="", group="")]
ft = ns["freq_list_text"]
check("export complet", ft(rows, "full").split("\r\n")[1], "Main Stage;Groupe A;HF 1;506,000;Libre")
check("export Nom;MHz", ft(rows, "name_mhz").split("\r\n")[:2], ["Nom;MHz", "HF 1;506,000"])
check("export Nom, MHz", ft(rows, "name_mhz_comma").split("\r\n")[0], "HF 1, 506.000")
check("export MHz seul", ft(rows, "mhz").split("\r\n")[:2], ["506.000", "507.500"])
sp_ = ns["split_freq_rows"]
check("tout dans un fichier", [(n, len(r)) for n, r in sp_(rows, "all")], [("frequences", 4)])
check("un fichier par scène", [(n, len(r)) for n, r in sp_(rows, "scene")], [("Main Stage", 2), ("Side_Stage", 1), ("Sans scène", 1)])
check("un fichier par groupe", [n for n, r in sp_(rows, "group")], ["Main Stage - Groupe A", "Main Stage - Groupe B", "Side_Stage - Sans groupe", "Sans scène - Sans groupe"])
check("nom de fichier sûr", ns["safe_filename"]('a/b:c*?"<>|.'), "a_b_c")
check("nom de fichier vide", ns["safe_filename"]("  .. "), "export")
# round trip : notre export complet se réimporte avec scène/groupe/statut
an = ns["analyze_csv"](ft(rows, "full"))
ent = ns["build_entries_ex"](an, an["name_col"], an["freq_cols"], an["status_col"], an["scene_col"], an["group_col"])
check("réimport : 4 fréquences", len(ent), 4)
check("réimport : nom/MHz/statut/scène/groupe", ent[0], ("HF 1", 506.0, "Libre", "Main Stage", "Groupe A"))

# ================================================================ rapport HTML
ev = [("12:00:01", "Chant <b>", "506.000", "-40.0", "CONFLIT", "Main Stage › A", ""),
      ("12:00:09", "Basse", "507.500", "-120.0", "ABSENT", "Main Stage › B", "TX éteint ?"),
      ("12:03:00", "Signal inconnu", "499.000", "-62.0", "INCONNU", "", "IM3 probable : 2×HF 2 − HF 1"),
      ("12:04:00", "Chant", "506.000", "-70.0", "Libre (59 s)", "Main Stage › A", "")]
rws = [dict(name="Chant <b>", freq=506.0, status="Libre", layer="Main Stage › A", max=-40.0, occ_pct=12.0, events=2, conflicts=1, absents=0),
       dict(name="Basse", freq=507.5, status="En service", layer="Main Stage › B", max=None, occ_pct=None, events=1, conflicts=0, absents=1)]
Fx = np.linspace(470, 520, 1001)
Lx = -100 + 5 * np.sin(Fx)
html = ns["build_report_html"](dict(title="Festival <X>", venue="Lyon", operator="Clément", generated="2026-10-24 21:00",
                                    duration="3 h 12", notes="ligne 1\nligne 2", events=ev, rows=rws, F=Fx, L=Lx, thr=-80.0,
                                    groups=[dict(name="Main Stage › A", n=1, occ=0, events=2, conflicts=1, absents=0, prio="Critique")],
                                    im=[dict(f=499.0, order="IM3", text="2×HF 1 − HF 2", tname="Victime (499.000)", delta="+0", verdict="à risque")],
                                    app="TinySA Monitor 7.0"))
ok("rapport : titre échappé", "Festival &lt;X&gt;" in html and "Festival <X>" not in html)
ok("rapport : noms échappés", "Chant &lt;b&gt;" in html and "<b>)" not in html.replace("<b>", "", 0))
ok("rapport : aucun script", "<script" not in html.lower())
ok("rapport : cartes de synthèse (1 conflit, 1 absent)", "<b>1</b>Conflits" in html and "<b>1</b>TX absents" in html, html[html.index("cards"):html.index("cards") + 400])
ok("rapport : SVG du spectre + polyline", "<svg" in html and "<polyline" in html and "class='mk hot'" in html)
ok("rapport : section intermod", "Intermodulation (1)" in html and "2×HF 1 − HF 2" in html)
ok("rapport : note IM dans le journal", "IM3 probable" in html)
ok("rapport : autonome (pas de lien externe)", "http://" not in html.replace("http://www.w3.org/2000/svg", "") and "https://" not in html)
ok("rapport : balises équilibrées", html.count("<table") == html.count("</table>") and html.count("<tr") == html.count("</tr>"))
h0 = ns["build_report_html"](dict(events=[], rows=[], F=None, L=None))
ok("rapport vide : ne plante pas", "Aucun conflit" in h0 and "Pas de mesure" in h0)

# ================================================================ en-têtes anglais à l'import
an = ns["analyze_csv"]("Name;Frequency;Group\nHF A;606.125;Plateau\nHF B;607.250;Plateau\n")
check("import : colonne « Group » reconnue comme groupe", an["group_col"], 2)
check("import : « Groupe » toujours reconnu", ns["header_kind"]("Groupe"), "group")

# ================================================================ 2e tinySA : adresses et répartition
pda, asg, spl = ns["parse_device_addr"], ns["assign_bands"], ns["split_band"]
check("adresse COM", pda("COM4"), ("serial", "COM4"))
check("adresse COM minuscules", pda(" com12 "), ("serial", "com12"))
check("adresse Linux", pda("/dev/ttyACM0"), ("serial", "/dev/ttyACM0"))
check("adresse IP seule → port relais", pda("192.168.1.20"), ("net", "socket://192.168.1.20:5025"))
check("adresse IP:port", pda("192.168.1.20:6000"), ("net", "socket://192.168.1.20:6000"))
check("adresse nom de PC", pda("pc-scene"), ("net", "socket://pc-scene:5025"))
check("url pyserial telle quelle", pda("rfc2217://10.0.0.5:4000"), ("net", "rfc2217://10.0.0.5:4000"))
check("adresse vide", pda(""), (None, ""))
check("adresse illisible", pda("pc scène")[0], None)
check("port hors plage", pda("1.2.3.4:70000")[0], None)
B = [dict(id=1, pts=1121, dev=None), dict(id=2, pts=300, dev=None), dict(id=3, pts=500, dev=None),
     dict(id=4, pts=200, dev=None)]
a = asg(B, 2)
load = [sum(b["pts"] for b in B if a[b["id"]] == d) for d in (0, 1)]
ok("auto : toutes les bandes affectées", set(a) == {1, 2, 3, 4} and set(a.values()) == {0, 1}, str(a))
ok("auto : charge équilibrée", abs(load[0] - load[1]) <= 200, str(load))
check("auto : déterministe", asg(B, 2), a)
a = asg([dict(id=1, pts=100, dev=1), dict(id=2, pts=900, dev=None)], 2)
check("bande fixée sur le 2", a[1], 1)
check("auto va sur le moins chargé", a[2], 0)
a = asg([dict(id=1, pts=100, dev=1), dict(id=2, pts=900, dev=None)], 2, live=[True, False])
check("2e hors ligne : tout sur le 1er", a, {1: 0, 2: 0})
a = asg([dict(id=1, pts=100, dev=0), dict(id=2, pts=900, dev=None)], 2, live=[False, True])
check("1er hors ligne : tout sur le 2e", a, {1: 1, 2: 1})
check("les deux hors ligne : repli sur le 1er", asg([dict(id=1, pts=10, dev=1)], 2, live=[False, False]), {1: 0})
check("un seul appareil", asg(B, 1), {1: 0, 2: 0, 3: 0, 4: 0})
check("couper une bande", spl(470.0, 694.0, 200.0), ((470.0, 582.0, 200.0), (582.0, 694.0, 200.0)))

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
