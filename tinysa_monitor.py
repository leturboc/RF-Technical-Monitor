#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TinySA Monitor v7
Analyse spectrale + monitoring de 100+ fréquences pour tinySA Ultra.

Nouveautés v7 :
  - Alarmes : statut « Doit émettre » (⚠ ABSENT si un TX se tait), acquittement, priorité par groupe
    (Critique = son répété jusqu'à acquittement), panneau des alarmes
  - Scans WSM / WWB : import d'un scan comme courbe de référence, conversion WSM → WWB, export au format WWB
  - Rapport de fin de show (HTML imprimable en PDF)
  - Enregistrement des balayages + relecture (curseur de temps, lecture accélérée, saut à un événement)
  - Export des fréquences par scène / par groupe

Nouveautés v6 :
  - Intermodulation 2 / 3 / 5 TX (ordres 3, 5, 7) : qui tombe sur quoi, et « d'où ça peut venir ? » pour un
    signal inconnu (note automatique dans le journal)
  - Fréquence de secours : canaux libres d'après le spectre mesuré, sans intermod avec ta liste
  - Nommage rapide : mots de base (MIC, HF, IEM, Intercom, Bolero…), auto-complétion, numérotation +1 sur la
    sélection (HF 1 → HF 5), Ctrl+D pour numéroter vers le bas
  - Fenêtres libres : panneaux déplaçables / détachables (double écran), dispositions prêtes à l'emploi

Nouveautés v5 :
  - Guide des bandes : toute l'étendue 100 kHz – 5,9 GHz expliquée (police/pompiers, aéro, marine, 4G/5G,
    CB/PMR, amateur, satellites/GNSS, radars, ISM…), par pays, avec recherche et ajout en un clic
  - Couches de monitoring : Scènes › Groupes saisis en amont (ou importés), un clic sur un groupe = on
    ne surveille que lui ; bouton Global pour tout voir ; option « scanner seulement la sélection »

Nouveautés v4 :
  - Choix du pays : canaux TV + attributions du spectre (4G/5G, TNT, micros HF, militaire…) en bandeaux
    sous le spectre, infos au survol, colonne « Spectre » dans la liste (indicatif, à vérifier)
  - Taux d'occupation par fréquence (10 min à 12 h), seuil propre à chaque fréquence
  - Statut « doit rester libre » : alerte ⚠ CONFLIT si un signal apparaît
  - Courbe de référence (bruit de fond du lieu) et seuil relatif à cette référence
  - Mur de fréquences (grandes tuiles, 2e écran), profils d'événement, journal CSV automatique
  - Export du scan en CSV (unités / séparateurs au choix)

Nouveautés v3 :
  - 101 -> 30000 points par balayage (découpage automatique en segments)
  - Couleurs 100 % personnalisables (thèmes + sélecteurs), mode "nuit rouge"
  - Etats du signal libre / faible / occupé + statuts manuels personnalisables
  - Import CSV intelligent (Shure, Sennheiser, Wisycom, générique) avec noms automatiques
  - Glisser-déposer d'un CSV sur la fenêtre, filtre, menu clic droit
  - Interface réorganisée (panneau de réglages à gauche)

Dépendances : PySide6, pyqtgraph, pyserial, numpy  (voir requirements.txt)
"""
import bisect
import csv
import io
import itertools
import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters  # noqa: F401  (capture PNG)
import serial
import serial.tools.list_ports
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

APP_NAME = "TinySA Monitor"
APP_VER = "7.0"
MIN_PTS = 51                 # minimum accepté par la commande scan
POINTS_CHOICES = [101, 145, 290, 500, 1000, 3000, 5000, 10000, 30000]
SEG_CHOICES = [None, 145, 290, 450]     # points max par commande scan (None = auto)
RBW_LIST = [0.3, 1, 3, 10, 30, 100, 300, 600, 850]
WF_ROWS = 150                # profondeur du waterfall
WF_MAX_COLS = 3000           # colonnes max du waterfall (réduction par maximum)
ZOOM_ID = -2                 # identifiant interne de la "bande" de zoom live
MAX_LABELS = 30              # nb max de noms affichés sur le graphe
HYST = 3.0                   # hystérésis (dB) pour repasser en "libre"
TINYSA_VID, TINYSA_PID = 0x0483, 0x5740
CFG_PATH = Path(os.environ.get("APPDATA", str(Path.home()))) / "TinySAMonitor" / "config.json"
PROFILE_DIR = CFG_PATH.parent / "profils"
REF_PATH = CFG_PATH.parent / "reference.json"
LOG_DIR = Path.home() / "Documents" / "TinySA Monitor" / "Journaux"

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
    ("st_free", "Signal : libre", "Etats du signal"),
    ("st_weak", "Signal : faible", "Etats du signal"),
    ("st_occ", "Signal : occupé", "Etats du signal"),
    ("st_unk", "Signal : inconnu (hors liste)", "Etats du signal"),
    ("st_none", "Pas encore de mesure", "Etats du signal"),
]

THEMES = {
    "Sombre": dict(ui_bg="#1b2027", ui_base="#11151a", ui_button="#262d36", ui_text="#dfe6ee",
                   ui_accent="#2f81f7", plot_bg="#0f1318", plot_fg="#c8d0d8", curve="#4fd0ff",
                   maxhold="#ffb347", thr="#ff6666", thr_weak="#e0b43c", st_free="#2ecc71",
                   st_weak="#f1c40f", st_occ="#ff4d4d", st_unk="#ffa94d", st_none="#7d8896",
                   wf="Inferno"),
    "Clair": dict(ui_bg="#f0f2f5", ui_base="#ffffff", ui_button="#e1e6ec", ui_text="#1d232b",
                  ui_accent="#2f81f7", plot_bg="#ffffff", plot_fg="#2b333d", curve="#0b6fb8",
                  maxhold="#d9822b", thr="#d62f2f", thr_weak="#c79a00", st_free="#1e9e57",
                  st_weak="#c79a00", st_occ="#d62f2f", st_unk="#e07a1f", st_none="#8a94a0",
                  wf="Gris"),
    "Haut contraste": dict(ui_bg="#000000", ui_base="#000000", ui_button="#242424", ui_text="#ffffff",
                           ui_accent="#0078ff", plot_bg="#000000", plot_fg="#ffffff", curve="#00ffff",
                           maxhold="#ffff00", thr="#ff3030", thr_weak="#ffa500", st_free="#00ff66",
                           st_weak="#ffe600", st_occ="#ff2d2d", st_unk="#ff9d00", st_none="#9a9a9a",
                           wf="Chaud"),
    "Nuit (rouge)": dict(ui_bg="#140000", ui_base="#0b0000", ui_button="#2a0707", ui_text="#ff7a7a",
                         ui_accent="#a01818", plot_bg="#090000", plot_fg="#d05555", curve="#ff4a4a",
                         maxhold="#a02a2a", thr="#ffb4b4", thr_weak="#c07070", st_free="#8a3535",
                         st_weak="#e0803c", st_occ="#ff2a2a", st_unk="#ffb347", st_none="#6a3030",
                         wf="Rouge (nuit)"),
    "Analyseur vert": dict(ui_bg="#06150a", ui_base="#020a04", ui_button="#0f2a16", ui_text="#9dffb0",
                           ui_accent="#1f9d4a", plot_bg="#010802", plot_fg="#58c46f", curve="#3dff6a",
                           maxhold="#e8ff4a", thr="#ff5a5a", thr_weak="#ffc24a", st_free="#3dff6a",
                           st_weak="#ffd84a", st_occ="#ff4d4d", st_unk="#ffa94d", st_none="#4a7a56",
                           wf="Viridis"),
}

WF_MAPS = {
    "Inferno": [(0.0, (0, 0, 4)), (0.25, (87, 16, 110)), (0.5, (188, 55, 84)),
                (0.75, (249, 142, 9)), (1.0, (252, 255, 164))],
    "Viridis": [(0.0, (68, 1, 84)), (0.25, (59, 82, 139)), (0.5, (33, 145, 140)),
                (0.75, (94, 201, 98)), (1.0, (253, 231, 37))],
    "Gris": [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))],
    "Chaud": [(0.0, (0, 0, 0)), (0.33, (180, 0, 0)), (0.66, (255, 200, 0)), (1.0, (255, 255, 255))],
    "Bleu-rouge": [(0.0, (0, 0, 60)), (0.35, (0, 120, 255)), (0.65, (255, 230, 0)), (1.0, (255, 0, 0))],
    "Rouge (nuit)": [(0.0, (0, 0, 0)), (0.5, (140, 0, 0)), (1.0, (255, 80, 80))],
}

DEFAULT_STATUSES = [("Libre", "#2ecc71"), ("Occupé", "#e74c3c"),
                    ("Réservé", "#3498db"), ("Hors service", "#7f8c8d"), ("En service", "#f1c40f")]
STATUS_AUTO_COLORS = ["#9b59b6", "#1abc9c", "#f39c12", "#e91e63", "#00bcd4", "#8bc34a",
                      "#ff7043", "#5c6bc0"]

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


def contrast_text(bg):
    r, g, b = hex_to_rgb(bg)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def make_stylesheet(t):
    bd = blend(t["ui_text"], t["ui_bg"], 0.28)
    return (
        "QGroupBox { border:1px solid %s; border-radius:6px; margin-top:12px; padding:10px 6px 6px 6px; }"
        "QGroupBox::title { subcontrol-origin: margin; left:10px; padding:0 4px; color:%s; }"
        "QToolTip { color:%s; background:%s; border:1px solid %s; }"
        "QTabBar::tab { padding:6px 14px; }"
        % (bd, t["ui_accent"], t["ui_text"], t["ui_button"], bd))


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
    freqs = np.array(fr, dtype=float) if (len(fr) == len(lv) and len(fr) > 0) else None
    return freqs, levels


# ----------------------------------------------------------------- import CSV
def decode_text(raw):
    """Décode un fichier texte (UTF-8, UTF-16 Excel, cp1252, latin-1)."""
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
_NIGHT_BP = dict(tv="#8a2a2a", tv_off="#3a1212", mobile="#c03030", pmse="#ff5a5a", broadcast="#a04040",
                 safety="#ff2a2a", mil="#7a3a10", aero="#b04848", marine="#8a3030", sat="#a05050",
                 ism="#b05050", amateur="#c08040", civ="#d06a3a", pro="#904040", other="#4a2020")
for _n, _t in THEMES.items():
    _t.setdefault("ref", "#ff9a9a" if _n == "Nuit (rouge)" else "#c084fc")
    for _k, (_lab, _col) in CATEGORIES.items():
        _t.setdefault("bp_" + _k, _NIGHT_BP[_k] if _n == "Nuit (rouge)" else _col)

COUNTRIES = [("FR", "France"), ("BE", "Belgique"), ("CH", "Suisse"), ("DE", "Allemagne"),
             ("GB", "Royaume-Uni"), ("IT", "Italie"), ("ES", "Espagne"), ("NL", "Pays-Bas"),
             ("EU", "Europe (générique CEPT)"), ("US", "États-Unis"), ("CA", "Canada")]

COUNTRY_NOTES = {
    "FR": "Plan indicatif (ANFR / TNRBF). 470-694 MHz partagés TNT (canaux 21-48) / micros HF ; 700 et 800 MHz attribués "
          "à la 4G/5G ; 823-832, 863-865 et 1785-1805 MHz libres pour les micros HF ; 380-400 MHz : réseaux "
          "police / pompiers / secours.",
    "DE": "Plan indicatif (BNetzA). DVB-T2 sur les canaux 21-48 ; 736-753 MHz micros HF sans licence ; 823-832 MHz et 1785-1805 MHz libres.",
    "GB": "Plan indicatif (Ofcom). Canal 38 (606-614) et canal 70 (863-865) sans licence ; 700 MHz libéré en 2020, bande de garde 694-703 MHz conservée.",
    "CH": "Plan indicatif (OFCOM). DVB-T arrêté en 2019 : à vérifier pour l'usage des micros HF en UHF.",
    "BE": "Plan indicatif (IBPT). Usage de la TNT très réduit : à vérifier.",
    "IT": "Plan indicatif (MIMIT/AGCOM). Transition DVB-T2 : à vérifier.",
    "ES": "Plan indicatif (CNMC / SETID). 700 MHz libéré en 2020.",
    "NL": "Plan indicatif (Agentschap Telecom).",
    "EU": "Plan harmonisé CEPT / UIT région 1, indicatif.",
    "US": "Plan indicatif (FCC). Canaux TV de 6 MHz ; bande 600 MHz vendue aux opérateurs mobiles ; micros HF limités après 2020.",
    "CA": "Plan proche des USA (ISED). Canaux TV de 6 MHz ; vérifier les règles canadiennes.",
}

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
430-440|amateur|Radioamateur 70 cm|
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
865-870|ism|SRD / RFID / IoT 868 MHz|
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
470-606|tv|TNT (DVB-T2) + micros HF pros : usage partagé|
606-614|other|Canal 38 : hors micros HF en France (radioastronomie)|
614-694|tv|TNT (DVB-T2) + micros HF pros : usage partagé|
""",
    "DE": """
736-753|pmse|Micros HF professionnels sans licence (Allemagne)|
1492-1525|pmse|Micros HF : enregistrement requis, intérieur|
""",
    "GB": """
606-614|pmse|Canal 38 : micros HF sans licence (UK)|
863-865|pmse|Canal 70 : micros HF sans licence (UK)|
""",
    "CH": """
470-694|pmse|UHF : DVB-T éteint (2019), micros HF : vérifier OFCOM|
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
902-928|ism|ISM 900 MHz (micros numériques, LoRa)|
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


def eff_thresholds(own_thr, ref_lvl, rel_on, margin, gthr, gweak):
    """Seuils (occupé, faible) : seuil propre > référence + marge > seuil global."""
    if own_thr is not None:
        return own_thr, own_thr - (gthr - gweak)
    if rel_on and ref_lvl is not None:
        return ref_lvl + margin, ref_lvl + margin / 2.0
    return gthr, gweak


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


def im_pairs(n, order, max_tx=None):
    """Nombre de couples (groupe +, groupe −) à examiner pour n émetteurs et un ordre impair.
    Avec max_tx ≤ 2 (produits du type 2A−B), seuls les couples ordonnés d'émetteurs comptent."""
    if max_tx is not None and max_tx <= 2:
        return n * (n - 1)
    p = (order + 1) // 2
    q = order - p
    return math.comb(n + p - 1, p) * math.comb(n + q - 1, q)


def im_scan(freqs, orders=(3,), max_tx=3, targets=None, guard=0.2, fmin=0.1, fmax=6000.0, limit=20000):
    """Produits d'intermodulation d'une liste d'émetteurs (MHz).

    Un produit d'ordre n vaut (somme de p fréquences) − (somme de q fréquences), avec p = q + 1 et p + q = n
    (on ne garde que ceux qui retombent dans la même bande). Un émetteur n'est jamais dans les deux
    groupes (il s'annulerait). max_tx = nombre maximal d'émetteurs DIFFÉRENTS impliqués :
    2 -> 2A−B ; 3 -> A+B−C ; 5 -> A+B+C−D−E…
    targets : fréquences à protéger. Si fourni, on ne garde que les produits qui tombent à moins de `guard`
    MHz de l'une d'elles (hors émetteurs impliqués dans le produit lui-même).
    -> (rows, info). rows = [dict(f, order, terms, ntx, target, delta)] ; terms = [(indice, coefficient)]."""
    F = np.asarray(list(freqs), dtype=float)
    n = len(F)
    info = dict(pairs=0, truncated=False, too_big=False)
    rows = []
    if n < 2:
        return rows, info
    T = None
    if targets is not None:
        T = np.sort(np.asarray(list(targets), dtype=float))
        if len(T) == 0:
            return rows, info
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
            msk = (vals >= fmin) & (vals <= fmax)
            tv = None
            if T is not None:
                k = np.searchsorted(T, vals)
                ilo, ihi = np.clip(k - 1, 0, len(T) - 1), np.clip(k, 0, len(T) - 1)
                tv = np.where(np.abs(T[ihi] - vals) < np.abs(T[ilo] - vals), T[ihi], T[ilo])
                msk &= np.abs(vals - tv) <= guard
                msk &= (np.abs(F[ii] - tv) >= 1e-6) & (np.abs(F[jj] - tv) >= 1e-6)
            hits = np.nonzero(msk)[0]
            if len(hits) > cap:
                info["truncated"] = True
                hits = hits[:cap]
            for h in hits:
                rows.append(dict(f=float(vals[h]), order=order, ntx=2,
                                 terms=[(int(ii[h]), a), (int(jj[h]), -b)],
                                 target=None if tv is None else float(tv[h]),
                                 delta=None if tv is None else float(vals[h] - tv[h])))
        if T is not None:
            rows.sort(key=lambda r: (r["order"], r["ntx"], abs(r["delta"]), r["f"]))
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
                m &= np.minimum(np.abs(prod - lo), np.abs(prod - hi)) <= guard
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
            tv = None
            if T is not None:
                k = np.searchsorted(T, vals)
                ilo, ihi = np.clip(k - 1, 0, len(T) - 1), np.clip(k, 0, len(T) - 1)
                tv = np.where(np.abs(T[ihi] - vals) < np.abs(T[ilo] - vals), T[ihi], T[ilo])
                ok &= ~(np.abs(F[allidx] - tv[:, None]) < 1e-6).any(axis=1)
            for h in np.nonzero(ok)[0]:
                terms = {}
                for t_i in pi[h]:
                    terms[int(t_i)] = terms.get(int(t_i), 0) + 1
                for t_i in qj[h]:
                    terms[int(t_i)] = terms.get(int(t_i), 0) - 1
                rows.append(dict(f=float(vals[h]), order=order, ntx=int(ntx[h]),
                                 terms=sorted(terms.items(), key=lambda kv: (-kv[1], kv[0])),
                                 target=None if tv is None else float(tv[h]),
                                 delta=None if tv is None else float(vals[h] - tv[h])))
            if len(rows) > cap:
                info["truncated"] = True
                break
        if info["truncated"]:
            break
    if T is not None:
        rows.sort(key=lambda r: (r["order"], r["ntx"], abs(r["delta"]), r["f"]))
    else:
        rows.sort(key=lambda r: (r["f"], r["order"]))
    if len(rows) > limit:
        info["truncated"] = True
        rows = rows[:limit]
    return rows, info


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


def im_explain(f, freqs, orders=(3, 5), max_tx=5, tol=0.1, limit=40):
    """Quelles combinaisons d'émetteurs peuvent produire un signal à f (MHz) ?"""
    return im_scan(freqs, orders, max_tx, targets=[f], guard=tol, limit=limit)


def im3_clash(c, F, guard):
    """Collisions d'intermodulation 3e ordre mettant en jeu la fréquence candidate c (MHz) avec les émetteurs F.
    -> [(texte, écart en MHz)] ; vide = aucun risque à ± guard."""
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
        m = (J != K) & (idx != J) & (idx != K) & (np.abs(d) <= guard)
        for j, k in zip(*np.nonzero(m)):
            out.append((f"{c:.3f} + {F[j]:.3f} − {F[k]:.3f} ≈ {F[idx[j, k]]:.3f}", float(d[j, k])))
        # fj + fk − c ≈ fl
        idx, d = nearest(F[J] + F[K] - c)
        m = (J < K) & (idx != J) & (idx != K) & (np.abs(d) <= guard)
        for j, k in zip(*np.nonzero(m)):
            out.append((f"{F[j]:.3f} + {F[k]:.3f} − {c:.3f} ≈ {F[idx[j, k]]:.3f}", float(d[j, k])))
    out.sort(key=lambda t: abs(t[1]))
    return out


def find_free(F, L, a, b, existing, n=3, width=0.2, min_sep=0.3, thr=-90.0, guard=0.2, grid=0.025,
              max_check=600):
    """Cherche n fréquences libres entre a et b (MHz) d'après un spectre mesuré (F trié, L en dBm) :
    niveau max sur ± width/2 sous thr, à plus de min_sep de toute fréquence existante ou déjà choisie,
    et sans intermodulation 3e ordre à ± guard sur l'ensemble.
    -> (liste de dict(f, level, dist), diag)"""
    ex = sorted(float(x) for x in existing)
    diag = dict(grille=0, sans_mesure=0, bruyantes=0, trop_proches=0, intermod=0)
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
    good = ~np.isnan(lv)
    quiet = good & (lv <= thr)
    diag["bruyantes"] = int((good & ~quiet).sum())
    exa = np.array(ex)

    def dist_to(c, arr):
        return float(np.min(np.abs(arr - c))) if len(arr) else 1e9

    order = [i for i in np.nonzero(quiet)[0]]
    order.sort(key=lambda i: (round(float(lv[i])), -dist_to(float(cand[i]), exa)))
    chosen = []
    for i in order[:max_check]:
        c = float(cand[i])
        allf = np.array(ex + chosen)
        if dist_to(c, allf) < min_sep:
            diag["trop_proches"] += 1
            continue
        if im3_clash(c, allf, guard):
            diag["intermod"] += 1
            continue
        chosen.append(c)
        res.append(dict(f=c, level=float(lv[i]), dist=dist_to(c, exa)))
        if len(res) >= n:
            break
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


def parse_scan_text(text):
    """Lit un scan de fréquences : export WSM (Sennheiser) ou fichier « fréquence, niveau » (WWB, notre export…).
    -> (F en MHz croissant, L en dBm, info) ; ValueError avec un message clair si ce n'est pas un scan."""
    text = str(text).lstrip("﻿")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # --- export WSM : « Frequency;RF level (%);RF level;Memory (%);… », niveau en % de 0 (−120 dBm) à 100 (0 dBm)
    for k, ln in enumerate(lines[:80]):
        cells = [c.strip().strip('"') for c in ln.split(";")]
        low = [c.lower() for c in cells]
        if len(cells) >= 2 and low[0].startswith("freq") and any("(%)" in c for c in low[1:]):
            cols = [i for i, c in enumerate(low) if i > 0 and "(%)" in c]
            col = next((i for i in cols if "rf level" in low[i]), cols[0])
            F, L = [], []
            for ln2 in lines[k + 1:]:
                cs = [c.strip().strip('"') for c in ln2.split(";")]
                f = _scan_float(cs[0]) if cs else None
                p = _scan_float(cs[col]) if len(cs) > col else None
                if f is None or p is None:
                    if F:
                        break
                    continue
                F.append(f)
                L.append(p * 1.2 - 120.0)
            if len(F) < 5:
                raise ValueError("l'en-tête WSM est là, mais je ne trouve pas de points de mesure en dessous")
            F = np.asarray(F, dtype=float)
            F = F * scan_unit_scale(F, _scan_unit_hint(ln))
            L = np.asarray(L, dtype=float)
            o = np.argsort(F, kind="stable")
            return F[o], L[o], dict(fmt="wsm", n=len(F), unit="kHz",
                                    note="export WSM : niveau en % converti en dBm (0 % = −120 dBm, 100 % = 0 dBm)")
    # --- fichier simple : « fréquence, niveau » (WWB), « fréquence;niveau », tabulations, avec ou sans en-tête
    F, L, hint = [], [], None
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
    if float(np.nanmax(L)) > 30.0:
        note = "niveaux supérieurs à 30 : ce ne sont peut-être pas des dBm"
    o = np.argsort(F, kind="stable")
    return F[o], L[o], dict(fmt="simple", n=len(F), unit=unit, note=note)


def wwb_scan_text(F, L):
    """Texte d'import de scan pour WWB : une ligne « 470.000, -98 » par point (MHz, dBm entier), sans en-tête."""
    out = []
    for f, l in zip(F, L):
        f, l = float(f), float(l)
        if math.isfinite(f) and math.isfinite(l):
            out.append(f"{f:.3f}, {int(round(l))}")
    return "\r\n".join(out) + "\r\n"


def wsm_to_wwb_text(text):
    """Export WSM (ou tout scan lisible) -> texte pour WWB. -> (texte, info)."""
    F, L, info = parse_scan_text(text)
    return wwb_scan_text(F, L), info


# ------------------------------------------------- alarmes : acquittement, priorités
ALARM_PRIO = {2: "Critique", 1: "Normale", 0: "Info"}
ALARM_ORDER = (2, 1, 0)


class AlarmBook:
    """Registre des alarmes : une alarme par (type, fréquence), qui reste affichée jusqu'à ce que la cause
    disparaisse ; l'acquittement coupe le son sans l'effacer."""

    def __init__(self, repeat_s=10.0):
        self.active = {}          # clé -> alarme en cours
        self.done = []            # alarmes terminées (les plus récentes en dernier)
        self.seq = 0
        self.repeat_s = float(repeat_s)

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
        self.active[key] = dict(id=self.seq, key=key, kind=kind, name=name, freq=freq, prio=int(prio), t0=now,
                                t_last=now, t_end=None, level=level, layer=layer, info=info, acked=False,
                                last_sound=now)
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
        """Alarmes à afficher : en cours (non acquittées d'abord, par priorité), puis terminées (récentes d'abord)."""
        cur = sorted(self.active.values(), key=lambda a: (a["acked"], -a["prio"], a["t0"]))
        return cur + list(reversed(self.done))

    def due_repeat(self, now):
        """Alarmes critiques toujours non acquittées dont le son doit être rejoué."""
        out = []
        for a in self.active.values():
            if a["prio"] >= 2 and not a["acked"] and now - a["last_sound"] >= self.repeat_s:
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
         ".thr{stroke:#d33;stroke-dasharray:5 4}",
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
    p.append(f"<p class='muted'>Généré par {e(d.get('app', 'TinySA Monitor'))}. Mesures indicatives du tinySA : "
             "elles ne remplacent pas ta coordination (EazyRF / WWB…).</p></body></html>")
    return "".join(p)


# ===== PURE-END


# --------------------------------------------------------------------------
# Communication avec le tinySA
# --------------------------------------------------------------------------
class TinySA:
    PROMPT = b"ch>"

    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.2)
        self.ser.reset_input_buffer()
        self.cmd("", timeout=3)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    def cmd(self, text, timeout=15.0):
        self.ser.reset_input_buffer()
        self.ser.write((text + "\r").encode())
        buf, t0 = b"", time.time()
        while True:
            if time.time() - t0 > timeout:
                raise TimeoutError(f"Pas de réponse du tinySA à « {text} »")
            n = self.ser.in_waiting
            chunk = self.ser.read(n if n else 1)
            if chunk:
                buf += chunk
                if buf.rstrip().endswith(self.PROMPT):
                    break
        lines = [l.strip() for l in buf.decode(errors="ignore").replace("\r", "\n").split("\n")]
        lines = [l for l in lines if l and not l.startswith("ch>")]
        if lines and text and lines[0].startswith(text[:12]):
            lines = lines[1:]
        return lines

    def try_cmd(self, text):
        """Commande de réglage ; renvoie (ok, message d'erreur)."""
        try:
            lines = self.cmd(text, timeout=6)
        except TimeoutError:
            return False, f"{text} : pas de réponse"
        bad = [l for l in lines if "usage" in l.lower() or l.endswith("?")]
        return (not bad), (f"{text} : {bad[0]}" if bad else "")

    def version(self):
        try:
            lines = self.cmd("version", timeout=4)
            return lines[0] if lines else ""
        except Exception:
            return ""

    def set_rbw(self, khz):
        return self.try_cmd("rbw auto" if khz is None else f"rbw {khz:g}")

    def set_input(self, high):
        return self.try_cmd("mode high input" if high else "mode low input")

    def scan(self, start_hz, stop_hz, points):
        """Renvoie (freqs Hz ou None, niveaux dBm)."""
        lines = self.cmd(f"scan {int(start_hz)} {int(stop_hz)} {int(points)} 3", timeout=900)
        freqs, levels = parse_scan_lines(lines)
        if not len(levels):
            raise RuntimeError("Le tinySA n'a renvoyé aucune mesure (scan).")
        return freqs, levels


# --------------------------------------------------------------------------
# Thread de balayage
# --------------------------------------------------------------------------
class ScanWorker(QtCore.QThread):
    sweep = Signal(int, object, object)            # id bande, freqs MHz, niveaux dBm
    partial = Signal(int, object, object, int, int)  # id bande, freqs, niveaux, segment, total
    cycle = Signal(float, int)                     # durée du cycle, nb de bandes
    status = Signal(str)
    info = Signal(str)
    error = Signal(str)

    def __init__(self, port, demo, get_cfg, get_ver):
        super().__init__()
        self.port, self.demo = port, demo
        self.get_cfg, self.get_ver = get_cfg, get_ver
        self.rng = np.random.default_rng()
        self.demo_carriers = {}
        self.seg_auto = 290
        self.st = dict(rbw="?", front="?", high=None)

    def run(self):
        dev = None
        try:
            if not self.demo:
                dev = TinySA(self.port)
                ver = dev.version()
                if "tinysa4" in ver.lower():
                    self.seg_auto = 450
                self.info.emit(ver or "tinySA")
                self.status.emit(f"Connecté sur {self.port}")
            else:
                self.info.emit("Mode démo")
                self.status.emit("Mode démo (signaux simulés)")
            while not self.isInterruptionRequested():
                cfg = self.get_cfg()
                bands = [b for b in cfg["bands"] if b["enabled"]]
                if not bands:
                    self.status.emit("Aucune bande active")
                    self.msleep(300)
                    continue
                if dev is not None:
                    self._apply_settings(dev, cfg)
                t0, aborted = time.time(), False
                for b in bands:
                    res = self._scan_band(dev, b, cfg)
                    if res is None:
                        aborted = True
                        break
                    if len(res[0]):
                        self.sweep.emit(b["id"], res[0], res[1])
                if not aborted and not self.isInterruptionRequested():
                    self.cycle.emit(time.time() - t0, len(bands))
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        finally:
            if dev is not None:
                dev.close()

    def _apply_settings(self, dev, cfg):
        if cfg["rbw"] != self.st["rbw"]:
            ok, msg = dev.set_rbw(cfg["rbw"])
            self.st["rbw"] = cfg["rbw"]
            if not ok:
                self.status.emit(f"⚠ Réglage refusé par le tinySA — {msg}")
        front = (cfg["lna"], cfg["att"])
        if front != self.st["front"]:
            self._apply_front(dev, cfg)
            self.st["front"] = front

    def _apply_front(self, dev, cfg):
        """LNA + atténuateur (mutuellement exclusifs sur le tinySA)."""
        fails = []
        if cfg["lna"] is True:
            ok, m = dev.try_cmd("lna on")
            if not ok:
                fails.append(m)
        else:
            if cfg["lna"] is False:
                ok, m = dev.try_cmd("lna off")
                if not ok:
                    fails.append(m)
            ok, m = dev.try_cmd("attenuate auto" if cfg["att"] == "auto" else f"attenuate {cfg['att']}")
            if not ok:
                fails.append(m)
        if fails:
            self.status.emit("⚠ Réglage refusé par le tinySA — " + " ; ".join(fails))

    def _scan_band(self, dev, b, cfg):
        """Balaye une bande en segments. Renvoie None si la config a changé / arrêt demandé."""
        n = max(2, int(b["n"]))
        grid = np.linspace(b["start_hz"], b["stop_hz"], n)
        step = (b["stop_hz"] - b["start_hz"]) / (n - 1)
        seg = cfg["seg"] or self.seg_auto
        plan = segment_plan(n, seg)
        fo, lo = [], []
        for k, (i0, i1) in enumerate(plan):
            if self.isInterruptionRequested() or self.get_ver() != cfg["ver"]:
                return None
            a, z = grid[i0], grid[i1 - 1]
            pts = i1 - i0
            if z <= a:
                z = a + step
            if pts < MIN_PTS:
                pts = MIN_PTS
            if dev is not None:
                high = (cfg["input"] == "high") or (cfg["input"] == "auto" and a >= 800e6)
                if high != self.st["high"]:
                    ok, msg = dev.set_input(high)
                    self.st["high"] = high
                    if not ok:
                        self.status.emit(f"⚠ Changement d'entrée refusé — {msg}")
                    self._apply_front(dev, cfg)
                fr, lv = dev.scan(a, z, pts)
                if fr is None or len(fr) != len(lv):
                    fr = np.linspace(a, z, len(lv))
            else:
                fr = np.linspace(a, z, pts)
                lv = self._demo_levels(fr, b, cfg)
                self.msleep(30 + pts // 10)
            fo.append(fr / 1e6)
            lo.append(lv + cfg["offset"])
            if len(plan) > 1 and k < len(plan) - 1:
                self.partial.emit(b["id"], np.concatenate(fo), np.concatenate(lo), k + 1, len(plan))
        if not fo:
            return np.array([]), np.array([])
        return np.concatenate(fo), np.concatenate(lo)

    def _demo_levels(self, fr, b, cfg):
        lv = -98 + self.rng.normal(0, 1.2, len(fr))
        key = (b["id"], round(b["start_hz"] / 1e5), round(b["stop_hz"] / 1e5))
        if len(self.demo_carriers) > 40:
            self.demo_carriers.clear()
        rnd = self.demo_carriers.setdefault(
            key, [(self.rng.uniform(b["start_hz"], b["stop_hz"]),
                   self.rng.uniform(-70, -40), self.rng.uniform(0.3, 1.2),
                   self.rng.uniform(0, 6)) for _ in range(5)])
        car = list(rnd)
        for k, f in enumerate(cfg["demo_freqs"]):
            if k % 4 == 0:
                car.append((f * 1e6, -62 - (k % 5) * 4, 0.4 + (k % 3) * 0.3, k))
        t = time.time()
        for pos, amp, w, ph in car:
            if fr[0] - 2e5 <= pos <= fr[-1] + 2e5 and np.sin(t * w + ph) > -0.2:
                d = (fr - pos) / 100e3
                lv = np.maximum(lv, amp - 12 * d ** 2 + self.rng.normal(0, 0.8, len(fr)))
        return lv


# --------------------------------------------------------------------------
# Aides graphiques
# --------------------------------------------------------------------------
def build_palette(t):
    C = QtGui.QColor
    R, G = QtGui.QPalette.ColorRole, QtGui.QPalette.ColorGroup
    p = QtGui.QPalette()
    p.setColor(R.Window, C(t["ui_bg"]))
    p.setColor(R.WindowText, C(t["ui_text"]))
    p.setColor(R.Base, C(t["ui_base"]))
    p.setColor(R.AlternateBase, C(t["ui_bg"]))
    p.setColor(R.Text, C(t["ui_text"]))
    p.setColor(R.Button, C(t["ui_button"]))
    p.setColor(R.ButtonText, C(t["ui_text"]))
    p.setColor(R.ToolTipBase, C(t["ui_button"]))
    p.setColor(R.ToolTipText, C(t["ui_text"]))
    p.setColor(R.Highlight, C(t["ui_accent"]))
    p.setColor(R.HighlightedText, C(contrast_text(t["ui_accent"])))
    p.setColor(R.PlaceholderText, C(blend(t["ui_text"], t["ui_bg"], 0.5)))
    dis = C(blend(t["ui_text"], t["ui_bg"], 0.4))
    p.setColor(G.Disabled, R.Text, dis)
    p.setColor(G.Disabled, R.ButtonText, dis)
    p.setColor(G.Disabled, R.WindowText, dis)
    return p


def make_lut(name):
    stops = WF_MAPS.get(name) or WF_MAPS["Inferno"]
    cmap = pg.ColorMap([s[0] for s in stops], [s[1] for s in stops])
    return cmap.getLookupTable(0.0, 1.0, 256)


def color_icon(color, size=12):
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtGui.QColor(color))
    return QtGui.QIcon(pm)


