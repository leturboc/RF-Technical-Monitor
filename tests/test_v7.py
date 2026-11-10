import os
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
rl, ml = ref.split("\r\n")[:-1], mine.split("\n")[:-1]     # 7.32.1 : WWB comme ses vrais exports (« 470.000,-104.531 »)
check("WSM : même nombre de lignes que le converter", len(ml), len(rl))
check("WSM : 2721 points", len(ml), n_pts)
check("WSM : mêmes fréquences (texte identique)", [x.split(",")[0] for x in ml], [x.split(", ")[0] for x in rl])
dl = [abs(float(x.split(",")[1]) - int(y.split(", ")[1])) for x, y in zip(ml, rl)]
ok(f"WSM : niveaux à ±1 dB du converter (écart max {max(dl)})", max(dl) <= 1)
check("WSM : format de ligne", ml[0].split(",")[0], "470.000")
ok("WSM : la ligne a bien « 470.000,-N.NNN » (comme un vrai export WWB)", re.fullmatch(r"\d{3}\.\d{3},-?\d+\.\d{3}", ml[0]) is not None, ml[0])
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
check("WWB : 1ʳᵉ ligne (comme un vrai export WWB)", w_text.split("\n")[0], f"470.000,{L[0]:.3f}")
check("WWB : une ligne par point, sans ligne vide", w_text.endswith("\n") and "\n\n" not in w_text, True)
F2, L2, i2 = parse_scan_text(w_text)
ok("WWB : relecture", len(F2) == n_pts and np.allclose(F2, F, atol=5e-4) and np.max(np.abs(L2 - L)) <= 0.001, str(np.max(np.abs(L2 - L))))
check("WWB : format détecté simple", i2["fmt"], "simple")
Fn, Ln = wwb_scan_text([470.0, float("nan"), 471.0], [-90.4, -80.0, float("inf")]), None
check("WWB : valeurs invalides ignorées", Fn, "470.000,-90.400\n")

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
AB = ns["AlarmBook"]()
AB.raise_(("ABSENT", 1), "ABSENT", "HF 1", 470.0, 2, 100.0)
AB.raise_(("APPAREIL", -2), "APPAREIL", "tinySA 2", 0.0, 2, 200.0)
check("alarme APPAREIL en tête de liste", [a["kind"] for a in AB.listing()], ["APPAREIL", "ABSENT"])
co = ns["calib_offset"]
rng = np.random.default_rng(1)
Fc = np.linspace(470, 530, 601)
base = -100 + rng.normal(0, 1.0, Fc.size)
for fc in (480, 495, 510, 522):
    base = np.maximum(base, -50 - 30 * ((Fc - fc) / 0.2) ** 2)
L2c = base - 3.0 + rng.normal(0, 0.3, Fc.size)         # le 2e lit 3 dB trop bas
r = co(Fc, base, Fc, L2c)
ok("calibration : +3 dB trouvé sur les signaux", r is not None and abs(r[0] - 3.0) <= 0.3 and r[2] == "signaux", str(r))
F2c = np.linspace(470, 530, 401)                        # grilles différentes
r = co(Fc, base, F2c, np.interp(F2c, Fc, base) + 2.0)
ok("calibration : grilles différentes, −2 dB", r is not None and abs(r[0] + 2.0) <= 0.5, str(r))
noise1 = -100 + rng.normal(0, 1.0, Fc.size)
r = co(Fc, noise1, Fc, noise1 - 4.0)
ok("calibration : sans signal → plancher de bruit", r is not None and r[2] == "bruit de fond" and abs(r[0] - 4.0) <= 0.3, str(r))
only1 = noise1.copy()
only1[100:110] = -40                                    # porteuse vue d'un seul côté : ignorée
r = co(Fc, only1, Fc, noise1 - 1.0)
ok("calibration : porteuse d'un seul côté ignorée", r is not None and abs(r[0] - 1.0) <= 0.3, str(r))
check("calibration : pas de recouvrement", co([1, 2, 3], [0, 0, 0], [10, 11, 12], [0, 0, 0]), None)
mv, mkd = ns["marker_visible"], ns["mk_default"]
w0 = dict(state="occ", status="En service", scene="Grande scène", group="IEM")
check("repère : visible par défaut", mv(w0, mkd()), True)
check("repère : tout masqué", mv(w0, dict(mkd(), on=False), alarm=True), False)
check("repère : état décoché", mv(w0, dict(mkd(), states=["free"])), False)
check("repère : sans mesure = « none »", mv(dict(w0, state=None), dict(mkd(), states=["none"])), True)
check("repère : statut masqué", mv(w0, dict(mkd(), hide_status=["En service"])), False)
check("repère : couche masquée", mv(w0, dict(mkd(), hide_layers=[ns["mk_layer_key"]("Grande scène", "IEM")])), False)
check("repère : autre couche non touchée", mv(w0, dict(mkd(), hide_layers=[ns["mk_layer_key"]("Grande scène", "HF")])), True)
check("repère : sans scène", mv(dict(w0, scene="", group=""), dict(mkd(), hide_layers=[""])), False)
check("repère : masqué à la main", mv(dict(w0, hide_mk=True), mkd()), False)
check("repère : alarme visible malgré tout", mv(dict(w0, hide_mk=True), dict(mkd(), states=[]), alarm=True), True)
check("repère : alarme suit les filtres si demandé", mv(dict(w0, hide_mk=True), dict(mkd(), alarms=False), alarm=True), False)
check("filtre actif", (ns["mk_filtered"](mkd()), ns["mk_filtered"](dict(mkd(), hide_status=["x"]))), (False, True))
lb = ns["level_block"]
Fb = np.linspace(600, 620, 401)                          # pas 50 kHz
Lb = -100 + 0 * Fb
Lb[(Fb >= 606) & (Fb <= 614)] = -65                     # plateau WMAS 8 MHz centré sur 610
check("bloc : niveau médian du plateau", lb(Fb, Lb, 610.0, 8.0), -65.0)
Ls = -100 + 0 * Fb
Ls[np.argmin(abs(Fb - 611.0))] = -45                    # une porteuse étroite dans un bloc vide
check("bloc vide + porteuse : médiane reste basse", lb(Fb, Ls, 610.0, 8.0), -100.0)
check("bloc vide + porteuse : le max la voit", lb(Fb, Ls, 610.0, 8.0, "max"), -45.0)
check("bloc hors balayage", lb(Fb, Lb, 700.0, 8.0), None)
check("bloc de largeur nulle", lb(Fb, Lb, 610.0, 0), None)
bc = ns["block_choices"](ns["tv_channels"]("FR"))
check("canaux bloc FR : 21 → 48, 8 MHz", (bc[0], len(bc), bc[-1][1]), (("CH 21 — 470–478 MHz", 474.0, 8.0), 28, 690.0))
bcu = ns["block_choices"](ns["tv_channels"]("US"))
ok("canaux bloc US : 6 MHz", bcu[0][2] == 6.0 and all(c[1] < 698 for c in bcu), str(bcu[:2]))
bp = ns["block_points"]
check("points d'un bloc", (bp(610.0, 8.0)[0], bp(610.0, 8.0)[-1], len(bp(610.0, 8.0))), (606.0, 614.0, 9))
check("points d'une fréquence simple", bp(500.0, 0.0), [500.0])
bo = ns["block_overlaps"]
items = [("Spectera 38", 610.0, 8.0), ("HF 1", 607.5, 0.0), ("HF 2", 615.0, 0.0), ("Bloc 39", 616.0, 6.0),
         ("HF 3", 620.0, 0.0)]
check("chevauchements : HF 1 dans le bloc 38, blocs 38/39 qui se touchent, HF 2 dans le 39",
      bo(items), {1: "Spectera 38", 0: "Bloc 39", 3: "Spectera 38", 2: "Bloc 39"})
check("chevauchements : marge de garde", bo([("B", 610.0, 8.0), ("HF", 614.3, 0.0)], guard=0.5), {1: "B"})
check("pas de bloc : rien", bo([("a", 1.0, 0.0), ("b", 1.0, 0.0)]), {})
import json as _json
cfg_full = dict(bands=[dict(name="UHF", start=470.0, stop=694.0, step=200.0, enabled=True)],
                watch=[dict(name="HF 1", freq=500.0, status="En service", thr=None, scene="S", group="G"),
                       dict(name="Spectera ch 38", freq=610.0, status="En service", thr=None, scene="", group="", bw=8.0)],
                scenes=[dict(name="S", color="#fff", groups=[dict(name="G", color="#000", prio=2)])],
                statuses=[dict(name="En service", color="#0f0", free=False, on=True)], thr=-75, country="FR",
                theme=dict(ui_base="#000"), log_dir="/x", web=dict(on=True, port=8080),
                dev2=dict(on=True, addr="192.168.1.20", offset=1.0), dev_names=["Plateau", "FOH"], markers=dict(on=False))
meta = dict(name="Fest", venue="Grande scène", date_from="2025-07-17", date_to="2025-07-20", notes="antenne FOH")
doc = ns["show_doc"](cfg_full, meta, [([470.0, 471.0], [-100.04, -99.0])], "7.1")
check("show : format", (doc["format"], doc["version"], doc["app"]), ("tinysa-show", 1, "7.1"))
check("show : contient les fréquences, scènes, bandes, seuils, noms de position",
      all(k in doc["show"] for k in ("watch", "scenes", "bands", "thr", "country", "dev_names")), True)
check("show : PAS les préférences du logiciel", [k for k in ("theme", "log_dir", "web", "markers") if k in doc["show"]], [])
check("show : le 2ᵉ tinySA (adresse réseau) suit le show (demande de Clément 7.31)", "dev2" in doc["show"], True)
check("show : courbe de référence arrondie", doc["ref"], [dict(f=[470.0, 471.0], l=[-100.0, -99.0])])
back = ns["read_show"](_json.dumps(doc))
check("show : relu à l'identique", (back["meta"], back["show"], back["ref"]),
      (meta, doc["show"], [([470.0, 471.0], [-100.0, -99.0])]))
mine = dict(cfg_full, theme=dict(ui_base="#123"), watch=[], thr=-90, log_dir="/cette-annee")
ap = ns["show_apply"](mine, back)
check("show appliqué : fréquences et seuils du show", (len(ap["watch"]), ap["thr"]), (2, -75))
check("show appliqué : mes préférences gardées", (ap["theme"], ap["log_dir"]), (dict(ui_base="#123"), "/cette-annee"))
old = ns["read_show"](_json.dumps(dict(cfg_full, profil="TinySA Monitor")), "evenement")
check("ancien profil : lu, préférences ignorées", (old["meta"]["name"], "theme" in old["show"], len(old["show"]["watch"])),
      ("evenement", False, 2))
try:
    ns["read_show"]('{"a": 1}')
    check("fichier quelconque refusé", False, True)
except ValueError:
    check("fichier quelconque refusé", True, True)
sm = ns["show_summary"](back)
check("résumé", (sm["dates"], sm["n_freq"], sm["n_blocks"], sm["has_ref"]), ("2025-07-17 → 2025-07-20", 2, 1, True))
check("nom de fichier", ns["show_filename"](meta), "2025 Fest - Grande scène.tsashow")
check("nom de fichier sans infos", ns["show_filename"]({}), "show.tsashow")
check("nom de fichier : caractères interdits", ns["show_filename"](dict(name="A/B: C?")), "A_B_ C.tsashow")
# garde-fou : une case de menu branchée sur « lambda checked=False » reçoit toujours False avec PySide6
bad = re.findall(r"\.(?:triggered|toggled|clicked)\.connect\(lambda ([A-Za-z]\w*)=", src)
check("pas de lambda à argument optionnel sur triggered / toggled / clicked", bad, [])
sv = ns["signal_view"]
check("doit émettre + signal = OK (vert)", sv("occ", keep_on=True), ("OK", "ok"))
check("doit émettre + muet = orange, puis ABSENT rouge", (sv("free", keep_on=True), sv("free", keep_on=True, absent=True)),
      (("muet", "warn"), ("⚠ ABSENT", "bad")))
check("doit rester libre + signal = CONFLIT (rouge)", sv("occ", keep_free=True), ("⚠ CONFLIT", "bad"))
check("doit rester libre + rien = ✔ libre (ton « libre », distinct de OK)", sv("free", keep_free=True), ("✔ libre", "free"))
check("sans statut + rien = libre (ton « libre »)", sv("free"), ("libre", "free"))
check("doit émettre + signal = OK (ton « ok »)", sv("occ", keep_on=True), ("OK", "ok"))
cc_ = ns["clean_colors"]
check("couleurs : seules les valides restent", cc_({"ok": "#22C55E", "free": "bleu", "zzz": "#000000", "free_ok": "#3b82f6"}),
      {"ok": "#22c55e", "free_ok": "#3b82f6"})
