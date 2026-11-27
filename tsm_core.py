# RF Technical Monitor — le cœur SANS interface (8.1) : formats de scans et de plans, intermodulation, alarmes, seuils,
# occupation, rapports, page web, SDR (calculs)… Rien ici ne dépend de Qt : c'est testé seul (tests/test_*.py
# exécutent la partie PURE dans un espace de noms restreint). L'interface (tinysa_monitor.py) importe tout d'ici.
import bisect
import csv
import io
import itertools
import math
import re
import unicodedata
from collections import deque
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 8.1 : calculs de numpy sur un seul fil
    _os.environ.setdefault(_v, "1")                                          # (voir tinysa_monitor.py)

import numpy as np

MIN_PTS = 51                 # minimum accepté par la commande scan
RBW_LIST = [0.3, 1, 3, 10, 30, 100, 300, 600, 850]
HYST = 3.0                   # hystérésis (dB) pour repasser en "libre"


# ===== PURE-BEGIN  (code sans interface graphique, testé séparément)

# ----------------------------------------------------------------- couleurs
THEME_KEYS = [
    ("ui_bg", "Fond de l'interface", "Interface"),
    ("ui_base", "Fond des tableaux", "Interface"),
    ("ui_button", "Boutons", "Interface"),
    ("ui_text", "Texte", "Interface"),
    ("ui_accent", "Sélection / accent", "Interface"),
    ("plot_bg", "Fond du spectre", "Graphique"),
    ("plot_fg", "Axes et texte du graphique", "Graphique"),
    ("curve", "Courbe en direct", "Graphique"),
    ("maxhold", "Max hold", "Graphique"),
    ("thr", "Ligne de seuil « occupé »", "Graphique"),
    ("thr_weak", "Ligne de seuil « faible »", "Graphique"),
    ("st_free", "Signal : OK (vert)", "Etats du signal"),
    ("st_libre", "Signal : réserve libre (bleu)", "Etats du signal"),
    ("st_weak", "Signal : faible", "Etats du signal"),
    ("st_occ", "Signal : occupé", "Etats du signal"),
    ("st_unk", "Signal : inconnu (hors liste)", "Etats du signal"),
    ("st_none", "Pas encore de mesure", "Etats du signal"),
]

DEFAULT_THEME = "Pro sombre"
# 7.54 (Clément : « pro, type soft Apple », « le rouge et le vert c'est pas beau », « plusieurs daltoniens ») :
# - plus de vert / rouge purs : OK = menthe, problème = corail (thèmes de style) ;
# - palettes d'éditeurs connus (Catppuccin, Tokyo Night, Dracula, Rosé Pine, Gruvbox, Nord), couleurs reprises de
#   leurs palettes publiées ;
# - un thème par type de daltonisme, vérifié par simulation (Machado 2009, ΔE entre états critiques : OK / occupé /
#   faible / réserve libre ≥ ≈ 30 pour la vision visée ; l'ancien « Sombre doux » tombait à 9 en deutéranopie) ;
#   Okabe-Ito (deutéranopie, protanopie), Paul Tol (tritanopie), niveaux de gris (achromatopsie).
_G = dict(ui_bg="#1c1c1e", ui_base="#232326", ui_button="#2c2c2e", ui_text="#f2f2f7", ui_accent="#0a84ff",
          plot_bg="#161618", plot_fg="#8e8e93")                      # base graphite commune
THEMES = {
    "Pro sombre": dict(_G, curve="#64d2ff", maxhold="#ffb340", thr="#ff6b6b", thr_weak="#ffc35c",
                       st_free="#4fd1c5", st_libre="#5e9eff", st_weak="#ffc35c", st_occ="#ff6b6b",
                       st_unk="#c48bff", st_none="#636366", ref="#c48bff", wf="Viridis"),
    "Pro clair": dict(ui_bg="#f5f5f7", ui_base="#ffffff", ui_button="#e9e9ee", ui_text="#1d1d1f",
                      ui_accent="#007aff", plot_bg="#ffffff", plot_fg="#6e6e73", curve="#007aff",
                      maxhold="#e8890c", thr="#f2545b", thr_weak="#d99a1e", st_free="#12a89d",
                      st_libre="#3478f6", st_weak="#e8a33c", st_occ="#f2545b", st_unk="#a55bd8",
                      st_none="#8e8e93", ref="#a55bd8", wf="Gris"),
    "Catppuccin (Mocha)": dict(ui_bg="#1e1e2e", ui_base="#181825", ui_button="#313244", ui_text="#cdd6f4",
                               ui_accent="#89b4fa", plot_bg="#11111b", plot_fg="#a6adc8", curve="#89dceb",
                               maxhold="#fab387", thr="#f38ba8", thr_weak="#f9e2af", st_free="#94e2d5",
                               st_libre="#89b4fa", st_weak="#f9e2af", st_occ="#f38ba8", st_unk="#cba6f7",
                               st_none="#6c7086", ref="#cba6f7", wf="Viridis"),
    "Tokyo Night": dict(ui_bg="#1a1b26", ui_base="#16161e", ui_button="#292e42", ui_text="#c0caf5",
                        ui_accent="#7aa2f7", plot_bg="#13141c", plot_fg="#a9b1d6", curve="#7dcfff",
                        maxhold="#ff9e64", thr="#f7768e", thr_weak="#e0af68", st_free="#73daca",
                        st_libre="#7aa2f7", st_weak="#e0af68", st_occ="#f7768e", st_unk="#bb9af7",
                        st_none="#565f89", ref="#bb9af7", wf="Viridis"),
    "Dracula": dict(ui_bg="#282a36", ui_base="#21222c", ui_button="#44475a", ui_text="#f8f8f2",
                    ui_accent="#bd93f9", plot_bg="#1e1f29", plot_fg="#c5c8d6", curve="#8be9fd",
                    maxhold="#ffb86c", thr="#ff5555", thr_weak="#f1fa8c", st_free="#8be9fd",
                    st_libre="#bd93f9", st_weak="#f1fa8c", st_occ="#ff5555", st_unk="#ffb86c",
                    st_none="#6272a4", ref="#ff79c6", wf="Inferno"),
    "Rosé Pine": dict(ui_bg="#191724", ui_base="#1f1d2e", ui_button="#26233a", ui_text="#e0def4",
                      ui_accent="#c4a7e7", plot_bg="#14121e", plot_fg="#908caa", curve="#9ccfd8",
                      maxhold="#f6c177", thr="#eb6f92", thr_weak="#f6c177", st_free="#9ccfd8",
                      st_libre="#c4a7e7", st_weak="#f6c177", st_occ="#eb6f92", st_unk="#ebbcba",
                      st_none="#6e6a86", ref="#ebbcba", wf="Inferno"),
    "Gruvbox": dict(ui_bg="#282828", ui_base="#1d2021", ui_button="#3c3836", ui_text="#ebdbb2",
                    ui_accent="#83a598", plot_bg="#1d2021", plot_fg="#bdae93", curve="#83a598",
                    maxhold="#fe8019", thr="#fb4934", thr_weak="#fabd2f", st_free="#8ec07c",
                    st_libre="#83a598", st_weak="#fabd2f", st_occ="#fb4934", st_unk="#d3869b",
                    st_none="#928374", ref="#d3869b", wf="Chaud"),
    "Nord": dict(ui_bg="#2e3440", ui_base="#272c36", ui_button="#3b4252", ui_text="#e5e9f0",
                 ui_accent="#88c0d0", plot_bg="#242933", plot_fg="#d8dee9", curve="#88c0d0",
                 maxhold="#ebcb8b", thr="#bf616a", thr_weak="#ebcb8b", st_free="#8fbcbb", st_libre="#5e81ac",
                 st_weak="#ebcb8b", st_occ="#bf616a", st_unk="#d08770", st_none="#4c566a", ref="#b48ead",
                 wf="Viridis"),
    "Daltonien · deutéranopie (vert)": dict(_G, curve="#9ad0f5", maxhold="#e69f00", thr="#e66100", thr_weak="#f0e442",
                                            st_free="#56b4e9", st_libre="#c9d3dd", st_weak="#f0e442",
                                            st_occ="#e66100", st_unk="#cc79a7", st_none="#636366",
                                            ref="#cc79a7", wf="Viridis"),
    "Daltonien · protanopie (rouge)": dict(_G, curve="#9ad0f5", maxhold="#ffe680", thr="#ff7f00", thr_weak="#ffe680",
                                           st_free="#4f8fe6", st_libre="#c9d3dd", st_weak="#ffe680",
                                           st_occ="#ff7f00", st_unk="#a07bd6", st_none="#636366",
                                           ref="#a07bd6", wf="Viridis"),
    "Daltonien · tritanopie (bleu / jaune)": dict(_G, curve="#33bbee", maxhold="#f5e6c8", thr="#ee3377",
                                                  thr_weak="#f5e6c8", st_free="#33bbee", st_libre="#8c8c8c",
                                                  st_weak="#f5e6c8", st_occ="#ee3377", st_unk="#bbbbbb",
                                                  st_none="#555558", ref="#ee3377", wf="Inferno"),
    "Monochrome (sans couleur)": dict(_G, ui_accent="#8e8e93", curve="#e0e0e0", maxhold="#8a8a8a", thr="#ffffff",
                                      thr_weak="#b0b0b0", st_free="#9a9a9a", st_libre="#5a5a5a",
                                      st_weak="#c8c8c8", st_occ="#ffffff", st_unk="#767676", st_none="#2e2e30",
                                      ref="#b0b0b0", wf="Gris"),
    "Haut contraste": dict(ui_bg="#000000", ui_base="#000000", ui_button="#242424", ui_text="#ffffff",
                           ui_accent="#0078ff", plot_bg="#000000", plot_fg="#ffffff", curve="#00ffff",
                           maxhold="#ffff00", thr="#ff3030", thr_weak="#ffa500", st_free="#00e5ff",
                           st_weak="#ffe600", st_occ="#ff2d2d", st_unk="#ff9d00", st_none="#9a9a9a",
                           wf="Chaud"),
    # 7.54.1 (Clément : « le filtre rouge ou vert c'est pas beau », photo d'un vieil analyseur à tube : « plutôt comme
    # ça ») : interface neutre, SPECTRE façon écran cathodique (plot_style « crt » : grille bien visible, trace
    # phosphore, une seule teinte pour la grille, les axes et la trace).
    "Nuit (rouge)": dict(_G, plot_bg="#0c0505", plot_fg="#ff6f5e", curve="#ffc2b8",
                         maxhold="#c0503f", thr="#ffe0da", thr_weak="#e89080", st_free="#5fb3a1",
                         st_libre="#7a8fd6", st_weak="#e0b050", st_occ="#ff5c5c", st_unk="#b48ad6",
                         st_none="#4a4240", ref="#d08a8a", wf="Rouge (nuit)", plot_style="crt"),
    "Analyseur vert": dict(_G, plot_bg="#06100b", plot_fg="#5fe39a", curve="#b8ffd6",
                           maxhold="#3a9e64", thr="#e2ffee", thr_weak="#9ad8b0", st_free="#3ddc84",
                           st_libre="#5e9eff", st_weak="#ffc35c", st_occ="#ff6b6b", st_unk="#c48bff",
                           st_none="#636366", ref="#8fd6b0", wf="Phosphore vert", plot_style="crt"),
    # gamme « analyseur à tube » (Clément : « un bleu aussi, genre une gamme de thèmes analo »)
    "Analyseur bleu": dict(_G, plot_bg="#050a14", plot_fg="#6fb4ff", curve="#cfe6ff",
                           maxhold="#3f78c0", thr="#e6f2ff", thr_weak="#9cc4f0", st_free="#4fd1c5",
                           st_libre="#8f9cff", st_weak="#ffc35c", st_occ="#ff6b6b", st_unk="#c48bff",
                           st_none="#636366", ref="#a8c8f0", wf="Phosphore bleu", plot_style="crt"),
    "Analyseur ambre": dict(_G, plot_bg="#0f0904", plot_fg="#ffae42", curve="#ffe0b0",
                            maxhold="#b8742a", thr="#fff0d8", thr_weak="#e8b070", st_free="#4fd1c5",
                            st_libre="#5e9eff", st_weak="#ffd60a", st_occ="#ff6b6b", st_unk="#c48bff",
                            st_none="#636366", ref="#e8c08a", wf="Phosphore ambre", plot_style="crt"),
    "Analyseur blanc": dict(_G, plot_bg="#0a0b0c", plot_fg="#c8ccd2", curve="#ffffff", maxhold="#8a9098",
                            thr="#ffb4a8", thr_weak="#ffd68a", st_free="#4fd1c5", st_libre="#5e9eff",
                            st_weak="#ffc35c", st_occ="#ff6b6b", st_unk="#c48bff", st_none="#636366",
                            ref="#b0b6c0", wf="Gris", plot_style="crt"),
}
# l'ancien thème par défaut (7.12) : une config qui l'a gardé tel quel passe au nouveau (voir _apply_config)
OLD_DEFAULT_THEME = dict(ui_bg="#21252b", ui_base="#1b1f24", ui_button="#2c313a", ui_text="#d7dae0",
                         ui_accent="#528bff", plot_bg="#181a1f", plot_fg="#abb2bf", curve="#61afef",
                         maxhold="#d19a66", thr="#e06c75", thr_weak="#e5c07b", st_free="#4f9d69",
                         st_libre="#4d8fd6", st_weak="#d4a94e", st_occ="#c95c5c", st_unk="#d19a66",
                         st_none="#5c6370", ref="#c678dd")

WF_MAPS = {
    "Inferno": [(0.0, (0, 0, 4)), (0.25, (87, 16, 110)), (0.5, (188, 55, 84)),
                (0.75, (249, 142, 9)), (1.0, (252, 255, 164))],
    "Viridis": [(0.0, (68, 1, 84)), (0.25, (59, 82, 139)), (0.5, (33, 145, 140)),
                (0.75, (94, 201, 98)), (1.0, (253, 231, 37))],
    "Gris": [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))],
    "Chaud": [(0.0, (0, 0, 0)), (0.33, (180, 0, 0)), (0.66, (255, 200, 0)), (1.0, (255, 255, 255))],
    "Bleu-rouge": [(0.0, (0, 0, 60)), (0.35, (0, 120, 255)), (0.65, (255, 230, 0)), (1.0, (255, 0, 0))],
    "Rouge (nuit)": [(0.0, (0, 0, 0)), (0.5, (140, 0, 0)), (1.0, (255, 80, 80))],
    "Phosphore vert": [(0.0, (2, 8, 4)), (0.5, (20, 140, 70)), (1.0, (200, 255, 220))],
    "Phosphore bleu": [(0.0, (2, 4, 12)), (0.5, (30, 90, 190)), (1.0, (215, 235, 255))],
    "Phosphore ambre": [(0.0, (10, 5, 0)), (0.5, (170, 95, 15)), (1.0, (255, 230, 180))],
}

DEFAULT_STATUSES = [("Libre", "#4d8fd6"), ("Occupé", "#c95c5c"),            # couleurs douces (7.12)
                    ("Réservé", "#8a7fc9"), ("Hors service", "#6b7280"), ("En service", "#4f9d69")]
STATUS_AUTO_COLORS = ["#9b7fc4", "#4fa3a5", "#d19a66", "#c26d8f", "#5aa6c4", "#8aab5a",
                      "#d1825f", "#7385c4"]

BAND_PRESETS = [
    ("Aperçu : tout le tinySA 0,1–5300 MHz (pas 5 MHz)", 0.1, 5300.0, 5000.0),
    ("Aperçu : HF 0,1–30 MHz (pas 20 kHz)", 0.1, 30.0, 20.0),
    ("Aperçu : 30–1000 MHz (pas 500 kHz)", 30.0, 1000.0, 500.0),
    ("Aperçu : 1–3 GHz (pas 2 MHz)", 1000.0, 3000.0, 2000.0),
    ("Radio FM 87,5–108 MHz", 87.5, 108.0, 25.0),
    ("Aéro 108–137 MHz", 108.0, 137.0, 25.0),
    ("Police / pompiers 380–400 MHz", 380.0, 400.0, 25.0),
    ("PMR446 446–446,2 MHz", 446.0, 446.2, 6.25),
    ("UHF 470–694 MHz", 470.0, 694.0, 200.0),
    ("UHF 470–608 MHz", 470.0, 608.0, 200.0),
    ("UHF 606–694 MHz", 606.0, 694.0, 200.0),
    ("823–832 MHz", 823.0, 832.0, 100.0),
    ("863–865 MHz", 863.0, 865.0, 100.0),
    ("863–870 MHz", 863.0, 870.0, 100.0),
    ("1785–1805 MHz", 1785.0, 1805.0, 200.0),
    ("2,4 GHz (2400–2483)", 2400.0, 2483.5, 500.0),
    ("Spectera UHF 470–608 MHz", 470.0, 608.0, 200.0),
    ("Spectera UHF 630–698 MHz", 630.0, 698.0, 200.0),
    ("Spectera 1G4 1350–1400 MHz", 1350.0, 1400.0, 200.0),
    ("Spectera 1G4 1435–1525 MHz", 1435.0, 1525.0, 200.0),
]


def hex_to_rgb(h):
    h = str(h).lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return 128, 128, 128


def rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (max(0, min(255, int(round(r)))),
                              max(0, min(255, int(round(g)))),
                              max(0, min(255, int(round(b)))))


def blend(fg, bg, a):
    """Mélange fg (poids a) sur bg -> '#rrggbb'."""
    f, b = hex_to_rgb(fg), hex_to_rgb(bg)
    return rgb_to_hex(*(f[i] * a + b[i] * (1 - a) for i in range(3)))


_LEAD_ICON = re.compile("^[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u2600-\u27BF"
                        "\u2B00-\u2BFF\uFE0F\u200D]+\\s+")


def plain_btn_text(t):
    """Texte d'un bouton sans son emoji de tête (7.54, Clément : « les boutons sont vraiment pas beaux ») :
    « 🎪 Shows » -> « Shows ». Un bouton qui n'est qu'une icône (« 🔔 », « 🔔 1 », « ⚙ ») la garde."""
    if not isinstance(t, str):
        return t
    m = _LEAD_ICON.match(t)
    if not m:
        return t
    rest = t[m.end():]
    return rest if re.search(r"[^\W\d_]", rest) else t


def soft_style(c, bg, txt):
    """Bandeau « façon Apple » (7.54) : fond légèrement teinté de la couleur d'état, contour fin de la même couleur,
    texte normal. Pour les états calmes ; une alarme garde un fond plein (doit sauter aux yeux)."""
    return (f"background:{blend(c, bg, 0.18)}; color:{txt}; border:1px solid {blend(c, bg, 0.60)}; "
            f"border-radius:10px")


def contrast_text(bg):
    r, g, b = hex_to_rgb(bg)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def make_stylesheet(t):
    """Feuille de style de toute l'appli (7.54 : look « pro, façon Apple » : coins arrondis, bordures fines, survol
    discret, accent bleu pour ce qui est choisi). Les cases à cocher et les flèches des champs numériques restent
    dessinées par Qt (les styler demanderait des images)."""
    bd = blend(t["ui_text"], t["ui_bg"], 0.16)            # bordure fine
    bd2 = blend(t["ui_text"], t["ui_bg"], 0.26)           # bordure au survol
    sub = blend(t["ui_text"], t["ui_bg"], 0.62)           # texte secondaire
    hov = blend(t["ui_text"], t["ui_button"], 0.08)       # bouton survolé
    prs = blend(t["ui_text"], t["ui_button"], 0.16)       # bouton enfoncé
    sel = blend(t["ui_accent"], t["ui_base"], 0.35)       # sélection dans les listes
    alt = blend(t["ui_text"], t["ui_base"], 0.025)        # une ligne sur deux
    hdl = blend(t["ui_text"], t["ui_bg"], 0.30)           # poignée des barres de défilement
    acc, txt, bg, base, btn = t["ui_accent"], t["ui_text"], t["ui_bg"], t["ui_base"], t["ui_button"]
    on = contrast_text(acc)
    return """
QWidget { font-family: "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", sans-serif; }
QGroupBox { border:1px solid %(bd)s; border-radius:10px; margin-top:12px; padding:9px 6px 6px 6px; }
QGroupBox::title { subcontrol-origin: margin; left:12px; padding:0 4px; color:%(sub)s; font-weight:600; }
QToolTip { color:%(txt)s; background:%(btn)s; border:1px solid %(bd2)s; border-radius:6px; padding:5px 7px; }
QPushButton, QToolButton { background:%(btn)s; border:1px solid %(bd)s; border-radius:7px; padding:3px 10px; }
QPushButton:hover, QToolButton:hover { background:%(hov)s; border-color:%(bd2)s; }
QPushButton:pressed, QToolButton:pressed { background:%(prs)s; }
QPushButton:checked, QToolButton:checked { background:%(acc)s; color:%(on)s; border-color:%(acc)s; }
QPushButton:disabled, QToolButton:disabled { color:%(sub)s; background:%(bg)s; }
QPushButton:default { border:1px solid %(acc)s; }
QToolButton[popupMode="1"], QToolButton[popupMode="2"] { padding-right:18px; }
QToolBar { background:%(bg)s; border:0; spacing:4px; padding:2px 6px; }
QToolBar QToolButton { background:transparent; border:1px solid transparent; }
QToolBar QToolButton:hover { background:%(hov)s; border-color:%(bd)s; }
QToolBar QToolButton:checked { background:%(acc)s; color:%(on)s; }
QLineEdit { background:%(base)s; border:1px solid %(bd)s; border-radius:6px; padding:3px 7px;
            selection-background-color:%(acc)s; selection-color:%(on)s; }
QLineEdit:focus { border:1px solid %(acc)s; }
QTableView, QTreeView, QListView { background:%(base)s; alternate-background-color:%(alt)s; border:1px solid %(bd)s;
            border-radius:10px; gridline-color:%(bd)s; selection-background-color:%(sel)s; selection-color:%(txt)s; }
QTableView::item, QTreeView::item, QListView::item { padding:2px 4px; }
QHeaderView { background:transparent; }
QHeaderView::section { background:%(bg)s; color:%(sub)s; border:0; border-bottom:1px solid %(bd)s;
            border-right:1px solid %(bd)s; padding:5px 6px; font-weight:600; }
QTableCornerButton::section { background:%(bg)s; border:0; }
QMenu { background:%(btn)s; border:1px solid %(bd2)s; border-radius:9px; padding:5px; }
QMenu::item { padding:5px 22px 5px 12px; border-radius:6px; }
QMenu::item:selected { background:%(acc)s; color:%(on)s; }
QMenu::item:disabled { color:%(sub)s; }
QMenu::separator { height:1px; background:%(bd)s; margin:5px 8px; }
QMenu::section { color:%(sub)s; font-weight:600; padding:6px 12px 2px 12px; }
QTabWidget::pane { border:1px solid %(bd)s; border-radius:10px; top:-1px; }
QTabBar::tab { background:transparent; border:1px solid transparent; border-radius:7px; padding:5px 14px;
            margin:2px 2px; color:%(sub)s; }
QTabBar::tab:selected { background:%(btn)s; border-color:%(bd)s; color:%(txt)s; }
QTabBar::tab:hover:!selected { color:%(txt)s; }
QDockWidget { titlebar-close-icon:none; }
QDockWidget::title { background:%(bg)s; padding:6px 8px; font-weight:600; color:%(sub)s; }
QScrollBar:vertical { background:transparent; width:10px; margin:2px; }
QScrollBar:horizontal { background:transparent; height:10px; margin:2px; }
QScrollBar::handle { background:%(hdl)s; border-radius:3px; min-height:28px; min-width:28px; }
QScrollBar::handle:hover { background:%(sub)s; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
QSplitter::handle { background:%(bg)s; }
QStatusBar { color:%(sub)s; }
QProgressBar { border:1px solid %(bd)s; border-radius:6px; background:%(base)s; text-align:center; }
QProgressBar::chunk { background:%(acc)s; border-radius:5px; }
""" % dict(bd=bd, bd2=bd2, sub=sub, hov=hov, prs=prs, sel=sel, alt=alt, hdl=hdl, acc=acc, txt=txt,
                    bg=bg, base=base, btn=btn, on=on)


# ----------------------------------------------------------------- utilitaires
def _num(s):
    s = re.sub(r"(?i)\s*mhz$", "", str(s).strip()).replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def norm_freq(v):
    """Convertit Hz / kHz / MHz en MHz selon l'ordre de grandeur."""
    if v >= 1e6:
        return v / 1e6
    if v >= 7000:
        return v / 1e3
    return v


def fmt_comma(v, nd=3):
    return f"{v:.{nd}f}".replace(".", ",")


def auto_rbw(step_khz):
    """RBW adaptée au pas de mesure (utilisée par le zoom live)."""
    ok = [c for c in RBW_LIST if c <= step_khz * 3]
    return max(ok) if ok else RBW_LIST[0]


def input_plan(model_ultra, setting, start_hz):
    """Entrée à demander au tinySA pour un segment qui commence à start_hz -> "low" | "high". tinySA d'origine : deux prises, « haute » au-delà de ~800 MHz en Auto. tinySA Ultra : UNE seule
    prise, il monte au-dessus de 800 MHz en mode « ultra » ; lui envoyer « mode high input » en Auto le mettait
    dans un état bancal (retour de Clément : bandes prédéfinies au-dessus de 800 MHz qui plantent)."""
    if setting in ("low", "high"):
        return setting
    if model_ultra:
        return "low"            # entrée normale toujours (elle couvre aussi le mode ultra > 800 MHz). 7.5.1 n'envoyait
                                # plus rien : un Ultra resté en « high » (laissé par 7.5.0) ne revenait jamais → plus de scan
    return "high" if start_hz >= 800e6 else "low"


def segment_plan(n, max_pts):
    """Découpe n points en segments équilibrés de <= max_pts points."""
    max_pts = max(MIN_PTS, int(max_pts))
    n_seg = max(1, math.ceil(n / max_pts))
    base = math.ceil(n / n_seg)
    out, i = [], 0
    while i < n:
        j = min(n, i + base)
        out.append((i, j))
        i = j
    return out


def next_state(prev, lvl, occ_thr, weak_thr, weak_on, hyst=HYST):
    """Etat du signal : None / 'free' / 'weak' / 'occ' (avec hystérésis)."""
    if lvl is None:
        return None
    can_weak = bool(weak_on) and weak_thr < occ_thr
    if prev == "occ":
        if lvl >= occ_thr - hyst:
            return "occ"
        return "weak" if (can_weak and lvl >= weak_thr) else "free"
    if lvl >= occ_thr:
        return "occ"
    if can_weak:
        if prev == "weak":
            return "weak" if lvl >= weak_thr - hyst else "free"
        return "weak" if lvl >= weak_thr else "free"
    return "free"


def decimate_max(a, target):
    n = len(a)
    if n <= target:
        return a
    k = math.ceil(n / target)
    m = (n // k) * k
    out = a[:m].reshape(-1, k).max(axis=1)
    if m < n:
        out = np.append(out, a[m:].max())
    return out


TINYSA_REFUSALS = (
    ("usb disk mode active", "Le tinySA est en mode « disque USB » : il refuse les mesures. Sur le tinySA : "
                             "STORAGE › MORE › USB DISK pour en sortir (ou redémarre-le)."),
    ("firmware update active", "Le tinySA est en train de mettre à jour son firmware : attends la fin et son "
                               "redémarrage."),
    ("frequency range is invalid", "Le tinySA refuse cette plage de fréquences (hors de ses limites ?)."),
    ("exceeds range", "Le tinySA refuse ce nombre de points par commande : choisis un segment plus petit "
                      "(mode expert › Segment)."),
)


def tinysa_refusal(lines):
    """Réponse du tinySA qui refuse la commande (firmware 2026 : disque USB, mise à jour…) -> message clair, ou ""."""
    low = " ".join(str(x) for x in lines).lower()
    return next((msg for key, msg in TINYSA_REFUSALS if key in low), "")


def parse_scan_lines(lines):
    """Lignes renvoyées par `scan` -> (freqs Hz ou None, niveaux dBm).
    Accepte 'niveau' seul ou 'freq niveau', et le bug de formatage de certains firmwares."""
    fr, lv = [], []
    for l in lines:
        t = l.replace("-:.0", "-10.0").replace(":.0", "10.0").split()
        if not t:
            continue
        try:
            nums = [float(x) for x in t[:2]]
        except ValueError:
            continue
        if len(nums) >= 2 and abs(nums[0]) > 1000:
            fr.append(nums[0])
            lv.append(nums[1])
        else:
            lv.append(nums[0])
    levels = np.array(lv, dtype=float)
    if len(fr) == len(lv) and len(fr) > 0:
        freqs = np.array(fr, dtype=float)
    elif fr:                                     # audit 7.53 : réponse MÉLANGÉE (certaines lignes avec fréquence,
        freqs = np.full(len(lv), np.nan)         # d'autres sans) : on ne fait pas comme si c'était « niveaux seuls » ;
    else:                                        # NaN = fréquences illisibles -> scan_check refuse le segment
        freqs = None
    return freqs, levels


# ----------------------------------------------------------------- import CSV
def decode_text(raw):
    """Décode un fichier texte (UTF-8, UTF-16 Excel, cp1252, latin-1). Scan binaire WWB (.sdb3) : latin-1, pour que
    parse_scan_text retrouve les octets exacts."""
    if raw.lstrip(b"\xef\xbb\xbf")[:12] == b"//@ShureScan":
        return raw.decode("latin-1")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def parse_freq_cell(s, unit_hint=None):
    """'470.125' | '470,125 MHz' | '470125' | '470125000' ... -> MHz (ou None)."""
    s = str(s).strip().strip('"').strip()
    if not s:
        return None
    m = re.match(r"^([+-]?[\d\s.,]*\d)\s*(ghz|mhz|khz|hz)?$", s, re.I)
    if not m:
        return None
    num, unit = m.group(1).replace(" ", ""), (m.group(2) or unit_hint or "").lower()
    if "," in num and "." in num:
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        num = num.replace(",", "") if num.count(",") > 1 else num.replace(",", ".")
    elif num.count(".") > 1:
        num = num.replace(".", "")
    try:
        v = float(num)
    except ValueError:
        return None
    if unit == "ghz":
        mhz = v * 1000.0
    elif unit == "mhz":
        mhz = v
    elif unit == "khz":
        mhz = v / 1000.0
    elif unit == "hz":
        mhz = v / 1e6
    else:
        mhz = norm_freq(v)
    return mhz if 30.0 <= mhz <= 6000.0 else None


def _norm_hdr(h):
    h = unicodedata.normalize("NFKD", str(h)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", h).strip()


_FREQ_WORDS = ("freq", "frecuen", "carrier", "porteuse", "trager")
_NAME_PRIORITY = ["channel name", "chan name", "device name", "rf name", "name", "nom", "label",
                  "designation", "description", "bezeichnung", "nome", "nombre", "talent", "user",
                  "assignment", "affectation", "source", "utilisation", "usage", "application",
                  "kanalname", "mic", "microphone"]
_STATUS_WORDS = ("status", "statut", "state", "etat", "stato", "zustand")
_SCENE_WORDS = ("scene", "stage", "scena", "escenario", "buhne", "zone")
_GROUP_WORDS = ("groupe", "group", "artiste", "artist", "act", "show", "formation")


def unit_hint(h):
    nh = _norm_hdr(h)
    if "ghz" in nh:
        return "ghz"
    if "mhz" in nh:
        return "mhz"
    if "khz" in nh:
        return "khz"
    if re.search(r"\bhz\b", nh):
        return "hz"
    return None


def header_kind(c):
    nh = _norm_hdr(c)
    if not nh:
        return None
    if any(w in nh for w in _FREQ_WORDS) or re.fullmatch(r"(f|mhz|khz|ghz|hz|f mhz|f khz)", nh):
        return "freq"
    if any(w == nh or nh.startswith(w + " ") or nh.endswith(" " + w) for w in _STATUS_WORDS):
        return "status"
    if any(nh == w or nh.startswith(w + " ") or nh.endswith(" " + w) for w in _SCENE_WORDS):
        return "scene"
    if any(nh == w or nh.startswith(w + " ") or nh.endswith(" " + w) for w in _GROUP_WORDS):
        return "group"
    if name_rank(c) is not None:
        return "name"
    return None


def name_rank(c):
    nh = _norm_hdr(c)
    for i, k in enumerate(_NAME_PRIORITY):
        if nh == k:
            return i
    for i, k in enumerate(_NAME_PRIORITY):
        if k in nh.split() or nh.startswith(k + " ") or nh.endswith(" " + k):
            return 100 + i
    return None


def sniff_delimiter(lines):
    best, best_score = None, 0.0
    for d in (";", "\t", ","):
        counts = [l.count(d) for l in lines]
        nz = [c for c in counts if c > 0]
        if not nz:
            continue
        mode = max(set(nz), key=nz.count)
        ratio = sum(1 for c in counts if c == mode) / len(counts)
        if ratio < 0.6:
            continue
        score = ratio * (1 + min(mode, 5))
        if score > best_score + 1e-9:
            best, best_score = d, score
    return best


def _split_free_line(l):
    """'470.125 Micro 1' ou 'Micro 1 470.125 MHz' -> [nom, fréquence]."""
    toks = l.split()
    for i, tk in enumerate(toks):
        j = i
        if i + 1 < len(toks) and toks[i + 1].lower() in ("mhz", "khz", "hz", "ghz"):
            tk = tk + " " + toks[i + 1]
            j = i + 1
        if parse_freq_cell(tk) is not None:
            return [" ".join(toks[:i] + toks[j + 1:]), tk]
    return None


def read_rows(text):
    """Texte -> (rows, delimiter). Gère CSV ; , tab et lignes libres."""
    text = text.lstrip("﻿")
    lines = [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith(("#", "//"))]
    if not lines:
        return [], None
    d = sniff_delimiter(lines[:40])
    if d:
        rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=d, skipinitialspace=True))
        return rows, d
    rows = []
    for l in lines:
        r = _split_free_line(l)
        if r:
            rows.append(r)
    return rows, None


def find_header(rows):
    for i, r in enumerate(rows[:30]):
        kinds = [header_kind(c) for c in r]
        if any(parse_freq_cell(c, None) is not None for c in r):
            continue
        if any(k == "freq" for k in kinds) or sum(1 for k in kinds if k) >= 2:
            return i
    return None


_BRANDS = {
    "Shure": [r"shure", r"wwb", r"axient", r"\bqlx", r"\bulx", r"\bslx", r"\bpsm\b", r"\bad4", r"\bblx",
              r"\bglx"],
    "Sennheiser": [r"sennheiser", r"\bwsm\b", r"\bew[ -]?d", r"\bew[ -]?g", r"\bskm\b", r"\bewd\b",
                   r"\bsk ?[2369]000", r"\bem ?[2369]000", r"evolution wireless", r"\bsks\b"],
    "Wisycom": [r"wisycom", r"\bmcr\d", r"\bmtp\d", r"\bmtk\d", r"\bmpr\d", r"\bmtp\b", r"\bmcr\b"],
}


def detect_brand(text):
    low = text.lower()
    best, best_n = "Générique", 0
    for brand, pats in _BRANDS.items():
        n = sum(len(re.findall(p, low)) for p in pats)
        if n > best_n:
            best, best_n = brand, n
    return best


def analyze_csv(text):
    """Analyse un CSV : colonnes, en-tête, marque, colonnes suggérées."""
    rows, delim = read_rows(text)
    brand = detect_brand(text[:20000])
    hdr = find_header(rows) if rows else None
    ncol = max((len(r) for r in rows), default=0)
    if hdr is not None:
        headers = [str(c).strip() for c in rows[hdr]] + [""] * (ncol - len(rows[hdr]))
        data = rows[hdr + 1:]
    else:
        headers = [f"Colonne {i + 1}" for i in range(ncol)]
        data = rows
    data = [r for r in data if any(str(c).strip() for c in r)]
    hints = [unit_hint(h) if hdr is not None else None for h in headers]
    fr_frac, txt_frac, uniq = [], [], []
    for c in range(ncol):
        cells = [str(r[c]).strip() for r in data if c < len(r) and str(r[c]).strip()]
        nv = sum(1 for x in cells if parse_freq_cell(x, hints[c]) is not None)
        fr_frac.append(nv / len(data) if data else 0.0)
        nt = sum(1 for x in cells if parse_freq_cell(x, hints[c]) is None and not re.fullmatch(r"[\d.,\s+-]+", x))
        txt_frac.append(nt / len(data) if data else 0.0)
        uniq.append(len(set(cells)) / len(cells) if cells else 0.0)
    kinds = [header_kind(h) if hdr is not None else None for h in headers]
    cand = [c for c in range(ncol) if fr_frac[c] >= 0.3]
    freq_cols = [c for c in cand if kinds[c] == "freq"]
    if not freq_cols and cand:
        freq_cols = [max(cand, key=lambda c: (round(fr_frac[c], 2), -c))]
    name_col = None
    ranked = [(name_rank(headers[c]), c) for c in range(ncol)
              if hdr is not None and c not in freq_cols and name_rank(headers[c]) is not None
              and kinds[c] not in ("scene", "group") and txt_frac[c] > 0.2]
    if ranked:
        name_col = min(ranked)[1]
    else:
        texts = [c for c in range(ncol) if c not in freq_cols and txt_frac[c] >= 0.5
                 and kinds[c] not in ("scene", "group")]
        if texts:
            name_col = max(texts, key=lambda c: (round(uniq[c], 2), -c))
    status_col = next((c for c in range(ncol) if kinds[c] == "status" and c not in freq_cols), None)
    scene_col = next((c for c in range(ncol) if kinds[c] == "scene" and c not in freq_cols
                      and txt_frac[c] > 0.2), None)
    group_col = next((c for c in range(ncol) if kinds[c] == "group" and c not in freq_cols and c != scene_col
                      and txt_frac[c] > 0.2), None)
    return dict(rows=rows, delim=delim, brand=brand, hdr=hdr, headers=headers, data=data, ncol=ncol,
                hints=hints, freq_cols=freq_cols, name_col=name_col, status_col=status_col,
                scene_col=scene_col, group_col=group_col,
                samples=[next((str(r[c]).strip() for r in data if c < len(r) and str(r[c]).strip()), "")
                         for c in range(ncol)])


def build_entries_ex(an, name_col, freq_cols, status_col, scene_col=None, group_col=None):
    """-> liste de (nom, MHz, statut, scène, groupe), sans doublons de fréquence (à 1 kHz près)."""
    out, seen = [], {}
    multi = len(freq_cols) > 1

    def cell(r, c):
        return str(r[c]).strip() if (c is not None and c < len(r)) else ""

    for r in an["data"]:
        for fc in freq_cols:
            if fc >= len(r):
                continue
            f = parse_freq_cell(r[fc], an["hints"][fc])
            if f is None:
                continue
            name = cell(r, name_col)
            if multi:
                suf = re.sub(r"\(.*?\)|\[.*?\]", "", an["headers"][fc]).strip()
                name = f"{name} – {suf}" if (name and suf) else (name or suf)
            if not name:
                name = f"{f:.3f}"
            st, sc, gr = cell(r, status_col), cell(r, scene_col), cell(r, group_col)
            key = int(round(f * 1000))
            if key in seen:
                prev = out[seen[key]]
                if re.fullmatch(r"[\d.]+", prev[0]) and not re.fullmatch(r"[\d.]+", name):
                    out[seen[key]] = (name, prev[1], prev[2] or st, prev[3] or sc, prev[4] or gr)
                continue
            seen[key] = len(out)
            out.append((name, f, st, sc, gr))
    return out


def build_entries(an, name_col, freq_cols, status_col):
    """-> liste de (nom, MHz, statut), sans doublons de fréquence (à 1 kHz près)."""
    return [(n, f, s) for (n, f, s, _a, _b) in build_entries_ex(an, name_col, freq_cols, status_col)]


# ----------------------------------------------------------------- plans de bandes
CATEGORIES = {
    "tv": ("TV / TNT", "#3b82f6"),
    "tv_off": ("Ancien canal TV (réattribué)", "#475569"),
    "mobile": ("Mobile 2G / 3G / 4G / 5G", "#e0457b"),
    "pmse": ("Micros HF / PMSE", "#22c55e"),
    "broadcast": ("Radio FM / DAB+ / AM / ondes courtes", "#a855f7"),
    "safety": ("Police / pompiers / secours", "#ef4444"),
    "mil": ("Défense / militaire / radars", "#92400e"),
    "aero": ("Aéronautique civile", "#14b8a6"),
    "marine": ("Marine", "#0284c7"),
    "sat": ("Satellites / GNSS / météo", "#6366f1"),
    "ism": ("ISM / Wi-Fi / DECT / IoT", "#06b6d4"),
    "amateur": ("Radioamateur", "#eab308"),
    "civ": ("Talkies / CB (sans licence)", "#f97316"),
    "pro": ("Radios pro / rail / taxis", "#9ca3af"),
    "other": ("Autre / science / non attribué", "#64748b"),
}
THEME_KEYS.append(("ref", "Courbe de référence", "Graphique"))
for _k, (_lab, _col) in CATEGORIES.items():
    THEME_KEYS.append(("bp_" + _k, _lab, "Bandes du spectre"))
# 7.54.1 (Clément : « des couleurs prédéfinies pour les groupes qui suivent le thème, en analo aussi ») : palette des
# scènes / groupes / statuts de chaque thème (clé « pal », couleurs séparées par des virgules). Thèmes « analyseur » :
# nuances du phosphore (calculées).
GROUP_COLORS_DEF = ["#38bdf8", "#f472b6", "#a3e635", "#fbbf24", "#c084fc", "#2dd4bf", "#fb923c", "#60a5fa",
                    "#f87171", "#34d399"]
_OKABE = ["#56b4e9", "#e69f00", "#f0e442", "#0072b2", "#cc79a7", "#d55e00", "#009e73", "#999999"]
THEME_PALETTES = {
    "Pro sombre": ["#0a84ff", "#ff9f0a", "#30d158", "#bf5af2", "#ff375f", "#64d2ff", "#ffd60a", "#5e5ce6",
                   "#ff6b6b", "#4fd1c5"],
    "Pro clair": ["#007aff", "#ff9500", "#34c759", "#af52de", "#ff2d55", "#32ade6", "#ffcc00", "#5856d6",
                  "#ff3b30", "#00c7be"],
    "Catppuccin (Mocha)": ["#89b4fa", "#f5c2e7", "#a6e3a1", "#f9e2af", "#cba6f7", "#94e2d5", "#fab387", "#74c7ec",
                           "#f38ba8", "#b4befe"],
    "Tokyo Night": ["#7aa2f7", "#bb9af7", "#9ece6a", "#e0af68", "#7dcfff", "#f7768e", "#ff9e64", "#73daca",
                    "#2ac3de", "#c0caf5"],
    "Dracula": ["#bd93f9", "#ff79c6", "#50fa7b", "#f1fa8c", "#8be9fd", "#ffb86c", "#ff5555", "#6272a4"],
    "Rosé Pine": ["#c4a7e7", "#ebbcba", "#9ccfd8", "#f6c177", "#31748f", "#eb6f92", "#e0def4", "#908caa"],
    "Gruvbox": ["#83a598", "#d3869b", "#b8bb26", "#fabd2f", "#8ec07c", "#fe8019", "#fb4934", "#d5c4a1"],
    "Nord": ["#88c0d0", "#b48ead", "#a3be8c", "#ebcb8b", "#81a1c1", "#d08770", "#bf616a", "#8fbcbb", "#5e81ac"],
    "Daltonien · deutéranopie (vert)": _OKABE,
    "Daltonien · protanopie (rouge)": _OKABE,
    "Daltonien · tritanopie (bleu / jaune)": ["#33bbee", "#ee3377", "#009988", "#ee7733", "#0077bb", "#cc3311",
                                              "#bbbbbb"],
    "Monochrome (sans couleur)": ["#f0f0f0", "#a0a0a0", "#d0d0d0", "#787878", "#c0c0c0", "#8c8c8c", "#e0e0e0"],
    "Haut contraste": ["#00ffff", "#ffff00", "#ff00ff", "#00ff00", "#ff8000", "#ffffff", "#0080ff", "#ff3030"],
}


def phosphor_shades(fg, n=8):
    """Nuances d'une couleur de phosphore (de la plus vive à la plus sombre, en alternant clair / foncé pour que deux
    groupes voisins se distinguent)."""
    steps = [0.0, 0.55, 0.25, 0.75, 0.40, 0.15, 0.65, 0.33]
    out = []
    for i, k in enumerate(steps[:n]):
        out.append(blend("#ffffff", fg, k * 0.6) if i % 2 == 0 else blend("#000000", fg, k * 0.6))
    return out


def theme_pal(t):
    """Palette des scènes / groupes / statuts du thème t (liste de couleurs #rrggbb)."""
    pal = [c.strip() for c in str(t.get("pal") or "").split(",") if re.fullmatch(r"#[0-9a-fA-F]{6}", c.strip())]
    return pal or list(GROUP_COLORS_DEF)


def layers_recolor(scenes, statuses, t):
    """Recolore scènes, groupes et statuts avec la palette du thème t. Les statuts gardent leur sens : « doit rester
    libre » = couleur « réserve libre » du thème, « doit émettre » = couleur « OK » ; les autres prennent la palette.
    Renvoie (scènes, statuts) neufs."""
    pal = theme_pal(t)
    sc_out, n = [], 0
    for i, sc in enumerate(scenes):
        d = dict(sc, color=pal[i % len(pal)])
        gs = []
        for g in sc.get("groups", []):
            gs.append(dict(g, color=pal[(n + 1) % len(pal)]))
            n += 1
        d["groups"] = gs
        sc_out.append(d)
    st_out, k = [], 0
    for st in statuses:
        if st.get("free"):
            c = t.get("st_libre", pal[0])
        elif st.get("on"):
            c = t.get("st_free", pal[0])
        else:
            c = pal[(k + 3) % len(pal)]
            k += 1
        st_out.append(dict(st, color=c))
    return sc_out, st_out


# 7.57.1 (Clément : « les thèmes analo sont trop unis, ça fait trop vert, c'est surtout la visu qui est cool ») : seul
# le SPECTRE (fond, grille, axes, trace, waterfall) est façon tube ; autour (accent, scènes / groupes, bandeaux) = comme
# « Pro sombre ». OLD_CRT_THEMES = ce que ces thèmes étaient en 7.54.1-7.57.0 (accent, palette et bandeaux du phosphore)
# pour migrer une config qui les a gardés tels quels.
_OLD_CRT_ACC = {"Nuit (rouge)": "#c2453d", "Analyseur vert": "#2fbf71", "Analyseur bleu": "#3a8dff",
                "Analyseur ambre": "#e08a1e"}
OLD_CRT_THEMES = {}
for _n, _t in THEMES.items():
    _t.setdefault("ref", "#c084fc")
    _t.setdefault("plot_style", "normal")       # « crt » = spectre façon écran cathodique (7.54.1)
    _t.setdefault("pal", ",".join(THEME_PALETTES.get(_n) or (THEME_PALETTES["Pro sombre"] if _t["plot_style"] == "crt"
                                                             else GROUP_COLORS_DEF)))
    _t.setdefault("st_libre", "#3b82f6")
    for _i, (_k, (_lab, _col)) in enumerate(CATEGORIES.items()):
        _t.setdefault("bp_" + _k, _col)
    if _t["plot_style"] == "crt":
        _sh = phosphor_shades(_t["plot_fg"])
        _o = dict(pal=",".join(_sh), ui_accent=_OLD_CRT_ACC.get(_n, _t["ui_accent"]))
        for _i, (_k, (_lab, _col)) in enumerate(CATEGORIES.items()):
            _o["bp_" + _k] = blend(_sh[_i % len(_sh)], _t["plot_bg"], 0.55)
        OLD_CRT_THEMES[_n] = _o

COUNTRIES = [("FR", "France"), ("BE", "Belgique"), ("CH", "Suisse"), ("DE", "Allemagne"),
             ("GB", "Royaume-Uni"), ("IT", "Italie"), ("ES", "Espagne"), ("NL", "Pays-Bas"),
             ("EU", "Europe (générique CEPT)"), ("US", "États-Unis"), ("CA", "Canada"),
             ("AU", "Australie"), ("NZ", "Nouvelle-Zélande"), ("JP", "Japon")]

# 7.57 (Clément : « mettre la Vue sur UHF 470-694 direct si on est en France pour un nouveau show, déduire tout ça
# rapidement ») : bande UHF des micros par pays (télé + micros HF) ; États-Unis / Canada : 470-608 après le « repack ».
# 7.58.3 (Clément : « quand je change de pays ça garde 470-694 ; on add des pays ? ») : recherches du 13/11/2026 (ACMA
# LIPD 2025 : 520-694 ; RSM GUSL 272800 + GURL-SRD : 502-606 + 622-698 (7.59.1 : 502-698) ; tableau MIC Japon : 470-710 + 710-714 ; Ofcom :
# spectre entrelacé ≈ 470-702) — INDICATIF, la bande principale seulement (les petits bouts sont dans COUNTRY_NOTES).
COUNTRY_UHF = {"US": (470.0, 608.0), "CA": (470.0, 608.0), "GB": (470.0, 702.0), "AU": (520.0, 694.0),
               "NZ": (502.0, 698.0), "JP": (470.0, 714.0)}
COUNTRY_UHF_DEFAULT = (470.0, 694.0)


def country_uhf(code):
    """(début, fin) MHz de la bande UHF des micros du pays."""
    return COUNTRY_UHF.get(str(code or "").upper(), COUNTRY_UHF_DEFAULT)


def default_view_band(bands, country):
    """Bande à afficher d'office (nouveau show, 1er lancement) : la bande balayée qui recouvre le plus l'UHF du pays
    (à égalité : la plus étroite, donc la plus lisible) ; une seule bande balayée -> elle ; rien -> None.
    bands = [{id, start, stop, enabled}]."""
    on = [b for b in bands if b.get("enabled", True)]
    if len(on) == 1:
        return on[0]["id"]
    lo, hi = country_uhf(country)
    best, key = None, None
    for b in on:
        ov = min(float(b["stop"]), hi) - max(float(b["start"]), lo)
        if ov <= 0:
            continue
        k = (ov, -(float(b["stop"]) - float(b["start"])))
        if key is None or k > key:
            best, key = b["id"], k
    return best


def uhf_band_needed(bands, country, cover=0.8):
    """7.57 : bande UHF des micros du pays du show. -> None (déjà balayée : une bande cochée en couvre ≥ 80 %),
    ("resize", id, nom, début, fin) (7.58.3 : la bande « UHF … » de l'appli est recalée sur le pays), ("enable", id)
    (une bande décochée la couvre : la réactiver) ou ("add", nom, début, fin, pas) (à créer)."""
    lo, hi = country_uhf(country)
    need = cover * (hi - lo)

    def ov(b):
        return min(float(b["stop"]), hi) - max(float(b["start"]), lo)
    auto = [b for b in bands if b.get("enabled", True) and str(b.get("name", "")).startswith("UHF")
            and ov(b) >= 0.5 * (hi - lo)]
    if auto:                                      # bande créée par l'appli (ou nommée « UHF … ») : suit le pays
        b = max(auto, key=ov)
        if abs(float(b["start"]) - lo) > 0.5 or abs(float(b["stop"]) - hi) > 0.5:
            return ("resize", b["id"], f"UHF {lo:g}–{hi:g} MHz", lo, hi)
        return None
    if any(b.get("enabled", True) and ov(b) >= need for b in bands):
        return None
    off = [b for b in bands if not b.get("enabled", True) and ov(b) >= need]
    if off:
        return ("enable", min(off, key=lambda b: float(b["stop"]) - float(b["start"]))["id"])
    return ("add", f"UHF {lo:g}–{hi:g} MHz", lo, hi, 200.0)


def country_from_locale(name):
    """Code pays de l'appli d'après la langue / région du système (« fr_FR » -> « FR », « de_CH » -> « CH ») ;
    inconnu -> "". Un système en ANGLAIS ne dit rien de sûr (beaucoup de techniciens ont un Windows « en_US » en
    France : vu sur la CI Windows en 7.57) -> "" (l'appli garde la France)."""
    codes = [c for c, _n in COUNTRIES]
    t = str(name or "")
    if t[:2].lower() == "en":
        return ""
    m = re.search(r"[_-]([A-Za-z]{2})\b", t)
    c = m.group(1).upper() if m else ""
    return c if c in codes else ""


def missing_bands(freqs, bands, pad=2.0, join=10.0):
    """Fréquences de la liste qu'AUCUNE bande balayée ne couvre -> bandes à proposer [(début, fin, nombre)] en MHz
    ronds (fréquences à moins de join MHz réunies, pad MHz de marge de chaque côté). Avant 7.57 : elles restaient
    simplement « pas surveillées » (dit seulement dans « Prêt pour le show ? »)."""
    on = [(float(b["start"]), float(b["stop"])) for b in bands if b.get("enabled", True)]
    out = sorted(float(f) for f in freqs if f and not any(a - 0.05 <= float(f) <= z + 0.05 for a, z in on))
    groups = []
    for f in out:
        if groups and f - groups[-1][-1] <= join:
            groups[-1].append(f)
        else:
            groups.append([f])
    return [(float(math.floor(g[0] - pad)), float(math.ceil(g[-1] + pad)), len(g)) for g in groups]


def single_band_view(view_id, bands, zoom_id):
    """Bande du waterfall : celle de la Vue ; en « Toutes les bandes » avec UNE seule bande balayée -> celle-là
    (avant 7.57 le waterfall restait vide en disant « choisis une bande ») ; sinon None."""
    if view_id not in (-1, None):
        return view_id
    on = [b["id"] for b in bands if b.get("enabled", True)]
    return on[0] if len(on) == 1 else None


COUNTRY_NOTES = {
    # 7.59.1 (Clément : « pas sûr de toutes les bandes par pays ») : Europe revérifiée dans le tableau officiel CEPT EFIS
    # « Annex 4 : national conditions for audio PMSE » (ERC/REC 25-10, rempli par chaque régulateur), novembre 2026.
    "FR": "Plan indicatif (ANFR / ARCEP ; tableau CEPT, 2026). Micros HF en usage secondaire, 50 mW : 470-694 MHz partagés "
          "avec la TNT (canaux 21-48, canal 38 compris), 174-223 MHz, 823-832 MHz, 863-865 MHz, 1785-1805 MHz ; "
          "1350-1400 MHz sur autorisation temporaire ; 694-790 MHz interdit depuis le 1er juillet 2019 ; 380-400 MHz : "
          "réseaux police / pompiers / secours.",
    "DE": "Plan indicatif (BNetzA ; tableau CEPT, 2026). Micros HF, 50 mW : 470-694 MHz SAUF 608-614 MHz (radioastronomie), "
          "174-230 MHz, 736-753 MHz, 823-832 MHz, 863-865 MHz, 1785-1805 MHz ; 1350-1400 et 1518-1525 MHz en intérieur.",
    "GB": "Plan indicatif (Ofcom ; tableau CEPT, 2026). Micros HF dans le spectre TV entrelacé 470-694 MHz (licence Ofcom, "
          "coordonné) + bande de garde 694-703 MHz ; canal 38 (606-614) : licence Ofcom partagée ; canal 70 (863-865) sans "
          "licence ; 823-832, 1518-1525 et 1785-1805 MHz avec licence ; 703-790 MHz interdit depuis 2020.",
    "CH": "Plan indicatif (OFCOM ; tableau CEPT, 2026). Micros HF, 50 mW : 470-694 MHz (DVB-T éteint en 2019 ; 608-614 MHz "
          "interdit près de Bleien, radioastronomie), 174-223 MHz, 823-832 MHz, 863-865 MHz, 1785-1805 MHz ; "
          "1350-1400 MHz en intérieur.",
    "BE": "Plan indicatif (IBPT ; tableau CEPT, 2026). Micros HF : 470-694 MHz (le tableau CEPT indique même 470-786 MHz "
          "possible : à confirmer auprès de l'IBPT), 821,5-832 MHz, 863-865 MHz, 1785-1804,8 MHz.",
    "IT": "Plan indicatif (MIMIT ; tableau CEPT, 2026). Micros HF : 470-694 MHz, 174-223 MHz, 694-698 et 736-738 MHz, "
          "823-832 MHz, 863-865 MHz, 1518-1525 MHz, 1785-1805 MHz.",
    "ES": "Plan indicatif (SETID ; tableau CEPT, 2026). Micros HF, 50 mW : 470-694 MHz dans les canaux TV libres, "
          "821,5-832 MHz, 863-865 MHz, 1785-1805 MHz ; 174-216 MHz : 5 canaux seulement ; 694-790 MHz interdit.",
    "NL": "Plan indicatif (RDI, ex-Agentschap Telecom ; tableau CEPT, 2026). Micros HF sans licence, 100 mW : 470-694 MHz "
          "SAUF 556-558, 564-566, 572-574, 580-582, 588-590 et 604-614 MHz (liaisons audio ; 608-614 : licence, "
          "radioastronomie de Westerbork), 736-753 MHz, 821,5-832 MHz, 863-865 MHz, 1785-1805 MHz ; 1350-1400 et "
          "1518-1525 MHz avec licence.",
    "EU": "Plan harmonisé indicatif (CEPT, décision 2014/641/UE) : 470-694 MHz dans les canaux TV libres, 823-832 MHz, "
          "863-865 MHz, 1785-1805 MHz ; le reste dépend du pays.",
    "US": "Plan indicatif (FCC ; base ITU-R ENG 09/2026). Canaux TV de 6 MHz ; micros HF sur 470-608 MHz (hors canal "
          "37, 608-614), bande de garde 614-616 MHz (sans licence, 20 mW), 653-657 MHz (avec licence) et 657-663 MHz "
          "(sans licence) ; 54-72, 76-88 et 174-216 MHz ; 902-928 MHz (ISM), 1920-1930 MHz (DECT) ; 169-172 MHz, "
          "morceaux de 941-960 MHz et 1435-1525 MHz avec licence.",
    "CA": "Plan proche des USA (ISED ; base ITU-R ENG 09/2026). Canaux TV de 6 MHz ; micros HF sur 470-608 MHz, 54-72, "
          "76-88 et 174-216 MHz ; bande de garde 614-616 MHz et 657-663 MHz sans licence, 653-657 MHz avec licence ; "
          "902-928 et 1920-1930 MHz ; morceaux de 941-960 MHz et 1435-1492 MHz avec licence.",
    "AU": "Plan indicatif (ACMA, licence LIPD 2025 ; base ITU-R ENG 09/2026). Micros HF dans les canaux TV libres de "
          "520-694 MHz (canaux de 7 MHz, 100 mW e.i.r.p.), sur 174-230 MHz et 1790-1800 MHz ; 694-820 MHz interdit "
          "depuis 2015.",
    "NZ": "Plan indicatif (RSM). Micros HF sur 502-606 MHz et 622-698 MHz (licences GUSL 272800 et GURL-SRD) ; "
          "606-622 MHz exclu ; 698-806 MHz interdit depuis 2015.",
    "JP": "Plan indicatif (MIC ; base ITU-R ENG 09/2026). Micros professionnels dans les espaces blancs TV 470-710 MHz "
          "(canaux de 6 MHz) + bande dédiée 710-714 MHz, AVEC licence ; micros basse puissance sans licence sur 806-810"
          " MHz ; 1240-1260 MHz avec licence.",
}

# 7.60 (audit externe : « séparer ce qu'on balaye, ce qui est autorisé et ce qui est occupé ») : TROIS notions distinctes.
#   1. plage BALAYÉE (country_uhf, bandes à balayer) : ce que le tinySA mesure, souvent plus large que l'utilisable ;
#   2. plages AUTORISÉES (COUNTRY_ALLOWED, ci-dessous) : où un micro / IEM peut émettre d'après les notes du pays,
#      avec leurs exclusions et conditions — INDICATIF (tableau CEPT EFIS pour l'Europe, FCC / ISED / ACMA / RSM / MIC
#      ailleurs, novembre 2026), jamais une validation juridique ;
#   3. ce qui est OCCUPÉ ici : la mesure (seuils, canaux TNT mesurés).
# Condition : "" = utilisable sous les conditions générales (puissance limitée, usage secondaire) ; « licence » ;
# « intérieur » ; « limité » (créneaux ou lieux restreints : voir la note du pays).
COUNTRY_ALLOWED = {        # (début, fin, condition, puissance max indiquée par la source ; "" = non précisée)
    "FR": [(174, 223, "", "50 mW e.r.p."), (470, 694, "", "50 mW e.r.p."), (823, 832, "", "20 mW main / 100 mW corps e.i.r.p."),
           (863, 865, "", "10 mW e.r.p."), (1350, 1400, "licence", ""), (1785, 1805, "", "20 à 50 mW e.i.r.p.")],
    "DE": [(174, 230, "", "50 mW e.r.p."), (470, 608, "", "50 mW e.r.p."), (614, 694, "", "50 mW e.r.p."),
           (736, 753, "", "50 mW e.r.p."), (823, 832, "", "100 mW e.i.r.p. (823-826 main : 82 mW)"),
           (863, 865, "", "10 mW e.i.r.p."), (1350, 1400, "intérieur", "50 mW e.r.p."),
           (1518, 1525, "intérieur", "50 mW e.r.p."), (1785, 1805, "", "82 mW e.i.r.p.")],
    "GB": [(174, 216, "limité", "50 mW e.r.p."), (470, 703, "licence", "50 mW e.r.p."), (823, 832, "licence", ""),
           (863, 865, "", ""), (1518, 1525, "licence", ""), (1785, 1805, "licence", "50 mW e.r.p.")],
    "CH": [(174, 223, "", "50 mW e.r.p."), (470, 608, "", "50 mW e.r.p."), (608, 614, "limité", "50 mW e.r.p."),
           (614, 694, "", "50 mW e.r.p."), (823, 832, "", "20 mW main / 100 mW corps e.i.r.p."),
           (863, 865, "", "10 mW e.r.p."), (1350, 1400, "intérieur", ""), (1785, 1805, "", "20 à 50 mW e.i.r.p.")],
    "BE": [(174, 216, "limité", ""), (470, 694, "", ""), (821.5, 832, "", ""), (863, 865, "", ""), (1785, 1804.8, "", "")],
    "NL": [(195, 202, "", "100 mW e.i.r.p."), (470, 556, "", "100 mW e.i.r.p."), (558, 564, "", "100 mW e.i.r.p."),
           (566, 572, "", "100 mW e.i.r.p."), (574, 580, "", "100 mW e.i.r.p."), (582, 588, "", "100 mW e.i.r.p."),
           (590, 604, "", "100 mW e.i.r.p."), (608, 614, "licence", ""), (614, 694, "", "100 mW e.i.r.p."),
           (736, 753, "", "50 mW e.r.p."), (821.5, 832, "", "20 mW main / 100 mW corps e.i.r.p."),
           (863, 865, "", "10 mW e.r.p."), (1350, 1400, "licence", ""), (1518, 1525, "licence", ""),
           (1785, 1805, "", "20 mW main / 50 mW corps e.i.r.p.")],
    "IT": [(174, 223, "", ""), (470, 694, "", ""), (694, 698, "limité", ""), (736, 738, "limité", ""), (823, 832, "", ""),
           (863, 865, "", ""), (1518, 1525, "", ""), (1785, 1805, "", "")],
    "ES": [(174, 180, "limité", "50 mW e.r.p."), (470, 694, "", "50 mW e.r.p."),
           (821.5, 832, "", "20 mW main / 100 mW corps e.r.p."), (863, 865, "", "10 mW e.r.p."), (1785, 1805, "", "")],
    "EU": [(470, 694, "", "50 mW e.r.p. (habituel)"), (823, 832, "", "20 mW main / 100 mW corps e.i.r.p."),
           (863, 865, "", "10 mW e.r.p."), (1785, 1805, "", "20 à 50 mW e.i.r.p.")],
    "US": [(54, 72, "", ""), (76, 88, "", ""), (169, 172, "licence", ""), (174, 216, "", ""), (470, 608, "", ""),
           (614, 616, "", "20 mW"), (653, 657, "licence", ""), (657, 663, "", "20 mW"), (902, 928, "", ""),
           (941.5, 944, "licence", ""), (944, 952, "licence", ""), (952.85, 956.25, "licence", ""),
           (956.45, 959.85, "licence", ""), (1435, 1525, "licence", ""), (1920, 1930, "", "")],
    "CA": [(54, 72, "", ""), (76, 88, "", ""), (174, 216, "", ""), (470, 608, "", ""), (614, 616, "", ""),
           (653, 657, "licence", ""), (657, 663, "", ""), (902, 928, "", ""), (941.5, 944, "licence", ""),
           (944, 952, "licence", ""), (952.85, 956.25, "licence", ""), (956.85, 959.85, "licence", ""),
           (1435, 1492, "licence", ""), (1920, 1930, "", "")],
    "AU": [(174, 230, "", ""), (520, 694, "", "100 mW e.i.r.p."), (1790, 1800, "", "")],
    "NZ": [(502, 606, "", ""), (622, 698, "", "")],
    "JP": [(470, 714, "licence", ""), (806, 810, "", ""), (1240, 1260, "licence", "")],
}
# Sources (ordre de confiance : régulateur national > tableau CEPT EFIS > base ITU-R ENG/PMSE) et date de vérification.
REG_CHECKED = "novembre 2026"
_SRC_CEPT = ("CEPT EFIS, ERC/REC 25-10 annexe 4", "https://efis.cept.org/report/report2510AnnexImplementation.do?annexId=1")
_SRC_ITU = ("ITU-R, base ENG/PMSE (09/2026)", "https://www.itu.int/en/ITU-R/study-groups/rsg6/rwp6a/Pages/engdb.aspx")
COUNTRY_SOURCES = {
    "FR": [("ANFR / ARCEP", "https://www.anfr.fr/"), _SRC_CEPT, _SRC_ITU],
    "DE": [("Bundesnetzagentur", "https://www.bundesnetzagentur.de/"), _SRC_CEPT, _SRC_ITU],
    "GB": [("Ofcom", "https://www.ofcom.org.uk/spectrum/radio-equipment/mics-monitors"), _SRC_CEPT, _SRC_ITU],
    "CH": [("OFCOM (Suisse)", "https://www.bakom.admin.ch/en/radio_microphones"), _SRC_CEPT, _SRC_ITU],
    "BE": [("IBPT", "https://www.ibpt.be/"), _SRC_CEPT, _SRC_ITU],
    "NL": [("RDI", "https://www.rdi.nl/"), _SRC_CEPT, _SRC_ITU],
    "IT": [("MIMIT", "https://www.mimit.gov.it/"), _SRC_CEPT, _SRC_ITU],
    "ES": [("SETID", "https://avancedigital.mineco.gob.es/"), _SRC_CEPT, _SRC_ITU],
    "EU": [_SRC_CEPT, _SRC_ITU],
    "US": [("FCC, § 74.802 et part 15", "https://www.fcc.gov/wireless-microphones"), _SRC_ITU],
    "CA": [("ISED", "https://www.ised-isde.canada.ca/site/spectrum-management-telecommunications/en/node/1621"), _SRC_ITU],
    "AU": [("ACMA, licence LIPD 2025", "https://www.acma.gov.au/wireless-microphones"), _SRC_ITU],
    "NZ": [("RSM", "https://www.rsm.govt.nz/licensing/frequencies-for-anyone/radio-microphone-devices-gusl"), _SRC_ITU],
    "JP": [("MIC", "https://www.soumu.go.jp/main_content/001085598.pdf"), _SRC_ITU],
}
# 7.60.1 (audit : « le document exact, sa référence, et les incertitudes ») : textes cités par les sources lues.
COUNTRY_REFS = {
    "FR": "ARCEP, décision n° 2015-0830 (470-694, 823-832, 1785-1805 MHz) ; décisions n° 2010-0849 et 2010-0850 "
          "(174-223 MHz) ; décision n° 2016-0272 (fin de 694-790 MHz au 01/07/2019) ; décision n° 2014-1263 (863-865 MHz).",
    "DE": "BNetzA, Allgemeinzuteilungen « Mikrofone » : Vfg. 34/2020 modifiée par Vfg. 99/2022 (470-694), Vfg. 100/2022 "
          "(736-753), Vfg. 2/2015 (823-832), Vfg. 107/2018 (863-865), Vfg. 06/2022 (1350-1400), Vfg. 3/2015 (1785-1805), "
          "Vfg. 59/2015 (174-230).",
    "CH": "OFCOM, prescriptions techniques d'interface RIR1009 (-02 174-223, -05 863-865, -09 1785-1805, -10 470-694, "
          "-13 et -18 823-832 MHz).",
    "NL": "« Regeling gebruik van frequentieruimte zonder vergunning en zonder meldingsplicht » (sans licence) ; licence "
          "individuelle pour 608-614 MHz (protection du radiotélescope de Westerbork).",
    "ES": "ERC/REC 70-03 annexe 10 et décision 2014/641/UE, selon le tableau CEPT (texte national non lu).",
    "IT": "Selon le tableau CEPT (texte national non lu).",
    "BE": "Selon le tableau CEPT (texte national non lu).",
    "GB": "Ofcom : licences PMSE partagées / coordonnées, IR2030 (exemption 863-865 MHz), décision 2014/641/UE (selon le "
          "tableau CEPT ; la page Ofcom n'a pas pu être lue automatiquement).",
    "EU": "Décision 2014/641/UE (bandes PMSE audio harmonisées) ; ERC/REC 70-03 annexe 10 ; ERC/REC 25-10.",
    "US": "FCC 47 CFR § 74.802 (licence, partie 74) et § 15.236 (sans licence, partie 15).",
    "CA": "ISED, décision sur le cadre des microphones sans fil (2019) ; RSS-210 ; CPC-2-1-28.",
    "AU": "ACMA, Radiocommunications (Low Interference Potential Devices) Class Licence 2025.",
    "NZ": "RSM, General User Spectrum Licence 272800 et General User Radio Licence for Short Range Devices (GURL-SRD).",
    "JP": "Tableau des bandes du MIC et base ITU-R ENG/PMSE (régime de licence des micros professionnels).",
}
COUNTRY_DOUBTS = {
    "BE": "Le tableau CEPT indique même 470-786 MHz possible : ancien, à confirmer auprès de l'IBPT.",
    "GB": "Conditions de licence (coordination, lieu, durée) à voir avec l'Ofcom avant chaque événement.",
    "CH": "La base ITU indique « sous licence » alors que l'OFCOM décrit ces bandes sans licence : on suit l'OFCOM.",
    "JP": "Licence : démarches et conditions non détaillées ici.",
    "CA": "Les sources ne concordent pas toutes sur 652-663 MHz : on suit la base ITU (comme aux États-Unis).",
    "NZ": "622-698 MHz : la base ITU ne le montre pas, la page du RSM oui : on suit le RSM.",
    "IT": "Plages 694-698 et 736-738 MHz limitées : conditions non détaillées.",
}


# 7.60 (Clément : thethingsnetwork.org « LoRaWAN frequencies by country », lu le 13/11/2026) : bandes IoT / LoRaWAN où
# des capteurs émettent sans prévenir (souvent par paquets courts). Utile pour un micro posé dans une bande partagée.
LORA_PLANS = {"EU": ("EU863-870", [(867.0, 868.6), (868.7, 868.9), (869.4, 869.65), (433.05, 434.79)]),
              "US": ("US902-928", [(902.0, 915.0), (923.0, 928.0)]),
              "AU": ("AU915-928", [(915.0, 928.0)]),
              "JP": ("AS920-923", [(920.0, 923.5)])}
LORA_COUNTRY = {"FR": "EU", "DE": "EU", "GB": "EU", "CH": "EU", "BE": "EU", "NL": "EU", "IT": "EU", "ES": "EU", "EU": "EU",
                "US": "US", "CA": "US", "AU": "AU", "NZ": "AU", "JP": "JP"}


def lora_overlap(code, f, bw=0.0):
    """Nom du plan LoRaWAN du pays si la fréquence (ou le bloc) touche une de ses bandes, sinon ""."""
    k = LORA_COUNTRY.get(str(code or "").upper())
    if not k:
        return ""
    name, rngs = LORA_PLANS[k]
    lo, hi = float(f) - float(bw or 0) / 2.0, float(f) + float(bw or 0) / 2.0
    return name if any(lo < b and hi > a for a, b in rngs) else ""


def country_bands(code):
    """Les deux premières notions pour un pays : {scan: (début, fin) balayé, allowed: [(début, fin, condition)]}."""
    c = str(code or "").upper()
    return dict(scan=country_uhf(c), allowed=[(float(t[0]), float(t[1]), t[2]) for t in COUNTRY_ALLOWED.get(c, [])],
                power=[(float(t[0]), float(t[1]), t[3] if len(t) > 3 else "") for t in COUNTRY_ALLOWED.get(c, [])],
                sources=list(COUNTRY_SOURCES.get(c, [])), checked=REG_CHECKED)


def reg_status(code, f, bw=0.0):
    """Une fréquence (ou un bloc de largeur bw MHz) face aux plages autorisées du pays. -> (état, condition) :
    « ok » (dans une plage sans condition), « cond » (dans une plage sous condition : licence, intérieur, limité),
    « out » (hors de toutes les plages connues pour ce pays), « unknown » (pays sans liste). Un bloc doit tenir EN
    ENTIER dans des plages contiguës ; à cheval sur une plage libre et une sous condition -> la condition."""
    al = country_bands(code)["allowed"]
    if not al:
        return ("unknown", "")
    lo, hi = float(f) - float(bw or 0) / 2.0, float(f) + float(bw or 0) / 2.0
    eps = 1e-6
    for a, b, k in al:                                      # 1) dans une seule plage
        if a - eps <= lo and hi <= b + eps:
            return ("ok" if not k else "cond", k)
    segs = sorted(al)                                       # 2) bloc à cheval sur des plages qui se touchent
    pos, conds = lo, []
    for a, b, k in segs:
        if a - eps <= pos < b:
            conds.append(k)
            pos = b
            if pos >= hi - eps:
                k2 = next((x for x in conds if x), "")
                return ("ok" if not k2 else "cond", k2)
    return ("out", "")


def reg_known(code):
    """Le pays a-t-il une liste de plages autorisées ?"""
    return bool(COUNTRY_ALLOWED.get(str(code or "").upper()))


def reg_tag(code, f, bw=0.0):
    """7.60.1 (audit) : étiquette à coller sur une fréquence PROPOSÉE. "" = dans une plage sans condition ;
    sinon ce qui reste à faire : licence à obtenir, intérieur seulement, usage limité, hors bandes, ou réglementation
    inconnue (pays sans liste : une absence de données ne vaut JAMAIS autorisation)."""
    st, k = reg_status(code, f, bw)
    if st == "ok":
        return ""
    if st == "unknown":
        return "réglementation inconnue : non vérifiée"
    if st == "out":
        return "hors des bandes autorisées"
    return {"licence": "sous licence : autorisation à obtenir avant d'émettre",
            "intérieur": "en intérieur seulement", "limité": "usage limité : voir la note du pays"}.get(k, k)


def reg_allowed_pred(code, bw=0.0, cond_ok=True):
    """Pour la coordination / le secours : prédicat c -> True si la candidate est dans une plage autorisée
    (cond_ok=False : seulement les plages sans condition). Pays sans liste -> None : on ne peut pas filtrer, et les
    propositions sont alors marquées « réglementation inconnue » (reg_tag, reg_note) — jamais présentées comme validées."""
    if not COUNTRY_ALLOWED.get(str(code or "").upper()):
        return None
    ok = ("ok", "cond") if cond_ok else ("ok",)

    def pred(c):
        return reg_status(code, c, bw)[0] in ok
    if not bw:                                      # fréquence simple : test vectorisé (plages qui se touchent = ok)
        iv = [(a, b) for a, b, k in country_bands(code)["allowed"] if cond_ok or not k]

        def vec(cs):
            cs = np.asarray(cs, dtype=float)
            m = np.zeros(len(cs), dtype=bool)
            for a, b in iv:
                m |= (cs >= a - 1e-6) & (cs <= b + 1e-6)
            return m
        pred.vec = vec
    return pred


def reg_issues(code, items):
    """items = [(nom, MHz, largeur, émet)] -> (hors, sous condition) : [(nom, MHz, condition)] des ÉMETTEURS seulement
    (une réserve « doit rester libre » n'émet pas : rien à autoriser)."""
    out, cond = [], []
    for name, f, bw, tx in items:
        if not tx:
            continue
        st, k = reg_status(code, f, bw)
        if st == "out":
            out.append((name, float(f), ""))
        elif st == "cond":
            cond.append((name, float(f), k))
    return out, cond


def reg_detail(code, tr=None):
    """Tableau texte, une plage par ligne : « 470-608 MHz · autorisé · 50 mW e.r.p. », puis les sources et la date."""
    tr = tr or (lambda x: x)
    d = country_bands(code)
    if not d["allowed"]:
        return ""
    f = lambda v: f"{v:g}".replace(".", ",")
    lines = []
    for (a, b, k), (_a, _b, pw) in zip(d["allowed"], d["power"]):
        lines.append(f"{f(a)}-{f(b)} MHz · " + tr(k or "autorisé") + (f" · {tr(pw)}" if pw else ""))
    src = "; ".join(n for n, _u in d["sources"])
    c = str(code or "").upper()
    out = "\n".join(lines) + "\n" + tr("Sources : ") + src
    if COUNTRY_REFS.get(c):
        out += "\n" + tr("Textes : ") + tr(COUNTRY_REFS[c])
    if COUNTRY_DOUBTS.get(c):
        out += "\n" + tr("Incertitude : ") + tr(COUNTRY_DOUBTS[c])
    return out + "\n" + tr("Vérifié en ") + tr(d["checked"]) + "\n" + tr(
        "Autorisé par le cadre réglementaire ne veut pas dire libre ici : la TNT et la mesure décident sur place.")


def reg_summary(code, tr=None):
    """Une ligne lisible : « 470-608, 614-694 MHz ; sous condition : 1350-1400 (intérieur)… » (tr = traduction des
    mots, pour l'interface en anglais)."""
    tr = tr or (lambda x: x)
    al = country_bands(code)["allowed"]
    if not al:
        return ""
    f = lambda v: f"{v:g}".replace(".", ",")
    free = [f"{f(a)}-{f(b)}" for a, b, k in al if not k]
    cnd = [f"{f(a)}-{f(b)} ({tr(k)})" for a, b, k in al if k]
    return ", ".join(free) + " MHz" + (tr(" ; sous condition : ") + ", ".join(cnd) if cnd else "")


# début-fin (MHz) | catégorie | libellé | note
PLAN_EU = """
0.1-0.1485|other|Radionavigation / signaux horaires (LF)|Dont radioamateur 135,7-137,8 kHz
0.1485-0.2835|broadcast|Radio grandes ondes (LW)|
0.2835-0.5265|aero|Radiobalises NDB (aéro) / marine|Bande 283,5-526,5 kHz
0.5265-1.6065|broadcast|Radio AM ondes moyennes (MW)|
1.6065-1.81|marine|Marine / fixe (HF bas)|
1.81-2|amateur|Radioamateur 160 m|
2-3.5|marine|Marine / aéro / mobile HF|Dont détresse 2182 kHz
3.5-3.8|amateur|Radioamateur 80 m|
3.8-5.9|pro|HF mobile / fixe / défense|Dont radio tropicale 3,9-4,0 et 4,75-5,06 MHz
5.9-6.2|broadcast|Ondes courtes 49 m|
6.2-7|marine|Marine / aéro HF|
7-7.2|amateur|Radioamateur 40 m|
7.2-7.45|broadcast|Ondes courtes 41 m|
7.45-9.4|pro|HF mobile / fixe / défense|
9.4-9.9|broadcast|Ondes courtes 31 m|
9.9-10.1|pro|HF fixe / mobile|Étalon de fréquence 10 MHz
10.1-10.15|amateur|Radioamateur 30 m|
10.15-11.6|pro|HF mobile / fixe / aéro|
11.6-12.1|broadcast|Ondes courtes 25 m|
12.1-13.57|marine|Marine / aéro HF|
13.57-13.87|broadcast|Ondes courtes 22 m|
13.87-14|pro|HF fixe|
14-14.35|amateur|Radioamateur 20 m|
14.35-15.1|pro|HF mobile / fixe|
15.1-15.8|broadcast|Ondes courtes 19 m|
15.8-17.48|marine|Marine / aéro HF|
17.48-17.9|broadcast|Ondes courtes 16 m|
17.9-18.068|aero|Aéro HF|
18.068-18.168|amateur|Radioamateur 17 m|
18.168-21|pro|HF fixe / mobile|
21-21.45|amateur|Radioamateur 15 m|
21.45-21.85|broadcast|Ondes courtes 13 m|
21.85-24.89|marine|Marine / aéro HF|
24.89-24.99|amateur|Radioamateur 12 m|
24.99-26.565|broadcast|Ondes courtes 11 m / HF|
26.565-26.965|civ|CB / modélisme (bas de la bande 27 MHz)|
26.965-27.405|civ|CB 27 MHz (40 canaux)|Sans licence dans beaucoup de pays (puissance limitée)
27.405-28|civ|CB / modélisme / ISM 27 MHz|
28-29.7|amateur|Radioamateur 10 m|
29.7-47|pro|VHF bas : radios pro, défense, secours|
47-68|tv_off|Ancienne bande I TV (47-68 MHz)|Aujourd'hui radios pro / défense selon pays
68-87.5|pro|VHF bas : radios pro / défense / secours|
87.5-108|broadcast|Radio FM|
108-117.975|aero|Aéronautique : radionavigation (VOR / ILS)|
117.975-137|aero|Aéronautique : voix avions|
137-138|sat|Satellites météo (NOAA APT, Meteor)|
138-144|mil|Défense / aéronautique militaire|
144-146|amateur|Radioamateur 2 m|
146-156|pro|VHF mobile professionnel (PMR, secours, taxis)|
156-162.05|marine|Marine VHF|Dont AIS 161,975 et 162,025 MHz
162.05-174|pro|VHF mobile professionnel (PMR, secours)|
174-230|broadcast|VHF bande III : DAB+ (et anciens canaux TV)|
230-380|mil|Défense : aéronautique militaire (OTAN)|Bande 225-400 MHz
380-400|safety|Sécurité publique : police / pompiers / secours (TETRA, Tetrapol)|Réseaux numériques harmonisés en Europe
400-406|sat|Radiosondes météo / satellites|
406-406.1|sat|Balises de détresse (COSPAS-SARSAT)|
406.1-410|other|Radioastronomie / mobile|
410-430|mil|Défense / radios pro (mobile)|
430-433.05|amateur|Radioamateur 70 cm|
433.05-434.79|ism|ISM 433 MHz : télécommandes, capteurs, LoRa (EU433)|Partagé avec le radioamateur 70 cm
434.79-440|amateur|Radioamateur 70 cm|
440-446|pro|UHF mobile professionnel|
446-446.2|civ|PMR446 (talkies sans licence)|
446.2-450|pro|UHF mobile professionnel|
450-470|pro|UHF mobile professionnel (PMR/PAMR)|
470-694|tv|TNT / DVB-T2 + micros HF (PMSE)|Bande UHF partagée TV / micros HF, varie selon la région
694-703|pmse|Bande de garde 700 MHz (micros HF selon pays)|
703-733|mobile|4G/5G 700 MHz : montant|
733-758|pmse|Écart duplex 700 MHz (PPDR / SDL / micros selon pays)|
758-788|mobile|4G/5G 700 MHz : descendant|
788-791|other|Garde 700/800 MHz|
791-821|mobile|4G 800 MHz : descendant|
821-832|pmse|Écart duplex 800 MHz (micros HF 823-832)|
832-862|mobile|4G 800 MHz : montant|
863-865|pmse|Micros HF libres 863-865 MHz (10 mW)|
865-870|ism|SRD / RFID / IoT 868 MHz (LoRaWAN EU863-870)|LoRaWAN : 867,1-868,5 MHz et 869,525 MHz (passerelles)
870-876|pro|Radios pro / SRD|
876-880|pro|GSM-R (trains) : montant|
880-915|mobile|2G/3G/4G 900 MHz : montant|
915-921|ism|SRD / RFID|
921-925|pro|GSM-R (trains) : descendant|
925-960|mobile|2G/3G/4G 900 MHz : descendant|
960-1215|aero|Aéronautique : DME / TACAN / radar secondaire / ADS-B 1090|
1215-1240|sat|GNSS (GPS L2) / radars|
1240-1300|amateur|Radioamateur 23 cm / GNSS Galileo E6|
1300-1350|mil|Radars de contrôle aérien|
1350-1400|mil|Défense / radars|
1400-1427|other|Radioastronomie (raie de l'hydrogène)|
1427-1518|mobile|Bande L : 4G/5G descendant supplémentaire|Usage variable selon pays
1518-1559|sat|Satellites mobiles (Inmarsat) : descendant|
1559-1610|sat|GNSS (GPS L1, Galileo E1, GLONASS)|
1610-1626.5|sat|Satellites mobiles (Iridium, Globalstar)|
1626.5-1660.5|sat|Satellites mobiles : montant|
1660.5-1710|sat|Satellites météo / radiosondes / radioastronomie|
1710-1785|mobile|4G 1800 MHz : montant|
1785-1805|pmse|Écart duplex 1800 MHz (micros HF)|
1805-1880|mobile|4G 1800 MHz : descendant|
1880-1900|ism|DECT|
1900-1920|mobile|TDD 2000 MHz|
1920-1980|mobile|3G/4G 2100 MHz : montant|
1980-2010|sat|Satellites mobiles : montant|
2010-2025|mobile|TDD 2000 MHz|
2025-2110|pmse|Liaisons vidéo mobiles (caméras HF) / spatial|
2110-2170|mobile|3G/4G 2100 MHz : descendant|
2170-2200|sat|Satellites mobiles : descendant|
2200-2290|mil|Défense / spatial|
2290-2300|sat|Spatial|
2300-2400|other|Défense / liaisons vidéo / 4G TDD selon pays|
2400-2483.5|ism|Wi-Fi / Bluetooth 2,4 GHz (ISM)|
2483.5-2500|sat|Satellites mobiles|
2500-2570|mobile|4G 2600 MHz : montant|
2570-2620|mobile|4G 2600 MHz : TDD|
2620-2690|mobile|4G 2600 MHz : descendant|
2690-2700|other|Radioastronomie|
2700-3100|mil|Radars (aviation / météo / défense)|
3100-3400|mil|Radars (maritime / météo / défense)|
3400-3800|mobile|5G 3,5 GHz|
3800-4200|sat|Satellites (bande C descendant) / 5G selon pays|
4200-4400|aero|Altimètres radar d'aéronefs|
4400-5000|mil|Défense / liaisons fixes|
5000-5150|aero|Aéronautique : MLS / liaisons|
5150-5350|ism|Wi-Fi 5 GHz|
5350-5470|mil|Radars (météo / défense)|
5470-5725|ism|Wi-Fi 5 GHz|
5725-5875|ism|5,8 GHz (Wi-Fi / ISM / télépéage)|
5875-5925|ism|ITS (véhicules connectés)|
"""

PLAN_OVERRIDES = {
    "FR": """
174-223|broadcast|DAB+ (VHF III) : micros HF libres, interférences régionales|
380-400|safety|Police / gendarmerie / pompiers / SAMU (réseaux INPT, Tetrapol)|Numérique, souvent chiffré : on ne mesure que le niveau
470-694|tv|TNT (DVB-T2) + micros HF pros : usage partagé|
""",
    "DE": """
608-614|other|608-614 MHz : radioastronomie, interdit aux micros (Allemagne)|
736-753|pmse|Micros HF professionnels sans licence (Allemagne)|
1350-1400|pmse|Micros HF en intérieur (Allemagne)|
1518-1525|pmse|Micros HF en intérieur (Allemagne)|
""",
    "GB": """
606-614|pmse|Canal 38 : micros HF, licence Ofcom partagée (UK)|
694-703|pmse|Bande de garde 700 MHz : micros HF (licence Ofcom)|
863-865|pmse|Canal 70 : micros HF sans licence (UK)|
""",
    "CH": """
470-608|pmse|UHF : DVB-T éteint (2019), micros HF autorisés (50 mW)|
608-614|other|608-614 MHz : interdit près de Bleien (radioastronomie)|
614-694|pmse|UHF : DVB-T éteint (2019), micros HF autorisés (50 mW)|
""",
    "NL": """
604-614|other|604-614 MHz : pas pour les micros sans licence (608-614 : licence, radioastronomie)|
736-753|pmse|Micros HF sans licence (Pays-Bas)|
""",
    "AU": """
790-915|mobile|Téléphonie mobile 4G/5G (plan du pays)|
915-928|ism|ISM 915-928 MHz : LoRaWAN AU915-928, RFID, IoT|LoRaWAN : montante 915-928 MHz, descendante 923-928 MHz
928-960|mobile|Téléphonie mobile 4G/5G (plan du pays)|
""",
    "NZ": """
790-915|mobile|Téléphonie mobile 4G/5G (plan du pays)|
915-928|ism|ISM 915-928 MHz : LoRaWAN AU915-928, RFID, IoT|LoRaWAN : montante 915-928 MHz, descendante 923-928 MHz
928-960|mobile|Téléphonie mobile 4G/5G (plan du pays)|
""",
    "JP": """
790-806|mobile|Téléphonie mobile 4G/5G (plan du pays)|
806-810|pmse|Micros basse puissance sans licence (Japon)|
810-915|mobile|Téléphonie mobile 4G/5G (plan du pays)|
915-928|ism|ISM 920 MHz : LoRaWAN AS920-923, RFID, IoT|LoRaWAN AS920-923 : 920-923,5 MHz
928-960|mobile|Téléphonie mobile 4G/5G (plan du pays)|
""",
    "IT": """
694-698|pmse|Micros HF (Italie, limité)|
736-738|pmse|Micros HF (Italie, limité)|
""",
}

# Bas du spectre (< 30 MHz) pour les USA : on reprend le plan européen avec ces corrections.
PLAN_US_LOW = """
0.535-1.705|broadcast|Radio AM (MW)|
3.5-4|amateur|Radioamateur 80 m|
7-7.3|amateur|Radioamateur 40 m|
"""

PLAN_US = """
30-50|pro|VHF bas : gouvernement, radios pro|
50-54|amateur|Radioamateur 6 m|
54-72|tv|TV VHF bas (canaux 2-4)|
72-76|pro|Radios pro / micros d'assistance (72-76 MHz)|
76-88|tv|TV VHF bas (canaux 5-6)|
88-108|broadcast|Radio FM|
108-137|aero|Aéronautique : VOR / ILS et voix avions|
137-138|sat|Satellites météo|
138-144|mil|Gouvernement / militaire|
144-148|amateur|Radioamateur 2 m|
148-150.8|pro|Gouvernement / satellites|
150.8-156|pro|VHF mobile pro (MURS 151-154 MHz, business)|
156-162.025|marine|Marine VHF|
162.025-162.4|pro|VHF mobile pro / sécurité publique|
162.4-162.55|other|NOAA Weather Radio|
162.55-174|pro|VHF mobile pro / sécurité publique|
174-216|tv|TV VHF haut (canaux 7-13)|
216-220|pro|Radios pro / télémétrie|
222-225|amateur|Radioamateur 1,25 m|
225-400|mil|Gouvernement / aéronautique militaire|
400-406|sat|Radiosondes météo / satellites|
406-406.1|sat|Balises de détresse (COSPAS-SARSAT)|
406.1-420|pro|Gouvernement / radios pro|
420-450|amateur|Radioamateur 70 cm|
450-462|pro|UHF mobile pro / sécurité publique|
462-467.725|civ|FRS / GMRS (talkies)|
467.725-470|pro|UHF mobile pro|
470-608|tv|TV UHF (canaux 14-36) + micros HF|
608-614|other|Canal 37 : radioastronomie / télémétrie médicale|
614-616|pmse|Garde 600 MHz : micros sans licence (20 mW)|
617-652|mobile|4G/5G 600 MHz : descendant|
652-663|pmse|Écart duplex 600 MHz : micros HF (licence / white space)|
663-698|mobile|4G/5G 600 MHz : montant|
698-806|mobile|4G/5G 700 MHz (opérateurs, FirstNet)|
806-824|pro|Sécurité publique / SMR 800 MHz|
824-849|mobile|Cellulaire 850 MHz : montant|
851-869|pro|Sécurité publique / SMR 800 MHz|
869-894|mobile|Cellulaire 850 MHz : descendant|
902-928|ism|ISM 900 MHz (micros numériques, LoRa)|LoRaWAN US902-928 : montante 902-915 MHz, descendante 923-928 MHz
960-1215|aero|Aéronautique : DME / TACAN / radar secondaire / ADS-B 1090|
1215-1350|mil|Radars / GNSS|
1559-1610|sat|GNSS (GPS L1)|
1710-1755|mobile|AWS : montant|
1850-1915|mobile|PCS : montant|
1920-1930|ism|DECT 6.0|
1930-1995|mobile|PCS : descendant|
2110-2155|mobile|AWS : descendant|
2400-2483.5|ism|Wi-Fi / Bluetooth 2,4 GHz (ISM)|
2496-2690|mobile|4G/5G 2,5 GHz|
2700-3100|mil|Radars (aviation / météo / défense)|
3450-3550|mobile|5G 3,45 GHz|
3550-3700|mobile|CBRS (partagé)|
3700-3980|mobile|5G bande C|
4200-4400|aero|Altimètres radar d'aéronefs|
5150-5895|ism|Wi-Fi 5 GHz|
"""


def parse_plan_text(text):
    """'début-fin|catégorie|libellé|note' -> [(début, fin, libellé, cat, note)]."""
    out = []
    for line in str(text).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) < 3 or "-" not in p[0]:
            continue
        a, b = p[0].split("-", 1)
        try:
            a, b = float(a), float(b)
        except ValueError:
            continue
        if b <= a:
            continue
        cat = p[1] if p[1] in CATEGORIES else "other"
        out.append((a, b, p[2], cat, p[3] if len(p) > 3 else ""))
    return out


def apply_overrides(base, over):
    """Remplace dans `base` les plages couvertes par `over` (qui sont ajoutées)."""
    out = []
    for (a, b, lab, cat, note) in base:
        segs = [(a, b)]
        for o in over:
            oa, ob = o[0], o[1]
            nxt = []
            for (s, e) in segs:
                if ob <= s or oa >= e:
                    nxt.append((s, e))
                else:
                    if oa > s:
                        nxt.append((s, oa))
                    if ob < e:
                        nxt.append((ob, e))
            segs = nxt
        for s, e in segs:
            out.append((s, e, lab, cat, note))
    out.extend(over)
    out.sort(key=lambda t: (t[0], t[1]))
    return out


def build_plan(code, user_text=None):
    if user_text and user_text.strip():
        plan = parse_plan_text(user_text)
        if plan:
            return plan
    if code in ("US", "CA"):
        low = [e for e in parse_plan_text(PLAN_EU) if e[1] <= 30.0]
        low = apply_overrides(low, parse_plan_text(PLAN_US_LOW))
        return sorted(low + parse_plan_text(PLAN_US), key=lambda t: (t[0], t[1]))
    base = parse_plan_text(PLAN_EU)
    ov = PLAN_OVERRIDES.get(code)
    return apply_overrides(base, parse_plan_text(ov)) if ov else base


def fmt_freq_mhz(v):
    """0.1485 -> '148,5 kHz' ; 470 -> '470 MHz' ; 5300 -> '5,3 GHz'."""
    if v < 1.0:
        s, u = v * 1000.0, "kHz"
    elif v >= 1000.0:
        s, u = v / 1000.0, "GHz"
    else:
        s, u = v, "MHz"
    return f"{s:.4f}".rstrip("0").rstrip(".").replace(".", ",") + " " + u


def plan_to_text(plan):
    return "\n".join(f"{a:g}-{b:g}|{cat}|{lab}|{note}" for (a, b, lab, cat, note) in plan)


def tv_channels(code):
    """Canaux TV du pays : [(début, fin, libellé, cat, note)]."""
    out = []
    if code in ("US", "CA"):
        def add(n, a, cat="tv", note=None):
            out.append((a, a + 6, f"CH {n}", cat, note or f"Canal TV {n} : {a:g}-{a + 6:g} MHz"))
        for n in (2, 3, 4):
            add(n, 54 + 6 * (n - 2))
        for n in (5, 6):
            add(n, 76 + 6 * (n - 5))
        for n in range(7, 14):
            add(n, 174 + 6 * (n - 7))
        for n in range(14, 37):
            add(n, 470 + 6 * (n - 14))
        add(37, 608, "other", "Canal 37 : radioastronomie / télémétrie médicale")
        return out
    if code == "AU":                                 # 7.58.3 : canaux de 7 MHz (UHF 27 = 519-526 … 51 = 687-694)
        for n in range(27, 52):
            a = 519 + 7 * (n - 27)
            out.append((a, a + 7, f"CH {n}", "tv", f"Canal UHF {n} (7 MHz) : {a}-{a + 7} MHz"))
        return out
    if code == "JP":                                 # 7.58.3 : canaux de 6 MHz (13 = 470-476 … 52 = 704-710)
        for n in range(13, 53):
            a = 470 + 6 * (n - 13)
            out.append((a, a + 6, f"CH {n}", "tv", f"Canal UHF {n} (6 MHz) : {a}-{a + 6} MHz"))
        return out
    for n in range(5, 13):
        a = 174 + 7 * (n - 5)
        out.append((a, a + 7, f"CH {n}", "tv_off",
                    f"Canal VHF {n} (7 MHz) : {a}-{a + 7} MHz, aujourd'hui surtout DAB+"))
    for n in range(21, 70):
        a = 470 + 8 * (n - 21)
        if n <= 48:
            cat = "tv_off" if code == "CH" else "tv"
            note = f"Canal UHF {n} (8 MHz) : {a}-{a + 8} MHz"
            if code == "CH":
                note += " (DVB-T éteint en Suisse)"
        elif n <= 60:
            cat, note = "tv_off", f"Ancien canal {n} : {a}-{a + 8} MHz, réattribué à la 4G/5G (700 MHz)"
        else:
            cat, note = "tv_off", f"Ancien canal {n} : {a}-{a + 8} MHz, réattribué à la 4G (800 MHz)"
        out.append((a, a + 8, f"CH {n}", cat, note))
    return out


# 7.58 (Clément : « une base à jour des bandes / de la TNT ») : 📺 canaux TNT MESURÉS au lieu du show (sans internet) +
# émetteurs TNT proches d'après la base ouverte de l'ANFR (position, exploitant, nombre de multiplex ; la base ne donne
# PAS les canaux : elle indique toute la bande 470-694 / 470-790 pour chaque émetteur).
TNT_MARGIN_DB = 10.0          # un canal est « TNT » si son plateau est à ≥ 10 dB au-dessus du bruit de fond…
TNT_FILL = 0.6                # … sur au moins 60 % de sa largeur (une porteuse étroite seule = « autre signal »)


def tnt_channel_list(code):
    """Canaux TV de la bande UHF des micros du pays : [(n°, début, fin)] (8 MHz en Europe, 6 MHz aux USA / Canada)."""
    lo, hi = country_uhf(code)
    out = []
    for (a, b, lab, cat, note) in tv_channels(code):
        if cat in ("tv", "tv_off") and a >= lo - 1e-6 and b <= hi + 1e-6:
            try:
                out.append((int(str(lab).split()[-1]), float(a), float(b)))
            except ValueError:
                pass
    return out


def tnt_measure(F, L, chans, margin=TNT_MARGIN_DB, floor=None):
    """Canaux TNT d'après un spectre mesuré. -> dict(floor, rows=[dict(ch, lo, hi, state, level, peak, above, fill)]) ;
    state : « tv » (plateau large au-dessus du bruit), « other » (signal étroit, micro, porteuse…), « free », « none »
    (pas mesuré). floor = bruit de fond (10ᵉ centile du spectre si None)."""
    F = np.asarray(F, dtype=float) if F is not None else np.zeros(0)
    L = np.asarray(L, dtype=float) if L is not None else np.zeros(0)
    ok = np.isfinite(F) & np.isfinite(L)
    F, L = F[ok], L[ok]
    if floor is None:
        floor = float(np.percentile(L, 10)) if len(L) >= 8 else None
    rows = []
    for n, a, b in chans:
        m = (F >= a + 0.5) & (F <= b - 0.5)
        r = dict(ch=int(n), lo=float(a), hi=float(b), state="none", level=None, peak=None, above=None, fill=None)
        if floor is not None and int(m.sum()) >= 4:
            lv = L[m]
            med = float(np.median(lv))
            fill = float(np.mean(lv >= floor + margin))
            r.update(level=med, peak=float(lv.max()), above=med - floor, fill=fill)
            if fill >= TNT_FILL and med - floor >= margin:
                r["state"] = "tv"
            elif float(lv.max()) >= floor + margin:
                r["state"] = "other"
            else:
                r["state"] = "free"
        rows.append(r)
    return dict(floor=floor, rows=rows)


def tnt_summary(res):
    """Phrase courte : canaux TNT pris / libres / autres signaux / pas mesurés."""
    rows = res.get("rows") or []
    by = {k: [str(r["ch"]) for r in rows if r["state"] == k] for k in ("tv", "other", "free", "none")}
    if not rows or len(by["none"]) == len(rows):
        return "Pas de mesure sur la bande UHF : lance un scan (▶ Scanner ici) puis recommence."
    parts = [f"📺 TNT sur {len(by['tv'])} canal(aux) : {', '.join(by['tv']) or 'aucun'}",
             f"libres : {', '.join(by['free']) or 'aucun'}"]
    if by["other"]:
        parts.append(f"autres signaux : {', '.join(by['other'])}")
    if by["none"]:
        parts.append(f"pas mesurés : {', '.join(by['none'])}")
    return " · ".join(parts)


TNT_DEFAULT = dict(place="", radius=60, margin=10, mark=True, manual={}, plan=[], plan_src="")


def tnt_cfg_norm(c):
    """Réglages 📺 TNT (config + show) : lieu tapé, rayon km, marge dB, canaux grisés sur le spectre."""
    c = c if isinstance(c, dict) else {}
    out = dict(TNT_DEFAULT)
    out["place"] = " ".join(str(c.get("place") or "").split())[:60]
    for k, lo, hi in (("radius", 5, 200), ("margin", 3, 30)):
        try:
            out[k] = int(min(hi, max(lo, int(c.get(k, out[k])))))
        except (TypeError, ValueError):
            pass
    out["mark"] = bool(c.get("mark", True))
    man = {}
    for k, v in (c.get("manual") or {}).items() if isinstance(c.get("manual"), dict) else []:
        try:
            n = int(k)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 99 and v in ("tv", "free"):
            man[str(n)] = v
    out["manual"] = man
    plan = []
    for v in c.get("plan") or [] if isinstance(c.get("plan"), list) else []:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 99 and n not in plan:
            plan.append(n)
    out["plan"] = sorted(plan)
    out["plan_src"] = " ".join(str(c.get("plan_src") or "").split())[:80] if plan else ""
    return out


def tnt_apply_manual(res, manual, plan=None):
    """Choix faits à la main (« tv » = griser, « free » = pas de TNT) puis canaux TV du plan de coordination importé
    (7.58.2), par-dessus la mesure : rows copiées ; « src » = manual | plan | "" (mesure), « manual » = forcé à la main."""
    manual, plan = manual or {}, set(plan or [])
    rows = []
    for r in (res or {}).get("rows") or []:
        m = manual.get(str(r["ch"]))
        if m in ("tv", "free"):
            rows.append(dict(r, state=m, manual=True, src="manual"))
        elif r["ch"] in plan:
            rows.append(dict(r, state="tv", manual=False, src="plan"))
        else:
            rows.append(dict(r, manual=False, src=""))
    return dict(res or {}, rows=rows)


ANFR_DATASET = ("https://www.data.gouv.fr/api/1/datasets/"
                "donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1/")
ANFR_TNT_SYSTEM = "RDF DVB-T"


def anfr_text(raw):
    """Ligne d'un fichier ANFR (octets) -> texte : UTF-8 si possible, sinon latin-1 (les fichiers mélangent)."""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _anfr_dms(d, m, s_, h):
    v = int(d) + int(m) / 60.0 + float(str(s_).replace(",", ".")) / 3600.0
    return -v if h in ("S", "W", "O") else v


def anfr_tnt_sites(emetteur, support, station=(), exploitant=()):
    """Fichiers de la base ANFR (lignes texte, avec leur en-tête) -> dict(sites=[[lat, lon, multiplex, hauteur m, lieu,
    code postal, exploitant]], cp={code postal: [lat, lon]}) ; sites = supports d'émetteurs TNT réunis par position
    (un multiplex = un émetteur DVB-T) ; cp = centre des supports de chaque code postal (pour trouver un lieu sans
    internet)."""
    tnt = {}
    for ln in emetteur:
        p = anfr_text(ln).rstrip("\r\n").split(";")
        if len(p) > 2 and p[1].strip() == ANFR_TNT_SYSTEM:
            tnt[p[2].strip()] = tnt.get(p[2].strip(), 0) + 1
    names = {}
    for ln in exploitant:
        p = anfr_text(ln).rstrip("\r\n").split(";")
        if len(p) > 1:
            names[p[0].strip()] = p[1].strip()
    adm = {}
    for ln in station:
        p = anfr_text(ln).rstrip("\r\n").split(";")
        if len(p) > 1 and p[0].strip() in tnt:
            adm[p[0].strip()] = names.get(p[1].strip(), "")
    sites, cps, seen = {}, {}, set()
    for ln in support:
        p = anfr_text(ln).rstrip("\r\n").split(";")
        if len(p) < 19:
            continue
        try:
            lat = _anfr_dms(p[3], p[4], p[5], p[6].strip())
            lon = _anfr_dms(p[7], p[8], p[9], p[10].strip())
        except (ValueError, TypeError):
            continue
        cp = p[17].strip()
        if re.fullmatch(r"\d{5}", cp):
            c = cps.setdefault(cp, [0.0, 0.0, 0])
            c[0] += lat
            c[1] += lon
            c[2] += 1
        sta = p[1].strip()
        if sta in tnt and sta not in seen:
            seen.add(sta)
            k = (round(lat, 3), round(lon, 3))
            st = sites.setdefault(k, [round(lat, 4), round(lon, 4), 0, 0, "", cp, ""])
            st[2] += tnt[sta]
            try:
                st[3] = max(st[3], int(float(p[11].replace(",", "."))))
            except ValueError:
                pass
            st[4] = st[4] or " ".join(p[13].split()) or " ".join(p[14].split())
            st[6] = st[6] or adm.get(sta, "")
    return dict(sites=list(sites.values()),
                cp={k: [round(v[0] / v[2], 4), round(v[1] / v[2], 4)] for k, v in cps.items() if v[2]})


def anfr_pick(api):
    """Réponse JSON de data.gouv.fr (jeu ANFR) -> (url des tables « supports … émetteurs », url des tables de référence,
    date) des fichiers les plus récents ; (None, None, "") si introuvable."""
    def plain(t):
        return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    data = ref = None
    for r in sorted(api.get("resources") or [], key=lambda r_: str(r_.get("last_modified") or ""), reverse=True):
        t, u = plain(r.get("title")), r.get("url")
        if data is None and "support" in t and "emetteur" in t:
            data = (u, str(r.get("last_modified") or "")[:10])
        elif ref is None and "reference" in t:
            ref = u
    return (data[0] if data else None), ref, (data[1] if data else "")


def geo_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau en km (formule de haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def place_parse(text, cps=None):
    """Lieu tapé par l'utilisateur -> (lat, lon, libellé) ou None : « 48.8584, 2.2945 », « 48,8584 2,2945 » (degrés
    décimaux) ou un code postal à 5 chiffres (centre des supports ANFR de ce code)."""
    t = " ".join(str(text or "").split())
    m = re.fullmatch(r"(-?\d{1,2}(?:[.,]\d+)?)\s*[;, ]\s*(-?\d{1,3}(?:[.,]\d+)?)", t)
    if m:
        lat, lon = float(m.group(1).replace(",", ".")), float(m.group(2).replace(",", "."))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon, f"{lat:.4f}, {lon:.4f}"
    m = re.fullmatch(r"(\d{5})", t)
    if m and cps and m.group(1) in cps:
        lat, lon = cps[m.group(1)]
        return float(lat), float(lon), m.group(1)
    return None


def tnt_sites_near(sites, lat, lon, radius=60.0, n=40):
    """Sites TNT à moins de radius km -> [(km, site)] du plus proche au plus loin (n au plus)."""
    out = []
    for s_ in sites or []:
        try:
            d = geo_km(lat, lon, float(s_[0]), float(s_[1]))
        except (TypeError, ValueError, IndexError):
            continue
        if d <= radius:
            out.append((d, s_))
    out.sort(key=lambda x: x[0])
    return out[:n]


def tnt_near_text(near):
    """Phrase de conseil d'après le site TNT le plus proche."""
    if not near:
        return "Aucun émetteur TNT dans ce rayon : la TNT reçue vient de loin, elle devrait être faible."
    d, s_ = near[0]
    big = int(s_[2] or 0) >= 4
    if d < 5:
        how = "très proche : attends-toi à une TNT très forte, garde de la marge autour des canaux pris"
    elif d < 20:
        how = "proche : TNT forte sur ses canaux"
    else:
        how = "assez loin : TNT moyenne à faible"
    return (f"Émetteur le plus proche : {s_[4] or s_[5]} à {d:.1f} km ({int(s_[2] or 0)} multiplex"
            f"{', site principal' if big else ''}) — {how}.")


def spectrum_text(f, plan, tv):
    """Description courte d'une fréquence : canal TV + attribution la plus précise."""
    parts = []
    for (a, b, lab, cat, note) in tv:
        if a <= f < b:
            parts.append(lab if cat != "tv_off" else lab + " (ex-TV)")
            break
    hits = [e for e in plan if e[0] <= f < e[1]]
    if hits:
        parts.append(min(hits, key=lambda e: e[1] - e[0])[2])
    return " · ".join(parts)


def spectrum_info(f, plan, tv):
    """(texte court, catégorie) pour une fréquence : canal TV + attribution la plus précise."""
    parts, cat = [], None
    for (a, b, lab, c, note) in tv:
        if a <= f < b:
            parts.append(lab if c != "tv_off" else lab + " (ex-TV)")
            cat = c
            break
    hits = [e for e in plan if e[0] <= f < e[1]]
    if hits:
        e = min(hits, key=lambda e: e[1] - e[0])
        parts.append(e[2])
        cat = e[3]
    return " · ".join(parts), cat


def describe_freq(f, plan, tv):
    """Phrase complète pour l'affichage au survol."""
    out = [f"{f:.3f} MHz"]
    for (a, b, lab, c, note) in tv:
        if a <= f < b:
            out.append(note or lab)
            break
    hits = [e for e in plan if e[0] <= f < e[1]]
    if hits:
        a, b, lab, c, note = min(hits, key=lambda e: e[1] - e[0])
        s = f"{CATEGORIES[c][0]} : {lab} ({a:g}–{b:g} MHz)"
        if note:
            s += f" — {note}"
        out.append(s)
    else:
        out.append("aucune attribution dans le plan chargé")
    return "   |   ".join(out)


# ----------------------------------------------------------------- mesures
def level_at(F, L, f, win, near=0.25):
    """Niveau max dans ±win MHz autour de f (F trié) ; sinon le point le plus proche s'il est assez près."""
    if F is None or len(F) == 0:
        return None
    lo = int(np.searchsorted(F, f - win))
    hi = int(np.searchsorted(F, f + win, side="right"))
    if hi > lo:
        return float(L[lo:hi].max())
    j = int(np.searchsorted(F, f))
    c = [k for k in (j - 1, j) if 0 <= k < len(F)]
    if not c:
        return None
    k = min(c, key=lambda k: abs(F[k] - f))
    return float(L[k]) if abs(F[k] - f) <= max(win, near) else None


def level_at_many(F, L, cs, win, near=0.25):
    """level_at pour tout un tableau de fréquences d'un coup (7.60.2 : la coordination testait « occupé ? » point par
    point sur ~45 000 candidates). -> tableau (NaN = pas de mesure)."""
    cs = np.asarray(cs, dtype=float)
    out = np.full(len(cs), np.nan)
    if F is None or len(F) == 0 or not len(cs):
        return out
    F = np.asarray(F, dtype=float)
    L = np.asarray(L, dtype=float)
    lo = np.searchsorted(F, cs - win)
    hi = np.searchsorted(F, cs + win, side="right")
    has = hi > lo
    if has.any():
        L2 = np.append(L, -np.inf)
        idx = np.empty(2 * int(has.sum()), dtype=np.int64)
        idx[0::2], idx[1::2] = lo[has], hi[has]
        out[has] = np.maximum.reduceat(L2, idx)[0::2]
    rest = np.nonzero(~has)[0]
    if len(rest):                                   # sinon le point le plus proche, s'il est assez près
        j = np.searchsorted(F, cs[rest])
        a, b = np.clip(j - 1, 0, len(F) - 1), np.clip(j, 0, len(F) - 1)
        k = np.where(np.abs(F[a] - cs[rest]) <= np.abs(F[b] - cs[rest]), a, b)
        near_ok = np.abs(F[k] - cs[rest]) <= max(win, near)
        out[rest[near_ok]] = L[k[near_ok]]
    return out


def busy_pred(F, L, lim, win):
    """« Occupé » d'après un spectre mesuré : niveau max à ± win ≥ lim. Prédicat c -> bool, avec .vec(tableau) ->
    tableau de bool (rapide : pf_suggest l'utilise sur toutes les candidates d'un coup)."""
    def one(c):
        v = level_at(F, L, c, win)
        return v is not None and v >= lim

    def vec(cs):
        v = level_at_many(F, L, cs, win)
        return np.nan_to_num(v, nan=-np.inf) >= lim
    one.vec = vec
    return one


def level_block(F, L, f, bw, how="median"):
    """Niveau d'un bloc large (Spectera / WMAS : bw MHz centré sur f, F trié). « median » : le porteur large
    est-il là (niveau de son plateau) ; « max » : le moindre signal dans le bloc. None si trop peu de points."""
    if F is None or len(F) == 0 or not bw or bw <= 0:
        return None
    lo = int(np.searchsorted(F, f - bw / 2.0))
    hi = int(np.searchsorted(F, f + bw / 2.0, side="right"))
    if hi - lo < 3:
        return None
    seg = L[lo:hi]
    return float(np.median(seg)) if how == "median" else float(seg.max())


def block_choices(tv):
    """Canaux TV proposés pour un bloc Spectera / WMAS : [(libellé, centre MHz, largeur MHz)] (UHF 470–698)."""
    out = []
    for a, b, lab, _cat, _note in tv:
        if 470 <= a and b <= 698 and (b - a) in (6, 8):
            out.append((f"{lab} — {a:g}–{b:g} MHz", (a + b) / 2.0, float(b - a)))
    return out


def block_overlaps(items, guard=0.0):
    """Fréquences qui tombent dans un bloc large (ou blocs qui se chevauchent) : conflit de plan.
    items : [(nom, fréquence, largeur)] -> {index: nom du bloc gênant}. guard : marge en MHz autour des blocs."""
    out = {}
    blocks = [(i, n, f - bw / 2.0 - guard, f + bw / 2.0 + guard) for i, (n, f, bw) in enumerate(items) if bw]
    for i, (n, f, bw) in enumerate(items):
        lo, hi = (f - bw / 2.0, f + bw / 2.0) if bw else (f, f)
        for j, bn, a, b in blocks:
            if j != i and lo < b and hi > a:
                out.setdefault(i, bn)
    return out


def block_points(f, bw, step=1.0):
    """Points répartis sur un bloc (pour que le scan ciblé et « Bandes depuis la liste » le couvrent en entier)."""
    if not bw or bw <= 0:
        return [f]
    n = max(2, int(math.ceil(bw / step)) + 1)
    return [f - bw / 2.0 + bw * k / (n - 1) for k in range(n)]


def eff_thresholds(own_thr, ref_lvl, rel_on, margin, gthr, gweak, auto_floor=None, auto_m=(10.0, 4.0)):
    """Seuils (occupé, faible) : seuil propre > référence + marge > auto (bruit de fond + marges) > seuil global."""
    if own_thr is not None:
        return own_thr, own_thr - (gthr - gweak)
    if rel_on and ref_lvl is not None:
        return ref_lvl + margin, ref_lvl + margin / 2.0
    if auto_floor is not None:
        return auto_floor + auto_m[0], auto_floor + auto_m[1]
    return gthr, gweak


AUTO_THR_DEFAULT = (12.0, 6.0)                  # seuils auto : occupé = bruit + 12 dB, faible = bruit + 6 dB
AUTO_RISE_S, AUTO_FALL_S = 600.0, 5.0           # le bruit appris monte lentement (10 min), redescend vite


def floor_track(prev, cur, dt, busy=False, rise=AUTO_RISE_S, fall=AUTO_FALL_S):
    """Bruit de fond appris (seuils auto) : suit vite une baisse, lentement une hausse, et NE MONTE PAS tant que la
    fréquence est occupée (sinon un brouilleur large finirait par relever son propre seuil et l'alarme s'éteindrait).
    Marche sur des nombres ou des tableaux numpy (NaN = pas de mesure). -> nouvelle valeur."""
    if cur is None:
        return prev
    if prev is None:
        return cur
    p, c = np.asarray(prev, dtype=float), np.asarray(cur, dtype=float)
    if p.shape != c.shape:
        return cur
    dt = max(0.0, float(dt))
    up = c > p
    a = np.where(up, 1.0 - math.exp(-dt / rise), 1.0 - math.exp(-dt / fall))
    if busy is True:
        a = np.where(up, 0.0, a)
    elif busy is not False:
        a = np.where(up & np.asarray(busy, dtype=bool), 0.0, a)
    out = np.where(np.isfinite(p), p + (c - p) * a, c)
    out = np.where(np.isfinite(c), out, p)
    return float(out) if out.ndim == 0 else out


def speed_table(by):
    """7.57.1 : vitesse réelle du tinySA par réglage {(rbw, pas kHz, lna): [points, secondes]} -> lignes du 🩺."""
    if not by:
        return ""
    rows = []
    for (rbw, stp, lna), (n, t) in sorted(by.items(), key=lambda kv: (float(kv[0][0] or 0), kv[0][1], kv[0][2])):
        if n and t > 0:
            rbw_t = "auto" if rbw in (None, 0, "0", "auto") else f"{rbw} kHz"
            rows.append(f"\n    RBW {rbw_t} · pas {stp} kHz · LNA {'oui' if lna else 'non'} : {n / t:.0f} points/s "
                        f"({1000.0 * t / n:.2f} ms par point, {n} points mesurés)")
    return ("\n  Vitesse par réglage :" + "".join(rows)) if rows else ""


def density_raster(traces, x0, x1, y0, y1, W, H, weights=None):
    """Rémanence façon analyseur numérique (7.55) : densité des anciens balayages sur une grille de W × H pixels.
    traces = [(x, y)] du plus récent au plus ancien (NaN = coupure entre bandes) ; weights = poids de chacun (défaut 1).
    Chaque trace est tracée comme une ligne brisée continue : dans chaque colonne, de son minimum à son maximum sur
    l'intervalle de la colonne (extrémités interpolées + points du balayage) -> aucun trou sur un pic raide.
    Renvoie un tableau (W, H) float32 entre 0 et 1 (1 = touché par tous les balayages), colonne 0 = x0, ligne 0 = y0."""
    W, H = int(W), int(H)
    out = np.zeros((W, H + 1), dtype=np.float64)
    if W < 2 or H < 2 or not traces or not (x1 > x0) or not (y1 > y0):
        return np.zeros((max(W, 1), max(H, 1)), dtype=np.float32)
    weights = list(weights) if weights is not None else [1.0] * len(traces)
    tot = float(sum(weights[:len(traces)])) or 1.0
    bounds = x0 + (x1 - x0) * np.arange(W + 1) / W
    sx, sy = W / (x1 - x0), H / (y1 - y0)
    for (x, y), w in zip(traces, weights):
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        if len(x) < 2:
            continue
        bad = ~(np.isfinite(x) & np.isfinite(y))
        cuts = np.flatnonzero(bad)
        starts = np.concatenate(([0], cuts + 1))
        ends = np.concatenate((cuts, [len(x)]))
        for a, b in zip(starts, ends):
            if b - a < 1:
                continue
            xs, ys = x[a:b], y[a:b]
            if xs[0] > xs[-1]:
                xs, ys = xs[::-1], ys[::-1]
            if xs[-1] < x0 or xs[0] > x1:
                continue
            c0 = int(max(0, np.floor((xs[0] - x0) * sx)))
            c1 = int(min(W - 1, np.floor((xs[-1] - x0) * sx)))
            if c1 < c0:
                continue
            bl = np.clip(bounds[c0:c1 + 2], xs[0], xs[-1])
            vb = np.interp(bl, xs, ys)
            lo = np.minimum(vb[:-1], vb[1:])
            hi = np.maximum(vb[:-1], vb[1:])
            # points du balayage à l'intérieur des colonnes (pics plus fins qu'une colonne)
            pc = np.floor((xs - x0) * sx).astype(int)
            ok = (pc >= c0) & (pc <= c1)
            if ok.any():
                np.minimum.at(lo, pc[ok] - c0, ys[ok])
                np.maximum.at(hi, pc[ok] - c0, ys[ok])
            r0 = np.floor((lo - y0) * sy).astype(int)
            r1 = np.floor((hi - y0) * sy).astype(int)
            vis = (r1 >= 0) & (r0 <= H - 1)
            if not vis.any():
                continue
            cols = np.arange(c0, c1 + 1)[vis]
            np.add.at(out, (cols, np.clip(r0[vis], 0, H - 1)), w)
            np.add.at(out, (cols, np.clip(r1[vis], 0, H - 1) + 1), -w)
    return (np.cumsum(out, axis=1)[:, :H] / tot).clip(0.0, 1.0).astype(np.float32)


def density_glow(a, k=0.35):
    """Léger halo du phosphore sur l'image de densité : chaque pixel déborde d'un pixel autour (part k), borné à 1."""
    a = np.asarray(a, dtype=np.float32)
    if a.ndim != 2 or min(a.shape) < 3:
        return a
    g = a.copy()
    g[:, 1:] += k * a[:, :-1]
    g[:, :-1] += k * a[:, 1:]
    g[1:, :] += 0.6 * k * a[:-1, :]
    g[:-1, :] += 0.6 * k * a[1:, :]
    return np.clip(g, 0.0, 1.0)


def density_lut(color, gamma=0.45, alpha_max=235):
    """Table de couleurs RGBA (256 × 4) de la rémanence : la couleur de la trace, de transparente (jamais touché) à
    presque opaque (touché à chaque balayage) ; gamma < 1 = les passages rares restent visibles."""
    c = str(color).lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    k = (np.arange(256) / 255.0) ** gamma
    lut = np.zeros((256, 4), dtype=np.uint8)
    lut[:, 0], lut[:, 1], lut[:, 2] = r, g, b
    lut[:, 3] = np.round(alpha_max * k).astype(np.uint8)
    lut[0, 3] = 0
    return lut


def floor_curve(F, L, win=2.0, step=0.5, q=20.0):
    """Courbe du bruit de fond le long du spectre (seuil auto dessiné) : q-ième centile à ± win MHz, tous les step MHz.
    Trous du balayage (plus de 4 × le pas) = NaN. -> (Fc, Lc) ou (None, None)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    ok = np.isfinite(F) & np.isfinite(L)
    F, L = F[ok], L[ok]
    if len(F) < 5:
        return None, None
    o = np.argsort(F)
    F, L = F[o], L[o]
    c = np.arange(F[0], F[-1] + step / 2.0, step)
    lo = np.searchsorted(F, c - win)
    hi = np.searchsorted(F, c + win, side="right")
    near = np.searchsorted(F, c).clip(1, len(F) - 1)
    d = np.minimum(np.abs(F[near] - c), np.abs(F[near - 1] - c))
    st = float(np.median(np.diff(F))) if len(F) > 1 else step
    out = np.full(len(c), np.nan)
    ok = ((hi - lo) >= 5) & (d <= max(step, 4 * st))
    if ok.any():
        # 7.56 : toutes les fenêtres d'un coup (avant : une boucle Python + un centile par fenêtre, ≈ 3 % de processeur)
        lo_, n_ = lo[ok], (hi - lo)[ok]
        idx = lo_[:, None] + np.arange(int(n_.max()))[None, :]
        inside = idx < (lo_ + n_)[:, None]
        vals = np.sort(np.where(inside, L[np.minimum(idx, len(L) - 1)], np.inf), axis=1)   # les « trous » à la fin
        k = (n_ - 1) * (q / 100.0)                       # centile « linéaire », comme np.percentile
        k0 = np.floor(k).astype(int)
        k1 = np.minimum(k0 + 1, n_ - 1)
        r = np.arange(len(n_))
        a0, a1 = vals[r, k0], vals[r, k1]
        out[ok] = a0 + (a1 - a0) * (k - k0)
    return c, out


class OccWindow:
    """Taux d'occupation sur une fenêtre glissante (seaux d'une minute, pondérés par le temps)."""

    def __init__(self, minutes=60):
        self.minutes = minutes
        self.b = deque()

    def add(self, now, dt, occ):
        if dt <= 0:
            return
        m = int(now // 60)
        if self.b and self.b[-1][0] == m:
            self.b[-1][2] += dt
            if occ:
                self.b[-1][1] += dt
        else:
            self.b.append([m, dt if occ else 0.0, dt])
        while self.b and self.b[0][0] <= m - self.minutes:
            self.b.popleft()

    def pct(self, now=None):
        if now is not None:
            m = int(now // 60)
            while self.b and self.b[0][0] <= m - self.minutes:
                self.b.popleft()
        tot = sum(x[2] for x in self.b)
        if tot < 1.0:
            return None
        return 100.0 * sum(x[1] for x in self.b) / tot

    def clear(self):
        self.b.clear()


# ------------------------------------------------------------ export du scan
UNIT_DIV = {"Hz": 1e-6, "kHz": 1e-3, "MHz": 1.0}    # facteur pour convertir MHz -> unité = 1 / valeur
DELIMS = {"; (point-virgule)": ";", ", (virgule)": ",", "Tabulation": "\t"}


def scan_csv(freqs_mhz, columns, unit="MHz", delim=";", dec=",", header=True, col_names=None):
    """Texte CSV d'un scan. `columns` : liste de tableaux de niveaux (dBm) de même longueur que freqs_mhz."""
    div = UNIT_DIV.get(unit, 1.0)
    nd = {"Hz": 0, "kHz": 3, "MHz": 6}.get(unit, 6)
    names = col_names or [f"Niveau {i + 1} (dBm)" for i in range(len(columns))]
    out = []
    if header:
        out.append(delim.join([f"Frequence ({unit})"] + list(names)))

    def fmt(v, n):
        s = f"{v:.{n}f}"
        return s.replace(".", ",") if dec == "," else s

    for i, fm in enumerate(freqs_mhz):
        row = [fmt(float(fm) / div, nd)]
        for c in columns:
            row.append(fmt(float(c[i]), 1))
        out.append(delim.join(row))
    return "\r\n".join(out) + "\r\n"
# ------------------------------------------------- scènes / groupes / focus
GROUP_COLORS = ["#38bdf8", "#f472b6", "#a3e635", "#fbbf24", "#c084fc", "#2dd4bf", "#fb923c", "#60a5fa",
                "#f87171", "#34d399"]
SEP = "\x1f"
DEFAULT_SCENE = "Scène 1"


def key_enc(scene, group=None):
    """Clé texte d'un noeud scène / groupe (stockable dans un widget Qt sans conversion)."""
    return "S" + SEP + scene if group is None else "G" + SEP + scene + SEP + group


def key_dec(s):
    p = str(s).split(SEP)
    if p[0] == "S" and len(p) == 2:
        return (p[1], None)
    if p[0] == "G" and len(p) == 3:
        return (p[1], p[2])
    return None


SIGNAL_LABELS = (     # clé, situation (pour la fenêtre « Mots affichés »), texte par défaut
    ("ok", "Doit émettre : signal reçu", "OK"),
    ("ok_weak", "Doit émettre : signal faible", "OK (faible)"),
    ("silent", "Doit émettre : plus de signal (avant ABSENT)", "muet"),
    ("absent", "Doit émettre : silencieux trop longtemps", "⚠ ABSENT"),
    ("conflict", "Doit rester libre : un signal est là", "⚠ CONFLIT"),
    ("intermod", "Doit rester libre : le signal est un produit d'intermod de tes émetteurs", "⚠ INTERMOD"),
    ("free_weak", "Doit rester libre : signal faible", "signal faible"),
    ("free_ok", "Doit rester libre : rien", "✔ libre"),
    ("occ", "Sans statut : occupé (pas de place ici)", "OCCUPÉ"),
    ("weak", "Sans statut : faible", "faible"),
    ("free", "Sans statut : libre", "libre"),
)
SIGNAL_DEFAULTS = {k: t for k, _s, t in SIGNAL_LABELS}
SIGNAL_TONES = {"ok": "ok", "ok_weak": "warn", "silent": "warn", "absent": "bad", "conflict": "bad", "intermod": "bad",
                "free_weak": "warn", "free_ok": "free", "occ": "bad", "weak": "warn", "free": "free"}
LIBRE_COLOR = "#3b82f6"          # couleur par défaut de « libre » (bleu), distincte du vert « OK »


def clean_colors(d):
    """{clé de SIGNAL_LABELS: "#rrggbb"} valides seulement (config relue, saisie)."""
    d = d if isinstance(d, dict) else {}
    return {k: str(v).lower() for k, v in d.items() if k in SIGNAL_DEFAULTS and re.fullmatch(r"#[0-9a-fA-F]{6}", str(v))}


def signal_key(state, keep_free=False, keep_on=False, absent=False, intermod=False):
    """Situation du signal POUR CETTE fréquence -> (clé de SIGNAL_LABELS ou None, ton : ok | free | bad | warn | none).
    ok = mon émetteur est bien là ; free = rien sur la fréquence (libre) : deux couleurs différentes.
    « Doit émettre » : signal = OK, c'est bien notre émetteur (vert) ; « doit rester libre » : signal = conflit
    (rouge), INTERMOD s'il s'explique par tes émetteurs ; sans statut : occupé = pas de place ici (rouge)."""
    if keep_on:
        if absent:
            return "absent", "bad"
        return {"occ": ("ok", "ok"), "weak": ("ok_weak", "warn"), "free": ("silent", "warn")}.get(state, (None, "none"))
    if keep_free:
        if state == "occ":
            return ("intermod" if intermod else "conflict"), "bad"
        return {"weak": ("free_weak", "warn"), "free": ("free_ok", "free")}.get(state, (None, "none"))
    return {"occ": ("occ", "bad"), "weak": ("weak", "warn"), "free": ("free", "free")}.get(state, (None, "none"))


def signal_view(state, keep_free=False, keep_on=False, absent=False, intermod=False, labels=None):
    """-> (texte affiché, ton). labels : tes mots (clé -> texte), sinon les mots par défaut."""
    key, tone = signal_key(state, keep_free, keep_on, absent, intermod)
    if key is None:
        return "—", tone
    txt = (labels or {}).get(key) or SIGNAL_DEFAULTS[key]
    return txt, tone


LEVEL_UNITS = (("dbm", "dBm"), ("dbuv", "dBµV (50 Ω)"), ("pct", "% (comme WSM)"),
               ("dbw", "dBW"), ("dbuw", "dBµW"))                      # 8.1 : dBW, dBµW
UNIT_SUFFIX = {"dbm": "dBm", "dbuv": "dBµV", "pct": "%", "dbw": "dBW", "dbuw": "dBµW"}


def to_unit(dbm, unit):
    """Niveau dBm -> unité d'affichage. dBµV = dBm + 107 (50 Ω) ; % = échelle WSM (0 % = −120 dBm, 100 % = 0 dBm)."""
    if dbm is None:
        return None
    if unit == "dbuv":
        return dbm + 107.0
    if unit == "pct":
        return min(100.0, max(0.0, (dbm + 120.0) * 100.0 / 120.0))
    if unit == "dbw":
        return dbm - 30.0
    if unit == "dbuw":
        return dbm + 30.0
    return dbm


def from_unit(v, unit):
    """Unité d'affichage -> dBm (inverse de to_unit)."""
    if v is None:
        return None
    if unit == "dbuv":
        return v - 107.0
    if unit == "pct":
        return v * 120.0 / 100.0 - 120.0
    if unit == "dbw":
        return v + 30.0
    if unit == "dbuw":
        return v - 30.0
    return v


def fmt_level(dbm, unit, nd=1, suffix=False):
    """Texte d'un niveau dans l'unité choisie ("—" si inconnu)."""
    if dbm is None:
        return "—"
    v = to_unit(dbm, unit)
    nd = 0 if unit == "pct" else nd
    return f"{v:.{nd}f}" + (f" {UNIT_SUFFIX.get(unit, 'dBm')}" if suffix else "")


def strong_peaks(F, L, thr, merge=1.0, limit=6):
    """Signaux plus forts que thr (dBm) : [(MHz, dBm)] du plus fort au plus faible, un seul par zone de merge MHz."""
    if F is None or len(F) == 0:
        return []
    idx = np.nonzero(np.asarray(L) > thr)[0]
    out = []
    for i in sorted(idx, key=lambda k: -L[k]):
        f = float(F[i])
        if all(abs(f - g) > merge for g, _ in out):
            out.append((f, float(L[i])))
            if len(out) >= limit:
                break
    return out


MK_STATES = (("occ", "Occupées"), ("weak", "Faibles"), ("free", "Libres"), ("none", "Sans mesure"))


def mk_default():
    """Réglage des repères du spectre : tout afficher."""
    return dict(on=True, states=[k for k, _ in MK_STATES], hide_layers=[], hide_status=[], alarms=True,
                unk=True, style="full")


def wall_visible(w, in_scope=True, alarm=False, only_active=False, alarms_always=True):
    """La fréquence w a-t-elle sa tuile sur le mur ? (couche active, retirée à la main, « occupées seulement »,
    une alarme la ramène si demandé)."""
    if not in_scope:
        return False
    if alarm and alarms_always:
        return True
    if w.get("hide_wall"):
        return False
    return not only_active or w.get("state") in ("occ", "weak")


WALL_SIZES = [("auto", "Taille auto"), ("s", "Petites"), ("m", "Moyennes"), ("l", "Grandes")]
WALL_TILE = {"s": (150, 64, 11), "m": (210, 90, 15), "l": (300, 128, 22)}   # largeur mini, hauteur, police (px)


def wall_grid(n, W, H, size="auto", gap=6):
    """Grille du mur : (colonnes, rangées, hauteur de tuile ou 0 si elle s'étire, police px).
    auto = les tuiles remplissent la place ; s / m / l = taille fixe, autant de colonnes que la largeur en
    permet, et on fait défiler s'il y en a trop."""
    W, H = max(100, W), max(60, H)
    if n <= 0:
        return 1, 0, 0, 14
    if size in WALL_TILE:
        tw, th, fs = WALL_TILE[size]
        cols = max(1, min(n, int((W + gap) // (tw + gap))))
        return cols, int(math.ceil(n / cols)), th, fs
    cols = max(1, min(n, int(math.ceil(math.sqrt(n * W / H / 1.5)))))
    rows = int(math.ceil(n / cols))
    tw, th = W / cols, H / rows
    return cols, rows, 0, int(max(8, min(36, th * 0.16, tw / 9.5)))


# ---------------------------------------------------------------- appel des micros (line check)
LC_TEXT = {None: "⏳ en attente", "ok": "✓ OK", "weak": "✓ faible", "manual": "✓ à la main", "skip": "⏭ ignorée"}


def lc_new(items):
    """Appel des micros : items = [(clé, nom, MHz, couche)] -> {clé: entrée}. res : None (attendue), ok, weak
    (vue mais faible), manual (validée à la main), skip (ignorée : spare, pack absent du show…)."""
    return {k: dict(name=n, freq=f, layer=ly, res=None, t=None, lvl=None) for k, n, f, ly in items}


def lc_feed(lc, key, state, level, now):
    """Un balayage : True si l'entrée vient d'être validée (ou de passer de faible à OK)."""
    e = lc.get(key)
    if e is None or state not in ("occ", "weak") or level is None:
        return False
    if e["res"] in ("ok", "weak"):
        e["lvl"] = max(e["lvl"], level) if e["lvl"] is not None else level
    if e["res"] is None or (e["res"] == "weak" and state == "occ"):
        e["res"] = "ok" if state == "occ" else "weak"
        e["t"], e["lvl"] = now, level if e["lvl"] is None else max(e["lvl"], level)
        return True
    return False


def lc_summary(lc):
    """-> dict(n, ok, weak, missing [noms], skipped, done, text)."""
    es = sorted(lc.values(), key=lambda e: e["freq"])
    n = sum(1 for e in es if e["res"] != "skip")
    ok = sum(1 for e in es if e["res"] in ("ok", "manual"))
    weak = sum(1 for e in es if e["res"] == "weak")
    miss = [e["name"] or f"{e['freq']:.3f}" for e in es if e["res"] is None]
    skipped = sum(1 for e in es if e["res"] == "skip")
    wk = (f" (dont {weak} faibles)" if weak > 1 else f" (dont {weak} faible)") if weak else ""   # mots entiers : traduisibles
    if not n:
        text = "Rien à appeler"
    elif not miss:
        text = f"Tout est là ✓ ({ok + weak} / {n})" + wk
    else:
        text = (f"{ok + weak} / {n} OK" + wk + (" · manquent : " if len(miss) > 1 else " · manque : ")
                + ", ".join(miss[:8]) + (f" … (+{len(miss) - 8})" if len(miss) > 8 else ""))
    if skipped:
        text += f" · {skipped} ignorée(s)"
    return dict(n=n, ok=ok, weak=weak, missing=miss, skipped=skipped, done=bool(n) and not miss, text=text)


def lc_hints(lc, unknown, span=3.0):
    """Pour chaque fréquence encore attendue : un signal inconnu tout près ? (pack réglé sur le mauvais canal).
    unknown = [MHz] -> [(nom, MHz attendue, MHz vue)]."""
    out = []
    for e in sorted(lc.values(), key=lambda e: e["freq"]):
        if e["res"] is not None or not unknown:
            continue
        u = min(unknown, key=lambda x: abs(x - e["freq"]))
        if abs(u - e["freq"]) <= span:
            out.append((e["name"] or f"{e['freq']:.3f}", e["freq"], u))
    return out


def lc_text(lc, title="", when="", fmt=None):
    """Résumé à copier (WhatsApp, mail à la régie…). fmt(niveau) -> texte du niveau."""
    fmt = fmt or (lambda v: f"{v:.0f} dBm")
    sm = lc_summary(lc)
    lines = [f"Appel des micros{' — ' + title if title else ''}{' · ' + when if when else ''}", sm["text"], ""]
    for e in sorted(lc.values(), key=lambda e: e["freq"]):
        mark = {"ok": "✓", "weak": "~", "manual": "✓", "skip": "–"}.get(e["res"], "✗")
        extra = (f" · {fmt(e['lvl'])}" if e["lvl"] is not None else "") + (" (faible)" if e["res"] == "weak" else "") \
            + (" (à la main)" if e["res"] == "manual" else "") + (" (ignorée)" if e["res"] == "skip" else "")
        lines.append(f"{mark} {e['name'] or '—'} · {e['freq']:.3f} MHz{extra}")
    return "\n".join(lines)


def mk_layer_key(scene, group):
    """Clé de couche pour le filtre des repères ("" = fréquence sans scène)."""
    return key_enc(scene, group or "") if scene else ""


def marker_visible(w, mk, alarm=False):
    """Le repère de la fréquence w doit-il être dessiné ? (on/off global, en alarme toujours visible si demandé,
    masquage à la main, état mesuré, statut, couche)."""
    if not mk.get("on", True):
        return False
    if alarm and mk.get("alarms", True):
        return True
    if w.get("hide_mk"):
        return False
    if (w.get("state") or "none") not in mk.get("states", ()):
        return False
    if (w.get("status") or "") in mk.get("hide_status", ()):
        return False
    return mk_layer_key(w.get("scene", ""), w.get("group", "")) not in mk.get("hide_layers", ())


def mk_filtered(mk):
    """Un filtre est-il actif (pour l'afficher sur le bouton) ?"""
    return (set(mk.get("states", ())) != {k for k, _ in MK_STATES} or bool(mk.get("hide_layers"))
            or bool(mk.get("hide_status")))


def scope_match(scope, scene, group):
    """scope : None / [] = global ; sinon liste de (scène, groupe|None)."""
    if not scope:
        return True
    return any(k[0] == scene and (k[1] is None or k[1] == group) for k in scope)


def focus_plan(freqs, pts_cap, step_khz=20.0, gap=4.0, margin=0.3, min_pts=101, fmin=0.1, fmax=6000.0):
    """Bandes de balayage minimales couvrant une liste de fréquences : [(début, fin, nb de points)]."""
    fs = sorted(f for f in freqs if f is not None and fmin <= f <= fmax)
    if not fs:
        return []
    groups, cur = [], [fs[0]]
    for f in fs[1:]:
        if f - cur[-1] <= gap:
            cur.append(f)
        else:
            groups.append(cur)
            cur = [f]
    groups.append(cur)
    out = []
    for g in groups:
        a, b = max(fmin, g[0] - margin), min(fmax, g[-1] + margin)
        if b - a < 0.05:
            mid = (a + b) / 2.0
            a, b = max(fmin, mid - 0.025), min(fmax, mid + 0.025)
        n = int(math.ceil((b - a) * 1000.0 / step_khz)) + 1
        n = min(max(min_pts, n), max(min_pts, int(pts_cap)))
        out.append((round(a, 6), round(b, 6), n))
    return out


# ------------------------------------------------- intermodulation
IM_MAX_PAIRS = 40_000_000       # au-delà, le calcul est refusé (trop long)
IM_CHUNK = 1_500_000
IM_NAMES = {3: "IM3", 5: "IM5", 7: "IM7"}
# Règles d'intermod : tolérance (MHz) par type de produit ; un produit plus loin que ça de la porteuse est accepté,
# 0 = type ignoré. 100 / 50 kHz = défauts des guides du logiciel de coord (2 TX / 3 TX) ; 5ᵉ ordre : notre choix.
# Le 1er réglage (Standard : 2 TX 100 / 3 TX 50 kHz) est celui par défaut ; avec le FILTRE du récepteur
# (32 MHz pour un Wisycom MRK980), un plan Wisycom réel de Clément donne 0 IM.
IM_TOL_PRESETS = [
    ("🟢 Standard (2 TX ±100 · 3 TX ±50 kHz)", {"2tx3": 0.100, "3tx3": 0.050, "5": 0.0, "7": 0.0},
     "Les tolérances les plus courantes en coordination : produits à 2 émetteurs (2A − B) à ±100 kHz et à "
     "3 émetteurs (A + B − C) à ±50 kHz, avec le filtre du récepteur."),
    ("⚪ Simple : 2A − B seulement", {"2tx3": 0.100, "3tx3": 0.0, "5": 0.0, "7": 0.0},
     "Seulement les produits à 2 émetteurs (2A − B), les plus forts, à ±100 kHz. Le contrôle minimum."),
    ("🟠 Prudent : + 5ᵉ ordre", {"2tx3": 0.100, "3tx3": 0.050, "5": 0.050, "7": 0.0},
     "Ajoute le 5ᵉ ordre (3A − 2B, 2A + B − 2C…), encore plus faible. Pour un plan très serré ou du matériel "
     "sensible."),
    ("🔴 Très prudent : marges doublées", {"2tx3": 0.200, "3tx3": 0.100, "5": 0.100, "7": 0.0},
     "Comme « Prudent », avec des marges doublées (200 / 100 / 100 kHz)."),
]
IM_TOL_CUSTOM = "✏ Personnalisé"


def im_rules_text(tol, sep_mhz=None, filt=0.0):
    """Phrase « ce qui est vérifié » pour des tolérances (et un écart mini entre porteuses, un filtre)."""
    def one(k, lab):
        v = tol.get(k, 0.0)
        return f"{lab} à moins de {v * 1000:.0f} kHz d'une fréquence" if v > 0 else f"{lab} : non vérifié"
    parts = ([f"écart d'au moins {sep_mhz * 1000:.0f} kHz entre deux porteuses"] if sep_mhz is not None else [])
    parts += [one("2tx3", "2A − B (2 émetteurs)"), one("3tx3", "A + B − C (3 émetteurs)"), one("5", "5ᵉ ordre")]
    if filt and filt > 0:
        parts.append(f"seuls comptent les émetteurs à ±{filt:g} MHz de la fréquence touchée (filtre {filt:g} MHz)")
    return "On vérifie : " + " · ".join(parts)


def im_class(order, ntx):
    """Type de produit pour les tolérances : 2tx3 (2A − B), 3tx3 (A + B − C), puis "5", "7"…"""
    return ("2tx3" if ntx <= 2 else "3tx3") if order == 3 else str(order)


def im_pairs(n, order, max_tx=None):
    """Nombre de couples (groupe +, groupe −) à examiner pour n émetteurs et un ordre impair.
    Avec max_tx ≤ 2 (produits du type 2A−B), seuls les couples ordonnés d'émetteurs comptent."""
    if max_tx is not None and max_tx <= 2:
        return n * (n - 1)
    p = (order + 1) // 2
    q = order - p
    return math.comb(n + p - 1, p) * math.comb(n + q - 1, q)


def im_scan(freqs, orders=(3,), max_tx=3, targets=None, guard=0.2, fmin=0.1, fmax=6000.0, limit=20000,
            bws=None, tbws=None):
    """Produits d'intermodulation d'une liste d'émetteurs (MHz).

    Un produit d'ordre n vaut (somme de p fréquences) − (somme de q fréquences), avec p = q + 1 et p + q = n
    (on ne garde que ceux qui retombent dans la même bande). Un émetteur n'est jamais dans les deux
    groupes (il s'annulerait). max_tx = nombre maximal d'émetteurs DIFFÉRENTS impliqués :
    2 -> 2A−B ; 3 -> A+B−C ; 5 -> A+B+C−D−E…
    targets : fréquences à protéger. Si fourni, on ne garde que les produits qui tombent à moins de `guard`
    MHz de l'une d'elles (hors émetteurs impliqués dans le produit lui-même).
    bws / tbws : largeur (MHz) de chaque émetteur / cible, 0 = fréquence simple. Blocs larges (Spectera, WMAS) :
    a·A − b·B s'étale sur ± (a·largeur A + b·largeur B) / 2 autour de son centre ; « tombe sur » une cible quand
    cette bande arrive à moins de guard du bord de la cible.
    guard : tolérance (MHz), ou dict par type de produit (im_class : {"2tx3": 0.1, "3tx3": 0.05, "5": 0.05}) ;
    dans le dict, 0 = type ignoré (convention courante des logiciels de coordination).
    -> (rows, info). rows = [dict(f, order, terms, ntx, target, delta, hw, gap)] ; terms = [(indice, coefficient)] ;
    hw = demi-largeur du produit ; gap = écart bord à bord avec la cible (≤ 0 : ça se chevauche)."""
    gd = dict(guard) if isinstance(guard, dict) else None
    guard = max(gd.values()) if gd else float(guard)

    def tol(order, ntx):
        return guard if gd is None else gd.get(im_class(order, ntx), guard)

    def ignored(order, ntx):
        """Tolérance 0 dans le dict = ce type de produit n'est pas compté (comme 0 dans le logiciel de coord)."""
        return gd is not None and tol(order, ntx) <= 0
    F = np.asarray(list(freqs), dtype=float)
    n = len(F)
    info = dict(pairs=0, truncated=False, too_big=False)
    rows = []
    if n < 2:
        return rows, info
    B = np.zeros(n) if bws is None else np.clip(np.asarray(list(bws), dtype=float), 0.0, None)
    T = TB = None
    if targets is not None:
        T = np.asarray(list(targets), dtype=float)
        TB = np.zeros(len(T)) if tbws is None else np.clip(np.asarray(list(tbws), dtype=float), 0.0, None)
        o_ = np.argsort(T, kind="stable")
        T, TB = T[o_], TB[o_]
        if len(T) == 0:
            return rows, info
    wide = bool(B.any()) or (TB is not None and bool(TB.any()))
    # pré-filtre élargi (les produits de blocs sont larges), puis test exact bord à bord
    g_pre = guard + ((max(orders) * float(B.max()) / 2.0 + float(TB.max()) / 2.0) if wide and TB is not None else 0.0)

    def near_t(vals, hw, inv):
        """Cible la plus proche (bord à bord) qui n'est PAS un des émetteurs du produit (inv : leurs fréquences,
        une ligne par produit) -> (indice, écart bord à bord ; inf si aucune). Fréquences simples : les 2 voisines
        suffisent ; blocs larges : un produit large peut en recouvrir plusieurs → toutes les cibles sont regardées."""
        if not wide:
            k = np.searchsorted(T, vals)
            ilo, ihi = np.clip(k - 1, 0, len(T) - 1), np.clip(k, 0, len(T) - 1)
            gl = np.abs(T[ilo] - vals) - TB[ilo] / 2.0
            gh = np.abs(T[ihi] - vals) - TB[ihi] / 2.0
            gl = np.where((np.abs(inv - T[ilo][:, None]) < 1e-6).any(axis=1), np.inf, gl)
            gh = np.where((np.abs(inv - T[ihi][:, None]) < 1e-6).any(axis=1), np.inf, gh)
            return np.where(gh < gl, ihi, ilo), np.minimum(gl, gh) - hw
        ti, gg = np.zeros(len(vals), dtype=int), np.full(len(vals), np.inf)
        for a in range(0, len(vals), 4000):
            v, h, iv = vals[a:a + 4000], hw[a:a + 4000], inv[a:a + 4000]
            G = np.abs(v[:, None] - T[None, :]) - TB[None, :] / 2.0 - h[:, None]
            G = np.where((np.abs(iv[:, :, None] - T[None, None, :]) < 1e-6).any(axis=1), np.inf, G)
            k = np.argmin(G, axis=1)
            ti[a:a + 4000], gg[a:a + 4000] = k, G[np.arange(len(v)), k]
        return ti, gg
    total = sum(im_pairs(n, o, max_tx) for o in orders)
    info["pairs"] = total
    if total > IM_MAX_PAIRS:
        info["too_big"] = True
        return rows, info
    cap = max(limit * 3, 3000)
    if max_tx <= 2:
        # 2 émetteurs seulement : a·A − b·B avec a − b = 1 (2A−B, 3A−2B, 4A−3B), une paire ordonnée à la fois
        ii, jj = np.nonzero(~np.eye(n, dtype=bool))
        for order in orders:
            a = (order + 1) // 2
            b = order - a
            vals = a * F[ii] - b * F[jj]
            hw = (a * B[ii] + b * B[jj]) / 2.0
            msk = (vals >= fmin) & (vals <= fmax)
            tv = gap = None
            if T is not None:
                ti, gap = near_t(vals, hw, np.stack([F[ii], F[jj]], axis=1))
                tv = T[ti]
                msk &= (gap <= tol(order, 2)) & (not ignored(order, 2))
            hits = np.nonzero(msk)[0]
            if len(hits) > cap:
                info["truncated"] = True
                hits = hits[:cap]
            for h in hits:
                rows.append(dict(f=float(vals[h]), order=order, ntx=2,
                                 terms=[(int(ii[h]), a), (int(jj[h]), -b)],
                                 target=None if tv is None else float(tv[h]),
                                 delta=None if tv is None else float(vals[h] - tv[h]),
                                 hw=float(hw[h]), gap=None if gap is None else float(gap[h])))
        if T is not None:
            rows.sort(key=lambda r: (r["order"], r["ntx"], r["gap"], r["f"]))
        else:
            rows.sort(key=lambda r: (r["f"], r["order"]))
        if len(rows) > limit:
            info["truncated"] = True
            rows = rows[:limit]
        return rows, info
    for order in orders:
        p = (order + 1) // 2
        q = order - p
        pos = np.array(list(itertools.combinations_with_replacement(range(n), p)), dtype=np.int32).reshape(-1, p)
        neg = np.array(list(itertools.combinations_with_replacement(range(n), q)), dtype=np.int32).reshape(-1, q)
        P = F[pos].sum(axis=1)
        Q = F[neg].sum(axis=1)
        step_rows = max(1, IM_CHUNK // max(1, len(Q)))
        for a in range(0, len(P), step_rows):
            prod = P[a:a + step_rows, None] - Q[None, :]
            m = (prod >= fmin) & (prod <= fmax)
            if T is not None:
                k = np.searchsorted(T, prod)
                lo = T[np.clip(k - 1, 0, len(T) - 1)]
                hi = T[np.clip(k, 0, len(T) - 1)]
                m &= np.minimum(np.abs(prod - lo), np.abs(prod - hi)) <= g_pre
            ir, jj = np.nonzero(m)
            if not len(ir):
                continue
            pi, qj = pos[ir + a], neg[jj]
            overlap = (pi[:, :, None] == qj[:, None, :]).any(axis=(1, 2))
            allidx = np.concatenate([pi, qj], axis=1)
            srt = np.sort(allidx, axis=1)
            ntx = 1 + (np.diff(srt, axis=1) != 0).sum(axis=1)
            ok = (~overlap) & (ntx <= max_tx)
            vals = prod[ir, jj]
            hw = (B[pi].sum(axis=1) + B[qj].sum(axis=1)) / 2.0
            tv = gap = None
            if T is not None:
                ti, gap = near_t(vals, hw, F[allidx])
                tv = T[ti]
                ok &= gap <= np.where(ntx <= 2, tol(order, 2), tol(order, 3))
                ok &= np.where(ntx <= 2, not ignored(order, 2), not ignored(order, 3))
            for h in np.nonzero(ok)[0]:
                terms = {}
                for t_i in pi[h]:
                    terms[int(t_i)] = terms.get(int(t_i), 0) + 1
                for t_i in qj[h]:
                    terms[int(t_i)] = terms.get(int(t_i), 0) - 1
                rows.append(dict(f=float(vals[h]), order=order, ntx=int(ntx[h]),
                                 terms=sorted(terms.items(), key=lambda kv: (-kv[1], kv[0])),
                                 target=None if tv is None else float(tv[h]),
                                 delta=None if tv is None else float(vals[h] - tv[h]),
                                 hw=float(hw[h]), gap=None if gap is None else float(gap[h])))
            if len(rows) > cap:
                info["truncated"] = True
                break
        if info["truncated"]:
            break
    if T is not None:
        rows.sort(key=lambda r: (r["order"], r["ntx"], r["gap"], r["f"]))
    else:
        rows.sort(key=lambda r: (r["f"], r["order"]))
    if len(rows) > limit:
        info["truncated"] = True
        rows = rows[:limit]
    return rows, info


IM_SEV_TEXT = {3: "🔴 visible sur le spectre", 2: "🟠 à vérifier (énergie)", 1: "🟡 à surveiller (IM3 2 TX)",
               0: "⚪ faible risque (calcul)"}


def im_verdict(meas, thr, weak, weak_on, order, ntx, masked=False):
    """Gravité d'un produit qui tombe sur une de tes fréquences -> (0…3, texte).
    3 rouge : on MESURE au-dessus du seuil « occupé » à cet endroit ; 2 orange : au-dessus du seuil « faible » ;
    1 jaune : rien de mesuré mais c'est un IM3 à 2 émetteurs (2A − B, le produit le plus fort) ;
    0 gris : rien de mesuré, produit plus faible (A + B − C, 5ᵉ / 7ᵉ ordre). Cible en émission : son niveau est
    celui de sa propre porteuse, on ne peut pas mesurer le produit → gravité selon le calcul seulement."""
    if meas is not None and not masked:
        if meas >= thr:
            return 3, IM_SEV_TEXT[3]
        if weak_on and meas >= weak:
            return 2, IM_SEV_TEXT[2]
    sev = 1 if (order == 3 and ntx <= 2) else 0
    txt = IM_SEV_TEXT[sev]
    if masked:
        txt += " · cible émet"
    elif meas is None:
        txt += " (pas de mesure)"
    return sev, txt


def im_formula(terms, names=None, freqs=None, numeric=False):
    """[(indice, coefficient)] -> '2×Chant − Basse' (ou avec les fréquences si numeric)."""
    out = ""
    for k, (i, c) in enumerate(terms):
        lab = f"{freqs[i]:.3f}" if (numeric or not names) else str(names[i])
        a = abs(c)
        s = lab if a == 1 else f"{a}×{lab}"
        if k == 0:
            out = s if c > 0 else "−" + s
        else:
            out += (" + " if c > 0 else " − ") + s
    return out


def im_explain(f, freqs, orders=(3, 5), max_tx=5, tol=0.1, limit=40, bws=None):
    """Quelles combinaisons d'émetteurs peuvent produire un signal à f (MHz) ? bws : largeurs des émetteurs."""
    return im_scan(freqs, orders, max_tx, targets=[f], guard=tol, limit=limit, bws=bws)


# ------------------------------------------------- vérification d'un plan de fréquences
PF_SEP = 0.300          # écart mini par défaut entre deux porteuses (MHz) ; réglable dans la fenêtre


def pf_orders(tol):
    """Ordres à calculer d'après les tolérances (0 = ignoré). Jusqu'au 5ᵉ : le 7ᵉ multiplie les
    combinaisons par ~100 (30 émetteurs : 200 millions) pour des produits très faibles."""
    return tuple(o for o, k in ((3, "2tx3"), (5, "5")) if tol.get(k, 0) > 0 or (o == 3 and tol.get("3tx3", 0) > 0))


# Profils d'appareil (comme dans les logiciels de coordination) : écart mini, filtre d'entrée du récepteur, pas de réglage et
# tolérances d'intermod. src = d'où vient le FILTRE : "eazyrf" (clé de donnée) = valeur des profils du logiciel de coord de Clément (Wisycom
# MRK980 : profil complet ; Sennheiser evolution, Shure SLX / PSM : 16 MHz ; Shure AD / QLX-D : 32 MHz, d'après lui),
# "guess" = valeur de départ NON vérifiée. Écart, pas et tolérances des profils autres que Wisycom : de départ aussi.
# Les clés restent stables (enregistrées dans les listes et les shows : w["rx"]).
_TOL_EZ = {"2tx3": 0.100, "3tx3": 0.050, "5": 0.050, "7": 0.0}      # la plupart des appareils du logiciel de coord
_TOL_LARGE = {"2tx3": 0.150, "3tx3": 0.075, "5": 0.050, "7": 0.0}
_TOL_IEM = {"2tx3": 0.150, "3tx3": 0.100, "5": 0.050, "7": 0.0}     # Shure PSM 1000 dans le logiciel de coord
_TOL_SLXD = {"2tx3": 0.200, "3tx3": 0.0, "5": 0.050, "7": 0.0}      # Shure SLX-D dans le logiciel de coord (3 TX ignoré)
_TOL_NONE = {"2tx3": 0.0, "3tx3": 0.0, "5": 0.0, "7": 0.0}          # Sennheiser EW-D / EW-DX : écart seulement
_EZ = "Réglages de coordination courants pour ce modèle."
RX_PROFILES = [
    ("wisycom", "Wisycom (MRK980, MTK952…) · filtre 32 MHz",
     dict(sep=0.500, filt=32.0, step=0.005, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " MRK980 : écart 500 kHz (250 kHz en NB), filtre 32 MHz, pas 5 kHz ; MTK952 : pas 25 kHz."),
    ("senn_evo", "Sennheiser ew G4 · filtre 32 MHz",
     dict(sep=0.400, filt=32.0, step=0.025, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " ew G4 : écart 400 kHz (450 kHz sur certaines gammes), filtre 32 MHz."),
    ("senn_ana", "Sennheiser analogique (2000, 3000, 5000)",
     dict(sep=0.400, filt=0.0, step=0.025, tol=_TOL_LARGE, src="guess"),
     "Valeurs génériques prudentes : sans filtre, tous les émetteurs comptent. Pour les valeurs exactes de ton "
     "modèle : crée un profil perso."),
    ("senn_dig", "Sennheiser EW-D / EW-DX · filtre 32 MHz",
     dict(sep=0.600, filt=32.0, step=0.025, tol=_TOL_NONE, src="eazyrf"),
     _EZ + " Numérique : pas d'intermodulation comptée, écart 600 kHz."),
    ("shure_ad", "Shure Axient Digital (AD4D / AD4Q) · filtre 32 MHz",
     dict(sep=0.400, filt=32.0, step=0.025, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " Écart 400 kHz, filtre 32 MHz."),
    ("shure_dig", "Shure ULX-D / QLX-D · filtre 16 MHz",
     dict(sep=0.300, filt=16.0, step=0.025, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " Écart 300 kHz, filtre 16 MHz."),
    ("shure_slx", "Shure SLX (analogique) · filtre 16 MHz",
     dict(sep=0.300, filt=16.0, step=0.025, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " Écart 300 kHz, filtre 16 MHz."),
    ("shure_slxd", "Shure SLX-D · filtre 50 MHz",
     dict(sep=0.450, filt=50.0, step=0.025, tol=_TOL_SLXD, src="eazyrf"),
     _EZ + " Écart 450 kHz, filtre 50 MHz, tolérance 2 TX 200 kHz, 3 TX non compté."),
    ("shure_ana", "Shure analogique (UR, BLX…)",
     dict(sep=0.400, filt=0.0, step=0.025, tol=_TOL_LARGE, src="guess"),
     "Valeurs génériques prudentes : sans filtre, tous les émetteurs comptent. Pour les valeurs exactes de ton "
     "modèle : crée un profil perso."),
    ("shure_psm", "Shure PSM 900 · filtre 16 MHz",
     dict(sep=0.300, filt=16.0, step=0.025, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " Écart 300 kHz, filtre 16 MHz."),
    ("shure_psm1000", "Shure PSM 1000 · filtre 16 MHz",
     dict(sep=0.500, filt=16.0, step=0.025, tol=_TOL_IEM, src="eazyrf"),
     _EZ + " Écart 500 kHz, filtre 16 MHz, tolérances 150 / 100 / 50 kHz."),
    ("shure_adt", "Shure Axient Digital PSM (ADTQ / ADTD)",
     dict(sep=0.400, filt=0.0, step=0.025, tol=_TOL_IEM, src="guess"),
     "Valeurs génériques prudentes. Pour les valeurs exactes : crée un profil perso."),
    ("iem", "Sennheiser ew IEM G4 · filtre 32 MHz",
     dict(sep=0.450, filt=32.0, step=0.025, tol=_TOL_EZ, src="eazyrf"),
     _EZ + " Écart 450 kHz, filtre 32 MHz."),
]
RX_CUSTOM = []          # profils perso (config et shows : « rx_custom »), même forme que RX_PROFILES


RX_LIBRARY = []         # bibliothèque d'appareils importée (.lst4) : [{name, type, lo, hi, sep, filt, step, tol}]


def parse_lst4(data):
    """Bibliothèque d'appareils (.lst4) (« Appareils.lst4 », XML) -> [{name, type, lo, hi, sep, filt, step, tol, img}].
    Séparation et tolérances en kHz dans le fichier -> MHz ici ; décimales à virgule ; tolérance 0 = type ignoré."""
    import xml.etree.ElementTree as ET
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    try:
        root = ET.fromstring(raw.lstrip(b"\xef\xbb\xbf"))
    except ET.ParseError as e:
        raise ValueError(f"fichier illisible ({e})") from None
    out = []
    for d in root:
        def g(k):
            return (d.findtext(k) or "").strip()

        def num(k, dft):
            try:
                return float(g(k).replace(",", ".")) if g(k) else dft
            except ValueError:
                return dft
        name = re.sub(r"\s+", " ", g("Description"))[:80]
        if not name:
            continue
        out.append(dict(name=name, type=g("Type")[:30], lo=num("Départ", 0.0), hi=num("Arrêt", 0.0),
                        sep=num("Séparation", 300.0) / 1000.0, filt=num("Filtre", 0.0),
                        step=num("Incrément", 0.025) or 0.025,
                        tol={"2tx3": num("Tolérance", 100.0) / 1000.0, "3tx3": num("Tolérance3TX", 50.0) / 1000.0,
                             "5": num("Tolérance5e", 50.0) / 1000.0, "7": 0.0},
                        img=num("FréqImage", 0.0) if g("FréqImageDéfinie").lower() == "true" else 0.0))
    if not out:
        raise ValueError("aucun appareil dans ce fichier (est-ce bien une bibliothèque .lst4 ?)")
    return out


def rx_library_find(lib, text, limit=400):
    """Recherche dans la bibliothèque : tous les mots tapés (sans accents / casse) dans le nom ou le type."""
    def k(x):
        return "".join(c for c in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(c) != "Mn")
    words = k(text).split()
    hits = [d for d in lib or [] if all(w in k(d["name"] + " " + d["type"]) for w in words)]
    return hits[:limit]


def rx_from_library(dev):
    """Appareil de la bibliothèque -> profil perso (rx_custom_norm), avec sa plage de fréquences."""
    return dict(name=dev["name"], sep=dev["sep"], filt=dev["filt"], step=dev["step"], tol=dict(dev["tol"]),
                lo=dev.get("lo", 0.0), hi=dev.get("hi", 0.0), src="eazyrf", img=float(dev.get("img") or 0.0),
                note=f"Bibliothèque · {dev.get('type', '')} · {dev.get('lo', 0):g}–{dev.get('hi', 0):g} MHz")


def _ez_num(x, dft=0.0):
    try:
        return float(str(x).strip().replace(",", "."))
    except (TypeError, ValueError):
        return dft


def _ez_dev_params(name, g, eval5=True):
    """Réglages d'un appareil d'un document .ezrf3 (mêmes champs que la bibliothèque .lst4)."""
    return dict(name=name, lo=_ez_num(g("Départ")), hi=_ez_num(g("Arrêt")),
                sep=_ez_num(g("Séparation"), 300.0) / 1000.0, filt=_ez_num(g("Filtre")),
                step=_ez_num(g("Incrément"), 0.025) or 0.025,
                tol={"2tx3": _ez_num(g("Tolérance"), 100.0) / 1000.0, "3tx3": _ez_num(g("Tolérance3TX"), 50.0) / 1000.0,
                     "5": (_ez_num(g("Tolérance5e"), 50.0) / 1000.0 if eval5 and g("Eval5eOrdre").lower() == "true" else 0.0),
                     "7": 0.0},     # 5ᵉ ordre : interrupteur du document (Options) ET case de l'appareil
                img=_ez_num(g("FréqImage")) if g("FréqImageDéfinie").lower() == "true" else 0.0)


def ezrf_dev_key(p):
    """Clé d'un appareil : nom + réglages (deux « AKG DMS700 » réglés différemment = deux profils)."""
    t = p.get("tol") or {}
    return (p["name"], round(p.get("sep", 0), 4), round(p.get("filt", 0), 3), round(p.get("step", 0), 4),
            round(t.get("2tx3", 0), 4), round(t.get("3tx3", 0), 4), round(t.get("5", 0), 4), round(p.get("img") or 0, 3))


def parse_ezrf3(data):
    """Document .ezrf3 (XML) -> dict(title, date, version, rows, devices, interf, scan, scan_title,
    tv, warn). Les éléments sont À PLAT dans le fichier, dans l'ordre : GroupeDt (NbSect sections), SectionDt (NbApp
    appareils), AppareilDt (NbreFréqDésiré fréquences), FréquenceDt -> on reconstruit Zone > Groupe > Section >
    Appareil > Fréquence avec ces nombres. Lu sur un vrai fichier .ezrf3 (version 4.81) (Roc d'Azur 2026) ; si les nombres ne
    tombent pas juste, les fréquences sont gardées sans classement (warn)."""
    import xml.etree.ElementTree as ET
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    try:
        root = ET.fromstring(raw.lstrip(b"\xef\xbb\xbf"))
    except ET.ParseError as e:
        raise ValueError(f"fichier illisible ({e})") from None
    if root.tag != "EazyRFds":
        raise ValueError("ce n'est pas un document EazyRF (.ezrf3)")

    def getter(e):
        return lambda k: (e.findtext(k) or "").strip()

    def yes(e, k):
        return (e.findtext(k) or "").strip().lower() == "true"
    zones = {}
    for z in root.findall("ZonesDt"):
        zones[(z.findtext("NoZone") or "").strip()] = (z.findtext("Title") or "").strip()
    groups, sects, apps, freqs = (root.findall(t) for t in ("GroupeDt", "SectionDt", "AppareilDt", "FréquenceDt"))
    warn = ""

    def cnt(e, k):
        try:
            return max(0, int(_ez_num(e.findtext(k))))
        except (TypeError, ValueError):
            return 0
    ok = (sum(cnt(g, "NbSect") for g in groups) == len(sects) and sum(cnt(s, "NbApp") for s in sects) == len(apps)
          and sum(cnt(a, "NbreFréqDésiré") for a in apps) == len(freqs))
    devices, rows = {}, []
    op = root.find("OptionsDt")
    eval5 = op is None or (op.findtext("Eval5eOrdre") or "true").strip().lower() == "true"

    def add_row(fr, zone, scene, group, dev, devno, off):
        g = getter(fr)
        f = _ez_num(g("Valeur"))
        if not 1.0 <= f <= 7000.0:
            return
        rows.append(dict(zone=zone, scene=scene, group=group, dev=dev, devno=devno, name=g("Description")[:60],
                         note=g("Commentaire")[:200], freq=round(f, 5),
                         off=off or yes(fr, "Rayé") or yes(fr, "Libéré")))
    if ok:
        si = ai = fi = 0
        for gr in groups:
            gg = getter(gr)
            zone, scene, goff = zones.get(gg("ZoneNo"), ""), gg("Title"), yes(gr, "HorsFonction")
            for _ in range(cnt(gr, "NbSect")):
                se = sects[si]
                si += 1
                group, soff = getter(se)("Title"), yes(se, "HorsFonction")
                for _ in range(cnt(se, "NbApp")):
                    ap = apps[ai]
                    ai += 1
                    ga = getter(ap)
                    p = _ez_dev_params(ga("AppareilName")[:60] or "Appareil", ga, eval5)
                    k = ezrf_dev_key(p)
                    devices.setdefault(k, p)
                    aoff = yes(ap, "HorsFonction") or yes(ap, "Rayé")
                    for _ in range(cnt(ap, "NbreFréqDésiré")):
                        add_row(freqs[fi], zone, scene, group, k, ga("AppDescription")[:20],
                                goff or soff or aoff)
                        fi += 1
    else:
        warn = "structure inattendue : fréquences importées sans scène / groupe / appareil"
        for fr in freqs:
            add_row(fr, "", "", "", None, "", False)
    pa = root.find("ParamsDt")
    gp = getter(pa) if pa is not None else (lambda k: "")
    interf = sorted({round(_ez_num(i.findtext("Départ")), 4) for i in root.findall("InterférencesDt")
                     if _ez_num(i.findtext("Départ")) > 1.0})
    scan = None
    if gp("ZipScanData"):
        try:
            import base64
            import gzip
            buf = gzip.decompress(base64.b64decode(gp("ZipScanData")))
            a = np.frombuffer(buf[:len(buf) // 16 * 16], dtype="<f8").reshape(-1, 2)
            a = a[np.isfinite(a).all(axis=1) & (a[:, 0] > 1.0) & (a[:, 0] < 7000.0) & (a[:, 1] > -200.0)
                  & (a[:, 1] < 50.0)]
            if len(a) >= 2:
                o = np.argsort(a[:, 0], kind="stable")
                scan = (a[o, 0].copy(), a[o, 1].copy())
        except Exception:                          # scan illisible : le reste du document reste bon
            scan = None
    tv = []
    for g in groups:                               # 7.58.2 : canaux TV de TOUS les groupes / zones (réunis)
        for ln in (g.findtext("ChTVActifList") or "").splitlines():
            a, _, b = ln.partition(";")
            if b.strip().lower() == "true" and a.strip().isdigit() and int(a) not in tv:
                tv.append(int(a))
    tv.sort()
    info = root.find("InformsDt")
    gi = getter(info) if info is not None else (lambda k: "")
    if not rows:
        raise ValueError("aucune fréquence dans ce document EazyRF")
    return dict(title=gi("Titre")[:80], date=gi("Date")[:40], version=gi("Version")[:60], rows=rows, devices=devices,
                interf=interf, scan=scan, scan_title=(gp("ScanTitle") or gp("ScanFilenamesList")).strip()[:60], tv=tv,
                warn=warn)


_EZ_DEV_RE = re.compile(r"^#\s*(\d+)\s*-\s*(.+)$")


_QE_NUM = re.compile(r"(?<![\w.,])(\d{2,7}(?:[.,]\d{1,6})?)\s*(mhz|khz|m|k)?(?![\w])", re.I)


def parse_quick_entry(text, max_items=300):
    """⌨ 7.62 Saisie express : « HF1 558.2, HF2 574, IEM 606.5 PSM », ou un message collé (mail, WhatsApp, tableau) ->
    [dict(name, freq)] (nom "" si aucun : l'appli numérote). Morceaux séparés par retour à la ligne, « ; », « , » (pas
    une virgule décimale « 558,2 ») ou « / » entre espaces. Fréquence = nombre à virgule ≥ 30 MHz, ou entier ≥ 100
    (MHz) ; entier de 30 000 à 6 000 000 ou suivi de « kHz » = kHz. Les petits nombres (HF 12, 20:30, téléphone)
    sont ignorés. Plusieurs fréquences dans un morceau = « nom 1 », « nom 2 »… Doublons (au kHz) retirés.
    Un entier SANS unité lu en kHz est marqué khz=True (l'aperçu demande de vérifier : code postal, référence…).
    -> (lignes, morceaux ignorés)."""
    chunks = re.split(r"[\n\r;]+|,(?!\d)|(?<!\d),|\s/\s", str(text or ""))
    out, ignored, seen = [], [], set()
    for ch in chunks:
        ch = ch.strip()
        if not ch:
            continue
        hits = []
        for m in _QE_NUM.finditer(ch):
            raw, unit = m.group(1).replace(",", "."), (m.group(2) or "").lower()
            v = float(raw)
            dec = "." in raw
            guess = False
            if unit in ("khz", "k") or (not dec and 30000 <= v <= 6e6 and unit not in ("mhz", "m")):
                guess = unit not in ("khz", "k")    # entier sans unité lu en kHz : à vérifier (code postal…)
                v /= 1000.0
            elif not (30.0 <= v <= 6000.0 and (dec or v >= 100 or unit in ("mhz", "m"))):
                continue
            if 30.0 <= v <= 6000.0:
                hits.append((m.start(), m.end(), round(v, 4), guess))
        if not hits:
            ignored.append(ch)
            continue
        before = ch[:hits[0][0]]
        parts = [x for x in re.split(r"[:→>]", before) if x.strip(" \t=")]
        before = parts[-1] if parts else ""
        after = ch[hits[-1][1]:]
        words = [x for x in re.split(r"[\s\-–—=:()\[\]]+", after) if x and not re.fullmatch(r"(?i)mhz|khz", x)]
        name = " ".join([x for x in re.split(r"[\s=:]+", before) if x][-4:] + (words if len(words) <= 2 else []))
        name = re.sub(r"\s+", " ", name).strip(" -–—:=.").strip()[:40]
        for k, (_a, _b, f, guess) in enumerate(hits, 1):
            key = int(round(f * 1000))
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(name=(f"{name} {k}" if name and len(hits) > 1 else name), freq=f))
            if guess:
                out[-1]["khz"] = True              # l'aperçu le signale : lu en kHz, à vérifier
            if len(out) >= max_items:
                return out, ignored
    return out, ignored


def quick_names(items, prefix, taken):
    """Noms des lignes sans nom : « prefix 1, prefix 2… » en sautant ceux déjà pris. -> liste de noms."""
    taken, out, k = set(taken), [], 1
    for it in items:
        if it["name"]:
            out.append(it["name"])
            continue
        while f"{prefix} {k}" in taken:
            k += 1
        out.append(f"{prefix} {k}")
        taken.add(out[-1])
    return out


def is_ezrf_paste(text):
    """Texte copié depuis le plan de fréquences du logiciel de coord (Ctrl+C) : lignes « #7 - Appareil » + fréquences."""
    lines = [ln.rstrip("\t \r") for ln in str(text).splitlines()]
    return any(_EZ_DEV_RE.match(ln.strip()) and "\t" not in ln.strip() for ln in lines) and any(
        "\t" in ln and re.fullmatch(r"\d{2,4}[,.]\d+", (ln.split("\t") + [""])[1].strip()) for ln in lines)


def parse_ezrf_paste(text):
    """Plan copié depuis le logiciel de coord -> dict comme parse_ezrf3 (sans réglages d'appareils ni scan). Après chaque ligne vide,
    les lignes de titre remplacent les niveaux les plus bas : 1 = appareil, 2 = section + appareil, 3 = groupe + …,
    4 = zone + groupe + section + appareil. Fréquence = « nom<TAB>MHz » (nom facultatif), décimale à virgule."""
    zone = scene = group = ""
    dev, devno, heads, rows = None, "", [], []

    def flush():
        nonlocal zone, scene, group, dev, devno
        if not heads:
            return
        h = list(heads)
        m = _EZ_DEV_RE.match(h[-1])
        if m:
            devno, dev = f"#{m.group(1)}", m.group(2).strip()[:60]
            h = h[:-1]
        if len(h) >= 3:
            zone, scene, group = h[-3:]
        elif len(h) == 2:
            scene, group = h
        elif len(h) == 1:
            group = h[0]
        heads.clear()
    for ln in str(text).splitlines():
        cells = ln.rstrip("\r").split("\t")
        first = cells[0].strip()
        rest = [c.strip() for c in cells[1:]]
        if not first and not any(rest):
            heads.clear()
            continue
        fr = next((c for c in rest if re.fullmatch(r"\d{2,4}(?:[,.]\d+)?", c)), "")
        if fr:
            flush()
            f = _ez_num(fr)
            if 1.0 <= f <= 7000.0:
                rows.append(dict(zone=zone, scene=scene, group=group, dev=(dev,) if dev else None, devno=devno,
                                 name=first[:60], note="", freq=round(f, 5), off=False))
        elif first and not any(rest):
            heads.append(first[:60])
    if not rows:
        raise ValueError("aucune fréquence dans le texte collé")
    devices = {(r["dev"][0],): dict(name=r["dev"][0]) for r in rows if r["dev"]}
    return dict(title="", date="", version="", rows=rows, devices=devices, interf=[], scan=None, scan_title="", tv=[],
                warn="")


def _xml_root(data, what):
    import xml.etree.ElementTree as ET
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    raw = raw.lstrip(b"\xef\xbb\xbf")
    raw = re.sub(rb"<!DOCTYPE[^>]*>", b"", raw, count=1)          # WSM : « <!DOCTYPE WSM> » en tête
    try:
        return ET.fromstring(raw)
    except ET.ParseError as e:
        raise ValueError(f"{what} illisible ({e})") from None


def _plan_doc(rows, devices, title="", warn=""):
    """Même forme que parse_ezrf3 : l'import, l'aperçu et le suivi du fichier marchent pareil pour tous les formats."""
    return dict(title=title, date="", version="", rows=rows, devices=devices, interf=[], scan=None, scan_title="",
                tv=[], warn=warn)


def _khz(x):
    try:
        v = float(str(x).strip().replace(",", ".")) / 1000.0
    except (TypeError, ValueError):
        return 0.0
    return round(v, 5) if 1.0 <= v <= 7000.0 else 0.0


def parse_wwb_show(data):
    """Show Shure Wireless Workbench (.shw, vrai fichier de Clément, WWB 7.9) -> doc comme parse_ezrf3. Fréquences =
    « coordinated_data_root » (freq_entry : value kHz, source_name = nom du canal, compat_key zone / series / band,
    model) ; sinon les canaux de l'inventaire (channel/frequency). Scène = zone (sauf « Default »), groupe = série +
    bande (« AD G56 »), appareil = modèle. Pas de règles de coordination dans le fichier : profil à choisir à la main."""
    root = _xml_root(data, "show WWB")
    if root.tag != "show":
        raise ValueError("ce n'est pas un show Wireless Workbench (.shw)")
    title = (root.findtext("show_properties/show_info/name") or "").strip()
    rows, devices = [], {}

    def add(name, f, zone, series, band, model):
        if not f:
            return
        zone = "" if zone.strip().lower() in ("", "default") else zone.strip()
        k = (model or series or "Shure",)
        devices.setdefault(k, dict(name=k[0]))
        rows.append(dict(zone="", scene=zone[:60], group=" ".join(x for x in (series, band) if x)[:60], dev=k,
                         devno="", name=name.strip()[:60], note=model, freq=f, off=False))
    for fe in root.iter("freq_entry"):
        ck = fe.find("compat_key")
        g = (lambda t: (ck.findtext(t) or "").strip()) if ck is not None else (lambda t: "")
        add(fe.findtext("source_name") or "", _khz(fe.findtext("value")), g("zone"), g("series"), g("band"),
            (fe.findtext("model") or "").strip())
    if not rows:                                   # pas encore coordonné : les canaux de l'inventaire
        for dv in root.iter("device"):
            gd = lambda t: (dv.findtext(t) or "").strip()      # noqa: E731
            for ch in dv.findall("channel"):
                add(ch.findtext("channel_name") or "", _khz(ch.findtext("frequency")), gd("zone"), gd("series"),
                    gd("band"), gd("model"))
    if not rows:
        raise ValueError("aucune fréquence dans ce show")
    _number_dups(rows)
    return _plan_doc(rows, devices, title)


def _number_dups(rows):
    """Noms en double (WWB nomme souvent tous les canaux « Shure ») -> « Shure 1 », « Shure 2 »… ; vide -> modèle n."""
    cnt, seen = {}, {}
    for r in rows:
        r["name"] = r["name"] or (r["note"] or "Canal")
        cnt[r["name"]] = cnt.get(r["name"], 0) + 1
    for r in rows:
        if cnt[r["name"]] > 1:
            seen[r["name"]] = seen.get(r["name"], 0) + 1
            r["name"] = f"{r['name']} {seen[r['name']]}"[:60]


def parse_wsm_project(data):
    """Projet Sennheiser Wireless Systems Manager (.wsm, vrai fichier de Clément, WSM 4.9) -> doc comme parse_ezrf3.
    Fréquences = FrequencyManager/Devices/Device (Frequency kHz, Name, StationaryDeviceType, Min / MaxFrequency,
    SearchStep, SpacingParams : Carriers = écart entre porteuses kHz, Device2TxIM3 / Device3TxIM3 / Device2TxIM5 =
    tolérances kHz) ; sinon les récepteurs (Receiver/CurrentFrequency). Groupe = type de récepteur."""
    root = _xml_root(data, "projet WSM")
    if root.tag != "WSM":
        raise ValueError("ce n'est pas un projet Wireless Systems Manager (.wsm)")
    rows, devices = [], {}

    def num(e, t, d=0.0):
        try:
            return float((e.findtext(t) or "").strip())
        except ValueError:
            return d
    fm = root.find("FrequencyManager/Devices")
    for dv in (fm.findall("Device") if fm is not None else []):
        f = _khz(dv.findtext("Frequency"))
        if not f:
            continue
        typ = (dv.findtext("StationaryDeviceType") or dv.findtext("Name") or "WSM").strip()[:60]
        sp = dv.find("SpacingParams")
        p = dict(name=typ, lo=num(dv, "MinFrequency") / 1000.0, hi=num(dv, "MaxFrequency") / 1000.0,
                 sep=(num(sp, "Carriers", 300.0) if sp is not None else 300.0) / 1000.0, filt=0.0,
                 step=(num(dv, "SearchStep", 25.0) or 25.0) / 1000.0,
                 tol={"2tx3": (num(sp, "Device2TxIM3", 100.0) if sp is not None else 100.0) / 1000.0,
                      "3tx3": (num(sp, "Device3TxIM3", 50.0) if sp is not None else 50.0) / 1000.0,
                      "5": (num(sp, "Device2TxIM5") if sp is not None else 0.0) / 1000.0, "7": 0.0}, img=0.0)
        k = ezrf_dev_key(p)
        devices.setdefault(k, p)
        rows.append(dict(zone="", scene="", group=typ, dev=k, devno="", name=(dv.findtext("Name") or "").strip()[:60],
                         note="", freq=f, off=False))
    if not rows:
        for rc in root.iter("Receiver"):
            f = _khz(rc.findtext("CurrentFrequency"))
            typ = (rc.get("Type") or "WSM")[:60]
            if f:
                devices.setdefault((typ,), dict(name=typ))
                rows.append(dict(zone="", scene="", group=typ, dev=(typ,), devno="",
                                 name=(rc.findtext("Name") or "").strip()[:60], note=typ, freq=f, off=False))
    if not rows:
        raise ValueError("aucune fréquence dans ce projet")
    _number_dups(rows)
    return _plan_doc(rows, devices)


def parse_shure_cug(data):
    """Groupe personnalisé Shure exporté par WWB (.cug, vrai fichier de Clément) : <custom_groups><frequencies
    series band><channel frequency (kHz) number>. Nom = « série bande · n° », groupe = « série bande »."""
    root = _xml_root(data, "groupe Shure")
    if root.tag != "custom_groups":
        raise ValueError("ce n'est pas un groupe personnalisé Shure (.cug)")
    rows, devices = [], {}
    for fq in root.iter("frequencies"):
        sb = " ".join(x for x in ((fq.get("series") or "").strip(), (fq.get("band") or "").strip()) if x) or "Shure"
        devices.setdefault((sb,), dict(name=sb))
        for ch in fq.findall("channel"):
            f = _khz(ch.get("frequency"))
            if f:
                rows.append(dict(zone="", scene="", group=sb[:60], dev=(sb,), devno="",
                                 name=f"{sb} · {(ch.get('number') or '').strip() or len(rows) + 1}"[:60], note="",
                                 freq=f, off=False))
    if not rows:
        raise ValueError("aucune fréquence dans ce groupe")
    return _plan_doc(rows, devices)


def parse_wisycom_show(data):
    """Show Wisycom Manager (.wshow, vrai fichier de Clément, WisycomManager 5.1) : seuls les ÉMETTEURS (MTK…)
    gardent leur fréquence (DeviceChannel : Name, TunedFreq en Hz) ; les récepteurs (MRK, MCR) n'ont que des noms de
    canaux -> signalés dans warn (à ajouter à la main). Groupe = modèle de l'appareil (Device Name)."""
    root = _xml_root(data, "show Wisycom")
    if root.tag != "ShowFile":
        raise ValueError("ce n'est pas un show Wisycom Manager (.wshow)")
    rows, devices, missing = [], {}, []
    for dv in root.iter("Device"):
        model = (dv.get("Name") or "Wisycom").strip()[:60]
        chans = dv.findall("DeviceAttr/DeviceChannel")
        for ch in chans:
            try:
                f = round(float(ch.find("TunedFreq").get("Value")) / 1e6, 5)
            except (AttributeError, TypeError, ValueError):
                f = 0.0
            if not 1.0 <= f <= 7000.0:
                continue
            nm = ch.find("Name")
            devices.setdefault((model,), dict(name=model))
            rows.append(dict(zone="", scene="", group=model, dev=(model,), devno="",
                             name=((nm.get("Value") if nm is not None else "") or "").strip()[:60], note=model, freq=f,
                             off=False))
        if not chans:                              # récepteur : noms de canaux seulement (pas ceux = nom de l'appareil,
            missing += [dict(name=n[:60], model=model)                                                  # MAT288, MRK16…)
                        for n in ((c.get("Name") or "").strip() for c in dv.findall("Channels/*")) if n and n != model]
    if not rows and not missing:
        raise ValueError("aucune fréquence dans ce show (Wisycom n'y enregistre que celles des émetteurs)")
    _number_dups(rows)
    warn = ""
    if missing:
        warn = (f"{len(missing)} canal(aux) de récepteur sans fréquence dans le fichier : Wisycom Manager ne les y "
                f"enregistre pas. Complète-les dans le tableau « À compléter » (fréquence trouvée par le nom dans ta "
                f"liste quand c'est possible).")
    doc = _plan_doc(rows, devices, warn=warn)
    cnt, seen = {}, {}
    for p_ in missing:
        cnt[p_["name"]] = cnt.get(p_["name"], 0) + 1
    for p_ in missing:                          # 3 × « SPARE » -> SPARE 1, 2, 3 (à compléter chacun)
        if cnt[p_["name"]] > 1:
            seen[p_["name"]] = seen.get(p_["name"], 0) + 1
            p_["name"] = f"{p_['name']} {seen[p_['name']]}"[:60]
    doc["pending"] = missing
    return doc


def _name_tokens(s):
    k = "".join(c for c in unicodedata.normalize("NFD", str(s).upper()) if unicodedata.category(c) != "Mn")
    words = re.findall(r"[A-Z]+|\d+", k)
    return [w for w in words if not w.isdigit()], [int(w) for w in words if w.isdigit()]


def name_match(name, candidates, avoid=()):
    """Corrélation par le nom (Clément : « fais une corrélation au nom ») : canal d'un récepteur Wisycom → l'entrée de la
    liste qui porte le même nom, sinon les mêmes numéros + chaque mot du canal = début d'un mot du candidat (« DEP 1 »
    ↔ « HF 1 DEPART », « SCE 2 » ↔ « HF 2 SCENE »). avoid = mots qui écartent un candidat (« IEM » pour un récepteur de
    micros). -> indice dans candidates, ou None (rien, ou plusieurs à égalité)."""
    nk = re.sub(r"\s+", " ", str(name).strip().lower())
    exact = [i for i, c in enumerate(candidates) if re.sub(r"\s+", " ", str(c).strip().lower()) == nk]
    if exact:
        return exact[0] if len(exact) == 1 else None
    wa, na = _name_tokens(name)
    if not wa and not na:
        return None
    best, hits = 0, []
    for i, c in enumerate(candidates):
        wb, nb = _name_tokens(c)
        if sorted(na) != sorted(nb) or any(x in wb for x in avoid if x not in wa):
            continue
        if not all(any(b.startswith(a) or a.startswith(b) for b in wb) for a in wa):
            continue
        sc = sum(1 for a in wa for b in wb if b.startswith(a) or a.startswith(b))
        if sc > best:
            best, hits = sc, [i]
        elif sc == best:
            hits.append(i)
    return hits[0] if len(hits) == 1 else None


def plan_fill_pending(doc, manual):
    """Canaux sans fréquence complétés (manual = {nom: MHz}) -> ajoutés aux lignes du plan (groupe = modèle), le reste
    reste « à compléter ». Utilisé à l'import ET à chaque relecture du fichier suivi."""
    rows, left = list(doc["rows"]), []
    devices = dict(doc["devices"])
    for p in doc.get("pending") or []:
        f = (manual or {}).get(p["name"])
        try:
            f = round(float(f), 5) if f else 0.0
        except (TypeError, ValueError):
            f = 0.0
        if 1.0 <= f <= 7000.0:
            devices.setdefault((p["model"],), dict(name=p["model"]))
            rows.append(dict(zone="", scene="", group=p["model"], dev=(p["model"],), devno="", name=p["name"],
                             note=p["model"], freq=f, off=False))
        else:
            left.append(p)
    return dict(doc, rows=rows, devices=devices, pending=left)


def parse_dpa_acp(data):
    """Projet DPA N (.acp, JSON, vrai fichier de Clément, récepteurs N-DR1) : par appareil, réglages « /ch/N/name » et
    « /ch/N/radio/manual » (kHz). Règles : profil du modèle (frequencyManagerProject/modelProfiles, mode du canal :
    channelSpacing = écart, spacingToIM3Product = tolérance intermod), plage = 1re bande de frequencyTable."""
    import json
    try:
        d = json.loads(data.decode("utf-8-sig") if isinstance(data, (bytes, bytearray)) else data)
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"projet DPA illisible ({e})") from None
    if not isinstance(d, dict) or "devices" not in d:
        raise ValueError("ce n'est pas un projet DPA (.acp)")
    profs = {}
    for mp in ((d.get("frequencyManagerProject") or {}).get("modelProfiles") or []):
        profs[mp.get("model")] = {c.get("mode"): c for c in (mp.get("calculationProfiles") or [])}
    rows, devices = [], {}
    for dv in d.get("devices") or []:
        model = str(dv.get("model") or "DPA")[:40]
        st = {}
        for x in dv.get("settings") or []:
            if x.get("key") and x.get("values"):
                st[x["key"]] = x["values"][0].get("value")
        bands = ((dv.get("frequencyTable") or {}).get("bands") or [{}])
        lo, hi = _khz(bands[0].get("startFrequency")), _khz(bands[0].get("stopFrequency"))
        for n in range(1, int(dv.get("numberOfChannels") or 2) + 1):
            f = _khz(st.get(f"/ch/{n}/radio/manual"))
            if not f:
                continue
            mode = next((x["values"][0].get("value") for x in dv.get("settings") or []
                         if x.get("guiType") == "Mode" and x.get("channelNumber") == n and x.get("values")), 1)
            cp = (profs.get(dv.get("model")) or {}).get(mode)
            p = dict(name=f"DPA {model}", lo=lo, hi=hi, sep=float(cp.get("channelSpacing", 500)) / 1000.0, filt=0.0,
                     step=0.025, img=0.0,
                     tol={"2tx3": float(cp.get("spacingToIM3Product", 0)) / 1000.0,
                          "3tx3": float(cp.get("spacingToIM3Product", 0)) / 1000.0, "5": 0.0, "7": 0.0}) \
                if cp else dict(name=f"DPA {model}")
            k = ezrf_dev_key(p) if cp else (p["name"],)
            devices.setdefault(k, p)
            rows.append(dict(zone="", scene="", group=f"DPA {model}", dev=k, devno="",
                             name=str(st.get(f"/ch/{n}/name") or "").strip()[:60], note=model, freq=f, off=False))
    if not rows:
        raise ValueError("aucune fréquence dans ce projet")
    _number_dups(rows)
    title = re.split(r"[\\/]", str(d.get("name") or ""))[-1].rsplit(".", 1)[0]
    return _plan_doc(rows, devices, title)


PLAN_EXTS = {".ezrf3": "EazyRF", ".shw": "Shure WWB", ".wsm": "Sennheiser WSM", ".cug": "Shure (groupe)",
             ".wshow": "Wisycom Manager", ".acp": "DPA"}


def parse_plan_file(data, name=""):
    """Plan de fréquences d'un logiciel de coordination -> (doc comme parse_ezrf3, nom du logiciel). Choisi par
    l'extension, sinon par le contenu (balise racine)."""
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    head = (data[:400].decode("utf-8", "ignore") if isinstance(data, (bytes, bytearray)) else str(data)[:400])
    kind = PLAN_EXTS.get(ext) or next((n for tag, n in (("<EazyRFds", "EazyRF"), ("<ShowFile", "Wisycom Manager"),
                                                       ("<show", "Shure WWB"), ("WSM", "Sennheiser WSM"),
                                                       ("<custom_groups", "Shure (groupe)"),
                                                       ('"projectFileVersion"', "DPA")) if tag in head), "")
    fn = {"EazyRF": parse_ezrf3, "Shure WWB": parse_wwb_show, "Sennheiser WSM": parse_wsm_project,
          "Shure (groupe)": parse_shure_cug, "Wisycom Manager": parse_wisycom_show, "DPA": parse_dpa_acp}.get(kind)
    if fn is None:
        raise ValueError("format de plan inconnu (EazyRF .ezrf3, Shure WWB .shw / .cug, Sennheiser WSM .wsm, "
                         "Wisycom .wshow, DPA .acp)")
    return fn(data), kind


def ezrf_id(scene, group, name):
    """Identifiant stable d'une fréquence venue d'un plan .ezrf3 (pour suivre le fichier : w["ez"])."""
    return f"{scene}|{group}|{name}"


def ezrf_diff(entries, cur):
    """🔗 Plan .ezrf3 réenregistré : entries = ezrf_entries(nouveau document) ; cur = [(id, MHz)] des fréquences de la liste
    venues du plan -> dict(add=[entrée], change=[(id, ancienne MHz, nouvelle MHz, entrée)], remove=[id])."""
    new = {}
    for e in entries:
        new.setdefault(ezrf_id(e[2], e[3], e[0]), e)
    old = dict(cur)
    return dict(add=[e for i, e in new.items() if i not in old],
                change=[(i, old[i], new[i][1], new[i]) for i in new if i in old and abs(new[i][1] - old[i]) > 1e-6],
                remove=[i for i in old if i not in new])


def ezrf_profile_names(devices):
    """Appareils d'un document -> {clé: nom de profil}. Même nom, réglages différents -> « nom (sép. 300 kHz) »."""
    by_name = {}
    for k, p in devices.items():
        by_name.setdefault(p["name"], []).append(k)
    out = {}
    for name, ks in by_name.items():
        for k in ks:
            p = devices[k]
            if len(ks) == 1 or "sep" not in p:
                out[k] = name
            else:
                out[k] = f"{name} (sép. {p['sep'] * 1000:g} kHz · filtre {p['filt']:g} MHz)"[:60]
    return out


EZRF_NAMINGS = (("dev", "Nom de l'appareil (Shure AD4Q #1 · 2)"), ("group", "Nom du groupe (THE BROWNING · MICS 1)"),
                ("both", "Groupe + appareil (THE BROWNING · MICS 1 · Shure AD4Q)"))


def ezrf_group_label(name):
    """Nom de groupe du plan sans préfixe de scène ni horaire : « T2 - THE BROWNING 23:20 - 00:10 » -> « THE BROWNING »."""
    x = str(name or "")
    m = EZRF_PREFIX.match(x)
    if m:
        x = m.group(2)
    x = EZRF_TIMES.sub("", x)
    return re.sub(r"\s+", " ", x).strip(" -–:·|") or str(name or "").strip()


def ezrf_entries(doc, skip_off=True, naming="dev"):
    """Lignes à importer -> [(nom, MHz, scène, groupe, clé appareil, note)]. Scène = groupe du document (préfixé de la zone
    s'il y en a plusieurs), groupe = section ; nom vide -> « Appareil #n · k » (naming « dev »), « Groupe · section k »
    (« group », 7.66.1, idée de Clément) ou les deux (« both ») ; un nom écrit dans le plan est toujours gardé."""
    multi = len({r["zone"] for r in doc["rows"]}) > 1
    naming = naming if naming in ("dev", "group", "both") else "dev"
    out, seen = [], {}
    for r in doc["rows"]:
        if skip_off and r["off"]:
            continue
        sc = r["scene"]
        if multi and r["zone"]:
            sc = f"{r['zone']} · {sc}" if sc else r["zone"]
        name, note = r["name"], r["note"]
        if not name:
            dn = (doc["devices"].get(r["dev"]) or {}).get("name", "") if r["dev"] else ""
            dev = " ".join(x for x in (dn, r["devno"]) if x)
            if naming == "dev" or not (r["scene"] or r["group"]):
                base = dev or (r["group"] or sc or "EazyRF")
                k = (sc, r["group"], base)
                seen[k] = seen.get(k, 0) + 1
                name = f"{base} · {seen[k]}"
            else:
                lab = ezrf_group_label(r["scene"])
                k = (sc, r["group"], "\0")
                seen[k] = seen.get(k, 0) + 1
                name = " · ".join(x for x in (lab, f"{r['group']} {seen[k]}".strip()) if x)
                if naming == "both" and dn:
                    name += f" · {dn}"
                elif dev:                               # le modèle reste lisible dans la note
                    note = " · ".join(x for x in (note, dev) if x)
        out.append((name[:60], r["freq"], sc[:60], r["group"][:60], r["dev"], note))
    return out


# 7.66 (Clément, plan réel : « T2 - 111 15:00 - 15:40 » = un passage de la scène « TERMINAL 2 » ; l'import faisait
# une scène par passage) : ranger les scènes du plan à l'import (et au suivi du fichier)
EZRF_PREFIX = re.compile(r"^\s*([A-Za-z0-9]{1,8})\s*[-–:·|]\s*(\S.*)$")
EZRF_GROUP_MODES = (("keep", "Garder les sections (MICS, IEMS…)"), ("source", "Nom d'origine (le passage)"),
                    ("both", "Passage · section"))
EZRF_TIMES = re.compile(r"(\d{1,2})[:hH](\d{2})\s*[-–à]\s*(\d{1,2})[:hH](\d{2})")


def _abbrev(name):
    """« TERMINAL 2 » -> « T2 », « Grande scène » -> « GS » (initiales des mots + nombres)."""
    words = re.findall(r"[^\W\d_]+|\d+", str(name or ""))
    return "".join(w if w.isdigit() else w[0] for w in words).upper()


def ezrf_scene_guess(src, candidates):
    """Scène d'un plan nommée « T2 - 111 15:00 » -> (« TERMINAL 2 », « 111 15:00 ») si une scène candidate a pour
    initiales (ou pour nom) le préfixe « T2 » ; sinon None."""
    def split(x):                                 # plan à plusieurs zones : « Zone Nord · T2 - … »
        x = str(x or "")
        return x.rsplit(" · ", 1) if " · " in x else ("", x)
    zone, base = split(src)
    m = EZRF_PREFIX.match(base)
    if not m:
        return None
    pre, rest = m.group(1).upper(), m.group(2).strip()
    for c in candidates:
        cz, cb = split(c)
        if c != src and cz == zone and not EZRF_PREFIX.match(cb) and (_abbrev(cb) == pre or cb.strip().upper() == pre):
            return c, rest
    return None


def ezrf_auto_map(scenes, existing=()):
    """Rangement proposé à l'import : {scène du plan: {scene, group, label}} pour celles qui se rattachent à une autre
    (« T2 - … » -> « TERMINAL 2 », groupe « passage · section »). Les autres ne bougent pas."""
    cands = list(dict.fromkeys(list(scenes) + [e for e in existing or () if e not in scenes]))
    out = {}
    for s_ in scenes:
        g = ezrf_scene_guess(s_, cands)
        if g:
            out[s_] = dict(scene=g[0], group="both", label=g[1])
    return out


def ezrf_map_norm(m):
    """Rangement lu (suivi du fichier, config) -> {source: {scene, group keep|source|both, label}} propre."""
    out = {}
    for k, v in (m or {}).items() if isinstance(m, dict) else ():
        if isinstance(k, str) and isinstance(v, dict):
            sc = str(v.get("scene") or "").strip()[:60]
            mode = v.get("group") if v.get("group") in ("keep", "source", "both") else "keep"
            if sc and (sc != k or mode != "keep"):
                out[k[:60]] = dict(scene=sc, group=mode, label=str(v.get("label") or k).strip()[:60])
    return out


def ezrf_remap(entries, mapping):
    """Entrées d'ezrf_entries rangées selon mapping (voir ezrf_auto_map) : scène remplacée, groupe = section, nom
    d'origine (label) ou « label · section »."""
    mapping = ezrf_map_norm(mapping)
    out = []
    for name, f, sc, gr, dk, note in entries:
        mp = mapping.get(sc)
        if mp:
            lab = mp["label"] or sc
            gr = lab if mp["group"] == "source" else (f"{lab} · {gr}" if gr else lab) if mp["group"] == "both" else gr
            sc = mp["scene"]
        out.append((name, f, sc[:60], (gr or "")[:60], dk, note))
    return out


def ezrf_planning(entries):
    """Créneaux de 🎬 Planning lus dans les noms de groupe (« 111 15:00 - 15:40 ») -> [{scene, group, day, start,
    end}] (un par groupe, tous les jours)."""
    seen, out = set(), []
    for _n, _f, sc, gr, _d, _x in entries:
        m = EZRF_TIMES.search(gr or "")
        if not m or (sc, gr) in seen:
            continue
        seen.add((sc, gr))
        a, b = f"{int(m.group(1)):02d}:{m.group(2)}", f"{int(m.group(3)):02d}:{m.group(4)}"
        if _hm(a) is not None and _hm(b) is not None:
            out.append(dict(scene=sc, group=gr, day="", start=a, end=b))
    return out


def rx_all():
    """Profils intégrés puis profils perso."""
    return RX_PROFILES + RX_CUSTOM


def rx_profile(key):
    """Profil d'appareil par sa clé -> dict(sep, filt, step, tol, src), ou None (= réglages de la fenêtre)."""
    for k, _n, d, _w in rx_all():
        if k == key:
            return dict(d, tol=dict(d["tol"]))
    return None


def _rx_num(x, lo, hi, dflt):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return dflt
    return dflt if v != v else min(hi, max(lo, v))


def rx_custom_norm(lst):
    """Profils perso lus (config / show) -> liste propre de (clé, nom, réglages, note). Clés « perso_… » uniques."""
    out, seen = [], {k for k, *_ in RX_PROFILES}
    for i, p in enumerate(lst if isinstance(lst, list) else []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()[:60]
        if not name:
            continue
        key = str(p.get("key") or "")
        if not re.fullmatch(r"perso_[A-Za-z0-9_]{1,40}", key) or key in seen:
            key = f"perso_{len(out) + 1}"
            while key in seen:
                key += "_"
        seen.add(key)
        t = p.get("tol") if isinstance(p.get("tol"), dict) else {}
        tol = {k: _rx_num(t.get(k), 0.0, 2.0, d) for k, d in _TOL_EZ.items()}
        tol["7"] = 0.0
        extra = {k_: _rx_num(p.get(k_), 0.0, 7000.0, 0.0) for k_ in ("lo", "hi") if p.get(k_)}
        if p.get("img"):
            extra["img"] = _rx_num(p.get("img"), 0.0, 200.0, 0.0)      # FI (fréquence intermédiaire) : image à ± FI (vérifié 7.51)
        out.append((key, name, dict(sep=_rx_num(p.get("sep"), 0.0, 10.0, 0.4), filt=_rx_num(p.get("filt"), 0.0, 400.0, 0.0),
                                    step=_rx_num(p.get("step"), 0.001, 1.0, 0.025), tol=tol,
                                    src="eazyrf" if p.get("src") == "eazyrf" else "perso", **extra),
                    str(p.get("note") or "Profil perso.")[:300]))
    return out


def rx_set_custom(lst):
    RX_CUSTOM[:] = rx_custom_norm(lst)


def rx_custom_dump():
    """Profils perso -> liste JSON (config, shows)."""
    return [dict(key=k, name=n, sep=d["sep"], filt=d["filt"], step=d["step"], tol=dict(d["tol"]), note=w,
                 src=d.get("src", "perso"), **{k_: d[k_] for k_ in ("lo", "hi", "img") if d.get(k_)})
            for k, n, d, w in RX_CUSTOM]


RX_SRC_TXT = {"eazyrf": "courant", "guess": "générique", "perso": "ton profil"}


def rx_help_html():
    """Explication du filtre récepteur + tableau des profils (fenêtre « ❓ Le filtre, c'est quoi ? »)."""
    rows = "".join(
        f"<tr><td>{n}</td><td align=right>{('%g MHz' % d['filt']) if d['filt'] else 'aucun'}</td>"
        f"<td align=right>{d['sep'] * 1000:.0f} kHz</td><td align=right>{d['step'] * 1000:g} kHz</td>"
        f"<td>{RX_SRC_TXT.get(d.get('src'), '')}</td></tr>" for _k, n, d, _w in rx_all())
    return (
        "<h3>Le filtre récepteur, c'est quoi ?</h3>"
        "<p>Chaque récepteur a, juste après l'antenne, un <b>filtre d'entrée</b> (présélection) : il ne laisse passer "
        "qu'une tranche du spectre autour de la fréquence réglée. Un Wisycom MRK980 a un filtre de <b>32 MHz</b> : "
        "on prend en compte les émetteurs à <b>±32 MHz</b> autour de la fréquence (avec 16 MHz, pour une porteuse à 500 MHz : de 484 à 516 MHz).</p>"
        "<p><b>Pourquoi ça compte pour l'intermod ?</b> Un produit d'intermodulation (ex. 2A − B) est fabriqué "
        "dans l'<b>étage d'entrée du récepteur</b> à partir des émetteurs qu'il reçoit fort. Si l'émetteur A est à "
        "40 MHz de là, le filtre l'a déjà coupé : il ne peut plus fabriquer de produit dans ce récepteur. "
        "Donc : <b>un produit ne gêne une fréquence que si TOUS ses émetteurs sont dans le "
        "filtre de son récepteur</b> (à ± la valeur du filtre).</p>"
        "<ul><li>Le chiffre du filtre dit seulement <b>quelle tranche du spectre entre dans le récepteur</b>, donc "
        "combien d'émetteurs comptent dans le calcul (16 MHz en fait compter moins que 32 MHz). Il ne classe pas les "
        "récepteurs entre eux.</li>"
        "<li>L'<b>écart</b> (distance minimale entre deux porteuses) et les <b>tolérances</b> (marge autour d'un "
        "produit, par type ; 0 = type ignoré) complètent le profil.</li>"
        "<li><b>Aucun</b> (0) = tous les émetteurs comptent : le plus prudent, à utiliser quand on ne connaît pas "
        "l'appareil.</li></ul>"
        "<p>Les produits fabriqués ailleurs (dans les <b>émetteurs</b> eux-mêmes, ex. des ears couplés sur un "
        "combineur, ou dans un ampli d'antenne) ne sont pas filtrés par le récepteur : c'est pour ça qu'on "
        "compte aussi le 5ᵉ ordre sur les profils d'ears.</p>"
        "<p><b>Écart mini</b> = distance minimale entre deux porteuses (sinon le récepteur entend la voisine). "
        "<b>Pas</b> = le pas de réglage de l'appareil (les fréquences proposées tombent dessus).</p>"
        "<h3>Profils disponibles</h3>"
        "<table border=1 cellspacing=0 cellpadding=4><tr><th>Appareil</th><th>Filtre</th><th>Écart mini</th>"
        "<th>Pas</th><th>Source du filtre</th></tr>" + rows + "</table>"
        "<p>« Valeur de départ » = pas vérifiée : si tu connais la valeur (ton logiciel de coordination, doc du fabricant), crée un "
        "<b>profil perso</b> avec « ✏ Mes profils ». Le filtre d'un même appareil peut dépendre de sa bande "
        "(ex. groupe / banque A d'un evolution) : un profil perso par bande si besoin.</p>")


def _pf_vec(x, n):
    """Scalaire ou liste -> tableau de n valeurs (None = 0)."""
    if isinstance(x, (list, tuple, np.ndarray)):
        return np.asarray([0.0 if v is None else float(v) for v in x], dtype=float)
    return np.full(n, 0.0 if x is None else float(x))


def _pf_tols(tol, n):
    """tol : dict, ou liste de dicts (un par fréquence) -> (liste de n dicts, dict du max par type)."""
    dflt = IM_TOL_PRESETS[0][1]
    if isinstance(tol, (list, tuple)):
        L = [dict(dflt if t is None else t) for t in tol]
    else:
        L = [dict(dflt if tol is None else tol)] * n
    return L, {k: max([t.get(k, 0.0) for t in L], default=0.0) for k in ("2tx3", "3tx3", "5", "7")}


def pf_check(freqs, is_tx=None, bws=None, sep=PF_SEP, tol=None, max_tx=None, filt=0.0, img=0.0):
    """Compatibilité d'un plan : pour chaque fréquence, la liste de ses problèmes.
    - « sep » : une autre porteuse à moins de `sep` MHz (bord à bord pour un bloc large) ;
    - « im » : un produit d'intermod des ÉMETTEURS (is_tx) tombe dessus, dans la tolérance de son type (`tol`,
      2 TX / 3 TX / 5ᵉ ; 0 = type ignoré). Les réserves (is_tx False) sont protégées sans émettre.
    filt : largeur (MHz) du filtre d'entrée du récepteur (« Filtre » du logiciel de coord) ; un produit ne gêne une fréquence
    que si tous ses émetteurs sont à ± filt / 2 d'elle (les autres sont filtrés). 0 = pas de filtre.
    sep, filt et tol peuvent être donnés PAR FRÉQUENCE (listes : profil d'appareil de chacune) : l'écart entre deux
    porteuses est le plus grand des deux, le filtre et les tolérances sont ceux de la fréquence touchée.
    img : FI du récepteur (MHz, 0 = pas vérifié ; une valeur ou une par fréquence). Récepteur superhétérodyne (les
    analogiques, FI 10,7 MHz) : un ÉMETTEUR à f ± FI -> problème « img » (règle vérifiée par Clément le
    09/11/2026 : G3 sur 600 → « IMAGE de 589,300 / 610,700 », rien à 578,6 / 621,4) (tolérance =
    celle des 2 TX du récepteur, 100 kHz si elle vaut 0). Les deux côtés sont vérifiés (côté de l'oscillateur inconnu).
    -> (issues, info) ; issues[i] = [dict(kind, others=[indices], gap MHz, order, ntx, terms)]."""
    F = np.asarray(list(freqs), dtype=float)
    n = len(F)
    B = np.zeros(n) if bws is None else np.clip(np.asarray(list(bws), dtype=float), 0.0, None)
    tx = np.ones(n, dtype=bool) if is_tx is None else np.asarray(list(is_tx), dtype=bool)
    TL, tmax = _pf_tols(tol, n)
    SP, FL = _pf_vec(sep, n), _pf_vec(filt, n)
    if max_tx is None:
        max_tx = 3 if tmax.get("3tx3", 0) > 0 or tmax.get("5", 0) > 0 else 2
    issues = [[] for _ in range(n)]
    info = dict(pairs=0, truncated=False, too_big=False)
    if n < 2:
        return issues, info
    D = np.abs(F[:, None] - F[None, :]) - (B[:, None] + B[None, :]) / 2.0
    ii, jj = np.nonzero(np.triu(D < np.maximum(SP[:, None], SP[None, :]) - 1e-9, 1))
    for a, b in zip(ii.tolist(), jj.tolist()):
        g = float(D[a, b])
        issues[a].append(dict(kind="sep", others=[b], gap=g))
        issues[b].append(dict(kind="sep", others=[a], gap=g))
    IM = _pf_vec(img, n)
    for v in np.nonzero(IM > 0)[0].tolist():                   # fréquence image des récepteurs superhétérodynes
        ti = TL[v].get("2tx3", 0.0) or 0.100
        for k in np.nonzero(tx)[0].tolist():
            if k == v:
                continue
            for side in (1.0, -1.0):
                g = abs(F[k] - (F[v] + side * IM[v])) - (B[k] + B[v]) / 2.0
                if g < ti - 1e-6:
                    issues[v].append(dict(kind="img", others=[k], gap=float(max(0.0, g)), fi=float(IM[v])))
                    break
    txi = np.nonzero(tx)[0]
    orders = pf_orders(tmax)
    if len(txi) >= 2 and orders:
        TV = {k: np.array([t.get(k, 0.0) for t in TL]) for k in ("2tx3", "3tx3", "5", "7")}
        rows, info = im_scan(F[txi], orders, max_tx, targets=F, guard=tmax, bws=B[txi], tbws=B, limit=20000)
        o3 = [o for o in orders if o <= 3]
        if info.get("too_big") and o3 and len(o3) < len(orders):
            # 7.60.3 : trop de combinaisons avec le 5ᵉ ordre (dès ~60 émetteurs) -> on vérifie quand même le 3ᵉ ordre
            # (avant : AUCUNE intermod, seulement les écarts) ; info["reduced"] le dit à l'écran.
            rows, info2 = im_scan(F[txi], o3, max_tx, targets=F, guard=tmax, bws=B[txi], tbws=B, limit=20000)
            if not info2.get("too_big"):
                info = dict(info2, reduced=True)
        for r in rows:
            src = [(int(txi[i]), c) for i, c in r["terms"]]
            used = {k for k, _c in src}
            tv = TV.get(im_class(r["order"], r["ntx"]), TV["5"])
            g_ = np.abs(F - r["f"]) - r["hw"] - B / 2.0
            for v in np.nonzero((tv > 0) & (g_ < tv - 1e-6))[0].tolist():   # « au-delà » = accepté (doc du logiciel de coord)
                if v in used:
                    continue
                if FL[v] > 0 and any(abs(F[k] - F[v]) > FL[v] + 1e-9 for k in used):
                    continue                    # émetteur hors du filtre du récepteur : filtré
                issues[v].append(dict(kind="im", others=sorted(used), gap=float(g_[v]), order=r["order"],
                                      ntx=r["ntx"], terms=src, f=r["f"], hw=r["hw"]))
    return issues, info


def pf_issue_text(it, names, freqs):
    """Une ligne lisible pour un problème de pf_check."""
    if it["kind"] == "band":
        return f"hors de la bande de son appareil ({it['lo']:g}–{it['hi']:g} MHz)"
    if it["kind"] == "img":
        o = it["others"][0]
        if it["gap"] <= 0.001:
            return f"fréquence image : {names[o]} ({freqs[o]:.3f}) pile à ± FI ({it['fi']:g} MHz)"
        return f"fréquence image : {names[o]} ({freqs[o]:.3f}) à {it['gap'] * 1000:.0f} kHz de ± FI ({it['fi']:g} MHz)"
    if it["kind"] == "sep":
        o = it["others"][0]
        if it["gap"] < 0:
            return f"chevauche {names[o]} ({freqs[o]:.3f})"
        return f"trop près de {names[o]} ({freqs[o]:.3f}) : {it['gap'] * 1000:.0f} kHz d'écart"
    lab = IM_NAMES.get(it["order"], "IM") + f" {it['ntx']} TX"
    return f"{lab} : " + im_formula(it["terms"], names) + (" (pile dessus)" if it["gap"] <= 0.001 else
                                                        f" (à {it['gap'] * 1000:.0f} kHz)")


def rx_band(d):
    """(lo, hi) MHz de la bande d'un profil d'appareil (bibliothèque, plan importé, profil perso), sinon None."""
    try:
        lo, hi = float(d.get("lo") or 0.0), float(d.get("hi") or 0.0)
    except (AttributeError, TypeError, ValueError):
        return None
    return (lo, hi) if hi > lo > 0 else None


def band_issue(f, bw, band):
    """7.61 : fréquence (± bw / 2) hors de la bande de son appareil -> problème « band » de pf_check, sinon None."""
    if not band:
        return None
    lo, hi = band
    h = max(0.0, float(bw or 0.0)) / 2.0
    gap = max(lo - (f - h), (f + h) - hi)
    if gap <= 1e-6:
        return None
    return dict(kind="band", others=[], gap=float(gap), lo=float(lo), hi=float(hi))


def band_clip(a, b, band, bw=0.0):
    """Plage de recherche [a, b] réduite à la bande de l'appareil (bloc large : il doit y tenir en entier).
    -> (a, b), ou None si rien ne reste."""
    if not band:
        return (a, b) if b > a else None
    h = max(0.0, float(bw or 0.0)) / 2.0
    a2, b2 = max(a, band[0] + h), min(b, band[1] - h)
    return (a2, b2) if b2 > a2 + 1e-9 else None


def pf_suggest(i, freqs, is_tx=None, bws=None, sep=PF_SEP, tol=None, max_tx=None, lo=None, hi=None, step=0.025,
               n=5, busy=None, max_check=600, filt=0.0, img=0.0, skip=None, stats=None):
    """Fréquences de remplacement pour la n° i, les plus proches d'abord : aucune incompatibilité pour elle,
    et pas de NOUVEAU problème pour les autres. busy(c) -> True si le spectre mesuré y est occupé (on évite).
    sep / tol / filt : comme pf_check (une valeur, ou une par fréquence). step : pas des fréquences proposées.
    Pré-filtre vectorisé (écart, produits des autres qui tombent sur la candidate, 3ᵉ ordre impliquant la
    candidate), puis vérification exacte (pf_check) des meilleures seulement : rapide même avec des blocs larges.
    -> [(MHz, écart à l'actuelle en MHz)]."""
    F = [float(x) for x in freqs]
    nn = len(F)
    B = [0.0] * nn if bws is None else [float(x or 0.0) for x in bws]
    T = [True] * nn if is_tx is None else [bool(x) for x in is_tx]
    TL, tmax = _pf_tols(tol, nn)
    SP, FL = _pf_vec(sep, nn), _pf_vec(filt, nn)
    if max_tx is None:
        max_tx = 3 if tmax.get("3tx3", 0) > 0 or tmax.get("5", 0) > 0 else 2
    f0, bi, ti = F[i], B[i], TL[i]
    lo = f0 - 10.0 if lo is None else lo
    hi = f0 + 10.0 if hi is None else hi
    others = [k for k in range(nn) if k != i]
    Fo, Bo, To = [F[k] for k in others], [B[k] for k in others], [T[k] for k in others]
    TLo, SPo, FLo = [TL[k] for k in others], [float(SP[k]) for k in others], [float(FL[k]) for k in others]
    IMv = _pf_vec(img, nn)
    IMo = [float(IMv[k]) for k in others]
    base, _ = pf_check(Fo, To, Bo, SPo, TLo, max_tx, FLo, IMo)
    base_n = sum(len(x) for x in base)
    grid = np.round(np.arange(math.ceil(lo / step - 1e-9) * step, hi + 1e-9, step), 6)
    grid = grid[np.abs(grid - f0) > 1e-9]
    half = FL[i] + 1e-9 if FL[i] > 0 else np.inf                    # filtre de la candidate
    Fa, Ba = np.asarray(Fo, dtype=float), np.asarray(Bo, dtype=float)
    Ha = np.where(np.asarray(FLo) > 0, np.asarray(FLo) + 1e-9, np.inf) if len(Fo) else np.zeros(0)
    ok = np.ones(len(grid), dtype=bool)
    if len(Fa):                                                  # écart entre porteuses (le plus grand des deux)
        sp_ = np.maximum(SP[i], np.asarray(SPo))
        for k0 in range(0, len(grid), 4000):
            g = grid[k0:k0 + 4000]
            ok[k0:k0 + 4000] &= ~np.any(np.abs(g[:, None] - Fa[None, :]) - (Ba[None, :] + bi) / 2.0
                                        < sp_[None, :] - 1e-9, axis=1)
    txo = np.asarray([k for k, t in enumerate(To) if t], dtype=int)
    orders = pf_orders(tmax)
    if len(txo) >= 2 and orders:                                 # produits des autres qui tombent sur la candidate
        rows, _ = im_scan(Fa[txo], orders, max_tx, fmin=lo - 1.0, fmax=hi + 1.0, limit=400000, bws=Ba[txo])
        if rows:
            pv = np.array([r["f"] for r in rows])
            ph = np.array([r["hw"] for r in rows])
            pt = np.array([ti.get(im_class(r["order"], r["ntx"]), 0.0) for r in rows])
            pmin = np.array([min(Fa[txo][i_] for i_, _c in r["terms"]) for r in rows])
            pmax = np.array([max(Fa[txo][i_] for i_, _c in r["terms"]) for r in rows])
            keep = pt > 0
            pv, ph, pt, pmin, pmax = pv[keep], ph[keep], pt[keep], pmin[keep], pmax[keep]
            for k0 in range(0, len(grid), 2000):
                g = grid[k0:k0 + 2000]
                if len(pv):
                    hit = np.abs(g[:, None] - pv[None, :]) - ph[None, :] - bi / 2.0 < pt[None, :] - 1e-6
                    hit &= (g[:, None] - pmin[None, :] <= half) & (pmax[None, :] - g[:, None] <= half)
                    ok[k0:k0 + 2000] &= ~np.any(hit, axis=1)
    T2 = np.array([t.get("2tx3", 0.0) for t in TLo])[None, None, :] if len(Fo) else None
    T3 = np.array([t.get("3tx3", 0.0) for t in TLo])[None, None, :] if len(Fo) else None
    if T[i] and len(txo) >= 1 and len(Fa) and (tmax.get("2tx3", 0) > 0 or tmax.get("3tx3", 0) > 0):
        Ft, Bt = Fa[txo], Ba[txo]                                 # 3ᵉ ordre impliquant la candidate
        Hv = Ha[None, None, :]
        for k0 in range(0, len(grid), 500):
            g = grid[k0:k0 + 500][:, None, None]
            bad = np.zeros(g.shape[0], dtype=bool)
            vic, bv = Fa[None, None, :], Ba[None, None, :]
            if (T2 > 0).any():
                for val, hw in ((2 * g - Ft[None, :, None], (2 * bi + Bt[None, :, None]) / 2.0),
                                (2 * Ft[None, :, None] - g, (bi + 2 * Bt[None, :, None]) / 2.0)):
                    hit = (np.abs(val - vic) - hw - bv / 2.0 < T2 - 1e-6) & (T2 > 0)
                    hit &= np.abs(Ft[None, :, None] - vic) > 1e-9          # pas sur un émetteur du produit
                    hit &= (np.abs(g - vic) <= Hv) & (np.abs(Ft[None, :, None] - vic) <= Hv)   # filtre
                    bad |= hit.any(axis=(1, 2))
            if (T3 > 0).any() and max_tx >= 3 and len(Ft) >= 2:
                J, K = np.meshgrid(np.arange(len(Ft)), np.arange(len(Ft)), indexing="ij")
                m = (J != K).ravel()
                fj, fk = Ft[J.ravel()[m]], Ft[K.ravel()[m]]
                bj, bk = Bt[J.ravel()[m]], Bt[K.ravel()[m]]
                for val, hw in ((g + fj[None, :, None] - fk[None, :, None], (bi + bj + bk)[None, :, None] / 2.0),
                                (fj[None, :, None] + fk[None, :, None] - g, (bi + bj + bk)[None, :, None] / 2.0)):
                    hit = (np.abs(val - vic) - hw - bv / 2.0 < T3 - 1e-6) & (T3 > 0)
                    hit &= (np.abs(fj[None, :, None] - vic) > 1e-9) & (np.abs(fk[None, :, None] - vic) > 1e-9)
                    hit &= ((np.abs(g - vic) <= Hv) & (np.abs(fj[None, :, None] - vic) <= Hv)
                            & (np.abs(fk[None, :, None] - vic) <= Hv))
                    bad |= hit.any(axis=(1, 2))
            ok[k0:k0 + 500] &= ~bad
    cand = grid[ok]
    bvec = getattr(busy, "vec", None) if busy is not None else None
    if bvec is not None and len(cand):              # 7.60.2 : « occupé ? » sur toutes les candidates d'un coup
        cand = cand[~np.asarray(bvec(np.round(cand, 6)), dtype=bool)]
        busy = None
    cand = cand[np.lexsort((cand, np.round(np.abs(cand - f0), 6)))]     # le plus proche, puis le plus bas
    if skip is not None and len(cand):             # 7.60.2 : déjà examinées (fenêtre précédente de _pf_pick)
        cand = cand[(cand < skip[0] - 1e-9) | (cand > skip[1] + 1e-9)]
    out, checked = [], 0
    trunc = False
    for c in cand:
        c = round(float(c), 6)
        if busy is not None and busy(c):
            continue
        checked += 1
        if checked > max_check:
            trunc = True
            break
        iss, _ = pf_check(Fo + [c], To + [T[i]], Bo + [bi], SPo + [float(SP[i])], TLo + [ti], max_tx,
                          FLo + [float(FL[i])], IMo + [float(IMv[i])])           # vérification exacte
        if iss[-1] or sum(len(x) for x in iss[:-1]) > base_n:
            continue
        out.append((c, c - f0))
        if len(out) >= n:
            break
    if stats is not None:
        stats.update(checked=min(checked, max_check), trunc=trunc)
    return out


COORD_ORDERS = (("random", "🎲 Réparties au hasard (meilleur de 3 essais)"),
                ("random1", "🎲 Réparties au hasard (1 essai, plus rapide)"),
                ("low", "⬆ À la suite (la plus basse d'abord)"))
COORD_TRIES = {"random": 3, "random1": 1, "low": 1}


def _pf_pick(F, T, B, SP, TL, FL, new_sep, new_tol, new_filt, lo, hi, step, seed, busy, max_check, IM=None,
             new_img=0.0):
    """La fréquence compatible la plus proche de `seed` dans [lo, hi] (None si aucune). 7.60.2 : recherche par
    FENÊTRES qui s'élargissent autour de la graine (2, 6, 20, 60 MHz, puis tout) : pf_suggest ne contrôle plus
    toute la bande au pas de l'appareil à chaque ajout (40 fréquences = 7 min 30 avant) ; même résultat, car on
    garde la plus proche et une plus proche serait déjà dans la fenêtre."""
    budget, prev = int(max_check), None          # un seul budget de vérifications exactes pour toutes les fenêtres
    for w in (2.0, 6.0, 20.0, 60.0, None):
        a = lo if w is None else max(lo, seed - w)
        z = hi if w is None else min(hi, seed + w)
        if z - a < step:
            continue
        st = {}
        sg = pf_suggest(len(F), F + [seed], T + [True], B + [0.0], SP + [new_sep], TL + [new_tol], None,
                        lo=a, hi=z, step=step, n=1, busy=busy, max_check=budget, filt=FL + [new_filt],
                        skip=prev, stats=st, img=(list(IM) + [new_img]) if IM is not None else 0.0)
        if sg:
            return sg[0][0]
        budget -= int(st.get("checked", 0))
        if budget <= 0 or st.get("trunc") or w is None or (a <= lo and z >= hi):
            break
        prev = (a, z)                               # fenêtre entièrement examinée : la suivante la saute
    return None


def pf_fill(n_new, freqs, is_tx=None, bws=None, sep=PF_SEP, tol=None, filt=0.0, new_sep=PF_SEP, new_tol=None,
            new_filt=0.0, lo=470.0, hi=694.0, step=0.025, busy=None, max_check=800, order="low", rng=None,
            tick=None, cancel=None, img=0.0, new_img=0.0):
    """Coordination automatique : n_new fréquences compatibles avec le plan existant (freqs, réglages par fréquence
    comme pf_check) ET entre elles, pour un appareil (new_sep / new_tol / new_filt, pas `step`), dans [lo, hi],
    en évitant ce que busy(c) dit occupé. Ajout une par une, chaque ajout vérifié par pf_suggest (aucun problème pour
    elle, aucun nouveau pour les autres). order « low » : la plus basse compatible d'abord (tout se tasse en bas de
    la plage) ; « random » (7.60.2, Clément : « à la suite ça marche pas en général ») : à chaque ajout, la compatible
    la plus proche d'un point tiré AU HASARD dans la plage -> fréquences réparties. rng = np.random.Generator.
    tick() (7.61) : appelé à chaque fréquence trouvée (progression) ; cancel() -> True : arrêt.
    -> liste des MHz trouvés (peut être plus courte que n_new : bande pleine)."""
    F = [float(x) for x in freqs]
    m = len(F)
    T = [True] * m if is_tx is None else [bool(x) for x in is_tx]
    B = [0.0] * m if bws is None else [float(x or 0.0) for x in bws]

    def per(x, d):
        return list(x) if isinstance(x, (list, tuple)) else [x] * m
    SP, TL, FL = per(sep, PF_SEP), per(tol, None), per(filt, 0.0)
    IM = per(img, 0.0)                       # 7.68 : FI des récepteurs (fréquence image), comme pf_check
    rng = rng if rng is not None else np.random.default_rng()
    out = []
    for _k in range(int(n_new)):
        if cancel is not None and cancel():
            break
        if order == "low":
            c = _pf_pick(F, T, B, SP, TL, FL, new_sep, new_tol, new_filt, lo, hi, step, lo - step, busy, max_check,
                         IM, new_img)
        else:                                # _pf_pick finit par toute la plage : rien = vraiment plus de place
            c = _pf_pick(F, T, B, SP, TL, FL, new_sep, new_tol, new_filt, lo, hi, step,
                         float(rng.uniform(lo, hi)) + 1e-7, busy, max_check, IM, new_img)
        if c is None:
            break
        out.append(c)
        if tick is not None:
            tick()
        F.append(c)
        T.append(True)
        B.append(0.0)
        SP.append(new_sep)
        TL.append(new_tol)
        FL.append(new_filt)
        IM.append(new_img)
    return out


def _fill_score(got):
    """Pour garder le meilleur essai : le plus de fréquences trouvées, puis le plus grand écart minimum."""
    allf = sorted(c for g in got for c in g)
    gap = min((b - a for a, b in zip(allf, allf[1:])), default=0.0)
    return (len(allf), gap)


def pf_fill_lots(lots, freqs, is_tx=None, bws=None, sep=PF_SEP, tol=None, filt=0.0, busy=None, max_check=300,
                 order="low", tries=1, seed=None, progress=None, cancel=None, found=None, img=0.0):
    """Coordination entre appareils : plusieurs lots {n, sep, tol, filt, lo, hi, step} (ex. 8 × QLX-D + 6 × PSM 1000),
    cherchés l'un après l'autre ; chaque fréquence trouvée rejoint le plan avec les règles de SON appareil, donc les
    lots suivants doivent lui être compatibles (et elle à eux : pf_suggest vérifie les deux sens). order / tries
    (7.60.2) : « random » refait le tirage `tries` fois et garde le meilleur (_fill_score). progress(essai, total)
    et cancel() -> True (arrêt) sont facultatifs ; found(trouvées, demandées) (7.61) à chaque fréquence trouvée
    pendant l'essai en cours. -> une liste de MHz par lot (dans l'ordre des lots).
    Conseil : l'appareil le plus exigeant en premier."""
    rng = np.random.default_rng(seed)
    best = None
    n_try = max(1, int(tries)) if order != "low" else 1
    for t in range(n_try):
        if cancel is not None and cancel():
            break
        if progress is not None:
            progress(t + 1, n_try)
        F = [float(x) for x in freqs]
        m = len(F)
        T = [True] * m if is_tx is None else [bool(x) for x in is_tx]
        B = [0.0] * m if bws is None else [float(x or 0.0) for x in bws]

        def per(x):
            return list(x) if isinstance(x, (list, tuple)) else [x] * m
        SP, TL, FL, IM = per(sep), per(tol), per(filt), per(img)
        out = []
        want = sum(int(l.get("n", 0)) for l in lots)
        cnt = [0]

        def tick():
            cnt[0] += 1
            if found is not None:
                found(cnt[0], want)
        if found is not None:
            found(0, want)
        for lot in lots:
            got = pf_fill(int(lot.get("n", 0)), F, T, B, SP, TL, FL, lot.get("sep", PF_SEP), lot.get("tol"),
                          lot.get("filt", 0.0), lot.get("lo", 470.0), lot.get("hi", 694.0), lot.get("step", 0.025),
                          busy, max_check, order="low" if order == "low" else "random", rng=rng, tick=tick,
                          cancel=cancel, img=IM, new_img=float(lot.get("img") or 0.0))
            out.append(got)
            for c in got:
                F.append(c)
                T.append(True)
                B.append(0.0)
                SP.append(lot.get("sep", PF_SEP))
                TL.append(lot.get("tol"))
                FL.append(lot.get("filt", 0.0))
                IM.append(float(lot.get("img") or 0.0))
        if best is None or _fill_score(out) > _fill_score(best):
            best = out
        if sum(len(g) for g in out) >= sum(int(l.get("n", 0)) for l in lots) and order == "low":
            break
    return best if best is not None else [[] for _l in lots]


def coord_blockers(lo, hi, step, freqs, bws=None, sep_new=PF_SEP, seps=None, busy=None, allowed=None):
    """7.61 « pourquoi pas plus ? » : sur la grille [lo, hi] au pas `step`, qui bloque chaque fréquence possible,
    avec le plan FINAL (freqs = liste + trouvées) ? Une seule cause par point, dans cet ordre :
    hors des bandes autorisées du pays (allowed(c) faux), occupé d'après la mesure (busy(c) vrai : TNT, autre
    signal), trop près d'une fréquence du plan (écart, bord à bord), sinon « intermod » (ce qui reste n'a pas été
    retenu par le calcul : produits d'intermod sur elle, ou elle en créerait pour les autres).
    busy / allowed : prédicats, avec .vec (tableau -> tableau de bool) s'ils l'ont (rapide).
    -> dict(grid, illegal, busy, near, im) en nombre de points de grille."""
    out = dict(grid=0, illegal=0, busy=0, near=0, im=0)
    if hi <= lo or step <= 0:
        return out
    G = np.round(np.arange(math.ceil(lo / step - 1e-9) * step, hi + 1e-9, step), 6)
    out["grid"] = len(G)
    if not len(G):
        return out

    def ask(pred):
        if pred is None:
            return np.zeros(len(G), dtype=bool)
        v = getattr(pred, "vec", None)
        return np.asarray(v(G), dtype=bool) if v is not None else np.array([bool(pred(float(c))) for c in G])
    bad_reg = ~ask(allowed) if allowed is not None else np.zeros(len(G), dtype=bool)
    bad_busy = ask(busy) & ~bad_reg
    F = np.asarray(list(freqs), dtype=float)
    near = np.zeros(len(G), dtype=bool)
    if len(F):
        B = np.zeros(len(F)) if bws is None else np.asarray([float(b or 0.0) for b in bws])
        S = np.full(len(F), float(sep_new)) if seps is None else np.maximum(float(sep_new), np.asarray(seps, float))
        for k0 in range(0, len(G), 4000):
            g = G[k0:k0 + 4000]
            near[k0:k0 + 4000] = np.any(np.abs(g[:, None] - F[None, :]) - B[None, :] / 2.0 < S[None, :] - 1e-9, axis=1)
    near &= ~bad_reg & ~bad_busy
    out.update(illegal=int(bad_reg.sum()), busy=int(bad_busy.sum()), near=int(near.sum()))
    out["im"] = int(len(G) - out["illegal"] - out["busy"] - out["near"])
    return out


# 7.66.3 (Clément : « j'arrive pas à calculer des fréquences en plus, c'est le seuil auto ? ») : en seuil auto, le seuil
# global « typique » = bruit INSTANTANÉ + 13 dB ; comparé au MAX HOLD (des heures de pics de bruit) → 99 % « occupé ».
# Les outils qui lisent un spectre gardé / max hold ont leur propre seuil, calé sur le bruit de CE spectre.
BUSY_MODES = (("auto", "Auto : bruit du spectre + marge"), ("global", "Mon seuil « occupé »"), ("fixed", "Seuil fixe"))
BUSY_MARGIN = 15.0


def busy_lim(L, mode="auto", margin=BUSY_MARGIN, fixed=-80.0, glob=None):
    """Seuil « occupé » (dBm) pour éviter ce qu'un spectre (max hold, scan gardé) montre : « auto » = 10ᵉ centile du
    spectre (son bruit de fond) + marge ; « global » = le seuil de la fenêtre ; « fixed » = valeur donnée."""
    if mode == "fixed":
        return float(fixed)
    if mode == "global" and glob is not None:
        return float(glob)
    v = np.asarray(L if L is not None else [], dtype=float)
    v = v[np.isfinite(v)]
    if not len(v):
        return float(fixed if glob is None else glob)
    return float(np.percentile(v, 10)) + float(margin)


def coord_why_text(b, tr=None):
    """Phrase « ce qui bloque » d'après coord_blockers, la cause principale d'abord."""
    tr = tr or (lambda x: x)
    n = max(1, b.get("grid", 0))
    labs = (("illegal", tr("hors des bandes autorisées du pays")),
            ("busy", tr("occupé d'après la mesure (TNT, autre signal)")),
            ("near", tr("trop près d'une fréquence du plan (écart)")),
            ("im", tr("intermod (sur elle, ou elle en créerait pour les autres)")))
    parts = [(b.get(k, 0), lab) for k, lab in labs if b.get(k, 0)]
    parts.sort(key=lambda x: -x[0])
    return " · ".join(f"{lab} {100.0 * v / n:.0f} %" for v, lab in parts)


def coord_why_advice(b):
    """Conseil selon la cause principale de coord_blockers."""
    k = max(("illegal", "busy", "near", "im"), key=lambda x: b.get(x, 0))
    return {"illegal": "La plage sort souvent des bandes autorisées : choisis une plage dans les bandes du pays.",
            "busy": "La mesure voit la plage très chargée : élargis-la, ou décoche « éviter ce qui est occupé » "
                    "si le scan est ancien.",
            "near": "La plage est pleine d'émetteurs : élargis-la ou mets ce lot sur une autre plage.",
            "im": "C'est l'intermod qui bloque : un appareil plus robuste (tolérances plus serrées, filtre), moins "
                  "d'émetteurs dans la même zone, ou des règles plus souples."}[k]


def im3_clash(c, F, guard, guard3=None):
    """Collisions d'intermodulation 3e ordre mettant en jeu la fréquence candidate c (MHz) avec les émetteurs F.
    guard : tolérance des produits 2 TX (2A − B) ; guard3 : celle des 3 TX (A + B − C), = guard si absente.
    -> [(texte, écart en MHz)] ; vide = aucun risque."""
    g3 = guard if guard3 is None else guard3
    F = np.sort(np.asarray(F, dtype=float))
    n = len(F)
    out = []
    if n == 0:
        return out

    def nearest(v):
        k = np.searchsorted(F, v)
        lo, hi = np.clip(k - 1, 0, n - 1), np.clip(k, 0, n - 1)
        use_hi = np.abs(F[hi] - v) < np.abs(F[lo] - v)
        idx = np.where(use_hi, hi, lo)
        return idx, F[idx] - v

    ar = np.arange(n)
    # 2c − fj ≈ fk
    idx, d = nearest(2 * c - F)
    for j in np.nonzero((np.abs(d) <= guard) & (idx != ar))[0]:
        out.append((f"2×{c:.3f} − {F[j]:.3f} ≈ {F[idx[j]]:.3f}", float(d[j])))
    # 2fj − c ≈ fk
    idx, d = nearest(2 * F - c)
    for j in np.nonzero((np.abs(d) <= guard) & (idx != ar))[0]:
        out.append((f"2×{F[j]:.3f} − {c:.3f} ≈ {F[idx[j]]:.3f}", float(d[j])))
    if n >= 2:
        J, K = np.meshgrid(ar, ar, indexing="ij")
        # c + fj − fk ≈ fl
        idx, d = nearest(c + F[J] - F[K])
        m = (J != K) & (idx != J) & (idx != K) & (np.abs(d) <= g3)
        for j, k in zip(*np.nonzero(m)):
            out.append((f"{c:.3f} + {F[j]:.3f} − {F[k]:.3f} ≈ {F[idx[j, k]]:.3f}", float(d[j, k])))
        # fj + fk − c ≈ fl
        idx, d = nearest(F[J] + F[K] - c)
        m = (J < K) & (idx != J) & (idx != K) & (np.abs(d) <= g3)
        for j, k in zip(*np.nonzero(m)):
            out.append((f"{F[j]:.3f} + {F[k]:.3f} − {c:.3f} ≈ {F[idx[j, k]]:.3f}", float(d[j, k])))
    out.sort(key=lambda t: abs(t[1]))
    return out


def find_free(F, L, a, b, existing, n=3, width=0.2, min_sep=0.3, thr=-90.0, guard=0.2, grid=0.025,
              max_check=600, guard3=None, emitters=None, filt=0.0, im3=True, alt=True, allowed=None):
    """Cherche n fréquences libres entre a et b (MHz) d'après un spectre mesuré (F trié, L en dBm) :
    niveau max sur ± width/2 sous thr, à plus de min_sep de toute fréquence existante ou déjà choisie,
    et sans intermodulation 3e ordre à ± guard avec les ÉMETTEURS (emitters, défaut = existing ; une réserve
    « doit rester libre » n'émet pas). filt (MHz) : filtre du récepteur, seuls les émetteurs à ± filt / 2 de la
    candidate comptent (0 = tous). im3=False : 2A − B seulement (A + B − C ignoré), guard=None : pas d'intermod.
    alt : s'il en manque, des « moins mauvaises » sont proposées (clé warn : ce qui cloche).
    allowed : prédicat c -> True si la candidate est dans une plage autorisée du pays (7.60, reg_allowed_pred) ;
    les autres ne sont jamais proposées, même en « moins mauvaises ».
    -> (liste de dict(f, level, dist[, warn]), diag)"""
    ex = sorted(float(x) for x in existing)
    em = sorted(float(x) for x in (existing if emitters is None else emitters))
    diag = dict(grille=0, sans_mesure=0, bruyantes=0, trop_proches=0, intermod=0, alternatives=0, hors_bandes=0)
    res = []
    if F is None or len(F) == 0 or b <= a:
        return res, diag
    cand = np.arange(a, b + 1e-9, grid)
    diag["grille"] = len(cand)
    near = max(grid, float(np.median(np.diff(F)))) if len(F) > 1 else grid
    lv = np.full(len(cand), np.nan)
    for i, c in enumerate(cand):
        x = level_at(F, L, float(c), width / 2.0, near=near)
        if x is not None:
            lv[i] = x
    diag["sans_mesure"] = int(np.isnan(lv).sum())
    if allowed is not None:                     # 7.60 : hors des plages autorisées du pays = jamais proposée
        legal = np.array([bool(allowed(float(c))) for c in cand], dtype=bool)
        diag["hors_bandes"] = int((~legal).sum())
        diag["sans_mesure"] = int((np.isnan(lv) & legal).sum())
        lv[~legal] = np.nan
    good = ~np.isnan(lv)
    quiet = good & (lv <= thr)
    diag["bruyantes"] = int((good & ~quiet).sum())
    exa = np.array(ex)
    ema = np.array(em)
    g3 = (guard if guard3 is None else guard3) if im3 else -1.0

    def dist_to(c, arr):
        return float(np.min(np.abs(arr - c))) if len(arr) else 1e9

    def clashes(c, chosen):
        if guard is None:
            return []
        e = np.concatenate([ema, np.array(chosen, dtype=float)])
        if filt and filt > 0:
            e = e[np.abs(e - c) <= filt]
        return im3_clash(c, e, guard, g3)

    order = [i for i in np.nonzero(quiet)[0]]
    order.sort(key=lambda i: (round(float(lv[i])), -dist_to(float(cand[i]), exa)))
    chosen, rej_im = [], []
    for i in order[:max_check]:
        c = float(cand[i])
        allf = np.array(ex + chosen)
        if dist_to(c, allf) < min_sep:
            diag["trop_proches"] += 1
            continue
        cl = clashes(c, chosen)
        if cl:
            diag["intermod"] += 1
            rej_im.append((len(cl), float(lv[i]), c, cl[0][0]))
            continue
        chosen.append(c)
        res.append(dict(f=c, level=float(lv[i]), dist=dist_to(c, exa)))
        if len(res) >= n:
            break
    if alt and len(res) < n:
        # pas assez de parfaites : les moins mauvaises, d'abord le moins d'intermod, puis le moins de niveau
        noisy = [(0, float(lv[i]), float(cand[i]), None) for i in np.nonzero(good & ~quiet)[0]]
        pool = sorted(rej_im) + sorted(noisy, key=lambda x: x[1])
        for k, lvl, c, why in pool:
            if len(res) >= n:
                break
            if dist_to(c, np.array(ex + chosen)) < min_sep:
                continue
            w = (f"intermod ×{k} : {why}" if why else f"niveau {lvl:.1f} dBm > {thr:.1f}")
            chosen.append(c)
            res.append(dict(f=c, level=lvl, dist=dist_to(c, exa), warn=w))
            diag["alternatives"] += 1
    return res, diag


# ------------------------------------------------- nommage rapide
NAME_WORDS = ["MIC", "HF", "IEM", "Intercom", "Bolero", "Beltpack", "Talkback", "Walkie", "PMR", "Chant", "Lead",
              "Backing", "Chœur", "Guitare", "Basse", "Clavier", "Batterie", "Kick", "Snare", "Overhead",
              "Cuivres", "Sax", "Trompette", "Violon", "Orateur", "Présentateur", "Cravate", "Serre-tête",
              "Main", "Ear", "Retour", "Wedge", "Sidefill", "Instrument", "Antenne", "Combiner", "Caméra",
              "Régie", "Plateau", "Prod", "Sécu", "Catering", "Backline", "Danseur", "Comédien"]
SCENE_WORDS = ["Main Stage", "Scène 1", "Scène 2", "Scène 3", "Grande scène", "Petite scène", "Chapiteau",
               "Club", "Plateau TV", "Conférence", "Régie FOH", "Régie MON", "Backstage", "Production",
               "Sécurité", "Catering", "Intermod"]
GROUP_WORDS = ["Groupe 1", "Groupe 2", "Groupe 3", "Artiste 1", "Headliner", "Support 1", "Support 2",
               "Changeover", "Retours MON", "Intercom", "Production", "Sécurité", "Backline", "Régie", "Plateau",
               "Orchestre", "Danseurs", "Présentateur", "Conférenciers", "Technique"]
_LABEL_RE = re.compile(r"^(.*?)([\s\-_.:]*)(\d+)$")


def parse_label(s):
    """'HF 12' -> ('HF', ' ', 12, 0) ; 'MIC03' -> ('MIC', '', 3, 2) ; 'HF-3' -> ('HF', '-', 3, 0) ;
    'Bolero' -> ('Bolero', '', None, 0). La largeur (4e valeur) n'est non nulle que s'il y a des zéros de
    remplissage. Un nombre seul ('470.125') n'est pas un numéro."""
    s = str(s).strip()
    m = _LABEL_RE.match(s)
    if not m or not m.group(1).strip() or re.fullmatch(r"[\d.,\s]+", m.group(1)):
        return s, "", None, 0
    d = m.group(3)
    return m.group(1), m.group(2), int(d), len(d) if d.startswith("0") and len(d) > 1 else 0


def make_label(base, n, width=0, sep=" "):
    base = str(base).strip()
    num = f"{n:0{width}d}" if width else str(n)
    return f"{base}{sep}{num}"


def next_free_number(base, names):
    """Plus grand numéro déjà utilisé avec ce mot de base (sans tenir compte de la casse), + 1."""
    key = str(base).strip().lower()
    best = 0
    for nm in names:
        b, _s, n, _w = parse_label(nm)
        if n is not None and b.strip().lower() == key:
            best = max(best, n)
    return best + 1


def number_run(first, count, step=1):
    """Numérotation « vers le bas » : 'HF 1' -> ['HF 1', 'HF 2', …] ; 'MIC 08' garde sa largeur ;
    un nom sans numéro ('Bolero') est numéroté à partir de 1."""
    base, sep, n, w = parse_label(first)
    if n is None:
        n, sep = 1, " "
    return [make_label(base, n + i * step, w, sep) for i in range(max(0, count))]


def label_words(names):
    """Mots de base utilisés dans une liste de noms (pour apprendre le vocabulaire)."""
    out, seen = [], set()
    for nm in names:
        b, _s, n, _w = parse_label(nm)
        b = b.strip()
        if n is not None and b and b.lower() not in seen and len(b) <= 24 and not re.fullmatch(r"[\d.,\s]+", b):
            seen.add(b.lower())
            out.append(b)
    return out


def name_candidates(vocab, names):
    """Liste de propositions pour l'auto-complétion : chaque mot seul, avec son prochain numéro libre,
    puis les noms déjà utilisés."""
    out, seen = [], set()

    def add(x):
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    for w in vocab:
        add(w)
        add(make_label(w, next_free_number(w, names)))
    for nm in names:
        add(str(nm))
    return out


def suggest_labels(prefix, vocab, names, limit=12):
    """Ce qui est proposé quand on tape `prefix` (tri : début de mot, puis contient)."""
    p = str(prefix).strip().lower()
    c = name_candidates(vocab, names)
    if not p:
        return c[:limit]
    a = [x for x in c if x.lower().startswith(p)]
    b = [x for x in c if p in x.lower() and not x.lower().startswith(p)]
    return (a + b)[:limit]




# ------------------------------------------------- scans WSM / WWB : import, export, conversion
def _scan_float(tok):
    try:
        return float(str(tok).strip().strip('"').replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _scan_tokens(ln):
    if ";" in ln:
        toks = ln.split(";")
    elif "\t" in ln:
        toks = ln.split("\t")
    else:
        toks = re.split(r"[,\s]+", ln)
    return [t.strip().strip('"') for t in toks if t.strip()]


def _scan_unit_hint(text):
    low = text.lower()
    for key, unit in (("(khz)", "kHz"), ("(mhz)", "MHz"), ("(hz)", "Hz"), ("(ghz)", "GHz")):
        if key in low:
            return unit
    return None


def scan_unit_scale(freqs, hint=None):
    """Facteur qui convertit les fréquences d'un fichier de scan en MHz : l'unité de l'en-tête si elle est
    écrite, sinon l'ordre de grandeur (WSM écrit des kHz : 470000 = 470 MHz)."""
    if hint in ("Hz", "kHz", "MHz", "GHz"):
        return {"Hz": 1e-6, "kHz": 1e-3, "MHz": 1.0, "GHz": 1e3}[hint]
    if not len(freqs):
        return 1.0
    med = float(np.median(np.abs(np.asarray(freqs, dtype=float))))
    if med > 6.0e6:
        return 1e-6
    if med > 6500.0:
        return 1e-3
    return 1.0


def parse_sdb3(raw):
    """Scan Shure WWB natif (.sdb3, « //@ShureScan ») : en-tête JSON (plages en kHz, BitWidth, Scale Factor,
    NoDataValue), puis « @Binary: » = balayages « @Swp » (id, horodatage, niveaux entiers signés big-endian / Scale
    Factor = dBm, CRC16), puis « @Extended: » (infos WWB), « @End ». Plusieurs balayages -> max hold (le pire cas).
    -> (F MHz, L dBm, info). Format déduit d'un vrai fichier (WWB 7, SLXD4) : pas de doc Shure publique."""
    import json
    raw = bytes(raw).lstrip(b"\xef\xbb\xbf")
    i = raw.find(b"@Binary:")
    if not raw.startswith(b"//@ShureScan") or i < 0:
        raise ValueError("ce n'est pas un scan WWB (.sdb3)")
    head = json.loads(raw[raw.index(b"{"):i].decode("utf-8", "replace"))
    j = raw.find(b"@Extended:", i)
    data = raw[i + 8: j if j > 0 else len(raw)]
    fmul = {"hz": 1e-6, "khz": 1e-3, "mhz": 1.0, "ghz": 1e3}.get(str(head.get("FreqUnits", "KHz")).lower(), 1e-3)
    bw = int(head.get("BitWidth", 16)) // 8
    scale = float(head.get("Scale Factor", 10) or 1)
    nodata = head.get("NoDataValue")
    lay, fr = [], None                     # (octets, None) champ simple ; (n points, fréquences) courbe
    for el in head.get("BinarySchema", []):
        if "Curve" in el:
            fs = []
            for r in el["Curve"].get("FreqRanges", []):
                a_, b_, st = float(r["StartFreq"]), float(r["EndFreq"]), float(r["StepFreq"])
                fs.append(a_ + st * np.arange(int(round((b_ - a_) / st)) + 1))
            f_ = np.concatenate(fs) * fmul if fs else np.zeros(0)
            lay.append((len(f_) * bw, f_))
            if fr is None or el["Curve"].get("CoordinationSource"):
                fr = (len(lay) - 1, f_)
        else:
            lay.append((int(el.get("Bytes", 0)), None))
    if fr is None or not len(fr[1]):
        raise ValueError("scan WWB sans courbe de mesure")
    rec = sum(n for n, _ in lay)
    off = sum(n for n, _ in lay[:fr[0]])
    sweeps = []
    k = data.find(b"@Swp")
    while k >= 0 and k + rec <= len(data):
        v = np.frombuffer(data, dtype=f">i{bw}", count=len(fr[1]), offset=k + off).astype(float)
        if nodata is not None:
            v[v == float(nodata)] = np.nan
        sweeps.append(v / scale)
        k = data.find(b"@Swp", k + rec)
    if not sweeps:
        raise ValueError("scan WWB sans balayage")
    with np.errstate(all="ignore"):
        L = np.nanmax(np.vstack(sweeps), axis=0)
    ok_ = np.isfinite(L)
    F, L = fr[1][ok_], L[ok_]
    o = np.argsort(F, kind="stable")
    name = " · ".join(x for x in (head.get("ScannerName"), head.get("Title")) if x)
    return F[o], L[o], dict(fmt="sdb3", n=len(F), unit="kHz", title=name,
                            note=f"scan WWB natif (.sdb3) : {len(sweeps)} balayage(s), max gardé")


def parse_scan_text(text):
    """Lit un scan de fréquences : export WSM (Sennheiser) ou fichier « fréquence, niveau » (WWB, notre export…).
    -> (F en MHz croissant, L en dBm, info) ; ValueError avec un message clair si ce n'est pas un scan."""
    text = str(text).lstrip("﻿")
    if text.startswith("//@ShureScan"):                       # .sdb3 lu par decode_text en latin-1
        return parse_sdb3(text.encode("latin-1"))
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # --- Wisycom Manager : « Freq2D;RFA;RFB;MaxRFA;MaxRFB », puis « N;début kHz;fin kHz;min;max », puis MHz et dBµV
    #     (vrai fichier de Clément, 7.32.1) : le plus fort des 4 colonnes, converti en dBm (dBm = dBµV − 107)
    head0 = lines[0].strip().lower().replace(" ", "") if lines else ""
    if head0.startswith("freq2d;"):
        F, L = [], []
        for ln2 in lines[2:]:
            cs = [_scan_float(c.strip().strip('"')) for c in ln2.split(";")]
            if len(cs) < 2 or cs[0] is None:
                continue
            vals = [v for v in cs[1:] if v is not None]
            if vals:
                F.append(cs[0])
                L.append(max(vals) - 107.0)
        if len(F) < 5:
            raise ValueError("fichier Wisycom reconnu, mais je ne trouve pas de points de mesure")
        F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
        o = np.argsort(F, kind="stable")
        return F[o], L[o], dict(fmt="wisycom", n=len(F), unit="MHz",
                                note="scan Wisycom : le plus fort des voies A / B (et de leurs max), dBµV convertis en dBm "
                                     "(dBm = dBµV − 107)")
    # --- export WSM : métadonnées (RFUnit…), « Frequency;RF level (%);RF level », fréquences en kHz. Vrai fichier WSM
    #     (Clément, 7.32.1) : colonne % vide, niveau en dB (dBµV, « RFUnit;dB ») ; ancien format : niveau en %
    #     (0 % = −120 dBm, 100 % = 0 dBm)
    rf_db = any(re.match(r"\s*rfunit\s*;\s*db", x.lower()) for x in lines[:40])
    for k, ln in enumerate(lines[:80]):
        cells = [c.strip().strip('"') for c in ln.split(";")]
        low = [c.lower() for c in cells]
        if len(cells) >= 2 and low[0].startswith("freq") and any("rf level" in c or "(%)" in c for c in low[1:]):
            pcts = [i for i, c in enumerate(low) if i > 0 and "(%)" in c]
            col_pct = next((i for i in pcts if "rf level" in low[i]), pcts[0] if pcts else None)
            col_db = next((i for i, c in enumerate(low) if i > 0 and "rf level" in c and "(%)" not in c), None)
            F, L, used = [], [], set()
            for ln2 in lines[k + 1:]:
                cs = [c.strip().strip('"') for c in ln2.split(";")]
                f = _scan_float(cs[0]) if cs else None
                v_db = _scan_float(cs[col_db]) if col_db is not None and len(cs) > col_db else None
                v_pc = _scan_float(cs[col_pct]) if col_pct is not None and len(cs) > col_pct else None
                if f is None or (v_db is None and v_pc is None):
                    if F:
                        break
                    continue
                F.append(f)
                if v_db is not None and (rf_db or v_pc is None):
                    L.append(v_db - 107.0 if rf_db else v_db)
                    used.add("db")
                else:
                    L.append(v_pc * 1.2 - 120.0)
                    used.add("pct")
            if len(F) < 5:
                raise ValueError("l'en-tête WSM est là, mais je ne trouve pas de points de mesure en dessous")
            F = np.asarray(F, dtype=float)
            F = F * scan_unit_scale(F, _scan_unit_hint(ln) or ("kHz" if float(np.median(F)) > 10000 else None))
            L = np.asarray(L, dtype=float)
            o = np.argsort(F, kind="stable")
            note = ("export WSM : niveau en dB µV converti en dBm (dBm = dBµV − 107)" if "db" in used and rf_db else
                    "export WSM : niveau lu tel quel (dBm)" if "db" in used else
                    "export WSM : niveau en % converti en dBm (0 % = −120 dBm, 100 % = 0 dBm)")
            return F[o], L[o], dict(fmt="wsm", n=len(F), unit="kHz", note=note)
    # --- fichier simple : « fréquence, niveau » (WWB), « fréquence;niveau », tabulations, avec ou sans en-tête
    F, L, hint, head = [], [], None, ""
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        toks = _scan_tokens(s)
        a = _scan_float(toks[0]) if len(toks) >= 2 else None
        b = _scan_float(toks[1]) if len(toks) >= 2 else None
        if a is None or b is None:
            if F:
                break
            hint = hint or _scan_unit_hint(s)
            head += " " + s.lower()
            continue
        if F and a < F[-1]:
            if len(F) < 3:
                F, L = [], []
            else:
                break
        F.append(a)
        L.append(b)
    if len(F) < 5:
        raise ValueError("je ne trouve pas de lignes « fréquence, niveau » dans ce fichier")
    F = np.asarray(F, dtype=float)
    L = np.asarray(L, dtype=float)
    unit = hint or ""
    F = F * scan_unit_scale(F, hint)
    note = ""
    if re.search(r"db\s*[µμu]v", head):                  # Wisycom Manager peut exporter en dBµV (50 Ω)
        L = L - 107.0
        note = "niveaux en dBµV convertis en dBm (dBm = dBµV − 107, 50 Ω)"
    elif float(np.nanmax(L)) > 30.0:
        note = "niveaux supérieurs à 30 : ce ne sont peut-être pas des dBm (des dBµV ? dBm = dBµV − 107)"
    o = np.argsort(F, kind="stable")
    return F[o], L[o], dict(fmt="simple", n=len(F), unit=unit, note=note)


def wwb_scan_text(F, L):
    """Texte d'import de scan pour WWB, comme ses propres exports (vrai fichier de Clément, 7.32.1) : « 470.000,-104.531 »
    (MHz à 3 décimales, virgule, dBm), sans en-tête."""
    out = []
    for f, l in zip(F, L):
        f, l = float(f), float(l)
        if math.isfinite(f) and math.isfinite(l):
            out.append(f"{f:.3f},{l:.3f}")
    return "\n".join(out) + "\n"


def scan_uniform(F, L, step):
    """Scan remis sur une grille régulière au pas `step` MHz (WSM et Wisycom l'attendent) : le plus fort dans chaque
    case ; une case vide prend la valeur interpolée dans une même bande, sinon (trou entre deux bandes) le plancher
    du scan. -> (G, V)."""
    F, L = _valid(F, L)
    o = np.argsort(F, kind="stable")
    F, L = F[o], L[o]
    step = max(float(step), 1e-6)
    lo = math.floor(F[0] / step + 1e-9) * step
    n = int(round((F[-1] - lo) / step)) + 1
    G = lo + np.arange(n) * step
    V = np.full(n, -np.inf)
    np.maximum.at(V, np.clip(np.round((F - lo) / step).astype(int), 0, n - 1), L)
    empty = ~np.isfinite(V)
    if empty.any():
        cuts = [0, *scan_gaps(F), len(F)]
        filled = np.full(n, float(np.min(L)))
        for a, b in zip(cuts[:-1], cuts[1:]):
            inside = (G >= F[a]) & (G <= F[b - 1])
            filled[inside] = np.interp(G[inside], F[a:b], L[a:b])
        V[empty] = filled[empty]
    return G, V


def _scan_step(F, default):
    d = np.diff(np.sort(np.asarray(F, dtype=float)))
    d = d[d > 1e-9]
    return float(np.median(d)) if len(d) else default


# ------------------------------------------------- convertisseur de scans (entrée / sortie au choix)
SCAN_LEVEL_UNITS = [("dbm", "dBm"), ("dbuv", "dBµV"), ("pct", "% (échelle WSM : 0 % = −120 dBm, 100 % = 0 dBm)")]
SCAN_FREQ_UNITS = ["auto", "Hz", "kHz", "MHz", "GHz"]
SCAN_SEPS = [("auto", "auto"), (";", "point-virgule ;"), (",", "virgule ,"), ("\t", "tabulation"), (" ", "espace")]


def parse_scan_custom(text, sep="auto", fcol=0, lcol=1, funit="auto", lunit="dbm", skip=0, dec="auto"):
    """Lit un scan CSV « à la main » : colonnes (comptées à partir de 0), unités, lignes d'en-tête à sauter.
    Les lignes illisibles (en-têtes, pieds de page) sont ignorées. -> (F MHz croissant, L dBm, info)."""
    text = str(text).lstrip("\ufeff")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")[max(0, int(skip)):]
    F, L, hint = [], [], None
    for ln in lines:
        s_ = ln.strip()
        if not s_:
            continue
        if sep == "auto":
            toks = _scan_tokens(s_)
        else:
            toks = [t.strip().strip('"') for t in (s_.split(sep) if sep != " " else s_.split())]
        if len(toks) <= max(fcol, lcol):
            hint = hint or _scan_unit_hint(s_)
            continue
        a, b = toks[fcol], toks[lcol]
        if dec == ".":
            a, b = a.replace(",", ""), b.replace(",", "")
        f, l = _scan_float(a), _scan_float(b)
        if f is None or l is None:
            hint = hint or _scan_unit_hint(s_)
            continue
        F.append(f)
        L.append(l)
    if len(F) < 2:
        raise ValueError("je ne trouve pas de lignes lisibles avec ces colonnes / ce séparateur")
    F = np.asarray(F, dtype=float)
    L = np.asarray(L, dtype=float)
    F = F * scan_unit_scale(F, hint if funit == "auto" else funit)
    L = np.asarray([from_unit(float(v), lunit) for v in L], dtype=float)
    o = np.argsort(F, kind="stable")
    return F[o], L[o], dict(fmt="custom", n=len(F), unit=funit, note="")


class UndoStack:
    """↶ / ↷ Annuler / rétablir par instantanés : track(état, signature) est appelé régulièrement ; quand la signature
    change, l'état d'avant est mis de côté. back() / fwd() -> l'état à remettre (ou None). Après une remise, resync(sig)
    recale la signature (l'état relu peut s'écrire un peu autrement) sans créer de nouveau retour."""

    def __init__(self, limit=60):
        self.limit = int(limit)
        self.undo, self.redo, self.cur = [], [], None

    def track(self, state, sig):
        if self.cur is None:
            self.cur = (sig, state)
            return False
        if sig == self.cur[0]:
            return False
        self.undo.append(self.cur)
        del self.undo[:-self.limit]
        self.redo.clear()
        self.cur = (sig, state)
        return True

    def back(self):
        if not self.undo:
            return None
        self.redo.append(self.cur)
        self.cur = self.undo.pop()
        return self.cur[1]

    def fwd(self):
        if not self.redo:
            return None
        self.undo.append(self.cur)
        self.cur = self.redo.pop()
        return self.cur[1]

    def resync(self, sig):
        if self.cur is not None:
            self.cur = (sig, self.cur[1])


def scan_crop(F, *cols, lo=None, hi=None):
    """Garde seulement [lo, hi] MHz d'un scan (et de ses colonnes de niveaux) : pour n'exporter vers le logiciel de coord / WWB /
    WSM que la bande utile. lo / hi None = pas de limite ; bornes inversées remises dans l'ordre.
    -> (F, *cols) en tableaux numpy (vides si rien dans la plage)."""
    F = np.asarray(F, dtype=float)
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    m = np.ones(len(F), dtype=bool)
    if lo is not None:
        m &= F >= float(lo) - 1e-9
    if hi is not None:
        m &= F <= float(hi) + 1e-9
    return (F[m], *[np.asarray(c, dtype=float)[m] for c in cols])


def scan_write(F, L, fmt="wwb", sep=";", dec=",", funit="MHz", lunit="dbm", header=True, title=""):
    """Écrit un scan comme les vrais exports (fichiers de Clément, 7.32) : « wwb », « wsm », « wisycom », « tti »,
    ou « csv » (personnalisé : séparateur, décimale, unités, en-tête)."""
    if fmt == "wwb":
        return wwb_scan_text(F, L)
    if fmt == "tti":                              # TTI (vrai fichier de Clément) : « 470.0000,-88.0 », CRLF
        return "".join(f"{float(f):.4f},{float(l):.1f}\r\n" for f, l in zip(F, L)
                       if math.isfinite(float(f)) and math.isfinite(float(l)))
    if fmt == "wsm":                              # comme un vrai export WSM (Clément, 7.32.1) : kHz, niveau en dB µV
        stp = max(1.0, round(_scan_step(F, 0.025) * 1000.0))          # pas entier en kHz
        G, V = scan_uniform(F, L, stp / 1000.0)
        now = title or "RF Technical Monitor"
        meta = [("Receiver", "tinySA"), ("Date/Time", ""), ("RFUnit", "dB"), ("Owner", ""), ("ScanCity", ""),
                ("ScanComment", "RF Technical Monitor"), ("ScanCountry", ""), ("ScanDescription", ""),
                ("ScanInteriorExterior", ""), ("ScanLatitude", ""), ("ScanLongitude", ""), ("ScanName", now),
                ("ScanPostalCode", "")]
        out = [f"{k};{v}" for k, v in meta] + [
            "", f"Frequency Range [kHz];{G[0] * 1000:.0f};{G[-1] * 1000:.0f};{stp:.0f}", "Frequency;RF level (%);RF level"]
        out += [f"{g * 1000:.0f};;{int(round(v + 107.0))}" for g, v in zip(G, V)]
        return "\r\n".join(out) + "\r\n"
    if fmt == "wisycom":                          # comme Wisycom Manager (Clément) : MHz, 4 colonnes en dBµV
        stp = max(0.01, math.floor(_scan_step(F, 0.1) * 100 + 1e-6) / 100)   # pas en 1/100 MHz (2 décimales)
        G, V = scan_uniform(F, L, stp)
        out = ["Freq2D;RFA;RFB;MaxRFA;MaxRFB", f"{len(G)};{G[0] * 1000:.2f};{G[-1] * 1000:.2f};-10.00;70.00"]
        for g, v in zip(G, V):
            u = f"{v + 107.0:.2f}"
            out.append(f"{g:.2f};{u};{u};{u};{u}")
        return "\r\n".join(out) + "\r\n"
    div = {"Hz": 1e-6, "kHz": 1e-3, "MHz": 1.0, "GHz": 1e3}.get(funit, 1.0)
    nd = {"Hz": 0, "kHz": 3, "MHz": 6, "GHz": 9}.get(funit, 6)
    sp = sep
    lu = dict(SCAN_LEVEL_UNITS).get(lunit, "dBm").split(" ")[0]
    out = [sp.join([f"Fréquence ({funit})", f"Niveau ({lu})"])] if header else []
    for f, l in zip(F, L):
        f, l = float(f), float(l)
        if not (math.isfinite(f) and math.isfinite(l)):
            continue
        a, b = f"{f / div:.{nd}f}", f"{to_unit(l, lunit):.1f}"
        if dec == ",":
            a, b = a.replace(".", ","), b.replace(".", ",")
        out.append(sp.join([a, b]))
    return "\r\n".join(out) + "\r\n"


def wsm_to_wwb_text(text):
    """Export WSM (ou tout scan lisible) -> texte pour WWB. -> (texte, info)."""
    F, L, info = parse_scan_text(text)
    return wwb_scan_text(F, L), info


# ------------------------------------------------- alarmes : acquittement, priorités
ALARM_PRIO = {2: "Critique", 1: "Normale", 0: "Info"}
ALARM_ORDER = (2, 1, 0)


SIM_MARK = "🧪 "              # 8.1 : préfixe de tout ce qui vient d'une source simulée (démo tinySA / SDR démo)


class AlarmBook:
    """Registre des alarmes : une alarme par (type, fréquence), qui reste affichée jusqu'à ce que la cause
    disparaisse ; l'acquittement coupe le son sans l'effacer."""

    def __init__(self, repeat_s=10.0):
        self.active = {}          # clé -> alarme en cours
        self.done = []            # alarmes terminées (les plus récentes en dernier)
        self.seq = 0
        self.repeat_s = float(repeat_s)
        self.sim = False          # 8.1 : source SIMULÉE (démo) en ce moment -> les nouvelles alarmes sont marquées

    def raise_(self, key, kind, name, freq, prio, now, level=None, layer="", info=""):
        """Déclenche l'alarme. -> True si elle est NOUVELLE (c'est là qu'on fait du bruit)."""
        a = self.active.get(key)
        if a is not None:
            a["t_last"] = now
            if level is not None:
                a["level"] = level
            a["prio"] = prio
            return False
        self.seq += 1
        if self.sim:              # 8.1 : jamais une alarme de démo prise pour une vraie (liste, mode Show, web, alertes)
            name, info = SIM_MARK + name, ("simulé (démo) · " + info) if info else "simulé (démo)"
        self.active[key] = dict(id=self.seq, key=key, kind=kind, name=name, freq=freq, prio=int(prio), t0=now,
                                t_last=now, t_end=None, level=level, layer=layer, info=info, acked=False,
                                last_sound=now, sim=bool(self.sim))
        return True

    def clear(self, key, now):
        a = self.active.pop(key, None)
        if a is None:
            return None
        a["t_end"] = now
        self.done.append(a)
        del self.done[:-200]
        return a

    def ack(self, aid):
        for a in self.active.values():
            if a["id"] == aid:
                a["acked"] = True
                return True
        return False

    def ack_all(self):
        n = 0
        for a in self.active.values():
            if not a["acked"]:
                a["acked"] = True
                n += 1
        return n

    def unacked(self):
        return [a for a in self.active.values() if not a["acked"]]

    def listing(self):
        """Alarmes à afficher : en cours (non acquittées d'abord, appareil perdu en tête, par priorité), puis
        terminées (récentes d'abord)."""
        cur = sorted(self.active.values(), key=lambda a: (a["acked"], a["kind"] != "APPAREIL", -a["prio"], a["t0"]))
        return cur + list(reversed(self.done))

    def due_repeat(self, now):
        """Alarmes critiques toujours non acquittées dont le son doit être rejoué."""
        out = []
        for a in self.active.values():
            if self.repeat_s > 0 and a["prio"] >= 2 and not a["acked"] and now - a["last_sound"] >= self.repeat_s:
                a["last_sound"] = now
                out.append(a)
        return out

    def purge_done(self):
        n = len(self.done)
        self.done.clear()
        return n

    def reset(self):
        self.active.clear()
        self.done.clear()

    def counts(self):
        un = self.unacked()
        return len(un), len(self.active), max([a["prio"] for a in un], default=-1)


# ------------------------------------------------- relecture : mémoire tampon des balayages
class SweepStore:
    """Mémorise les derniers balayages de chaque bande (temps, fréquences, niveaux) pour les revoir."""

    def __init__(self, seconds=1800.0, max_mb=300.0):
        self.seconds = float(seconds)
        self.max_bytes = int(max_mb * 1e6)
        self.t, self.d = {}, {}
        self.bytes = 0

    def add(self, bid, t, f, l):
        l32 = np.array(l, dtype=np.float32)
        ts, ds = self.t.setdefault(bid, []), self.d.setdefault(bid, [])
        if ds and ds[-1][0].shape == np.shape(f) and ds[-1][0][0] == f[0] and ds[-1][0][-1] == f[-1]:
            fr = ds[-1][0]
        else:
            fr = np.array(f, dtype=np.float64)
        if ts and t < ts[-1]:
            return
        ts.append(float(t))
        ds.append((fr, l32))
        self.bytes += l32.nbytes
        k = bisect.bisect_left(ts, t - self.seconds)
        if k:
            self.bytes -= sum(x[1].nbytes for x in ds[:k])
            del ts[:k]
            del ds[:k]
        while self.bytes > self.max_bytes:
            heads = [(self.t[b][0], b) for b in self.t if self.t[b]]
            if not heads:
                break
            _t0, b = min(heads)
            self.bytes -= self.d[b][0][1].nbytes
            del self.t[b][0]
            del self.d[b][0]

    def span(self):
        lo = [v[0] for v in self.t.values() if v]
        hi = [v[-1] for v in self.t.values() if v]
        return (min(lo), max(hi)) if lo else None

    def times(self):
        """Tous les instants de balayage (triés) : les crans du curseur de relecture."""
        arr = [np.asarray(v, dtype=float) for v in self.t.values() if v]
        return np.unique(np.concatenate(arr)) if arr else np.array([])

    def snapshot(self, t, stale=120.0):
        """Spectre à l'instant t : pour chaque bande, le dernier balayage fait avant t (pas plus vieux que stale s)."""
        Fs, Ls = [], []
        for b, ts in self.t.items():
            k = bisect.bisect_right(ts, t) - 1
            if k < 0 or (stale is not None and t - ts[k] > stale):
                continue
            f, l = self.d[b][k]
            Fs.append(f)
            Ls.append(l)
        if not Fs:
            return None, None
        F, L = np.concatenate(Fs), np.concatenate(Ls)
        o = np.argsort(F, kind="stable")
        return F[o], L[o]

    def maxhold(self, t0, t1):
        """Max hold sur [t0, t1] (bande par bande, balayages de même grille)."""
        Fs, Ls = [], []
        for b, ts in self.t.items():
            i0, i1 = bisect.bisect_left(ts, t0), bisect.bisect_right(ts, t1)
            if i1 <= i0:
                continue
            f, l = self.d[b][i1 - 1]
            acc = l.copy()
            for j in range(i0, i1 - 1):
                if self.d[b][j][1].shape == acc.shape:
                    np.maximum(acc, self.d[b][j][1], out=acc)
            Fs.append(f)
            Ls.append(acc)
        if not Fs:
            return None, None
        F, L = np.concatenate(Fs), np.concatenate(Ls)
        o = np.argsort(F, kind="stable")
        return F[o], L[o]


# ------------------------------------------------- export des fréquences (par scène / par groupe)
def safe_filename(s, default="export"):
    s = unicodedata.normalize("NFKC", str(s)).strip()
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", s).strip(" ._")
    return s[:80] or default


# --------------------------------------------------------------------------
# Shows : ce qui appartient à un événement (rappelable d'une année à l'autre), sans les préférences du logiciel
# --------------------------------------------------------------------------
SHOW_EXT = ".tsashow"
SHOW_KEYS = ("bands", "watch", "scenes", "statuses", "scope", "focus", "strong_on", "strong_thr",
             "points", "points_auto", "points_sel", "planning", "site_scans", "rbw", "zrbw", "zpts", "input", "lna", "att", "seg", "offset",
             "thr", "weak_thr", "weak_on", "win", "absent_s", "occ_minutes", "ref_rel", "ref_margin",
             "country", "plan_custom", "dev_names", "rx_custom", "net_profiles", "net_addr", "port_net", "dev2", "devx", "states",
             "state_cur", "ezrf_link", "thr_auto", "auto_occ", "auto_weak",
             "user_presets", "persist", "hold", "alarm_timing",      # 7.57 : préréglages perso + leurs réglages
             "tnt",                                                  # 7.58 : lieu du show pour les émetteurs TNT
             "history",                                              # 7.63 : 🕘 historique des modifications
             "map")                                                  # 7.64 : 🗺 carte du site
SHOW_META = ("name", "venue", "date_from", "date_to", "notes")
# 7.57 (Clément : « un mode préférences utilisateur, qu'on puisse se passer les préférences : affichage, seuils,
# préréglages perso… comme des bases user ») : ce qu'un 👤 profil utilisateur emporte. PAS le show (fréquences, scènes,
# bandes, statuts, tinySA, scans) ni ce qui dépend du PC (sortie audio, dossiers, fenêtres, page web, alertes).
USER_KEYS = ("theme", "theme_v", "unit", "smooth", "coord_tools", "home", "expert", "ui_level", "labels", "sig_colors",
             "spec_more", "wall_size", "markers", "mark", "names", "watch_cols", "watch_cols_v", "log_kinds",
             "persist", "hold", "points_sel", "points_auto", "thr_auto", "auto_occ", "auto_weak", "thr", "weak_thr",
             "weak_on", "win", "absent_s", "strong_on", "strong_thr", "sound", "alarm_timing", "user_presets",
             "layout", "sdr_view", "alarm_sounds")      # V8 : mode + poste SDR, sons des alarmes
LAYOUT_PARTS = ("geometry", "docks", "panel_windows", "layout_ver")   # 7.57.1 : disposition des fenêtres du profil


def user_doc(cfg, name, app_ver=""):
    """Fichier profil utilisateur (.tsauser) : nom + préférences (clés USER_KEYS présentes dans la config)."""
    prefs = {k: cfg[k] for k in USER_KEYS if k in cfg}
    lay = {k: cfg[k] for k in LAYOUT_PARTS if k in cfg}
    if lay:
        prefs["layout"] = lay                     # fenêtre principale, panneaux, vraies fenêtres (écrans)
    if isinstance(prefs.get("sound"), dict):
        prefs["sound"] = {k: v for k, v in prefs["sound"].items() if k != "device"}   # la sortie audio reste au PC
    sd = cfg.get("sdr") if isinstance(cfg.get("sdr"), dict) else {}
    prefs["sdr_view"] = dict(rf_mode=rf_mode_norm(sd.get("rf_mode")), station=station_norm(sd.get("station")))
    return dict(format="tinysa-user", version=1, app=app_ver, name=" ".join(str(name or "").split())[:60] or "Profil",
                prefs=prefs)


def read_user(text):
    """Texte d'un fichier .tsauser -> doc ; ValueError s'il n'en est pas un."""
    import json as _json                          # section PURE : pas de json global (tests)
    try:
        d = _json.loads(text)
    except ValueError as e:
        raise ValueError("Fichier illisible (pas du JSON).") from e
    if not isinstance(d, dict) or d.get("format") != "tinysa-user" or not isinstance(d.get("prefs"), dict):
        raise ValueError("Ce n'est pas un profil utilisateur RF Technical Monitor.")
    return dict(name=" ".join(str(d.get("name") or "").split())[:60] or "Profil", app=str(d.get("app") or ""),
                prefs={k: v for k, v in d["prefs"].items() if k in USER_KEYS})


def user_apply(cfg_now, doc):
    """Config actuelle + profil -> config à appliquer : seules les préférences du profil changent ; la sortie audio
    de CE PC est gardée."""
    out = dict(cfg_now)
    for k, v in doc["prefs"].items():
        if k == "sound" and isinstance(v, dict):
            dev = (cfg_now.get("sound") or {}).get("device", "")
            v = dict(v, device=dev)
        if k == "layout":
            continue                              # appliquée à part par la fenêtre (restoreState…)
        if k == "sdr_view":                       # V8 : mode (tinySA / SDR / combiné) et poste SDR
            if isinstance(v, dict):
                out["sdr"] = dict(out.get("sdr") or {}, rf_mode=rf_mode_norm(v.get("rf_mode")),
                                  station=station_norm(v.get("station")))
            continue
        out[k] = v
    return out


def user_filename(name):
    """Nom de fichier du profil : « Clément.tsauser » (caractères interdits par Windows retirés)."""
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", " ".join(str(name or "").split())).strip(" .")[:60] or "Profil"
    return base + ".tsauser"


def show_doc(cfg, meta, ref=None, app_ver=""):
    """Fichier show (dict JSON) : infos + réglages de l'événement + courbe de référence du lieu."""
    m = {k: str(meta.get(k, "") or "") for k in SHOW_META}
    return dict(format="tinysa-show", version=1, app=app_ver, meta=m,
                show={k: cfg[k] for k in SHOW_KEYS if k in cfg},
                ref=[dict(f=[round(float(x), 6) for x in f], l=[round(float(x), 1) for x in l]) for f, l in (ref or [])])


def read_show(text, fallback_name=""):
    """Lit un show (.tsashow) ou un ancien profil (.json). -> doc normalisé ; ValueError si illisible."""
    import json as _json
    d = _json.loads(text)
    if not isinstance(d, dict):
        raise ValueError("ce fichier n'est pas un show")
    if d.get("format") == "tinysa-show" and isinstance(d.get("show"), dict):
        meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
        show, ref = d["show"], d.get("ref") or []
    elif "bands" in d or "watch" in d:                     # ancien profil : tout en vrac, on garde la partie show
        meta, show, ref = {}, {k: d[k] for k in SHOW_KEYS if k in d}, []
    else:
        raise ValueError("ce fichier ne ressemble pas à un show")
    meta = {k: str(meta.get(k, "") or "") for k in SHOW_META}
    if not meta["name"]:
        meta["name"] = fallback_name
    curves = []
    for c in ref if isinstance(ref, list) else []:
        try:
            f, l = list(map(float, c["f"])), list(map(float, c["l"]))
            if f and len(f) == len(l):
                curves.append((f, l))
        except (KeyError, TypeError, ValueError):
            pass
    return dict(meta=meta, show={k: v for k, v in show.items() if k in SHOW_KEYS}, ref=curves)


def show_apply(cfg_now, doc):
    """Config complète actuelle + show -> config à appliquer (les préférences du logiciel ne bougent pas)."""
    out = dict(cfg_now)
    out.update(doc["show"])
    return out


TEMPLATE_DROP = ("watch", "site_scans", "states", "state_cur", "ezrf_link", "planning", "scope", "focus", "history")


def show_template(doc):
    """📐 7.62 « Nouveau show depuis un modèle » : la STRUCTURE d'un show (scènes, groupes et leurs appareils, statuts,
    bandes, seuils, alarmes, tinySA, profils d'appareil, préréglages) sans ce qui appartient à l'édition passée : liste
    de fréquences, scans par lieu, états, plan suivi, planning, courbe de référence, dates, notes. Le lieu TNT est vidé
    (réglages gardés). -> nouveau doc de show."""
    sh = {k: v for k, v in doc["show"].items() if k not in TEMPLATE_DROP}
    if isinstance(sh.get("tnt"), dict):
        sh["tnt"] = dict(sh["tnt"], place="", manual={}, plan=[], plan_src="")
    if isinstance(sh.get("map"), dict):                  # 🗺 la carte (positions, plan) reste ; les points de chaleur non
        sh["map"] = dict(sh["map"], heat=[])
    m = doc.get("meta") or {}
    return dict(doc, show=sh, ref=[], meta=dict({k: "" for k in SHOW_META}, venue=str(m.get("venue") or "")),
                template=str(m.get("name") or ""))


def show_summary(doc):
    """Résumé pour la liste des shows."""
    sh, m = doc["show"], doc["meta"]
    w = sh.get("watch") or []
    dates = m["date_from"] + (f" → {m['date_to']}" if m["date_to"] and m["date_to"] != m["date_from"] else "")
    return dict(name=m["name"], venue=m["venue"], dates=dates, n_freq=len(w),
                n_blocks=sum(1 for x in w if isinstance(x, dict) and x.get("bw")),
                n_scenes=len(sh.get("scenes") or []), has_ref=bool(doc["ref"]))


def show_filename(meta):
    """Nom de fichier proposé : « 2025 Festival X - Grande scène.tsashow »."""
    year = (meta.get("date_from") or "")[:4]
    base = " - ".join(x for x in (meta.get("name", ""), meta.get("venue", "")) if x) or "show"
    return safe_filename(f"{year} {base}".strip(), "show") + SHOW_EXT


FREQ_FORMATS = [
    ("Complet : Scène ; Groupe ; Nom ; MHz ; Statut (se réimporte tel quel)", "full"),
    ("Simple : Nom ; MHz  (Excel français)", "name_mhz"),
    ("Simple : Nom, MHz  (virgule, point décimal)", "name_mhz_comma"),
    ("MHz seulement, une par ligne", "mhz"),
]


def freq_list_text(rows, fmt="full"):
    """rows : [dict(name, freq, status, scene, group)] -> texte CSV."""
    out = []
    if fmt == "full":
        out.append("Scène;Groupe;Nom;MHz;Statut")
        for r in rows:
            out.append(";".join([r.get("scene", ""), r.get("group", ""), r["name"], fmt_comma(r["freq"]),
                                 r.get("status", "") or ""]))
    elif fmt == "name_mhz":
        out.append("Nom;MHz")
        for r in rows:
            out.append(f'{r["name"]};{fmt_comma(r["freq"])}')
    elif fmt == "name_mhz_comma":
        for r in rows:
            nm = str(r["name"]).replace(",", " ")
            out.append(f'{nm}, {r["freq"]:.3f}')
    else:
        for r in rows:
            out.append(f'{r["freq"]:.3f}')
    return "\r\n".join(out) + "\r\n"


def split_freq_rows(rows, mode="all"):
    """-> [(nom de fichier sans extension, [rows])] : un seul fichier, ou un par scène, ou un par groupe."""
    if mode == "scene":
        keys = lambda r: (r.get("scene") or "Sans scène",)
    elif mode == "group":
        keys = lambda r: ((r.get("scene") or "Sans scène"), (r.get("group") or "Sans groupe"))
    else:
        return [("frequences", list(rows))]
    out, order = {}, []
    for r in rows:
        k = keys(r)
        if k not in out:
            out[k] = []
            order.append(k)
        out[k].append(r)
    return [(" - ".join(safe_filename(x) for x in k), out[k]) for k in order]


# ------------------------------------------------- rapport de fin de show (HTML autonome)
def html_esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            .replace("'", "&#39;"))


def _svg_spectrum(F, L, marks, thr, width=1000, height=260):
    """Courbe max hold + repères des fréquences (rouge = a été occupée) en SVG."""
    if F is None or len(F) < 2:
        return "<p class='muted'>Pas de mesure de spectre.</p>"
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    k = max(1, int(math.ceil(len(F) / 900)))
    if k > 1:
        m = (len(F) // k) * k
        F2, L2 = F[:m].reshape(-1, k).mean(axis=1), L[:m].reshape(-1, k).max(axis=1)
    else:
        F2, L2 = F, L
    f0, f1 = float(F2[0]), float(F2[-1])
    lo, hi = -120.0, max(-20.0, float(np.nanmax(L2)) + 5.0)
    px, py = 46, 10
    w, h = width - px - 8, height - py - 26

    def X(f):
        return px + (f - f0) / max(f1 - f0, 1e-9) * w

    def Y(v):
        return py + (hi - min(max(v, lo), hi)) / (hi - lo) * h

    s = [f"<svg viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' class='spec'>"]
    for v in range(int(lo), int(hi) + 1, 20):
        s.append(f"<line x1='{px}' x2='{px + w}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' class='grid'/>"
                 f"<text x='{px - 6}' y='{Y(v) + 4:.1f}' class='ax' text-anchor='end'>{v}</text>")
    nt = 8
    for i in range(nt + 1):
        f = f0 + (f1 - f0) * i / nt
        s.append(f"<text x='{X(f):.1f}' y='{height - 8}' class='ax' text-anchor='middle'>{f:.1f}</text>")
    for f, nm, hot in marks:
        if f0 <= f <= f1:
            s.append(f"<line x1='{X(f):.1f}' x2='{X(f):.1f}' y1='{py}' y2='{py + h}' class='{'mk hot' if hot else 'mk'}'>"
                     f"<title>{html_esc(nm)} {f:.3f} MHz</title></line>")
    if thr is not None and lo <= thr <= hi:
        s.append(f"<line x1='{px}' x2='{px + w}' y1='{Y(thr):.1f}' y2='{Y(thr):.1f}' class='thr'/>")
    pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(F2, L2))
    s.append(f"<polyline points='{pts}' class='curve'/>")
    s.append(f"<text x='{px + w}' y='{py + 12}' class='ax' text-anchor='end'>MHz · dBm</text></svg>")
    return "".join(s)


MS_BAD = ("CONFLIT", "INTERMOD", "ABSENT", "APPAREIL PERDU", "TROP FORT")
MS_WARN = ("INCONNU", "OCCUPÉ", "APPEL INCOMPLET")
MS_FLAP = 10                 # passages libre ↔ occupé à partir desquels une fréquence est « instable »


def morning_summary(events):
    """7.61 « le bilan lisible en 10 secondes » : à partir des événements du journal (du plus ancien au plus récent,
    tuples (heure HH:MM:SS, nom, MHz, dBm, événement, couche, note)) ->
    dict(verdict ok|warn|bad, n_bad, n_warn, hours [(heure, bad, warn, other)] dans l'ordre (la nuit passe minuit),
    hot [heures les plus chargées], groups [(événement, nom, MHz, nombre, première, dernière)] (alarmes réunies),
    flap [(nom, MHz, passages)] (fréquences instables : seuil pile sur un signal faible), moved [(heure, nom, note)]
    (fréquences changées), top [(nom, MHz, événements)])."""
    hours, order = {}, []
    groups, flap, top, moved = {}, {}, {}, []
    n_bad = n_warn = 0
    for x in events:
        if len(x) < 5:
            continue
        hh = str(x[0])[:2]
        k = str(x[4]).split(" (")[0]
        if hh.isdigit():
            if not order or order[-1].rstrip("'") != hh:
                while hh in hours:                 # même heure revue plus de 24 h après : case à part
                    hh += "'"
                hours[hh] = [0, 0, 0]
                order.append(hh)
            hours[order[-1]][0 if k in MS_BAD else 1 if k in MS_WARN else 2] += 1
        if k in MS_BAD:
            n_bad += 1
        elif k in MS_WARN:
            n_warn += 1
        nm, f = str(x[1]), str(x[2])
        if k in MS_BAD or k == "INCONNU":
            g = groups.setdefault((k, nm, f), [0, str(x[0]), str(x[0])])
            g[0] += 1
            g[2] = str(x[0])
        if k == "OCCUPÉ":
            flap[(nm, f)] = flap.get((nm, f), 0) + 1
        if k == "NOUVELLE FRÉQUENCE":
            moved.append((str(x[0]), nm, str(x[6]) if len(x) > 6 else ""))
        if f not in ("", "—") and (k in MS_BAD or k in MS_WARN):
            top[(nm, f)] = top.get((nm, f), 0) + 1
    hl = [(h, *hours[h]) for h in order]
    busy_h = sorted([r for r in hl if r[1] or r[2]], key=lambda r: -(3 * r[1] + r[2]))[:3]
    return dict(verdict="bad" if n_bad else "warn" if n_warn else "ok", n_bad=n_bad, n_warn=n_warn, hours=hl,
                hot=[r[0] for r in busy_h],
                groups=sorted(((k, nm, f, *v) for (k, nm, f), v in groups.items()), key=lambda r: -r[3])[:40],
                flap=sorted(((nm, f, n) for (nm, f), n in flap.items() if n >= MS_FLAP), key=lambda r: -r[2]),
                moved=moved[-40:], top=sorted(((nm, f, n) for (nm, f), n in top.items()), key=lambda r: -r[2])[:8])


def _svg_hours(hours, width=1000, height=150):
    """Barres empilées par heure (rouge = alarmes, orange = à surveiller, gris = le reste)."""
    if not hours:
        return ""
    mx = max(1, max(b + w + o for _h, b, w, o in hours))
    n = len(hours)
    px, py, h = 30, 8, height - 34
    bw = (width - px - 8) / n
    s = [f"<svg viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' class='spec hours'>"]
    for i, (hh, b, w, o) in enumerate(hours):
        x, y = px + i * bw, py + h
        for v, cls in ((o, "hb-o"), (w, "hb-w"), (b, "hb-b")):
            if v:
                hv = v / mx * h
                y -= hv
                s.append(f"<rect x='{x + 2:.1f}' y='{y:.1f}' width='{max(1.0, bw - 4):.1f}' height='{hv:.1f}' "
                         f"class='{cls}' rx='2'><title>{html_esc(hh.rstrip(chr(39)))} h : {b} · {w} · {o}</title></rect>")
        s.append(f"<text x='{x + bw / 2:.1f}' y='{height - 10}' class='ax' text-anchor='middle'>"
                 f"{html_esc(hh.rstrip(chr(39)))}h</text>")
    s.append(f"<text x='{px - 4}' y='{py + 10}' class='ax' text-anchor='end'>{mx}</text></svg>")
    return "".join(s)


MS_CSS = (".glance{border-radius:14px;padding:14px 18px;margin:12px 0;font-size:18px;font-weight:600}"
          ".glance.ok{background:#e8f7ee;color:#14532d}.glance.warn{background:#fff6e0;color:#7a4b00}"
          ".glance.bad{background:#fdecea;color:#8c1d18}.glance small{display:block;font-weight:400;font-size:14px}"
          ".hb-b{fill:#e5484d}.hb-w{fill:#f5a524}.hb-o{fill:#c7ccd6}"
          ".cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}"
          ".box{border:1px solid #e3e7ef;border-radius:12px;padding:10px 14px;min-width:0}.box.wide{grid-column:1/-1}.box h3{margin:2px 0 8px;font-size:15px}"
          ".bar{display:inline-block;height:8px;border-radius:4px;background:#e5484d;vertical-align:middle;margin-right:6px}")


def morning_html(ms):
    """Section « En un coup d'œil » du rapport (bilan du matin, rapport de show)."""
    e = html_esc
    if ms["verdict"] == "ok":
        head = "✔ Rien d'important : aucune alarme."
    elif ms["verdict"] == "warn":
        head = f"⚠ Pas d'alarme, mais {ms['n_warn']} événement(s) à regarder."
    else:
        head = f"✗ {ms['n_bad']} alarme(s) pendant la période."
    sub = (f"Heures les plus chargées : {', '.join(h.rstrip(chr(39)) + ' h' for h in ms['hot'])}." if ms["hot"]
           else "Aucune heure chargée.")
    p = ["<h2>En un coup d'œil</h2>", f"<div class='glance {ms['verdict']}'>{e(head)}<small>{e(sub)}</small></div>"]
    if ms["hours"]:
        p.append(_svg_hours(ms["hours"]))
        p.append("<p class='muted'>Événements par heure : rouge = alarmes (conflit, absent, intermod, trop fort, tinySA "
                 "perdu), orange = à regarder (occupé, inconnu), gris = le reste.</p>")
    p.append("<div class='cols'>")
    p.append("<div class='box wide'><h3>Alarmes regroupées</h3>")
    if ms["groups"]:
        p.append("<table><tr><th>Événement</th><th>Nom</th><th class='n'>MHz</th><th class='n'>Fois</th>"
                 "<th>De</th><th>À</th></tr>")
        for k, nm, f, n, a, z in ms["groups"]:
            p.append(f"<tr><td><span class='tag {e(k)}'>{e(k)}</span></td><td>{e(nm)}</td><td class='n'>{e(f)}</td>"
                     f"<td class='n'>{n}</td><td>{e(a)}</td><td>{e(z)}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>Aucune. ✔</p>")
    p.append("</div><div class='box'><h3>Les plus actives</h3>")
    if ms["top"]:
        mx = max(n for _a, _b, n in ms["top"])
        for nm, f, n in ms["top"]:
            p.append(f"<div><span class='bar' style='width:{max(4, int(120 * n / mx))}px'></span>{e(nm)} "
                     f"<span class='muted'>{e(f)} MHz · {n}</span></div>")
    else:
        p.append("<p>Rien à signaler.</p>")
    p.append("</div>")
    if ms["flap"]:
        p.append("<div class='box'><h3>Instables (libre ↔ occupé)</h3>")
        for nm, f, n in ms["flap"]:
            p.append(f"<div>{e(nm)} <span class='muted'>{e(f)} MHz · {n} passages</span></div>")
        p.append("<p class='muted'>Souvent un signal faible pile au seuil : donne-lui un seuil propre (clic droit sur "
                 "la fréquence) ou passe en seuil auto.</p></div>")
    if ms["moved"]:
        p.append("<div class='box'><h3>Fréquences changées</h3>")
        for t, nm, note in ms["moved"]:
            p.append(f"<div>{e(t)} · {e(nm)} <span class='muted'>{e(note)}</span></div>")
        p.append("</div>")
    p.append("</div>")
    return "".join(p)


# 7.56 : rapports (bilan du matin, rapport de show, étude de site) au look « pro » des thèmes de l'appli : clair pour
# l'impression, typo système, cartes arrondies, tableaux aérés, couleurs système. Ajouté APRÈS les styles d'origine.
REPORT_PRO_CSS = (
    "body{font:14px/1.5 -apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI Variable Text','Segoe UI',Roboto,"
    "sans-serif;color:#1d1d1f;background:#fff;-webkit-font-smoothing:antialiased}"
    "h1{font-size:30px;font-weight:700;letter-spacing:-.02em;margin:0 0 6px}"
    "h2{font-size:19px;font-weight:650;letter-spacing:-.01em;margin:34px 0 10px;border:0;padding:0}"
    "h2::before{content:'';display:inline-block;width:4px;height:18px;border-radius:2px;background:#007aff;"
    "vertical-align:-3px;margin-right:9px}h3{font-weight:650}.muted{color:#6e6e73}"
    ".cards{gap:12px}.card{border:0;border-radius:14px;background:#f5f5f7;padding:14px 18px;min-width:140px;"
    "color:#6e6e73}.card b{color:#1d1d1f;font-size:30px;font-weight:700;letter-spacing:-.02em}"
    ".card.bad{background:#fff1f0}.card.bad b{color:#d70015}"
    "table{border-collapse:separate;border-spacing:0;border:1px solid #e5e5ea;border-radius:12px;overflow:hidden}"
    "th,td{border-bottom:1px solid #f0f0f3;padding:7px 10px}th{background:#f5f5f7;color:#6e6e73;font-weight:600;"
    "font-size:12px;letter-spacing:.02em}tr:last-child td{border-bottom:0}tr:nth-child(even) td{background:#fbfbfd}"
    ".tag{border-radius:999px;padding:1px 9px}"
    "svg.spec{border:1px solid #e5e5ea;border-radius:14px;background:#fff}.grid{stroke:#ececf0}.ax{fill:#86868b}"
    ".curve{stroke:#ff9500;stroke-width:1.3}.mk{stroke:#34c759}.mk.hot{stroke:#ff3b30;opacity:.6}.thr{stroke:#ff3b30}"
)


def build_report_html(d):
    """Rapport autonome (un seul fichier, sans connexion) : à ouvrir dans le navigateur puis imprimer en PDF."""
    e = html_esc
    ev = d.get("events", [])
    rows = d.get("rows", [])
    cnt = {}
    for x in ev:
        cnt[x[4].split(" (")[0]] = cnt.get(x[4].split(" (")[0], 0) + 1
    hot = {int(round(r["freq"] * 1000)) for r in rows if r.get("conflicts") or r.get("absents") or r.get("occ_events")}
    marks = [(r["freq"], r["name"], int(round(r["freq"] * 1000)) in hot) for r in rows]
    cards = [("Fréquences surveillées", len(rows)), ("Événements", len(ev)), ("Conflits", cnt.get("CONFLIT", 0)),
             ("TX absents", cnt.get("ABSENT", 0)), ("Signaux inconnus", cnt.get("INCONNU", 0))]
    p = ["<!doctype html><html lang='fr'><head><meta charset='utf-8'>",
         f"<title>{e(d.get('title') or 'Rapport de show')}</title>",
         "<meta name='viewport' content='width=device-width,initial-scale=1'>",
         "<style>",
         "body{font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;color:#1d2433;max-width:1100px;margin:0 auto;padding:24px 18px}",
         "h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px;border-bottom:2px solid #d8dde8;padding-bottom:4px}",
         ".muted{color:#6b7488}.cards{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}",
         ".card{border:1px solid #d8dde8;border-radius:10px;padding:10px 16px;min-width:130px;background:#f7f9fc}",
         ".card b{display:block;font-size:26px}.card.bad{background:#fdecea;border-color:#f0b4ae}",
         "table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #e3e7ef;padding:4px 8px;text-align:left}",
         "th{background:#eef1f7;position:sticky;top:0}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}",
         ".tag{display:inline-block;border-radius:6px;padding:0 7px;font-size:12px;font-weight:600}",
         ".CONFLIT,.ABSENT{background:#fdecea;color:#b3261e}.INCONNU{background:#fff4d6;color:#8a5a00}",
         ".OCCUPÉ{background:#e8eefc;color:#1d4ed8}.Libre,.Retour{background:#e6f6ec;color:#17803d}",
         "svg.spec{width:100%;height:auto;border:1px solid #d8dde8;border-radius:8px;background:#fbfcfe}",
         ".grid{stroke:#e3e7ef}.ax{font-size:11px;fill:#6b7488}.curve{fill:none;stroke:#e08a1e;stroke-width:1.2}",
         ".mk{stroke:#2e8b57;stroke-width:1;opacity:.55}.mk.hot{stroke:#d33;stroke-width:1.6;opacity:.9}",
         ".thr{stroke:#d33;stroke-dasharray:5 4}", REPORT_PRO_CSS, MS_CSS,
         "@media print{body{padding:0}h2{break-after:avoid}tr{break-inside:avoid}th{position:static}}",
         "</style></head><body>",
         f"<h1>{e(d.get('title') or 'Rapport de show')}</h1>",
         f"<div class='muted'>{e(d.get('venue', ''))}{' · ' if d.get('venue') and d.get('operator') else ''}"
         f"{e(d.get('operator', ''))} · {e(d.get('generated', ''))}"
         f"{' · surveillance : ' + e(d['duration']) if d.get('duration') else ''}</div>"]
    if d.get("notes"):
        p.append(f"<p>{e(d['notes']).replace(chr(10), '<br>')}</p>")
    p.append("<div class='cards'>" + "".join(
        f"<div class='card{' bad' if (t in ('Conflits', 'TX absents') and v) else ''}'><b>{v}</b>{e(t)}</div>"
        for t, v in cards) + "</div>")
    p.append(morning_html(morning_summary(ev)))          # 7.61 : lisible en 10 secondes
    p.append("<h2>Spectre (max hold)</h2>")
    p.append(_svg_spectrum(d.get("F"), d.get("L"), marks, d.get("thr")))
    p.append("<p class='muted'>Traits verts : fréquences surveillées · rouges : fréquences ayant eu un conflit, une absence "
             "ou une occupation · pointillé : seuil « occupé ».</p>")
    grp = d.get("groups", [])
    if grp:
        p.append("<h2>Par scène et groupe</h2><table><tr><th>Scène › Groupe</th><th class='n'>Fréq.</th>"
                 "<th class='n'>Occupées à la fin</th><th class='n'>Événements</th><th class='n'>Conflits</th>"
                 "<th class='n'>Absences</th><th>Priorité</th></tr>")
        for g in grp:
            p.append(f"<tr><td>{e(g['name'])}</td><td class='n'>{g['n']}</td><td class='n'>{g['occ']}</td>"
                     f"<td class='n'>{g['events']}</td><td class='n'>{g['conflicts']}</td>"
                     f"<td class='n'>{g['absents']}</td><td>{e(g.get('prio', ''))}</td></tr>")
        p.append("</table>")
    bad = [x for x in ev if x[4].split(" (")[0] in ("CONFLIT", "ABSENT")]
    p.append(f"<h2>Alertes importantes ({len(bad)})</h2>")
    if bad:
        p.append("<table><tr><th>Heure</th><th>Nom</th><th class='n'>MHz</th><th>Événement</th><th>Scène › Groupe</th><th>Note</th></tr>")
        for x in bad[:300]:
            k = x[4].split(" (")[0]
            p.append(f"<tr><td>{e(x[0])}</td><td>{e(x[1])}</td><td class='n'>{e(x[2])}</td>"
                     f"<td><span class='tag {e(k)}'>{e(x[4])}</span></td><td>{e(x[5])}</td><td>{e(x[6])}</td></tr>")
        p.append("</table>")
    else:
        p.append("<p>Aucun conflit ni émetteur absent pendant la surveillance. ✔</p>")
    p.append(f"<h2>Fréquences ({len(rows)})</h2><table><tr><th>Nom</th><th class='n'>MHz</th><th>Statut</th>"
             "<th>Scène › Groupe</th><th class='n'>Max dBm</th><th class='n'>Occupation</th><th class='n'>Événements</th>"
             "<th class='n'>Conflits</th><th class='n'>Absences</th></tr>")
    for r in rows:
        mx = "—" if r.get("max") is None else f"{r['max']:.1f}"
        oc = "—" if r.get("occ_pct") is None else f"{r['occ_pct']:.0f} %"
        p.append(f"<tr><td>{e(r['name'])}</td><td class='n'>{r['freq']:.3f}</td><td>{e(r.get('status') or '')}</td>"
                 f"<td>{e(r.get('layer') or '')}</td><td class='n'>{mx}</td><td class='n'>{oc}</td>"
                 f"<td class='n'>{r.get('events', 0)}</td><td class='n'>{r.get('conflicts', 0)}</td>"
                 f"<td class='n'>{r.get('absents', 0)}</td></tr>")
    p.append("</table>")
    im = d.get("im", [])
    if im:
        p.append(f"<h2>Intermodulation ({len(im)})</h2><table><tr><th class='n'>Produit MHz</th><th>Ordre</th>"
                 "<th>Origine</th><th>Tombe sur</th><th class='n'>Écart kHz</th><th>Verdict</th></tr>")
        for r in im[:200]:
            p.append(f"<tr><td class='n'>{r['f']:.3f}</td><td>{e(r['order'])}</td><td>{e(r['text'])}</td>"
                     f"<td>{e(r['tname'])}</td><td class='n'>{e(r['delta'])}</td><td>{e(r['verdict'])}</td></tr>")
        p.append("</table><p class='muted'>Calcul théorique : il ne dit pas quel appareil fabrique le produit.</p>")
    p.append(f"<h2>Journal complet ({len(ev)})</h2><table><tr><th>Heure</th><th>Nom</th><th class='n'>MHz</th>"
             "<th class='n'>dBm</th><th>Événement</th><th>Scène › Groupe</th><th>Note</th></tr>")
    for x in ev[:1500]:
        k = x[4].split(" (")[0]
        p.append(f"<tr><td>{e(x[0])}</td><td>{e(x[1])}</td><td class='n'>{e(x[2])}</td><td class='n'>{e(x[3])}</td>"
                 f"<td><span class='tag {e(k)}'>{e(x[4])}</span></td><td>{e(x[5])}</td><td>{e(x[6])}</td></tr>")
    p.append("</table>")
    if len(ev) > 1500:
        p.append(f"<p class='muted'>… {len(ev) - 1500} événements de plus dans le journal CSV.</p>")
    p.append(f"<p class='muted'>Généré par {e(d.get('app', 'RF Technical Monitor'))}. Mesures indicatives du tinySA : "
             "elles ne remplacent pas ta coordination (logiciel dédié).</p></body></html>")
    return "".join(p)


# --------------------------------------------------------------------------
# Plusieurs tinySA : adresses (USB ou réseau) et répartition des bandes
# --------------------------------------------------------------------------
RELAY_PORT = 5025            # port TCP par défaut du relais réseau (RF-Technical-Monitor.exe --relais)


def parse_device_addr(s, default_port=RELAY_PORT):
    """Adresse d'un appareil -> (genre, url pyserial). « COM4 », « /dev/ttyACM0 » : USB ; « 192.168.1.20 »,
    « 192.168.1.20:5025 », « pc-scene:6000 » : réseau ; « socket://… », « rfc2217://… » tels quels.
    Genre None = adresse illisible."""
    s = (s or "").strip()
    if not s:
        return None, ""
    if parse_sdr_addr(s) is not None:                  # V8 : « hackrf », « rtlsdr:1 » (outil de balayage)
        return "sdr", s
    if "://" in s:
        return "net", s
    if re.fullmatch(r"(?i)com\d{1,3}", s) or s.startswith("/dev/") or s.startswith("\\\\.\\"):
        return "serial", s
    host, port = s, default_port
    m = re.fullmatch(r"(.+?):(\d{1,5})", s)
    if m:
        host, port = m.group(1), int(m.group(2))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]*", host) or not 0 < port < 65536:
        return None, s
    return "net", f"socket://{host}:{port}"


def net_profiles_norm(lst, limit=30):
    """🌐 Adresses réseau enregistrées (Raspberry Pi, autre PC : une par Wi-Fi / lieu) -> [{name, addr}] valides, noms
    uniques (le dernier gagne), dans l'ordre, `limit` au plus."""
    out = {}
    for d in lst if isinstance(lst, list) else []:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "").strip()[:40]
        addr = str(d.get("addr") or "").strip()[:120]
        if name and parse_device_addr(addr)[0] == "net":
            out.pop(name, None)
            out[name] = dict(name=name, addr=addr)
    return list(out.values())[-limit:]


def net_profiles_merge(old, new):
    """Adresses du PC + celles d'un show : celles du show gagnent à nom égal, les autres restent (ordre : PC puis show)."""
    return net_profiles_norm(list(old or []) + list(new or []))


def net_host_port(addr, default_port=RELAY_PORT):
    """(hôte, port) d'une adresse réseau (« 192.168.1.20 », « tinysa-sac.local:6000 », « socket://… ») ; None sinon."""
    kind, url = parse_device_addr(addr, default_port)
    if kind != "net":
        return None
    m = re.fullmatch(r"[a-z0-9]+://([^:/]+):(\d+).*", url)
    return (m.group(1), int(m.group(2))) if m else None


def net_profile_name(profiles, addr):
    """Nom de l'adresse enregistrée qui pointe au même endroit que addr ("" si aucune)."""
    u = parse_device_addr(addr)[1]
    return next((p["name"] for p in profiles or [] if parse_device_addr(p["addr"])[1] == u), "") if u else ""


def assign_bands(items, ndev=2, live=None):
    """Répartit les bandes entre les tinySA. items : [{id, pts, dev}] avec dev None (auto) ou n° d'appareil.
    Une bande fixée sur un appareil hors ligne passe sur un appareil vivant. Les bandes « auto » vont à
    l'appareil le moins chargé (en points), les plus grosses d'abord. -> {id: appareil}"""
    live = list(live) if live is not None else [True] * ndev
    ok = [d for d in range(ndev) if d < len(live) and live[d]] or [0]
    load = {d: 0 for d in ok}
    out, auto = {}, []
    for it in items:
        d = it.get("dev")
        if d is not None and d in load:
            out[it["id"]] = d
            load[d] += it["pts"]
        else:
            auto.append(it)
    for it in sorted(auto, key=lambda x: (-x["pts"], x["id"])):
        d = min(ok, key=lambda k: (load[k], k))
        out[it["id"]] = d
        load[d] += it["pts"]
    return out


def _clean_grid(F, L):
    """Fréquences / niveaux nettoyés : valeurs finies, fréquences strictement croissantes (np.interp l'exige)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    n = min(len(F), len(L))
    F, L = F[:n], L[:n]
    ok = np.isfinite(F) & np.isfinite(L)
    F, L = F[ok], L[ok]
    if len(F) > 1 and np.any(np.diff(F) <= 0):
        o = np.argsort(F, kind="stable")
        F, L = F[o], L[o]
        keep = np.concatenate(([True], np.diff(F) > 0))
        F, L = F[keep], L[keep]
    return F, L


def calib_maxhold(sweeps, n):
    """Max hold des n PREMIERS balayages d'un tinySA (même nombre pour chaque appareil : le max du bruit monte avec
    le nombre de balayages, comparer 5 balayages à 3 biaisait l'offset — revue de code 7.41). Les balayages dont la
    grille de fréquences diffère de celle du 1er sont ignorés. -> (F, L) ou None."""
    sel = list(sweeps)[:max(1, int(n))]
    if not sel:
        return None
    f0, l0 = _clean_grid(*sel[0])
    if len(f0) < 2:
        return None
    ls = [l0]
    for f_, l_ in sel[1:]:
        f_, l_ = _clean_grid(f_, l_)
        if f_.shape == f0.shape and np.allclose(f_, f0, rtol=0, atol=max(1e-6, 1e-3 * abs(f0[1] - f0[0]))):
            ls.append(l_)
    return f0, np.max(np.vstack(ls), axis=0)


def calib_repeat(sweeps1, sweeps2, n, snr=10.0):
    """Répétabilité : offset calculé balayage par balayage (i-ème du 1er contre i-ème de l'autre) -> (médiane, écart
    max − min) en dB, ou None. Sert à dire si la calibration est stable."""
    ds = []
    for (f1, l1), (f2, l2) in zip(list(sweeps1)[:n], list(sweeps2)[:n]):
        r = calib_offset(f1, l1, f2, l2, snr)
        if r is not None:
            ds.append(r[0])
    if not ds:
        return None
    return round(float(np.median(ds)), 1) + 0.0, round(float(max(ds) - min(ds)), 1) + 0.0


def scan_check(fr, lv, a, z, pts):
    """Contrôle d'un segment reçu du tinySA (revue de code 7.41 : un scan tronqué était étalé sur toute la bande sans
    rien dire). fr = fréquences Hz renvoyées (ou None), lv = niveaux, [a, z] Hz demandés, pts demandés.
    -> (fréquences à utiliser, état "ok" | "court" | "invalide", note). « court » = moins de points que demandé
    (utilisable, signalé) ; « invalide » = inutilisable (rien, ou niveaux absurdes)."""
    lv = np.asarray(lv, dtype=float)
    n = len(lv)
    if n < 2:
        return None, "invalide", f"{n} point(s) reçu(s) sur {pts}"
    if not np.isfinite(lv).all():              # audit 7.44 : un seul NaN fausse le max hold, les seuils, la marge…
        return None, "invalide", f"{int((~np.isfinite(lv)).sum())} niveau(x) illisible(s) sur {n}"
    if np.nanmax(lv) > 40 or np.nanmin(lv) < -200:
        return None, "invalide", "niveaux hors de toute plage possible"
    step = (z - a) / max(1, pts - 1)
    good = False
    if fr is not None and len(fr) == n:
        fr = np.asarray(fr, dtype=float)
        good = (np.isfinite(fr).all() and np.all(np.diff(fr) > 0)
                and fr[0] >= a - 2 * step - 1 and fr[-1] <= z + 2 * step + 1)
    if n < pts and not good:     # audit 7.44 : sans fréquences fiables, on ne sait pas QUELLE partie manque :
        return None, "invalide", f"{n} points reçus sur {pts}, sans fréquences fiables"   # étaler = décaler
    if not good:
        grid = np.linspace(a, z, n)
        if fr is not None and len(fr) == n:      # audit 7.52 : fréquences EXPLICITES mais incohérentes
            fr = np.asarray(fr, dtype=float)
            if not (np.isfinite(fr).all() and np.max(np.abs(fr - grid)) <= step / 2 + 1):
                return None, "invalide", "fréquences renvoyées par le tinySA incohérentes avec la bande demandée"
        fr = grid                                # (simple arrondi à moins d'un demi-pas : grille théorique)
    if n < pts:
        return fr, "court", f"{n} points reçus sur {pts} demandés"
    return fr, "ok", ""


def calib_offset(F1, L1, F2, L2, snr=10.0, min_pts=5):
    """Écart de lecture entre deux tinySA qui ont balayé la même bande (même antenne / splitter).
    -> (correction à AJOUTER au 2e en dB, nb de points utilisés, base « signaux » | « bruit de fond ») ou None.
    On compare d'abord les signaux vus par les deux (> plancher + snr dB) ; sinon le plancher de bruit."""
    F1, L1 = _clean_grid(F1, L1)
    F2, L2 = _clean_grid(F2, L2)
    if len(F1) < 2 or len(F2) < 2:
        return None
    lo, hi = max(F1[0], F2[0]), min(F1[-1], F2[-1])
    m = (F1 >= lo) & (F1 <= hi)
    if m.sum() < min_pts:
        return None
    f, a = F1[m], L1[m]
    b = np.interp(f, F2, L2)
    floor = float(np.median(np.minimum(a, b)))
    sig = np.minimum(a, b) > floor + snr          # signal vu par LES DEUX (une porteuse vue d'un seul côté fausserait)
    if sig.sum() >= min_pts:
        d, kind = a[sig] - b[sig], "signaux"
    else:
        d, kind = a - b, "bruit de fond"
    return round(float(np.median(d)), 1) + 0.0, int(len(d)), kind      # + 0.0 : pas de « -0.0 dB »


# --------------------------------------------------------------------------
# Alertes sur téléphone (ntfy / Telegram) : textes et requêtes HTTP (l'envoi est fait hors de cette section)
# --------------------------------------------------------------------------
NOTIFY_MODES = (("off", "Désactivées"), ("crit", "Critiques seulement"), ("all", "Critiques + normales"))


def notify_wanted(prio, mode):
    """Faut-il envoyer une alarme de cette priorité (2 critique, 1 normale, 0 info) ?"""
    return (mode == "crit" and prio >= 2) or (mode == "all" and prio >= 1)


# 7.56 (revue UX : « distinguer détecté / déduit / recommandé ») : chaque alarme dit ce qui est MESURÉ (sûr), ce qu'on
# en DÉDUIT (cause probable, jamais certaine) et ce qu'on CONSEILLE de faire.
ALARM_HELP = {
    "CONFLIT": ("Quelqu'un émet sur une fréquence qui doit rester libre : un émetteur d'une autre équipe, un talkie, "
                "ou un de tes émetteurs mal réglé.",
                "Chasse au brouilleur pour le trouver ; si ça dure, Fréquence de secours."),
    "INTERMOD": ("Probablement un produit d'intermodulation de tes propres émetteurs (formule indiquée) : il apparaît "
                 "quand ils émettent ensemble.",
                 "Coupe ou éloigne un des émetteurs cités pour confirmer ; sinon change de fréquence (Fréquence de "
                 "secours)."),
    "ABSENT": ("L'émetteur est éteint, à court de piles, hors de portée ou coupé.",
               "Vérifie le pack et les piles. S'il est éteint exprès : clic droit › Éteint (je sais)."),
    "TROP FORT": ("Un émetteur est très près de l'antenne (talkie, pack posé à côté) : il peut saturer les récepteurs "
                  "et le tinySA.",
                  "Éloigne l'émetteur ou l'antenne ; si c'est le tien, baisse sa puissance."),
    "APPAREIL": ("Câble USB ou réseau débranché, tinySA éteint ou figé.",
                 "Vérifie le câble et l'alimentation : l'appli réessaie toute seule. Si rien ne revient, débranche et "
                 "rebranche le tinySA."),
}


def alarm_explain(a, now, level_txt="", thr_txt=""):
    """Alarme (dict AlarmBook) -> {measured, deduced, advice} : mesuré (sûr), cause probable, quoi faire.
    level_txt / thr_txt : niveau et seuil déjà mis dans l'unité de l'appli (vides = pas affichés)."""
    kind = a.get("kind", "")
    f = a.get("freq") or 0.0
    t0, t1 = a.get("t0"), a.get("t_end")
    dur = fmt_duration(max(0.0, (now if t1 is None else t1) - (now if t0 is None else t0)))
    info = str(a.get("info") or "")
    if kind == "ABSENT":
        meas = f"Plus de signal sur {f:.3f} MHz depuis {dur}"
    elif kind == "APPAREIL":
        meas = f"Plus de réponse du tinySA depuis {dur}"
    else:
        lv = level_txt or ("—" if a.get("level") is None else f"{a['level']:.0f} dBm")
        meas = (f"{lv} sur {f:.3f} MHz (seuil {thr_txt}), depuis {dur}" if thr_txt else
                f"{lv} sur {f:.3f} MHz, depuis {dur}")
        if info:
            meas += " · " + info
    ded, adv = ALARM_HELP.get(kind, ("", ""))
    return dict(measured=meas, deduced=ded, advice=adv)


def notify_text(a, site=""):
    """Alarme (dict AlarmBook) -> (titre, corps) courts, lisibles sur un écran verrouillé.
    7.56 : + une ligne « quoi faire » (conseil d'ALARM_HELP)."""
    title = f"⚠ {a['kind']} — {a['name']}" + (" (SIMULÉ, démo)" if a.get("sim") else "")
    bits = []
    if a.get("freq"):
        bits.append(f"{a['freq']:.3f} MHz")
    if a.get("level") is not None:
        bits.append(f"{a['level']:.0f} dBm")
    for k in ("layer", "info"):
        if a.get(k):
            bits.append(str(a[k]))
    body = " · ".join(bits) or "alarme"
    if site:
        body = f"[{site}] " + body
    adv = ALARM_HELP.get(a.get("kind", ""), ("", ""))[1]
    if adv:
        body += "\n" + adv
    return title, body


def ntfy_request(server, topic, title, body, prio=2):
    """Requête ntfy (appli gratuite iOS / Android, sans compte) -> (url, en-têtes, données)."""
    url = (server or "https://ntfy.sh").rstrip("/") + "/" + topic.strip().strip("/")
    hdr = {"Title": _hdr_safe(title),
           "Priority": "urgent" if prio >= 2 else ("high" if prio >= 0 else "default"),
           "Tags": "rotating_light" if prio >= 2 else ("warning" if prio >= 0 else "white_check_mark")}
    return url, hdr, body.encode("utf-8")


def _hdr_safe(s):
    """Les en-têtes HTTP sont en latin-1 : ntfy accepte le format RFC 2047 pour le reste (accents, emojis)."""
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        import base64
        return "=?UTF-8?B?" + base64.b64encode(s.encode("utf-8")).decode("ascii") + "?="


def telegram_request(token, chat_id, title, body):
    """Requête Telegram (bot créé avec @BotFather) -> (url, en-têtes, données)."""
    import json as _json
    url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
    data = _json.dumps({"chat_id": str(chat_id).strip(), "text": f"{title}\n{body}",
                        "disable_web_page_preview": True}).encode("utf-8")
    return url, {"Content-Type": "application/json"}, data


def telegram_chats(updates):
    """Réponse de getUpdates (dict JSON) -> [(chat id, nom)] des discussions qui ont écrit au bot, plus récente
    d'abord, sans doublon. Sert à remplir le « chat id » tout seul."""
    out, seen = [], set()
    for u in reversed((updates or {}).get("result") or []):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or u.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None or cid in seen:
            continue
        seen.add(cid)
        name = chat.get("title") or " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) \
            or chat.get("username") or str(cid)
        out.append((str(cid), str(name)))
    return out


TUTO_ALERTES = """<h3>📱 ntfy — le plus simple (gratuit, sans compte)</h3>
<ol>
<li>Sur le téléphone, installe l'appli <b>ntfy</b> (App Store / Google Play / F-Droid).</li>
<li>Dans RF Technical Monitor (cette fenêtre) : <b>Service</b> = ntfy, garde le <b>Canal ntfy</b> proposé
(ex. <code>tinysa-3f9a1c7e</code>) ou mets le tien — long et difficile à deviner : <b>quiconque connaît ce
nom peut lire tes alertes</b>.</li>
<li>Dans l'appli ntfy : <b>+</b> (S'abonner à un sujet) → tape <b>exactement le même nom</b> de canal → serveur
par défaut (ntfy.sh) → S'abonner.</li>
<li>Choisis <b>Envoyer</b> (critiques seulement, ou toutes les alarmes), puis <b>Envoyer une alerte de test</b> :
elle doit arriver en quelques secondes.</li>
<li>Android : dans l'appli ntfy, ouvre le canal › Paramètres › autorise les priorités « urgentes » à sonner
même en mode Ne pas déranger si tu veux être réveillé. iPhone : autorise les notifications de ntfy.</li>
</ol>
<p>Plusieurs personnes ? Chacun s'abonne au même canal sur son téléphone.</p>
<h3>✈ Telegram — si l'équipe est déjà dessus</h3>
<ol>
<li>Dans Telegram, cherche <b>@BotFather</b> (le compte officiel, coche bleue) → envoie <code>/newbot</code> →
donne un nom (ex. « TinySA Festival ») puis un identifiant qui finit par <code>bot</code>
(ex. <code>tinysa_festival_bot</code>).</li>
<li>BotFather répond avec un <b>jeton</b> du genre <code>123456789:AAE…</code> : colle-le dans <b>Jeton du
bot</b>. Garde-le secret (il permet d'écrire au nom du bot).</li>
<li>Ouvre la discussion avec ton bot (lien donné par BotFather) et envoie-lui un message, par exemple
<code>/start</code>. Pour un <b>groupe</b> d'équipe : ajoute le bot au groupe et écris un message dans le groupe.</li>
<li>Clique <b>🔎 Trouver mon chat id</b> : RF Technical Monitor demande à Telegram qui a écrit au bot et remplit le
<b>Chat id</b> (un groupe a un id négatif, ex. <code>-1001234…</code>).</li>
<li><b>Envoyer une alerte de test</b>.</li>
</ol>
<h3>⚠ À savoir</h3>
<ul>
<li>Le PC de surveillance doit avoir <b>Internet</b> (partage 4G du téléphone, wifi du site…). Sans réseau,
les alertes attendent et sont réessayées 3 fois ; l'erreur s'affiche dans cette fenêtre.</li>
<li>Erreur « <i>hostname ntfy.sh not verified</i> » / « certificat » avec un nom bizarre
(<code>portail.hotspot…</code>) : le téléphone (ou le PC) est sur un <b>Wi-Fi à portail</b> (hôtel, camping, hotspot)
pas encore validé. Ouvre une page web pour valider le portail, ou coupe le Wi-Fi et passe en 4G.</li>
<li>Une alerte est envoyée <b>une fois</b> par alarme (pas à chaque bip).</li>
<li>Le jeton Telegram reste dans la config de CE PC : il n'est jamais copié dans les fichiers de show.</li>
</ul>"""


# --------------------------------------------------------------------------
# Page web en lecture seule (téléphone du régisseur…) : état JSON + page autonome
# --------------------------------------------------------------------------
WEB_PORT = 8080
STATE_TXT = {"occ": "OCCUPÉ", "weak": "faible", "free": "libre", None: "—"}


class PinGuard:
    """Code PIN de la page web (acquitter depuis le téléphone). Trop d'erreurs depuis une même adresse → bloquée
    un moment (on ne devine pas un code à 4 chiffres en tapant 10 000 fois)."""

    def __init__(self, tries=5, lock_s=60.0):
        self.tries, self.lock_s, self.bad = tries, lock_s, {}       # adresse -> [erreurs, bloquée jusqu'à]

    def check(self, pin, given, addr, now):
        """-> "ok" | "bad" | "locked" | "off" (pas de code réglé = acquittement désactivé)."""
        pin, given = str(pin or "").strip(), str(given or "").strip()
        if len(pin) < 4:
            return "off"
        st = self.bad.setdefault(addr, [0, 0.0])
        if now < st[1]:
            return "locked"
        acc = len(pin) ^ len(given)                    # comparaison à temps constant
        for a, b in zip(pin, given.ljust(len(pin))):
            acc |= ord(a) ^ ord(b)
        if acc == 0:
            st[0] = 0
            return "ok"
        st[0] += 1
        if st[0] >= self.tries:
            st[:] = [0, now + self.lock_s]
            return "locked"
        return "bad"


# icône de l'appli (parabole 📡, Noto Color Emoji — Apache 2.0), 64 px, pour la page web (favicon / écran d'accueil)
APP_ICON_PNG64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAPMUlEQVR42uWbW6ycV3XHf2vv/V3mdmbm3Hw5SXxNYmMIhmAuScDgNOWBiItKW0BIVUXVB1BVtfDWB9qqrdSn9oU+VO0LqkAqKgUUqVJpoC0lShsaQwzETmLHx1dsn+NzzsycuXzft/fqw4yPL/GxjRPHx+4nbc1oZvbsve7/tdbewtUfA+hoyH1bd+5D5UkVfRRlKzAOCGvrUeA8whFR+SGiTx078uL3LtAwGuHKSVcjwgIe4L4tOz+rIl8QeK+IoKqoKmv5ERFW9grPiupXjr364j9cSdsqDPh1C9/wG7fseMBi/8YYeVxRNARGE+WSsRYfvWRYMQZBCEGf9vjPn3r14EsXaLwKA4Zf3LtlxxMi5msiMhmC9yAyMok78Qmgaoy1qjqnGj5z/NWD372UCXKpamzcuvNxK+YpUU01hAIRx93wqBZijFORvtfw5KkjLz59geYL0g33bt++TUL0HNBUVQ9iL/qPO5r6EQ3qRcQCC2ryPcdfeeUwYAx8eej1ffT3IM0QggcsK85O7/ABI1rskDZpDmnFwJeH4r1n045PG2u/Fnxx96j9NczBWOeC9585MXvw64a9ex0iX1JVReS26rsIWKOXvd6KODmi9Uvs3etkZtOuDxkTnh7Fd7mdxPsAnb4hjZRBLpQTxVnlFkAPFRFCMI87Mf7jiBFU/cgzvvnEA95D5ODPP32G9+3s8vwrJf7yW5N0BwZneaOZEBCxYvzHHRoeucCU2yV9Y6DVM/zVp37Bb39sAZbg4bf2aJYLfvdvZ6hZj76xyiloAA2PGEW2jtTf3C7p5x7Gq54PP9ShWBDyTCjOC7+ya5n19ZysMG+0PzBDqCxbHUrjdqJ7BYzA8sAw37ZsXJ+TtwWXKgtzlnbfYkQJ4ZYs3zBrAeYKkBfCn/7zNAtti0uUds/wJ9+cotMb+oBbZX0ys+nBNZHeGRkSff+GjK/+/kn+4O/W818vlWlWPSHcOvfkVtDS7c5aglJJC04sWM4vWU4uWspJcatU/7LCx5rA6yoQjCOtp0SJJR1LCMZd4inuYgboyBOaWoVoegqiCDsxjhurgBFuZQ3GrYUCjwImijCVMhsfew/rdvaZPvYQx84fgryHdrO7WQOGEpA4xlTKzDy8m1K9zsye3bixCiaORwD91kjK3egGbykDRBBrcOWUZKyGzwakY2O4SoXCWRDQcLPJkbz+KHArk0TVUSHTGmySEFdKBO9J6zWicglvDWJkxCf5Jf9brytAdyMcdM7dMiaEEMAKLoqI05SolBJanrhRJqlVyeMYjWIQjzHmiirPtYnP8+KNYICS5/kt1ACFYCB41Bisi9AQsFGERBE+ePKigLy4JUJYG9UfERCDiSNsFKFBsVFEVEpBhiagV4bNKyR7s8y57WHw4vqCjSNs5NAQMNbiSimIoMgK0XqpBZhRAyvoyEnKzWjA7QYCutJ5sHGMiRyqQwZEpRSMIGZI+gqznMGUUnAOUSX0+miWX/Cod6oJCC6NMdYOpWmFqFwCY4eSlou5s62UiSbHGdt8L/3zi3RPnqZYaKF58UuXTczaYkA6ZIAqIoa4UkasIGJWQrpEDimXmHz7Lj7y13/Grk9/AlOrYEvJTQEmd2P7kxuw5Zt3SmIMYgxRmiL2YgEwqVYR6xBrVv7PxDG2lLLhnQ9RqtdZt/MB0olxeq0OYbkHl/iCG2nkXpcBAsRRdCFnQ5BRn1lH75QwWkiMGbYjQsAy8twCZvT+avMVhSjCRY4kTTEjvokqabWCS2IkjvBxTFAlShNcpUxlYhw/GJBUypTGGxSnzmCSGC08IgYBsiy7rj6463EpAOeXu4hAai197wmqlK0lC0oWPKXIIaWEvJSQiEB/QKezTBSUxFh6Pqw+Xz1VK9iioJtEBOcApR87qFXxwGKWUfR6pNbQzTMiAVcukRuDb9SRUomu93R6fWLvcWLoeU/Zuev6BHe9LCA2hj3TDfKgHFhqsWe8ScVZnl9YYms1ZWOa8kLWZ2yiyVtnNvCqCGdPn+Gx/oBTS21mO132Tk+ShXD1+aWUA0VBPUl4rJ9RX1ggFBHbD86y2PL8JEn4QLNJ1zgOtFq8o16nUalQrVaYOnWGLfPzHIgcrlxiy7ppDi4sslx43js5zv6FJQY+rGjVTTlBVaVTFCwXBapK1xe0i4KgSt97WsFDuYRMTrDr936HfX/xR4zt2M5ykjAYAZj2avNDoJXneIFchEEpJTiHDwUdARmrIpGjo0o3DDv1PaAXRbhSSmaErFLBVirkAq3gyYMSUNp5MXKmr0MDBMhV2b+whDBU4ReXOgSU1FqOLnc5nA2orpuifN8Mxx/YRr0+xthbHuS5n/wMshyHsn9h8arzZ5e7vNIJVJt1BiHw4kSTWqOB6oAj0w1axQRYy4+7XYp2h9RaDvb7VJ1lU5pyvllnbnqSUK9xrig4urSEyzIswvMLi6TWvj4TuMCEshviJUVJRx45qJJYg00TbBLTWDfFmHNIltGY2cBYrUre6ZIPMsrWDhGdDgkXYTjfGBIxGGOIrGUsijCFR33AdLqklXW4NKHiHNnIEafOUi+ViEsp9AckCmmlTOQctSimGOSAUHFuxTnfJA7QS8wgoISRH1eChhVYqs5hkpjK9CS4YVe9Mj2Jq1Ux5RScIRCGWd9w9sr8oIGADtHeiJkhBIqiIMsGuFKKK6WoMcPmgTVgDKac4tKE5aXWUJvGxsBa1MiFXY3WuD4uMFfrqV+IDMNDUYGr5B5D+3IWVylha1XKk8ODY8F7So06yeQ48dQEcbOOjKo6KyvoCNMbAeewcYRJkmH+7wu8L8h6fVwSk9SqSOwwcYyJI0wSE5XLuDii22oTCk95oolNEiR2o/zgciFerAu8dqyaDKmOJhohjuMREy7+WKzFVMukk5NE403GNqwnHwwYLHcpN+tUN65HgqI+YJMUv9RGs2zIOGuRKEKMIFFE1GyS1sdIazWKQUbwnnyQUbKW8kSTpNHAjc5m2UadUqOOdRG9Tod8MKAy0SRp1JHOMvRzdJCBKkVerGCP1eh0q5apASKLLZXwzmKMQYNH/VDyppQQNRu4dZM8/FufYsPO+1k8c47O4hL37XyQZLxBabzB1JNP8NNvfIfl4ycp2suAIGmMWouJI+JKGTdWw4xVicslsn6fEAJ5f4AYg6tWCeUSLo6GkLmUUJocR4zQa3fIen1KjTrReB3f62HynKK9TOgPUO8h6DULKG5V6zcGV63gJprU7p0h6/Xw/T7WOUJQbKUMUcTMe97J5j27EYXFs+dYOnOOrbvfxtTWzTRnNrBl9266iy1e/u73kSwnz3LS8SZv/+RHac/Nc+SZ/8GWUur3bCQdq9JbmAOFIs8IRcHE1k0UWc7C7Al8njOz+6287SNPUGQZ/W6PbqvN1D0bKa+bHjrPUkr/7ByD+QWss/hOD9WwajRwq9YpnUWd5Z73vYv3f/HzHN9/gBM/PkDrzDkeevJX6XWWaZ2dY8u730nRH3Do2R9x5shRVJXzJ0+z9V3vwBcFy61F1r3lAY4+/wKlSplkrEpt3TQPPLGXbLnLul07OH3wZbY/sodyo875Y0eHVahBTt7vs/nht7PtkXfz3De+w6kXX2LTu99BWqswf/I07bnztJoNZh7YRuPeGXbsez+9hSXmjxzFL7U4+I/fRiKLZuGXrQcoghLynG37HqM2NcX9H3iEre/bw9zsMaa3bSH4IVddEjN/4hSzz+2H4PGF5+TPD7Fr3/vJuj1QZWLTvTz8mx+jNjFBY+N6uotLDNodijxnZteDTG/dhBhDa26e04deQQwMllqoKmbUGd3xwUdZv/N+Ju69h7NHj/PCv36fIs9pn50jhMDODz1GpdkAlPs/+AhJpUJ//jwv/9NTWCMMe2yv1QNbHWv+8WoIUMSweOIUrXabLMsIwdPYsJ7WmXMU/QHLC4ssnTnH0Wd/xNzPD+FbbXy3R9btMrV9C/3lLsd/doj69CT19euGnnupRVqrcu7VWX78L/+GzzJqU5OcP36S//76N+nMzvKxDQd56vB6tLGRcq3EwumzVMYbjE1OUmQZh/79h8y/fBgGGf1Wi8aG9VQnx2mfm6fIc7oLSxzff4CFlw6z8NJhUEX06n5Apjdu0VXdoDGYconyjm3EjTpJo05Sq1DkOSKGkOdk7Q5+uYvv9ghZjnEWWy6TTk1g04Qiy0gq5RUgFAqPcY6828VnOQgk5TJZu8Og1cEWfb764f/kD595lDOyjtp4laLwxKUUVcX3B/TmF4YRxXtMHBOP1Uga9eG+jBCynM7JX7D80mFCq0PoD0aky40jQUGGXjTPMYMcv9ii2+7QHYXAUZyEEAhZjuYFqBLyAs0LOt0uxjnEWnphiCVW8nTvV1JpgF4Iw9JW5oEcDZ5iqU2/J+j8WcQ5umGET0KAwhNG64mzFK0O3dNnRtWkMKwoeY/2+oR+ds0GyXVyAUGznO7siVHV5hIiWEE1F9tbF/J7ZHSkWlY+fy04eS260gCxDfhBRv/4aZYX5imiC0FMVn6kegkmWXVfAb/cAw3XLM5cuygqw4WKhcXXAGS5anSVyyH0lZ9c/vVrZKIKEkGkBX5piWLeYSMdhvIrKmhXbkSvWmk3lxRJ9XWUxJy7ZNN6mYZcvyu32vkuuXr4NcrpJUcQNzQhFzB6/V7f5Z0DubLmvvoepzdu9qyx4/CxU/JC3oyCfXCqLDK8ArNmnn4mvEmHdhcNcGTkJMJaYcCbQHwY0XzEoPrMRQtc2/eB3rDzCBdD0TMmWL41DLBqLv7gbh4AalDVYPmWmd+++Qequn+kEv7/gQr40a2y/fPbN//AMjsbqrVGW4z5pKoG7twLUjds/8YYC/rF5Z/+5IWVG2FTGzZ9T8TsVQ237dj8myN9Y1XDf5w7PbvvUiAUKMLnguU5hCYrl6buKufnEbEawoL48LlR1DN25Blst9uaL5XrPxLhN0QkBi3uInMoRMSh2tfAJ+bOHf/fkZaHCwR6wM6fPfZ0EP2oKnMixo0+D3eyvY/U3qkyF0Q/On/22MqdQa6wdQVsr9N6pTxW+TaYt4gx24aYTK+MEGv96mwAjIgRMWIUfRqT/9r86ZPPccX94Wtenp5ef99nVfgCyHsvpF13wuXpi2mnPivKV87+4tiNXp6+rGO0Uk+enr5vnxqeVOVRZI1fn1eOiPBDCTx19uyx616f/z8sbtq90rGpbgAAAABJRU5ErkJggg=="

# vues de la page web (façon Ontime : une adresse, plusieurs écrans au choix) ; le PC choisit celles qu'il partage
WEB_VIEWS = [("liste", "📋", "Liste", "Toutes les fréquences, filtrables par scène / groupe"),
             ("mur", "🧱", "Mur", "Grandes tuiles lisibles de loin, plein écran"),
             ("spectre", "📈", "Spectre", "Le spectre en direct, avec tes fréquences"),
             ("waterfall", "🌊", "Waterfall", "L'historique du spectre qui défile"),
             ("alarmes", "🔔", "Alarmes", "Conflits et émetteurs absents, à acquitter"),
             ("regie", "🎛", "Régie", "Gros voyants par groupe, alarmes en haut : pour l'écran de la régie"),
             ("chasse", "🔎", "Chasse", "Chasser un brouilleur en se déplaçant : niveau en gros et bip sur le téléphone"),
             ("terrain", "🎒", "Terrain", "tinySA volant : dire à quelle(s) scène(s) il est et garder des scans pour la coordination"),
             ("tech", "🛠", "Tech", "Gérer le serveur : surveillance, seuils, fréquences, tinySA (accès protégé)")]
WEB_VIEW_KEYS = [k for k, *_ in WEB_VIEWS]
WEB_VIEWS_HIDDEN = ("terrain", "tech", "ecoute")   # cachées tant qu'on ne les coche pas (outils de l'équipe HF, écoute)
_WEB_BASE_VIEWS = tuple(WEB_VIEW_KEYS)   # 7.68 : vues écrites dans WEB_PAGE ; celles ajoutées ensuite (V8) = VIEWS_X


def web_link(ip, port, view=""):
    """📱 7.63 : adresse de la page web (QR code) : http://ip:port/ ou …/#/vue."""
    return f"http://{ip}:{int(port)}/" + (f"#/{view}" if view in WEB_VIEW_KEYS else "")


def web_views_norm(v):
    """{vue: bool} complet (les vues inconnues sont ignorées ; les manquantes sont partagées, sauf les cachées)."""
    v = v if isinstance(v, dict) else {}
    return {k: bool(v.get(k, k not in WEB_VIEWS_HIDDEN)) for k in WEB_VIEW_KEYS}


class ClientBook:
    """Qui regarde la page web : un jeton par navigateur (cookie), un nom choisi par la personne, la vue ouverte.
    En ligne = vu depuis moins de `online_s` ; oublié après `keep_s` sans nouvelles."""

    def __init__(self, online_s=12.0, keep_s=3600.0):
        self.online_s, self.keep_s, self.c = online_s, keep_s, {}

    def login(self, token, name, addr, ua, now):
        name = re.sub(r"\s+", " ", str(name or "")).strip()[:32] or "Invité"
        self.c[token] = dict(name=name, addr=str(addr), ua=str(ua or "")[:120], view="", since=now, last=now)
        self.purge(now)
        return self.c[token]

    def touch(self, token, addr, view, now):
        e = self.c.get(token)
        if e is None:
            return None
        e["last"], e["addr"] = now, str(addr)
        if view:
            e["view"] = str(view)[:20]
        return e

    def rename(self, token, name):
        e = self.c.get(token)
        if e is not None:
            e["name"] = re.sub(r"\s+", " ", str(name or "")).strip()[:32] or e["name"]
        return e

    def identify(self, token, now, secs=8.0):
        """Fait clignoter l'écran de ce client pendant `secs` s (pour savoir quelle tablette est laquelle)."""
        e = self.c.get(token)
        if e is not None:
            e["ident"] = now + secs
        return e

    def purge(self, now):
        for t in [t for t, e in self.c.items() if now - e["last"] > self.keep_s]:
            del self.c[t]

    def revoke_all(self):
        self.c.clear()

    def set_tech(self, token, state, now):
        """🛠 Accès Tech d'un navigateur : None (aucun), « pending » (en attente du PC) ou « ok »."""
        e = self.c.get(token)
        if e is None:
            return None
        if state:
            e["tech"], e["tech_t"] = state, now
        else:
            e.pop("tech", None)
            e.pop("tech_t", None)
        return e

    def tech_state(self, token, now, max_age=43200.0):
        """État Tech du navigateur ; un accès accordé expire au bout de max_age s (12 h)."""
        e = self.c.get(token)
        if e is None or not e.get("tech"):
            return None
        if now - e.get("tech_t", now) > max_age:
            e.pop("tech", None)
            return None
        return e["tech"]

    def watching(self, views, now):
        """Quelqu'un regarde-t-il une de ces vues en ce moment ?"""
        return any(e["view"] in views and now - e["last"] <= self.online_s for e in self.c.values())

    def listing(self, now):
        out = [dict(e, token=t, online=now - e["last"] <= self.online_s) for t, e in self.c.items()]
        out.sort(key=lambda e: (not e["online"], e["name"].lower()))
        return out


def web_spectrum(segments, n_max=900, nd=1):
    """Spectre allégé pour le téléphone : segments = [(nom, F, L, maxhold ou None)] -> [{name, f, l, mh}].
    Chaque segment est ramené à n_max points au plus en gardant le MAX de chaque paquet (un pic étroit ne
    disparaît pas)."""
    out = []
    for name, F, L, MH in segments:
        F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
        if len(F) == 0 or len(F) != len(L):
            continue
        MH = None if MH is None or len(MH) != len(F) else np.asarray(MH, dtype=float)
        if len(F) > n_max:
            edges = np.linspace(0, len(F), n_max + 1).astype(int)[:-1]
            f2 = (np.add.reduceat(F, edges) / np.diff(np.append(edges, len(F))))
            l2 = np.maximum.reduceat(L, edges)
            m2 = None if MH is None else np.maximum.reduceat(MH, edges)
        else:
            f2, l2, m2 = F, L, MH
        out.append(dict(name=str(name), f=[round(float(x), 4) for x in f2], l=[round(float(x), nd) for x in l2],
                        mh=None if m2 is None else [round(float(x), nd) for x in m2]))
    return out


def web_state(rows, alarms, info):
    """rows : [{name, freq, level, state, status, scene, group, absent, conflict}] ; alarms : listing AlarmBook.
    -> dict sérialisable pour /etat.json."""
    out = []
    for r in rows:
        st = r.get("state")
        out.append(dict(name=r["name"], freq=round(float(r["freq"]), 4), bw=float(r.get("bw") or 0.0),
                        level=None if r.get("level") is None else round(float(r["level"]), 1),
                        level_txt=r.get("level_txt") or ("" if r.get("level") is None else f"{float(r['level']):.1f} dBm"),
                        state=st or "", state_txt=r.get("sig_txt") or STATE_TXT.get(st, "—"),
                        tone=r.get("tone") or {"occ": "bad", "weak": "warn", "free": "free"}.get(st, "none"),
                        color=r.get("color") or "",
                        status=r.get("status") or "",
                        scene=r.get("scene") or "", group=r.get("group") or "", paused=bool(r.get("paused")),
                        alarm="ABSENT" if r.get("absent") else ("CONFLIT" if r.get("conflict") else "")))
    al = [dict(id=int(a.get("id", 0)), kind=a["kind"], name=a["name"], freq=round(float(a["freq"] or 0), 4), prio=int(a["prio"]),
               acked=bool(a["acked"]), layer=a.get("layer") or "", info=a.get("info") or "", t0=a["t0"],
               hint=ALARM_HELP.get(a["kind"], ("", ""))[1])            # 7.56 : quoi faire
          for a in alarms if a.get("t_end") is None]
    return dict(rows=out, alarms=al, **info)


WEB_PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#000000"><title>RF Technical Monitor</title>
<link rel="icon" href="data:image/png;base64,__ICON__"><link rel="apple-touch-icon" href="data:image/png;base64,__ICON__">
<style>
:root{--bg:#000000;--panel:#1c1c1e;--panel2:#2c2c2e;--line:#38383a;--fg:#f5f5f7;--mut:#98989d;--acc:#0a84ff;
--ok:#30d158;--bad:#ff453a;--warn:#ffd60a;--abs:#ff9f0a;--none:#48484a;--r:14px}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--fg);font:15px/1.4 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI Variable Text","Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased;
-webkit-tap-highlight-color:transparent}
button,input,select{font:inherit;color:inherit}
.hidden{display:none!important}.mut{color:var(--mut)}.hint{display:block;margin-top:3px;font-weight:500;opacity:.85}
.rg-al{margin:10px 16px;border-radius:20px;padding:16px 22px;font-weight:700;font-size:clamp(22px,3.6vw,46px);line-height:1.15;letter-spacing:-.01em}
.rg-al.ok{background:rgba(48,209,88,.14);color:var(--fg);border:1px solid rgba(48,209,88,.45)}
.rg-al.warn{background:rgba(255,159,10,.16);color:var(--fg);border:1px solid rgba(255,159,10,.5)}.rg-al.bad{background:var(--bad);color:#fff;animation:rgp .8s ease-in-out infinite alternate}
.rg-al small{display:block;font-size:.45em;font-weight:600;opacity:.9;margin-top:4px}
@keyframes rgp{from{filter:brightness(1)}to{filter:brightness(1.3)}}
.rg{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--rw,280px),1fr));gap:12px;padding:6px 16px 20px}
.rg .g{border-radius:20px;padding:16px 18px;border:1.5px solid var(--line);background:var(--panel)}
.rg .g b{display:block;font-size:var(--rf,26px);line-height:1.15}
.rg .g .k{font-size:calc(var(--rf,26px)*.7);font-weight:800;margin-top:6px}
.rg .g .p{font-size:calc(var(--rf,26px)*.5);margin-top:6px;opacity:.95}
.rg .g.ok{background:rgba(48,209,88,.12);border-color:rgba(48,209,88,.55)}.rg .g.ok .k{color:var(--ok)}
.rg .g.warn{background:rgba(255,159,10,.13);border-color:rgba(255,159,10,.6)}.rg .g.warn .k{color:var(--abs)}
.rg .g.bad{background:var(--bad);border-color:var(--bad)}.rg .g.none{opacity:.7}
.hb{text-align:center;padding:10px 16px}.hb .lv{font-size:clamp(54px,16vw,120px);font-weight:900;line-height:1.05}
.hb .bar{height:28px;border-radius:14px;background:var(--panel2);overflow:hidden;margin:12px 0}
.hb .bar i{display:block;height:100%;background:linear-gradient(90deg,#22c55e,#eab308,#ef4444);transition:width .3s}
.hb .sub{color:var(--mut);font-size:16px}
#stale{display:none;position:sticky;top:0;z-index:9;background:var(--bad);color:#fff;padding:8px 16px;font-weight:700;text-align:center}
#ident{position:fixed;inset:0;z-index:50;display:grid;place-items:center;text-align:center;animation:blink .5s steps(1) infinite}
#ident div{font-size:72px}#ident b{display:block;font-size:42px;margin:8px 16px}#ident span{font-size:20px;opacity:.85}
@keyframes blink{0%{background:#ff9f1c;color:#111}50%{background:#111;color:#ff9f1c}}
/* --- connexion --- */
#login{min-height:100%;display:flex;align-items:center;justify-content:center;padding:24px 16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:28px 24px;width:100%;max-width:380px;
box-shadow:0 20px 60px #0008}
.card h1{margin:8px 0 4px;font-size:22px}.card p{margin:0 0 18px;color:var(--mut)}
.logo{width:52px;height:52px;border-radius:14px;background:linear-gradient(135deg,#ff9f1c,#ff5e3a);display:grid;
place-items:center;font-size:28px}
label{display:block;font-size:13px;color:var(--mut);margin:12px 0 6px}
.in{width:100%;padding:12px 14px;border-radius:10px;border:1px solid var(--line);background:var(--bg);outline:none}
.in:focus{border-color:var(--acc)}
.btn{border:0;border-radius:10px;padding:10px 16px;background:var(--panel2);border:1px solid var(--line);cursor:pointer;
font-weight:600}.btn:hover{border-color:#3a4252}
.btn.pri{background:var(--acc);color:#fff;border-color:var(--acc);width:100%;padding:13px;margin-top:18px;font-size:16px}
.err{color:var(--bad);min-height:20px;margin-top:10px;font-size:14px}
/* --- en-tête --- */
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);
border-bottom:1px solid var(--line)}
.bar{display:flex;align-items:center;gap:12px;padding:10px 16px}
.bar .logo{width:38px;height:38px;font-size:20px;border-radius:10px;flex:none}
.ttl{min-width:0;flex:1}.ttl b{display:block;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ttl span{font-size:12.5px}
.clock{font:700 22px/1 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.5px;font-variant-numeric:tabular-nums}
.pill{padding:6px 12px;border-radius:999px;font-weight:700;font-size:13px;white-space:nowrap;background:var(--panel2);
border:1px solid var(--line)}.pill.ok{background:#22c55e22;color:#4ade80;border-color:#22c55e55}
.pill.bad{background:var(--bad);color:#fff;border-color:var(--bad);animation:pulse 1.2s infinite}
@keyframes pulse{50%{opacity:.75}}
.chip{background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:6px 12px;cursor:pointer;
font-size:13px;white-space:nowrap;max-width:140px;overflow:hidden;text-overflow:ellipsis}
nav{display:flex;gap:6px;padding:0 12px 10px;overflow-x:auto;scrollbar-width:none}nav::-webkit-scrollbar{display:none}
nav a{flex:none;text-decoration:none;color:var(--mut);padding:8px 14px;border-radius:10px;font-weight:600;
border:1px solid transparent}nav a.on{color:var(--fg);background:var(--panel2);border-color:var(--line)}
/* --- bandeau d'alarmes --- */
#al{padding:0 16px}#al:empty{display:none}
.al{display:flex;align-items:center;gap:10px;background:var(--bad);color:#fff;border-radius:12px;padding:10px 12px;
margin-top:10px;font-weight:600}.al.ack{background:var(--abs)}.al .x{flex:1;min-width:0}
.al small{display:block;font-weight:500;opacity:.9}
.al button,.ackbtn{border:0;border-radius:8px;padding:7px 12px;background:#fff;color:#000;font-weight:700;cursor:pointer;flex:none}
/* --- contenu --- */
main{padding:14px 16px 40px}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.tools .in{width:auto;padding:8px 10px;flex:1;min-width:140px}
.tools select.in{flex:0 1 auto}
.sw{display:flex;align-items:center;gap:6px;color:var(--mut);font-size:14px;cursor:pointer;user-select:none}
.home{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.vcard{display:block;text-decoration:none;color:inherit;background:var(--panel);border:1px solid var(--line);
border-radius:var(--r);padding:18px;transition:transform .1s,border-color .1s}
.vcard:hover{border-color:var(--acc);transform:translateY(-2px)}
.vcard .i{font-size:30px}.vcard b{display:block;font-size:18px;margin:8px 0 4px}.vcard span{color:var(--mut);font-size:13.5px}
.sum{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:14px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:12px 14px}
.kpi b{display:block;font-size:26px;font-variant-numeric:tabular-nums}.kpi span{color:var(--mut);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:10px}
.c{background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--none);border-radius:12px;padding:10px 12px}
.c.ok{border-left-color:var(--ok)}.c.bad{border-left-color:var(--bad)}.c.warn{border-left-color:var(--warn)}
.c.free{border-left-color:var(--acc)}.t.free{background:rgba(10,132,255,.14);border-color:rgba(10,132,255,.6)}
.c.alarm{background:var(--abs);color:#111;border-color:var(--abs)}
.c .n{font-weight:700;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c .f{color:var(--mut);font-size:13px;font-variant-numeric:tabular-nums}.c.alarm .f,.c.alarm .s{color:#111}
.c .l{font-size:15px;margin-top:3px;font-weight:600}.c .s{color:var(--mut);font-size:12.5px}
.wall{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(var(--tw,200px),1fr))}
.t{border-radius:18px;padding:14px;text-align:center;background:var(--panel);border:1.5px solid var(--line);min-height:var(--th,130px);
display:flex;flex-direction:column;justify-content:center}
.t.ok{background:rgba(48,209,88,.13);border-color:rgba(48,209,88,.6)}.t.bad{background:rgba(255,69,58,.28);border-color:var(--bad)}
.t.warn{background:rgba(255,159,10,.14);border-color:rgba(255,159,10,.6)}.t.alarm{background:var(--abs);border-color:#fff;color:#111}
.t .n{font-weight:700;font-size:calc(var(--fs,22px)*1.15);line-height:1.1}.t .f{opacity:.8;font-size:calc(var(--fs,22px)*.62)}
.t .l{font-weight:700;font-size:var(--fs,22px);margin-top:4px}
.wallfs{position:fixed;inset:0;z-index:20;background:var(--bg);padding:12px;overflow:auto}
.plot{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
.plot canvas{display:block;width:100%;touch-action:none}
.read{position:absolute;right:10px;top:8px;background:#000a;padding:4px 8px;border-radius:8px;font:600 13px ui-monospace,Menlo,monospace;
pointer-events:none}.read:empty{display:none}
.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--mut);font-size:12.5px;margin-top:8px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:5px}
.alist .row{display:flex;gap:12px;align-items:center;background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--bad);
border-radius:12px;padding:12px;margin-bottom:8px}.alist .row.ack{border-left-color:var(--abs)}
.alist .row .x{flex:1;min-width:0}.alist b{font-size:16px}.empty{color:var(--mut);text-align:center;padding:40px 10px;font-size:16px}
.who{font-size:13px;color:var(--mut);margin-top:16px;text-align:center}
@media (max-width:560px){.clock{font-size:17px}.bar{gap:8px;padding:8px 12px}.pill{font-size:12px;padding:5px 9px}
.ttl span{display:none}.chip{max-width:90px}main{padding:12px 12px 40px}}
</style></head><body>
<div id="stale">⚠ Plus de nouvelles du PC de surveillance</div>
<div id="ident" class="hidden"><div>👋<b id="identn"></b><span>C'est cet écran-ci</span></div></div>
<div id="login" class="hidden"><form class="card" id="lf">
 <div class="logo"><img src="data:image/png;base64,__ICON__" alt="" width="56" height="56"></div><h1 id="lt">RF Technical Monitor</h1><p>Surveillance HF en direct</p>
 <label for="ln">Ton nom (pour que la régie sache qui regarde)</label>
 <input class="in" id="ln" maxlength="32" placeholder="ex. Alex — FOH" autocomplete="name">
 <div id="lpw"><label for="lp">Mot de passe</label><input class="in" id="lp" type="password" autocomplete="current-password"></div>
 <button class="btn pri" type="submit" id="lgo">Entrer</button><button class="btn hidden" type="button" id="lcancel" style="width:100%;margin-top:8px">Annuler</button>
 <div class="err" id="le"></div></form></div>
<div id="app" class="hidden">
 <header class="top"><div class="bar"><div class="logo"><img src="data:image/png;base64,__ICON__" alt="" width="38" height="38" style="border-radius:10px;display:block"></div>
  <div class="ttl"><b id="t">RF Technical Monitor</b><span id="meta" class="mut"></span></div>
  <span id="pill" class="pill"></span><span id="clock" class="clock"></span><button id="me" class="chip" title="Changer de nom"></button><a id="lng" class="chip" href="?lang=en" title="English" style="text-decoration:none;color:inherit">EN</a></div>
  <nav id="nav"></nav></header>
 <section id="al"></section><main id="view"></main>
</div>
<script>
const VIEWS=__VIEWS__;Object.assign(VIEWS,/*__VIEWS_X__*/{});
const EXT={};   // 7.68 : vues ajoutées par une autre version (V8) : EXT[clé]={mount(el), update(st)}
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const LS={get(k,d){try{const v=localStorage.getItem(k);return v==null?d:v}catch(e){return d}},set(k,v){try{localStorage.setItem(k,v)}catch(e){}}};
let editing=false,D=null,last=0,cur="",mounted=null,spec=null,specT=0,wf=null,busy=false;
const lay=r=>r.scene+(r.group?" › "+r.group:"");
function route(){const h=(location.hash||"").replace(/^#\/?/,"");return h}
async function api(u,o){return fetch(u,Object.assign({cache:"no-store",credentials:"same-origin"},o||{}))}
function post(u,b){return api(u,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)})}
// ---------- connexion
function showLogin(needPw,msg){const was=!$("#login").classList.contains("hidden");
 $("#app").classList.add("hidden");$("#login").classList.remove("hidden");$("#lpw").classList.toggle("hidden",!needPw);
 if(was)return;   // déjà affiché : surtout ne pas effacer ce que la personne est en train de taper
 $("#ln").value=LS.get("name","");$("#le").textContent=msg||"";(LS.get("name","")&&needPw?$("#lp"):$("#ln")).focus()}
function closeLogin(){editing=false;$("#lcancel").classList.add("hidden");$("#lgo").textContent="Entrer";
 $("#login").classList.add("hidden");$("#app").classList.remove("hidden")}
$("#lcancel").onclick=()=>closeLogin();
$("#lf").onsubmit=async e=>{e.preventDefault();const name=$("#ln").value.trim()||"Invité";
 if(editing&&D&&D.me){let r;try{r=await post("renommer",{name:name})}catch(x){$("#le").textContent="PC injoignable";return}
  if(r.ok){const j=await r.json();LS.set("name",j.name);D.me=j.name;closeLogin();render();return}
  editing=false}
 let r;try{r=await post("connexion",{name:name,password:$("#lp").value})}catch(x){$("#le").textContent="PC injoignable";return}
 if(r.ok){LS.set("name",name);$("#lp").value="";closeLogin();tick();return}
 $("#le").textContent=r.status===429?"Trop d'essais : attends une minute.":"Mot de passe incorrect."};
$("#me").onclick=()=>{editing=true;$("#login").classList.add("hidden");showLogin(false,"");
 $("#ln").value=(D&&D.me)||LS.get("name","");$("#lcancel").classList.remove("hidden");$("#lgo").textContent="Changer de nom";$("#ln").select()};
// ---------- boucle
async function tick(){if(busy)return;busy=true;try{
 const v=route();let r;
 try{r=await api("etat.json?v="+encodeURIComponent(v))}catch(e){return}
 if(r.status===401){editing=false;showLogin(true);return}
 const d=await r.json();last=Date.now();D=d;
 if(!d.me){const n=LS.get("name","");if(n&&!d.password){await post("connexion",{name:n,password:""});}
  else if(!n){showLogin(d.password);return}}
 if(!editing){$("#login").classList.add("hidden");$("#app").classList.remove("hidden")}
 if(d.me&&d.me!==LS.get("name",""))LS.set("name",d.me);       // renommé depuis le PC
 $("#ident").classList.toggle("hidden",!d.ident);$("#identn").textContent=d.me||"";
 if((v==="spectre"||v==="waterfall"||v==="terrain")&&d.views.includes(v)){try{const s=await api("spectre.json");if(s.ok){spec=await s.json()}}catch(e){}}
 if(v==="tech"&&d.views.includes(v)){try{const t=await api("tech.json");TS=t.status;TJ=await t.json()}catch(e){}}
 render()}finally{busy=false;$("#stale").style.display=(last&&Date.now()-last>8000)?"block":"none"}}
function clock(){const n=new Date();$("#clock").textContent=n.toLocaleTimeString("fr-FR",{hour12:false})}
setInterval(clock,500);clock();setInterval(tick,1000);tick();
window.addEventListener("hashchange",()=>{render();tick()});
window.addEventListener("resize",()=>{if(mounted==="spectre"||mounted==="waterfall"){wf=null;draw()}else if(mounted==="mur")render()});
// ---------- rendu
function render(){if(!D)return;const st=D.state,v0=route(),v=(v0===""||D.views.includes(v0))?v0:"";
 $("#t").textContent=st.title||"RF Technical Monitor";document.title=st.title||"RF Technical Monitor";$("#lt").textContent=st.title||"RF Technical Monitor";
 $("#meta").textContent=(st.running?"● en surveillance":"○ arrêté")+(st.cycle?" · cycle "+st.cycle:"")+(st.ver?" · v"+st.ver:"");
 const un=st.alarms.filter(a=>!a.acked).length,all=st.alarms.length,p=$("#pill");
 p.className="pill "+(un?"bad":(all?"":"ok"));p.textContent=un?("⚠ "+un+" alarme"+(un>1?"s":"")):(all?all+" acquittée"+(all>1?"s":""):"✔ Tout va bien");
 p.onclick=()=>{if(D.views.includes("alarmes"))location.hash="#/alarmes"};
 $("#me").textContent="👤 "+(D.me||"Invité");
 $("#nav").innerHTML=`<a href="#/" class="${v===""?"on":""}">🏠 Accueil</a>`+D.views.map(k=>`<a href="#/${k}" class="${v===k?"on":""}">${VIEWS[k][0]} ${VIEWS[k][1]}</a>`).join("");
 $("#al").innerHTML=(v==="alarmes"||v==="regie")?"":st.alarms.filter(a=>!a.acked).slice(0,3).map(alHtml).join("");
 if(mounted!==v){mounted=v;wf=null;mount(v)}update(v)}
function alHtml(a){return `<div class="al${a.acked?" ack":""}"><div class="x">⚠ ${esc(a.kind)} — ${esc(a.name)}<small>${a.freq?a.freq.toFixed(3)+" MHz":""}${a.layer?" · "+esc(a.layer):""}${a.info?" · "+esc(a.info):""}${a.acked?" · acquittée":""}${a.hint?`<span class="hint">→ ${esc(a.hint)}</span>`:""}</small></div>${D.ack&&!a.acked?`<button data-id="${a.id}">Acquitter</button>`:""}</div>`}
document.addEventListener("click",e=>{const b=e.target.closest("button[data-id]");if(b)ack(b.dataset.id==="all"?"all":+b.dataset.id)});
async function ack(id){let pin=LS.get("pin","");if(!pin){pin=prompt("Code PIN (réglé sur le PC de surveillance) :")||"";if(!pin)return}
 let r;try{r=await post("acquitter",{pin:pin,id:id})}catch(e){alert("PC injoignable");return}
 if(r.ok){LS.set("pin",pin);tick();return}
 try{localStorage.removeItem("pin")}catch(x){}
 alert(r.status===429?"Trop d'essais : réessaie dans une minute.":r.status===403?"Code faux (ou acquittement désactivé sur le PC).":"Erreur "+r.status)}
// ---------- chasse au brouilleur : commande (code PIN) + bip joué PAR LE TÉLÉPHONE (même formule que le PC)
async function hunt(action){let pin=LS.get("pin","");if(!pin){pin=prompt("Code PIN (réglé sur le PC de surveillance) :")||"";if(!pin)return}
 const b={pin:pin,action:action,f:parseFloat($("#hf").value)||0,span:parseFloat($("#hs").value)||2,follow:$("#hfo").checked,dev:parseInt($("#hd").value||"0")};
 let r;try{r=await post("chasse",b)}catch(e){alert("PC injoignable");return}
 if(r.ok){LS.set("pin",pin);tick();return}
 if(r.status===403)try{localStorage.removeItem("pin")}catch(x){}
 alert(r.status===429?"Trop d'essais : réessaie dans une minute.":r.status===403?"Code faux (ou commande à distance désactivée sur le PC).":"Erreur "+r.status)}
// ---------- 🗺 « je suis ici » sur le plan (carte de chaleur) : même code PIN que la chasse
async function huntCmd(b){let pin=LS.get("pin","");if(!pin){pin=prompt("Code PIN (réglé sur le PC de surveillance) :")||"";if(!pin)return}
 let r;try{r=await post("chasse",Object.assign({pin:pin},b))}catch(e){alert("PC injoignable");return}
 if(r.ok){LS.set("pin",pin);tick();return}
 if(r.status===403)try{localStorage.removeItem("pin")}catch(x){}
 alert(r.status===429?"Trop d'essais : réessaie dans une minute.":r.status===403?"Code faux (ou commande à distance désactivée sur le PC).":"Erreur "+r.status)}
function huntMark(x,y){const h=D.state.hunt||{};if(!h.on){alert("Lance d'abord la chasse : le point note le niveau mesuré.");return}huntCmd({action:"mark",x:x,y:y})}
// ---------- 🎒 terrain : le tinySA volant dit où il est, et garde des scans (code PIN)
async function terrain(action,extra){let pin=LS.get("pin","");if(!pin){pin=prompt("Code PIN (réglé sur le PC de surveillance) :")||"";if(!pin)return}
 const b=Object.assign({pin:pin,action:action,dev:parseInt($("#td").value||"0")},extra||{});
 let r;try{r=await post("terrain",b)}catch(e){alert("PC injoignable");return}
 if(r.ok){LS.set("pin",pin);tick();return}
 if(r.status===403)try{localStorage.removeItem("pin")}catch(x){}
 alert(r.status===429?"Trop d'essais : réessaie dans une minute.":r.status===403?"Code faux (ou commande à distance désactivée sur le PC).":"Erreur "+r.status)}
function tChecked(){return[...document.querySelectorAll("#tsc input:checked")].map(c=>c.value)}
document.addEventListener("click",e=>{const b=e.target.closest("button[data-del]");if(b&&confirm("Effacer ce scan gardé ?\n"+b.dataset.del))terrain("delete",{name:b.dataset.del})});
let AC=null,hTimer=null,hLvl=null;
function huntAudio(){try{AC=AC||new (window.AudioContext||window.webkitAudioContext)();if(AC.state==="suspended")AC.resume()}catch(e){}}
function huntTone(l){const x=Math.max(0,Math.min(1,(l+100)/70));return[400+1600*x,1000-920*x]}
function blip(hz){if(!AC)return;const o=AC.createOscillator(),g=AC.createGain(),t=AC.currentTime;o.frequency.value=hz;g.gain.setValueAtTime(0,t);
 g.gain.linearRampToValueAtTime(.4,t+.005);g.gain.linearRampToValueAtTime(0,t+.045);o.connect(g).connect(AC.destination);o.start(t);o.stop(t+.05)}
function huntBeep(l){hLvl=l;if(l==null){if(hTimer){clearTimeout(hTimer);hTimer=null}return}if(hTimer)return;
 const step=()=>{if(hLvl==null||mounted!=="chasse"){hTimer=null;return}const[hz,per]=huntTone(hLvl);blip(hz);hTimer=setTimeout(step,Math.max(60,per))};step()}
function layers(){return[...new Set(D.state.rows.map(lay).filter(x=>x))].sort()}
function layerSel(id){const k=LS.get("flt","");return `<select class="in" id="${id}"><option value="">Toutes les couches</option>${layers().map(l=>`<option${l===k?" selected":""}>${esc(l)}</option>`).join("")}</select>`}
function keepLayer(id){const s=$("#"+id);if(s)s.onchange=()=>{LS.set("flt",s.value);update(mounted)}}
function inLayer(r){const f=LS.get("flt","");return !f||lay(r)===f||r.scene===f}
function mount(v){const el=$("#view");
 if(EXT[v]){EXT[v].mount(el);return}
 if(v===""){el.innerHTML=`<div class="sum" id="kpi"></div><div class="home">${D.views.map(k=>`<a class="vcard" href="#/${k}"><div class="i">${VIEWS[k][0]}</div><b>${VIEWS[k][1]}</b><span>${VIEWS[k][2]}</span></a>`).join("")}</div><div class="who">Connecté en tant que <b>${esc(D.me||"Invité")}</b>${D.state.ver?" · RF Technical Monitor v"+esc(D.state.ver):""}</div>`;return}
 if(v==="liste"){el.innerHTML=`<div class="tools">${layerSel("flt")}<input class="in" id="q" placeholder="🔎 Nom, fréquence…"><label class="sw"><input type="checkbox" id="oo"> Occupées seulement</label></div><div class="grid" id="g"></div>`;
  keepLayer("flt");$("#q").oninput=()=>update(v);$("#oo").onchange=()=>update(v);return}
 if(v==="mur"){el.innerHTML=`<div class="tools">${layerSel("flt")}<label class="sw"><input type="checkbox" id="oo"> Occupées / faibles seulement</label><button class="btn" id="fs">⛶ Plein écran</button></div><div class="wall" id="g"></div>`;
  keepLayer("flt");$("#oo").onchange=()=>update(v);$("#fs").onclick=()=>{const g=$("#view");(g.requestFullscreen?g.requestFullscreen():g.webkitRequestFullscreen&&g.webkitRequestFullscreen())};return}
 if(v==="spectre"||v==="waterfall"){el.innerHTML=`<div class="tools"><select class="in" id="band"></select>${v==="spectre"?'<label class="sw"><input type="checkbox" id="mh" checked> Max hold</label><label class="sw"><input type="checkbox" id="rm"> Rémanence</label>':""}<label class="sw"><input type="checkbox" id="mk" checked> Mes fréquences</label></div><div class="plot"><canvas id="cv"></canvas><div class="read" id="rd"></div></div><div class="legend" id="lg"></div>`;
  $("#band").onchange=()=>{LS.set("band",$("#band").value);wf=null;pers=null;draw()};
  const rmc=$("#rm");if(rmc){rmc.checked=LS.get("rm","")==="1";rmc.onchange=()=>{LS.set("rm",rmc.checked?"1":"");pers=null;draw()}}["mh","mk"].forEach(i=>{const c=$("#"+i);if(c)c.onchange=()=>draw()});
  const cv=$("#cv");cv.onpointermove=cv.onpointerdown=e=>readout(e);cv.onpointerleave=()=>{$("#rd").textContent=""};return}
 if(v==="chasse"){const h=D.state.hunt||{};el.innerHTML=`<div class="tools"><input class="in" id="hf" type="number" step="0.001" inputmode="decimal" value="${h.f||""}" placeholder="MHz" style="max-width:140px"><select class="in" id="hs">${[1,2,5,10].map(x=>`<option value="${x}"${x==(h.span||2)?" selected":""}>± ${x/2} MHz</option>`).join("")}</select><select class="in" id="hd">${(h.devs||[]).map((n,i)=>`<option value="${i}"${i==(h.dev!=null?h.dev:(h.devs||[]).length-1)?" selected":""}>${esc(n)}</option>`).join("")}</select><label class="sw"><input type="checkbox" id="hfo"${h.follow?" checked":""}> Suivre le plus fort</label></div><div class="tools"><button class="btn pri" id="hgo" style="width:auto;margin:0"></button><button class="btn" id="hrs">↺ Max à zéro</button><label class="sw"><input type="checkbox" id="hmu"> Muet</label></div><div class="hb"><div class="lv" id="hl">—</div><div class="bar"><i id="hbar" style="width:0%"></i></div><div class="sub" id="hsub">Branche le tinySA portable, choisis la fréquence puis « Chasser ». Le téléphone bippe plus vite et plus aigu quand tu te rapproches.</div></div><div class="tools hidden" id="hmt"><b>🗺 Où suis-je ?</b></div><div class="sub hidden" id="hmh">Touche le plan là où tu es : le niveau de la chasse y est noté (carte de chaleur sur le PC).</div><div id="hmap" class="hidden" style="position:relative;margin:8px 0"><img id="hmi" alt="" style="width:100%;border-radius:12px;display:block;cursor:crosshair"><div id="hdots"></div></div><div class="tools"><button class="btn hidden" id="hun">↶ Retirer mon dernier point</button></div>`;
  $("#hd").classList.toggle("hidden",(h.devs||[]).length<2);
  $("#hgo").onclick=()=>{huntAudio();const on=D.state.hunt&&D.state.hunt.on;hunt(on?"stop":"start")};
  $("#hrs").onclick=()=>hunt("reset");
  $("#hmi").onclick=e=>{const r=e.target.getBoundingClientRect();huntMark((e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height)};
  $("#hun").onclick=()=>huntCmd({action:"unmark"});return}
 if(v==="tech"){el.innerHTML=`<div id="tlog" class="hb hidden"><b>🛠 Accès Tech</b><div class="sub">Réservé à l’équipe HF : mot de passe Tech, puis accord sur le PC de surveillance.</div><div class="tools"><input class="in" id="tpw" type="password" placeholder="Mot de passe Tech" autocomplete="current-password"><button class="btn pri" id="tgo" style="width:auto;margin:0">Demander l’accès</button></div><div class="sub" id="terr"></div></div><div id="twait" class="hb hidden"><b>⏳ En attente</b><div class="sub">Accepte la demande sur le PC de surveillance (fenêtre « Accès Tech »).</div></div><div id="toff" class="hb hidden"><div class="sub">Page Tech désactivée : règle un mot de passe Tech sur le PC (🔔 Alertes et page web).</div></div><div id="tapp" class="hidden"><div class="tools"><b id="trun"></b><button class="btn pri" id="tstart" style="width:auto;margin:0">▶ Démarrer</button><button class="btn" id="tstop">■ Arrêter</button><button class="btn" id="tsnz">🔕 Silence 15 min</button><button class="btn" id="tack">✔ Tout acquitter</button><button class="btn" id="tsave">💾 Enregistrer</button><button class="btn" id="tout">Quitter Tech</button></div><div class="tools hidden" id="tstb"><b>📸 État</b><select class="in" id="tstate"></select></div><div class="mut" id="tmsg2" style="margin-bottom:12px"></div><div class="tools"><b>Seuils</b><label class="sw">Occupé au-dessus de <input class="in" id="tocc" type="number" step="1" style="width:90px;min-width:0;flex:none"> dBm</label><label class="sw"><input type="checkbox" id="twon"> Faible dès</label><input class="in" id="twk" type="number" step="1" style="width:90px;min-width:0;flex:none"><label class="sw">TX absent après <input class="in" id="tabs" type="number" step="1" style="width:80px;min-width:0;flex:none"> s</label><button class="btn" id="tthr">Appliquer</button></div><div class="tools"><b>📡 Mes tinySA</b></div><div class="alist" id="tdevs"></div><div id="tsg" class="hb hidden"></div><div class="tools"><b>⌨ Ajouter des micros</b></div><textarea class="in" id="tqa" rows="3" style="width:100%;box-sizing:border-box;margin-bottom:8px" placeholder="HF1 558.2, HF2 574, IEM 606.5 PSM — ou colle un message"></textarea><div class="tools"><select class="in" id="tast"></select><input class="in" id="tasc" list="tscl" placeholder="Scène"><input class="in" id="tagr" list="tgrl" placeholder="Groupe"><datalist id="tscl"></datalist><datalist id="tgrl"></datalist><button class="btn pri" id="tadd" style="width:auto;margin:0">＋ Ajouter</button></div><div class="tools"><b>📋 Fréquences</b><input class="in" id="tq" placeholder="Chercher…"></div><div class="alist" id="tws"></div><div class="tools"><b>👥 Connectés</b></div><div class="alist" id="tcl"></div></div>`;
  techMount();return}
 if(v==="terrain"){el.innerHTML=`<div class="tools"><b>📍 Où est ce tinySA ?</b><select class="in" id="td"></select></div><div class="tools" id="tsc"></div><div class="tools"><button class="btn" id="tall">☑ Toutes</button><button class="btn pri" id="tap" style="width:auto;margin:0">📡 Ce tinySA est ici</button></div><div class="hb"><div class="sub" id="tlive"></div><div class="tools"><input class="in" id="tlab" placeholder="Étiquette (facultatif) : jardin, régie…" maxlength="40"><button class="btn pri" id="tsv" style="width:auto;margin:0">💾 Garder ce scan</button><button class="btn" id="trs">↺ Nouveau scan ici</button></div><div class="sub" id="tmsg"></div></div><div class="tools"><b>📈 Ce que voit le tinySA</b><label class="sw"><input type="checkbox" id="rm" checked> Rémanence</label><label class="sw"><input type="checkbox" id="mk"> Mes fréquences</label><select class="in" id="tmh"></select></div><div class="plot"><canvas id="cv"></canvas><div class="read" id="rd"></div></div><div class="legend" id="lg"></div><div class="tools"><b>📊 Scans gardés (pour la coordination)</b></div><div class="alist" id="tsaved"></div>`;
  $("#td").onchange=()=>{$("#tsc").dataset.k="";$("#tsc").dataset.dirty="";update(v)};
  $("#tsc").onchange=()=>{$("#tsc").dataset.dirty="1"};
  $("#tall").onclick=()=>{const cs=[...document.querySelectorAll("#tsc input")],all=cs.every(c=>c.checked);cs.forEach(c=>c.checked=!all);$("#tsc").dataset.dirty="1"};
  $("#tap").onclick=()=>{$("#tsc").dataset.dirty="";terrain("assign",{scenes:tChecked()})};
  $("#tsv").onclick=()=>{terrain("save",{label:$("#tlab").value});$("#tlab").value=""};
  pers=null;["rm","mk"].forEach(i=>{$("#"+i).onchange=()=>{if(i==="rm")pers=null;draw()}});
  $("#tmh").onchange=()=>{LS.set("tmh",$("#tmh").value);pers=null;draw()};
  const cv=$("#cv");cv.onpointermove=cv.onpointerdown=e=>readout(e);cv.onpointerleave=()=>{$("#rd").textContent=""};
  $("#trs").onclick=()=>{if(confirm("Repartir de zéro ici ? Le max hold de ce tinySA est remis à zéro (les scans déjà gardés restent)."))terrain("reset")};return}
 if(v==="regie"){el.innerHTML=`<div class="tools">${layerSel("flt")}<button class="btn" id="fs">⛶ Plein écran</button></div><div id="ra"></div><div class="rg" id="g"></div>`;
  keepLayer("flt");$("#fs").onclick=()=>{const g=$("#view");(g.requestFullscreen?g.requestFullscreen():g.webkitRequestFullscreen&&g.webkitRequestFullscreen())};return}
 if(v==="alarmes"){el.innerHTML=`<div class="tools"><b style="flex:1">Alarmes en cours</b><span id="aa"></span></div><div class="alist" id="g"></div>`;return}}
function update(v){const st=D.state;
 if(EXT[v]){if(EXT[v].update)EXT[v].update(st);return}
 if(v===""){const rs=st.rows,occ=rs.filter(r=>r.state==="occ").length,ab=rs.filter(r=>r.alarm).length,k=$("#kpi");
  if(k)k.innerHTML=`<div class="kpi"><b>${rs.length}</b><span>fréquences</span></div><div class="kpi"><b>${rs.filter(r=>r.tone==="ok"||r.tone==="free").length}</b><span>OK / libres</span></div><div class="kpi"><b>${occ}</b><span>avec signal</span></div><div class="kpi"><b style="color:${ab?"var(--bad)":"inherit"}">${ab}</b><span>en alarme</span></div>`;return}
 if(v==="liste"){const q=($("#q").value||"").toLowerCase(),oo=$("#oo").checked;
  $("#g").innerHTML=st.rows.filter(r=>inLayer(r)&&(!oo||r.state==="occ"||r.state==="weak")&&(!q||(r.name+" "+r.freq.toFixed(3)+" "+r.status).toLowerCase().includes(q))).map(r=>`<div class="c ${r.tone}${r.alarm?" alarm":""}"${r.color&&!r.alarm?` style="border-left-color:${r.color}"`:""}><div class="n">${r.alarm?"⚠ ":""}${esc(r.name)}</div><div class="f">${r.freq.toFixed(3)} MHz${r.status?" · "+esc(r.status):""}</div><div class="l">${r.alarm&&!r.state_txt.includes(r.alarm)?esc(r.alarm)+" · ":""}${esc(r.state_txt)}${r.level_txt?" · "+esc(r.level_txt):""}</div><div class="s">${esc(lay(r))}</div></div>`).join("")||'<div class="empty">Aucune fréquence</div>';return}
 if(v==="mur"){const oo=$("#oo").checked,rs=st.rows.filter(r=>inLayer(r)&&(!oo||r.alarm||r.state==="occ"||r.state==="weak")),g=$("#g");
  const W=g.clientWidth||innerWidth,H=Math.max(200,innerHeight-g.getBoundingClientRect().top-20),n=Math.max(1,rs.length);
  let cols=Math.max(1,Math.min(n,Math.round(Math.sqrt(n*W/H/1.4))));const tw=Math.max(140,W/cols-10),th=Math.max(90,Math.min(H/Math.ceil(n/cols)-10,tw*.8));
  g.style.setProperty("--tw",tw+"px");g.style.setProperty("--th",th+"px");g.style.setProperty("--fs",Math.max(13,Math.min(40,th*.17,tw/9))+"px");
  g.innerHTML=rs.map(r=>`<div class="t ${r.tone}${r.alarm?" alarm":""}"${r.color&&!r.alarm&&r.tone!=="none"?` style="background:${r.color}${r.tone==="bad"?"aa":"55"};border-color:${r.color}"`:""}><div class="n">${r.alarm?"⚠ ":""}${esc(r.name)}</div><div class="f">${r.freq.toFixed(3)} MHz</div><div class="l">${esc(r.state_txt)}${r.level_txt?" · "+esc(r.level_txt):""}</div></div>`).join("")||'<div class="empty">Rien à afficher</div>';return}
 if(v==="regie"){const rs=st.rows.filter(inLayer),un=st.alarms.filter(a=>!a.acked);
  const hd=st.health&&st.health.data;
  const hb=!st.running?`<div class="rg-al bad">■ Surveillance arrêtée<small>Rien n'est surveillé en ce moment.</small></div>`
   :!hd?`<div class="rg-al bad">⚠ État de surveillance indéterminé</div>`
   :hd.tone!=="ok"?`<div class="rg-al ${hd.tone==="bad"?"bad":"warn"}">${esc(hd.text)}</div>`:"";
  $("#ra").innerHTML=(un.length?un.slice(0,4).map(a=>`<div class="rg-al bad">⚠ ${esc(a.kind)} — ${esc(a.name)}<small>${a.freq?a.freq.toFixed(3)+" MHz":""}${a.layer?" · "+esc(a.layer):""}${a.info?" · "+esc(a.info):""}${a.hint?`<span class="hint">→ ${esc(a.hint)}</span>`:""}</small></div>`).join("")+(un.length>4?`<div class="who">+ ${un.length-4} autre(s) alarme(s)</div>`:""):"")
   +(hb||(un.length?"":`<div class="rg-al ok">✔ Tout va bien<small>${rs.length} fréquence(s) surveillée(s)</small></div>`));
  const G={};rs.forEach(r=>{const k=lay(r)||"Sans scène";(G[k]=G[k]||[]).push(r)});
  const ks=Object.keys(G).sort(),g=$("#g"),n=Math.max(1,ks.length),W=g.clientWidth||innerWidth,cols=Math.min(n,W<700?1:(W<1200?2:3));
  g.style.setProperty("--rw",Math.max(220,W/cols-16)+"px");g.style.setProperty("--rf",Math.max(18,Math.min(44,(W/cols)/11))+"px");
  const h=ks.map(k=>{const a=G[k],bad=a.filter(r=>r.alarm),wn=a.filter(r=>!r.alarm&&(r.tone==="warn"||r.tone==="bad")),ok=a.filter(r=>r.tone==="ok"||r.tone==="free").length;
   const c=bad.length?"bad":(wn.length?"warn":(a.every(r=>r.paused)?"none":(ok?"ok":"none"))),pb=[...bad,...wn].slice(0,6).map(r=>esc(r.name)+(r.alarm?" ("+esc(r.alarm)+")":"")).join(" · ");
   const kt=bad.length?`⚠ ${bad.length} alarme(s)`:(wn.length?`◐ ${wn.length} à surveiller`:(a.every(r=>r.paused)?`💤 pas sur scène`:`✔ ${ok} / ${a.length} OK`));
   return `<div class="g ${c}"><b>${esc(k)}</b><div class="k">${kt}</div>${pb?`<div class="p">${pb}</div>`:""}</div>`}).join("");g.innerHTML=h||`<div class="who">Aucune fréquence surveillée.</div>`;return}
 if(v==="chasse"){const h=st.hunt||{},hd=$("#hd"),ds=h.devs||[];
  if(hd.options.length!==ds.length){hd.innerHTML=ds.map((n,i)=>`<option value="${i}">${esc(n)}</option>`).join("");hd.value=String(h.dev!=null?h.dev:ds.length-1);hd.classList.toggle("hidden",ds.length<2)}
  if(!$("#hf").value&&h.f)$("#hf").value=h.f;
  $("#hgo").textContent=h.on?"■ Arrêter la chasse":"▶ Chasser";
  $("#hl").textContent=h.on&&h.level!=null?h.level_txt:"—";
  $("#hbar").style.width=(h.on&&h.level!=null?Math.max(0,Math.min(100,(h.level+110)/90*100)):0)+"%";
  if(!h.on&&h.msg)$("#hsub").textContent=h.msg;
  if(h.on)$("#hsub").textContent=(h.level==null?"Attends le premier balayage…":"Pic à "+h.fpk.toFixed(3)+" MHz"+(h.best!=null?" · max vu "+h.best_txt+" ("+(h.level-h.best).toFixed(1)+" dB)":""))+" · "+(h.devs&&h.devs[h.dev]||"");
  ["#hmt","#hmh","#hmap","#hun"].forEach(id=>$(id).classList.toggle("hidden",!h.map));
  const mi=$("#hmi");if(h.map&&mi.dataset.t!==String(h.map_t)){mi.dataset.t=String(h.map_t);mi.src="carte.png?t="+h.map_t}
  const mk=JSON.stringify(h.marks||[]);if($("#hdots").dataset.k!==mk){$("#hdots").dataset.k=mk;const ms=h.marks||[],lv=ms.map(m=>m.level),lo=Math.min(...lv),hi=Math.max(...lv);
   $("#hdots").innerHTML=ms.map(m=>{const t=hi>lo?(m.level-lo)/(hi-lo):1,c=m.c||(t<.5?"#3b82f6":t<.8?"#facc15":"#ef4444");return`<i style="position:absolute;left:${m.x*100}%;top:${m.y*100}%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:${c};border:2px solid #fff"></i>`}).join("")}
  huntBeep(h.on&&!$("#hmu").checked?h.level:null);return}
 if(v==="tech"){techUpdate();return}
 if(v==="terrain"){const T=st.terrain||{},ds=T.devs||[],td=$("#td"),box=$("#tsc"),scs=T.scenes||[];
  const dk=ds.map(d=>d.label).join("|");
  if(td.dataset.k!==dk){td.innerHTML=ds.map((d,i)=>`<option value="${i}">${esc(d.label)}</option>`).join("");td.dataset.k=dk;td.value=String(Math.max(0,ds.length-1));td.classList.toggle("hidden",ds.length<2);box.dataset.k=""}
  const di=parseInt(td.value||"0"),d=ds[di]||{scenes:[],live:false},mine=d.scenes||[],sk=scs.join("|")+"#"+di+"#"+mine.join("|");
  const noSc="Crée d’abord tes scènes sur le PC (« Classer par scène › groupe »).";
  if(box.dataset.k!==sk&&!box.dataset.dirty){const h=scs.map(s=>`<label class="sw"><input type="checkbox" value="${esc(s)}"${mine.includes(s)?" checked":""}> ${esc(s)}</label>`).join("");box.innerHTML=h||esc(noSc);box.dataset.k=sk}
  const lv=T.live||{},off="⚠ Ce tinySA n’est pas connecté (▶ Démarrer sur le PC).",none="Ce tinySA ne surveille aucune scène : coche où tu es puis « Ce tinySA est ici ».";
  const tl=s=>{const l=lv[s],t=l?l.bands+" bande(s) en max hold · dernier balayage il y a "+l.age+" s":"pas encore de balayage";return esc(s+" : "+t)};
  $("#tlive").innerHTML=[d.live?"":esc(off)].concat(mine.length?mine.map(tl):[esc(none)]).filter(x=>x).join("<br>");
  $("#tmsg").textContent=T.msg||"";
  const sv=T.saved||[],noSv="Aucun scan gardé pour l’instant";
  const hs=sv.map(x=>`<div class="row" style="border-left-color:#64748b"><div class="x"><b>${esc(x.name)}</b><div class="mut">${esc(x.scene)} · ${x.lo.toFixed(1)}–${x.hi.toFixed(1)} MHz · ${x.n} points · ${new Date(x.t*1000).toLocaleString("fr-FR",{hour12:false,day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"})}${x.auto?" · mis à jour tout seul":""}</div></div><button class="ackbtn" data-del="${esc(x.name)}">🗑</button></div>`).join("");
  $("#tsaved").innerHTML=hs||`<div class="empty">${esc(noSv)}</div>`;
  const scm=Object.keys((spec&&spec.scenes)||{}),tm=$("#tmh"),ok=["","*"].concat(scm).join("|");
  if(tm.dataset.k!==ok){const want=tm.value||LS.get("tmh","*");tm.innerHTML=`<option value="">Max hold : aucun</option><option value="*">Max hold : toutes les scènes</option>`+scm.map(x=>`<option value="${esc(x)}">Max hold : ${esc(x)}</option>`).join("");tm.value=[""].concat(["*"],scm).includes(want)?want:"*";tm.dataset.k=ok}
  if(spec&&spec.t!==specT)specT=spec.t;draw();return}
 if(v==="alarmes"){const al=st.alarms,un=al.filter(a=>!a.acked).length;$("#aa").innerHTML=D.ack&&un>1?'<button class="btn" data-id="all">✔ Tout acquitter</button>':"";
  $("#g").innerHTML=al.map(a=>`<div class="row${a.acked?" ack":""}"><div class="x"><b>⚠ ${esc(a.kind)} — ${esc(a.name)}</b><div class="mut">${a.freq?a.freq.toFixed(3)+" MHz":""}${a.layer?" · "+esc(a.layer):""}${a.info?" · "+esc(a.info):""} · depuis ${new Date(a.t0*1000).toLocaleTimeString("fr-FR",{hour12:false})}${a.acked?" · acquittée":""}${a.hint?`<span class="hint">→ ${esc(a.hint)}</span>`:""}</div></div>${D.ack&&!a.acked?`<button class="ackbtn" data-id="${a.id}">Acquitter</button>`:""}</div>`).join("")||'<div class="empty">✔ Aucune alarme en cours</div>';
  if(!D.ack&&al.length)$("#g").insertAdjacentHTML("beforeend",'<div class="who">Acquittement depuis le téléphone désactivé (code PIN à régler sur le PC).</div>');return}
 if(v==="spectre"||v==="waterfall"){const b=$("#band"),bs=(spec&&spec.bands)||[],want=LS.get("band","*");
  const opts='<option value="*">Toutes les bandes</option>'+bs.map(x=>`<option${x.name===want?" selected":""}>${esc(x.name)}</option>`).join("");
  if(b.dataset.o!==opts){b.innerHTML=opts;b.dataset.o=opts;b.value=bs.some(x=>x.name===want)?want:"*"}
  if(spec&&spec.t!==specT){specT=spec.t;if(v==="waterfall")wfAdd()}draw()}}
// ---------- 🛠 Tech : gérer le serveur (mot de passe Tech, puis accord sur le PC)
let TS=0,TJ=null;
async function tcmd(b){let r;try{r=await post("tech",b)}catch(e){alert("PC injoignable");return}
 if(r.status===403){TS=403;TJ={login:true};techUpdate();return}
 if(!r.ok){alert("Refusé ("+r.status+")");return}setTimeout(tick,400)}
async function tlogin(){const pw=$("#tpw").value;if(!pw)return;let r;try{r=await post("tech/login",{password:pw})}catch(e){$("#terr").textContent="PC injoignable";return}
 $("#tpw").value="";if(r.ok){$("#terr").textContent="";tick();return}
 $("#terr").textContent=r.status===429?"Trop d’essais : attends 5 minutes.":r.status===403?"Mot de passe Tech incorrect.":"Refusé."}
function techMount(){$("#tgo").onclick=tlogin;$("#tpw").onkeydown=e=>{if(e.key==="Enter")tlogin()};
 $("#tstart").onclick=()=>tcmd({action:"run",on:true});
 $("#tstop").onclick=()=>{if(confirm("Arrêter la surveillance ?"))tcmd({action:"run",on:false})};
 $("#tsnz").onclick=()=>tcmd({action:"snooze",min:15});$("#tack").onclick=()=>tcmd({action:"ack_all"});
 $("#tsave").onclick=()=>tcmd({action:"save"});$("#tout").onclick=async()=>{await post("tech/logout",{});tick()};
 ["tocc","twk","tabs","twon"].forEach(k=>{$("#"+k).oninput=()=>{$("#tthr").dataset.dirty="1"}});
 $("#tthr").onclick=()=>{$("#tthr").dataset.dirty="";tcmd({action:"thr",occ:+$("#tocc").value,weak:+$("#twk").value,weak_on:$("#twon").checked,absent:+$("#tabs").value})};
 $("#tadd").onclick=()=>{const t=($("#tqa").value||"").trim();if(!t){alert("Tape au moins une fréquence (ex. HF1 558.2)");return}
  tcmd({action:"quick_add",text:t,status:$("#tast").value,scene:$("#tasc").value,group:$("#tagr").value});$("#tqa").value=""};
 $("#tasc").oninput=()=>{$("#tgrl").dataset.k=""};
 $("#tq").oninput=()=>{$("#tws").dataset.k="";techUpdate()};
 $("#tstate").onchange=()=>{const v=$("#tstate").value;$("#tstate").dataset.k="";tcmd({action:"state",name:v})}}
document.addEventListener("click",e=>{const b=e.target.closest("[data-tdel],[data-ted],[data-tid],[data-tmu],[data-trp],[data-trf],[data-tsx]");if(!b||mounted!=="tech")return;
 if(b.dataset.trp)tcmd({action:"suggest",key:+b.dataset.trp});
 else if(b.dataset.trf){if(confirm("Remplacer « "+b.dataset.n+" » par "+b.dataset.trf+" MHz ?"))tcmd({action:"replace",key:+b.dataset.tk,f:+b.dataset.trf})}
 else if(b.dataset.tsx)tcmd({action:"sugg_close"});
 else if(b.dataset.tmu)tcmd({action:"mute",key:+b.dataset.tmu,on:b.dataset.on==="1"});
 else if(b.dataset.tdel){if(confirm("Retirer « "+b.dataset.n+" » de la liste ?"))tcmd({action:"watch_del",key:+b.dataset.tdel})}
 else if(b.dataset.ted){const n=prompt("Nom :",b.dataset.n);if(n==null)return;const f=prompt("Fréquence (MHz) :",b.dataset.f);if(f==null)return;
  tcmd({action:"watch_edit",key:+b.dataset.ted,name:n,freq:parseFloat(f.replace(",","."))})}
 else if(b.dataset.tid)tcmd({action:"identify",dev:+b.dataset.tid})});
document.addEventListener("change",e=>{const s=e.target;if(mounted!=="tech")return;
 if(s.dataset.tst!==undefined)tcmd({action:"watch_edit",key:+s.dataset.tst,status:s.value});
 if(s.dataset.tsc!==undefined)tcmd({action:"dev_scenes",dev:+s.dataset.tsc,scenes:s.value?[s.value]:[]})});
function techUpdate(){const sh=(id,on)=>$(id).classList.toggle("hidden",!on);
 const off=TS===403&&TJ&&TJ.off,pend=TJ&&TJ.pending,ok=TS===200&&TJ&&TJ.devs;
 sh("#toff",!!off);sh("#twait",!!pend&&!ok);sh("#tlog",!off&&!pend&&!ok);sh("#tapp",!!ok);if(!ok)return;
 const T=TJ,act=(document.activeElement||{}).id||"",inside=id=>document.activeElement&&$(id).contains(document.activeElement);
 $("#trun").textContent=(T.running?"● en surveillance":"○ arrêté")+(T.snooze?" · 🔕 "+Math.ceil(T.snooze/60)+" min":"")+(T.show?" · "+T.show:"");
 $("#tmsg2").textContent=T.msg||"";
 const sts=T.states||[],sk=JSON.stringify([sts,T.state_cur]);$("#tstb").classList.toggle("hidden",!sts.length);
 if($("#tstate").dataset.k!==sk&&act!=="tstate"){$("#tstate").dataset.k=sk;$("#tstate").innerHTML=`<option value="">Tout actif</option>`+sts.map(x=>`<option${x===T.state_cur?" selected":""}>${esc(x)}</option>`).join("")}
 if(!$("#tthr").dataset.dirty&&!["tocc","twk","tabs"].includes(act)){$("#tocc").value=Math.round(T.thr.occ);$("#twk").value=Math.round(T.thr.weak);$("#twon").checked=T.thr.weak_on;$("#tabs").value=T.thr.absent}
 const so=`<option value="">(aucun statut)</option>`+T.statuses.map(x=>`<option>${esc(x.name)}</option>`).join("");
 const ta=$("#tast");if(ta.dataset.k!==so){const v=ta.value;ta.innerHTML=so;ta.dataset.k=so;ta.value=v}
 const scl=T.scenes.map(x=>`<option value="${esc(x.name)}">`).join("");if($("#tscl").dataset.k!==scl){$("#tscl").dataset.k=scl;$("#tscl").innerHTML=scl}
 const sc0=T.scenes.find(x=>x.name===$("#tasc").value),grl=(sc0?sc0.groups:[]).map(g=>`<option value="${esc(g)}">`).join("");if($("#tgrl").dataset.k!==grl){$("#tgrl").dataset.k=grl;$("#tgrl").innerHTML=grl}
 const sg=T.sugg,sgk=JSON.stringify(sg);if($("#tsg").dataset.k!==sgk){$("#tsg").dataset.k=sgk;$("#tsg").classList.toggle("hidden",!sg);
  if(sg)$("#tsg").innerHTML=`<b>🆘 Remplacer ${esc(sg.name)} · ${sg.freq.toFixed(3)} MHz</b><div class="sub">Libres d’après la mesure, compatibles avec ton plan et l’appareil. Un appui = remplacer (puis règle l’émetteur ET le récepteur).</div>`+(sg.busy?`<div class="sub">⏳ Calcul en cours…</div>`:sg.cands.length?sg.cands.map(c=>`<button class="btn pri" style="margin:6px 0;width:100%" data-trf="${c.f}" data-tk="${sg.key}" data-n="${esc(sg.name)}">${c.f.toFixed(3)} MHz <span class="mut">(${c.d>0?"+":""}${c.d} kHz${c.level?" · "+esc(c.level):""})</span>${c.tag?" ⚠ "+esc(c.tag):""}</button>`).join(""):`<div class="sub">Rien de libre et compatible : essaie la fréquence de secours sur le PC.</div>`)+`<button class="btn" data-tsx="1">Fermer</button>`}
 const scn=T.scenes.map(x=>x.name),dk=JSON.stringify([T.devs,scn]);
 if($("#tdevs").dataset.k!==dk&&!inside("#tdevs")){$("#tdevs").dataset.k=dk;
  $("#tdevs").innerHTML=T.devs.map(d=>`<div class="row" style="border-left-color:${d.live?"var(--ok)":"var(--none)"}"><div class="x"><b>${esc(d.ord)} tinySA · ${esc(d.name)}</b><div class="mut">${d.live?"● en ligne":"○ pas connecté"} · ${esc(d.addr)}${d.cycle?" · cycle "+d.cycle+" s":""}</div></div><select class="in" data-tsc="${d.rank}" style="width:auto;flex:0 1 auto"><option value="">Tout le site</option>${scn.map(x=>`<option${d.scenes.length===1&&d.scenes[0]===x?" selected":""}>${esc(x)}</option>`).join("")}${d.scenes.length>1?`<option disabled selected>${esc(d.scenes.join(" + "))}</option>`:""}</select><button class="btn" data-tid="${d.rank}" title="Identifier">👋</button></div>`).join("")}
 const q=($("#tq").value||"").toLowerCase(),rows=T.watch.filter(w=>!q||(w.name+" "+w.freq+" "+w.scene+" "+w.group).toLowerCase().includes(q)),wk=JSON.stringify(rows)+so;
 if($("#tws").dataset.k!==wk&&!inside("#tws")){$("#tws").dataset.k=wk;
  $("#tws").innerHTML=rows.map(w=>`<div class="row" style="border-left-color:${esc(w.color)}"><div class="x"><b>${esc(w.name)}</b> <span class="mut">${w.freq.toFixed(3)} MHz</span><div class="mut">${esc(w.sig)}${w.level?" · "+esc(w.level):""}${w.scene?" · "+esc(w.scene+(w.group?" › "+w.group:"")):""}</div></div><select class="in" data-tst="${w.key}" style="width:auto;flex:0 1 auto">${w.status?so.replace(`<option>${esc(w.status)}</option>`,`<option selected>${esc(w.status)}</option>`):so}</select><button class="btn" data-trp="${w.key}" title="Remplacer ce micro (3 propositions)">🆘</button><button class="btn" data-tmu="${w.key}" data-on="${w.muted?0:1}" title="${w.muted?"Rallumer":"Éteint (je sais) : pas d’alarme ABSENT"}">${w.muted?"🔔":"💤"}</button><button class="btn" data-ted="${w.key}" data-n="${esc(w.name)}" data-f="${w.freq}" title="Modifier">✏</button><button class="btn" data-tdel="${w.key}" data-n="${esc(w.name)}" title="Retirer">🗑</button></div>`).join("")||`<div class="empty">Aucune fréquence</div>`}
 $("#tcl").innerHTML=T.clients.map(c=>`<div class="row" style="border-left-color:${c.online?"var(--ok)":"var(--none)"}"><div class="x"><b>${esc(c.name)}</b>${c.tech==="ok"?" 🛠":c.tech==="pending"?" ⏳":""}<div class="mut">${esc(c.addr)}${c.view?" · "+esc(c.view):""}</div></div></div>`).join("")||`<div class="empty">—</div>`}
// ---------- spectre / waterfall
function segs(){const bs=(spec&&spec.bands)||[],k=$("#band")?$("#band").value:"*";return bs.filter(x=>k==="*"||x.name===k)}
function span(ss){let a=1e9,b=-1e9;ss.forEach(s=>{if(s.f.length){a=Math.min(a,s.f[0]);b=Math.max(b,s.f[s.f.length-1])}});return b>a?[a,b]:null}
function setup(cv,h){const d=devicePixelRatio||1,w=cv.clientWidth;cv.style.height=h+"px";if(cv.width!==Math.round(w*d)||cv.height!==Math.round(h*d)){cv.width=Math.round(w*d);cv.height=Math.round(h*d)}
 const c=cv.getContext("2d");c.setTransform(d,0,0,d,0,0);return[c,w,h]}
const PL=44,PB=24,PT=24;
function ticks(a,b,n){const st=[.01,.025,.05,.1,.25,.5,1,2,5,10,20,25,50,100,200,500,1000],raw=(b-a)/n,s=st.find(x=>x>=raw)||raw;const o=[];for(let x=Math.ceil(a/s)*s;x<=b;x+=s)o.push(+x.toFixed(4));return o}
function marks(c,w,h,f0,f1,top){if(!$("#mk")||!$("#mk").checked)return;const X=f=>PL+(f-f0)/(f1-f0)*(w-PL-8);let lastX=-99;
 const col={ok:"#22c55e",free:"#3b82f6",bad:"#ef4444",warn:"#eab308",none:"#8b95a5"};
 D.state.rows.filter(r=>r.freq>=f0&&r.freq<=f1).sort((a,b)=>a.freq-b.freq).forEach(r=>{const x=X(r.freq),cc=r.alarm?"#f97316":(r.color||col[r.tone]||"#8b95a5");
  c.globalAlpha=.85;c.strokeStyle=cc;c.lineWidth=1.5;
  if(r.bw){const x0=X(r.freq-r.bw/2),x1=X(r.freq+r.bw/2);c.fillStyle=cc+"22";c.fillRect(x0,top,x1-x0,h-PB-top);c.strokeRect(x0,top,x1-x0,h-PB-top)}
  else{c.setLineDash([3,3]);c.beginPath();c.moveTo(x,top);c.lineTo(x,h-PB);c.stroke();c.setLineDash([])}
  c.globalAlpha=1;if(x-lastX>46){c.fillStyle=cc;c.font="600 11px system-ui";c.textAlign="center";c.fillText(r.name.slice(0,10),x,top-6);lastX=x}})}
// couleurs du spectre = thème de l'appli (7.56) ; « crt » = gamme Analyseur (grille et trace phosphore)
function PC(){const p=Object.assign({bg:"#0b0d10",fg:"#8b95a5",curve:"#ff9f1c",mh:"#ff9f1c",thr:"#ef4444",crt:false},(D.state&&D.state.plot)||{});
 p.grid=p.crt?p.fg+"66":"#272d38";p.txt=p.crt?p.fg:"#8b95a5";return p}
// rémanence : chaque balayage laisse une trace qui s'estompe ; les traces s'ADDITIONNENT (ce qui revient souvent brille,
// comme la persistance d'un analyseur numérique)
let pers=null;
function persLayer(c,w,h,ss,X,Y,key){const cv=$("#cv"),P=PC(),k=key+"|"+cv.width+"x"+cv.height+"|"+P.curve;
 if(!pers||pers.k!==k){const b=document.createElement("canvas");b.width=cv.width;b.height=cv.height;const g=b.getContext("2d");g.scale(cv.width/w,cv.height/h);pers={c:b,g:g,k:k,t:0,n:0}}
 if(spec.t!==pers.t){pers.t=spec.t;pers.n++;const g=pers.g;g.globalCompositeOperation="destination-out";g.fillStyle="rgba(0,0,0,.13)";g.fillRect(0,0,w,h);g.globalCompositeOperation="source-over";
  g.globalCompositeOperation="lighter";
  ss.forEach(s=>{g.beginPath();s.l.forEach((v,i)=>{const x=X(s.f[i]),y=Y(v);i?g.lineTo(x,y):g.moveTo(x,y)});g.strokeStyle=P.curve+"40";g.lineWidth=1.8;g.stroke()});
  g.globalCompositeOperation="source-over"}
 c.drawImage(pers.c,0,0,w,h)}
function draw(){const cv=$("#cv");if(!cv||!spec)return;const ss=segs(),sp=span(ss),lg=$("#lg");
 const H=mounted==="spectre"?Math.max(240,Math.min(innerHeight-230,520)):mounted==="terrain"?Math.max(220,Math.min(innerHeight*.45,420)):Math.max(260,innerHeight-220);
 const[c,w,h]=setup(cv,H),P=PC();c.clearRect(0,0,w,h);c.fillStyle=P.bg;c.fillRect(PL,PT,w-PL-8,h-PT-PB);if(!sp){c.fillStyle="#8b95a5";c.font="15px system-ui";c.textAlign="center";c.fillText(spec.bands.length?"…":"Pas encore de balayage",w/2,h/2);return}
 const[f0,f1]=sp,X=f=>PL+(f-f0)/(f1-f0)*(w-PL-8);
 c.font="11px system-ui";c.fillStyle=P.txt;c.strokeStyle=P.grid;c.lineWidth=1;c.textAlign="center";
 ticks(f0,f1,Math.max(3,Math.floor(w/90))).forEach(f=>{const x=X(f);c.beginPath();c.moveTo(x,PT);c.lineTo(x,h-PB);c.stroke();c.fillText(f.toFixed(f1-f0<5?2:(f1-f0<50?1:0)),x,h-8)});
 if(mounted==="waterfall"){wfDraw(c,w,h,f0,f1);marks(c,w,h,f0,f1,PT);lg.innerHTML='<span>Récent en haut · une ligne par balayage (il se remplit tant que la vue est ouverte)</span><span><i style="background:linear-gradient(90deg,#0b1e5b,#1d9bf0,#22c55e,#eab308,#ef4444)"></i>faible → fort</span>';return}
 const tsm=mounted==="terrain"&&$("#tmh")?$("#tmh").value:"",scs=Object.entries((spec&&spec.scenes)||{}).filter(([k])=>tsm==="*"||k===tsm);
 const lo=-120,hi=Math.max(-20,Math.ceil((Math.max(...ss.flatMap(s=>s.mh||s.l),...scs.flatMap(([k,o])=>o.segs.flatMap(g=>g.l)))+5)/10)*10),Y=v=>PT+(hi-v)/(hi-lo)*(h-PT-PB);
 c.textAlign="right";for(let v=lo;v<=hi;v+=10){const y=Y(v);c.strokeStyle=P.grid;c.beginPath();c.moveTo(PL,y);c.lineTo(w-8,y);c.stroke();c.fillText(v,PL-6,y+4)}
 const line=(arr,f,col,lw,fill)=>{c.beginPath();arr.forEach((v,i)=>{const x=X(f[i]),y=Y(Math.max(lo,v));i?c.lineTo(x,y):c.moveTo(x,y)});c.strokeStyle=col;c.lineWidth=lw;c.stroke();
  if(fill){c.lineTo(X(f[f.length-1]),h-PB);c.lineTo(X(f[0]),h-PB);c.closePath();const g=c.createLinearGradient(0,PT,0,h-PB);g.addColorStop(0,P.curve+"55");g.addColorStop(1,P.curve+"05");c.fillStyle=g;c.fill()}};
 const mh=$("#mh")&&$("#mh").checked,rm=$("#rm")&&$("#rm").checked;if(rm)persLayer(c,w,h,ss,X,Y,[$("#band")?$("#band").value:"*",f0,f1,hi].join("|"));
 scs.forEach(([k,o])=>o.segs.forEach(g=>{const f=g.f.filter((x,i)=>x>=f0&&x<=f1),idx=g.f.map((x,i)=>i).filter(i=>g.f[i]>=f0&&g.f[i]<=f1);
  if(idx.length>1)line(idx.map(i=>g.l[i]),f,o.color||"#a3e635",1.4,false)}));
 ss.forEach(s=>{if(mh&&s.mh)line(s.mh,s.f,P.mh+"88",1,false);line(s.l,s.f,P.curve,rm?1.2:1.6,!rm)});
 if(D.state.thr!=null){const y=Y(D.state.thr);c.setLineDash([6,4]);c.strokeStyle=P.thr;c.lineWidth=1.2;c.beginPath();c.moveTo(PL,y);c.lineTo(w-8,y);c.stroke();c.setLineDash([]);c.fillStyle=P.thr;c.textAlign="left";c.fillText("seuil "+D.state.thr+" dBm",PL+4,y-4)}
 marks(c,w,h,f0,f1,PT);c.fillStyle=P.txt;c.textAlign="left";c.fillText("dBm",4,PT-8);
 const scLg=scs.map(([k,o])=>{const t="max hold "+k;return `<span><i style="background:${esc(o.color||"#a3e635")}"></i>${esc(t)}</span>`}).join("");
 lg.innerHTML=scLg+'<span><i style="background:'+P.curve+'"></i>en direct</span>'+(mh?'<span><i style="background:'+P.mh+'88"></i>max hold</span>':"")+(rm?'<span><i style="background:'+P.curve+'66"></i>rémanence (plus c’est épais et vif, plus le signal est souvent là)</span>':"")+'<span><i style="background:'+P.thr+'"></i>seuil « occupé »</span><span><i style="background:#22c55e"></i>mes fréquences (couleur = état)</span>'}
function levelAt(f){let best=null,bd=1e9;segs().forEach(s=>{let lo=0,hi=s.f.length-1;while(hi-lo>1){const m=(lo+hi)>>1;s.f[m]<f?lo=m:hi=m}[lo,hi].forEach(i=>{const d=Math.abs(s.f[i]-f);if(d<bd){bd=d;best=s.l[i]}})});return best}
function readout(e){const cv=$("#cv"),sp=span(segs());if(!sp)return;const r=cv.getBoundingClientRect(),x=e.clientX-r.left,f=sp[0]+(x-PL)/(r.width-PL-8)*(sp[1]-sp[0]);
 if(f<sp[0]||f>sp[1]){$("#rd").textContent="";return}const l=levelAt(f),near=D.state.rows.filter(w=>Math.abs(w.freq-f)<Math.max(.15,(w.bw||0)/2)).sort((a,b)=>Math.abs(a.freq-f)-Math.abs(b.freq-f))[0];
 $("#rd").textContent=f.toFixed(3)+" MHz"+(l!=null?" · "+l.toFixed(1)+" dBm":"")+(near?" · "+near.name:"")}
function wfCol(v){const t=Math.max(0,Math.min(1,(v+110)/70)),S=[[11,30,91],[29,155,240],[34,197,94],[234,179,8],[239,68,68]],p=t*(S.length-1),i=Math.min(S.length-2,Math.floor(p)),k=p-i;
 return S[i].map((a,j)=>Math.round(a+(S[i+1][j]-a)*k))}
function wfAdd(){const cv=$("#cv");if(!cv)return;const ss=segs(),sp=span(ss);if(!sp)return;const W=Math.max(50,Math.round(cv.clientWidth-PL-8)),N=Math.max(100,Math.round(innerHeight));
 if(!wf||wf.w!==W||wf.key!==($("#band").value||"*")){const b=document.createElement("canvas");b.width=W;b.height=N;wf={c:b,w:W,key:$("#band").value||"*",n:0}}
 const g=wf.c.getContext("2d");g.drawImage(wf.c,0,1);const img=g.createImageData(W,1);
 for(let x=0;x<W;x++){const f=sp[0]+x/(W-1)*(sp[1]-sp[0]),v=levelAt(f),q=v==null?[13,15,19]:wfCol(v);img.data.set([q[0],q[1],q[2],255],x*4)}
 g.putImageData(img,0,0);wf.n++}
function wfDraw(c,w,h,f0,f1){if(!wf){c.fillStyle="#8b95a5";c.textAlign="center";c.fillText("Le waterfall se remplit à chaque balayage…",w/2,h/2);return}
 c.imageSmoothingEnabled=false;const rows=Math.min(wf.n,Math.floor((h-PT-PB)/2));c.drawImage(wf.c,0,0,wf.w,rows,PL,PT,w-PL-8,rows*2)}
/*__EXTRA_JS__*/
</script></body></html>""".replace("__ICON__", APP_ICON_PNG64).replace(
    "__VIEWS__", "{" + ",".join(f'"{k}":["{i}","{t}","{d}"]' for k, i, t, d in WEB_VIEWS) + "}")


def split_band(start, stop, step):
    """Coupe une bande en deux moitiés jointives (pour la partager entre deux tinySA)."""
    mid = round((start + stop) / 2.0, 3)
    return (start, mid, step), (mid, stop, step)



# ------------------------------------------------------------------ SDR (V8) : balayage par les outils officiels
# hackrf_sweep (HackRF One) et rtl_power (RTL-SDR) écrivent le même CSV : date, heure, Hz bas, Hz haut, largeur de
# case (Hz), nb d'échantillons, puis les niveaux en dB des cases. Niveaux NON étalonnés en dBm (offset / calibration).
SDR_KINDS = {
    "hackrf": dict(name="HackRF One / Pro", tool="hackrf_sweep", iq_tool="hackrf_transfer", fmin=1.0, fmax=6000.0, bin_min=2445.0, bin_max=5e6,
                   lna=(0, 40, 8), vga=(0, 62, 2), amp=True),
    "rtlsdr": dict(name="RTL-SDR", tool="rtl_power", iq_tool="rtl_sdr", fmin=24.0, fmax=1766.0, bin_min=1.0, bin_max=2.8e6,
                   lna=(0, 50, 1), vga=None, amp=False),
    # SDRplay RSP1B (choix de Clément) : 14 bits, 1 kHz – 2 GHz, jusqu'à 10 MHz de large. Pas d'outil officiel en
    # ligne de commande : rx_tools (rx_power = clone de rtl_power, rx_sdr = clone de rtl_sdr) au-dessus de SoapySDR
    # + module SoapySDRPlay3 + API SDRplay (à installer depuis sdrplay.com). NON TESTÉ avec un vrai RSP1B.
    "sdrplay": dict(name="SDRplay RSP (1A, 1B, dx, duo)", tool="rx_power", iq_tool="rx_sdr", fmin=1.0, fmax=2000.0, bin_min=1.0,
                    bin_max=8e6, lna=(0, 60, 1), vga=None, amp=False, soapy="sdrplay"),
    # étape 7 : autres SDR par SoapySDR + rx_tools (même chemin que le RSP1B ; modules Soapy du fabricant à installer)
    "airspy": dict(name="Airspy R2 / Mini", tool="rx_power", iq_tool="rx_sdr", fmin=24.0, fmax=1700.0, bin_min=1.0,
                   bin_max=8e6, lna=(0, 21, 1), vga=None, amp=False, soapy="airspy"),
    "airspyhf": dict(name="Airspy HF+", tool="rx_power", iq_tool="rx_sdr", fmin=1.0, fmax=260.0, bin_min=1.0,
                     bin_max=6e5, lna=(0, 48, 6), vga=None, amp=False, soapy="airspyhf"),
    "lime": dict(name="LimeSDR", tool="rx_power", iq_tool="rx_sdr", fmin=10.0, fmax=3500.0, bin_min=1.0, bin_max=8e6,
                 lna=(0, 70, 1), vga=None, amp=False, soapy="lime"),
    "pluto": dict(name="ADALM-Pluto", tool="rx_power", iq_tool="rx_sdr", fmin=325.0, fmax=3800.0, bin_min=1.0,
                  bin_max=4e6, lna=(0, 70, 1), vga=None, amp=False, soapy="plutosdr"),
    "uhd": dict(name="Ettus USRP", tool="rx_power", iq_tool="rx_sdr", fmin=70.0, fmax=6000.0, bin_min=1.0, bin_max=8e6,
                lna=(0, 76, 1), vga=None, amp=False, soapy="uhd"),
    "bladerf": dict(name="bladeRF", tool="rx_power", iq_tool="rx_sdr", fmin=47.0, fmax=6000.0, bin_min=1.0,
                    bin_max=8e6, lna=(0, 60, 1), vga=None, amp=False, soapy="bladerf"),
    # WiNRADiO G39DDC : pas d'outil en ligne de commande, sa DLL Windows (G39DDCAPI.dll) est appelée directement
    "winradio": dict(name="WiNRADiO G39DDC", tool=None, iq_tool=None, dll="G39DDCAPI.dll", fmin=0.009, fmax=3500.0,
                     bin_min=1.0, bin_max=8e6, lna=(0, 18, 6), vga=None, amp=True),
}
SDR_ALIASES = [("winradio", r"winradio|g39ddc|g39"), ("airspyhf", r"airspyhf|airspy-hf|hfplus"),
               ("airspy", r"airspy"), ("lime", r"lime|limesdr"), ("pluto", r"pluto|plutosdr|adalm"),
               ("uhd", r"uhd|usrp|b200|b210"), ("bladerf", r"bladerf"), ("hackrf", r"hackrf"),
               ("sdrplay", r"sdrplay|rsp\w*"), ("rtlsdr", r"rtlsdr|rtl-sdr|rtl")]


def parse_sdr_addr(s):
    """« hackrf », « hackrf:<n° de série> », « rtlsdr », « rtlsdr:1 », « sdrplay », « rsp1b:<série> » -> (genre, n° de
    série / index ou ""), sinon None."""
    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9+\-]*)\s*(?::\s*([A-Za-z0-9]+))?\s*", str(s or ""))
    if not m:
        return None
    g = m.group(1).lower()
    kind = next((k for k, pat in SDR_ALIASES if re.fullmatch(pat, g)), None)
    if kind is None:
        return None
    return kind, (m.group(2) or "")


def sweep_line(line):
    """Une ligne hackrf_sweep / rtl_power -> (Hz bas, Hz haut, case Hz, niveaux np.array) ou None."""
    parts = [x.strip() for x in str(line).split(",")]
    if len(parts) < 7:
        return None
    try:
        lo, hi, bw = float(parts[2]), float(parts[3]), float(parts[4])
        lv = np.array([float(x) for x in parts[6:] if x not in ("", "nan", "-nan")], dtype=float)
    except ValueError:
        return None
    if not len(lv) or bw <= 0 or hi <= lo:
        return None
    return lo, hi, bw, lv


class SweepAccum:
    """Reconstitue les passages complets d'un outil de balayage à partir de ses lignes (dans le désordre de
    fréquence par bloc, comme hackrf_sweep). Un passage est fini quand une ligne revient en arrière (Hz bas ≤
    au plus bas déjà vu dans le passage en cours) : snapshot() = dernier passage complet, passes = compteur."""

    def __init__(self):
        self.cur, self.lo_seen, self.passes, self.last = {}, None, 0, None

    def feed(self, item):
        if item is None:
            return False
        lo, hi, bw, lv = item
        done = False
        if self.cur and lo in self.cur:                 # même bloc revu : nouveau passage
            done = True
        if done:
            self._close()
        f = lo + (np.arange(len(lv)) + 0.5) * bw
        self.cur[lo] = (f, lv)
        return done

    def _close(self):
        keys = sorted(self.cur)
        F = np.concatenate([self.cur[k][0] for k in keys])
        L = np.concatenate([self.cur[k][1] for k in keys])
        o = np.argsort(F, kind="stable")
        self.last = (F[o], L[o])
        self.passes += 1
        self.cur = {}

    def snapshot(self):
        return self.last


def resample_max(F, L, a, z, pts):
    """Niveaux (dB) aux pts fréquences de a à z (Hz) : le MAX des cases qui tombent dans chaque cellule (pour ne
    pas rater une porteuse), interpolation quand les cases sont plus larges que les cellules. -> np.array."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    x = np.linspace(a, z, int(pts))
    if not len(F):
        return np.full(len(x), np.nan)
    out = np.interp(x, F, L)
    if len(x) > 1:
        half = (x[1] - x[0]) / 2.0
        idx = np.searchsorted(F, np.append(x - half, x[-1] + half), side="left")   # cellule k = [idx[k], idx[k+1])
        has = idx[1:] > idx[:-1]
        if has.any():
            Lp = np.append(L, -np.inf)                     # sentinelle : la dernière cellule s'arrête à idx[-1]
            mx = np.maximum.reduceat(Lp, np.minimum(idx, len(L)))[:-1]
            out[has] = mx[has]
    return out


def sdr_ranges(bands_hz, maxn=10, fmin=1.0, fmax=6000.0):
    """Bandes [(Hz début, Hz fin)] -> plages en MHz entiers pour l'outil (fusionnées, au plus maxn : on réunit les
    plus proches). -> [(lo, hi)]."""
    r = sorted((max(fmin, math.floor(a / 1e6)), min(fmax, math.ceil(b / 1e6))) for a, b in bands_hz if b > a)
    r = [(lo, max(hi, lo + 1)) for lo, hi in r]
    out = []
    for lo, hi in r:
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    while len(out) > maxn:
        k = min(range(len(out) - 1), key=lambda i: out[i + 1][0] - out[i][1])
        out[k:k + 2] = [(out[k][0], out[k + 1][1])]
    return [(int(lo), int(hi)) for lo, hi in out]


def sdr_bin_hz(kind, bands, rbw_khz=None, finest=5000.0):
    """Largeur de case de l'outil : la RBW si elle est fixée, sinon le pas le plus fin des bandes (pas plus fin
    que `finest` Hz : au-delà, le balayage devient très lent), dans les limites de l'outil."""
    k = SDR_KINDS[kind]
    if rbw_khz:
        b = rbw_khz * 1000.0
    else:
        steps = [(x["stop_hz"] - x["start_hz"]) / max(1, int(x["n"]) - 1) for x in bands] or [25000.0]
        b = max(finest, min(steps))
    return float(min(k["bin_max"], max(k["bin_min"], b)))


def sdr_cmd(kind, exe, ranges, bin_hz, lna=24, vga=20, amp=False, serial=""):
    """Ligne de commande de l'outil de balayage (liste d'arguments)."""
    exe = list(exe) if isinstance(exe, (list, tuple)) else [exe]
    if kind == "hackrf":
        a = exe[:]
        for lo, hi in ranges:
            a += ["-f", f"{lo}:{hi}"]
        a += ["-w", str(int(round(bin_hz))), "-l", str(int(lna) // 8 * 8), "-g", str(int(vga) // 2 * 2),
              "-a", "1" if amp else "0"]
        if serial:
            a += ["-d", serial]
        return a
    lo, hi = min(r[0] for r in ranges), max(r[1] for r in ranges)
    a = exe + ["-f", f"{lo}M:{hi}M:{int(round(bin_hz))}", "-i", "1", "-g", str(int(lna))]
    soapy = SDR_KINDS.get(kind, {}).get("soapy")
    if soapy:                                           # rx_power : appareil SoapySDR par chaîne « driver=… »
        a += ["-d", f"driver={soapy}" + (f",serial={serial}" if serial else "")]
    elif serial:
        a += ["-d", serial]
    return a + ["-"]


# ------------------------------------------------------------------ V8 : écoute (démodulation) d'un SDR
# L'outil (hackrf_transfer / rtl_sdr) envoie l'IQ brut ; on mélange chaque canal à 0 Hz, on filtre et décime
# (FIR fenêtré, en flux), puis discriminateur FM (ou enveloppe AM), désaccentuation, filtre audio, 48 kHz.
# Les companders des marques (HDX, Shure, Wisycom…) ne sont pas publiés : « expanseur 2:1 » = approximation.
LISTEN_RATE = 48000
LISTEN_IF = 240000                       # 1er étage : canal décimé à 240 kHz (FM large d'un micro HF : ±50 kHz)
LISTEN_MODES = {
    "wfm": dict(name="FM large (micros HF, ears en mono)", cut=90000.0, dev=50000.0),
    "wfm_st": dict(name="FM stéréo (radio FM, ears stéréo)", cut=110000.0, dev=75000.0),
    "nfm": dict(name="FM étroite (talkies, guide)", cut=8000.0, dev=3000.0),
    "am": dict(name="AM (aviation, ondes courtes)", cut=6000.0, dev=None),
    "usb": dict(name="BLU haute (USB, radioamateurs)", cut=3000.0, dev=None),
    "lsb": dict(name="BLU basse (LSB, radioamateurs < 10 MHz)", cut=3000.0, dev=None),
    "cw": dict(name="CW (morse, porteuse pure : bip à 700 Hz)", cut=500.0, dev=None),
}
# Companders : un émetteur HF analogique compresse son audio, le récepteur l'étend. Les courbes exactes des marques
# ne sont pas publiées : chaque mode est un expanseur APPROCHÉ, réglé d'après ce qu'on en sait (fiches Wisycom
# MCR54 + docs lues par Clément) :
#   ENC (Extended-NC) = voix / fidélité, pré-accentuation RÉDUITE, transitoires rapides ;
#   ENR (Extended-NR) = réduction de bruit max : expansion plus forte quand le signal est faible, détecteur qui
#       ignore les aigus extrêmes (pas de pompage sur des clés, des couverts) ;
#   ENS (Sound) = le plus récent, compromis voix / musique (live, ears), tient aussi en bande étroite ;
#   1.2 = dynamique réduite (entrées caméra) ; le MCR54 émule aussi SA572 / SA575 / RMS.
#   À l'oreille (Clément) : ENS = beaucoup plus d'air (aigus relevés), ENC = plus plat, ENR = coupe le haut.
#   Manuel Wisycom (capture de Clément) : NONE-d50 / NONE-d75 = pas de compander, désaccentuation 50 / 75 µs ;
#   ENR-WISY = « noise optimized » ; ENC-WISY = « voice and high-fidelity optimized » ; FLAT = aucun compander,
#   « test purposes only » (donc ici sans désaccentuation non plus).
# Clés : ratio, attack / release (lissage par bloc de 5 ms), det « avg » (redressement moyen, SA572) ou « rms »,
# deemph (µs, None = celle du préréglage), knee (dB sous la référence : en dessous, expansion + low), hf (Hz : le
# détecteur ne voit pas au-delà). Valeurs AU JUGÉ, non vérifiées sur un vrai récepteur : à régler à l'oreille.
def _cp(name, ratio=2.0, attack=0.3, release=0.05, det="rms", deemph=None, knee=None, low=0.0, hf=None, air=0.0,
        lp=None):
    """air : aigus relevés (dB au-dessus de ~6 kHz) ; lp : passe-bas final (Hz) — la « couleur » du mode."""
    return dict(name=name, ratio=ratio, attack=attack, release=release, det=det, deemph=deemph, knee=knee, low=low,
                hf=hf, air=air, lp=lp)


COMPANDERS = {
    "none": _cp("FLAT : ni compander ni désaccentuation (test)", ratio=1.0, deemph=0.0),
    "none_d50": _cp("NONE-d50 : pas de compander, désaccentuation 50 µs", ratio=1.0, deemph=50.0),
    "none_d75": _cp("NONE-d75 : pas de compander, désaccentuation 75 µs", ratio=1.0, deemph=75.0),
    "x2": _cp("Expanseur 2:1 générique"),
    "sa572": _cp("Circuit SA572 / NE570 (2:1, redressement moyen)", attack=0.25, release=0.04, det="avg"),
    "rms": _cp("Compander RMS 2:1 (type dbx)", attack=0.35, release=0.06),
    "wisy_enc": _cp("≈ Wisycom ENC (voix, plat, pré-accentuation réduite)", attack=0.5, release=0.12, deemph=25.0),
    "wisy_enr": _cp("≈ Wisycom ENR (réduction de bruit, coupe le haut)", attack=0.35, release=0.05, knee=-30.0,
                    low=1.0, hf=8000.0, lp=10000.0),
    "wisy_ens": _cp("≈ Wisycom ENS (live, plus d'air)", attack=0.4, release=0.08, air=4.0),
    "wisy_enc12": _cp("≈ Wisycom ENC 1.2 (dynamique réduite)", ratio=1.5, attack=0.5, release=0.12, deemph=25.0),
    "wisy_enr12": _cp("≈ Wisycom ENR 1.2 (dynamique réduite)", ratio=1.5, attack=0.35, release=0.05, knee=-30.0,
                      low=0.5, hf=8000.0, lp=10000.0),
    "sen": _cp("≈ SEN : Sennheiser 3000 / 5000 (HiDyn plus)", attack=0.35, release=0.06),
    "evo": _cp("≈ EVO : Sennheiser evolution (ew G2 / G3 / G4, HDX)", attack=0.35, release=0.06, det="avg"),
    "shure": _cp("≈ Shure analogique", attack=0.3, release=0.04, det="avg"),
    "lex": _cp("≈ Lectrosonics (mode SR / LEX)", attack=0.25, release=0.03),
}
LISTEN_COMPANDERS = {k: v["name"] for k, v in COMPANDERS.items()}
# Préréglages de démodulation par type d'appareil : mode, déviation crête (Hz, = 100 % du volume), largeur du canal
# (filtre, demi-largeur Hz), bande audio (Hz), désaccentuation (µs), compander. Valeurs de départ d'après les
# fiches techniques publiques / l'usage courant, NON vérifiées sur les vrais appareils (à ajuster à l'oreille).
DEMOD_PRESETS = [
    ("senn_ana", "Micro Sennheiser evolution (ew G2 / G3 / G4)",
     dict(mode="wfm", dev=48000, cut=90000, audio=18000, deemph=50.0, comp="evo"),
     "FM ±48 kHz crête, compander HDX (approché, comme le mode EVO d'un récepteur Wisycom)."),
    ("senn_pro", "Micro Sennheiser 3000 / 5000 (SK 5212, SK 50…)",
     dict(mode="wfm", dev=48000, cut=90000, audio=18000, deemph=50.0, comp="sen"),
     "FM ±48 kHz crête, compander HiDyn plus (approché, comme le mode SEN d'un récepteur Wisycom)."),
    ("shure_ana", "Micro Shure analogique (UR, ULX, SLX, BLX)",
     dict(mode="wfm", dev=45000, cut=85000, audio=15000, deemph=50.0, comp="shure"),
     "FM ±45 kHz environ, compander Shure (approché)."),
    ("wisy_ana", "Micro Wisycom analogique (MTP, MRK)",
     dict(mode="wfm", dev=50000, cut=90000, audio=18000, deemph=50.0, comp="wisy_enr"),
     "FM ±50 kHz environ, compander Wisycom ENR (approché ; ENC / ENS / 1.2 / FLAT dans « Compander » : mets le "
     "même mode que l'émetteur)."),
    ("lectro", "Micro Lectrosonics analogique / compatible",
     dict(mode="wfm", dev=50000, cut=90000, audio=18000, deemph=50.0, comp="lex"),
     "FM large, compander type Lectrosonics (approché, mode SR / LEX des récepteurs Wisycom). Le « Digital Hybrid » "
     "Lectrosonics natif n'est pas un FM analogique classique : son rendu ne sera pas bon."),
    ("iem", "Ear monitor analogique stéréo (PSM, EW IEM)",
     dict(mode="wfm_st", dev=48000, cut=100000, audio=15000, deemph=50.0, comp="x2"),
     "Multiplex stéréo à porteuse pilote 19 kHz (comme la radio FM) : gauche / droite séparés si le pilote est là, "
     "sinon mono."),
    ("guide", "Guide / talkback FM étroit",
     dict(mode="nfm", dev=5000, cut=12000, audio=4000, deemph=0.0, comp="none"),
     "FM étroite ±5 kHz (systèmes de guide, retours d'ordres analogiques)."),
    ("pmr446", "Talkie PMR446 / talkie pro (12,5 kHz)",
     dict(mode="nfm", dev=2500, cut=6250, audio=3500, deemph=0.0, comp="none"),
     "Canaux 12,5 kHz, FM ±2,5 kHz."),
    ("radio_fm", "Radio FM (bande 87,5–108)",
     dict(mode="wfm_st", dev=75000, cut=110000, audio=15000, deemph=50.0, comp="none_d50"),
     "FM ±75 kHz stéréo (pilote 19 kHz), désaccentuation 50 µs (Europe)."),
    ("aviation", "Aviation (AM 118–137 MHz)",
     dict(mode="am", dev=None, cut=5000, audio=3500, deemph=0.0, comp="none"),
     "AM, canaux 8,33 / 25 kHz."),
    ("ham_usb", "Radioamateur phonie BLU haute (USB)",
     dict(mode="usb", dev=None, cut=3000, audio=3000, deemph=0.0, comp="none"),
     "USB au-dessus de 10 MHz (VHF / UHF comprises) ; LSB en dessous : choisis « BLU basse » dans Mode."),
    ("cw", "Morse (CW)",
     dict(mode="cw", dev=None, cut=500, audio=1500, deemph=0.0, comp="none"),
     "Porteuse pure rendue en bip de 700 Hz, filtre étroit 500 Hz."),
]
DEMOD_CUSTOM = "✏ Réglages à la main"


def demod_preset(key):
    """Préréglage de démodulation par sa clé -> dict, ou None."""
    for k, _n, d, _w in DEMOD_PRESETS:
        if k == key:
            return dict(d)
    return None


def sdr_iq_rate(kind):
    """Fréquence d'échantillonnage IQ (multiple de 240 kHz) : HackRF 4,8 MS/s (≈ 4 MHz utiles), RTL 2,4 MS/s."""
    if kind in ("hackrf", "sdrplay"):
        return 4800000
    if kind == "rtlsdr":
        return 2400000
    m = sdr_model(SDR_MODEL_DEFAULT.get(kind))       # étape 7 : d'après la fiche du modèle (Airspy 10 MS/s…)
    return sdr_rate(m, kind) if m is not None and m.get("rates") else 2400000


SDR_DTYPE = {"hackrf": "ci8", "rtlsdr": "cu8", "sdrplay": "ci16_le", "airspy": "ci16_le", "airspyhf": "ci16_le",
             "lime": "ci16_le", "pluto": "ci16_le", "uhd": "ci16_le", "bladerf": "ci16_le", "winradio": "ci16_le"}   # format IQ brut de chaque SDR (noms SigMF)
IQ_BYTES = {"ci8": 2, "cu8": 2, "ci16_le": 4, "ci32_le": 8, "cf32_le": 8}   # octets par échantillon complexe


def iq_decode(dtype, buf):
    """Octets IQ entrelacés (format SigMF ci8 / cu8 / ci16_le / cf32_le) -> np.complex64, pleine échelle ≈ 1."""
    nb = IQ_BYTES[dtype]
    buf = bytes(buf[:len(buf) // nb * nb])
    if dtype == "cf32_le":
        return np.frombuffer(buf, dtype="<f4").copy().view(np.complex64)
    a = np.frombuffer(buf, dtype={"ci8": np.int8, "cu8": np.uint8, "ci16_le": "<i2", "ci32_le": "<i4"}[dtype]
                      ).astype(np.float32)
    if dtype == "cu8":
        a -= 127.5
    a *= np.float32(1.0 / {"ci16_le": 32768.0, "ci32_le": 2147483648.0}.get(dtype, 128.0))
    return a.view(np.complex64)                        # I, Q entrelacés en float32 = complex64, sans recopie


def iq_from_bytes(kind, buf):
    """Octets IQ d'un SDR -> np.complex64. HackRF : int8 signé ; RTL-SDR : uint8 centré sur 127,5."""
    return iq_decode(SDR_DTYPE[kind], buf)


def lowpass_taps(cut, fs, n=129):
    """FIR passe-bas fenêtré (Blackman), gain 1 en continu."""
    k = np.arange(n) - (n - 1) / 2.0
    h = np.sinc(2.0 * cut / fs * k) * np.blackman(n)
    return (h / h.sum()).astype(np.float32)


class FirDecim:
    """Filtre FIR + décimation par D, en flux (garde la fin du bloc précédent)."""

    def __init__(self, taps, D):
        self.h, self.D = np.asarray(taps)[::-1].copy(), int(D)
        self.buf = None

    def __call__(self, x):
        b = x if self.buf is None else np.concatenate([self.buf, x])
        n = len(self.h)
        m = (len(b) - n) // self.D + 1 if len(b) >= n else 0
        if m <= 0:
            self.buf = b
            return b[:0]
        if self.D == 1:                              # 8.1 : convolution directe (bien moins chère que la matrice)
            y = np.convolve(b, self.h[::-1], "valid")[:m]
        else:                                        # 8.1 : polyphase (D petites convolutions), SANS produit de
            y = None                                 # matrices : sous Windows, la multiplication passait par OpenBLAS
            for p in range(self.D):                  # et la démodulation prenait 58 ms pour 50 ms de son (Clément)
                hp = self.h[p::self.D]
                if not len(hp):
                    continue
                c = np.convolve(b[p::self.D], hp[::-1], "valid")[:m]
                y = c if y is None else y + c
        self.buf = b[m * self.D:]
        return y


class ChannelDemod:
    """Un canal : décalage f_off (Hz) dans la bande IQ (fs), mode (LISTEN_MODES : wfm, wfm_st, nfm, am, usb, lsb,
    cw), déviation / largeur / bande audio (préréglage), désaccentuation (µs, 0 = non), squelch (dBFS, None =
    ouvert), compander (COMPANDERS). process(iq) -> (audio float32 à 48 kHz : (n,) mono ou (n, 2) stéréo, niveau
    RF dBFS). Chaîne : oscillateur → FIR + décimation à 240 kHz → démodulation → 48 kHz."""
    BFO = 700.0                          # CW : hauteur du bip (Hz)

    def __init__(self, fs, f_off, mode="wfm", deemph_us=50.0, squelch=None, compander=None, dev=None, cut=None,
                 audio=None):
        self.fs, self.f_off, self.mode = float(fs), float(f_off), mode
        self.D1 = max(1, int(round(fs / LISTEN_IF)))
        self.fs1 = fs / self.D1
        self.D2 = max(1, int(round(self.fs1 / LISTEN_RATE)))
        fa = self.fs1 / self.D2              # étape 7 : Airspy 10 MS/s, WiNRADiO… -> son pas tout à fait à 48 kHz
        self.rs = Resampler(fa, LISTEN_RATE) if abs(fa - LISTEN_RATE) > 1.0 else None
        md = LISTEN_MODES[mode]
        cut = float(cut or md["cut"])
        fm = mode in ("wfm", "wfm_st", "nfm")
        audio = float(audio or (15000.0 if mode in ("wfm", "wfm_st") else 4000.0))
        # 1er étage : assez large pour le canal (BLU / CW : on filtre finement après, à 48 kHz)
        c1 = cut if fm or mode == "am" else 6000.0
        self.f1 = FirDecim(lowpass_taps(min(c1, 0.45 * self.fs1), fs, 129), self.D1)
        self.f2 = FirDecim(lowpass_taps(min(audio, 0.45 * LISTEN_RATE), self.fs1, 63), self.D2)
        self.dev = float(dev or md["dev"] or 1.0)
        self.ph, self.prev = 0.0, np.complex64(1.0)
        self.squelch, self.compander = squelch, compander
        self.de = None
        cpd = COMPANDERS.get(compander, {}).get("deemph")
        if cpd is not None:
            deemph_us = cpd                  # FLAT : aucune ; NONE-d50 / d75 ; ENC : pré-accentuation réduite
        if deemph_us and fm:
            a = math.exp(-1.0 / (LISTEN_RATE * deemph_us * 1e-6))
            self.de = ((1.0 - a) * a ** np.arange(64)).astype(np.float32)   # IIR 1 pôle tronqué (FIR)
        self.de_tail = {0: np.zeros(63, dtype=np.float32), 1: np.zeros(63, dtype=np.float32)}
        self.env, self.dc, self.agc = 0.05, 0.0, 0.05
        self.level = -120.0
        self.pilot, self._pbuf = None, []             # tonalité ultrasonore vue dans le FM (pilote, données)
        self.health, self._hbuf = None, []            # étape 8 : déviation crête / dérive (FM)
        self.chain = CompChain(compander, 0.0)      # 8.2 : couleur + expanseur (même code que le Compander Lab)
        self.pre = self.pre_raw = None
        if mode == "wfm_st":             # stéréo : pilote 19 kHz, sous-porteuse 38 kHz (G − D)
            k = np.arange(129) - 64
            self.fp = FirDecim(2.0 * lowpass_taps(800.0, self.fs1, 129) * np.cos(2 * np.pi * 19000.0 * k / self.fs1), 1)
            self.f3 = FirDecim(lowpass_taps(min(audio, 0.45 * LISTEN_RATE), self.fs1, 63), self.D2)
            # FirDecim n'ajoute pas de retard : sa sortie k correspond à l'entrée k + 64 (moitié du filtre) ; la
            # dérivée centrée en retire 1 → la sous-porteuse k correspond au composite k + 63 : on aligne G+D et
            # G−D sur ce même flux (composite sans ses 63 premiers échantillons)
            self.dbuf, self.dskip = np.zeros(0, dtype=np.float32), 63
            self.pprev = np.zeros(2, dtype=np.float32)
            self.pil = None
            self.sinD = math.sin(2 * math.pi * 19000.0 / self.fs1)
        if mode in ("usb", "lsb", "cw"):  # BLU / CW : canal ramené à 48 kHz, puis filtre de bande latérale
            self.fz = FirDecim(lowpass_taps(min(6000.0, 0.45 * LISTEN_RATE), self.fs1, 63), self.D2)
            half = (cut / 2.0) if mode != "cw" else cut / 2.0
            self.sb = FirDecim(lowpass_taps(half, LISTEN_RATE, 255).astype(np.complex64), 1)
            self.sh = (cut / 2.0 if mode == "usb" else -cut / 2.0) if mode != "cw" else 0.0
            self.ph2, self.ph3 = 0.0, 0.0

    def _nco(self, x, f, fs, attr):
        """Décale x de −f Hz (oscillateur table × phase par bloc, phase gardée dans self.<attr>)."""
        n = len(x)
        w = -2.0 * math.pi * f / fs
        B = 8192
        key = "_tab_" + attr
        if getattr(self, key, None) is None:
            setattr(self, key, np.exp(1j * w * np.arange(B)).astype(np.complex64))
        nb = -(-n // B)
        ph = getattr(self, attr)
        steps = np.exp(1j * (ph + w * B * np.arange(nb))).astype(np.complex64)
        setattr(self, attr, (ph + w * n) % (2.0 * math.pi))
        return x * (steps[:, None] * getattr(self, key)[None, :]).ravel()[:n]

    def _deemph(self, a, ch):
        if self.de is None or not len(a):
            return a
        t = self.de_tail[ch]
        c = np.convolve(np.concatenate([t, a]), self.de)[63:63 + len(a)]
        self.de_tail[ch] = np.concatenate([t, a])[-63:]
        return c.astype(np.float32)

    def _watch_health(self, d):
        """Étape 8 : santé d'un micro FM, toutes les ~0,5 s : déviation crête (kHz, 99,5ᵉ centile de l'écart de fréquence
        instantanée) et dérive (kHz, écart moyen à la fréquence réglée). self.health = dict(dev, drift) ou None."""
        self._hbuf.append(np.asarray(d, dtype=np.float32))
        if sum(len(x) for x in self._hbuf) < int(0.5 * self.fs1):
            return
        x = np.concatenate(self._hbuf) * self.dev
        self._hbuf = []
        k = max(1, int(round(self.fs1 / 30000.0)))        # 8.1 : bande audio seulement (le bruit large bande gonflait
        if k > 1 and len(x) > 4 * k:                       # les petites déviations : 9,7 kHz mesurés pour 6)
            x = np.convolve(x, np.ones(k) / k, mode="valid")
        mu = float(np.mean(x))
        self.health = dict(dev=float(np.percentile(np.abs(x - mu), 99.5)) / 1000.0, drift=mu / 1000.0)

    def _watch_pilot(self, d, n=8192):
        """Cherche une tonalité au-dessus de l'audio (15–100 kHz) dans le FM démodulé : pilote de squelch
        (Sennheiser, Shure…), porteuse de données (batterie, Wisycom numérique) ou pilote stéréo 19 kHz.
        self.pilot = (fréquence Hz, dB au-dessus du bruit) si elle dépasse le bruit de 20 dB, sinon None."""
        self._pbuf.append(np.asarray(d, dtype=np.float32))
        if sum(len(x) for x in self._pbuf) < n:
            return
        x = np.concatenate(self._pbuf)[-n:]
        self._pbuf = []
        sp = np.abs(np.fft.rfft(x * np.hanning(n))) ** 2
        fr = np.fft.rfftfreq(n, 1.0 / self.fs1)
        m_ = (fr >= 15000.0) & (fr <= min(100000.0, 0.45 * self.fs1))
        if not m_.any():
            return
        band, fb = sp[m_], fr[m_]
        k = int(np.argmax(band))
        snr = 10.0 * math.log10(band[k] / (np.median(band) + 1e-20) + 1e-20)
        self.pilot = (float(fb[k]), snr) if snr > 20.0 else None

    def _agc(self, a, target=0.3):
        """Contrôle automatique de gain lent (BLU, CW, AM : le niveau audio suit le niveau du signal)."""
        if not len(a):
            return a
        pk = float(np.max(np.abs(a)))
        self.agc = pk if pk > self.agc else 0.995 * self.agc + 0.005 * pk
        return (a * (target / max(self.agc, 1e-4))).astype(np.float32)

    def _tp(self, k, t0):
        """8.1 : temps (ms, moyenne glissante) passé dans chaque étape -> self.prof (diagnostic de lenteur)."""
        import time as _t
        t1 = _t.perf_counter()
        if not hasattr(self, "prof"):
            self.prof = {}
        self.prof[k] = 0.9 * self.prof.get(k, 0.0) + 0.1 * (t1 - t0) * 1000.0
        return t1

    def process(self, iq):
        import time as _t
        t0 = _t.perf_counter()
        x = self._nco(iq, self.f_off, self.fs, "ph")
        t0 = self._tp("mix", t0)
        y = self.f1(x)
        t0 = self._tp("filtre", t0)
        if len(y):
            self.last_bb = y[-2048:]                 # 8.1 : le canal en bande de base (constellation, phase)
        if not len(y):
            return np.zeros(0, dtype=np.float32), self.level
        pw = float(np.mean(np.abs(y) ** 2))
        self.level = 10.0 * math.log10(pw + 1e-12)
        m = self.mode
        if m in ("wfm", "wfm_st", "nfm"):
            z = np.concatenate([[self.prev], y])
            d = np.angle(z[1:] * np.conj(z[:-1])).astype(np.float32) * (self.fs1 / (2.0 * math.pi * self.dev))
            self.prev = y[-1]
            t0 = self._tp("FM", t0)
            if m == "wfm_st":
                p = self.fp(d).astype(np.float32)
                amp = float(np.sqrt(2.0 * np.mean(p ** 2))) if len(p) else 0.0
                self.pil = amp if self.pil is None else 0.8 * self.pil + 0.2 * amp
                pf = np.concatenate([self.pprev, p])
                self.pprev = pf[-2:]
                self.dbuf = np.concatenate([self.dbuf, d])
                if self.dskip:
                    k_ = min(self.dskip, len(self.dbuf))
                    self.dbuf, self.dskip = self.dbuf[k_:], self.dskip - k_
                n_ = len(p)
                da, self.dbuf = self.dbuf[:n_], self.dbuf[n_:]
                m0 = self.f2(da).astype(np.float32)
                self.pre_raw = m0
                mono = self._deemph(m0, 0)
                if self.pil > 0.02:                         # pilote présent : stéréo
                    # pilote A·sin θ, sous-porteuse sin 2θ = 2 sin θ cos θ (norme : passages à zéro communs) ;
                    # cos θ par dérivée centrée
                    sn = pf[1:-1] / self.pil
                    cs = (pf[2:] - pf[:-2]) / (2.0 * self.sinD * self.pil)
                    diff = self._deemph(self.f3(2.0 * da * (2.0 * sn * cs)).astype(np.float32), 1)
                else:
                    diff = self._deemph(self.f3(np.zeros(len(da), dtype=np.float32)), 1) * 0.0
                nn = min(len(mono), len(diff))
                a = np.stack([mono[:nn] + diff[:nn], mono[:nn] - diff[:nn]], axis=1)
            else:
                a0 = self.f2(d).astype(np.float32)
                self.pre_raw = a0                         # 8.2 : son démodulé brut (avant désaccentuation et expanseur)
                a = self._deemph(a0, 0)
            t0 = self._tp("audio", t0)
            self._watch_pilot(d)
            self._watch_health(d)
            t0 = self._tp("pilote+santé", t0)
        elif m == "am":
            d = np.abs(y).astype(np.float32)
            self.dc = 0.99 * self.dc + 0.01 * float(d.mean()) if self.dc else float(d.mean())
            a = self._agc(self.f2(d - self.dc).astype(np.float32))
        else:                                               # usb / lsb / cw
            zz = self.fz(y)
            if not len(zz):
                return np.zeros(0, dtype=np.float32), self.level
            zz = self._nco(zz, self.sh, LISTEN_RATE, "ph2")  # bande latérale voulue centrée sur 0
            zz = self.sb(zz)
            if m == "cw":
                zz = self._nco(zz, -self.BFO, LISTEN_RATE, "ph3")   # porteuse → bip à 700 Hz
            else:
                zz = self._nco(zz, -self.sh, LISTEN_RATE, "ph3")    # retour : audio = partie réelle
            a = self._agc(np.real(zz).astype(np.float32))
        if len(a):
            self.pre = a                                  # 8.2 : son AVANT expanseur (Compander Lab en direct)
            a = self.chain.color_expand(a)
            t0 = self._tp("compander", t0)
        if self.squelch is not None and self.level < self.squelch:
            a = np.zeros_like(a)
        if self.rs is not None:              # étape 7 : débit qui ne tombe pas juste -> 48 kHz exacts
            a = self.rs(a)
        return a, self.level


def _cp_state(st):
    """État d'un compandeur en flux (dict de l'appelant, ou attribut « _cps » d'un objet comme ChannelDemod)."""
    if isinstance(st, dict):
        return st.setdefault("_cps", {})
    S = getattr(st, "_cps", None)
    if S is None:
        S = {"env": float(getattr(st, "env", 0.0) or 0.0)}   # ChannelDemod part de son enveloppe de départ
        try:
            st._cps = S
        except AttributeError:
            pass
    return S


def _gain_stream(a, side, S, block, level, gain):
    """8.1 (audit de la démo SDR) : gain par blocs de `block` échantillons sur une grille STABLE du flux, quelle que soit
    la taille des morceaux reçus : le reliquat d'un appel attend le suivant (S["buf"]), l'enveloppe et le dernier gain
    sont gardés, et le gain passe en rampe d'un bloc à l'autre (pas de marche). Sortie retardée d'UN bloc (5 ms à 48 kHz)
    et de même longueur que l'entrée : traiter un son d'un seul tenant ou en morceaux de n'importe quelle taille donne
    le même résultat. level(seg) -> niveau du détecteur d'un bloc ; gain(niveau) -> gain (met à jour l'enveloppe)."""
    a = np.asarray(a, dtype=np.float32)
    n = len(a)
    det = side if side is not None and len(side) == n else (a.mean(axis=1) if a.ndim == 2 else a)
    det = np.asarray(det, dtype=np.float32)
    if S.get("shape") != a.shape[1:]:                   # 1er appel (ou mono <-> stéréo) : flux remis à zéro
        S["shape"] = a.shape[1:]                        # (l'enveloppe « env », elle, est gardée)
        S["buf"] = np.zeros((0,) + a.shape[1:], dtype=np.float32)
        S["sbuf"] = np.zeros(0, dtype=np.float32)
        S["out"] = np.zeros((block,) + a.shape[1:], dtype=np.float32)
        S["g"] = None
    x = np.concatenate([S["buf"], a]) if len(S["buf"]) else a
    d = np.concatenate([S["sbuf"], det]) if len(S["sbuf"]) else det
    nb = len(x) // block
    if nb:
        G = np.empty(nb, dtype=np.float64)
        for k in range(nb):
            G[k] = gain(level(d[k * block:(k + 1) * block]))
        g0 = G[0] if S["g"] is None else S["g"]
        P = np.concatenate([[g0], G[:-1]])
        ramp = (P[:, None] + (G - P)[:, None] * (np.arange(1, block + 1) / float(block))[None, :]).astype(np.float32)
        ramp = ramp.reshape(-1)
        y = x[:nb * block] * (ramp[:, None] if x.ndim == 2 else ramp)
        S["g"] = float(G[-1])
        produced = np.concatenate([S["out"], y])
    else:
        produced = S["out"]
    S["buf"], S["sbuf"] = x[nb * block:].copy(), d[nb * block:].copy()
    S["out"] = produced[n:].copy()
    return produced[:n]


def _level_fn(detector):
    if detector == "avg":
        k = math.pi / (2 * math.sqrt(2))                # redressement moyen ramené à l'échelle efficace d'un sinus
        return lambda seg: float(np.mean(np.abs(seg))) * k
    return lambda seg: float(np.sqrt(np.mean(seg.astype(np.float64) ** 2)))


def compress2(a, st, block=240, ref=0.25, attack=0.3, release=0.05, ratio=2.0, detector="rms"):
    """8.1 : l'inverse d'expand2 (ce que fait l'ÉMETTEUR) : gain = (enveloppe / ref)^(1/taux − 1). Un son compressé
    ici puis étendu par expand2 (même ref, même détecteur) revient à son niveau : −18 dBFS au générateur = −18 dBFS à
    l'écoute. st = dict (état gardé). En flux (voir _gain_stream) : indépendant de la taille des morceaux."""
    a = np.asarray(a, dtype=np.float32)
    if not len(a) or ratio <= 1.0:
        return a
    S = _cp_state(st)
    lev = _level_fn(detector)

    def gain(r):
        e = S.get("env", 0.0)
        e += (attack if r > e else release) * (r - e)
        S["env"] = e
        return min(30.0, max(0.03, (max(e, 1e-6) / ref) ** (1.0 / ratio - 1.0)))
    return _gain_stream(a, None, S, block, lev, gain)


def expand2(a, st, block=240, ref=0.25, attack=0.3, release=0.05, ratio=2.0, detector="rms", knee=None, low=0.0,
            side=None):
    """Expanseur (approximation d'un compander de micro HF) : gain = (enveloppe / ref)^(taux − 1) par blocs de
    5 ms (taux 2 = 2:1 : 10 dB en entrée → 20 dB en sortie), lissé (montée rapide, descente lente), en rampe d'un bloc
    à l'autre. detector : « rms » (efficace) ou « avg » (redressement moyen, comme le SA572 ; ramené à l'échelle
    efficace d'un sinus). Stéréo (n, 2) : même gain sur les 2 voies. knee (dB sous ref) + low : sous ce niveau, le taux
    monte de `low` (réduction de bruit plus forte, ENR). side : signal vu par le détecteur à la place de l'audio (ex. sans
    les aigus extrêmes). 8.1 : en flux (voir _gain_stream), indépendant de la taille des morceaux reçus."""
    a = np.asarray(a, dtype=np.float32)
    if not len(a):
        return a
    S = _cp_state(st)
    lev = _level_fn(detector)

    def gain(r):
        e = S.get("env", 0.0)
        e += (attack if r > e else release) * (r - e)
        S["env"] = e
        r_ = max(e, 1e-6) / ref
        rt = ratio
        if knee is not None and low and 20.0 * math.log10(r_) < knee:
            rt = ratio + low                              # sous le genou : on « ferme » plus le souffle
        return min(4.0, max(0.001, r_ ** (rt - 1.0)))
    return _gain_stream(a, side, S, block, lev, gain)


def to_stereo(a):
    """Audio mono (n,) ou stéréo (n, 2) -> stéréo (n, 2)."""
    a = np.asarray(a, dtype=np.float32)
    return a if a.ndim == 2 else np.stack([a, a], axis=1)


def audio_int16(a, volume=1.0):
    """Audio float (mono ou stéréo) -> octets int16 STÉRÉO entrelacés G, D (écrêtage doux)."""
    return (np.tanh(to_stereo(a) * volume) * 32000).astype("<i2").tobytes()


def listen_center(freqs_mhz, kind):
    """Fréquence centrale (Hz) pour écouter ces fréquences ensemble, et celles qui tiennent dans la bande utile
    (80 % de l'échantillonnage, en évitant le pic du continu au centre). -> (centre Hz, [MHz retenues])."""
    fs = sdr_iq_rate(kind)
    use = 0.4 * fs / 1e6
    F = sorted(float(f) for f in freqs_mhz)
    if not F:
        return None, []
    best = []
    for f0 in F:                                   # la plus grande grappe qui tient dans la fenêtre
        g = [f for f in F if f0 <= f <= f0 + 2 * use - 0.3]
        if len(g) > len(best):
            best = g
    c = (best[0] + best[-1]) / 2.0
    if min(abs(f - c) for f in best) < 0.15:       # pas de canal pile sur le continu du SDR
        c -= 0.2
    return c * 1e6, best


def sigmf_meta(dtype, rate, center_hz, t0, hw="", annotations=()):
    """Métadonnées SigMF (fichier .sigmf-meta, JSON) d'un enregistrement IQ."""
    return {"global": {"core:datatype": dtype, "core:sample_rate": float(rate), "core:version": "1.0.0",
                       "core:recorder": "RF Technical Monitor", "core:hw": hw,
                       "core:description": "Enregistrement IQ (RF Technical Monitor, temps réel)"},
            "captures": [{"core:sample_start": 0, "core:frequency": float(center_hz),
                          "core:datetime": datetime_utc_iso(t0)}],
            "annotations": list(annotations)}


def datetime_utc_iso(t):
    """Horodatage epoch -> « 2026-10-29T14:03:12.250Z » (sans dépendre du module datetime)."""
    import time as _t
    return _t.strftime("%Y-%m-%dT%H:%M:%S", _t.gmtime(t)) + f".{int((t % 1) * 1000):03d}Z"


def iso_to_epoch(s):
    """« 2026-10-29T14:03:12.250Z » -> epoch (UTC), None si illisible."""
    import calendar
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.\d+)?", str(s or ""))
    if not m:
        return None
    t = calendar.timegm(tuple(int(m.group(i)) for i in range(1, 7)) + (0, 0, 0))
    return t + (float(m.group(7)) if m.group(7) else 0.0)


def sigmf_info(meta):
    """Métadonnées SigMF -> dict(dtype, rate, center, t0, hw). ValueError si format non géré."""
    g = meta.get("global", {})
    dtype = str(g.get("core:datatype", "")).lower()
    if dtype not in IQ_BYTES:
        raise ValueError(f"format IQ « {dtype} » non géré (ci8, cu8, ci16_le, cf32_le)")
    caps = meta.get("captures") or [{}]
    rate = float(g.get("core:sample_rate") or 0)
    if rate <= 0:
        raise ValueError("fréquence d'échantillonnage absente")
    return dict(dtype=dtype, rate=rate, center=float(caps[0].get("core:frequency") or 0.0),
                t0=iso_to_epoch(caps[0].get("core:datetime")), hw=str(g.get("core:hw", "")))


def sigmf_annot(ev, t0, rate):
    """Événement du détecteur -> annotation SigMF (début / durée en échantillons, bande, étiquette)."""
    s0 = max(0, int(round((ev["t0"] - t0) * rate)))
    n = max(1, int(round((ev["t1"] - ev["t0"]) * rate)))
    hw = max(ev.get("width", 0.0), 0.025) / 2.0
    return {"core:sample_start": s0, "core:sample_count": n, "core:freq_lower_edge": (ev["f"] - hw) * 1e6,
            "core:freq_upper_edge": (ev["f"] + hw) * 1e6, "core:label": f"signal {ev['f']:.3f} MHz {ev['peak']:.0f} dBFS"}


def rec_size_text(nbytes):
    """Taille lisible : « 1,4 Go », « 350 Mo »."""
    if nbytes >= 1e9:
        return f"{nbytes / 1e9:.1f} Go".replace(".", ",")
    return f"{nbytes / 1e6:.0f} Mo"


def listen_cmd(kind, exe, center_hz, rate, lna=24, vga=20, amp=False, serial=""):
    """Commande de l'outil d'IQ : hackrf_transfer -r - (HackRF), rtl_sdr - (RTL-SDR)."""
    exe = list(exe) if isinstance(exe, (list, tuple)) else [exe]
    if kind == "hackrf":
        a = exe + ["-r", "-", "-f", str(int(round(center_hz))), "-s", str(int(rate)), "-l", str(int(lna) // 8 * 8),
                   "-g", str(int(vga) // 2 * 2), "-a", "1" if amp else "0"]
    elif SDR_KINDS.get(kind, {}).get("soapy"):         # rx_sdr : IQ 16 bits (CS16) sur la sortie standard
        soapy = SDR_KINDS[kind]["soapy"]
        return exe + ["-d", f"driver={soapy}" + (f",serial={serial}" if serial else ""), "-f", str(int(round(center_hz))),
                      "-s", str(int(rate)), "-g", str(int(lna)), "-F", "CS16", "-"]
    else:
        a = exe + ["-f", str(int(round(center_hz))), "-s", str(int(rate)), "-g", str(int(lna))]
    if serial:
        a += ["-d", serial]
    return a + ([] if kind == "hackrf" else ["-"])


# ------------------------------------------------------------------ V8 : mode temps réel (fenêtre fixe, sans trou)
# Le SDR reste sur une fenêtre (jusqu'à ~15 MHz utiles sur un HackRF à 19,2 MS/s) : TOUS les échantillons passent
# dans des FFT jointives → rien n'échappe dans la fenêtre (contrairement à un balayage). Taux multiples de 240 kHz
# pour pouvoir démoduler directement (ChannelDemod) en cliquant sur le spectre.
RT_RATES = {"hackrf": [19200000, 9600000, 4800000], "rtlsdr": [2400000], "sdrplay": [9600000, 4800000, 2400000]}
RT_FFT = [1024, 2048, 4096, 8192, 16384]


def rt_frames(iq, nfft):
    """IQ -> FFT jointives (fenêtre de Blackman-Harris approchée par Blackman) : (moyenne dB, max dB) par case,
    centrées (fftshift), en dBFS (porteuse pleine échelle ≈ 0 dB). Les échantillons en trop (< nfft) sont ignorés."""
    m = len(iq) // nfft
    if m == 0:
        return None, None
    w = np.blackman(nfft).astype(np.float32)
    X = np.fft.fft(np.asarray(iq[:m * nfft]).reshape(m, nfft) * w, axis=1)
    P = (np.abs(X) ** 2) / (w.sum() ** 2)
    P = np.fft.fftshift(P, axes=1)
    return 10.0 * np.log10(P.mean(axis=0) + 1e-20), 10.0 * np.log10(P.max(axis=0) + 1e-20)


def rt_freqs(center_hz, rate, nfft):
    """Fréquences (MHz) des cases d'une FFT centrée."""
    return (center_hz + (np.arange(nfft) - nfft // 2) * (rate / nfft)) / 1e6


def rt_useful(center_hz, rate):
    """Partie utile de la fenêtre (MHz) : 80 % de l'échantillonnage (les bords sont filtrés par le SDR)."""
    return (center_hz - 0.4 * rate) / 1e6, (center_hz + 0.4 * rate) / 1e6


def decimate_max(y, n):
    """Réduit un tableau à ≤ n points en gardant le max de chaque paquet (affichage sans perdre de pic)."""
    y = np.asarray(y)
    if len(y) <= n:
        return y
    k = int(math.ceil(len(y) / n))
    m = len(y) // k * k
    out = y[:m].reshape(-1, k).max(axis=1)
    return np.append(out, y[m:].max()) if m < len(y) else out


class Persist:
    """Persistance : histogramme (fréquence × niveau) qui s'efface doucement. Montre la « densité » des signaux :
    une porteuse fixe fait un trait fort, un signal bref une trace pâle qui reste visible quelques secondes."""

    def __init__(self, nx, lo=-120.0, hi=0.0, ny=120, decay=0.92):
        self.nx, self.ny, self.lo, self.hi, self.decay = nx, ny, lo, hi, decay
        self.img = np.zeros((nx, ny), dtype=np.float32)

    def add(self, L):
        L = np.asarray(L, dtype=float)
        if len(L) != self.nx:
            self.__init__(len(L), self.lo, self.hi, self.ny, self.decay)
        self.img *= self.decay
        j = np.clip(((L - self.lo) / (self.hi - self.lo) * self.ny).astype(int), 0, self.ny - 1)
        self.img[np.arange(self.nx), j] += 1.0
        return self.img


class BurstDetector:
    """Repère les signaux qui apparaissent au-dessus d'un seuil (dBFS) dans la fenêtre, les suit tant qu'ils sont là,
    et rend un événement à leur disparition : {t0, t1, f (MHz, au pic), peak (dB), width (MHz)}. Les cases au-dessus
    du seuil séparées de moins de `gap` cases font un seul signal. `active` = signaux en cours."""

    def __init__(self, gap=3, min_dur=0.0):
        self.gap, self.min_dur = gap, min_dur
        self.active = []                 # [{i0, i1, t0, t_last, f, peak}]

    def feed(self, t, F, L, thr):
        L = np.asarray(L, dtype=float)
        on = np.nonzero(L >= thr)[0]
        groups = []
        if len(on):
            cut = np.nonzero(np.diff(on) > self.gap)[0]
            for a, b in zip(np.r_[0, cut + 1], np.r_[cut, len(on) - 1]):
                i0, i1 = int(on[a]), int(on[b])
                k = i0 + int(np.argmax(L[i0:i1 + 1]))
                groups.append((i0, i1, float(F[k]), float(L[k])))
        done, keep, used = [], [], set()
        for ev in self.active:
            m = next((g for g in range(len(groups)) if g not in used
                      and groups[g][0] <= ev["i1"] + self.gap and groups[g][1] >= ev["i0"] - self.gap), None)
            if m is None:
                if ev["t_last"] - ev["t0"] >= self.min_dur:
                    done.append(dict(t0=ev["t0"], t1=ev["t_last"], f=ev["f"], peak=ev["peak"],
                                     width=ev["width"]))
                continue
            used.add(m)
            i0, i1, f, pk = groups[m]
            ev.update(i0=i0, i1=i1, t_last=t)
            if pk > ev["peak"]:
                ev.update(peak=pk, f=f)
            ev["width"] = max(ev["width"], abs(F[i1] - F[i0]))
            keep.append(ev)
        for g, (i0, i1, f, pk) in enumerate(groups):
            if g not in used:
                keep.append(dict(i0=i0, i1=i1, t0=t, t_last=t, f=f, peak=pk, width=abs(F[i1] - F[i0])))
        self.active = keep
        return done


# ------------------------------------------------------------------ V8 étape 6 : écouter de partout
# Écoute depuis une alarme / une tuile / la chasse (FREQ_ACTIONS de la V7), son enregistré en WAV, balayage d'écoute
# (passe d'une fenêtre du SDR à l'autre), écoute sur le téléphone (vue web « ecoute », son en PCM 16 kHz mono).
LISTEN_WEB_RATE = 16000          # son envoyé au téléphone : 16 kHz mono 16 bits (voix, ~32 ko/s)
LISTEN_WEB_KEEP = 4.0            # secondes gardées pour le téléphone
LISTEN_HOP_DWELL = (2, 3, 5, 8, 12)   # s par fenêtre (balayage d'écoute)
HOP_OPEN_DB = 12.0               # squelch ouvert : « ça parle » = 12 dB au-dessus du canal le plus calme vu


def listen_windows(freqs_mhz, kind, maxch=4):
    """Fréquences à écouter -> fenêtres du SDR [(centre Hz, [MHz])] : la plus grande grappe d'abord (listen_center),
    puis la suivante avec ce qui reste ; au plus `maxch` canaux par fenêtre (démodulation simultanée)."""
    rest = sorted(set(round(float(f), 6) for f in freqs_mhz))
    out = []
    while rest:
        c, use = listen_center(rest, kind)
        use = list(use)[:maxch] if use else rest[:1]
        if c is None or not use:
            break
        if len(use) < len(listen_center(rest, kind)[1]):
            c = listen_center(use, kind)[0]
        out.append((c, use))
        rest = [f for f in rest if f not in use]
    return out


class HopState:
    """Balayage d'écoute : rester `dwell` s par fenêtre ; si un canal est actif (niveau au-dessus du squelch), rester
    tant qu'il l'est, puis `hang` s de plus (la fin d'une phrase). feed(t, actif) -> True quand il faut passer à la
    fenêtre suivante (l'appelant change de fenêtre puis appelle reset(t))."""

    def __init__(self, dwell=3.0, hang=2.0):
        self.dwell, self.hang = float(dwell), float(hang)
        self.t0 = self.last_on = None

    def reset(self, t):
        self.t0, self.last_on = t, None

    def feed(self, t, active):
        if self.t0 is None:
            self.reset(t)
        if active:
            self.last_on = t
            return False
        if self.last_on is not None:
            return t - self.last_on >= self.hang
        return t - self.t0 >= self.dwell


def pcm_mono16k(b):
    """Son de l'écoute (int16 stéréo entrelacé, 48 kHz) -> int16 mono 16 kHz pour le téléphone (moyenne G + D, puis
    moyenne de 3 échantillons = petit filtre avant de garder 1 sur 3)."""
    a = np.frombuffer(b, dtype="<i2").astype(np.float32)
    n = (len(a) // 6) * 6
    if n <= 0:
        return b""
    m = a[:n].reshape(-1, 2).mean(axis=1)
    return np.round(m.reshape(-1, 3).mean(axis=1)).astype("<i2").tobytes()


class PcmRing:
    """Son pour le téléphone : morceaux numérotés, les `keep` dernières secondes. since(n) -> (dernier n°, octets
    des morceaux après n) ; n trop ancien (téléphone en retard, ou 1re demande) = seulement les ~0,5 dernière s."""

    def __init__(self, rate=LISTEN_WEB_RATE, keep=LISTEN_WEB_KEEP):
        self.rate, self.keep = int(rate), float(keep)
        self.seq, self.chunks = 0, deque()

    def push(self, b):
        if not b:
            return
        self.seq += 1
        self.chunks.append((self.seq, b))
        size = sum(len(x) for _s, x in self.chunks)
        while self.chunks and size > self.keep * self.rate * 2:
            size -= len(self.chunks.popleft()[1])

    def clear(self):
        self.chunks.clear()

    def since(self, n):
        n = int(n or 0)
        if not self.chunks:
            return self.seq, b""
        first = self.chunks[0][0]
        if n <= 0 or n < first - 1 or n > self.seq:   # 1re demande, trop vieux, serveur relancé : le présent
            out, size = [], 0
            for s, x in reversed(self.chunks):
                out.append(x)
                size += len(x)
                if size >= self.rate:                    # ~0,5 s (16 bits)
                    break
            return self.seq, b"".join(reversed(out))
        return self.seq, b"".join(x for s, x in self.chunks if s > n)


def pcm_packet(seq, rate, data):
    """Réponse de /ecoute.pcm : 4 octets « TSMA », n° (uint32), fréquence d'échantillonnage (uint32), puis PCM int16."""
    return b"TSMA" + np.array([int(seq) & 0xFFFFFFFF, int(rate)], dtype="<u4").tobytes() + (data or b"")


def listen_request(req):
    """Commande POST /ecoute (téléphone, code PIN) -> dict(action start | stop | pick, f MHz, mode) ; ValueError."""
    if not isinstance(req, dict):
        raise ValueError("requête")
    act = str(req.get("action", ""))
    if act not in ("start", "stop"):
        raise ValueError("action")
    out = dict(action=act)
    if act == "start":
        f = float(req.get("f"))
        if not (1.0 <= f <= 6000.0) or f != f:
            raise ValueError("fréquence")
        out["f"] = round(f, 6)
        mode = str(req.get("mode") or "")
        out["mode"] = mode if mode in LISTEN_MODES else ""
    return out


# ------------------------------------------------------------------ V8 étape 7 : fiches des SDR (ce qui change d'un appareil à l'autre)
# Sources : fiches des fabricants lues le 24/11/2026 (Great Scott Gadgets HackRF One / Pro, Airspy R2 / Mini / HF+,
# rtl-sdr.com V4, kit WiNRADiO G39DDC / G65DDC : doc + G39DDCAPI.h). SDRplay, Lime, Pluto, USRP, bladeRF : valeurs des
# fiches publiques connues, PAS relues ici (site injoignable) -> « src » = "fiche (non relue)".
# kind = façon de le piloter (SDR_KINDS) ; rates = débits IQ proposés (S/s) ; usable = part utile de la bande IQ ;
# bits / enob = résolution du convertisseur ; max_in = puissance d'entrée max conseillée (dBm, None = inconnue) ;
# gains = étages [(clé, nom, min, max, pas, défaut)] ; cal = niveaux déjà en dBm (WiNRADiO), sinon dBFS à caler.
SDR_MODELS = [
    dict(key="hackrf_one", kind="hackrf", name="HackRF One", fmin=1.0, fmax=6000.0, bits=8, enob=7.0,
         rates=[19200000, 9600000, 4800000, 2400000], usable=0.8, max_in=-5.0,
         gains=[("lna", "LNA (gain RF)", 0, 40, 8, 24), ("vga", "VGA (gain bande de base)", 0, 62, 2, 20),
                ("amp", "Ampli d'entrée +14 dB", 0, 1, 1, 0)], cal=False, src="greatscottgadgets.com",
         note="8 bits : environ 48 dB de dynamique dans la fenêtre ; un émetteur fort tout près sature vite. "
              "Ne pas dépasser −5 dBm à l'entrée."),
    dict(key="hackrf_pro", kind="hackrf", name="HackRF Pro", fmin=0.1, fmax=6000.0, bits=8, enob=7.0,
         rates=[19200000, 9600000, 4800000, 2400000], usable=0.8, max_in=-5.0,
         gains=[("lna", "LNA (gain RF)", 0, 40, 8, 24), ("vga", "VGA (gain bande de base)", 0, 62, 2, 20),
                ("amp", "Ampli d'entrée", 0, 1, 1, 0)], cal=False, src="greatscottgadgets.com",
         note="100 kHz – 6 GHz, 8 bits ; mode 16 bits (ENOB 9 à 11) à bas débit, pas encore utilisé par les outils "
              "hackrf_* (supposé). Entrée max supposée comme le One."),
    dict(key="rtl_v3", kind="rtlsdr", name="RTL-SDR Blog V3", fmin=24.0, fmax=1766.0, bits=8, enob=7.0,
         rates=[2400000], usable=0.8, max_in=10.0,
         gains=[("lna", "Gain du tuner", 0, 50, 1, 30)], cal=False, src="fiche (non relue)",
         note="8 bits, 2,4 MS/s stables (≈ 1,9 MHz utiles) : une seule petite fenêtre."),
    dict(key="rtl_v4", kind="rtlsdr", name="RTL-SDR Blog V4", fmin=0.5, fmax=1766.0, bits=8, enob=7.0,
         rates=[2400000], usable=0.8, max_in=10.0,
         gains=[("lna", "Gain du tuner", 0, 50, 1, 30)], cal=False, src="rtl-sdr.com",
         note="Comme le V3 avec la HF intégrée (convertisseur) ; 8 bits, 2,4 MS/s."),
    dict(key="rsp1b", kind="sdrplay", name="SDRplay RSP1B", fmin=0.001, fmax=2000.0, bits=14, enob=None,
         rates=[9600000, 4800000, 2400000], usable=0.8, max_in=0.0,
         gains=[("lna", "Gain (réduction LNA + IF)", 0, 60, 1, 40)], cal=False, src="fiche (non relue)",
         note="14 bits jusqu'à ~6 MS/s (moins de bits au-delà, jusqu'à 10 MHz de large). Bien plus de dynamique "
              "qu'un 8 bits : un micro faible à côté d'un émetteur fort reste visible."),
    dict(key="rsp1a", kind="sdrplay", name="SDRplay RSP1A", fmin=0.001, fmax=2000.0, bits=14, enob=None,
         rates=[9600000, 4800000, 2400000], usable=0.8, max_in=0.0,
         gains=[("lna", "Gain (réduction LNA + IF)", 0, 60, 1, 40)], cal=False, src="fiche (non relue)",
         note="Même électronique de réception que le RSP1B (14 bits, 10 MHz)."),
    dict(key="rspdx", kind="sdrplay", name="SDRplay RSPdx / RSPdx-R2", fmin=0.001, fmax=2000.0, bits=14, enob=None,
         rates=[9600000, 4800000, 2400000], usable=0.8, max_in=0.0,
         gains=[("lna", "Gain (réduction LNA + IF)", 0, 60, 1, 40)], cal=False, src="fiche (non relue)",
         note="14 bits, 10 MHz, 3 entrées d'antenne (choisies dans le logiciel SDRplay)."),
    dict(key="rspduo", kind="sdrplay", name="SDRplay RSPduo", fmin=0.001, fmax=2000.0, bits=14, enob=None,
         rates=[9600000, 4800000, 2400000], usable=0.8, max_in=0.0,
         gains=[("lna", "Gain (réduction LNA + IF)", 0, 60, 1, 40)], cal=False, src="fiche (non relue)",
         note="Deux tuners : 10 MHz avec un seul, 2 MHz chacun en double tuner (non géré ici : un seul tuner)."),
    dict(key="airspy_r2", kind="airspy", name="Airspy R2", fmin=24.0, fmax=1700.0, bits=12, enob=10.4,
         rates=[10000000, 2500000], usable=0.9, max_in=10.0,
         gains=[("lna", "Gain (linéarité 0 – 21)", 0, 21, 1, 14)], cal=False, src="airspy.com",
         note="12 bits (10,4 ENOB), 10 MS/s, ~9 MHz sans repliement. Débits pas multiples de 240 kHz : son "
              "rééchantillonné."),
    dict(key="airspy_mini", kind="airspy", name="Airspy Mini", fmin=24.0, fmax=1700.0, bits=12, enob=10.4,
         rates=[10000000, 6000000, 3000000], usable=0.8, max_in=10.0,
         gains=[("lna", "Gain (linéarité 0 – 21)", 0, 21, 1, 14)], cal=False, src="airspy.com",
         note="12 bits, jusqu'à 6 MHz de vue (10 MS/s possibles)."),
    dict(key="airspy_hf", kind="airspyhf", name="Airspy HF+ Discovery", fmin=0.0005, fmax=260.0, bits=None,
         enob=None, rates=[768000, 384000, 192000], usable=0.8, max_in=None,
         gains=[("lna", "Atténuateur (0 = automatique)", 0, 48, 6, 0)], cal=False, src="airspy.com",
         note="HF 0,5 kHz – 31 MHz et VHF 64 – 260 MHz : PAS d'UHF (micros 470-694 hors de portée). "
              "Très grande dynamique (110 dB BDR en HF)."),
    dict(key="limemini", kind="lime", name="LimeSDR Mini", fmin=10.0, fmax=3500.0, bits=12, enob=None,
         rates=[19200000, 9600000, 4800000], usable=0.8, max_in=None,
         gains=[("lna", "Gain", 0, 70, 1, 40)], cal=False, src="fiche (non relue)", note="12 bits, jusqu'à ~30 MS/s."),
    dict(key="pluto", kind="pluto", name="ADALM-Pluto", fmin=325.0, fmax=3800.0, bits=12, enob=None,
         rates=[4800000, 2400000], usable=0.8, max_in=None,
         gains=[("lna", "Gain", 0, 70, 1, 50)], cal=False, src="fiche (non relue)",
         note="12 bits ; en USB 2 le débit utile tient autour de 4 MS/s."),
    dict(key="b200", kind="uhd", name="Ettus USRP B200 / B210", fmin=70.0, fmax=6000.0, bits=12, enob=None,
         rates=[19200000, 9600000, 4800000], usable=0.8, max_in=-15.0,
         gains=[("lna", "Gain", 0, 76, 1, 40)], cal=False, src="fiche (non relue)",
         note="12 bits, jusqu'à 56 MHz ; entrée max −15 dBm (fiche)."),
    dict(key="bladerf2", kind="bladerf", name="bladeRF 2.0 micro", fmin=47.0, fmax=6000.0, bits=12, enob=None,
         rates=[19200000, 9600000, 4800000], usable=0.8, max_in=None,
         gains=[("lna", "Gain", 0, 60, 1, 30)], cal=False, src="fiche (non relue)", note="12 bits, jusqu'à 61,44 MS/s."),
    dict(key="g39ddc", kind="winradio", name="WiNRADiO G39DDC Excelsior", fmin=0.009, fmax=3500.0, bits=16,
         enob=None, rates=[5000000], usable=0.8, max_in=None,
         gains=[("att", "Atténuateur (< 60 MHz)", 0, 18, 6, 0), ("amp", "Préampli", 0, 1, 1, 0)], cal=True,
         src="winradio.com (doc + G39DDCAPI.h)",
         note="16 bits à 100 MS/s. Balayage matériel calibré en dBm. Flux IQ (DDC1) jusqu'à 4 MHz (2 canaux) ou "
              "6 MHz (mode large) : débits demandés au récepteur. Piloté par sa DLL Windows G39DDCAPI.dll."),
    dict(key="g65ddc", kind="", name="WiNRADiO G65DDC", fmin=0.009, fmax=88.0, bits=16, enob=None, rates=[],
         usable=1.0, max_in=None, gains=[], cal=True, src="winradio.com (doc + G65DDCAPI.h)",
         note="0 – 88 MHz seulement : pas de micros UHF. Pas pris en charge (API différente : canaux DDC multiples)."),
]
SDR_MODEL_DEFAULT = {"hackrf": "hackrf_one", "rtlsdr": "rtl_v3", "sdrplay": "rsp1b", "airspy": "airspy_r2",
                     "airspyhf": "airspy_hf", "lime": "limemini", "pluto": "pluto", "uhd": "b200", "bladerf": "bladerf2",
                     "winradio": "g39ddc"}


def sdr_model(key):
    """Fiche d'un modèle par sa clé (None si inconnue)."""
    return next((m for m in SDR_MODELS if m["key"] == key), None)


for _k, _mk in SDR_MODEL_DEFAULT.items():         # temps réel : débits proposés d'après la fiche du modèle
    if _mk and sdr_model(_mk) and sdr_model(_mk)["rates"]:
        RT_RATES.setdefault(_k, sorted(sdr_model(_mk)["rates"], reverse=True))


def sdr_models_for(kind):
    """Modèles pilotés de la même façon (pour choisir le sien)."""
    return [m for m in SDR_MODELS if m["kind"] == kind]


def sdr_model_of(kind, chosen=None):
    """Modèle retenu pour un genre : celui choisi par l'utilisateur ({genre: clé}) s'il va avec, sinon le défaut."""
    m = sdr_model((chosen or {}).get(kind)) if chosen else None
    return m if m is not None and m["kind"] == kind else sdr_model(SDR_MODEL_DEFAULT.get(kind))


def bits_dynamic(bits):
    """Dynamique théorique d'un convertisseur de `bits` bits (dB) : 6,02 × bits + 1,76."""
    return None if not bits else round(6.02 * bits + 1.76, 1)


def sdr_floor_dbfs(model, rate=None, chan_hz=200000.0):
    """Plancher de quantification dans un canal (dBFS) : bruit du convertisseur réparti sur toute la bande IQ, dont le
    canal ne voit qu'une part. Borne basse de l'échelle des niveaux (le vrai bruit, analogique, est souvent au-dessus)."""
    b = (model or {}).get("enob") or (model or {}).get("bits") or 8
    fs = float(rate or ((model or {}).get("rates") or [2400000])[0])
    return round(-(6.02 * b + 1.76) - 10.0 * math.log10(max(1.0, fs / chan_hz)), 1)


def sdr_rate(model, kind=None, want=None):
    """Débit IQ à utiliser : `want` s'il est proposé, sinon le plus petit ≥ 4,8 MS/s, sinon le plus grand."""
    rates = sorted((model or {}).get("rates") or [])
    if not rates:
        return sdr_iq_rate(kind or (model or {}).get("kind") or "")
    if want in rates:
        return want
    big = [r for r in rates if r >= 4800000]
    return big[0] if big else rates[-1]


def sdr_span_mhz(model, rate):
    """Largeur utile (MHz) d'une fenêtre IQ à ce débit."""
    return float(rate) * float((model or {}).get("usable") or 0.8) / 1e6


def sdr_in_range(model, f_mhz):
    return model is not None and model["fmin"] <= float(f_mhz) <= model["fmax"]


def sdr_model_text(m, tr=None):
    """Fiche lisible d'un modèle (fenêtre Réglages SDR)."""
    tr = tr or (lambda x: x)
    if not m:
        return ""
    lines = [f"{m['name']} : {m['fmin']:g} – {m['fmax']:g} MHz"]
    if m.get("bits"):
        d = bits_dynamic(m.get("enob") or m["bits"])
        lines.append(tr("{} bits").format(m["bits"]) + (f" (ENOB {m['enob']:g})" if m.get("enob") else "")
                     + " · " + tr("dynamique théorique ≈ {} dB").format(f"{d:.0f}"))
    if m.get("rates"):
        r = max(m["rates"])
        lines.append(tr("Débits : {} MS/s · fenêtre utile jusqu'à {} MHz").format(
            " / ".join(f"{x / 1e6:g}" for x in sorted(m["rates"], reverse=True)), f"{sdr_span_mhz(m, r):.1f}"))
    if m.get("max_in") is not None:
        lines.append(tr("Entrée max conseillée : {} dBm").format(f"{m['max_in']:g}"))
    lines.append(tr("Niveaux en vrais dBm (calibrés par l'appareil)") if m.get("cal") else
                 tr("Niveaux en dBFS : à caler sur un tinySA (offset)"))
    if m.get("note"):
        lines.append(tr(m["note"]))
    lines.append(tr("Source : {}").format(m.get("src", "")))
    return "\n".join(lines)


def sdr_cfg_extra(sd):
    """Réglages SDR de l'étape 7 lus de la config (relus prudemment) : model, models {genre: clé}, gains {clé: {étage:
    entier}}, offsets {clé: dB}."""
    out = {}
    sd = sd if isinstance(sd, dict) else {}
    if sdr_model(sd.get("model")):
        out["model"] = sd["model"]
    mods = sd.get("models")
    if isinstance(mods, dict):
        out["models"] = {k: v for k, v in mods.items() if k in SDR_KINDS and sdr_model(v) and sdr_model(v)["kind"] == k}
    gs = sd.get("gains")
    if isinstance(gs, dict):
        g2 = {}
        for k, d in gs.items():
            m = sdr_model(k)
            if m is None or not isinstance(d, dict):
                continue
            g2[k] = {}
            for gk, _n, lo, hi, _st, _df in m["gains"]:
                try:
                    if gk in d:
                        g2[k][gk] = int(min(hi, max(lo, int(d[gk]))))
                except (TypeError, ValueError):
                    pass
        out["gains"] = g2
    offs = sd.get("offsets")
    if isinstance(offs, dict):
        o2 = {}
        for k, v in offs.items():
            try:
                if sdr_model(k):
                    o2[k] = float(min(60.0, max(-60.0, float(v))))
            except (TypeError, ValueError):
                pass
        out["offsets"] = o2
    if "privacy" in sd:                                 # étape 12 : son enregistré, durée de conservation
        out["privacy"] = privacy_norm(sd.get("privacy"))
    rh = rehearsal_norm(sd.get("rehearsal"))           # étape 11 : profil de répétition, récepteurs Shure
    if rh:
        out["rehearsal"] = rh
    if "station" in sd:                                # étape 16 : poste SDR (fréquences A / B, réglages)
        out["station"] = station_norm(sd.get("station"))
    if "favs" in sd:                                   # étape 18 : raccourcis du pavé numérique
        out["favs"] = favs_norm(sd.get("favs"))
    if "audio_dev" in sd:                              # 8.1 : sortie de l'écoute SDR ("" = celle des sons de l'appli)
        out["audio_dev"] = str(sd.get("audio_dev") or "")[:200]
    if "af_post" in sd:                                # 8.1 : vu-mètre du son avant / après le volume
        out["af_post"] = bool(sd.get("af_post"))
    if isinstance(sd.get("rx_views"), dict):            # 8.1 : vues des 2 petites fenêtres du Récepteur
        rv = sd["rx_views"]
        out["rx_views"] = dict(iff=rv.get("iff") if rv.get("iff") in dict(RX_IF_VIEWS) else "spec",
                               af=rv.get("af") if rv.get("af") in dict(RX_AF_VIEWS) else "spec")
    if sd.get("meter_style") in dict(METER_STYLES):     # 8.1 : vu-mètre RF en aiguille ou en barre
        out["meter_style"] = sd["meter_style"]
    if "demo" in sd:                                   # étape 21 : SDR démo (sans matériel)
        out["demo"] = bool(sd.get("demo"))
    if sd.get("rewind_min") in REWIND_MINUTES:          # étape 22 : ⏪ minutes gardées
        out["rewind_min"] = int(sd["rewind_min"])
    if isinstance(sd.get("demo_snd"), dict):            # étape 21 : son de chaque micro dans le SDR démo
        out["demo_snd"] = {str(k): audio_spec_norm(v) for k, v in list(sd["demo_snd"].items())[:200]
                           if str(k).isdigit()}
    if isinstance(sd.get("demo_kind"), dict):           # 8.0.3 : type de signal de chaque micro dans les démos
        out["demo_kind"] = {str(k): v for k, v in list(sd["demo_kind"].items())[:300]
                            if str(k).isdigit() and v in dict(DEMO_SIG_KINDS)}
    if "auto" in sd:                                   # étape 20 : alarme -> calage, patrouille, pilote
        out["auto"] = sdr_auto_norm(sd.get("auto"))
    if "posts" in sd:                                  # étape 17 : plusieurs postes SDR
        out["posts"] = sdr_posts_norm(sd.get("posts"))
    if isinstance(sd.get("stations"), dict):
        out["stations"] = {str(k): station_norm(v) for k, v in sd["stations"].items()
                           if str(k).isdigit() and 2 <= int(k) <= SDR_POSTS_MAX}
    if "rf_mode" in sd:
        out["rf_mode"] = rf_mode_norm(sd.get("rf_mode"))
    if "phases" in sd or rh:                           # 20. phases du show (l'ancienne répétition y est reprise)
        out["phases"] = phases_norm(sd.get("phases"), sd.get("rehearsal"))
    if isinstance(sd.get("shure"), str):               # étape 13 : toutes marques (préfixe g4: / ssc: …)
        out["shure"] = receiver_addrs_text(receiver_addrs(sd["shure"]))
    return out


def sdr_gains_for(model, gains_cfg=None, legacy=None):
    """Gains à passer aux outils pour un modèle : {lna, vga, amp, att} (valeurs de l'utilisateur, sinon les défauts du
    modèle ; `legacy` = anciens réglages globaux lna / vga / amp, utilisés s'il n'a rien réglé pour ce modèle)."""
    out = dict(lna=24, vga=20, amp=False, att=0)
    legacy = legacy or {}
    g = (gains_cfg or {}).get((model or {}).get("key"), {})
    for gk, _n, lo, hi, _st, dflt in (model or {}).get("gains", []):
        v = g.get(gk, legacy.get(gk, dflt))
        try:
            v = int(min(hi, max(lo, int(v))))
        except (TypeError, ValueError):
            v = dflt
        out[gk] = bool(v) if gk == "amp" else v
    return out


class Resampler:
    """Rééchantillonnage linéaire en flux (fs_in -> fs_out) : le son d'un débit qui ne tombe pas juste (Airspy
    10 MS/s, WiNRADiO) sort quand même à 48 kHz, sans changer la hauteur. Mono (n,) ou stéréo (n, 2)."""

    def __init__(self, fs_in, fs_out):
        self.r = float(fs_in) / float(fs_out)
        self.prev = None                   # dernier échantillon du bloc précédent (index 0 du bloc suivant)
        self.t = 0.0                       # position du prochain échantillon de sortie (en échantillons d'entrée)

    def __call__(self, x):
        x = np.asarray(x, dtype=np.float32)
        if abs(self.r - 1.0) < 1e-6 or not len(x):
            return x
        y = x if self.prev is None else np.concatenate([self.prev[None], x])
        n = len(y)
        if self.t > n - 1:                 # rien à sortir dans ce bloc
            self.t -= n - 1
            self.prev = y[-1].copy()
            return y[:0]
        k = np.arange(self.t, n - 1 + 1e-9, self.r)
        i0 = np.floor(k).astype(int)
        fr = (k - i0).astype(np.float32)
        i1 = np.minimum(i0 + 1, n - 1)
        if y.ndim == 1:
            out = y[i0] * (1 - fr) + y[i1] * fr
        else:
            out = y[i0] * (1 - fr)[:, None] + y[i1] * fr[:, None]
        self.t = k[-1] + self.r - (n - 1)
        self.prev = y[-1].copy()
        return out.astype(np.float32)


# --- WiNRADiO G39DDC : calculs (sans la DLL) -------------------------------------------------------------------
WR_ADC_RATE = 100000000           # convertisseur du G39DDC : 100 MS/s, 16 bits signés (instantanés « IF »)


def wr_pick_ddc(infos, want_bw):
    """Types de DDC1 [(index, débit, largeur utile, bits)] -> index du plus petit type dont la largeur utile couvre
    want_bw (Hz), en 16 bits de préférence (moitié moins de données) ; sinon le plus large. None si liste vide."""
    if not infos:
        return None
    ok = [x for x in infos if x[2] >= want_bw]
    if ok:
        ok.sort(key=lambda x: (x[2], x[3] != 16, x[1]))
        return ok[0][0]
    return max(infos, key=lambda x: (x[2], x[3] == 16))[0]


def wr_snapshot_spectrum(samples, center_if, fe_hz, window_w, comp_db=None, adc_rate=WR_ADC_RATE, nfft=8192,
                         inverted=False):
    """Instantané IF du G39DDC (16 bits réels à 100 MS/s) -> (F MHz, dBm) de la bande utile. FFT moyennée sur des blocs
    de nfft (fenêtre de Blackman), moitié basse ; compensation de la DLL (dB par case, GetIFSpectrumCompensation)
    ajoutée -> dBm. Bande utile = center_if ± window_w / 2 (FrontEndWindowWidth) ; fréquence RF = fe_hz +
    (f_IF − center_if), ou l'inverse si le spectre est inversé (`inverted` : sens NON vérifié sur un vrai G39DDC)."""
    x = np.asarray(samples, dtype=np.float32) / 32768.0
    m = len(x) // nfft
    if m == 0:
        return None, None
    w = np.blackman(nfft).astype(np.float32)
    seg = x[:m * nfft].reshape(m, nfft) * w
    P = np.mean(np.abs(np.fft.rfft(seg, axis=1)[:, :nfft // 2]) ** 2, axis=0)
    db = 10.0 * np.log10(np.maximum(P, 1e-20))
    if comp_db is not None and len(comp_db) == len(db):
        db = db + np.asarray(comp_db, dtype=float)
    fif = np.arange(nfft // 2) * (adc_rate / nfft)
    lo, hi = center_if - window_w / 2.0, center_if + window_w / 2.0
    sel = (fif >= lo) & (fif <= hi)
    off = fif[sel] - center_if
    F = (fe_hz + (-off if inverted else off)) / 1e6
    L = db[sel]
    o = np.argsort(F)
    return F[o], L[o]


# ------------------------------------------------------------------ V8 étape 8 : ce que le SDR sait dire en plus
# (Clément : « go 1/2/3/4/5 ») 1. type de signal, 2. santé d'un micro analogique, 3. signaux brefs -> alarme,
# 4. enregistrement automatique sur alarme, 5. mesures (largeur occupée, SNR, tient dans le canal ?).
# Seuils = valeurs de départ (choix de Claude), PAS mesurées sur de vrais émetteurs.
SIG_TYPES = {   # clé -> (nom court, ce que c'est probablement)
    "tnt": ("TV numérique (TNT)", "Plateau large (5 – 8 MHz) et plat : un multiplex TNT. Les micros doivent l'éviter."),
    "wide": ("Signal large", "Plus de 1 MHz de large sans être plat : bloc numérique (WMAS, Spectera ?), vidéo HF, "
             "LTE / 5G, ou plusieurs signaux collés."),
    "num": ("Micro / ears numérique", "Plateau plat de 150 kHz à 1 MHz : micro ou ears numérique (codec), DECT, "
            "données. Ne s'écoute pas."),
    "fm_st": ("FM stéréo (ears / radio)", "FM large avec pilote stéréo 19 kHz : ears analogique en stéréo ou "
              "radio FM."),
    "fm_ana": ("Micro / ears FM analogique", "FM large (≈ 50 – 250 kHz) : micro HF ou ears analogique. Il "
               "s'écoute (🎧)."),
    "nfm": ("FM étroite (talkie)", "FM étroite (10 – 50 kHz) : talkie, PMR446, intercom, télémétrie."),
    "cw": ("Porteuse pure", "Très étroit et stable : porteuse sans modulation (émetteur allumé micro coupé, oscillateur, "
           "horloge d'un appareil, intermod d'une porteuse)."),
    "none": ("Rien de net", "Pas de signal assez fort à cette fréquence."),
}
CHANNEL_KHZ = 200.0         # canal d'un micro analogique (EN 300 422 : 200 kHz) — repère, pas un contrôle réglementaire


def obw_khz(F, L, f0, span=1.0, frac=0.99):
    """Largeur occupée (kHz) autour de f0 (MHz) : bande qui contient `frac` de la puissance au-dessus du bruit, dans
    f0 ± span. -> (largeur kHz, début MHz, fin MHz) ou (None, None, None)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    m = (np.abs(F - f0) <= span) & np.isfinite(L)
    if m.sum() < 5:
        return None, None, None
    Fs, Ls = F[m], L[m]
    fl = float(np.percentile(Ls, 20))
    p = np.maximum(10.0 ** (Ls / 10.0) - 10.0 ** (fl / 10.0), 0.0)
    tot = float(p.sum())
    if tot <= 0:
        return None, None, None
    c = np.cumsum(p) / tot
    lo = float(Fs[int(np.searchsorted(c, (1.0 - frac) / 2.0))])
    hi = float(Fs[min(len(Fs) - 1, int(np.searchsorted(c, 1.0 - (1.0 - frac) / 2.0)))])
    step = float(np.median(np.diff(Fs))) if len(Fs) > 1 else 0.0
    return max(step, hi - lo) * 1000.0, lo, hi


def classify_signal(F, L, f0, pilot=None, span=None):
    """1. « C'est quoi ce signal ? » d'après le spectre autour de f0 (MHz) : largeur à −20 dB du pic, platitude du
    haut, pilote vu dans le FM démodulé (Hz, dB) s'il y en a. -> dict(kind, name, why, bw_khz (−20 dB), obw_khz (99 %),
    snr, flat)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    span = float(span or (5.0 if (F.max() - F.min()) > 6 else max(0.3, 0.45 * (F.max() - F.min()))))
    m = (np.abs(F - f0) <= span) & np.isfinite(L)
    out = dict(kind="none", bw_khz=None, obw_khz=None, snr=None, flat=None)
    if m.sum() < 8:
        out.update(name=SIG_TYPES["none"][0], why=SIG_TYPES["none"][1])
        return out
    Fs, Ls = F[m], L[m]
    floor = float(np.percentile(Ls, 15))
    near = np.abs(Fs - f0) <= max(0.05, 2.5 * float(np.median(np.diff(Fs))))
    k = int(np.argmax(np.where(near, Ls, -np.inf))) if near.any() else int(np.argmax(Ls))
    pk = float(Ls[k])
    snr = pk - floor
    out["snr"] = round(snr, 1)
    if snr < 8:
        out.update(name=SIG_TYPES["none"][0], why=SIG_TYPES["none"][1])
        return out
    thr = max(pk - 20.0, floor + 4.0)
    i, j = k, k
    while i > 0 and Ls[i - 1] >= thr:
        i -= 1
    while j < len(Ls) - 1 and Ls[j + 1] >= thr:
        j += 1
    step = float(np.median(np.diff(Fs)))
    bw = (Fs[j] - Fs[i] + step) * 1000.0
    top = Ls[i:j + 1]
    core = top[len(top) // 5: len(top) - len(top) // 5] if len(top) >= 5 else top
    flat = float(np.std(core)) if len(core) >= 3 else 99.0
    ob = obw_khz(Fs, Ls, float(Fs[k]), span)[0]
    out.update(bw_khz=round(bw, 1), obw_khz=round(ob, 1) if ob else None, flat=round(flat, 1))
    if pilot and abs(pilot[0] - 19000.0) < 400:
        kind = "fm_st"
    elif bw >= 4500:
        kind = "tnt" if flat < 3.5 else "wide"
    elif bw >= 1000:
        kind = "wide"
    elif bw >= 120 and flat < 2.5:
        kind = "num"
    elif bw >= 50 or (pilot and bw >= 25):
        kind = "fm_ana"
    elif bw > max(6.0, 4.5 * step * 1000.0):      # au-delà de la largeur d'une porteuse vue à cette résolution
        kind = "nfm"
    else:
        kind = "cw"
    out.update(kind=kind, name=SIG_TYPES[kind][0], why=SIG_TYPES[kind][1])
    return out


def signal_report(c, tr=None, channel_khz=CHANNEL_KHZ):
    """5. Phrase de mesure : type, largeur occupée 99 %, SNR, tient dans un canal de 200 kHz ?"""
    tr = tr or (lambda x: x)
    if c.get("kind") == "none":
        return tr(c.get("name", ""))
    parts = [tr(c["name"])]
    if c.get("obw_khz"):
        parts.append(tr("largeur occupée {} kHz").format(f"{c['obw_khz']:.0f}"))
    if c.get("snr") is not None:
        parts.append(tr("{} dB au-dessus du bruit").format(f"{c['snr']:.0f}"))
    if c.get("kind") in ("fm_ana", "fm_st", "nfm", "cw") and c.get("obw_khz"):
        parts.append(tr("✔ tient dans un canal de {} kHz").format(f"{channel_khz:.0f}") if c["obw_khz"] <= channel_khz
                     else tr("⚠ déborde d'un canal de {} kHz").format(f"{channel_khz:.0f}"))
    return " · ".join(parts)


def mic_health(dev_khz, nominal_khz, drift_khz=None, pilot=None, audio=None):
    """2. Santé d'un micro FM analogique : déviation crête mesurée (kHz) comparée à la nominale du préréglage, dérive
    de fréquence (kHz, écart à la fréquence réglée), pilote, présence de son. -> (texte, ton ok|warn|bad|none)."""
    if dev_khz is None:
        return "—", "none"
    parts, tone = [f"dév. ±{dev_khz:.0f} kHz"], "ok"
    nom = float(nominal_khz or 0) or None
    if nom:
        r = dev_khz / nom
        if r > 1.25:
            parts.append("trop chaud (sature ?)")
            tone = "bad" if r > 1.6 else "warn"
        elif r < 0.12 and (audio or 0) > 0.02:
            parts.append("très froid")
            tone = "warn"
    if drift_khz is not None:
        parts.append(f"dérive {drift_khz:+.1f} kHz")
        if abs(drift_khz) > 15:
            tone = "bad"
            parts.append("hors fréquence ?")
        elif abs(drift_khz) > 5 and tone == "ok":
            tone = "warn"
    if pilot:
        parts.append(f"pilote {pilot[0] / 1000:.1f} kHz")
    return " · ".join(parts), tone


class PreRing:
    """4. Les `keep` dernières secondes d'un flux (octets), pour enregistrer AVANT l'alarme."""

    def __init__(self, keep_s=10.0, bytes_per_s=192000):
        self.max = int(keep_s * bytes_per_s)
        self.q, self.n = deque(), 0

    def push(self, b):
        self.q.append(b)
        self.n += len(b)
        while self.q and self.n - len(self.q[0]) >= self.max:
            self.n -= len(self.q.popleft())

    def dump(self):
        return b"".join(self.q)


def alarms_in_window(alarms, lo, hi, seen):
    """4. Alarmes CONFLIT / INTERMOD / ABSENT nouvelles (clé pas dans `seen`) dont la fréquence tombe dans [lo, hi]
    MHz. -> liste d'alarmes."""
    out = []
    for a in alarms:
        if a.get("kind") in ("CONFLIT", "INTERMOD", "ABSENT") and a.get("key") not in seen and a.get("freq") \
                and lo <= float(a["freq"]) <= hi:
            out.append(a)
    return out


# ------------------------------------------------------------------ V8 étape 9 : moniteur multicanal SDR (lot A)
# Clément : « monitoring multicanal, waterfall par micro, analyse audio, historique, dérive, largeur, canaux adjacents,
# gestionnaire de ressources, performances ». Toutes les fréquences de la fenêtre : niveaux par la FFT (léger) ;
# les micros prioritaires : « récepteurs virtuels » (démodulation complète : audio, déviation, dérive).
# Seuils = valeurs de départ (choix de Claude), PAS mesurées sur de vrais micros.
AUDIO_SILENCE_DB = -50.0     # son plus bas que ça = silence
AUDIO_PRESENT_DB = -35.0     # son plus haut que ça = quelqu'un parle / joue
AUDIO_CLIP = 0.97            # échantillon au-delà = saturation (pleine échelle ≈ 1)
ADJ_WARN_DB = 20.0           # voisin à moins de 20 dB sous le canal = à surveiller
VRX_MAX = 8                  # récepteurs virtuels au plus (charge du PC)
AUDIO_NOISY_DB = -45.0       # 17. le son « entre les mots » plus fort que ça = souffle
AUDIO_CHOPS = 8              # 17. passages son <-> rien en 10 s (RF bonne) = son haché
AUDIO_DYN_DB = 15.0          # 17. écart entre le son et les pauses : en dessous, son continu (musique, tonalité)
WIDE_RATIO = 1.3             # 11. largeur occupée 30 % au-dessus de la largeur attendue = débordement
ADJ_RISE_DB = 10.0           # 12. canal voisin 10 dB au-dessus de sa médiane des 5 dernières minutes


def expected_obw_khz(mode="wfm"):
    """11. Largeur attendue d'un micro (Carson : 2 × (déviation + 15 kHz de son) en FM ; 200 kHz sinon)."""
    m = LISTEN_MODES.get(mode or "wfm") or {}
    if "fm" in (mode or "wfm") and m.get("dev"):
        return round(2.0 * (m["dev"] / 1000.0 + 15.0), 1)
    return CHANNEL_KHZ


class AudioMeter:
    """4. / 17. Analyse audio d'un canal démodulé, par blocs : RMS, crête (dBFS), part d'échantillons saturés,
    silence en cours (s), coupures (son présent qui disparaît d'un coup alors que la RF est là)."""

    def __init__(self):
        self.silent_s, self.was_on, self.cuts, self.t_last = 0.0, False, deque(maxlen=50), None
        self.rms_db = self.peak_db = -120.0
        self.clip = 0.0
        self.rec, self.flips = deque(maxlen=200), deque(maxlen=60)      # 17. 10 s de blocs, passages son <-> rien

    def feed(self, a, dt, rf_ok=True, t=None):
        a = np.asarray(a, dtype=np.float32)
        if not len(a):
            return self.state()
        m = a.mean(axis=1) if a.ndim == 2 else a
        rms = float(np.sqrt(np.mean(m ** 2)))
        pk = float(np.max(np.abs(a)))
        self.rms_db = 20.0 * math.log10(rms + 1e-9)
        self.peak_db = 20.0 * math.log10(pk + 1e-9)
        self.clip = float(np.mean(np.abs(a) >= AUDIO_CLIP))
        on = self.rms_db > AUDIO_PRESENT_DB
        if self.rms_db < AUDIO_SILENCE_DB:
            if self.was_on and rf_ok and self.silent_s == 0.0:
                self.cuts.append(t if t is not None else 0.0)       # coupure franche (son -> rien, RF présente)
            self.silent_s += float(dt)
        else:
            self.silent_s = 0.0
        prev = self.was_on
        self.was_on = on or (self.was_on and self.rms_db >= AUDIO_SILENCE_DB)
        tt = t if t is not None else (self.rec[-1][0] + dt if self.rec else 0.0)
        if rf_ok:
            self.rec.append((tt, self.rms_db))
            if prev != self.was_on:
                self.flips.append(tt)
        return self.state()

    def state(self):
        tt = self.rec[-1][0] if self.rec else 0.0
        r = [v for t_, v in self.rec if tt - t_ <= 10.0]
        floor = round(float(np.percentile(r, 10)), 1) if len(r) >= 40 else None    # le son entre les mots
        dyn = round(float(np.percentile(r, 90)) - floor, 1) if floor is not None else None   # il y a des pauses ?
        chops = sum(1 for t_ in self.flips if tt - t_ <= 10.0)
        return dict(rms=round(self.rms_db, 1), peak=round(self.peak_db, 1), clip=round(self.clip, 4),
                    silent=round(self.silent_s, 1), cuts=len(self.cuts), afloor=floor, adyn=dyn, chops=chops)


def adjacent_db(F, L, f0, chan_khz=200.0):
    """12. Canaux adjacents : (niveau dans le canal, voisin bas, voisin haut) en dB, max dans ± chan/2 et dans les
    tranches [chan/2, 1,5 × chan] de chaque côté. None si pas mesuré."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    h = chan_khz / 2000.0
    d = F - f0

    def mx(sel):
        return float(np.max(L[sel])) if sel.any() else None
    return mx(np.abs(d) <= h), mx((d < -h) & (d >= -3 * h)), mx((d > h) & (d <= 3 * h))


def rf_audio_diag(m, tr=None):
    """5. Diagnostic RF + audio d'un micro (mesures d'un récepteur virtuel). m = dict(snr, rms, clip, silent, cuts,
    dev, nominal, drift, adj_margin, rf_drops, keep_on) -> [(code, ton ok|warn|bad, phrase)], le plus grave d'abord."""
    tr = tr or (lambda x: x)
    out = []
    snr = m.get("snr")
    if snr is not None and snr < 6:
        out.append(("rf_low", "bad", tr("RF trop faible : risque de décrochage (antenne, distance, pile ?).")))
    if (m.get("rf_drops") or 0) >= 2:
        out.append(("rf_drops", "bad", tr("Décrochages RF répétés : antenne masquée, trop loin, ou brouillage.")))
    if snr is not None and snr >= 10 and (m.get("silent") or 0) >= 5 and m.get("rms") is not None:
        out.append(("mute", "warn", tr("Porteuse là mais pas de son : micro coupé (mute) ou pack sans audio.")))
    if (m.get("cuts") or 0) >= 2 and snr is not None and snr >= 10:
        out.append(("cuts", "warn", tr("Coupures de son alors que la RF est bonne : câble, capsule, bouton mute ?")))
    nom = m.get("nominal") or 0
    if (m.get("clip") or 0) > 0.005 or (nom and (m.get("dev") or 0) > 1.25 * nom):
        out.append(("hot", "warn", tr("Son saturé : gain du pack trop fort (ou chanteur très près).")))
    if m.get("drift") is not None and abs(m["drift"]) > 5:
        out.append(("drift", "warn" if abs(m["drift"]) <= 15 else "bad",
                    tr("Fréquence qui dérive ({} kHz) : pack froid, quartz, mauvais réglage.").format(
                        f"{m['drift']:+.1f}")))
    if m.get("adj_margin") is not None and m["adj_margin"] < ADJ_WARN_DB:
        out.append(("adj", "warn", tr("Signal fort dans le canal voisin ({} dB sous le canal) : désensibilisation, "
                                      "intermod.").format(f"{m['adj_margin']:.0f}")))
    if m.get("afloor") is not None and m["afloor"] > AUDIO_NOISY_DB and snr is not None and snr >= 10 \
            and (m.get("adyn") or 0) >= AUDIO_DYN_DB:        # seulement s'il y a des pauses (pas une musique continue)
        out.append(("noisy", "warn", tr("Souffle dans le son ({} dBFS entre les mots) : réglage du compander, pack "
                                        "fatigué, ou RF juste.").format(f"{m['afloor']:.0f}")))
    if (m.get("chops") or 0) >= AUDIO_CHOPS and snr is not None and snr >= 10:
        out.append(("chop", "warn", tr("Son haché ({} coupures en 10 s) : contact, câble de capsule, squelch trop "
                                       "haut ?").format(m["chops"])))
    if m.get("obw") is not None and m.get("obw_exp") and m["obw"] > WIDE_RATIO * m["obw_exp"]:
        out.append(("wide", "warn", tr("Signal plus large que prévu ({} kHz au lieu de {}) : déviation trop forte, "
                                       "pack déréglé, ou deux émetteurs l'un sur l'autre.").format(
                                           f"{m['obw']:.0f}", f"{m['obw_exp']:.0f}")))
    for a_ in m.get("rx_alerts") or []:
        out.append(("rx", "warn", a_))
    if not out:
        out.append(("ok", "ok", tr("RAS")))
    rank = {"bad": 0, "warn": 1, "ok": 2}
    return sorted(out, key=lambda x: rank[x[1]])


def diag_short(txt, n=34):
    """Phrase de diagnostic -> sa première partie (avant « : » ou « ( »), pour une colonne étroite ; la phrase entière
    reste en bulle et sous le tableau."""
    t = re.split(r"\s*(?::\s|\()", str(txt), maxsplit=1)[0].strip()
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def plan_vrx(items, n_max, turn=0):
    """16. Gestionnaire de ressources : quels micros ont un récepteur virtuel (démodulation complète) ? items =
    [dict(key, alarm, prio, keep_on, selected)] -> clés retenues : celui qu'on écoute, puis alarmes, puis priorité
    (critique d'abord), puis émetteurs « doit émettre » ; le reste tourne (turn) sur les places libres."""
    n_max = max(1, int(n_max))
    fixed = sorted((it for it in items if it.get("selected") or it.get("alarm")),
                   key=lambda it: (not it.get("selected"), -int(it.get("prio") or 1)))
    out = [it["key"] for it in fixed][:n_max]
    rest = [it for it in items if it["key"] not in out]
    rest.sort(key=lambda it: (-int(it.get("prio") or 1), not it.get("keep_on")))
    crit = [it["key"] for it in rest if int(it.get("prio") or 1) >= 2]
    for k in crit:
        if len(out) < n_max:
            out.append(k)
    others = [it["key"] for it in rest if it["key"] not in out]
    if others and len(out) < n_max:
        k0 = turn % len(others)
        rot = others[k0:] + others[:k0]
        out += rot[:n_max - len(out)]
    return out


class MicHistory:
    """6. Historique d'un micro : un point par seconde au plus (t, et les mesures du moment), une heure max."""

    def __init__(self, maxlen=3600):
        self.pts = deque(maxlen=maxlen)

    def add(self, t, **v):
        if self.pts and t - self.pts[-1][0] < 0.95:
            return False
        self.pts.append((float(t), dict(v)))
        return True

    def series(self, key, since=None):
        rows = [(t, v.get(key)) for t, v in self.pts if v.get(key) is not None and (since is None or t >= since)]
        if not rows:
            return np.zeros(0), np.zeros(0)
        return np.array([r[0] for r in rows]), np.array([r[1] for r in rows], dtype=float)

    def drift_stats(self, minutes=10.0):
        """7. Dérive : moyenne et écart-type de la fréquence observée (kHz) sur les dernières minutes."""
        t, v = self.series("drift", (self.pts[-1][0] - minutes * 60.0) if self.pts else None)
        if len(v) < 3:
            return None
        return dict(mean=round(float(np.mean(v)), 2), std=round(float(np.std(v)), 2),
                    span=round(float(np.max(v) - np.min(v)), 2))


def perf_view(expected, got, load, lag_s=0.0):
    """19. Performances du SDR : échantillons perdus (%), charge du calcul (1 = le PC ne suit plus), retard (s).
    -> (texte, ton)."""
    lost = 0.0 if expected <= 0 else max(0.0, 1.0 - float(got) / float(expected)) * 100.0
    tone = "bad" if (lost > 5 or load > 0.95 or lag_s > 2) else ("warn" if (lost > 1 or load > 0.7 or lag_s > 0.5)
                                                                 else "ok")
    return f"pertes {lost:.1f} % · charge {load * 100:.0f} % · retard {lag_s:.1f} s", tone


# ------------------------------------------------------------------ V8 étape 10 : incidents (lot B)
# 3. tampon IQ circulaire · 8. perturbations repérées toutes seules · 18. rapport d'incident · 9. relecture.
# Quand quelque chose arrive sur un micro (alarme, décrochage, bruit qui monte…), le moniteur multicanal garde l'IQ
# des secondes AVANT (tampon) et APRÈS, ses mesures et un rapport : un « dossier d'incident » qu'on peut rejouer.
# Seuils = valeurs de départ (choix de Claude), PAS mesurées sur de vrais micros.
IQ_RING_S = 20.0                 # secondes d'IQ gardées en mémoire (avant l'incident)
IQ_RING_BUDGET = 256 * 2 ** 20   # … au plus 256 Mo de mémoire
INC_POST_S = 10.0                # secondes gardées APRÈS le déclenchement
INC_COOLDOWN_S = 60.0            # un même type d'anomalie sur un même micro : une fois par minute au plus
INC_GAP_S = 120.0                # dossiers automatiques : un toutes les 2 min au plus (place disque)
INC_MAX_MB = 2048                # dossier « incidents » : les plus anciens effacés au-delà de 2 Go
ANOM_DROP_DB = 15.0              # décrochage : RF 15 dB sous sa médiane des 30 dernières secondes
ANOM_NOISE_DB = 8.0              # bruit qui monte : 8 dB au-dessus de sa médiane des 5 dernières minutes
ANOM_FLAPS = 3                   # décrochages répétés : 3 en 10 minutes
ANOM_FLAP_S = 600.0
ANOM_APPEAR_DB = 10.0            # « doit rester libre » / sans statut : un signal 10 dB au-dessus du bruit
ANOM_LABELS = {
    "drop": "Décrochage RF", "flaps": "Décrochages répétés", "noise": "Bruit qui monte",
    "adj": "Voisin trop fort", "appear": "Signal sur la fréquence", "diag": "Diagnostic RF + son",
    "burst": "Signal bref inconnu", "alarm": "Alarme", "manual": "Incident noté à la main",
    "wide": "Signal plus large que prévu", "adj_rise": "Le canal voisin monte", "rx": "Alerte du récepteur",
}
INC_AUTO_KINDS = ("drop", "flaps", "noise", "adj", "appear", "diag", "alarm", "wide", "adj_rise")   # ceux qui ouvrent un dossier


def iq_ring_seconds(bytes_per_s, keep_s=IQ_RING_S, budget=IQ_RING_BUDGET):
    """3. Secondes d'IQ que le tampon peut garder : `keep_s`, ou moins si le débit dépasse le budget mémoire."""
    return max(1.0, min(float(keep_s), float(budget) / max(1.0, float(bytes_per_s))))


class AnomalyTracker:
    """8. Perturbations d'UN micro, repérées dans ses mesures (2 par seconde). keep_on=True (micro, ou sans statut) :
    décrochage seulement s'il y avait une porteuse ; False (« doit rester libre ») : un signal qui arrive = anomalie.
    Décrochage (RF qui s'effondre),
    décrochages répétés, bruit qui monte, voisin qui se rapproche, signal sur une fréquence qui doit rester libre,
    diagnostic qui passe au rouge. feed(t, …) -> [{kind, t, value}] (chaque type : une fois par INC_COOLDOWN_S)."""

    def __init__(self, keep_on=True):
        self.keep_on = bool(keep_on)
        self.rf, self.nz = deque(maxlen=60), deque(maxlen=600)    # 30 s / 5 min à 2 mesures par seconde
        self.drops, self.last = deque(maxlen=20), {}
        self.in_drop = self.adj_bad = self.on = False
        self.ref = 0.0
        self.wide_n, self.adjl = 0, deque(maxlen=600)             # 11. / 12.
        self.bad = None

    def _emit(self, out, kind, t, value=None):
        if t - self.last.get(kind, -1e18) >= INC_COOLDOWN_S:
            self.last[kind] = t
            out.append(dict(kind=kind, t=float(t), value=value))

    def feed(self, t, rf=None, noise=None, adj_margin=None, bad=None, obw=None, obw_exp=None, adj_lvl=None):
        out = []
        if obw is not None and obw_exp:                              # 11. débordement (3 mesures de suite)
            self.wide_n = self.wide_n + 1 if obw > WIDE_RATIO * obw_exp else 0
            if self.wide_n == 3:
                self._emit(out, "wide", t, round(float(obw), 0))
        if adj_lvl is not None:                                      # 12. un voisin qui monte
            al = [v for t_, v in self.adjl if t - t_ <= 300.0]
            if len(al) >= 20 and adj_lvl - float(np.median(al)) >= ADJ_RISE_DB:
                self._emit(out, "adj_rise", t, round(adj_lvl - float(np.median(al)), 1))
            else:
                self.adjl.append((float(t), float(adj_lvl)))
        rs = [v for t_, v in self.rf if t - t_ <= 30.0]
        nzs = [v for t_, v in self.nz if t - t_ <= 300.0]
        med_nz = float(np.median(nzs)) if len(nzs) >= 20 else None
        if rf is not None and noise is not None:
            if self.keep_on:
                if self.in_drop:                      # sortie du décrochage : retour près du niveau d'avant
                    if self.ref - rf < ANOM_DROP_DB / 2.0:
                        self.in_drop = False
                elif len(rs) >= 10:
                    med = float(np.median(rs))
                    carrier = med_nz is None or med - med_nz >= 10.0
                    if carrier and med - rf >= ANOM_DROP_DB:
                        self.in_drop, self.ref = True, med
                        self.drops.append(t)
                        self._emit(out, "drop", t, round(med - rf, 1))
                        if sum(1 for x in self.drops if t - x <= ANOM_FLAP_S) >= ANOM_FLAPS:
                            self._emit(out, "flaps", t, sum(1 for x in self.drops if t - x <= ANOM_FLAP_S))
            else:
                on = rf - noise >= ANOM_APPEAR_DB
                if on and not self.on:
                    self._emit(out, "appear", t, round(rf - noise, 1))
                self.on = on
            if not self.in_drop:
                self.rf.append((float(t), float(rf)))
        if noise is not None:
            recent = [v for t_, v in self.nz if t - t_ <= 5.0] + [float(noise)]
            if med_nz is not None and float(np.median(recent)) - med_nz >= ANOM_NOISE_DB:
                self._emit(out, "noise", t, round(float(np.median(recent)) - med_nz, 1))
            else:
                self.nz.append((float(t), float(noise)))         # le bruit « normal » ne suit pas la montée
        if adj_margin is not None:
            b = adj_margin < ADJ_WARN_DB
            if b and not self.adj_bad:
                self._emit(out, "adj", t, round(float(adj_margin), 1))
            self.adj_bad = b
        if bad and bad != self.bad:
            self._emit(out, "diag", t, bad)
        self.bad = bad or None
        return out


def anomaly_text(ev, tr=None):
    """Événement -> phrase (« Décrochage RF : −18 dB »)."""
    tr = tr or (lambda x: x)
    k, v = ev.get("kind"), ev.get("value")
    base = tr(ANOM_LABELS.get(k, str(k)))
    if v is None or v == "":
        return base
    if k in ("drop", "noise", "adj_rise"):
        return f"{base} : {'-' if k == 'drop' else '+'}{abs(float(v)):.0f} dB"
    if k == "wide":
        return base + f" : {float(v):.0f} kHz"
    if k == "flaps":
        return base + tr(" : {} en 10 min").format(int(v))
    if k in ("adj", "appear"):
        return base + tr(" : {} dB").format(f"{round(float(v)):.0f}")
    if k == "burst":
        return base + f" : {v}"
    return f"{base} : {tr(str(v))}"


def unknown_bursts(events, chan_freqs, tol=0.15):
    """8. Signaux brefs du détecteur qui ne tombent sur AUCUN micro (à ± tol MHz) : ce sont les inconnus."""
    fs = [float(f) for f in chan_freqs]
    return [ev for ev in events if all(abs(float(ev["f"]) - f) > tol for f in fs)]


def incident_slug(name):
    """Nom de micro -> morceau de nom de dossier (lettres, chiffres, tirets)."""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")
    return (s or "micro")[:30]


def incident_prune(entries, max_bytes):
    """Dossiers d'incident [(chemin, date, taille)] -> chemins à effacer (les plus anciens) pour tenir dans max_bytes."""
    tot = sum(int(x[2]) for x in entries)
    out = []
    for p, _t, n in sorted(entries, key=lambda x: x[1]):
        if tot <= max_bytes:
            break
        out.append(p)
        tot -= int(n)
    return out


# ------------------------------------------------------------------ V8 étape 11 : répétition, comparaison, récepteurs (lot C)
# 20. Mode répétition / spectacle : pendant la répétition, le moniteur APPREND ce qui est normal pour chaque micro
# (niveau, écart au bruit, bruit, son) ; pendant le spectacle, il prévient quand un micro s'en écarte.
# 10. Comparaison des récepteurs : SDR, tinySA et récepteurs Shure mesurent le même micro -> décalage, décrochages
# vus par un seul (antenne, placement). 14. / 15. Télémétrie Shure (ULX-D, QLX-D, SLX-D, Axient Digital) : protocole
# texte TCP port 2202 (« < GET 1 RX_RF_LVL > »), écrit de mémoire d'après la doc publique de Shure : PAS essayé sur un
# vrai récepteur (formats SAMPLE en particulier).
REH_MIN_N = 60                   # mesures mini (≈ 30 s) pour qu'un micro soit « appris »
REH_SNR_DB = 10.0                # spectacle : écart au bruit 10 dB sous le plus faible de la répétition
REH_NOISE_DB = 6.0               # … bruit 6 dB au-dessus de celui de la répétition
REH_AUDIO_DB = 6.0               # … son 6 dB au-dessus du plus fort de la répétition
SDR_MODES = (("watch", "Surveillance"), ("learn", "🎭 Apprendre la phase"), ("show", "🎤 Comparer à la phase"))


class RehearsalProfile:
    """20. Ce qui est normal pour chaque micro, appris pendant la répétition. learn(row) avec les lignes du moniteur ;
    summary() -> {clé: {name, freq, n, snr_p10, snr_med, noise_med, rf_med, audio_p50, audio_p95}}."""

    def __init__(self):
        self.d = {}

    def learn(self, row):
        k = row.get("key")
        if k is None:
            return
        e = self.d.setdefault(k, dict(name=row.get("name", ""), freq=row.get("freq"), snr=deque(maxlen=7200),
                                      noise=deque(maxlen=7200), rf=deque(maxlen=7200), audio=deque(maxlen=7200)))
        for f in ("snr", "noise", "rf"):
            if row.get(f) is not None:
                e[f].append(float(row[f]))
        if row.get("rms") is not None and row.get("rms") > AUDIO_SILENCE_DB:      # le son quand quelqu'un parle
            e["audio"].append(float(row["rms"]))

    def summary(self):
        out = {}
        for k, e in self.d.items():
            if len(e["snr"]) < REH_MIN_N:
                continue

            def pc(v, q):
                return round(float(np.percentile(np.array(v), q)), 1) if len(v) else None
            out[k] = dict(name=e["name"], freq=e["freq"], n=len(e["snr"]), snr_p10=pc(e["snr"], 10),
                          snr_med=pc(e["snr"], 50), noise_med=pc(e["noise"], 50), rf_med=pc(e["rf"], 50),
                          audio_p50=pc(e["audio"], 50), audio_p95=pc(e["audio"], 95))
        return out


def rehearsal_norm(d):
    """Profil de répétition lu de la config -> {t, name, mics: {clé int: résumé}} (ou None)."""
    if not isinstance(d, dict) or not isinstance(d.get("mics"), dict):
        return None
    mics = {}
    for k, v in d["mics"].items():
        try:
            k = int(k)
        except (TypeError, ValueError):
            continue
        if isinstance(v, dict):
            mics[k] = {f: (None if v.get(f) is None else float(v[f])) if f not in ("name",) else str(v.get(f, ""))[:60]
                       for f in ("name", "freq", "n", "snr_p10", "snr_med", "noise_med", "rf_med", "audio_p50", "audio_p95")}
    return dict(t=float(d.get("t") or 0.0), name=str(d.get("name", ""))[:60], mics=mics) if mics else None


def rehearsal_check(ref, row, tr=None):
    """20. Spectacle : écarts d'un micro à sa répétition -> [(code, ton, phrase)] (vide = comme en répétition)."""
    tr = tr or (lambda x: x)
    if not ref:
        return []
    out = []
    if ref.get("snr_p10") is not None and row.get("snr") is not None and row["snr"] < ref["snr_p10"] - REH_SNR_DB:
        out.append(("reh_rf", "bad", tr("RF bien plus faible qu'en répétition ({} dB)").format(
            f"{row['snr'] - ref['snr_p10']:+.0f}")))
    if ref.get("noise_med") is not None and row.get("noise") is not None and row["noise"] > ref["noise_med"] + REH_NOISE_DB:
        out.append(("reh_noise", "warn", tr("Bruit plus haut qu'en répétition ({} dB)").format(
            f"{row['noise'] - ref['noise_med']:+.0f}")))
    if ref.get("audio_p95") is not None and row.get("rms") is not None and row["rms"] > ref["audio_p95"] + REH_AUDIO_DB:
        out.append(("reh_audio", "warn", tr("Son plus fort qu'en répétition ({} dB)").format(
            f"{row['rms'] - ref['audio_p95']:+.0f}")))
    return out


def compare_receivers(a, b, tol_s=1.5, drop_db=15.0):
    """10. Deux séries de niveaux d'un même micro [(t, dB)] (ex. SDR et tinySA, ou antenne A / B d'un récepteur) ->
    {n, offset (médiane b − a), spread (écart-type), corr, only_a, only_b} ; only_x = décrochages (niveau 15 dB sous sa
    médiane) vus par x alors que l'autre allait bien (antenne masquée, mauvais placement). None si < 10 paires."""
    a = sorted((float(t), float(v)) for t, v in a if v is not None)
    b = sorted((float(t), float(v)) for t, v in b if v is not None)
    if len(a) < 10 or len(b) < 10:
        return None
    tb = np.array([t for t, _ in b])
    vb = np.array([v for _, v in b])
    pa, pb = [], []
    for t, v in a:
        i = int(np.argmin(np.abs(tb - t)))
        if abs(tb[i] - t) <= tol_s:
            pa.append(v)
            pb.append(vb[i])
    if len(pa) < 10:
        return None
    pa, pb = np.array(pa), np.array(pb)
    ma, mb = float(np.median(pa)), float(np.median(pb))
    da, db = pa < ma - drop_db, pb < mb - drop_db
    d = pb - pa
    corr = float(np.corrcoef(pa, pb)[0, 1]) if np.std(pa) > 0 and np.std(pb) > 0 else None
    return dict(n=len(pa), offset=round(float(np.median(d)), 1), spread=round(float(np.std(d)), 1),
                corr=None if corr is None else round(corr, 2), only_a=int(np.sum(da & ~db)), only_b=int(np.sum(db & ~da)),
                std_a=round(float(np.std(pa)), 1), std_b=round(float(np.std(pb)), 1))


def compare_text(c, na, nb, tr=None):
    """Résultat de compare_receivers -> phrase."""
    tr = tr or (lambda x: x)
    if not c:
        return tr("{} / {} : pas assez de mesures communes").format(na, nb)
    s = tr("{} / {} : décalage {} dB (± {})").format(na, nb, f"{c['offset']:+.1f}", f"{c['spread']:.1f}")
    if c["only_a"] or c["only_b"]:
        s += tr(" · décrochages vus seulement par {} : {}, seulement par {} : {}").format(na, c["only_a"], nb, c["only_b"])
    if c.get("std_a") is not None:
        s += tr(" · stabilité ± {} / ± {} dB").format(f"{c['std_a']:.1f}", f"{c['std_b']:.1f}")
    return s


SHURE_PORT = 2202


def shure_split(buf):
    """Flux texte d'un récepteur Shure -> (messages « < … > » complets, reste)."""
    out = []
    while True:
        i = buf.find("<")
        j = buf.find(">", i + 1) if i >= 0 else -1
        if i < 0 or j < 0:
            return out, (buf[i:] if i >= 0 else "")
        out.append(buf[i + 1:j].strip())
        buf = buf[j + 1:]


def shure_parse(msg):
    """« REP 1 RX_RF_LVL 095 » / « REP 1 CHAN_NAME {Chant  } » / « SAMPLE 1 ALL AX 095 040 » -> dict(type, ch, key,
    val (texte), args (liste)) ou None. Canal 0 = tout l'appareil."""
    m = re.match(r"(REP|SAMPLE|REPORT)\s+(?:(\d+)\s+)?(\w+)\s*(.*)$", str(msg).strip())
    if not m:
        return None
    rest = m.group(4).strip()
    br = re.match(r"\{(.*)\}", rest)
    val = br.group(1).strip() if br else rest
    return dict(type=m.group(1), ch=int(m.group(2) or 0), key=m.group(3).upper(), val=val,
                args=[] if br else rest.split())


def shure_apply(state, msg):
    """Met à jour {canal: {name, freq MHz, rf dBm, ant, audio dBFS, batt barres, tx}} avec un message. Échelles (doc Shure,
    de mémoire) : RX_RF_LVL 000–115 = valeur − 128 dBm, AUDIO_LVL 000–050 = valeur − 50 dBFS, FREQUENCY = kHz × 1000 sur
    6–7 chiffres, TX_BATT_BARS 0–5 (255 = inconnu). -> True si quelque chose a changé."""
    p = shure_parse(msg) if isinstance(msg, str) else msg
    if not p or p["ch"] <= 0:
        return False
    st = state.setdefault(p["ch"], {})
    k, v, a = p["key"], p["val"], p["args"]

    def num(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return None
    if k == "CHAN_NAME":
        st["name"] = v
    elif k == "FREQUENCY" and num(v) is not None:
        st["freq"] = num(v) / 1000.0
    elif k in ("RX_RF_LVL", "RF_LVL") and num(v) is not None:
        st["rf"] = num(v) - 128
    elif k == "AUDIO_LVL" and num(v) is not None:
        st["audio"] = num(v) - 50
    elif k == "RF_ANTENNA":
        st["ant"] = v
    elif k == "TX_BATT_BARS" and num(v) is not None:
        st["batt"] = None if num(v) == 255 else num(v)
    elif k == "TX_TYPE":
        st["tx"] = None if v in ("UNKN", "UNKNOWN") else v
    elif re.search(r"ALARM|WARN|FAULT|ERROR|INTERFERENCE|RF_INT_DET", k):        # 14. alertes matérielles
        al = st.setdefault("alarms", {})
        if v in ("", "OFF", "NONE", "0", "000", "CLEAR", "OK"):
            al.pop(k, None)
        else:
            al[k] = v
    elif k == "ALL" and p["type"] == "SAMPLE" and a:
        if re.fullmatch(r"[AX][BX]", a[0]):
            st["ant"] = a[0]
            nums = [num(x) for x in a[1:]]
            if len(nums) >= 1 and nums[0] is not None:
                st["rf"] = nums[0] - 128
            if len(nums) >= 2 and nums[-1] is not None:
                st["audio"] = nums[-1] - 50
    else:
        return False
    return True


def shure_init(n_ch=4, rate_ms=1000):
    """Commandes envoyées à la connexion : tout lire, puis des mesures toutes les `rate_ms` ms par canal."""
    out = ["< GET 0 ALL >"]
    for c in range(1, n_ch + 1):
        out.append(f"< SET {c} METER_RATE {int(rate_ms):05d} >")
    return out


class DiversityAB:
    """15. Diversity A / B d'un canal de récepteur : part du temps sur chaque antenne, bascules, secondes sans aucune."""

    def __init__(self):
        self.n = {"A": 0, "B": 0, "-": 0}
        self.prev, self.switches = None, 0
        self.losses, self._lost = deque(maxlen=50), None            # 15. pertes de diversité [(début, fin)]

    def feed(self, ant, t=None):
        s = "A" if ant and ant[0] == "A" else ("B" if ant and ant[-1] == "B" else "-")
        self.n[s] += 1
        if s == "-" and self._lost is None:
            self._lost = t
        elif s != "-" and self._lost is not None:
            self.losses.append((self._lost, t))
            self._lost = None
        if s in "AB" and self.prev in ("A", "B") and s != self.prev:
            self.switches += 1
        if s != "-":
            self.prev = s
        return s

    def text(self, tr=None):
        tr = tr or (lambda x: x)
        tot = sum(self.n.values())
        if not tot:
            return "—"
        s = f"A {100 * self.n['A'] / tot:.0f} % · B {100 * self.n['B'] / tot:.0f} % · " + tr("{} bascules").format(self.switches)
        if self.n["-"]:
            s += " · " + tr("aucune : {} %").format(f"{100 * self.n['-'] / tot:.0f}")
        return s

    def dead(self, min_n=300, share=0.05):
        """15. Antenne quasi jamais utilisée (« A » ou « B ») sur au moins min_n mesures : câble, antenne, booster ?"""
        tot = self.n["A"] + self.n["B"]
        if tot < min_n:
            return None
        for a in ("A", "B"):
            if self.n[a] / tot < share:
                return a
        return None


def receiver_alerts(st, div=None, tr=None):
    """14. / 15. Ce qui ne va pas sur un canal de récepteur -> [phrase]."""
    tr = tr or (lambda x: x)
    out = []
    if st.get("batt") is not None and st["batt"] <= 1:
        out.append(tr("Pile du micro presque vide ({} barre)").format(st["batt"]))
    for k, v in sorted((st.get("alarms") or {}).items()):
        out.append(tr("Le récepteur signale : {} {}").format(k, v))
    if div is not None:
        d = div.dead()
        if d:
            out.append(tr("Antenne {} presque jamais utilisée : câble, antenne ou booster à vérifier").format(d))
        n = sum(1 for a, b in div.losses if a is not None and b is not None and b - a >= 1.0)
        if n >= 3:
            out.append(tr("{} pertes de diversité (aucune antenne) : micro hors de portée ?").format(n))
    return out


def shure_addrs(text):
    """« 192.168.1.50, 192.168.1.51:2202 » -> [(hôte, port)] (sans doublons)."""
    out = []
    for x in re.split(r"[\s,;]+", str(text or "")):
        if not x:
            continue
        h, _, p = x.partition(":")
        try:
            p = int(p) if p else SHURE_PORT
        except ValueError:
            continue
        if re.fullmatch(r"[A-Za-z0-9.\-]+", h) and (h, p) not in out:
            out.append((h, p))
    return out[:16]


# ------------------------------------------------------------------ V8 étape 12 : fondations (lot D)
# Son enregistré et vie privée : un enregistrement de son (ou d'IQ, qu'on peut démoduler) contient des VOIX (artistes,
# équipes, public). Rien n'est enregistré sans accord explicite, tout est effacé après `keep_days` jours.
PRIVACY_DEFAULT = dict(alarm_audio=False, keep_days=7, ack=False)
KEEP_DAYS = (1, 3, 7, 14, 30, 0)                 # 0 = tout garder
PRIVACY_TEXT = ("Ce que l'appli garde, et quand :\n"
                "• En mémoire seulement (rien sur le disque) : le son que tu écoutes, et les ~20 dernières secondes de "
                "signal brut (IQ) du moniteur. Tout disparaît à l'arrêt.\n"
                "• Sur le disque, uniquement quand :\n"
                "  – tu cliques « ⏺ Enregistrer le son » ou « Enregistrer l'IQ » (jusqu'à ce que tu arrêtes) ;\n"
                "  – une alarme part et « Sur alarme : garder le son » est coché (10 s avant + 10 s après) ;\n"
                "  – un incident du moniteur est noté (dossier : IQ d'avant et d'après, mesures, rapport).\n"
                "• Où : dans le dossier des journaux (enregistrements_audio, enregistrements_iq, incidents).\n"
                "• Contenu : des VOIX (artistes, équipes, public) — l'IQ aussi, on peut le réécouter.\n"
                "• Combien de temps : effacés tout seuls après la durée choisie (vérifié toutes les heures). L'appli "
                "efface SES fichiers ; elle ne peut rien pour les copies faites ailleurs (clé USB, sauvegarde, e-mail).\n"
                "N'enregistre que ce qui sert, ne le diffuse pas, et préviens les personnes concernées si les règles du "
                "lieu le demandent.")


def privacy_norm(d):
    """Réglages « son et vie privée » lus de la config (prudemment)."""
    d = d if isinstance(d, dict) else {}
    out = dict(PRIVACY_DEFAULT)
    out["alarm_audio"] = bool(d.get("alarm_audio", False))
    out["ack"] = bool(d.get("ack", False))
    try:
        k = int(d.get("keep_days", 7))
        out["keep_days"] = k if k in KEEP_DAYS else 7
    except (TypeError, ValueError):
        pass
    return out


def keep_text(days, tr=None):
    tr = tr or (lambda x: x)
    return tr("tout garder") if not days else (tr("1 jour") if days == 1 else tr("{} jours").format(days))


def retention_pick(entries, now, days):
    """Fichiers / dossiers [(chemin, date)] plus vieux que `days` jours -> chemins à effacer (days 0 = rien)."""
    if not days:
        return []
    lim = float(now) - float(days) * 86400.0
    return [p for p, t in entries if float(t) < lim]


# Horloge commune : chaque mesure porte l'heure où elle a été CAPTÉE (pas celle où le calcul l'a vue passer). tinySA :
# heure du balayage (sweep_t, V7 7.45) ; SDR : heure d'après le compte d'échantillons ; son : heure du bloc démodulé.
class AcqClock:
    """Heure des échantillons d'un flux IQ : ancrée sur l'heure du PC aux 1res données, puis avancée du nombre
    d'échantillons reçus / débit. Retard = heure du PC − heure des échantillons (ce que le calcul a de retard, plus les
    échantillons perdus en route) ; au-delà de RESYNC_S, recalage (compté : des échantillons ont été perdus)."""
    RESYNC_S = 2.0

    def __init__(self, rate):
        self.rate, self.t0, self.n, self.resyncs, self.lag = float(rate), None, 0, 0, 0.0

    def feed(self, n_samples, now):
        """Un bloc de n échantillons vient d'arriver à `now` -> heure de la FIN du bloc (heure de capture)."""
        if self.t0 is None:
            self.t0 = float(now) - n_samples / self.rate
        self.n += int(n_samples)
        t = self.t0 + self.n / self.rate
        self.lag = float(now) - t
        if self.lag > self.RESYNC_S or self.lag < -0.5:
            self.t0 = float(now) - self.n / self.rate
            self.resyncs += 1
            self.lag, t = 0.0, float(now)
        return t


_OVR = re.compile(r"overflow|overrun|underrun|dropped|lost samples|samples lost|\bO{2,}\b|^O+$", re.I)


def count_overruns(lines):
    """19. Lignes d'erreur d'un outil SDR (hackrf_transfer, rtl_sdr, rx_sdr…) qui signalent des échantillons perdus."""
    return sum(1 for x in lines if _OVR.search(str(x).strip()))


# Capacité : ce que le SDR COUVRE (fenêtre utile) et ce que le PC peut DÉMODULER (charge mesurée).
VRX_BUDGET = 0.6                 # part du temps de calcul qu'on s'autorise (le reste : affichage, autres fenêtres)


def vrx_auto(base_load, cost_vrx, n_max=VRX_MAX, budget=VRX_BUDGET):
    """16. Récepteurs virtuels possibles : (budget − charge de la FFT) / coût d'un récepteur (part du temps réel par
    récepteur, mesurée). Au moins 1, au plus n_max ; coût inconnu -> 4."""
    if not cost_vrx or cost_vrx <= 0:
        return min(4, n_max)
    return int(max(1, min(n_max, math.floor((budget - max(0.0, base_load)) / cost_vrx))))


def capacity_view(n_asked, n_in, n_vrx, n_crit, tr=None, planned=False):
    """16. Phrase honnête sur ce qui est vraiment surveillé : -> (texte, ton). n_asked = fréquences de la liste dans la
    plage du SDR, n_in = dans la fenêtre, n_vrx = démodulées en continu, n_crit = critiques qui n'ont pas de récepteur."""
    tr = tr or (lambda x: x)
    out_ = max(0, n_asked - n_in)
    rot = max(0, n_in - n_vrx)
    s = tr("{} fréquences dans la fenêtre : niveau, voisins et largeur de toutes").format(n_in)
    if planned:                                   # avant ▶ : on ne sait pas encore ce que le PC tiendra
        s += tr(" · son démodulé pour le plus possible (selon le PC), les autres à tour de rôle")
        if out_:
            s += tr(" · {} HORS de la fenêtre : pas surveillées par ce SDR").format(out_)
        return s, ("warn" if out_ else "ok")
    s += tr(" · {} démodulées en continu").format(min(n_vrx, n_in))
    if rot:
        s += tr(" · {} à tour de rôle (toutes les 5 s)").format(rot)
    if out_:
        s += tr(" · {} HORS de la fenêtre : pas surveillées par ce SDR").format(out_)
    if n_crit:
        s += tr(" · ⚠ {} critique(s) sans récepteur : le PC ne suit pas, baisse le nombre de micros ou ferme d'autres "
                "fenêtres").format(n_crit)
        return s, "bad"
    return s, ("warn" if out_ else "ok")


def device_caps(kind, model=None):
    """Fiche commune de ce que sait faire un appareil : {name, sweep, iq, span (MHz utiles d'un coup), bits, enob, fmin,
    fmax, demod}. kind "" / "tinysa" = tinySA (balaye, ne démodule pas)."""
    if not kind or kind == "tinysa":
        return dict(name="tinySA", sweep=True, iq=False, span=None, bits=None, enob=None, fmin=0.1, fmax=6000.0,
                    demod=False)
    sp = SDR_KINDS.get(kind) or {}
    m = model or {}
    rate = sdr_rate(m, kind) if m else sdr_iq_rate(kind)
    iq = bool(sp.get("iq_tool")) or kind == "winradio"
    return dict(name=m.get("name") or sp.get("name", kind), sweep=bool(sp.get("tool")) or kind == "winradio", iq=iq,
                span=round(sdr_span_mhz(m, rate), 2) if iq else None, bits=m.get("bits"), enob=m.get("enob"),
                fmin=m.get("fmin", sp.get("fmin")), fmax=m.get("fmax", sp.get("fmax")), demod=iq)


def caps_text(c, tr=None):
    tr = tr or (lambda x: x)
    p = [tr("balaye") if c["sweep"] else None,
         (tr("écoute et démodule ({} MHz d'un coup)").format(f"{c['span']:g}") if c["iq"] else tr("ne démodule pas")),
         (tr("{} bits").format(c["bits"]) if c.get("bits") else None)]
    return f"{c['name']} : " + " · ".join(x for x in p if x)


def resource_view(i, tr=None):
    """19. Santé du système (onglet Système du moniteur) : i = dict(lost %, load, lag s, resyncs, overruns, vrx, vrx_want,
    ring_mb, ring_s, disk_gb, inc_mb, audio_mb, iq_mb, queue, disc, disc_why) -> [(libellé, valeur, ton)]."""
    tr = tr or (lambda x: x)

    def tone(v, w, b, hi=True):
        if v is None:
            return "none"
        return ("bad" if v >= b else "warn" if v >= w else "ok") if hi else ("bad" if v <= b else "warn" if v <= w else "ok")
    out = [
        (tr("Échantillons perdus"), "—" if i.get("lost") is None else f"{i['lost']:.1f} %", tone(i.get("lost"), 1, 5)),
        (tr("Pertes signalées par le SDR"), str(i.get("overruns", 0)), tone(i.get("overruns", 0), 1, 20)),
        (tr("Recalages d'horloge"), str(i.get("resyncs", 0)), tone(i.get("resyncs", 0), 1, 5)),
        (tr("Retard du calcul"), "—" if i.get("lag") is None else f"{i['lag']:.2f} s", tone(i.get("lag"), 0.5, 2)),
        (tr("Charge du calcul"), "—" if i.get("load") is None else f"{100 * i['load']:.0f} %", tone(i.get("load"), 0.7, 0.95)),
        (tr("Récepteurs virtuels"), f"{i.get('vrx', 0)} / {i.get('vrx_want', 0)}",
         "warn" if i.get("vrx", 0) < i.get("vrx_want", 0) else "ok"),
        (tr("Mémoire du tampon IQ"), f"{i.get('ring_mb', 0):.0f} Mo · {i.get('ring_s', 0):.0f} s", "ok"),
        (tr("File du son"), str(i.get("queue", 0)), tone(i.get("queue", 0), 50, 150)),
        (tr("Disque libre"), "—" if i.get("disk_gb") is None else f"{i['disk_gb']:.1f} Go", tone(i.get("disk_gb"), 10, 2, False)),
        (tr("Incidents gardés"), f"{i.get('inc_mb', 0):.0f} Mo", tone(i.get("inc_mb", 0), INC_MAX_MB * 0.8, INC_MAX_MB)),
        (tr("Son enregistré"), f"{i.get('audio_mb', 0):.0f} Mo", "ok"),
        (tr("IQ enregistré"), f"{i.get('iq_mb', 0):.0f} Mo", "ok"),
        (tr("Déconnexions du SDR"), str(i.get("disc", 0)) + (f" ({i['disc_why']})" if i.get("disc_why") else ""),
         tone(i.get("disc", 0), 1, 3)),
    ]
    return out


# 20. Phases du show (balance, répétition, début, exploitation…) : chaque phase apprise est gardée à part, et le
# spectacle se compare à celle qu'on choisit ; un tableau les met côte à côte.
PHASES = ("Balance", "Répétition", "Début du spectacle", "Exploitation")


def phases_norm(d, legacy=None):
    """Phases lues de la config -> {nom: {t, mics}} ; l'ancienne « rehearsal » (étape 11) devient « Répétition »."""
    out = {}
    if isinstance(d, dict):
        for k, v in list(d.items())[:20]:
            r = rehearsal_norm(v)
            if r:
                out[str(k)[:40]] = r
    lg = rehearsal_norm(legacy)
    if lg and "Répétition" not in out:
        out["Répétition"] = lg
    return out


def phases_table(phases, keys, field="snr_med"):
    """20. Tableau micros × phases : {clé: {phase: valeur}} pour le champ demandé (écart au bruit médian…)."""
    out = {}
    for k in keys:
        out[k] = {p: (v.get("mics") or {}).get(k, {}).get(field) for p, v in phases.items()}
    return out


def incident_duration(series, t, ref_s=30.0, back_db=7.5):
    """18. Durée d'un incident : du déclenchement au retour du niveau RF à moins de back_db de celui d'avant (médiane
    des ref_s secondes d'avant). series = [(t, dB)]. -> secondes, ou None (pas revenu dans ce qu'on a)."""
    before = [v for a, v in series if v is not None and t - ref_s <= a < t - 0.5]
    if len(before) < 3:
        return None
    ref = float(np.median(before))
    low = False
    for a, v in series:
        if a < t or v is None:
            continue
        if v < ref - back_db:
            low = True
        elif low or a > t + 1.0:
            return round(max(0.0, a - t), 1) if low else 0.0
    return None


def _svg_iq_spectrum(F, L, f0, w=900, h=220, half=1.0):
    """18. Capture du spectre au moment de l'incident (± half MHz autour du micro, trait rouge sur le micro)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    sel = np.abs(F - f0) <= half
    if sel.sum() < 5:
        return ""
    F, L = F[sel], L[sel]
    if len(F) > 900:
        k = int(math.ceil(len(F) / 900))
        n = len(F) // k * k
        F, L = F[:n].reshape(-1, k).mean(axis=1), L[:n].reshape(-1, k).max(axis=1)
    pts = [(float(a), float(b)) for a, b in zip(F, L)]
    s = _svg_series([("", "#0a84ff", pts)], f0, w, h, unit="dBFS")
    return s.replace(f"{(F[0] - f0):+.0f} s", f"{F[0]:.3f} MHz").replace(f"{(F[-1] - f0):+.0f} s", f"{F[-1]:.3f} MHz")


# ------------------------------------------------------------------ V8 étape 13 : récepteurs d'autres marques
# 14. Télémétrie des récepteurs, par marque. Protocoles écrits DE MÉMOIRE d'après les docs publiques / modules
# communautaires (Bitfocus Companion…) : JAMAIS essayés sur un vrai récepteur. Lecteurs volontairement tolérants.
#   shure   : texte « < GET 1 RX_RF_LVL > », TCP 2202 (ULX-D, QLX-D, SLX-D, Axient Digital).
#   g4      : Sennheiser evolution G3 / G4 / 2000 (« Push 60 100 3 » puis lignes « RF1 45 », « Bat 3 »…), UDP 53212.
#   ssc     : Sennheiser Sound Control (JSON en UDP 45 : EW-DX, Digital 6000, SpeechLine…), chemins lus en vrac.
#   wisycom, other : pas de protocole public -> rien envoyé, explication affichée.
RX_BRANDS = {
    "shure": dict(name="Shure (ULX-D, QLX-D, SLX-D, Axient Digital)", port=2202, proto="tcp"),
    "g4": dict(name="Sennheiser evolution G3 / G4 / 2000", port=53212, proto="udp"),
    "ssc": dict(name="Sennheiser EW-DX / Digital 6000 / SpeechLine (SSC)", port=45, proto="udp"),
    "wisycom": dict(name="Wisycom (MRK, MCR)", port=None, proto=None,
                    why="Wisycom n'a pas de protocole public (Wisycom Manager parle en privé avec ses récepteurs). "
                        "Pour l'ajouter : une capture réseau (Wireshark) entre Wisycom Manager et un récepteur."),
    "other": dict(name="Autre marque (Sony, Audio-Technica, Lectrosonics, Mipro…)", port=None, proto=None,
                  why="Pas de protocole réseau public connu pour cette marque. Avec une doc ou une capture réseau "
                      "(Wireshark) de son logiciel, on peut l'ajouter."),
}
RX_ALIASES = {"sennheiser": "g4", "senn": "g4", "ew": "g4", "ewdx": "ssc", "ew-dx": "ssc", "d6000": "ssc",
              "6000": "ssc", "speechline": "ssc", "wisy": "wisycom"}


def receiver_addrs(text):
    """« 192.168.1.50, g4:192.168.1.60, ssc:10.0.0.7:45 » -> [(marque, hôte, port)] ; sans préfixe = Shure."""
    out = []
    for x in re.split(r"[\s,;]+", str(text or "")):
        if not x:
            continue
        b, sep, rest = x.partition(":")
        bk = RX_ALIASES.get(b.lower(), b.lower())
        if sep and bk in RX_BRANDS:
            x = rest
        else:
            bk = "shure"
        h, _, p = x.partition(":")
        try:
            p = int(p) if p else (RX_BRANDS[bk]["port"] or 0)
        except ValueError:
            continue
        if re.fullmatch(r"[A-Za-z0-9.\-]+", h) and (bk, h, p) not in out:
            out.append((bk, h, p))
    return out[:24]


def receiver_addrs_text(addrs):
    """Inverse de receiver_addrs (pour la config) : Shure sans préfixe, port par défaut omis."""
    out = []
    for b, h, p in addrs:
        s = h if p in (RX_BRANDS[b]["port"], 0, None) else f"{h}:{p}"
        out.append(s if b == "shure" else f"{b}:{s}")
    return ", ".join(out)


def g4_init():
    """Sennheiser G3 / G4 : demande des mesures pendant 60 s, toutes les 100 ms (à renvoyer avant la fin)."""
    return ["Push 60 100 3\r"]


def g4_apply(state, line):
    """Une ligne « Clé valeur… » d'un récepteur G3 / G4 -> canal 1 : rf (%, max des 2 antennes), rf_a / rf_b, ant (AX si
    l'antenne A est la plus forte, sinon XB), audio (%), batt (0-3 -> barres sur 5), freq (MHz, la valeur est en kHz),
    name, alarms (« Msg » / « Warnings » sauf OK). -> True si compris."""
    p = str(line).strip().split(None, 1)
    if len(p) < 2:
        return False
    k, v = p[0].lower(), p[1].strip()
    st = state.setdefault(1, {})
    st["rf_unit"] = "%"

    def num(x):
        m = re.match(r"-?\d+(?:\.\d+)?", x)
        return float(m.group(0)) if m else None
    if k in ("rf1", "rf2"):
        n = num(v)
        if n is None:
            return False
        st["rf_a" if k == "rf1" else "rf_b"] = n
        a, b = st.get("rf_a"), st.get("rf_b")
        st["rf"] = max(x for x in (a, b) if x is not None)
        if a is not None and b is not None:
            st["ant"] = "AX" if a >= b else "XB"
    elif k == "af" and num(v) is not None:
        st["audio"] = num(v)
    elif k in ("bat", "battery"):
        n = num(v)
        st["batt"] = None if n is None else int(round(min(5.0, n * 5.0 / 3.0)))
    elif k == "frequency" and num(v) is not None:
        st["freq"] = num(v) / 1000.0
    elif k == "name":
        st["name"] = v.strip("\"' ")
    elif k in ("msg", "warnings", "warning"):
        al = st.setdefault("alarms", {})
        if v.upper() in ("OK", "0", "NONE", ""):
            al.pop("MSG", None)
        else:
            al["MSG"] = v
    else:
        return False
    return True


def ssc_init():
    """Sennheiser SSC : demandes JSON (une par trame UDP). Chemins de mémoire ; ceux qui n'existent pas sont ignorés
    par l'appareil (réponse « error »)."""
    reqs = [{"device": {"name": None, "identity": {"product": None}}}]
    for c in (1, 2, 3, 4):
        reqs.append({f"rx{c}": {"name": None, "frequency": None, "rf_quality": None, "warnings": None,
                                "rf1": {"level": None}, "rf2": {"level": None}, "af": {"level": None}}})
        reqs.append({"mates": {f"tx{c}": {"battery": {"gauge": None}}}})
    return [json_dumps_compact(r) for r in reqs]


def json_dumps_compact(o):
    """JSON compact (la section PURE n'importe pas json : écrit à la main, pour des dicts / listes / None / nombres)."""
    if o is None:
        return "null"
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, (int, float)):
        return repr(o)
    if isinstance(o, str):
        return '"' + "".join("\\" + c if c in '"\\' else c for c in o) + '"'
    if isinstance(o, dict):
        return "{" + ",".join(json_dumps_compact(str(k)) + ":" + json_dumps_compact(v) for k, v in o.items()) + "}"
    return "[" + ",".join(json_dumps_compact(v) for v in o) + "]"


def ssc_flatten(o, pre=""):
    """Réponse SSC (dict JSON) -> {chemin « rx1/rf1/level »: valeur}."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(ssc_flatten(v, f"{pre}/{k}" if pre else str(k)))
    else:
        out[pre] = o
    return out


def ssc_apply(state, obj):
    """Réponse SSC -> canaux : rx<n>/… (rf, rf_a / rf_b, ant, audio, freq, name, alarms), mates/tx<n>/battery."""
    ok = False
    for path, v in ssc_flatten(obj).items():
        m = re.match(r"(?:mates/)?(rx|tx)(\d+)/(.+)$", path)
        if not m or v is None:
            continue
        st = state.setdefault(int(m.group(2)), {})
        k = m.group(3)
        try:
            if k == "name":
                st["name"] = str(v).strip()
            elif k == "frequency":
                f = float(v)
                st["freq"] = f / 1000.0 if f > 10000 else f            # kHz ou MHz selon l'appareil
            elif k in ("rf1/level", "rf2/level"):
                st["rf_a" if k.startswith("rf1") else "rf_b"] = float(v)
                st["rf_unit"] = "dBm" if float(v) < 0 else "%"
                a, b = st.get("rf_a"), st.get("rf_b")
                st["rf"] = max(x for x in (a, b) if x is not None)
                if a is not None and b is not None:
                    st["ant"] = "AX" if a >= b else "XB"
            elif k == "rf_quality" and "rf" not in st:
                st["rf"], st["rf_unit"] = float(v), "%"
            elif k == "af/level":
                st["audio"] = float(v)
            elif k.startswith("battery") and k.endswith("gauge"):
                st["batt"] = int(round(max(0.0, min(100.0, float(v))) / 20.0))
            elif k == "warnings":
                ws = [str(x) for x in (v if isinstance(v, list) else [v]) if str(x) not in ("", "[]", "None")]
                st["alarms"] = {f"W{i + 1}": w for i, w in enumerate(ws)}
            else:
                continue
        except (TypeError, ValueError):
            continue
        ok = True
    return ok


# ------------------------------------------------------------------ V8 étape 14 : fiabilité (lot E, 2ᵉ audit)
# 1. Une mesure ancienne ne doit JAMAIS passer pour actuelle. 2. Chaque micro dit comment il est surveillé.
FRESH_S = 2.5            # moniteur : plus de mesure depuis 2,5 s (5 envois manqués) = valeurs « anciennes »
FROZEN_S = 8.0           # … depuis 8 s = flux figé : on coupe l'outil du SDR et on relance
RX_STALE_S = 10.0        # récepteur réseau : plus de nouvelles depuis 10 s = valeurs anciennes


def freshness(age, stale=FRESH_S, lost=FROZEN_S):
    """Âge d'une mesure (s) -> « live » | « stale » (ancienne) | « lost » (plus rien) | « none » (jamais mesuré)."""
    if age is None:
        return "none"
    return "live" if age < stale else ("stale" if age < lost else "lost")


def age_text(age, tr=None):
    """Âge lisible : « 4 s », « 3 min », « 2 h »."""
    tr = tr or (lambda x: x)
    if age is None:
        return tr("jamais")
    a = max(0.0, float(age))
    if a < 90:
        return tr("{} s").format(int(round(a)))
    if a < 5400:
        return tr("{} min").format(int(round(a / 60)))
    return tr("{} h").format(int(round(a / 3600)))


COVERAGE = {   # 2. comment un micro est surveillé : (texte, ton)
    "full": ("● RF + son en continu", "ok"),
    "turn": ("◐ RF en continu, son à tour de rôle", "ok"),
    "degr": ("⚠ dégradée (pertes ou retard)", "warn"),
    "stale": ("⏸ mesure ancienne", "warn"),
    "out": ("○ PAS surveillé (hors fenêtre)", "bad"),
    "stop": ("■ arrêté", "none"),
    "wait": ("… en attente des premières mesures", "none"),
}


def coverage_state(running, in_window, vrx, fresh, perf_tone="ok"):
    """2. État de surveillance d'un micro dans le moniteur : full | turn | degr | stale | out | stop."""
    if not in_window:
        return "out"
    if not running:
        return "stop"
    if fresh != "live":
        return "stale"
    if perf_tone == "bad":
        return "degr"
    return "full" if vrx else "turn"


def coverage_text(key, age=None, tr=None):
    tr = tr or (lambda x: x)
    t = tr(COVERAGE[key][0])
    if key == "stale" and age is not None:
        t += " " + tr("(il y a {})").format(age_text(age, tr))
    return t


# 6. Avalanche d'alertes : un même problème sur un même micro, répété, = une seule ligne « ×N ».
CHRON_GROUP_S = 600.0


def chron_group(rows, name, kind, t, window=CHRON_GROUP_S):
    """Ligne de la chronologie (index) qui regroupe déjà ce problème (même micro, même type, il y a moins de `window`
    secondes, sans dossier d'incident propre) ; None = nouvelle ligne."""
    for i, x in enumerate(rows[:50]):
        if x.get("name") == name and x.get("kind") == kind and t - x.get("t_last", x.get("t", 0)) <= window \
                and not x.get("dir"):
            return i
    return None


# 4. « Tester mon SDR » : vraie vérification (l'outil répond, le SDR est vu, l'IQ arrive au bon débit).
SDR_PROBE = {   # genre : (outil, arguments, motif « trouvé »)
    "hackrf": ("hackrf_info", [], r"Found HackRF|Serial number"),
    "rtlsdr": ("rtl_test", ["-t"], r"Found \d+ device|Using device"),
    "sdrplay": ("SoapySDRUtil", ["--find=driver=sdrplay"], r"driver\s*=\s*sdrplay"),
    "soapy": ("SoapySDRUtil", ["--find"], r"driver\s*="),
}
PROBE_STEPS = ("tool", "seen", "iq", "rate")
PROBE_TEXT = {"tool": "Outil du SDR trouvé", "seen": "SDR détecté (pilote OK)", "iq": "Signal reçu (IQ)",
              "rate": "Débit tenu"}


def probe_seen(kind, out):
    """Sortie de l'outil de détection -> (vu ?, détail : la ligne qui le dit, ou la dernière ligne d'erreur)."""
    pat = (SDR_PROBE.get(kind) or SDR_PROBE["soapy"])[2]
    lines = [x.strip() for x in str(out).splitlines() if x.strip()]
    hit = next((x for x in lines if re.search(pat, x, re.I)), None)
    if hit:
        return True, hit[:120]
    bad = next((x for x in reversed(lines) if re.search(r"error|not found|no .*device|failed|impossible|denied", x, re.I)),
               lines[-1] if lines else "")
    return False, bad[:160]


def probe_rate(nbytes, secs, rate, nb):
    """Débit IQ réellement reçu pendant le test -> (MS/s reçus, part du débit demandé)."""
    if secs <= 0 or rate <= 0:
        return 0.0, 0.0
    got = nbytes / float(nb) / secs
    return round(got / 1e6, 3), round(got / float(rate), 2)


def probe_report(res, tr=None):
    """Résultat du test {étape: (ok | None, détail)} -> lignes « ✔ / ✗ / … étape : détail » et verdict."""
    tr = tr or (lambda x: x)
    lines = []
    for k in PROBE_STEPS:
        if k not in res:
            continue
        ok, d = res[k]
        mark = "✔" if ok else ("…" if ok is None else "✗")
        lines.append(f"{mark} {tr(PROBE_TEXT[k])}" + (f" : {d}" if d else ""))
    done = all(res.get(k, (False,))[0] for k in PROBE_STEPS if k in res) and "rate" in res
    return lines, done


# ------------------------------------------------------------------ V8 étape 16 : le SDR au cœur (panneaux, modes)
# Clément : « le SDR doit être au cœur du projet, pas une fonction ; des fenêtres de base que l'utilisateur bouge et
# modifie à sa sauce, comme la base du soft ; modes tinySA / SDR / combiné ; simple / plus / expert ».
RF_MODES = (("tiny", "📟 tinySA"), ("sdr", "📡 SDR (bêta)"), ("both", "📟+📡 Combiné (bêta)"))   # 8.0 : SDR en bêta
SDR_LAYOUTS = (("listen", "🎧 Écouter"), ("watch", "👁 Surveiller mes micros"), ("analyze", "🔎 Analyser le spectre"),
               ("dual", "🖥 Spectre SDR sur l'autre écran"))
SDR_STEPS_KHZ = (1.0, 5.0, 10.0, 12.5, 25.0, 100.0, 1000.0)
SDR_NFFT = (2048, 4096, 8192)
STATION_DEFAULT = dict(a=None, b=None, b_on=False, step=25.0, vol=0.8, sq=None, split=False, nfft=4096, maxhold=False)
S9_DBM = -93.0                  # S-mètre VHF / UHF : S9 = −93 dBm, 6 dB par unité S


def station_norm(d):
    """Réglages du poste SDR lus de la config (prudemment)."""
    d = d if isinstance(d, dict) else {}
    out = dict(STATION_DEFAULT)

    def num(k, lo, hi):
        try:
            v = float(d[k])
            if lo <= v <= hi:
                out[k] = v
        except (KeyError, TypeError, ValueError):
            pass
    num("a", 0.01, 100000.0)
    num("b", 0.01, 100000.0)
    num("vol", 0.0, 2.0)
    num("sq", -160.0, 0.0)
    if d.get("step") in SDR_STEPS_KHZ:
        out["step"] = float(d["step"])
    if d.get("nfft") in SDR_NFFT:
        out["nfft"] = int(d["nfft"])
    for k in ("b_on", "split", "maxhold"):
        if k in d:
            out[k] = bool(d[k])
    return out


def rf_mode_norm(m):
    return m if m in dict(RF_MODES) else "tiny"


def sdr_level(ui_level):
    """Niveau d'affichage de l'appli -> niveau des panneaux SDR : ultra simple = Simple, simple = Plus, expert = Expert."""
    return {"ultra": "simple", "simple": "plus", "expert": "expert"}.get(ui_level, "plus")


def s_meter(dbm):
    """Niveau (dBm) -> (« S7 », « S9+12 », part de la barre 0..1)."""
    if dbm is None:
        return "—", 0.0
    s = 9.0 + (float(dbm) - S9_DBM) / 6.0
    txt = f"S{max(0, int(round(s)))}" if s <= 9.0 else f"S9+{int(round(float(dbm) - S9_DBM))}"
    return txt, max(0.0, min(1.0, (float(dbm) + 130.0) / 100.0))


def vfo_inside(center_hz, span_mhz, f_mhz, margin_mhz=0.1):
    """La fréquence f tient-elle dans la fenêtre du SDR (centre ± largeur utile / 2, moins une marge) ?"""
    if center_hz is None:
        return False
    return abs(float(f_mhz) * 1e6 - float(center_hz)) <= max(0.0, float(span_mhz) / 2.0 - margin_mhz) * 1e6


def vfo_center(f_mhz, span_mhz):
    """Centre du SDR pour écouter f : f est mis au quart de la fenêtre (pas sur le pic du continu, au centre)."""
    return (float(f_mhz) - 0.25 * float(span_mhz)) * 1e6


# Étape 16 bis (Clément montre WiNRADiO G33WSM et un analyseur SDR moderne) : grande fréquence réglable chiffre par
# chiffre, micros étiquetés sur le spectre, zones à éviter, barre d'état (RBW, FFT…), aller de micro en micro.
def freq_digits(hz):
    """Fréquence (Hz) -> texte « 600.100 000 » (MHz, groupes de 3) et, pour chaque caractère, la valeur d'un cran de
    molette sur lui (Hz) ou 0 (séparateur)."""
    hz = max(0, int(round(float(hz))))
    mhz, rest = divmod(hz, 1000000)
    txt = f"{mhz}.{rest // 1000:03d} {rest % 1000:03d}"
    w = len(str(mhz))
    places = [10 ** (6 + w - 1 - i) for i in range(w)] + [0] + [10 ** (5 - i) for i in range(3)] + [0] + \
             [10 ** (2 - i) for i in range(3)]
    return txt, places


def sdr_zones(code, manual=None, plan=None, lo=None, hi=None):
    """Zones à éviter dessinées sur le spectre SDR : canaux TV marqués « TNT » (à la main ou dans le plan importé) ->
    [(début, fin, libellé)] dans [lo, hi] MHz."""
    manual, plan = manual or {}, set(int(x) for x in (plan or []) if str(x).lstrip("-").isdigit())
    out = []
    for n, a, b in tnt_channel_list(code or "FR"):
        st = manual.get(str(n))
        if st == "tv" or (n in plan and st != "free"):
            if (lo is None or b >= lo) and (hi is None or a <= hi):
                out.append((a, b, f"TNT {n}"))
    return out


def spectrum_status(rate, nfft, load=0.0, ovf=0.0, calibrated=False, tr=None):
    """Barre d'état du spectre SDR : RBW (fenêtre de Blackman : 1,73 case), FFT, détecteur, charge, saturation, échelle."""
    tr = tr or (lambda x: x)
    rbw = 1.73 * float(rate) / max(1, int(nfft))
    rb = f"{rbw / 1000:.2f} kHz" if rbw >= 1000 else f"{rbw:.0f} Hz"
    s = f"RBW {rb} · FFT {int(nfft)} · Blackman · " + tr("moyenne + crête") + \
        " · " + tr("charge {} %").format(f"{100 * float(load):.0f}")
    if ovf > 0.001:
        s += " · ⚠ " + tr("SATURATION {} %").format(f"{100 * float(ovf):.1f}")
    return s + " · " + (tr("dBm (calé)") if calibrated else tr("dBFS (non calé)"))


def next_mic(freqs, f, direction):
    """Micro suivant (+1) ou précédent (−1) de f dans la liste triée des fréquences ; None s'il n'y en a pas."""
    F = sorted(float(x) for x in freqs)
    if direction > 0:
        return next((x for x in F if x > f + 1e-6), None)
    return next((x for x in reversed(F) if x < f - 1e-6), None)


LEVEL_WORDS = ((-95.0, "très faible", "bad"), (-80.0, "faible", "warn"), (-55.0, "bon", "ok"),
               (-30.0, "fort", "ok"), (1e9, "trop fort", "bad"))    # valeurs de départ (choix de Claude)


def level_words(dbm, tr=None):
    """Niveau reçu (dBm) -> (mot simple, ton) pour le vu-mètre : très faible < −95 · faible < −80 · bon < −55 ·
    fort < −30 · au-delà trop fort. None -> (« — », none)."""
    tr = tr or (lambda x: x)
    if dbm is None:
        return "—", "none"
    for lim, w, tone in LEVEL_WORDS:
        if dbm < lim:
            return tr(w), tone
    return tr(LEVEL_WORDS[-1][1]), "bad"


# Étape 17 (Clément : « plusieurs tinySA sur les scènes ET un ou plusieurs SDR qui tournent pour monitorer, à placer sur la
# carte comme les tinySA ») : des POSTES SDR (jusqu'à 4), chacun : nom, modèle, n° de série (pour distinguer deux SDR
# identiques), scènes surveillées, place sur la carte, ses panneaux.
SDR_POSTS_MAX = 4


def sdr_posts_norm(d):
    """Postes SDR lus de la config -> [{id 1..4, name, model, serial, scenes}] triés ; toujours au moins le poste 1."""
    out, seen = [], set()
    for x in (d if isinstance(d, list) else []):
        if not isinstance(x, dict):
            continue
        try:
            pid = int(x.get("id"))
        except (TypeError, ValueError):
            continue
        if not 1 <= pid <= SDR_POSTS_MAX or pid in seen:
            continue
        seen.add(pid)
        m = str(x.get("model") or "")
        out.append(dict(id=pid, name=" ".join(str(x.get("name") or f"SDR {pid}").split())[:40] or f"SDR {pid}",
                        model=m if sdr_model(m) else "", serial=re.sub(r"[^\w:.\-]", "", str(x.get("serial") or ""))[:40],
                        scenes=[str(s)[:60] for s in (x.get("scenes") or []) if str(s).strip()][:20],
                        mics=post_mics_norm(x.get("mics"))))
    if 1 not in seen:
        out.append(dict(id=1, name="SDR 1", model="", serial="", scenes=[], mics=[]))
    return sorted(out, key=lambda p: p["id"])


POST_MICS_MAX = 300


def post_mics_norm(v):
    """8.0.2 : micros CHOISIS pour un poste SDR (kHz, sans doublon, triés) ; vide = ceux de ses scènes."""
    out = set()
    for x in (v if isinstance(v, (list, tuple, set)) else []):
        try:
            k = int(round(float(x)))
        except (TypeError, ValueError):
            continue
        if 1000 <= k <= 7_000_000:
            out.add(k)
    return sorted(out)[:POST_MICS_MAX]


def post_mics_set(mics, keys, on):
    """Ajoute (on) ou retire des micros (kHz) de la liste choisie d'un poste."""
    cur = set(post_mics_norm(mics))
    keys = set(post_mics_norm(keys))
    return post_mics_norm(sorted(cur | keys if on else cur - keys))


def post_watch(watch, scenes, mics=None):
    """Micros suivis par un poste : ceux CHOISIS (8.0.2, depuis Mes fréquences) s'il y en a, sinon ceux de ses scènes
    (toutes si aucune scène n'est choisie)."""
    keys = set(post_mics_norm(mics))
    if keys:
        return [w for w in watch if int(round(w["freq"] * 1000)) in keys]
    sc = set(scenes or [])
    return [w for w in watch if not sc or w.get("scene") in sc]


def sdr_post_clash(items):
    """Deux postes sur le MÊME SDR ? items = [(id, genre, n° de série)] -> [(id1, id2)] : même genre ET (même n° de série,
    ou n° de série vide sur l'un des deux : on ne peut pas savoir lequel est lequel)."""
    out = []
    for i, (a, ka, sa) in enumerate(items):
        for b, kb, sb in items[i + 1:]:
            if ka == kb and (not sa or not sb or sa == sb):
                out.append((a, b))
    return out


# Étape 18 (Clément : « double-clic sur mes fréquences = le SDR se cale dessus ; des fréquences hyper importantes sur le
# pavé numérique qui basculent l'écoute, la fréquence et le SDR »).
FAV_KEYS = 9


def favs_norm(d):
    """Raccourcis du pavé numérique lus de la config -> {1..9: fréquence en kHz}."""
    out = {}
    for k, v in (d.items() if isinstance(d, dict) else []):
        try:
            k, v = int(k), int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= k <= FAV_KEYS and v > 0:
            out[k] = v
    return out


def fav_assign(favs, key, khz):
    """Met le micro (kHz) sur la touche `key` (une fréquence n'est que sur une touche) ; khz None = vider la touche."""
    out = {k: v for k, v in favs_norm(favs).items() if v != khz and k != key}
    if khz:
        out[int(key)] = int(khz)
    return out


# Étape 19 (Clément : « en favori, si ça vient d'un plan Workbench, .ezrf3… ça met le compandeur automatiquement ? et en
# switchant au pavé num ça change le compandeur aussi ») : réglage d'écoute DÉDUIT de ce qu'on sait du micro (profil
# d'appareil, groupe, nom), modifiable (retenu par micro : w["demod"]).
DEMOD_DIGITAL = "digital"
DEMOD_RULES = (    # (motif, préréglage) : le 1er qui correspond gagne ; motifs sur le texte en minuscules sans accents
    (r"ulx-?d|ulxd|axient|\bad\d|\bad ?[124]|qlx|slx-?d|slxd|ew-?dx|ew-?d\b|\bewd\b|digital 6000|\bd6000\b|\b6000\b|spectera|"
     r"\bwmas\b|numeri|digital|\bdx\b|\bsk ?6\d{3}|\bem ?6000", DEMOD_DIGITAL),
    (r"psm|\biem\b|in-?ear|\bears?\b|ear ?monitor|\bsr ?3\d\d\b|\bek ?3\d\d iem|\bg[34] iem|ew iem", "iem"),
    (r"\b(3000|5000)\b|sk ?5212|\bsk ?50\b|em ?3732|em ?3532|\bsk ?5[0-9]{2}\b", "senn_pro"),
    (r"sennheiser|\bew\b|\bew ?\d{3}|evolution|\bg[234]\b|\bsk ?[13-5]00\b|xsw|\bekp\b", "senn_ana"),
    (r"shure|\bur ?[124]d?\b|\bur\d\b|\bulx\b|\bslx\b|\bblx\b|\bglx\b|\bpgx\b|\bsvx\b", "shure_ana"),
    (r"wisycom|wisy|\bmtp\b|\bmrk\b|\bmtk\b|\bmcr\b|\bmpr\b", "wisy_ana"),
    (r"lectro|lectrosonics|\bssm\b|\bsmqv\b|\bsmdb\b|\bsrc\b", "lectro"),
    (r"talkie|\bpmr\b|motorola|kenwood|hytera|\bicom\b", "pmr446"),
    (r"guide|talkback|intercom|interphone", "guide"),
)


def demod_guess(*texts):
    """Préréglage d'écoute deviné d'après ce qu'on sait d'un micro (profil d'appareil, groupe, nom…) : clé de
    DEMOD_PRESETS, DEMOD_DIGITAL (système numérique : ne s'écoute pas), ou None (inconnu)."""
    t = unicodedata.normalize("NFKD", " ".join(str(x or "") for x in texts)).encode("ascii", "ignore").decode().lower()
    for pat, key in DEMOD_RULES:
        if re.search(pat, t):
            return key
    return None


# Étape 20 (Clément : « 1234 !! » sur : alarme -> le SDR s'y cale et enregistre, patrouille d'écoute, pilote, « c'est quoi
# ce signal »). Seuils = choix de Claude, pas mesurés sur de vrais micros.
SDR_AUTO_DEFAULT = dict(tune=True, rec=False, dwell=8, src="favs", pilot_alarm=True)
PATROL_DWELLS = (3, 5, 8, 12, 20, 30)          # secondes par micro
PATROL_SRCS = (("favs", "Mes favoris ⭐ (pavé numérique)"), ("all", "Tous les micros suivis par ce SDR"))
ALARM_TUNE_KINDS = ("CONFLIT", "INTERMOD", "ABSENT", "TROP FORT", "PILOTE")
ALARM_REC_PRE_S = 10.0       # son gardé AVANT l'alarme (seulement si A était déjà sur ce micro)
ALARM_REC_POST_S = 20.0      # son enregistré APRÈS l'alarme
ALARM_TUNE_COOLDOWN_S = 60.0  # même alarme : pas de nouveau calage avant 60 s
ALARM_USER_HOLD_S = 30.0     # tu viens de choisir une fréquence : le SDR ne se cale pas sur une alarme pendant 30 s
PILOT_TOL_HZ = 300.0         # même pilote si à ± 300 Hz
PILOT_LEARN_S = 3.0          # pilote vu 3 s d'affilée -> appris pour ce micro
PILOT_MISS_S = 5.0           # porteuse là mais pilote disparu depuis 5 s -> « pas ton émetteur ? »


def sdr_auto_norm(d):
    """Réglages automatiques du poste SDR (sdr_cfg « auto ») : tune (se caler sur une alarme), rec (enregistrer le son
    de l'alarme : accord vie privée demandé à part), dwell (s par micro en patrouille), src (favs | all),
    pilot_alarm (alarme si la porteuse reste sans son pilote)."""
    d = d if isinstance(d, dict) else {}
    out = dict(SDR_AUTO_DEFAULT)
    for k in ("tune", "rec", "pilot_alarm"):
        if k in d:
            out[k] = bool(d[k])
    try:
        v = int(d.get("dwell", out["dwell"]))
        out["dwell"] = min(PATROL_DWELLS, key=lambda x: abs(x - v))
    except (TypeError, ValueError):
        pass
    if d.get("src") in dict(PATROL_SRCS):
        out["src"] = d["src"]
    return out


def patrol_items(favs, mics, src="favs"):
    """Micros parcourus par la patrouille d'écoute, par fréquence (les micros d'une même fenêtre du SDR à la suite : il
    se recentre le moins possible) -> [kHz]. favs {touche: kHz} ; mics = [(kHz, éteint ou en pause)] des micros du poste
    (dans sa plage). « favs » : les favoris (s'il n'y en a aucun, tous les micros) ; éteints / en pause sautés."""
    ok = {int(k): bool(off) for k, off in mics}
    if src == "favs":
        keys = sorted(int(v) for v in favs_norm(favs).values() if int(v) in ok)   # audit : par fréquence, pour que
        if keys:                                                                # le SDR se recentre le moins possible
            return [k for k in dict.fromkeys(keys) if not ok[k]]
    return [k for k in dict.fromkeys(sorted(ok)) if not ok[k]]


def patrol_next(items, cur):
    """Micro suivant de la patrouille (après cur, en boucle) ; cur absent -> le 1er ; liste vide -> None."""
    if not items:
        return None
    try:
        return items[(items.index(cur) + 1) % len(items)]
    except ValueError:
        return items[0]


def alarm_pick(alarms, seen, ok_freq, kinds=ALARM_TUNE_KINDS):
    """Alarme NOUVELLE (n° — sinon clé — pas dans `seen`) la plus grave sur laquelle le SDR peut se caler (ok_freq(MHz) vrai) ;
    à gravité égale la plus récente. -> alarme ou None."""
    c = [a for a in alarms if a.get("kind") in kinds and a.get("id", a.get("key")) not in seen and a.get("freq")
         and ok_freq(float(a["freq"]))]
    return max(c, key=lambda a: (int(a.get("prio", 0)), float(a.get("t0", 0.0)))) if c else None


def pilot_verdict(learned_hz, pilot, carrier, miss_s=0.0, tr=None):
    """Ce que dit le pilote d'un micro écouté. learned_hz = pilote appris (Hz) ou None ; pilot = (Hz, dB) vu maintenant
    ou None ; carrier = une porteuse est là ; miss_s = depuis quand elle est là sans son pilote.
    -> (clé, texte, ton) ; clés : same, other, missing, wait, seen, none, off."""
    tr = tr or (lambda x: x)
    if not carrier:
        return "off", tr("pas de porteuse : pilote non jugé"), "none"
    if pilot is not None:
        k = f"{pilot[0] / 1000.0:.1f}"
        if learned_hz is None:
            return "seen", tr("pilote {} kHz vu (il sera retenu pour ce micro)").format(k), "none"
        if abs(pilot[0] - learned_hz) <= PILOT_TOL_HZ:
            return "same", tr("✔ pilote {} kHz : c'est bien ton émetteur").format(k), "ok"
        return "other", tr("⚠ pilote {} kHz au lieu de {} kHz : un autre émetteur ?").format(
            k, f"{learned_hz / 1000.0:.1f}"), "warn"
    if learned_hz is None:
        return "none", tr("pas de pilote vu (normal pour certains micros)"), "none"
    if miss_s >= PILOT_MISS_S:
        return "missing", tr("⚠ porteuse SANS son pilote : ce n'est peut-être pas ton émetteur (brouilleur ?)"), "bad"
    return "wait", tr("pilote attendu ({} kHz)…").format(f"{learned_hz / 1000.0:.1f}"), "warn"


def pilot_learn(hist, pilot, now, learn_s=PILOT_LEARN_S):
    """Apprentissage du pilote : hist = dict(hz, t0) en cours (ou None) ; renvoie (hist mis à jour, Hz appris ou None).
    Il faut le même pilote (± PILOT_TOL_HZ) pendant learn_s secondes d'affilée."""
    if pilot is None:
        return None, None
    if hist is None or abs(pilot[0] - hist["hz"]) > PILOT_TOL_HZ:
        return dict(hz=float(pilot[0]), t0=float(now)), None
    if now - hist["t0"] >= learn_s:
        return hist, float(round(hist["hz"]))
    return hist, None


def sdr_carrier(F, L, f0, half=0.05, margin=12.0):
    """Une porteuse est-elle là ? Pic à ± half MHz de f0 au moins `margin` dB au-dessus de la médiane du spectre."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    if len(F) < 8 or len(F) != len(L):
        return False
    m = np.abs(F - f0) <= half
    return bool(m.any() and float(np.max(L[m])) - float(np.median(L)) >= margin)


def what_is(F, L, f0, pilot=None):
    """« C'est quoi » autour de f0 : d'abord au plus près (± 0,5 MHz : un micro voisin ne gonfle pas la largeur), puis
    sur ± 5 MHz si c'est large (TNT, bloc numérique)."""
    c = classify_signal(F, L, f0, pilot, span=0.5)
    if c.get("kind") in ("wide", "num") and (c.get("bw_khz") or 0) > 700:
        c = classify_signal(F, L, f0, pilot, span=5.0)
    return c


def what_is_text(c, tr=None):
    """Phrase courte « c'est quoi » pour le poste SDR : 🏷 type · largeur · dB au-dessus du bruit."""
    tr = tr or (lambda x: x)
    if not c or c.get("kind") == "none":
        return tr("🏷 Rien de net sur A")
    return "🏷 " + signal_report(c, tr)


# ------------------------------------------------------------------ V8 étape 21 : générateur de signaux
# Clément : « un mode démo sur le SDR, avec audio pour écouter » + « générer avec du SDR » -> « Bothhh ». Un seul
# générateur : il fabrique l'IQ du SDR démo (à l'écran, sans matériel) ET ce qu'un HackRF émet en câble.
DEMO_RATE = 2400000            # débit IQ du SDR démo
DEMO_DBM = -40.0               # dBFS -> dBm du SDR démo (niveaux et seuils proches d'un vrai SDR)
DEMO_PILOT = 32768.0           # pilote des micros de démo (Hz) : une valeur d'exemple, pas celle d'une marque
DEMO_SOUNDS = (("voice", "Voix « un, deux »"), ("melody", "Mélodie"), ("beep", "Bips"), ("tone", "Tonalité 1 kHz"))
SIG_KINDS = (("fm", "Micro FM (large)"), ("nfm", "Talkie (FM étroite)"), ("cw", "Porteuse pure"),
             ("noise", "Bloc large (numérique, TNT)"))
SDR_DEMO_MODEL = dict(key="demo", kind="demo", name="🧪 SDR démo (sans matériel)", fmin=1.0, fmax=6000.0, bits=12,
                      enob=10.0, rates=[DEMO_RATE], usable=0.8, max_in=None, gains=[], cal=False, src="",
                      note="Signaux fabriqués par l'appli à partir de tes micros (son, pilote, brouilleur qui passe, "
                           "micro qui s'éteint) : pour découvrir le poste SDR sans matériel.")
SDR_DEMO_KIND = dict(name="SDR démo", tool=None, iq_tool=None, fmin=1.0, fmax=6000.0)
TX_RATES = (4000000, 10000000, 20000000)     # débits d'émission HackRF essayés (le plus petit qui contient tout)
TX_MAX_SIGS = 8
TX_DURATIONS = (1, 5, 15, 30)                # minutes : l'émission s'arrête toute seule


AUDIO_SRCS = (("voice", "Voix « un, deux »"), ("melody", "Mélodie"), ("beep", "Bips"),
              ("tone", "Générateur : une fréquence (20 Hz – 20 kHz)"), ("sweep", "Générateur : balayage (sweep)"),
              ("white", "Bruit blanc"), ("pink", "Bruit rose"), ("app", "Un son de l'appli"), ("wav", "Mon fichier WAV"),
              ("silence", "Silence (porteuse seule)"), ("stair", "Signal de test : escalier de niveaux (mesurer un émetteur)"))
APP_SOUNDS = (("alarm2", "Alarme critique"), ("alarm1", "Alarme normale"), ("alarm0", "Alarme info"),
              ("ok", "Appel des micros ✓"))


def app_sound_seq(key):
    """Notes [(Hz, ms)] d'un son de l'appli (alarmes, appel des micros)."""
    return {"alarm2": ALARM_TONES[2], "alarm1": ALARM_TONES[1], "alarm0": ALARM_TONES[0], "ok": TONE_OK}.get(
        key, ALARM_TONES[2])
WAV_PCM = {}                  # fichier WAV -> son mono 48 kHz (float32), rempli par l'interface (lecture du fichier)


def audio_spec_norm(d):
    """Source sonore -> dict(src, f, f1, f2, dur, log, app, path) complet et borné (ancien format = un nom simple)."""
    if isinstance(d, str):
        d = dict(src=d)
    d = d if isinstance(d, dict) else {}
    out = dict(src="voice", f=1000.0, f1=20.0, f2=20000.0, dur=10.0, log=True, app="alarm2", path="")
    if d.get("src") in dict(AUDIO_SRCS):
        out["src"] = d["src"]
    for k, lo, hi in (("f", 20.0, 20000.0), ("f1", 20.0, 20000.0), ("f2", 20.0, 20000.0), ("dur", 1.0, 120.0)):
        try:
            out[k] = float(min(hi, max(lo, float(d.get(k, out[k])))))
        except (TypeError, ValueError):
            pass
    out["log"] = bool(d.get("log", True))
    if d.get("app") in [a for a, _n in APP_SOUNDS]:
        out["app"] = d["app"]
    out["path"] = str(d.get("path") or "")[:500]
    out["lvl"] = None                                  # 8.1 : niveau visé (dBFS, sinus crête = 0) ; None = d'origine
    try:
        if d.get("lvl") is not None:
            out["lvl"] = float(min(0.0, max(-60.0, float(d["lvl"]))))
    except (TypeError, ValueError):
        pass
    out["gain"] = 0.0                                  # 8.1 : gain à la main (dB), utilisé quand lvl est None
    try:
        out["gain"] = float(min(40.0, max(-60.0, float(d.get("gain") or 0.0))))
    except (TypeError, ValueError):
        pass
    return out


def audio_text(d, tr=None):
    """Source sonore en quelques mots (bouton, journal) ; 8.1 : « · −18 dBFS » si un niveau est réglé."""
    tr = tr or (lambda x: x)
    d = audio_spec_norm(d)
    if d.get("lvl") is not None:
        return _audio_text(dict(d, lvl=None), tr) + f" · {d['lvl']:+.1f} dBFS".replace(".", ",")
    if d.get("gain"):
        return _audio_text(d, tr) + f" · {d['gain']:+.1f} dB".replace(".", ",")
    return _audio_text(d, tr)


def _audio_text(d, tr):
    """Texte d'une source sans le niveau."""
    src = d["src"]
    if src == "tone":
        return tr("Tonalité {} Hz").format(f"{d['f']:g}")
    if src == "sweep":
        return tr("Balayage {} → {} Hz en {} s ({})").format(f"{d['f1']:g}", f"{d['f2']:g}", f"{d['dur']:g}",
                                                             tr("log") if d["log"] else tr("linéaire"))
    if src == "app":
        return tr(dict(APP_SOUNDS).get(d["app"], ""))
    if src == "wav":
        return tr("WAV : {}").format((d["path"].replace("\\", "/").rsplit("/", 1)[-1]) or "—")
    return tr(dict(AUDIO_SRCS)[src])


ALARM_SND_MAX_S = 4.0         # un son d'alarme personnalisé est coupé à 4 s (il ne recouvre pas l'alarme suivante)


def alarm_sounds_norm(d):
    """Sons des alarmes choisis (config « alarm_sounds ») -> {clé d'APP_SOUNDS: source} ; absent = son d'origine."""
    d = d if isinstance(d, dict) else {}
    keys = [k for k, _n in APP_SOUNDS]
    return {k: audio_spec_norm(v) for k, v in d.items() if k in keys and isinstance(v, (dict, str))}


def alarm_pcm(spec, max_s=ALARM_SND_MAX_S):
    """Source sonore -> son court d'alarme (float32, 48 kHz) : durée selon la source, fondu de 10 ms au début / à la fin."""
    sp = audio_spec_norm(spec)
    src = sp["src"]
    if src == "sweep":
        secs = sp["dur"]
    elif src == "wav":
        secs = len(WAV_PCM.get(sp["path"], ())) / 48000.0 or 0.1
    elif src == "app":
        secs = sum(ms for _h, ms in app_sound_seq(sp["app"])) / 1000.0
    elif src in ("voice", "melody"):
        secs = 2.2 if src == "voice" else 2.4
    else:
        secs = 1.0
    n = int(48000 * max(0.05, min(float(max_s), secs)))
    a = demo_audio(sp, np.arange(n) / 48000.0, 0).astype(np.float32)
    f = min(len(a) // 2, 480)
    if f:
        ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
        a[:f] *= ramp
        a[-f:] *= ramp[::-1]
    return a


def _seq_audio(seq, t, gap=0.8):
    """Suite de notes [(Hz, ms)] jouée en boucle (avec un blanc de `gap` s) aux instants t."""
    ends = np.cumsum([ms / 1000.0 for _hz, ms in seq])
    per = float(ends[-1]) + gap
    c = t % per
    i = np.searchsorted(ends, c, side="right")
    hz = np.array([h for h, _ms in seq] + [0.0])[np.minimum(i, len(seq))]
    st = np.concatenate([[0.0], ends])[np.minimum(i, len(seq))]
    pos = c - st
    env = np.clip(np.minimum(pos, 0.02) / 0.005, 0.0, 1.0)
    return (0.8 * env * (hz > 0) * np.sin(2 * np.pi * hz * t)).astype(np.float32)


NOISE_RATE = 48000
_NOISE = {}


def _noise_loop(kind, secs=8.0):
    """Bruit blanc / rose de `secs` secondes à 48 kHz, fabriqué une fois (graine fixe), dont la fin se raccorde au
    début (mise en forme par FFT sur toute la boucle : périodique, donc pas de couture)."""
    if kind not in _NOISE:
        n = int(secs * NOISE_RATE)
        w = np.random.default_rng(12345 if kind == "pink" else 54321).standard_normal(n)
        if kind == "pink":
            X = np.fft.rfft(w)
            fr = np.arange(len(X), dtype=np.float64)
            X[1:] = X[1:] / np.sqrt(fr[1:])
            X[0] = 0.0
            w = np.fft.irfft(X, n)
        w = w / (np.std(w) + 1e-12)
        _NOISE[kind] = (0.25 * np.clip(w, -3.5, 3.5)).astype(np.float32)
    return _NOISE[kind]


_SRC_LEVEL = {}


def audio_source_stats(spec, k=0):
    """8.1 : (niveau moyen RMS, crête) d'origine d'une source, en dBFS (AES17), mesurés une fois : sur TOUT le fichier
    pour un WAV (avant : ses 4 premières secondes -> une intro calme donnait un gain énorme et le reste du morceau
    écrêté), sur la durée d'un balayage, sinon sur 4 s."""
    sp = dict(audio_spec_norm(spec), lvl=None, gain=0.0)
    key = (tuple(sorted((a, str(b)) for a, b in sp.items())), int(k))
    if sp["src"] == "wav":                               # 8.1 (audit) : un WAV remplacé sous le même nom est re-mesuré
        w_ = WAV_PCM.get(sp["path"])
        key += ((len(w_), float(np.sum(np.abs(w_[::997], dtype=np.float64)))) if w_ is not None and len(w_) else None,)
    if key not in _SRC_LEVEL:
        if sp["src"] == "wav" and len(WAV_PCM.get(sp["path"], [])):
            x = np.asarray(WAV_PCM[sp["path"]], dtype=np.float32)
        else:
            n = int(min(12.0, max(4.0, sp["dur"] if sp["src"] == "sweep" else 4.0)) * 48000)
            x = demo_audio(sp, np.arange(n) / 48000.0, k)
        m = audio_meter(x, 48000)
        _SRC_LEVEL[key] = (m["rms"], m["peak"])
    return _SRC_LEVEL[key]


def audio_source_level(spec, k=0):
    """Niveau moyen d'origine (dBFS) d'une source (voir audio_source_stats)."""
    return audio_source_stats(spec, k)[0]


def audio_gain(spec, k=0):
    """8.1 : gain appliqué à une source (dB) -> (gain, limité par la crête ?). Niveau visé : gain pour y amener le
    niveau MOYEN, mais jamais au point d'écrêter (crête ≤ −0,3 dBFS) ; sinon le gain réglé à la main."""
    sp = audio_spec_norm(spec)
    if sp.get("lvl") is None:
        return float(sp.get("gain") or 0.0), False
    rms, pk = audio_source_stats(sp, k)
    if not math.isfinite(rms):
        return 0.0, False
    return gain_to_target(rms, sp["lvl"], pk)


def demo_audio(kind, t, k=0):
    """Son de démo (float32, −1…1) aux instants t (s). k = n° du micro : chacun a sa hauteur, on les reconnaît.
    kind = nom (voice, melody, beep, tone…) ou source complète (dict d'audio_spec_norm : générateur, balayage,
    bruit, son de l'appli, fichier WAV). 8.1 : niveau visé (lvl, dBFS) -> gain constant (mesuré sur la source)."""
    t = np.asarray(t, dtype=np.float64)
    spec = audio_spec_norm(kind) if isinstance(kind, dict) else None
    if spec is not None and (spec.get("lvl") is not None or spec.get("gain")):
        g, _lim = audio_gain(spec, k)
        x = demo_audio(dict(spec, lvl=None, gain=0.0), t, k)
        return np.clip(x * 10.0 ** (g / 20.0), -1.0, 1.0).astype(np.float32)
    if spec is not None:
        kind = spec["src"]
    if kind == "silence":
        return np.zeros(len(t), dtype=np.float32)
    if kind == "stair":                           # 8.2 : signal de test du Compander Lab
        return stair_signal(t)
    if kind == "tone":
        f = spec["f"] if spec else 1000.0
        return (0.8 * np.sin(2 * np.pi * f * t)).astype(np.float32)
    if kind == "sweep":
        f1, f2, T = (spec["f1"], spec["f2"], spec["dur"]) if spec else (20.0, 20000.0, 10.0)
        tau = t % T
        if (spec["log"] if spec else True) and f1 != f2:
            K = math.log(f2 / f1)
            ph = 2 * np.pi * f1 * T / K * (np.exp(K * tau / T) - 1.0)
        else:
            ph = 2 * np.pi * (f1 * tau + (f2 - f1) * tau * tau / (2.0 * T))
        return (0.8 * np.sin(ph)).astype(np.float32)
    if kind in ("white", "pink"):
        loop = _noise_loop(kind)                  # 8.1 : boucle de 8 s lue au fil du temps (avant : un bruit refait à
        if not len(t):                            # chaque morceau = « burst » au rythme de l'affichage du SDR démo)
            return np.zeros(0, dtype=np.float32)
        i = np.round(np.asarray(t, dtype=np.float64) * NOISE_RATE).astype(np.int64) % len(loop)
        return loop[i]
    if kind == "app":
        return _seq_audio(app_sound_seq(spec["app"] if spec else "alarm2"), t)
    if kind == "wav":
        pcm = WAV_PCM.get(spec["path"] if spec else "")
        if pcm is None or not len(pcm):
            return np.zeros(len(t), dtype=np.float32)
        return np.asarray(pcm, dtype=np.float32)[(np.round(t * 48000.0).astype(np.int64)) % len(pcm)]
    if kind == "beep":
        on = (t % 1.0) < 0.2
        return (0.8 * on * np.sin(2 * np.pi * (700.0 + 90.0 * k) * t)).astype(np.float32)
    if kind == "melody":
        notes = np.array([0, 4, 7, 12, 7, 4, 2, 5])
        i = np.floor(t / 0.3).astype(np.int64) % len(notes)
        f = 262.0 * 2.0 ** ((notes[i] + 2 * (k % 6)) / 12.0)
        ph = 2 * np.pi * f * t
        env = np.clip(np.minimum(t % 0.3, 0.3 - t % 0.3) / 0.03, 0.0, 1.0)
        return (0.55 * env * (np.sin(ph) + 0.3 * np.sin(2 * ph))).astype(np.float32)
    # « voice » : deux syllabes (« un », « deux ») sur une voix synthétique (fondamentale + harmoniques façon voyelle)
    c = t % 2.2
    on1, on2 = (c < 0.35), (c >= 0.6) & (c < 0.95)
    env = np.where(on1, np.sin(np.pi * np.clip(c / 0.35, 0, 1)), 0.0) + \
        np.where(on2, np.sin(np.pi * np.clip((c - 0.6) / 0.35, 0, 1)), 0.0)
    fb = 110.0 + 18.0 * (k % 5)                    # fondamentale + vibrato de 6 Hz à 5 Hz (phase exacte : continue)
    f0 = fb + 6.0 * np.sin(2 * np.pi * 5.0 * t)
    ph = 2 * np.pi * fb * t - (6.0 / 5.0) * np.cos(2 * np.pi * 5.0 * t)
    fm1 = np.where(on1, 650.0, 450.0)            # 1er formant : « un » plus ouvert que « deux »
    fm2 = np.where(on1, 1100.0, 1700.0)
    a = np.zeros(len(t))
    for h in range(1, 13):
        fh = h * f0
        w = np.exp(-((fh - fm1) / 180.0) ** 2) + 0.6 * np.exp(-((fh - fm2) / 250.0) ** 2) + 0.15 / h
        a = a + w * np.sin(h * ph)
    return (0.45 * env * a / 2.2).astype(np.float32)


def sched_on(s, t):
    """Programme d'un signal : None = toujours ; (période s, durée allumé s, décalage s)."""
    if not s:
        return True
    per, on, off = float(s[0]), float(s[1]), float(s[2] if len(s) > 2 else 0.0)
    return ((t + off) % max(per, 1e-3)) < on


class SigGen:
    """Fabrique de l'IQ (complexe, ~ −1…1) autour de `center_hz` à `rate` éch./s, bloc par bloc, sans coupure de phase.
    Signal = dict(key, kind fm|nfm|cw|noise, f MHz, lvl dB (0 = le plus fort), dev Hz, audio, k, pilot Hz, bw MHz,
    on (programme), pilot_on (programme du pilote)). Pur numpy : sert au SDR démo et à l'émission HackRF."""

    def __init__(self, rate, center_hz, sigs=(), noise=0.01, seed=7):
        self.rate, self.center = float(rate), float(center_hz)
        self.noise, self.n0, self.st = float(noise), 0, {}
        self.rng = np.random.default_rng(seed)
        self.sigs = []
        self.set_sigs(sigs)

    def set_sigs(self, sigs):
        self.sigs = [dict(s) for s in sigs]
        keep = {s.get("key") for s in self.sigs}
        self.st = {k: v for k, v in self.st.items() if k in keep}

    def _rot(self, f, n):
        """exp(j·2π·f·k/fs), k = 0…n-1, en complex64, gardé (même porteuse / pilote, même taille de bloc d'un appel à
        l'autre) : 8.0.3, le SDR démo calculait tout en double précision -> 1 s de calcul pour 1 s d'IQ (saccades)."""
        key = (round(float(f), 3), int(n))
        c = self._rots.get(key)
        if c is None:
            if len(self._rots) > 64:
                self._rots.clear()
            c = self._rots[key] = np.exp(2j * np.pi * float(f) / self.rate * np.arange(n)).astype(np.complex64)
        return c

    def block(self, n):
        n = int(n)
        fs = self.rate
        if not hasattr(self, "_rots"):
            self._rots = {}
        n0 = self.n0
        t0 = n0 / fs
        x = (self.noise / math.sqrt(2.0)) * (self.rng.standard_normal(n, dtype=np.float32)
                                             + 1j * self.rng.standard_normal(n, dtype=np.float32))
        x = x.astype(np.complex64)
        noise_sigs = []
        step = max(1, int(round(fs / 48000.0)))
        ta = None
        buf = np.empty(n, dtype=np.complex64)
        tt = None

        def _mask(prog):
            """8.1 (audit) : programme évalué À L'ÉCHANTILLON (avant : au début du bloc seulement, une coupure pouvait
            attendre le bloc suivant) -> None = allumé tout le bloc, False = éteint tout le bloc, sinon un masque 0 / 1."""
            nonlocal tt
            if not prog:
                return None
            if tt is None:
                tt = (n0 + np.arange(n, dtype=np.float64)) / fs
            m_ = sched_on(prog, tt)
            return None if m_.all() else (False if not m_.any() else m_.astype(np.float32))
        for s in self.sigs:
            kind = s.get("kind", "fm")
            msk = _mask(s.get("on")) if kind != "noise" else (None if sched_on(s.get("on"), t0) else False)
            if msk is False:
                continue
            off = float(s["f"]) * 1e6 - self.center
            bw = float(s.get("bw") or 0.0) * 1e6
            if abs(off) - bw / 2.0 > 0.5 * fs:
                continue                                   # hors de la fenêtre
            amp = 0.3 * 10.0 ** (float(s.get("lvl", 0.0)) / 20.0)
            if kind == "noise":
                noise_sigs.append((round(off), round(bw), round(amp, 6)))
                continue
            car = self._rot(off, n) * np.complex64(amp * np.exp(2j * np.pi * ((off * n0 / fs) % 1.0)))
            if kind in ("fm", "nfm"):
                dev = float(s.get("dev") or (30000.0 if kind == "fm" else 2500.0))
                if ta is None:
                    ta = (n0 + np.arange(0, n, step, dtype=np.float64)) / fs
                st = self.st.setdefault(s.get("key"), dict(acc=0.0))
                sig_ = (repr(s.get("audio")), s.get("comp") or "", int(s.get("k", 0)))
                if st.get("sig") != sig_:                  # 8.1 (audit) : autre son / autre compander -> l'état du
                    st["sig"] = sig_                       # traitement audio repart de zéro ; la PHASE (acc) est gardée
                    st.pop("cp", None)
                a = demo_audio(s.get("audio", "voice"), ta, int(s.get("k", 0)))
                cp = COMPANDERS.get(s.get("comp") or "")
                if cp is not None and cp["ratio"] > 1.0:   # 8.1 : l'émetteur démo comprime comme un vrai pack
                    a = compress2(a, st.setdefault("cp", {}), ratio=cp["ratio"], attack=cp["attack"],
                                  release=cp["release"], detector=cp["det"])
                a = np.repeat(a, step)[:n]
                ph = np.cumsum(a.astype(np.float32) * np.float32(2 * np.pi * dev / fs))    # simple précision : assez
                ph += np.float32(st["acc"])
                st["acc"] = float(ph[-1]) % (2 * np.pi) if n else st["acc"]
                p = float(s.get("pilot") or 0.0)
                pm = _mask(s.get("pilot_on")) if p else False
                if p and pm is not False:
                    pr = self._rot(p, n)                   # sin(2π p t) = Im(rotation de départ × table)
                    e0 = np.exp(2j * np.pi * ((p * n0 / fs) % 1.0))
                    pil = np.float32(4000.0 / p) * (np.float32(e0.real) * pr.imag + np.float32(e0.imag) * pr.real)
                    ph += pil if pm is None else pil * pm
                buf.real = np.cos(ph)                        # exp(jφ) en complex64 (13× plus rapide que np.exp)
                buf.imag = np.sin(ph)
                x += car * buf if msk is None else car * buf * msk
            else:
                x += car if msk is None else car * msk
        if noise_sigs:                                  # blocs larges (TNT, numérique) : bruit mis en forme UNE fois
            key = (tuple(sorted(noise_sigs)), n)
            tex = getattr(self, "_tex", None)
            if tex is None or tex[0] != key:
                L = 8 * n
                fr = np.fft.fftfreq(L, 1.0 / fs)
                sp = np.zeros(L)
                for off_, bw_, amp_ in noise_sigs:
                    sp += amp_ * ((fr >= off_ - bw_ / 2.0) & (fr <= off_ + bw_ / 2.0))
                w = self.rng.standard_normal(L) + 1j * self.rng.standard_normal(L)
                tex = self._tex = (key, np.fft.ifft(np.fft.fft(w) * sp).astype(np.complex64), 0)
            k0 = (tex[2] + n) % (8 * n)
            x += tex[1][k0:k0 + n] if k0 + n <= 8 * n else np.concatenate((tex[1][k0:], tex[1][:k0 + n - 8 * n]))
            self._tex = (tex[0], tex[1], k0)
        self.n0 += n
        return x.astype(np.complex64)


def demo_sdr_plan(mics):
    """Signaux du SDR démo d'après tes micros. mics = [dict(f MHz, name, bw MHz, free (doit rester libre), digital)].
    Le 1er micro s'éteint 15 s toutes les 2 min (alarme ABSENT), le 2ᵉ perd son pilote 10 s toutes les 90 s (alarme
    PILOTE), un brouilleur passe 8 s par minute sur la 1re « doit rester libre », + deux canaux TNT. Sans micros :
    7 signaux d'exemple autour de 606 MHz (5 micros HF, une réserve « doit rester libre », un micro numérique)."""
    mics = list(mics or [])
    if not mics:
        mics = [dict(f=f, name=f"HF {i + 1}", bw=0.0, free=False, digital=False)
                for i, f in enumerate((606.2, 606.9, 607.6, 608.4, 609.1))]
        mics += [dict(f=605.5, name="Réserve", bw=0.0, free=True, digital=False),
                 dict(f=610.0, name="Numérique", bw=0.0, free=False, digital=True)]
    out, k, jam = [], 0, False
    for m in sorted(mics, key=lambda m: float(m["f"])):
        f = float(m["f"])
        key = f"{f:.4f}"
        kind = m.get("kind") or "auto"                # 8.0.3 : type de signal choisi pour ce micro (générateur)
        if kind == "off":
            continue
        if kind == "jam":
            out.append(dict(key="jam" + key, kind="nfm", f=f, lvl=-12.0, audio=audio_spec_norm(m["snd"]) if m.get("snd")
                            else "beep", k=3))
            continue
        if kind == "digital":
            out.append(dict(key="num" + key, kind="noise", f=f, bw=0.2, lvl=-14.0))
            continue
        if kind in ("fm", "intermittent"):
            m = dict(m, free=False, bw=0.0, digital=False)
        if m.get("free"):
            if not jam:
                out.append(dict(key="jam" + key, kind="nfm", f=f, lvl=-12.0, audio="beep", k=3, on=(60.0, 8.0, 20.0)))
                jam = True
            continue
        if float(m.get("bw") or 0) > 0:
            out.append(dict(key="blk" + key, kind="noise", f=f, bw=float(m["bw"]), lvl=-22.0))
            continue
        if m.get("digital"):
            out.append(dict(key="num" + key, kind="noise", f=f, bw=0.2, lvl=-14.0))
            continue
        h = sum(ord(c) for c in str(m.get("name", ""))) % 12
        s = dict(key="mic" + key, kind="fm", f=f, lvl=-6.0 - h,      # 8.1 : 0 dBFS = déviation nominale du micro
                 dev=float(m.get("dev") or (25000.0 + 1500.0 * (h % 8))), comp=m.get("comp") or "",
                 audio=audio_spec_norm(m["snd"]) if m.get("snd") else DEMO_SOUNDS[k % len(DEMO_SOUNDS)][0], k=k,
                 pilot=DEMO_PILOT)
        if kind == "intermittent":
            s["on"] = (40.0, 25.0, 0.0)
        elif kind == "fm":
            pass                                          # choisi « micro FM » : toujours là
        elif k == 0:
            s["on"] = (120.0, 105.0, 0.0)
        elif k == 1:
            s["pilot_on"] = (90.0, 80.0, 40.0)
        out.append(s)
        k += 1
    out += [dict(key="tnt21", kind="noise", f=478.0, bw=7.6, lvl=-24.0),
            dict(key="tnt30", kind="noise", f=546.0, bw=7.6, lvl=-26.0)]
    return out


DEMO_SIG_KINDS = (("auto", "Automatique (d'après le statut)"), ("fm", "Micro FM (avec son)"),
                  ("digital", "Micro numérique (bloc)"), ("intermittent", "Coupe de temps en temps"),
                  ("jam", "Brouilleur"), ("off", "Rien (éteint)"))


def demo_plan_levels(fr_mhz, plan, t, rng=None):
    """8.0.3 (Clément : « le mode démo devrait générer la fréquence monitorée ») : le démo du tinySA voit le MÊME plan que
    le SDR démo (tes micros, le brouilleur, les coupures, la TNT). -> niveaux dBm (NaN là où rien n'émet)."""
    fr = np.asarray(fr_mhz, dtype=float)
    lv = np.full(len(fr), np.nan)
    if not len(fr):
        return lv
    for sg in plan or ():
        if not sched_on(sg.get("on"), t):
            continue
        f, top = float(sg["f"]), DEMO_DBM + float(sg.get("lvl", 0.0)) - 8.0
        if sg.get("kind") == "noise":
            bw = float(sg.get("bw") or 0.2)
            d = np.maximum(0.0, np.abs(fr - f) - bw / 2.0)
            m = d < 0.4
            if not m.any():
                continue
            x = top - 60.0 * d[m] + (rng.normal(0, 1.5, int(m.sum())) if rng is not None else 0.0)
        else:
            w = 0.06 if sg.get("kind") == "nfm" else 0.1
            m = np.abs(fr - f) < 0.6
            if not m.any():
                continue
            x = top - 12.0 * ((fr[m] - f) / w) ** 2 + (rng.normal(0, 0.8, int(m.sum())) if rng is not None else 0.0)
        lv[m] = np.fmax(lv[m], x)
    return lv


def tx_plan(rows, rates=TX_RATES, fmin=1.0, fmax=6000.0):
    """Émission : lignes [dict(f MHz, kind, audio, pilot bool, lvl dB)] -> (centre Hz, débit, signaux) ou un texte
    d'erreur. Centre décalé pour qu'aucun signal ne tombe sur le continu du HackRF (fuite de l'oscillateur)."""
    rows = [r for r in rows if r.get("f")]
    if not rows:
        return "Ajoute au moins un signal."
    if len(rows) > TX_MAX_SIGS:
        return f"{TX_MAX_SIGS} signaux au plus."
    fs_ = [float(r["f"]) for r in rows]
    if min(fs_) < fmin or max(fs_) > fmax:
        return f"Fréquences entre {fmin:g} et {fmax:g} MHz."
    half = max(float(r.get("bw") or 0.0) / 2.0 if r.get("kind") == "noise" else 0.1 for r in rows)
    lo, hi = min(fs_) - half, max(fs_) + half
    c = (lo + hi) / 2.0
    if any(abs(f - c) < 0.15 for f in fs_):
        c = c - 0.3 if (hi - lo) < 1.0 else c + 0.15
    span = 2.0 * max(abs(hi - c), abs(lo - c))
    rate = next((r_ for r_ in rates if span <= 0.75 * r_ / 1e6), None)
    if rate is None:
        return f"Signaux trop écartés ({span:.1f} MHz) : {0.75 * max(rates) / 1e6:.0f} MHz au plus en une fois."
    sigs = []
    for i, r in enumerate(rows):
        kind = r.get("kind") or "fm"
        sigs.append(dict(key=f"tx{i}", kind=kind, f=float(r["f"]), lvl=float(r.get("lvl", 0.0)),
                         audio=audio_spec_norm(r.get("audio") or "voice"), k=i, bw=float(r.get("bw") or (0.2 if kind == "noise" else 0)),
                         pilot=DEMO_PILOT if r.get("pilot") and kind in ("fm", "nfm") else 0.0,
                         on=(4.0, 1.0, 0.0) if r.get("burst") else None))
    return c * 1e6, rate, sigs


def tx_cmd(exe, fc_hz, rate, gain=0, amp=False, serial=""):
    """Commande hackrf_transfer d'émission : IQ int8 lu sur l'entrée standard (« -t - »), gain d'émission 0–47 dB."""
    a = [exe, "-t", "-", "-f", str(int(round(fc_hz))), "-s", str(int(rate)), "-x", str(int(max(0, min(47, gain)))),
         "-a", "1" if amp else "0"]
    return a + (["-d", str(serial)] if serial else [])


def iq_ci8(x, scale=None):
    """IQ complexe -> octets int8 entrelacés (format HackRF). Ramené sous la pleine échelle (pas d'écrêtage)."""
    x = np.asarray(x)
    m = float(np.max(np.abs(x))) if len(x) else 1.0
    s = scale if scale is not None else (0.9 / m if m > 0.9 else 1.0)
    out = np.empty(2 * len(x), dtype=np.int8)
    out[0::2] = np.clip(np.round(x.real * s * 127.0), -127, 127)
    out[1::2] = np.clip(np.round(x.imag * s * 127.0), -127, 127)
    return out.tobytes()


# ------------------------------------------------------------------ V8 étape 22 : premier branchement, calibration,
# remonter le temps (Clément : « 1234 !! » sur assistant / calibrer avec le tinySA / remonter le temps / manuel + 8.0).
GAIN_OVF_MAX = 0.001          # au-delà de 0,1 % d'échantillons à pleine échelle : saturation
GAIN_HEADROOM_DB = 6.0        # le plus fort signal doit rester 6 dB sous la pleine échelle
CAL_SNR_DB = 15.0             # un signal sert à la calibration s'il dépasse son bruit de 15 dB des DEUX côtés
CAL_HALF_MHZ = 0.1            # puissance de canal mesurée sur ± 100 kHz (micro FM, porteuse)
CAL_MIN_SIGNALS = 2
REWIND_MINUTES = (0, 1, 3, 5)      # 0 = désactivé (rien gardé en mémoire)
REWIND_FRAME_S = 0.5          # un spectre gardé toutes les 0,5 s (max des trames reçues entre deux)
REWIND_BINS = 1024


def gain_steps(model, key="lna"):
    """Valeurs d'un étage de gain du modèle à essayer (du plus bas au plus haut, 8 au plus)."""
    g = next((x for x in (model or {}).get("gains", []) if x[0] == key), None)
    if g is None:
        return []
    _k, _n, lo, hi, st, _d = g
    vals = list(range(int(lo), int(hi) + 1, max(1, int(st))))
    if len(vals) > 8:
        vals = [vals[int(round(i * (len(vals) - 1) / 7))] for i in range(8)]
    return vals


def auto_gain_pick(rows, ovf_max=GAIN_OVF_MAX, headroom=GAIN_HEADROOM_DB):
    """Essais [dict(gain, ovf, floor, peak)] (dBFS) -> (gain conseillé, raison). Le plus fort sans saturer et avec
    `headroom` dB de marge ; s'ils saturent tous : le plus bas (+ raison « trop fort même au minimum »)."""
    rows = sorted([r for r in rows if r.get("gain") is not None], key=lambda r: r["gain"])
    if not rows:
        return None, "aucun essai"
    ok = [r for r in rows if r.get("ovf", 1.0) <= ovf_max and (r.get("peak") is None or r["peak"] <= -headroom)]
    if not ok:
        clean = [r for r in rows if r.get("ovf", 1.0) <= ovf_max]
        if clean:                                  # rien n'écrête, mais la crête frôle le maximum
            return clean[0]["gain"], "signal très fort : peu de marge, même au plus bas (atténuateur conseillé)"
        return rows[0]["gain"], "sature même au plus bas : éloigne l'antenne ou ajoute un atténuateur"
    best = ok[-1]
    if best is rows[-1]:
        return best["gain"], "gain maximal sans saturer"
    return best["gain"], "le plus haut sans saturer ({} dB de marge)".format(f"{-(best.get('peak') or 0.0):.0f}")


def chan_power(F, L, f, half=CAL_HALF_MHZ, bin_bw_khz=None, enbw=1.0):
    """Puissance d'un canal (dB) : somme des cases à f ± half MHz, ramenée à la largeur de chaque case (bin_bw_khz :
    RBW du tinySA ; 1 case FFT = 1) et divisée par l'ENBW de la fenêtre (Blackman ≈ 1,73 case). None si hors mesure."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    m = (np.abs(F - f) <= half) & np.isfinite(L)
    if m.sum() < 2:
        return None
    p = 10.0 ** (L[m] / 10.0)
    if bin_bw_khz:                                 # chaque point = la puissance dans UNE RBW ; il représente un pas :
        step = float(np.median(np.diff(F[m]))) * 1000.0 if m.sum() > 1 else bin_bw_khz
        p = p * (step / float(bin_bw_khz))         # (audit : avant plafonné à 1 -> −9 dB avec pas 75 / RBW 10 kHz)
    return float(10.0 * np.log10(p.sum() / max(1e-9, enbw)))


def calib_candidates(Ft, Lt, Fs, Ls, rbw_khz, snr=CAL_SNR_DB, half=CAL_HALF_MHZ, enbw=1.73):
    """Signaux vus par le tinySA (Ft, Lt dBm) ET par le SDR (Fs, Ls dBFS) à plus de `snr` dB de leur bruit, dans la
    fenêtre du SDR -> [dict(f, tsa, sdr)] (puissances de canal)."""
    Ft, Lt, Fs, Ls = (np.asarray(x, dtype=float) for x in (Ft, Lt, Fs, Ls))
    if len(Fs) < 16 or len(Ft) < 8:
        return []
    lo, hi = float(Fs.min()) + half, float(Fs.max()) - half
    fl_s, fl_t = float(np.percentile(Ls, 20)), float(np.nanpercentile(Lt, 20))
    out, last = [], -1e9
    order = np.argsort(Ls)[::-1]
    for i in order[:400]:
        f = float(Fs[i])
        if not lo <= f <= hi or Ls[i] < fl_s + snr or any(abs(f - c["f"]) < 2 * half for c in out):
            continue
        mt = np.abs(Ft - f) <= half
        if not mt.any() or float(np.max(Lt[mt])) < fl_t + snr:
            continue
        pt = chan_power(Ft, Lt, f, half, rbw_khz)
        ps = chan_power(Fs, Ls, f, half, None, enbw)
        if pt is not None and ps is not None:
            out.append(dict(f=round(f, 4), tsa=round(pt, 1), sdr=round(ps, 1)))
        if len(out) >= 12:
            break
    return sorted(out, key=lambda c: c["f"])


def sdr_tsa_offset(cands, min_n=CAL_MIN_SIGNALS):
    """Correction dBFS -> dBm du SDR d'après les signaux communs -> dict(offset, spread, n) ou None (pas assez)."""
    d = [c["tsa"] - c["sdr"] for c in cands]
    if len(d) < min_n:
        return None
    med = float(np.median(d))
    return dict(offset=round(med, 1), spread=round(float(np.max(np.abs(np.asarray(d) - med))), 1), n=len(d))


class RewindBuffer:
    """⏪ Les dernières minutes du poste SDR, EN MÉMOIRE seulement : spectres (max par tranche de REWIND_FRAME_S,
    REWIND_BINS cases, float16), son entendu (octets PCM stéréo 48 kHz) et fréquence de A dans le temps."""

    def __init__(self, minutes=3, bytes_per_s=192000):
        self.set_minutes(minutes)
        self.bps = int(bytes_per_s)
        self.frames, self.audio, self.tunes = deque(), deque(), deque()
        self._acc, self._acc_t = None, 0.0

    def set_minutes(self, minutes):
        self.keep = 60.0 * max(0, int(minutes))
        if not self.keep and hasattr(self, "frames"):
            self.clear()

    def _trim(self, now):
        for q in (self.frames, self.audio):
            while len(q) > 1 and q[0][0] < now - self.keep:
                q.popleft()
        while len(self.tunes) > 1 and self.tunes[1][0] < now - self.keep:   # garde le réglage en cours au début
            self.tunes.popleft()

    def push_frame(self, t, F, L):
        if not self.keep:
            return
        F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
        if len(L) > REWIND_BINS:
            k = len(L) // REWIND_BINS
            L = L[: k * REWIND_BINS].reshape(REWIND_BINS, k).max(axis=1)
            F = F[: k * REWIND_BINS].reshape(REWIND_BINS, k).mean(axis=1)
        if self._acc is not None and len(self._acc[1]) == len(L) and abs(self._acc[0][0] - F[0]) < 1e-6:
            self._acc = (F, np.maximum(self._acc[1], L))
        else:
            self._acc = (F, L)
        if t - self._acc_t >= REWIND_FRAME_S:
            self._acc_t = t
            self.frames.append((float(t), self._acc[0].astype(np.float32), self._acc[1].astype(np.float16)))
            self._acc = None
            self._trim(t)

    def push_audio(self, t, b):
        if b and self.keep:
            self.audio.append((float(t), bytes(b)))

    def push_tune(self, t, f, name=""):
        if not self.tunes or abs(self.tunes[-1][1] - f) > 1e-6:
            self.tunes.append((float(t), float(f), str(name or "")))

    def span(self):
        """(début, fin) de ce qui est gardé (s), ou None."""
        ts = [q[0][0] for q in (self.frames, self.audio) if q] + [q[-1][0] for q in (self.frames, self.audio) if q]
        return (min(ts), max(ts)) if ts else None

    def tune_at(self, t):
        """(MHz, nom) de A à l'instant t (le dernier réglage avant t)."""
        out = None
        for tt, f, n in self.tunes:
            if tt > t:
                break
            out = (f, n)
        return out or ((self.tunes[0][1], self.tunes[0][2]) if self.tunes else None)

    def audio_from(self, t0, secs=60.0):
        """Son entendu de t0 à t0 + secs (octets PCM stéréo 16 bits 48 kHz)."""
        out, n = [], 0
        lim = int(secs * self.bps)
        for t, b in self.audio:
            if t + len(b) / self.bps < t0:
                continue
            if n >= lim:
                break
            out.append(b)
            n += len(b)
        return b"".join(out)[:lim]

    def mem_mb(self):
        return (sum(len(b) for _t, b in self.audio) + sum(f.nbytes + l.nbytes for _t, f, l in self.frames)) / 1e6

    def clear(self):
        self.frames.clear()
        self.audio.clear()
        self.tunes.clear()
        self._acc = None


def reconnect_delay(fails):
    """19. Attente avant de relancer un SDR décroché : 3 s, puis 10 s, puis 30 s."""
    return 3.0 if fails <= 1 else (10.0 if fails <= 3 else 30.0)


def _svg_series(series, t_mark, w=900, h=190, unit="dB"):
    """Petit graphique SVG de plusieurs courbes [(nom, couleur, [(t, v)])] avec un trait au moment de l'incident."""
    pts = [p for _n, _c, s in series for p in s if p[1] is not None]
    if len(pts) < 2:
        return ""
    t0 = min(p[0] for p in pts)
    t1 = max(max(p[0] for p in pts), t0 + 1.0)
    v0, v1 = min(p[1] for p in pts), max(p[1] for p in pts)
    if v1 - v0 < 10:
        v0, v1 = (v0 + v1) / 2 - 5, (v0 + v1) / 2 + 5
    ml, mb, mt = 44, 22, 8

    def X(t):
        return ml + (t - t0) / (t1 - t0) * (w - ml - 8)

    def Y(v):
        return mt + (v1 - v) / (v1 - v0) * (h - mt - mb)
    o = [f"<svg viewBox='0 0 {w} {h}' width='100%' style='max-width:{w}px'>",
         f"<rect x='{ml}' y='{mt}' width='{w - ml - 8}' height='{h - mt - mb}' fill='#f7f9fc' stroke='#d8dde8'/>"]
    for k in range(5):
        v = v0 + (v1 - v0) * k / 4
        o.append(f"<text x='{ml - 4}' y='{Y(v) + 4:.0f}' font-size='10' text-anchor='end' fill='#6b7488'>{v:.0f}</text>")
    o.append(f"<text x='{ml}' y='{h - 6}' font-size='10' fill='#6b7488'>{(t0 - t_mark):+.0f} s</text>")
    o.append(f"<text x='{w - 8}' y='{h - 6}' font-size='10' text-anchor='end' fill='#6b7488'>{(t1 - t_mark):+.0f} s</text>")
    if t0 <= t_mark <= t1:
        o.append(f"<line x1='{X(t_mark):.1f}' x2='{X(t_mark):.1f}' y1='{mt}' y2='{h - mb}' stroke='#ff3b30' "
                 "stroke-dasharray='4 3'/>")
    for i, (name, col, s) in enumerate(series):
        segs, cur = [], []
        for t, v in s:
            if v is None:
                if cur:
                    segs.append(cur)
                cur = []
            else:
                cur.append(f"{X(t):.1f},{Y(v):.1f}")
        if cur:
            segs.append(cur)
        for sg in segs:
            if len(sg) > 1:
                o.append(f"<polyline fill='none' stroke='{col}' stroke-width='1.5' points='{' '.join(sg)}'/>")
        o.append(f"<text x='{ml + 8 + i * 110}' y='{mt + 14}' font-size='11' fill='{col}'>■ {html_esc(name)}</text>")
    o.append(f"<text x='4' y='{mt + 10}' font-size='10' fill='#6b7488'>{html_esc(unit)}</text></svg>")
    return "".join(o)


def incident_report_html(doc, tr=None):
    """18. Rapport d'incident autonome (HTML) : quoi, quand, mesures avant / après en courbes, diagnostic, chronologie
    du micro, fichiers (IQ à rejouer)."""
    tr = tr or (lambda x: x)
    e = html_esc
    t = float(doc.get("t") or 0.0)
    tg = doc.get("trigger") or {}
    se = doc.get("series") or {}

    def S(k):
        return [(float(a), None if b is None else float(b)) for a, b in se.get(k, [])]
    p = ["<!doctype html><html><head><meta charset='utf-8'>",
         f"<title>{e(tr('Incident'))} · {e(doc.get('name', ''))}</title>",
         "<meta name='viewport' content='width=device-width,initial-scale=1'><style>",
         "body{font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;color:#1d2433;max-width:1000px;margin:0 auto;padding:24px 18px}",
         "h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:24px 0 8px;border-bottom:2px solid #d8dde8}",
         "table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #e3e7ef;padding:4px 8px;"
         "text-align:left}.muted{color:#6b7488}.bad{color:#c0392b}.warn{color:#b9770e}.ok{color:#1e8449}",
         REPORT_PRO_CSS, "</style></head><body>",
         f"<h1>⚠ {e(tr('Incident'))} : {e(doc.get('name', ''))} · {float(doc.get('freq') or 0):.3f} MHz</h1>",
         f"<p class='muted'>{e(doc.get('when', ''))} · {e(anomaly_text(tg, tr))}"
         + (f" · {e(tr('durée : {} s').format(doc['duration']))}" if doc.get("duration") is not None else "")
         + "</p>"]
    also = doc.get("also") or []
    if also:
        p.append("<p>" + e(tr("Aussi pendant ce temps : ")) + e(" · ".join(anomaly_text(a, tr) for a in also)) + "</p>")
    p.append(f"<h2>{e(tr('Mesures autour du moment (trait rouge)'))}</h2>")
    p.append(_svg_series([(tr("RF"), "#0a84ff", S("rf")), (tr("bruit"), "#8e8e93", S("noise"))], t, unit="dBFS"))
    au = S("audio")
    if any(v is not None for _t, v in au):
        p.append(_svg_series([(tr("son"), "#30a14e", au)], t, h=150, unit="dBFS"))
    dr = S("drift")
    if any(v is not None for _t, v in dr):
        p.append(_svg_series([(tr("dérive"), "#af52de", dr)], t, h=150, unit="kHz"))
    sp = doc.get("spectrum") or {}
    if sp.get("F"):
        p.append(f"<h2>{e(tr('Spectre au moment de l’incident'))}</h2>")
        p.append(_svg_iq_spectrum(sp["F"], sp["L"], float(doc.get("freq") or 0)))
    if doc.get("wf_png"):
        p.append(f"<h2>{e(tr('Waterfall du micro (± 150 kHz, le plus récent en haut)'))}</h2>"
                 f"<img src='{e(doc['wf_png'])}' style='width:100%;max-width:900px;image-rendering:pixelated'>")
    dg = doc.get("diag") or []
    if dg:
        p.append(f"<h2>{e(tr('Diagnostic RF + son'))}</h2><ul>")
        p += [f"<li class='{e(tone)}'>{e(txt)}</li>" for _c, tone, txt in dg]
        p.append("</ul>")
    ev = doc.get("events") or []
    if ev:
        p.append(f"<h2>{e(tr('Chronologie du micro'))}</h2><table><tr><th>{e(tr('Heure'))}</th><th>{e(tr('Quoi'))}</th></tr>")
        p += [f"<tr><td>{e(x.get('when', ''))}</td><td>{e(anomaly_text(x, tr))}</td></tr>" for x in ev]
        p.append("</table>")
    iq = doc.get("iq") or {}
    p.append(f"<h2>{e(tr('Fichiers'))}</h2><ul>")
    if iq.get("file"):
        txt = tr("IQ (SigMF) : {} — {} s, {} MHz autour de {} MHz").format(
            iq["file"], f"{float(iq.get('dur', 0)):.0f}", f"{float(iq.get('rate', 0)) / 1e6:.2f}",
            f"{float(iq.get('center', 0)) / 1e6:.3f}")
        p.append(f"<li>{e(txt)}</li>")
    else:
        p.append(f"<li>{e(tr('Pas d’IQ enregistré : {}').format(iq.get('why') or '—'))}</li>")
    p.append(f"<li>{e(tr('Mesures : mesures.json'))}</li></ul>")
    p.append(f"<p class='muted'>{e(tr('Rejouer : 📡 Moniteur multicanal › Chronologie › ▶ Rejouer, ou Temps réel › Relire un enregistrement.'))}</p>")
    p.append("</body></html>")
    return "\n".join(p)


# ------------------------------------------------------------------ langues (français par défaut, anglais)
# Les textes du programme sont écrits en français. Pour l'anglais, une couche posée sur Qt (install_language) fait
# passer chaque texte affiché par Translator : dictionnaire exact (lang_en.EXACT) + modèles à trous pour les textes
# construits avec des f-strings (lang_en.TEMPLATES : « {} fréquences » → « {} frequencies »). tests/test_i18n.py
# vérifie que tout texte du programme a sa traduction (sinon un nouveau texte resterait en français).
class Translator:
    """tr(texte français) -> texte traduit (inchangé si inconnu). Cache des résultats (textes répétés à chaque
    balayage). Les morceaux variables d'un modèle sont traduits à leur tour (« « Spectre » raccroché » → les
    guillemets, puis « Spectre »)."""

    LETTER = re.compile(r"[A-Za-zÀ-ÿ]")
    SEP = re.compile(r"(\s+[·|—]\s+)")
    LEAD = re.compile(r"([^\w\s«“(\[<{-]+\s+)(\S.*)\Z", re.S)

    def __init__(self, exact=None, templates=None):
        self.exact = dict(exact or {})
        for fr, en in list(self.exact.items()):           # morceaux collés au programme (« \nDécoché : … ») :
            if fr.strip() != fr and fr.strip():           # aussi sans les espaces / retours autour, et ligne à ligne
                self.exact.setdefault(fr.strip(), en.strip())
            a, b = fr.strip().split("\n"), en.strip().split("\n")
            if len(a) > 1 and len(a) == len(b):
                for x, y in zip(a, b):
                    if x.strip() and self.LETTER.search(x):
                        self.exact.setdefault(x.strip(), y.strip())
        self.cache = {}
        self.by_head, self.loose = {}, []
        tpl = dict(templates or {})
        for fr, en in list(tpl.items()):                  # morceaux de phrases : « {} fréq. » (pris dans
            a, b = self.SEP.split(fr), self.SEP.split(en)  # « Cycle {} s · … · {} fréq. »), « ⚠ {} alarme(s) »
            if len(a) > 1 and len(a) == len(b):
                for x, y in zip(a[::2], b[::2]):
                    if x.count("{}") and x.count("{}") == y.count("{}") and x.strip() != y.strip():
                        tpl.setdefault(x.strip(), y.strip())      # (« {} MHz » → « {} MHz » : inutile, trop large)
            elif fr.strip(" ·|—") != fr and fr.strip(" ·|—"):
                tpl.setdefault(fr.strip(" ·|—"), en.strip(" ·|—"))
        for fr, en in tpl.items():
            parts = re.split(r"(\{\})", fr.replace("{{", "\x01").replace("}}", "\x02"))
            lits = [x.replace("\x01", "{").replace("\x02", "}") for x in parts if x != "{}"]
            if sum(len(self.LETTER.findall(x)) for x in lits) < 3:
                continue                                  # « {} ({}) » : trop vague, on ne le traduit pas
            rx = "".join("(.*?)" if x == "{}" else re.escape(x.replace("\x01", "{").replace("\x02", "}"))
                         for x in parts)
            item = (re.compile(rx + r"\Z", re.S), en, sum(len(x) for x in lits),
                    [x.replace("\x01", "{").replace("\x02", "}") for x in parts[::2]], "\n" in fr)
            head = parts[0].replace("\x01", "{").replace("\x02", "}")
            if parts[0] and parts[0] != "{}" and len(head) >= 2:
                self.by_head.setdefault(head[:2], []).append(item)
            else:
                self.loose.append(item)
        for lst in list(self.by_head.values()) + [self.loose]:
            lst.sort(key=lambda it: -it[2])           # le plus précis d'abord

    def __bool__(self):
        return bool(self.exact)

    def __call__(self, s):
        if not isinstance(s, str) or not s or not self.exact:
            return s
        r = self.cache.get(s)
        if r is None:
            r = self._tr(s, 0)
            if "<" in s and re.search(r"</?[a-zA-Z][^<>]*>", s) and r not in self.exact.values():
                r = self.html(">" + s + "<")[1:-1]       # texte riche : on traduit le texte entre les balises
            if len(self.cache) > 60000:
                self.cache.clear()
            self.cache[s] = r
        return r

    def _tr(self, s, depth):
        e = self.exact.get(s)
        if e is not None:
            return e
        if depth > 4 or not self.LETTER.search(s):
            return s
        if "\n" in s:                                     # plusieurs lignes : chacune pour elle
            whole = self._tpl(s, depth, multiline=True)
            if whole is not None:
                return whole
            lines = s.split("\n")
            out = [self._tr(x, depth + 1) for x in lines]
            return "\n".join(out) if out != lines else s
        st = s.strip()
        if st != s and st:                                # espaces autour : on garde les espaces
            t = self._tr(st, depth + 1)
            if t != st:
                i = s.index(st)
                pre = s[:i]
                if st[0] == ":" and t[0] == ":" and pre.endswith(" "):
                    pre = pre[:-1]                        # « … » : suite → « … »: suite (typographie anglaise)
                return pre + t + s[i + len(st):]
        parts = self.SEP.split(s)                         # « 6 fréquences · 2 occupée(s) · … », « … | … »
        split = None
        if len(parts) > 1:
            out = [x if i % 2 else self._tr(x, depth + 1) for i, x in enumerate(parts)]
            if all(o != x or not self.LETTER.search(x) for o, x in zip(out[::2], parts[::2])):
                return "".join(out)                       # chaque morceau traduit
            if out != parts:
                split = "".join(out)
        t = self._tpl(s, depth)
        if t is not None:
            return t
        if split is not None:
            return split
        i = s.find(" : ")                                 # « Libellé : valeur » (typographie française)
        if 0 < i:
            head, tail = s[:i], s[i + 3:]
            h = self.exact.get(head + " :")
            h = h.rstrip() if h else self._tr(head, depth + 1) + ":"
            if h.rstrip(":") != head:
                return h + " " + self._tr(tail, depth + 1)
        m = self.LEAD.match(s)                            # « 📋 Liste » : emoji / symbole devant
        if m:
            t = self._tr(m.group(2), depth + 1)
            if t != m.group(2):
                return m.group(1) + t
        for suf, en_suf in ((" :", ":"), (":", ":"), (" …", " …"), ("…", "…"), (".", "."), (" ?", "?")):
            if s.endswith(suf) and len(s) > len(suf) + 1:  # « Fond des tableaux : » → « Table background: »
                t = self._tr(s[:-len(suf)], depth + 1)
                if t != s[:-len(suf)] or suf == " :":     # « 2A − B : » → « 2A − B: »
                    return t.rstrip(" :") + en_suf
        if s[0].islower():                                # « libre » → comme « Libre », en minuscule
            t = self.exact.get(s[0].upper() + s[1:])
            if t:
                return t[0].lower() + t[1:]
        return s

    @staticmethod
    def _splits(s, lits, first, cap=40):
        """Découpages de s selon les morceaux fixes lits (s = lits[0] {} lits[1] {} … lits[-1]) : d'abord celui
        de la regex (first), puis les autres."""
        yield first
        n = [0]

        def rec(pos, k, acc):
            if n[0] > cap:
                return
            if k == len(lits) - 1:
                if s.endswith(lits[k]) and len(s) - len(lits[k]) >= pos:
                    n[0] += 1
                    yield acc + [s[pos:len(s) - len(lits[k])]]
                return
            j = s.find(lits[k], pos) if lits[k] else pos
            while j >= 0 and n[0] <= cap:
                yield from rec(j + len(lits[k]), k + 1, acc + [s[pos:j]])
                if not lits[k]:
                    return
                j = s.find(lits[k], j + 1)

        if len(lits) > 2 and s.startswith(lits[0]):
            for g in rec(len(lits[0]), 1, []):
                if tuple(g) != tuple(first):
                    yield g

    def _tpl(self, s, depth, multiline=False):
        for it in self.by_head.get(s[:2], []) + self.loose:
            if multiline and not it[4]:
                continue                                  # texte sur plusieurs lignes : modèles sur plusieurs lignes
            m = it[0].match(s)
            if m:
                best = None                               # plusieurs découpages possibles (« {} : {} » avec
                for gs in self._splits(s, it[3], m.groups()):   # deux « : ») : celui qui se traduit le mieux
                    tg = [self._tr(g, depth + 1) for g in gs]
                    miss = sum(1 for g, t in zip(gs, tg) if g == t and self.LETTER.search(g))
                    if best is None or miss < best[0]:
                        best = (miss, tg)
                    if not miss:
                        break
                try:
                    return it[1].format(*best[1])
                except (IndexError, KeyError, ValueError):
                    return None
        return None

    def deep(self, obj):
        """Traduit toutes les chaînes d'une structure (dict / list) : page web, notifications."""
        if isinstance(obj, str):
            return self(obj)
        if isinstance(obj, list):
            return [self.deep(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.deep(v) for k, v in obj.items()}
        return obj

    def html(self, h):
        """Traduit les textes d'un document HTML (entre les balises, et les title="…")."""
        h = re.sub(r">([^<>]+)<", lambda m: ">" + self._tr(m.group(1), 0) + "<", h)
        return re.sub(r'title="([^"]*)"', lambda m: 'title="' + self(m.group(1)) + '"', h)


TR = Translator()                                     # langue active (vide = français : rien à traduire)


def web_page_lang(page, pairs, tr):
    """Page web dans une autre langue : remplacements exacts (lang_en.WEB), puis noms et descriptions des vues.
    -> (page, morceaux introuvables) : un morceau introuvable = la page a changé, la traduction est à revoir."""
    missing = []
    for fr, en in pairs:
        if fr not in page:
            missing.append(fr)
        page = page.replace(fr, en)
    for k, i, t, d in WEB_VIEWS:
        page = page.replace(f'"{k}":["{i}","{t}","{d}"]', f'"{k}":["{i}","{tr(t)}","{tr(d)}"]')
    return page, missing
LANGS = [("fr", "Français"), ("en", "English")]


# ------------------------------------------------------------------ sessions enregistrées (proposées à ▶ Démarrer)
# Un dossier par session : tranches .npz du spectre (SweepRecorder), session.json (liste de fréquences, bandes,
# show, début / fin) et journal.csv (mêmes colonnes que le journal automatique). ⏪ Relecture › Ouvrir une session.
SESSION_DEFAULT = dict(ask=True, rec=True, dir="")
SESSION_JOURNAL_HEAD = ["Date", "Heure", "Nom", "MHz", "dBm", "Événement", "Statut", "Scène", "Groupe", "Spectre",
                        "Note"]


def session_name(stamp, show=""):
    """Nom de dossier d'une session : « 2026-10-29_2015 Mon festival » (caractères interdits sous Windows ôtés)."""
    s = f"{stamp} {show}".strip()
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", unicodedata.normalize("NFKC", s)).strip(" ._")
    return s[:80] or stamp


def session_cfg_norm(c):
    """Réglages « enregistrer la session » lus de la config (valeurs manquantes ou bancales -> défaut)."""
    out = dict(SESSION_DEFAULT)
    if isinstance(c, dict):
        out["ask"] = bool(c.get("ask", True))
        out["rec"] = bool(c.get("rec", True))
        out["dir"] = str(c.get("dir") or "")
    return out


def session_journal_rows(text):
    """journal.csv d'une session -> [(date « AAAA-MM-JJ », heure « HH:MM:SS », texte de l'événement)]."""
    out = []
    for row in csv.reader(io.StringIO(text.lstrip("\ufeff")), delimiter=";"):
        if len(row) < 6 or not re.fullmatch(r"\d{4}-\d\d-\d\d", row[0]) or not re.fullmatch(r"\d\d:\d\d:\d\d", row[1]):
            continue
        mhz = f"  {row[3].replace(',', '.')} MHz" if row[3] not in ("", "—") else ""
        out.append((row[0], row[1], f"{row[1]}  {row[5]}  {row[2]}{mhz}"))
    return out


# Ce qu'on note au journal (demande de Clément : « choisir quoi mettre dans les logs ») : les alarmes se
# déclenchent quand même, seul le journal (tableau, CSV du jour, journal de la session) est filtré.
LOG_KINDS = (
    ("alarm", "⚠ Alarmes : CONFLIT, INTERMOD, ABSENT"),
    ("strong", "⚠ TROP FORT"),
    ("busy", "Fréquence qui s'allume (OCCUPÉ)"),
    ("back", "Retours à la normale (Libre, Retour)"),
    ("unknown", "Signaux inconnus (hors liste)"),
    ("device", "tinySA perdu / retrouvé"),
    ("ops", "Opérations : appel des micros, nouvelle fréquence"),
)


def log_kind(event):
    """Événement du journal -> type (clé de LOG_KINDS)."""
    e = str(event)
    if e in ("CONFLIT", "INTERMOD", "ABSENT"):
        return "alarm"
    if e == "TROP FORT":
        return "strong"
    if e == "OCCUPÉ":
        return "busy"
    if e.startswith(("Libre", "Retour")):
        return "back"
    if e == "INCONNU":
        return "unknown"
    if e.startswith("APPAREIL"):
        return "device"
    return "ops"


def log_kinds_norm(d):
    """Choix lus de la config -> {clé: bool} complet (tout coché par défaut)."""
    d = d if isinstance(d, dict) else {}
    return {k: bool(d.get(k, True)) for k, _t in LOG_KINDS}


def rec_mb_per_hour(points, cycle_s):
    """Place disque estimée d'un enregistrement (Mo / heure) : float16 compressé ≈ 1,3 octet par point."""
    if not points or not cycle_s or cycle_s <= 0:
        return None
    return points * 1.3 * 3600.0 / cycle_s / 1e6



# ------------------------------------------------------------------ ajouter depuis le scan (7.13, idée de Clément)
def scan_peaks(F, L, thr, merge_khz=150.0, wide_mhz=1.5, exclude=(), excl_khz=100.0):
    """Signaux d'un spectre au-dessus de thr (dBm), pour les ajouter à la liste sans les taper :
    zones contiguës au-dessus du seuil, réunies si moins de merge_khz les séparent ; une zone plus large que
    wide_mhz = plateau (TNT, Spectera, bloc numérique). Les fréquences déjà connues (exclude, MHz) à moins de
    excl_khz sont écartées. -> [dict(f MHz (pic, ou centre d'un plateau), level dBm, width kHz, wide bool)],
    triés par fréquence."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    if not len(F):
        return []
    above = np.nonzero(L >= thr)[0]
    if not len(above):
        return []
    zones, start, prev = [], above[0], above[0]
    for k in above[1:]:
        gap = (F[k] - F[prev]) * 1000.0             # points voisins du balayage = même signal (pas grossier),
        if (k != prev + 1 and gap > merge_khz) or gap > 5000.0:    # sauf saut de bande
            zones.append((start, prev))
            start = k
        prev = k
    zones.append((start, prev))
    ex = np.asarray(sorted(float(x) for x in exclude), dtype=float)
    out = []
    for a, z in zones:
        seg = L[a:z + 1]
        width = (F[z] - F[a]) * 1000.0
        wide = width >= wide_mhz * 1000.0
        top = a + np.nonzero(seg >= seg.max() - 1e-9)[0]     # sommet plat (plusieurs points au max) : son milieu
        f = float((F[a] + F[z]) / 2.0) if wide else float(np.mean(F[top]))
        if len(ex) and np.min(np.abs(ex - f)) * 1000.0 <= max(excl_khz, width / 2.0 if wide else 0.0):
            continue
        out.append(dict(f=round(f, 4), level=round(float(seg.max()), 1), width=round(width, 1), wide=bool(wide)))
    return out


# ------------------------------------------------------------------ marqueurs du spectre (7.14, demande de Clément :
# « un marqueur déplaçable, affichable ou non, plus précis qu'à la souris »)
def _valid(F, L):
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    ok = np.isfinite(F) & np.isfinite(L)
    return F[ok], L[ok]


def trace_at(F, L, f):
    """Point de la courbe le plus proche de f -> (MHz, dBm) ou None."""
    F, L = _valid(F, L)
    if not len(F):
        return None
    k = int(np.argmin(np.abs(F - f)))
    return float(F[k]), float(L[k])


def peak_near(F, L, f, span=0.5):
    """Le plus haut point à ±span MHz de f -> (MHz, dBm) ou None."""
    F, L = _valid(F, L)
    m = np.abs(F - f) <= span
    if not m.any():
        return None
    k = int(np.argmax(np.where(m, L, -np.inf)))
    return float(F[k]), float(L[k])


def occupied_width(F, L, f, drop_db=20.0, span=0.5):
    """Bande occupée par le signal le plus fort près de f : de part et d'autre du pic, tant que le niveau reste au-dessus
    de (pic − drop_db). -> (MHz bas, MHz haut, MHz du pic, dBm du pic) ou None."""
    F, L = _valid(F, L)
    o = np.argsort(F)
    F, L = F[o], L[o]
    pk = peak_near(F, L, f, span)
    if pk is None:
        return None
    k = int(np.argmin(np.abs(F - pk[0])))
    lim = pk[1] - drop_db
    a = z = k
    while a > 0 and L[a - 1] >= lim:
        a -= 1
    while z < len(L) - 1 and L[z + 1] >= lim:
        z += 1
    return float(F[a]), float(F[z]), pk[0], pk[1]


def scan_segments(F):
    """Plages réellement mesurées d'un scan TRIÉ (une par bande, coupées aux trous de scan_gaps) -> [(début, fin)]."""
    F = np.asarray(F, dtype=float)
    if not len(F):
        return []
    cuts = [0, *[int(i) for i in scan_gaps(F)], len(F)]
    return [(float(F[a]), float(F[b - 1])) for a, b in zip(cuts[:-1], cuts[1:]) if b > a]


def axis_panels(segs, min_gap=10.0, rel_gap=0.05):
    """Axe des fréquences COUPÉ (dossier de préparation, 7.67.1) : plages mesurées (scan_segments) réunies si
    l'écart entre deux est petit (< max(min_gap MHz, rel_gap × étendue totale)) -> [(début, fin)] = une case par
    groupe ; un grand vide (700 -> 820 MHz) devient une coupure au lieu d'un tiers de l'image."""
    segs = sorted((float(a), float(b)) for a, b in segs if b >= a)
    if not segs:
        return []
    lim = max(min_gap, rel_gap * (segs[-1][1] - segs[0][0]))
    out = [list(segs[0])]
    for a, b in segs[1:]:
        if a - out[-1][1] <= lim:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def covered(x, segs, pad=0.0):
    """Masque : x (MHz, tableau) tombe dans une des plages mesurées segs (± pad MHz)."""
    x = np.asarray(x, dtype=float)
    m = np.zeros(x.shape, dtype=bool)
    for a, b in segs:
        m |= (x >= a - pad) & (x <= b + pad)
    return m


def interp_measured(F, L, x):
    """Niveau de (F, L) TRIÉ aux fréquences x, NaN là où F n'a rien mesuré (hors plage, trou entre deux bandes) :
    jamais d'interpolation par-dessus un trou (audit 7.64 : « disparu » annoncé dans une zone jamais mesurée)."""
    x = np.asarray(x, dtype=float)
    v = np.interp(x, F, L) if len(F) else np.full(x.shape, np.nan)
    return np.where(covered(x, scan_segments(F)), v, np.nan)


def compare_spectra(F1, L1, F2, L2, thr, margin=10.0):
    """Comparer deux spectres (ex. max hold de la balance et du show) : signaux au-dessus de thr présents dans l'un
    et pas dans l'autre (au moins margin dB de plus). -> (nouveaux dans 1, disparus = présents dans 2), listes de
    scan_peaks. Seulement là où les DEUX ont mesuré (7.65 : les trous entre bandes ne sont plus interpolés)."""
    F1, L1 = _valid(F1, L1)
    F2, L2 = _valid(F2, L2)
    if not len(F1) or not len(F2):
        return [], []
    o1, o2 = np.argsort(F1), np.argsort(F2)
    F1, L1, F2, L2 = F1[o1], L1[o1], F2[o2], L2[o2]
    o21, o12 = interp_measured(F2, L2, F1), interp_measured(F1, L1, F2)
    with np.errstate(invalid="ignore"):
        a1 = np.where(np.isfinite(o21) & (L1 - o21 >= margin), L1, -999.0)
        a2 = np.where(np.isfinite(o12) & (L2 - o12 >= margin), L2, -999.0)
    return scan_peaks(F1, a1, thr), scan_peaks(F2, a2, thr)


def _zone(p, pad):
    w = float(p.get("width") or 0.0) / 2000.0
    return (p["f"] - w - pad, p["f"] + w + pad)


def scan_changes(FA, LA, FB, LB, thr, margin=10.0, step_db=6.0):
    """📸 7.63 « avant / après » : A = scan d'avant (ex. avant l'installation des micros), B = après. -> liste triée
    par fréquence de dict(kind new|gone|up|down, f MHz, before dBm ou None, after dBm ou None, delta dB) :
    new = apparu (≥ margin dB au-dessus d'avant), gone = disparu, up / down = présent les deux fois mais monté /
    baissé d'au moins step_db. « apparu » = sous le seuil avant ; « disparu » = sous le seuil après. Seulement là où les
    deux ont mesuré (trous entre bandes exclus). 7.65 (audit) : un signal n'est écarté comme « déjà compté » que si SA
    zone recouvre celle d'un événement déjà trouvé (avant : tout ce qui était à moins de 300 kHz)."""
    new, gone = compare_spectra(FB, LB, FA, LA, thr, margin)
    FA, LA = _valid(FA, LA)
    FB, LB = _valid(FB, LB)
    if not len(FA) or not len(FB):
        return []
    oa, ob = np.argsort(FA), np.argsort(FB)
    FA, LA, FB, LB = FA[oa], LA[oa], FB[ob], LB[ob]
    pad = 0.5 * min(float(np.median(np.diff(FA))) if len(FA) > 1 else 0.0,
                    float(np.median(np.diff(FB))) if len(FB) > 1 else 0.0)
    out, zones = [], []
    for p in new:                                 # présent avant (au-dessus du seuil) = « plus fort », pas « apparu »
        bf = float(interp_measured(FA, LA, [p["f"]])[0])
        out.append(dict(kind="new" if bf < thr else "up", f=p["f"], before=bf, after=p["level"]))
        zones.append(_zone(p, pad))
    for p in gone:
        af = float(interp_measured(FB, LB, [p["f"]])[0])
        out.append(dict(kind="gone" if af < thr else "down", f=p["f"], before=p["level"], after=af))
        zones.append(_zone(p, pad))

    def overlaps(z):
        return any(z[0] <= b and a <= z[1] for a, b in zones)
    for F1, L1, F2, L2, kind in ((FB, LB, FA, LA, "up"), (FA, LA, FB, LB, "down")):
        for p in scan_peaks(F1, L1, thr):
            z = _zone(p, pad)
            if overlaps(z):
                continue
            other = float(interp_measured(F2, L2, [p["f"]])[0])
            if not np.isfinite(other):            # pas mesuré dans l'autre scan : on ne dit rien
                continue
            if p["level"] - other >= step_db:
                b_, a_ = (other, p["level"]) if kind == "up" else (p["level"], other)
                out.append(dict(kind=kind, f=p["f"], before=b_, after=a_))
                zones.append(z)
    for x in out:
        x["delta"] = None if x["before"] is None or x["after"] is None else round(x["after"] - x["before"], 1)
    return sorted(out, key=lambda x: x["f"])


CHANGE_LABELS = {"new": "🆕 apparu", "gone": "➖ disparu", "up": "↑ plus fort", "down": "↓ plus faible"}


def copy_name(name, taken):
    """⧉ 7.63 : nom d'une copie : « X (copie) », puis « X (copie 2) »… jamais un nom déjà pris."""
    base = re.sub(r"\s*\(copie(?: \d+)?\)$", "", str(name or "").strip()) or "Copie"
    taken = set(taken)
    cand, k = f"{base} (copie)", 2
    while cand in taken:
        cand, k = f"{base} (copie {k})", k + 1
    return cand


HIST_MAX = 1000
HIST_WHAT = {"add": "ajoutée", "del": "retirée", "freq": "fréquence", "name": "renommée", "status": "statut",
             "layer": "scène › groupe"}


def watch_rows(watch):
    """🕘 7.63 : ce qu'on suit dans l'historique : (nom, MHz au kHz, statut, scène › groupe) de chaque fréquence."""
    return [(str(w.get("name") or ""), round(float(w.get("freq") or 0.0), 3), str(w.get("status") or ""),
             " › ".join(x for x in (w.get("scene") or "", w.get("group") or "") if x)) for w in watch or []]


def watch_diff(old, new):
    """🕘 Changements entre deux watch_rows : apparié d'abord par (nom, MHz), puis par nom (fréquence changée), puis par
    MHz (renommée) ; le reste = ajoutée / retirée. -> [dict(what, name, old, new)]."""
    old, new = list(old), list(new)
    out, used_o, used_n = [], set(), set()

    def pair(key):
        idx = {}
        for i, r in enumerate(old):
            if i not in used_o:
                idx.setdefault(key(r), []).append(i)
        for j, r in enumerate(new):
            if j in used_n:
                continue
            lst = idx.get(key(r))
            if lst:
                i = lst.pop(0)
                used_o.add(i)
                used_n.add(j)
                o = old[i]
                if o[1] != r[1]:
                    out.append(dict(what="freq", name=r[0], old=f"{o[1]:.3f}", new=f"{r[1]:.3f}"))
                if o[0] != r[0]:
                    out.append(dict(what="name", name=r[0], old=o[0], new=r[0]))
                if o[2] != r[2]:
                    out.append(dict(what="status", name=r[0], old=o[2], new=r[2]))
                if o[3] != r[3]:
                    out.append(dict(what="layer", name=r[0], old=o[3], new=r[3]))
    pair(lambda r: (r[0], r[1]))
    pair(lambda r: r[0])
    pair(lambda r: r[1])
    for i, o in enumerate(old):
        if i not in used_o:
            out.append(dict(what="del", name=o[0], old=f"{o[1]:.3f}", new=""))
    for j, r in enumerate(new):
        if j not in used_n:
            out.append(dict(what="add", name=r[0], old="", new=f"{r[1]:.3f}"))
    return out


def history_norm(h, limit=HIST_MAX):
    """Historique lu (config / show) -> liste propre [{t, who, what, name, old, new}], les `limit` derniers."""
    out = []
    for x in h if isinstance(h, list) else []:
        if isinstance(x, dict) and x.get("what") in HIST_WHAT:
            try:
                t = float(x.get("t") or 0.0)
            except (TypeError, ValueError):
                continue
            out.append(dict(t=t, who=str(x.get("who") or "")[:40], what=x["what"], name=str(x.get("name") or "")[:60],
                            old=str(x.get("old") or "")[:80], new=str(x.get("new") or "")[:80]))
    return out[-limit:]


SECRET_WEB = ("pin", "password", "tech")


def config_public(cfg):
    """📦 7.63 : config SANS secrets (jetons ntfy / Telegram, PIN, mots de passe de la page web) pour un envoi."""
    out = {k: v for k, v in (cfg or {}).items() if k != "notify"}
    if isinstance(out.get("web"), dict):
        out["web"] = {k: v for k, v in out["web"].items() if k not in SECRET_WEB}
    return out


def bundle_pick(files, now, days=7.0, max_mb=60.0):
    """📦 Fichiers à mettre dans la sauvegarde : files = [(chemin, taille octets, date modif)] -> chemins des fichiers
    des `days` derniers jours, les plus récents d'abord, jusqu'à max_mb en tout."""
    keep, total = [], 0
    for path, size, mt in sorted(files, key=lambda x: -x[2]):
        if now - mt > days * 86400.0:
            continue
        if total + size > max_mb * 1e6:
            continue
        keep.append(path)
        total += size
    return keep


def store_occupancy(store, freqs, thr, hour_of, win=0.1):
    """Occupation de chaque fréquence (MHz) par heure, à partir des balayages d'un SweepStore : à chaque balayage,
    occupée si le niveau à ±win MHz atteint thr. hour_of(t) -> heure (0-23). -> {heure: (n balayages par
    fréquence np.array, n occupés np.array)}."""
    freqs = np.asarray(freqs, dtype=float)
    out = {}
    for b, ts in store.t.items():
        for t, (f, l) in zip(ts, store.d[b]):
            if not len(f):
                continue
            inb = (freqs >= f[0] - win) & (freqs <= f[-1] + win)
            if not inb.any():
                continue
            h = int(hour_of(t))
            n, k = out.setdefault(h, (np.zeros(len(freqs)), np.zeros(len(freqs))))
            for i in np.nonzero(inb)[0]:
                m = np.abs(f - freqs[i]) <= win
                v = float(np.max(l[m])) if m.any() else float(l[int(np.argmin(np.abs(f - freqs[i])))])
                n[i] += 1
                k[i] += v >= thr
    return out


# ------------------------------------------------------------------ parcours et niveaux d'affichage (7.13)
UI_LEVELS = (("ultra", "🟢 Ultra simple : spectre, liste et alarmes"),
             ("simple", "🔵 Simple : + réglages essentiels, journal, scènes / groupes"),
             ("expert", "🎛 Expert : tous les réglages"))
# 7.46 (revue UX : « une seule porte d'entrée ») : 4 familles dans la barre du haut, à la place du parcours ①…⑥ et
# des sections de ☰ Plus. Famille = (clé, texte du bouton, bulle, menu [(texte, méthode)] ; (None, None) = séparateur).
# Les numéros ① ② ③ restent ceux des 3 cartes de l'accueil (tinySA, micros, surveiller).
STEPS = (
    ("prep", "📋 Préparer", "Avant le show : scanner le lieu, ta liste de fréquences (importer, ajouter, nommer),\n"
     "le planning des plateaux et les états.",
     (("🧭 Assistant « nouveau show » (pas à pas)…", "open_wizard"),
      ("§1. Scanner le lieu", None),
      ("▶ Scanner ici (pics remis à zéro)", "step_scan"),
      ("📏 Scan pour la coordination (RBW fine, gardé avec sa RBW)…", "open_coord_scan"),
      ("📍 Scans par lieu (plusieurs scènes, comparer, rapport)…", "open_sites"),
      ("📺 Canaux TNT du lieu et émetteurs proches…", "open_tnt"),
      ("§2. Ma liste de fréquences", None),
      ("📥 Importer une liste ou un plan (EazyRF, WWB, WSM, Wisycom, DPA, CSV…)…", "import_watch"),
      ("⌨ Ajouter des micros (saisie express)…", "add_watch_dialog"), ("📋 Coller une liste…", "paste_watch"),
      ("📡 Ajouter depuis le scan (au-dessus d'un seuil)…", "open_scan_add"),
      ("📶 Ajouter un bloc Spectera / WMAS (canal 6 / 8 MHz)…", "add_block_dialog"),
      ("✏ Nommer la sélection (HF 1, HF 2…)…", "quick_name_dialog"),
      ("Mon vocabulaire (noms proposés)…", "edit_vocab"),
      ("🔗 Plan suivi (EazyRF, WWB, WSM, Wisycom, DPA)…", "ezrf_follow_info"),
      ("📤 Exporter les fréquences (par scène / groupe)…", "export_by_scene"),
      ("❓ Doit émettre / doit rester libre : c'est quoi ?", "status_help"),
      ("§3. Coordination (avancé)", None),
      ("🔒 Outils de coordination cachés : les afficher…", "show_coord_setting"),
      ("🪄 Trouver N fréquences compatibles (coordination auto)…", "open_coord"),
      ("🧮 Vérifier le plan de fréquences (compatibilité)…", "open_plan_check"),
      ("⚡ Intermodulation (2 / 3 / 5 TX)…", "open_intermod"),
      ("🎛 Profils d'appareil (filtre récepteur)…", "open_rx_profiles"),
      ("§4. Organiser le show", None),
      ("🎬 Planning des plateaux (qui joue quand)…", "open_planning"),
      ("📸 États (basculer de plan d'un clic)…", "open_states"),
      ("🖨 Dossier de préparation (PDF à imprimer / envoyer)…", "export_prep"))),
    ("show", "🎚 Surveiller", "Pendant le show : démarrer, vérifier que tout est prêt, mode Show plein écran, appel des\n"
     "micros, mur pour un 2ᵉ écran, fréquence de secours, alertes sur téléphone.",
     (("§Avant d'ouvrir les portes", None),
      ("⚡ Préréglages rapides (festival, salle, nuit…)…", "open_presets"),
      ("✅ Prêt pour le show ? (tout vérifier)…", "open_ready"),
      ("🩺 Diagnostic RF : ce qui cloche dans la mesure…", "open_rf_diag"),
      ("🎤 Appel des micros (line check)…  Ctrl+L", "open_linecheck"),
      ("§Pendant le show", None),
      ("▶ Démarrer la surveillance", "step_monitor"),
      ("🖥 Mode Show (plein écran, l'essentiel)  F10", "open_show_mode"),
      ("🧱 Mur de fréquences (2ᵉ écran)", "open_wall"),
      ("🗺 Carte du site (scènes, tinySA, carte de chaleur)…", "open_map"),
      ("§Un micro est brouillé ?", None),
      ("🆘 Remplacer ce micro (3 propositions, 1 clic)…", "open_replace"),
      ("🆘 Fréquence de secours (recherche détaillée)…", "open_rescue"),
      ("🔎 Chasse au brouilleur (bip qui suit le niveau)…", "open_hunt"),
      ("§À distance et la nuit", None),
      ("📣 Alertes téléphone et page web…", "open_alerts"),
      ("📱 QR code de la page web (pour l'équipe)…", "open_qr"),
      ("🌙 Mode festival (nuit complète, bilan chaque jour)…", "open_festival"))),
    ("after", "📊 Analyser", "Après le show : revoir ce qui s'est passé, rapport, occupation par heure, scans.",
     (("§Revoir le show", None),
      ("🌅 Résumé de la nuit (en un coup d'œil)…", "open_night_summary"),
      ("🔁 Perturbations qui reviennent (même heure, plusieurs jours)…", "open_recurring"),
      ("🕘 Historique des modifications (qui a changé quoi)…", "open_history"),
      ("⏪ Relecture : revoir le spectre / une session…", "open_replay"),
      ("📊 Occupation par heure (créneaux à risque)…", "open_occupancy"),
      ("📄 Rapport de show…", "make_report"),
      ("📸 Comparer avant / après (ce qui a changé)…", "open_before_after"),
      ("§Scans des autres logiciels", None),
      ("📏 Importer un scan WSM / WWB comme référence…", "import_scan_as_ref"),
      ("🔁 Convertir / exporter un scan (WSM, WWB, CSV…)…", "open_scan_convert"))),
    ("hw", "🔌 Matériel", "Le matériel : plusieurs tinySA, tinySA en réseau (Raspberry Pi), relais, réglages de\n"
     "mesure, calibration, générateur, diagnostic.",
     (("§Mes tinySA", None),
      ("📡 Mes tinySA et les scènes qu'ils surveillent…", "open_devices"),
      ("🗺 Carte : placer mes tinySA et mes scènes…", "open_map"),
      ("➕ Plusieurs tinySA et leurs noms…", "open_devs_settings"),
      ("⚖ Calibrer les autres tinySA sur le 1er…", "start_calib"),
      ("§En réseau (Raspberry Pi, autre PC)", None),
      ("🌐 tinySA en réseau : adresses enregistrées…", "open_net_profiles"),
      ("📡 Relais réseau : partager le tinySA de CE PC…", "open_relay"),
      ("§Mesure et dépannage", None),
      ("🎛 Réglages de mesure (finesse, préampli, atténuateur)…", "open_measure"),
      ("🩺 Diagnostic RF automatique (bruit, saturation, seuils)…", "open_rf_diag"),
      ("📡 Mode émission (générateur : tester un récepteur)…", "open_emit"),
      ("🩺 Diagnostic tinySA (fichier pour le support)…", "open_diag"),
      ("📦 Tout envoyer pour un dépannage (ZIP)…", "export_bundle"))),
)
# anciennes clés du parcours (tutos, tests) -> famille
STEP_ALIAS = dict(scan="prep", list="prep", plan="prep", im="prep")
STEP_DEFAULT = {}
# Outils de coordination : cachés par défaut (7.43, Clément : « toute la partie coord je préfère la garder en caché pour
# moi, on peut laisser la fréquence de secours ») ; ⚙ › Général › « Outils de coordination (avancé) » les remontre.
COORD_METHODS = ("open_coord", "open_plan_check", "open_rx_profiles", "open_intermod", "open_intermod_for")
COORD_STEPS = ()
COORD_TOURS = ("coord",)
STEP_HINTS = {
    "prep": "📋 Scanne le lieu quelques minutes, puis entre tes fréquences (import, scan ou à la main).",
    "show": "🎚 Vert = OK. Une alarme sonne si un micro se tait ou si un signal arrive sur une réserve.",
    "after": "📊 Relecture : revois n'importe quel moment de la session enregistrée.",
    "hw": "🔌 Plusieurs tinySA, réseau, mesure : ce qui concerne le matériel.",
}
STATUS_HELP = ("Chaque fréquence de ta liste a un STATUT, qui dit ce que tu attends d'elle :\n\n"
               "• « En service » = DOIT ÉMETTRE : un de tes micros / ears est censé être là. S'il se tait trop\n"
               "  longtemps → alarme ⚠ ABSENT (pile vide, micro éteint…). Raccourci : Ctrl+E.\n\n"
               "• « Libre » = DOIT RESTER LIBRE : une réserve, une fréquence de secours. Au moindre signal dessus\n"
               "  → alarme ⚠ CONFLIT (quelqu'un d'autre émet là).\n\n"
               "• Sans statut : simple surveillance (occupé / libre), pas d'alarme.\n\n"
               "Pour changer : double-clic sur la colonne « Statut », ou sélectionne des lignes puis Ctrl+1…9.")

def zoom_points(span_mhz, want=None, most=1000, step_khz=10.0, cap=290):
    """Points du zoom live. want = nombre fixe choisi (None = auto). Auto : un pas d'environ step_khz (assez
    fin pour voir la porteuse d'un micro), jamais plus de cap points (une seule commande tinySA = rapide) ni
    plus que most (points choisis pour les bandes), au moins MIN_PTS. Zoomer = moins de points, pas plus."""
    if want:
        return max(2, int(want))
    n = int(math.ceil(max(0.0, float(span_mhz)) * 1000.0 / float(step_khz) - 1e-9)) + 1
    return max(MIN_PTS, min(int(cap), max(MIN_PTS, int(most)), n))


# ------------------------------------------------------------------ mode festival (nuit complète)
FESTIVAL_DEFAULT = dict(on=False, autostart=True, nosleep=True, daily=True, hour=9, last="", was_running=False,
                        guard=True)


def festival_cfg_norm(d):
    """Réglages du mode festival lus de la config (valeurs manquantes ou bancales -> défaut)."""
    d = d if isinstance(d, dict) else {}
    out = dict(FESTIVAL_DEFAULT)
    for k in ("on", "autostart", "nosleep", "daily", "was_running", "guard"):
        if k in d:
            out[k] = bool(d[k])
    try:
        out["hour"] = min(23, max(0, int(d.get("hour", out["hour"]))))
    except (TypeError, ValueError):
        pass
    out["last"] = str(d.get("last", "") or "")[:10]
    return out


# ------------------------------------------------------------------ garde (relance si l'appli plante ou se fige)
GUARD_HANG_S = 90.0      # plus de battement de cœur depuis 90 s = appli figée -> on la ferme et on la relance
GUARD_GRACE_S = 180.0    # au démarrage, le 1er battement peut tarder (gros show, PC lent)
GUARD_BEAT_S = 5.0       # l'appli écrit son battement toutes les 5 s


def guard_action(code, hb_age, up_s, hang_s=GUARD_HANG_S, grace_s=GUARD_GRACE_S):
    """Que fait la garde ? code = code de sortie de l'appli (None = tourne encore), hb_age = âge du dernier
    battement (s, None = pas encore battu), up_s = depuis quand elle tourne.
    -> "stop" (fermée exprès, code 0), "restart" (plantée), "kill" (figée), "wait"."""
    if code is not None:
        return "stop" if code == 0 else "restart"
    if hb_age is None:
        return "kill" if up_s >= grace_s else "wait"
    return "kill" if hb_age >= hang_s else "wait"


def guard_delay(starts, now, burst=5, window=600.0, pause=300.0):
    """Attente avant une relance : 3 s, sauf si elle a déjà été relancée `burst` fois dans les `window` dernières
    secondes (elle plante en boucle : config abîmée, tinySA qui fait tout tomber…) -> pause de 5 min."""
    recent = [t for t in starts if now - t < window]
    return pause if len(recent) >= burst else 3.0


def festival_due(ymd, hour_now, cfg):
    """Le bilan quotidien est-il à faire ? ymd = « AAAA-MM-JJ » d'aujourd'hui, hour_now = heure locale.
    Une fois par jour, dès l'heure choisie (rattrapé plus tard si le PC dormait à l'heure pile)."""
    return (bool(cfg.get("on") and cfg.get("daily")) and int(hour_now) >= int(cfg.get("hour", 9))
            and cfg.get("last", "") != ymd)


def alarm_stats(alarms, since):
    """Alarmes commencées depuis `since` (horodatage, s) -> {type: nombre}."""
    out = {}
    for a in alarms:
        if float(a.get("t0") or 0) >= since:
            out[a["kind"]] = out.get(a["kind"], 0) + 1
    return out


def festival_text(site, stats, open_n, unacked, nfreq, running, run_h, devs_ok, devs, report=""):
    """Message du bilan quotidien (téléphone) -> (titre, corps, tout va bien ?)."""
    ok = bool(running) and not open_n and devs_ok >= devs
    if not running:
        head = "⚠ Surveillance arrêtée"
    elif devs_ok < devs:
        head = "⚠ tinySA hors ligne"
    elif open_n:
        head = f"⚠ {open_n} alarme(s) en cours"
    else:
        head = "✔ Tout va bien"
    title = f"{head} — {site}" if site else head
    lines = []
    if stats:
        lines.append("Dernières 24 h : " + " · ".join(f"{k} : {n}" for k, n in sorted(stats.items())))
    else:
        lines.append("Dernières 24 h : aucune alarme.")
    if unacked:
        lines.append(f"Non acquittée(s) : {unacked}")
    if running:
        lines.append(f"{nfreq} fréquence(s) surveillée(s) · depuis {run_h:.0f} h")
    if devs > 1 or devs_ok < devs:
        lines.append(f"tinySA en ligne : {devs_ok} / {devs}")
    if report:
        lines.append(f"Rapport : {report}")
    return title, "\n".join(lines), ok


# ------------------------------------------------------------------ points par balayage « Auto »
AUTO_STEPS_KHZ = (10, 12.5, 20, 25, 40, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 1000)
# choix « Auto » de « Points / balayage » : (donnée du menu, texte, points visés par cycle). Les nombres fixes sont > 0.
AUTO_POINTS = ((-1, "⚡ Auto rapide", 2000), (0, "⚡ Auto équilibré", 4500), (-2, "⚡ Auto détaillé", 9000))
AUTO_BUDGET = {k: b for k, _t, b in AUTO_POINTS}


def auto_scan_step(total_mhz, rbw_khz=None, budget=4500, step_min=10.0):
    """Pas « Auto » des bandes (kHz) : le plus fin qui garde le cycle rapide.
    total_mhz = largeur totale balayée (toutes les bandes cochées) ; budget = points visés par cycle (≈ 10 commandes
    de 450 points : quelques secondes sur un tinySA Ultra à jour) ; jamais plus fin que step_min (10 kHz : une porteuse
    de micro occupe ~200 kHz, plus fin ne montre rien de plus et ralentit). RBW imposée : pas ≤ RBW, sinon un
    signal étroit tombé entre deux points peut passer inaperçu (lisibilité avant vitesse). Arrondi à un pas « rond »."""
    raw = max(float(step_min), float(total_mhz) * 1000.0 / max(1, int(budget)))
    step = next((x for x in AUTO_STEPS_KHZ if x >= raw - 1e-9), AUTO_STEPS_KHZ[-1])
    if rbw_khz and step > rbw_khz:
        step = max([x for x in AUTO_STEPS_KHZ if x <= rbw_khz] or [AUTO_STEPS_KHZ[0]])
    return step


# ------------------------------------------------------------------ sons de l'appli (sortie audio au choix)
SOUND_DEFAULT = dict(device="", volume=70, style="tones",      # device "" = sortie par défaut de Windows
                     repeat=30, confirm=3, occ_beep=False)      # critiques rejouées / CONFLIT confirmé après / bip « occupé »
ALARM_REPEATS = ((10, "toutes les 10 s"), (30, "toutes les 30 s"), (60, "toutes les minutes"),
                 (300, "toutes les 5 minutes"), (0, "jamais (un seul son)"))
SOUND_STYLES = (("tones", "🎵 Carillons doux (sortie audio au choix)"), ("classic", "📟 Bips nets (anciens sons)"),
                ("beep", "🔔 Bip de Windows"))
# 8.0.3 (Clément : « les sons d'alarme font chippppp ») : notes plus graves, timbre de carillon (harmoniques, attaque
# douce, son qui résonne et s'éteint) au lieu de bips purs très aigus. Les anciens restent au choix (« Bips nets »).
ALARM_TONES = {2: [(784, 170), (0, 40), (988, 170), (0, 40), (1175, 520)],     # critique : 3 notes qui montent
               1: [(880, 260), (0, 50), (698, 520)],                             # normale : « ding-dong »
               0: [(784, 420)]}                                                  # info : 1 note
TONE_OK = [(1047, 160)]                                                          # appel des micros : ✓
ALARM_TONES_CLASSIC = {2: [(1320, 140), (0, 60), (1320, 140), (0, 60), (1760, 260)],
                       1: [(990, 160), (0, 80), (990, 160)],
                       0: [(880, 110)]}
TONE_OK_CLASSIC = [(1500, 70)]


def sound_cfg_norm(d):
    """Réglages du son lus de la config (valeurs manquantes ou bancales -> défaut)."""
    d = d if isinstance(d, dict) else {}
    out = dict(SOUND_DEFAULT)
    out["device"] = str(d.get("device", "") or "")[:200]
    try:
        out["volume"] = min(100, max(0, int(d.get("volume", out["volume"]))))
    except (TypeError, ValueError):
        pass
    if d.get("style") in dict(SOUND_STYLES):
        out["style"] = d["style"]
    if d.get("repeat") in dict(ALARM_REPEATS):
        out["repeat"] = int(d["repeat"])
    try:
        out["confirm"] = min(60, max(0, int(d.get("confirm", out["confirm"]))))
    except (TypeError, ValueError):
        pass
    out["occ_beep"] = bool(d.get("occ_beep", False))
    return out


# 7.56 : ⚡ Préréglages rapides (revue UX : « profils de configuration rapides »). Un clic règle d'un coup les seuils, la
# mesure, la rémanence et les alarmes pour une situation type ; la fenêtre montre AVANT ce qui va changer.
# Réglages : thr_auto (seuils auto), auto_occ / auto_weak (marges dB), points (donnée de AUTO_POINTS), persist
# (rémanence, balayages), absent (s), confirm (CONFLIT confirmé après, s), repeat (son rejoué, s, 0 = jamais),
# strong / strong_lvl (alerte trop fort), hold (pics gardés). « after » = fenêtre proposée ensuite (méthode).
QUICK_PRESETS = (
    ("festival", "🎪 Festival plein air",
     "Beaucoup de monde, des talkies, de la télé, des équipes qui arrivent avec leur matériel : seuils automatiques "
     "un peu larges, une occupation doit durer 3 s pour sonner, rémanence pour voir passer les brouilleurs.",
     dict(thr_auto=True, auto_occ=12, auto_weak=6, points=0, persist=10, absent=20, confirm=3, repeat=30,
          strong=True, strong_lvl=-25.0, hold=True), None),
    ("salle", "🎭 Salle / théâtre",
     "Lieu fermé et calme, émetteurs près de l'antenne : détection plus sensible, mesure plus fine, alarmes plus "
     "rapides ; l'alerte « trop fort » monte un peu (les micros sont tout près).",
     dict(thr_auto=True, auto_occ=10, auto_weak=5, points=-2, persist=5, absent=10, confirm=2, repeat=30,
          strong=True, strong_lvl=-20.0, hold=True), None),
    ("nuit", "🌙 Nuit de surveillance",
     "Personne devant l'écran : balayage rapide, une occupation doit durer 5 s pour sonner (moins de fausses "
     "alertes), son rejoué toutes les minutes, pas de rémanence (moins de processeur). Pense au mode festival : "
     "relance automatique, PC qui ne s'endort pas, bilan chaque matin.",
     dict(thr_auto=True, auto_occ=12, auto_weak=6, points=-1, persist=0, absent=30, confirm=5, repeat=60,
          strong=True, strong_lvl=-25.0, hold=True), "open_festival"),
    ("scan", "🔭 Scan de repérage",
     "Avant le show, pour trouver la place libre : mesure détaillée, pics gardés, rémanence longue, alarmes "
     "discrètes (un seul son, pas d'alerte « trop fort »). Ensuite : 📋 Préparer › Ajouter depuis le scan.",
     dict(thr_auto=True, auto_occ=10, auto_weak=5, points=-2, persist=20, absent=60, confirm=5, repeat=0,
          strong=False, strong_lvl=-25.0, hold=True), None),
)
PRESET_LABELS = (("thr_auto", "Seuils automatiques"), ("auto_occ", "Occupé dès"), ("auto_weak", "Faible dès"),
                 ("points", "Points par balayage"), ("persist", "Rémanence"), ("absent", "TX absent après"),
                 ("confirm", "Conflit confirmé après"), ("repeat", "Alarme rejouée"),
                 ("strong", "Alerte « trop fort »"), ("hold", "Pics gardés"))


def user_presets_norm(lst):
    """7.57 : préréglages perso [{name, desc, st}] lus de la config / d'un show / d'un profil : noms uniques (≤ 40
    caractères), au plus 30, réglages manquants ou bancals = ceux du préréglage « festival »."""
    base = QUICK_PRESETS[0][3]
    out, seen = [], set()
    for d in lst if isinstance(lst, list) else []:
        if not isinstance(d, dict):
            continue
        name = " ".join(str(d.get("name") or "").split())[:40]
        if not name or name.lower() in seen:
            continue
        st0 = d.get("st") if isinstance(d.get("st"), dict) else {}
        st = {}
        for k, v in base.items():
            x = st0.get(k, v)
            if isinstance(v, bool):
                x = bool(x)
            elif isinstance(v, float):
                x = float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else v
            else:
                x = int(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else v
            st[k] = x
        if st["repeat"] not in dict(ALARM_REPEATS):
            st["repeat"] = base["repeat"]
        if st["points"] not in [d_ for d_, *_ in AUTO_POINTS]:
            st["points"] = base["points"]
        seen.add(name.lower())
        out.append(dict(name=name, desc=str(d.get("desc") or "")[:300], st=st))
        if len(out) >= 30:
            break
    return out


def user_presets_merge(old, new):
    """Préréglages perso du PC + ceux d'un show ou d'un profil (à nom égal, le nouveau gagne)."""
    new_ = user_presets_norm(new)
    names = {p["name"].lower() for p in new_}
    return user_presets_norm([p for p in user_presets_norm(old) if p["name"].lower() not in names] + new_)


def presets_all(user=None):
    """Préréglages intégrés + perso (clé « u:nom », nom précédé de ⭐), au format de QUICK_PRESETS."""
    return tuple(QUICK_PRESETS) + tuple(("u:" + p["name"], "⭐ " + p["name"], p["desc"], p["st"], None)
                                        for p in user_presets_norm(user))


def quick_preset(key, user=None):
    """(clé, nom, explication, réglages, fenêtre proposée ensuite) du préréglage (intégré ou perso), ou None."""
    return next((p for p in presets_all(user) if p[0] == key), None)


def preset_value_text(k, v, cfg=None):
    """Texte lisible d'un réglage de préréglage (« bruit + 12 dB », « 10 balayages », « toutes les 30 s »…)."""
    cfg = cfg or {}
    if v is None:
        return "—"
    if k in ("thr_auto", "hold"):
        return "oui" if v else "non"
    if k in ("auto_occ", "auto_weak"):
        return f"bruit + {int(v)} dB"
    if k == "points":
        return next((n for d, n, _b in AUTO_POINTS if d == v), "à la main")
    if k == "persist":
        return "aucune" if not v else f"{int(v)} balayages"
    if k in ("absent", "confirm"):
        return f"{int(v)} s" if v else "tout de suite"
    if k == "repeat":
        return dict(ALARM_REPEATS).get(int(v), f"{int(v)} s")
    if k == "strong":
        return f"au-dessus de {float(cfg.get('strong_lvl', -25.0)):.0f} dBm" if v else "non"
    return str(v)


def preset_changes(cur, key, user=None):
    """Ce que le préréglage key va changer par rapport aux réglages actuels cur (mêmes clés) :
    [(libellé, maintenant, après)] ; seulement les réglages qui changent vraiment."""
    p = quick_preset(key, user)
    if not p:
        return []
    new = p[3]
    out = []
    for k, lab in PRESET_LABELS:
        if k not in new:
            continue
        a, b = cur.get(k), new[k]
        same = a == b
        if k == "strong":
            same = bool(a) == bool(b) and (not b or abs(float(cur.get("strong_lvl", 0)) - float(new["strong_lvl"])) < 0.05)
        if k in ("auto_occ", "auto_weak") and not new.get("thr_auto"):
            continue
        if not same:
            out.append((lab, preset_value_text(k, a, cur), preset_value_text(k, b, new)))
    return out


def preset_match(cur, user=None):
    """Clé du préréglage dont TOUS les réglages valent les réglages actuels, sinon "" (réglé à la main)."""
    return next((p[0] for p in presets_all(user) if not preset_changes(cur, p[0], user)), "")


def net_text(nbytes, dt, rtt):
    """🌐 Lien réseau d'un tinySA : « 🌐 12 Ko/s · 8 ms » (débit sur dt secondes, délai de réponse)."""
    if dt <= 0:
        return ""
    kb = nbytes / dt / 1024.0
    out = f"🌐 {kb:.0f} Ko/s" if kb >= 10 else f"🌐 {kb:.1f} Ko/s"
    return out + (f" · {rtt * 1000:.0f} ms" if rtt is not None else "")


def snooze_left(until, now):
    """🔕 Silence en cours : secondes restantes (0 = pas de silence)."""
    return max(0, int(round(until - now))) if until and until > now else 0


def tone_pcm(seq, rate=22050, volume=0.7, timbre="sine"):
    """Suite de notes [(Hz, ms)] (Hz 0 = silence) -> octets PCM 16 bits mono, petit fondu (5 ms) contre les clics.
    timbre « chime » (8.0.3) : carillon (fondamentale + harmoniques douces, attaque 8 ms, son qui s'éteint en
    résonnant ; chaque note déborde sur le silence qui suit, la fin est fondue)."""
    if timbre == "chime":
        return _chime_pcm(seq, rate, volume)
    parts = []
    fade = max(1, int(rate * 0.005))
    for hz, ms in seq:
        n = max(1, int(rate * float(ms) / 1000.0))
        if not hz:
            parts.append(np.zeros(n))
            continue
        t = np.arange(n) / float(rate)
        x = np.sin(2 * np.pi * float(hz) * t)
        env = np.ones(n)
        k = min(fade, n // 2)
        if k:
            env[:k] = np.linspace(0.0, 1.0, k)
            env[-k:] = np.linspace(1.0, 0.0, k)
        parts.append(x * env)
    sig = np.concatenate(parts) if parts else np.zeros(1)
    v = min(1.0, max(0.0, float(volume)))
    return (sig * v * 32000).astype("<i2").tobytes()


def _chime_pcm(seq, rate=22050, volume=0.7):
    total = sum(max(1, int(rate * float(ms) / 1000.0)) for _hz, ms in seq) or 1
    tail = int(rate * 0.25)
    out = np.zeros(total + tail)
    pos = 0
    for hz, ms in seq:
        n = max(1, int(rate * float(ms) / 1000.0))
        if hz:
            ln = n + tail
            t = np.arange(ln) / float(rate)
            f = float(hz)
            x = (np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t)
                 + 0.08 * np.sin(2 * np.pi * 3 * f * t) + 0.05 * np.sin(2 * np.pi * 4.2 * f * t) * np.exp(-t / 0.05))
            env = np.exp(-t / max(0.12, 0.55 * ms / 1000.0))       # résonne, puis s'éteint
            a = max(1, int(rate * 0.008))
            env[:a] *= np.linspace(0.0, 1.0, a)
            out[pos:pos + ln] += x * env
        pos += n
    k = max(1, int(rate * 0.03))
    out[-k:] *= np.linspace(1.0, 0.0, k)
    peak = float(np.max(np.abs(out))) or 1.0
    v = min(1.0, max(0.0, float(volume)))
    return (out / peak * v * 30000).astype("<i2").tobytes()


# ------------------------------------------------------------------ chasse au brouilleur (bip qui suit le niveau)
def hunt_level(F, L, f0, win_khz=100.0, follow=False, span_mhz=None):
    """Niveau à suivre : le max à ± win_khz de f0 ; follow = le plus haut pic de toute la zone (± span / 2).
    -> (niveau dBm, fréquence du pic MHz) ou (None, None)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    if not len(F) or len(F) != len(L):
        return None, None
    half = (span_mhz / 2.0) if (follow and span_mhz) else win_khz / 1000.0
    m = np.abs(F - float(f0)) <= max(half, 1e-6)
    if not m.any():
        i = int(np.argmin(np.abs(F - float(f0))))
        return float(L[i]), float(F[i])
    idx = np.nonzero(m)[0]
    i = int(idx[np.argmax(L[idx])])
    return float(L[i]), float(F[i])


def hunt_tone(level, lo=-100.0, hi=-30.0):
    """Bip de la chasse : plus le niveau monte, plus c'est aigu et rapide (comme un détecteur de métaux).
    -> (Hz, période en ms) ; niveau None -> (0, 1000) = silence."""
    if level is None:
        return 0, 1000
    x = min(1.0, max(0.0, (float(level) - lo) / max(1e-6, hi - lo)))
    return int(round(400 + 1600 * x)), int(round(1000 - 920 * x))


# ------------------------------------------------------------------ 🎬 planning des plateaux (qui joue quand, par scène)
PLANNING_DEFAULT = dict(on=True, pre=15, post=10, slots=[])


def _hm(s_):
    """« 20:30 » -> 1230 minutes (None si illisible)."""
    m_ = re.fullmatch(r"\s*(\d{1,2})[:hH.](\d{2})\s*", str(s_ or ""))
    if not m_ or int(m_.group(1)) > 24 or int(m_.group(2)) > 59:
        return None
    return int(m_.group(1)) * 60 + int(m_.group(2))


def planning_norm(d):
    """Planning lu de la config / d'un show. Créneau = {scene, group ("" = toute la scène), day ("" = tous les jours,
    sinon « AAAA-MM-JJ »), start, end « HH:MM »} ; fin avant le début = finit après minuit."""
    d = d if isinstance(d, dict) else {}
    out = dict(PLANNING_DEFAULT, slots=[])
    out["on"] = bool(d.get("on", True))
    for k, hi in (("pre", 240), ("post", 240)):
        try:
            out[k] = min(hi, max(0, int(d.get(k, out[k]))))
        except (TypeError, ValueError):
            pass
    for s_ in d.get("slots") or []:
        if not isinstance(s_, dict) or not str(s_.get("scene", "")).strip():
            continue
        a, b = _hm(s_.get("start")), _hm(s_.get("end"))
        day = str(s_.get("day", "") or "").strip()
        if a is None or b is None or (day and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)):
            continue
        out["slots"].append(dict(scene=str(s_["scene"]).strip(), group=str(s_.get("group", "") or "").strip(),
                                 day=day, start=f"{a // 60:02d}:{a % 60:02d}", end=f"{b // 60:02d}:{b % 60:02d}"))
    out["slots"].sort(key=lambda x: (x["scene"].lower(), x["day"], _hm(x["start"])))
    return out


def planning_active(pl, ymd, minute, prev_ymd="", next_ymd=""):
    """Qui est sur scène maintenant (marges avant / après comprises) -> (actifs {(scène, groupe)}, scènes planifiées)."""
    act, planned = set(), set()
    if not pl or not pl.get("on"):
        return act, planned
    pre, post = int(pl.get("pre", 0)), int(pl.get("post", 0))
    for s_ in pl.get("slots") or []:
        planned.add(s_["scene"])
        a0, b0 = _hm(s_["start"]), _hm(s_["end"])
        if a0 is None or b0 is None:
            continue
        b = b0 + (1440 if b0 <= a0 else 0)
        a, b = a0 - pre, b + post
        for day, m_ in ((ymd, minute), (prev_ymd, minute + 1440), (next_ymd, minute - 1440)):
            if day and s_["day"] in ("", day) and a <= m_ < b:
                act.add((s_["scene"], s_["group"]))
    return act, planned


def planning_paused(scene, group, act, planned):
    """Fréquence d'un groupe pas sur scène en ce moment (sa scène a un planning, et ce n'est pas son créneau) ?"""
    return bool(scene) and scene in planned and (scene, group) not in act and (scene, "") not in act


def planning_lines(pl, act, ymd, minute):
    """Pour chaque scène planifiée : qui joue maintenant, et le prochain créneau du jour -> [texte]."""
    out = []
    for sc in sorted({s_["scene"] for s_ in (pl or {}).get("slots", [])}, key=str.lower):
        now = [g or "toute la scène" for (c, g) in sorted(act) if c == sc]
        nxt = sorted((s_ for s_ in pl["slots"] if s_["scene"] == sc and s_["day"] in ("", ymd)
                      and _hm(s_["start"]) > minute), key=lambda x: _hm(x["start"]))
        t = f"{sc} : " + (f"▶ {', '.join(now)}" if now else "💤 personne")
        if nxt:
            t += f" · ensuite {nxt[0]['group'] or 'toute la scène'} à {nxt[0]['start']}"
        out.append(t)
    return out


# ------------------------------------------------------------------ 📡 mode émission (générateur du tinySA Ultra)
# Commandes lues dans le source officiel du firmware (sa_cmd.c, 2026) : « mode low output » / « mode low input »,
# « freq <Hz> », « level <dBm> » (borné par le firmware), « modulation off|am|fm », « modulation freq <Hz> »,
# « modulation deviation <Hz> », « output on|off ».
GEN_MODS = (("off", "Porteuse pure (CW)"), ("fm", "FM (comme un micro HF analogique)"), ("am", "AM"))


def gen_commands(freq_mhz, level_dbm, mod="off", dev_khz=25.0, tone_hz=1000):
    """Réglage complet du générateur -> liste de commandes tinySA (à envoyer après « mode low output »)."""
    f = int(round(float(freq_mhz) * 1e6))
    cmds = [f"freq {f}", f"level {float(level_dbm):.1f}"]
    mod = mod if mod in dict(GEN_MODS) else "off"
    cmds.append(f"modulation {mod}")
    if mod != "off":
        cmds.append(f"modulation freq {int(max(100, min(6000, tone_hz)))}")
    if mod == "fm":
        cmds.append(f"modulation deviation {int(max(1000, min(300000, float(dev_khz) * 1000)))}")
    return cmds


def hunt_request(req):
    """Commande de chasse venue du téléphone -> dict propre (ValueError si bancale). « mark » (7.64) : « je suis ici »
    sur le plan de la carte (x, y entre 0 et 1 sur l'image /carte.png) -> point de la carte de chaleur."""
    if not isinstance(req, dict) or req.get("action") not in ("start", "stop", "reset", "mark", "unmark"):
        raise ValueError("action")
    if req["action"] in ("mark", "unmark"):
        if req["action"] == "unmark":
            return dict(action="unmark")
        x, y = float(req.get("x")), float(req.get("y"))
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError("position")
        return dict(action="mark", x=x, y=y)
    f, span = float(req.get("f") or 0), float(req.get("span") or 2)
    if req["action"] == "start" and not 0.1 <= f <= 6000:
        raise ValueError("fréquence")
    return dict(action=req["action"], f=f, span=min(50.0, max(0.2, span)), follow=bool(req.get("follow")),
                dev=1 if int(req.get("dev") or 0) == 1 else 0)


# ------------------------------------------------------------------ 🗺 7.64 : carte du site (façon canevas réseau)
MAP_DEFAULT = dict(pos={}, bg="", bg_op=0.45, bg_scale=1.0, bg_pos=[0.0, 0.0], heat=[], grid=True,
                   heat_reach=170.0, heat_iso=True, heat_arrow=True, heat_path=False,
                   heat_pal="classic", heat_op=0.55, heat_labels=True, heat_dot=1.0, heat_trail=2.0,
                   heat_dir="accent")
HEAT_DOT_SIZES = ((0.7, "Petits"), (1.0, "Moyens"), (1.5, "Gros"))
HEAT_TRAIL_WIDTHS = ((1.2, "Fine"), (2.0, "Normale"), (3.5, "Épaisse"))
HEAT_DIR_COLORS = (("accent", "Accent du thème"), ("hot", "Couleur du point le plus fort"), ("#ffffff", "Blanc"),
                   ("#ff9f0a", "Orange"), ("#30d158", "Vert"))


def heat_dir_color(choice, accent, hot_rgb=None):
    """Couleur de la direction « par là » -> « #rrggbb »."""
    if choice == "hot" and hot_rgb:
        return "#%02x%02x%02x" % tuple(hot_rgb)
    if isinstance(choice, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", choice or ""):
        return choice.lower()
    return accent
HEAT_REACHES = (90.0, 170.0, 300.0)   # portée du dégradé : serrée / normale / large (unités de carte)
MAP_BG_MAX_B64 = 12_000_000  # plan embarqué dans un show : ≈ 9 Mo d'image au plus (base64)
MAP_STEP = 40.0                   # pas de la grille (et de l'aimantation) en unités de carte
HEAT_MAX = 2000


def map_key(kind, name):
    """Clé d'un élément de la carte : « scene:Grande scène », « dev:0 » (n° de tinySA)."""
    return f"{kind}:{name}"


MAP_COORD_MAX = 1.0e6       # coordonnées de carte au-delà = fichier abîmé (7.65, audit : NaN / 1e100 acceptés avant)


def _fin(v, lim=MAP_COORD_MAX):
    """Nombre fini et raisonnable, sinon ValueError (NaN, inf, 1e100 d'un show abîmé ne passent plus)."""
    x = float(v)
    if not math.isfinite(x) or abs(x) > lim:
        raise ValueError(v)
    return x


def map_cfg_norm(d):
    """Carte lue (config / show) -> dict propre : positions {clé: [x, y]}, plan de fond (chemin, opacité, échelle,
    position), points de chaleur [{x, y, level, f, t}] (les HEAT_MAX derniers). Tout nombre non fini ou démesuré est
    écarté (point / position ignoré, réglage laissé à sa valeur par défaut)."""
    out = dict(MAP_DEFAULT, pos={}, heat=[], bg_pos=[0.0, 0.0])
    if not isinstance(d, dict):
        return out
    for k, v in (d.get("pos") or {}).items():
        try:
            if isinstance(k, str) and ":" in k and len(v) == 2:
                out["pos"][k[:80]] = [round(_fin(v[0]), 1), round(_fin(v[1]), 1)]
        except (TypeError, ValueError):
            continue
    out["bg"] = str(d.get("bg") or "")[:500]
    for key, lo, hi in (("bg_op", 0.0, 1.0), ("bg_scale", 0.02, 20.0)):
        try:
            out[key] = min(hi, max(lo, _fin(d.get(key, out[key]))))
        except (TypeError, ValueError):
            pass
    try:
        bp = d.get("bg_pos") or [0, 0]
        out["bg_pos"] = [_fin(bp[0]), _fin(bp[1])]
    except (TypeError, ValueError, IndexError, KeyError):
        pass
    bd = d.get("bg_data")
    if isinstance(bd, str) and 0 < len(bd) <= MAP_BG_MAX_B64 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", bd[:4096]):
        out["bg_data"] = bd                        # plan embarqué dans le show (base64), voir map_bg_embed
        out["bg_name"] = str(d.get("bg_name") or "plan.png")[:120]
    out["grid"] = bool(d.get("grid", True))
    for k in ("heat_iso", "heat_arrow", "heat_path", "heat_labels"):
        out[k] = bool(d.get(k, MAP_DEFAULT[k]))
    hd = d.get("heat_dir")
    out["heat_dir"] = hd if hd in ("accent", "hot") or (isinstance(hd, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", hd)) \
        else MAP_DEFAULT["heat_dir"]
    pal = d.get("heat_pal")
    out["heat_pal"] = pal if pal in [k for k, _n, _s in HEAT_PALETTES] else MAP_DEFAULT["heat_pal"]
    for key, lo, hi in (("heat_op", 0.1, 0.95), ("heat_dot", 0.4, 2.5), ("heat_trail", 0.5, 6.0),
                        ("heat_reach", 40.0, 500.0)):
        try:
            out[key] = min(hi, max(lo, _fin(d.get(key, MAP_DEFAULT[key]))))
        except (TypeError, ValueError):
            pass
    for h in (d.get("heat") or [])[-HEAT_MAX:]:
        try:
            lv, f, t = _fin(h["level"], 400.0), _fin(h.get("f") or 0.0, 1.0e5), _fin(h.get("t") or 0.0, 1.0e11)
            if f < 0 or t < 0:
                continue
            out["heat"].append(dict(x=round(_fin(h["x"]), 1), y=round(_fin(h["y"]), 1), level=round(lv, 1),
                                    f=round(f, 4), t=t))
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return out


def map_scene_monitor(running, devs, states):
    """🗺 7.65 : état de la SURVEILLANCE d'une scène sur la carte (à côté de l'état RF de ses micros) -> "off"
    (arrêtée), "lost" (aucun de ses tinySA en ligne), "nodata" (aucun de ses micros mesuré), "partial" (certains
    sans mesure), "ok". devs = [(n°, en ligne ?)] ; states = état de chaque micro (None = pas de mesure fraîche)."""
    if not running:
        return "off"
    if devs and not any(live for _d, live in devs):
        return "lost"
    st = list(states)
    if st and all(x is None for x in st):
        return "nodata"
    if any(x is None for x in st):
        return "partial"
    return "ok"


def map_bg_embed(m, data, name):
    """🗺 7.65 (audit : « le plan n'est pas dans le show ») : copie de la carte avec l'image du plan embarquée
    (bg_data = base64, bg_name = nom du fichier) ; trop grosse ou vide -> carte inchangée."""
    import base64
    out = dict(m or {})
    if data and len(data) * 4 // 3 + 4 <= MAP_BG_MAX_B64:
        out["bg_data"] = base64.b64encode(bytes(data)).decode("ascii")
        out["bg_name"] = re.sub(r"[^\w.\- ]", "_", str(name or "plan.png"))[-80:] or "plan.png"
    return out


def map_bg_extract(m):
    """Plan embarqué d'une carte -> (octets, nom de fichier sûr) ou None ; la carte n'est pas modifiée."""
    import base64
    bd = (m or {}).get("bg_data")
    if not bd:
        return None
    try:
        data = base64.b64decode(bd, validate=False)
    except (ValueError, TypeError):
        return None
    name = re.sub(r"[^\w.\- ]", "_", str((m or {}).get("bg_name") or "plan.png"))[-80:] or "plan.png"
    if not re.search(r"\.(png|jpe?g|bmp|gif)$", name, re.I):
        name += ".png"
    return (data, name) if data else None


def map_auto_place(keys, pos, step=MAP_STEP):
    """Positions des éléments pas encore placés : les scènes sur une rangée, les tinySA sur la rangée du dessous, à
    droite de ce qui existe déjà. -> {clé: [x, y]} (seulement les nouvelles)."""
    new = {}
    xs = [p[0] for p in pos.values()] or [0.0]
    x0 = (max(xs) + 8 * step) if pos else 0.0
    col = {"scene": 0, "dev": 0}
    for k in keys:
        if k in pos:
            continue
        kind = k.split(":", 1)[0]
        row = 0.0 if kind == "scene" else 6 * step
        new[k] = [x0 + col.get(kind, 0) * 8 * step, row]
        col[kind] = col.get(kind, 0) + 1
    return new


def map_snap(x, y, step=MAP_STEP):
    """Aimantation à la grille."""
    return [round(x / step) * step, round(y / step) * step]


def heat_for(points, f=None, tol=0.5):
    """Points de chaleur d'une fréquence (± tol MHz) ; f None = tous."""
    return [p for p in points or [] if f is None or abs(float(p.get("f") or 0.0) - f) <= tol]


def heat_freqs(points):
    """Fréquences chassées présentes dans les points (arrondies au kHz), les plus récentes d'abord."""
    seen = {}
    for p in points or []:
        k = round(float(p.get("f") or 0.0), 3)
        seen[k] = max(seen.get(k, 0.0), float(p.get("t") or 0.0))
    return [k for k, _t in sorted(seen.items(), key=lambda x: -x[1])]


def heat_scale(levels):
    """Échelle de couleur des points : (bas, haut) en dBm, 10 dB au moins."""
    lv = [float(x) for x in levels if x is not None]
    if not lv:
        return (-110.0, -40.0)
    lo, hi = min(lv), max(lv)
    if hi - lo < 10.0:
        mid = (hi + lo) / 2.0
        lo, hi = mid - 5.0, mid + 5.0
    return (lo, hi)


HEAT_PALETTES = [   # (clé, nom, couleurs du plus faible au plus fort ; None = accent du thème)
    ("classic", "Classique (bleu → jaune → rouge)", [(59, 130, 246), (250, 204, 21), (239, 68, 68)]),
    ("thermal", "Caméra thermique (violet → rouge → jaune)", [(49, 46, 129), (190, 24, 93), (239, 68, 68),
                                                             (251, 191, 36), (254, 243, 199)]),
    ("viridis", "Daltonien (violet → vert → jaune)", [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98),
                                                      (253, 231, 37)]),
    ("ice", "Glacier (bleu nuit → cyan → blanc)", [(30, 58, 138), (14, 165, 233), (103, 232, 249), (240, 253, 255)]),
    ("mint", "Doux (menthe → corail, couleurs du défaut)", [(79, 209, 197), (250, 204, 21), (255, 107, 107)]),
    ("accent", "Une seule couleur (accent du thème)", None),
]
HEAT_PAL_DEFAULT = "classic"


def heat_stops(pal=HEAT_PAL_DEFAULT, accent="#0a84ff"):
    """Couleurs d'une palette de chaleur -> [(r, g, b), …] du plus faible au plus fort."""
    for k, _n, st in HEAT_PALETTES:
        if k == pal:
            if st is not None:
                return list(st)
            a = accent.lstrip("#")
            r, g, b = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
            return [(round(r * 0.25), round(g * 0.25), round(b * 0.25)), (r, g, b),
                    (round(r + (255 - r) * 0.75), round(g + (255 - g) * 0.75), round(b + (255 - b) * 0.75))]
    return list(HEAT_PALETTES[0][2])


def heat_rgb(level, lo, hi, stops=None):
    """Couleur d'un niveau : du plus faible (1re couleur) au plus fort (dernière) ; défaut bleu → jaune → rouge."""
    st = stops or HEAT_PALETTES[0][2]
    t = 0.0 if hi <= lo else min(1.0, max(0.0, (float(level) - lo) / (hi - lo)))
    x = t * (len(st) - 1)
    k = min(int(x), len(st) - 2)
    u = x - k
    ca, cb = st[k], st[k + 1]
    return tuple(int(round(ca[i] + (cb[i] - ca[i]) * u)) for i in range(3))


def heat_hex(level, lo, hi, stops=None):
    return "#%02x%02x%02x" % heat_rgb(level, lo, hi, stops)


HEAT_REACH = 170.0     # au-delà de cette distance (unités de la carte) du point le plus proche : pas de couleur


def heat_field(points, x0, y0, w, h, cell=8.0, reach=HEAT_REACH):
    """Carte de chaleur continue (façon relevé Wi-Fi) : niveau lissé entre les points (noyau gaussien : un dégradé
    continu, pas une tache par point ; le niveau exact est écrit sur chaque point) et opacité pleine près des points
    qui s'éteint en douceur au-delà.
    -> (niveaux [ny, nx], opacité 0..1 [ny, nx]) sur une grille de pas `cell` partant de (x0, y0)."""
    nx, ny = max(1, int(math.ceil(w / cell))), max(1, int(math.ceil(h / cell)))
    pts = [p for p in points or [] if p.get("level") is not None]
    if not pts:
        return np.full((ny, nx), np.nan), np.zeros((ny, nx))
    px = np.array([float(p["x"]) for p in pts])
    py = np.array([float(p["y"]) for p in pts])
    lv = np.array([float(p["level"]) for p in pts])
    gx = x0 + (np.arange(nx) + 0.5) * cell
    gy = y0 + (np.arange(ny) + 0.5) * cell
    d2 = (gx[None, None, :] - px[:, None, None]) ** 2 + (gy[None, :, None] - py[:, None, None]) ** 2
    sig = reach * 0.55
    wgt = np.exp(-(d2 - d2.min(0)[None]) / (2.0 * sig * sig))   # noyau gaussien (stable loin des points)
    field = (wgt * lv[:, None, None]).sum(0) / wgt.sum(0)
    dmin = np.sqrt(d2.min(0))
    u = np.clip((dmin - 0.4 * reach) / (0.6 * reach), 0.0, 1.0)
    alpha = 1.0 - u * u * (3.0 - 2.0 * u)              # pleine près des points, puis fondu doux (smoothstep)
    return field, alpha


def heat_rgba(field, alpha, lo, hi, opacity=0.55, stops=None):
    """Image RGBA (uint8 [ny, nx, 4]) de heat_field, mêmes couleurs que heat_rgb (opacity = intensité 0..1)."""
    t = np.clip((np.nan_to_num(field, nan=lo) - lo) / max(1e-9, hi - lo), 0.0, 1.0)
    stops = np.array(stops or HEAT_PALETTES[0][2], dtype=float)
    n = len(stops) - 1
    k = np.minimum((t * n).astype(int), n - 1)
    u = (t * n - k)[..., None]
    rgb = stops[k] + (stops[k + 1] - stops[k]) * u
    a = np.clip(alpha, 0.0, 1.0) * opacity * 255.0
    a = np.where(np.isnan(field), 0.0, a)
    return np.dstack([rgb, a[..., None]]).round().astype(np.uint8)


def heat_isolines(field, alpha, x0, y0, cell, step=5.0, amin=0.35):
    """Courbes de niveau du dégradé (carrés qui marchent) tous les `step` dB, seulement là où il est bien visible
    (opacité ≥ amin). -> [(niveau, [(xa, ya, xb, yb), …]), …], du plus faible au plus fort."""
    f = np.where(np.asarray(alpha) >= amin, np.asarray(field, dtype=float), np.nan)
    if f.shape[0] < 2 or f.shape[1] < 2 or not np.isfinite(f).any():
        return []
    lo, hi = np.nanmin(f), np.nanmax(f)
    out = []
    v00, v01, v10, v11 = f[:-1, :-1], f[:-1, 1:], f[1:, :-1], f[1:, 1:]
    ok = np.isfinite(v00) & np.isfinite(v01) & np.isfinite(v10) & np.isfinite(v11)
    for lev in np.arange(math.ceil(lo / step) * step, hi + 1e-9, step):
        b = ((v00 >= lev) * 1 + (v01 >= lev) * 2 + (v11 >= lev) * 4 + (v10 >= lev) * 8)
        segs = []
        for i, j in zip(*np.nonzero(ok & (b > 0) & (b < 15))):
            a, bb, c, d = v00[i, j], v01[i, j], v11[i, j], v10[i, j]
            cx, cy = x0 + (j + 0.5) * cell, y0 + (i + 0.5) * cell

            def t(p, q):
                return 0.5 if q == p else (lev - p) / (q - p)
            e = {"T": (cx + t(a, bb) * cell, cy), "R": (cx + cell, cy + t(bb, c) * cell),
                 "B": (cx + t(d, c) * cell, cy + cell), "L": (cx, cy + t(a, d) * cell)}
            k = int(b[i, j])
            lt, tr, rb, bl, lr, tb = (("L", "T"),), (("T", "R"),), (("R", "B"),), (("B", "L"),), (("L", "R"),), (("T", "B"),)
            pairs = {1: lt, 14: lt, 2: tr, 13: tr, 4: rb, 11: rb, 8: bl, 7: bl, 3: lr, 12: lr,
                     6: tb, 9: tb, 5: lt + rb, 10: tr + bl}[k]
            for pr in pairs:
                (xa, ya), (xb, yb) = e[pr[0]], e[pr[1]]
                segs.append((round(xa, 1), round(ya, 1), round(xb, 1), round(yb, 1)))
        if segs:
            out.append((float(lev), segs))
    return out


def heat_path(points):
    """Parcours de la chasse : les points dans l'ordre où ils ont été notés -> [(x, y), …]."""
    pts = [p for p in points or [] if p.get("level") is not None]
    return [(float(p["x"]), float(p["y"])) for p in sorted(pts, key=lambda p: float(p.get("t") or 0.0))]


def heat_arrow(points, min_gain=3.0, max_len=280.0):
    """Flèche « par là » : depuis le DERNIER point noté vers le point le plus fort.
    -> None (moins de 2 points), {"here": True} (tu es sur le plus fort, ou à moins de min_gain dB de lui), sinon
    {"x0", "y0", "x1", "y1", "gain" (dB à gagner), "dist" (unités de carte)} ; flèche longue de max_len au plus."""
    pts = [p for p in points or [] if p.get("level") is not None]
    if len(pts) < 2:
        return None
    last = max(pts, key=lambda p: float(p.get("t") or 0.0))
    hot = max(pts, key=lambda p: p["level"])
    gain = float(hot["level"]) - float(last["level"])
    dx, dy = float(hot["x"]) - float(last["x"]), float(hot["y"]) - float(last["y"])
    dist = math.hypot(dx, dy)
    if hot is last or gain < min_gain or dist < 1.0:
        return {"here": True}
    L = min(dist - 14.0, max_len) if dist > 30 else dist * 0.6
    return dict(x0=float(last["x"]), y0=float(last["y"]), x1=float(last["x"]) + dx / dist * L,
                y1=float(last["y"]) + dy / dist * L, gain=round(gain, 1), dist=round(dist, 1))


def heat_hot(points):
    """Le point le plus fort (là où chercher) ou None."""
    pts = [p for p in points or [] if p.get("level") is not None]
    return max(pts, key=lambda p: p["level"]) if pts else None


# ------------------------------------------------------------------ 📍 scans par lieu (un tinySA promené de scène en scène)
def scan_gaps(F, k=4.0):
    """Trous d'un scan à plusieurs bandes : indices i où F[i] - F[i-1] dépasse k fois le pas des deux côtés (le pas
    de la bande d'avant et de celle d'après : deux bandes à pas différents ne font pas de faux trous)."""
    F = np.asarray(F, dtype=float)
    if len(F) < 3:
        return np.array([], dtype=int)
    d = np.diff(F)
    left = np.concatenate(([d[1]], d[:-1]))
    right = np.concatenate((d[1:], [d[-2]]))
    return np.nonzero(d > k * np.maximum(np.maximum(left, right), 1e-9))[0] + 1


def gap_nan(F, L):
    """(F, L) avec un NaN dans chaque trou entre bandes : une courbe tracée avec connect="finite" ne relie plus
    la fin d'une bande au début de la suivante (bug 7.28, retour de Clément : « des traits entre les bandes »)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    g = scan_gaps(F)
    if not len(g):
        return F, L
    return np.insert(F, g, np.nan), np.insert(L, g, np.nan)


def merge_scans(scans, max_points=60000):
    """Fusion de scans [(F MHz, L dBm)] sur une grille commune : le MAX de tous (le pire cas du site) -> (F, L).
    Grille au pas le plus fin des scans (plafonnée à max_points) ; chaque scan est interpolé sur sa propre plage, et
    ses points exacts sont aussi posés sur la grille (un pic étroit n'est pas perdu). (None, None) si rien."""
    ok_ = []
    for F, L in scans or []:
        if F is None or L is None:
            continue
        F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
        if len(F) < 2 or len(F) != len(L):
            continue
        o = np.argsort(F, kind="stable")
        F, L = F[o], L[o]
        cuts = [0, *scan_gaps(F), len(F)]          # une bande = un morceau : pas d'interpolation entre deux bandes
        for a, b in zip(cuts[:-1], cuts[1:]):
            if b - a >= 2:
                ok_.append((F[a:b], L[a:b]))
    if not ok_:
        return None, None
    lo = min(F[0] for F, _L in ok_)
    hi = max(F[-1] for F, _L in ok_)
    step = min(float(np.median(np.diff(F))) for F, _L in ok_) or 0.001
    step = max(step, (hi - lo) / max(1, max_points - 1), 1e-6)
    n = int(round((hi - lo) / step)) + 1
    G = lo + np.arange(n) * step
    out = np.full(n, np.nan)
    for F, L in ok_:
        inside = (G >= F[0]) & (G <= F[-1])
        out[inside] = np.fmax(out[inside], np.interp(G[inside], F, L))
        idx = np.clip(np.round((F - lo) / step).astype(int), 0, n - 1)
        np.fmax.at(out, idx, L)
    keep = np.isfinite(out)
    return G[keep], out[keep]


def site_scan_doc(name, F, L, t, scene=None, dur=None, rbw=None, rbw_est=False):
    """Scan d'un lieu en version compacte (config / show) : MHz à 4 décimales, dBm à 1 décimale. scene : la scène
    d'un scan gardé à la main (plusieurs par scène possibles, ex. « Grande scène · jardin ») ; sinon le nom.
    rbw (kHz) : finesse de mesure du scan (7.66.4, Clément : « pour un scan pour la coord c'est important de le
    marquer ») ; rbw_est = RBW auto du tinySA, estimée d'après le pas ; « mixed » = scans de RBW différents fusionnés."""
    d = dict(name=str(name).strip()[:60], t=float(t), f=[round(float(x), 4) for x in F],
             l=[round(float(x), 1) for x in L])
    if scene and str(scene).strip() != d["name"]:
        d["scene"] = str(scene).strip()[:60]
    if dur:
        d["dur"] = round(float(dur), 1)
    if rbw == "mixed":
        d["rbw"] = "mixed"
    elif rbw:
        d["rbw"] = round(float(rbw), 1)
        if rbw_est:
            d["rbw_est"] = True
    return d


def rbw_merge(a, b):
    """RBW d'un scan fusionné de deux scans : la même si elles sont égales, « mixed » sinon, None si l'une est inconnue."""
    if a is None or b is None:
        return None
    return a if a == b else "mixed"


def rbw_text(rbw, est=False, tr=None):
    """« RBW 100 kHz », « RBW ≈ 100 kHz (auto) », « RBW mélangées », « RBW inconnue »."""
    tr = tr or (lambda x: x)
    if rbw == "mixed":
        return tr("RBW mélangées (niveaux pas comparables)")
    if not rbw:
        return tr("RBW inconnue")
    v = f"{float(rbw):g} kHz"
    return f"RBW ≈ {v} " + tr("(auto)") if est else f"RBW {v}"


COORD_RBW_MAX = 30.0          # conseil : scan pour une coordination = RBW fine (≤ 30 kHz)
COORD_RBW_TIP = ("Scan pour une coordination : RBW fine, 30 kHz ou moins. Une RBW large étale les signaux étroits "
                 "(micros, talkies) et remonte le bruit : les niveaux et le seuil « occupé » ne veulent plus dire la "
                 "même chose. De 100 à 30 kHz, le bruit et la TNT descendent d'environ 5 dB, un micro presque pas.")


def rbw_combine(items):
    """RBW d'un ensemble de scans [(rbw, estimée)] -> (rbw | "mixed" | None, estimée)."""
    items = list(items)
    if not items:
        return None, False
    vals = [r for r, _e in items]
    est = any(e for _r, e in items)
    if any(v is None for v in vals):
        return (None if all(v is None for v in vals) else "mixed"), est
    first = vals[0]
    return (first if all(v == first for v in vals) else "mixed"), est


def rbw_coord_line(rbw, est=False, tr=None, step=None):
    """Phrase « ce scan est-il bon pour une coordination ? » -> (texte, ok). step (kHz) : écart entre deux points ;
    plus large que la RBW, des signaux étroits passent ENTRE les points (7.66.5 : RBW 10 kHz avec 3 000 points sur
    224 MHz = un point tous les 75 kHz)."""
    tr = tr or (lambda x: x)
    if rbw not in (None, "mixed") and step and float(step) > 1.5 * float(rbw):
        return (f"⚠ {rbw_text(rbw, est, tr)} · " + tr("pas de {} kHz entre deux points : des signaux étroits passent "
                "entre les points. Mets plus de points (pas ≤ RBW) ou une RBW au moins égale au pas.")
                .format(f"{float(step):g}")), False
    if rbw == "mixed":
        return tr("⚠ Scans de RBW différentes mélangés : niveaux pas comparables (refais-les avec la même RBW fine, "
                  "≤ 30 kHz)."), False
    if not rbw:
        return tr("⚠ RBW inconnue : vérifie que ce scan a été fait avec une RBW fine (≤ 30 kHz)."), False
    t = rbw_text(rbw, est, tr)
    if float(rbw) <= COORD_RBW_MAX:
        return f"✔ {t} · " + tr("fine : bonne pour une coordination."), True
    return f"⚠ {t} · " + tr("trop large pour une coordination : mets 30 kHz ou moins (⚙ › Mesure)."), False


def scan_step_khz(F):
    """Écart typique entre deux points d'un scan (kHz), None si inconnu."""
    F = np.asarray(F if F is not None else [], dtype=float)
    if len(F) < 2:
        return None
    d = np.diff(F)
    d = d[d > 0]
    return round(float(np.median(d)) * 1000.0, 1) if len(d) else None


def rbw_tag(rbw):
    """Morceau de nom de fichier : « RBW100k » (rien si inconnue ou mélangée)."""
    if not rbw or rbw == "mixed":
        return ""
    return f"RBW{float(rbw):g}k".replace(".", ",")


def site_doc_scene(d):
    """Scène d'un scan gardé (son nom pour le scan continu d'une scène)."""
    return d.get("scene") or d.get("name", "")


def coord_docs(site_scans, src):
    """Scans gardés qui comptent pour la coordination : src « live » -> aucun, « all » -> tous, sinon une scène ->
    les siens (le scan continu de la scène + ceux gardés à la main)."""
    if src == "live":
        return []
    if src == "all":
        return list(site_scans or [])
    return [d for d in site_scans or [] if site_doc_scene(d) == src]


def snapshot_name(scene, label, existing, hhmm):
    """Nom d'un scan gardé à la main : « Scène · étiquette » (ou l'heure), rendu unique."""
    base = f"{scene} · {str(label or '').strip() or hhmm}"[:56]
    name, k = base, 2
    while name in existing:
        name, k = f"{base} ({k})", k + 1
    return name


TECH_ACTIONS = ("run", "snooze", "ack_all", "thr", "watch_add", "watch_edit", "watch_del", "dev_scenes", "identify",
                "save", "state", "mute", "quick_add", "suggest", "replace", "sugg_close")


def tech_request(req):
    """🛠 Commande de la page Tech -> dict propre (ValueError si bancale). Rien n'est exécuté ici."""
    if not isinstance(req, dict) or req.get("action") not in TECH_ACTIONS:
        raise ValueError("action")
    a = req["action"]
    out = dict(action=a)

    def num(k, lo, hi, opt=False):
        v = req.get(k)
        if v is None or v == "":
            if opt:
                return None
            raise ValueError(k)
        if isinstance(v, bool):
            raise ValueError(k)
        v = float(v)
        if not (lo <= v <= hi):                    # NaN aussi
            raise ValueError(k)
        return v

    def txt(k, n):
        return re.sub(r"\s+", " ", str(req.get(k) or "")).strip()[:n]
    if a == "run":
        out["on"] = bool(req.get("on"))
    elif a == "snooze":
        out["min"] = int(num("min", 0, 240))
    elif a == "thr":
        out.update(occ=num("occ", -140, 0), weak=num("weak", -150, 0, True), absent=num("absent", 1, 600, True),
                   weak_on=bool(req.get("weak_on", True)))
    elif a == "watch_add":
        out.update(freq=num("freq", 1, 7000), name=txt("name", 40), status=txt("status", 30), scene=txt("scene", 60),
                   group=txt("group", 60))
    elif a == "quick_add":                         # ⌨ 7.62 : saisie express depuis le téléphone
        out.update(text=str(req.get("text") or "")[:4000], status=txt("status", 30), scene=txt("scene", 60),
                   group=txt("group", 60))
    elif a in ("suggest", "replace"):             # 🆘 7.62 : remplacer un micro
        out["key"] = int(num("key", 1000, 7000000))
        if a == "replace":
            out["f"] = num("f", 1, 7000)
    elif a in ("watch_edit", "watch_del", "mute"):
        out["key"] = int(num("key", 1000, 7000000))
        if a == "mute":
            out["on"] = bool(req.get("on"))
        if a == "watch_edit":
            out.update(freq=num("freq", 1, 7000, True), name=txt("name", 40) if "name" in req else None,
                       status=txt("status", 30) if "status" in req else None)
    elif a == "state":
        out["name"] = txt("name", 40)
    elif a in ("dev_scenes", "identify"):
        out["dev"] = int(num("dev", 0, 7))
        if a == "dev_scenes":
            sc = req.get("scenes")
            out["scenes"] = [str(x).strip()[:60] for x in (sc if isinstance(sc, list) else []) if str(x).strip()][:50]
    return out


def terrain_request(req):
    """Commande de la vue Terrain (téléphone) -> dict propre (ValueError si bancale)."""
    if not isinstance(req, dict) or req.get("action") not in ("assign", "reset", "save", "delete"):
        raise ValueError("action")
    sc = req.get("scenes")
    sc = [str(x).strip()[:60] for x in (sc if isinstance(sc, list) else []) if str(x).strip()][:50]
    name = str(req.get("name") or "").strip()[:80]
    if req["action"] == "delete" and not name:
        raise ValueError("nom")
    return dict(action=req["action"], dev=1 if int(req.get("dev") or 0) == 1 else 0, scenes=sc,
                label=re.sub(r"\s+", " ", str(req.get("label") or "")).strip()[:40], name=name)


def site_scans_norm(lst):
    """Scans par lieu lus d'un fichier -> [{name, t, f, l}] valides (noms uniques, le dernier gagne)."""
    out = {}
    for d in lst if isinstance(lst, list) else []:
        try:
            f, l = list(d["f"]), list(d["l"])
            name = str(d["name"]).strip()
            if name and len(f) >= 2 and len(f) == len(l):
                out[name] = dict(name=name[:60], t=float(d.get("t") or 0), f=[float(x) for x in f], l=[float(x) for x in l])
                if d.get("scene"):
                    out[name]["scene"] = str(d["scene"]).strip()[:60]
                if isinstance(d.get("dur"), (int, float)) and d["dur"] > 0:
                    out[name]["dur"] = round(float(d["dur"]), 1)     # durée du scan (s), si connue
                if d.get("hidden"):
                    out[name]["hidden"] = True       # 7.66 : masqué (pas tracé sur le spectre ni fusionné)
                rb = d.get("rbw")
                if rb == "mixed":
                    out[name]["rbw"] = "mixed"
                elif isinstance(rb, (int, float)) and 0.1 <= rb <= 10000:
                    out[name]["rbw"] = round(float(rb), 1)       # 7.66.4 : RBW du scan (kHz)
                    if d.get("rbw_est"):
                        out[name]["rbw_est"] = True
        except (KeyError, TypeError, ValueError):
            continue
    return list(out.values())

def site_replace(lst, doc):
    """Remplace (ou ajoute à la fin) le scan de même nom, À SA PLACE, en gardant son état masqué (7.66 : le scan continu
    d'une scène, regardé toutes les 30 s, passait en fin de liste et redevenait visible)."""
    out, done = [], False
    for d in lst or []:
        if d["name"] == doc["name"]:
            nd = dict(doc)
            if d.get("hidden"):
                nd["hidden"] = True
            out.append(nd)
            done = True
        else:
            out.append(d)
    return out if done else out + [dict(doc)]


def site_set_hidden(lst, names, hidden):
    """Masque / affiche les scans nommés -> nouvelle liste (les autres inchangés)."""
    names = set(names)
    out = []
    for d in lst or []:
        if d["name"] in names:
            d = dict(d)
            if hidden:
                d["hidden"] = True
            else:
                d.pop("hidden", None)
        out.append(d)
    return out


def site_visible(lst):
    """Scans affichés (pas masqués)."""
    return [d for d in lst or [] if not d.get("hidden")]


# ------------------------------------------------- 📍 scans par lieu : gestion, comparaison, dans le temps, rapport
def site_scan_info(d):
    """Résumé d'un scan gardé -> dict(scene, t, lo, hi, n, step kHz, bands, dur s ou None)."""
    F = np.asarray(d.get("f") or [], dtype=float)
    steps = np.diff(F) if len(F) > 1 else np.array([0.0])
    return dict(scene=site_doc_scene(d), t=float(d.get("t") or 0), lo=float(F[0]) if len(F) else 0.0,
                hi=float(F[-1]) if len(F) else 0.0, n=int(len(F)),
                step=round(float(np.median(steps)) * 1000.0, 1) if len(F) > 1 else 0.0,
                bands=int(len(scan_gaps(F)) + 1) if len(F) else 0,
                dur=float(d["dur"]) if isinstance(d.get("dur"), (int, float)) and d["dur"] > 0 else None,
                rbw=d.get("rbw"), rbw_est=bool(d.get("rbw_est")))


def _fmt_ts(t, fmt):
    """Date d'un horodatage (s) ; « — » si inconnue (import local : la section PURE n'a pas datetime)."""
    import datetime as _dt
    return _dt.datetime.fromtimestamp(float(t)).strftime(fmt) if t else "—"


def fmt_duration(s):
    """Durée lisible : « 45 s », « 12 min », « 1 h 05 »."""
    s = int(round(float(s or 0)))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    return f"{s // 3600} h {(s % 3600) // 60:02d}"


def level_everywhere(docs, f, bw=0.0, win=0.1):
    """📍 7.68 (« le niveau d'une fréquence partout », Scans par lieu) : niveau de f (MHz, bloc de largeur bw) dans
    chaque scan gardé. Niveau = max à ± (win + bw/2) MHz ; bruit de fond local (noise_floor) ; None si le scan n'a pas
    mesuré cette fréquence (hors plage, trou entre deux bandes). -> lignes dict(name, scene, t, level, floor, margin,
    rbw, rbw_est), les plus fortes d'abord, les non mesurées à la fin."""
    out = []
    half = float(win) + float(bw or 0.0) / 2.0
    for d in docs or ():
        F = np.asarray(d.get("f") or [], dtype=float)
        L = np.asarray(d.get("l") or [], dtype=float)
        i_ = site_scan_info(d)
        row = dict(name=d.get("name", ""), scene=i_["scene"], t=i_["t"], level=None, floor=None, margin=None,
                   rbw=i_["rbw"], rbw_est=i_["rbw_est"])
        if len(F) >= 2 and covered(np.array([f]), scan_segments(F), pad=half)[0]:
            m = np.abs(F - f) <= max(half, float(np.median(np.diff(F))) / 2.0 + 1e-9)
            if m.any():
                row["level"] = float(np.max(L[m]))
                fl_ = noise_floor(F, L, f, win=2.0 + bw / 2.0, exclude=max(0.15, half))
                row["floor"] = fl_
                row["margin"] = (row["level"] - fl_) if fl_ is not None else None
        out.append(row)
    out.sort(key=lambda r: (r["level"] is None, -(r["level"] if r["level"] is not None else 0.0)))
    return out


def level_everywhere_text(rows, f, fmt=None):
    """Phrase de résumé : où c'est le plus fort / le plus calme."""
    fmt = fmt or (lambda v: f"{v:.0f} dBm")
    got = [r for r in rows if r["level"] is not None]
    if not got:
        return f"{f:.3f} MHz n'a été mesurée dans aucun scan gardé."
    hi_, lo_ = got[0], got[-1]
    if len(got) == 1:
        return f"{f:.3f} MHz : {fmt(hi_['level'])} dans « {hi_['name']} » (seul scan qui la mesure)."
    return (f"{f:.3f} MHz : la plus forte dans « {hi_['name']} » ({fmt(hi_['level'])}), la plus calme dans "
            f"« {lo_['name']} » ({fmt(lo_['level'])}), écart {hi_['level'] - lo_['level']:.0f} dB.")


def site_rename(scans, old, new):
    """Renomme un scan gardé. -> (nouvelle liste, message d'erreur ou "")."""
    new = str(new).strip()[:60]
    if not new:
        return scans, "Donne un nom."
    if new != old and any(d["name"] == new for d in scans):
        return scans, f"« {new} » existe déjà."
    out = []
    for d in scans:
        if d["name"] == old:
            sc = site_doc_scene(d)
            d = dict(d, name=new)
            if sc and sc != new:
                d["scene"] = sc               # il reste rangé dans sa scène
            else:
                d.pop("scene", None)
        out.append(d)
    return out, ""


def site_move(scans, name, scene):
    """Range un scan gardé dans une autre scène (scene "" = le scan redevient son propre lieu)."""
    out = []
    for d in scans:
        if d["name"] == name:
            d = dict(d)
            if scene and scene != d["name"]:
                d["scene"] = str(scene).strip()[:60]
            else:
                d.pop("scene", None)
        out.append(d)
    return out


def diff_spectra(F1, L1, F2, L2):
    """Différence A − B (dB) là où les deux scans ont mesuré (pas dans les trous entre bandes de B) -> (F, D) sur les
    points de A, NaN ailleurs ; (None, None) si rien en commun."""
    F1, L1 = _valid(F1, L1)
    F2, L2 = _valid(F2, L2)
    if len(F1) < 2 or len(F2) < 2:
        return None, None
    o1, o2 = np.argsort(F1), np.argsort(F2)
    F1, L1, F2, L2 = F1[o1], L1[o1], F2[o2], L2[o2]
    cover = covered(F1, scan_segments(F2))
    if not cover.any():
        return None, None
    D = np.where(cover, L1 - np.interp(F1, F2, L2), np.nan)
    return F1, D


def scene_timeline(scans, scene):
    """Scans gardés d'une scène, du plus ancien au plus récent."""
    return sorted((d for d in scans or [] if site_doc_scene(d) == scene), key=lambda d: float(d.get("t") or 0))


def only_here(scans, name, thr, margin=10.0):
    """Signaux vus dans le scan `name` et pas ailleurs (au moins margin dB au-dessus de la fusion des autres lieux) :
    ce qui est propre à ce lieu (émetteur local, écran LED…)."""
    me = next((d for d in scans if d["name"] == name), None)
    others = [(d["f"], d["l"]) for d in scans if d["name"] != name and site_doc_scene(d) != site_doc_scene(me or {})]
    if me is None:
        return []
    if not others:
        return []
    Fo, Lo = merge_scans(others)
    if Fo is None:
        return []
    new, _gone = compare_spectra(me["f"], me["l"], Fo, Lo, thr, margin)
    return new


def _svg_multi(series, thr=None, width=1000, height=260, ylo=-120.0, yhi=None, unit="dBm", zero=False):
    """Plusieurs courbes en SVG, coupées dans les trous entre bandes. series = [(F, L, couleur, pointillé, nom)]."""
    series = [(np.asarray(F, dtype=float), np.asarray(L, dtype=float), c, dash, nm) for F, L, c, dash, nm in series
              if F is not None and len(F) >= 2]
    if not series:
        return "<p class='muted'>Pas de mesure.</p>"
    f0 = min(float(np.nanmin(F)) for F, *_ in series)
    f1 = max(float(np.nanmax(F)) for F, *_ in series)
    top = max(float(np.nanmax(L)) for _F, L, *_ in series if np.isfinite(L).any())
    hi = yhi if yhi is not None else max(-20.0, top + 5.0)
    lo = ylo
    px, py = 46, 10
    w, h = width - px - 8, height - py - 26
    # axe coupé : chaque bande mesurée garde sa part de largeur (pas 1 700 MHz de vide entre l'UHF et le 2,4 GHz)
    iv = []                                         # bandes de chaque courbe, puis réunies
    for F, *_ in series:
        Fs = np.sort(F[np.isfinite(F)])
        cuts = [0, *scan_gaps(Fs), len(Fs)]
        iv += [(float(Fs[a]), float(Fs[b - 1])) for a, b in zip(cuts[:-1], cuts[1:]) if b > a]
    segs = []
    for a, b in sorted(iv):
        if segs and a <= segs[-1][1] + 1e-9:
            segs[-1] = (segs[-1][0], max(segs[-1][1], b))
        else:
            segs.append((a, b))
    segs = [(a, b) for a, b in segs if b > a] or [(f0, f1)]
    span = sum(b - a for a, b in segs)
    if len(segs) < 2 or span >= 0.7 * (f1 - f0):
        segs = [(f0, f1)]
    gapx = 14.0
    usable = w - gapx * (len(segs) - 1)
    raw = [max((b - a) / max(sum(y - x for x, y in segs), 1e-9), 0.12) for a, b in segs]
    widths = [usable * r / sum(raw) for r in raw]
    x0s = [px + sum(widths[:k]) + gapx * k for k in range(len(segs))]

    def X(f):
        for (a, b), x0, ww in zip(segs, x0s, widths):
            if f <= b or (a, b) == segs[-1]:
                return x0 + (min(max(f, a), b) - a) / max(b - a, 1e-9) * ww
        return px

    def Y(v):
        return py + (hi - min(max(v, lo), hi)) / (hi - lo) * h

    s = [f"<svg viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' class='spec'>"]
    stepy = 20 if hi - lo > 60 else 10
    for v in range(int(math.ceil(lo / stepy) * stepy), int(hi) + 1, stepy):
        s.append(f"<line x1='{px}' x2='{px + w}' y1='{Y(v):.1f}' y2='{Y(v):.1f}' class='grid'/>"
                 f"<text x='{px - 6}' y='{Y(v) + 4:.1f}' class='ax' text-anchor='end'>{v}</text>")
    for (a, b), x0, ww in zip(segs, x0s, widths):
        nt = max(1, min(8, int(ww // 110)))
        for i in range(nt + 1):
            f = a + (b - a) * i / nt
            anc = "start" if i == 0 and len(segs) > 1 else "end" if i == nt and len(segs) > 1 else "middle"
            s.append(f"<text x='{X(f):.1f}' y='{height - 8}' class='ax' text-anchor='{anc}'>{f:.1f}</text>")
        if x0 > px:                                 # coupure entre deux bandes
            s.append(f"<rect x='{x0 - gapx + 2:.1f}' y='{py}' width='{gapx - 4:.1f}' height='{h}' fill='#eef1f7'/>")
    if zero and lo < 0 < hi:
        s.append(f"<line x1='{px}' x2='{px + w}' y1='{Y(0):.1f}' y2='{Y(0):.1f}' class='thr'/>")
    if thr is not None and lo <= thr <= hi:
        s.append(f"<line x1='{px}' x2='{px + w}' y1='{Y(thr):.1f}' y2='{Y(thr):.1f}' class='thr'/>")
    for F, L, col, dash, nm in series:
        o = np.argsort(F)
        F, L = F[o], L[o]
        cuts = [0, *scan_gaps(F), len(F)]
        for a, b in zip(cuts[:-1], cuts[1:]):
            Fa, La = F[a:b], L[a:b]
            k = max(1, int(math.ceil(len(Fa) / 900)))
            if k > 1:
                m = (len(Fa) // k) * k
                Fa, La = Fa[:m].reshape(-1, k).mean(axis=1), np.nanmax(La[:m].reshape(-1, k), axis=1)
            pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in zip(Fa, La) if np.isfinite(y))
            if pts.count(",") >= 2:
                s.append(f"<polyline points='{pts}' fill='none' stroke='{col}' stroke-width='1.2'"
                         f"{' stroke-dasharray=\"5 4\"' if dash else ''}><title>{html_esc(nm)}</title></polyline>")
    s.append(f"<text x='{px + w}' y='{py + 12}' class='ax' text-anchor='end'>MHz · {unit}</text></svg>")
    return "".join(s)


SITE_COLORS = ["#2f6fdb", "#e08a1e", "#2e8b57", "#b03fbf", "#d33a2c", "#0f9aa8", "#8a6d1e", "#5a5fd6"]


def site_report_html(scans, thr, title="Étude de site", venue="", generated="", margin=10.0):
    """📄 Rapport d'étude de site autonome : chaque lieu (infos, spectre, signaux, ce qui n'est vu qu'ici), la fusion
    du site, et l'évolution des scènes scannées plusieurs fois. À ouvrir dans un navigateur et imprimer en PDF."""
    e = html_esc
    scans = list(scans or [])
    p = ["<!doctype html><html lang='fr'><head><meta charset='utf-8'>", f"<title>{e(title)}</title>",
         "<meta name='viewport' content='width=device-width,initial-scale=1'><style>",
         "body{font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;color:#1d2433;max-width:1100px;margin:0 auto;padding:24px 18px}",
         "h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:30px 0 8px;border-bottom:2px solid #d8dde8;padding-bottom:4px}",
         "h3{font-size:15px;margin:18px 0 6px}.muted{color:#6b7488}",
         "table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}th,td{border-bottom:1px solid #e3e7ef;"
         "padding:4px 8px;text-align:left}th{background:#eef1f7}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}",
         "svg.spec{width:100%;height:auto;border:1px solid #d8dde8;border-radius:8px;background:#fbfcfe}",
         ".grid{stroke:#e3e7ef}.ax{font-size:11px;fill:#6b7488}.thr{stroke:#d33;stroke-dasharray:5 4}",
         ".lg span{display:inline-block;margin-right:14px}.lg i{display:inline-block;width:14px;height:3px;"
         "vertical-align:middle;margin-right:5px}", REPORT_PRO_CSS,
         "@media print{body{padding:0}h2{break-before:page}h2:first-of-type{break-before:auto}tr{break-inside:avoid}}",
         "</style></head><body>", f"<h1>{e(title)}</h1>",
         f"<div class='muted'>{e(venue) + ' · ' if venue else ''}{e(generated)} · {len(scans)} scan(s) gardé(s) · "
         f"seuil « occupé » {thr:.0f} dBm</div>"]
    if not scans:
        p.append("<p>Aucun scan gardé.</p></body></html>")
        return "".join(p)
    col = {d["name"]: SITE_COLORS[i % len(SITE_COLORS)] for i, d in enumerate(scans)}
    # --- sommaire
    p.append("<h2>Les scans</h2><table><tr><th>Scan</th><th>Scène</th><th>Date</th><th class='n'>Plage (MHz)</th>"
             "<th class='n'>Pas (kHz)</th><th class='n'>RBW</th><th class='n'>Bandes</th><th class='n'>Durée</th>"
             "<th class='n'>Signaux</th></tr>")
    for d in scans:
        i_ = site_scan_info(d)
        n_sig = len(scan_peaks(d["f"], d["l"], thr))
        when = _fmt_ts(i_["t"], "%d/%m/%Y %H:%M")
        p.append(f"<tr><td><b style='color:{col[d['name']]}'>{e(d['name'])}</b></td><td>{e(i_['scene'])}</td>"
                 f"<td>{when}</td><td class='n'>{i_['lo']:.3f}–{i_['hi']:.3f}</td><td class='n'>{i_['step']:g}</td>"
                 f"<td class='n'>{e(rbw_text(i_['rbw'], i_['rbw_est']))}</td>"
                 f"<td class='n'>{i_['bands']}</td><td class='n'>{fmt_duration(i_['dur']) if i_['dur'] else '—'}</td>"
                 f"<td class='n'>{n_sig}</td></tr>")
    p.append("</table>")
    # --- fusion
    Fm, Lm = merge_scans([(d["f"], d["l"]) for d in scans])
    p.append("<h2>Tout le site</h2><p>Le plus fort de tous les scans en chaque fréquence (le pire cas) : c'est ce qui "
             "compte pour une coordination de tout le site.</p>")
    p.append(_svg_multi([(d["f"], d["l"], col[d["name"]], False, d["name"]) for d in scans]
                        + [(Fm, Lm, "#1d2433", True, "Fusion")], thr))
    p.append("<div class='lg muted'>" + "".join(f"<span><i style='background:{col[d['name']]}'></i>{e(d['name'])}</span>"
                                                 for d in scans) + "<span><i style='background:#1d2433'></i>Fusion "
             "(pointillés)</span></div>")
    # --- chaque lieu
    for d in scans:
        i_ = site_scan_info(d)
        p.append(f"<h2>{e(d['name'])}</h2><div class='muted'>Scène : {e(i_['scene'])} · {i_['lo']:.3f}–{i_['hi']:.3f} MHz · "
                 f"{i_['n']} points · {e(rbw_text(i_['rbw'], i_['rbw_est']))}</div>")
        p.append(_svg_multi([(d["f"], d["l"], col[d["name"]], False, d["name"])], thr))
        pk = scan_peaks(d["f"], d["l"], thr)
        if pk:
            p.append(f"<h3>Signaux au-dessus du seuil ({len(pk)})</h3><table><tr><th class='n'>MHz</th>"
                     "<th class='n'>Niveau (dBm)</th><th class='n'>Largeur (kHz)</th><th>Type</th></tr>")
            for x in pk[:60]:
                p.append(f"<tr><td class='n'>{x['f']:.3f}</td><td class='n'>{x['level']:.1f}</td>"
                         f"<td class='n'>{x['width']:.0f}</td><td>{'large (TNT, bloc numérique…)' if x['wide'] else 'porteuse'}"
                         "</td></tr>")
            p.append("</table>" + (f"<p class='muted'>… et {len(pk) - 60} autres.</p>" if len(pk) > 60 else ""))
        else:
            p.append("<p class='muted'>Aucun signal au-dessus du seuil.</p>")
        oh = only_here(scans, d["name"], thr, margin)
        if oh:
            p.append(f"<h3>Vus seulement ici ({len(oh)})</h3><p class='muted'>Au moins {margin:.0f} dB plus forts que "
                     "partout ailleurs : un émetteur proche de ce lieu.</p><p>"
                     + ", ".join(f"{x['f']:.3f} MHz ({x['level']:.0f} dBm)" for x in oh[:30]) + "</p>")
    # --- dans le temps
    scenes = []
    for d in scans:
        sc = site_doc_scene(d)
        if sc not in scenes and len(scene_timeline(scans, sc)) > 1:
            scenes.append(sc)
    if scenes:
        p.append("<h2>Dans le temps</h2><p>Les scènes scannées plusieurs fois : ce qui est apparu ou a disparu entre le "
                 "premier et le dernier scan.</p>")
        for sc in scenes:
            tl = scene_timeline(scans, sc)
            a, b = tl[0], tl[-1]
            new, gone = compare_spectra(b["f"], b["l"], a["f"], a["l"], thr, margin)
            when = [_fmt_ts(x.get("t"), "%d/%m %H:%M") for x in (a, b)]
            p.append(f"<h3>{e(sc)} : {len(tl)} scans, du {when[0]} au {when[1]}</h3>")
            p.append(_svg_multi([(x["f"], x["l"], SITE_COLORS[k % len(SITE_COLORS)], False, x["name"])
                                 for k, x in enumerate(tl)], thr))
            p.append("<p><b>Apparus :</b> " + (", ".join(f"{x['f']:.3f} MHz ({x['level']:.0f} dBm)" for x in new[:30])
                                                or "aucun") + "<br><b>Disparus :</b> "
                     + (", ".join(f"{x['f']:.3f} MHz ({x['level']:.0f} dBm)" for x in gone[:30]) or "aucun") + "</p>")
    p.append("</body></html>")
    return "".join(p)


def sites_for_scope(site_scans, scope):
    """Scans gardés à montrer sur le spectre : Global (scope None) -> tous ; une scène (ou un de ses groupes)
    choisie dans « Mes fréquences » -> les scans de cette scène (le continu + ceux gardés à la main)."""
    if not scope:
        return site_visible(site_scans)
    names = {k[0] for k in scope if k}
    return [d for d in site_visible(site_scans) if site_doc_scene(d) in names]


def multi_site(dev_scenes, ndev, live=None):
    """Deux tinySA (vivants) rattachés à des scènes DIFFÉRENTES : chacun balaye toutes les bandes chez lui, au lieu de
    se les partager. dev_scenes = {n° appareil: [scènes]} (un ancien {n°: « scène »} est accepté)."""
    live = list(live) if live is not None else [True] * ndev
    sets = []
    for d in range(ndev):
        v = dev_scenes.get(d)
        v = [v] if isinstance(v, str) else list(v or [])
        if d < len(live) and live[d] and v:
            sets.append(frozenset(v))
    return ndev > 1 and len(set(sets)) > 1


def diversity_merge(entries, now, stale):
    """🔀 Diversity maison : deux tinySA sur deux antennes balayent la MÊME bande ; on garde, point par point, le
    meilleur niveau des balayages récents (comme un récepteur diversity choisit la meilleure antenne).
    entries = {n° appareil: (F, L, t)} ; un balayage plus vieux que `stale` s'il n'est pas le dernier reçu est ignoré.
    -> (F, L, src) : grille du balayage le plus récent, niveaux max, src = n° de l'appareil gagnant par point ;
    ou None si rien."""
    items = sorted(((t, d, F, L) for d, (F, L, t) in entries.items() if len(F)), key=lambda x: -x[0])
    if not items:
        return None
    t0, d0, F, L = items[0]
    F = np.asarray(F, dtype=float)
    best = np.asarray(L, dtype=float).copy()
    src = np.full(len(F), d0, dtype=int)
    for t, d, F2, L2 in items[1:]:
        if now - t > stale:
            continue
        F2, L2 = np.asarray(F2, dtype=float), np.asarray(L2, dtype=float)
        if F2.shape == F.shape and np.allclose(F2, F, atol=1e-6):
            l2 = L2
        else:                                      # grilles différentes : niveau de l'autre lu sur notre grille
            inside = (F >= F2[0] - 1e-9) & (F <= F2[-1] + 1e-9)
            l2 = np.where(inside, np.interp(F, F2, L2), -np.inf)
        win = l2 > best
        best = np.where(win, l2, best)
        src = np.where(win, d, src)
    return F, best, src


def diversity_share(srcs, ndev=2):
    """Part des points gagnés par chaque appareil (en %) -> [p0, p1…], pour voir que le diversity sert."""
    tot = np.zeros(ndev)
    for s_ in srcs:
        s_ = np.asarray(s_, dtype=int)
        for d in range(ndev):
            tot[d] += np.count_nonzero(s_ == d)
    n = tot.sum()
    return [round(float(x) * 100.0 / n) for x in tot] if n else [0] * ndev


def states_norm(lst):
    """📸 États (façon Snapshots du logiciel de coord) lus de la config / d'un show -> [{name, keys}] : noms uniques, clés = fréquences
    actives en kHz (entiers), 30 états au plus."""
    out, seen = [], set()
    for x in (lst if isinstance(lst, list) else []):
        if not isinstance(x, dict):
            continue
        name = re.sub(r"\s+", " ", str(x.get("name") or "")).strip()[:40]
        if not name or name.lower() in seen:
            continue
        keys = set()
        for k in (x.get("keys") if isinstance(x.get("keys"), list) else []):
            try:
                k = int(k)
            except (TypeError, ValueError):
                continue
            if 1000 <= k <= 7000000:
                keys.add(k)
        seen.add(name.lower())
        out.append(dict(name=name, keys=sorted(keys)))
        if len(out) >= 30:
            break
    return out


def state_off(state_keys, all_keys, iso_keys=()):
    """Fréquences mises en pause par un état : toutes sauf celles de l'état et les « toujours actives » (ISO)."""
    return set(all_keys) - set(state_keys) - set(iso_keys)


def dev_ord(d):
    """Rang d'un tinySA : « 1er », « 2ᵉ », « 3ᵉ »…"""
    return "1er" if int(d) == 0 else f"{int(d) + 1}ᵉ"


def devx_norm(lst, max_devs=8):
    """tinySA 3 à 8 lus (config / show) -> [{on, addr, name, offset}] (au plus max_devs − 2)."""
    out = []
    for x in (lst if isinstance(lst, list) else []):
        if not isinstance(x, dict):
            continue
        if len(out) >= max(0, max_devs - 2):
            break
        try:
            off = max(-40.0, min(40.0, float(x.get("offset", 0.0) or 0.0)))
        except (TypeError, ValueError):
            off = 0.0
        out.append(dict(on=bool(x.get("on", True)), addr=str(x.get("addr") or "").strip()[:120],
                        name=str(x.get("name") or "").strip()[:40], offset=round(off, 1)))
    return out


def dev_scenes_norm(d):
    """Scènes de chaque tinySA lues de la config -> {0: [..], 1: [..], …} (accepte l'ancien « dev_sites »)."""
    out = {}
    for k, v in (d.items() if isinstance(d, dict) else []):
        if str(k) not in [str(i) for i in range(8)]:
            continue
        v = [v] if isinstance(v, str) else (v if isinstance(v, list) else [])
        v = list(dict.fromkeys(str(x).strip()[:60] for x in v if str(x).strip()))
        if v:
            out[int(k)] = v
    return out


def palette_color(lines, idx=0):
    """Réponse de « color » (tinySA) -> couleur n° idx en entier (0xRRGGBB), ou None."""
    for ln in lines:
        m_ = re.match(r"\s*(\d+)\s*:\s*0x([0-9a-fA-F]{1,6})", str(ln))
        if m_ and int(m_.group(1)) == idx:
            return int(m_.group(2), 16)
    return None


def parse_deviceid(lines):
    """Réponse de « deviceid » -> numéro gravé dans le tinySA (0 = pas numéroté), ou None."""
    for ln in lines:
        m_ = re.match(r"\s*deviceid\s+(\d+)", str(ln))
        if m_:
            return int(m_.group(1))
    return None


# ------------------------------------------------------------------ 🎓 tutos intégrés et lexique (pour débutants complets)
TOURS = [
    ("ecran", "🖥 Découvrir l'écran", 3,
     "Chaque partie de la fenêtre, à quoi elle sert, où cliquer. Commence par celui-là si tu ouvres l'appli pour la "
     "première fois."),
    ("show", "🎤 Mon premier show, de A à Z", 10,
     "Le travail complet dans l'ordre : brancher, scanner le lieu, entrer ses fréquences, vérifier le plan, régler "
     "les alarmes, surveiller, puis revoir après le show."),
    ("spectre", "📈 Lire le spectre", 4,
     "Comprendre le graphique : fréquences, niveaux, bruit de fond, max hold, seuil, zoom, marqueurs. Sans "
     "connaissance préalable."),
    ("coord", "🪄 Coordonner ses fréquences", 5,
     "Trouver des fréquences qui ne se gênent pas : profils d'appareil, coordination auto, vérification du plan, "
     "intermodulation, fréquence de secours."),
    ("scenes", "🏟 Plusieurs scènes, tinySA volant", 5,
     "Festival à plusieurs scènes : ranger les fréquences par scène, garder un scan par lieu, le tinySA dans le sac "
     "(Raspberry Pi), la coordination par scène ou globale."),
    ("live", "🚨 Pendant le show", 4,
     "Réagir à une alarme, appeler les micros, le mur pour la régie, chasser un brouilleur, trouver une fréquence "
     "de secours, laisser tourner la nuit."),
]
TOUR_KEYS = [k for k, *_ in TOURS]

# 7.59 (Clément : « comment on rend tout ça intuitif, compréhensible ? ») : 🧭 assistant « Nouveau show » pas à pas,
# légende cliquable posée sur le spectre, propositions au bon moment (bandeau au-dessus du spectre).
WIZARD_STEPS = (
    ("show", "1. Le show", "Le pays donne la bande UHF des micros et les canaux TV ; le lieu (code postal) sert à "
     "trouver les émetteurs TNT proches.", "Donne un nom au show, choisis le pays, tape le code postal du lieu."),
    ("micros", "2. Mes micros", "La liste des fréquences à surveiller : ce que tu as coordonné (plan importé) ou ce que "
     "tu ajoutes à la main.", "Importe ton plan (EazyRF, WWB, WSM, Wisycom, DPA, tableau), colle une liste ou ajoute "
     "tes fréquences. Tu peux aussi le faire après le scan (« Depuis le scan »)."),
    ("scan", "3. Scanner le lieu", "Avant de surveiller, il faut savoir ce qui occupe déjà les ondes : TNT, autres "
     "équipes, talkies, écrans LED.", "Branche le tinySA là où seront les récepteurs, clique « Scanner ici » et laisse "
     "tourner au moins 5 minutes (idéalement pendant les essais lumière et écrans)."),
    ("tnt", "4. Les canaux TNT", "La TNT occupe des canaux entiers : il vaut mieux ne pas y poser de micros, ou alors "
     "bien au-dessus.", "Clique « Mesurer et griser » : les canaux pris par la TNT sont grisés sur le spectre. Tu peux "
     "en griser ou dégriser à la main dans le détail."),
    ("ready", "5. Prêt pour le show", "Une dernière vérification : tinySA, liste, son, alertes, enregistrement.",
     "Ouvre « Prêt pour le show ? », règle ce qui est en orange ou rouge, puis démarre la surveillance."),
)
WIZARD_SCAN_S = 300          # durée de scan conseillée (5 min)


def wizard_status(i):
    """État de chaque étape de l'assistant. i = dict(name, country_name, place, n_watch, running, scan_s, tnt_done,
    tnt_tv, ready) -> [(clé, fait ?, texte)]."""
    out = []
    nm = i.get("name") or ""
    out.append(("show", bool(nm),
                (f"Show « {nm} » · {i.get('country_name') or '?'}" if nm else "Pas encore de nom")
                + (f" · lieu {i['place']}" if i.get("place") else "")))
    n = int(i.get("n_watch") or 0)
    out.append(("micros", n > 0, f"{n} fréquence(s) dans ta liste" if n else "Liste vide"))
    sc = i.get("scan_s")
    if sc is None:
        out.append(("scan", False, "Pas de scan en cours"))
    else:
        m_, s_ = int(sc) // 60, int(sc) % 60
        ok = sc >= WIZARD_SCAN_S
        out.append(("scan", ok, f"Scan depuis {m_} min {s_:02d} s" + ("" if ok else " (5 min conseillées)")))
    if i.get("tnt_done"):
        out.append(("tnt", True, f"{int(i.get('tnt_tv') or 0)} canal(aux) TNT grisé(s)"))
    else:
        out.append(("tnt", False, "Pas encore mesuré"))
    lvl = i.get("ready")
    txt = {"ok": "Tout est prêt", "warn": "Quelques points à vérifier", "bad": "Il reste des problèmes"}.get(
        lvl, "Pas encore vérifié")
    out.append(("ready", lvl == "ok" and bool(i.get("running")),
                txt + (" · surveillance en cours" if i.get("running") else "")))
    return out


HINT_TNT_S = 300             # après 5 min de scan : « N canaux TNT trouvés »
HINT_EMPTY_S = 120           # surveillance sans liste depuis 2 min : « ajoute tes micros depuis le scan »


def hint_due(i, done):
    """Proposition à faire maintenant (une seule) ou None. i = dict(running, scan_s, tnt_tv, tnt_chs, tnt_marked,
    n_watch, run_s) ; done = clés déjà proposées. -> (clé, texte, [(libellé, méthode)])."""
    if (i.get("running") and (i.get("scan_s") or 0) >= HINT_TNT_S and int(i.get("tnt_tv") or 0) > 0
            and not i.get("tnt_marked") and "tnt" not in done):
        chs = ", ".join(str(c) for c in (i.get("tnt_chs") or [])[:8])
        return ("tnt", f"📺 {int(i['tnt_tv'])} canal(aux) TNT trouvé(s) dans ton scan ({chs}). Les griser sur le "
                       f"spectre pour ne pas y poser de micros ?",
                [("Griser", "hint_tnt_mark"), ("Voir le détail", "open_tnt")])
    if i.get("running") and (i.get("run_s") or 0) >= HINT_EMPTY_S and not i.get("n_watch") and "empty" not in done:
        return ("empty", "📡 Ta liste est vide : rien n'est surveillé. Ajouter les signaux vus dans le scan, ou "
                         "importer ton plan ?",
                [("Depuis le scan", "open_scan_add"), ("Importer", "import_watch")])
    return None


LEGEND_ITEMS = (
    ("curve", "Direct", "curve", "Le dernier balayage : ce que reçoit le tinySA maintenant. Le « tapis » du bas est le "
     "bruit de fond, une bosse qui en sort est un émetteur."),
    ("hold", "Pics gardés", "maxhold", "Le plus haut niveau vu à chaque fréquence depuis le dernier « Effacer les "
     "pics » : garde la trace des signaux brefs (talkie, brouilleur qui passe)."),
    ("thr", "Seuil", "thr", "Au-dessus, une fréquence est « occupée ». En Auto (tirets) : bruit de fond local + 12 dB, "
     "qui monte sur la TNT."),
    ("tnt", "TNT", "bp_tv", "Bandes bleutées « TNT n » : canaux pris par la télévision (mesurés, grisés à la main ou "
     "venus de ton plan). Évite d'y poser des micros."),
    ("mk", "Mes micros", "st_free", "Un trait par fréquence de ta liste, coloré selon l'état : vert OK, bleu libre, "
     "rouge problème, jaune faible."),
)


# 7.58.3 (Clément : « faut bien expliquer le seuil auto ») : fiche ❓ à côté de « Auto » (titre, paragraphes).
AUTO_THR_HELP = (
    ("La courbe en tirets", "C'est le seuil « occupé » de chaque fréquence : le bruit de fond LOCAL (mesuré sur ± 2 MHz "
     "autour) plus une marge, + 12 dB d'origine. Entre les canaux TV, le fond est le bruit du lieu (vers −100 dBm) : la "
     "courbe est donc vers −88. Elle bouge toute seule quand le lieu change (écran LED allumé, TNT qui varie)."),
    ("Pourquoi elle monte sur la TNT", "Dans un canal TNT, le fond local, c'est la TNT elle-même. Le seuil est donc "
     "« TNT + 12 dB » : ce n'est pas une erreur, c'est voulu."),
    ("Ce que ça change pour toi", "Un micro posé dans un canal TNT doit sortir 12 dB au-dessus de la TNT pour compter. "
     "S'il s'éteint, l'alarme ABSENT part bien. Avec un seuil sur le bruit pur, la TNT seule dépasserait le seuil : le "
     "canal serait toujours « occupé », l'ABSENT ne partirait jamais, et une réserve « doit rester libre » posée sur la "
     "TNT serait en CONFLIT en permanence."),
    ("La limite", "Dans un canal TNT, un signal plus faible que TNT + 12 dB ne se voit pas (le tinySA ne peut de toute "
     "façon pas le séparer d'une TNT forte). Pour savoir quels canaux sont pris par la TNT, utilise 📋 Préparer › "
     "📺 Canaux TNT : lui compare au vrai bruit du lieu."),
    ("Le bruit appris", "Le fond est appris en continu : il redescend vite (quelques secondes) mais remonte lentement "
     "(environ 10 minutes) et ne remonte jamais pendant qu'une fréquence est occupée. Un brouilleur qui s'installe ne "
     "peut donc pas « effacer » sa propre alarme en relevant le seuil."),
    ("Régler", "« bruit + 12 dB » (occupé) et « bruit + 6 dB » (faible) se règlent dans la barre au-dessus du spectre : "
     "plus petit = plus sensible, plus de fausses alertes. Une fréquence capricieuse (station faible pile au seuil) : "
     "clic droit › Seuil propre à la fréquence, il passe avant l'auto. Décoche Auto pour revenir à un seuil fixe pour "
     "tout le spectre."),
    ("Exemple", "Bruit du lieu −100 dBm, canal TNT à −82 dBm. Entre deux canaux : occupé dès −88. Dans le canal TNT : "
     "occupé dès −70, donc ton micro à −55 est vu, et s'il s'éteint, ABSENT."),
)


def auto_thr_help_html(tr=lambda t: t):
    """Fiche du seuil auto en HTML (chaque morceau traduit à part)."""
    return "".join(f"<p><b>{tr(t)}</b><br>{tr(x)}</p>" for t, x in AUTO_THR_HELP)


DEVICE_HELP = {   # 8.0 (Clément : « bien réexpliquer ce qu'est un tinySA et ce qu'est le SDR ») : bulles + lexique + manuel
    "tiny": "📟 tinySA = un petit analyseur de spectre. Il BALAYE toute une bande (par exemple 470–694 MHz), fréquence "
            "après fréquence, et mesure la puissance de chacune en dBm. Parfait pour SURVEILLER tous tes micros d'un coup "
            "et voir ce qui occupe le site. Il ne fait pas entendre le son.",
    "sdr": "📡 SDR = une radio logicielle (HackRF, SDRplay, RTL-SDR…). Elle reçoit d'un coup une FENÊTRE de quelques MHz, "
           "sans trou, et peut DÉMODULER : tu ENTENDS le son d'un micro analogique. Elle voit moins large d'un coup que "
           "le balayage du tinySA, et ses niveaux sont en vrais dBm une fois calés sur un tinySA. (Fonctions SDR en "
           "bêta.)",
    "both": "📟+📡 Les deux ensemble : le tinySA surveille tout le site, le SDR écoute et regarde de près un micro ou une "
            "zone.",
}
GLOSSARY = [
    ("HF", "Ici : tout ce qui passe par les ondes radio (micros sans fil, ears, talkies). Dans le métier on dit "
     "« la HF » pour l'ensemble des liaisons sans fil d'un spectacle."),
    ("tinySA", "Un petit analyseur de spectre : il balaye toute une bande, fréquence après fréquence, et mesure la "
     "puissance de chacune en dBm. C'est l'appareil de base de l'appli pour SURVEILLER tous tes micros. Il ne fait pas "
     "entendre le son."),
    ("SDR", "Radio logicielle (HackRF, SDRplay, RTL-SDR…) : elle reçoit d'un coup une fenêtre de quelques MHz, sans "
     "trou, et peut démoduler : tu entends un micro analogique. Moins large d'un coup que le tinySA ; ses niveaux sont "
     "justes une fois calés sur un tinySA. (Bêta.)"),
    ("Démoduler", "Retrouver le son transporté par une onde radio (ce que fait un récepteur de micro). Le SDR sait le "
     "faire, le tinySA non. Les micros numériques ne se démodulent pas : leur son est codé, souvent chiffré."),
    ("Fréquence (MHz)", "La « place » où émet un appareil, en mégahertz. Deux micros sur la même fréquence se "
     "brouillent. Exemple : 606,500 MHz. Les micros de spectacle sont surtout entre 470 et 694 MHz (UHF)."),
    ("Spectre", "Le graphique de l'appli : de gauche à droite les fréquences, de bas en haut la puissance reçue. Un "
     "émetteur fait une « bosse » (un pic) à sa fréquence."),
    ("dBm", "L'unité de puissance reçue. Plus le nombre est grand (proche de 0), plus c'est fort : −40 dBm est très "
     "fort, −90 dBm est faible, −110 dBm c'est le bruit. +10 dB = 10 fois plus de puissance."),
    ("dBµV", "Autre unité de niveau, utilisée par certains logiciels (Wisycom…). dBµV = dBm + 107."),
    ('dBFS', "Niveau d'un son NUMÉRIQUE par rapport au maximum possible (0 dBFS). Toujours négatif : au-dessus de 0, le son coupe. Les vu-mètres de l'appli (générateur, écoute SDR) sont en dBFS ; on cale souvent un récepteur avec un ton à −18 dBFS."),
    ('dBu / dBV', "Niveaux d'un son ANALOGIQUE (une tension). 0 dBu = 0,775 V, 0 dBV = 1 V (= +2,2 dBu). Niveau ligne pro : +4 dBu ; grand public : −10 dBV. Rien à voir avec le dBm de la RF."),
    ('Alignement (EBU, SMPTE)', 'La correspondance entre numérique et analogique de ton installation : EBU (Europe) −18 dBFS = 0 dBu ; SMPTE (USA) −20 dBFS = +4 dBu. Se règle dans 📏 Échelles et niveaux.'),
    ('True Peak (dBTP)', "La vraie crête d'un son numérique, y compris entre deux échantillons : elle peut dépasser 0 dBFS après conversion. On vise ≤ −1 dBTP."),
    ('Déviation FM', "De combien la fréquence d'un émetteur FM bouge avec le son (en kHz). Chaque appareil a une déviation nominale : trop de déviation = son qui sature au récepteur, trop peu = souffle. L'écoute SDR la mesure et la compare à la nominale."),
    ("Bruit de fond (tapis)", "Le niveau minimum que le tinySA voit même sans émetteur : son propre bruit plus celui "
     "du lieu (écrans LED, éclairage…). Tout ce qui dépasse franchement le tapis est un signal."),
    ("Balayage (sweep)", "Le tinySA mesure une fréquence après l'autre, de gauche à droite : un passage complet "
     "s'appelle un balayage. Il dure de moins d'une seconde à plusieurs secondes selon la largeur et le nombre de "
     "points."),
    ("Points", "Le nombre de mesures par balayage. Plus de points = plus de détails mais plus lent. « ⚡ Auto » choisit "
     "un bon compromis tout seul."),
    ("RBW", "La « finesse » de chaque mesure (largeur du filtre du tinySA). Fine = voit les petits signaux proches "
     "mais lente ; large = rapide mais deux signaux proches se confondent. Laisse en Auto si tu débutes."),
    ("Max hold", "La courbe orange : le plus haut niveau vu à chaque fréquence depuis le dernier « Reset max ». "
     "Elle garde la trace d'un émetteur même s'il n'a émis qu'une seconde."),
    ("Pics gardés", "Le nom du max hold en mode simple : la courbe orange, le plus haut niveau vu à chaque fréquence "
     "depuis « Effacer les pics »."),
    ("Rémanence", "Chaque balayage laisse une trace qui s'estompe peu à peu, comme sur un analyseur : ce qui est "
     "souvent là brille, ce qui passe rarement laisse une trace pâle (spectre de l'appli, bouton ⋯, et vues web "
     "Spectre / Terrain)."),
    ("Seuil auto", "Un seuil par fréquence = son bruit de fond local + une marge (+ 12 dB d'origine), dessiné en "
     "tirets. Sur un canal TNT, le fond local est la TNT : le seuil monte avec elle, pour qu'un micro posé dans ce "
     "canal reste surveillé (ABSENT). Fiche complète : bouton ❓ à côté de « Auto »."),
    ("Seuil « occupé »", "La ligne rouge : au-dessus, une fréquence est considérée comme occupée (quelqu'un émet). "
     "« Auto » le place un peu au-dessus du bruit de fond."),
    ("Seuil « faible »", "En dessous du seuil occupé : un signal qui dépasse ce niveau sans atteindre « occupé » est "
     "« faible » (émetteur loin, pile faible, ou bruit qui monte)."),
    ("Doit émettre (En service)", "Statut d'une fréquence où TON émetteur doit être allumé. S'il se tait trop "
     "longtemps : alarme ABSENT."),
    ("Doit rester libre (Libre)", "Statut d'une fréquence que tu gardes en réserve (secours, fréquence d'un autre "
     "jour…). Si un signal y apparaît : alarme CONFLIT."),
    ("ABSENT", "Alarme : un émetteur qui doit émettre ne se voit plus (pile vide, émetteur éteint, antenne "
     "débranchée, artiste trop loin)."),
    ("CONFLIT", "Alarme : un signal est apparu sur une fréquence qui devait rester libre (autre équipe, brouilleur, "
     "intermodulation)."),
    ("Acquitter", "Dire « j'ai vu » à une alarme : le son s'arrête, l'alarme reste affichée tant que le problème "
     "dure."),
    ("Intermodulation (IM)", "Quand plusieurs émetteurs sont proches, ils fabriquent des « fréquences fantômes » "
     "par calcul (ex. 2 × A − B). Si un fantôme tombe sur un de tes micros, il le brouille. La coordination sert "
     "surtout à éviter ça."),
    ("IM3 / IM5", "Ordre de l'intermodulation : le 3ᵉ ordre (2A − B, A + B − C) est le plus fort et le plus gênant, "
     "le 5ᵉ ordre (3A − 2B…) est plus faible."),
    ("Coordination", "Choisir les fréquences de tous les appareils pour qu'aucune ne gêne une autre : assez "
     "d'écart entre elles, pas d'intermodulation dessus, loin de ce qui est déjà occupé sur le lieu."),
    ("Plan de fréquences", "La liste finale des fréquences de tous tes appareils, une fois coordonnée."),
    ("Écart (séparation)", "La distance minimale entre deux porteuses pour qu'elles ne se gênent pas (ex. 300 à "
     "500 kHz selon les appareils)."),
    ("Filtre récepteur", "La tranche de spectre qui entre dans le récepteur autour de sa fréquence (présélection, ex. "
     "16 MHz : les émetteurs à ±16 MHz comptent). Pour le calcul, seuls les émetteurs dans cette tranche peuvent fabriquer de l'intermod dans "
     "ce récepteur. Ce chiffre ne dit pas à lui seul si un récepteur est bon : sa robustesse se règle avec l'écart et "
     "les tolérances du profil."),
    ("Profil d'appareil", "Les réglages de coordination d'une marque / gamme (écart, filtre, tolérances, pas). "
     "Choisis celui de ton matériel pour que les calculs collent."),
    ("Pas (incrément)", "Les fréquences possibles sur un appareil vont de pas en pas (ex. 25 kHz) : la "
     "coordination ne propose que des fréquences réglables sur ton appareil."),
    ("Porteuse", "Le signal d'un émetteur à sa fréquence (le pic sur le spectre)."),
    ("Bloc large (WMAS, Spectera)", "Certains systèmes numériques récents occupent un canal entier de 6 à 8 MHz au "
     "lieu d'une seule fréquence : sur le spectre, un plateau au lieu d'un pic."),
    ("TNT", "La télévision numérique terrestre : des plateaux de 8 MHz dans la bande UHF. Ces canaux sont pris, il "
     "faut les éviter (bandeau des canaux TV en bas du spectre)."),
    ("UHF", "La bande 470–694 MHz (en France) où travaillent la plupart des micros de spectacle, partagée avec la "
     "TNT."),
    ("Scène / groupe", "Le classement de tes fréquences : une scène = un lieu ou un plateau, un groupe = un ensemble "
     "(micros, ears, talkies…). Facultatif mais utile en festival."),
    ("Scan gardé", "Un spectre enregistré (le max hold à un moment, à un endroit) : sert de mémoire du lieu et pour "
     "la coordination."),
    ("Fusion", "Le mélange de plusieurs scans : on garde le niveau le plus fort de chacun, pour voir le pire cas de "
     "tout le site."),
    ("tinySA volant", "Un tinySA promené de scène en scène (dans un sac, avec un Raspberry Pi) pour scanner chaque "
     "lieu, pendant que le PC reste en régie."),
    ("Relais", "Le petit programme qui partage un tinySA sur le réseau (sur un Raspberry Pi ou un autre PC), pour "
     "que l'appli le voie à distance."),
    ("Line check (appel des micros)", "Avant le show : on allume chaque émetteur l'un après l'autre et l'appli coche "
     "ceux qu'elle voit, pour vérifier que tout est là."),
    ("Session", "L'enregistrement de tout ce que l'appli a vu pendant une surveillance, pour le revoir après "
     "(relecture)."),
    ("Show (🎪)", "Un fichier qui contient tout ton travail pour un événement (fréquences, scènes, bandes, scans…), "
     "à rouvrir l'année suivante."),
]


def glossary_find(text):
    """Lexique : les mots dont le nom ou l'explication contient le texte cherché (sans les accents ni la casse)."""
    def k(x):
        return "".join(c for c in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(c) != "Mn")
    q = k(text).strip()
    return [g for g in GLOSSARY if not q or q in k(g[0]) or q in k(g[1])]


def feature_match(items, query):
    """🔎 Chercher une fonction (Ctrl+K) : items = [(chemin du menu, bulle d'aide)] -> indices des entrées qui
    contiennent TOUS les mots cherchés (sans accents ni casse), d'abord celles où ils sont dans le nom."""
    def k(x):
        return "".join(c for c in unicodedata.normalize("NFD", str(x).lower()) if unicodedata.category(c) != "Mn")
    words = k(query).split()
    out = []
    for i, (name, tip) in enumerate(items):
        n_, t_ = k(name), k(tip)
        if all(w in n_ or w in t_ for w in words):
            out.append((0 if all(w in n_ for w in words) else 1, i))
    return [i for _r, i in sorted(out)]


# ------------------------------------------------------------------ ✅ prêt pour le show ?
READY_ICONS = {"ok": "✅", "warn": "⚠️", "bad": "❌", "info": "ℹ️"}


SLOW_CYCLE_S = 2.5          # 7.57.1 : tour complet plus long -> « Prêt ? » propose la RBW Auto si elle est forcée


def ready_checks(i):
    """Vérification avant le show. i = état de l'appli (dict, clés facultatives). -> liste de dict(key, level
    ok|warn|bad|info, title, text, fix) ; fix = nom d'une méthode de MainWindow qui ouvre le bon réglage (ou "")."""
    out = []

    def add(key, level, title, text, fix=""):
        out.append(dict(key=key, level=level, title=title, text=text, fix=fix))

    devs = i.get("devs") or []
    dead = [d["name"] for d in devs if not d.get("live", True)]
    age = i.get("sweep_age")
    if not i.get("running"):
        add("run", "bad", "Surveillance", "La surveillance est arrêtée : clique ▶ Démarrer.", "toggle_run")
    elif dead:
        add("run", "bad", "Surveillance", "Liaison perdue : " + ", ".join(dead) + ".", "open_devices")
    elif age is None or age > max(30.0, 3 * float(i.get("cycle") or 0)):
        add("run", "warn", "Surveillance", "Démarrée mais aucun balayage récent : le tinySA répond-il ?", "dump_diag")
    else:
        nd, cy = len(devs) or 1, float(i.get("cycle") or 0)
        add("run", "ok", "Surveillance", f"{nd} tinySA, cycle de {cy:.1f} s (démo : pas de vrai tinySA)."
            if i.get("demo") else f"{nd} tinySA, cycle de {cy:.1f} s.")
    rbw, cy = i.get("rbw"), float(i.get("cycle") or 0)
    if i.get("running") and not i.get("demo") and rbw and cy >= SLOW_CYCLE_S:
        add("speed", "warn", "Vitesse du balayage",
            f"Un tour complet prend {cy:.1f} s, avec la finesse de mesure (RBW) forcée à {rbw:g} kHz. En Auto, le tinySA "
            "choisit une RBW adaptée au pas et balaye souvent 2 à 4 fois plus vite (deux micros très proches se "
            "séparent alors moins bien : le zoom live garde une RBW fine).", "set_rbw_auto")
    if i.get("demo") and i.get("running"):
        add("demo", "bad", "Mode démo", "Le mode démo est coché : ce n'est pas le vrai spectre !", "toggle_demo_off")
    n, unc = int(i.get("watch_n") or 0), int(i.get("uncovered") or 0)
    if not n:
        add("watch", "bad", "Mes fréquences", "La liste est vide : rien n'est surveillé.", "import_watch")
    elif unc:
        add("watch", "bad", "Mes fréquences", f"{unc} fréquence(s) hors des bandes balayées : pas surveillées.",
            "new_band_dialog")
    else:
        add("watch", "ok", "Mes fréquences", f"{n} fréquence(s), toutes dans les bandes balayées.")
    nost = int(i.get("no_status") or 0)
    if n and nost:
        add("status", "warn", "Statuts", f"{nost} fréquence(s) sans statut : pas d'alarme CONFLIT ni ABSENT pour elles.",
            "")
    sat = i.get("sat")
    if sat in ("warn", "bad"):
        add("sat", "bad" if sat == "bad" else "warn", "Saturation",
            f"Le tinySA reçoit un signal très fort ({i.get('sat_dbm', 0):.0f} dBm) : ses mesures peuvent être fausses "
            "(niveaux écrasés, faux signaux). Éloigne l'antenne des émetteurs, coupe le LNA, ou ajoute de "
            "l'atténuation.", "open_measure")
    low = i.get("low_snr") or []
    if low:
        who = ", ".join(low[:4]) + (" …" if len(low) > 4 else "")
        add("snr", "warn", "Marge au-dessus du bruit",
            f"{len(low)} micro(s) à peine au-dessus du bruit ({who}) : rapproche l'antenne du tinySA ou vérifie les "
            "émetteurs.", "")
    rp = i.get("res_pairs") or []
    if rp:
        a_, b_, gap, r_ = rp[0]
        add("res", "warn", "Résolution",
            f"{len(rp)} paire(s) de fréquences trop proches pour la résolution actuelle (ex. {a_} et {b_} : "
            f"{gap * 1000:.0f} kHz d'écart, résolution {r_ * 1000:.0f} kHz) : elles se confondent sur le spectre. "
            "⚡ Points › Auto détaillé, ou un pas plus fin.", "")
    stale = int(i.get("stale") or 0)
    if stale and i.get("running"):
        add("stale", "warn", "Mesures anciennes",
            f"{stale} fréquence(s) sans mesure récente alors que la surveillance tourne.", "dump_diag")
    ro, rc, cn = i.get("reg_out") or [], i.get("reg_cond") or [], i.get("country_name") or ""
    if i.get("reg_unknown"):
        add("reg", "warn", "Bandes autorisées", f"Aucune liste de bandes autorisées pour {cn} : rien n'est vérifié "
            "réglementairement (renseigne-toi auprès du régulateur).", "open_country")
    if ro:
        lst = ", ".join(ro[:6]) + (" …" if len(ro) > 6 else "")
        add("reg", "warn", "Bandes autorisées", f"{len(ro)} émetteur(s) hors des bandes indiquées pour {cn} : {lst}. "
            "Indicatif : vérifie auprès du régulateur.", "open_country")
    elif rc:
        lst = ", ".join(rc[:6]) + (" …" if len(rc) > 6 else "")
        add("reg", "info", "Bandes autorisées", f"{len(rc)} émetteur(s) dans une bande sous condition ({cn}) : {lst}.",
            "open_country")
    lo_ = i.get("lora") or []
    if lo_:
        lst = ", ".join(lo_[:6]) + (" …" if len(lo_) > 6 else "")
        add("lora", "info", "Bande partagée avec l'IoT", f"{len(lo_)} émetteur(s) dans une bande LoRaWAN / IoT ({lst}) : des "
            "capteurs peuvent y émettre par paquets courts, sans prévenir. Garde de la marge ou une fréquence de secours.")
    mu = int(i.get("muted") or 0)
    if mu:
        add("muted", "info", "Éteints (je sais)", f"{mu} fréquence(s) en 💤 éteint (je sais) : pas d'alarme ABSENT pour "
            "elles. Rallume-les si elles doivent émettre.", "")
    pi = i.get("plan_issues")
    if pi is not None and n:
        if pi:
            add("plan", "warn", "Plan de fréquences", f"{pi} fréquence(s) avec un problème (écart ou intermod).",
                "open_plan_check")
        else:
            add("plan", "ok", "Plan de fréquences", "Aucun problème d'écart ni d'intermod.")
    if i.get("conflicts"):
        add("alarms", "bad", "Alarmes", f"{i['conflicts']} alarme(s) en cours.", "")
    snz = float(i.get("snooze") or 0)
    if snz > 0:
        add("snooze", "warn", "Son", f"Alarmes en silence encore {int(snz // 60) + 1} min.", "snooze_off")
    elif i.get("sound_device_missing"):
        add("sound", "bad", "Son", "La sortie audio choisie n'est pas branchée : les alarmes ne s'entendront pas.",
            "open_sound")
    elif int(i.get("volume", 70)) < 20:
        add("sound", "warn", "Son", "Volume des alarmes très bas.", "open_sound")
    else:
        add("sound", "ok", "Son", "Sortie audio prête. Clique « 🔊 Tester le son » pour l'entendre.")
    if i.get("notify_mode", "off") == "off":
        add("notify", "info", "Alertes téléphone", "Pas d'alertes sur le téléphone (ntfy / Telegram).", "open_alerts")
    elif not i.get("notify_ready"):
        add("notify", "bad", "Alertes téléphone", "Activées mais incomplètes (sujet ntfy ou jeton Telegram manquant).",
            "open_alerts")
    else:
        add("notify", "ok", "Alertes téléphone", "Prêtes. « 📨 Alerte test » pour vérifier sur le téléphone.")
    if i.get("web_on"):
        add("web", "ok" if i.get("web_up") else "bad", "Page web",
            i.get("web_url") or "Le serveur web ne répond pas (port déjà pris ?).", "" if i.get("web_up") else "open_alerts")
        if not i.get("web_pin"):
            add("pin", "info", "Page web", "Pas de code PIN : personne ne peut acquitter depuis un téléphone.",
                "open_alerts")
    if not i.get("show_path"):
        add("show", "warn", "Show", "Le show n'est enregistré dans aucun fichier (Ctrl+S).", "save_show")
    else:
        add("show", "ok", "Show", f"Enregistré : {i['show_path']}")
    if not i.get("session_rec"):
        add("rec", "info", "Enregistrement", "La session n'est pas enregistrée : pas de relecture après coup.",
            "open_settings_files")
    disk = i.get("disk_gb")
    if disk is not None:
        if disk < 1.0:
            add("disk", "bad", "Disque", f"Plus que {disk:.1f} Go libres pour les journaux et les enregistrements.")
        elif disk < 5.0:
            add("disk", "warn", "Disque", f"{disk:.1f} Go libres pour les journaux et les enregistrements.")
        else:
            add("disk", "ok", "Disque", f"{disk:.0f} Go libres.")
    if i.get("windows") and not i.get("guarded"):
        add("guard", "info", "Garde", "L'appli ne se relancera pas toute seule si elle plante (🌙 Mode festival › Garde).",
            "open_festival")
    elif i.get("guarded"):
        add("guard", "ok", "Garde", "L'appli se relance toute seule si elle plante ou se fige.")
    return out


def ready_summary(checks):
    """-> (niveau global, texte) : le plus grave des points."""
    bad = sum(c["level"] == "bad" for c in checks)
    warn = sum(c["level"] == "warn" for c in checks)
    if bad:
        return "bad", f"❌ {bad} problème(s) à régler avant le show"
    if warn:
        return "warn", f"⚠️ Presque prêt : {warn} point(s) à regarder"
    return "ok", "✅ Prêt pour le show !"


# ------------------------------------------------------------------ qualité de mesure (7.44, revue de code)
SNR_GOOD, SNR_OK, SNR_LOW = 20.0, 10.0, 6.0       # marge au-dessus du bruit (dB) : très bon / correct / juste
# Saturation : niveau MAX reçu par le tinySA au-delà duquel ses mesures deviennent douteuses (compression, faux
# signaux). Valeurs de départ prudentes, PAS mesurées sur un vrai tinySA Ultra (atténuateur auto) : à ajuster.
SAT_WARN, SAT_BAD = -25.0, -15.0
STOPPED_HEALTH = "■ Surveillance arrêtée : rien n'est surveillé en ce moment."
UNKNOWN_HEALTH = ("⚠ État de surveillance indéterminé : impossible de vérifier la fraîcheur des mesures "
                  "(voir crash.log). Vérifie le spectre et la liste.")
SAT_LNA_SHIFT = 15.0                                # préampli (LNA) en marche : sature ~15 dB plus tôt


def noise_floor(F, L, f, win=2.0, exclude=0.15, q=20.0):
    """Bruit de fond LOCAL autour de f (MHz) : 20ᵉ centile des points à ± win MHz, sans ceux à ± exclude de f (le
    signal lui-même). -> dBm ou None (pas assez de points)."""
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    if len(F) < 5:
        return None
    m = (np.abs(F - f) <= win) & (np.abs(F - f) > exclude) & np.isfinite(L)
    if m.sum() < 5:
        return None
    return float(np.percentile(L[m], q))


def snr_view(margin, keep_free=False):
    """Marge (dB au-dessus du bruit) -> (texte court, ton ok|warn|bad|none, explication)."""
    if margin is None:
        return "—", "none", "Pas encore de mesure."
    t = f"{margin:+.0f} dB"
    if keep_free:                                   # réserve : une grande marge = quelqu'un est dessus
        if margin >= SNR_OK:
            return t, "bad", "Un signal dépasse nettement le bruit sur cette réserve."
        return t, "ok", "Rien au-dessus du bruit : la réserve est propre."
    if margin >= SNR_GOOD:
        return t, "ok", "Très bon : le signal est largement au-dessus du bruit."
    if margin >= SNR_OK:
        return t, "ok", "Correct : le signal se distingue bien du bruit."
    if margin >= SNR_LOW:
        return t, "warn", "Juste : le signal dépasse à peine le bruit (antenne, distance, pile ?)."
    return t, "bad", "Noyé dans le bruit : on ne peut pas dire si l'émetteur est là."


def sat_level(max_dbm, lna=False):
    """Niveau le plus fort vu par le tinySA -> "ok" | "warn" | "bad" (risque de saturation)."""
    if max_dbm is None:
        return "ok"
    shift = SAT_LNA_SHIFT if lna else 0.0
    if max_dbm >= SAT_BAD - shift:
        return "bad"
    if max_dbm >= SAT_WARN - shift:
        return "warn"
    return "ok"


def resolution_pairs(items, res_mhz):
    """Fréquences trop proches pour être distinguées avec la résolution du balayage (pas ou RBW, en MHz).
    items = [(nom, MHz, résolution propre ou None)] -> [(nom1, nom2, écart MHz, résolution)]. Deux signaux à moins
    de 2 × résolution se confondent sur le spectre."""
    out = []
    its = sorted(items, key=lambda x: x[1])
    for (n1, f1, r1), (n2, f2, r2) in zip(its, its[1:]):
        r = max(r1 or res_mhz, r2 or res_mhz)
        if f2 - f1 < 2.0 * r - 1e-9:
            out.append((n1, n2, round(f2 - f1, 4), r))
    return out


# ------------------------------------------------------------------ 🩺 7.68 : diagnostic RF automatique
# Bruit de fond ATTENDU d'un tinySA Ultra (dBm/Hz) : valeurs de DÉPART (pas mesurées en labo) ; calées sur les scans de
# Clément (≈ −110 dBm en RBW ~100 kHz, préampli en marche).
NOISE_DBM_HZ = {True: -160.0, False: -150.0}       # préampli (LNA) en marche / arrêté
DIAG_NOISE_HIGH = 12.0      # bruit de fond plus haut que prévu de … dB -> à signaler
DIAG_ZONE_DB = 10.0         # zone plus bruyante que le reste de … dB (hors canaux TV) -> à signaler
DIAG_ZONE_MHZ = 2.0         # … sur au moins cette largeur
DIAG_FLAPS = 6              # changements libre <-> occupé en DIAG_FLAP_MIN minutes = « pile au seuil »
DIAG_FLAP_MIN = 30
DIAG_EDGE_DB = 4.0          # niveau à moins de … dB du seuil = pile au seuil
DIAG_TV_MARGIN = 10.0       # micro dans un canal TV : moins de … dB au-dessus de la télé = fragile
DIAG_ICONS = {"bad": "❌", "warn": "⚠️", "info": "ℹ️", "ok": "✅"}


def expected_floor(rbw_khz, lna=True):
    """Bruit de fond attendu (dBm) pour une RBW (kHz) : densité de bruit + 10·log10(RBW)."""
    if not rbw_khz or rbw_khz <= 0:
        return None
    return NOISE_DBM_HZ[bool(lna)] + 10.0 * math.log10(float(rbw_khz) * 1000.0)


def noisy_zones(Fc, Lc, ref, tv=(), above=DIAG_ZONE_DB, min_mhz=DIAG_ZONE_MHZ):
    """Zones où la courbe du bruit de fond (floor_curve) dépasse `ref` de `above` dB sur au moins `min_mhz`, hors canaux
    TV mesurés (tv = [(début, fin)]). -> [dict(lo, hi, excess)] (excès médian en dB), les plus fortes d'abord."""
    if Fc is None or Lc is None or ref is None:
        return []
    Fc, Lc = np.asarray(Fc, dtype=float), np.asarray(Lc, dtype=float)
    m = np.isfinite(Lc) & (Lc >= ref + above)
    for a, b in tv:
        m &= ~((Fc >= a - 0.5) & (Fc <= b + 0.5))
    out, i, n = [], 0, len(Fc)
    while i < n:
        if not m[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and m[j + 1]:
            j += 1
        if Fc[j] - Fc[i] >= min_mhz - 1e-9:
            out.append(dict(lo=float(Fc[i]), hi=float(Fc[j]), excess=float(np.median(Lc[i:j + 1]) - ref)))
        i = j + 1
    return sorted(out, key=lambda z: -z["excess"])


def flap_count(times, now, minutes=DIAG_FLAP_MIN):
    """Nombre de passages libre <-> occupé dans les `minutes` dernières minutes (times = heures des passages)."""
    return sum(1 for t in times or () if now - t <= minutes * 60.0)


def suggest_own_thr(level, floor, keep_on):
    """Seuil propre proposé pour un micro « pile au seuil » : sous son niveau habituel (il doit être vu présent) sans
    descendre dans le bruit ; pour une réserve ou sans statut : au-dessus du niveau qui clignote (le bruit ou une
    station faible ne doit plus la dire occupée). -> dBm arrondi ou None."""
    if level is None:
        return None
    if keep_on:
        v = level - 6.0
        if floor is not None:
            v = max(v, floor + 4.0)
        return float(round(v))
    return float(round(level + 6.0))


def rf_diagnose(i):
    """🩺 Diagnostic RF automatique : ce qui cloche dans la MESURE, en clair, avec quoi faire.
    i = dict (clés facultatives) : running, demo, F / L (spectre en direct, triés), rbw (kHz, None = auto), rbw_est,
    step_khz, lna, sat_dbm, thr (seuil global), thr_auto, tv = [(début, fin, canal)] mesurés « TV », unknown = [MHz]
    (signaux au-dessus du seuil hors liste), watch = [dict(key, name, freq, keep_free, keep_on, paused, level, typ
    (niveau habituel), floor, margin, ethr, own_thr, flaps, state, tv (canal TV où elle tombe ou None),
    tv_level)], fmt = fonction dBm -> texte (unité choisie).
    -> [dict(key, level bad|warn|info|ok, title, text, advice, fix, arg)] ; fix = méthode de MainWindow (ou ""),
    arg = argument(s) de cette méthode."""
    fmt = i.get("fmt") or (lambda v: f"{v:.0f} dBm")
    out = []

    def add(key, level, title, text, advice="", fix="", arg=None):
        out.append(dict(key=key, level=level, title=title, text=text, advice=advice, fix=fix, arg=arg))
    F, L = i.get("F"), i.get("L")
    if not i.get("running") or F is None or L is None or len(F) < 20:
        add("data", "info", "Pas de mesure en cours",
            "Le diagnostic lit le spectre en direct : lance la surveillance (▶ Démarrer) et attends un ou deux balayages.",
            fix="toggle_run")
        return out
    F, L = np.asarray(F, dtype=float), np.asarray(L, dtype=float)
    ok = np.isfinite(F) & np.isfinite(L)
    F, L = F[ok], L[ok]
    tv = list(i.get("tv") or [])
    tvm = np.zeros(len(F), dtype=bool)
    for a, b, _c in tv:
        tvm |= (F >= a) & (F <= b)
    rest = L[~tvm] if (~tvm).sum() >= 20 else L
    floor = float(np.percentile(rest, 20))
    lna = bool(i.get("lna"))
    # --- saturation
    sat = sat_level(i.get("sat_dbm"), lna)
    if sat != "ok":
        add("sat", "bad" if sat == "bad" else "warn", "Signal très fort : risque de saturation",
            f"Le tinySA reçoit jusqu'à {fmt(i['sat_dbm'])}. Au-delà de ce niveau il peut se saturer : faux signaux "
            "(intermod créée par le tinySA lui-même), bruit de fond qui monte, niveaux faux.",
            "Coupe le préampli (LNA) si il est en marche, ajoute de l'atténuation, ou éloigne l'antenne de l'émetteur "
            "le plus fort (souvent un émetteur ears / un rack de récepteurs).", "open_measure")
    # --- bruit de fond général
    rbw = i.get("rbw") or i.get("rbw_est")
    exp = expected_floor(rbw, lna)
    if exp is not None and floor > exp + DIAG_NOISE_HIGH:
        add("floor", "warn", "Bruit de fond plus haut que prévu",
            f"Bruit de fond à {fmt(floor)}, environ {floor - exp:.0f} dB au-dessus de ce qu'on attend pour cette finesse "
            f"de mesure (RBW {rbw:g} kHz{', préampli en marche' if lna else ''}). Les signaux faibles se noient.",
            ("Avec un signal très fort à côté, c'est sans doute le tinySA qui sature : règle d'abord ça.\n" if sat != "ok"
             else "") + "Causes fréquentes : écrans LED / murs vidéo, alimentations à découpage, ordinateur ou hub "
            "USB près de l'antenne, câble d'antenne abîmé. Essaie d'éloigner l'antenne, de changer de câble, puis "
            "relance le diagnostic.", "open_measure")
    # --- zones bruitées (hors TV)
    try:
        Fc, Lc = floor_curve(F, L)
        zones = noisy_zones(Fc, Lc, floor, [(a, b) for a, b, _c in tv])
    except Exception:  # noqa: BLE001
        zones = []
    for z in zones[:4]:
        c = (z["lo"] + z["hi"]) / 2.0
        add(f"zone{c:.1f}", "warn", f"Zone bruyante {z['lo']:.1f}–{z['hi']:.1f} MHz",
            f"Le bruit de fond y est {z['excess']:.0f} dB plus haut qu'ailleurs, et ce n'est pas un canal TV mesuré.",
            "Ça peut être un mur LED / écran, une liaison vidéo HF, un système large (Spectera, WMAS), ou une "
            "intermod. Évite d'y mettre des micros ; pour trouver la source : 🔎 Chasser.", "open_hunt", c)
    # --- seuil global (seuils fixes seulement)
    thr = i.get("thr")
    if thr is not None and not i.get("thr_auto"):
        frac = float(np.mean(rest >= thr))
        if thr - floor < 6.0 or frac > 0.25:
            add("thr_low", "bad", "Seuil « occupé » trop bas",
                f"Seuil à {fmt(thr)} pour un bruit de fond à {fmt(floor)} : {frac * 100:.0f} % du spectre (hors TV) "
                "passe pour « occupé ». Le bruit déclenche des fausses alarmes et des conflits.",
                f"Passe en seuils Auto (bruit de fond + marge, fréquence par fréquence), ou remonte le seuil à "
                f"{fmt(round(floor + 12))} environ.", "set_thr_auto", True)
        elif thr - floor > 35.0:
            add("thr_high", "warn", "Seuil « occupé » très haut",
                f"Seuil à {fmt(thr)}, {thr - floor:.0f} dB au-dessus du bruit de fond : un micro faible ou loin ne sera "
                "pas vu, et un brouilleur faible passera inaperçu.",
                f"Passe en seuils Auto, ou baisse le seuil vers {fmt(round(floor + 15))}.", "set_thr_auto", True)
    # --- résolution
    step = i.get("step_khz")
    if step and rbw and step > 1.5 * rbw:
        add("res", "warn", "Des signaux peuvent passer entre deux points",
            f"Un point tous les {step:.0f} kHz avec une finesse (RBW) de {rbw:g} kHz : un micro étroit qui tombe entre "
            "deux points est vu plus faible qu'il n'est, voire pas du tout.",
            "Mets plus de points (⚡ Points › Détaillé) ou la RBW en Auto.", "open_measure")
    # --- fréquences de la liste
    now_ws = [w for w in i.get("watch") or [] if not w.get("paused")]
    for w in now_ws:
        nm = w.get("name") or f"{w['freq']:.3f}"
        lv, typ = w.get("level"), w.get("typ") if w.get("typ") is not None else w.get("level")
        if w.get("flaps", 0) >= DIAG_FLAPS and w.get("ethr") is not None and typ is not None \
                and abs(typ - w["ethr"]) <= DIAG_EDGE_DB:
            sug = suggest_own_thr(typ, w.get("floor"), w.get("keep_on"))
            add(f"flap{w['key']}", "warn", f"{nm} : pile au seuil",
                f"{nm} ({w['freq']:.3f} MHz) a changé {w['flaps']} fois d'état en {DIAG_FLAP_MIN} min : son niveau "
                f"({fmt(typ)}) est pile au seuil ({fmt(w['ethr'])}). Ça remplit le journal et peut faire des "
                "alarmes à répétition.",
                (f"Donne-lui un seuil à elle : {fmt(sug)} (clic sur « Régler »)." if sug is not None else
                 "Donne-lui un seuil à elle (clic droit sur la ligne › seuil).")
                + ("\nSi c'est un émetteur que tu connais, mets-lui le statut « doit émettre »."
                   if not w.get("keep_on") and not w.get("keep_free") else ""),
                "diag_set_thr", (w["key"], sug))
        if w.get("tv") is not None and not w.get("keep_free") and lv is not None and w.get("tv_level") is not None:
            d = lv - w["tv_level"]
            if d < DIAG_TV_MARGIN:
                add(f"tv{w['key']}", "warn", f"{nm} : dans le canal TV {w['tv']}",
                    f"{nm} ({w['freq']:.3f} MHz) est dans le canal TV {w['tv']}, seulement {d:+.0f} dB au-dessus de la "
                    "télé. Le récepteur risque de décrocher dès que le micro s'éloigne.",
                    "Déplace-le hors du canal TV (🆘 Remplacer ce micro), ou rapproche les antennes de la scène.",
                    "open_replace_key", w["key"])
        elif w.get("keep_on") and w.get("margin") is not None and lv is not None and w.get("state") in ("weak", "occ") \
                and w["margin"] < SNR_LOW:
            add(f"snr{w['key']}", "warn", f"{nm} : à peine au-dessus du bruit",
                f"{nm} ne dépasse le bruit que de {w['margin']:.0f} dB : on ne peut pas dire de façon sûre s'il émet.",
                "Antenne de mesure plus près de la scène, pile de l'émetteur, ou préampli (LNA) en marche.",
                "open_measure")
    # --- signaux inconnus
    unk = sorted(set(round(float(x), 1) for x in i.get("unknown") or ()))
    if unk:
        lst = ", ".join(f"{x:.1f}" for x in unk[:6]) + (" …" if len(unk) > 6 else "")
        add("unk", "info", f"{len(unk)} signal(aux) hors de ta liste",
            f"Au-dessus du seuil mais pas dans « Mes fréquences » : {lst} MHz.",
            "Si ce sont tes émetteurs, ajoute-les (📡 Depuis le scan) ; sinon note-les et évite-les.", "open_scan_add")
    if not [x for x in out if x["level"] in ("bad", "warn")]:
        add("ok", "ok", "Rien d'anormal dans la mesure",
            (f"Bruit de fond à {fmt(floor)} (attendu ≈ {fmt(exp)})." if exp is not None else
             f"Bruit de fond à {fmt(floor)}.") + "\nPas de saturation, pas de zone bruyante hors TV, pas de micro "
            "pile au seuil.")
    rank = {"bad": 0, "warn": 1, "info": 2, "ok": 3}
    out.sort(key=lambda x: rank.get(x["level"], 4))
    return out


def rf_diag_summary(items):
    """-> (niveau le plus grave, phrase)."""
    bad = sum(1 for x in items if x["level"] == "bad")
    warn = sum(1 for x in items if x["level"] == "warn")
    if bad:
        return "bad", f"❌ {bad} problème(s) qui faussent la surveillance" + (f", {warn} point(s) à voir" if warn else "")
    if warn:
        return "warn", f"⚠️ {warn} point(s) à voir"
    if items and items[0]["key"] == "data":
        return "info", "ℹ️ Pas de mesure en cours"
    return "ok", "✅ Mesure saine"


# ------------------------------------------------------------------ accueil (7.43 : « écran de base imbuvable »)
def home_next(i):
    """Prochaine étape pour un débutant : "port" (brancher le tinySA), "list" (ajouter ses micros), "run" (démarrer)
    ou "" (tout tourne)."""
    if i.get("running"):
        return ""
    if not i.get("port") and not i.get("demo"):
        return "port"
    if not i.get("n_watch"):
        return "list"
    return "run"


def data_status(i):
    """État des DONNÉES (7.47, revue UX : « absence d'alarme ≠ absence de mesure ≠ mesure trop ancienne ≠ couverture
    incomplète ») : (ton, texte) ou None si les mesures sont fraîches et complètes. UNE seule logique, utilisée par
    l'accueil, le bandeau du mode Show et la vue Régie de la page web. i : last_age (s depuis la dernière mesure prise
    après ▶ Démarrer, None = aucune), run_age (s depuis ▶ Démarrer), stale_lim, stale_names, sat, sat_dbm."""
    if "last_age" not in i:
        return _sat_status(i)
    age, lim = i.get("last_age"), float(i.get("stale_lim") or 15.0)
    if age is None:
        run_age = float(i.get("run_age") or 0.0)
        if run_age > lim:                        # la 1re mesure n'arrive jamais : pas « en cours », c'est un problème
            return "bad", (f"⚠ Surveillance dégradée : aucune mesure depuis le démarrage ({run_age:.0f} s) — "
                           "tes micros ne sont PAS surveillés. Vérifie le tinySA (câble, réseau).")
        return "wait", "⏳ Premier balayage en cours… pas encore de mesure : tes micros ne sont pas encore surveillés."
    if age > lim:
        return "bad", (f"⚠ Surveillance dégradée : aucune mesure depuis {age:.0f} s — les états affichés sont "
                       "périmés. Vérifie le tinySA (câble, réseau).")
    if i.get("zoom"):
        return "warn", "🔍 Zoom live : seule la zone zoomée est mesurée, le reste de ta liste n'est pas surveillé."
    names = list(i.get("stale_names") or [])
    if names:
        shown = ", ".join(names[:4]) + (f" (+ {len(names) - 4})" if len(names) > 4 else "")
        return "warn", f"⚠ Surveillance partielle : pas de mesure pour {shown} — hors des bandes balayées ? (📶 Bandes)"
    return _sat_status(i)


def _sat_status(i):
    if i.get("sat") in ("warn", "bad"):
        return "warn", (f"⚠ Signal très fort à l'entrée du tinySA ({i.get('sat_dbm', 0):.0f} dBm) : mesures "
                        "peut-être faussées — éloigne l'antenne d'un émetteur ou ajoute de l'atténuation")
    return None


def home_status(i):
    """Grande phrase d'état de l'accueil -> (ton ok|warn|bad|idle, texte). i : running, demo, port, n_watch,
    alarms [(type, nom)], ok, free, weak, muted, lost (tinySA perdus)."""
    nxt = home_next(i)
    if nxt == "port":
        return "idle", "① Branche le tinySA en USB et allume-le (ou essaie le mode démo)."
    if nxt == "list":
        return "idle", "② Ajoute tes micros : importe ton plan de fréquences ou ajoute-les à la main."
    if nxt == "run":
        return "idle", "③ Prêt : clique ▶ Démarrer la surveillance."
    if i.get("lost"):
        who = ", ".join(i["lost"])
        return "bad", f"⚠ tinySA déconnecté : {who} — vérifie le câble (reconnexion automatique)"
    al = i.get("alarms") or []
    if al:
        shown = " · ".join(f"{n} : {k}" for k, n in al[:3]) + (f" (+ {len(al) - 3})" if len(al) > 3 else "")
        return "bad", f"⚠ {len(al)} problème(s) — {shown}"
    ds = data_status(i)
    if ds is not None:
        return ds
    bits = []
    if i.get("ok"):
        bits.append(f"{i['ok']} micro(s) OK")
    if i.get("free"):
        bits.append(f"{i['free']} réserve(s) libre(s)")
    if i.get("weak"):
        bits.append(f"{i['weak']} signal(aux) faible(s)")
    if i.get("silent"):
        bits.append(f"{i['silent']} micro(s) sans signal pour l'instant")
    if i.get("muted"):
        bits.append(f"{i['muted']} éteint(s) exprès")
    if i.get("demo"):
        bits.append("mode démo")
    if i.get("last_age") is not None:
        bits.append(f"mesure il y a {i['last_age']:.0f} s")
    if i.get("weak") or i.get("silent"):
        return "warn", "✔ Pas d'alarme — " + " · ".join(bits)
    return "ok", "✔ Tout va bien" + (" — " + " · ".join(bits) if bits else "")


# ------------------------------------------------------------------ mots simples (7.46, revue UX) : en ultra simple /
# simple, des mots de tous les jours ; le terme technique reste en expert et dans la bulle d'aide.
UI_WORDS = {
    "hold_chk": ("Pics gardés", "Max hold"),
    "reset_btn": ("Effacer les pics", "Reset max"),
}


def ui_word(key, expert):
    """Texte d'un contrôle selon le niveau : (simple, expert) de UI_WORDS ; clé inconnue -> ""."""
    simple, tech = UI_WORDS.get(key, ("", ""))
    return tech if expert else simple


# ------------------------------------------------------------------ fiches « problème » (7.46, revue UX : un débutant
# ne sait pas quoi faire de « PermissionError(13…) » ou « USB DISK MODE ACTIVE » -> ce qui se passe + quoi faire 1-2-3)
PROBLEM_CARDS = {
    "no_port": ("Aucun tinySA choisi",
                "L'appli ne sait pas encore sur quelle prise est ton tinySA.",
                ("Branche le tinySA sur le PC avec un câble USB qui transporte les données (pas un câble de charge "
                 "seule) et allume-le.",
                 "Clique sur « ① Le tinySA » puis choisis la ligne marquée ✔ tinySA (ou « Chercher à nouveau »).",
                 "Pas de tinySA sous la main ? Choisis « Mode démo » pour essayer l'appli.")),
    "busy": ("La prise du tinySA est déjà utilisée",
             "Un autre programme parle déjà au tinySA (tinySA-App, une 2ᵉ fenêtre de RF Technical Monitor…) : une seule "
             "application à la fois peut l'utiliser.",
             ("Ferme tinySA-App et tout autre logiciel du tinySA (ou l'autre fenêtre de RF Technical Monitor).",
              "Débranche le câble USB, attends 5 secondes, rebranche-le.",
              "Clique sur « Réessayer ».")),
    "gone": ("Le tinySA n'est pas trouvé",
             "La prise choisie ne répond pas : le tinySA est éteint, débranché, ou branché ailleurs.",
             ("Vérifie que le tinySA est allumé et que son écran affiche le spectre.",
              "Essaie un autre câble USB (beaucoup de câbles USB-C ne font que la charge) ou une autre prise du PC.",
              "Clique sur « ① Le tinySA › Chercher à nouveau », choisis la ligne ✔ tinySA, puis « Réessayer ».")),
    "usbdisk": ("Le tinySA n'est pas disponible",
                "Le tinySA est en mode « stockage USB » (il se présente comme une clé USB) : dans ce mode il refuse "
                "toute mesure.",
                ("Sur le tinySA : STORAGE › MORE › USB DISK pour sortir de ce mode (ou éteins-le).",
                 "Redémarre le tinySA normalement.",
                 "Rebranche-le au PC puis clique sur « Réessayer ».")),
    "fwupdate": ("Le tinySA se met à jour",
                 "Le tinySA est en train d'installer un nouveau firmware : il refuse les mesures pendant ce temps.",
                 ("Attends la fin de la mise à jour et le redémarrage du tinySA (ne le débranche pas).",
                  "Clique ensuite sur « Réessayer ».")),
    "mute": ("Le tinySA ne répond plus",
             "Le tinySA est relié mais ne répond pas aux commandes (il est peut-être figé ou dans un menu).",
             ("Sur le tinySA, quitte les menus ouverts (retour à l'écran du spectre).",
              "Débranche puis rebranche le câble USB (ou éteins / rallume le tinySA).",
              "Clique sur « Réessayer ». Si ça recommence : « 🩺 Diagnostic » et envoie le fichier.")),
    "net_refused": ("Le relais réseau ne répond pas",
                    "À cette adresse, il y a bien un appareil, mais le relais du tinySA n'y tourne pas (ou pas sur ce "
                    "port).",
                    ("Vérifie que le Raspberry Pi (ou l'autre PC) est allumé et que le tinySA y est branché.",
                     "Sur l'autre PC : « Partager ce tinySA » doit être lancé. Sur le Pi : le relais démarre tout seul "
                     "(compte 1 minute après l'allumage).",
                     "Vérifie le port (5025 d'habitude), puis « Réessayer ».")),
    "net_unreach": ("Adresse réseau injoignable",
                    "Le PC n'arrive pas à joindre cette adresse : appareil éteint, autre réseau Wi-Fi, ou adresse qui "
                    "a changé.",
                    ("Mets le PC et le Raspberry Pi (ou l'autre PC) sur le même réseau.",
                     "L'adresse du Pi change d'un réseau à l'autre : « 🔌 Matériel › Adresses réseau » puis « Tester ».",
                     "Un pare-feu peut bloquer : autorise RF Technical Monitor sur un réseau privé, puis « Réessayer ».")),
    "range": ("Bande de fréquences refusée",
              "Le tinySA refuse une des bandes à balayer (hors de ce qu'il sait mesurer).",
              ("Ouvre « Vue › Gérer les bandes » et vérifie le début et la fin de chaque bande (en MHz).",
               "Clique sur « Réessayer ».")),
    "segment": ("Trop de points d'un coup",
                "Le tinySA refuse un balayage aussi long en une seule commande.",
                ("Laisse « ⚡ Points » sur Auto, ou baisse le nombre de points.",
                 "Clique sur « Réessayer ».")),
    "lost": ("Liaison perdue avec le tinySA",
             "Le tinySA ne répond plus (câble, alimentation ou réseau). L'appli réessaie toute seule ; les autres "
             "tinySA, s'il y en a, reprennent ses bandes.",
             ("Vérifie le câble USB (ou le réseau / le Raspberry Pi) et que le tinySA est allumé.",
              "Si son écran est figé : débranche / rebranche l'USB, ou éteins / rallume le tinySA.",
              "Rien à faire de plus : dès qu'il revient, la surveillance reprend.")),
    "other": ("Le tinySA a renvoyé une erreur",
              "La mesure s'est arrêtée sur une erreur inattendue.",
              ("Clique sur « Réessayer ».",
               "Si ça recommence : débranche / rebranche le tinySA, ou essaie en mode démo pour vérifier l'appli.",
               "« 🩺 Diagnostic » crée un fichier à envoyer pour comprendre le problème.")),
}
_PROBLEM_KEYS = (                                 # expressions régulières sur le message en minuscules
    ("usbdisk", r"\b(disque usb|usb disk)"), ("fwupdate", r"\b(mise à jour son firmware|firmware update)"),
    ("range", r"\b(plage de fréquences|frequency range)"), ("segment", r"\b(nombre de points|exceeds range)"),
    ("busy", r"\b(permissionerror|accès refusé|access is denied|permission denied|resource busy|errno 1[36]\b)"),
    ("net_refused", r"\b(connection refused|connexion refusée|errno 111|10061|actively refused)"),
    ("net_unreach", r"\b(timed out|10060|unreachable|getaddrinfo|name or service not known|no route|errno 11[03]\b|"
                    r"errno 101|11001|nodename)"),
    ("mute", r"\b(muet|pas de réponse|aucune mesure|inutilisable)"),
    ("gone", r"\b(introuvable|filenotfound|no such file|could not open port|cannot find|le fichier spécifié|errno 2\b|"
             r"not found)"),
)


def problem_key(msg):
    """Message d'erreur brut (pyserial, socket, tinySA) -> clé de PROBLEM_CARDS."""
    low = str(msg or "").lower()
    return next((k for k, rx in _PROBLEM_KEYS if re.search(rx, low)), "other")


# conséquence sur la surveillance et état réel après l'erreur (7.47, revue UX : « rassurer sans masquer »)
PROBLEM_IMPACT = {
    "no_port": "Rien n'est mesuré : la surveillance n'a pas démarré.",
    "lost": "Les fréquences de ce tinySA ne sont plus mesurées (sauf si un autre tinySA reprend ses bandes). L'appli "
            "réessaie toute seule ; l'alarme APPAREIL reste affichée tant qu'il n'est pas revenu.",
}
PROBLEM_IMPACT_DEFAULT = ("La surveillance est arrêtée : tes micros ne sont PAS surveillés en ce moment. Tes réglages "
                          "et ta liste sont conservés.")


def problem_card(msg="", key=None):
    """-> dict(key, title, what, steps, impact, detail) : fiche lisible par un débutant ; impact = conséquence sur la
    surveillance ; detail = message technique d'origine."""
    k = key or problem_key(msg)
    title, what, steps = PROBLEM_CARDS.get(k, PROBLEM_CARDS["other"])
    return dict(key=k, title=title, what=what, steps=list(steps), impact=PROBLEM_IMPACT.get(k, PROBLEM_IMPACT_DEFAULT),
                detail=str(msg or ""))


# ---------------------------------------------------------------- 7.67 : perturbations qui reviennent (journal)
RECUR_KINDS = ("CONFLIT", "INTERMOD", "ABSENT", "OCCUPÉ", "INCONNU", "TROP FORT", "APPAREIL PERDU")
RECUR_LABELS = {"CONFLIT": "signal sur une réserve", "INTERMOD": "intermod sur une réserve",
                "ABSENT": "micro qui décroche", "OCCUPÉ": "signal présent", "INCONNU": "signal inconnu",
                "TROP FORT": "signal trop fort", "APPAREIL PERDU": "tinySA perdu"}


def journal_csv_rows(text):
    """Journal automatique (journal_AAAAMMJJ.csv, « ; ») -> [dict(day "AAAA-MM-JJ", minute (0-1439), sec, name, mhz,
    kind, status, scene, group)]. kind = l'événement sans sa durée (« Libre (3 s) » -> « Libre »)."""
    out = []
    rd = csv.reader(io.StringIO(str(text or "").lstrip("﻿")), delimiter=";")
    for row in rd:
        if len(row) < 6 or row[0].strip().lower() in ("date", ""):
            continue
        day, hm = row[0].strip(), row[1].strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", hm)
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day) or not m:
            continue
        try:
            mhz = float(row[3].replace(",", ".")) if row[3].strip() not in ("", "—", "-") else None
        except ValueError:
            mhz = None
        h, mi, se = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        out.append(dict(day=day, minute=h * 60 + mi, sec=h * 3600 + mi * 60 + se, name=row[2].strip(), mhz=mhz,
                        kind=row[5].split(" (")[0].strip(), status=row[6].strip() if len(row) > 6 else "",
                        scene=row[7].strip() if len(row) > 7 else "", group=row[8].strip() if len(row) > 8 else ""))
    return out


def _circ_dist(a, b):
    d = abs(int(a) - int(b)) % 1440
    return min(d, 1440 - d)


def recurring_events(rows, kinds=RECUR_KINDS, tol=20, min_days=2, on_statuses=(), min_share=0.0):
    """Perturbations qui reviennent à la même heure sur plusieurs jours (journal de plusieurs jours).
    rows = journal_csv_rows(...) ; on_statuses : statuts « doit émettre » (leur OCCUPÉ = le micro est là, ignoré).
    -> [dict(kind, name, mhz, days, total_days, center (minute), spread (min), count, dates)] du plus fréquent au
    moins fréquent. Un même événement au même endroit, ±tol minutes, au moins min_days jours différents."""
    kinds = set(kinds or RECUR_KINDS)
    on = set(on_statuses or ())
    all_days = sorted({r["day"] for r in rows})
    groups = {}
    for r in rows:
        k = r["kind"]
        if k not in kinds or (k == "OCCUPÉ" and r["status"] in on):
            continue
        key = (k, r["name"], round(r["mhz"], 3) if r["mhz"] is not None else None)
        groups.setdefault(key, []).append((r["day"], r["minute"]))
    out = []
    for (k, name, mhz), ev in groups.items():
        left = list(ev)
        while left:
            best = None
            for _d, m0 in left:
                near = [x for x in left if _circ_dist(x[1], m0) <= tol]
                nd = len({d for d, _m in near})
                if best is None or nd > best[0] or (nd == best[0] and len(near) > len(best[2])):
                    best = (nd, m0, near)
            nd, m0, near = best
            if nd < max(2, int(min_days)):
                break
            ang = [2 * math.pi * m / 1440.0 for _d, m in near]
            c = math.atan2(sum(math.sin(x) for x in ang), sum(math.cos(x) for x in ang))
            center = int(round((c % (2 * math.pi)) * 1440.0 / (2 * math.pi))) % 1440
            spread = max(_circ_dist(m, center) for _d, m in near)
            days = sorted({d for d, _m in near})
            share = len(days) / max(1, len(all_days))
            if share >= min_share:
                out.append(dict(kind=k, name=name, mhz=mhz, days=len(days), total_days=len(all_days), center=center,
                                spread=int(spread), count=len(near), dates=days))
            used = set(map(id, near))
            left = [x for x in left if id(x) not in used]      # mêmes objets que dans left : on en retire au moins 1
    out.sort(key=lambda d: (-d["days"], -d["count"], d["center"]))
    return out


def recurring_text(p, tr=None):
    """« CONFLIT · HF 3 (556,000 MHz) : 3 jours sur 4 vers 19:05 (± 12 min) »."""
    tr = tr or (lambda x: x)
    where = p["name"] + (f" ({p['mhz']:.3f} MHz)" if p["mhz"] is not None and p["name"] != f"{p['mhz']:.3f}" else "")
    hm = f"{p['center'] // 60:02d}:{p['center'] % 60:02d}"
    return (f"{tr(p['kind'])} · {where} : " + tr("{} jours sur {} vers {} (± {} min)").format(
        p["days"], p["total_days"], hm, p["spread"]) + f" · {p['count']} " + tr("fois"))


# ---------------------------------------------------------------- 7.67 : dossier de préparation (PDF / HTML)
PREP_CSS = ("body{font-family:'Segoe UI',Arial,sans-serif;font-size:10pt;color:#1d1d1f}"
            "h1{font-size:18pt;margin:0 0 4px 0}h2{font-size:13pt;margin:14px 0 4px 0;color:#0a5bd3}"
            "h3{font-size:11pt;margin:10px 0 2px 0}.mut{color:#6e6e73}.warn{color:#b25000}"
            "table{border-collapse:collapse;width:100%}th{background:#eef2f8;text-align:left}"
            "th,td{border:1px solid #c7ccd6;padding:3px 6px}td.n{text-align:right}")


def prep_dates(a, b):
    """Dates du show pour le dossier : « 12/11/2026 » (un seul jour) ou « 12/11/2026 – 14/11/2026 »."""
    def f(x):
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(x or "").strip())
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(x or "").strip()
    a, b = f(a), f(b)
    if a and b and a != b:
        return f"{a} – {b}"
    return a or b


def prep_html(info, tr=None, img=None):
    """Dossier de préparation d'un show (à imprimer / envoyer) : infos du show, plan de fréquences par scène ›
    groupe, réglementation du pays, canaux TNT, scans du lieu (avec leur RBW), vérification du plan.
    info : dict(title, place, dates, country, generated, rows=[dict(scene, group, name, mhz, status, rx, note, reg,
    off)], reg_lines, tnt=[dict(ch, lo, hi, state)], scans=[dict(name, scene, date, lo, hi, rbw)], plan=dict(n, lines,
    reduced) | None, notes) ; img : source de l'image du spectre (None = pas d'image)."""
    tr = tr or (lambda x: x)
    e = html_esc
    p = [f"<html><head><meta charset='utf-8'><style>{PREP_CSS}</style></head><body>"]
    p.append(f"<h1>{e(info.get('title') or tr('Dossier de préparation'))}</h1>")
    sub = " · ".join(x for x in (info.get("place"), info.get("dates"), info.get("country")) if x)
    if sub:
        p.append(f"<div>{e(sub)}</div>")
    p.append(f"<div class='mut'>{e(tr('Généré le'))} {e(info.get('generated', ''))} · RF Technical Monitor</div>")
    rows = info.get("rows") or []
    on_air = [r for r in rows if not r.get("off")]
    scenes = []
    for r in rows:
        if r["scene"] not in scenes:
            scenes.append(r["scene"])
    p.append(f"<h2>{e(tr('En résumé'))}</h2><ul>")
    p.append("<li>" + e(tr("{} fréquence(s) dans le plan, {} scène(s)").format(len(rows), len([s for s in scenes if s])))
             + "</li>")
    n_st = sum(1 for r in rows if r.get("why", "state" if r.get("off") else "") == "state")
    n_mu = sum(1 for r in rows if r.get("why") == "muted")
    if n_st:
        p.append("<li>" + e(tr("{} hors de l'état actif « {} » (pas surveillées en ce moment)").format(
            n_st, info.get("state") or "?") if info.get("state") else
            tr("{} en pause (état)").format(n_st)) + "</li>")
    if n_mu:
        p.append("<li>" + e(tr("{} éteinte(s) exprès (je sais)").format(n_mu)) + "</li>")
    regs = [r for r in rows if r.get("reg")]
    if regs:
        p.append("<li class='warn'>" + e(tr("{} fréquence(s) à vérifier côté réglementation (voir la colonne « Réglementation »)")
                                        .format(len(regs))) + "</li>")
    pl = info.get("plan")
    if pl is not None:
        p.append("<li" + (" class='warn'" if pl.get("n") else "") + ">" + e(
            tr("Vérification du plan : {} problème(s)").format(pl.get("n", 0)) if pl.get("n") else
            tr("Vérification du plan : aucun problème trouvé")) + "</li>")
    tv = [t for t in info.get("tnt") or [] if t.get("state") == "tv"]
    if tv:
        p.append("<li>" + e(tr("Canaux TV occupés ici : {}").format(", ".join(str(t["ch"]) for t in tv))) + "</li>")
    p.append("</ul>")
    if img:
        iw = int(info.get("img_w") or 0)
        p.append(f"<h2>{e(tr('Spectre du lieu'))}</h2><p><img src='{e(img)}' "
                 + (f"width='{iw}'" if iw else "style='width:100%'") + "></p>")
    p.append(f"<h2>{e(tr('Plan de fréquences'))}</h2>")
    has_reg = any(r.get("reg") for r in rows)          # 7.67.1 : colonnes vides retirées
    has_note = any(r.get("note") for r in rows)
    has_rx = any(r.get("rx") for r in rows)
    for sc in scenes:
        p.append(f"<h3>{e(sc or tr('Sans scène'))}</h3><table width='100%' cellspacing='0' cellpadding='3' border='1'>"
                 f"<tr><th>{e(tr('Groupe'))}</th><th>{e(tr('Nom'))}</th><th>MHz</th><th>{e(tr('Statut'))}</th>"
                 + (f"<th>{e(tr('Appareil'))}</th>" if has_rx else "")
                 + (f"<th>{e(tr('Réglementation'))}</th>" if has_reg else "")
                 + (f"<th>{e(tr('Note'))}</th>" if has_note else "") + "</tr>")
        prev = None
        for r in [x for x in rows if x["scene"] == sc]:
            st = r.get("status") or ""
            why = r.get("why", "state" if r.get("off") else "")
            if why:
                st = (st + " · " if st else "") + (tr("éteint (je sais)") if why == "muted" else tr("hors état"))
            g = r.get("group") or ""
            p.append(f"<tr><td>{e(g if g != prev else '')}</td><td>{e(r['name'])}</td><td class='n'>{r['mhz']:.3f}</td>"
                     f"<td{' class=mut' if why else ''}>{e(st)}</td>"
                     + (f"<td>{e(r.get('rx') or '')}</td>" if has_rx else "")
                     + (f"<td class='warn'>{e(tr(r['reg']) if r.get('reg') else '')}</td>" if has_reg else "")
                     + (f"<td>{e(r.get('note') or '')}</td>" if has_note else "") + "</tr>")
            prev = g
        p.append("</table>")
    if info.get("reg_lines"):
        p.append(f"<h2>{e(tr('Réglementation du pays (indicatif)'))}</h2><ul>")
        p.extend(f"<li>{e(x)}</li>" for x in info["reg_lines"])
        p.append("</ul>")
    if info.get("tnt"):
        lab = {"tv": tr("TV"), "free": tr("libre"), "other": tr("autre signal"), "none": tr("pas mesuré")}
        p.append(f"<h2>{e(tr('Canaux TNT'))}</h2><table width='100%' cellspacing='0' cellpadding='3' border='1'><tr><th>{e(tr('Canal'))}</th><th>MHz</th>"
                 f"<th>{e(tr('État'))}</th></tr>")
        for t in info["tnt"]:
            p.append(f"<tr><td>{t['ch']}</td><td>{t['lo']:g}–{t['hi']:g}</td><td>{e(lab.get(t['state'], t['state']))}"
                     "</td></tr>")
        p.append("</table>")
    if info.get("scans"):
        p.append(f"<h2>{e(tr('Scans du lieu'))}</h2><table width='100%' cellspacing='0' cellpadding='3' border='1'><tr><th>{e(tr('Scan'))}</th><th>{e(tr('Scène'))}</th>"
                 f"<th>{e(tr('Date'))}</th><th>MHz</th><th>RBW</th></tr>")
        for d in info["scans"]:
            p.append(f"<tr><td>{e(d['name'])}</td><td>{e(d.get('scene') or '')}</td><td>{e(d.get('date') or '')}</td>"
                     f"<td>{d['lo']:.3f}–{d['hi']:.3f}</td><td>{e(rbw_text(d.get('rbw'), d.get('rbw_est'), tr))}</td></tr>")
        p.append("</table>")
    if pl is not None and pl.get("lines"):
        p.append(f"<h2>{e(tr('Vérification du plan'))}</h2><ul>")
        p.extend(f"<li>{e(x)}</li>" for x in pl["lines"][:40])
        if len(pl["lines"]) > 40:
            p.append("<li>" + e(tr("… et {} autre(s)").format(len(pl["lines"]) - 40)) + "</li>")
        p.append("</ul>")
    if info.get("notes"):
        p.append(f"<h2>{e(tr('Notes'))}</h2><p>{e(info['notes'])}</p>")
    if info.get("disclaimer"):
        p.append(f"<p class='mut'>{e(tr(info['disclaimer']))}</p>")
    p.append("</body></html>")
    return "".join(p)


# 8.0.2 (Clément : « un vrai mode double écran ou plus : tinySA complet sur l'un, SDR complet sur l'autre, ou un mix
# qu'on choisit ») : chaque panneau va sur l'écran choisi ; un écran autre que celui de la fenêtre principale reçoit
# une fenêtre complète qui réunit ses panneaux (rangés, en onglets…).
SCREEN_PANELS = (
    ("dock_spectre", "tiny", "📟 Spectre tinySA"),
    ("dock_wf", "tiny", "📟 Waterfall tinySA"),
    ("dock_alarmes", "tiny", "🔔 Alarmes"),
    ("dock_freq", "list", "📋 Mes fréquences"),
    ("dock_journal", "list", "📝 Journal"),
    ("dock_sdr_rx", "sdr", "📡 SDR · Récepteur"),
    ("dock_sdr_spec", "sdr", "📡 SDR · Spectre"),
    ("dock_sdr_wf", "sdr", "📡 SDR · Waterfall"),
    ("dock_sdr_mics", "sdr", "📡 SDR · Mes micros"),
    ("dock_lab_chain", "lab", "🧪 Labo · Chaîne complète"),        # 8.2 : labo SDR en panneaux
    ("dock_lab_cmp", "lab", "🧪 Labo · Compandeurs"),
    ("dock_lab_live", "lab", "🧪 Labo · En direct (SDR)"),
    ("dock_lab_mod", "lab", "🧪 Labo · Modulations"),
    ("dock_lab_fault", "lab", "🧪 Labo · Pannes simulées"),
)
SCREEN_PRESETS = (
    ("tiny_sdr", "📟 tinySA ici · 📡 SDR sur l'autre écran"),
    ("sdr_tiny", "📡 SDR ici · 📟 tinySA sur l'autre écran"),
    ("list_out", "📋 Mes fréquences et journal sur l'autre écran"),
    ("all_here", "🧩 Tout dans la fenêtre principale"),
)
SCREEN_HIDE = -1


def screen_preset(key, main=0, other=1, sdr=True):
    """Plan {panneau: n° d'écran (0 = 1er), -1 = caché} d'un préréglage. sdr : le SDR est utilisé (sinon ses panneaux
    restent cachés quand le préréglage ne les demande pas)."""
    plan = {}
    for n, g, _t in SCREEN_PANELS:
        if key == "tiny_sdr":
            v = other if g == "sdr" else main
        elif key == "sdr_tiny":
            v = other if g == "tiny" else main
        elif key == "list_out":
            v = other if g == "list" else main
        else:
            v = main
        if g == "sdr" and not sdr and key not in ("tiny_sdr", "sdr_tiny"):
            v = SCREEN_HIDE
        if g == "lab":
            v = SCREEN_HIDE                                  # 8.2 : le labo ne s'ouvre que si on le demande
        if n == "dock_alarmes" and key == "all_here":
            v = SCREEN_HIDE                                  # comme la disposition de base (bandeau au besoin)
        plan[n] = v
    return plan


def screens_norm(d, nscr=8):
    """Config « screens » : {on, plan {panneau: écran | -1}, full, hosts {écran: {geo, state}}} nettoyée."""
    d = d if isinstance(d, dict) else {}
    names = {n for n, _g, _t in SCREEN_PANELS}
    plan = {}
    if isinstance(d.get("plan"), dict):
        for n, v in d["plan"].items():
            if n in names and isinstance(v, int) and not isinstance(v, bool) and SCREEN_HIDE <= v < nscr:
                plan[n] = v
    hosts = {}
    if isinstance(d.get("hosts"), dict):
        for k, v in d["hosts"].items():
            if isinstance(v, dict) and str(k).isdigit():
                hosts[str(k)] = {x: str(v[x]) for x in ("geo", "state") if isinstance(v.get(x), str)}
    return dict(on=bool(d.get("on")) and bool(plan), plan=plan, full=bool(d.get("full")), hosts=hosts)


def screens_used(plan, main):
    """Écrans (autres que celui de la fenêtre principale) qui reçoivent au moins un panneau."""
    return sorted({v for v in (plan or {}).values() if v >= 0 and v != main})


def screen_rf_mode(plan):
    """Mode d'après les panneaux montrés : tinySA, SDR ou combiné."""
    groups = {n: g for n, g, _t in SCREEN_PANELS}
    shown = {groups[n] for n, v in (plan or {}).items() if v >= 0 and n in groups and n != "dock_alarmes"}
    tiny, sdr = "tiny" in shown, "sdr" in shown
    return "both" if tiny and sdr else ("sdr" if sdr else "tiny")


def screen_plan_fit(plan, nscr, main):
    """Écran débranché depuis : ses panneaux reviennent dans la fenêtre principale."""
    return {n: (v if v < nscr else main) for n, v in (plan or {}).items()}


# ---------------------------------------------------------------- 8.1 : échelles de niveau (Clément : « absolument une
# échelle en dB pour caler des récepteurs à −18 dBFS, choisir la réf en dBu / dBV…, un vu-mètre et un niveau à atteindre,
# en émission ET en réception ; garder dBm, dBW, dBµW, dBµV ; tout réexpliquer dans un tableau »).
AUDIO_UNITS = (("dbfs", "dBFS"), ("dbu", "dBu"), ("dbv", "dBV"), ("vrms", "V RMS"), ("vu", "dB VU"), ("dbr", "dBr"))
AUDIO_ALIGNS = (("ebu", "EBU R68 : −18 dBFS = 0 dBu", -18.0, 0.0),
                ("smpte", "SMPTE RP155 : −20 dBFS = +4 dBu", -20.0, 4.0),
                ("k14", "Broadcast / streaming : −14 dBFS = +4 dBu", -14.0, 4.0),
                ("custom", "Personnalisé", -18.0, 0.0))
AUDIO_REF_DEFAULT = dict(unit="dbfs", align="ebu", dbfs=-18.0, dbu=0.0, dbr=-18.0, target=-18.0)
DBU_V = 0.7746                       # 0 dBu = 0,775 V RMS (1 mW sur 600 Ω)
DBV_DBU = 2.2185                     # 0 dBV = 1 V = +2,21 dBu


def audio_ref_norm(d):
    """Préférences d'échelle audio : unité d'affichage, alignement numérique / analogique, référence dBr, niveau visé."""
    d = d if isinstance(d, dict) else {}
    out = dict(AUDIO_REF_DEFAULT)
    if d.get("unit") in dict(AUDIO_UNITS):
        out["unit"] = d["unit"]
    if d.get("align") in [a[0] for a in AUDIO_ALIGNS]:
        out["align"] = d["align"]
    for k, lo, hi in (("dbfs", -60.0, 0.0), ("dbu", -40.0, 30.0), ("dbr", -60.0, 0.0), ("target", -60.0, 0.0)):
        try:
            out[k] = min(hi, max(lo, float(d.get(k, out[k]))))
        except (TypeError, ValueError):
            pass
    return out


def audio_align(ref):
    """(dBFS, dBu) qui se correspondent selon l'alignement choisi."""
    ref = audio_ref_norm(ref)
    a = next(x for x in AUDIO_ALIGNS if x[0] == ref["align"])
    return (ref["dbfs"], ref["dbu"]) if a[0] == "custom" else (a[2], a[3])


def dbfs_to_unit(dbfs, ref, unit=None):
    """dBFS (crête d'un sinus = 0 dBFS, convention AES17) -> unité choisie : dBu = dBFS − réf. dBFS + réf. dBu ;
    dBV = dBu − 2,21 ; V RMS = 0,775 × 10^(dBu/20) ; dB VU = dBu − 4 ; dBr = dBFS − référence dBr."""
    if dbfs is None:
        return None
    ref = audio_ref_norm(ref)
    unit = unit or ref["unit"]
    a_fs, a_u = audio_align(ref)
    dbu = float(dbfs) - a_fs + a_u
    return {"dbfs": float(dbfs), "dbu": dbu, "dbv": dbu - DBV_DBU, "vrms": DBU_V * 10.0 ** (dbu / 20.0),
            "vu": dbu - 4.0, "dbr": float(dbfs) - ref["dbr"]}.get(unit, float(dbfs))


def unit_to_dbfs(v, ref, unit=None):
    """Inverse de dbfs_to_unit."""
    if v is None:
        return None
    ref = audio_ref_norm(ref)
    unit = unit or ref["unit"]
    a_fs, a_u = audio_align(ref)
    v = float(v)
    if unit == "dbfs":
        return v
    if unit == "dbr":
        return v + ref["dbr"]
    dbu = {"dbu": v, "dbv": v + DBV_DBU, "vu": v + 4.0,
           "vrms": 20.0 * math.log10(max(v, 1e-9) / DBU_V)}.get(unit, v)
    return dbu - a_u + a_fs


def fmt_audio(dbfs, ref, unit=None, nd=1):
    """« −18,0 dBFS », « +4,0 dBu », « 1,228 V »… ("—" si inconnu)."""
    if dbfs is None or not math.isfinite(dbfs):
        return "—"
    unit = unit or audio_ref_norm(ref)["unit"]
    v = dbfs_to_unit(dbfs, ref, unit)
    if unit == "vrms":
        return (f"{v * 1000:.0f} mV" if v < 0.1 else f"{v:.3f} V").replace(".", ",")
    sfx = dict(AUDIO_UNITS).get(unit, "dBFS")
    return f"{v:+.{nd}f} {sfx}".replace(".", ",")


RX_IF_VIEWS = (("spec", "Spectre du canal"), ("const", "Constellation I/Q"), ("phase", "Phase dans le temps"),
               ("finst", "Fréquence instantanée (FM)"))
RX_AF_VIEWS = (("spec", "Spectre du son"), ("scope", "Oscilloscope"), ("gonio", "Goniomètre (phase G/D)"))


def bb_views(bb, fs):
    """8.1 : vues « phase » du canal en bande de base (complexe, fs Hz) -> dict : const (I, Q normalisés, ≤ 800
    points), phase (ms, degrés : phase déroulée moins sa pente = l'écart de fréquence retiré), finst (ms, kHz :
    fréquence instantanée = ce que le démodulateur FM entend)."""
    bb = np.asarray(bb, dtype=np.complex64)
    if len(bb) < 8 or fs <= 0:
        return None
    a = float(np.sqrt(np.mean(np.abs(bb) ** 2))) or 1.0
    k = max(1, len(bb) // 800)
    z = bb[::k] / a
    t = np.arange(len(bb)) / float(fs) * 1000.0
    ph = np.unwrap(np.angle(bb).astype(np.float64))
    if len(ph) > 2:
        ph = ph - np.polyval(np.polyfit(t, ph, 1), t)
    ph = (ph + math.pi) % (2 * math.pi) - math.pi    # repliée entre −180° et +180° (lisible même pour un FM large)
    fi = np.diff(np.unwrap(np.angle(bb).astype(np.float64))) * float(fs) / (2 * math.pi) / 1000.0
    k2 = max(1, len(t) // 1500)
    return dict(I=z.real.astype(np.float32), Q=z.imag.astype(np.float32), t=t.astype(np.float32),
                tp=t[::k2].astype(np.float32), phase=np.degrees(ph[::k2]).astype(np.float32), tf=t[1:].astype(np.float32), finst=fi.astype(np.float32))


def gonio_points(L, R):
    """8.1 : goniomètre (vectorscope) d'un son stéréo : x = (G − D)/√2, y = (G + D)/√2 (mono = trait vertical, hors
    phase = trait horizontal), et corrélation G/D (+1 = mono, 0 = large, −1 = inversé)."""
    L = np.asarray(L, dtype=np.float32)
    R = np.asarray(R, dtype=np.float32)
    n = min(len(L), len(R))
    if n < 8:
        return None
    L, R = L[:n], R[:n]
    den = float(np.sqrt(np.sum(L * L) * np.sum(R * R)))
    corr = float(np.sum(L * R) / den) if den > 0 else 0.0
    k = max(1, n // 1200)
    return dict(x=((L - R) / math.sqrt(2.0))[::k], y=((L + R) / math.sqrt(2.0))[::k], corr=corr)


METER_STYLES = (("analog", "🕐 Aiguille (vu-mètre analogique)"), ("bar", "▬ Barre (vu-mètre linéaire)"))


def meter_ticks(lo, hi, px, label_px=34, minor_px=4):
    """8.1 : graduations d'un vu-mètre de lo à hi (dB) sur px pixels : pas des petits traits (1, 2, 5 ou 10 dB, au moins
    minor_px pixels entre deux), pas des moyens (5 / 10 / 20 dB) et valeurs écrites (assez de place pour le texte).
    -> (petits, moyens, écrits) : listes de dB, du plus bas au plus haut, sans doublon entre elles."""
    span = float(hi - lo)
    if span <= 0 or px <= 0:
        return [], [], []
    ppd = px / span
    minor = next((s for s in (1, 2, 5, 10, 20) if s * ppd >= minor_px), 20)
    mid = next((s for s in (5, 10, 20, 50) if s > minor and s * ppd >= 2 * minor_px), 50)
    lab = next((s for s in (5, 10, 20, 40, 50, 100) if s >= mid and s % mid == 0 and s * ppd >= label_px), 100)
    grid = lambda st: [v for v in range(int(math.ceil(lo / st)) * st, int(math.floor(hi / st)) * st + 1, st)]  # noqa: E731
    labs = grid(lab)
    mids = [v for v in grid(mid) if v not in labs]
    mins = [v for v in grid(minor) if v not in labs and v not in mids]
    return mins, mids, labs


def audio_meter(x, rate=48000):
    """Vu-mètre d'un morceau de son (float −1…1, mono ou entrelacé) : niveau RMS (dBFS, sinus plein = 0 : RMS × √2),
    crête échantillon, True Peak (sur-échantillonné ×4, dBTP), coupé (≥ 0 dBFS). -> dict ; silence = −inf."""
    x = np.asarray(x, dtype=np.float64).ravel()
    if not len(x):
        return dict(rms=-math.inf, peak=-math.inf, tp=-math.inf, clip=False)
    rms = float(np.sqrt(np.mean(x * x)))
    pk = float(np.max(np.abs(x)))
    tp = pk
    if len(x) >= 16:
        n = len(x)
        X = np.fft.rfft(x)
        y = np.fft.irfft(X, 4 * n) * 4.0
        tp = max(pk, float(np.max(np.abs(y))))
    db = lambda v: 20.0 * math.log10(v) if v > 1e-9 else -math.inf  # noqa: E731
    return dict(rms=db(rms * math.sqrt(2.0)), peak=db(pk), tp=db(tp), clip=pk >= 0.999)


def gain_to_target(level_dbfs, target_dbfs, peak_dbfs=None, headroom=0.3):
    """Gain (dB) pour amener un son mesuré au niveau visé, sans dépasser 0 dBFS en crête (−0,3 dB de marge).
    -> (gain dB, limité par la crête ?)."""
    if level_dbfs is None or not math.isfinite(level_dbfs):
        return 0.0, False
    g = float(target_dbfs) - float(level_dbfs)
    if peak_dbfs is not None and math.isfinite(peak_dbfs) and peak_dbfs + g > -headroom:
        return -headroom - float(peak_dbfs), True
    return g, False


def fm_deviation(level_dbfs, dev_full_khz):
    """Déviation FM crête (kHz) d'un son au niveau donné quand 0 dBFS (crête d'un sinus) = dev_full_khz."""
    if level_dbfs is None or not math.isfinite(level_dbfs):
        return 0.0
    return float(dev_full_khz) * 10.0 ** (float(level_dbfs) / 20.0)


def deviation_db(dev_khz, nominal_khz):
    """Déviation mesurée par rapport à la nominale de l'appareil, en dB (0 = pile la nominale, + = trop chaud)."""
    if not dev_khz or not nominal_khz or dev_khz <= 0 or nominal_khz <= 0:
        return None
    return 20.0 * math.log10(float(dev_khz) / float(nominal_khz))


def rf_linear_text(dbm):
    """Niveau RF en valeurs « directes » sur 50 Ω : tension (µV / mV) et puissance (pW / nW / µW / mW)."""
    if dbm is None or not math.isfinite(dbm):
        return "—"
    uv = 10.0 ** ((float(dbm) + 107.0) / 20.0)
    w = 10.0 ** (float(dbm) / 10.0) / 1000.0
    v_txt = f"{uv:.2f} µV" if uv < 1000 else f"{uv / 1000:.2f} mV"
    for f_, u_ in ((1e-3, "mW"), (1e-6, "µW"), (1e-9, "nW"), (1e-12, "pW"), (1e-15, "fW")):
        if w >= f_:
            p_txt = f"{w / f_:.2f} {u_}"
            break
    else:
        p_txt = f"{w * 1e18:.2f} aW"
    return f"{v_txt} · {p_txt}".replace(".", ",")


# Tableau de référence (fiche ❓ « Échelles et niveaux », manuel) : (domaine, unité, 0 dB =, où ça sert, comment
# l'utiliser ici, essentiel ?). Domaines : rf (50 Ω), audio (électrique / numérique), salle, hf (liaisons sans fil).
SCALES = (
    ("rf", "dBm", "1 mW sur 50 Ω", "Spectre, seuils, niveaux mesurés (tinySA, SDR)",
     "L'unité de base de l'appli. −100 dBm = bruit de fond typique, −30 dBm = signal très fort.", True),
    ("rf", "dBµV", "1 µV sur 50 Ω (= dBm + 107)", "Fiches de récepteurs, Wisycom Manager, normes",
     "« Sensibilité 10 dBµV » = −97 dBm. ⚙ › Unité des niveaux.", True),
    ("rf", "dBW", "1 W (= dBm − 30)", "Puissance d'émetteurs, réglementation",
     "Un émetteur de 50 mW = 17 dBm = −13 dBW.", False),
    ("rf", "dBµW", "1 µW (= dBm + 30)", "Fiches techniques, très petits niveaux",
     "−70 dBm = −40 dBµW.", False),
    ("rf", "µV / pW", "valeurs directes sur 50 Ω", "Lecture « physique » d'un niveau",
     "Affichées au survol du spectre à côté du dBm.", False),
    ("rf", "%", "échelle WSM : 0 % = −120 dBm, 100 % = 0 dBm", "Sennheiser WSM",
     "Pour comparer avec un scan WSM.", False),
    ("audio", "dBFS", "pleine échelle numérique (sinus crête = 0)", "Son numérique : générateur, écoute SDR, WAV",
     "Le niveau des vu-mètres de l'appli. Jamais au-dessus de 0 : ça coupe.", True),
    ("audio", "dBu", "0,775 V RMS", "Niveau analogique pro (consoles, sorties de récepteurs)",
     "+4 dBu = niveau ligne pro. Avec l'alignement EBU, −18 dBFS = 0 dBu.", True),
    ("audio", "dBV", "1 V RMS (= dBu − 2,21)", "Matériel grand public, certaines fiches",
     "−10 dBV = niveau ligne grand public (0,316 V).", True),
    ("audio", "V RMS", "tension efficace", "Multimètre, fiches d'entrées / sorties",
     "+4 dBu = 1,228 V ; 0 dBu = 0,775 V ; 0 dBV = 1 V.", True),
    ("audio", "dB VU", "+4 dBu (1,228 V)", "Vu-mètres analogiques à aiguille",
     "0 VU = +4 dBu. Le VU est lent (300 ms) : il montre la moyenne, pas les crêtes.", False),
    ("audio", "dBr", "une référence que TU choisis", "Comparer à un niveau de base (« ce pack = 0 »)",
     "Règle la référence dBr dans l'échelle des vu-mètres.", True),
    ("audio", "dBTP", "pleine échelle, crêtes entre échantillons comprises", "Diffusion, mastering",
     "Une crête à 0 dBFS peut dépasser après conversion : on vise ≤ −1 dBTP.", True),
    ("audio", "Alignement", "EBU R68 : −18 dBFS = 0 dBu · SMPTE RP155 : −20 dBFS = +4 dBu",
     "Faire correspondre numérique et analogique", "Le ton de référence 1 kHz à −18 dBFS (EBU) ou −20 dBFS (SMPTE).", True),
    ("audio", "LUFS / LU", "sonie perçue (EBU R128)", "Diffusion, streaming",
     "Cibles : −23 LUFS (EBU R128), −24 LKFS (USA), ~−14 LUFS en streaming. LU = écart à la cible.", False),
    ("audio", "PPM / K-System", "crête-mètres de consoles ; K-20 / K-14 / K-12 = 0 à −20 / −14 / −12 dBFS",
     "Habitudes de studio et de diffusion", "Pour lire une console ; l'appli reste en dBFS.", False),
    ("hf", "Déviation FM", "déviation crête (kHz) ; « 0 dB » = la nominale de l'appareil",
     "Calibrer une liaison émetteur / récepteur", "Le générateur affiche la déviation d'un niveau ; l'écoute SDR mesure "
     "celle d'un pack et dit de combien de dB il est au-dessus / au-dessous de la nominale.", True),
    ("hf", "Sensibilité micro", "mV/Pa ou dBV/Pa (1 Pa = 94 dB SPL)", "Régler le gain d'entrée d'un pack",
     "Un micro de 10 mV/Pa sort −40 dBV à 94 dB SPL.", True),
    ("hf", "S/B et THD+N", "rapport signal / bruit (dB), distorsion + bruit (%)", "Qualité de la sortie d'un récepteur",
     "Avec un sinus de test, l'écoute SDR montre le souffle (niveau sans modulation) ; la distorsion n'est pas encore "
     "mesurée par l'appli.", False),
    ("salle", "dB SPL", "20 µPa (seuil d'audition)", "Niveau sonore dans la salle",
     "94 dB SPL = 1 Pa. Pas mesuré par l'appli (il faut un sonomètre).", False),
    ("salle", "dB(A) / dB(C) / LAeq", "pondérations de l'oreille / des graves ; moyenne sur 10–15 min",
     "Réglementation des concerts (102 dB(A) en France)", "Pour la fiche : pas mesuré par l'appli.", False),
    ("audio", "dBm (audio)", "1 mW sur 600 Ω (≈ dBu)", "Vieille référence téléphonique",
     "⚠ Ne pas confondre avec le dBm RF (50 Ω) de l'appli.", False),
)


def scales_help_html(tr=lambda s: s):
    """Fiche « Échelles et niveaux » : un tableau par domaine, l'essentiel d'abord, le reste « en option »."""
    e = lambda t: (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))  # noqa: E731
    doms = (("rf", tr("RF (antenne, 50 Ω)")), ("audio", tr("Audio (son électrique et numérique)")),
            ("hf", tr("Liaisons sans fil (calibration)")), ("salle", tr("Son dans la salle")))
    out = [f"<p>{e(tr('Deux mondes à ne pas mélanger : la RF (ce que reçoit l’antenne, en dBm sur 50 Ω) et l’audio (le son, en dBFS / dBu / dBV). Le tableau dit où chaque unité sert et comment l’utiliser ici. En gras : l’essentiel ; « option » : utile seulement dans certains cas.'))}</p>"]
    for k, title in doms:
        rows = [x for x in SCALES if x[0] == k]
        rows = [x for x in rows if x[5]] + [x for x in rows if not x[5]]
        out.append(f"<h3>{e(title)}</h3><table border='1' cellspacing='0' cellpadding='4'>"
                   f"<tr><th>{e(tr('Unité'))}</th><th>{e(tr('0 dB ='))}</th><th>{e(tr('Où ça sert'))}</th>"
                   f"<th>{e(tr('Comment l’utiliser ici'))}</th></tr>")
        for _d, u, ref, where, how, ess in rows:
            uu = f"<b>{e(u)}</b>" if ess else f"{e(u)} <i>({e(tr('option'))})</i>"
            out.append(f"<tr><td>{uu}</td><td>{e(tr(ref))}</td><td>{e(tr(where))}</td><td>{e(tr(how))}</td></tr>")
        out.append("</table>")
    out.append(f"<h3>{e(tr('Repères audio'))}</h3><table border='1' cellspacing='0' cellpadding='4'>"
               f"<tr><th>{e(tr('Situation'))}</th><th>dBu</th><th>dBV</th><th>V RMS</th></tr>")
    for sit, dbu in ((tr("Référence dBu"), 0.0), (tr("Référence dBV"), DBV_DBU), (tr("Niveau pro nominal (0 VU)"), 4.0),
                     (tr("Niveau grand public"), -10.0 + DBV_DBU), (tr("Niveau micro typique"), -50.0)):
        out.append(f"<tr><td>{e(sit)}</td><td>{dbu:+.2f}</td><td>{dbu - DBV_DBU:+.2f}</td>"
                   f"<td>{DBU_V * 10 ** (dbu / 20):.3f}</td></tr>".replace(".", ","))
    out.append("</table>")
    return "".join(out)



# ----- 8.2 : 🧪 Labo SDR (démo) — la chaîne d'un micro HF, pas à pas, et des pannes simulées -----
LAB_RATE = 480000                 # débit IQ du labo (2 × le 1er étage de l'écoute : calcul léger)
LAB_MODES = (("wfm", "FM large (micro HF)"), ("nfm", "FM étroite (talkie)"))
LAB_FAULTS = (("none", "Aucune"), ("drop", "Blocs perdus (trous dans l'IQ)"), ("sat", "Saturation (entrée trop forte)"),
              ("jam", "Brouilleur juste à côté"), ("pilot", "Pilote qui disparaît"), ("noise", "Signal faible (bruit)"),
              ("drift", "Émetteur qui dérive"))
LAB_FAULT_HELP = {
    "none": ("Chaîne propre.", "Rien à signaler : niveau de sortie ≈ niveau d'entrée si les compandeurs sont les mêmes."),
    "drop": ("Le SDR perd des paquets d'échantillons (USB trop chargé, PC qui ne suit pas).",
             "Clics / trous dans le son ; en direct, l'appli compte les « échantillons perdus » du flux."),
    "sat": ("L'entrée du SDR est trop forte : le convertisseur écrête.",
            "Spectre qui s'élargit (raies parasites), constellation carrée ; en direct : indicateur « saturation »."),
    "jam": ("Un autre émetteur à 70 kHz entre dans le canal.",
            "Sifflements / craquements, fréquence instantanée qui saute ; le spectre montre la 2ᵉ porteuse."),
    "pilot": ("Le pilote (tonalité ultrasonore) s'arrête à mi-chemin.",
              "Le pilote n'est plus vu ; sur une fréquence suivie, l'appli lève l'alarme PILOTE."),
    "noise": ("Le signal arrive faible (8 dB au-dessus du bruit).",
              "Souffle, crépitements ; le compandeur du récepteur « pompe » le bruit."),
    "drift": ("L'émetteur dérive de 0 à 15 kHz pendant l'essai.",
              "Fréquence instantanée qui monte ; la santé du micro affiche la dérive."),
}
LAB_SECONDS = 1.6


def _lab_env(x, rate=48000, win=0.01):
    """Enveloppe efficace (dBFS d'un sinus : RMS × √2) par fenêtres de `win` s -> (t s, dB)."""
    x = np.asarray(x, dtype=np.float64)
    n = max(1, int(rate * win))
    m = len(x) // n
    if m == 0:
        return np.zeros(0), np.zeros(0)
    r = np.sqrt(np.mean(x[:m * n].reshape(m, n) ** 2, axis=1)) * math.sqrt(2.0)
    return (np.arange(m) + 0.5) * win, 20.0 * np.log10(r + 1e-9)


def _lab_db(x):
    x = np.asarray(x, dtype=np.float64)
    return 20.0 * math.log10(math.sqrt(float(np.mean(x * x))) * math.sqrt(2.0) + 1e-9) if len(x) else -math.inf


def lab_align(src, out, rate=48000, lo_ms=-20.0, hi_ms=80.0):
    """Retard de `out` sur `src` (ms) par intercorrélation (FFT), cherché entre lo_ms et hi_ms. -> (retard ms, corr)."""
    a = np.asarray(src, dtype=np.float64)
    b = np.asarray(out, dtype=np.float64)
    n = min(len(a), len(b))
    if n < 64:
        return 0.0, 0.0
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    N = 1 << int(math.ceil(math.log2(2 * n)))
    c = np.fft.irfft(np.conj(np.fft.rfft(a, N)) * np.fft.rfft(b, N), N)
    lags = np.arange(N)
    lags[lags >= N // 2] -= N
    lo, hi = int(lo_ms * rate / 1000.0), int(hi_ms * rate / 1000.0)
    m = (lags >= lo) & (lags <= hi)
    i = int(np.argmax(np.abs(c[m])))
    den = float(np.sqrt(np.sum(a * a) * np.sum(b * b))) or 1.0
    return float(lags[m][i]) * 1000.0 / rate, float(c[m][i] / den)


def _lab_comp(audio, k, n, comp):
    t = np.arange(n) / 48000.0
    src = demo_audio(audio, t, k)
    cp = COMPANDERS.get(comp or "")
    if cp is None or cp["ratio"] <= 1.0:
        return src, src
    return src, compress2(src, {}, ratio=cp["ratio"], attack=cp["attack"], release=cp["release"], detector=cp["det"])


def lab_chain(audio="voice", k=0, mode="wfm", dev=None, tx_comp="", rx_comp="", snr=40.0, seconds=LAB_SECONDS,
              fault="none", rate=LAB_RATE, f_off=60000.0, seed=3):
    """Toute la chaîne d'un micro HF, calculée d'un coup (pur numpy) : son de départ -> compresseur de l'émetteur ->
    modulation FM (IQ, + bruit, + panne) -> démodulation du récepteur -> expanseur -> son de sortie. Mesures : niveaux,
    écart, erreur après alignement, retard, « pompage » (écart d'enveloppe), pilote, santé. -> dict."""
    seconds = max(0.4, float(seconds))
    md = LISTEN_MODES.get(mode) or LISTEN_MODES["wfm"]
    dev = float(dev or (30000.0 if mode == "wfm" else 2500.0))
    n_a = int(seconds * 48000)
    src, cmp_ = _lab_comp(audio, k, n_a, tx_comp)
    if fault == "noise":
        snr = min(float(snr), 8.0)
    cut = md["cut"]
    amp = 0.3
    noise = math.sqrt(amp * amp / 10.0 ** (float(snr) / 10.0) * rate / (2.0 * cut))   # C/N dans le canal (± cut)
    sig = dict(key="lab", kind="fm" if mode == "wfm" else "nfm", f=100.0 + f_off / 1e6, lvl=0.0, dev=dev,
               audio=audio, k=k, comp=tx_comp or "", pilot=DEMO_PILOT if mode == "wfm" else 0.0)
    if fault == "pilot":
        sig["pilot_on"] = (10.0 * seconds, seconds / 2.0, 0.0)
    sigs = [sig]
    if fault == "jam":
        sigs.append(dict(key="jam", kind="nfm", f=100.0 + (f_off + 70000.0) / 1e6, lvl=-4.0, dev=3000.0,
                         audio="beep", k=3))
    gen = SigGen(rate, 100e6, sigs, noise=noise, seed=seed)
    n_iq = int(seconds * rate)
    iq = gen.block(n_iq)
    notes = []
    if fault == "drift":
        df = np.linspace(0.0, 15000.0, n_iq)
        iq = (iq * np.exp(2j * np.pi * np.cumsum(df) / rate)).astype(np.complex64)
    elif fault == "sat":
        g = 6.0
        iq = (np.clip(iq.real * g, -1, 1) + 1j * np.clip(iq.imag * g, -1, 1)).astype(np.complex64)
    ovf = float(np.mean(np.abs(iq.real) > 0.98))
    if fault == "drop":
        blk = int(0.05 * rate)
        keep = np.ones(n_iq, dtype=bool)
        for c in (0.55, 0.62, 0.8):
            i0 = int(c * n_iq)
            keep[i0:i0 + blk // 2] = False
        lost = 1.0 - keep.mean()
        iq = iq[keep]
        notes.append(f"{lost * 100:.1f} %")
    dem = ChannelDemod(rate, f_off, mode, 0.0, None, rx_comp or None, dev)
    outs, step = [], int(0.05 * rate)
    pil_seen = []
    for i in range(0, len(iq), step):
        a, _lv = dem.process(iq[i:i + step])
        if len(a):
            outs.append(np.asarray(a[:, 0] if np.ndim(a) == 2 else a, dtype=np.float32))
        pil_seen.append(dem.pilot is not None)
    out = np.concatenate(outs) if outs else np.zeros(0, dtype=np.float32)
    lat, corr = lab_align(src, out)
    sh = int(round(lat * 48.0))
    o = out[sh:] if sh >= 0 else np.concatenate([np.zeros(-sh, dtype=np.float32), out])
    n = min(len(src), len(o))
    s0 = int(0.3 * 48000)                                  # 0,3 s pour que les compandeurs se posent
    S, O = src[s0:n].astype(np.float64), o[s0:n].astype(np.float64)
    g = float(np.dot(S, O) / (np.dot(S, S) or 1.0))
    err = 10.0 * math.log10(float(np.sum((O - g * S) ** 2)) / (float(np.sum((g * S) ** 2)) or 1e-12) + 1e-12) \
        if len(S) else 0.0
    te, es = _lab_env(src[:n])
    _, ec = _lab_env(cmp_[:n])
    _, eo = _lab_env(o[:n])
    m = (es > -45.0) & (te > 0.3)
    dif = eo[m] - es[m]
    pump = float(np.std(dif)) if m.sum() > 4 else 0.0
    avg, mx = rt_frames(iq, 4096)
    Fk = (np.arange(4096) - 2048) * (rate / 4096) / 1000.0
    bb = getattr(dem, "last_bb", None)
    views = bb_views(bb, dem.fs1) if bb is not None else None
    ki = int(0.002 * rate)
    Fc = Fk - f_off / 1000.0                                # kHz autour de la fréquence du canal
    other = None
    if avg is not None:
        flo = float(np.percentile(avg, 20))
        side_ = (np.abs(Fc) > dev / 1000.0 + 20.0) & (np.abs(Fc) <= cut / 1000.0)
        if side_.any() and float(np.max(avg[side_])) > flo + 25.0:
            other = float(Fc[side_][int(np.argmax(avg[side_]))])
    return dict(other=other,
        rate=rate, t=np.arange(n) / 48000.0, src=src[:n], comp=cmp_[:n], out=o[:n], te=te, env_src=es, env_comp=ec,
        env_out=eo, iq_t=np.arange(ki) / rate * 1000.0, I=iq.real[:ki].copy(), Q=iq.imag[:ki].copy(),
        F=Fc, L=avg, Lmax=mx, views=views, fault=fault, mode=mode, dev=dev, tx_comp=tx_comp or "",
        rx_comp=rx_comp or "", ovf=ovf, lost=notes[0] if notes else None,
        pilot_start=bool(any(pil_seen[: max(1, len(pil_seen) // 2)])), pilot_end=bool(pil_seen and pil_seen[-1]),
        health=dem.health, level=dem.level,
        m=dict(src=_lab_db(S), comp=_lab_db(cmp_[s0:n]), out=_lab_db(O), diff=_lab_db(O) - _lab_db(S),
               pk_src=20 * math.log10(float(np.max(np.abs(S))) + 1e-9) if len(S) else -math.inf,
               pk_out=20 * math.log10(float(np.max(np.abs(O))) + 1e-9) if len(O) else -math.inf,
               err=err, gain=20 * math.log10(abs(g) + 1e-9), lat=lat, corr=corr, pump=pump))


def lab_findings(r, tr=None):
    """Ce que le labo voit dans un résultat de lab_chain -> [(texte, ton ok|warn|bad)]."""
    tr = tr or (lambda x: x)
    m = r["m"]
    out = []
    d = m["diff"]
    if abs(d) <= 1.5:
        out.append((tr("Niveau : la sortie retrouve l'entrée ({} dB)").format(f"{d:+.1f}"), "ok"))
    else:
        out.append((tr("Niveau : la sortie s'écarte de l'entrée ({} dB)").format(f"{d:+.1f}"), "warn" if abs(d) < 6 else "bad"))
    if r["tx_comp"] != r["rx_comp"] and (COMPANDERS.get(r["tx_comp"] or "none", {}).get("ratio", 1) > 1
                                         or COMPANDERS.get(r["rx_comp"] or "none", {}).get("ratio", 1) > 1):
        out.append((tr("Compandeurs différents à l'émission et à la réception : la dynamique est faussée"), "bad"))
    if m["pump"] > 3.0:
        out.append((tr("Pompage : le niveau de sortie suit mal l'entrée (écart ± {} dB)").format(f"{m['pump']:.1f}"),
                    "warn" if m["pump"] < 6 else "bad"))
    out.append((tr("Fidélité : erreur résiduelle {} dB (plus c'est bas, mieux c'est)").format(f"{m['err']:.0f}"),
                "ok" if m["err"] < -20 else "warn" if m["err"] < -8 else "bad"))
    out.append((tr("Retard de la chaîne : {} ms").format(f"{m['lat']:.1f}"), "ok"))
    if r.get("other") is not None:
        out.append((tr("Autre signal dans le canal, à {} kHz de la porteuse").format(f"{r['other']:+.0f}"), "bad"))
    if r["ovf"] > 0.001:
        out.append((tr("Saturation : {} % des échantillons à pleine échelle").format(f"{100 * r['ovf']:.1f}"), "bad"))
    if r.get("lost"):
        out.append((tr("Échantillons perdus : {}").format(r["lost"]), "bad"))
    if r["mode"] == "wfm":
        if r["pilot_start"] and not r["pilot_end"]:
            out.append((tr("Pilote vu au début, perdu à la fin : alarme PILOTE en direct"), "bad"))
        elif r["pilot_start"]:
            out.append((tr("Pilote vu tout le long"), "ok"))
    h = r.get("health")
    if h and abs(h.get("drift", 0.0)) > 3.0:
        out.append((tr("Dérive mesurée : {} kHz").format(f"{h['drift']:+.1f}"), "warn" if abs(h["drift"]) < 8 else "bad"))
    return out


def comp_curve(comp, side="rx", lo=-60.0, hi=0.0, n=61):
    """Courbe statique d'un compandeur (niveau stable) : entrée dBFS -> sortie dBFS, côté émetteur (« tx » :
    compression) ou récepteur (« rx » : expansion, genou compris), ou « chain » (tx puis rx). Même formule que
    compress2 / expand2 (réf. 0,25 efficace), sans les butées de temps. -> (x, y) ; None si pas de compandeur."""
    cp = COMPANDERS.get(comp or "")
    if cp is None or cp["ratio"] <= 1.0:
        return None
    x = np.linspace(lo, hi, n)
    ref = 20.0 * math.log10(0.25 * math.sqrt(2.0))      # référence en dBFS d'un sinus

    def tx(v):
        g = np.clip((v - ref) * (1.0 / cp["ratio"] - 1.0), 20 * math.log10(0.03), 20 * math.log10(30.0))
        return v + g

    def rx(v):
        r = np.full_like(v, cp["ratio"])
        if cp.get("knee") is not None and cp.get("low"):
            r = np.where(v - ref < cp["knee"], cp["ratio"] + cp["low"], r)
        g = np.clip((v - ref) * (r - 1.0), 20 * math.log10(0.001), 20 * math.log10(4.0))
        return v + g
    y = tx(x) if side == "tx" else rx(x) if side == "rx" else rx(tx(x))
    return x, y


LAB_EXPECT = dict(wfm="fm_ana", nfm="nfm", cw="cw", am=None, num="num", tnt="tnt")   # am : pas de classe AM


def lab_modulations(audio="melody", k=0):
    """Comparateur : même son, modulations différentes -> [dict(key, name, F MHz, L dB, cls (classify_signal), span)].
    Pour voir à quoi ressemble chaque famille sur un spectre et ce que l'appli en devine."""
    rows = []
    specs = (("wfm", "Micro HF (FM ±30 kHz)", dict(kind="fm", dev=30000.0, pilot=DEMO_PILOT), 2400000, 0.5),
             ("nfm", "Talkie (FM ±5 kHz)", dict(kind="nfm", dev=5000.0), 2400000, 0.06),
             ("cw", "Porteuse pure", dict(kind="cw"), 2400000, 0.06),
             ("am", "AM (aviation)", None, 2400000, 0.06),
             ("num", "Micro numérique (bloc 200 kHz)", dict(kind="noise", bw=0.2), 2400000, 0.5),
             ("tnt", "TNT (bloc 7,6 MHz)", dict(kind="noise", bw=7.6), 12000000, 6.0))
    for key, name, sg, rate, span in specs:
        n = int(rate * 0.12)
        if sg is None:
            t = np.arange(n) / rate
            ta = np.arange(int(0.12 * 48000) + 2) / 48000.0
            a = np.interp(t, ta, demo_audio(audio, ta, k))       # interpolé (répéter créait des images à ±48 kHz)
            noise = 0.01 / math.sqrt(2.0) * (np.random.default_rng(1).standard_normal(n)
                                             + 1j * np.random.default_rng(2).standard_normal(n))
            iq = (0.3 * (1.0 + 0.6 * a) * np.exp(2j * np.pi * 0.0 * t) + noise).astype(np.complex64)
        else:
            s = dict(sg, key=key, f=100.0, lvl=0.0, audio=audio, k=k)
            iq = SigGen(rate, 100e6, [s], noise=0.01, seed=5).block(n)
        nfft = 16384 if rate > 3e6 else 8192
        avg, _mx = rt_frames(iq, nfft)
        F = rt_freqs(100e6, rate, nfft)
        msk = np.abs(F - 100.0) <= span
        cls = classify_signal(F[msk], avg[msk], 100.0, (DEMO_PILOT, 30.0) if key == "wfm" else None, span=span)
        rows.append(dict(key=key, name=name, F=F[msk], L=avg[msk], cls=cls, span=span, expect=LAB_EXPECT.get(key),
                         ok=(cls["kind"] == LAB_EXPECT.get(key)) if LAB_EXPECT.get(key) else None))
    return rows


# Pannes à injecter dans le SDR démo en DIRECT (DemoIQ) : ce que l'appli doit détecter
DEMO_FAULTS = (("drop", "Blocs perdus (USB qui sature)"), ("stall", "Flux figé 3 s"), ("sat", "Saturation"),
               ("unplug", "SDR débranché"), ("jam", "Brouilleur sur un micro"), ("pilot", "Pilotes coupés"),
               ("noise", "Bruit fort (antenne loin)"))
DEMO_FAULT_HELP = {
    "drop": "Le SDR démo perd 20 % de ses échantillons : la ligne « Flux » du poste passe en orange (échantillons perdus).",
    "stall": "Le flux s'arrête 3 s : « Flux » signale une coupure, le moniteur grise ses mesures.",
    "sat": "L'entrée écrête : « Flux » signale la saturation, le spectre se remplit de raies.",
    "unplug": "Le SDR ne répond plus : le poste s'arrête (« débranché ou occupé ? ») puis repart quand la panne cesse.",
    "jam": "Un brouilleur se pose sur le 1er micro : alarme CONFLIT / son qui grésille.",
    "pilot": "Tous les pilotes s'arrêtent : alarme PILOTE sur les micros dont le pilote est appris.",
    "noise": "Le bruit monte de 20 dB : marges qui fondent, micros « faibles ».",
}


def stream_quality(q, ovf=0.0, tr=None):
    """8.2 : qualité du flux IQ d'un SDR (réel ou démo). q = dict(lost %, gaps (coupures > 0,5 s depuis 1 min), short
    (lectures incomplètes), rate_ok). -> (texte, ton ok|warn|bad)."""
    tr = tr or (lambda x: x)
    q = q or {}
    parts, tone = [], "ok"
    lost = q.get("lost")
    if lost is not None and lost >= 0.5:
        parts.append(tr("{} % d'échantillons perdus").format(f"{lost:.1f}"))
        tone = "bad" if lost >= 5 else "warn"
    if q.get("gaps"):
        parts.append(tr("{} coupure(s) du flux").format(q["gaps"]))
        tone = "bad"
    if ovf and ovf > 0.001:
        parts.append(tr("saturation {} %").format(f"{100 * ovf:.1f}"))
        tone = "bad" if ovf > 0.01 else ("warn" if tone == "ok" else tone)
    if not parts:
        return tr("✔ Flux propre (aucune perte, aucune saturation)"), "ok"
    return "⚠ " + " · ".join(parts), tone


class StreamStats:
    """8.2 : compte, sur une minute glissante, ce que le SDR a vraiment livré (échantillons reçus / attendus au débit
    réglé, coupures > `gap_s`) : une perte d'échantillons (USB, PC) ne passe plus inaperçue."""

    def __init__(self, rate, gap_s=0.5, win=10.0):
        self.rate, self.gap_s, self.win = float(rate), float(gap_s), float(win)
        self.t0 = self.tl = None
        self.got = deque()
        self.gaps = deque()

    def feed(self, t, n):
        if self.t0 is None:
            self.t0 = self.tl = t
            self.got.append((t, n))
            return
        if t - self.tl > self.gap_s:
            self.gaps.append(t)
        self.tl = t
        self.got.append((t, n))
        while self.got and t - self.got[0][0] > self.win:
            self.got.popleft()
        while self.gaps and t - self.gaps[0] > 60.0:
            self.gaps.popleft()

    def view(self):
        if len(self.got) < 3:
            return dict(lost=None, gaps=len(self.gaps))
        t0, t1 = self.got[0][0], self.got[-1][0]
        if t1 - t0 < 1.0:
            return dict(lost=None, gaps=len(self.gaps))
        got = sum(n for _t, n in list(self.got)[1:])
        exp = self.rate * (t1 - t0)
        return dict(lost=max(0.0, 100.0 * (1.0 - got / exp)) if exp > 0 else None, gaps=len(self.gaps))


def sdr_compat_rows():
    """8.2 : tableau de compatibilité des SDR connus -> [dict(name, kind, range, bits, rate, span, sweep, iq, tx, dbm,
    tested, src)] (tx = émission prise en charge ; tested = essayé avec le vrai matériel)."""
    rows = []
    for m in SDR_MODELS:
        c = device_caps(m["kind"], m)
        r = max(m.get("rates") or [0])
        rows.append(dict(name=m["name"], kind=m["kind"], range=f"{m['fmin']:g} – {m['fmax']:g} MHz",
                         bits=m.get("bits"), rate=r / 1e6 if r else None, span=c.get("span"), sweep=c["sweep"],
                         iq=c["iq"], tx=m["kind"] == "hackrf", dbm=bool(m.get("cal")), tested=False,
                         src=m.get("src", "")))
    return rows



# ----- 8.2 : RF Compander Lab — un moteur de mesure COMMUN (simulé ou observé), des fiches de modèles, la provenance -----
PROVENANCE = {"sim": "🧪 simulé", "obs": "📡 observé (SDR réel)", "calc": "🧮 calculé (formule)"}
CMP_IMPL = {"exact": "Formule publique (exacte)", "approx": "Approché d'après une documentation publique",
            "generic": "Modèle générique (pas d'une marque)", "auth": "Traitement propriétaire autorisé"}
CMP_MODEL_VER = "2026.11-1"     # version des modèles : change dès qu'un réglage d'un compandeur bouge
_CARD_APPROX = ("Courbe réelle non publiée : modèle 2:1 réglé au jugé d'après la description du fabricant. "
                "Non validé par une mesure sur le vrai matériel.")
COMPANDER_CARDS = {
    "none": dict(maker="—", model="Aucun traitement", tech="Ni compandeur ni désaccentuation", impl="exact",
                 doc="Définition (sortie = entrée)", limits="Sert de référence."),
    "none_d50": dict(maker="—", model="Désaccentuation 50 µs", tech="Filtre du 1er ordre (Europe)", impl="exact",
                     doc="Norme de radiodiffusion FM (constante de temps publique)", limits="Pas de compandeur."),
    "none_d75": dict(maker="—", model="Désaccentuation 75 µs", tech="Filtre du 1er ordre (Amériques)", impl="exact",
                     doc="Norme de radiodiffusion FM (constante de temps publique)", limits="Pas de compandeur."),
    "x2": dict(maker="—", model="Expanseur 2:1 générique", tech="2:1, détecteur efficace", impl="generic",
               doc="Principe général d'un compandeur", limits="Ne correspond à aucune marque."),
    "sa572": dict(maker="NXP / Philips (circuit)", model="SA572 / NE570", tech="2:1, redressement moyen",
                  impl="approx", doc="Fiche technique publique du circuit",
                  limits="Temps de montée / descente dépendent des condensateurs du fabricant du micro."),
    "rms": dict(maker="—", model="Compandeur RMS 2:1 (type dbx)", tech="2:1, détecteur efficace", impl="generic",
                doc="Principe public du détecteur efficace", limits="Pas le circuit dbx (propriétaire)."),
    "wisy_enc": dict(maker="Wisycom", model="ENC", tech="Voix, pré-accentuation réduite", impl="approx",
                     doc="Manuel Wisycom (description des modes)", limits=_CARD_APPROX),
    "wisy_enr": dict(maker="Wisycom", model="ENR", tech="Réduction de bruit, genou, détecteur sans les aigus",
                     impl="approx", doc="Manuel Wisycom (description des modes)", limits=_CARD_APPROX),
    "wisy_ens": dict(maker="Wisycom", model="ENS", tech="Live, aigus relevés", impl="approx",
                     doc="Manuel Wisycom (description des modes)", limits=_CARD_APPROX),
    "wisy_enc12": dict(maker="Wisycom", model="ENC 1.2", tech="Dynamique réduite (1,5:1)", impl="approx",
                       doc="Manuel Wisycom (description des modes)", limits=_CARD_APPROX),
    "wisy_enr12": dict(maker="Wisycom", model="ENR 1.2", tech="Dynamique réduite, genou", impl="approx",
                       doc="Manuel Wisycom (description des modes)", limits=_CARD_APPROX),
    "sen": dict(maker="Sennheiser", model="HiDyn plus (3000 / 5000)", tech="2:1", impl="approx",
                doc="Fiches produit (nom du procédé seulement)", limits=_CARD_APPROX),
    "evo": dict(maker="Sennheiser", model="HDX (evolution G2 / G3 / G4)", tech="2:1, redressement moyen", impl="approx",
                doc="Fiches produit (nom du procédé seulement)", limits=_CARD_APPROX),
    "shure": dict(maker="Shure", model="Compandeur analogique", tech="2:1, redressement moyen", impl="approx",
                  doc="Fiches produit (nom du procédé seulement)", limits=_CARD_APPROX),
    "lex": dict(maker="Lectrosonics", model="Mode SR / LEX", tech="2:1, rapide", impl="approx",
                doc="Fiches produit (nom du procédé seulement)", limits=_CARD_APPROX),
}


def compander_card(key):
    """Fiche normalisée d'un compandeur : fabricant, modèle, technologie, documentation, implémentation, fidélité,
    limites, version, réglages du modèle. Jamais de mélange : un modèle générique, une approximation et un traitement
    propriétaire sont des niveaux d'implémentation différents."""
    cp = COMPANDERS.get(key)
    if cp is None:
        return None
    c = dict(COMPANDER_CARDS.get(key) or dict(maker="—", model=cp["name"], tech="", impl="generic", doc="", limits=""))
    c.update(key=key, name=cp["name"], ver=CMP_MODEL_VER,
             fidelity="Formule exacte" if c["impl"] == "exact" else "Non validé par une mesure sur le vrai matériel",
             params=dict(ratio=cp["ratio"], attack=cp["attack"], release=cp["release"], det=cp["det"],
                         deemph=cp["deemph"], knee=cp["knee"], low=cp["low"], hf=cp["hf"], air=cp["air"], lp=cp["lp"]))
    return c


def _deemph_taps(us, rate=48000):
    a = math.exp(-1.0 / (rate * us * 1e-6))
    return ((1.0 - a) * a ** np.arange(64)).astype(np.float32)


class CompChain:
    """Chaîne audio d'un RÉCEPTEUR pour un modèle (8.2, interface commune) : désaccentuation (celle du modèle, sinon
    `deemph_us`), couleur (aigus / passe-bas), expanseur. Même calcul que ChannelDemod (qui l'utilise) : le labo mesure
    exactement ce que l'écoute fait. En flux : traiter d'un tenant ou par morceaux donne le même son."""

    def __init__(self, key, deemph_us=None, rate=48000):
        self.key, self.rate = key, rate
        cp = COMPANDERS.get(key) or {}
        self.cp = cp
        d = cp.get("deemph")
        us = d if d is not None else deemph_us
        self.de = _deemph_taps(us, rate) if us else None
        self.de_tail = {0: np.zeros(63, dtype=np.float32), 1: np.zeros(63, dtype=np.float32)}
        self.eq = None
        if cp.get("air") or cp.get("lp"):
            h = np.zeros(63, dtype=np.float32)
            h[31] = 1.0
            g = 10.0 ** (cp.get("air", 0.0) / 20.0) - 1.0
            if g:
                h = h * (1.0 + g) - g * lowpass_taps(6000.0, rate, 63)
            if cp.get("lp"):
                h = np.convolve(h, lowpass_taps(cp["lp"], rate, 63)).astype(np.float32)
            self.eq = [FirDecim(h, 1), FirDecim(h, 1)]
        self.st = {"_cps": {"env": 0.05}}
        self._hf = FirDecim(lowpass_taps(cp["hf"], rate, 31), 1) if cp.get("hf") else None

    def deemph(self, a, ch=0):
        if self.de is None or not len(a):
            return a
        t = self.de_tail[ch]
        x = np.concatenate([t, a])
        c = np.convolve(x, self.de)[63:63 + len(a)]
        self.de_tail[ch] = x[-63:]
        return c.astype(np.float32)

    def color_expand(self, a):
        """Couleur puis expanseur (ce que ChannelDemod fait après sa désaccentuation)."""
        a = np.asarray(a, dtype=np.float32)
        if self.eq is not None and len(a):
            if a.ndim == 2:
                l_, r_ = self.eq[0](a[:, 0]), self.eq[1](a[:, 1])
                nn = min(len(l_), len(r_))
                a = np.stack([l_[:nn], r_[:nn]], axis=1).astype(np.float32)
            else:
                a = self.eq[0](a).astype(np.float32)
        cp = self.cp
        if cp and cp["ratio"] > 1.0 and len(a):
            side = None
            if self._hf is not None:
                mono_ = a.mean(axis=1) if a.ndim == 2 else a
                side = self._hf(mono_.astype(np.float32))[:len(mono_)]
                if len(side) < len(mono_):
                    side = np.concatenate([side, np.zeros(len(mono_) - len(side), dtype=np.float32)])
            a = expand2(a, self.st, ratio=cp["ratio"], attack=cp["attack"], release=cp["release"], detector=cp["det"],
                        knee=cp["knee"], low=cp["low"], side=side)
        return a

    def __call__(self, a):
        return self.color_expand(self.deemph(np.asarray(a, dtype=np.float32)))


class CompTx:
    """Chaîne audio d'un ÉMETTEUR pour un modèle : compresseur puis pré-accentuation (l'inverse exact de la
    désaccentuation du récepteur, si le modèle en a une)."""

    def __init__(self, key, deemph_us=None, rate=48000):
        cp = COMPANDERS.get(key) or {}
        self.cp = cp
        d = cp.get("deemph")
        us = d if d is not None else deemph_us
        self.a = math.exp(-1.0 / (rate * us * 1e-6)) if us else None
        self.prev = 0.0
        self.st = {}

    def __call__(self, x):
        x = np.asarray(x, dtype=np.float32)
        cp = self.cp
        if cp and cp["ratio"] > 1.0 and len(x):
            x = compress2(x, self.st, ratio=cp["ratio"], attack=cp["attack"], release=cp["release"], detector=cp["det"])
        if self.a is not None and len(x):
            y = np.concatenate([[self.prev], x.astype(np.float64)])
            self.prev = float(x[-1])
            x = ((y[1:] - self.a * y[:-1]) / (1.0 - self.a)).astype(np.float32)
        return x


def _run_chunks(proc, x, n=1200):
    out = [proc(x[i:i + n]) for i in range(0, len(x), n)]
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def _sine(db, n, f=1000.0, rate=48000, t0=0):
    return (10.0 ** (db / 20.0) * np.sin(2 * np.pi * f * (t0 + np.arange(n)) / rate)).astype(np.float32)


def measure_transfer(make, lo=-60.0, hi=0.0, step=5.0, dwell=0.4, rate=48000):
    """Courbe de transfert MESURÉE (pas la formule) : un escalier de sinus 1 kHz traverse la chaîne `make()` d'un seul
    tenant ; niveau de sortie mesuré sur la fin de chaque marche (une fois l'enveloppe posée). -> (entrée dB, sortie dB)."""
    lv = np.arange(lo, hi + 1e-9, step)
    n = int(dwell * rate)
    x = np.concatenate([_sine(v, n, t0=i * n) for i, v in enumerate(lv)])
    y = _run_chunks(make(), x)
    tail = int(0.15 * rate)
    out = [_lab_db(y[(i + 1) * n - tail:(i + 1) * n]) for i in range(len(lv))]
    return lv, np.array(out)


def measure_transient(make, lo=-30.0, hi=-10.0, rate=48000, seg=1.0):
    """Saut de niveau (lo -> hi -> lo, sinus 1 kHz) : enveloppe de sortie (2 ms), dépassement (dB au-dessus du niveau
    posé juste après la montée), temps de montée et de descente (à 1 dB près du niveau posé). -> dict."""
    n = int(seg * rate)
    x = np.concatenate([_sine(lo, n), _sine(hi, n, t0=n), _sine(lo, n, t0=2 * n)])
    y = _run_chunks(make(), x)
    t, e = _lab_env(y, rate, 0.002)
    tin, ein = _lab_env(x, rate, 0.002)

    def settle(i0, i1):
        steady = float(np.median(e[i1 - int(0.2 / 0.002):i1]))
        seg_ = e[i0:i1]
        far = np.nonzero(np.abs(seg_ - steady) > 1.0)[0]
        ts = (far[-1] + 1) * 0.002 if len(far) else 0.0
        return steady, ts, float(np.max(seg_) - steady), float(np.min(seg_) - steady)
    k = int(seg / 0.002)
    s_up, t_up, over, _ = settle(k, 2 * k)
    s_dn, t_dn, _, under = settle(2 * k, 3 * k)
    return dict(t=t, env=e, env_in=ein, up_ms=1000.0 * t_up, down_ms=1000.0 * t_dn, over_db=over, under_db=under,
                step_in=hi - lo, step_out=s_up - s_dn)


def xfer_spectrum(x, y, rate=48000, nfft=4096):
    """Fonction de transfert de x vers y par spectres croisés moyennés (Welch) : |H| dB et phase (degrés, retard pur
    retiré), sur 50 Hz – 20 kHz. Le même calcul sert au labo (simulé) et au direct (observé). -> dict(f, mag, phase,
    delay_ms, coh)."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = min(len(x), len(y))
    if n < nfft:
        return None
    w = np.hanning(nfft)
    hop = nfft // 2
    Sxx = Syy = 0.0
    Sxy = 0.0
    for i in range(0, n - nfft + 1, hop):
        X = np.fft.rfft(x[i:i + nfft] * w)
        Y = np.fft.rfft(y[i:i + nfft] * w)
        Sxx = Sxx + np.abs(X) ** 2
        Syy = Syy + np.abs(Y) ** 2
        Sxy = Sxy + Y * np.conj(X)
    f = np.fft.rfftfreq(nfft, 1.0 / rate)
    H = Sxy / (Sxx + 1e-20)
    coh = np.abs(Sxy) ** 2 / (Sxx * Syy + 1e-30)
    m = (f >= 50.0) & (f <= 20000.0)
    ph = np.unwrap(np.angle(H[m]))
    good = coh[m] > 0.5
    delay = 0.0
    if good.sum() > 8:
        sl = np.polyfit(2 * np.pi * f[m][good], ph[good], 1)[0]
        delay = -sl
        ph = ph + 2 * np.pi * f[m] * delay
    ph = (ph + math.pi) % (2 * math.pi) - math.pi
    return dict(f=f[m], mag=20.0 * np.log10(np.abs(H[m]) + 1e-12), phase=np.degrees(ph), delay_ms=1000.0 * delay,
                coh=coh[m])


def measure_freq(make, level=-20.0, seconds=3.0, rate=48000):
    """Réponse en fréquence ET en phase d'une chaîne (bruit rose à `level` dBFS, enveloppe stable : le gain du
    compandeur se pose). -> xfer_spectrum (+ 1 s d'attente pour que l'enveloppe se pose)."""
    n = int(seconds * rate)
    x = demo_audio("pink", np.arange(n) / rate)
    x = (x * 10.0 ** ((level - _lab_db(x)) / 20.0)).astype(np.float32)
    y = _run_chunks(make(), x)
    s0 = rate
    return xfer_spectrum(x[s0:], y[s0:], rate)


def comp_compare(keys, tx_key="", audio="voice", deemph_us=50.0, seconds=4.0, k=0):
    """8.2 : comparateur multi-modèles. Pour chaque modèle de récepteur : courbe de transfert mesurée (récepteur seul,
    et chaîne émetteur -> récepteur), saut de niveau, réponse en fréquence et en phase de la chaîne, et passage de la
    même source (niveau, erreur, retard, pompage). Mêmes signaux, même moteur de mesure pour tous. -> dict."""
    n = int(seconds * 48000)
    src = demo_audio(audio, np.arange(n) / 48000.0, k)
    out = dict(meta=dict(tx=tx_key or "", audio=audio, deemph=deemph_us, seconds=seconds, ver=CMP_MODEL_VER,
                         prov="sim"), rows=[])
    for key in keys:
        if key not in COMPANDERS:
            continue
        rx_only = lambda key=key: CompChain(key, deemph_us)                       # noqa: E731
        chain = lambda key=key: (lambda tx, rx: (lambda a: rx(tx(a))))(CompTx(tx_key, deemph_us),
                                                                       CompChain(key, deemph_us))   # noqa: E731
        xi, yo = measure_transfer(rx_only)
        _, yc = measure_transfer(chain)
        tr_ = measure_transient(chain)
        fq = measure_freq(chain)
        y = _run_chunks(chain(), src)
        lat, corr = lab_align(src, y)
        sh = int(round(lat * 48.0))
        o = y[sh:] if sh >= 0 else np.concatenate([np.zeros(-sh, dtype=np.float32), y])
        m_ = min(len(src), len(o))
        s0 = int(0.5 * 48000)
        S, O = src[s0:m_].astype(np.float64), o[s0:m_].astype(np.float64)
        g = float(np.dot(S, O) / (np.dot(S, S) or 1.0))
        err = 10.0 * math.log10(float(np.sum((O - g * S) ** 2)) / (float(np.sum((g * S) ** 2)) or 1e-12) + 1e-12)
        te, es = _lab_env(src[:m_])
        _, eo = _lab_env(o[:m_])
        mm = (es > -45.0) & (te > 0.5)
        pump = float(np.std(eo[mm] - es[mm])) if mm.sum() > 4 else 0.0
        sl = np.polyfit(xi[xi >= -40], yo[xi >= -40], 1)[0] if len(xi) > 3 else 1.0
        out["rows"].append(dict(key=key, card=compander_card(key), xin=xi, rx=yo, chain=yc, slope=float(sl),
                                transient=tr_, freq=fq, out=o[:m_], te=te, env_out=eo,
                                m=dict(diff=_lab_db(O) - _lab_db(S), err=err, lat=lat, corr=corr, pump=pump,
                                       up=tr_["up_ms"], down=tr_["down_ms"], over=tr_["over_db"],
                                       step=tr_["step_out"])))
    out["src"], out["env_src"] = src, _lab_env(src)[1]
    return out


# Signal de test « escalier » (à mettre dans l'entrée audio d'un VRAI émetteur) : 0,6 s de silence (repère), puis
# 9 marches de 1 kHz de −40 à 0 dBFS, 1 s chacune. Reçu au SDR AVANT l'expanseur, il donne la compression de
# l'émetteur : pente = 1 / taux.
STAIR_LEVELS = tuple(range(-40, 1, 5))
STAIR_STEP_S, STAIR_GAP_S = 1.0, 0.6
STAIR_PERIOD = STAIR_GAP_S + STAIR_STEP_S * len(STAIR_LEVELS)


def stair_signal(t):
    t = np.asarray(t, dtype=np.float64)
    c = t % STAIR_PERIOD - STAIR_GAP_S
    i = np.clip(np.floor(c / STAIR_STEP_S).astype(np.int64), 0, len(STAIR_LEVELS) - 1)
    a = 10.0 ** (np.asarray(STAIR_LEVELS, dtype=np.float64)[i] / 20.0)
    return np.where(c >= 0, a * np.sin(2 * np.pi * 1000.0 * t), 0.0).astype(np.float32)


def stair_fit(x, rate=48000):
    """Analyse un escalier reçu (son démodulé AVANT l'expanseur, au moins une période complète) : cherche le silence
    repère, mesure chaque marche (milieu), et ajuste sortie = pente × entrée + décalage. -> dict(ok, levels_in,
    levels_out, slope, ratio (taux de compression = 1 / pente), r2, why)."""
    x = np.asarray(x, dtype=np.float32)
    t, e = _lab_env(x, rate, 0.02)
    if len(e) < int(STAIR_PERIOD / 0.02) + 10:
        return dict(ok=False, why="Pas assez de son : il faut au moins une période complète de l'escalier "
                                  f"({STAIR_PERIOD:.1f} s), mieux deux.")
    top = float(np.percentile(e, 95))
    quiet = e < top - 40.0
    k_gap = int(0.4 / 0.02)
    ends, run = [], 0
    for i, q in enumerate(quiet):               # fin de chaque silence d'au moins 0,4 s = début d'un escalier
        if q:
            run += 1
        else:
            if run >= k_gap:
                ends.append(i)
            run = 0
    for j in ends:
        if j + int(STAIR_STEP_S * len(STAIR_LEVELS) / 0.02) > len(e):
            continue
        lv = []
        for k in range(len(STAIR_LEVELS)):
            a0 = j + int((k * STAIR_STEP_S + 0.3) / 0.02)
            a1 = j + int((k * STAIR_STEP_S + 0.8) / 0.02)
            lv.append(float(np.median(e[a0:a1])))
        xi = np.asarray(STAIR_LEVELS, dtype=float)
        yo = np.asarray(lv)
        if np.any(np.diff(yo) <= 0):
            continue
        p = np.polyfit(xi, yo, 1)
        res = yo - np.polyval(p, xi)
        r2 = 1.0 - float(np.sum(res ** 2)) / (float(np.sum((yo - yo.mean()) ** 2)) or 1e-12)
        sl = float(p[0])
        return dict(ok=True, levels_in=list(xi), levels_out=lv, slope=sl, ratio=1.0 / sl if sl > 0.05 else None,
                    offset=float(p[1]), r2=r2, why="")
    if ends and all(j + int(STAIR_STEP_S * len(STAIR_LEVELS) / 0.02) > len(e) for j in ends):
        return dict(ok=False, why="Escalier pas encore complet : attends encore quelques secondes et recommence.")
    return dict(ok=False, why="Escalier non reconnu : vérifie que le signal de test passe bien (silence repère, "
                              "marches qui montent), et que le son n'est pas coupé par le squelch.")


def comp_report_html(res, tr=None, title="RF Compander Lab — rapport comparatif", observed=None):
    """Rapport comparatif (HTML autonome) : conditions, sources, modèles et versions (fiches), indicateurs, écarts
    observés, limites de validité. observed = résultat de stair_fit d'une mesure réelle (provenance 📡) ou None."""
    tr = tr or (lambda s: s)
    from html import escape as e
    import datetime as _dt
    meta = res.get("meta", {})
    rows = res.get("rows", [])
    css = ("body{font-family:-apple-system,Segoe UI,Arial,Helvetica;max-width:1000px;margin:24px auto;color:#1c1c1e;"
           "padding:0 16px}h1{font-size:22px}h2{font-size:17px;margin-top:28px}table{border-collapse:collapse;"
           "width:100%;font-size:13px}td,th{border:1px solid #d1d1d6;padding:5px 7px;text-align:left}th{background:"
           "#f2f2f7}.prov{display:inline-block;padding:2px 8px;border-radius:10px;background:#e5f1ff;font-size:12px}"
           ".warn{background:#fff4e0;border-left:4px solid #ff9f0a;padding:8px 12px;margin:12px 0}")
    h = [f"<!doctype html><meta charset='utf-8'><title>{e(tr(title))}</title><style>{css}</style>",
         f"<h1>{e(tr(title))}</h1>",
         f"<p>{e(_dt.datetime.now().strftime('%d/%m/%Y %H:%M'))} · <span class='prov'>"
         f"{e(tr(PROVENANCE[meta.get('prov', 'sim')]))}</span> · {e(tr('version des modèles'))} {e(meta.get('ver', ''))}</p>",
         f"<div class='warn'>{e(tr('Les compandeurs des marques ne sont pas publiés : les modèles « approchés » sont des reproductions au jugé, pas les vrais traitements. Une différence entre deux modèles dit comment ces MODÈLES se comportent, pas les vrais appareils.'))}</div>",
         f"<h2>{e(tr('Conditions de comparaison'))}</h2><table>",
         f"<tr><th>{e(tr('Source'))}</th><td>{e(tr(audio_text(meta.get('audio', 'voice'), tr)))}</td></tr>",
         f"<tr><th>{e(tr('Émetteur (compresseur)'))}</th><td>{e(tr(COMPANDERS.get(meta.get('tx') or 'none', {}).get('name', '—')))}</td></tr>",
         f"<tr><th>{e(tr('Désaccentuation par défaut'))}</th><td>{meta.get('deemph', 0):g} µs</td></tr>",
         f"<tr><th>{e(tr('Durée de la source'))}</th><td>{meta.get('seconds', 0):g} s</td></tr>",
         f"<tr><th>{e(tr('Mesures'))}</th><td>{e(tr('escalier de sinus 1 kHz (−60 → 0 dBFS, 0,4 s par marche) ; saut −30 → −10 dBFS ; bruit rose à −20 dBFS (réponse et phase, retard retiré) ; passage de la source'))}</td></tr></table>",
         f"<h2>{e(tr('Modèles comparés'))}</h2><table><tr><th>{e(tr('Modèle'))}</th><th>{e(tr('Fabricant'))}</th>"
         f"<th>{e(tr('Technologie'))}</th><th>{e(tr('Implémentation'))}</th><th>{e(tr('Documentation'))}</th>"
         f"<th>{e(tr('Fidélité'))}</th><th>{e(tr('Limites'))}</th></tr>"]
    for r in rows:
        c = r["card"]
        h.append(f"<tr><td>{e(tr(c['name']))}</td><td>{e(tr(c['maker']))}</td><td>{e(tr(c['tech']))}</td>"
                 f"<td>{e(tr(CMP_IMPL[c['impl']]))}</td><td>{e(tr(c['doc']))}</td><td>{e(tr(c['fidelity']))}</td>"
                 f"<td>{e(tr(c['limits']))}</td></tr>")
    h.append("</table>")
    h.append(f"<h2>{e(tr('Indicateurs calculés'))}</h2><table><tr><th>{e(tr('Modèle'))}</th>"
             f"<th>{e(tr('Pente (récepteur seul)'))}</th><th>{e(tr('Niveau sortie − entrée'))}</th>"
             f"<th>{e(tr('Erreur résiduelle'))}</th><th>{e(tr('Pompage'))}</th><th>{e(tr('Montée'))}</th>"
             f"<th>{e(tr('Descente'))}</th><th>{e(tr('Dépassement'))}</th><th>{e(tr('Saut de 20 dB rendu'))}</th>"
             f"<th>{e(tr('Retard'))}</th></tr>")
    for r in rows:
        m = r["m"]
        h.append(f"<tr><td>{e(tr(r['card']['name']))}</td><td>{r['slope']:.2f}</td><td>{m['diff']:+.1f} dB</td>"
                 f"<td>{m['err']:.0f} dB</td><td>± {m['pump']:.1f} dB</td><td>{m['up']:.0f} ms</td>"
                 f"<td>{m['down']:.0f} ms</td><td>{m['over']:+.1f} dB</td><td>{m['step']:.1f} dB</td>"
                 f"<td>{m['lat']:.1f} ms</td></tr>")
    h.append("</table>")
    if len(rows) >= 2:
        h.append(f"<h2>{e(tr('Différences observées'))}</h2><ul>")
        base = rows[0]
        for r in rows[1:]:
            d = r["m"]["diff"] - base["m"]["diff"]
            h.append("<li>" + e(tr("{} contre {} : niveau {} dB, pompage {} dB, montée {} ms").format(
                tr(r["card"]["name"]), tr(base["card"]["name"]), f"{d:+.1f}",
                f"{r['m']['pump'] - base['m']['pump']:+.1f}", f"{r['m']['up'] - base['m']['up']:+.0f}")) + "</li>")
        h.append("</ul>")
    if observed:
        h.append(f"<h2>{e(tr('Observation réelle'))} <span class='prov'>{e(tr(PROVENANCE['obs']))}</span></h2>")
        if observed.get("ok"):
            h.append("<p>" + e(tr("Émetteur mesuré avec l'escalier : pente {} (taux ≈ {}:1), linéarité R² = {}.").format(
                f"{observed['slope']:.2f}", f"{observed['ratio']:.2f}" if observed.get("ratio") else "—",
                f"{observed['r2']:.3f}")) + "</p>")
        else:
            h.append("<p>" + e(tr(observed.get("why", ""))) + "</p>")
    h.append(f"<h2>{e(tr('Limites de validité'))}</h2><ul>" + "".join(
        f"<li>{e(tr(x))}</li>" for x in (
            "Mesures faites sur les MODÈLES de l'appli (simulation), sauf la section « Observation réelle ».",
            "Le son reçu par un SDR a pu passer par d'autres traitements (limiteur, filtres de l'émetteur) : sans "
            "référence connue, une différence ne peut pas être attribuée au seul compandeur.",
            "Pente mesurée entre −40 et 0 dBFS ; sous −40 dBFS, le genou (ENR) et les butées changent le comportement.",
            "Temps de montée / descente : à 1 dB près du niveau posé, après un saut de 20 dB à 1 kHz.")) + "</ul>")
    return "\n".join(h)


# ===== PURE-END
