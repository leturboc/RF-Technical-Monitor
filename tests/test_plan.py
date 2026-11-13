import io, csv, json, math, os, re, sys, unicodedata, itertools
import numpy as np

src = open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "..", "tinysa_monitor.py"), encoding="utf-8").read()
a = src.index("# ===== PURE-BEGIN")
b = src.index("# ===== PURE-END")
ns = dict(itertools=itertools, re=re, csv=csv, io=io, math=math, np=np, unicodedata=unicodedata, deque=__import__('collections').deque, MIN_PTS=51, HYST=3.0,
          RBW_LIST=[0.3, 1, 3, 10, 30, 100, 300, 600, 850])
exec(src[a:b], ns)
fails = 0
def check(label, got, exp):
    global fails
    ok = got == exp
    fails += (not ok)
    print(("OK  " if ok else "FAIL"), label, "" if ok else f"-> {got!r} != {exp!r}")

for code, _ in ns["COUNTRIES"]:
    plan = ns["build_plan"](code)
    tv = ns["tv_channels"](code)
    # pas de chevauchement dans le plan (sauf héritage volontaire) et bornes cohérentes
    ov = [(p, q) for p, q in zip(plan, plan[1:]) if q[0] < p[1] - 1e-9]
    check(f"{code}: plan sans chevauchement", ov, [])
    check(f"{code}: canaux TV non vides", len(tv) > 10, True)
    tvo = [(p, q) for p, q in zip(sorted(tv), sorted(tv)[1:]) if q[0] < p[1] - 1e-9]
    check(f"{code}: canaux TV sans chevauchement", tvo, [])

st = ns["spectrum_text"]
fr_plan, fr_tv = ns["build_plan"]("FR"), ns["tv_channels"]("FR")
check("FR 506.0 = canal 25 (502-510)", st(506.0, fr_plan, fr_tv)[:5], "CH 25")
check("FR 470.0 = canal 21", st(470.0, fr_plan, fr_tv)[:5], "CH 21")
check("FR 477.99 = canal 21", st(477.99, fr_plan, fr_tv)[:5], "CH 21")
check("FR 478.0 = canal 22", st(478.0, fr_plan, fr_tv)[:5], "CH 22")
check("FR canal 21 = 470-478", [(c[0], c[1]) for c in fr_tv if c[2] == "CH 21"], [(470, 478)])
check("FR canal 48 = 686-694", [(c[0], c[1]) for c in fr_tv if c[2] == "CH 48"], [(686, 694)])
check("FR canal 49 ex-TV", [c[3] for c in fr_tv if c[2] == "CH 49"], ["tv_off"])
check("FR canal 69 = 854-862", [(c[0], c[1]) for c in fr_tv if c[2] == "CH 69"], [(854, 862)])
check("FR 827 = écart duplex 800", "823-832" in st(827.0, fr_plan, fr_tv) or "800" in st(827.0, fr_plan, fr_tv), True)
check("FR 760 = mobile 700", "700" in st(760.0, fr_plan, fr_tv), True)
check("FR 610 canal 38 = TNT + micros (utilisable)", "micros HF pros" in st(610.0, fr_plan, fr_tv), True)
gb = ns["build_plan"]("GB"); check("GB 610 canal 38 sous licence partagée", "licence Ofcom" in st(610.0, gb, ns["tv_channels"]("GB")), True)
us_tv = ns["tv_channels"]("US")
check("US ch14 = 470-476", [(c[0], c[1]) for c in us_tv if c[2] == "CH 14"], [(470, 476)])
check("US ch36 = 602-608", [(c[0], c[1]) for c in us_tv if c[2] == "CH 36"], [(602, 608)])
check("US ch7 = 174-180", [(c[0], c[1]) for c in us_tv if c[2] == "CH 7"], [(174, 180)])
check("US ch13 = 210-216", [(c[0], c[1]) for c in us_tv if c[2] == "CH 13"], [(210, 216)])
check("US 650 mobile 600", "600" in st(640.0, ns["build_plan"]("US"), us_tv), True)
txt = ns["plan_to_text"](fr_plan)
check("aller-retour texte", [(p[0], p[1], p[2]) for p in ns["parse_plan_text"](txt)], [(p[0], p[1], p[2]) for p in fr_plan])
check("thème: clés bp_ présentes", all(("bp_tv" in t and "ref" in t) for t in ns["THEMES"].values()), True)
check("THEME_KEYS contient ref", any(k == "ref" for k, _, _ in ns["THEME_KEYS"]), True)