ok("tons par situation : tous connus", set(ns["SIGNAL_TONES"]) == set(ns["SIGNAL_DEFAULTS"]))
_sk = ns["signal_key"]
_cas = [(st, kf, ko, ab, im) for st in ("occ", "weak", "free") for kf, ko in ((0, 0), (1, 0), (0, 1)) for ab in (0, 1) for im in (0, 1)]
ok("tons par situation : identiques à signal_key", all(ns["SIGNAL_TONES"][k] == t for k, t in
                                                      (_sk(*c) for c in _cas) if k is not None))
check("sans statut : occupé = pas de place (rouge)", sv("occ"), ("OCCUPÉ", "bad"))
check("pas de mesure", sv(None, keep_on=True), ("—", "none"))
check("doit rester libre + intermod = INTERMOD (rouge)", sv("occ", keep_free=True, intermod=True), ("⚠ INTERMOD", "bad"))
check("intermod sans importance si ce n'est pas « doit rester libre »", sv("occ", keep_on=True, intermod=True), ("OK", "ok"))
check("mes mots", sv("occ", keep_on=True, labels={"ok": "BON"}), ("BON", "ok"))
check("mot vide = mot par défaut", sv("free", keep_free=True, labels={"free_ok": ""}), ("✔ libre", "free"))
check("toutes les situations ont un mot par défaut", all(ns["SIGNAL_DEFAULTS"][k] for k in ns["SIGNAL_DEFAULTS"]), True)
tu, fu, fl = ns["to_unit"], ns["from_unit"], ns["fmt_level"]
check("dBµV = dBm + 107", tu(-80.0, "dbuv"), 27.0)
check("% WSM : -120 dBm = 0 %, 0 dBm = 100 %, -60 = 50 %", (tu(-120.0, "pct"), tu(0.0, "pct"), tu(-60.0, "pct")),
      (0.0, 100.0, 50.0))
check("% : écrêté à 0–100", (tu(-140.0, "pct"), tu(10.0, "pct")), (0.0, 100.0))
ok("aller-retour dBµV / %", abs(fu(tu(-73.4, "dbuv"), "dbuv") + 73.4) < 1e-9 and abs(fu(tu(-73.4, "pct"), "pct") + 73.4) < 1e-9)
check("textes", (fl(-80.0, "dbm"), fl(-80.0, "dbuv", suffix=True), fl(-60.0, "pct", suffix=True), fl(None, "pct")),
      ("-80.0", "27.0 dBµV", "50 %", "—"))
wv = ns["wall_visible"]
check("mur : affichée par défaut", wv(dict(state="free")), True)
check("mur : hors couche", wv(dict(state="occ"), in_scope=False), False)
check("mur : retirée à la main", wv(dict(state="occ", hide_wall=True)), False)
check("mur : retirée mais en alarme → revient", wv(dict(state="free", hide_wall=True), alarm=True), True)
check("mur : … sauf si l'option est décochée", wv(dict(state="free", hide_wall=True), alarm=True, alarms_always=False), False)
check("mur : occupées seulement", (wv(dict(state="free"), only_active=True), wv(dict(state="weak"), only_active=True)),
      (False, True))
wg = ns["wall_grid"]
check("grille mur : petites tuiles, 300 px de large → 1 colonne, défile", wg(15, 300, 200, "s")[:3], (1, 15, 64))
check("grille mur : petites tuiles, 1000 px → 6 colonnes", wg(15, 1000, 400, "s")[:2], (6, 3))
check("grille mur : police fixe selon la taille", (wg(5, 800, 400, "s")[3], wg(5, 800, 400, "l")[3]), (11, 22))
c_, r_, h_, f_ = wg(15, 1200, 700, "auto")
ok("grille mur : auto remplit (hauteur 0 = s'étire)", h_ == 0 and c_ * r_ >= 15 and 8 <= f_ <= 44)
check("grille mur : petit panneau auto → police mini 8", wg(40, 250, 120)[3], 8)
check("grille mur : aucune tuile", wg(0, 500, 300)[1], 0)
lcn, lcf, lcs, lch, lct = ns["lc_new"], ns["lc_feed"], ns["lc_summary"], ns["lc_hints"], ns["lc_text"]
lc = lcn([(470200, "HF 1", 470.2, "A"), (471800, "HF 2", 471.8, "A"), (483600, "HF 6", 483.6, "A")])
check("appel : rien de validé au départ", lcs(lc)["text"], "0 / 3 OK · manquent : HF 1, HF 2, HF 6")
ok("appel : un signal fort valide", lcf(lc, 470200, "occ", -60.0, 10.0) and lc[470200]["res"] == "ok")
ok("appel : déjà validée → pas de 2ᵉ bip", not lcf(lc, 470200, "occ", -55.0, 11.0) and lc[470200]["lvl"] == -55.0)
ok("appel : libre ne valide pas", not lcf(lc, 471800, "free", -100.0, 11.0) and lc[471800]["res"] is None)
ok("appel : faible, puis fort = mise à jour", lcf(lc, 471800, "weak", -88.0, 12.0) and lc[471800]["res"] == "weak"
   and lcf(lc, 471800, "occ", -70.0, 13.0) and lc[471800]["res"] == "ok")
ok("appel : clé inconnue ignorée", not lcf(lc, 999, "occ", -50.0, 1.0))
check("appel : manque HF 6", lcs(lc)["text"], "2 / 3 OK · manque : HF 6")
check("appel : pack mal réglé repéré", lch(lc, [483.9, 600.0]), [("HF 6", 483.6, 483.9)])
check("appel : inconnu trop loin ignoré", lch(lc, [495.0]), [])
lc[483600]["res"] = "skip"
s_ = lcs(lc)
ok("appel : ignorée = hors compte, terminé", s_["done"] and s_["n"] == 2 and s_["text"] == "Tout est là ✓ (2 / 2) · 1 ignorée(s)")
t_ = lct(lc, "Festival", "24/10 18:00")
ok("appel : résumé à copier", t_.splitlines()[0] == "Appel des micros — Festival · 24/10 18:00"
   and "✓ HF 1 · 470.200 MHz · -55 dBm" in t_ and "– HF 6 · 483.600 MHz (ignorée)" in t_, t_)
check("appel : liste vide", lcs(lcn([]))["text"], "Rien à appeler")
ip_ = ns["input_plan"]
check("entrée : tinySA d'origine en Auto", (ip_(False, "auto", 500e6), ip_(False, "auto", 2400e6)), ("low", "high"))
check("entrée : Ultra en Auto → toujours l'entrée normale (jamais « mode high »)",
      (ip_(True, "auto", 500e6), ip_(True, "auto", 2400e6)), ("low", "low"))
check("entrée : forcée", (ip_(True, "low", 2400e6), ip_(False, "high", 100e6)), ("low", "high"))
# ---- convertisseur de scans
sw_, psc_, pst_ = ns["scan_write"], ns["parse_scan_custom"], ns["parse_scan_text"]
Fc = np.array([470.0, 470.025, 470.05, 470.075, 470.1, 470.125])
Lc = np.array([-98.0, -97.5, -60.2, -95.0, -99.9, -101.0])
t_ = sw_(Fc, Lc, "wwb")
ok("conv : WWB = « 470.000,-98.000 »", t_.splitlines()[0] == "470.000,-98.000", t_.splitlines()[0])
F2_, L2_, i2_ = pst_(sw_(Fc, Lc, "wsm", title="Test"))
ok("conv : WSM écrit → relu comme un export WSM, niveaux à 0,5 dB près (dB µV entiers, comme WSM)", i2_["fmt"] == "wsm"
   and np.allclose(F2_, Fc) and np.allclose(L2_, Lc, atol=0.51), str((i2_, L2_)))
t3_ = sw_(Fc, Lc, "csv", sep="\t", dec=",", funit="kHz", lunit="dbuv", header=True)
ok("conv : CSV kHz, dBµV, tabulation, virgule", t3_.splitlines()[1] == "470000,000\t9,0", t3_.splitlines()[:2])
F3_, L3_, _ = psc_(t3_, sep="\t", fcol=0, lcol=1, funit="kHz", lunit="dbuv", dec=",")
ok("conv : CSV relu avec ses réglages = d'origine", np.allclose(F3_, Fc) and np.allclose(L3_, Lc, atol=0.05), str(L3_))
F4_, L4_, _ = psc_("Freq;Rien;Level\n470,1;x;-80\n470,2;y;-81\nPied de page\n", sep=";", fcol=0, lcol=2)
ok("conv : colonnes au choix, en-tête et pied ignorés", list(F4_) == [470.1, 470.2] and list(L4_) == [-80.0, -81.0])
F5_, L5_, _ = psc_("x\nx\n470000 50\n470025 25\n", sep=" ", skip=2, funit="kHz", lunit="pct")
ok("conv : lignes sautées, %, kHz", np.allclose(F5_, [470.0, 470.025]) and np.allclose(L5_, [-60.0, -90.0]), str((F5_, L5_)))
try:
    psc_("rien d'utile\n", fcol=0, lcol=1)
    ok("conv : fichier illisible → erreur claire", False)
except ValueError as e:
    ok("conv : fichier illisible → erreur claire", "colonnes" in str(e))
sp = ns["strong_peaks"]
Fs_ = np.linspace(470, 700, 2301)
Ls_ = -100 + 0 * Fs_
Ls_[np.argmin(abs(Fs_ - 500.0))] = -15
Ls_[np.argmin(abs(Fs_ - 500.3))] = -18                   # même zone (< 1 MHz) : un seul pic
Ls_[np.argmin(abs(Fs_ - 650.0))] = -22
check("trop fort : 2 zones, la plus forte d'abord", [(round(f, 1), l) for f, l in sp(Fs_, Ls_, -25.0)],
      [(500.0, -15.0), (650.0, -22.0)])
check("trop fort : rien sous le seuil", sp(Fs_, Ls_, -10.0), [])
check("trop fort : balayage vide", sp(np.array([]), np.array([]), -25.0), [])
check("couper une bande", spl(470.0, 694.0, 200.0), ((470.0, 582.0, 200.0), (582.0, 694.0, 200.0)))

# sessions enregistrées (proposées à ▶ Démarrer)
check("session : nom de dossier sans caractère interdit", ns["session_name"]("2026-10-29_2015", 'Fest: A/B "x"'),
      "2026-10-29_2015 Fest_ A_B _x")
check("session : nom sans show", ns["session_name"]("2026-10-29_2015"), "2026-10-29_2015")
check("session : réglages par défaut", ns["session_cfg_norm"](None), dict(ask=True, rec=True, dir=""))
check("session : réglages lus", ns["session_cfg_norm"](dict(ask=0, rec=False, dir="D:/Shows")),
      dict(ask=False, rec=False, dir="D:/Shows"))
check("session : journal relu", ns["session_journal_rows"](
    "\ufeffDate;Heure;Nom;MHz;dBm;Événement;Statut\n2026-10-29;20:15:02;HF 1;470,200;-50,0;CONFLIT;Libre\n"
    "bancal;;\n2026-10-29;21:00:00;tinySA;—;—;APPAREIL PERDU;\n"),
      [("2026-10-29", "20:15:02", "20:15:02  CONFLIT  HF 1  470.200 MHz"),
       ("2026-10-29", "21:00:00", "21:00:00  APPAREIL PERDU  tinySA")])
check("session : place estimée", round(ns["rec_mb_per_hour"](3000, 1.0), 2), 14.04)
check("session : place inconnue", ns["rec_mb_per_hour"](0, 1.0), None)

lk = ns["log_kind"]
check("journal : types d'événements", [lk(e) for e in ("CONFLIT", "INTERMOD", "ABSENT", "TROP FORT", "OCCUPÉ",
                                                        "Libre (12 s)", "Retour (3 s)", "Retour", "INCONNU",
                                                        "APPAREIL PERDU", "APPEL OK", "NOUVELLE FRÉQUENCE")],
      ["alarm", "alarm", "alarm", "strong", "busy", "back", "back", "back", "unknown", "device", "ops", "ops"])
check("journal : tout coché par défaut", all(ns["log_kinds_norm"](None).values()), True)
check("journal : choix relus", ns["log_kinds_norm"]({"busy": False, "x": 1})["busy"], False)

