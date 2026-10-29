"""Traduction anglaise : chaque texte du programme a sa traduction (lang_en.py), le moteur Translator (section
PURE) traduit les phrases à trous, les morceaux, le HTML, et la page web anglaise est complète.
    python tests/test_i18n.py        -> ÉCHECS: 0"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import itertools, csv, io, math, unicodedata, bisect          # noqa: E401  (espace de noms de la section PURE)
from collections import deque
import numpy as np
import i18n_extract as X
import lang_en as L

src = open(os.path.join(ROOT, "tinysa_monitor.py"), encoding="utf-8").read()
pure = src[src.index("# ===== PURE-BEGIN"):src.index("# ===== PURE-END")]
ns = dict(itertools=itertools, re=re, csv=csv, io=io, math=math, np=np, unicodedata=unicodedata, bisect=bisect,
          deque=deque, MIN_PTS=3, HYST=3.0, RBW_LIST=[])
exec(compile(pure, "pure", "exec"), ns)
fails = 0


def check(label, cond, extra=""):
    global fails
    fails += not cond
    print(("OK  " if cond else "FAIL"), label, "" if cond else extra)


consts, tpls, html = X.extract(src)
vocab_words = set(ns["NAME_WORDS"]) | set(ns["SCENE_WORDS"]) | set(ns["GROUP_WORDS"])
miss_c = [c for c in sorted(set(consts) | set(html)) if c not in L.EXACT and not (c in vocab_words and c in L.VOCAB)]
miss_t = [t for t in tpls if t not in L.TEMPLATES and t not in L.SAME_TEMPLATES]
check(f"{len(set(consts) | set(html))} textes fixes traduits", not miss_c,
      "\n  à ajouter dans lang_en.EXACT :\n" + "\n".join("  " + repr(c) for c in miss_c[:30]))
check(f"{len(tpls)} phrases à trous traduites", not miss_t,
      "\n  à ajouter dans lang_en.TEMPLATES :\n" + "\n".join("  " + repr(t) for t in miss_t[:30]))
bad = [k for k, v in L.TEMPLATES.items()
       if k.count("{}") != len(re.findall(r"(?<!\{)\{\}(?!\})", v.replace("{{", "").replace("}}", "")))]
check("même nombre de trous « {} » en français et en anglais", not bad, str(bad[:5]))
lead = [k for k, v in L.EXACT.items() if k[:1] != v[:1] and (k[:1] in "⚠✔🔴🟠🟡⚪📋🧱🔔🎤📖" or v[:1] in "⚠✔")]
check("emojis de tête gardés", not lead, str(lead[:5]))
rest = [k for k, v in L.EXACT.items() if re.search(r"[éèàùçêô]", v) and k != v and "Langue" not in v
        and "langue" not in v and not re.search(r"Français|Sémaphore|Clément", v)]
check("pas d'accent français dans les traductions", not rest, str(rest[:8]))

T = ns["Translator"](L.EXACT, L.TEMPLATES)
cases = [
    ("Libre", "Free"),
    ("libre", "free"),
    ("Fond des tableaux :", "Table background:"),
    ("6 fréq.", "6 freq."),
    ("Main stage   ·  6 fréq.  ·  ⚠ 1 alarme(s)", "Main stage   ·  6 freq.  ·  ⚠ 1 alarm(s)"),
    ("Canal UHF 21 (8 MHz) : 470-478 MHz", "UHF channel 21 (8 MHz): 470-478 MHz"),
    ("TV / TNT : TNT (DVB-T2) + micros HF pros : usage partagé (470–606 MHz)",
     "TV / DTT: DTT (DVB-T2) + pro wireless mics: shared use (470–606 MHz)"),
    ("<b>Libre</b>", "<b>Free</b>"),
    ("📋 Liste", "📋 List"),
    ("2A − B :", "2A − B:"),
    ("texte inconnu xyz", "texte inconnu xyz"),
    ("", ""),
]
for fr, en in cases:
    got = T(fr)
    check(f"traduit {fr[:40]!r}", got == en, f"-> {got!r}")
r = T(ns["im_rules_text"]({"2tx3": 0.1, "3tx3": 0.05, "5": 0.0}, 0.3, 32.0))
check("phrase des règles d'intermod en anglais", r.startswith("We check:") and not re.search(r"[éè]|ordre", r), r)
for k in ("CONFLIT", "ABSENT", "INCONNU"):
    check(f"mot d'alarme {k}", T(k) != k and T(k).isupper(), T(k))
_, title_body = None, ns["notify_text"](dict(kind="CONFLIT", name="HF 1", freq=606.5, prio=2, layer="", info=""), "")
tb = [T(x) for x in title_body]
check("notification traduite", not any(re.search(r"[éè]|CONFLIT", x) for x in tb), str(tb))
ns["WEB_VIEWS"] = ns.get("WEB_VIEWS")
page_src = src[src.index('WEB_PAGE = r"""') + len('WEB_PAGE = r"""'):]
page_src = page_src[:page_src.index('"""')]
page, missing = ns["web_page_lang"](page_src, L.WEB, T)
check("page web : tous les morceaux à traduire trouvés", not missing, str(missing))
vis = [t for t in re.findall(r">([^<>{}]+)<", page) if re.search(r"[éèàùç]", t)]
check("page web : plus de texte français visible", not vis, str(vis[:5]))
check("page web : langue « en »", 'lang="en"' in page and '"fr-FR"' not in page)
left = [t for _k, _s, t in ns["SIGNAL_LABELS"] if T(t) == t and t not in ("OK", "⚠ INTERMOD")]
check("mots de la colonne Signal traduits", not left, str(left))
check("noms de l'utilisateur jamais traduits (« Grande scène » reste tel quel)", T("Grande scène") == "Grande scène")
check("mots proposés traduits (VOCAB)", L.VOCAB.get("Batterie") == "Drums" and L.VOCAB.get("Grande scène") == "Main stage")
check("Translator vide = français inchangé", ns["TR"]("Libre") == "Libre")
check("choix de langue : fr et en", [c for c, _ in ns["LANGS"]] == ["fr", "en"])
print(f"ÉCHECS: {fails}")
sys.exit(1 if fails else 0)