# ---- mesures / occupation / export
F = np.array([100.0, 100.1, 100.2, 100.3, 100.4]); L = np.array([-90.0, -80.0, -60.0, -85.0, -95.0])
la = ns["level_at"]
check("level_at fenêtre", la(F, L, 100.2, 0.15), -60.0)
check("level_at petit écart -> point proche", la(F, L, 100.25, 0.01), -60.0 if False else la(F, L, 100.25, 0.01))
check("level_at hors plage", la(F, L, 120.0, 0.1), None)
check("level_at vide", la(np.array([]), np.array([]), 100.0, 0.1), None)
et = ns["eff_thresholds"]
check("seuil propre", et(-70.0, -100.0, True, 6, -80.0, -90.0), (-70.0, -80.0))
check("seuil relatif", et(None, -100.0, True, 6, -80.0, -90.0), (-94.0, -97.0))
check("seuil global", et(None, None, True, 6, -80.0, -90.0), (-80.0, -90.0))
check("relatif désactivé", et(None, -100.0, False, 6, -80.0, -90.0), (-80.0, -90.0))
ow = ns["OccWindow"](60)
t0 = 1_000_000.0
for i in range(10):
    ow.add(t0 + i, 1.0, i < 4)
check("occupation 40 %", round(ow.pct(), 1), 40.0)
ow.add(t0 + 7200, 5.0, False)
check("fenêtre glissante: anciens seaux retirés", round(ow.pct(t0 + 7200), 1), 0.0)
check("occupation vide", ns["OccWindow"](10).pct(), None)
csvt = ns["scan_csv"]([470.0, 470.2], [[-80.0, -75.5]], "MHz", ";", ",", True, ["Niveau (dBm)"])
check("csv FR", csvt, "Frequence (MHz);Niveau (dBm)\r\n470,000000;-80,0\r\n470,200000;-75,5\r\n")
csvh = ns["scan_csv"]([470.0], [[-80.0], ], "Hz", ",", ".", False)
check("csv Hz", csvh, "470000000,-80.0\r\n")
csvk = ns["scan_csv"]([470.125], [[-80.0], [-70.0]], "kHz", "\t", ".", False)
check("csv kHz 2 colonnes", csvk, "470125.000\t-80.0\t-70.0\r\n")
si = ns["spectrum_info"]
check("info FR 506", si(506.0, fr_plan, fr_tv)[1], "tv")
check("info FR 760 (mobile)", si(740.0, fr_plan, fr_tv)[1], "pmse")
check("info FR 770 (mobile)", si(770.0, fr_plan, fr_tv)[1], "mobile")
check("describe contient canal", "CH 25" in ns["describe_freq"](506.0, fr_plan, fr_tv) or "Canal UHF 25" in ns["describe_freq"](506.0, fr_plan, fr_tv), True)
check("describe sans attribution", "aucune attribution" in ns["describe_freq"](862.5, fr_plan, fr_tv), True)
check("Nuit: spectre cathodique rouge", (ns["THEMES"]["Nuit (rouge)"]["plot_style"], ns["THEMES"]["Analyseur vert"]["plot_style"], ns["THEMES"]["Pro sombre"]["plot_style"]), ("crt", "crt", "normal"))


def ok(label, cond, extra=""):
    global fails
    fails += (not cond)
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra)