# ajouter depuis le scan : signaux au-dessus d'un seuil
sp_ = ns["scan_peaks"]
F_ = np.round(np.arange(600.0, 620.0, 0.025), 4)
L_ = np.full(len(F_), -100.0)
L_[(F_ >= 602.0) & (F_ <= 602.1)] = -50.0          # micro (100 kHz)
L_[(F_ >= 602.2) & (F_ <= 602.25)] = -60.0         # à 100 kHz : réuni au précédent (réunir à 150)
L_[(F_ >= 605.0) & (F_ <= 605.05)] = -70.0
L_[np.abs(F_ - 605.0) < 1e-6] = -65.0
L_[(F_ >= 610.0) & (F_ <= 617.9)] = -75.0          # plateau 8 MHz (TNT)
pk_ = sp_(F_, L_, -80.0)
check("scan : 3 signaux (réunis à 150 kHz)", [(p_["f"], p_["wide"]) for p_ in pk_],
      [(602.05, False), (605.0, False), (613.95, True)])
check("scan : niveau max et largeur", (pk_[0]["level"], pk_[0]["width"]), (-50.0, 250.0))
check("scan : déjà dans la liste → écarté", [p_["f"] for p_ in sp_(F_, L_, -80.0, exclude=[605.05])],
      [602.05, 613.95])
check("scan : plateau écarté si une fréquence de la liste est dedans",
      [p_["f"] for p_ in sp_(F_, L_, -80.0, exclude=[612.0])], [602.05, 605.0])
check("scan : seuil plus haut", [p_["f"] for p_ in sp_(F_, L_, -55.0)], [602.05])
check("scan : rien au-dessus", sp_(F_, L_, -10.0), [])
check("scan : spectre vide", sp_([], [], -80.0), [])
F2_ = np.round(np.arange(470.0, 480.0, 0.224), 3)  # balayage grossier (pas 224 kHz) : plateau TNT 470–478
L2_ = np.where(F2_ < 478.0, -64.0, -100.0)
check("scan : pas grossier, plateau = UN signal large", [(p_["wide"], round(p_["f"])) for p_ in sp_(F2_, L2_, -80.0)],
      [(True, 474)])

# marqueurs : niveau à une fréquence, pic voisin, largeur occupée
Fm_ = np.round(np.arange(600.0, 601.0, 0.01), 3)
Lm_ = np.full(len(Fm_), -100.0)
Lm_[(Fm_ >= 600.45) & (Fm_ <= 600.55)] = -60.0
Lm_[np.abs(Fm_ - 600.5) < 1e-6] = -50.0
check("marqueur : niveau au point le plus proche", ns["trace_at"](Fm_, Lm_, 600.452), (600.45, -60.0))
check("marqueur : pic voisin", ns["peak_near"](Fm_, Lm_, 600.3), (600.5, -50.0))
check("marqueur : largeur occupée à −20 dB (pic − 20 = −70)", ns["occupied_width"](Fm_, Lm_, 600.4, 20.0),
      (600.45, 600.55, 600.5, -50.0))
check("marqueur : NaN (trous entre bandes) ignorés", ns["trace_at"]([600.0, np.nan, 601.0], [-80, np.nan, -70], 600.6),
      (601.0, -70.0))
check("marqueur : rien", ns["peak_near"]([], [], 600.0), None)

# comparer deux sessions (max hold)
Fc_ = np.round(np.arange(600.0, 610.0, 0.025), 3)
La_ = np.full(len(Fc_), -100.0)
Lb_ = La_.copy()
La_[np.abs(Fc_ - 602.0) < 0.03] = -50.0             # présent dans les deux
Lb_[np.abs(Fc_ - 602.0) < 0.03] = -52.0
La_[np.abs(Fc_ - 605.0) < 0.03] = -60.0             # nouveau dans A
Lb_[np.abs(Fc_ - 608.0) < 0.03] = -55.0             # disparu (seulement dans B)
nw_, gn_ = ns["compare_spectra"](Fc_, La_, Fc_, Lb_, -80.0)
check("comparer : signal en plus / en moins, l'identique ignoré",
      ([round(p_["f"], 2) for p_ in nw_], [round(p_["f"], 2) for p_ in gn_]), ([605.0], [608.0]))

# occupation par heure à partir d'un SweepStore
st_ = ns["SweepStore"](seconds=1e9, max_mb=50)
Fo_ = np.round(np.arange(600.0, 601.0, 0.01), 3)
for k_ in range(20):                                 # 20 balayages : heure 20 (k < 10) puis 21
    Lo_ = np.full(len(Fo_), -100.0)
    if k_ % 2 == 0:
        Lo_[np.abs(Fo_ - 600.5) < 0.02] = -50.0      # 600.5 occupée un balayage sur deux
    st_.add(1, 1000.0 + k_, Fo_, Lo_)
oc_ = ns["store_occupancy"](st_, [600.5, 600.2, 700.0], -80.0, lambda t: 20 if t < 1010 else 21, 0.05)
check("occupation : 50 % sur 600.5, 0 % sur 600.2, rien hors bande",
      {h: (list(n), list(k)) for h, (n, k) in oc_.items()},
      {20: ([10.0, 10.0, 0.0], [5.0, 0.0, 0.0]), 21: ([10.0, 10.0, 0.0], [5.0, 0.0, 0.0])})

# --- zoom live : points automatiques
zoom_points, MIN_PTS = ns["zoom_points"], ns["MIN_PTS"]
check("zoom 2 MHz -> 201 pts (10 kHz)", zoom_points(2.0), 201)
check("zoom 20 MHz -> plafond 290", zoom_points(20.0), 290)
check("zoom 0.1 MHz -> minimum MIN_PTS", zoom_points(0.1), MIN_PTS)
check("zoom auto jamais plus que les points des bandes", zoom_points(20.0, None, 101), 101)
check("zoom : nombre fixe respecté", zoom_points(2.0, 1000), 1000)

# --- mode festival
fcn, fdue, astats, ftext = ns["festival_cfg_norm"], ns["festival_due"], ns["alarm_stats"], ns["festival_text"]
fc = fcn({"on": 1, "hour": "30", "last": "2026-10-28", "bidule": 3})
check("festival : heure bornée, valeurs lues", (fc["on"], fc["hour"], fc["last"], fc["autostart"]), (True, 23, "2026-10-28", True))
check("festival : config bancale -> défaut", fcn("x")["on"], False)
fc = fcn({"on": True, "hour": 9, "last": "2026-10-28"})
check("bilan : pas avant l'heure", fdue("2026-10-29", 8, fc), False)
check("bilan : à l'heure", fdue("2026-10-29", 9, fc), True)
check("bilan : rattrapé plus tard dans la journée", fdue("2026-10-29", 15, fc), True)
check("bilan : une seule fois par jour", fdue("2026-10-28", 15, fc), False)
check("bilan : rien si mode coupé", fdue("2026-10-29", 15, fcn({"on": False})), False)
check("bilan : rien si bilan décoché", fdue("2026-10-29", 15, fcn({"on": True, "daily": False})), False)
al_ = [dict(kind="CONFLIT", t0=100.0), dict(kind="ABSENT", t0=200.0), dict(kind="ABSENT", t0=300.0), dict(kind="CONFLIT", t0=50.0)]
check("statistiques d'alarmes depuis t", astats(al_, 100.0), {"CONFLIT": 1, "ABSENT": 2})
t_, b_, ok_ = ftext("Main Stage", {}, 0, 0, 24, True, 26.4, 1, 1, "bilan.html")
ok("bilan : tout va bien", ok_ and t_ == "✔ Tout va bien — Main Stage" and "aucune alarme" in b_ and "24 fréquence(s)" in b_
   and "26 h" in b_ and "bilan.html" in b_, repr((t_, b_)))
t_, b_, ok_ = ftext("", {"ABSENT": 2}, 1, 1, 24, True, 3, 2, 2)
ok("bilan : alarmes en cours", not ok_ and t_ == "⚠ 1 alarme(s) en cours" and "ABSENT : 2" in b_ and "2 / 2" in b_, repr((t_, b_)))
t_, b_, ok_ = ftext("", {}, 0, 0, 24, True, 3, 1, 2)
ok("bilan : un tinySA hors ligne", not ok_ and "hors ligne" in t_, t_)
t_, b_, ok_ = ftext("", {}, 0, 0, 24, False, 0, 0, 1)
ok("bilan : surveillance arrêtée", not ok_ and "arrêtée" in t_, t_)
req_ = ns["ntfy_request"]("https://ntfy.sh", "t", "x", "y", -1)
check("ntfy : message « tout va bien » en priorité normale", req_[1]["Priority"], "default")

# --- firmware 2026 : refus du tinySA expliqué
trf = ns["tinysa_refusal"]
ok("tinySA en disque USB : message clair", "disque USB" in trf(["usb disk mode active"]))
ok("tinySA en mise à jour : message clair", "firmware" in trf(["firmware update active"]))
ok("trop de points par commande : message clair", "Segment" in trf(["sweep points exceeds range 450"]))
check("réponse normale : pas de refus", trf(["470000000 -9.8e+01 0.0"]), "")

# --- points par balayage « Auto »
ast_ = ns["auto_scan_step"]
check("auto : petite zone (2 MHz) -> 10 kHz", ast_(2.0), 10)
check("auto : bande FM (20,5 MHz) -> 10 kHz", ast_(20.5), 10)
check("auto : UHF 470-694 (224 MHz) -> 50 kHz", ast_(224.0), 50)
check("auto : 470-960 (490 MHz) -> 125 kHz", ast_(490.0), 125)
check("auto : RBW 30 kHz imposée -> pas ≤ RBW", ast_(490.0, 30), 25)
check("auto : RBW large imposée ne change rien", ast_(224.0, 300), 50)
check("auto : très large -> plafond 1 MHz", ast_(6000.0), 1000)
ok("auto : cycle UHF ≤ 4 500 points", 224000 / ast_(224.0) + 1 <= 4501)

check("auto rapide (2 000 pts) : UHF 224 MHz -> 125 kHz", ast_(224.0, None, ns["AUTO_BUDGET"][-1]), 125)
check("auto détaillé (9 000 pts) : UHF 224 MHz -> 25 kHz", ast_(224.0, None, ns["AUTO_BUDGET"][-2]), 25)
check("auto équilibré = donnée 0 du menu", ns["AUTO_BUDGET"][0], 4500)

# --- scans des autres logiciels (comparatif de Clément, 7.16.2)
pst_ = ns["parse_scan_text"]
def _rows(fmt, n=8):
    return "".join(fmt.format(f=470 + i * 0.025, l=-98 + (i % 3)) for i in range(n))
for nom_, txt_ in (("WWB virgule", _rows("{f:.3f},{l:.1f}\n")), ("WWB point-virgule", _rows("{f:.3f};{l:.1f}\n")),
                   ("WWB tabulation", _rows("{f:.3f}\t{l:.1f}\n")),
                   ("WSM [Data]", "[Sennheiser WSM Scan Data]\nStartFrequency;470000\nEndFrequency;600000\nStepSize;25\n[Data]\n"
                    + _rows("{f:.3f};{l:.0f}\n")),
                   ("décimale virgule", _rows("{f:.3f};{l:.1f}\n").replace(".", ",")),
                   ("Hz", "".join(f"{int((470 + i * 0.025) * 1e6)},{-98 + i % 3}\n" for i in range(8)))):
    F_, L_, _i = pst_(txt_)
    ok(f"scan {nom_} : lu en MHz / dBm", abs(F_[1] - 470.025) < 1e-6 and abs(L_[0] + 98) < 1e-6, f"{F_[:2]} {L_[:2]}")
F_, L_, i_ = pst_("Frequency (MHz);Level (dBµV)\n" + "".join(f"{470 + i * 0.025:.3f};{9 + i % 3:.1f}\n" for i in range(8)))
ok("scan Wisycom en dBµV : converti en dBm", abs(L_[0] + 98) < 1e-6 and "dBµV" in i_["note"], f"{L_[:2]} {i_}")

# --- sons de l'appli (7.17)
scn_, tpcm_ = ns["sound_cfg_norm"], ns["tone_pcm"]
check("son : config bancale -> défaut", scn_({"volume": "x", "style": "??"}), ns["SOUND_DEFAULT"])
check("son : volume borné", scn_({"volume": 250})["volume"], 100)
pc_ = tpcm_([(1000, 100), (0, 50)], 22050, 0.5)
check("son : 150 ms à 22 050 Hz en 16 bits", len(pc_), (2205 + 1102) * 2)
a_ = np.frombuffer(pc_, dtype="<i2")
ok("son : la note est là puis le silence", np.abs(a_[:2205]).max() > 10000 and np.abs(a_[2205:]).max() == 0)
ok("son : fondu (pas de clic au début)", abs(int(a_[0])) < 200)
ok("son : alarme critique = 3 notes", sum(1 for hz, _ms in ns["ALARM_TONES"][2] if hz) == 3)