class FlowLayout(QtWidgets.QLayout):
    """Rangée de widgets qui passe à la ligne quand la fenêtre est trop étroite (barres d'outils)."""

    def __init__(self, parent=None, hspace=6, vspace=4):
        super().__init__(parent)
        self._items, self._hs, self._vs = [], hspace, vspace
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._place(QtCore.QRect(0, 0, w, 0), False)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._place(r, True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        sz = QtCore.QSize()
        for it in self._items:
            sz = sz.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return sz + QtCore.QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, r, apply):
        m = self.contentsMargins()
        r = r.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = r.x(), r.y(), 0
        for it in self._items:
            if it.isEmpty():
                continue
            sh = it.sizeHint()
            if x + sh.width() > r.right() + 1 and line_h > 0:
                x, y, line_h = r.x(), y + line_h + self._vs, 0
            if apply:
                it.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), sh))
            x += sh.width() + self._hs
            line_h = max(line_h, sh.height())
        return y + line_h - r.y() + m.top() + m.bottom()


def swatch_style(color):
    return ("QPushButton{background:%s;color:%s;border:1px solid #888;border-radius:4px;padding:3px 10px;}"
            % (color, contrast_text(color)))


# --------------------------------------------------------------------------
# Dialogue : couleurs
# --------------------------------------------------------------------------
class ColorsDialog(QtWidgets.QDialog):
    def __init__(self, parent, theme, preview_cb):
        super().__init__(parent)
        self.setWindowTitle("Couleurs")
        self.resize(460, 640)
        self.original = dict(theme)
        self.theme = dict(theme)
        self.preview_cb = preview_cb
        self.buttons = {}

        lay = QtWidgets.QVBoxLayout(self)
        self.preset = QtWidgets.QComboBox()
        self.preset.addItem("Personnalisé")
        for n in THEMES:
            self.preset.addItem(n)
        self.preset.activated.connect(self.on_preset)
        self.wf_combo = QtWidgets.QComboBox()
        for n in WF_MAPS:
            self.wf_combo.addItem(n)
        self.wf_combo.setCurrentText(self.theme.get("wf", "Inferno"))
        self.wf_combo.activated.connect(self.on_wf)
        top = QtWidgets.QFormLayout()
        top.addRow("Thème prédéfini :", self.preset)
        top.addRow("Palette du waterfall :", self.wf_combo)
        lay.addLayout(top)

        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        iv = QtWidgets.QVBoxLayout(inner)
        for group in ("Interface", "Graphique", "Etats du signal", "Bandes du spectre"):
            box = QtWidgets.QGroupBox(group)
            form = QtWidgets.QFormLayout(box)
            for key, label, g in THEME_KEYS:
                if g != group:
                    continue
                b = QtWidgets.QPushButton(self.theme[key])
                b.clicked.connect(lambda _=False, k=key: self.pick(k))
                self.buttons[key] = b
                form.addRow(label + " :", b)
            iv.addWidget(box)
        iv.addStretch(1)
        area.setWidget(inner)
        lay.addWidget(area, 1)
        hint = QtWidgets.QLabel("Les couleurs des statuts manuels se règlent dans « Statuts ».\n"
                                "Les changements s'appliquent en direct.")
        lay.addWidget(hint)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.refresh_buttons()

    def refresh_buttons(self):
        for k, b in self.buttons.items():
            b.setText(self.theme[k])
            b.setStyleSheet(swatch_style(self.theme[k]))

    def pick(self, key):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.theme[key]), self, "Choisir une couleur")
        if c.isValid():
            self.theme[key] = c.name()
            self.preset.setCurrentIndex(0)
            self.refresh_buttons()
            self.preview_cb(self.theme)

    def on_preset(self, idx):
        if idx <= 0:
            return
        self.theme = dict(THEMES[self.preset.currentText()])
        self.wf_combo.setCurrentText(self.theme["wf"])
        self.refresh_buttons()
        self.preview_cb(self.theme)

    def on_wf(self, _):
        self.theme["wf"] = self.wf_combo.currentText()
        self.preset.setCurrentIndex(0)
        self.preview_cb(self.theme)

    def reject(self):
        self.preview_cb(self.original)
        super().reject()


# --------------------------------------------------------------------------
# Dialogue : statuts manuels
# --------------------------------------------------------------------------
class StatusDialog(QtWidgets.QDialog):
    def __init__(self, parent, statuses):
        super().__init__(parent)
        self.setWindowTitle("Statuts des fréquences")
        self.resize(520, 420)
        self.rows = [dict(name=s["name"], color=s["color"], orig=s["name"], free=bool(s.get("free", False)),
                          on=bool(s.get("on", False))) for s in statuses]
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel("Crée tes propres statuts (libre, occupé, réservé, en test…)\n"
                                       "et choisis leur couleur. Ils s'affectent dans la liste des fréquences.\n"
                                       "Coche « Doit rester libre » : si un signal apparaît sur une fréquence "
                                       "ayant ce statut, tu as une alerte CONFLIT.\n"
                                       "Coche « Doit émettre » : si la fréquence reste sans signal, tu as une alerte "
                                       "ABSENT (micro HF éteint, pile morte, TX coupé…)."))
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nom du statut", "Couleur", "Doit rester libre", "Doit émettre"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self.on_item)
        lay.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("＋ Ajouter")
        add.clicked.connect(self.add_row)
        rem = QtWidgets.QPushButton("Supprimer")
        rem.clicked.connect(self.del_row)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.rebuild()

    def rebuild(self):
        self._busy = True
        self.table.setRowCount(len(self.rows))
        for r, s in enumerate(self.rows):
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(s["name"]))
            b = QtWidgets.QPushButton(s["color"])
            b.setStyleSheet(swatch_style(s["color"]))
            b.clicked.connect(lambda _=False, i=r: self.pick(i))
            self.table.setCellWidget(r, 1, b)
            ck = QtWidgets.QTableWidgetItem("")
            ck.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            ck.setCheckState(Qt.CheckState.Checked if s.get("free") else Qt.CheckState.Unchecked)
            self.table.setItem(r, 2, ck)
            ck2 = QtWidgets.QTableWidgetItem("")
            ck2.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            ck2.setCheckState(Qt.CheckState.Checked if s.get("on") else Qt.CheckState.Unchecked)
            self.table.setItem(r, 3, ck2)
        self._busy = False

    def on_item(self, item):
        if getattr(self, "_busy", False) or item.row() >= len(self.rows):
            return
        if item.column() == 0:
            self.rows[item.row()]["name"] = item.text().strip()
        elif item.column() == 2:
            self.rows[item.row()]["free"] = item.checkState() == Qt.CheckState.Checked
            if self.rows[item.row()]["free"] and self.rows[item.row()].get("on"):
                self.rows[item.row()]["on"] = False         # « libre » et « doit émettre » s'excluent
                QtCore.QTimer.singleShot(0, self.rebuild)
        elif item.column() == 3:
            self.rows[item.row()]["on"] = item.checkState() == Qt.CheckState.Checked
            if self.rows[item.row()]["on"] and self.rows[item.row()].get("free"):
                self.rows[item.row()]["free"] = False
                QtCore.QTimer.singleShot(0, self.rebuild)

    def pick(self, i):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(self.rows[i]["color"]), self, "Couleur du statut")
        if c.isValid():
            self.rows[i]["color"] = c.name()
            self.rebuild()

    def add_row(self):
        col = STATUS_AUTO_COLORS[len(self.rows) % len(STATUS_AUTO_COLORS)]
        self.rows.append(dict(name="Nouveau statut", color=col, orig=None, free=False, on=False))
        self.rebuild()

    def del_row(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.rows):
            self.rows.pop(r)
            self.rebuild()

    def result_rows(self):
        out, seen = [], set()
        for s in self.rows:
            n = s["name"].strip()
            if n and n.lower() not in seen:
                seen.add(n.lower())
                out.append(dict(name=n, color=s["color"], orig=s["orig"], free=bool(s.get("free")),
                                on=bool(s.get("on")) and not bool(s.get("free"))))
        return out


# --------------------------------------------------------------------------
# Dialogue : import CSV intelligent
# --------------------------------------------------------------------------
class ImportDialog(QtWidgets.QDialog):
    def __init__(self, parent, text, source, scenes=None, preset=("", "")):
        super().__init__(parent)
        self.setWindowTitle("Importer des fréquences")
        self.resize(760, 720)
        self.an = analyze_csv(text)
        self.scenes = scenes or []
        self._preset_group = preset[1]
        an = self.an
        lay = QtWidgets.QVBoxLayout(self)
        delim = {";": "point-virgule", "\t": "tabulation", ",": "virgule", None: "lignes libres"}[an["delim"]]
        info = QtWidgets.QLabel(f"<b>{source}</b><br>Format détecté : <b>{an['brand']}</b> · séparateur : {delim} · "
                                f"{len(an['data'])} ligne(s) · en-tête : {'oui' if an['hdr'] is not None else 'non'}")
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.name_combo = QtWidgets.QComboBox()
        self.name_combo.addItem("(aucune : la fréquence sert de nom)", None)
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItem("(aucune)", None)
        self.scene_col_combo = QtWidgets.QComboBox()
        self.scene_col_combo.addItem("(aucune)", None)
        self.group_col_combo = QtWidgets.QComboBox()
        self.group_col_combo.addItem("(aucune)", None)
        for c in range(an["ncol"]):
            lab = f"{c + 1}. {an['headers'][c]}   (ex. {an['samples'][c][:22]})"
            for cb in (self.name_combo, self.status_combo, self.scene_col_combo, self.group_col_combo):
                cb.addItem(lab, c)
        self.name_combo.setCurrentIndex(max(0, self.name_combo.findData(an["name_col"])))
        self.status_combo.setCurrentIndex(max(0, self.status_combo.findData(an["status_col"])))
        self.scene_col_combo.setCurrentIndex(max(0, self.scene_col_combo.findData(an["scene_col"])))
        self.group_col_combo.setCurrentIndex(max(0, self.group_col_combo.findData(an["group_col"])))
        form.addRow("Colonne des noms :", self.name_combo)
        form.addRow("Colonne du statut :", self.status_combo)
        form.addRow("Colonne de la scène :", self.scene_col_combo)
        form.addRow("Colonne du groupe / artiste :", self.group_col_combo)

        self.scene_edit = QtWidgets.QComboBox()
        self.scene_edit.setEditable(True)
        self.scene_edit.addItem("")
        for s in self.scenes:
            self.scene_edit.addItem(s["name"])
        self.scene_edit.setEditText(preset[0])
        self.group_edit = QtWidgets.QComboBox()
        self.group_edit.setEditable(True)
        self.scene_edit.currentTextChanged.connect(self._fill_groups)
        self._fill_groups()
        form.addRow("Affecter tout le fichier à la scène :", self.scene_edit)
        form.addRow("… et au groupe :", self.group_edit)
        lay.addLayout(form)
        tip = QtWidgets.QLabel("Astuce : un fichier par groupe ? Choisis ici sa scène et son groupe (ou tape-les : "
                               "ils seront créés). Les colonnes du fichier, si elles existent, ont priorité.")
        tip.setWordWrap(True)
        lay.addWidget(tip)

        lay.addWidget(QtWidgets.QLabel("Colonnes de fréquence (coche toutes celles à importer) :"))
        self.freq_list = QtWidgets.QListWidget()
        self.freq_list.setMaximumHeight(110)
        for c in range(an["ncol"]):
            it = QtWidgets.QListWidgetItem(f"{c + 1}. {an['headers'][c]}   (ex. {an['samples'][c][:22]})")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if c in an["freq_cols"] else Qt.CheckState.Unchecked)
            it.setData(Qt.ItemDataRole.UserRole, c)
            self.freq_list.addItem(it)
        lay.addWidget(self.freq_list)

        mode = QtWidgets.QHBoxLayout()
        self.r_add = QtWidgets.QRadioButton("Ajouter à ma liste")
        self.r_rep = QtWidgets.QRadioButton("Remplacer ma liste")
        self.r_add.setChecked(True)
        mode.addWidget(self.r_add)
        mode.addWidget(self.r_rep)
        mode.addStretch(1)
        lay.addLayout(mode)

        self.count_lbl = QtWidgets.QLabel("")
        lay.addWidget(self.count_lbl)
        self.prev = QtWidgets.QTableWidget(0, 5)
        self.prev.setHorizontalHeaderLabels(["Nom", "MHz", "Statut", "Scène", "Groupe"])
        self.prev.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.prev.verticalHeader().setVisible(False)
        self.prev.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.prev, 1)

        self.bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)
        for cb in (self.name_combo, self.status_combo, self.scene_col_combo, self.group_col_combo):
            cb.currentIndexChanged.connect(self.refresh)
        self.scene_edit.currentTextChanged.connect(self.refresh)
        self.group_edit.currentTextChanged.connect(self.refresh)
        self.freq_list.itemChanged.connect(self.refresh)
        self.refresh()

    def _fill_groups(self, *_):
        cur = self.group_edit.currentText().strip() or self._preset_group
        self.group_edit.blockSignals(True)
        self.group_edit.clear()
        self.group_edit.addItem("")
        sc = self.scene_edit.currentText().strip()
        for s in self.scenes:
            if s["name"] == sc:
                for g in s["groups"]:
                    self.group_edit.addItem(g["name"])
        self.group_edit.setEditText(cur)
        self.group_edit.blockSignals(False)

    def selection(self):
        fcols = [self.freq_list.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.freq_list.count())
                 if self.freq_list.item(i).checkState() == Qt.CheckState.Checked]
        return self.name_combo.currentData(), fcols, self.status_combo.currentData()

    def entries(self):
        """-> [(nom, MHz, statut, scène, groupe)]"""
        n, f, s = self.selection()
        ent = build_entries_ex(self.an, n, f, s, self.scene_col_combo.currentData(),
                               self.group_col_combo.currentData())
        fs, fg = self.scene_edit.currentText().strip(), self.group_edit.currentText().strip()
        out = []
        for (nm, fr, st, sc, gr) in ent:
            sc, gr = sc or fs, gr or fg
            if gr and not sc:
                sc = DEFAULT_SCENE
            out.append((nm, fr, st, sc, gr))
        return out

    def replace(self):
        return self.r_rep.isChecked()

    def refresh(self, *_):
        e = self.entries()
        self.count_lbl.setText(f"{len(e)} fréquence(s) trouvée(s). Aperçu :")
        self.prev.setRowCount(min(len(e), 40))
        for r, (n, f, s, sc, gr) in enumerate(e[:40]):
            self.prev.setItem(r, 0, QtWidgets.QTableWidgetItem(n))
            it = QtWidgets.QTableWidgetItem(f"{f:.3f}")
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.prev.setItem(r, 1, it)
            self.prev.setItem(r, 2, QtWidgets.QTableWidgetItem(s))
            self.prev.setItem(r, 3, QtWidgets.QTableWidgetItem(sc))
            self.prev.setItem(r, 4, QtWidgets.QTableWidgetItem(gr))
        self.bb.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(len(e) > 0)


# --------------------------------------------------------------------------
# Dialogue : guide des bandes (que contient chaque bande du spectre ?)
# --------------------------------------------------------------------------
class BandGuideDialog(QtWidgets.QDialog):
    def __init__(self, parent, country, plan, tv, theme, add_cb, view_cb):
        super().__init__(parent)
        self.setWindowTitle(f"Guide des bandes – {country}")
        self.resize(1000, 660)
        self.plan, self.tv, self.theme = plan, tv, theme
        self.add_cb, self.view_cb = add_cb, view_cb
        self.shown = []
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Ce qui est attribué dans le spectre que ton tinySA peut balayer (100 kHz – 5,9 GHz), pays par pays. "
            "Plan <b>indicatif</b> : le Tableau national de répartition des fréquences (ANFR, Ofcom, BNetzA, FCC…) "
            "fait foi. Ici on ne fait que <b>mesurer des niveaux</b> : rien n'est décodé.")
        info.setWordWrap(True)
        lay.addWidget(info)
        top = QtWidgets.QHBoxLayout()
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Attributions du spectre", "plan")
        self.src_combo.addItem("Canaux TV", "tv")
        self.cat_combo = QtWidgets.QComboBox()
        self.cat_combo.addItem("Toutes les catégories", None)
        for k, (lab, _c) in CATEGORIES.items():
            self.cat_combo.addItem(lab, k)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("🔎 Un usage ou une fréquence : police, 4G, CB, ADS-B, 868, 446…")
        self.search.setClearButtonEnabled(True)
        top.addWidget(self.src_combo)
        top.addWidget(self.cat_combo)
        top.addWidget(self.search, 1)
        lay.addLayout(top)
        self.count_lbl = QtWidgets.QLabel("")
        lay.addWidget(self.count_lbl)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Début", "Fin", "Catégorie", "Usage", "Note"])
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 95)
        self.table.setColumnWidth(1, 95)
        self.table.setColumnWidth(2, 190)
        self.table.setColumnWidth(4, 260)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_view())
        lay.addWidget(self.table, 1)
        self.msg = QtWidgets.QLabel("Sélectionne une ligne : « Voir » zoome dessus, « Ajouter » l'ajoute à tes bandes à balayer.")
        lay.addWidget(self.msg)
        row = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("＋ Ajouter aux bandes à balayer")
        b_add.clicked.connect(self.on_add)
        b_view = QtWidgets.QPushButton("🔍 Voir sur le spectre")
        b_view.clicked.connect(self.on_view)
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        row.addWidget(b_add)
        row.addWidget(b_view)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)
        self.src_combo.currentIndexChanged.connect(self.refresh)
        self.cat_combo.currentIndexChanged.connect(self.refresh)
        self.search.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        entries = self.plan if self.src_combo.currentData() == "plan" else self.tv
        cat = self.cat_combo.currentData()
        txt = self.search.text().strip().lower()
        try:
            fnum = float(txt.replace(",", "."))
        except ValueError:
            fnum = None
        self.shown = []
        for e in entries:
            a, b, lab, c, note = e
            if cat and c != cat:
                continue
            if txt:
                hay = f"{lab} {note} {CATEGORIES.get(c, ('',))[0]}".lower()
                if not (txt in hay or (fnum is not None and a <= fnum < b)):
                    continue
            self.shown.append(e)
        t, th = self.table, self.theme
        t.setRowCount(len(self.shown))
        for r, (a, b, lab, c, note) in enumerate(self.shown):
            col = th.get("bp_" + c, "#64748b")
            vals = (fmt_freq_mhz(a), fmt_freq_mhz(b), CATEGORIES.get(c, ("?",))[0], lab, note)
            for k, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if k == 2:
                    it.setBackground(QtGui.QColor(col))
                    it.setForeground(QtGui.QColor(contrast_text(col)))
                it.setToolTip(f"{a:g} – {b:g} MHz\n{lab}" + (f"\n{note}" if note else ""))
                t.setItem(r, k, it)
        self.count_lbl.setText(f"{len(self.shown)} ligne(s)")

    def _current(self):
        r = self.table.currentRow()
        return self.shown[r] if 0 <= r < len(self.shown) else None

    def on_add(self):
        e = self._current()
        if e is None:
            self.msg.setText("Sélectionne d'abord une ligne.")
            return
        self.add_cb(e[2], e[0], e[1])
        self.msg.setText(f"« {e[2]} » ajoutée aux bandes à balayer.")

    def on_view(self):
        e = self._current()
        if e is not None:
            self.view_cb(e[0], e[1])


# --------------------------------------------------------------------------
# Dialogue : plan de fréquences personnalisé
# --------------------------------------------------------------------------
class PlanDialog(QtWidgets.QDialog):
    def __init__(self, parent, country, text):
        super().__init__(parent)
        self.setWindowTitle(f"Plan de fréquences : {country}")
        self.resize(780, 560)
        self.reset = False
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Une ligne par attribution :   début-fin (MHz) | catégorie | libellé | note (facultative)\n"
            "Catégories : " + ", ".join(CATEGORIES) + "\n"
            "Les plans fournis sont indicatifs : corrige-les avec les infos de ton régulateur "
            "(ANFR, Ofcom, BNetzA, FCC…). Les plages les plus étroites sont prioritaires à l'affichage.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.edit = QtWidgets.QPlainTextEdit(text)
        self.edit.setStyleSheet("font-family:Consolas,monospace;")
        self.edit.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.edit, 1)
        row = QtWidgets.QHBoxLayout()
        b_reset = QtWidgets.QPushButton("Rétablir le plan d'origine")
        b_reset.clicked.connect(self.on_reset)
        row.addWidget(b_reset)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def on_reset(self):
        self.reset = True
        super().accept()

    def accept(self):
        if not parse_plan_text(self.edit.toPlainText()):
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Aucune ligne valide.\nExemple :  470-694|tv|TNT|ma note")
            return
        super().accept()

    def result_text(self):
        return "" if self.reset else self.edit.toPlainText()


# --------------------------------------------------------------------------
# Dialogue : export du scan en CSV
# --------------------------------------------------------------------------
class ExportScanDialog(QtWidgets.QDialog):
    def __init__(self, parent, prefs):
        super().__init__(parent)
        self.setWindowTitle("Exporter le scan en CSV")
        self.resize(420, 300)
        p = prefs or {}
        form = QtWidgets.QFormLayout(self)

        def combo(items, cur):
            c = QtWidgets.QComboBox()
            for txt, data in items:
                c.addItem(txt, data)
            c.setCurrentIndex(max(0, c.findData(cur)))
            return c

        self.src = combo([("Balayage actuel", "live"), ("Max hold", "max"),
                          ("Les deux (2 colonnes)", "both")], p.get("src", "live"))
        self.scope = combo([("Bande affichée", "view"), ("Toutes les bandes activées", "all")],
                           p.get("scope", "view"))
        self.unit = combo([("MHz", "MHz"), ("kHz", "kHz"), ("Hz", "Hz")], p.get("unit", "MHz"))
        self.delim = combo([(k, v) for k, v in DELIMS.items()], p.get("delim", ";"))
        self.dec = combo([(". (point)", "."), (", (virgule)", ",")], p.get("dec", ","))
        self.header = QtWidgets.QCheckBox("Ligne d'en-tête")
        self.header.setChecked(p.get("header", True))
        form.addRow("Contenu :", self.src)
        form.addRow("Bandes :", self.scope)
        form.addRow("Unité des fréquences :", self.unit)
        form.addRow("Séparateur de colonnes :", self.delim)
        form.addRow("Séparateur décimal :", self.dec)
        form.addRow("", self.header)
        note = QtWidgets.QLabel("Excel français : MHz, « ; » et virgule. Autres logiciels : essaie kHz ou Hz avec "
                                "point décimal. Le format exact attendu par WWB / WSM dépend de ta version : "
                                "envoie-moi un exemple et je l'ajoute en un clic.")
        note.setWordWrap(True)
        form.addRow(note)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self):
        return dict(src=self.src.currentData(), scope=self.scope.currentData(), unit=self.unit.currentData(),
                    delim=self.delim.currentData(), dec=self.dec.currentData(),
                    header=self.header.isChecked())


# --------------------------------------------------------------------------
# Saisie assistée : nom avec auto-complétion
# --------------------------------------------------------------------------
def make_completer(words, parent):
    comp = QtWidgets.QCompleter(list(words), parent)
    comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    comp.setFilterMode(Qt.MatchFlag.MatchContains)
    comp.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
    return comp


class NameDialog(QtWidgets.QDialog):
    """Saisie d'un nom (scène, groupe, fréquence) avec propositions pendant la frappe."""
    def __init__(self, parent, title, label, words, text=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(430, 130)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(label))
        self.edit = QtWidgets.QLineEdit()
        self.edit.setText(text)
        self.edit.setCompleter(make_completer(words, self.edit))
        lay.addWidget(self.edit)
        lay.addWidget(QtWidgets.QLabel("Tape les premières lettres : des propositions apparaissent."))
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def value(self):
        return self.edit.text().strip()


class NameDelegate(QtWidgets.QStyledItemDelegate):
    """Éditeur de la colonne « Nom » : propose les mots de base, le prochain numéro libre (HF 5…) et les noms déjà utilisés."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def createEditor(self, parent, option, index):
        ed = QtWidgets.QLineEdit(parent)
        ed.setCompleter(make_completer(self.owner.name_suggestions(), ed))
        return ed


class QuickNameDialog(QtWidgets.QDialog):
    """Nommer toute la sélection d'un coup : un mot de base + numérotation automatique (HF 1, HF 2, HF 3…)."""
    def __init__(self, owner, rows):
        super().__init__(owner)
        self.owner, self.rows = owner, list(rows)
        self.setWindowTitle("Nommer la sélection")
        self.resize(560, 640)
        rs = set(self.rows)
        self._others = [w["name"] for i, w in enumerate(owner.watch) if i not in rs]
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(f"<b>{len(self.rows)}</b> fréquence(s) à nommer, dans l'ordre des fréquences."))
        form = QtWidgets.QFormLayout()
        self.base_combo = QtWidgets.QComboBox()
        self.base_combo.setEditable(True)
        self.base_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        words = owner.vocab_all("name")
        for w in words:
            self.base_combo.addItem(w)
        self.base_combo.setCompleter(make_completer(words, self.base_combo))
        self.base_combo.setEditText("HF")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Numéroter : HF 1, HF 2, HF 3…", "num")
        self.mode_combo.addItem("Même nom pour toutes : HF", "same")
        self.auto_chk = QtWidgets.QCheckBox("Commencer au prochain numéro libre pour ce mot")
        self.auto_chk.setChecked(True)
        self.start_spin = QtWidgets.QSpinBox()
        self.start_spin.setRange(0, 9999)
        self.start_spin.setValue(1)
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(0, 4)
        self.width_spin.setToolTip("0 : HF 1   ·   2 : HF 01")
        self.sep_combo = QtWidgets.QComboBox()
        for lab, v in (("espace  (HF 1)", " "), ("rien  (HF1)", ""), ("tiret  (HF-1)", "-"), ("souligné  (HF_1)", "_")):
            self.sep_combo.addItem(lab, v)
        self.rev_chk = QtWidgets.QCheckBox("Du plus haut au plus bas en fréquence")
        self.learn_chk = QtWidgets.QCheckBox("Retenir ce mot dans mon vocabulaire")
        self.base_combo.setToolTip("Tape un mot (HF, MIC, IEM, Bolero…) : il est numéroté tout seul.\n"
                                   "Tape « HF 5 » pour démarrer à 5.")
        self.learn_chk.setChecked(True)
        form.addRow("Mot :", self.base_combo)
        form.addRow("Mode :", self.mode_combo)
        form.addRow(self.auto_chk)
        form.addRow("Premier numéro :", self.start_spin)
        form.addRow("Zéros de remplissage :", self.width_spin)
        form.addRow("Séparateur :", self.sep_combo)
        form.addRow(self.rev_chk)
        form.addRow(self.learn_chk)
        lay.addLayout(form)
        lay.addWidget(QtWidgets.QLabel("Aperçu :"))
        self.prev = QtWidgets.QTableWidget(0, 3)
        self.prev.setHorizontalHeaderLabels(["MHz", "Avant", "Après"])
        self.prev.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.prev.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.prev.verticalHeader().setVisible(False)
        self.prev.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.prev, 1)
        self.bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)
        self.base_combo.currentTextChanged.connect(self._on_base)
        self.auto_chk.toggled.connect(self._on_base)
        for w in (self.mode_combo, self.sep_combo):
            w.currentIndexChanged.connect(self.refresh)
        self.start_spin.valueChanged.connect(self.refresh)
        self.width_spin.valueChanged.connect(self.refresh)
        self.rev_chk.toggled.connect(self.refresh)
        self._on_base()

    def base(self):
        return self.base_combo.currentText().strip()

    def _split(self):
        """Ce qui est tapé dans « Mot » : « HF » ou « HF 5 » (le numéro tapé devient le point de départ)."""
        b = self.base()
        return parse_label(b) if b else ("", " ", None, 0)

    def word(self):
        return self._split()[0]

    def _on_base(self, *_):
        b, _sep, n0, _wd = self._split()
        if n0 is not None:
            self.auto_chk.setEnabled(False)
            self.start_spin.setEnabled(False)
            self.start_spin.setValue(n0)
        else:
            self.auto_chk.setEnabled(True)
            self.start_spin.setEnabled(not self.auto_chk.isChecked())
            if self.auto_chk.isChecked() and b:
                self.start_spin.setValue(next_free_number(b, self._others))
        self.refresh()

    def names(self):
        base, n = self.base(), len(self.rows)
        if not base:
            return None
        if self.mode_combo.currentData() == "same":
            return [base] * n
        b, sep0, n0, wd0 = self._split()
        if n0 is not None:
            base, start, wd, sep = b, n0, (wd0 or self.width_spin.value()), sep0
        else:
            start, wd, sep = self.start_spin.value(), self.width_spin.value(), self.sep_combo.currentData()
        labs = [make_label(base, start + i, wd, sep) for i in range(n)]
        if self.rev_chk.isChecked():
            labs.reverse()
        return labs

    def refresh(self, *_):
        new = self.names()
        ok = new is not None
        self.bb.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(ok)
        shown = list(range(len(self.rows)))
        if len(shown) > 14:
            shown = shown[:7] + shown[-7:]
        self.prev.setRowCount(len(shown))
        for r, k in enumerate(shown):
            w = self.owner.watch[self.rows[k]]
            self.prev.setItem(r, 0, QtWidgets.QTableWidgetItem(f'{w["freq"]:.3f}'))
            self.prev.setItem(r, 1, QtWidgets.QTableWidgetItem(w["name"]))
            self.prev.setItem(r, 2, QtWidgets.QTableWidgetItem(new[k] if ok else ""))


