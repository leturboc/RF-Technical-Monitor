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
check("show : PAS les préférences du logiciel", [k for k in ("theme", "log_dir", "web", "dev2", "markers") if k in doc["show"]], [])
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
ok("conv : WWB = « 470.000, -98 »", t_.splitlines()[0] == "470.000, -98", t_.splitlines()[0])
F2_, L2_, i2_ = pst_(sw_(Fc, Lc, "wsm", title="Test"))
ok("conv : WSM écrit → relu comme un export WSM, niveaux à 0,1 dB près", i2_["fmt"] == "wsm"
   and np.allclose(F2_, Fc) and np.allclose(L2_, Lc, atol=0.15), str((i2_, L2_)))
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
check("scènes des tinySA : listes, doublons, clés inconnues", dsn_({"0": ["A", "A", " B "], "1": ["C"], "7": ["X"]}),
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
print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