# --- chasse au brouilleur
hl_, ht_ = ns["hunt_level"], ns["hunt_tone"]
Fh_ = np.linspace(599, 601, 201)
Lh_ = np.full_like(Fh_, -100.0)
Lh_[100] = -60.0                                   # 600.000
Lh_[160] = -40.0                                   # 600.600 : plus fort, mais hors de ± 100 kHz
check("chasse : niveau à ± 100 kHz", hl_(Fh_, Lh_, 600.0)[0], -60.0)
check("chasse : suivre le plus fort de la zone", hl_(Fh_, Lh_, 600.0, follow=True, span_mhz=2.0), (-40.0, 600.6))
ok("chasse : plus fort = plus aigu et plus rapide", ht_(-40)[0] > ht_(-90)[0] and ht_(-40)[1] < ht_(-90)[1])
check("chasse : rien mesuré = silence", ht_(None)[0], 0)
check("chasse : bornes (très faible / saturé)", (ht_(-200), ht_(10)), ((400, 1000), (2000, 80)))

# --- 🎬 planning des plateaux
pn_, pa_, pp_, pl_ = ns["planning_norm"], ns["planning_active"], ns["planning_paused"], ns["planning_lines"]
P_ = pn_(dict(pre=15, post=10, slots=[
    dict(scene="Grande scène", group="Groupe A", start="20:30", end="22:00"),
    dict(scene="Grande scène", group="Groupe B", start="22:30", end="00:30"),          # finit après minuit
    dict(scene="Club", group="DJ", day="2026-07-12", start="23:00", end="02:00"),
    dict(scene="", group="x", start="10:00", end="11:00"),                               # sans scène : ignoré
    dict(scene="Club", group="y", start="99:00", end="10:00")]))                        # heure illisible : ignoré
check("planning : créneaux lus (illisibles écartés)", len(P_["slots"]), 3)
def _act(ymd, hm, prev="", nxt=""):
    return pa_(P_, ymd, ns["_hm"](hm), prev, nxt)[0]
check("planning : A sur scène à 21 h", _act("2026-07-12", "21:00"), {("Grande scène", "Groupe A")})
check("planning : marge avant (A dès 20:15)", ("Grande scène", "Groupe A") in _act("2026-07-12", "20:15"), True)
check("planning : marge après (A jusqu'à 22:10)", ("Grande scène", "Groupe A") in _act("2026-07-12", "22:09"), True)
check("planning : changement de plateau 22:12 → personne", _act("2026-07-12", "22:12"), set())
check("planning : B après minuit (00:20)", ("Grande scène", "Groupe B") in _act("2026-07-13", "00:20", "2026-07-12"), True)
check("planning : DJ seulement le 12 (01:00 le 13)", ("Club", "DJ") in _act("2026-07-13", "01:00", "2026-07-12"), True)
check("planning : DJ pas le 13 au soir", ("Club", "DJ") in _act("2026-07-13", "23:30", "2026-07-12", "2026-07-14"), False)
act_, plan_ = pa_(P_, "2026-07-12", ns["_hm"]("21:00"))
ok("planning : B en pause pendant A", pp_("Grande scène", "Groupe B", act_, plan_) and not pp_("Grande scène", "Groupe A", act_, plan_))
ok("planning : scène sans planning jamais en pause", not pp_("Petite scène", "X", act_, plan_) and not pp_("", "", act_, plan_))
ok("planning : coupé = rien en pause", pa_(dict(P_, on=False), "2026-07-12", 1260) == (set(), set()))
ok("planning : texte « maintenant / ensuite »", any("▶ Groupe A" in t and "ensuite Groupe B à 22:30" in t for t in pl_(P_, act_, "2026-07-12", 1260)),
   str(pl_(P_, act_, "2026-07-12", 1260)))

# --- 📡 mode émission : commandes du générateur (lues dans le source du firmware)
gc_ = ns["gen_commands"]
check("générateur : FM", gc_(606.5, -60, "fm", 25, 1000),
      ["freq 606500000", "level -60.0", "modulation fm", "modulation freq 1000", "modulation deviation 25000"])
check("générateur : porteuse pure", gc_(470.2, -80.25, "off"), ["freq 470200000", "level -80.2", "modulation off"])
check("générateur : modulation inconnue -> porteuse", gc_(470, -80, "xx")[-1], "modulation off")
check("générateur : AM, son borné", gc_(470, -80, "am", tone_hz=20000)[-1], "modulation freq 6000")

# --- 🔎 chasse commandée depuis le téléphone
hr_ = ns["hunt_request"]
check("chasse web : commande propre", hr_(dict(action="start", f="606.5", span=200, dev="1", follow=1)),
      dict(action="start", f=606.5, span=50.0, follow=True, dev=1))
for bad_ in (dict(action="start", f=0), dict(action="x"), None, dict(action="start", f="abc")):
    try:
        hr_(bad_)
        ok(f"chasse web : refusée {bad_}", False)
    except (ValueError, TypeError, AttributeError):
        ok(f"chasse web : refusée {bad_}", True)

# --- 📍 scans par lieu : fusion (le pire cas du site)
ms_ = ns["merge_scans"]
Fa_ = np.linspace(470, 500, 1201)                 # pas 25 kHz
La_ = np.full_like(Fa_, -100.0)
La_[400] = -60.0                                  # 480.000 vu seulement à la scène A
Fb_ = np.linspace(490, 520, 301)                  # pas 100 kHz, plage différente
Lb_ = np.full_like(Fb_, -95.0)
Lb_[150] = -50.0                                  # 505.000 vu seulement à la scène B
Fm_, Lm_ = ms_([(Fa_, La_), (Fb_, Lb_)])
ok("fusion : couvre 470–520 MHz", abs(Fm_[0] - 470) < 1e-6 and abs(Fm_[-1] - 520) < 1e-6, f"{Fm_[0]} {Fm_[-1]}")
ok("fusion : pas le plus fin (25 kHz)", abs(float(np.median(np.diff(Fm_))) - 0.025) < 1e-6)
ok("fusion : le pic de la scène A est là", abs(ns["level_at"](Fm_, Lm_, 480.0, 0.05) + 60) < 0.01)
ok("fusion : le pic de la scène B est là", abs(ns["level_at"](Fm_, Lm_, 505.0, 0.05) + 50) < 0.01)
ok("fusion : là où les deux se recouvrent, le plus fort (−95 de B)", abs(ns["level_at"](Fm_, Lm_, 495.0, 0.01) + 95) < 0.5)
check("fusion : rien -> rien", ms_([]), (None, None))
# un scan à plusieurs bandes (UHF au pas de 50 kHz + 2,4 GHz au pas de 500 kHz) : pas de trait entre les bandes
Fu_ = np.concatenate([np.linspace(470, 520, 1001), np.linspace(2400, 2480, 161)])
Lu_ = np.concatenate([np.full(1001, -100.0), np.full(161, -90.0)])
check("trous : seulement entre les deux bandes (pas différents)", list(ns["scan_gaps"](Fu_)), [1001])
Fg_, Lg_ = ns["gap_nan"](Fu_, Lu_)
ok("trous : un NaN entre les bandes", len(Fg_) == 1163 and np.isnan(Fg_[1001]) and np.isnan(Lg_[1001]))
Fm2_, Lm2_ = ms_([(Fu_, Lu_), (Fa_, La_)])
ok("fusion de scans à plusieurs bandes : rien d'inventé entre 520 et 2400 MHz",
   not np.any((Fm2_ > 520.1) & (Fm2_ < 2399.9)), str(Fm2_[(Fm2_ > 520.1) & (Fm2_ < 2399.9)][:5]))
ok("fusion de scans à plusieurs bandes : le trou reste un trou au tracé", np.isnan(ns["gap_nan"](Fm2_, Lm2_)[1]).sum() == 1)
check("trous : scan d'une seule bande -> aucun", list(ns["scan_gaps"](Fa_)), [])
# --- vrais formats de scan envoyés par Clément (7.32.1) : WSM (dB µV), Wisycom (4 colonnes dBµV), TTI, WWB
DD_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
pst_ = ns["parse_scan_text"]
Fw_, Lw_, iw_ = pst_(open(os.path.join(DD_, "wsm_reel_essai.csv"), encoding="utf-8").read())
check("WSM réel : kHz -> MHz, dB µV -> dBm, pic à 470,450", (iw_["fmt"], round(Fw_[0], 3), round(float(Lw_[10]), 1), len(Fw_)),
      ("wsm", 470.2, -67.0, 21))
Fy_, Ly_, iy_ = pst_(open(os.path.join(DD_, "wisycom_essai.csv"), encoding="utf-8").read())
check("Wisycom : ligne d'infos sautée, le plus fort des 4 colonnes, dBµV -> dBm", (iy_["fmt"], len(Fy_), round(float(Ly_[5]), 1),
      round(float(Ly_[0]), 1)), ("wisycom", 11, -87.0, -110.0))
Ft_, Lt_, it_ = pst_(open(os.path.join(DD_, "tti_essai.csv"), encoding="utf-8").read())
check("TTI : MHz, dBm", (len(Ft_), float(Lt_[3])), (20, -42.0))
F2_, L2_, _ = pst_(ns["scan_write"](Fw_, Lw_, "wisycom"))      # grille au 1/100 MHz : le pic et la plage restent
check("écrire puis relire en wisycom : pic et plage gardés", (round(float(L2_.max()), 1), round(F2_[0], 2), round(F2_[-1], 2)),
      (round(float(Lw_.max()), 1), 470.2, 470.7))
for fm_ in ("wwb", "wsm", "tti", "csv"):
    txt_ = ns["scan_write"](Fw_, Lw_, fm_, title="x")
    F2_, L2_, i2_ = pst_(txt_)
    ok(f"écrire puis relire en {fm_} : rien de perdu", len(F2_) == len(Fw_) and np.allclose(np.interp(Fw_, F2_, L2_), Lw_, atol=0.51),
       f"{len(F2_)} {np.max(np.abs(np.interp(Fw_, F2_, L2_) - Lw_))}")
check("WWB comme ses exports : « 470.000,-104.531 »", ns["scan_write"]([470.0, 470.5], [-104.531, -98.0], "wwb"),
      "470.000,-104.531\n470.500,-98.000\n")
check("TTI comme ses exports : « 470.0000,-88.0 » CRLF", ns["scan_write"]([470.0], [-88.0], "tti"), "470.0000,-88.0\r\n")
wsm_ = ns["scan_write"](Fw_, Lw_, "wsm").split("\r\n")
check("WSM comme ses exports : RFUnit dB, plage, en-tête, « kHz;;dBµV »", ("RFUnit;dB" in wsm_, wsm_[14], wsm_[15], wsm_[16]),
      (True, "Frequency Range [kHz];470200;470700;25", "Frequency;RF level (%);RF level", "470200;;6"))
G_, V_ = ns["scan_uniform"]([470.0, 470.1, 470.3, 600.0, 600.1], [-90, -80, -70, -60, -65], 0.1)
ok("grille régulière : trou entre bandes au plancher, case vide interpolée", abs(V_[2] + 75) < 1e-6 and V_[100] == -90.0,
   f"{V_[:4]} {V_[100]}")
# --- ↶ / ↷ annuler / rétablir par instantanés
U_ = ns["UndoStack"](limit=3)
check("annuler : rien au départ", (U_.track("A", "a"), U_.back()), (False, None))
U_.track("A", "a"); U_.track("B", "b"); U_.track("C", "c")
check("annuler : même signature = rien de nouveau", U_.track("C2", "c"), False)
check("annuler : on revient en arrière dans l'ordre", (U_.back(), U_.back(), U_.back()), ("B", "A", None))
check("rétablir : dans l'autre sens", (U_.fwd(), U_.fwd(), U_.fwd()), ("B", "C", None))
U_.back(); U_.track("D", "d")
check("une nouvelle modification efface les rétablissements", U_.fwd(), None)
for k_ in "efghij":
    U_.track(k_, k_)
check("annuler : limité (pas de mémoire infinie)", len(U_.undo), 3)
U_.resync("autre")
check("annuler : resync ne crée pas de retour", (U_.track("j", "autre"), len(U_.undo)), (False, 3))
# --- plage d'export d'un scan (vers EazyRF, WWB, WSM…)
cr_ = ns["scan_crop"]
Fc_, Lc_, Mc_ = cr_(np.linspace(400, 800, 401), np.arange(401.0), -np.arange(401.0), lo=470, hi=608)
check("export : seulement 470–608 MHz", (Fc_[0], Fc_[-1], len(Fc_), Lc_[0], Mc_[-1]), (470.0, 608.0, 139, 70.0, -208.0))
check("export : bornes inversées remises dans l'ordre", len(cr_([1, 2, 3, 4], lo=3, hi=2)[0]), 2)
check("export : sans limite = tout", len(cr_([1, 2, 3])[0]), 3)
check("export : rien dans la plage = vide", len(cr_([1, 2, 3], [5, 6, 7], lo=10, hi=20)[1]), 0)
# --- 🌐 adresses réseau enregistrées (le Pi change d'IP selon le Wi-Fi)
np_ = ns["net_profiles_norm"]([dict(name="Pi maison", addr="192.168.1.20"), dict(name="", addr="1.2.3.4"),
                               dict(name="Pi festival", addr="10.0.0.5:6000"), dict(name="USB", addr="COM4"),
                               dict(name="Pi maison", addr="tinysa-sac.local"), "x"])