# --------------------------------------------------------------------------
# Dialogue : intermodulation (2 / 3 / 5 TX) et origine d'un signal
# --------------------------------------------------------------------------
class IntermodDialog(QtWidgets.QDialog):
    def __init__(self, owner, origin=None):
        super().__init__(owner)
        self.owner = owner
        self.rows = []
        self.setWindowTitle("Intermodulation : d'où ça peut venir ?")
        self.resize(1040, 720)
        R = owner._row
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Calcule les produits d'intermodulation de tes émetteurs (les fréquences de la liste) : 2 TX → 2A − B ; "
            "3 TX → A + B − C ; 5 TX → A + B + C − D − E… Tu vois quelle combinaison peut retomber sur une de tes "
            "fréquences, ou expliquer un signal inconnu vu sur le spectre. C'est un calcul théorique : il ne dit "
            "pas quel appareil (émetteur, ampli d'antenne, combiner…) le fabrique vraiment.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Calculer les produits : qui tombe sur quoi ?", "calc")
        self.mode_combo.addItem("Chercher l'origine d'un signal à…", "origin")
        self.freq_spin = QtWidgets.QDoubleSpinBox()
        self.freq_spin.setDecimals(3)
        self.freq_spin.setRange(0.1, 6000.0)
        self.freq_spin.setValue(origin if origin else 500.0)
        self.freq_spin.setSuffix(" MHz")
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Émetteurs : toute la liste", "all")
        self.src_combo.addItem("Émetteurs : la couche active", "scope")
        self.src_combo.addItem("Émetteurs : les lignes sélectionnées", "sel")
        self.active_chk = QtWidgets.QCheckBox("Seulement ceux qui émettent (vus sur le spectre)")
        self.active_chk.setToolTip("Un produit n'existe que si les émetteurs sont allumés : on ne garde que ceux "
                                   "dont l'état est « occupé » ou « faible ».")
        self.src_lbl = QtWidgets.QLabel("")
        self.maxtx_combo = QtWidgets.QComboBox()
        self.maxtx_combo.addItem("2 TX  (2A − B)", 2)
        self.maxtx_combo.addItem("jusqu'à 3 TX  (2A − B, A + B − C)", 3)
        self.maxtx_combo.addItem("jusqu'à 5 TX  (… A + B + C − D − E)", 5)
        self.maxtx_combo.setCurrentIndex(1)
        self.o3_chk = QtWidgets.QCheckBox("3ᵉ ordre")
        self.o3_chk.setChecked(True)
        self.o5_chk = QtWidgets.QCheckBox("5ᵉ ordre")
        self.o7_chk = QtWidgets.QCheckBox("7ᵉ ordre")
        self.tgt_combo = QtWidgets.QComboBox()
        self.tgt_combo.addItem("Protéger : toutes les fréquences de la liste", "all")
        self.tgt_combo.addItem("Protéger : la couche active seulement", "scope")
        self.tgt_combo.addItem("Aucune cible : lister tous les produits dans la plage", "none")
        self.guard_spin = QtWidgets.QDoubleSpinBox()
        self.guard_spin.setDecimals(3)
        self.guard_spin.setRange(0.005, 5.0)
        self.guard_spin.setSingleStep(0.05)
        self.guard_spin.setValue(0.30)
        self.guard_spin.setPrefix("± ")
        self.guard_spin.setSuffix(" MHz")
        self.guard_spin.setToolTip("Écart sous lequel un produit est considéré comme gênant.\n"
                                   "300 kHz = écart par défaut d'EazyRF · 350 kHz = minimum de WWB (mode Standard).")
        bands = [b for b in owner.bands if b["enabled"]]
        self.fmin_spin = QtWidgets.QDoubleSpinBox()
        self.fmax_spin = QtWidgets.QDoubleSpinBox()
        for sp in (self.fmin_spin, self.fmax_spin):
            sp.setDecimals(3)
            sp.setRange(0.1, 6000.0)
            sp.setSuffix(" MHz")
        self.fmin_spin.setValue(min((b["start"] for b in bands), default=470.0))
        self.fmax_spin.setValue(max((b["stop"] for b in bands), default=694.0))
        self.go_btn = QtWidgets.QPushButton("⚡ Calculer")
        self.go_btn.clicked.connect(lambda *_: self.compute())
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addLayout(R("Mode :", self.mode_combo, self.freq_spin, None))
        lay.addLayout(R(self.src_combo, self.active_chk, self.src_lbl, None))
        lay.addLayout(R("Combinaisons :", self.maxtx_combo, self.o3_chk, self.o5_chk, self.o7_chk, None))
        lay.addLayout(R(self.tgt_combo, "Marge :", self.guard_spin, None))
        lay.addLayout(R("Plage (liste complète) :", self.fmin_spin, "à", self.fmax_spin, None, self.go_btn))
        lay.addWidget(self.msg)
        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Produit MHz", "Ordre", "Origine (émetteurs)", "Tombe sur", "Écart kHz",
                                              "Mesuré dBm", "Verdict"])
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for c, w in ((0, 96), (1, 52), (3, 190), (4, 76), (5, 88), (6, 190)):
            self.table.setColumnWidth(c, w)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_zoom())
        lay.addWidget(self.table, 1)
        b_zoom = QtWidgets.QPushButton("🔍 Voir le produit sur le spectre")
        b_zoom.clicked.connect(lambda *_: self.on_zoom())
        b_watch = QtWidgets.QPushButton("👁 Surveiller les produits sélectionnés")
        b_watch.setToolTip("Ajoute les lignes sélectionnées à ta liste (scène « Intermod »), statut « Libre » :\n"
                           "si de l'énergie apparaît dessus, ça déclenche ⚠ CONFLIT.")
        b_watch.clicked.connect(lambda *_: self.on_watch())
        b_csv = QtWidgets.QPushButton("💾 Exporter CSV…")
        b_csv.clicked.connect(lambda *_: self.on_csv())
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        lay.addLayout(R(b_zoom, b_watch, b_csv, None, b_close))
        for w in (self.src_combo,):
            w.currentIndexChanged.connect(self.update_src)
        self.active_chk.toggled.connect(self.update_src)
        self.mode_combo.currentIndexChanged.connect(self.on_mode)
        if origin:
            self.mode_combo.setCurrentIndex(1)
        else:
            self.on_mode()
        self.update_src()

    def on_mode(self, *_):
        origin = self.mode_combo.currentData() == "origin"
        self.freq_spin.setEnabled(origin)
        self.tgt_combo.setEnabled(not origin)
        if origin:
            self.o5_chk.setChecked(True)
            self.maxtx_combo.setCurrentIndex(2)
            n_act = sum(1 for w in self.owner.watch if w["state"] in ("occ", "weak"))
            self.active_chk.setChecked(n_act >= 2)

    def source_indices(self):
        o = self.owner
        kind = self.src_combo.currentData()
        if kind == "sel":
            idx = o._sel_rows()
        elif kind == "scope":
            idx = [i for i, w in enumerate(o.watch) if o.in_scope(w)]
        else:
            idx = list(range(len(o.watch)))
        if self.active_chk.isChecked():
            idx = [i for i in idx if o.watch[i]["state"] in ("occ", "weak")]
        return idx

    def update_src(self, *_):
        self.src_lbl.setText(f"→ {len(self.source_indices())} émetteur(s)")

    def orders(self):
        out = tuple(x for x, c in ((3, self.o3_chk), (5, self.o5_chk), (7, self.o7_chk)) if c.isChecked())
        return out or (3,)

    def compute(self):
        o = self.owner
        idx = self.source_indices()
        freqs = [o.watch[i]["freq"] for i in idx]
        names = [o.watch[i]["name"] for i in idx]
        orders, max_tx, guard = self.orders(), self.maxtx_combo.currentData(), self.guard_spin.value()
        if len(freqs) < 2:
            self.msg.setText("Il faut au moins 2 émetteurs (change la source ou décoche « seulement ceux qui émettent »).")
            return
        pairs = sum(im_pairs(len(freqs), x, max_tx) for x in orders)
        if pairs > IM_MAX_PAIRS:
            self.msg.setText((f"Trop de combinaisons ({pairs:,}) pour {len(freqs)} émetteurs. Essaie : « 2 TX » (rapide "
                              f"même avec des centaines de fréquences), « seulement ceux qui émettent », une couche plus "
                              f"petite, ou retire les ordres 5 / 7 qui sont les plus gourmands.").replace(",", " "))
            return
        origin = self.mode_combo.currentData() == "origin"
        if origin:
            targets, fmin, fmax = [self.freq_spin.value()], 0.1, 6000.0
        else:
            tm = self.tgt_combo.currentData()
            fmin, fmax = self.fmin_spin.value(), self.fmax_spin.value()
            if tm == "all":
                targets, fmin, fmax = [w["freq"] for w in o.watch], 0.1, 6000.0
            elif tm == "scope":
                targets, fmin, fmax = [w["freq"] for w in o.scope_ws()], 0.1, 6000.0
            else:
                targets = None
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            rows, info = im_scan(freqs, orders, max_tx, targets, guard, fmin, fmax, limit=5000)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        F, L = o.fresh_FL()
        win = max(0.05, o.win_spin.value() / 1000.0)
        thr, weak = o.thr_spin.value(), o.weak_spin.value()
        by_freq = {int(round(w["freq"] * 1000)): w["name"] for w in o.watch}
        for r in rows:
            r["text"] = im_formula(r["terms"], names)
            r["numtext"] = im_formula(r["terms"], freqs=freqs, numeric=True)
            r["meas"] = level_at(F, L, r["f"], win) if F is not None else None
            if r["target"] is None:
                r["tname"] = ""
            elif origin:
                r["tname"] = f"signal à {r['target']:.3f}"
            else:
                r["tname"] = f"{by_freq.get(int(round(r['target'] * 1000)), '?')} ({r['target']:.3f})"
            if r["meas"] is not None and r["meas"] >= thr:
                r["verdict"], r["level"] = "⚠ visible sur le spectre", 2
            elif r["meas"] is not None and o.weak_chk.isChecked() and r["meas"] >= weak:
                r["verdict"], r["level"] = "énergie faible mesurée", 1
            elif r["target"] is not None and not origin:
                r["verdict"], r["level"] = "à risque (calcul)", 1
            elif origin:
                r["verdict"], r["level"] = "origine possible", 1
            else:
                r["verdict"], r["level"] = "", 0
        self.rows = rows
        self.cur_freqs, self.cur_names = freqs, names
        self.fill()
        txt = f"{len(rows)} produit(s)" + (" (liste tronquée)" if info["truncated"] else "")
        txt += f" · {len(freqs)} émetteur(s) · ordres {', '.join(str(x) for x in orders)} · {info['pairs']:,} combinaisons examinées".replace(",", " ")
        n_vis = sum(1 for r in rows if r["level"] == 2)
        if n_vis:
            txt += f"\n⚠ {n_vis} produit(s) retombent sur un niveau mesuré au-dessus du seuil : à regarder en priorité."
        elif not origin and targets is not None and not rows:
            txt += "\n✔ Aucun produit ne tombe à moins de la marge d'une de tes fréquences (pour ces combinaisons)."
        elif origin and not rows:
            txt += "\nAucune combinaison de ces émetteurs n'explique ce signal : il vient peut-être d'ailleurs " \
                   "(émetteur absent de la liste, intermod dans un ampli, source extérieure…)."
        self.msg.setText(txt)

    def fill(self):
        t, th = self.table, self.owner.theme
        t.setRowCount(len(self.rows))
        base = th["ui_base"]
        for r, row in enumerate(self.rows):
            vals = (f"{row['f']:.3f}", IM_NAMES.get(row["order"], str(row["order"])), row["text"], row["tname"],
                    "" if row["delta"] is None else f"{row['delta'] * 1000:+.0f}",
                    "—" if row["meas"] is None else f"{row['meas']:.1f}", row["verdict"])
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (0, 4, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 2:
                    it.setToolTip(row["numtext"])
                if row["level"] == 2:
                    bg = blend(th["st_occ"], base, 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif row["level"] == 1 and c == 6:
                    bg = blend(th["st_weak"], base, 0.5)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                t.setItem(r, c, it)

    def selected(self):
        rs = sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.rows)})
        return [self.rows[r] for r in rs]

    def on_zoom(self):
        sel = self.selected()
        if sel:
            f = sel[0]["f"]
            self.owner.view_range(f - 1.0, f + 1.0, f"Produit {IM_NAMES.get(sel[0]['order'], '')} à {f:.3f} MHz")

    def on_watch(self):
        sel = self.selected()
        if not sel:
            self.msg.setText("Sélectionne d'abord des lignes (Ctrl+A pour tout prendre).")
            return
        n = self.owner.add_im_watches([(r["f"], f"{IM_NAMES.get(r['order'], 'IM')} {r['text']}") for r in sel])
        self.msg.setText(f"{n} fréquence(s) ajoutée(s) à la scène « Intermod » (statut Libre)." if n else
                         "Ces fréquences sont déjà dans ta liste.")

    def on_csv(self):
        if not self.rows:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter les produits", "intermod.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                wr = csv.writer(fh, delimiter=";")
                wr.writerow(["Produit MHz", "Ordre", "Origine", "Origine (MHz)", "Tombe sur", "Écart kHz", "Mesuré dBm",
                             "Verdict"])
                for r in self.rows:
                    wr.writerow([fmt_comma(r["f"]), r["order"], r["text"], r["numtext"].replace(".", ","), r["tname"],
                                 "" if r["delta"] is None else fmt_comma(r["delta"] * 1000, 0),
                                 "" if r["meas"] is None else fmt_comma(r["meas"], 1), r["verdict"]])
            self.msg.setText(f"Exporté : {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")


# --------------------------------------------------------------------------
# Dialogue : fréquence de secours
# --------------------------------------------------------------------------
class RescueDialog(QtWidgets.QDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.found = []
        self.setWindowTitle("Fréquence de secours")
        self.resize(900, 640)
        R = owner._row
        lay = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel(
            "Cherche des fréquences libres d'après ce que le tinySA a mesuré (max hold), à bonne distance de tes "
            "émetteurs et sans intermodulation de 3ᵉ ordre avec eux. Aide de dépannage : ça ne remplace pas ta "
            "coordination (EazyRF / WWB…). Vérifie que la fréquence est autorisée et compatible avec ton matériel "
            "avant de l'utiliser. Scanne bien la zone un moment avant de chercher.")
        info.setWordWrap(True)
        lay.addWidget(info)
        vr = owner.spec.getPlotItem().vb.viewRange()[0]
        a0, b0 = (vr[0], vr[1]) if 0.1 <= vr[0] < vr[1] <= 6000 and (vr[1] - vr[0]) <= 400 else (470.0, 694.0)
        self.a_spin, self.b_spin = QtWidgets.QDoubleSpinBox(), QtWidgets.QDoubleSpinBox()
        for sp in (self.a_spin, self.b_spin):
            sp.setDecimals(3)
            sp.setRange(0.1, 6000.0)
            sp.setSuffix(" MHz")
        self.a_spin.setValue(round(a0, 3))
        self.b_spin.setValue(round(b0, 3))
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(1, 30)
        self.n_spin.setValue(3)
        self.width_spin = QtWidgets.QDoubleSpinBox()
        self.width_spin.setDecimals(3)
        self.width_spin.setRange(0.025, 2.0)
        self.width_spin.setValue(0.2)
        self.width_spin.setSuffix(" MHz")
        self.width_spin.setToolTip("Largeur à garder libre autour de la fréquence (canal du micro / de l'IEM).")
        self.sep_spin = QtWidgets.QDoubleSpinBox()
        self.sep_spin.setDecimals(3)
        self.sep_spin.setRange(0.0, 5.0)
        self.sep_spin.setSingleStep(0.05)
        self.sep_spin.setValue(0.30)
        self.sep_spin.setSuffix(" MHz")
        self.sep_spin.setToolTip("Écart minimal avec tes autres fréquences (300 kHz EazyRF · 350 kHz WWB).")
        self.guard_spin = QtWidgets.QDoubleSpinBox()
        self.guard_spin.setDecimals(3)
        self.guard_spin.setRange(0.005, 5.0)
        self.guard_spin.setSingleStep(0.05)
        self.guard_spin.setValue(0.30)
        self.guard_spin.setPrefix("± ")
        self.guard_spin.setSuffix(" MHz")
        self.guard_spin.setToolTip("Marge d'intermodulation 3ᵉ ordre avec tes fréquences.")
        self.thr_spin = QtWidgets.QDoubleSpinBox()
        self.thr_spin.setRange(-130, 0)
        self.thr_spin.setValue(owner.weak_spin.value() if owner.weak_chk.isChecked() else owner.thr_spin.value() - 10)
        self.thr_spin.setSuffix(" dBm")
        self.thr_spin.setToolTip("Niveau maximum mesuré toléré sur le canal (max hold).")
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Éviter : toute la liste", "all")
        self.src_combo.addItem("Éviter : la couche active seulement", "scope")
        self.go_btn = QtWidgets.QPushButton("🔎 Chercher")
        self.go_btn.clicked.connect(lambda *_: self.search())
        lay.addLayout(R("De", self.a_spin, "à", self.b_spin, "Nombre :", self.n_spin, None))
        lay.addLayout(R("Canal :", self.width_spin, "Écart mini :", self.sep_spin, "Intermod :", self.guard_spin, None))
        lay.addLayout(R("Niveau max toléré :", self.thr_spin, self.src_combo, None, self.go_btn))
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fréquence MHz", "Niveau max dBm", "Voisine la plus proche", "Écart kHz",
                                              "Spectre"])
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        for c, w in ((0, 110), (1, 110), (2, 200), (3, 76)):
            self.table.setColumnWidth(c, w)
        self.table.cellDoubleClicked.connect(lambda r, c: self.on_view())
        lay.addWidget(self.table, 1)
        self.layer_combo = QtWidgets.QComboBox()
        self.layer_combo.addItem("Ajouter dans : (sans scène)", ("", ""))
        for sc in owner.scenes:
            for g in sc["groups"]:
                self.layer_combo.addItem(f"Ajouter dans : {sc['name']} › {g['name']}", (sc["name"], g["name"]))
        self.layer_combo.addItem("Ajouter dans : Secours › Fréquences de secours (nouveau)", ("Secours", "Fréquences de secours"))
        self.layer_combo.setCurrentIndex(self.layer_combo.count() - 1)
        b_view = QtWidgets.QPushButton("🔍 Voir")
        b_view.clicked.connect(lambda *_: self.on_view())
        b_add = QtWidgets.QPushButton("＋ Ajouter la sélection à ma liste")
        b_add.clicked.connect(lambda *_: self.on_add())
        b_close = QtWidgets.QPushButton("Fermer")
        b_close.clicked.connect(self.close)
        lay.addLayout(R(self.layer_combo, b_view, b_add, None, b_close))

    def search(self):
        o = self.owner
        F, L = o.fresh_FL(use_max=True, any_age=True)
        if F is None:
            self.msg.setText("Aucune mesure : lance un balayage (▶ Démarrer) sur cette zone, laisse tourner un moment, "
                             "puis relance la recherche.")
            return
        a, b = self.a_spin.value(), self.b_spin.value()
        if b <= a:
            self.msg.setText("La plage est à l'envers.")
            return
        if self.src_combo.currentData() == "scope":
            ex = [w["freq"] for w in o.scope_ws()]
        else:
            ex = [w["freq"] for w in o.watch]
        res, d = find_free(F, L, a, b, ex, self.n_spin.value(), self.width_spin.value(), self.sep_spin.value(),
                           self.thr_spin.value(), self.guard_spin.value())
        self.found = res
        exa = sorted(w["freq"] for w in o.watch)
        t = self.table
        t.setRowCount(len(res))
        for r, x in enumerate(res):
            near = min(o.watch, key=lambda w: abs(w["freq"] - x["f"]), default=None)
            nn = "—" if near is None else f'{near["name"]} ({near["freq"]:.3f})'
            dk = "" if near is None else f'{abs(near["freq"] - x["f"]) * 1000:.0f}'
            vals = (f'{x["f"]:.3f}', f'{x["level"]:.1f}', nn, dk, spectrum_info(x["f"], o.plan, o.tv)[0] or "—")
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (0, 1, 3):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                t.setItem(r, c, it)
        cover = f"{F.min():.1f}–{F.max():.1f} MHz"
        txt = (f"{len(res)} fréquence(s) trouvée(s) sur {self.n_spin.value()} demandée(s). "
               f"Grille : {d['grille']} points · trop bruyants : {d['bruyantes']} · hors mesure : {d['sans_mesure']} · "
               f"trop proches : {d['trop_proches']} · rejetés pour intermod : {d['intermod']}. Mesures disponibles : {cover}.")
        if len(res) < self.n_spin.value():
            txt += "\nPas assez de place avec ces réglages : élargis la plage, baisse l'écart ou la marge, ou accepte un niveau plus haut."
        self.msg.setText(txt)

    def _sel(self):
        rs = sorted({i.row() for i in self.table.selectedIndexes() if i.row() < len(self.found)})
        return [self.found[r] for r in rs]

    def on_view(self):
        s = self._sel()
        if s:
            self.owner.view_range(s[0]["f"] - 1.0, s[0]["f"] + 1.0, f"Fréquence candidate {s[0]['f']:.3f} MHz")

    def on_add(self):
        s = self._sel() or self.found
        if not s:
            return
        sc, gr = self.layer_combo.currentData()
        n = self.owner.add_free_freqs([x["f"] for x in s], sc, gr)
        self.msg.setText(f"{n} fréquence(s) ajoutée(s) à ta liste.")


# --------------------------------------------------------------------------
# Enregistrement disque des balayages + relecture
# --------------------------------------------------------------------------
REC_SESSION_MB = 2000          # taille maximale d'un enregistrement (les plus anciennes tranches sont supprimées)


class SweepRecorder:
    """Enregistre les balayages sur disque : une tranche .npz compressée toutes les ~30 s
    (niveaux en float16 : précision de 0,06 dB)."""

    def __init__(self, folder, flush_s=30.0, max_mb=REC_SESSION_MB):
        self.folder = Path(folder)
        self.flush_s, self.max_bytes = float(flush_s), int(max_mb * 1e6)
        self.pending, self.n_chunk, self.n_sweeps, self.error = [], 0, 0, ""
        self.t_flush = time.time()

    def add(self, bid, t, f, l):
        if not self.error:
            self.pending.append((int(bid), float(t), np.asarray(f, dtype=np.float64), np.asarray(l, dtype=np.float16)))

    def maybe_flush(self, now):
        if self.pending and now - self.t_flush >= self.flush_s:
            self.flush(now)

    def flush(self, now=None):
        if not self.pending or self.error:
            return
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            segs, cur = [], None
            for bid, t, f, l in self.pending:
                key = (bid, len(f), float(f[0]), float(f[-1]))
                if cur is None or cur[0] != key:
                    cur = [key, [], f, []]
                    segs.append(cur)
                cur[1].append(t)
                cur[3].append(l)
            arrs = {"n": np.array(len(segs))}
            for i, (key, ts, f, ls) in enumerate(segs):
                arrs[f"b{i}"] = np.array(key[0])
                arrs[f"t{i}"] = np.array(ts, dtype=np.float64)
                arrs[f"f{i}"] = f
                arrs[f"l{i}"] = np.stack(ls)
            self.n_chunk += 1
            path = self.folder / f"chunk_{self.n_chunk:06d}.npz"
            part = self.folder / f"chunk_{self.n_chunk:06d}.part"
            with open(part, "wb") as fh:
                np.savez_compressed(fh, **arrs)
            os.replace(part, path)
            self.n_sweeps += len(self.pending)
            self.pending = []
            self.t_flush = now if now is not None else time.time()
            self._trim()
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    def _trim(self):
        files = sorted(self.folder.glob("chunk_*.npz"))
        sizes = [p.stat().st_size for p in files]
        total = sum(sizes)
        for p, s in zip(files[:-1], sizes[:-1]):
            if total <= self.max_bytes:
                break
            try:
                p.unlink()
                total -= s
            except OSError:
                break

    def close(self):
        self.flush()


def load_recording(folder, store):
    """Relit un dossier d'enregistrement dans un SweepStore. -> (nombre de balayages, nombre de tranches)."""
    files = sorted(Path(folder).glob("chunk_*.npz"))
    n = 0
    for p in files:
        try:
            with np.load(p) as z:
                for i in range(int(z["n"])):
                    bid, ts, f, ls = int(z[f"b{i}"]), z[f"t{i}"], z[f"f{i}"], z[f"l{i}"]
                    for t, l in zip(ts, ls):
                        store.add(bid, float(t), f, l.astype(np.float32))
                        n += 1
        except Exception:  # noqa: BLE001
            continue
    return n, len(files)


