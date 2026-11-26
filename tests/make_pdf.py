"""Manuels en PDF (lisibles directement sur GitHub, qui n'affiche pas le HTML) :
docs/manuel.html -> docs/manuel.pdf, docs/manual_en.html -> docs/manual_en.pdf. Il faut Playwright + Chromium.
    python tests/make_pdf.py"""
import os
from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium"
    br = p.chromium.launch(executable_path=exe) if os.path.exists(exe) else p.chromium.launch()
    for src, dst in (("manuel.html", "manuel.pdf"), ("manual_en.html", "manual_en.pdf")):
        pg = br.new_page()
        pg.goto("file://" + os.path.abspath(os.path.join(ROOT, "docs", src)))
        pg.evaluate("document.documentElement.dataset.theme = 'light'")      # PDF toujours en clair
        pg.pdf(path=os.path.join(ROOT, "docs", dst), format="A4", print_background=True,
               margin=dict(top="16mm", bottom="16mm", left="14mm", right="14mm"),
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#888">'
                               'RF Technical Monitor — <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        print("écrit", dst, os.path.getsize(os.path.join(ROOT, "docs", dst)) // 1024, "Ko")
    br.close()