check("adresses : valides, noms uniques (le dernier gagne)", [(d["name"], d["addr"]) for d in np_],
      [("Pi festival", "10.0.0.5:6000"), ("Pi maison", "tinysa-sac.local")])
mg_ = ns["net_profiles_merge"](np_, [dict(name="Pi festival", addr="10.0.0.9"), dict(name="Pi hotspot", addr="172.20.10.2")])
check("adresses du show fusionnées (le show gagne à nom égal)", [(d["name"], d["addr"]) for d in mg_],
      [("Pi maison", "tinysa-sac.local"), ("Pi festival", "10.0.0.9"), ("Pi hotspot", "172.20.10.2")])
check("hôte et port", [ns["net_host_port"](x) for x in ("192.168.1.20", "pi.local:6000", "socket://10.0.0.1:5025", "COM4")],
      [("192.168.1.20", 5025), ("pi.local", 6000), ("10.0.0.1", 5025), None])
check("nom d'une adresse enregistrée", (ns["net_profile_name"](mg_, "10.0.0.9:5025"), ns["net_profile_name"](mg_, "1.1.1.1")),
      ("Pi festival", ""))
check("adresses et tinySA en réseau dans les shows", all(k in ns["SHOW_KEYS"] for k in ("net_profiles", "net_addr", "dev2")), True)
# --- 📍 gestion des scans gardés, comparaison, dans le temps, rapport d'étude de site
sd_ = ns["site_scan_doc"]
A_ = sd_("Grande scène", Fu_, Lu_, 1_700_000_000.0, dur=600)
Lb2_ = Lu_.copy(); Lb2_[500] = -40.0                          # 495.000 MHz vu seulement au Club
B_ = sd_("Club", Fu_, Lb2_, 1_700_003_600.0)
C_ = sd_("Grande scène · soir", Fu_, np.where(np.arange(len(Fu_)) == 200, -45.0, Lu_), 1_700_020_000.0,
         scene="Grande scène")
sc_ = [A_, B_, C_]
i_ = ns["site_scan_info"](A_)
check("info : scène, plage, bandes, pas, durée", (i_["scene"], round(i_["lo"]), round(i_["hi"]), i_["bands"], i_["step"], i_["dur"]),
      ("Grande scène", 470, 2480, 2, 50.0, 600.0))
check("info : durée inconnue -> None", ns["site_scan_info"](B_)["dur"], None)
check("durées lisibles", [ns["fmt_duration"](x) for x in (45, 720, 3900)], ["45 s", "12 min", "1 h 05"])
check("durée gardée dans la config", ns["site_scans_norm"]([A_])[0].get("dur"), 600.0)
r_, err_ = ns["site_rename"](sc_, "Grande scène · soir", "GS soir")
check("renommer : reste rangé dans sa scène", (err_, [ns["site_doc_scene"](d) for d in r_]),
      ("", ["Grande scène", "Club", "Grande scène"]))
check("renommer : nom déjà pris refusé", ns["site_rename"](sc_, "Club", "Grande scène")[1] != "", True)
m_ = ns["site_move"](sc_, "Club", "Grande scène")
check("changer de scène", ns["site_doc_scene"](next(d for d in m_ if d["name"] == "Club")), "Grande scène")
check("changer de scène : vide = son propre lieu", ns["site_doc_scene"](next(d for d in ns["site_move"](m_, "Club", "")
                                                                             if d["name"] == "Club")), "Club")
Fd_, Dd_ = ns["diff_spectra"](B_["f"], B_["l"], A_["f"], A_["l"])
ok("différence Club − Grande scène : +60 dB à 495 MHz", abs(Dd_[500] - 60.0) < 0.01)
ok("différence : 0 ailleurs, pas de valeur inventée", abs(np.nanmax(np.abs(np.delete(Dd_, 500)))) < 1e-6)
Fd2_, Dd2_ = ns["diff_spectra"](np.linspace(470, 3000, 50), np.zeros(50), Fu_, Lu_)
ok("différence : rien entre les bandes de B (NaN)", np.isnan(Dd2_[(Fd2_ > 521) & (Fd2_ < 2399)]).all())
check("dans le temps : les scans d'une scène dans l'ordre", [d["name"] for d in ns["scene_timeline"](sc_, "Grande scène")],
      ["Grande scène", "Grande scène · soir"])
oh_ = ns["only_here"](sc_, "Club", -80.0)
check("vu seulement ici : 495 MHz au Club", [round(x["f"], 3) for x in oh_], [495.0])
check("vu seulement ici : rien de propre à la Grande scène (son scan du soir est la même scène)",
      ns["only_here"](sc_, "Grande scène", -80.0), [])
h_ = ns["site_report_html"](sc_, -80.0, "Étude", "Festival X", "01/11/2026")
ok("rapport : chaque scan, la fusion, le temps", all(k in h_ for k in ("Club", "Tout le site", "Dans le temps", "Apparus",
                                                                       "Vus seulement ici", "<svg")), "")
ok("rapport : 480 MHz apparu le soir sur la Grande scène", "480.000 MHz" in h_.split("Dans le temps")[1])
check("rapport : aucun scan", "Aucun scan gardé" in ns["site_report_html"]([], -80.0), True)
d_ = ns["site_scan_doc"]("Grande scène", Fa_[:3], La_[:3], 1000.0)
check("lieu : version compacte", (d_["name"], d_["f"], d_["l"]), ("Grande scène", [470.0, 470.025, 470.05], [-100.0, -100.0, -100.0]))
check("lieux lus d'un fichier : invalides écartés, nom unique", [x["name"] for x in ns["site_scans_norm"](
    [d_, dict(name="", f=[1, 2], l=[1, 2]), dict(name="B", f=[1], l=[1]), dict(d_, l=[-1.0, -2.0, -3.0])])], ["Grande scène"])

sfs_ = ns["sites_for_scope"]
_ss = [dict(name="Grande scène"), dict(name="Club")]
check("lieux : Global -> tous", [d["name"] for d in sfs_(_ss, None)], ["Grande scène", "Club"])
check("lieux : un groupe de la scène -> le scan de la scène", [d["name"] for d in sfs_(_ss, [("Club", "DJ")])], ["Club"])
check("lieux : scène sans scan -> rien", sfs_(_ss, [("Scène 3", None)]), [])

msi_ = ns["multi_site"]
ok("multi-lieux : 2 tinySA à 2 lieux", msi_({0: "A", 1: "B"}, 2))
ok("multi-lieux : même lieu = partage des bandes", not msi_({0: "A", 1: "A"}, 2))
ok("multi-lieux : un seul tinySA", not msi_({0: "A"}, 1))
ok("multi-lieux : le 2ᵉ hors ligne", not msi_({0: "A", 1: "B"}, 2, [True, False]))
ok("multi-scènes : mêmes scènes = partage", not msi_({0: ["A", "B"], 1: ["B", "A"]}, 2))
ok("multi-scènes : scènes différentes", msi_({0: ["A", "B"], 1: ["C"]}, 2))
ok("multi-scènes : le 2ᵉ sans scène", not msi_({0: ["A"], 1: []}, 2))
dsn_ = ns["dev_scenes_norm"]
check("scènes des tinySA : ancien réglage à 1 lieu", dsn_({"0": "Grande scène", "1": ""}), {0: ["Grande scène"]})
check("scènes des tinySA : listes, doublons, clés inconnues", dsn_({"0": ["A", "A", " B "], "1": ["C"], "8": ["X"]}),
      {0: ["A", "B"], 1: ["C"]})
check("scènes des tinySA : config abîmée", dsn_("n'importe quoi"), {})
pc_ = ns["palette_color"]
check("palette tinySA : fond (couleur 0)", pc_(["color", "  0: 0x000000", "  1: 0xffffff", "ch> "], 0), 0)
check("palette tinySA : couleur 1", pc_([" 0: 0x101010", " 1: 0xffffff"], 1), 0xFFFFFF)
check("palette tinySA : rien compris", pc_(["usage: color"], 0), None)
pd_ = ns["parse_deviceid"]
check("numéro gravé lu", pd_(["deviceid", "deviceid 3", "ch> "]), 3)
check("numéro gravé : vieux firmware", pd_(["?"]), None)

# --- scan WWB natif (.sdb3) : vrai fichier envoyé par Clément (SLXD4, bande H56, WWB 7)
_sdb = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "wwb_slxd4_scan.sdb3"), "rb").read()
Fs, Ls, inf_s = parse_scan_text(ns["decode_text"](_sdb))
check("sdb3 : 1 751 points", len(Fs), 1751)
ok("sdb3 : plage H56 518,125 – 561,875 MHz", abs(Fs[0] - 518.125) < 1e-6 and abs(Fs[-1] - 561.875) < 1e-6)
ok("sdb3 : pas de 25 kHz", abs(Fs[1] - Fs[0] - 0.025) < 1e-9)
ok("sdb3 : niveaux en dBm plausibles (dixièmes)", -110 < Ls.min() < -100 and -75 < Ls.max() < -65
   and abs(Ls[0] + 99.0) < 1e-6, f"{Ls.min()} {Ls.max()} {Ls[0]}")
ok("sdb3 : format reconnu", inf_s["fmt"] == "sdb3" and "SLXD4" in inf_s["title"])
# deux balayages -> max gardé ; « pas de mesure » (-1400) retiré
_i = _sdb.index(b"@Binary:") + 8
_j = _sdb.index(b"@Extended:")
_sw = bytearray(_sdb[_i:_j])
_sw2 = bytearray(_sw)
_sw2[12:14] = (-500).to_bytes(2, "big", signed=True)        # 1er point du 2ᵉ balayage : -50 dBm
_sw2[14:16] = (-1400).to_bytes(2, "big", signed=True)       # 2ᵉ point : pas de mesure (le 1er balayage compte)
F2, L2, i2 = ns["parse_sdb3"](_sdb[:_i] + bytes(_sw) + bytes(_sw2) + _sdb[_j:])
ok("sdb3 : 2 balayages -> max hold", abs(L2[0] + 50) < 1e-6 and abs(L2[1] - Ls[1]) < 1e-6 and "2 balayage" in i2["note"])
try:
    ns["parse_sdb3"](b"//@ShureScan\n{}")
    ok("sdb3 abîmé : erreur claire", False)
except ValueError:
    ok("sdb3 abîmé : erreur claire", True)

# --- 🎒 terrain : plusieurs scans gardés par scène
sn_ = ns["snapshot_name"]
check("scan gardé : nom « scène · étiquette »", sn_("Club", " jardin ", set(), "14:32"), "Club · jardin")
check("scan gardé : sans étiquette = l'heure", sn_("Club", "", set(), "14:32"), "Club · 14:32")
check("scan gardé : nom unique", sn_("Club", "bar", {"Club · bar", "Club · bar (2)"}, "x"), "Club · bar (3)")
_d1 = ns["site_scan_doc"]("Club · bar", [470, 471], [-90, -80], 1.0, scene="Club")
_d0 = ns["site_scan_doc"]("Club", [470, 471], [-95, -85], 2.0)
ok("scan gardé : sa scène est notée (pas pour le continu)", _d1["scene"] == "Club" and "scene" not in _d0)
check("scans d'une scène : continu + gardés", [d["name"] for d in ns["sites_for_scope"]([_d0, _d1, dict(name="Autre")],
                                                                                      [("Club", None)])], ["Club", "Club · bar"])
ok("scène gardée relue de la config", ns["site_scans_norm"]([_d1])[0]["scene"] == "Club")
cd_ = ns["coord_docs"]
_all = [_d0, _d1, dict(name="Autre", f=[1, 2], l=[0, 0])]
check("coord par scène : ses scans seulement", [d["name"] for d in cd_(_all, "Club")], ["Club", "Club · bar"])
check("coord globale : tous les scans", len(cd_(_all, "all")), 3)
check("coord max hold actuel : aucun scan gardé", cd_(_all, "live"), [])
tq_ = ns["terrain_request"]
check("terrain : commande propre", tq_(dict(action="assign", dev="1", scenes=["A", " ", "B"])),
      dict(action="assign", dev=1, scenes=["A", "B"], label="", name=""))
for _bad in (dict(action="rm"), dict(action="delete"), "x"):
    try:
        tq_(_bad)
        ok(f"terrain : refusé {_bad}", False)
    except ValueError:
        ok(f"terrain : refusé {_bad}", True)