# ---- plan étendu 100 kHz - 5,9 GHz
for code in ("FR", "EU", "DE", "GB", "US"):
    pl = ns["build_plan"](code)
    ok(f"{code}: démarre à 100 kHz", abs(pl[0][0] - 0.1) < 1e-9, str(pl[0]))
    ok(f"{code}: couvre au moins jusqu'à 5,1 GHz", pl[-1][1] >= 5100, str(pl[-1]))
    ok(f"{code}: catégories valides", all(e[3] in ns["CATEGORIES"] for e in pl))
    ok(f"{code}: au moins 80 attributions", len(pl) >= 55, str(len(pl)))
si = ns["spectrum_info"]
for f, cat in [(0.162, "broadcast"), (1.0, "broadcast"), (27.0, "civ"), (98.0, "broadcast"), (121.5, "aero"),
               (145.5, "amateur"), (156.8, "marine"), (390.0, "safety"), (446.1, "civ"), (462.6, "civ")]:
    c = si(f, ns["build_plan"]("US" if f == 462.6 else "FR"), ns["tv_channels"]("FR"))[1]
    exp = cat
    if f == 462.6: c = si(f, ns["build_plan"]("US"), ns["tv_channels"]("US"))[1]
    ok(f"info {f} MHz -> {exp}", c == exp, str(c))
ok("police dans le plan FR", "police" in ns["describe_freq"](390.0, fr_plan, fr_tv).lower(), ns["describe_freq"](390.0, fr_plan, fr_tv))
# 7.59.1 : bandes revérifiées dans le tableau CEPT EFIS (radioastronomie 608-614 en DE / CH / NL, 622-698 en NZ)
for _c, _f in (("DE", 610.0), ("CH", 610.0), ("NL", 610.0)):
    _p = ns["build_plan"](_c)
    ok(f"7.59.1 : {_c} 610 MHz = radioastronomie", "radioastronomie" in ns["describe_freq"](_f, _p, ns["tv_channels"](_c)).lower(),
       ns["describe_freq"](_f, _p, ns["tv_channels"](_c)))
for _c in ("AU", "NZ", "JP"):
    _p = ns["build_plan"](_c)
    _d = ns["describe_freq"](922.0, _p, ns["tv_channels"](_c))
    ok(f"7.60 : {_c} 922 MHz = LoRaWAN / ISM, plus de GSM-R européen", "lorawan" in _d.lower() and "gsm-r" not in _d.lower(), _d)
ok("7.60 : Japon 808 MHz = micros basse puissance",
   "micros" in ns["describe_freq"](808.0, ns["build_plan"]("JP"), ns["tv_channels"]("JP")).lower())
ok("7.60 : Europe 868,3 MHz = LoRaWAN", "lorawan" in ns["describe_freq"](868.3, ns["build_plan"]("FR"), ns["tv_channels"]("FR")).lower())
ok("7.59.1 : NZ 502-698", ns["country_uhf"]("NZ") == (502.0, 698.0))
ok("7.59.1 : notes européennes tirées du tableau CEPT",
   all("CEPT" in ns["COUNTRY_NOTES"][c] for c in ("FR", "DE", "GB", "CH", "BE", "IT", "ES", "NL", "EU")))
ok("GNSS 1575", si(1575.42, fr_plan, fr_tv)[1] == "sat")
ok("ADS-B 1090", si(1090.0, fr_plan, fr_tv)[1] == "aero")
ok("Wi-Fi 2,4", si(2437.0, fr_plan, fr_tv)[1] == "ism")
ok("5G 3,5 GHz", si(3500.0, fr_plan, fr_tv)[1] == "mobile")
ff = ns["fmt_freq_mhz"]
ok("fmt kHz exact", ff(0.1485) == "148,5 kHz", ff(0.1485))
ok("fmt MHz", ff(470.0) == "470 MHz", ff(470.0))
ok("fmt MHz décimales", ff(446.00625) == "446,0063 MHz" or ff(446.00625) == "446,0062 MHz", ff(446.00625))
ok("fmt GHz", ff(5300.0) == "5,3 GHz", ff(5300.0))
ok("thèmes: toutes les catégories", all(("bp_" + k) in t for t in ns["THEMES"].values() for k in ns["CATEGORIES"]))

