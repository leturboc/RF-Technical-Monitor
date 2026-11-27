"""Parties de l'interface de RF Technical Monitor (8.1 étape 3).

Ce ne sont PAS des modules à importer un par un : chacune est exécutée, dans l'ordre de PARTS, dans l'espace de noms
de tinysa_monitor.py (load_parts). Le code voit donc tous les noms du programme comme quand il n'était qu'un fichier,
et un test qui remplace un réglage du programme (m.X = ...) le remplace pour toutes les parties.
PyInstaller : --collect-submodules tsm_ui (le code compilé est relu par find_spec / get_code, aussi dans l'exe)."""
import importlib.util

PARTS = ('appareils', 'web', 'dialogues', 'sdr_materiel', 'sdr_poste', 'outils', 'accueil', 'carte', 'fenetres', 'demarrage', 'sdr_fenetres', 'labo', 'fen_construction', 'fen_config', 'fen_appareils', 'fen_scenes', 'fen_liste', 'fen_spectre', 'fen_outils', 'fen_alarmes')


def load_parts(g, names=PARTS):
    for n in names:
        spec = importlib.util.find_spec(__name__ + "." + n)
        if spec is None or spec.loader is None:
            raise ImportError(f"partie de l'interface introuvable : {__name__}.{n}")
        exec(spec.loader.get_code(spec.name), g)