# --- 🎓 tutos et lexique
check("tutos : 6 parcours", ns["TOUR_KEYS"], ["ecran", "show", "spectre", "coord", "scenes", "live"])
gf_ = ns["glossary_find"]
ok("lexique : au moins 30 mots, tous expliqués", len(ns["GLOSSARY"]) >= 30 and all(len(x) > 30 for _t, x in ns["GLOSSARY"]))
ok("lexique : recherche sans accents ni majuscules", any(t.startswith("Rémanence") for t, _x in gf_("REMANENCE")))
ok("lexique : recherche dans l'explication", any(t == "TNT" for t, _x in gf_("télévision")))
check("lexique : rien = tout", len(gf_("")), len(ns["GLOSSARY"]))
# --- 📚 bibliothèque d'appareils EazyRF (.lst4) : échantillon inventé au même format
_lib = ns["parse_lst4"](open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "appareils_essai.lst4"),
                             "rb").read())
check("lst4 : 3 appareils", [d["name"] for d in _lib], ["Essai Micro Numérique G1", "Essai Micro Analogique B", "Essai Ear 1000"])
check("lst4 : valeurs (kHz -> MHz, virgules)", (_lib[0]["lo"], _lib[0]["hi"], _lib[0]["sep"], _lib[0]["filt"],
                                                _lib[0]["tol"]["2tx3"], _lib[0]["tol"]["3tx3"], _lib[0]["tol"]["5"]),
      (470.125, 514.0, 0.45, 50.0, 0.2, 0.0, 0.05))
ok("lst4 : pas absent -> 25 kHz ; fréquence image lue", _lib[2]["step"] == 0.025 and _lib[1]["img"] == 10.7
   and _lib[0]["img"] == 0.0)
check("lst4 : recherche (mots, sans accents)", [d["name"] for d in ns["rx_library_find"](_lib, "numerique g1")],
      ["Essai Micro Numérique G1"])
check("lst4 : recherche par type", len(ns["rx_library_find"](_lib, "in-ear")), 1)
_pr = ns["rx_custom_norm"]([ns["rx_from_library"](_lib[0])])[0]
ok("lst4 -> profil perso : valeurs, plage et source gardées", _pr[2]["filt"] == 50.0 and _pr[2]["tol"]["3tx3"] == 0.0
   and _pr[2]["lo"] == 470.125 and _pr[2]["src"] == "eazyrf", str(_pr))
for _bad in (b"<x/>", b"pas du xml"):
    try:
        ns["parse_lst4"](_bad)
        ok(f"lst4 refusé : {_bad[:10]!r}", False)
    except ValueError:
        ok(f"lst4 refusé : {_bad[:10]!r}", True)

# --- 🔕 alarmes moins envahissantes
scn_ = ns["sound_cfg_norm"]
check("son : nouveaux défauts (rejoué 30 s, CONFLIT confirmé 3 s, pas de bip « occupé »)",
      (scn_({})["repeat"], scn_({})["confirm"], scn_({})["occ_beep"]), (30, 3, False))
check("son : réglages lus", (scn_(dict(repeat=0, confirm=8, occ_beep=1))["repeat"], scn_(dict(confirm=999))["confirm"],
                            scn_(dict(repeat=7))["repeat"]), (0, 60, 30))
check("silence : temps restant", (ns["snooze_left"](100.0, 40.0), ns["snooze_left"](0, 40.0), ns["snooze_left"](30.0, 40.0)),
      (60, 0, 0))
_ab = ns["AlarmBook"](0)
_ab.raise_(("CONFLIT", 1), "CONFLIT", "x", 1.0, 2, 0.0, -50, "", "")
check("répétition « jamais » : la critique ne resonne pas", _ab.due_repeat(1000.0), [])

check("🌐 texte du lien réseau", (ns["net_text"](24 * 1024, 2.0, 0.008), ns["net_text"](1024, 2.0, None),
                                    ns["net_text"](10, 0, 0.1)), ("🌐 12 Ko/s · 8 ms", "🌐 0.5 Ko/s", ""))
# --- 📥 plan EazyRF (.ezrf3 et copier-coller) : fichiers INVENTÉS, même structure qu'un vrai document EazyRF 4.81
_ez = ns["parse_ezrf3"](open(os.path.join(DD_, "eazyrf_essai.ezrf3"), "rb").read())
check("ezrf3 : titre, 7 fréquences, 5 appareils, 2 interférences, canaux TV",
      (_ez["title"], len(_ez["rows"]), len(_ez["devices"]), _ez["interf"], _ez["tv"], _ez["warn"]),
      ("Festival d'essai", 7, 5, [521.35, 526.0], [23, 41], ""))
check("ezrf3 : hiérarchie Zone > Groupe > Section", [(r["zone"], r["scene"], r["group"], r["freq"]) for r in _ez["rows"]],
      [("Zone Nord", "Plateau A", "Micros", 500.1), ("Zone Nord", "Plateau A", "Micros", 503.45),
       ("Zone Nord", "Plateau A", "Micros", 512.0), ("Zone Nord", "Plateau A", "Ears", 530.25),
       ("Zone Nord", "Plateau B", "Micros", 534.875), ("Zone Sud", "Loge", "Micros", 540.0),
       ("Zone Sud", "Loge", "Talk", 455.5)])
check("ezrf3 : rayée / section hors fonction", [r["off"] for r in _ez["rows"]],
      [False, False, False, False, True, False, True])
_d0 = _ez["devices"][_ez["rows"][0]["dev"]]
check("ezrf3 : réglages d'appareil (kHz -> MHz, virgules)", (_d0["sep"], _d0["filt"], _d0["step"], _d0["tol"]["2tx3"],
                                                              _d0["tol"]["5"], _d0["img"]), (0.5, 32.0, 0.025, 0.1, 0.0, 0.0))
check("ezrf3 : fréquence image", _ez["devices"][_ez["rows"][2]["dev"]]["img"], 10.7)
check("ezrf3 : scan embarqué", (len(_ez["scan"][0]), float(_ez["scan"][0][60]), float(_ez["scan"][1].max())),
      (201, 500.0, -70.0))
_pn = ns["ezrf_profile_names"](_ez["devices"])
check("ezrf3 : même appareil, réglages différents -> 2 profils",
      sorted(n for n in _pn.values() if n.startswith("Essai RX Alpha")),
      ["Essai RX Alpha (sép. 2000 kHz · filtre 32 MHz)", "Essai RX Alpha (sép. 500 kHz · filtre 32 MHz)"])
_en = ns["ezrf_entries"](_ez)
check("ezrf3 -> lignes (zone en préfixe car 2 zones, nom vide -> appareil #n · k, hors fonction ignoré)",
      [e[:4] for e in _en],
      [("Chant 1", 500.1, "Zone Nord · Plateau A", "Micros"), ("Chant 2", 503.45, "Zone Nord · Plateau A", "Micros"),
       ("Essai RX Beta #1 · 1", 512.0, "Zone Nord · Plateau A", "Micros"),
       ("Ear 1", 530.25, "Zone Nord · Plateau A", "Ears"), ("Loge 1", 540.0, "Zone Sud · Loge", "Micros")])
check("ezrf3 : sans ignorer les hors fonction", len(ns["ezrf_entries"](_ez, False)), 7)
for _bad in (b"<x/>", b"pas du xml", b"<EazyRFds></EazyRFds>"):
    try:
        ns["parse_ezrf3"](_bad)
        ok(f"ezrf3 refusé : {_bad[:12]!r}", False)
    except ValueError:
        ok(f"ezrf3 refusé : {_bad[:12]!r}", True)
_ptx = open(os.path.join(DD_, "eazyrf_collage_essai.txt"), encoding="utf-8").read()
ok("collage EazyRF reconnu", ns["is_ezrf_paste"](_ptx))
ok("tableau ordinaire pas pris pour EazyRF", not ns["is_ezrf_paste"]("Nom;MHz\nA;500,1\n")
   and not ns["is_ezrf_paste"]("Chant 1\t500,100\n"))
_pp = ns["parse_ezrf_paste"](_ptx)
check("collage EazyRF : mêmes lignes que le document (sauf la rayée, que le collage ne dit pas)",
      [e[:4] for e in ns["ezrf_entries"](_pp)],
      [e[:4] for e in ns["ezrf_entries"](_ez, False) if e[2] != "Zone Sud · Loge" or e[3] != "Talk"])
check("collage EazyRF : appareils par nom", sorted(d["name"] for d in _pp["devices"].values()),
      ["Essai IEM", "Essai RX Alpha", "Essai RX Beta"])
_raw5 = open(os.path.join(DD_, "eazyrf_essai.ezrf3"), "rb").read().decode("utf-8").replace(
    "<Tolérance5e>0</Tolérance5e>", "<Tolérance5e>50</Tolérance5e><Eval5eOrdre>true</Eval5eOrdre>")
_t5 = lambda txt: sorted({d["tol"]["5"] for d in ns["parse_ezrf3"](txt.encode("utf-8"))["devices"].values()})
check("ezrf3 : 5ᵉ ordre coché sur l'appareil, document sans option -> compté", _t5(_raw5), [0.05])
check("ezrf3 : 5ᵉ ordre coupé dans les options du document -> pas compté (TechFest : 6 IM comme EazyRF)",
      _t5(_raw5.replace("</EazyRFds>", "<OptionsDt><Eval5eOrdre>false</Eval5eOrdre></OptionsDt></EazyRFds>")), [0.0])
check("profil perso : séparation jusqu'à 10 MHz", ns["rx_custom_norm"]([dict(name="x", sep=4.0)])[0][2]["sep"], 4.0)

# --- 🔀 diversity maison : deux tinySA sur deux antennes, meilleur niveau point par point
_dm = ns["diversity_merge"]
_F = np.array([500.0, 500.5, 501.0])
_r = _dm({0: (_F, np.array([-90.0, -50.0, -80.0]), 100.0), 1: (_F, np.array([-60.0, -70.0, -80.0]), 101.0)}, 101.0, 10.0)
check("diversity : max point par point + gagnant", (list(_r[1]), list(_r[2])), ([-60.0, -50.0, -80.0], [1, 0, 1]))
_r = _dm({0: (_F, np.array([-90.0, -50.0, -80.0]), 80.0), 1: (_F, np.array([-60.0, -70.0, -80.0]), 101.0)}, 101.0, 10.0)
check("diversity : balayage trop vieux de l'autre ignoré", list(_r[1]), [-60.0, -70.0, -80.0])
_r = _dm({0: (np.array([500.0, 501.0]), np.array([-40.0, -40.0]), 100.0),
          1: (_F, np.array([-60.0, -70.0, -80.0]), 101.0)}, 101.0, 10.0)
check("diversity : grilles différentes (interpolées)", list(_r[1]), [-40.0, -40.0, -40.0])
check("diversity : rien", _dm({}, 0, 10), None)
check("diversity : part des points", ns["diversity_share"]([np.array([0, 0, 1, 1]), np.array([0])]), [60, 40])

# --- plusieurs tinySA (jusqu'à 8)
check("rang des tinySA", [ns["dev_ord"](d) for d in (0, 1, 2, 7)], ["1er", "2ᵉ", "3ᵉ", "8ᵉ"])
_dx = ns["devx_norm"]([dict(addr=" COM5 ", name="Scène B", offset=99), "bancal", dict(on=False, addr="1.2.3.4:5025")] * 4)
check("tinySA 3 à 8 : nettoyés, 6 au plus", (len(_dx), _dx[0], _dx[1]["on"]),
      (6, dict(on=True, addr="COM5", name="Scène B", offset=40.0), False))
check("scènes : jusqu'au 8ᵉ tinySA", dsn_({"7": ["Club"]}), {7: ["Club"]})
_lm = [True, True, True, False, False, False, False, False]
check("répartition sur 3 tinySA", sorted(set(ns["assign_bands"]([dict(id=i, pts=100, dev=None) for i in range(6)], 8, _lm).values())),
      [0, 1, 2])
ok("4 tinySA, 4 scènes : chacun chez lui", msi_({0: ["A"], 1: ["B"], 2: ["C"], 3: ["D"]}, 8, [True] * 4 + [False] * 4))
_r = ns["diversity_merge"]({0: (np.array([1.0, 2.0]), np.array([-90.0, -50.0]), 10.0),
                            2: (np.array([1.0, 2.0]), np.array([-40.0, -80.0]), 10.5),
                            5: (np.array([1.0, 2.0]), np.array([-60.0, -30.0]), 11.0)}, 11.0, 10.0)
check("diversity à 3 tinySA : le meilleur des trois", (list(_r[1]), list(_r[2])), ([-40.0, -30.0], [2, 5]))