class ReplayDialog(QtWidgets.QDialog):
    """Revoir le spectre à un instant passé : curseur de temps, lecture accélérée, qui était allumé à ce moment-là."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.store = owner.store
        self.times = np.array([])
        self.idx = 0
        self.speed = 1
        self.setWindowTitle("Relecture : revoir le spectre")
        self.resize(1320, 780)
        th = owner.theme
        lay = QtWidgets.QVBoxLayout(self)
        self.src_lbl = QtWidgets.QLabel("")
        b_open = QtWidgets.QPushButton("📂 Ouvrir un enregistrement…")
        b_open.setToolTip("Relit un dossier créé par « 💾 Enregistrer les balayages » (un dossier par session).")
        b_open.clicked.connect(lambda *_: self.open_rec())
        b_mem = QtWidgets.QPushButton("↩ Mémoire en cours")
        b_mem.setToolTip("Les 30 dernières minutes gardées en mémoire par le logiciel.")
        b_mem.clicked.connect(lambda *_: self.use_memory())
        self.ev_combo = QtWidgets.QComboBox()
        self.ev_combo.setMinimumWidth(380)
        self.ev_combo.currentIndexChanged.connect(self.on_event_pick)
        lay.addLayout(owner._row(self.src_lbl, None, "Aller à :", self.ev_combo, b_open, b_mem))
        self.plot = pg.PlotWidget()
        pi = self.plot.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "Fréquence", units="MHz")
        pi.setLabel("left", "Niveau", units="dBm")
        pi.setYRange(-120, -10, padding=0)
        pi.getAxis("bottom").enableAutoSIPrefix(False)
        self.maxcurve = pi.plot(pen=pg.mkPen(th["maxhold"], width=1), connect="finite")
        self.curve = pi.plot(pen=pg.mkPen(th["curve"], width=1.6), connect="finite")
        self.thr_line = pg.InfiniteLine(pos=owner.thr_spin.value(), angle=0,
                                        pen=pg.mkPen(th["thr"], width=1.3, style=Qt.PenStyle.DashLine))
        pi.addItem(self.thr_line)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nom", "MHz", "Niveau", "Max", "À ce moment"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setMinimumWidth(430)
        self.table.setMaximumWidth(520)
        mid = QtWidgets.QHBoxLayout()
        mid.addWidget(self.plot, 1)
        mid.addWidget(self.table)
        lay.addLayout(mid, 1)
        self.slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self.seek)
        self.time_lbl = QtWidgets.QLabel("")
        self.time_lbl.setMinimumWidth(260)
        self.play_btn = QtWidgets.QPushButton("▶ Lecture")
        self.play_btn.clicked.connect(lambda *_: self.toggle_play())
        b_prev = QtWidgets.QPushButton("◀")
        b_prev.setToolTip("Balayage précédent")
        b_prev.clicked.connect(lambda *_: self.step(-1))
        b_next = QtWidgets.QPushButton("▶")
        b_next.setToolTip("Balayage suivant")
        b_next.clicked.connect(lambda *_: self.step(1))
        self.speed_combo = QtWidgets.QComboBox()
        for lab, v in (("×1", 1), ("×4", 4), ("×16", 16), ("×64", 64)):
            self.speed_combo.addItem(lab, v)
        self.speed_combo.currentIndexChanged.connect(self._on_speed)
        self.mh_chk = QtWidgets.QCheckBox("Max hold depuis le début")
        self.mh_chk.setChecked(True)
        self.mh_chk.toggled.connect(lambda *_: self.seek(self.idx))
        lay.addWidget(self.slider)
        lay.addLayout(owner._row(b_prev, self.play_btn, b_next, self.speed_combo, self.mh_chk, None, self.time_lbl))
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self._tick)
        self._fit = True
        self.reload()

    # ------------------------------------------------------------- source
    def reload(self):
        self.times = self.store.times()
        n = len(self.times)
        self.slider.setRange(0, max(0, n - 1))
        sp = self.store.span()
        if n == 0:
            self.src_lbl.setText("Aucun balayage en mémoire : lance un balayage (▶ Démarrer) ou ouvre un enregistrement.")
            self.curve.setData([], [])
            self.maxcurve.setData([], [])
            self.table.setRowCount(0)
            self.time_lbl.setText("—")
            return
        self.src_lbl.setText(f"{n} instants · {fmt_clock(sp[0])} → {fmt_clock(sp[1])} ({fmt_dur(sp[1] - sp[0])})")
        self.fill_events()
        self._fit = True
        self.slider.setValue(n - 1)
        self.seek(n - 1)

    def use_memory(self):
        self.store = self.owner.store
        self.reload()

    def open_rec(self):
        start = self.owner.log_dir / "enregistrements"
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier d'un enregistrement", str(start))
        if not d:
            return
        st = SweepStore(seconds=1e12, max_mb=2500)
        n, nf = load_recording(d, st)
        if n == 0:
            self.msg.setText(f"Aucun balayage lisible dans « {d} » ({nf} fichier(s) trouvé(s)).")
            return
        self.store = st
        self.msg.setText(f"Enregistrement chargé : {n} balayages ({nf} tranche(s)).")
        self.reload()

    def fill_events(self):
        """Événements du journal qui tombent dans la période relue (le journal ne garde que l'heure du jour)."""
        self.ev_combo.blockSignals(True)
        self.ev_combo.clear()
        self.ev_combo.addItem("— événement du journal —", None)
        sp = self.store.span()
        t = self.owner.log_table
        day = datetime.fromtimestamp(sp[0]).replace(hour=0, minute=0, second=0, microsecond=0)
        for r in range(t.rowCount() - 1, -1, -1):
            try:
                hh, mm, ss = (int(x) for x in t.item(r, 0).text().split(":"))
            except Exception:  # noqa: BLE001
                continue
            ep = day.replace(hour=hh, minute=mm, second=ss).timestamp()
            if ep < sp[0] - 60:
                ep += 86400.0
            if sp[0] - 60 <= ep <= sp[1] + 60:
                self.ev_combo.addItem(f'{t.item(r, 0).text()}  {t.item(r, 4).text()}  {t.item(r, 1).text()}  '
                                      f'{t.item(r, 2).text()} MHz', ep)
        self.ev_combo.blockSignals(False)

    def on_event_pick(self, *_):
        ep = self.ev_combo.currentData()
        if ep is not None and len(self.times):
            i = int(np.searchsorted(self.times, ep - 1.0))
            i = min(max(i, 0), len(self.times) - 1)
            self.slider.setValue(i)
            self.seek(i)

    # ------------------------------------------------------------- lecture
    def _on_speed(self, *_):
        self.speed = int(self.speed_combo.currentData() or 1)

    def toggle_play(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("▶ Lecture")
        else:
            if len(self.times) and self.idx >= len(self.times) - 1:
                self.slider.setValue(0)
                self.seek(0)
            self.timer.start()
            self.play_btn.setText("⏸ Pause")

    def _tick(self):
        if self.idx >= len(self.times) - 1:
            self.timer.stop()
            self.play_btn.setText("▶ Lecture")
            return
        i = min(len(self.times) - 1, self.idx + self.speed)
        self.slider.setValue(i)
        self.seek(i)

    def step(self, d):
        if len(self.times):
            i = min(max(self.idx + d, 0), len(self.times) - 1)
            self.slider.setValue(i)
            self.seek(i)

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)

    # ------------------------------------------------------------- affichage
    def seek(self, i):
        i = int(i)
        if not len(self.times):
            return
        i = min(max(i, 0), len(self.times) - 1)
        self.idx = i
        o = self.owner
        t = float(self.times[i])
        t0 = float(self.times[0])
        F, L = self.store.snapshot(t)
        if F is None:
            return
        self.curve.setData(F, L)
        if self.mh_chk.isChecked():
            Fm, Lm = self.store.maxhold(t0, t)
        else:
            Fm, Lm = None, None
        if Fm is not None:
            self.maxcurve.setData(Fm, Lm)
        else:
            self.maxcurve.setData([], [])
        if self._fit:
            self._fit = False
            self.plot.getPlotItem().setXRange(float(F[0]), float(F[-1]), padding=0.01)
        self.time_lbl.setText(f"{fmt_clock(t)}   ({fmt_dur(t - float(self.times[-1]), signed=True)} · "
                              f"{i + 1}/{len(self.times)})")
        win = max(0.05, o.win_spin.value() / 1000.0)
        gthr, gweak, weak_on = o.thr_spin.value(), o.weak_spin.value(), o.weak_chk.isChecked()
        rows = []
        for w in o.watch:
            if not o.in_scope(w):
                continue
            lv = level_at(F, L, w["freq"], win)
            mx = level_at(Fm, Lm, w["freq"], win) if Fm is not None else None
            thr = w["thr"] if w["thr"] is not None else gthr
            if lv is None:
                st = "—"
            elif lv >= thr:
                st = "OCCUPÉ"
            elif weak_on and lv >= (thr - (gthr - gweak)):
                st = "faible"
            else:
                st = "libre"
            rows.append((lv if lv is not None else -999.0, w["name"], w["freq"], lv, mx, st))
        rows.sort(key=lambda r: -r[0])
        rows = rows[:300]
        th = o.theme
        base = th["ui_base"]
        self.table.setRowCount(len(rows))
        for r, (_k, nm, fr, lv, mx, st) in enumerate(rows):
            vals = (nm, f"{fr:.3f}", "—" if lv is None else f"{lv:.1f}", "—" if mx is None else f"{mx:.1f}", st)
            for c, v in enumerate(vals):
                it = QtWidgets.QTableWidgetItem(v)
                if c in (1, 2, 3):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if st == "OCCUPÉ":
                    bg = blend(th["st_occ"], base, 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif st == "faible" and c == 4:
                    bg = blend(th["st_weak"], base, 0.5)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                self.table.setItem(r, c, it)


def fmt_clock(t):
    return datetime.fromtimestamp(float(t)).strftime("%H:%M:%S")


def fmt_dur(s, signed=False):
    s = float(s)
    sign = "-" if (signed and s < -0.5) else ""
    s = int(round(abs(s)))
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    txt = f"{h} h {m:02d} min {sec:02d} s" if h else (f"{m} min {sec:02d} s" if m else f"{sec} s")
    return sign + txt


# --------------------------------------------------------------------------
# Dialogue : rapport de fin de show
# --------------------------------------------------------------------------
class ReportDialog(QtWidgets.QDialog):
    def __init__(self, owner, prefs, has_im):
        super().__init__(owner)
        self.setWindowTitle("Rapport de show")
        self.resize(520, 420)
        p = prefs or {}
        lay = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Crée une page HTML autonome : événements, conflits, émetteurs absents, occupation par scène et groupe, "
            "spectre max hold, intermodulation. Ouvre-la dans le navigateur puis « Imprimer › Enregistrer en PDF ».")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        form = QtWidgets.QFormLayout()
        self.title = QtWidgets.QLineEdit(p.get("title") or f"Rapport de show — {datetime.now():%d/%m/%Y}")
        self.venue = QtWidgets.QLineEdit(p.get("venue", ""))
        self.venue.setPlaceholderText("Festival, lieu, scène…")
        self.operator = QtWidgets.QLineEdit(p.get("operator", ""))
        self.operator.setPlaceholderText("Ton nom / ta société")
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlainText(p.get("notes", ""))
        self.notes.setPlaceholderText("Remarques : matériel, météo, incidents, fréquences changées…")
        self.im_chk = QtWidgets.QCheckBox("Inclure le dernier calcul d'intermodulation")
        self.im_chk.setChecked(has_im)
        self.im_chk.setEnabled(has_im)
        self.open_chk = QtWidgets.QCheckBox("Ouvrir dans le navigateur après l'enregistrement")
        self.open_chk.setChecked(True)
        form.addRow("Titre :", self.title)
        form.addRow("Lieu :", self.venue)
        form.addRow("Par :", self.operator)
        form.addRow("Notes :", self.notes)
        form.addRow(self.im_chk)
        form.addRow(self.open_chk)
        lay.addLayout(form)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def values(self):
        return dict(title=self.title.text().strip(), venue=self.venue.text().strip(),
                    operator=self.operator.text().strip(), notes=self.notes.toPlainText().strip(),
                    im=self.im_chk.isChecked(), open=self.open_chk.isChecked())


# --------------------------------------------------------------------------
# Dialogue : export des fréquences par scène / groupe
# --------------------------------------------------------------------------
class ExportListDialog(QtWidgets.QDialog):
    def __init__(self, owner, n_all, n_scope, n_sel, prefs):
        super().__init__(owner)
        self.setWindowTitle("Exporter les fréquences")
        self.resize(560, 300)
        p = prefs or {}
        form = QtWidgets.QFormLayout(self)
        self.src = QtWidgets.QComboBox()
        self.src.addItem(f"Toute la liste ({n_all})", "all")
        self.src.addItem(f"La couche active ({n_scope})", "scope")
        self.src.addItem(f"Les lignes sélectionnées ({n_sel})", "sel")
        self.split = QtWidgets.QComboBox()
        self.split.addItem("Un seul fichier", "all")
        self.split.addItem("Un fichier par scène", "scene")
        self.split.addItem("Un fichier par groupe", "group")
        self.fmt = QtWidgets.QComboBox()
        for lab, v in FREQ_FORMATS:
            self.fmt.addItem(lab, v)
        for combo, key in ((self.src, "src"), (self.split, "split"), (self.fmt, "fmt")):
            i = combo.findData(p.get(key))
            if i >= 0:
                combo.setCurrentIndex(i)
        form.addRow("Quoi :", self.src)
        form.addRow("Découpage :", self.split)
        form.addRow("Format :", self.fmt)
        note = QtWidgets.QLabel("Les fichiers sont créés dans un nouveau dossier daté. Le format « Complet » se "
                                "réimporte tel quel (📥 Importer CSV). Pour un format précis d'EazyRF / WWB / WSM, "
                                "envoie-moi un exemple d'import de ton logiciel et j'ajoute l'option.")
        note.setWordWrap(True)
        form.addRow(note)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def values(self):
        return dict(src=self.src.currentData(), split=self.split.currentData(), fmt=self.fmt.currentData())


# --------------------------------------------------------------------------
# Fenêtre : mur de fréquences (tuiles, pour un 2e écran)
# --------------------------------------------------------------------------
class WallWindow(QtWidgets.QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setWindowTitle(f"{APP_NAME} – Mur de fréquences")
        self.resize(1100, 680)
        self.tiles, self._sig, self._vis, self._fs = [], [], None, 0
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        top = QtWidgets.QHBoxLayout()
        self.only_chk = QtWidgets.QCheckBox("Occupées / faibles seulement")
        self.only_chk.toggled.connect(self.relayout)
        self.sum_lbl = QtWidgets.QLabel("")
        self.full_btn = QtWidgets.QPushButton("⛶ Plein écran (F11)")
        self.full_btn.clicked.connect(self.toggle_full)
        top.addWidget(self.only_chk)
        top.addWidget(self.sum_lbl, 1)
        top.addWidget(self.full_btn)
        lay.addLayout(top)
        self.host = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(6)
        lay.addWidget(self.host, 1)
        sc = QtGui.QShortcut(QtGui.QKeySequence("F11"), self)
        sc.activated.connect(self.toggle_full)
        sc2 = QtGui.QShortcut(QtGui.QKeySequence("Escape"), self)
        sc2.activated.connect(self.leave_full)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.relayout)

    def toggle_full(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def leave_full(self):
        if self.isFullScreen():
            self.showNormal()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._timer.start()

    def showEvent(self, e):
        super().showEvent(e)
        self.rebuild()

    def rebuild(self):
        for t in self.tiles:
            self.grid.removeWidget(t)
            t.deleteLater()
        self.tiles = []
        for _ in self.owner.watch:
            lb = QtWidgets.QLabel("")
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setWordWrap(True)
            lb.setTextFormat(Qt.TextFormat.RichText)
            lb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
            self.tiles.append(lb)
        self._sig = [None] * len(self.tiles)
        self._vis = None
        self.relayout()
        self.refresh()

    def _visible_idx(self):
        ow = self.owner
        ws = ow.watch
        idx = [i for i, w in enumerate(ws) if ow.in_scope(w)]
        if self.only_chk.isChecked():
            idx = [i for i in idx if ws[i]["state"] in ("occ", "weak")]
        return idx

    def relayout(self, *_):
        if len(self.tiles) != len(self.owner.watch):
            self.rebuild()
            return
        vis = self._visible_idx()
        self._vis = tuple(vis)
        for t in self.tiles:
            self.grid.removeWidget(t)
            t.setVisible(False)
        n = len(vis)
        W, H = max(200, self.host.width()), max(120, self.host.height())
        if n:
            cols = max(1, min(n, int(math.ceil(math.sqrt(n * W / H / 1.5)))))
            rows = int(math.ceil(n / cols))
            for k in range(self.grid.columnCount() + 1):
                self.grid.setColumnStretch(k, 0)
            for k in range(self.grid.rowCount() + 1):
                self.grid.setRowStretch(k, 0)
            for c in range(cols):
                self.grid.setColumnStretch(c, 1)
            for r in range(rows):
                self.grid.setRowStretch(r, 1)
            for k, i in enumerate(vis):
                self.grid.addWidget(self.tiles[i], k // cols, k % cols)
                self.tiles[i].setVisible(True)
            tw, th = W / cols, H / rows
            fs = int(max(8, min(44, th * 0.22, tw / 7.5)))
        else:
            fs = 14
        if fs != self._fs:
            self._fs = fs
            self._sig = [None] * len(self.tiles)
        self.refresh()

    def refresh(self):
        if not self.isVisible():
            return
        ow = self.owner
        if len(self.tiles) != len(ow.watch):
            self.rebuild()
            return
        if self._vis != tuple(self._visible_idx()):
            self.relayout()
            return
        th, base, fs = ow.theme, ow.theme["ui_base"], self._fs
        n_occ = n_weak = n_tot = 0
        one_group = bool(ow.scope and len(ow.scope) == 1 and ow.scope[0][1])
        for i, w in enumerate(ow.watch):
            if not ow.in_scope(w):
                continue
            n_tot += 1
            st = w["state"]
            n_occ += st == "occ"
            n_weak += st == "weak"
            conf = st == "occ" and ow.is_keep_free(w["status"])
            absn = bool(w.get("absent"))
            lv = "—" if w["level"] is None else f'{w["level"]:.1f} dBm'
            pct = w["occw"].pct()
            layer = "" if one_group else ow.layer_text(w)
            sig = (st, conf, absn, lv, w["name"], w["status"], round(w["freq"], 3), fs, layer,
                   None if pct is None else int(pct), th["ui_base"], th["st_occ"], th["st_free"], th["st_weak"])
            if self._sig[i] == sig:
                continue
            self._sig[i] = sig
            if absn:
                bg = blend(th["st_unk"], base, 0.9)
            elif st == "occ":
                bg = blend(th["st_occ"], base, 0.85)
            elif st == "weak":
                bg = blend(th["st_weak"], base, 0.6)
            elif st == "free":
                bg = blend(th["st_free"], base, 0.30)
            else:
                bg = blend(th["st_none"], base, 0.25)
            fg = contrast_text(bg)
            bd = ow.status_color(w["status"]) if w["status"] else bg
            name = ("⚠ " if (conf or absn) else "") + (w["name"] or "—")
            occ = "" if pct is None else f" · occ. {pct:.0f} %"
            html = (f"<div style='font-size:{fs}px;font-weight:bold'>{_html_esc(name)}</div>"
                    f"<div style='font-size:{max(8, int(fs * 0.72))}px'>{w['freq']:.3f} MHz</div>"
                    f"<div style='font-size:{int(fs * 0.95)}px'>{'ABSENT · ' if absn else ''}{lv}{occ}</div>")
            if layer:
                html += f"<div style='font-size:{max(8, int(fs * 0.6))}px'>{_html_esc(layer)}</div>"
            self.tiles[i].setText(html)
            self.tiles[i].setStyleSheet(
                "QLabel{background:%s;color:%s;border:4px solid %s;border-radius:8px;}" % (bg, fg, bd))
        self.sum_lbl.setText(f"  {ow.scope_text()} · {n_tot} fréquences · {n_occ} occupée(s) · {n_weak} faible(s)")


def _html_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


C_NAME, C_FREQ, C_LVL, C_MAX, C_THR, C_SIG, C_STAT, C_OCC, C_LAYER, C_BAND = range(10)
WATCH_HEADERS = ["Nom", "MHz", "Niveau", "Max", "Seuil", "Signal", "Statut", "Occ.", "Scène › Groupe",
                 "Spectre"]
SIG_TEXT = {None: "—", "free": "libre", "weak": "faible", "occ": "OCCUPÉ"}
CONFLICT_TEXT = "⚠ CONFLIT"
ABSENT_TEXT = "⚠ ABSENT"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VER}")
        self.resize(1700, 980)
        self._fit_to_screen()
        self.setAcceptDrops(True)
        self.lock = threading.Lock()
        self._next_id = 1
        self._ver = 0
        self.bands, self.watch = [], []
        self.scenes = []                # [{name, color, groups:[{name, color}]}]
        self.scope = None               # None = global ; sinon [(scène, groupe|None), …]
        self._focus_bands, self._focus_sig = [], []
        self._tree_items, self._tree_sig, self._tree_lock = {}, {}, False
        self._guide = None
        self._im_dlg = self._rescue_dlg = self._replay = None
        self.alarms = AlarmBook()
        self.store = SweepStore(1800.0, 300.0)
        self.recorder = None
        self._t_start = None
        self.report_prefs, self.export_list_prefs = {}, {}
        self.vocab_user = dict(name=[], scene=[], group=[])
        self.docks, self._state_restored = [], False
        self.statuses = [dict(name=n, color=c, free=(n == "Libre"), on=(n == "En service")) for n, c in DEFAULT_STATUSES]
        self.theme = dict(THEMES["Sombre"])
        self.country, self.plan_custom = "FR", {}
        self.plan, self.tv = [], []
        self._strip_rects, self._strip_labels = [], []
        self._strip_rows = []
        self.ref_curves = []            # courbe de référence : liste de (freq, niveau)
        self._ref_F = self._ref_L = None
        self.wall = None
        self._log_err_shown = False
        self.log_dir = LOG_DIR
        self.export_prefs = {}
        self.latest, self.latest_t, self.maxhold, self.partial_data = {}, {}, {}, {}
        self.history = {}          # anciens balayages complets par bande (rémanence)
        self._hist_items = []
        self.unk_now, self.unk_seen = {}, {}
        self.worker = None
        self.view_id = -1
        self.wf_hist, self.wf_id = None, None
        self._fit_x = True
        self._updating = False
        self._last_xy = None
        self.last_cycle = 10.0
        self.labels = []
        self._mk_items = {}
        self._zoom = None
        self._zoom_view = None
        self._cfg = dict(rbw=100, zrbw=None, input="auto", lna=None, att="auto", offset=0.0,
                         seg=None, points=1000)
        self._build_ui()
        self._load_config()
        self._load_ref_file(REF_PATH, silent=True)
        self.refresh_ports()
        self._sync_cfg()
        self.rebuild_plan()
        self.apply_theme()
        self.rebuild_band_table()
        self.refresh_view_combo()
        self.rebuild_watch_table()
        self.set_status("Prêt. Ferme tinySA-App, choisis le port puis ▶ Démarrer (ou essaie le mode démo).")
        self._alarm_timer = QtCore.QTimer(self)
        self._alarm_timer.setInterval(1000)
        self._alarm_timer.timeout.connect(self._alarm_tick)
        self._alarm_timer.start()
        QtCore.QTimer.singleShot(0, self._late_layout)

    def _fit_to_screen(self):
        """Petit écran (portable 1366×768…) : la fenêtre ne doit pas déborder."""
        scr = QtGui.QGuiApplication.primaryScreen()
        if scr is None:
            return
        g = scr.availableGeometry()
        if g.width() > 0 and g.height() > 0:
            self.resize(min(self.width(), g.width()), min(self.height(), g.height()))

    def _late_layout(self):
        if not self._state_restored:
            self._dock_sizes()
            if self.view_id == -1:
                self.dock_wf.hide()      # pas de waterfall en vue « tout le spectre » : le spectre prend la place

    # ---------------------------------------------------------------- UI
    @staticmethod
    def _item(text, editable=False, right=False):
        it = QtWidgets.QTableWidgetItem(text)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        it.setFlags(flags)
        if right:
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return it

    @staticmethod
    def _row(*ws):
        h = QtWidgets.QHBoxLayout()
        for w in ws:
            if isinstance(w, str):
                h.addWidget(QtWidgets.QLabel(w))
            elif w is None:
                h.addStretch(1)
            else:
                h.addWidget(w)
        return h

    @staticmethod
    def _elastic(lab):
        """Texte qui change en direct (compteurs, état) : coupé si trop long, n'élargit jamais la fenêtre."""
        lab.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, lab.sizePolicy().verticalPolicy())
        lab.setMinimumWidth(40)
        return lab

    @staticmethod
    def _flow(*groups):
        """Barre qui se replie : chaque groupe (widget, texte ou tuple) reste d'un seul tenant."""
        fl = FlowLayout()
        for g in groups:
            if not isinstance(g, tuple):
                g = (g,)
            if len(g) == 1 and not isinstance(g[0], str):
                fl.addWidget(g[0])
                continue
            box = QtWidgets.QWidget()
            h = QtWidgets.QHBoxLayout(box)
            h.setContentsMargins(0, 0, 0, 0)
            for w in g:
                h.addWidget(QtWidgets.QLabel(w) if isinstance(w, str) else w)
            fl.addWidget(box)
        return fl

    @staticmethod
    def _combo(items, current=None):
        c = QtWidgets.QComboBox()
        for txt, data in items:
            c.addItem(txt, data)
        if current is not None:
            c.setCurrentIndex(max(0, c.findData(current)))
        return c

    def _build_ui(self):
        pg.setConfigOptions(antialias=True, background=self.theme["plot_bg"],
                            foreground=self.theme["plot_fg"])
        # --- barre du haut
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(220)
        btn_ports = QtWidgets.QToolButton()
        btn_ports.setText("⟳")
        btn_ports.setToolTip("Rafraîchir les ports")
        btn_ports.clicked.connect(self.refresh_ports)
        self.demo_chk = QtWidgets.QCheckBox("Mode démo")
        self.demo_chk.setToolTip("Signaux simulés, sans appareil branché")
        self.info_lbl = QtWidgets.QLabel("")
        colors_btn = QtWidgets.QPushButton("🎨 Couleurs")
        colors_btn.clicked.connect(self.edit_colors)
        status_btn = QtWidgets.QPushButton("🏷 Statuts")
        status_btn.clicked.connect(self.edit_statuses)
        self.start_btn = QtWidgets.QPushButton("▶ Démarrer")
        self.start_btn.clicked.connect(self.toggle_run)
        wall_btn = QtWidgets.QPushButton("🧱 Mur")
        wall_btn.setToolTip("Ouvre une fenêtre de grandes tuiles (une par fréquence), à mettre sur un 2e écran.\n"
                            "F11 : plein écran.")
        wall_btn.clicked.connect(self.open_wall)
        prof_btn = QtWidgets.QPushButton("📁 Profils")
        prof_btn.setToolTip("Enregistre / recharge tout le réglage d'un événement\n"
                            "(bandes, fréquences, statuts, seuils, couleurs, pays…).")
        pmenu = QtWidgets.QMenu(prof_btn)
        for txt, fn in (("Enregistrer le profil de l'événement…", self.save_profile),
                        ("Charger un profil…", self.load_profile),
                        (None, None),
                        ("Ouvrir le dossier des profils", self.open_profile_dir)):
            if txt is None:
                pmenu.addSeparator()
            else:
                pmenu.addAction(txt).triggered.connect(fn)
        prof_btn.setMenu(pmenu)
        tools_btn = QtWidgets.QPushButton("🔧 Outils")
        tools_btn.setToolTip("Intermodulation, fréquence de secours, relecture, rapport, scans WSM/WWB, export par scène, "
                             "nommage rapide, vocabulaire.")
        tmenu = QtWidgets.QMenu(tools_btn)
        for txt, fn in (("⚡ Intermodulation (2 / 3 / 5 TX)…", lambda *_: self.open_intermod()),
                        ("🆘 Fréquence de secours…", lambda *_: self.open_rescue()),
                        (None, None),
                        ("⏪ Relecture : revoir le spectre…", lambda *_: self.open_replay()),
                        ("📄 Rapport de show…", lambda *_: self.make_report()),
                        ("📤 Exporter les fréquences (par scène / groupe)…", lambda *_: self.export_by_scene()),
                        (None, None),
                        ("📏 Importer un scan WSM / WWB comme référence…", lambda *_: self.import_scan_as_ref()),
                        ("🔁 Convertir un scan WSM → WWB…", lambda *_: self.convert_wsm_wwb()),
                        ("💾 Exporter le scan au format WWB…", lambda *_: self.export_scan_wwb()),
                        (None, None),
                        ("✏ Nommer la sélection (HF 1, HF 2…)…", lambda *_: self.quick_name_dialog()),
                        ("⇣ Numéroter vers le bas depuis la 1ʳᵉ ligne  (Ctrl+D)", lambda *_: self.fill_down_names()),
                        ("Mon vocabulaire…", lambda *_: self.edit_vocab())):
            if txt is None:
                tmenu.addSeparator()
            else:
                tmenu.addAction(txt).triggered.connect(fn)
        tools_btn.setMenu(tmenu)
        win_btn = QtWidgets.QPushButton("🪟 Fenêtres")
        win_btn.setToolTip("Affiche / cache / détache les panneaux, dispositions prêtes à l'emploi (double écran…).\n"
                           "Tu peux aussi attraper un panneau par sa barre de titre et le poser où tu veux.")
        self.win_menu = QtWidgets.QMenu(win_btn)
        win_btn.setMenu(self.win_menu)
        self.alarm_btn = QtWidgets.QPushButton("🔔")
        self.alarm_btn.setToolTip("Alarmes : conflits (signal sur une fréquence « doit rester libre ») et émetteurs "
                                  "absents (« doit émettre »).\nRouge = à acquitter · orange = acquittées, toujours là.")
        self.alarm_btn.clicked.connect(lambda *_: self.toggle_alarm_dock())
        top = self._flow(("Port :", self.port_combo, btn_ports), (self.demo_chk, self.info_lbl),
                         self.alarm_btn, tools_btn, win_btn, wall_btn, prof_btn, colors_btn, status_btn, self.start_btn)

        # --- panneau de gauche : réglages
        self.points_combo = self._combo([(f"{p:,}".replace(",", " "), p) for p in POINTS_CHOICES], 1000)
        self.points_combo.setToolTip("Nombre de points par balayage et par bande (appliqué à toutes les bandes).\n"
                                     "Plus il y en a, plus c'est précis… et plus c'est long.")
        self.points_combo.activated.connect(self.apply_points)
        self.rbw_combo = self._combo([("Auto", None)] + [(f"{v:g} kHz", v) for v in RBW_LIST], 100)
        self.zrbw_combo = self._combo([("Auto (selon zoom)", None)] + [(f"{v:g} kHz", v) for v in RBW_LIST])
        self.input_combo = self._combo([("Auto", "auto"), ("Basse (≤ 800 MHz)", "low"),
                                        ("Haute (> 800 MHz)", "high")])
        self.lna_combo = self._combo([("Inchangé", None), ("ON", True), ("OFF", False)])
        self.lna_combo.setToolTip("LNA interne du tinySA Ultra (désactive l'atténuateur quand il est ON)")
        self.att_combo = self._combo([("Auto", "auto")] + [(f"{n} dB", n) for n in (0, 5, 10, 15, 20, 25, 30)])
        self.offset_spin = QtWidgets.QDoubleSpinBox()
        self.offset_spin.setRange(-60, 60)
        self.offset_spin.setSingleStep(0.5)
        self.offset_spin.setSuffix(" dB")
        self.offset_spin.setToolTip("Ajouté à toutes les mesures (gain d'antenne, perte de câble, ampli externe…)")
        self.seg_combo = self._combo([("Auto (selon le modèle)", None), ("145 pts", 145), ("290 pts", 290),
                                      ("450 pts", 450)])
        self.seg_combo.setToolTip("Nombre max de points demandés au tinySA par commande.\n"
                                  "Les balayages plus longs sont découpés en segments.\n"
                                  "Auto = 450 sur tinySA Ultra, 290 sinon.")
        self.est_lbl = QtWidgets.QLabel("")
        self.est_lbl.setWordWrap(True)
        for c in (self.rbw_combo, self.zrbw_combo, self.input_combo, self.lna_combo, self.att_combo,
                  self.seg_combo):
            c.currentIndexChanged.connect(self._sync_cfg)
        self.offset_spin.valueChanged.connect(self._sync_cfg)

        mbox, mform = QtWidgets.QGroupBox("Mesure"), None
        mform = QtWidgets.QFormLayout(mbox)
        mform.addRow("Points / balayage :", self.points_combo)
        mform.addRow("RBW :", self.rbw_combo)
        mform.addRow("RBW en zoom :", self.zrbw_combo)
        mform.addRow("Entrée :", self.input_combo)
        mform.addRow("LNA :", self.lna_combo)
        mform.addRow("Atténuateur :", self.att_combo)
        mform.addRow("Offset :", self.offset_spin)
        mform.addRow("Segment :", self.seg_combo)
        mform.addRow(self.est_lbl)

        self.thr_spin = QtWidgets.QDoubleSpinBox()
        self.thr_spin.setRange(-130, 0)
        self.thr_spin.setValue(-80)
        self.thr_spin.setSuffix(" dBm")
        self.thr_spin.valueChanged.connect(self._thr_from_spin)
        auto_btn = QtWidgets.QPushButton("Auto")
        auto_btn.setToolTip("Seuil = niveau médian mesuré + 10 dB")
        auto_btn.clicked.connect(self.auto_threshold)
        self.weak_chk = QtWidgets.QCheckBox("Niveau « faible » à partir de")
        self.weak_chk.setChecked(True)
        self.weak_spin = QtWidgets.QDoubleSpinBox()
        self.weak_spin.setRange(-130, 0)
        self.weak_spin.setValue(-90)
        self.weak_spin.setSuffix(" dBm")
        self.weak_spin.valueChanged.connect(self._weak_from_spin)
        self.weak_chk.toggled.connect(self._weak_toggled)
        self.win_spin = QtWidgets.QSpinBox()
        self.win_spin.setRange(10, 2000)
        self.win_spin.setSingleStep(10)
        self.win_spin.setValue(100)
        self.win_spin.setPrefix("± ")
        self.win_spin.setSuffix(" kHz")
        self.win_spin.setToolTip("Fenêtre autour de chaque fréquence (on prend le max)")
        self.alert_chk = QtWidgets.QCheckBox("Alerte sonore")
        self.alert_chk.setChecked(True)
        self.unk_chk = QtWidgets.QCheckBox("Détecter les signaux inconnus")
        self.unk_chk.setToolTip("Signale tout pic au-dessus du seuil qui n'est pas dans ta liste")
        self.unk_chk.setChecked(True)
        self.occ_combo = self._combo([("10 minutes", 10), ("1 heure", 60), ("4 heures", 240), ("12 heures", 720)], 60)
        self.occ_combo.setToolTip("Durée sur laquelle est calculé le taux d'occupation (colonne « Occ. »)")
        self.occ_combo.currentIndexChanged.connect(self.on_occ_window)
        self.ref_chk = QtWidgets.QCheckBox("Seuil = courbe de référence +")
        self.ref_chk.setToolTip("Chaque fréquence est « occupée » quand elle dépasse la référence de cette marge.\n"
                                "Capture d'abord une référence (bouton 📏 Référence) quand le spectre est calme.\n"
                                "Un seuil propre à une fréquence reste prioritaire.")
        self.ref_margin = QtWidgets.QDoubleSpinBox()
        self.ref_margin.setRange(1, 60)
        self.ref_margin.setValue(8)
        self.ref_margin.setPrefix("+ ")
        self.ref_margin.setSuffix(" dB")
        self.ref_chk.toggled.connect(self.reeval)
        self.ref_margin.valueChanged.connect(self.reeval)
        self.absent_spin = QtWidgets.QSpinBox()
        self.absent_spin.setRange(3, 3600)
        self.absent_spin.setValue(20)
        self.absent_spin.setSuffix(" s")
        self.absent_spin.setToolTip("Une fréquence au statut « Doit émettre » sans signal pendant ce délai déclenche\n"
                                    "⚠ ABSENT (micro éteint, pile vide, TX coupé…). Jamais moins de 2 cycles de balayage.")
        dbox = QtWidgets.QGroupBox("Détection")
        dform = QtWidgets.QFormLayout(dbox)
        dform.addRow("Seuil « occupé » :", self._row(self.thr_spin, auto_btn))
        dform.addRow(self.weak_chk)
        dform.addRow("", self.weak_spin)
        dform.addRow(self.ref_chk)
        dform.addRow("", self.ref_margin)
        dform.addRow("Fenêtre :", self.win_spin)
        dform.addRow("Occupation sur :", self.occ_combo)
        dform.addRow("TX absent après :", self.absent_spin)
        dform.addRow(self.alert_chk)
        dform.addRow(self.unk_chk)

        self.country_combo = self._combo([(name, code) for code, name in COUNTRIES], "FR")
        self.country_combo.currentIndexChanged.connect(self.on_country)
        self.alloc_chk = QtWidgets.QCheckBox("Attributions (4G/5G, TNT, militaire…)")
        self.alloc_chk.setChecked(True)
        self.tv_chk = QtWidgets.QCheckBox("Canaux TV")
        self.tv_chk.setChecked(True)
        self.alloc_chk.toggled.connect(self.update_strips)
        self.tv_chk.toggled.connect(self.update_strips)
        plan_btn = QtWidgets.QPushButton("Éditer le plan…")
        plan_btn.setToolTip("Corrige ou complète les attributions de ce pays (elles sont indicatives).")
        plan_btn.clicked.connect(self.edit_plan)
        guide_btn = QtWidgets.QPushButton("📖 Guide des bandes…")
        guide_btn.setToolTip("À quoi correspond chaque bande entre 100 kHz et 5,9 GHz ? Police, pompiers, aéro,\n"
                             "marine, 4G/5G, CB, PMR, amateur, satellites, radars… avec recherche, zoom\n"
                             "et ajout aux bandes à balayer.")
        guide_btn.clicked.connect(self.open_guide)
        self.country_note = QtWidgets.QLabel("")
        self.country_note.setWordWrap(True)
        self.legend_lbl = QtWidgets.QLabel("")
        self.legend_lbl.setWordWrap(True)
        self.legend_lbl.setTextFormat(Qt.TextFormat.RichText)
        pbox = QtWidgets.QGroupBox("Pays et plan de fréquences")
        pform = QtWidgets.QFormLayout(pbox)
        pform.addRow("Pays :", self.country_combo)
        pform.addRow(self.alloc_chk)
        pform.addRow(self.tv_chk)
        pform.addRow(guide_btn)
        pform.addRow(plan_btn)
        pform.addRow(self.country_note)
        pform.addRow(self.legend_lbl)

        bbox = QtWidgets.QGroupBox("Bandes à balayer")
        bl = QtWidgets.QVBoxLayout(bbox)
        self.band_table = QtWidgets.QTableWidget(0, 5)
        self.band_table.setHorizontalHeaderLabels(["Bande", "Début MHz", "Fin MHz", "Points", "Pas kHz"])
        self.band_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.band_table.verticalHeader().setVisible(False)
        self.band_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.band_table.setMinimumHeight(150)
        self.band_table.itemChanged.connect(self.on_band_edit)
        bl.addWidget(self.band_table)
        b_add = QtWidgets.QPushButton("＋ Bande")
        b_add.clicked.connect(lambda: self.add_band("Nouvelle bande", 470.0, 608.0, 200.0))
        b_del = QtWidgets.QPushButton("Supprimer")
        b_del.clicked.connect(self.del_band)
        bl.addLayout(self._row(b_add, b_del))
        self.preset_combo = QtWidgets.QComboBox()
        self.preset_combo.addItem("➕ Ajouter un préréglage…")
        for p in BAND_PRESETS:
            self.preset_combo.addItem(p[0], p)
        self.preset_combo.activated.connect(self.on_preset)
        bl.addWidget(self.preset_combo)

        lcont = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(lcont)
        lv.setContentsMargins(6, 4, 6, 4)
        lv.addWidget(mbox)
        lv.addWidget(dbox)
        lv.addWidget(pbox)
        lv.addWidget(bbox, 1)
        left = QtWidgets.QScrollArea()
        left.setWidgetResizable(True)
        left.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        left.setWidget(lcont)

        # --- centre : graphiques
        self.view_combo = QtWidgets.QComboBox()
        self.view_combo.setMinimumWidth(170)
        self.view_combo.currentIndexChanged.connect(self.on_view_changed)
        self.zoom_btn = QtWidgets.QPushButton("🔍 Zoom live")
        self.zoom_btn.setCheckable(True)
        self.zoom_btn.setToolTip("Le tinySA ne scanne plus que la zone visible, avec le nombre de points choisi.\n"
                                 "Zoome / déplace-toi sur le graphique : le scan suit.")
        self.zoom_btn.toggled.connect(self.toggle_zoom)
        self.names_chk = QtWidgets.QCheckBox("Noms")
        self.names_chk.setChecked(True)
        self.names_chk.toggled.connect(lambda *_: self._update_markers())
        self.hold_chk = QtWidgets.QCheckBox("Max hold")
        self.hold_chk.setChecked(True)
        self.mark_combo = self._combo([("Repères : état du signal", "signal"), ("Repères : statut manuel", "status"),
                                       ("Repères : couleur du groupe", "group")])
        self.mark_combo.currentIndexChanged.connect(lambda *_: self._update_markers())
        self.persist_combo = self._combo([("Rémanence : aucune", 0), ("Rémanence : 3 balayages", 3),
                                          ("Rémanence : 5 balayages", 5), ("Rémanence : 10 balayages", 10),
                                          ("Rémanence : 20 balayages", 20)])
        self.persist_combo.setToolTip("Garde à l'écran les anciens balayages, de plus en plus transparents.")
        self.persist_combo.currentIndexChanged.connect(lambda *_: self.update_plot())
        reset_btn = QtWidgets.QPushButton("Reset max")
        reset_btn.clicked.connect(self.reset_max)
        cap_btn = QtWidgets.QPushButton("📷 Capture")
        cap_btn.clicked.connect(self.capture)
        ref_btn = QtWidgets.QPushButton("📏 Référence")
        ref_btn.setToolTip("Courbe de référence (spectre calme / bruit de fond du lieu), affichée en pointillés.")
        rmenu = QtWidgets.QMenu(ref_btn)
        for txt, fn in (("Capturer : balayage actuel", lambda: self.capture_ref("live")),
                        ("Capturer : max hold", lambda: self.capture_ref("max")),
                        (None, None),
                        ("Enregistrer sous…", self.save_ref_as),
                        ("Charger…", self.load_ref_dialog),
                        ("Importer un scan WSM / WWB…", self.import_scan_as_ref),
                        (None, None),
                        ("Effacer la référence", self.clear_ref)):
            if txt is None:
                rmenu.addSeparator()
            else:
                rmenu.addAction(txt).triggered.connect(fn)
        ref_btn.setMenu(rmenu)
        self.showref_chk = QtWidgets.QCheckBox("Afficher")
        self.showref_chk.setChecked(True)
        self.showref_chk.toggled.connect(lambda *_: self.update_ref_curve())
        exp_btn = QtWidgets.QPushButton("💾 Exporter le scan…")
        exp_btn.clicked.connect(self.export_scan)
        self.band_lbl = QtWidgets.QLabel("Survole le spectre ou les bandeaux pour voir le canal TV et "
                                         "l'attribution de la fréquence.")
        self.band_lbl.setWordWrap(True)
        self.band_lbl.setMinimumHeight(36)
        self.readout = QtWidgets.QLabel("")
        self.readout.setMinimumWidth(210)
        self.readout.setStyleSheet("font-family:Consolas,monospace;")

        self.spec = pg.PlotWidget()
        pi = self.spec.getPlotItem()
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "Fréquence", units="MHz")
        pi.setLabel("left", "Niveau", units="dBm")
        pi.setYRange(-120, -10, padding=0)
        pi.getAxis("left").setWidth(65)
        pi.getAxis("bottom").enableAutoSIPrefix(False)
        pi.getAxis("left").enableAutoSIPrefix(False)
        self.refcurve = pi.plot(pen=pg.mkPen(self.theme["ref"], width=1.3, style=Qt.PenStyle.DashLine),
                                connect="finite")
        self.maxcurve = pi.plot(pen=pg.mkPen(self.theme["maxhold"], width=1), connect="finite")
        self.curve = pi.plot(pen=pg.mkPen(self.theme["curve"], width=1.6), connect="finite")
        self.thr_line = pg.InfiniteLine(pos=-80, angle=0, movable=True,
                                        pen=pg.mkPen(self.theme["thr"], width=1.5, style=Qt.PenStyle.DashLine))
        self.thr_line.sigPositionChanged.connect(self._thr_from_line)
        self.weak_line = pg.InfiniteLine(pos=-90, angle=0, movable=True,
                                         pen=pg.mkPen(self.theme["thr_weak"], width=1.2, style=Qt.PenStyle.DotLine))
        self.weak_line.sigPositionChanged.connect(self._weak_from_line)
        pi.addItem(self.thr_line)
        pi.addItem(self.weak_line)
        self.proxy = pg.SignalProxy(self.spec.scene().sigMouseMoved, rateLimit=30, slot=self.on_mouse)
        self._ovl_timer = QtCore.QTimer(self)
        self._ovl_timer.setSingleShot(True)
        self._ovl_timer.setInterval(40)
        self._ovl_timer.timeout.connect(self._update_markers)
        self._ovl_timer.timeout.connect(self.update_strip_labels)
        pi.vb.sigXRangeChanged.connect(lambda *a: self._ovl_timer.start())
        self.zoom_timer = QtCore.QTimer(self)
        self.zoom_timer.setInterval(500)
        self.zoom_timer.timeout.connect(self.zoom_follow)

        self.wf = pg.PlotWidget()
        wi = self.wf.getPlotItem()
        wi.invertY(True)
        wi.setMouseEnabled(x=True, y=False)
        wi.setXLink(pi)
        wi.getAxis("left").setWidth(65)
        wi.setLabel("left", "temps")
        wi.getAxis("bottom").enableAutoSIPrefix(False)
        self.wf_img = pg.ImageItem()
        wi.addItem(self.wf_img)
        self.wf.setVisible(False)

        # bandeaux : attributions du spectre + canaux TV (alignés sur l'axe des fréquences)
        self.bandw = pg.PlotWidget()
        bi = self.bandw.getPlotItem()
        bi.hideButtons()
        bi.setMenuEnabled(False)
        bi.vb.setMenuEnabled(False)
        bi.setMouseEnabled(x=True, y=False)
        bi.setXLink(pi)
        bi.hideAxis("bottom")
        bi.getAxis("left").setWidth(65)
        bi.getAxis("left").setStyle(showValues=False, tickLength=0)
        bi.setYRange(0, 2, padding=0)
        self.bandw.setFixedHeight(62)
        bi.vb.sigResized.connect(lambda *a: self._ovl_timer.start())
        self.bandw_proxy = pg.SignalProxy(self.bandw.scene().sigMouseMoved, rateLimit=30, slot=self.on_mouse_band)

        self.wf_hint = QtWidgets.QLabel("Choisis une bande dans « Vue » (ou active le zoom live) "
                                        "pour voir le waterfall.")
        self.wf_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wf_hint.setWordWrap(True)
        self.wf_box = QtWidgets.QWidget()
        wfl = QtWidgets.QVBoxLayout(self.wf_box)
        wfl.setContentsMargins(0, 0, 0, 0)
        wfl.addWidget(self.wf_hint)
        wfl.addWidget(self.wf, 1)
        center = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(center)
        cl.setContentsMargins(6, 4, 6, 0)
        cl.addLayout(self._flow(("Vue :", self.view_combo), self.zoom_btn, self.names_chk, self.hold_chk,
                                self.persist_combo, self.mark_combo, reset_btn, cap_btn, self.readout))
        cl.addLayout(self._row("Référence :", ref_btn, self.showref_chk, exp_btn, None))
        cl.addWidget(self.band_lbl)
        cl.addWidget(self.spec, 1)
        cl.addWidget(self.bandw)

        # --- droite : fréquences + journal
        ftab = QtWidgets.QWidget()
        fl = QtWidgets.QVBoxLayout(ftab)
        self.layer_lbl = QtWidgets.QLabel("")
        self.layer_lbl.setWordWrap(True)
        self.global_btn = QtWidgets.QPushButton("🌐 Global")
        self.global_btn.setToolTip("Surveille toutes les fréquences, toutes scènes confondues.")
        self.global_btn.clicked.connect(lambda *_: self.go_global())
        lb_sc = QtWidgets.QPushButton("＋ Scène")
        lb_sc.clicked.connect(lambda *_: self.add_scene())
        lb_gr = QtWidgets.QPushButton("＋ Groupe")
        lb_gr.clicked.connect(lambda *_: self.add_group())
        lb_rn = QtWidgets.QPushButton("✎")
        lb_rn.setToolTip("Renommer la scène / le groupe sélectionné")
        lb_rn.clicked.connect(lambda *_: self.layer_action("rename"))
        lb_dl = QtWidgets.QPushButton("🗑")
        lb_dl.setToolTip("Supprimer la scène / le groupe sélectionné (les fréquences restent dans la liste)")
        lb_dl.clicked.connect(lambda *_: self.layer_action("delete"))
        for b in (lb_rn, lb_dl):
            b.setMaximumWidth(38)
        self.layer_tree = QtWidgets.QTreeWidget()
        self.layer_tree.setHeaderHidden(True)
        self.layer_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.layer_tree.setMinimumHeight(60)
        self.layer_tree.itemSelectionChanged.connect(self.on_tree_sel)
        self.layer_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.layer_tree.customContextMenuRequested.connect(self.layer_menu)
        self.focus_chk = QtWidgets.QCheckBox("🎯 Scanner seulement la sélection")
        self.focus_chk.setToolTip("Le tinySA ne balaye plus que les petites zones autour des fréquences de la couche\n"
                                  "active (au lieu de toutes tes bandes) : cycles beaucoup plus rapides, donc\n"
                                  "détection plus réactive. Inactif en mode Global.")
        self.focus_chk.toggled.connect(self._on_focus_toggled)
        lbox = QtWidgets.QGroupBox("Couches de monitoring : scènes › groupes")
        lv2 = QtWidgets.QVBoxLayout(lbox)
        lv2.setContentsMargins(6, 4, 6, 4)
        lv2.addLayout(self._row(self.global_btn, lb_sc, lb_gr, lb_rn, lb_dl, None))
        lv2.addWidget(self.layer_tree)
        lv2.addWidget(self.focus_chk)
        lv2.addWidget(self.layer_lbl)
        layer_tip = QtWidgets.QLabel("Clic sur un groupe = on ne surveille que lui · Ctrl+clic = plusieurs · "
                                     "🌐 Global = tout. Clic droit : importer un CSV dans le groupe, renommer, "
                                     "couleur. Clic droit sur une fréquence ou double-clic sur « Scène › Groupe » "
                                     "pour l'affecter.")
        layer_tip.setToolTip(layer_tip.text())
        layer_tip.setText("ⓘ Clic = surveiller ce groupe · Ctrl+clic = plusieurs · clic droit = menu (survole pour l'aide)")
        layer_tip.setWordWrap(True)
        lv2.addWidget(layer_tip)
        # un QSplitter ignore la hauteur réelle des textes repliés : on la réserve (sinon chevauchements)
        lh = self.fontMetrics().lineSpacing()
        for lab, n in ((self.layer_lbl, 1), (layer_tip, 2)):
            lab.setMinimumHeight(lh * n + 4)
        # couches et table dans un séparateur : la table garde la place, la poignée se tire à la souris
        wbox = QtWidgets.QWidget()
        outer = fl
        fl = QtWidgets.QVBoxLayout(wbox)
        fl.setContentsMargins(0, 0, 0, 0)
        self.freq_split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.freq_split.setObjectName("freq_split")
        self.freq_split.setChildrenCollapsible(False)
        self.freq_split.addWidget(lbox)
        self.freq_split.addWidget(wbox)
        self.freq_split.setStretchFactor(0, 0)
        self.freq_split.setStretchFactor(1, 1)
        self.freq_split.setSizes([230, 600])
        outer.addWidget(self.freq_split, 1)
        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("🔎 Rechercher un nom, une fréquence, un statut…")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self.apply_filter)
        self.occ_only_chk = QtWidgets.QCheckBox("Occupées seulement")
        self.occ_only_chk.toggled.connect(self.apply_filter)
        fl.addLayout(self._row(self.filter_edit, self.occ_only_chk))
        self.count_lbl = self._elastic(QtWidgets.QLabel(""))
        fl.addWidget(self.count_lbl)
        r1, r2 = QtWidgets.QHBoxLayout(), QtWidgets.QHBoxLayout()
        for txt, fn, lay in [("＋ Ajouter", self.add_watch_dialog, r1),
                             ("📥 Importer CSV…", self.import_watch, r1),
                             ("Coller une liste", self.paste_watch, r1),
                             ("📤 Exporter", self.export_watch, r2),
                             ("Supprimer", self.del_watch, r2),
                             ("Bandes depuis la liste", self.bands_from_list, r2)]:
            b = QtWidgets.QPushButton(txt)
            b.clicked.connect(fn)
            lay.addWidget(b)
        fl.addLayout(r1)
        fl.addLayout(r2)
        self.watch_table = QtWidgets.QTableWidget(0, len(WATCH_HEADERS))
        self.watch_table.setHorizontalHeaderLabels(WATCH_HEADERS)
        for c, tip in ((C_THR, "Seuil propre à cette fréquence (dBm). Double-clic pour le modifier ; "
                               "vide = seuil global."),
                       (C_OCC, "Taux d'occupation sur la durée choisie dans « Détection »."),
                       (C_LAYER, "Scène et groupe de cette fréquence. Double-clic pour l'affecter."),
                       (C_BAND, "Canal TV et attribution du spectre à cette fréquence (selon le pays).")):
            self.watch_table.horizontalHeaderItem(c).setToolTip(tip)
        self.watch_table.horizontalHeader().setSectionResizeMode(C_NAME, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for c, w in ((C_FREQ, 72), (C_LVL, 56), (C_MAX, 56), (C_THR, 56), (C_SIG, 78), (C_STAT, 84),
                     (C_OCC, 48), (C_LAYER, 120), (C_BAND, 190)):
            self.watch_table.setColumnWidth(c, w)
        self.watch_table.verticalHeader().setVisible(False)
        self.watch_table.setWordWrap(False)
        self.watch_table.setMinimumHeight(120)
        self.watch_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.watch_table.itemChanged.connect(self.on_watch_edit)
        self.watch_table.cellDoubleClicked.connect(self.on_watch_dbl)
        self.watch_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.watch_table.customContextMenuRequested.connect(self.watch_menu)
        self.watch_table.setItemDelegateForColumn(C_NAME, NameDelegate(self))
        sc_fill = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+D"), self.watch_table)
        sc_fill.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_fill.activated.connect(lambda *_: self.fill_down_names())
        fl.addWidget(self.watch_table, 1)
        tip = QtWidgets.QLabel("Double-clic sur « Statut » : change le statut · sur Niveau / Signal : zoom live · "
                               "sur « Seuil » : seuil propre à la fréquence.\n"
                               "Clic droit : menu complet. Tu peux aussi glisser un CSV sur la fenêtre.\n"
                               "Nom : l'auto-complétion propose MIC, HF 5, IEM… · Ctrl+D numérote vers le bas "
                               "(HF 1, HF 2…).\n"
                               "Un statut « Doit rester libre » déclenche ⚠ CONFLIT si un signal apparaît.")
        tip.setToolTip(tip.text())
        tip.setText("ⓘ Double-clic Statut / Niveau / Seuil · clic droit = menu · Ctrl+D numérote (survole pour l'aide)")
        tip.setWordWrap(True)
        tip.setMinimumHeight(self.fontMetrics().lineSpacing() * 2 + 4)
        fl.addWidget(tip)

        ltab = QtWidgets.QWidget()
        lg = QtWidgets.QVBoxLayout(ltab)
        b1 = QtWidgets.QPushButton("Exporter le journal")
        b1.clicked.connect(self.export_log)
        b2 = QtWidgets.QPushButton("Effacer")
        b2.clicked.connect(lambda: self.log_table.setRowCount(0))
        lg.addLayout(self._row(b1, b2, None))
        self.autolog_chk = QtWidgets.QCheckBox("Journal automatique (un fichier CSV par jour)")
        self.autolog_chk.setToolTip("Chaque événement est ajouté tout de suite à journal_AAAAMMJJ.csv :\n"
                                    "rien n'est perdu si le logiciel ou l'ordinateur plante.")
        self.autolog_chk.setChecked(True)
        b_dir = QtWidgets.QPushButton("📂 Ouvrir le dossier")
        b_dir.clicked.connect(self.open_log_dir)
        b_pick = QtWidgets.QPushButton("Choisir le dossier…")
        b_pick.clicked.connect(self.pick_log_dir)
        self.logdir_lbl = QtWidgets.QLabel(str(self.log_dir))
        self.logdir_lbl.setWordWrap(True)
        lg.addWidget(self.autolog_chk)
        lg.addLayout(self._row(b_dir, b_pick, None))
        lg.addWidget(self.logdir_lbl)
        self.rec_chk = QtWidgets.QCheckBox("💾 Enregistrer les balayages (pour la relecture)")
        self.rec_chk.setToolTip("Garde tous les balayages sur disque (un dossier par session, compressé, 2 Go max) pour\n"
                                "revoir le spectre plus tard : 🔧 Outils › ⏪ Relecture. Sans cette case, le logiciel\n"
                                "garde quand même les 30 dernières minutes en mémoire.")
        self.rec_chk.toggled.connect(self.toggle_rec)
        self.rec_lbl = QtWidgets.QLabel("")
        self.rec_lbl.setWordWrap(True)
        lg.addWidget(self.rec_chk)
        lg.addWidget(self.rec_lbl)
        self.log_table = QtWidgets.QTableWidget(0, 7)
        self.log_table.setHorizontalHeaderLabels(["Heure", "Nom", "MHz", "dBm", "Événement", "Scène › Groupe", "Note"])
        self.log_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.log_table.horizontalHeader().setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.log_table.cellDoubleClicked.connect(self.on_log_dbl)
        self.log_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_table.customContextMenuRequested.connect(self.log_menu)
        lg.addWidget(self.log_table, 1)
        tip2 = QtWidgets.QLabel("Double-clic sur un « INCONNU » : l'ajoute à ta liste de fréquences. Clic droit : "
                                "d'où ça peut venir (intermodulation). La colonne Note propose une origine IM3 "
                                "probable quand les émetteurs actifs peuvent l'expliquer.")
        tip2.setWordWrap(True)
        lg.addWidget(tip2)

        root = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(root)
        rv.setContentsMargins(8, 8, 8, 0)
        rv.addLayout(top)
        rv.addWidget(center, 1)
        self.setCentralWidget(root)
        left.setMinimumWidth(300)
        self._build_docks(left, ftab, ltab, self.wf_box)
        # listes déroulantes : ne pas s'élargir au plus long choix (noms de ports COM à rallonge sous Windows…) ;
        # le menu déroulé affiche toujours le texte complet
        for cb in self.findChildren(QtWidgets.QComboBox):
            cb.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(12)

        self.stat_lbl = self._elastic(QtWidgets.QLabel(""))
        self.cycle_lbl = self._elastic(QtWidgets.QLabel(""))
        self.cycle_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addWidget(self.stat_lbl, 3)
        self.statusBar().addPermanentWidget(self.cycle_lbl, 2)

    def _style_start(self, running):
        t = self.theme
        col = t["st_occ"] if running else t["st_free"]
        hov = blend("#ffffff", col, 0.18)
        self.start_btn.setText("■ Arrêter" if running else "▶ Démarrer")
        self.start_btn.setStyleSheet(
            "QPushButton{background:%s;color:%s;font-weight:bold;padding:7px 24px;border-radius:5px;}"
            "QPushButton:hover{background:%s;}" % (col, contrast_text(col), hov))

    def set_status(self, txt):
        self.stat_lbl.setText(txt)

    # ------------------------------------------------------- configuration
    def _bump(self):
        self._ver += 1

    def get_ver(self):
        return self._ver

    def _sync_cfg(self, *_):
        c = self._cfg
        c["rbw"] = self.rbw_combo.currentData()
        c["zrbw"] = self.zrbw_combo.currentData()
        c["input"] = self.input_combo.currentData()
        c["lna"] = self.lna_combo.currentData()
        c["att"] = self.att_combo.currentData()
        c["offset"] = self.offset_spin.value()
        c["seg"] = self.seg_combo.currentData()
        c["points"] = int(self.points_combo.currentData() or 1000)
        self.att_combo.setEnabled(c["lna"] is not True)
        self._bump()
        self._refresh_focus()

    @staticmethod
    def _npts(b):
        return max(2, int(round((b["stop"] - b["start"]) * 1000.0 / b["step"])) + 1)

    def update_estimate(self):
        seg = self._cfg["seg"] or getattr(self, "seg_known", None) or 290
        act = [b for b in self.scan_bands() if b["enabled"]]
        tot = sum(self._npts(b) for b in act)
        nseg = sum(len(segment_plan(self._npts(b), seg)) for b in act)
        pre = f"🎯 Scan ciblé ({len(act)} zone(s)) · " if self._focus_bands else ""
        txt = pre + f"{tot:,} points au total · {nseg} commande(s) de ≤ {seg} pts par cycle".replace(",", " ")
        if nseg > 40:
            txt += "\n⚠ Cycle long : réduis les points ou la largeur des bandes."
        self.est_lbl.setText(txt)

    def get_cfg(self):
        with self.lock:
            c = self._cfg
            if self._zoom:
                a, b = self._zoom
                n = max(2, int(c["points"]))
                step_khz = (b - a) * 1000.0 / (n - 1)
                bands = [dict(id=ZOOM_ID, name="Zoom", start_hz=a * 1e6, stop_hz=b * 1e6, n=n, enabled=True)]
                rbw = c["zrbw"] if c["zrbw"] is not None else auto_rbw(step_khz)
            else:
                bands = [dict(id=b["id"], name=b["name"], start_hz=b["start"] * 1e6, stop_hz=b["stop"] * 1e6,
                              n=self._npts(b), enabled=b["enabled"]) for b in self.scan_bands()]
                rbw = c["rbw"]
            freqs = [w["freq"] for w in self.watch]
            return dict(bands=bands, rbw=rbw, input=c["input"], lna=c["lna"], att=c["att"],
                        offset=c["offset"], seg=c["seg"], demo_freqs=freqs, ver=self._ver)

    def _load_config(self):
        data = {}
        try:
            data = json.loads(CFG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        self._apply_config(data, startup=True)
        g = data.get("geometry")
        if g:
            try:
                self.restoreGeometry(QtCore.QByteArray.fromBase64(g.encode()))
            except Exception:
                pass
        st = data.get("docks")
        if st:
            try:
                self._state_restored = bool(self.restoreState(QtCore.QByteArray.fromBase64(st.encode())))
            except Exception:
                pass

    def _apply_config(self, data, startup=False):
        """Applique un dictionnaire de réglages (config au démarrage, ou profil d'événement)."""
        if not startup:
            with self.lock:
                self.bands.clear()
            self.watch.clear()
            self.scenes.clear()
            self.scope = None
            for d in (self.latest, self.latest_t, self.maxhold, self.partial_data, self.history, self.unk_now):
                d.clear()
            self.alarms.reset()
        for b in data.get("bands", []):
            try:
                self._append_band(b["name"], float(b["start"]), float(b["stop"]),
                                  float(b["step"]), bool(b.get("enabled", True)))
            except Exception:
                pass
        if not self.bands:
            self._append_band("UHF 470–694 MHz", 470.0, 694.0, 200.0, True)
        sts = []
        for s in data.get("statuses", []):
            if isinstance(s, dict) and "name" in s and "color" in s:
                free = s.get("free", str(s["name"]).strip().lower() in ("libre", "free"))
                sts.append(dict(name=s["name"], color=s["color"], free=bool(free), on=bool(s.get("on", False))))
        if sts:
            if not any("on" in s0 for s0 in data.get("statuses", []) if isinstance(s0, dict)) \
                    and not any(x["name"].lower() == "en service" for x in sts):
                sts.append(dict(name="En service", color="#f1c40f", free=False, on=True))    # config d'avant la v7
            self.statuses = sts
        for sc in data.get("scenes", []):
            try:
                sn = str(sc["name"]).strip()
                if not sn:
                    continue
                self.ensure_group(sn)
                srow = self.scene_by_name(sn)
                if isinstance(sc.get("color"), str):
                    srow["color"] = sc["color"]
                for g in sc.get("groups", []):
                    gn = str(g["name"]).strip()
                    if not gn:
                        continue
                    self.ensure_group(sn, gn)
                    grow = next(x for x in srow["groups"] if x["name"] == gn)
                    if isinstance(g.get("color"), str):
                        grow["color"] = g["color"]
                    if g.get("prio") in (0, 1, 2):
                        grow["prio"] = int(g["prio"])
            except Exception:
                pass
        for w in data.get("watch", []):
            try:
                thr = w.get("thr")
                self._append_watch(w["name"], float(w["freq"]), w.get("status", ""),
                                   None if thr is None else float(thr), str(w.get("scene", "") or ""),
                                   str(w.get("group", "") or ""))
            except Exception:
                pass
        sp = data.get("scope")
        if isinstance(sp, list):
            ks = []
            for k in sp:
                try:
                    ks.append((str(k[0]), None if k[1] in (None, "") else str(k[1])))
                except Exception:
                    pass
            self.scope = ks or None
        self.focus_chk.setChecked(bool(data.get("focus", False)))
        th = data.get("theme")
        if isinstance(th, dict):
            base = dict(THEMES["Sombre"])
            base.update({k: v for k, v in th.items() if k in base and isinstance(v, str)})
            self.theme = base

        def setc(combo, key):
            if key in data:
                i = combo.findData(data[key])
                if i >= 0:
                    combo.setCurrentIndex(i)

        for combo, key in [(self.points_combo, "points"), (self.rbw_combo, "rbw"), (self.zrbw_combo, "zrbw"),
                           (self.input_combo, "input"), (self.lna_combo, "lna"), (self.att_combo, "att"),
                           (self.seg_combo, "seg"), (self.mark_combo, "mark"), (self.persist_combo, "persist"),
                           (self.occ_combo, "occ_minutes"), (self.country_combo, "country")]:
            setc(combo, key)
        pc = data.get("plan_custom")
        self.plan_custom = {k: v for k, v in pc.items() if isinstance(v, str)} if isinstance(pc, dict) else {}
        self.offset_spin.setValue(data.get("offset", 0.0))
        self.thr_spin.setValue(data.get("thr", -80))
        self.weak_spin.setValue(data.get("weak_thr", -90))
        self.weak_chk.setChecked(data.get("weak_on", True))
        self.win_spin.setValue(data.get("win", 100))
        self.absent_spin.setValue(int(data.get("absent_s", 20)))
        self.alert_chk.setChecked(data.get("alert", True))
        self.unk_chk.setChecked(data.get("unk", True))
        self.names_chk.setChecked(data.get("names", True))
        self.hold_chk.setChecked(data.get("hold", True))
        self.alloc_chk.setChecked(data.get("show_alloc", True))
        self.tv_chk.setChecked(data.get("show_tv", True))
        self.ref_chk.setChecked(data.get("ref_rel", False))
        self.ref_margin.setValue(data.get("ref_margin", 8.0))
        self.showref_chk.setChecked(data.get("show_ref", True))
        self.autolog_chk.setChecked(data.get("log_auto", True))
        ld = data.get("log_dir")
        if isinstance(ld, str) and ld:
            self.log_dir = Path(ld)
        self.logdir_lbl.setText(str(self.log_dir))
        ex = data.get("export")
        self.export_prefs = ex if isinstance(ex, dict) else {}
        if startup:
            self.demo_chk.setChecked(data.get("demo", False))
            vu = data.get("vocab")
            if isinstance(vu, dict):
                self.vocab_user = {k: [x for x in vu.get(k, []) if isinstance(x, str)][:300]
                                   for k in ("name", "scene", "group")}
        else:
            self._after_apply()

    def _after_apply(self):
        self._fit_x = True
        self._sync_cfg()
        self.rebuild_plan()
        self.apply_theme()
        self.rebuild_band_table()
        self.refresh_view_combo()
        self.rebuild_watch_table()
        self.update_ref_curve()
        self.set_status("Profil chargé.")

    def _collect_config(self, full=True):
        c = self._cfg
        data = dict(
            bands=[{k: v for k, v in b.items() if k != "id"} for b in self.bands],
            watch=[dict(name=w["name"], freq=w["freq"], status=w["status"], thr=w["thr"],
                        scene=w["scene"], group=w["group"]) for w in self.watch],
            scenes=[dict(name=s["name"], color=s["color"],
                         groups=[dict(name=g["name"], color=g["color"], prio=int(g.get("prio", 1))) for g in s["groups"]])
                    for s in self.scenes],
            scope=[list(k) for k in self.scope] if self.scope else None,
            focus=self.focus_chk.isChecked(),
            statuses=[dict(name=s["name"], color=s["color"], free=bool(s.get("free")), on=bool(s.get("on")))
                      for s in self.statuses],
            theme=self.theme,
            points=c["points"], rbw=c["rbw"], zrbw=c["zrbw"], input=c["input"], lna=c["lna"],
            att=c["att"], seg=c["seg"], offset=c["offset"], mark=self.mark_combo.currentData(),
            persist=self.persist_combo.currentData(),
            thr=self.thr_spin.value(), weak_thr=self.weak_spin.value(), weak_on=self.weak_chk.isChecked(),
            win=self.win_spin.value(), alert=self.alert_chk.isChecked(), unk=self.unk_chk.isChecked(),
            absent_s=self.absent_spin.value(),
            names=self.names_chk.isChecked(), hold=self.hold_chk.isChecked(),
            country=self.country_combo.currentData(), show_alloc=self.alloc_chk.isChecked(),
            show_tv=self.tv_chk.isChecked(), plan_custom=self.plan_custom,
            occ_minutes=self.occ_combo.currentData(), ref_rel=self.ref_chk.isChecked(),
            ref_margin=self.ref_margin.value(), show_ref=self.showref_chk.isChecked(),
            log_auto=self.autolog_chk.isChecked(), log_dir=str(self.log_dir), export=self.export_prefs)
        if full:
            data["demo"] = self.demo_chk.isChecked()
            data["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
            data["docks"] = bytes(self.saveState().toBase64()).decode()
            data["vocab"] = self.vocab_user
        return data

    def _save_config(self):
        try:
            CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CFG_PATH.write_text(json.dumps(self._collect_config(True), ensure_ascii=False, indent=1),
                                encoding="utf-8")
        except Exception:
            pass

    # --------------------------------------------------------------- profils
    def save_profile(self):
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Enregistrer le profil de l'événement", str(PROFILE_DIR / "evenement.json"), "Profil (*.json)")
        if not path:
            return
        try:
            data = self._collect_config(False)
            data["profil"] = APP_NAME
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            self.set_status(f"Profil enregistré : {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Impossible d'enregistrer le profil :\n{e}")

    def load_profile(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Charger un profil", str(PROFILE_DIR), "Profil (*.json);;Tous les fichiers (*)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not ("bands" in data or "watch" in data):
                raise ValueError("ce fichier ne ressemble pas à un profil")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Profil illisible :\n{e}")
            return
        r = QtWidgets.QMessageBox.question(
            self, APP_NAME, "Charger ce profil remplace les bandes, fréquences, statuts et réglages actuels.\n"
                            "Continuer ?")
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            self._apply_config(data)
            self.set_status(f"Profil chargé : {os.path.basename(path)}")

    def open_profile_dir(self):
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(PROFILE_DIR)))

    # --------------------------------------------------------------- ports
    def refresh_ports(self):
        self.port_combo.clear()
        ports = list(serial.tools.list_ports.comports())
        ports.sort(key=lambda p: not (p.vid == TINYSA_VID and p.pid == TINYSA_PID))
        for p in ports:
            tag = "  ✔ tinySA" if (p.vid == TINYSA_VID and p.pid == TINYSA_PID) else ""
            self.port_combo.addItem(f"{p.device} — {p.description}{tag}", p.device)
        if not ports:
            self.port_combo.addItem("Aucun port détecté", None)

    # ----------------------------------------------------------- run / stop
    def toggle_run(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.start_btn.setEnabled(False)
            self.set_status("Arrêt en cours… (le segment en cours doit se terminer)")
            return
        demo = self.demo_chk.isChecked()
        port = self.port_combo.currentData()
        if not demo and not port:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Aucun port série sélectionné.\n"
                                          "Branche le tinySA (et ferme tinySA-App) ou active le mode démo.")
            return
        if not any(b["enabled"] for b in self.bands):
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Coche au moins une bande à balayer.")
            return
        self.worker = ScanWorker(port, demo, self.get_cfg, self.get_ver)
        self.worker.sweep.connect(self.on_sweep)
        self.worker.partial.connect(self.on_partial)
        self.worker.cycle.connect(self.on_cycle)
        self.worker.status.connect(self.set_status)
        self.worker.info.connect(self.on_info)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        self._style_start(True)
        self.port_combo.setEnabled(False)
        self.demo_chk.setEnabled(False)

    def on_info(self, txt):
        self.info_lbl.setText(f"  {txt}")
        self.seg_known = 450 if "tinysa4" in txt.lower() else 290
        self.update_estimate()

    def on_error(self, msg):
        QtWidgets.QMessageBox.critical(self, APP_NAME, f"Erreur de balayage :\n{msg}")

    def on_finished(self):
        self._style_start(False)
        self.start_btn.setEnabled(True)
        self.port_combo.setEnabled(True)
        self.demo_chk.setEnabled(True)
        self.partial_data.clear()
        self.set_status("Arrêté.")

    # --------------------------------------------------------------- bandes
    def _append_band(self, name, start, stop, step, enabled=True):
        with self.lock:
            self.bands.append(dict(id=self._next_id, name=name, start=start, stop=stop,
                                   step=step, enabled=enabled))
            self._next_id += 1

    def _bands_changed(self):
        self._bump()
        self.rebuild_band_table()
        self.refresh_view_combo()
        self.update_estimate()

    def add_band(self, name, start, stop, step, enabled=True):
        self._append_band(name, start, stop, step, enabled)
        self._bands_changed()

    def on_preset(self, idx):
        if idx > 0:
            p = self.preset_combo.itemData(idx)
            self.add_band(p[0], p[1], p[2], p[3])
        self.preset_combo.setCurrentIndex(0)

    def del_band(self):
        r = self.band_table.currentRow()
        if r < 0 or r >= len(self.bands):
            return
        with self.lock:
            b = self.bands.pop(r)
        for d in (self.latest, self.maxhold, self.partial_data):
            d.pop(b["id"], None)
        self._bands_changed()

    def apply_points(self, _=None):
        pts = int(self.points_combo.currentData() or 1000)
        with self.lock:
            for b in self.bands:
                b["step"] = round((b["stop"] - b["start"]) * 1000.0 / (pts - 1), 6)
        self.latest.clear()
        self.maxhold.clear()
        self.partial_data.clear()
        self.rebuild_band_table()
        self._sync_cfg()
        self.set_status(f"{pts} points par bande (pas recalculé pour chaque bande).")

    def rebuild_band_table(self):
        self._updating = True
        t = self.band_table
        t.setRowCount(len(self.bands))
        for r, b in enumerate(self.bands):
            it = QtWidgets.QTableWidgetItem(b["name"])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable |
                        Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Checked if b["enabled"] else Qt.CheckState.Unchecked)
            t.setItem(r, 0, it)
            t.setItem(r, 1, self._item(f'{b["start"]:g}', True, True))
            t.setItem(r, 2, self._item(f'{b["stop"]:g}', True, True))
            t.setItem(r, 3, self._item(str(self._npts(b)), True, True))
            t.setItem(r, 4, self._item(f'{b["step"]:.4g}', True, True))
        self._updating = False

    def on_band_edit(self, item):
        if self._updating or item.row() >= len(self.bands):
            return
        r, col, t = item.row(), item.column(), self.band_table
        name = t.item(r, 0).text()
        enabled = t.item(r, 0).checkState() == Qt.CheckState.Checked
        start, stop, step = (_num(t.item(r, c).text()) for c in (1, 2, 3 + 1))
        pts = _num(t.item(r, 3).text())
        if None in (start, stop, step, pts) or start < 0.1 or stop <= start or step <= 0 or pts < 2:
            QtCore.QTimer.singleShot(0, self.rebuild_band_table)
            return
        if col == 3:
            step = (stop - start) * 1000.0 / (int(pts) - 1)
        b = self.bands[r]
        with self.lock:
            b.update(name=name, start=start, stop=stop, step=round(step, 6), enabled=enabled)
        if col != 0:
            for d in (self.latest, self.maxhold, self.partial_data):
                d.pop(b["id"], None)
        self._fit_x = True
        QtCore.QTimer.singleShot(0, self._bands_changed)

    def refresh_view_combo(self):
        cur = self.view_combo.currentData()
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        self.view_combo.addItem("Toutes les bandes", -1)
        for b in self.scan_bands():
            self.view_combo.addItem(b["name"], b["id"])
        idx = self.view_combo.findData(cur)
        self.view_combo.setCurrentIndex(max(idx, 0))
        self.view_combo.blockSignals(False)
        self.on_view_changed()

    def on_view_changed(self, *_):
        if self._zoom is not None:
            return
        v = self.view_combo.currentData()
        self.view_id = -1 if v is None else v
        self._wf_show(self.view_id != -1)
        self.wf_hist, self.wf_id = None, None
        self._fit_x = True
        self.update_plot()

    # ----------------------------------------------------------- zoom live
    def toggle_zoom(self, on):
        if on:
            if self._last_xy is None:
                QtWidgets.QMessageBox.information(
                    self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer), zoome sur la zone qui "
                                    "t'intéresse, puis active le zoom live.")
                self.zoom_btn.setChecked(False)
                return
            vr = self.spec.getPlotItem().vb.viewRange()[0]
            self._set_zoom(vr[0], vr[1])
            self.view_id = ZOOM_ID
            self.view_combo.setEnabled(False)
            self._wf_show(True)
            self.zoom_timer.start()
            self.set_status("Zoom live : le tinySA scanne uniquement la zone visible avec le nombre de points "
                            "choisi. Zoome / déplace-toi, le scan suit (les autres fréquences sont suspendues).")
        else:
            if self._zoom is None:
                return
            self.zoom_timer.stop()
            with self.lock:
                self._zoom = None
            for d in (self.latest, self.maxhold, self.partial_data):
                d.pop(ZOOM_ID, None)
            self._bump()
            self.view_combo.setEnabled(True)
            self.on_view_changed()
            self.set_status("Zoom live désactivé.")

    def _set_zoom(self, a, b):
        self._zoom_view = (a, b)
        a, b = max(0.1, a), min(6000.0, b)
        if b - a < 0.05:
            mid = (a + b) / 2
            a, b = mid - 0.025, mid + 0.025
        with self.lock:
            self._zoom = (a, b)
        for d in (self.latest, self.maxhold, self.partial_data):
            d.pop(ZOOM_ID, None)
        self.wf_hist, self.wf_id = None, None
        self._bump()

    def zoom_follow(self):
        if self._zoom is None or self._zoom_view is None:
            return
        vr = self.spec.getPlotItem().vb.viewRange()[0]
        a, b = self._zoom_view
        tol = 0.02 * (b - a)
        if abs(vr[0] - a) > tol or abs(vr[1] - b) > tol:
            self._set_zoom(vr[0], vr[1])

    def zoom_on(self, row, half=1.0):
        if row >= len(self.watch):
            return
        if self._last_xy is None:
            self.set_status("Lance d'abord un balayage (▶ Démarrer) pour pouvoir zoomer.")
            return
        f = self.watch[row]["freq"]
        self.spec.getPlotItem().setXRange(f - half, f + half, padding=0)
        self._fit_x = False
        if not self.zoom_btn.isChecked():
            self.zoom_btn.setChecked(True)
        else:
            self._set_zoom(f - half, f + half)

    # ------------------------------------------------- couches : scènes › groupes
    def scene_by_name(self, name):
        return next((x for x in self.scenes if x["name"] == name), None)

    def ensure_group(self, scene, group=""):
        """Crée la scène (et le groupe) s'ils n'existent pas encore."""
        scene, group = (scene or "").strip(), (group or "").strip()
        if not scene:
            return
        sc = self.scene_by_name(scene)
        if sc is None:
            sc = dict(name=scene, color=GROUP_COLORS[len(self.scenes) % len(GROUP_COLORS)], groups=[])
            self.scenes.append(sc)
        if group and not any(g["name"] == group for g in sc["groups"]):
            n = sum(len(x["groups"]) for x in self.scenes)
            sc["groups"].append(dict(name=group, color=GROUP_COLORS[n % len(GROUP_COLORS)]))

    def group_color(self, scene, group):
        sc = self.scene_by_name(scene)
        if sc is None:
            return None
        for g in sc["groups"]:
            if g["name"] == group:
                return g["color"]
        return sc["color"]

    def in_scope(self, w):
        return scope_match(self.scope, w["scene"], w["group"])

    def scope_ws(self):
        return [w for w in self.watch if self.in_scope(w)]

    @staticmethod
    def layer_text(w):
        if w["scene"] and w["group"]:
            return f'{w["scene"]} › {w["group"]}'
        return w["scene"] or w["group"] or ""

    def scope_text(self):
        if not self.scope:
            return "Global"
        return " + ".join((f"{a} › {b}" if b else (a or "Sans scène")) for a, b in self.scope)

    def _scope_preset(self):
        """Scène / groupe proposés par défaut pour une nouvelle fréquence (la couche active, si c'est un groupe)."""
        if self.scope and len(self.scope) == 1 and self.scope[0][0]:
            return self.scope[0][0], (self.scope[0][1] or "")
        return "", ""

    def _tree_counts(self):
        cnt = {}
        for w in self.watch:
            keys = [(w["scene"], None)]
            if w["group"]:
                keys.append((w["scene"], w["group"]))
            for k in keys:
                c = cnt.setdefault(k, [0, 0, 0])
                c[0] += 1
                if w["state"] == "occ":
                    c[1] += 1
                    if self.is_keep_free(w["status"]):
                        c[2] += 1
                if w.get("absent"):
                    c[2] += 1
        return cnt

    @staticmethod
    def _tree_label(name, c):
        txt = f"{name}   ·  {c[0]} fréq."
        if c[2]:
            txt += f"  ·  ⚠ {c[2]} alarme(s)"
        elif c[1]:
            txt += f"  ·  {c[1]} occupée(s)"
        return txt

    def rebuild_tree(self):
        tree = self.layer_tree
        cnt = self._tree_counts()
        self._tree_lock = True
        tree.clear()
        self._tree_items, self._tree_sig = {}, {}

        def mk(parent, scene, group, name, color):
            it = QtWidgets.QTreeWidgetItem()
            it.setText(0, self._tree_label(name, cnt.get((scene, group), [0, 0, 0])))
            it.setIcon(0, color_icon(color))
            it.setData(0, Qt.ItemDataRole.UserRole, key_enc(scene, group))
            if parent is None:
                tree.addTopLevelItem(it)
            else:
                parent.addChild(it)
            self._tree_items[(scene, group)] = (it, name)
            return it

        for sc in self.scenes:
            top = mk(None, sc["name"], None, sc["name"], sc["color"])
            for g in sc["groups"]:
                mk(top, sc["name"], g["name"], g["name"] + self.prio_mark(g), g["color"])
        if self.scenes and any(w["scene"] == "" for w in self.watch):
            mk(None, "", None, "Sans scène", self.theme["st_none"])
        tree.expandAll()
        cur = list(self.scope or [])
        valid = [k for k in cur if k in self._tree_items]
        for k in valid:
            self._tree_items[k][0].setSelected(True)
        self._tree_lock = False
        if cur != valid:
            self.set_scope(valid or None)
        else:
            self.update_scope_ui()

    def update_tree_counts(self):
        cnt = self._tree_counts()
        th = self.theme
        for k, (it, name) in self._tree_items.items():
            c = cnt.get(k, [0, 0, 0])
            txt = self._tree_label(name, c)
            col = th["st_occ"] if c[2] else (th["st_weak"] if c[1] else th["ui_text"])
            if self._tree_sig.get(k) != (txt, col):
                self._tree_sig[k] = (txt, col)
                it.setText(0, txt)
                it.setForeground(0, QtGui.QBrush(QtGui.QColor(col)))

    def update_scope_ui(self):
        n = len(self.scope_ws())
        if self.scope:
            self.layer_lbl.setText(f"Couche active : {self.scope_text()} — {n} fréquence(s)")
        else:
            self.layer_lbl.setText(f"Couche active : Global — {len(self.watch)} fréquence(s)")
        self.focus_chk.setEnabled(bool(self.scope))
        col = self.theme["st_free"]
        self.global_btn.setStyleSheet(
            "QPushButton{background:%s;color:%s;font-weight:bold;}" % (col, contrast_text(col))
            if not self.scope else "")
        self.setWindowTitle(f"{APP_NAME} {APP_VER}" + (f" — {self.scope_text()}" if self.scope else ""))

    def set_scope(self, scope):
        self.scope = [tuple(k) for k in scope] if scope else None
        for w in self.watch:
            w["t_acc"] = None
            w["sig"] = None
        self._refresh_focus()
        self.update_scope_ui()
        self.update_watch_table(force=True)
        self._update_markers()
        if self.wall is not None and self.wall.isVisible():
            self.wall.relayout()

    def on_tree_sel(self):
        if self._tree_lock:
            return
        keys = []
        for it in self.layer_tree.selectedItems():
            k = key_dec(it.data(0, Qt.ItemDataRole.UserRole))
            if k is not None:
                keys.append(k)
        self.set_scope(keys or None)

    def go_global(self):
        self._tree_lock = True
        self.layer_tree.clearSelection()
        self._tree_lock = False
        self.set_scope(None)

    def _layers_changed(self):
        for w in self.watch:
            w["sig"] = None
        self.rebuild_tree()
        self._refresh_focus()
        self.update_watch_table(force=True)
        self._update_markers()
        if self.wall is not None and self.wall.isVisible():
            self.wall.relayout()

    def _sel_layer_key(self):
        its = self.layer_tree.selectedItems()
        return key_dec(its[0].data(0, Qt.ItemDataRole.UserRole)) if its else None

    def add_scene(self):
        txt, ok = self.ask_name("scene", "Nouvelle scène", "Nom de la scène (ex. Main Stage) :")
        name = txt.strip()
        if ok and name:
            self.ensure_group(name)
            self._layers_changed()
            return name
        return None

    def _pick_scene(self):
        k = self._sel_layer_key()
        if k is not None and k[0] and self.scene_by_name(k[0]) is not None:
            return k[0]
        if len(self.scenes) == 1:
            return self.scenes[0]["name"]
        if self.scenes:
            name, ok = QtWidgets.QInputDialog.getItem(self, "Scène", "Dans quelle scène ?",
                                                      [x["name"] for x in self.scenes], 0, False)
            return name if ok else None
        return None

    def add_group(self, scene=None):
        """Crée un groupe (et la scène si besoin) ; renvoie (scène, groupe) ou None."""
        scene = scene or self._pick_scene()
        if not scene:
            txt, ok = self.ask_name("scene", "Nouvelle scène", "Il n'y a pas encore de scène. Nom de la scène :")
            if not (ok and txt.strip()):
                return None
            scene = txt.strip()
        txt, ok = self.ask_name("group", "Nouveau groupe", f"Nom du groupe / de l'artiste dans « {scene} » :")
        name = txt.strip()
        if ok and name:
            self.ensure_group(scene, name)
            self._layers_changed()
            return scene, name
        return None

    def assign_rows(self, rows, scene, group=""):
        if group and not scene:
            scene = DEFAULT_SCENE
        self.ensure_group(scene, group)
        for r in rows:
            if r < len(self.watch):
                self.watch[r]["scene"], self.watch[r]["group"] = scene, group
        self._layers_changed()

    def assign_menu(self, parent):
        m = QtWidgets.QMenu(parent)
        for sc in self.scenes:
            sm = m.addMenu(color_icon(sc["color"]), sc["name"])
            a = sm.addAction(f"{sc['name']} (toute la scène)")
            a.setData(key_enc(sc["name"]))
            sm.addSeparator()
            for g in sc["groups"]:
                a = sm.addAction(color_icon(g["color"]), g["name"])
                a.setData(key_enc(sc["name"], g["name"]))
            sm.addSeparator()
            a = sm.addAction("＋ Nouveau groupe…")
            a.setData("N" + SEP + sc["name"])
        if self.scenes:
            m.addSeparator()
        a = m.addAction("＋ Nouvelle scène + groupe…")
        a.setData("NS" + SEP)
        a = m.addAction("— Aucune scène")
        a.setData("X" + SEP)
        return m

    def _assign_action(self, rows, d):
        """Traite l'action d'un menu « affecter » ; False si ce n'en est pas une."""
        if not (isinstance(d, str) and SEP in d):
            return False
        p = d.split(SEP)
        if p[0] == "X":
            self.assign_rows(rows, "", "")
        elif p[0] == "S" and len(p) == 2:
            self.assign_rows(rows, p[1], "")
        elif p[0] == "G" and len(p) == 3:
            self.assign_rows(rows, p[1], p[2])
        elif p[0] == "N" and len(p) == 2:
            r = self.add_group(p[1])
            if r:
                self.assign_rows(rows, r[0], r[1])
        elif p[0] == "NS":
            txt, ok = self.ask_name("scene", "Nouvelle scène", "Nom de la scène :")
            if ok and txt.strip():
                r = self.add_group(txt.strip())
                if r:
                    self.assign_rows(rows, r[0], r[1])
        return True

    def layer_popup(self, rows):
        m = self.assign_menu(self)
        act = m.exec(QtGui.QCursor.pos())
        if act is not None:
            self._assign_action(rows, act.data())

    def rename_layer(self, key):
        scene, group = key
        old = group if group else scene
        txt, ok = self.ask_name("scene" if group is None else "group", "Renommer", "Nouveau nom :", old)
        new = txt.strip()
        sc = self.scene_by_name(scene)
        if not ok or not new or new == old or sc is None:
            return
        if group is None:
            if self.scene_by_name(new) is not None:
                QtWidgets.QMessageBox.information(self, APP_NAME, "Une scène porte déjà ce nom.")
                return
            sc["name"] = new
            for w in self.watch:
                if w["scene"] == scene:
                    w["scene"] = new
            if self.scope:
                self.scope = [(new if k[0] == scene else k[0], k[1]) for k in self.scope]
        else:
            if any(g["name"] == new for g in sc["groups"]):
                QtWidgets.QMessageBox.information(self, APP_NAME, "Un groupe porte déjà ce nom dans cette scène.")
                return
            for g in sc["groups"]:
                if g["name"] == group:
                    g["name"] = new
            for w in self.watch:
                if w["scene"] == scene and w["group"] == group:
                    w["group"] = new
            if self.scope:
                self.scope = [(k[0], new if (k[0] == scene and k[1] == group) else k[1]) for k in self.scope]
        self._layers_changed()

    def delete_layer(self, key):
        scene, group = key
        sc = self.scene_by_name(scene)
        if sc is None:
            return
        if group is None:
            n = sum(1 for w in self.watch if w["scene"] == scene)
            msg = (f"Supprimer la scène « {scene} » et ses {len(sc['groups'])} groupe(s) ?\n"
                   f"Les {n} fréquence(s) restent dans ta liste, sans scène.")
        else:
            n = sum(1 for w in self.watch if w["scene"] == scene and w["group"] == group)
            msg = (f"Supprimer le groupe « {group} » ?\n"
                   f"Les {n} fréquence(s) restent dans la scène « {scene} », sans groupe.")
        if QtWidgets.QMessageBox.question(self, APP_NAME, msg) != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if group is None:
            self.scenes.remove(sc)
            for w in self.watch:
                if w["scene"] == scene:
                    w["scene"], w["group"] = "", ""
        else:
            sc["groups"] = [g for g in sc["groups"] if g["name"] != group]
            for w in self.watch:
                if w["scene"] == scene and w["group"] == group:
                    w["group"] = ""
        self._layers_changed()

    def pick_layer_color(self, key):
        scene, group = key
        sc = self.scene_by_name(scene)
        if sc is None:
            return
        tgt = sc if group is None else next((g for g in sc["groups"] if g["name"] == group), None)
        if tgt is None:
            return
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(tgt["color"]), self, "Couleur")
        if c.isValid():
            tgt["color"] = c.name()
            self._layers_changed()

    def layer_action(self, what):
        k = self._sel_layer_key()
        if k is None or self.scene_by_name(k[0]) is None:
            self.set_status("Sélectionne d'abord une scène ou un groupe dans l'arbre.")
            return
        if what == "rename":
            self.rename_layer(k)
        elif what == "delete":
            self.delete_layer(k)

    def layer_menu(self, pos):
        it = self.layer_tree.itemAt(pos)
        key = key_dec(it.data(0, Qt.ItemDataRole.UserRole)) if it is not None else None
        real = key is not None and self.scene_by_name(key[0]) is not None
        m = QtWidgets.QMenu(self)
        a_scene = m.addAction("＋ Nouvelle scène…")
        a_group = m.addAction("＋ Nouveau groupe…")
        a_imp = a_asg = a_ren = a_col = a_del = None
        rows = self._sel_rows()
        if real:
            m.addSeparator()
            a_imp = m.addAction("📥 Importer un CSV dans " + ("ce groupe…" if key[1] else "cette scène…"))
            if rows:
                a_asg = m.addAction(f"Affecter les {len(rows)} fréquence(s) sélectionnée(s) ici")
            m.addSeparator()
            a_ren = m.addAction("Renommer…")
            a_col = m.addAction("Couleur…")
            sub = QtWidgets.QMenu("🔔 Priorité des alarmes" + (" (ce groupe)" if key[1] else " (tous ses groupes)"), m)
            a_prio = {sub.addAction(f"{lab}{'  ✔' if cur else ''}"): p
                      for p, lab, cur in ((2, "❗ Critique : son répété jusqu'à acquittement", self._cur_prio(key) == 2),
                                          (1, "Normale : bip à l'apparition", self._cur_prio(key) == 1),
                                          (0, "🔕 Info : pas de son", self._cur_prio(key) == 0))}
            m.addMenu(sub)
            a_del = m.addAction("Supprimer")
        act = m.exec(self.layer_tree.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_scene:
            self.add_scene()
        elif act is a_group:
            if real:
                self.add_group(key[0])
            else:
                self.add_group()
        elif act is a_imp:
            self.import_into(key)
        elif act is a_asg:
            self.assign_rows(rows, key[0], key[1] or "")
        elif act is a_ren:
            self.rename_layer(key)
        elif act is a_col:
            self.pick_layer_color(key)
        elif act is a_del:
            self.delete_layer(key)
        elif real and act in a_prio:
            self.set_prio(key, a_prio[act])

    def _cur_prio(self, key):
        """Priorité d'un groupe (ou de la scène si tous ses groupes sont identiques, sinon -1)."""
        sc = self.scene_by_name(key[0])
        if sc is None:
            return -1
        ps = {int(g.get("prio", 1)) for g in sc["groups"] if not key[1] or g["name"] == key[1]}
        return ps.pop() if len(ps) == 1 else -1

    def import_into(self, key):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Importer des fréquences", "", "CSV / texte (*.csv *.txt *.tsv);;Tous les fichiers (*)")
        for p in paths:
            self.open_import(decode_text(Path(p).read_bytes()), os.path.basename(p),
                             preset=(key[0], key[1] or ""))

    # ------------------------------------------------------ scan ciblé (focus)
    def scan_bands(self):
        """Bandes réellement balayées : zones ciblées autour de la couche active, sinon tes bandes."""
        return self._focus_bands if self._focus_bands else self.bands

    def _on_focus_toggled(self, on):
        self._refresh_focus()
        if on and self.scope:
            self.set_status("🎯 Scan ciblé : seules les zones autour des fréquences de la couche active sont "
                            "balayées. Repasse en Global pour tout revoir.")
        elif on:
            self.set_status("Le scan ciblé s'active dès qu'une scène ou un groupe est sélectionné.")

    def _refresh_focus(self):
        new = []
        if self.scope and self.focus_chk.isChecked():
            fr = [w["freq"] for w in self.watch if self.in_scope(w)]
            for i, (a, b, n) in enumerate(focus_plan(fr, self._cfg["points"])):
                new.append(dict(id=-100 - i, name=f"{a:.2f}–{b:.2f} MHz", start=a, stop=b,
                                step=round((b - a) * 1000.0 / (n - 1), 6), enabled=True))
        sig = [(b["start"], b["stop"], b["step"]) for b in new]
        if sig != self._focus_sig:
            with self.lock:
                self._focus_bands, self._focus_sig = new, sig
            self._bump()
            ids = {b["id"] for b in self.scan_bands()}
            for d in (self.latest, self.latest_t, self.maxhold, self.partial_data, self.history, self.unk_now):
                for k in [k for k in d if k != ZOOM_ID and k not in ids]:
                    d.pop(k, None)
            self._fit_x = True
            self.refresh_view_combo()
        self.update_estimate()

    # ------------------------------------------------- fréquences surveillées
    def _append_watch(self, name, freq, status="", thr=None, scene="", group=""):
        scene, group = (scene or "").strip(), (group or "").strip()
        if group and not scene:
            scene = DEFAULT_SCENE
        self.ensure_group(scene, group)
        band, cat = spectrum_info(freq, self.plan, self.tv)
        self.watch.append(dict(name=name, freq=freq, status=status, level=None, max=None,
                               state=None, peak=None, since=0.0, sig=None, thr=thr,
                               occw=OccWindow(self.occ_combo.currentData() or 60), t_acc=None,
                               band=band, cat=cat, scene=scene, group=group, free_since=None, absent=False))

    def sort_watch(self):
        self.watch.sort(key=lambda w: w["freq"])

    def is_keep_free(self, name):
        return bool(name) and any(s["name"] == name and s.get("free") for s in self.statuses)

    def state_color(self, st):
        return {"free": self.theme["st_free"], "weak": self.theme["st_weak"],
                "occ": self.theme["st_occ"]}.get(st, self.theme["st_none"])

    def status_color(self, name):
        for s in self.statuses:
            if s["name"] == name:
                return s["color"]
        return self.theme["st_none"]

    def rebuild_watch_table(self):
        self._updating = True
        t = self.watch_table
        t.setRowCount(len(self.watch))
        for r, w in enumerate(self.watch):
            w["sig"] = None
            w["band"], w["cat"] = spectrum_info(w["freq"], self.plan, self.tv)
            t.setItem(r, C_NAME, self._item(w["name"], True))
            t.setItem(r, C_FREQ, self._item(f'{w["freq"]:.3f}', True, True))
            for c in (C_LVL, C_MAX):
                t.setItem(r, c, self._item("—", False, True))
            t.setItem(r, C_THR, self._item("—", True, True))
            t.setItem(r, C_SIG, self._item("—"))
            t.setItem(r, C_STAT, self._item("—"))
            t.setItem(r, C_OCC, self._item("—", False, True))
            t.setItem(r, C_LAYER, self._item("—"))
            t.setItem(r, C_BAND, self._item("—"))
        self._updating = False
        self.rebuild_tree()
        self._refresh_focus()
        self.update_watch_table(force=True)

    def update_watch_table(self, force=False):
        t, th = self.watch_table, self.theme
        base = th["ui_base"]
        self._updating = True
        n = dict(occ=0, weak=0, free=0)
        n_conf = n_ws = n_abs = 0
        for r, w in enumerate(self.watch):
            if r >= t.rowCount():
                break
            st = w["state"]
            conf = st == "occ" and self.is_keep_free(w["status"])
            absn = bool(w.get("absent"))
            if self.in_scope(w):
                n_ws += 1
                if st in n:
                    n[st] += 1
                n_conf += conf
                n_abs += absn
            lv = "—" if w["level"] is None else f'{w["level"]:.1f}'
            mx = "—" if w["max"] is None else f'{w["max"]:.1f}'
            stat = w["status"] or "—"
            thr_txt = "—" if w["thr"] is None else f'{w["thr"]:.1f}'
            pct = w["occw"].pct()
            occ_txt = "—" if pct is None else f"{pct:.0f} %"
            band = w["band"] or "—"
            layer = self.layer_text(w)
            gc = self.group_color(w["scene"], w["group"]) if layer else None
            sig = (lv, mx, st, conf, stat, w["name"], round(w["freq"], 3), thr_txt, occ_txt, band, layer, gc, absn)
            if not force and w["sig"] == sig:
                continue
            w["sig"] = sig
            row_bg = {"occ": blend(th["st_occ"], base, 0.55), "weak": blend(th["st_weak"], base, 0.35)}.get(st, base)
            row_fg = contrast_text(row_bg) if st in ("occ", "weak") else th["ui_text"]
            sig_txt = CONFLICT_TEXT if conf else (ABSENT_TEXT if absn else SIG_TEXT[st])
            cells = ((C_NAME, w["name"]), (C_FREQ, f'{w["freq"]:.3f}'), (C_LVL, lv), (C_MAX, mx),
                     (C_THR, thr_txt), (C_SIG, sig_txt), (C_STAT, stat), (C_OCC, occ_txt),
                     (C_LAYER, layer or "—"), (C_BAND, band))
            for c, txt in cells:
                it = t.item(r, c)
                if it is None:
                    continue
                if it.text() != txt:
                    it.setText(txt)
                bg, fg = row_bg, row_fg
                if c == C_SIG and absn:
                    bg = blend(th["st_occ"], base, 1.0)
                    fg = contrast_text(bg)
                elif c == C_SIG and st is not None:
                    bg = blend(self.state_color(st), base, 1.0 if conf else 0.8)
                    fg = contrast_text(bg)
                elif c == C_STAT and w["status"]:
                    bg = blend(self.status_color(w["status"]), base, 0.75)
                    fg = contrast_text(bg)
                elif c == C_LAYER and gc:
                    bg = blend(gc, base, 0.55)
                    fg = contrast_text(bg)
                elif c == C_BAND and w["cat"]:
                    bg = blend(th.get("bp_" + w["cat"], th["st_none"]), base, 0.6)
                    fg = contrast_text(bg)
                    tip = describe_freq(w["freq"], self.plan, self.tv)
                    if it.toolTip() != tip:
                        it.setToolTip(tip)
                it.setBackground(QtGui.QColor(bg))
                it.setForeground(QtGui.QColor(fg))
        self._updating = False
        total = f"{n_ws} fréquences" + (f" (sur {len(self.watch)})" if self.scope else "")
        txt = (f'{total} · {n["occ"]} occupée(s) · '
               f'{n["weak"]} faible(s) · {n["free"]} libre(s)')
        if n_conf:
            txt += f" · {CONFLICT_TEXT} ×{n_conf}"
        if n_abs:
            txt += f" · {ABSENT_TEXT} ×{n_abs}"
        self.count_lbl.setText(txt)
        self.apply_filter()
        self.update_tree_counts()
        if self.wall is not None and self.wall.isVisible():
            self.wall.refresh()

    def apply_filter(self, *_):
        t = self.watch_table
        txt = self.filter_edit.text().strip().lower().replace(",", ".")
        occ = self.occ_only_chk.isChecked()
        for r, w in enumerate(self.watch):
            if r >= t.rowCount():
                break
            hide = (not self.in_scope(w)) or (occ and w["state"] != "occ") or bool(
                txt and not (txt in w["name"].lower() or txt in f'{w["freq"]:.3f}'
                             or txt in (w["status"] or "").lower() or txt in (w["band"] or "").lower()
                             or txt in self.layer_text(w).lower()))
            if t.isRowHidden(r) != hide:
                t.setRowHidden(r, hide)

    def on_watch_edit(self, item):
        if self._updating or item.row() >= len(self.watch):
            return
        w = self.watch[item.row()]
        if item.column() == C_NAME:
            w["name"] = item.text()
            w["sig"] = None
            self._update_markers()
        elif item.column() == C_FREQ:
            v = parse_freq_cell(item.text())
            if v is None:
                QtCore.QTimer.singleShot(0, self.rebuild_watch_table)
                return
            w.update(freq=v, level=None, max=None, state=None, t_acc=None)
            w["occw"].clear()
            self.sort_watch()
            QtCore.QTimer.singleShot(0, self.rebuild_watch_table)
            self._update_markers()
        elif item.column() == C_THR:
            txt = item.text().strip().lower()
            if txt in ("", "—", "-", "global"):
                w["thr"] = None
            else:
                v = _num(txt)
                if v is not None and -140.0 <= v <= 20.0:
                    w["thr"] = v
            w["sig"] = None
            QtCore.QTimer.singleShot(0, lambda: self.update_watch_table(force=True))

    def on_watch_dbl(self, row, col):
        if col == C_STAT:
            self.status_popup([row])
        elif col == C_LAYER:
            self.layer_popup([row])
        elif col in (C_LVL, C_MAX, C_SIG):
            self.zoom_on(row)

    def _sel_rows(self):
        return sorted({i.row() for i in self.watch_table.selectedIndexes() if i.row() < len(self.watch)})

    def _status_menu(self, parent):
        m = QtWidgets.QMenu(parent)
        a0 = m.addAction("— aucun statut")
        a0.setData("")
        for s in self.statuses:
            a = m.addAction(color_icon(s["color"]), s["name"])
            a.setData(s["name"])
        return m

    def status_popup(self, rows):
        m = self._status_menu(self)
        act = m.exec(QtGui.QCursor.pos())
        if act is not None and act.data() is not None:
            self.set_status_rows(rows, act.data())

    def set_status_rows(self, rows, name):
        for r in rows:
            if r < len(self.watch):
                self.watch[r]["status"] = name
        self.update_watch_table(force=True)
        self._update_markers()

    def watch_menu(self, pos):
        rows = self._sel_rows()
        if not rows:
            r = self.watch_table.rowAt(pos.y())
            rows = [r] if 0 <= r < len(self.watch) else []
        if not rows:
            return
        m = QtWidgets.QMenu(self)
        sub = self._status_menu(m)
        sub.setTitle(f"Statut ({len(rows)} sélectionnée(s))" if len(rows) > 1 else "Statut")
        m.addMenu(sub)
        lay_sub = self.assign_menu(m)
        lay_sub.setTitle("Scène › Groupe")
        m.addMenu(lay_sub)
        a_zoom = m.addAction("🔍 Zoom live sur cette fréquence")
        a_ren = m.addAction("Renommer…")
        a_qn = m.addAction("✏ Nommer la sélection (HF 1, HF 2…)…")
        a_fd = m.addAction("⇣ Numéroter vers le bas depuis la 1ʳᵉ ligne")
        a_thr = m.addAction("Seuil propre à la fréquence…")
        a_thr0 = m.addAction("Revenir au seuil global")
        a_occ0 = m.addAction("Remettre l'occupation à zéro")
        m.addSeparator()
        a_del = m.addAction("Supprimer")
        act = m.exec(self.watch_table.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_zoom:
            self.zoom_on(rows[0])
        elif act is a_thr:
            w0 = self.watch[rows[0]]
            cur = w0["thr"] if w0["thr"] is not None else self.thr_spin.value()
            v, ok = QtWidgets.QInputDialog.getDouble(
                self, "Seuil propre", f"Seuil « occupé » (dBm) pour {len(rows)} fréquence(s) :", cur, -140.0, 20.0, 1)
            if ok:
                for r in rows:
                    self.watch[r]["thr"] = v
                self.update_watch_table(force=True)
        elif act is a_thr0:
            for r in rows:
                self.watch[r]["thr"] = None
            self.update_watch_table(force=True)
        elif act is a_occ0:
            for r in rows:
                self.watch[r]["occw"].clear()
            self.update_watch_table(force=True)
        elif act is a_qn:
            self.quick_name_dialog(rows)
        elif act is a_fd:
            self.fill_down_names(rows)
        elif act is a_ren:
            w = self.watch[rows[0]]
            txt, ok = self.ask_name("name", "Renommer", f"Nom de {w['freq']:.3f} MHz :", w["name"])
            if ok and txt.strip():
                w["name"] = txt.strip()
                self.update_watch_table(force=True)
                self._update_markers()
        elif act is a_del:
            self.del_watch()
        elif self._assign_action(rows, act.data()):
            pass
        elif act.data() is not None:
            self.set_status_rows(rows, act.data())

    def add_watch_dialog(self):
        f, ok = QtWidgets.QInputDialog.getDouble(self, "Ajouter une fréquence", "Fréquence (MHz) :",
                                                 500.0, 0.1, 6000.0, 3)
        if ok:
            sc, gr = self._scope_preset()
            self._append_watch(f"{f:.3f}", f, scene=sc, group=gr)
            self.sort_watch()
            self.rebuild_watch_table()
            self._update_markers()

    def del_watch(self):
        for r in reversed(self._sel_rows()):
            self.watch.pop(r)
        self.rebuild_watch_table()
        self._update_markers()

    def edit_statuses(self):
        dlg = StatusDialog(self, self.statuses)
        if not dlg.exec():
            return
        rows = dlg.result_rows()
        for w in self.watch:
            new = ""
            for s in rows:
                if s["orig"] is not None and s["orig"] == w["status"]:
                    new = s["name"]
                    break
            w["status"] = new
        self.statuses = [dict(name=s["name"], color=s["color"], free=bool(s.get("free")), on=bool(s.get("on")))
                         for s in rows]
        self.update_watch_table(force=True)
        self._update_markers()

    def edit_colors(self):
        dlg = ColorsDialog(self, self.theme, self.preview_theme)
        if dlg.exec():
            self.theme = dict(dlg.theme)
        self.apply_theme()

    def preview_theme(self, t):
        self.theme = dict(t)
        self.apply_theme()

    # ---------------------------------------------------- import / export
    def _resolve_status(self, st):
        if not st:
            return ""
        for s in self.statuses:
            if s["name"].lower() == st.lower():
                return s["name"]
        self.statuses.append(dict(name=st, color=STATUS_AUTO_COLORS[len(self.statuses) % len(STATUS_AUTO_COLORS)],
                                  free=False, on=False))
        return st

    def import_watch(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Importer des fréquences", "", "CSV / texte (*.csv *.txt *.tsv);;Tous les fichiers (*)")
        for p in paths:
            self.open_import(decode_text(Path(p).read_bytes()), os.path.basename(p), preset=self._scope_preset())

    def paste_watch(self):
        txt, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Coller une liste", "Colle un tableau (Excel, WWB, WSM, Wisycom…) ou une fréquence par ligne :")
        if ok and txt.strip():
            self.open_import(txt, "Texte collé", preset=self._scope_preset())

    def open_import(self, text, source, preset=("", "")):
        dlg = ImportDialog(self, text, source, self.scenes, preset)
        if not dlg.an["data"]:
            QtWidgets.QMessageBox.information(self, APP_NAME, f"Aucune fréquence reconnue dans « {source} ».")
            return
        if not dlg.exec():
            return
        entries = dlg.entries()
        if dlg.replace():
            self.watch.clear()
        by_key = {int(round(w["freq"] * 1000)): w for w in self.watch}
        added = moved = 0
        for name, f, st, sc, gr in entries:
            k = int(round(f * 1000))
            if k in by_key:
                w = by_key[k]
                if (sc or gr) and not w["scene"] and not w["group"]:
                    if gr and not sc:
                        sc = DEFAULT_SCENE
                    self.ensure_group(sc, gr)
                    w["scene"], w["group"] = sc, gr
                    moved += 1
                continue
            self._append_watch(name, f, self._resolve_status(st), None, sc, gr)
            by_key[k] = self.watch[-1]
            added += 1
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        extra = f", {moved} rangée(s) dans leur groupe" if moved else ""
        self.set_status(f"{added} fréquence(s) importée(s) depuis {source} "
                        f"({len(entries) - added} déjà présente(s){extra}).")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            p = u.toLocalFile()
            if p and Path(p).suffix.lower() in (".csv", ".txt", ".tsv"):
                self.open_import(decode_text(Path(p).read_bytes()), os.path.basename(p),
                                 preset=self._scope_preset())

    def export_watch(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter", "frequences.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                wr = csv.writer(f, delimiter=";")
                wr.writerow(["Nom", "MHz", "Statut", "Scène", "Groupe", "Niveau dBm", "Max dBm", "Signal",
                             "Seuil dBm", "Occupation %", "Spectre"])
                for w in self.watch:
                    pct = w["occw"].pct()
                    wr.writerow([w["name"], fmt_comma(w["freq"]), w["status"], w["scene"], w["group"],
                                 "" if w["level"] is None else fmt_comma(w["level"], 1),
                                 "" if w["max"] is None else fmt_comma(w["max"], 1), SIG_TEXT[w["state"]],
                                 "" if w["thr"] is None else fmt_comma(w["thr"], 1),
                                 "" if pct is None else fmt_comma(pct, 0), w["band"]])

    def bands_from_list(self):
        ws = self.scope_ws()
        if not ws:
            QtWidgets.QMessageBox.information(self, APP_NAME, "La liste de fréquences (ou la couche active) est vide.")
            return
        fs = sorted(w["freq"] for w in ws)
        groups, cur = [], [fs[0]]
        for f in fs[1:]:
            if f - cur[-1] <= 20.0:
                cur.append(f)
            else:
                groups.append(cur)
                cur = [f]
        groups.append(cur)
        new = [(f"{g[0]:.0f}–{g[-1]:.0f} MHz", max(0.1, g[0] - 0.5), g[-1] + 0.5, 200.0) for g in groups]
        tot = sum(int((b[2] - b[1]) * 1000 / b[3]) + 1 for b in new)
        r = QtWidgets.QMessageBox.question(
            self, APP_NAME, f"Remplacer les bandes actuelles par {len(new)} bande(s) "
                            f"couvrant {'la couche active' if self.scope else 'ta liste'} "
                            f"({tot} points au total, pas de 200 kHz) ?")
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            with self.lock:
                self.bands.clear()
            for d in (self.latest, self.maxhold, self.partial_data):
                d.clear()
            for b in new:
                self._append_band(*b)
            self._bands_changed()

    # -------------------------------------------------------------- journal
    def log_event(self, w, level, event):
        t = self.log_table
        t.insertRow(0)
        vals = [datetime.now().strftime("%H:%M:%S"), w["name"], f'{w["freq"]:.3f}', f"{level:.1f}", event,
                self.layer_text(w) if "scene" in w else "", w.get("note", "")]
        col = (self.theme["st_occ"] if event in ("OCCUPÉ", "CONFLIT", "ABSENT") else self.theme["st_unk"]
               if event == "INCONNU" else self.theme["st_free"])
        self._auto_log(vals, w)
        for c, v in enumerate(vals):
            it = self._item(v, False, c in (2, 3))
            if c == 4:
                it.setForeground(QtGui.QColor(col))
            t.setItem(0, c, it)
        while t.rowCount() > 2000:
            t.removeRow(t.rowCount() - 1)

    def on_log_dbl(self, row, col):
        it = self.log_table.item(row, 4)
        if it is None or it.text() != "INCONNU":
            return
        f = _num(self.log_table.item(row, 2).text())
        if f is None:
            return
        sc, gr = self._scope_preset()
        self._append_watch(f"Nouveau {f:.3f}", f, scene=sc, group=gr)
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        self.set_status(f"{f:.3f} MHz ajoutée à la liste (renomme-la : clic droit › Renommer).")

    def export_log(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter le journal", "journal.csv", "CSV (*.csv)")
        if not path:
            return
        t = self.log_table
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f, delimiter=";")
            wr.writerow(["Heure", "Nom", "MHz", "dBm", "Événement", "Scène › Groupe", "Note"])
            for r in range(t.rowCount() - 1, -1, -1):
                wr.writerow([t.item(r, c).text() for c in range(7)])

    # --------------------------------------------------------- données live
    def on_sweep(self, bid, f, l):
        self.partial_data.pop(bid, None)
        old = self.latest.get(bid)
        if (old is not None and old[0].shape == f.shape and abs(old[0][0] - f[0]) < 1e-6
                and abs(old[0][-1] - f[-1]) < 1e-6):
            self.history.setdefault(bid, deque(maxlen=20)).append(old)
        else:
            self.history.pop(bid, None)
        self.latest[bid] = (f, l)
        self.latest_t[bid] = time.time()
        if bid != ZOOM_ID:
            if self._t_start is None:
                self._t_start = self.latest_t[bid]
            self.store.add(bid, self.latest_t[bid], f, l)
            if self.recorder is not None:
                self.recorder.add(bid, self.latest_t[bid], f, l)
        mh = self.maxhold.get(bid)
        self.maxhold[bid] = np.maximum(mh, l) if (mh is not None and mh.shape == l.shape) else l.copy()
        self.update_watch_levels()
        self.update_watch_table()
        if self.unk_chk.isChecked():
            self.detect_unknown(bid, f, l)
        if self.view_id in (-1, bid):
            self.update_plot()
        if self.view_id == bid:
            self.update_waterfall(bid, f, l)

    def on_partial(self, bid, f, l, i, n):
        self.partial_data[bid] = (f, l)
        name = next((b["name"] for b in self.scan_bands() if b["id"] == bid), "Zoom")
        self.set_status(f"Balayage « {name} » : segment {i}/{n}")
        if self.view_id in (-1, bid):
            self.update_plot(hist=False)

    def on_cycle(self, dt, nb):
        self.last_cycle = dt
        ids = {b["id"] for b in self.scan_bands() if b["enabled"]}
        if self._zoom is not None:
            ids.add(ZOOM_ID)
        for k in list(self.latest):
            if k not in ids:
                for d in (self.latest, self.maxhold, self.unk_now, self.history):
                    d.pop(k, None)
        ws = self.scope_ws()
        occ = sum(1 for w in ws if w["state"] == "occ")
        conf = sum(1 for w in ws if w["state"] == "occ" and self.is_keep_free(w["status"]))
        absn = sum(1 for w in ws if w.get("absent"))
        mode = "ZOOM · " if self._zoom is not None else ("🎯 " if self._focus_bands else "")
        self.cycle_lbl.setText(f"{mode}Cycle {dt:.2f} s · {nb} bande(s) · {len(ws)} fréq. · "
                               f"{occ} occupée(s)" + (f" · {CONFLICT_TEXT} ×{conf}" if conf else "")
                               + (f" · {ABSENT_TEXT} ×{absn}" if absn else "") + "   ")

    def update_watch_levels(self):
        if not self.watch:
            return
        now = time.time()
        stale = max(15.0, 4 * self.last_cycle)
        fresh = [k for k in self.latest if now - self.latest_t.get(k, 0) <= stale]
        if not fresh:
            for w in self.watch:
                w["level"], w["state"], w["t_acc"] = None, None, None
                self._alarm_reset(w, now)
            return
        F = np.concatenate([self.latest[k][0] for k in fresh])
        L = np.concatenate([self.latest[k][1] for k in fresh])
        o = np.argsort(F)
        F, L = F[o], L[o]
        win = self.win_spin.value() / 1000.0
        gthr, gweak, weak_on = self.thr_spin.value(), self.weak_spin.value(), self.weak_chk.isChecked()
        rel = self.ref_chk.isChecked() and self._ref_F is not None
        margin = self.ref_margin.value()
        cap = max(5.0, 2.0 * self.last_cycle)
        delay = max(float(self.absent_spin.value()), 2.0 * self.last_cycle)
        alert = conflict = absent = None
        new_prio = -1
        for w in self.watch:
            if not self.in_scope(w):
                w["t_acc"] = None
                self._alarm_reset(w, now)
                continue
            f = w["freq"]
            lvl = level_at(F, L, f, win)
            w["level"] = lvl
            if lvl is None:
                w["state"], w["t_acc"] = None, None
                self._alarm_reset(w, now)
                continue
            w["max"] = lvl if w["max"] is None else max(w["max"], lvl)
            ref_l = level_at(self._ref_F, self._ref_L, f, win) if rel else None
            thr, weak = eff_thresholds(w["thr"], ref_l, rel, margin, gthr, gweak)
            prev = w["state"]
            new = next_state(prev, lvl, thr, weak, weak_on)
            t0 = w["t_acc"]
            w["t_acc"] = now
            if t0 is not None:
                w["occw"].add(now, min(now - t0, cap), new == "occ")
            keep_free = self.is_keep_free(w["status"])
            if new == "occ" and prev != "occ":
                w["peak"], w["since"] = lvl, now
                if keep_free:
                    self.log_event(w, lvl, "CONFLIT")
                    conflict = w
                else:
                    self.log_event(w, lvl, "OCCUPÉ")
                    alert = w
            elif new == "occ":
                w["peak"] = max(w["peak"] or lvl, lvl)
            elif prev == "occ":
                self.log_event(w, w["peak"] or lvl, f"Libre ({now - w['since']:.0f} s)")
            w["state"] = new
            # ---- alarmes : CONFLIT (signal sur une fréquence « doit rester libre ») et ABSENT (« doit émettre » muette)
            fk = int(round(f * 1000))
            if new == "occ" and keep_free:
                prio = self.freq_prio(w)
                if self.alarms.raise_(("CONFLIT", fk), "CONFLIT", w["name"], f, prio, now, lvl, self.layer_text(w)):
                    new_prio = max(new_prio, prio)
            else:
                self.alarms.clear(("CONFLIT", fk), now)
            if self.is_keep_on(w["status"]):
                if new == "free":
                    fs = w.get("free_since")
                    if fs is None:
                        fs = w["free_since"] = now
                    if now - fs >= delay:
                        prio = self.freq_prio(w)
                        if self.alarms.raise_(("ABSENT", fk), "ABSENT", w["name"], f, prio, now, lvl,
                                              self.layer_text(w), f"silence depuis {now - fs:.0f} s"):
                            w["absent"] = True
                            self.log_event(dict(w, note=f"aucun signal depuis {now - fs:.0f} s"), lvl, "ABSENT")
                            absent = w
                            new_prio = max(new_prio, prio)
                else:
                    w["free_since"] = None
                    a_ = self.alarms.clear(("ABSENT", fk), now)
                    if w.get("absent") or a_ is not None:
                        w["absent"] = False
                        self.log_event(w, lvl, f"Retour ({now - a_['t0']:.0f} s)" if a_ else "Retour")
            else:
                w["free_since"] = None
                if w.get("absent"):
                    w["absent"] = False
                    self.alarms.clear(("ABSENT", fk), now)
        if conflict is not None:
            self.set_status(f"⚠ CONFLIT : {conflict['name']} ({conflict['freq']:.3f} MHz) est occupée "
                            f"alors qu'elle doit rester libre.")
        if absent is not None:
            self.set_status(f"⚠ ABSENT : {absent['name']} ({absent['freq']:.3f} MHz) n'émet plus alors qu'elle "
                            f"doit émettre.")
        if alert is not None and conflict is None and self.alert_chk.isChecked():
            QtWidgets.QApplication.beep()
        if new_prio >= 0:
            self._alarm_sound(new_prio)
            self.refresh_alarms()

    def detect_unknown(self, bid, f, l):
        """Pics au-dessus du seuil qui ne correspondent à aucune fréquence de la liste."""
        self.unk_now[bid] = []
        if len(l) < 3:
            return
        thr = self.thr_spin.value()
        mid = l[1:-1]
        idx = np.where((mid >= thr) & (mid >= l[:-2]) & (mid > l[2:]))[0] + 1
        if not len(idx):
            return
        wf = np.array([w["freq"] for w in self.watch]) if self.watch else np.array([])
        step = float(np.median(np.diff(f))) if len(f) > 1 else 0.2
        guard = self.win_spin.value() / 1000.0 + step / 2 + 0.05
        now, logged = time.time(), 0
        for i in idx[:200]:
            fr = float(f[i])
            if len(wf) and float(np.min(np.abs(wf - fr))) <= guard:
                continue
            self.unk_now[bid].append(fr)
            key = round(fr / 0.1)
            last = self.unk_seen.get(key, 0.0)
            self.unk_seen[key] = now
            if now - last > 30 and logged < 10:
                note = self.im_note(fr, step)
                self.log_event({"name": "Signal inconnu", "freq": fr, "note": note}, float(l[i]), "INCONNU")
                logged += 1

    # ------------------------------------------------------------- graphes
    def _series(self, k):
        """Courbe à afficher : le balayage en cours posé sur l'ancien (comme un vrai analyseur)."""
        part, old = self.partial_data.get(k), self.latest.get(k)
        if part is None:
            return old
        if old is None or len(part[0]) == 0:
            return part
        keep = old[0] > part[0][-1]
        return np.concatenate([part[0], old[0][keep]]), np.concatenate([part[1], old[1][keep]])

    def _fit_range(self):
        if self.view_id == -1:
            bs = [b for b in self.scan_bands() if b["enabled"]]
        else:
            bs = [b for b in self.scan_bands() if b["id"] == self.view_id]
        if not bs:
            return None
        return min(b["start"] for b in bs), max(b["stop"] for b in bs)

    def update_plot(self, hist=True):
        nan = np.array([np.nan])
        if self.view_id == -1:
            keys = [k for k in set(self.latest) | set(self.partial_data) if k != ZOOM_ID]
            keys.sort(key=lambda k: self._series(k)[0][0])
        else:
            keys = [self.view_id] if self._series(self.view_id) is not None else []
        if not keys:
            self._clear_plot()
            return
        xs, ys, mxs, mys = [], [], [], []
        for k in keys:
            f, l = self._series(k)
            xs += [f, nan]
            ys += [l, nan]
            old, mh = self.latest.get(k), self.maxhold.get(k)
            if old is not None and mh is not None and mh.shape == old[1].shape:
                mxs += [old[0], nan]
                mys += [mh, nan]
            else:
                mxs += [f, nan]
                mys += [l, nan]
        x, y = np.concatenate(xs), np.concatenate(ys)
        mx, my = np.concatenate(mxs), np.concatenate(mys)
        self._last_xy = (x, y)
        self.curve.setData(x, y)
        if self.hold_chk.isChecked():
            self.maxcurve.setData(mx, my)
        else:
            self.maxcurve.setData([], [])
        if hist:
            self._update_history(keys)
        if self._fit_x and self._zoom is None:
            rng = self._fit_range()
            if rng:
                span = rng[1] - rng[0]
                self.spec.getPlotItem().setXRange(rng[0] - 0.01 * span, rng[1] + 0.01 * span, padding=0)
            self._fit_x = False
        elif self._zoom is not None:
            self._fit_x = False
        self._update_markers()

    def _clear_plot(self):
        self.curve.setData([], [])
        self.maxcurve.setData([], [])
        self._update_history([])
        self._update_markers()

    def _update_history(self, keys):
        """Rémanence : anciens balayages en transparence dégressive."""
        n = self.persist_combo.currentData() or 0
        nan = np.array([np.nan])
        base = QtGui.QColor(self.theme["curve"])
        for i in range(max(n, len(self._hist_items))):
            xs, ys = [], []
            if i < n:
                for k in keys:
                    h = self.history.get(k)
                    if k in self.latest and h and len(h) > i:
                        f, l = h[-1 - i]
                        xs += [f, nan]
                        ys += [l, nan]
            if xs:
                while len(self._hist_items) <= i:
                    it = pg.PlotCurveItem(connect="finite")
                    it.setZValue(-1)
                    self.spec.getPlotItem().addItem(it)
                    self._hist_items.append(it)
                c = QtGui.QColor(base)
                c.setAlpha(int(150 * (1 - i / (n + 0.5))) + 20)
                self._hist_items[i].setPen(pg.mkPen(c, width=1))
                self._hist_items[i].setData(np.concatenate(xs), np.concatenate(ys))
            elif i < len(self._hist_items):
                self._hist_items[i].setData(np.array([]), np.array([]))

    def _clear_hist_pool(self):
        pi = self.spec.getPlotItem()
        for it in self._hist_items:
            pi.removeItem(it)
        self._hist_items = []

    def _marker_item(self, key):
        it = self._mk_items.get(key)
        if it is None:
            pen = pg.mkPen(key[0], width=2.0, style=Qt.PenStyle.DotLine if key[1] else Qt.PenStyle.SolidLine)
            it = pg.PlotCurveItem(pen=pen, connect="pairs")
            self.spec.getPlotItem().addItem(it)
            self._mk_items[key] = it
        return it

    def _clear_marker_pool(self):
        pi = self.spec.getPlotItem()
        for it in self._mk_items.values():
            pi.removeItem(it)
        self._mk_items = {}

    def _update_markers(self):
        vb = self.spec.getPlotItem().vb
        (x0, x1), (y0, y1) = vb.viewRange()
        vis = [w for w in self.watch if x0 <= w["freq"] <= x1 and self.in_scope(w)]
        unk = [f for lst in self.unk_now.values() for f in lst if x0 <= f <= x1]
        mode = self.mark_combo.currentData()
        groups, colors = {}, []
        for w in vis:
            col = None
            if mode == "status" and w["status"]:
                col = self.status_color(w["status"])
            elif mode == "group":
                col = self.group_color(w["scene"], w["group"])
            if col is None:
                col = self.state_color(w["state"])
            groups.setdefault((col, False), []).append(w["freq"])
            colors.append(col)
        for f in unk:
            groups.setdefault((self.theme["st_unk"], True), []).append(f)
        for key, fr in groups.items():
            a = np.array(fr)
            self._marker_item(key).setData(np.repeat(a, 2), np.tile([-130.0, 0.0], len(a)))
        for key, it in self._mk_items.items():
            if key not in groups:
                it.setData(np.array([]), np.array([]))

        show = self.names_chk.isChecked() and 0 < len(vis) <= MAX_LABELS
        pi = self.spec.getPlotItem()
        while len(self.labels) < MAX_LABELS:
            lab = pg.TextItem("", anchor=(0.5, 0))
            pi.addItem(lab, ignoreBounds=True)
            lab.setVisible(False)
            self.labels.append(lab)
        for i, lab in enumerate(self.labels):
            if show and i < len(vis):
                lab.setText(vis[i]["name"], color=colors[i])
                lab.setPos(vis[i]["freq"], y1 - 2.0 - (i % 3) * 5.5)
                lab.setVisible(True)
            else:
                lab.setVisible(False)

    def update_waterfall(self, bid, f, l):
        lr = decimate_max(l, WF_MAX_COLS)
        if self.wf_hist is None or self.wf_id != bid or self.wf_hist.shape[0] != len(lr):
            self.wf_hist = np.full((len(lr), WF_ROWS), -120.0, dtype=np.float32)
            self.wf_id = bid
        self.wf_hist = np.roll(self.wf_hist, 1, axis=1)
        self.wf_hist[:, 0] = lr
        self.wf_img.setImage(self.wf_hist, autoLevels=False, levels=(-115, -40))
        self.wf_img.setRect(QtCore.QRectF(float(f[0]), 0.0, float(f[-1] - f[0]), float(WF_ROWS)))
        self.wf.getPlotItem().setYRange(0, WF_ROWS, padding=0)

    def on_mouse(self, evt):
        pos = evt[0]
        if not self.spec.sceneBoundingRect().contains(pos):
            return
        xm = self.spec.getPlotItem().vb.mapSceneToView(pos).x()
        self._show_band_info(float(xm))
        if self._last_xy is None:
            return
        x, y = self._last_xy
        try:
            k = int(np.nanargmin(np.abs(x - xm)))
        except ValueError:
            return
        self.readout.setText(f"{x[k]:.3f} MHz   {y[k]:.1f} dBm")

    def capture(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Capture du spectre", f"spectre_{datetime.now():%Y%m%d_%H%M%S}.png", "PNG (*.png)")
        if path:
            ex = pg.exporters.ImageExporter(self.spec.getPlotItem())
            ex.parameters()["width"] = 1800
            ex.export(path)
            self.set_status(f"Capture enregistrée : {path}")

    # ----------------------------------------------------------- seuils
    def _thr_from_spin(self, v):
        if abs(self.thr_line.value() - v) > 1e-6:
            self.thr_line.setValue(v)

    def _thr_from_line(self):
        v = round(self.thr_line.value(), 1)
        if abs(self.thr_spin.value() - v) > 1e-6:
            self.thr_spin.setValue(max(-130, min(0, v)))

    def _weak_from_spin(self, v):
        if abs(self.weak_line.value() - v) > 1e-6:
            self.weak_line.setValue(v)

    def _weak_from_line(self):
        v = round(self.weak_line.value(), 1)
        if abs(self.weak_spin.value() - v) > 1e-6:
            self.weak_spin.setValue(max(-130, min(0, v)))

    def _weak_toggled(self, on):
        self.weak_spin.setEnabled(on)
        self.weak_line.setVisible(on)

    def auto_threshold(self):
        if not self.latest:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        med = float(np.median(np.concatenate([v[1] for v in self.latest.values()])))
        self.thr_spin.setValue(round(med + 10.0))
        self.weak_spin.setValue(round(med + 4.0))

    def reset_max(self):
        self.maxhold.clear()
        for w in self.watch:
            w["max"] = None
            w["occw"].clear()
        self.update_watch_table(force=True)
        self.update_plot()

    # ---------------------------------------------------------------- thème
    def apply_theme(self):
        t = self.theme
        app = QtWidgets.QApplication.instance()
        app.setStyle("Fusion")
        app.setPalette(build_palette(t))
        app.setStyleSheet(make_stylesheet(t))
        try:
            for w in (self.spec, self.wf, self.bandw):
                w.setBackground(t["plot_bg"])
                pi = w.getPlotItem()
                for ax in ("bottom", "left"):
                    a = pi.getAxis(ax)
                    a.setPen(pg.mkPen(t["plot_fg"]))
                    a.setTextPen(pg.mkPen(t["plot_fg"]))
            self.curve.setPen(pg.mkPen(t["curve"], width=1.6))
            self.maxcurve.setPen(pg.mkPen(t["maxhold"], width=1))
            self.refcurve.setPen(pg.mkPen(t["ref"], width=1.3, style=Qt.PenStyle.DashLine))
            self.thr_line.setPen(pg.mkPen(t["thr"], width=1.5, style=Qt.PenStyle.DashLine))
            self.weak_line.setPen(pg.mkPen(t["thr_weak"], width=1.2, style=Qt.PenStyle.DotLine))
            self.wf_img.setLookupTable(make_lut(t.get("wf", "Inferno")))
        except Exception:
            pass
        self._clear_marker_pool()
        self._clear_hist_pool()
        self._style_start(self.worker is not None and self.worker.isRunning())
        self.readout.setStyleSheet("font-family:Consolas,monospace;")
        self.update_strips()
        self.update_watch_table(force=True)
        self._update_markers()

    # ------------------------------------------------- pays / plan de fréquences
    def on_country(self, *_):
        self.rebuild_plan()

    def rebuild_plan(self):
        code = self.country_combo.currentData() or "FR"
        self.country = code
        self.plan = build_plan(code, self.plan_custom.get(code))
        self.tv = tv_channels(code)
        note = COUNTRY_NOTES.get(code, "")
        if code in self.plan_custom:
            note += "\n(plan modifié par toi)"
        self.country_note.setText(note + "\nIndicatif : vérifie toujours auprès du régulateur de ton pays.")
        self.update_strips()
        for w in self.watch:
            w["band"], w["cat"] = spectrum_info(w["freq"], self.plan, self.tv)
            w["sig"] = None
        self.update_watch_table(force=True)

    def edit_plan(self):
        code = self.country_combo.currentData() or "FR"
        name = dict(COUNTRIES).get(code, code)
        dlg = PlanDialog(self, name, plan_to_text(self.plan))
        if not dlg.exec():
            return
        txt = dlg.result_text()
        if txt.strip():
            self.plan_custom[code] = txt
        else:
            self.plan_custom.pop(code, None)
        self.rebuild_plan()

    def _update_legend(self):
        used = {e[3] for e in self.plan} | {e[3] for e in self.tv}
        lines = [f"<span style='color:{self.theme.get('bp_' + k, '#888')}'>■</span> {lab}"
                 for k, (lab, _c) in CATEGORIES.items() if k in used]
        self.legend_lbl.setText("<br>".join(lines))

    def update_strips(self, *_):
        pi = self.bandw.getPlotItem()
        for it in self._strip_rects:
            pi.removeItem(it)
        self._strip_rects = []
        rows = []
        if self.alloc_chk.isChecked() and self.plan:
            rows.append(self.plan)
        if self.tv_chk.isChecked() and self.tv:
            rows.append(self.tv)
        self._strip_rows = []
        self.bandw.setVisible(bool(rows))
        self._update_legend()
        if not rows:
            self.update_strip_labels()
            return
        n = len(rows)
        self.bandw.setFixedHeight(30 * n + 4)
        pi.setYRange(0, n, padding=0)
        th = self.theme
        edge = pg.mkPen(th["plot_bg"], width=1)
        for k, entries in enumerate(rows):
            y0 = n - 1 - k
            self._strip_rows.append((entries, y0))
            for (a, b, lab, cat, note) in entries:
                r = QtWidgets.QGraphicsRectItem(a, y0 + 0.06, b - a, 0.88)
                r.setBrush(pg.mkBrush(th.get("bp_" + cat, "#64748b")))
                r.setPen(edge)
                pi.addItem(r, ignoreBounds=True)
                self._strip_rects.append(r)
        self.update_strip_labels()

    def update_strip_labels(self):
        if not self._strip_rows:
            for lb in self._strip_labels:
                lb.setVisible(False)
            return
        pi = self.bandw.getPlotItem()
        x0, x1 = pi.vb.viewRange()[0]
        px = max(50.0, float(pi.vb.width())) / max(1e-6, x1 - x0)     # pixels par MHz
        th, k = self.theme, 0
        for entries, y0 in self._strip_rows:
            for (a, b, lab, cat, note) in entries:
                if b < x0 or a > x1:
                    continue
                lo, hi = max(a, x0), min(b, x1)
                nch = int((hi - lo) * px / 6.4)
                if lab.startswith("CH "):
                    txt = lab if nch >= 5 else lab[3:]
                    if nch < 2 or len(txt) > nch:
                        continue
                else:
                    if nch < 4:
                        continue
                    txt = lab if len(lab) <= nch else lab[:nch - 1] + "…"
                while len(self._strip_labels) <= k:
                    t = pg.TextItem("", anchor=(0.5, 0.5))
                    t.setFont(QtGui.QFont("Segoe UI", 8))
                    t.setZValue(5)
                    pi.addItem(t, ignoreBounds=True)
                    self._strip_labels.append(t)
                t = self._strip_labels[k]
                t.setText(txt, color=contrast_text(th.get("bp_" + cat, "#64748b")))
                t.setPos((lo + hi) / 2.0, y0 + 0.5)
                t.setVisible(True)
                k += 1
        for t in self._strip_labels[k:]:
            t.setVisible(False)

    def on_mouse_band(self, evt):
        pos = evt[0]
        if not self.bandw.sceneBoundingRect().contains(pos):
            return
        self._show_band_info(self.bandw.getPlotItem().vb.mapSceneToView(pos).x())

    def _show_band_info(self, f):
        if f > 0:
            self.band_lbl.setText(describe_freq(f, self.plan, self.tv))

    # --------------------------------------------------- options de détection
    def reeval(self, *_):
        if self.latest:
            self.update_watch_levels()
        self.update_watch_table(force=True)

    def on_occ_window(self, *_):
        m = int(self.occ_combo.currentData() or 60)
        for w in self.watch:
            w["occw"].minutes = m
        self.update_watch_table(force=True)

    # ------------------------------------------------------ courbe de référence
    def _set_ref(self, curves):
        self.ref_curves = curves
        if curves:
            F = np.concatenate([c[0] for c in curves])
            L = np.concatenate([c[1] for c in curves])
            o = np.argsort(F)
            self._ref_F, self._ref_L = F[o], L[o]
        else:
            self._ref_F = self._ref_L = None
        self.update_ref_curve()

    def update_ref_curve(self):
        if not self.ref_curves or not self.showref_chk.isChecked():
            self.refcurve.setData([], [])
            return
        nan = np.array([np.nan])
        xs, ys = [], []
        for f, l in sorted(self.ref_curves, key=lambda c: c[0][0]):
            xs += [f, nan]
            ys += [l, nan]
        self.refcurve.setData(np.concatenate(xs), np.concatenate(ys))

    def capture_ref(self, src):
        curves = []
        for k in sorted(self.latest):
            f, l = self.latest[k]
            if src == "max":
                mh = self.maxhold.get(k)
                if mh is not None and mh.shape == l.shape:
                    l = mh
            curves.append((np.array(f, dtype=float), np.array(l, dtype=float)))
        if not curves:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        self._set_ref(curves)
        self._save_ref_file(REF_PATH)
        self.reeval()
        self.set_status("Référence enregistrée (" + ("max hold" if src == "max" else "balayage actuel") +
                        "). Coche « Seuil = courbe de référence + » pour l'utiliser.")

    def _save_ref_file(self, path):
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            data = dict(version=1, created=datetime.now().isoformat(timespec="seconds"),
                        curves=[dict(f=np.round(f, 6).tolist(), l=np.round(l, 1).tolist())
                                for f, l in self.ref_curves])
            Path(path).write_text(json.dumps(data), encoding="utf-8")
            return True
        except Exception as e:
            self.set_status(f"Référence non enregistrée : {e}")
            return False

    def _load_ref_file(self, path, silent=False):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            curves = []
            for c in data["curves"]:
                f, l = np.array(c["f"], dtype=float), np.array(c["l"], dtype=float)
                if len(f) and len(f) == len(l):
                    curves.append((f, l))
            if not curves:
                raise ValueError("aucune courbe dans ce fichier")
        except FileNotFoundError:
            return False
        except Exception as e:
            if not silent:
                QtWidgets.QMessageBox.warning(self, APP_NAME, f"Référence illisible :\n{e}")
            return False
        self._set_ref(curves)
        return True

    def save_ref_as(self):
        if not self.ref_curves:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Aucune référence : capture-en une d'abord.")
            return
        d = CFG_PATH.parent / "references"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer la référence",
                                                        str(d / "reference_lieu.json"), "Référence (*.json)")
        if path and self._save_ref_file(path):
            self.set_status(f"Référence enregistrée : {path}")

    def load_ref_dialog(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Charger une référence",
                                                        str(CFG_PATH.parent / "references"),
                                                        "Référence (*.json);;Tous les fichiers (*)")
        if path and self._load_ref_file(path):
            self._save_ref_file(REF_PATH)
            self.reeval()
            self.set_status(f"Référence chargée : {os.path.basename(path)}")

    def clear_ref(self):
        self._set_ref([])
        try:
            REF_PATH.unlink()
        except Exception:
            pass
        self.reeval()
        self.set_status("Référence effacée.")

    # --------------------------------------------------------- export du scan
    def export_scan(self):
        if not self.latest:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        dlg = ExportScanDialog(self, self.export_prefs)
        if not dlg.exec():
            return
        v = dlg.values()
        self.export_prefs = v
        if v["scope"] == "view" and self.view_id in self.latest:
            keys = [self.view_id]
        else:
            keys = list(self.latest)
        keys.sort(key=lambda k: float(self.latest[k][0][0]))
        fs, live, mxs = [], [], []
        for k in keys:
            f, l = self.latest[k]
            mh = self.maxhold.get(k)
            fs.append(f)
            live.append(l)
            mxs.append(mh if (mh is not None and mh.shape == l.shape) else l)
        F, LV, MX = np.concatenate(fs), np.concatenate(live), np.concatenate(mxs)
        o = np.argsort(F, kind="stable")
        F, LV, MX = F[o], LV[o], MX[o]
        cols, names = [], []
        if v["src"] in ("live", "both"):
            cols.append(LV)
            names.append("Niveau (dBm)")
        if v["src"] in ("max", "both"):
            cols.append(MX)
            names.append("Max hold (dBm)")
        text = scan_csv(F, cols, v["unit"], v["delim"], v["dec"], v["header"], names)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exporter le scan", f"scan_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                fh.write(text)
            self.set_status(f"Scan exporté ({len(F)} points) : {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")

    # --------------------------------------------------- mur / journal auto
    def open_wall(self):
        if self.wall is None:
            self.wall = WallWindow(self)
        self.wall.show()
        self.wall.raise_()
        self.wall.activateWindow()

    # ------------------------------------------------------- vocabulaire / saisie assistée
    def vocab_all(self, kind):
        """Mots proposés pour nommer : liste de base + mots appris + ce qui existe déjà."""
        base = {"name": NAME_WORDS, "scene": SCENE_WORDS, "group": GROUP_WORDS}[kind]
        extra = list(self.vocab_user.get(kind, []))
        if kind == "name":
            extra += label_words([w["name"] for w in self.watch])
        elif kind == "scene":
            extra += [s["name"] for s in self.scenes]
        else:
            extra += [g["name"] for s in self.scenes for g in s["groups"]]
        out, seen = [], set()
        for w in list(base) + extra:
            k = w.strip().lower()
            if k and k not in seen:
                seen.add(k)
                out.append(w.strip())
        return out

    def learn_word(self, kind, word):
        word = str(word).strip()
        if word and word.lower() not in {w.lower() for w in self.vocab_all(kind)}:
            lst = self.vocab_user.setdefault(kind, [])
            lst.append(word)
            del lst[:-300]

    def name_suggestions(self):
        return name_candidates(self.vocab_all("name"), [w["name"] for w in self.watch])

    def ask_name(self, kind, title, label, text=""):
        dlg = NameDialog(self, title, label, self.vocab_all(kind), text)
        if dlg.exec():
            return dlg.value(), True
        return "", False

    def edit_vocab(self):
        cur = "\n".join(self.vocab_user.get("name", []))
        txt, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "Mon vocabulaire", "Un mot par ligne (ex. Bolero, Cor anglais…). Ils seront proposés quand tu "
                                     "nommes une fréquence. Les mots de base (MIC, HF, IEM, Intercom…) y sont déjà.", cur)
        if ok:
            words = [x.strip() for x in txt.splitlines() if x.strip()]
            self.vocab_user["name"] = []
            for w in words:
                self.learn_word("name", w)
            self.set_status(f"Vocabulaire enregistré ({len(self.vocab_user['name'])} mot(s) à toi).")

    def quick_name_dialog(self, rows=None):
        rows = list(rows) if rows else self._sel_rows()
        if not rows:
            rows = [i for i, w in enumerate(self.watch) if self.in_scope(w)]
            if not rows:
                self.set_status("Aucune fréquence à nommer.")
                return
            self.set_status(f"Aucune ligne sélectionnée : on nomme les {len(rows)} fréquence(s) de la couche active.")
        dlg = QuickNameDialog(self, rows)
        if not dlg.exec():
            return
        names = dlg.names()
        if not names:
            return
        for i, nm in zip(rows, names):
            self.watch[i]["name"] = nm
            self.watch[i]["sig"] = None
        if dlg.learn_chk.isChecked():
            self.learn_word("name", dlg.word())
        self.update_watch_table(force=True)
        self._update_markers()
        self.set_status(f"{len(rows)} fréquence(s) nommée(s) : {names[0]} … {names[-1]}")

    def fill_down_names(self, rows=None):
        rows = list(rows) if rows else self._sel_rows()
        if len(rows) < 2:
            self.set_status("Sélectionne au moins 2 lignes : la 1ʳᵉ donne le nom de départ (ex. HF 1) et les "
                            "suivantes prennent HF 2, HF 3…")
            return
        names = number_run(self.watch[rows[0]]["name"], len(rows))
        for i, nm in zip(rows, names):
            self.watch[i]["name"] = nm
            self.watch[i]["sig"] = None
        self.update_watch_table(force=True)
        self._update_markers()
        self.set_status(f"Numérotées : {names[0]} … {names[-1]}")

    # ------------------------------------------------------- intermodulation / secours
    def fresh_FL(self, use_max=False, any_age=False):
        """Spectre actuel (toutes les bandes récentes) : (F trié, L) ou (None, None)."""
        now = time.time()
        stale = max(15.0, 4 * self.last_cycle)
        keys = [k for k in self.latest if k != ZOOM_ID and (any_age or now - self.latest_t.get(k, 0) <= stale)]
        if not keys:
            return None, None
        Fs, Ls = [], []
        for k in keys:
            f, l = self.latest[k]
            mh = self.maxhold.get(k) if use_max else None
            Fs.append(f)
            Ls.append(mh if (mh is not None and mh.shape == l.shape) else l)
        F, L = np.concatenate(Fs), np.concatenate(Ls)
        o = np.argsort(F)
        return F[o], L[o]

    def view_range(self, a, b, msg=None):
        self._fit_x = False
        self.spec.getPlotItem().setXRange(a, b, padding=0)
        self.set_status((msg + " : " if msg else "") + f"vue sur {a:g} – {b:g} MHz.")

    def open_intermod(self):
        self._im_dlg = IntermodDialog(self)
        self._im_dlg.show()

    def open_intermod_for(self, f):
        self._im_dlg = IntermodDialog(self, origin=f)
        self._im_dlg.show()

    def open_rescue(self):
        self._rescue_dlg = RescueDialog(self)
        self._rescue_dlg.show()

    def im_note(self, fr, step):
        """Pour un signal inconnu : combinaison d'émetteurs actifs qui pourrait l'expliquer (IM3), sinon ''."""
        act = [w for w in self.watch if w["state"] in ("occ", "weak")]
        if len(act) < 2:
            return ""
        act.sort(key=lambda w: -(w["level"] if w["level"] is not None else -999.0))
        act = act[:25]
        rows, _info = im_explain(fr, [w["freq"] for w in act], (3,), 3, max(0.1, step * 1.5), 3)
        if not rows:
            return ""
        r = rows[0]
        return f"{IM_NAMES.get(r['order'], 'IM')} probable : " + im_formula(r["terms"], [w["name"] for w in act])

    def add_im_watches(self, items):
        """items = [(MHz, nom)] -> ajoutés à la scène « Intermod », statut « Libre » (doit rester libre)."""
        st = self._resolve_status("Libre")
        known = {int(round(w["freq"] * 1000)) for w in self.watch}
        n = 0
        for f, name in items:
            k = int(round(f * 1000))
            if k in known:
                continue
            known.add(k)
            self._append_watch(name, f, st, None, "Intermod", "Produits")
            n += 1
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        return n

    def add_free_freqs(self, freqs, scene, group):
        known = {int(round(w["freq"] * 1000)) for w in self.watch}
        n = 0
        for f in freqs:
            k = int(round(f * 1000))
            if k in known:
                continue
            known.add(k)
            self._append_watch(f"Secours {f:.3f}", f, "", None, scene, group)
            n += 1
        self.sort_watch()
        self.rebuild_watch_table()
        self._update_markers()
        return n

    def log_menu(self, pos):
        r = self.log_table.rowAt(pos.y())
        if r < 0 or r >= self.log_table.rowCount():
            return
        f = _num(self.log_table.item(r, 2).text())
        if f is None:
            return
        m = QtWidgets.QMenu(self)
        a_or = m.addAction("⚡ D'où ça peut venir ? (intermodulation)…")
        a_zoom = m.addAction("🔍 Voir sur le spectre")
        a_add = m.addAction("＋ Ajouter à ma liste")
        act = m.exec(self.log_table.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act is a_or:
            self.open_intermod_for(f)
        elif act is a_zoom:
            self.view_range(f - 1.0, f + 1.0)
        elif act is a_add:
            sc, gr = self._scope_preset()
            self._append_watch(f"Nouveau {f:.3f}", f, scene=sc, group=gr)
            self.sort_watch()
            self.rebuild_watch_table()
            self._update_markers()

    # ------------------------------------------------------- fenêtres (docks)
    def _make_dock(self, title, name, widget, area):
        d = QtWidgets.QDockWidget(title, self)
        d.setObjectName(name)
        d.setWidget(widget)
        self.addDockWidget(area, d)
        return d

    def _build_docks(self, left, ftab, ltab, wf_box):
        L, R, B = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        self.dock_set = self._make_dock("Réglages", "dock_reglages", left, L)
        self.dock_freq = self._make_dock("Fréquences et couches", "dock_freq", ftab, R)
        self.dock_log = self._make_dock("Journal", "dock_journal", ltab, R)
        self.dock_wf = self._make_dock("Waterfall", "dock_wf", wf_box, B)
        self.dock_alarm = self._make_dock("Alarmes", "dock_alarmes", self._build_alarm_panel(), B)
        self.dock_alarm.hide()
        self.docks = [self.dock_set, self.dock_freq, self.dock_log, self.dock_wf, self.dock_alarm]
        self.tabifyDockWidget(self.dock_freq, self.dock_log)
        self.dock_freq.raise_()
        self.win_menu.clear()
        for d in self.docks:
            self.win_menu.addAction(d.toggleViewAction())
        self.win_menu.addSeparator()
        for txt, fn in (("Disposition standard", self.layout_standard),
                        ("Analyseur seul (spectre + réglages + waterfall)", self.layout_analyzer),
                        ("Monitoring (liste + couches + alarmes, sans réglages)", self.layout_monitor),
                        ("Double écran : panneaux sur l'autre écran", self.layout_dual)):
            self.win_menu.addAction(txt).triggered.connect(fn)
        self.win_menu.addSeparator()
        self.win_menu.addAction("🧱 Ouvrir le mur de fréquences").triggered.connect(self.open_wall)
        self.win_menu.addAction("🧱 Mur en plein écran sur l'autre écran").triggered.connect(self.wall_other_screen)

    def _dock_sizes(self):
        self.resizeDocks([self.dock_set], [360], Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_freq], [660], Qt.Orientation.Horizontal)
        self.resizeDocks([self.dock_wf], [230], Qt.Orientation.Vertical)

    def layout_standard(self):
        L, R, B = (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea,
                   Qt.DockWidgetArea.BottomDockWidgetArea)
        for d in self.docks:
            d.setFloating(False)
            d.show()
        self.addDockWidget(L, self.dock_set)
        self.addDockWidget(R, self.dock_freq)
        self.addDockWidget(R, self.dock_log)
        self.addDockWidget(B, self.dock_wf)
        self.addDockWidget(B, self.dock_alarm)
        self.tabifyDockWidget(self.dock_freq, self.dock_log)
        self.dock_freq.raise_()
        self.dock_alarm.hide()
        if self.view_id == -1 and self._zoom is None:
            self.dock_wf.hide()      # rien à afficher en vue « toutes les bandes »
        self._dock_sizes()

    def layout_analyzer(self):
        self.layout_standard()
        self.dock_freq.hide()
        self.dock_log.hide()
        self.set_status("Disposition « analyseur » : réaffiche les panneaux par le menu 🪟 Fenêtres.")

    def layout_monitor(self):
        self.layout_standard()
        self.dock_set.hide()
        self.dock_wf.hide()
        self.dock_alarm.show()
        self.set_status("Disposition « monitoring » : réaffiche les panneaux par le menu 🪟 Fenêtres.")

    def _other_screen(self):
        cur = self.screen()
        for s in QtGui.QGuiApplication.screens():
            if s != cur:
                return s
        return None

    def layout_dual(self):
        scr = self._other_screen()
        if scr is None:
            self.set_status("Un seul écran détecté. Branche le 2ᵉ écran, ou tire les panneaux par leur barre de "
                            "titre : ils deviennent des fenêtres libres.")
            return
        self.layout_standard()
        g = scr.availableGeometry()
        half = g.width() // 2
        for d in (self.dock_freq, self.dock_log, self.dock_wf):
            d.setFloating(True)
        self.dock_freq.setGeometry(QtCore.QRect(g.x(), g.y(), half, g.height()))
        self.dock_log.setGeometry(QtCore.QRect(g.x() + half, g.y(), g.width() - half, g.height() // 2))
        self.dock_wf.setGeometry(QtCore.QRect(g.x() + half, g.y() + g.height() // 2, g.width() - half,
                                              g.height() - g.height() // 2))
        self.set_status("Panneaux placés sur l'autre écran (tu peux les déplacer / les ré-accrocher à la souris).")

    def wall_other_screen(self):
        scr = self._other_screen()
        self.open_wall()
        if scr is None:
            self.set_status("Un seul écran détecté : le mur est ouvert en fenêtre (F11 pour le plein écran).")
            return
        wh = self.wall.windowHandle()
        if wh is not None:
            wh.setScreen(scr)
        self.wall.move(scr.geometry().topLeft())
        self.wall.showFullScreen()

    def _wf_show(self, on):
        self.wf.setVisible(bool(on))
        self.wf_hint.setVisible(not on)
        if on and getattr(self, "dock_wf", None) is not None:
            self.dock_wf.show()

    # ------------------------------------------------------- statuts / priorités
    def is_keep_on(self, name):
        return bool(name) and any(s["name"] == name and s.get("on") for s in self.statuses)

    def freq_prio(self, w):
        """Priorité des alarmes d'une fréquence = celle de son groupe (2 critique, 1 normale, 0 info)."""
        sc = self.scene_by_name(w["scene"]) if w["scene"] else None
        if sc is not None and w["group"]:
            for g in sc["groups"]:
                if g["name"] == w["group"]:
                    return int(g.get("prio", 1))
        return 1

    def set_prio(self, key, prio):
        sc = self.scene_by_name(key[0])
        if sc is None:
            return
        for g in sc["groups"]:
            if not key[1] or g["name"] == key[1]:
                g["prio"] = int(prio)
        self.rebuild_tree()
        what = f"« {key[1]} »" if key[1] else f"tous les groupes de « {key[0]} »"
        self.set_status(f"Priorité des alarmes pour {what} : {ALARM_PRIO[int(prio)]}."
                        + (" Critique = son répété toutes les 10 s jusqu'à acquittement." if prio == 2 else "")
                        + (" Info = pas de son." if prio == 0 else ""))

    @staticmethod
    def prio_mark(g):
        return {2: "  ❗", 0: "  🔕"}.get(int(g.get("prio", 1)), "")

    # ------------------------------------------------------- alarmes
    def _alarm_reset(self, w, now):
        """La fréquence n'est plus évaluée (hors couche, pas de mesure…) : ses alarmes s'arrêtent."""
        w["free_since"] = None
        w["absent"] = False
        fk = int(round(w["freq"] * 1000))
        self.alarms.clear(("CONFLIT", fk), now)
        self.alarms.clear(("ABSENT", fk), now)

    def _alarm_sound(self, prio):
        if prio < 0:
            return
        if prio >= 2 and getattr(self, "dock_alarm", None) is not None:
            self.dock_alarm.show()
            self.dock_alarm.raise_()
        if prio < 1 or not self.alert_chk.isChecked():
            return
        QtWidgets.QApplication.beep()
        QtCore.QTimer.singleShot(260, QtWidgets.QApplication.beep)
        if prio >= 2:
            QtCore.QTimer.singleShot(520, QtWidgets.QApplication.beep)

    def _alarm_tick(self):
        """Chaque seconde : nettoie les alarmes de fréquences supprimées, rejoue les critiques, met l'écran à jour."""
        now = time.time()
        if self.alarms.active:
            fks = {int(round(w["freq"] * 1000)) for w in self.watch}
            for key in [k for k in self.alarms.active if k[1] not in fks]:
                self.alarms.clear(key, now)
        for a in self.alarms.due_repeat(now):
            self._alarm_sound(a["prio"])
        if self.recorder is not None:
            self.recorder.maybe_flush(now)
            if self.recorder.error:
                self.set_status(f"⚠ Enregistrement arrêté : {self.recorder.error}")
                self.rec_chk.setChecked(False)
        self.refresh_alarms()

    def refresh_alarms(self):
        n_un, n_act, _pm = self.alarms.counts()
        th = self.theme
        if n_un:
            self.alarm_btn.setText(f"🔔 {n_un}")
            self.alarm_btn.setStyleSheet("QPushButton{background:%s;color:%s;font-weight:bold;}"
                                         % (th["st_occ"], contrast_text(th["st_occ"])))
        elif n_act:
            self.alarm_btn.setText(f"🔕 {n_act}")
            self.alarm_btn.setStyleSheet("QPushButton{background:%s;color:%s;}" % (th["st_weak"], contrast_text(th["st_weak"])))
        else:
            self.alarm_btn.setText("🔔")
            self.alarm_btn.setStyleSheet("")
        if not self.alarm_table.isVisible():
            return                      # panneau caché : seul le bouton 🔔 est tenu à jour
        self.alarm_lbl.setText(f"{n_un} à acquitter · {n_act} en cours · {len(self.alarms.done)} terminée(s)")
        now = time.time()
        items = self.alarms.listing()[:200]
        t, base = self.alarm_table, th["ui_base"]
        t.setRowCount(len(items))
        for r, a in enumerate(items):
            active = a["t_end"] is None
            end = now if active else a["t_end"]
            state = ("à acquitter" if not a["acked"] else "acquittée") if active else "terminée"
            vals = (ALARM_PRIO.get(a["prio"], "?"), a["kind"], a["name"], f'{a["freq"]:.3f}', fmt_clock(a["t0"]),
                    fmt_dur(end - a["t0"]), "—" if a["level"] is None else f'{a["level"]:.1f}', a["layer"], state)
            for c, v in enumerate(vals):
                it = self._item(v, False, c in (3, 6))
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, a["id"])
                if active and not a["acked"]:
                    bg = blend(th["st_occ"], base, 0.9 if a["prio"] >= 2 else 0.6)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                elif active:
                    bg = blend(th["st_weak"], base, 0.35)
                    it.setBackground(QtGui.QColor(bg))
                    it.setForeground(QtGui.QColor(contrast_text(bg)))
                else:
                    it.setForeground(QtGui.QColor(th["st_none"]))
                t.setItem(r, c, it)

    def _alarm_selected_ids(self):
        rows = sorted({i.row() for i in self.alarm_table.selectedIndexes()})
        out = []
        for r in rows:
            it = self.alarm_table.item(r, 0)
            if it is not None and it.data(Qt.ItemDataRole.UserRole) is not None:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

    def ack_selected(self):
        ids = self._alarm_selected_ids()
        n = sum(1 for i in ids if self.alarms.ack(i))
        self.refresh_alarms()
        self.set_status(f"{n} alarme(s) acquittée(s)." if n else "Sélectionne une alarme en cours à acquitter.")

    def ack_all_alarms(self):
        n = self.alarms.ack_all()
        self.refresh_alarms()
        self.set_status(f"{n} alarme(s) acquittée(s)." if n else "Aucune alarme à acquitter.")

    def purge_alarms(self):
        n = self.alarms.purge_done()
        self.refresh_alarms()
        self.set_status(f"{n} alarme(s) terminée(s) effacée(s).")

    def alarm_jump(self, row, col):
        it = self.alarm_table.item(row, 3)
        f = _num(it.text()) if it is not None else None
        if f is not None:
            self.view_range(f - 1.0, f + 1.0)

    def toggle_alarm_dock(self):
        d = self.dock_alarm
        if d.isVisible():
            d.hide()
        else:
            d.show()
            d.raise_()

    def _build_alarm_panel(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(6, 4, 6, 4)
        self.alarm_table = QtWidgets.QTableWidget(0, 9)
        self.alarm_table.setHorizontalHeaderLabels(["Prio", "Type", "Nom", "MHz", "Depuis", "Durée", "Niveau",
                                                    "Scène › Groupe", "État"])
        hh = self.alarm_table.horizontalHeader()
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.alarm_table.verticalHeader().setVisible(False)
        self.alarm_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.alarm_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.alarm_table.cellDoubleClicked.connect(self.alarm_jump)
        self.alarm_lbl = self._elastic(QtWidgets.QLabel(""))
        b_ack = QtWidgets.QPushButton("✔ Acquitter la sélection")
        b_ack.setToolTip("Coupe le son de l'alarme sans l'effacer : elle reste affichée tant que la cause est là.")
        b_ack.clicked.connect(lambda *_: self.ack_selected())
        b_all = QtWidgets.QPushButton("✔✔ Tout acquitter")
        b_all.clicked.connect(lambda *_: self.ack_all_alarms())
        b_clr = QtWidgets.QPushButton("🗑 Effacer les terminées")
        b_clr.clicked.connect(lambda *_: self.purge_alarms())
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(self.alarm_lbl, 1)
        bar.addLayout(self._flow(b_ack, b_all, b_clr), 2)
        lay.addLayout(bar)
        lay.addWidget(self.alarm_table, 1)
        tip = QtWidgets.QLabel("⚠ CONFLIT : un signal sur une fréquence « Doit rester libre » · ⚠ ABSENT : une fréquence "
                               "« Doit émettre » reste sans signal. Double-clic = voir sur le spectre. Priorité "
                               "(Critique ❗ / Normale / Info 🔕) : clic droit sur un groupe. Critique = son répété "
                               "toutes les 10 s jusqu'à acquittement.")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        return w

    # ------------------------------------------------------- scans WSM / WWB
    def import_scan_as_ref(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Importer un scan (export WSM, WWB, CSV…)", "", "Scans (*.csv *.txt);;Tous les fichiers (*)")
        if not path:
            return
        try:
            F, L, info = parse_scan_text(decode_text(Path(path).read_bytes()))
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Scan illisible :\n{e}")
            return
        self._set_ref([(F, L)])
        self._save_ref_file(REF_PATH)
        self.showref_chk.setChecked(True)
        self.reeval()
        kind = "export WSM" if info["fmt"] == "wsm" else "fichier fréquence, niveau"
        self.set_status(f"Scan importé comme référence ({kind}) : {len(F)} points, {F[0]:.3f} – {F[-1]:.3f} MHz"
                        + (f" · {info['note']}" if info.get("note") else "")
                        + ". Courbe en pointillés ; coche « Seuil = courbe de référence + » pour l'utiliser.")

    def convert_wsm_wwb(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Scans exportés de WSM à convertir pour WWB", "", "Scans WSM (*.csv *.txt);;Tous les fichiers (*)")
        if not paths:
            return
        done, errs, notes = [], [], []
        for p in paths:
            try:
                text, info = wsm_to_wwb_text(decode_text(Path(p).read_bytes()))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p)} : {e}")
                continue
            dflt = Path(p).with_name(Path(p).stem + "_WWB.csv")
            if len(paths) == 1:
                out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Enregistrer le fichier pour WWB", str(dflt),
                                                               "CSV (*.csv)")
                if not out:
                    return
            else:
                out, k = dflt, 2
                while Path(out).exists():
                    out = dflt.with_name(f"{dflt.stem} ({k}).csv")
                    k += 1
            try:
                with open(out, "w", newline="", encoding="utf-8") as fh:
                    fh.write(text)
                done.append(os.path.basename(str(out)))
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p)} : {e}")
                continue
            if info["fmt"] != "wsm":
                notes.append(os.path.basename(p))
        if done:
            msg = f"{len(done)} fichier(s) converti(s) pour WWB : {', '.join(done[:3])}" + (" …" if len(done) > 3 else "")
            if notes:
                msg += f" · ⚠ {len(notes)} ne ressemblai(en)t pas à un export WSM (converti comme « fréquence, niveau »)"
            self.set_status(msg + ". Dans WWB : importe-le comme un scan.")
        if errs:
            QtWidgets.QMessageBox.warning(self, APP_NAME, "Conversion impossible pour :\n" + "\n".join(errs))

    def export_scan_wwb(self):
        F, L = self.fresh_FL(use_max=True, any_age=True)
        if F is None:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Lance d'abord un balayage (▶ Démarrer).")
            return
        choice, ok = QtWidgets.QInputDialog.getItem(self, "Scan pour WWB", "Quelle courbe envoyer à WWB ?",
                                                    ["Max hold (recommandé)", "Balayage actuel"], 0, False)
        if not ok:
            return
        if choice.startswith("Balayage"):
            F, L = self.fresh_FL(use_max=False, any_age=True)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter le scan pour WWB",
                                                        f"scan_WWB_{datetime.now():%Y%m%d_%H%M%S}.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                fh.write(wwb_scan_text(F, L))
            self.set_status(f"Scan WWB exporté ({len(F)} points, {F[0]:.3f} – {F[-1]:.3f} MHz) : {path}")
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")

    # ------------------------------------------------------- enregistrement / relecture
    def toggle_rec(self, on):
        if on:
            d = self.log_dir / "enregistrements" / f"{datetime.now():%Y%m%d_%H%M%S}"
            self.recorder = SweepRecorder(d)
            self.rec_lbl.setText(f"Enregistrement → {d}")
            self.set_status("Enregistrement des balayages en cours (relecture : 🔧 Outils › ⏪ Relecture).")
        else:
            self._rec_stop()

    def _rec_stop(self):
        r, self.recorder = self.recorder, None
        if r is None:
            return
        r.close()
        self.rec_lbl.setText(f"Enregistrement terminé : {r.n_sweeps} balayages" + (f" · ⚠ {r.error}" if r.error else "")
                             + f"  ({r.folder})")

    def open_replay(self):
        self._replay = ReplayDialog(self)
        self._replay.show()

    # ------------------------------------------------------- rapport de show
    def collect_report(self, v):
        now = datetime.now()
        t = self.log_table
        events = [tuple(t.item(r, c).text() if t.item(r, c) is not None else "" for c in range(7))
                  for r in range(t.rowCount() - 1, -1, -1)]
        per = {}
        for e in events:
            d = per.setdefault(e[2], dict(events=0, conflicts=0, absents=0, occ=0))
            d["events"] += 1
            k = e[4].split(" (")[0]
            if k == "CONFLIT":
                d["conflicts"] += 1
            elif k == "ABSENT":
                d["absents"] += 1
            elif k == "OCCUPÉ":
                d["occ"] += 1
        rows = []
        for w in self.watch:
            d = per.get(f'{w["freq"]:.3f}', {})
            rows.append(dict(name=w["name"], freq=w["freq"], status=w["status"] or "", layer=self.layer_text(w),
                             max=w["max"], occ_pct=w["occw"].pct(), events=d.get("events", 0),
                             conflicts=d.get("conflicts", 0), absents=d.get("absents", 0), occ_events=d.get("occ", 0)))
        groups = []

        def add_group(label, ws, prio=""):
            if not ws:
                return
            ds = [per.get(f'{w["freq"]:.3f}', {}) for w in ws]
            groups.append(dict(name=label, n=len(ws), occ=sum(1 for w in ws if w["state"] == "occ"),
                               events=sum(d.get("events", 0) for d in ds), conflicts=sum(d.get("conflicts", 0) for d in ds),
                               absents=sum(d.get("absents", 0) for d in ds), prio=prio))

        for sc in self.scenes:
            for g in sc["groups"]:
                add_group(f'{sc["name"]} › {g["name"]}', [w for w in self.watch if w["scene"] == sc["name"] and w["group"] == g["name"]],
                          ALARM_PRIO.get(int(g.get("prio", 1)), ""))
            add_group(sc["name"] + " (sans groupe)", [w for w in self.watch if w["scene"] == sc["name"] and not w["group"]])
        add_group("Sans scène", [w for w in self.watch if not w["scene"]])
        F, L = self.fresh_FL(use_max=True, any_age=True)
        im = []
        if v.get("im") and self._im_dlg is not None:
            for r in getattr(self._im_dlg, "rows", [])[:200]:
                im.append(dict(f=r["f"], order=IM_NAMES.get(r["order"], str(r["order"])), text=r["text"], tname=r["tname"],
                               delta="" if r["delta"] is None else f'{r["delta"] * 1000:+.0f}', verdict=r["verdict"]))
        return dict(title=v["title"], venue=v["venue"], operator=v["operator"], notes=v["notes"],
                    generated=now.strftime("%d/%m/%Y %H:%M"),
                    duration=fmt_dur(time.time() - self._t_start) if self._t_start else "",
                    events=events, rows=rows, groups=groups, F=F, L=L, thr=self.thr_spin.value(), im=im,
                    app=f"{APP_NAME} {APP_VER}")

    def make_report(self):
        has_im = bool(self._im_dlg is not None and getattr(self._im_dlg, "rows", None))
        dlg = ReportDialog(self, self.report_prefs, has_im)
        if not dlg.exec():
            return
        v = dlg.values()
        self.report_prefs = dict(venue=v["venue"], operator=v["operator"])
        d = self.log_dir / "rapports"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Enregistrer le rapport", str(d / f"rapport_{datetime.now():%Y%m%d_%H%M}.html"), "Page web (*.html)")
        if not path:
            return
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(build_report_html(self.collect_report(v)))
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Rapport impossible :\n{e}")
            return
        self.set_status(f"Rapport enregistré : {path}  (navigateur › Imprimer › Enregistrer en PDF)")
        if v["open"]:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------- export des fréquences
    def export_by_scene(self):
        if not self.watch:
            QtWidgets.QMessageBox.information(self, APP_NAME, "La liste de fréquences est vide.")
            return
        scope_idx = [i for i, w in enumerate(self.watch) if self.in_scope(w)]
        sel = self._sel_rows()
        dlg = ExportListDialog(self, len(self.watch), len(scope_idx), len(sel), self.export_list_prefs)
        if not dlg.exec():
            return
        v = dlg.values()
        self.export_list_prefs = v
        idx = {"all": list(range(len(self.watch))), "scope": scope_idx, "sel": sel}[v["src"]]
        if not idx:
            QtWidgets.QMessageBox.information(self, APP_NAME, "Aucune fréquence dans ce choix.")
            return
        base = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier où créer l'export", str(self.log_dir))
        if not base:
            return
        out = Path(base) / f"frequences_{datetime.now():%Y%m%d_%H%M}"
        rows = [dict(name=self.watch[i]["name"], freq=self.watch[i]["freq"], status=self.watch[i]["status"] or "",
                     scene=self.watch[i]["scene"], group=self.watch[i]["group"]) for i in idx]
        enc = "utf-8-sig" if v["fmt"] in ("full", "name_mhz") else "utf-8"
        used, n = set(), 0
        try:
            out.mkdir(parents=True, exist_ok=True)
            for name, rs in split_freq_rows(rows, v["split"]):
                fn, k = name, 2
                while fn.lower() in used:
                    fn = f"{name} ({k})"
                    k += 1
                used.add(fn.lower())
                with open(out / (fn + ".csv"), "w", newline="", encoding=enc) as fh:
                    fh.write(freq_list_text(rs, v["fmt"]))
                n += 1
        except Exception as e:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, APP_NAME, f"Export impossible :\n{e}")
            return
        self.set_status(f"{len(rows)} fréquence(s) exportée(s) dans {n} fichier(s) : {out}")
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(out)))

    # ------------------------------------------------------- guide des bandes
    def open_guide(self):
        name = dict(COUNTRIES).get(self.country, self.country)
        self._guide = BandGuideDialog(self, name, self.plan, self.tv, self.theme, self._guide_add, self._guide_view)
        self._guide.show()

    def _guide_add(self, label, a, b):
        a, b = max(0.1, float(a)), min(6000.0, float(b))
        if b - a < 0.05:
            mid = (a + b) / 2.0
            a, b = max(0.1, mid - 0.025), mid + 0.025
        pts = max(MIN_PTS, int(self._cfg["points"]))
        self.add_band(label, a, b, round((b - a) * 1000.0 / (pts - 1), 6))
        self.set_status(f"« {label} » ajoutée aux bandes à balayer ({pts} points).")

    def _guide_view(self, a, b):
        pad = 0.03 * (b - a)
        self._fit_x = False
        self.spec.getPlotItem().setXRange(a - pad, b + pad, padding=0)
        self.set_status(f"Vue sur {a:g} – {b:g} MHz. Pas de courbe ? Cette zone n'est pas dans tes bandes "
                        f"à balayer : utilise « Ajouter aux bandes à balayer ».")

    def _auto_log(self, vals, w):
        if not self.autolog_chk.isChecked():
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            p = self.log_dir / f"journal_{datetime.now():%Y%m%d}.csv"
            new = not p.exists()
            with open(p, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
                wr = csv.writer(fh, delimiter=";")
                if new:
                    wr.writerow(["Date", "Heure", "Nom", "MHz", "dBm", "Événement", "Statut", "Scène", "Groupe",
                                 "Spectre", "Note"])
                wr.writerow([datetime.now().strftime("%Y-%m-%d"), vals[0], vals[1], vals[2].replace(".", ","),
                             vals[3].replace(".", ","), vals[4], w.get("status", ""), w.get("scene", ""),
                             w.get("group", ""), w.get("band", ""), vals[6] if len(vals) > 6 else ""])
        except Exception as e:
            if not self._log_err_shown:
                self._log_err_shown = True
                self.set_status(f"Journal automatique impossible : {e}")

    def open_log_dir(self):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.log_dir)))

    def pick_log_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Dossier du journal automatique", str(self.log_dir))
        if d:
            self.log_dir = Path(d)
            self._log_err_shown = False
            self.logdir_lbl.setText(str(self.log_dir))

    # ---------------------------------------------------------------- close
    def closeEvent(self, e):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait(8000)
        if self.wall is not None:
            self.wall.close()
        if self.recorder is not None:
            try:
                self.recorder.close()
            except Exception:
                pass
            self.recorder = None
        if self._replay is not None:
            try:
                self._replay.close()
            except Exception:
                pass
        self._save_config()
        e.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
