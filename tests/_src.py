"""8.1 : le programme est en deux fichiers (tsm_core.py = partie sans interface, tinysa_monitor.py = l'interface).
Les tests qui lisent le code source (extraits « PURE », textes à traduire…) lisent les deux, à la suite."""
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FILES = ("tinysa_monitor.py", "tsm_core.py")      # l'interface d'abord : sa docstring reste la 1re


def source():
    return "\n".join(open(os.path.join(ROOT, f), encoding="utf-8").read() for f in FILES)
