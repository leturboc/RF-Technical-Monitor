"""Le programme en plusieurs fichiers : tsm_core.py (partie sans interface), tinysa_monitor.py (en-tête, fenêtre
principale) et tsm_ui/*.py (8.1 étape 3 : le reste de l'interface, par thème, exécuté DANS tinysa_monitor.py à la
ligne « PARTIES-ICI »). Les tests qui lisent le code source (extraits « PURE », textes à traduire…) lisent tout,
dans l'ordre d'exécution : tinysa_monitor.py avec les parties insérées à leur place, puis tsm_core.py."""
import os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MARK = "_load_parts(globals())  # ===== PARTIES-ICI"


def parts():
    """Noms des parties de tsm_ui, dans l'ordre (lus dans tsm_ui/__init__.py sans l'importer)."""
    txt = open(os.path.join(ROOT, "tsm_ui", "__init__.py"), encoding="utf-8").read()
    return re.findall(r"'(\w+)'", re.search(r"PARTS = \((.*?)\)", txt, re.S).group(1))


def ui_files():
    return [os.path.join(ROOT, "tsm_ui", n + ".py") for n in parts()]


def ui_source():
    """L'interface telle qu'elle s'exécute : tinysa_monitor.py avec les parties à la place de la ligne PARTIES-ICI."""
    main = open(os.path.join(ROOT, "tinysa_monitor.py"), encoding="utf-8").read()
    head, tail = main.split(MARK)
    body = "\n".join(open(f, encoding="utf-8").read() for f in ui_files())
    return head + "\n" + body + "\n" + tail


def source():
    return ui_source() + "\n" + open(os.path.join(ROOT, "tsm_core.py"), encoding="utf-8").read()