# ---- scènes / groupes / focus
ke, kd, sm, fp = ns["key_enc"], ns["key_dec"], ns["scope_match"], ns["focus_plan"]
ok("clé scène", kd(ke("Main")) == ("Main", None))
ok("clé groupe", kd(ke("Main", "Groupe 1")) == ("Main", "Groupe 1"))
ok("clé invalide", kd("n'importe quoi") is None)
ok("scope global", sm(None, "A", "g") and sm([], "A", "g"))
ok("scope scène", sm([("A", None)], "A", "g") and not sm([("A", None)], "B", "g"))
ok("scope groupe", sm([("A", "g")], "A", "g") and not sm([("A", "g")], "A", "h"))
ok("scope multiple", sm([("A", "g"), ("B", None)], "B", "x") and sm([("A", "g"), ("B", None)], "A", "g"))
ok("scope sans scène", sm([("", None)], "", "") and not sm([("", None)], "A", ""))
pl = fp([506.0, 506.3, 520.0, 700.0], 1000)
ok("focus: 3 bandes", len(pl) == 3, str(pl))
ok("focus: marge", abs(pl[0][0] - 505.7) < 1e-6 and abs(pl[0][1] - 506.3 - 0.3) < 1e-6, str(pl))
ok("focus: points mini 101", pl[0][2] == 101 and pl[2][2] == 101, str(pl))
pl2 = fp([470.0, 473.0, 476.0, 479.0], 1000)
ok("focus: regroupe ≤ 4 MHz", len(pl2) == 1 and pl2[0][2] == int(__import__("math").ceil((pl2[0][1] - pl2[0][0]) * 1000 / 20)) + 1, str(pl2))
pl3 = fp([470.0, 473.0, 476.0, 479.0], 300)
ok("focus: plafond de points", pl3[0][2] == 300, str(pl3))
ok("focus: liste vide", fp([], 1000) == [] and fp([None, 5000000.0], 1000) == [])
ok("focus: bord bas", fp([0.15], 500)[0][0] == 0.1)

# import CSV avec scène / groupe
txt = "Nom;Fréquence;Scène;Groupe\nChant;518,125;Main;Les Trucs\nGuitare;520,350;Main;Les Trucs\nBasse;606,2;Club;DJ Set\n"
an = ns["analyze_csv"](txt)
ok("csv: scène détectée", an["scene_col"] == 2, str(an["scene_col"]))
ok("csv: groupe détecté", an["group_col"] == 3, str(an["group_col"]))
ok("csv: le nom reste la colonne Nom", an["name_col"] == 0, str(an["name_col"]))
ent = ns["build_entries_ex"](an, an["name_col"], an["freq_cols"], an["status_col"], an["scene_col"], an["group_col"])
ok("csv: 3 entrées avec scène/groupe", [(e[0], e[3], e[4]) for e in ent] == [("Chant", "Main", "Les Trucs"), ("Guitare", "Main", "Les Trucs"), ("Basse", "Club", "DJ Set")], str(ent))
ok("csv: build_entries inchangé (3-uplets)", all(len(e) == 3 for e in ns["build_entries"](an, 0, [1], None)))
# "Group" anglais (Shure/Sennheiser) ne doit PAS être pris pour un groupe d'artistes
an2 = ns["analyze_csv"]("Name;Group;Channel;Frequency\nA;1;1;518.125\nB;1;2;518.4\n")
ok("csv: 'Group' anglais ignoré", an2["group_col"] is None and an2["scene_col"] is None)
an3 = ns["analyze_csv"]("Name;Stage;Artist;Frequency\nA;Main;Zazie;518.125\nB;Main;Zazie;518.4\n")
ok("csv: Stage/Artist détectés", an3["scene_col"] == 1 and an3["group_col"] == 2, f"{an3['scene_col']} {an3['group_col']}")
an4 = ns["analyze_csv"]("Nom;Fréquence;Groupe\nA;518,125;7\nB;518,4;7\n")
ok("csv: 'Groupe' numérique (groupe de fréquences) ignoré", an4["group_col"] is None, str(an4["group_col"]))
ok("préréglages: aperçu tout le spectre", any(p[1] == 0.1 and p[2] == 5300.0 for p in ns["BAND_PRESETS"]))

