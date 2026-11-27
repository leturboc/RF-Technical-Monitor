"""Reconstruit docs/manuel.html et docs/manual_en.html en 5 parties (A commencer, B comprendre, C festival pas à pas,
D référence, E aide) : chapitres existants + docs/src/nouveaux_*.html, numérotation, sommaire, renvois « chapitre N »,
et le lexique généré depuis GLOSSARY (tinysa_monitor.py) / sa traduction (lang_en.py). Idempotent.

    python tests/make_manual.py      # puis python tests/make_pdf.py
"""
import base64
import html
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
SRC = "\n".join(open(os.path.join(ROOT, f_), encoding="utf-8").read() for f_ in ("tsm_core.py", "tinysa_monitor.py"))
VER = re.search(r'^APP_VER = "([^"]+)"', SRC, re.M).group(1)
import unicodedata  # noqa: E402
_g = {"unicodedata": unicodedata}
exec(SRC[SRC.index("GLOSSARY = ["):SRC.index("def glossary_find")], _g)
GLOSSARY = _g["GLOSSARY"]
import lang_en  # noqa: E402

PARTS = [
    ("A", "Pour commencer", "Getting started", ["lire", "intro", "materiel", "install", "ecran", "aide-in"]),
    ("B", "Comprendre la HF", "Understanding RF", ["rf", "spectre", "echelles", "pays"]),
    ("C", "Le festival pas à pas", "The festival step by step",
     ["vue", "avant", "arrivee", "terrain", "plan", "portes", "reagir", "nuit", "apres"]),
    ("D", "Référence des outils", "Tool reference",
     ["show", "seuils", "surveiller", "signal", "mur", "fenetres", "coordination", "filtre", "linecheck", "spectera",
      "deux", "alertes", "sessions", "journal", "apparence"]),
    ("E", "Le SDR (bêta)", "The SDR (beta)",
     ["sdr-poste", "sdr-branchement", "sdr-ecoute", "sdr-favoris", "sdr-surveiller", "sdr-plusieurs", "sdr-caler",
      "sdr-remonter", "sdr-demo", "sdr-labo", "sdr-emettre", "sdr-sons", "sdr-avance", "sdr-savoir"]),
    ("F", "Aide", "Help", ["faq", "depannage", "lexique", "menus", "clavier", "donnees"]),
]
DROP = {"limites"}          # chapitres retirés (« ce qui n'est pas vérifié » : suivi dans CLAUDE.md, pas dans le manuel)
# mise en page sobre (7.28, Clément : « un manuel beaucoup plus pro ») : couverture, parties en intertitres,
# numéros de chapitre en couleur, pas d'emoji dans les titres, captures d'écran de la vraie appli
CSS = """/*pro*/
body { font: 16px/1.65 "Segoe UI", system-ui, -apple-system, Roboto, sans-serif; }
.cover { display: flex; gap: 22px; align-items: center; max-width: 1148px; margin: 0 auto; padding: 34px 0 22px;
  border-bottom: 3px solid var(--accent); }
@media (max-width: 1180px) { .cover { margin: 0 16px; } }
.cover img { width: 80px; height: 80px; flex: none; }
.cover .kicker { text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 600; color: var(--muted); }
.cover h1 { font-size: 2.5rem; line-height: 1.1; margin: 4px 0 6px; letter-spacing: -.01em; }
.cover .sub { margin: 0; }
.part { margin: 76px 0 0; padding: 0 0 8px; border-bottom: 2px solid var(--accent); background: none; color: var(--accent);
  font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .14em; border-radius: 0; }
h2 { font-size: 1.5rem; font-weight: 650; margin: 46px 0 12px; border-top: 0; padding-top: 0; }
h2 .n { color: var(--accent); margin-right: .35em; font-variant-numeric: tabular-nums; }
h3 { font-weight: 650; }
.box { border-radius: 4px; }
.box.ok, .box.warn, .box.bad { color: var(--text); font-weight: 400; }   /* seule la bordure est colorée */
figure.shot { margin: 18px 0 22px; max-width: 900px; }
figure.shot img { display: block; width: 100%; height: auto; border: 1px solid var(--line); border-radius: 6px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, .14); }
figure.shot figcaption { font-size: 13px; color: var(--muted); margin-top: 6px; }
nav .np { margin: 14px 0 2px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em;
  color: var(--accent); }
@media print { .cover { margin: 0 0 18px; } .part { break-before: page; margin-top: 0; } figure.shot { break-inside: avoid; } h2 { break-after: avoid; } }
/*/pro*/
"""
ICON = os.path.join(ROOT, "assets", "icone.png")
IMG = os.path.join(ROOT, "docs", "img")
# captures (tests/gui_reel.py en français, tests/gui_en.py en anglais) : chapitre → (fichier, légende fr, légende en)
FIGS = {
    "ecran": [("ecran", "L'écran principal : l'accueil en haut (① tinySA, ② Mes micros, ③ Surveiller et la phrase d'état), "
                        "le spectre avec la barre des seuils, la liste des fréquences à droite.",
               "The main screen: the home bar at the top (① tinySA, ② My mics, ③ Monitor and the status sentence), the "
               "spectrum with the threshold bar, the frequency list on the right.")],
    "seuils": [("reglages", "⚙ Réglages › Seuils et alarmes.", "⚙ Settings › Thresholds and alarms.")],
    "mur": [("mur", "Le mur de fréquences : une tuile par fréquence, lisible de loin.",
             "The frequency wall: one tile per frequency, readable from a distance.")],
    "coordination": [("plan", "Vérifier le plan : chaque problème expliqué, avec une fréquence de remplacement proposée.",
                      "Check the plan: every problem explained, with a suggested replacement frequency.")],
    "spectre": [("outils", "La barre du spectre avec les outils dépliés (⋯).",
                 "The spectrum bar with the tools unfolded (⋯).")],
    "portes": [("pret", "✅ Prêt pour le show ? : chaque point vérifié, « Régler » ouvre le bon réglage.",
                "✅ Ready for the show?: every point checked, “Fix” opens the right setting.")],
    "reagir": [("showmode", "Le mode Show (F10) : alarmes en très gros, une tuile par fréquence.",
                "Show mode (F10): alarms in very large text, one tile per frequency.")],
}
SHOTS = {   # fichier de docs/img → nom de la capture (sans le numéro) dans tests/captures (fr) / tests/captures_en (en)
    "ecran": ("mode_simple", "mode_simple"), "reglages": ("reglages_seuils", "reglages_seuils"),
    "mur": ("mur_en_panneau", "mur_en"), "plan": ("plan_proposition", "PlanCheckDialog"),
    "outils": ("spectre_plus_outils", "spectre_plus_outils"),
    "pret": ("pret_pour_le_show", "ReadyDialog"), "showmode": ("mode_show", "ShowModeWindow"),
}
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def clean_title(t):
    """Titres sans emoji (les boutons cités dans le texte gardent les leurs)."""
    t = EMOJI.sub("", t)
    t = re.sub(r"\(\s*\)", "", t)               # « Enregistrer le show (🎪) » -> pas de « () » vide
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\s*:$", "", t)