# --- 📸 états (Snapshots)
_sn = ns["states_norm"]([dict(name=" Artiste  A ", keys=[606500, "614000", 1, "x", 606500]), dict(name="artiste a", keys=[]),
                         "bancal", dict(name="", keys=[1])] + [dict(name=f"S{i}") for i in range(40)])
check("états : nettoyés (noms uniques, clés kHz valides, 30 au plus)", (_sn[0], len(_sn)),
      (dict(name="Artiste A", keys=[606500, 614000]), 30))
check("états : en pause = hors état sauf « toujours »", sorted(ns["state_off"]([1000, 2000], [1000, 2000, 3000, 4000], [4000])),
      [3000])
check("tech : changer d'état", ns["tech_request"](dict(action="state", name="  Artiste A ")), dict(action="state", name="Artiste A"))

# --- 🔗 plan EazyRF suivi : différences entre deux enregistrements
_e1 = [("HF 1", 500.1, "A", "Micros", None, ""), ("HF 2", 503.45, "A", "Micros", None, ""), ("Ear", 530.25, "A", "Ears", None, "")]
_e2 = [("HF 1", 500.1, "A", "Micros", None, ""), ("HF 2", 504.0, "A", "Micros", None, ""), ("HF 3", 507.2, "A", "Micros", None, "")]
_cur = [(ns["ezrf_id"](e[2], e[3], e[0]), e[1]) for e in _e1]
_d = ns["ezrf_diff"](_e2, _cur)
check("EazyRF suivi : ajout / changement / retrait", ([e[0] for e in _d["add"]], [(c[0], c[1], c[2]) for c in _d["change"]],
                                                      _d["remove"]),
      (["HF 3"], [("A|Micros|HF 2", 503.45, 504.0)], ["A|Ears|Ear"]))
check("EazyRF suivi : rien n'a changé", ns["ezrf_diff"](_e1, _cur), dict(add=[], change=[], remove=[]))

# --- ✅ prêt pour le show ?
_rc = ns["ready_checks"]
_lv = lambda i: {c["key"]: c["level"] for c in _rc(i)}
_good = dict(running=True, devs=[dict(name="tinySA 1", live=True)], sweep_age=2.0, cycle=1.5, watch_n=12, uncovered=0,
             no_status=0, plan_issues=0, volume=70, notify_mode="all", notify_ready=True, web_on=True, web_up=True,
             web_url="http://192.168.1.10:8080", web_pin=True, show_path="C:/show.tsashow", session_rec=True,
             disk_gb=120.0, windows=True, guarded=True)
check("prêt : tout bon", ns["ready_summary"](_rc(_good))[0], "ok")
check("prêt : arrêté = problème", _lv(dict(_good, running=False))["run"], "bad")
check("prêt : liaison perdue", (_lv(dict(_good, devs=[dict(name="Plateau", live=False)]))["run"],
                                [c["text"] for c in _rc(dict(_good, devs=[dict(name="Plateau", live=False)]))][0]),
      ("bad", "Liaison perdue : Plateau."))
check("prêt : plus de balayage", _lv(dict(_good, sweep_age=200.0))["run"], "warn")
check("prêt : démo pendant le show", _lv(dict(_good, demo=True))["demo"], "bad")
check("prêt : fréquence hors bandes", _lv(dict(_good, uncovered=2))["watch"], "bad")
check("prêt : liste vide", _lv(dict(_good, watch_n=0))["watch"], "bad")
check("prêt : plan à problème", _lv(dict(_good, plan_issues=3))["plan"], "warn")
check("prêt : silence en cours", _lv(dict(_good, snooze=300))["snooze"], "warn")
check("prêt : sortie audio débranchée", _lv(dict(_good, sound_device_missing=True))["sound"], "bad")
check("prêt : alertes incomplètes", _lv(dict(_good, notify_ready=False))["notify"], "bad")
check("prêt : web en panne", _lv(dict(_good, web_up=False))["web"], "bad")
check("prêt : show pas enregistré", _lv(dict(_good, show_path=""))["show"], "warn")
check("prêt : disque presque plein", (_lv(dict(_good, disk_gb=0.5))["disk"], _lv(dict(_good, disk_gb=3))["disk"]),
      ("bad", "warn"))
check("prêt : pas de garde (Windows)", _lv(dict(_good, guarded=False))["guard"], "info")
check("prêt : résumé", (ns["ready_summary"](_rc(dict(_good, show_path="")))[0],
                        ns["ready_summary"](_rc(dict(_good, running=False, show_path="")))), 
      ("warn", ("bad", "❌ 1 problème(s) à régler avant le show")))
check("prêt : micros éteints (je sais) rappelés", _lv(dict(_good, muted=2)).get("muted"), "info")
check("tech : éteint (je sais)", ns["tech_request"](dict(action="mute", key="606500", on=1)),
      dict(action="mute", key=606500, on=True))
ok("prêt : chaque correction est un nom de méthode", all(re.fullmatch(r"[a-z_]*", c["fix"]) for c in _rc({})))

# --- fiabilité des mesures (revue de code 7.41)
_sc = ns["scan_check"]
_F = np.linspace(470e6, 480e6, 101)
check("scan complet accepté", _sc(_F, np.full(101, -90.0), 470e6, 480e6, 101)[1], "ok")
_r = _sc(None, np.full(80, -90.0), 470e6, 480e6, 101)
check("scan tronqué sans fréquences : refusé (on ne sait pas quoi manque)", (_r[0], _r[1]), (None, "invalide"))
_r = _sc(np.linspace(470e6, 478e6, 81), np.full(81, -90.0), 470e6, 480e6, 101)
check("scan tronqué AVEC fréquences fiables : « court », gardé à sa place", (_r[1], len(_r[0]), _r[0][-1]),
      ("court", 81, 478e6))
_nan = np.full(101, -90.0); _nan[40] = np.nan
check("un seul NaN : balayage refusé", _sc(_F, _nan, 470e6, 480e6, 101)[1], "invalide")
check("refus du tinySA reconnu (try_cmd)", bool(ns["tinysa_refusal"](["USB disk mode active"])), True)
check("scan vide / absurde : invalide", (_sc(None, [-90.0], 470e6, 480e6, 101)[1],
                                         _sc(None, np.full(50, 900.0), 470e6, 480e6, 50)[1]), ("invalide", "invalide"))
_bad = _F.copy(); _bad[10] = _bad[9]
check("audit 7.52 : fréquence dupliquée (un pas de travers) : refusé", _sc(_bad, np.full(101, -90.0), 470e6, 480e6,
                                                                         101)[1], "invalide")
check("audit 7.52 : fréquences hors de la bande demandée : refusé",
      _sc(_F + 50e6, np.full(101, -90.0), 470e6, 480e6, 101)[1], "invalide")
_jit = _F.copy(); _jit[10] += 0.5e5; _jit[11] -= 0.5e5     # arrondi : 2 points confondus à ½ pas près
_r = _sc(_jit, np.full(101, -90.0), 470e6, 480e6, 101)
check("simple arrondi (< ½ pas) : grille théorique, accepté", (_r[1], bool(np.all(np.diff(_r[0]) > 0))), ("ok", True))
check("sans fréquences, complet : grille théorique", _sc(None, np.full(101, -90.0), 470e6, 480e6, 101)[1], "ok")
_pl = ns["parse_scan_lines"]
_fa, _la = _pl(["470000000 -90.5", "470100000 -91.0", "470200000 -89.0"])
check("parser : fréquence + niveau", (list(_fa), list(_la)), ([470e6, 470.1e6, 470.2e6], [-90.5, -91.0, -89.0]))
_fb, _lb = _pl(["-90.5", "-91.0", "-89.0"])
check("parser : niveaux seuls = pas de fréquences", (_fb, len(_lb)), (None, 3))
_fc, _lc = _pl(["470000000 -90.5", "-91.0", "470200000 -89.0"])
ok("audit 7.53 : réponse mélangée = fréquences illisibles (pas « niveaux seuls »)",
   _fc is not None and len(_fc) == 3 and bool(np.isnan(_fc).all()))
check("audit 7.53 : réponse mélangée complète refusée par scan_check",
      _sc(*_pl(["470000000 -90"] + ["-90"] * 100), 470e6, 480e6, 101)[1], "invalide")
_rng = np.random.default_rng(3)
_mk = lambda off, k: [(np.linspace(500, 510, 201), -95 + off + _rng.normal(0, 2, 201)) for _ in range(k)]
_a, _b = _mk(0, 3), _mk(0, 9)
_mh_a, _mh_b = ns["calib_maxhold"](_a, 3), ns["calib_maxhold"](_b, 3)
_r_eq = ns["calib_offset"](*_mh_a, *_mh_b)
_mh_all = (np.linspace(500, 510, 201), np.max(np.vstack([l for _f, l in _b]), axis=0))
_r_old = ns["calib_offset"](*_mh_a, *_mh_all)
ok("calibration : même nombre de balayages = pas de biais (bruit identique)", abs(_r_eq[0]) < abs(_r_old[0])
      and abs(_r_eq[0]) <= 1.0, f"{_r_eq} vs ancien {_r_old}")
_g = [(np.linspace(500, 510, 201), np.full(201, -90.0)), (np.linspace(500.5, 510.5, 201), np.full(201, -50.0))]
check("calibration : balayage à une autre grille ignoré", float(ns["calib_maxhold"](_g, 3)[1].max()), -90.0)
ok("calibration : répétabilité (médiane, écart)", ns["calib_repeat"](_mk(0, 3), _mk(-3, 3), 3)[0] > 1.5)
_Fu = np.array([1.0, 3.0, 2.0, np.nan, 4.0]); _Lu = np.array([-1.0, -3.0, -2.0, -9.0, -4.0])
check("grille nettoyée (triée, sans NaN)", [list(x) for x in ns["_clean_grid"](_Fu, _Lu)], [[1, 2, 3, 4], [-1, -2, -3, -4]])

# --- 🏠 accueil
_hn, _hs = ns["home_next"], ns["home_status"]
check("accueil : rien de branché -> ① tinySA", (_hn({}), _hs({})[0]), ("port", "idle"))
check("accueil : démo sans liste -> ② micros", _hn(dict(demo=True)), "list")
check("accueil : prêt -> ③ démarrer", _hn(dict(port=True, n_watch=3)), "run")
check("accueil : en marche -> plus d'étape", _hn(dict(running=True, port=True, n_watch=3)), "")
check("accueil : tout va bien", _hs(dict(running=True, port=True, n_watch=3, ok=2, free=1)),
      ("ok", "✔ Tout va bien — 2 micro(s) OK · 1 réserve(s) libre(s)"))
check("accueil : alarmes en tête", _hs(dict(running=True, port=True, n_watch=3, alarms=[("ABSENT", "HF 3")], ok=2))[0], "bad")
check("accueil : tinySA perdu", _hs(dict(running=True, port=True, n_watch=3, lost=["Plateau"]))[0], "bad")
check("accueil : micro muet = à surveiller, pas d'alarme", _hs(dict(running=True, port=True, n_watch=3, ok=1, silent=2))[0],
      "warn")
_run = dict(running=True, port=True, n_watch=3, ok=2, free=1)
check("accueil : démarré sans mesure -> jamais « tout va bien »", _hs(dict(_run, last_age=None))[0], "wait")
check("accueil : mesures périmées -> surveillance dégradée", _hs(dict(_run, last_age=60, stale_lim=15))[0], "bad")
_p = _hs(dict(_run, last_age=2, stale_lim=15, stale_names=["HF 3", "HF 7"]))
check("accueil : fréquences sans mesure -> partielle, en les nommant", (_p[0], "HF 3, HF 7" in _p[1]), ("warn", True))
check("accueil : 1re mesure jamais arrivée -> dégradée (pas « en cours » sans fin)",
      _hs(dict(_run, last_age=None, run_age=60, stale_lim=15))[0], "bad")
check("accueil : zoom live = surveillance partielle dite", _hs(dict(_run, last_age=1, stale_lim=15, zoom=True))[0], "warn")
check("accueil : juste démarré -> en cours", _hs(dict(_run, last_age=None, run_age=3, stale_lim=15))[0], "wait")
check("état des données : frais et complet -> rien à dire (le mode Show garde « Tout va bien »)",
      ns["data_status"](dict(last_age=2, stale_lim=15, run_age=50)), None)
check("état des données : micro faible = pas un problème de données",
      ns["data_status"](dict(last_age=2, stale_lim=15, run_age=50, weak=3)), None)
check("accueil : mesure fraîche -> tout va bien + âge", _hs(dict(_run, last_age=2, stale_lim=15)),
      ("ok", "✔ Tout va bien — 2 micro(s) OK · 1 réserve(s) libre(s) · mesure il y a 2 s"))