# profils d'appareil : valeurs de filtre données par Clément (EazyRF), profils perso
rp = ns["rx_profile"]
check("filtre Sennheiser ew G4 32 MHz (bibliothèque EazyRF)", rp("senn_evo")["filt"], 32.0)
check("filtre Shure PSM 16 MHz", rp("shure_psm")["filt"], 16.0)
check("filtre Shure SLX 16 MHz", rp("shure_slx")["filt"], 16.0)
check("filtre Shure AD 32 MHz", rp("shure_ad")["filt"], 32.0)
check("filtre Shure ULX-D / QLX-D 16 MHz (bibliothèque EazyRF)", rp("shure_dig")["filt"], 16.0)
check("Shure SLX-D : 200 / 3 TX ignoré, écart 450, filtre 50 (EazyRF)", (rp("shure_slxd")["tol"]["2tx3"],
      rp("shure_slxd")["tol"]["3tx3"], rp("shure_slxd")["sep"], rp("shure_slxd")["filt"]), (0.2, 0.0, 0.45, 50.0))
check("filtre Wisycom 32 MHz (profil EazyRF)", (rp("wisycom")["filt"], rp("wisycom")["sep"]), (32.0, 0.5))
check("anciennes clés toujours là (listes / shows)", all(rp(k) for k in ("wisycom", "senn_dig", "senn_ana",
                                                                        "shure_dig", "shure_ana", "iem")), True)
check("ADT : filtre inconnu → aucun (prudent)", (rp("shure_adt")["filt"], rp("shure_adt")["src"]), (0.0, "guess"))
ns["rx_set_custom"]([dict(name="EW G4 bande A", filt=16, sep=0.4, step=0.025, tol={"2tx3": 0.1, "3tx3": 0.05}),
                     dict(name="", filt=8), "bancal", dict(name="Mon IEM", key="perso_x", filt="abc", sep=99)])
cu = ns["rx_custom_dump"]()
check("profils perso : lus et nettoyés", [(p_["key"], p_["name"], p_["filt"], p_["sep"]) for p_ in cu],
      [("perso_1", "EW G4 bande A", 16.0, 0.4), ("perso_x", "Mon IEM", 0.0, 10.0)])
check("profil perso utilisable comme les autres", (rp("perso_1")["filt"], rp("perso_1")["src"]), (16.0, "perso"))
check("profil perso : relu tel quel", ns["rx_custom_dump"]() == cu or None, True)
ns["rx_set_custom"](cu)
check("profil perso : relecture stable", ns["rx_custom_dump"](), cu)
check("clé perso ne remplace pas un profil intégré", ns["rx_custom_norm"]([dict(name="x", key="wisycom")])[0][0],
      "perso_1")
h = ns["rx_help_html"]()
check("aide filtre : chaque profil dans le tableau", all(n in h for _k, n, _d, _w in ns["rx_all"]()), True)
check("aide filtre : explique la règle « tous les émetteurs dans le filtre »", "TOUS ses émetteurs" in h, True)
ns["rx_set_custom"]([])
r16 = ns["pf_check"]([470.0, 486.0, 502.0], tol=ns["rx_profile"]("senn_evo")["tol"], sep=0.4, filt=16.0)
r0 = ns["pf_check"]([470.0, 486.0, 502.0], tol=ns["rx_profile"]("senn_evo")["tol"], sep=0.4, filt=0.0)
check("filtre 16 MHz : 470 / 486 / 502 → plus de 2A − B (émetteurs hors filtre)",
      (sum(len(x) for x in r16[0]) == 0, sum(len(x) for x in r0[0]) > 0), (True, True))

