"""V8 : fabrique le MANUEL SDR (à part du manuel principal, pour ne pas toucher aux fichiers de la V7) :
docs/src/sdr_fr.html / sdr_en.html (blocs <!--CH id|Titre-->)  ->  docs/manuel_sdr.html, docs/manual_sdr_en.html,
docs/manuel_sdr.pdf, docs/manual_sdr_en.pdf (si Playwright est là) et manual_sdr.py (le HTML embarqué dans l'exe :
importé par tinysa_monitor.py, PyInstaller le prend tout seul).

    python tests/make_manual_sdr.py [--no-pdf]

Le jour du passage en 8.0, ces chapitres rejoindront le manuel principal (tests/make_manual.py)."""
import os, re, sys, html

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TITLE = {"fr": ("Manuel SDR", "TinySA Monitor — le poste SDR (V8)", "Sommaire", "Chapitre"),
         "en": ("SDR manual", "TinySA Monitor — the SDR station (V8)", "Contents", "Chapter")}


def style():
    """Le style du manuel principal (clair / sombre, téléphone), pour que les deux se ressemblent."""
    src = open(os.path.join(ROOT, "docs", "manuel.html"), encoding="utf-8").read()
    return "\n".join(re.findall(r"<style>.*?</style>", src, re.S)[:2])


def chapters(lang):
    src = open(os.path.join(ROOT, "docs", "src", f"sdr_{lang}.html"), encoding="utf-8").read()
    parts = re.split(r"<!--CH ([^|]+)\|([^>]*?)-->", src)
    return [(parts[i].strip(), parts[i + 1].strip(), parts[i + 2].strip()) for i in range(1, len(parts), 3)]


def build(lang):
    t, sub, toc_t, ch_t = TITLE[lang]
    chs = chapters(lang)
    toc = "\n".join(f'<li><a href="#{k}">{html.escape(title)}</a></li>' for n, (k, title, _b) in enumerate(chs, 1))
    body = "\n".join(f'<section id="{k}"><h2>{n}. {html.escape(title)}</h2>\n{b}\n</section>'
                     for n, (k, title, b) in enumerate(chs, 1))
    return (f'<!doctype html>\n<html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(t)}</title>{style()}</head><body><main>"
            f'<header><h1>{html.escape(t)}</h1><p class="muted">{html.escape(sub)}</p></header>'
            f'<nav><h2>{html.escape(toc_t)}</h2><ol>{toc}</ol></nav>{body}</main></body></html>\n')


def pdf(src, dst):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pas de Playwright : PDF non refait")
        return
    with sync_playwright() as p:
        exe = "/opt/pw-browsers/chromium"            # Chromium déjà installé (sinon celui de Playwright)
        b = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
        pg = b.new_page()
        pg.goto("file://" + os.path.abspath(src))
        pg.emulate_media(media="print")
        pg.pdf(path=dst, format="A4", margin=dict(top="16mm", bottom="16mm", left="14mm", right="14mm"),
               print_background=True)
        b.close()
    print("écrit", os.path.basename(dst), f"{os.path.getsize(dst) // 1024} Ko")


def main():
    out = {}
    for lang, name in (("fr", "manuel_sdr"), ("en", "manual_sdr_en")):
        h = build(lang)
        out[lang] = h
        p = os.path.join(ROOT, "docs", name + ".html")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(h)
        print(lang, len(chapters(lang)), "chapitres")
        if "--no-pdf" not in sys.argv:
            pdf(p, os.path.join(ROOT, "docs", name + ".pdf"))
    with open(os.path.join(ROOT, "manual_sdr.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Manuel SDR (V8), FABRIQUÉ par tests/make_manual_sdr.py depuis docs/src/sdr_*.html : ne pas modifier à la '
                'main."""\nHTML = ' + repr(out) + "\n")
    print("écrit manual_sdr.py")


if __name__ == "__main__":
    main()