def shots(fr_dir, en_dir, width=1400):
    """Copie les captures choisies dans docs/img/<lang>/ (JPEG, largeur max width)."""
    from PIL import Image
    for lang, d in (("fr", fr_dir), ("en", en_dir)):
        os.makedirs(os.path.join(IMG, lang), exist_ok=True)
        for out, names in SHOTS.items():
            name = names[lang == "en"]
            found = sorted(f for f in os.listdir(d) if re.fullmatch(rf"\d+_{name}\.png", f)) if os.path.isdir(d) else []
            if not found:
                print("capture absente :", lang, name)
                continue
            im = Image.open(os.path.join(d, found[-1])).convert("RGB")
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            im.save(os.path.join(IMG, lang, out + ".jpg"), quality=82, optimize=True)
            print("capture", lang, out, im.size)


def data_uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def figure(lang, key):
    out = []
    for name, cap_fr, cap_en in FIGS.get(key, []):
        path = os.path.join(IMG, lang, name + ".jpg")
        if os.path.exists(path):
            cap = html.escape(cap_en if lang == "en" else cap_fr)
            out.append(f'<figure class="shot"><img src="{data_uri(path, "image/jpeg")}" alt="{cap}">'
                       f'<figcaption>{cap}</figcaption></figure>\n')
    return "".join(out)