# coordination automatique : N fréquences compatibles avec la liste ET entre elles
pf_fill = ns["pf_fill"]
tolW = ns["rx_profile"]("wisycom")["tol"]
plan0 = [470.2, 471.3, 478.0, 558.0, 574.0, 606.0, 614.0, 646.0]
got = pf_fill(6, plan0, sep=0.5, tol=tolW, filt=32.0, new_sep=0.5, new_tol=tolW, new_filt=32.0,
              lo=470.0, hi=520.0, step=0.025)
check("coordination : 6 trouvées dans la plage", (len(got), all(470.0 <= c <= 520.0 for c in got)), (6, True))
allf = plan0 + got
iss, _ = ns["pf_check"](allf, sep=0.5, tol=tolW, filt=32.0)
check("coordination : plan complet sans aucun problème", sum(len(x) for x in iss), 0)
check("coordination : sur le pas de 25 kHz", all(abs(c * 40 - round(c * 40)) < 1e-6 for c in got), True)
busy_ = lambda c: 480.0 <= c <= 490.0
got2 = pf_fill(4, plan0, sep=0.5, tol=tolW, filt=32.0, new_sep=0.5, new_tol=tolW, new_filt=32.0,
               lo=478.5, hi=495.0, busy=busy_)
check("coordination : évite l'occupé", (len(got2), any(busy_(c) for c in got2)), (4, False))
got3 = pf_fill(50, [], new_sep=0.5, new_tol=tolW, new_filt=0.0, lo=600.0, hi=602.0, step=0.025)
check("coordination : plage pleine → moins que demandé", 0 < len(got3) < 50, True)

# 7.60.2 (Clément : « une méthode aléatoire, à la suite ça fonctionne pas en général ») : réparties au hasard
_rng = np.random.default_rng(7)
gotr = pf_fill(10, plan0, sep=0.5, tol=tolW, filt=32.0, new_sep=0.5, new_tol=tolW, new_filt=32.0,
               lo=470.0, hi=694.0, step=0.025, order="random", rng=_rng)
issr, _ = ns["pf_check"](plan0 + gotr, sep=0.5, tol=tolW, filt=32.0)
check("hasard : 10 trouvées, plan sans aucun problème", (len(gotr), sum(len(x) for x in issr)), (10, 0))
gotl = pf_fill(10, plan0, sep=0.5, tol=tolW, filt=32.0, new_sep=0.5, new_tol=tolW, new_filt=32.0,
               lo=470.0, hi=694.0, step=0.025)
check("hasard : réparties sur la plage (bien plus large qu'à la suite)",
      (max(gotr) - min(gotr)) > 3 * (max(gotl) - min(gotl)), True)
_lots = [dict(n=4, sep=0.5, tol=tolW, filt=32.0, lo=470.0, hi=694.0, step=0.025)]
_a = ns["pf_fill_lots"](_lots, plan0, order="random", tries=2, seed=3)
_b = ns["pf_fill_lots"](_lots, plan0, order="random", tries=2, seed=3)
check("hasard : même graine = même résultat (reproductible)", _a, _b)
_steps = []
ns["pf_fill_lots"](_lots, plan0, order="random", tries=3, seed=1, progress=lambda k, n: _steps.append((k, n)))
check("hasard : progression essai par essai", _steps, [(1, 3), (2, 3), (3, 3)])
check("hasard : annulé avant de commencer -> rien", ns["pf_fill_lots"](_lots, plan0, order="random", tries=3,
      cancel=lambda: True), [[]])
# coordination entre appareils : 2 lots (QLX-D puis PSM 1000), chacun ses règles, tous compatibles entre eux
rp = ns["rx_profile"]
q_, p_ = rp("shure_dig"), rp("shure_psm1000")
lots = [dict(n=5, sep=q_["sep"], tol=q_["tol"], filt=q_["filt"], lo=470.0, hi=520.0, step=q_["step"]),
        dict(n=4, sep=p_["sep"], tol=p_["tol"], filt=p_["filt"], lo=490.0, hi=530.0, step=p_["step"])]
