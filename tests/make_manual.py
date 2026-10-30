"""Reconstruit docs/manuel.html et docs/manual_en.html en 5 parties (A commencer, B comprendre, C festival pas à pas,
D référence, E aide) : chapitres existants + docs/src/nouveaux_*.html, numérotation, sommaire, renvois « chapitre N »,
et le lexique généré depuis GLOSSARY (tinysa_monitor.py) / sa traduction (lang_en.py). Idempotent.

    python tests/make_manual.py      # puis python tests/make_pdf.py
"""
import html
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
SRC = open(os.path.join(ROOT, "tinysa_monitor.py"), encoding="utf-8").read()
VER = re.search(r'^APP_VER = "([^"]+)"', SRC, re.M).group(1)
import unicodedata  # noqa: E402
_g = {"unicodedata": unicodedata}
exec(SRC[SRC.index("GLOSSARY = ["):SRC.index("def glossary_find")], _g)
GLOSSARY = _g["GLOSSARY"]
import lang_en  # noqa: E402

PARTS = [
    ("A", "Pour commencer", "Getting started", ["lire", "intro", "materiel", "install", "ecran", "aide-in"]),
    ("B", "Comprendre la HF", "Understanding RF", ["rf", "spectre"]),
    ("C", "Le festival pas à pas", "The festival step by step",
     ["vue", "avant", "arrivee", "terrain", "plan", "portes", "reagir", "nuit", "apres"]),
    ("D", "Référence des outils", "Tool reference",
     ["show", "seuils", "surveiller", "signal", "mur", "fenetres", "coordination", "filtre", "linecheck", "spectera",
      "deux", "alertes", "sessions", "journal", "apparence"]),
    ("E", "Aide", "Help", ["faq", "depannage", "lexique", "menus", "clavier", "donnees", "limites"]),
]
CSS = (".part { margin: 56px 0 0; padding: 10px 14px; border-radius: 8px; background: var(--accent); color: #fff; "
       "font-weight: 700; letter-spacing: .03em; }\nnav .np { margin: 12px 0 2px; font-weight: 700; color: var(--accent); }\n")


def build(lang):
    fn = "manuel.html" if lang == "fr" else "manual_en.html"
    path = os.path.join(ROOT, "docs", fn)
    doc = open(path, encoding="utf-8").read()
    head = doc[:doc.index("<nav>")]
    if ".part {" not in head:
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
        m = re.match(r'<h2 id="([^"]+)">(?:(\d+)\. )?([^<]*)</h2>', c)
        if not m:
            continue
        body = re.sub(r'\s*<div class="part">.*?</div>\s*$', "\n", c[m.end():], flags=re.S)
        chap[m.group(1)] = [m.group(3), body]
        if m.group(2):
            old_num[m.group(2)] = m.group(1)
    nouveaux = open(os.path.join(ROOT, "docs", "src", f"nouveaux_{lang}.html"), encoding="utf-8").read()
    for m in re.finditer(r"<!--CH ([\w-]+)\|([^>]*)-->(.*?)(?=<!--CH |\Z)", nouveaux, re.S):
        chap[m.group(1)] = [m.group(2), "\n" + m.group(3).strip() + "\n\n"]
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
            out.append(f'<h2 id="{k}">{n}. {title}</h2>{body}')
            nav.append(f'  <a href="#{k}">{n}. {title}</a>')
    nav.append("</nav>\n")
    body = "".join(out)
    word = "chapter" if lang == "en" else "chapitre"
    body = re.sub(rf"({word}s?) (\d+)\b", lambda m: f"{m.group(1)} {num.get(old_num.get(m.group(2), ''), m.group(2))}",
                  body)
    top = re.sub(r"(Version|version) [\d.]+( ·)", rf"\g<1> {VER}\2", top, count=1)
    new = head + "\n".join(nav) + "<main>" + top + body + tail
    open(path, "w", encoding="utf-8").write(new)
    return n


if __name__ == "__main__":
    for lg in ("fr", "en"):
        print(lg, build(lg), "chapitres")