def build(lang):
    fn = "manuel.html" if lang == "fr" else "manual_en.html"
    path = os.path.join(ROOT, "docs", fn)
    doc = open(path, encoding="utf-8").read()
    head = doc[:doc.index("<nav>")]
    head = re.sub(r"/\*pro\*/.*?/\*/pro\*/\n", "", head, flags=re.S)
    head = re.sub(r"\.part \{ margin: 56px[^\n]*\nnav \.np[^\n]*\n", "", head)
    head = head.replace("</style>", CSS + "</style>")
    main = doc[doc.index("<main>") + 6:doc.index("</main>")]
    tail = doc[doc.index("</main>"):]
    first = main.index("<h2 id=")
    top = re.sub(r'\s*<div class="part">.*?</div>\s*', "\n", main[:first], flags=re.S)
    # chapitres existants (le 1er passage les numérote encore en « N. Titre »)
    chunks = re.split(r'(?=<h2 id=")', main[first:])
    chap, old_num = {}, {}
    for c in chunks:
        if c.strip().startswith('<div class="part">'):
            continue
        m = re.match(r'<h2 id="([^"]+)">(?:<span class="n">(\d+)\.</span> |(\d+)\. )?([^<]*)</h2>', c)
        if not m:
            continue
        key, old, title = m.group(1), m.group(2) or m.group(3), m.group(4)
        body = re.sub(r'\s*<div class="part">.*?</div>\s*$', "\n", c[m.end():], flags=re.S)
        body = re.sub(r'<figure class="shot">.*?</figure>\n?', "", body, flags=re.S)
        chap[key] = [title, body]
        if old:
            old_num[old] = key
    nouveaux = open(os.path.join(ROOT, "docs", "src", f"nouveaux_{lang}.html"), encoding="utf-8").read()
    for m in re.finditer(r"<!--CH ([\w-]+)\|([^>]*)-->(.*?)(?=<!--CH |\Z)", nouveaux, re.S):
        chap[m.group(1)] = [m.group(2), "\n" + m.group(3).strip() + "\n\n"]
    sdr = open(os.path.join(ROOT, "docs", "src", f"sdr_{lang}.html"), encoding="utf-8").read()   # 8.0 : partie SDR
    for m in re.finditer(r"<!--CH ([\w-]+)\|([^>]*)-->(.*?)(?=<!--CH |\Z)", sdr, re.S):
        chap["sdr-" + m.group(1)] = [m.group(2), "\n" + m.group(3).strip() + "\n\n"]
    # lexique depuis l'appli
    rows = []
    for t, x in GLOSSARY:
        if lang == "en":
            t, x = lang_en.EXACT.get(t, t), lang_en.EXACT.get(x, x)
        rows.append(f"  <tr><td><b>{html.escape(t)}</b></td><td>{html.escape(x)}</td></tr>")
    intro = ("Every word of RF and of the app, explained simply. The same glossary is in the app (☰ More › Help › 📚 "
             "Glossary), with a search." if lang == "en" else
             "Tous les mots de la HF et de l'appli, expliqués simplement. Le même lexique est dans l'appli (☰ Plus › "
             "Aide › 📚 Lexique), avec une recherche.")
    chap["lexique"] = ["Glossary" if lang == "en" else "Lexique",
                       f"\n<p>{intro}</p>\n<table>\n  <tr><th>{'Word' if lang == 'en' else 'Mot'}</th><th>"
                       f"{'Meaning' if lang == 'en' else 'Explication'}</th></tr>\n" + "\n".join(rows) + "\n</table>\n\n"]
    missing = [k for _p, _f, _e, ks in PARTS for k in ks if k not in chap]
    assert not missing, missing
    for k in DROP:
        chap.pop(k, None)
    extra = [k for k in chap if not any(k in ks for *_x, ks in PARTS)]
    assert not extra, extra
    num, out, nav = {}, [], ['<nav>\n  <b>' + ("Contents" if lang == "en" else "Sommaire") + "</b>"]
    n = 0
    for letter, fr_t, en_t, keys in PARTS:
        pt = f"{'Part' if lang == 'en' else 'Partie'} {letter} — {en_t if lang == 'en' else fr_t}"
        out.append(f'<div class="part">{pt}</div>\n')
        nav.append(f'  <div class="np">{letter}. {en_t if lang == "en" else fr_t}</div>')
        for k in keys:
            n += 1
            num[k] = n
            title, body = chap[k]
            title = clean_title(title)
            body = re.sub(r"<h3>([^<]*)</h3>", lambda m3: f"<h3>{clean_title(m3.group(1))}</h3>", body)
            fig = figure(lang, k)
            if fig:                                   # la capture après le 1er paragraphe du chapitre
                cut = body.find("</p>")
                body = body[:cut + 4] + "\n" + fig + body[cut + 4:] if 0 <= cut < 1500 else "\n" + fig + body
            out.append(f'<h2 id="{k}"><span class="n">{n}.</span> {title}</h2>{body}')
            nav.append(f'  <a href="#{k}">{n}. {title}</a>')
    nav.append("</nav>\n")
    body = "".join(out)
    word = "chapter" if lang == "en" else "chapitre"
    body = re.sub(rf"({word}s?) (\d+)\b", lambda m: f"{m.group(1)} {num.get(old_num.get(m.group(2), ''), m.group(2))}",
                  body)
    sub = (f"Version {VER} · tinySA Ultra and SDR on Windows · RF coordination for festivals, concerts and events" if lang == "en"
           else f"Version {VER} · tinySA Ultra et SDR sous Windows · coordination HF en festival, concert, événementiel")
    cover = (f'<header class="cover"><img src="{data_uri(ICON, "image/png")}" alt="">\n<div><div class="kicker">'
             f'{"User manual" if lang == "en" else "Manuel d&#39;utilisation"}</div>\n<h1>RF Technical Monitor</h1>\n'
             f'<p class="sub">{sub}</p></div></header>\n')
    top = re.sub(r'<header class="cover">.*?</header>\n', "", top, flags=re.S)
    top = re.sub(r"<h1>.*?</h1>\s*<p class=\"sub\">.*?</p>\n", "", top, flags=re.S)
    top = "\n" + top.lstrip("\n")
    head = re.sub(r'<header class="cover">.*?</header>\n', "", head, flags=re.S)   # couverture au-dessus des colonnes
    head = head.replace('<div class="wrap">', cover + '<div class="wrap">', 1)
    new = head + "\n".join(nav) + "<main>" + top + body + tail
    open(path, "w", encoding="utf-8").write(new)
    return n


if __name__ == "__main__":
    if "--shots" in sys.argv:          # python tests/make_manual.py --shots tests/captures tests/captures_en
        i = sys.argv.index("--shots")
        shots(sys.argv[i + 1], sys.argv[i + 2])
    for lg in ("fr", "en"):
        print(lg, build(lg), "chapitres")