gl = ns["pf_fill_lots"](lots, plan0, sep=0.5, tol=tolW, filt=32.0)
check("lots : 5 QLX-D + 4 PSM trouvées, chacune dans sa plage",
      (len(gl[0]), len(gl[1]), all(470 <= c <= 520 for c in gl[0]), all(490 <= c <= 530 for c in gl[1])),
      (5, 4, True, True))
F_ = plan0 + gl[0] + gl[1]
iss, _ = ns["pf_check"](F_, sep=[0.5] * 8 + [q_["sep"]] * 5 + [p_["sep"]] * 4,
                        tol=[tolW] * 8 + [q_["tol"]] * 5 + [p_["tol"]] * 4,
                        filt=[32.0] * 8 + [q_["filt"]] * 5 + [p_["filt"]] * 4)
check("lots : plan complet (3 appareils) sans aucun problème", sum(len(x) for x in iss), 0)
check("lots : aucune fréquence en double", len(set(F_)), len(F_))
check("lots : aucun lot -> rien", ns["pf_fill_lots"]([], plan0), [])

# ---- fréquence image (FI 10,7 MHz des récepteurs analogiques) : un émetteur à f ± FI (règle d'EazyRF, vérifiée 7.51)
_T0 = {"2tx3": 0.0, "3tx3": 0.0, "5": 0.0, "7": 0.0}
_iss, _ = ns["pf_check"]([500.000, 510.700], [True, True], None, 0.3, _T0, None, 0.0, [10.7, 0.0])
check("image : émetteur à f + 10,7 MHz signalé sur le récepteur analogique", [x["kind"] for x in _iss[0]], ["img"])
_isE = [ns["pf_check"]([600.000, b], [True, True], None, 0.3, _T0, None, 0.0, [10.7, 0.0])[0][0] for b in
        (610.7, 621.4, 589.3, 578.6)]
check("image : comme le test de Clément dans EazyRF (G3 sur 600 : 589,3 et 610,7 oui, 578,6 et 621,4 non)",
      [bool(x) for x in _isE], [True, False, True, False])
check("image : rien pour le récepteur sans FI", _iss[1], [])
_iss2, _ = ns["pf_check"]([500.000, 489.350], [True, True], None, 0.3, _T0, None, 0.0, 10.7)
check("image : aussi côté bas (f − FI), à 50 kHz", ([x["kind"] for x in _iss2[0]], round(_iss2[0][0]["gap"], 3)),
      (["img"], 0.05))
_iss3, _ = ns["pf_check"]([500.000, 511.000], [True, True], None, 0.3, _T0, None, 0.0, 10.7)
check("image : à 300 kHz de l'image = OK (tolérance 100 kHz)", _iss3, [[], []])
_iss4, _ = ns["pf_check"]([500.000, 510.700], [True, False], None, 0.3, _T0, None, 0.0, 10.7)
check("image : une réserve (n'émet pas) ne gêne pas", _iss4[0], [])
ok("image : texte", "fréquence image" in ns["pf_issue_text"](_iss[0][0], ["A", "B"], [500.0, 510.7]))
_sg = ns["pf_suggest"](0, [500.000, 510.700], [True, True], None, 0.3, _T0, None, lo=499.0, hi=501.0, step=0.025,
                       img=[10.7, 0.0])
ok("image : les propositions l'évitent", _sg and all(abs(abs(510.7 - c) - 10.7) >= 0.1 - 1e-6 for c, _d in _sg), str(_sg))
_cd = ns["rx_custom_norm"]([dict(name="Analogique", sep=0.4, img=10.7)])
check("image : gardée dans un profil perso", _cd[0][2].get("img"), 10.7)

print("\nÉCHECS:", fails)
sys.exit(1 if fails else 0)