check("accueil : alarme prioritaire sur les données", _hs(dict(_run, last_age=None, alarms=[("ABSENT", "HF 1")]))[0], "bad")

# --- qualité de mesure (7.44)
_Fq = np.linspace(600, 610, 501); _Lq = np.full(501, -100.0); _Lq[250] = -60.0
check("bruit local : le signal lui-même est ignoré", round(ns["noise_floor"](_Fq, _Lq, 605.0), 1), -100.0)
check("bruit local : trop peu de points -> None", ns["noise_floor"]([1, 2], [-90, -80], 1.5), None)
check("marge : très bon / juste / noyé", [ns["snr_view"](m)[1] for m in (25, 8, 2)], ["ok", "warn", "bad"])
check("marge : une réserve propre = ok, une réserve occupée = bad", [ns["snr_view"](m, True)[1] for m in (2, 15)],
      ["ok", "bad"])
check("saturation : seuils, plus tôt avec le LNA", [ns["sat_level"](x) for x in (-40, -20, -10, None)]
      + [ns["sat_level"](-35, True)], ["ok", "warn", "bad", "ok", "warn"])
check("résolution : deux micros à 60 kHz avec un pas de 50 kHz = confondus",
      [p_[:3] for p_ in ns["resolution_pairs"]([("A", 606.500, 0.05), ("B", 606.560, 0.05), ("C", 610.0, 0.05)], 0.0)],
      [("A", "B", 0.06)])
check("résolution : pas fin = OK", ns["resolution_pairs"]([("A", 606.500, 0.01), ("B", 606.560, 0.01)], 0.0), [])
_lvq = lambda i: {c["key"]: c["level"] for c in ns["ready_checks"](i)}
check("prêt : saturation signalée", _lvq(dict(running=True, sat="bad", sat_dbm=-8.0)).get("sat"), "bad")
check("prêt : marge faible, résolution, mesures anciennes",
      [_lvq(dict(running=True, low_snr=["HF 2"], res_pairs=[("A", "B", 0.06, 0.05)], stale=2)).get(k)
       for k in ("snr", "res", "stale")], ["warn", "warn", "warn"])
check("accueil : saturation = orange", ns["home_status"](dict(running=True, port=True, n_watch=2, ok=2, sat="warn",
                                                              sat_dbm=-20.0))[0], "warn")

# --- plans des autres logiciels (7.48, vrais fichiers de Clément : .shw, .wsm, .cug, .wshow, .acp ; essais inventés)
_pp = ns["parse_plan_file"]
def _plan(fn):
    return _pp(open(os.path.join(DD_, fn), "rb").read(), fn)
_d, _k = _plan("wwb_essai.shw")
_e = ns["ezrf_entries"](_d)
check("WWB .shw : fréquences coordonnées, noms en double numérotés, zone = scène",
      (_k, [(n, f, sc, g) for n, f, sc, g, *_ in _e]),
      ("Shure WWB", [("Chant", 542.85, "", "AD G56"), ("Shure 1", 564.8, "", "AD G56"), ("Shure 2", 577.6, "", "AD G56"),
                     ("Ears batteur", 609.075, "Scène B", "PSM300 K3E")]))
_d, _k = _plan("wsm_essai.wsm")
_e = ns["ezrf_entries"](_d)
check("WSM .wsm : 3 fréquences, groupe = type de récepteur", (_k, [(n, f, g) for n, f, _sc, g, *_ in _e]),
      ("Sennheiser WSM", [("EM3731 1", 560.0, "EM 3731/3732"), ("EM3731 2", 559.25, "EM 3731/3732"),
                          ("Retour 1", 557.625, "EM 300-500 G4")]))
_dv = sorted(_d["devices"].values(), key=lambda p: p["name"])
check("WSM .wsm : règles lues (écart, tolérances, plage)",
      [(p["name"], p["sep"], p["tol"]["2tx3"], p["tol"]["3tx3"], p["lo"], p["hi"]) for p in _dv],
      [("EM 300-500 G4", 0.375, 0.15, 0.075, 520.0, 558.0), ("EM 3731/3732", 0.3, 0.1, 0.075, 470.0, 560.0)])
_d, _k = _plan("shure_essai.cug")
check("groupe Shure .cug", (_k, [(r["name"], r["freq"]) for r in _d["rows"]]),
      ("Shure (groupe)", [("AD G56 · 1", 482.7), ("AD G56 · 2", 513.8), ("AD G56 · 3", 534.375)]))
_d, _k = _plan("wisycom_essai.wshow")
check("Wisycom .wshow : émetteurs gardés, récepteurs sans fréquence signalés",
      (_k, [(r["name"], r["freq"]) for r in _d["rows"]], [p_["name"] for p_ in _d["pending"]] == ["ARR 1", "ARR 2"]),
      ("Wisycom Manager", [("IEM 1", 670.0), ("IEM 2", 642.0)], True))
_rx_only = open(os.path.join(DD_, "wisycom_essai.wshow"), encoding="utf-8").read()
_rx_only = _rx_only[:_rx_only.index('    <Category CategoryName="Unknown">\n      <Device DeviceNum="2"')] + "  </DeviceList>\n</ShowFile>\n"
_dr, _ = _pp(_rx_only.encode("utf-8"), "rx.wshow")
check("Wisycom : show sans émetteur -> récepteurs « à compléter » (pas d'erreur)",
      (len(_dr["rows"]), [p_["name"] for p_ in _dr["pending"]]), (0, ["ARR 1", "ARR 2"]))
_nm = ns["name_match"]
_cands = ["HF 1 DEPART", "IEM 1 DEPART", "HF 3 ARRIVEE", "HF 2 SCENE", "Chant"]
check("nom : « DEP 1 » ambigu (HF et IEM) sans indice", _nm("DEP 1", _cands), None)
check("nom : récepteur de micros -> IEM écarté", _nm("DEP 1", _cands, ("IEM",)), 0)
check("nom : abréviations « ARR 3 », « SCE 2 »", (_nm("ARR 3", _cands), _nm("SCE 2", _cands)), (2, 3))
check("nom : identique (casse, espaces)", _nm(" chant ", _cands), 4)
check("nom : rien de proche", _nm("Trumpet 1", _cands), None)
_df = ns["plan_fill_pending"](_dr, {"ARR 1": 578.05, "ARR 2": "x"})
check("complétés à la main : ajoutés au plan, le reste reste à compléter",
      ([(r["name"], r["freq"], r["group"]) for r in _df["rows"]], [p_["name"] for p_ in _df["pending"]]),
      ([("ARR 1", 578.05, "MRK980")], ["ARR 2"]))
_d, _k = _plan("dpa_essai.acp")
check("DPA .acp : canaux, profil du mode (écart 500 kHz)",
      (_k, _d["title"], [(r["name"], r["freq"]) for r in _d["rows"]], [p.get("sep") for p in _d["devices"].values()]),
      ("DPA", "Essai DPA", [("Com1", 470.2), ("Com2", 500.9)], [0.5]))
check("plan : format reconnu au contenu (sans extension)", _pp(open(os.path.join(DD_, "wwb_essai.shw"), "rb").read(), "x")[1],
      "Shure WWB")
try:
    _pp(b"rien", "x.txt")
    ok("plan : format inconnu refusé", False)
except ValueError:
    ok("plan : format inconnu refusé", True)
_d1, _ = _plan("wwb_essai.shw")
_d2 = dict(_d1, rows=[dict(r, freq=(565.0 if r["name"] == "Shure 1" else r["freq"])) for r in _d1["rows"]][:-1])
for r in _d2["rows"]:
    r["name"] = r["name"]
_cur = [(ns["ezrf_id"](sc, g, n), f) for n, f, sc, g, *_ in ns["ezrf_entries"](_d1)]
_df = ns["ezrf_diff"](ns["ezrf_entries"](_d2), _cur)
check("suivi : une fréquence changée + une retirée dans WWB", (len(_df["add"]), len(_df["change"]), len(_df["remove"])), (0, 1, 1))

# --- 🔎 chercher une fonction (7.47)
_fm = ns["feature_match"]
_its = [("🎚 Surveiller › 🆘 Fréquence de secours…", "Propose des fréquences libres"), ("🔌 Matériel › 📡 Relais", "Partage"),
        ("📋 Préparer › 📥 Importer", "fichier EazyRF")]
check("recherche : sans accent ni majuscule", _fm(_its, "frequence SECOURS"), [0])
check("recherche : dans la bulle aussi", _fm(_its, "eazyrf"), [2])
check("recherche : vide = tout", _fm(_its, ""), [0, 1, 2])
check("recherche : rien", _fm(_its, "zzz"), [])

# --- fiches « problème » (7.46)
_pk = ns["problem_key"]
check("fiche : port pris par tinySA-App", _pk("could not open port 'COM4': PermissionError(13, 'Accès refusé.', None, 5)"), "busy")
check("fiche : port absent", _pk("could not open port 'COM9': FileNotFoundError(2, 'Le fichier spécifié est introuvable.')"), "gone")
check("fiche : mode disque USB", _pk(ns["tinysa_refusal"](["usb disk mode active"])), "usbdisk")
check("fiche : relais pas lancé", _pk("[Errno 111] Connection refused"), "net_refused")
check("fiche : Pi injoignable", _pk("timed out"), "net_unreach")
check("fiche : tinySA muet", _pk("tinySA muet depuis 12 s"), "mute")
check("fiche : inconnu", _pk("bizarre"), "other")
_c = ns["problem_card"]("x", "no_port")
ok("fiche : titre, explication, étapes, détail", _c["title"] and _c["what"] and len(_c["steps"]) >= 2 and _c["detail"] == "x")
ok("fiche : conséquence toujours dite (liaison perdue ≠ arrêt)", all(ns["problem_card"]("", k)["impact"] for k in ns["PROBLEM_CARDS"])
   and ns["problem_card"]("", "lost")["impact"] != ns["problem_card"]("", "busy")["impact"])
ok("fiche : toutes complètes", all(t and w and st for t, w, st in ns["PROBLEM_CARDS"].values()))

# 7.52 : seuils automatiques (bruit de fond appris)
_et, _ft, _fc = ns["eff_thresholds"], ns["floor_track"], ns["floor_curve"]
check("seuil auto : bruit + marges", _et(None, None, False, 8, -80, -90, -105.0, (10.0, 4.0)), (-95.0, -101.0))
check("seuil auto : seuil propre prioritaire", _et(-70, None, False, 8, -80, -90, -105.0, (10.0, 4.0))[0], -70)
check("seuil auto : sans bruit connu = seuil global", _et(None, None, False, 8, -80, -90, None), (-80, -90))
check("bruit appris : 1re mesure", _ft(None, -100.0, 1), -100.0)
ok("bruit appris : redescend vite", _ft(-90.0, -100.0, 5) < -96)
ok("bruit appris : remonte lentement", -100.0 < _ft(-100.0, -90.0, 5) < -99.5)
check("bruit appris : ne remonte pas si occupé", _ft(-100.0, -60.0, 600, busy=True), -100.0)
ok("bruit appris : redescend même si occupé", _ft(-90.0, -100.0, 5, busy=True) < -96)
_a = _ft(np.array([-100.0, -100.0]), np.array([-60.0, -60.0]), 600, busy=np.array([True, False]))
ok("bruit appris : tableau, case occupée gelée", _a[0] == -100.0 and _a[1] > -80)
_F = np.arange(470.0, 480.0, 0.025)
_L = np.full(len(_F), -105.0)
_L[(np.abs(_F - 474.0) < 0.05)] = -40.0                      # une porteuse
_Fc, _Lc = _fc(_F, _L)
ok("courbe de bruit : la porteuse ne relève pas le bruit", np.nanmax(np.abs(_Lc + 105.0)) < 0.5)
_F2 = np.concatenate([np.arange(470.0, 472.0, 0.025), np.arange(480.0, 482.0, 0.025)])
_Fc2, _Lc2 = _fc(_F2, np.full(len(_F2), -100.0))
ok("courbe de bruit : trou entre deux bandes = NaN", np.isnan(_Lc2[(_Fc2 > 474) & (_Fc2 < 478)]).all())
ok("seuils auto dans les shows", all(k in ns["SHOW_KEYS"] for k in ("thr_auto", "auto_occ", "auto_weak")))

_pb = ns["plain_btn_text"]
check("7.54 : bouton sans emoji de tête", [_pb(x) for x in ("🎪 Shows", "▶ Démarrer", "⚡ Auto · 50 kHz", "+ Ajouter")],
      ["Shows", "Démarrer", "Auto · 50 kHz", "+ Ajouter"])
check("7.54 : bouton-icône gardé", [_pb(x) for x in ("🔔", "🔔 1", "⚙", "")], ["🔔", "🔔 1", "⚙", ""])
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
